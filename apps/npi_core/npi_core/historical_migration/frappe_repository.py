from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Mapping
from uuid import UUID, uuid5

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.historical_migration.bundle import inspect_bundle
from npi_core.historical_migration.domain import (
    BUNDLE_SCHEMA_VERSION,
    CORRECTION_SCHEMA_VERSION,
    JOB_SCHEMA_VERSION,
    RECONCILIATION_SCHEMA_VERSION,
    ROLLBACK_SCHEMA_VERSION,
    BundleInspection,
    HistoricalMigrationConflict,
    HistoricalMigrationPreview,
    HistoricalMigrationProductionDenied,
    MigrationAction,
    MigrationDifference,
    MigrationFamily,
    MigrationFinding,
    MigrationJobState,
    MigrationResultState,
    MigrationRow,
    TargetObservation,
    build_preview,
    sha256_json,
)
from npi_core.historical_migration.frappe_validation import historical_migration_write
from npi_core.project.domain import (
    CreateProjectCommand,
    ProjectInstantiationService,
    ProjectReferenceType,
    ProjectType,
    ReferenceSourceSystem,
    TypedReference,
)
from npi_core.project.frappe_repository import FrappeProjectRepository
from npi_core.request_security import authenticated_principal


_JOB_NAMESPACE = UUID("d5f602ca-8ca5-459c-84ae-7c057a8d44c8")
_MAX_WORKSPACE_ITEMS = 50
_REFERENCE_DOCTYPES = {
    "part": "NPI Engineering Part",
    "tooling": "NPI Tooling Master",
}
_ERP_REFERENCE_KINDS = {
    "customer": "customer_master",
    "product": "formal_item_master",
    "part": "formal_item_master",
    "tooling": "tool_asset_status",
}


@dataclass(frozen=True, slots=True)
class HistoricalMigrationOutcome:
    response: dict[str, object]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class _SourceFile:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    optimistic_version: int
    sha256: str
    frappe_file_id: str
    content: bytes


class FrappeHistoricalMigrationRepository:
    """Operation-specific P9-05 repository; it never accepts a DocType name."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        clock=None,
    ) -> None:
        if principal.is_external or "System Manager" not in principal.roles:
            raise PermissionDenied()
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._inspection: BundleInspection | None = None
        self._source: _SourceFile | None = None
        self._project_rows: dict[str, MigrationRow] = {}
        self._reference_rows: dict[str, tuple[MigrationRow, ...]] = {}

    def workspace(self) -> dict[str, object]:
        previews = self._bounded_documents(
            "NPI Historical Migration Preview",
            order_by="created_at desc, global_id desc",
        )
        jobs = self._bounded_documents(
            "NPI Historical Migration Job",
            order_by="updated_at desc, global_id desc",
        )
        return {
            "schemaVersion": BUNDLE_SCHEMA_VERSION,
            "mode": "non_production_rehearsal",
            "executionEnabled": _execution_enabled(),
            "productionContact": False,
            "previews": [self._preview_response(row) for row in previews],
            "jobs": [self._job_response(row) for row in jobs],
        }

    def create_preview(
        self,
        *,
        tenant_id: str,
        file_revision_global_id: UUID,
        file_optimistic_version: int,
        source_sha256: str,
    ) -> HistoricalMigrationOutcome:
        source = self._load_source(
            tenant_id=tenant_id,
            file_revision_global_id=file_revision_global_id,
            file_optimistic_version=file_optimistic_version,
            source_sha256=source_sha256,
        )
        inspection = inspect_bundle(source.content, expected_sha256=source.sha256)
        self._prepare_resolver(inspection, source)
        now = self._now()
        preview = build_preview(
            inspection,
            self,
            source_file_revision_global_id=source.global_id,
            source_file_optimistic_version=source.optimistic_version,
            tenant_id=source.tenant_id,
            actor=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        existing = self._optional_doc(
            "NPI Historical Migration Preview", str(preview.global_id)
        )
        if existing is not None:
            if str(existing.snapshot_hash) != preview.snapshot_hash:
                raise HistoricalMigrationConflict()
            return HistoricalMigrationOutcome(
                self._preview_response(existing), replayed=True
            )

        batch_payload = self._batch_payload(inspection, source, now)
        batch_hash = sha256_json(batch_payload)
        with historical_migration_write():
            batch = self._optional_doc(
                "NPI Historical Migration Batch", str(inspection.bundle_id)
            )
            if batch is None:
                frappe.get_doc(
                    {
                        "doctype": "NPI Historical Migration Batch",
                        "global_id": str(inspection.bundle_id),
                        "tenant_id": source.tenant_id,
                        "schema_version": BUNDLE_SCHEMA_VERSION,
                        "source_system": inspection.source_system,
                        "source_file_revision_global_id": str(source.global_id),
                        "source_file_optimistic_version": source.optimistic_version,
                        "source_sha256": source.sha256,
                        "manifest_hash": inspection.manifest_hash,
                        "predecessor_manifest_hash": inspection.predecessor_manifest_hash,
                        "batch_snapshot": _canonical_json(batch_payload),
                        "snapshot_hash": batch_hash,
                        "created_by_user_id": self.actor,
                        "created_at": _database_datetime(now),
                        "request_id": self.request_id,
                        "trace_id": self.trace_id,
                    }
                ).insert()
            elif (
                str(batch.manifest_hash) != inspection.manifest_hash
                or str(batch.source_sha256) != source.sha256
                or str(batch.snapshot_hash) != batch_hash
            ):
                raise HistoricalMigrationConflict()
            summary = preview.summary()
            frappe.get_doc(
                {
                    "doctype": "NPI Historical Migration Preview",
                    "global_id": str(preview.global_id),
                    "tenant_id": preview.tenant_id,
                    "batch_global_id": str(preview.bundle_id),
                    "manifest_hash": preview.manifest_hash,
                    "source_file_revision_global_id": str(
                        preview.source_file_revision_global_id
                    ),
                    "source_file_optimistic_version": (
                        preview.source_file_optimistic_version
                    ),
                    "optimistic_version": preview.version,
                    "create_count": summary["create"],
                    "link_count": summary["link"],
                    "skip_count": summary["skip"],
                    "blocked_count": summary["blocked"],
                    "preview_snapshot": _canonical_json(preview.snapshot_payload()),
                    "snapshot_hash": preview.snapshot_hash,
                    "created_by_user_id": preview.created_by_user_id,
                    "created_at": _database_datetime(preview.created_at),
                    "request_id": str(preview.request_id),
                    "trace_id": preview.trace_id,
                }
            ).insert()
            self._append_audit(
                operation="historical_migration.preview.create",
                global_id=preview.global_id,
                object_version=preview.version,
                result="created",
                summary={
                    "manifestHash": preview.manifest_hash,
                    "sourceSha256": preview.source_sha256,
                    "rowCount": len(preview.rows),
                    "blockedCount": summary["blocked"],
                    "productionContact": False,
                },
            )
        return HistoricalMigrationOutcome(preview.response())

    def observe(self, row: MigrationRow) -> TargetObservation:
        if self._inspection is None or self._source is None:
            raise RuntimeError("Historical migration resolver is not prepared.")
        existing_binding = self._binding_for(row)
        if existing_binding is not None:
            if str(existing_binding.source_hash) != row.source_hash:
                return self._blocked(
                    "source_key_conflict",
                    "source_key",
                    _("The source key is already bound to different source content."),
                )
            return TargetObservation(
                action=MigrationAction.SKIP,
                target_global_id=UUID(str(existing_binding.target_global_id)),
                target_version=int(existing_binding.target_version),
                target_snapshot_hash=str(existing_binding.target_snapshot_hash),
            )
        if row.family is MigrationFamily.PROJECT:
            return self._observe_project(row)
        if row.family is MigrationFamily.TOOLING_MAPPING:
            return self._observe_exact_target(
                row,
                doctype="NPI Tooling Master",
                id_field="tooling_global_id",
                version_field="target_version",
                hash_field="target_snapshot_hash",
            )
        if row.family is MigrationFamily.FILE_INDEX:
            return self._observe_exact_target(
                row,
                doctype="NPI File Revision",
                id_field="file_revision_global_id",
                version_field="file_optimistic_version",
                hash_field="file_sha256",
                stored_hash_field="sha256",
                require_clean_private_file=True,
            )
        return self._observe_reference(row)

    def queue_execution(
        self,
        *,
        preview_id: UUID,
        expected_version: int,
        expected_snapshot_hash: str,
        execution_key_hash: str,
    ) -> HistoricalMigrationOutcome:
        _require_execution_enabled()
        preview = self._locked_doc("NPI Historical Migration Preview", str(preview_id))
        if (
            int(preview.optimistic_version) != expected_version
            or str(preview.snapshot_hash) != expected_snapshot_hash
        ):
            raise HistoricalMigrationConflict()
        existing = frappe.db.get_value(
            "NPI Historical Migration Job",
            {"execution_key_hash": execution_key_hash},
            "name",
        )
        if existing:
            job = frappe.get_doc("NPI Historical Migration Job", str(existing))
            if str(job.preview_global_id) != str(preview_id):
                raise HistoricalMigrationConflict()
            return HistoricalMigrationOutcome(self._job_response(job), replayed=True)
        now = self._now()
        job_id = uuid5(_JOB_NAMESPACE, f"{preview_id}:{execution_key_hash}")
        snapshot = self._job_payload(
            job_id=job_id,
            preview=preview,
            state=MigrationJobState.QUEUED,
            version=1,
            results=[],
            queued_at=now,
            updated_at=now,
        )
        with historical_migration_write():
            job = frappe.get_doc(
                {
                    "doctype": "NPI Historical Migration Job",
                    "global_id": str(job_id),
                    "tenant_id": str(preview.tenant_id),
                    "batch_global_id": str(preview.batch_global_id),
                    "preview_global_id": str(preview.global_id),
                    "preview_snapshot_hash": str(preview.snapshot_hash),
                    "execution_key_hash": execution_key_hash,
                    "actor_user_id": self.actor,
                    "state": MigrationJobState.QUEUED.value,
                    "optimistic_version": 1,
                    "job_snapshot": _canonical_json(snapshot),
                    "snapshot_hash": sha256_json(snapshot),
                    "queued_at": _database_datetime(now),
                    "updated_at": _database_datetime(now),
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                }
            ).insert()
            self._append_audit(
                operation="historical_migration.execute.queue",
                global_id=job_id,
                object_version=1,
                result="queued",
                summary={
                    "previewGlobalId": str(preview_id),
                    "previewSnapshotHash": expected_snapshot_hash,
                    "productionContact": False,
                },
            )
            frappe.enqueue(
                "npi_core.historical_migration.frappe_repository.run_historical_migration_job",
                queue="long",
                enqueue_after_commit=True,
                job_id=str(job_id),
                expected_snapshot_hash=sha256_json(snapshot),
            )
        return HistoricalMigrationOutcome(self._job_response(job))

    def job(self, job_id: UUID) -> dict[str, object]:
        return self._job_response(frappe.get_doc("NPI Historical Migration Job", str(job_id)))

    def create_correction(
        self, job_id: UUID, *, execution_key_hash: str
    ) -> HistoricalMigrationOutcome:
        job = self._locked_doc("NPI Historical Migration Job", str(job_id))
        snapshot = _json_object(job.job_snapshot)
        results = snapshot.get("results")
        if not isinstance(results, list):
            raise RuntimeError("Persisted historical migration job is invalid.")
        failed = [
            item
            for item in results
            if isinstance(item, dict)
            and item.get("state")
            in {
                MigrationResultState.FAILED_RETRYABLE.value,
                MigrationResultState.FAILED_FINAL.value,
            }
        ]
        if not failed:
            raise RequestValidationFailed(
                [{"path": "jobId", "message": _("The job has no failed rows to correct.")}]
            )
        content = _correction_csv(failed)
        digest = hashlib.sha256(content).hexdigest()
        if job.correction_file_id:
            if str(job.correction_sha256) != digest:
                raise HistoricalMigrationConflict()
            return HistoricalMigrationOutcome(
                self._correction_response(job, content, len(failed)), replayed=True
            )
        from frappe.utils.file_manager import save_file

        file_name = f"historical-migration-correction-{job_id}.csv"
        with historical_migration_write():
            file_document = save_file(
                file_name,
                content,
                "NPI Historical Migration Job",
                str(job_id),
                is_private=1,
            )
            job.correction_file_id = str(file_document.name)
            job.correction_sha256 = digest
            self._advance_job(
                job,
                state=MigrationJobState(str(job.state)),
                results=results,
                extra={
                    "correction": {
                        **self._correction_response(job, content, len(failed)),
                        "executionKeyHash": execution_key_hash,
                    }
                },
            )
            self._append_audit(
                operation="historical_migration.correction.create",
                global_id=job_id,
                object_version=int(job.optimistic_version),
                result="created",
                summary={
                    "failedRowCount": len(failed),
                    "sha256": digest,
                    "productionContact": False,
                },
            )
        return HistoricalMigrationOutcome(
            self._correction_response(job, content, len(failed))
        )

    def correction_content(self, job_id: UUID) -> tuple[bytes, str]:
        job = frappe.get_doc("NPI Historical Migration Job", str(job_id))
        if not job.correction_file_id or not job.correction_sha256:
            raise HistoricalMigrationConflict()
        file_document = frappe.get_doc("File", str(job.correction_file_id))
        if int(file_document.is_private or 0) != 1:
            raise HistoricalMigrationConflict()
        content = _content_bytes(file_document.get_content())
        if hashlib.sha256(content).hexdigest() != str(job.correction_sha256):
            raise HistoricalMigrationConflict()
        return content, str(file_document.file_name)

    def reconcile(
        self,
        job_id: UUID,
        *,
        expected_version: int,
        expected_snapshot_hash: str,
        execution_key_hash: str,
    ) -> HistoricalMigrationOutcome:
        job = self._locked_doc("NPI Historical Migration Job", str(job_id))
        snapshot = _json_object(job.job_snapshot)
        previous_reconciliation = snapshot.get("reconciliation")
        if (
            isinstance(previous_reconciliation, dict)
            and previous_reconciliation.get("executionKeyHash") == execution_key_hash
        ):
            return HistoricalMigrationOutcome(self._job_response(job), replayed=True)
        if (
            int(job.optimistic_version) != expected_version
            or str(job.snapshot_hash) != expected_snapshot_hash
        ):
            raise HistoricalMigrationConflict()
        if str(job.state) not in {
            MigrationJobState.PARTIALLY_SUCCEEDED.value,
            MigrationJobState.SUCCEEDED.value,
            MigrationJobState.FAILED_RETRYABLE.value,
            MigrationJobState.FAILED_FINAL.value,
            MigrationJobState.RECONCILED.value,
        }:
            raise RequestValidationFailed(
                [
                    {
                        "path": "jobId",
                        "message": _(
                            "Only a completed rehearsal job can be reconciled."
                        ),
                    }
                ]
            )
        results = _result_list(snapshot)
        observations: list[dict[str, object]] = []
        mismatch_count = 0
        for result in results:
            target_id = result.get("targetGlobalId")
            expected_hash = result.get("targetSnapshotHash")
            target_type = result.get("targetDoctype")
            if not all(isinstance(value, str) and value for value in (target_id, expected_hash, target_type)):
                continue
            observed_hash = self._current_target_hash(str(target_type), str(target_id))
            state = "matched" if observed_hash == expected_hash else "changed"
            mismatch_count += state != "matched"
            observations.append(
                {
                    "family": result.get("family"),
                    "sourceKey": result.get("sourceKey"),
                    "targetGlobalId": target_id,
                    "expectedSnapshotHash": expected_hash,
                    "observedSnapshotHash": observed_hash,
                    "state": state,
                }
            )
        reconciliation = {
            "schemaVersion": RECONCILIATION_SCHEMA_VERSION,
            "jobGlobalId": str(job_id),
            "jobSnapshotHash": str(job.snapshot_hash),
            "observationCount": len(observations),
            "mismatchCount": mismatch_count,
            "items": observations,
            "executionKeyHash": execution_key_hash,
            "createdAt": _utc_text(self._now()),
        }
        with historical_migration_write():
            self._advance_job(
                job,
                state=(
                    MigrationJobState.RECONCILED
                    if mismatch_count == 0
                    else MigrationJobState.PARTIALLY_SUCCEEDED
                ),
                results=results,
                extra={"reconciliation": reconciliation},
            )
            self._append_audit(
                operation="historical_migration.reconcile",
                global_id=job_id,
                object_version=int(job.optimistic_version),
                result=("matched" if mismatch_count == 0 else "mismatch"),
                summary={
                    "observationCount": len(observations),
                    "mismatchCount": mismatch_count,
                    "productionContact": False,
                },
            )
        return HistoricalMigrationOutcome(self._job_response(job))

    def rollback(
        self,
        job_id: UUID,
        *,
        expected_version: int,
        expected_snapshot_hash: str,
        execution_key_hash: str,
    ) -> HistoricalMigrationOutcome:
        _require_execution_enabled()
        job = self._locked_doc("NPI Historical Migration Job", str(job_id))
        snapshot = _json_object(job.job_snapshot)
        previous_rollback = snapshot.get("rollback")
        if (
            isinstance(previous_rollback, dict)
            and previous_rollback.get("executionKeyHash") == execution_key_hash
        ):
            return HistoricalMigrationOutcome(self._job_response(job), replayed=True)
        if (
            int(job.optimistic_version) != expected_version
            or str(job.snapshot_hash) != expected_snapshot_hash
        ):
            raise HistoricalMigrationConflict()
        if str(job.state) not in {
            MigrationJobState.PARTIALLY_SUCCEEDED.value,
            MigrationJobState.SUCCEEDED.value,
            MigrationJobState.FAILED_RETRYABLE.value,
            MigrationJobState.FAILED_FINAL.value,
            MigrationJobState.RECONCILED.value,
        }:
            raise RequestValidationFailed(
                [
                    {
                        "path": "jobId",
                        "message": _(
                            "Only a completed rehearsal job can be evaluated for rollback."
                        ),
                    }
                ]
            )
        results = _result_list(snapshot)
        names = frappe.get_all(
            "NPI Historical Migration Target Binding",
            filters={"created_by_job_global_id": str(job_id), "state": "active"},
            pluck="name",
            order_by="binding_key_hash asc",
            limit_page_length=2001,
        )
        if len(names) > 2000:
            raise RuntimeError("Historical migration binding collection exceeds its bound.")
        decisions: list[dict[str, object]] = []
        denied = False
        with historical_migration_write():
            for name in names:
                binding = frappe.get_doc(
                    "NPI Historical Migration Target Binding", str(name), for_update=True
                )
                observed_hash = self._current_target_hash(
                    str(binding.target_doctype), str(binding.target_global_id)
                )
                project_create = str(binding.family) == MigrationFamily.PROJECT.value
                allowed = observed_hash == str(binding.target_snapshot_hash) and not project_create
                binding.state = (
                    "rolled_back" if allowed else "forward_correction_required"
                )
                binding.updated_at = _database_datetime(self._now())
                binding.save()
                denied = denied or not allowed
                decisions.append(
                    {
                        "family": str(binding.family),
                        "sourceKey": str(binding.source_key),
                        "targetGlobalId": str(binding.target_global_id),
                        "decision": (
                            "logical_binding_rolled_back"
                            if allowed
                            else "forward_correction_required"
                        ),
                        "targetRetained": True,
                    }
                )
            rollback = {
                "schemaVersion": ROLLBACK_SCHEMA_VERSION,
                "jobGlobalId": str(job_id),
                "decision": "denied" if denied else "allowed",
                "items": decisions,
                "executionKeyHash": execution_key_hash,
                "createdAt": _utc_text(self._now()),
            }
            self._advance_job(
                job,
                state=(
                    MigrationJobState.ROLLBACK_DENIED
                    if denied
                    else MigrationJobState.ROLLED_BACK
                ),
                results=results,
                extra={"rollback": rollback},
            )
            self._append_audit(
                operation="historical_migration.rollback",
                global_id=job_id,
                object_version=int(job.optimistic_version),
                result=("denied" if denied else "logical_binding_rolled_back"),
                summary={
                    "bindingCount": len(decisions),
                    "targetDeletionCount": 0,
                    "productionContact": False,
                },
            )
        return HistoricalMigrationOutcome(self._job_response(job))

    def _prepare_resolver(self, inspection: BundleInspection, source: _SourceFile) -> None:
        self._inspection = inspection
        self._source = source
        self._project_rows = {
            row.source_key.casefold(): row
            for row in inspection.rows
            if row.family is MigrationFamily.PROJECT
        }
        self._reference_rows = {
            key: tuple(
                row
                for row in inspection.rows
                if row.family is MigrationFamily.NPI_REFERENCE
                and row.value_map.get("project_source_key", "").casefold() == key
            )
            for key in self._project_rows
        }

    def _observe_project(self, row: MigrationRow) -> TargetObservation:
        assert self._source is not None
        values = row.value_map
        names = frappe.get_all(
            "NPI Engineering Project",
            filters={
                "tenant_id": self._source.tenant_id,
                "business_code": values["business_code"],
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=2,
        )
        if len(names) > 1:
            raise RuntimeError("Project business-code uniqueness is violated.")
        if not names:
            if frappe.db.get_value("User", values["owner_user_id"], "enabled") != 1:
                return self._blocked(
                    "owner_unavailable",
                    "owner_user_id",
                    _("The Project owner is unavailable."),
                )
            project_repository = FrappeProjectRepository(
                principal=self.principal,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
            template = project_repository.get_template_version(
                UUID(values["template_global_id"]), int(values["template_version"])
            )
            if template is None or template.version != int(
                values["template_expected_version"]
            ):
                return self._blocked(
                    "template_version_unavailable",
                    "template_version",
                    _("The exact Project Template version is unavailable."),
                )
            supplied_types = {
                item.value_map["reference_type"]
                for item in self._reference_rows.get(row.source_key.casefold(), ())
                if not item.findings
            }
            if any(
                rule.required and rule.reference_type.value not in supplied_types
                for rule in template.reference_rules
            ):
                return self._blocked(
                    "required_reference_missing",
                    "references",
                    _("The Project is missing a reference required by its template."),
                )
            return TargetObservation(action=MigrationAction.CREATE)
        project = frappe.get_doc("NPI Engineering Project", str(names[0]))
        expected = {
            "business_code": values["business_code"],
            "title": values["title"],
            "project_type": values["project_type"],
            "owner_user_id": values["owner_user_id"],
            "target_sop": values["target_sop"],
            "template_global_id": values["template_global_id"],
            "template_version": values["template_version"],
        }
        differences = tuple(
            MigrationDifference(
                field=field,
                source_value=str(source_value),
                target_value=str(project.get(field) or ""),
            )
            for field, source_value in expected.items()
            if str(project.get(field) or "") != str(source_value)
        )
        target_hash = self._project_hash(project)
        if differences:
            return TargetObservation(
                action=MigrationAction.BLOCKED,
                target_global_id=UUID(str(project.global_id)),
                target_version=int(project.optimistic_version),
                target_snapshot_hash=target_hash,
                differences=differences,
                findings=(
                    MigrationFinding(
                        "target_difference",
                        "project",
                        _("The existing Project differs from the historical source."),
                    ),
                ),
            )
        return TargetObservation(
            action=MigrationAction.LINK,
            target_global_id=UUID(str(project.global_id)),
            target_version=int(project.optimistic_version),
            target_snapshot_hash=target_hash,
        )

    def _observe_exact_target(
        self,
        row: MigrationRow,
        *,
        doctype: str,
        id_field: str,
        version_field: str,
        hash_field: str,
        stored_hash_field: str = "snapshot_hash",
        require_clean_private_file: bool = False,
    ) -> TargetObservation:
        values = row.value_map
        document = self._optional_doc(doctype, values[id_field])
        if document is None:
            return self._blocked(
                "target_unavailable", id_field, _("The exact migration target is unavailable.")
            )
        if require_clean_private_file and (
            str(document.scan_state) != "clean"
            or int(document.is_private or 0) != 1
            or not str(document.file).startswith("/private/files/")
        ):
            return self._blocked(
                "file_not_clean_private",
                id_field,
                _("The exact clean private File Revision is unavailable."),
            )
        observed_version = int(
            document.get("optimistic_version")
            or document.get("current_revision_number")
            or 0
        )
        observed_hash = str(document.get(stored_hash_field) or "")
        differences: list[MigrationDifference] = []
        if observed_version != int(values[version_field]):
            differences.append(
                MigrationDifference(
                    version_field, values[version_field], str(observed_version)
                )
            )
        if observed_hash != values[hash_field]:
            differences.append(
                MigrationDifference(hash_field, values[hash_field], observed_hash)
            )
        if differences:
            return TargetObservation(
                action=MigrationAction.BLOCKED,
                target_global_id=UUID(str(document.global_id)),
                target_version=max(observed_version, 1),
                target_snapshot_hash=(
                    observed_hash
                    if len(observed_hash) == 64
                    else sha256_json({"invalidTargetHash": True})
                ),
                differences=tuple(differences),
                findings=(
                    MigrationFinding(
                        "target_version_or_hash_changed",
                        id_field,
                        _("The exact migration target version or hash changed."),
                    ),
                ),
            )
        return TargetObservation(
            action=MigrationAction.LINK,
            target_global_id=UUID(str(document.global_id)),
            target_version=observed_version,
            target_snapshot_hash=observed_hash,
        )

    def _observe_reference(self, row: MigrationRow) -> TargetObservation:
        values = row.value_map
        if values["source_system"] == "ERPNEXT":
            projection_kind = _ERP_REFERENCE_KINDS.get(values["reference_type"])
            if projection_kind is None:
                return self._blocked(
                    "erp_reference_not_supported",
                    "reference_type",
                    _("This ERP-owned reference type cannot be migrated as editable data."),
                )
            name = frappe.db.get_value(
                "NPI ERP Projection Head",
                {
                    "source_object_id": values["source_object_id"],
                    "projection_kind": projection_kind,
                },
                "name",
            )
            if not name:
                return self._blocked(
                    "erp_projection_unavailable",
                    "source_object_id",
                    _("The accepted ERPNext projection is unavailable."),
                )
            document = frappe.get_doc("NPI ERP Projection Head", str(name))
            return TargetObservation(
                action=MigrationAction.LINK,
                target_global_id=UUID(str(document.global_id)),
                target_version=int(document.optimistic_version),
                target_snapshot_hash=str(document.head_hash),
            )
        doctype = _REFERENCE_DOCTYPES.get(values["reference_type"])
        if doctype is None:
            return self._blocked(
                "npi_reference_not_supported",
                "reference_type",
                _("This NPI reference type is not supported by the closed migration bundle."),
            )
        document = self._optional_doc(doctype, values["source_object_id"])
        if document is None:
            return self._blocked(
                "npi_reference_unavailable",
                "source_object_id",
                _("The exact NPI reference is unavailable."),
            )
        version = int(
            document.get("optimistic_version")
            or document.get("current_revision_number")
            or 1
        )
        snapshot_hash = str(document.get("snapshot_hash") or "")
        if len(snapshot_hash) != 64:
            snapshot_hash = sha256_json(
                {"doctype": doctype, "globalId": str(document.global_id), "version": version}
            )
        return TargetObservation(
            action=MigrationAction.LINK,
            target_global_id=UUID(str(document.global_id)),
            target_version=version,
            target_snapshot_hash=snapshot_hash,
        )

    @staticmethod
    def _blocked(code: str, field: str, message: str) -> TargetObservation:
        return TargetObservation(
            action=MigrationAction.BLOCKED,
            findings=(MigrationFinding(code, field, message),),
        )

    def _load_source(
        self,
        *,
        tenant_id: str,
        file_revision_global_id: UUID,
        file_optimistic_version: int,
        source_sha256: str,
    ) -> _SourceFile:
        document = frappe.get_doc("NPI File Revision", str(file_revision_global_id))
        if (
            str(document.tenant_id) != tenant_id
            or int(document.optimistic_version) != file_optimistic_version
            or str(document.sha256) != source_sha256
            or str(document.scan_state) != "clean"
            or int(document.is_private or 0) != 1
            or not str(document.file).startswith("/private/files/")
        ):
            raise RequestValidationFailed(
                [
                    {
                        "path": "fileRevisionGlobalId",
                        "message": _("Select the exact clean private File Revision."),
                    }
                ]
            )
        file_document = frappe.get_doc("File", str(document.frappe_file_id))
        content = _content_bytes(file_document.get_content())
        if (
            int(file_document.is_private or 0) != 1
            or len(content) != int(document.size_bytes)
            or hashlib.sha256(content).hexdigest() != source_sha256
        ):
            raise HistoricalMigrationConflict()
        return _SourceFile(
            global_id=file_revision_global_id,
            tenant_id=tenant_id,
            project_global_id=UUID(str(document.project_global_id)),
            optimistic_version=file_optimistic_version,
            sha256=source_sha256,
            frappe_file_id=str(document.frappe_file_id),
            content=content,
        )

    def _batch_payload(
        self, inspection: BundleInspection, source: _SourceFile, now: datetime
    ) -> dict[str, object]:
        return {
            "schemaVersion": BUNDLE_SCHEMA_VERSION,
            "bundleId": str(inspection.bundle_id),
            "tenantId": source.tenant_id,
            "sourceSystem": inspection.source_system,
            "sourceFileRevisionGlobalId": str(source.global_id),
            "sourceFileOptimisticVersion": source.optimistic_version,
            "sourceSha256": source.sha256,
            "manifestHash": inspection.manifest_hash,
            "predecessorManifestHash": inspection.predecessor_manifest_hash,
            "rows": [
                {
                    **row.source_payload(),
                    "sourceHash": row.source_hash,
                    "findings": [item.payload() for item in row.findings],
                }
                for row in inspection.rows
            ],
            "createdByUserId": self.actor,
            "createdAt": _utc_text(now),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }

    def _binding_for(self, row: MigrationRow):
        assert self._inspection is not None and self._source is not None
        key_hash = _binding_key_hash(
            self._source.tenant_id,
            self._inspection.source_system,
            row.family,
            row.source_key,
        )
        return self._optional_doc("NPI Historical Migration Target Binding", key_hash)

    def _insert_binding(
        self,
        *,
        inspection: BundleInspection,
        source: _SourceFile,
        row: MigrationRow,
        job_id: UUID,
        target_doctype: str,
        target_global_id: str,
        target_version: int,
        target_snapshot_hash: str,
    ) -> None:
        key_hash = _binding_key_hash(
            source.tenant_id, inspection.source_system, row.family, row.source_key
        )
        existing = self._optional_doc("NPI Historical Migration Target Binding", key_hash)
        if existing is not None:
            if (
                str(existing.source_hash) != row.source_hash
                or str(existing.target_global_id) != target_global_id
                or str(existing.target_snapshot_hash) != target_snapshot_hash
            ):
                raise HistoricalMigrationConflict()
            return
        now = self._now()
        frappe.get_doc(
            {
                "doctype": "NPI Historical Migration Target Binding",
                "binding_key_hash": key_hash,
                "tenant_id": source.tenant_id,
                "family": row.family.value,
                "source_system": inspection.source_system,
                "source_key": row.source_key,
                "source_hash": row.source_hash,
                "target_doctype": target_doctype,
                "target_global_id": target_global_id,
                "target_version": target_version,
                "target_snapshot_hash": target_snapshot_hash,
                "created_by_job_global_id": str(job_id),
                "state": "active",
                "created_at": _database_datetime(now),
                "updated_at": _database_datetime(now),
            }
        ).insert()

    def _execute_row(
        self,
        *,
        inspection: BundleInspection,
        source: _SourceFile,
        preview_row: Mapping[str, object],
        source_row: MigrationRow,
        job_id: UUID,
    ) -> dict[str, object]:
        action = MigrationAction(str(preview_row["action"]))
        base: dict[str, object] = {
            "family": source_row.family.value,
            "sourceKey": source_row.source_key,
            "sourceHash": source_row.source_hash,
            "action": action.value,
        }
        if action is MigrationAction.BLOCKED:
            return {
                **base,
                "state": MigrationResultState.FAILED_FINAL.value,
                "findingCodes": [item.code for item in source_row.findings]
                or ["preview_blocked"],
            }
        if action is MigrationAction.SKIP:
            return {
                **base,
                "state": MigrationResultState.SKIPPED.value,
                "targetGlobalId": preview_row.get("targetGlobalId"),
                "targetVersion": preview_row.get("targetVersion"),
                "targetSnapshotHash": preview_row.get("targetSnapshotHash"),
            }
        if source_row.family is MigrationFamily.PROJECT and action is MigrationAction.CREATE:
            target = self._create_project(inspection, source, source_row)
            target_doctype = "NPI Engineering Project"
            target_id = str(target.global_id)
            target_version = target.version
            target_hash = sha256_json(_project_value_payload(target))
            result_state = MigrationResultState.CREATED
        else:
            target_doctype = self._target_doctype(source_row)
            target_id = str(preview_row["targetGlobalId"])
            target_version = int(preview_row["targetVersion"])
            target_hash = str(preview_row["targetSnapshotHash"])
            result_state = MigrationResultState.LINKED
        self._insert_binding(
            inspection=inspection,
            source=source,
            row=source_row,
            job_id=job_id,
            target_doctype=target_doctype,
            target_global_id=target_id,
            target_version=target_version,
            target_snapshot_hash=target_hash,
        )
        return {
            **base,
            "state": result_state.value,
            "targetDoctype": target_doctype,
            "targetGlobalId": target_id,
            "targetVersion": target_version,
            "targetSnapshotHash": target_hash,
        }

    def _create_project(
        self, inspection: BundleInspection, source: _SourceFile, row: MigrationRow
    ):
        values = row.value_map
        references = tuple(
            TypedReference(
                reference_type=ProjectReferenceType(item.value_map["reference_type"]),
                source_system=ReferenceSourceSystem(item.value_map["source_system"]),
                source_object_id=item.value_map["source_object_id"],
            )
            for item in self._reference_rows.get(row.source_key.casefold(), ())
            if not item.findings
        )
        command = CreateProjectCommand(
            idempotency_key=hashlib.sha256(
                f"{self.actor}\x1f{inspection.manifest_hash}\x1f{row.source_key}".encode()
            ).hexdigest(),
            tenant_id=source.tenant_id,
            business_code=values["business_code"],
            title=values["title"],
            project_type=ProjectType(values["project_type"]),
            owner_user_id=values["owner_user_id"],
            target_sop=date.fromisoformat(values["target_sop"]),
            template_global_id=UUID(values["template_global_id"]),
            template_version=int(values["template_version"]),
            expected_version=int(values["template_expected_version"]),
            references=references,
        )
        repository = FrappeProjectRepository(
            principal=self.principal,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        return ProjectInstantiationService(repository).instantiate(command).project

    @staticmethod
    def _target_doctype(row: MigrationRow) -> str:
        if row.family is MigrationFamily.TOOLING_MAPPING:
            return "NPI Tooling Master"
        if row.family is MigrationFamily.FILE_INDEX:
            return "NPI File Revision"
        if row.value_map["source_system"] == "ERPNEXT":
            return "NPI ERP Projection Head"
        return _REFERENCE_DOCTYPES[row.value_map["reference_type"]]

    def _advance_job(
        self,
        job: object,
        *,
        state: MigrationJobState,
        results: list[dict[str, object]],
        extra: Mapping[str, object] | None = None,
    ) -> None:
        version = int(job.optimistic_version) + 1
        old = _json_object(job.job_snapshot)
        snapshot = {
            **old,
            "state": state.value,
            "optimisticVersion": version,
            "results": results,
            "updatedAt": _utc_text(self._now()),
            **dict(extra or {}),
        }
        job.state = state.value
        job.optimistic_version = version
        job.job_snapshot = _canonical_json(snapshot)
        job.snapshot_hash = sha256_json(snapshot)
        job.updated_at = _database_datetime(self._now())
        job.save()

    def _job_payload(
        self,
        *,
        job_id: UUID,
        preview: object,
        state: MigrationJobState,
        version: int,
        results: list[dict[str, object]],
        queued_at: datetime,
        updated_at: datetime,
    ) -> dict[str, object]:
        return {
            "schemaVersion": JOB_SCHEMA_VERSION,
            "globalId": str(job_id),
            "batchGlobalId": str(preview.batch_global_id),
            "previewGlobalId": str(preview.global_id),
            "previewSnapshotHash": str(preview.snapshot_hash),
            "state": state.value,
            "optimisticVersion": version,
            "results": results,
            "queuedAt": _utc_text(queued_at),
            "updatedAt": _utc_text(updated_at),
            "actorUserId": self.actor,
            "requestId": self.request_id,
            "traceId": self.trace_id,
            "productionContact": False,
        }

    @staticmethod
    def _preview_response(document: object) -> dict[str, object]:
        snapshot = _json_object(document.preview_snapshot)
        return {**snapshot, "snapshotHash": str(document.snapshot_hash)}

    @staticmethod
    def _job_response(document: object) -> dict[str, object]:
        snapshot = _json_object(document.job_snapshot)
        return {**snapshot, "snapshotHash": str(document.snapshot_hash)}

    @staticmethod
    def _correction_response(
        job: object, content: bytes, failed_row_count: int
    ) -> dict[str, object]:
        return {
            "schemaVersion": CORRECTION_SCHEMA_VERSION,
            "jobGlobalId": str(job.global_id),
            "fileName": f"historical-migration-correction-{job.global_id}.csv",
            "sizeBytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "failedRowCount": failed_row_count,
            "private": True,
        }

    @staticmethod
    def _project_hash(document: object) -> str:
        return sha256_json(
            {
                "globalId": str(document.global_id),
                "tenantId": str(document.tenant_id),
                "businessCode": str(document.business_code),
                "title": str(document.title),
                "projectType": str(document.project_type),
                "ownerUserId": str(document.owner_user_id),
                "targetSop": str(document.target_sop),
                "templateGlobalId": str(document.template_global_id),
                "templateVersion": int(document.template_version),
                "optimisticVersion": int(document.optimistic_version),
            }
        )

    def _current_target_hash(self, doctype: str, global_id: str) -> str | None:
        allowed = {
            "NPI Engineering Project",
            "NPI Tooling Master",
            "NPI File Revision",
            "NPI Engineering Part",
            "NPI ERP Projection Head",
        }
        if doctype not in allowed:
            raise RuntimeError("Historical migration target type is not allowlisted.")
        document = self._optional_doc(doctype, global_id)
        if document is None:
            return None
        if doctype == "NPI Engineering Project":
            return self._project_hash(document)
        stored = str(
            document.get("snapshot_hash")
            or document.get("head_hash")
            or document.get("sha256")
            or ""
        )
        return stored if len(stored) == 64 else None

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        result: str,
        summary: Mapping[str, object],
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=object_version,
            result=result,
            input_summary=summary,
        )
        frappe.get_doc(
            {
                "doctype": "NPI Audit Event",
                "event_id": str(event.event_id),
                "global_id": str(event.global_id),
                "object_version": event.object_version,
                "actor": event.actor,
                "trace_id": event.trace_id,
                "operation": event.operation,
                "result": event.result,
                "input_summary": dict(event.input_summary),
            }
        ).insert()

    @staticmethod
    def _optional_doc(doctype: str, name: str):
        try:
            return frappe.get_doc(doctype, name)
        except frappe.DoesNotExistError:
            return None

    @staticmethod
    def _locked_doc(doctype: str, name: str):
        return frappe.get_doc(doctype, name, for_update=True)

    @staticmethod
    def _bounded_documents(doctype: str, *, order_by: str) -> tuple[object, ...]:
        names = frappe.get_all(
            doctype,
            pluck="name",
            order_by=order_by,
            limit_page_length=_MAX_WORKSPACE_ITEMS + 1,
        )
        if len(names) > _MAX_WORKSPACE_ITEMS:
            names = names[:_MAX_WORKSPACE_ITEMS]
        return tuple(frappe.get_doc(doctype, str(name)) for name in names)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise RuntimeError("Historical migration clock must be timezone aware.")
        return value.astimezone(UTC)


def run_historical_migration_job(job_id: str, expected_snapshot_hash: str) -> None:
    _require_execution_enabled()
    parsed_job_id = UUID(job_id)
    job = frappe.get_doc("NPI Historical Migration Job", str(parsed_job_id), for_update=True)
    if str(job.snapshot_hash) != expected_snapshot_hash or str(job.state) not in {
        MigrationJobState.QUEUED.value,
        MigrationJobState.PROCESSING.value,
    }:
        return
    try:
        principal = authenticated_principal(str(job.actor_user_id))
    except Exception:
        _fail_job(job, "actor_reauthorization_failed")
        return
    if principal.is_external or "System Manager" not in principal.roles:
        _fail_job(job, "actor_reauthorization_failed")
        return
    repository = FrappeHistoricalMigrationRepository(
        principal=principal,
        request_id=str(job.request_id),
        trace_id=str(job.trace_id),
    )
    preview = frappe.get_doc(
        "NPI Historical Migration Preview", str(job.preview_global_id)
    )
    batch = frappe.get_doc("NPI Historical Migration Batch", str(job.batch_global_id))
    if (
        str(preview.snapshot_hash) != str(job.preview_snapshot_hash)
        or str(preview.batch_global_id) != str(batch.global_id)
    ):
        _fail_job(job, "preview_reauthorization_failed")
        return
    source = repository._load_source(
        tenant_id=str(batch.tenant_id),
        file_revision_global_id=UUID(str(batch.source_file_revision_global_id)),
        file_optimistic_version=int(batch.source_file_optimistic_version),
        source_sha256=str(batch.source_sha256),
    )
    inspection = inspect_bundle(source.content, expected_sha256=source.sha256)
    if inspection.manifest_hash != str(batch.manifest_hash):
        _fail_job(job, "source_reauthorization_failed")
        return
    repository._prepare_resolver(inspection, source)
    preview_snapshot = _json_object(preview.preview_snapshot)
    preview_rows = preview_snapshot.get("rows")
    if not isinstance(preview_rows, list) or len(preview_rows) != len(inspection.rows):
        _fail_job(job, "preview_shape_changed")
        return
    with historical_migration_write():
        repository._advance_job(
            job,
            state=MigrationJobState.PROCESSING,
            results=[],
        )
    frappe.db.commit()
    results: list[dict[str, object]] = []
    try:
        with historical_migration_write():
            for source_row, preview_row in zip(
                inspection.rows, preview_rows, strict=True
            ):
                if not isinstance(preview_row, dict) or preview_row.get(
                    "sourceHash"
                ) != source_row.source_hash:
                    raise HistoricalMigrationConflict()
                results.append(
                    repository._execute_row(
                        inspection=inspection,
                        source=source,
                        preview_row=preview_row,
                        source_row=source_row,
                        job_id=parsed_job_id,
                    )
                )
            failed = sum(
                item["state"]
                in {
                    MigrationResultState.FAILED_RETRYABLE.value,
                    MigrationResultState.FAILED_FINAL.value,
                }
                for item in results
            )
            succeeded = len(results) - failed
            state = (
                MigrationJobState.SUCCEEDED
                if failed == 0
                else MigrationJobState.PARTIALLY_SUCCEEDED
                if succeeded
                else MigrationJobState.FAILED_FINAL
            )
            repository._advance_job(job, state=state, results=results)
            repository._append_audit(
                operation="historical_migration.execute.complete",
                global_id=parsed_job_id,
                object_version=int(job.optimistic_version),
                result=state.value,
                summary={
                    "rowCount": len(results),
                    "failedCount": failed,
                    "productionContact": False,
                },
            )
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        refreshed = frappe.get_doc(
            "NPI Historical Migration Job", str(parsed_job_id), for_update=True
        )
        _fail_job(refreshed, "execution_failed_retryable", retryable=True)
        raise


def _fail_job(job: object, reason: str, *, retryable: bool = False) -> None:
    old = _json_object(job.job_snapshot)
    state = (
        MigrationJobState.FAILED_RETRYABLE
        if retryable
        else MigrationJobState.FAILED_FINAL
    )
    version = int(job.optimistic_version) + 1
    now = datetime.now(UTC)
    results = [
        {
            "family": "job",
            "sourceKey": "job",
            "state": (
                MigrationResultState.FAILED_RETRYABLE.value
                if retryable
                else MigrationResultState.FAILED_FINAL.value
            ),
            "findingCodes": [reason],
        }
    ]
    snapshot = {
        **old,
        "state": state.value,
        "optimisticVersion": version,
        "results": results,
        "updatedAt": _utc_text(now),
    }
    with historical_migration_write():
        job.state = state.value
        job.optimistic_version = version
        job.job_snapshot = _canonical_json(snapshot)
        job.snapshot_hash = sha256_json(snapshot)
        job.updated_at = _database_datetime(now)
        job.save()
    frappe.db.commit()


def _execution_enabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    return bool(
        hasattr(configuration, "get")
        and configuration.get("npi_p9_05_routes_disabled") is False
        and configuration.get("npi_p9_05_non_production_rehearsal") is True
    )


def _require_execution_enabled() -> None:
    if not _execution_enabled():
        raise HistoricalMigrationProductionDenied()


def _binding_key_hash(
    tenant_id: str, source_system: str, family: MigrationFamily, source_key: str
) -> str:
    return hashlib.sha256(
        f"{tenant_id.casefold()}\x1f{source_system.casefold()}\x1f{family.value}\x1f"
        f"{source_key.casefold()}".encode()
    ).hexdigest()


def _project_value_payload(project: object) -> dict[str, object]:
    return {
        "globalId": str(project.global_id),
        "tenantId": str(project.tenant_id),
        "businessCode": str(project.business_code),
        "title": str(project.title),
        "projectType": str(project.project_type.value),
        "ownerUserId": str(project.owner_user_id),
        "targetSop": project.target_sop.isoformat(),
        "templateGlobalId": str(project.template_snapshot.template_global_id),
        "templateVersion": int(project.template_snapshot.template_version),
        "optimisticVersion": int(project.version),
    }


def _correction_csv(failed: list[dict[str, object]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "schema_version",
            "family",
            "source_key",
            "finding_code",
            "corrected_value",
        ]
    )
    for item in sorted(
        failed, key=lambda value: (str(value.get("family")), str(value.get("sourceKey")))
    ):
        codes = item.get("findingCodes")
        safe_codes = codes if isinstance(codes, list) and codes else ["review_required"]
        for code in safe_codes:
            writer.writerow(
                [
                    CORRECTION_SCHEMA_VERSION,
                    str(item.get("family") or ""),
                    str(item.get("sourceKey") or ""),
                    str(code),
                    "",
                ]
            )
    return output.getvalue().encode("utf-8")


def _result_list(snapshot: Mapping[str, object]) -> list[dict[str, object]]:
    value = snapshot.get("results")
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise RuntimeError("Persisted historical migration result shape is invalid.")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise RuntimeError("Persisted historical migration JSON is invalid.")
    return parsed


def _content_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode()
    raise RuntimeError("The controlled file content is invalid.")


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
