from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Iterator
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.request_security import (
    authenticated_principal,
    require_tooling_import_routes_enabled,
)
from npi_core.tooling.domain import (
    EngineeringPartRevision,
    ToolingReferenceUnavailable,
    ToolingVersionConflict,
    sha256_json,
)
from npi_core.tooling.frappe_validation import (
    tooling_command_write,
    tooling_import_rollback_targets,
)
from npi_core.tooling.import_domain import (
    FieldFinding,
    FindingSeverity,
    ImportFieldResult,
    ImportJobState,
    ImportRowResult,
    ImportRowResultState,
    MappingDisposition,
    MappingEntry,
    MappingRevisionState,
    PreviewAction,
    PreviewRow,
    SemanticClassification,
    ToolingImportJobSnapshot,
    ToolingImportMappingRevision,
    ToolingImportPreviewRevision,
    ToolingImportSource,
    derive_job_state,
    evaluate_rollback,
    latest_import_row_results,
    transform_field,
    RollbackObservation,
)
from npi_core.tooling.import_execution_domain import (
    CORRECTION_SCHEMA_VERSION,
    FIXTURE_MAPPING_VERSION,
    CorrectionEntry,
    ExecutionFieldBinding,
    FixtureMappingActivation,
    ReconciliationItem,
    ReconciliationSnapshot,
    ReconciliationState,
    rollback_item_state,
    validate_correction_entries,
)
from npi_core.tooling.import_frappe_validation import tooling_import_write
from npi_core.tooling.import_repository import (
    FrappeToolingImportRepository,
    ToolingImportCommandOutcome,
)


_MAX_JOBS = 200
_MAX_RESULTS = 100_000
_MAX_ARTIFACTS = 100
_MAX_RECONCILIATIONS = 500
_MAX_ROWS_PER_RUN = 25
_IMPORT_TARGET_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_IMPORT_TARGET_ROOT_INSERT",
        "P607_IMPORT_TARGET_REVISION_INSERT",
        "P607_IMPORT_TARGET_ROOT_ADVANCE",
        "P607_IMPORT_TARGET_ROW_RESULT_INSERT",
        "P607_IMPORT_TARGET_BINDING_INSERT",
    }
)
_CORRECTION_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_CORRECTION_RECEIPT_INSERT",
        "P607_CORRECTION_FILE_SAVE",
        "P607_CORRECTION_ARTIFACT_INSERT",
        "P607_CORRECTION_RESPONSE_BUILD",
        "P607_CORRECTION_AUDIT_APPEND",
        "P607_CORRECTION_RECEIPT_SEAL",
        "P607_CORRECTION_DOWNLOAD_CONTENT_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_PRIVACY_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_FILE_ID_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_FILE_NAME_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_SIZE_VALIDATE",
        "P607_CORRECTION_DOWNLOAD_DIGEST_VALIDATE",
    }
)
_FIXTURE_SOURCES = {
    "p6-07-synthetic-title-row-deleted.xlsx": (
        "b807aca4ef6776a0ad6e8eada1c8291b3a13dbe32724828d33661d67bc8e684f"
    ),
    "p6-07-synthetic-title-rows-inserted.xlsx": (
        "f1c67a991bb59cffbee208fcc786ee44de342d3a2cf56da31d3422c9026459b4"
    ),
}
_DEPENDENCY_FIELDS = (
    ("NPI Tooling Requirement", "target_part_revision_global_id"),
    ("NPI Tooling Applicability", "part_revision_global_id"),
    ("NPI Part Controlled Specification", "part_revision_global_id"),
)


@dataclass(frozen=True, slots=True)
class ToolingImportBinaryOutcome:
    content: bytes
    file_name: str
    mime_type: str
    replayed: bool = False


class FrappeToolingImportExecutionRepository(FrappeToolingImportRepository):
    """Controlled fixture execution, immutable results and safe rollback."""

    def __init__(self, *, mapping_authority=None, **values: object) -> None:
        super().__init__(
            mapping_authority=mapping_authority or self._mapping_authority_from_store,
            **values,
        )

    def tooling_import_batch_detail(
        self,
        project_id: UUID,
        batch_id: UUID,
    ) -> dict[str, object] | None:
        response = super().tooling_import_batch_detail(project_id, batch_id)
        if response is None:
            return None
        project = self._authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        if source is None:
            return None
        response["jobs"] = [
            self._job_detail(project, source, row)
            for row in self._job_documents(project, source)
        ]
        response["permissions"] = self._execution_permissions(source)
        return response

    def tooling_import_jobs(
        self,
        project_id: UUID,
        batch_id: UUID,
    ) -> dict[str, object] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        if source is None:
            return None
        return {
            "projectGlobalId": str(project.global_id),
            "batchGlobalId": str(source.batch_global_id),
            "permissions": self._execution_permissions(source),
            "jobs": [
                self._job_detail(project, source, row)
                for row in self._job_documents(project, source)
            ],
        }

    def tooling_import_job_detail(
        self,
        project_id: UUID,
        batch_id: UUID,
        job_id: UUID,
    ) -> dict[str, object] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        if source is None:
            return None
        job = self._job_for_project(project, source, job_id)
        return self._job_detail(project, source, job) if job is not None else None

    def execute_tooling_import_preview(
        self,
        project_id: UUID,
        batch_id: UUID,
        preview_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int,
        expected_snapshot_hash: str,
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        if source is None:
            return None
        preview = self._latest_preview_for_project(project, source, preview_id)
        if preview is None:
            return None
        if (
            preview.preview_version != expected_version
            or preview.snapshot_hash != expected_snapshot_hash
        ):
            raise ToolingVersionConflict()
        activation = self._activation_for_preview(project, source, preview)
        if activation is None or not preview.execution_eligible:
            raise ToolingReferenceUnavailable()
        payload = {
            "batchGlobalId": str(batch_id),
            "previewGlobalId": str(preview_id),
            "expectedVersion": expected_version,
            "expectedSnapshotHash": expected_snapshot_hash,
            "mappingActivationGlobalId": str(activation.global_id),
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_execution.start",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        if self._job_for_preview(project, source, preview) is not None:
            raise ToolingVersionConflict()
        receipt_key, payload_hash = context
        now = self._now()
        job_id = self._new_uuid()
        snapshot = ToolingImportJobSnapshot(
            global_id=job_id,
            batch_global_id=source.batch_global_id,
            preview_global_id=preview.preview_global_id,
            preview_snapshot_hash=preview.snapshot_hash,
            attempt=1,
            state=ImportJobState.QUEUED,
            row_results=(),
            queued_at=now,
            updated_at=now,
        )
        response = {"job": _public_job(snapshot, optimistic_version=1)}
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_execution.start",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_job(project, source, preview, activation, snapshot)
            self._append_audit(
                operation="tooling_import_execution.start",
                global_id=job_id,
                object_version=1,
                summary={
                    "batchGlobalId": str(batch_id),
                    "previewSnapshotHash": preview.snapshot_hash,
                    "mappingActivationSnapshotHash": activation.snapshot_hash,
                    "rowCount": len(preview.rows),
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_job",
                target_id=job_id,
                response=response,
                now=now,
            )
            self._enqueue_job(job_id, snapshot.snapshot_hash)
        return ToolingImportCommandOutcome(response)

    def retry_tooling_import_job(
        self,
        project_id: UUID,
        batch_id: UUID,
        job_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int,
        expected_snapshot_hash: str,
        correction_artifact_id: UUID,
        correction_artifact_snapshot_hash: str,
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        job = self._locked_job_for_project(project, source, job_id) if source else None
        if source is None or job is None:
            return None
        self._require_job_version(job, expected_version, expected_snapshot_hash)
        self._require_job_state(
            job,
            {ImportJobState.PARTIALLY_SUCCEEDED, ImportJobState.FAILED_RETRYABLE},
        )
        history = self._row_result_values(project, source, job)
        retryable = tuple(
            value
            for value in latest_import_row_results(history)
            if value.state is ImportRowResultState.FAILED_RETRYABLE
        )
        if not retryable:
            raise RequestValidationFailed(
                field_errors=[
                    {
                        "path": "jobGlobalId",
                        "message": _("The import job has no failed retryable rows."),
                    }
                ]
            )
        artifact = self._artifact_for_job(
            project,
            source,
            job,
            correction_artifact_id,
        )
        if (
            artifact is None
            or str(artifact.snapshot_hash) != correction_artifact_snapshot_hash
            or str(artifact.job_snapshot_hash) != str(job.snapshot_hash)
        ):
            raise ToolingReferenceUnavailable()
        payload = {
            "batchGlobalId": str(batch_id),
            "jobGlobalId": str(job_id),
            "expectedVersion": expected_version,
            "expectedSnapshotHash": expected_snapshot_hash,
            "correctionArtifactGlobalId": str(correction_artifact_id),
            "correctionArtifactSnapshotHash": correction_artifact_snapshot_hash,
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_execution.retry",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        now = self._now()
        queued = ToolingImportJobSnapshot(
            global_id=job_id,
            batch_global_id=source.batch_global_id,
            preview_global_id=UUID(str(job.preview_global_id)),
            preview_snapshot_hash=str(job.preview_snapshot_hash),
            attempt=int(job.attempt) + 1,
            state=ImportJobState.QUEUED,
            row_results=history,
            queued_at=_utc_datetime(job.queued_at),
            updated_at=now,
            correction_artifact_global_id=correction_artifact_id,
            correction_artifact_snapshot_hash=correction_artifact_snapshot_hash,
        )
        next_version = int(job.optimistic_version) + 1
        response = {"job": _public_job(queued, optimistic_version=next_version)}
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_execution.retry",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._apply_job_snapshot(job, queued, next_version)
            self._append_audit(
                operation="tooling_import_execution.retry",
                global_id=job_id,
                object_version=next_version,
                summary={
                    "attempt": queued.attempt,
                    "retryRowCount": len(retryable),
                    "correctionArtifactSnapshotHash": correction_artifact_snapshot_hash,
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_job",
                target_id=job_id,
                response=response,
                now=now,
            )
            self._enqueue_job(job_id, queued.snapshot_hash)
        return ToolingImportCommandOutcome(response)

    def create_correction_artifact(
        self,
        project_id: UUID,
        batch_id: UUID,
        job_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int,
        expected_snapshot_hash: str,
        corrections: Sequence[CorrectionEntry],
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        job = self._locked_job_for_project(project, source, job_id) if source else None
        if source is None or job is None:
            return None
        self._require_job_version(job, expected_version, expected_snapshot_hash)
        self._require_job_state(
            job,
            {ImportJobState.PARTIALLY_SUCCEEDED, ImportJobState.FAILED_RETRYABLE},
        )
        values = validate_correction_entries(corrections)
        self._authorize_corrections(project, source, job, values)
        payload = {
            "batchGlobalId": str(batch_id),
            "jobGlobalId": str(job_id),
            "expectedVersion": expected_version,
            "expectedSnapshotHash": expected_snapshot_hash,
            "correctionHashes": [
                sha256_json(
                    {
                        "worksheetName": item.worksheet_name,
                        "sourceRow": item.source_row,
                        "sourceHeader": item.source_header,
                        "correctedValue": item.corrected_value,
                    }
                )
                for item in values
            ],
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_correction.export",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        content = _correction_csv(values)
        digest = hashlib.sha256(content).hexdigest()
        artifact_id = self._new_uuid()
        now = self._now()
        file_name = f"tooling-import-corrections-{artifact_id}.csv"
        snapshot = {
            "schemaVersion": CORRECTION_SCHEMA_VERSION,
            "globalId": str(artifact_id),
            "batchGlobalId": str(batch_id),
            "jobGlobalId": str(job_id),
            "jobSnapshotHash": str(job.snapshot_hash),
            "frappeFileId": None,
            "fileName": file_name,
            "mimeType": "text/csv",
            "sizeBytes": len(content),
            "sha256": digest,
            "entryCount": len(values),
            "createdByUserId": self.actor,
            "createdAt": now.isoformat().replace("+00:00", "Z"),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        with tooling_import_write():
            with _correction_server_step(
                "P607_CORRECTION_RECEIPT_INSERT",
                self.trace_id,
            ):
                receipt = self._insert_import_receipt(
                    project,
                    receipt_key=receipt_key,
                    operation="tooling_import_correction.export",
                    idempotency_key_hash=idempotency_key_hash,
                    payload_hash=payload_hash,
                    now=now,
                )
            with _correction_server_step(
                "P607_CORRECTION_FILE_SAVE",
                self.trace_id,
            ):
                file_document = self._save_correction_file(
                    job_id,
                    file_name,
                    content,
                )
            snapshot.update(
                {
                    "frappeFileId": str(file_document.name),
                    "fileName": str(file_document.file_name),
                    "sizeBytes": int(file_document.file_size),
                }
            )
            with _correction_server_step(
                "P607_CORRECTION_ARTIFACT_INSERT",
                self.trace_id,
            ):
                artifact = self._insert_correction_artifact(
                    project,
                    source,
                    job,
                    artifact_id,
                    file_document,
                    snapshot,
                    now,
                )
            with _correction_server_step(
                "P607_CORRECTION_RESPONSE_BUILD",
                self.trace_id,
            ):
                response = {"correctionArtifact": self._public_artifact(artifact)}
            with _correction_server_step(
                "P607_CORRECTION_AUDIT_APPEND",
                self.trace_id,
            ):
                self._append_audit(
                    operation="tooling_import_correction.export",
                    global_id=artifact_id,
                    object_version=1,
                    summary={
                        "jobGlobalId": str(job_id),
                        "jobSnapshotHash": str(job.snapshot_hash),
                        "entryCount": len(values),
                        "artifactSha256": digest,
                    },
                )
            with _correction_server_step(
                "P607_CORRECTION_RECEIPT_SEAL",
                self.trace_id,
            ):
                self._seal_import_receipt(
                    receipt,
                    target_type="tooling_import_correction_artifact",
                    target_id=artifact_id,
                    response=response,
                    now=now,
                )
        return ToolingImportCommandOutcome(response)

    def correction_artifact_content(
        self,
        project_id: UUID,
        batch_id: UUID,
        job_id: UUID,
        artifact_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_snapshot_hash: str,
    ) -> ToolingImportBinaryOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        job = self._job_for_project(project, source, job_id) if source else None
        artifact = (
            self._artifact_for_job(project, source, job, artifact_id)
            if source is not None and job is not None
            else None
        )
        if artifact is None or str(artifact.snapshot_hash) != expected_snapshot_hash:
            return None
        payload = {
            "batchGlobalId": str(batch_id),
            "jobGlobalId": str(job_id),
            "artifactGlobalId": str(artifact_id),
            "expectedSnapshotHash": expected_snapshot_hash,
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_correction.download",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            file_document = frappe.get_doc("File", str(artifact.frappe_file_id))
            return self._verified_artifact_content(
                artifact,
                file_document,
                trace_id=self.trace_id,
                replayed=True,
            )
        receipt_key, payload_hash = context
        file_document = frappe.get_doc("File", str(artifact.frappe_file_id))
        outcome = self._verified_artifact_content(
            artifact,
            file_document,
            trace_id=self.trace_id,
        )
        now = self._now()
        response = {
            "artifactGlobalId": str(artifact_id),
            "snapshotHash": expected_snapshot_hash,
            "sha256": str(artifact.sha256),
        }
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_correction.download",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._append_audit(
                operation="tooling_import_correction.download",
                global_id=artifact_id,
                object_version=1,
                summary={"jobGlobalId": str(job_id), "artifactSha256": str(artifact.sha256)},
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_correction_artifact",
                target_id=artifact_id,
                response=response,
                now=now,
            )
        return outcome

    def reconcile_tooling_import_job(
        self,
        project_id: UUID,
        batch_id: UUID,
        job_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int,
        expected_snapshot_hash: str,
        kind: str = "reconciliation",
    ) -> ToolingImportCommandOutcome | None:
        return self._create_reconciliation_command(
            project_id,
            batch_id,
            job_id,
            idempotency_key_hash=idempotency_key_hash,
            expected_version=expected_version,
            expected_snapshot_hash=expected_snapshot_hash,
            kind=kind,
        )

    def rollback_tooling_import_job(
        self,
        project_id: UUID,
        batch_id: UUID,
        job_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int,
        expected_snapshot_hash: str,
        eligibility_id: UUID,
        eligibility_snapshot_hash: str,
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        job = self._locked_job_for_project(project, source, job_id) if source else None
        if source is None or job is None:
            return None
        self._require_job_version(job, expected_version, expected_snapshot_hash)
        self._require_job_state(
            job,
            {ImportJobState.PARTIALLY_SUCCEEDED, ImportJobState.SUCCEEDED},
        )
        eligibility = self._reconciliation_for_job(
            project,
            source,
            job,
            eligibility_id,
            kind="rollback_eligibility",
        )
        if eligibility is None or str(eligibility.snapshot_hash) != eligibility_snapshot_hash:
            raise ToolingReferenceUnavailable()
        if str(eligibility.job_snapshot_hash) != str(job.snapshot_hash):
            raise ToolingVersionConflict()
        eligibility_items = _json_array(eligibility.item_snapshot)
        payload = {
            "batchGlobalId": str(batch_id),
            "jobGlobalId": str(job_id),
            "expectedVersion": expected_version,
            "expectedSnapshotHash": expected_snapshot_hash,
            "eligibilityGlobalId": str(eligibility_id),
            "eligibilitySnapshotHash": eligibility_snapshot_hash,
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_rollback.execute",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        now = self._now()
        current_eligibility = self._build_reconciliation(
            project,
            source,
            job,
            "rollback_eligibility",
            now,
            lock_targets=True,
        )
        items = [item.snapshot_payload() for item in current_eligibility.items]
        allowed = (
            bool(items)
            and _same_eligibility_targets(eligibility_items, items)
            and all(item.get("state") == "matched" for item in items)
        )
        history = self._row_result_values(project, source, job)
        next_state = ImportJobState.ROLLED_BACK if allowed else ImportJobState.ROLLBACK_DENIED
        result_snapshot = ReconciliationSnapshot(
            global_id=self._new_uuid(),
            job_global_id=job_id,
            job_snapshot_hash=str(job.snapshot_hash),
            kind="rollback_result",
            items=tuple(
                ReconciliationItem(
                    row_result_global_id=UUID(str(item["rowResultGlobalId"])),
                    target_object_type=str(item["targetObjectType"]),
                    target_global_id=UUID(str(item["targetGlobalId"])),
                    expected_snapshot_hash=str(item["expectedSnapshotHash"]),
                    observed_snapshot_hash=(
                        str(item["observedSnapshotHash"])
                        if item.get("observedSnapshotHash")
                        else None
                    ),
                    downstream_reference_count=int(item["downstreamReferenceCount"]),
                    state=(
                        ReconciliationState.ROLLED_BACK
                        if allowed
                        else ReconciliationState(str(item["state"]))
                    ),
                )
                for item in items
            ),
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        final = ToolingImportJobSnapshot(
            global_id=job_id,
            batch_global_id=source.batch_global_id,
            preview_global_id=UUID(str(job.preview_global_id)),
            preview_snapshot_hash=str(job.preview_snapshot_hash),
            attempt=int(job.attempt),
            state=next_state,
            row_results=history,
            queued_at=_utc_datetime(job.queued_at),
            updated_at=now,
            correction_artifact_global_id=_optional_uuid_value(
                job.correction_artifact_global_id
            ),
            correction_artifact_snapshot_hash=(
                str(job.correction_artifact_snapshot_hash)
                if job.correction_artifact_snapshot_hash
                else None
            ),
        )
        next_version = int(job.optimistic_version) + 1
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_rollback.execute",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            if allowed:
                self._delete_eligible_targets(project, source, job, items)
            self._insert_reconciliation(project, source, result_snapshot)
            self._apply_job_snapshot(job, final, next_version)
            response = {
                "job": _public_job(final, optimistic_version=next_version),
                "rollback": _public_reconciliation(result_snapshot),
            }
            self._append_audit(
                operation="tooling_import_rollback.execute",
                global_id=result_snapshot.global_id,
                object_version=1,
                summary={
                    "jobGlobalId": str(job_id),
                    "eligibilitySnapshotHash": eligibility_snapshot_hash,
                    "state": next_state.value,
                    "targetCount": len(items),
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_reconciliation_revision",
                target_id=result_snapshot.global_id,
                response=response,
                now=now,
            )
        return ToolingImportCommandOutcome(response)

    def seed_synthetic_fixture_mapping_activation(
        self,
        project_id: UUID,
        batch_id: UUID,
        proposal_id: UUID,
    ) -> dict[str, object] | None:
        """Controlled-Site-only seed; never called from migrations or public BFF."""

        require_tooling_import_routes_enabled()
        if not self._is_internal_system_manager():
            raise ToolingReferenceUnavailable()
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        proposal = (
            self._mapping_for_project(project, source, proposal_id)
            if source is not None
            else None
        )
        if source is None or proposal is None:
            return None
        if (
            source.file_name not in _FIXTURE_SOURCES
            or _FIXTURE_SOURCES[source.file_name] != source.sha256
            or not source.customer_scope_id.casefold().startswith("synthetic")
            or proposal.state is not MappingRevisionState.PROPOSAL
            or proposal.mapping_version != 1
        ):
            raise ToolingReferenceUnavailable()
        existing = self._activation_for_source(project, source)
        if existing is not None:
            return {
                "mappingActivation": _public_activation(existing),
                "replayed": True,
            }
        now = self._now()
        approved = replace(
            proposal,
            global_id=self._new_uuid(),
            mapping_version=2,
            state=MappingRevisionState.APPROVED_FIXTURE,
            entries=tuple(_fixture_mapping_entry(entry) for entry in proposal.entries),
            reason="Controlled synthetic fixture execution mapping.",
            created_by_user_id=self.actor,
            created_at=now,
        )
        activation = FixtureMappingActivation(
            global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            batch_global_id=batch_id,
            source_snapshot_hash=source.snapshot_hash,
            source_sha256=source.sha256,
            customer_scope_id=source.customer_scope_id,
            fixture_version=FIXTURE_MAPPING_VERSION,
            mapping_revision_global_id=approved.global_id,
            mapping_snapshot_hash=approved.snapshot_hash,
            source_signature=approved.source_signature,
            bindings=(
                ExecutionFieldBinding(
                    "Part Name English",
                    "engineering_part_revision",
                    "title",
                ),
            ),
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with tooling_import_write():
            self._insert_mapping(project, approved)
            self._insert_activation(project, activation)
            self._append_audit(
                operation="tooling_import_fixture_mapping.activate",
                global_id=activation.global_id,
                object_version=1,
                summary={
                    "batchGlobalId": str(batch_id),
                    "sourceSha256": source.sha256,
                    "mappingSnapshotHash": approved.snapshot_hash,
                    "activationSnapshotHash": activation.snapshot_hash,
                },
            )
        return {
            "mappingProposal": _public_snapshot(approved),
            "mappingActivation": _public_activation(activation),
            "replayed": False,
        }

    # Persistence and execution helpers follow. They intentionally keep raw
    # workbook values out of logs, audits, receipts and normal detail payloads.

    def _execution_permissions(self, source: ToolingImportSource) -> dict[str, bool]:
        manage = self._is_internal_system_manager()
        activation = self._mapping_authority_from_store(source)
        available = activation.get("state") == "approved_fixture"
        return {
            **super()._import_permissions(),
            "execute": manage and available,
            "retry": manage,
            "createCorrectionArtifact": manage,
            "downloadCorrectionArtifact": manage,
            "reconcile": manage,
            "evaluateRollback": manage,
            "rollback": manage,
            "activateProductionMapping": False,
        }

    def _mapping_authority_from_store(
        self,
        source: ToolingImportSource | None,
    ) -> dict[str, str]:
        if source is None:
            return self._unavailable_mapping_authority(None)
        project = self._authorized_project(source.project_global_id)
        activation = (
            self._activation_for_source(project, source) if project is not None else None
        )
        if activation is None:
            return self._unavailable_mapping_authority(source)
        return {
            "state": "approved_fixture",
            "reasonCode": "synthetic_fixture_scope_only",
            "mappingRevisionGlobalId": str(activation.mapping_revision_global_id),
            "mappingSnapshotHash": activation.mapping_snapshot_hash,
            "activationGlobalId": str(activation.global_id),
            "activationSnapshotHash": activation.snapshot_hash,
        }

    def _activation_for_source(
        self,
        project: object,
        source: ToolingImportSource,
    ) -> FixtureMappingActivation | None:
        rows = self._bounded_documents(
            "NPI Tooling Import Mapping Activation",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "source_snapshot_hash": source.snapshot_hash,
                "state": "approved_fixture",
            },
            maximum=2,
            order_by="created_at asc",
        )
        if len(rows) > 1:
            raise RuntimeError("The Tooling import fixture mapping activation is ambiguous.")
        return self._activation_value(rows[0]) if rows else None

    def _activation_for_preview(
        self,
        project: object,
        source: ToolingImportSource,
        preview: ToolingImportPreviewRevision,
    ) -> FixtureMappingActivation | None:
        activation = self._activation_for_source(project, source)
        if activation is None or any(
            (
                activation.mapping_revision_global_id != preview.mapping_global_id,
                activation.mapping_snapshot_hash != preview.mapping_snapshot_hash,
                preview.mapping_state is not MappingRevisionState.APPROVED_FIXTURE,
            )
        ):
            return None
        return activation

    @staticmethod
    def _activation_value(row: object) -> FixtureMappingActivation:
        payload = _json_object(row.activation_snapshot)
        bindings = tuple(
            ExecutionFieldBinding(
                source_header=str(item["sourceHeader"]),
                target_object=str(item["targetObject"]),
                target_field=str(item["targetField"]),
            )
            for item in _json_array(payload.get("bindings", []))
        )
        value = FixtureMappingActivation(
            global_id=UUID(str(payload["globalId"])),
            tenant_id=str(payload["tenantId"]),
            project_global_id=UUID(str(payload["projectGlobalId"])),
            batch_global_id=UUID(str(payload["batchGlobalId"])),
            source_snapshot_hash=str(payload["sourceSnapshotHash"]),
            source_sha256=str(payload["sourceSha256"]),
            customer_scope_id=str(payload["customerScopeId"]),
            fixture_version=str(payload["fixtureVersion"]),
            mapping_revision_global_id=UUID(str(payload["mappingRevisionGlobalId"])),
            mapping_snapshot_hash=str(payload["mappingSnapshotHash"]),
            source_signature=str(payload["sourceSignature"]),
            bindings=bindings,
            created_by_user_id=str(payload["createdByUserId"]),
            created_at=_utc_datetime(payload["createdAt"]),
            request_id=UUID(str(payload["requestId"])),
            trace_id=str(payload["traceId"]),
        )
        if value.snapshot_hash != str(row.snapshot_hash):
            raise RuntimeError("The Tooling import mapping activation integrity drifted.")
        return value

    @staticmethod
    def _insert_activation(project: object, value: FixtureMappingActivation) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Import Mapping Activation",
                "global_id": str(value.global_id),
                "state": "approved_fixture",
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(value.batch_global_id),
                "source_snapshot_hash": value.source_snapshot_hash,
                "source_sha256": value.source_sha256,
                "customer_scope_id": value.customer_scope_id,
                "fixture_version": value.fixture_version,
                "mapping_revision_global_id": str(value.mapping_revision_global_id),
                "mapping_snapshot_hash": value.mapping_snapshot_hash,
                "source_signature": value.source_signature,
                "binding_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.bindings]
                ),
                "activation_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
            }
        ).insert()

    def _job_documents(
        self,
        project: object,
        source: ToolingImportSource,
    ) -> tuple[object, ...]:
        return self._bounded_documents(
            "NPI Tooling Import Job",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
            },
            maximum=_MAX_JOBS,
            order_by="queued_at desc",
        )

    def _job_for_project(
        self,
        project: object,
        source: ToolingImportSource,
        job_id: UUID,
    ) -> object | None:
        job = _optional_doc("NPI Tooling Import Job", str(job_id))
        if job is None or any(
            (
                str(job.global_id) != str(job_id),
                str(job.tenant_id) != str(project.tenant_id),
                str(job.project_global_id) != str(project.global_id),
                str(job.batch_global_id) != str(source.batch_global_id),
                str(job.source_snapshot_hash) != source.snapshot_hash,
            )
        ):
            return None
        return job

    def _job_for_preview(
        self,
        project: object,
        source: ToolingImportSource,
        preview: ToolingImportPreviewRevision,
    ) -> object | None:
        rows = self._bounded_documents(
            "NPI Tooling Import Job",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "preview_global_id": str(preview.preview_global_id),
                "preview_snapshot_hash": preview.snapshot_hash,
            },
            maximum=1,
        )
        return rows[0] if rows else None

    def _locked_job_for_project(
        self,
        project: object,
        source: ToolingImportSource,
        job_id: UUID,
    ) -> object | None:
        try:
            job = frappe.get_doc("NPI Tooling Import Job", str(job_id), for_update=True)
        except frappe.DoesNotExistError:
            return None
        if any(
            (
                str(job.global_id) != str(job_id),
                str(job.tenant_id) != str(project.tenant_id),
                str(job.project_global_id) != str(project.global_id),
                str(job.batch_global_id) != str(source.batch_global_id),
                str(job.source_snapshot_hash) != source.snapshot_hash,
            )
        ):
            return None
        return job

    def _job_detail(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
    ) -> dict[str, object]:
        snapshot = _json_object(job.job_snapshot)
        if sha256_json(snapshot) != str(job.snapshot_hash):
            raise RuntimeError("The Tooling import job projection integrity drifted.")
        return {
            **_localized_job_payload(snapshot),
            "optimisticVersion": int(job.optimistic_version),
            "snapshotHash": str(job.snapshot_hash),
            "correctionArtifacts": [
                self._public_artifact(row)
                for row in self._artifact_documents(project, source, job)
            ],
            "reconciliations": [
                self._public_reconciliation_document(row)
                for row in self._reconciliation_documents(project, source, job)
            ],
        }

    def _insert_job(
        self,
        project: object,
        source: ToolingImportSource,
        preview: ToolingImportPreviewRevision,
        activation: FixtureMappingActivation,
        snapshot: ToolingImportJobSnapshot,
    ) -> object:
        preview_document = frappe.get_doc(
            "NPI Tooling Import Preview Revision",
            str(preview.global_id),
        )
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Import Job",
                "global_id": str(snapshot.global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "source_snapshot_hash": source.snapshot_hash,
                "preview_global_id": str(preview.preview_global_id),
                "preview_revision_global_id": str(preview_document.global_id),
                "preview_snapshot_hash": preview.snapshot_hash,
                "mapping_activation_global_id": str(activation.global_id),
                "actor_user_id": self.actor,
                "attempt": snapshot.attempt,
                "state": snapshot.state.value,
                "optimistic_version": 1,
                "correction_artifact_global_id": None,
                "correction_artifact_snapshot_hash": None,
                "job_snapshot": _canonical_json(snapshot.snapshot_payload()),
                "snapshot_hash": snapshot.snapshot_hash,
                "queued_at": _database_datetime(snapshot.queued_at),
                "updated_at": _database_datetime(snapshot.updated_at),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    @staticmethod
    def _apply_job_snapshot(
        job: object,
        snapshot: ToolingImportJobSnapshot,
        optimistic_version: int,
    ) -> None:
        job.attempt = snapshot.attempt
        job.state = snapshot.state.value
        job.optimistic_version = optimistic_version
        job.correction_artifact_global_id = (
            str(snapshot.correction_artifact_global_id)
            if snapshot.correction_artifact_global_id is not None
            else None
        )
        job.correction_artifact_snapshot_hash = (
            snapshot.correction_artifact_snapshot_hash
        )
        job.job_snapshot = _canonical_json(snapshot.snapshot_payload())
        job.snapshot_hash = snapshot.snapshot_hash
        job.updated_at = _database_datetime(snapshot.updated_at)
        job.save()

    @staticmethod
    def _require_job_version(
        job: object,
        expected_version: int,
        expected_snapshot_hash: str,
    ) -> None:
        if (
            int(job.optimistic_version) != expected_version
            or str(job.snapshot_hash) != expected_snapshot_hash
        ):
            raise ToolingVersionConflict()

    @staticmethod
    def _require_job_state(
        job: object,
        allowed: set[ImportJobState],
    ) -> None:
        if ImportJobState(str(job.state)) not in allowed:
            raise RequestValidationFailed(
                field_errors=[
                    {
                        "path": "jobGlobalId",
                        "message": _("The Tooling import job state does not allow this command."),
                    }
                ]
            )

    @staticmethod
    def _enqueue_job(job_id: UUID, expected_snapshot_hash: str) -> None:
        frappe.enqueue(
            "npi_core.tooling.import_execution_repository.run_tooling_import_job",
            queue="long",
            enqueue_after_commit=True,
            job_id=str(job_id),
            expected_snapshot_hash=expected_snapshot_hash,
        )

    # Remaining helpers are intentionally below the worker entry point to make
    # the public command boundary easy to audit.

    def _row_result_documents(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
    ) -> tuple[object, ...]:
        return self._bounded_documents(
            "NPI Tooling Import Row Result",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "job_global_id": str(job.global_id),
            },
            maximum=_MAX_RESULTS,
            order_by="attempt asc, source_row asc",
        )

    def _row_result_values(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
    ) -> tuple[ImportRowResult, ...]:
        return tuple(_row_result_value(row) for row in self._row_result_documents(project, source, job))

    def _authorize_corrections(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
        corrections: Sequence[CorrectionEntry],
    ) -> None:
        latest = latest_import_row_results(self._row_result_values(project, source, job))
        retryable_fields = {
            (item.worksheet_name, item.source_row, field.source_header.casefold())
            for item in latest
            if item.state is ImportRowResultState.FAILED_RETRYABLE
            for field in item.field_results
        }
        if any(item.identity not in retryable_fields for item in corrections):
            raise RequestValidationFailed(
                field_errors=[
                    {
                        "path": "corrections",
                        "message": _("Corrections may only target failed retryable fields."),
                    }
                ]
            )
        if any(
            item.corrected_value.lstrip().startswith(("=", "+", "-", "@"))
            for item in corrections
        ):
            raise RequestValidationFailed(
                field_errors=[
                    {
                        "path": "corrections.correctedValue",
                        "message": _("Correction values cannot start with a spreadsheet formula marker."),
                    }
                ]
            )

    @staticmethod
    def _save_correction_file(job_id: UUID, file_name: str, content: bytes) -> object:
        from frappe.utils.file_manager import save_file

        return save_file(
            file_name,
            content,
            "NPI Tooling Import Job",
            str(job_id),
            is_private=1,
        )

    def _insert_correction_artifact(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
        artifact_id: UUID,
        file_document: object,
        snapshot: Mapping[str, object],
        now: datetime,
    ) -> object:
        snapshot_hash = sha256_json(snapshot)
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Import Correction Artifact",
                "global_id": str(artifact_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "job_global_id": str(job.global_id),
                "job_snapshot_hash": str(job.snapshot_hash),
                "frappe_file_id": str(file_document.name),
                "file_name": str(snapshot["fileName"]),
                "mime_type": "text/csv",
                "size_bytes": int(snapshot["sizeBytes"]),
                "sha256": str(snapshot["sha256"]),
                "entry_count": int(snapshot["entryCount"]),
                "artifact_snapshot": _canonical_json(snapshot),
                "snapshot_hash": snapshot_hash,
                "created_by_user_id": self.actor,
                "created_at": _database_datetime(now),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    def _artifact_documents(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
    ) -> tuple[object, ...]:
        return self._bounded_documents(
            "NPI Tooling Import Correction Artifact",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "job_global_id": str(job.global_id),
            },
            maximum=_MAX_ARTIFACTS,
            order_by="created_at asc",
        )

    def _artifact_for_job(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
        artifact_id: UUID,
    ) -> object | None:
        artifact = _optional_doc("NPI Tooling Import Correction Artifact", str(artifact_id))
        if artifact is None or any(
            (
                str(artifact.global_id) != str(artifact_id),
                str(artifact.tenant_id) != str(project.tenant_id),
                str(artifact.project_global_id) != str(project.global_id),
                str(artifact.batch_global_id) != str(source.batch_global_id),
                str(artifact.job_global_id) != str(job.global_id),
            )
        ):
            return None
        return artifact

    @staticmethod
    def _public_artifact(artifact: object) -> dict[str, object]:
        payload = _json_object(artifact.artifact_snapshot)
        if sha256_json(payload) != str(artifact.snapshot_hash):
            raise RuntimeError("The Tooling import correction artifact integrity drifted.")
        return {**payload, "snapshotHash": str(artifact.snapshot_hash)}

    @staticmethod
    def _verified_artifact_content(
        artifact: object,
        file_document: object,
        *,
        trace_id: str,
        replayed: bool = False,
    ) -> ToolingImportBinaryOutcome:
        raw_content = file_document.get_content()
        with _correction_server_step(
            "P607_CORRECTION_DOWNLOAD_CONTENT_VALIDATE",
            trace_id,
        ):
            if isinstance(raw_content, bytes):
                content = raw_content
            elif isinstance(raw_content, str):
                normalized_text = (
                    raw_content
                    if raw_content.startswith("\ufeff")
                    else "\ufeff" + raw_content
                )
                content = normalized_text.encode("utf-8")
            else:
                raise ToolingReferenceUnavailable()
        checks = (
            (
                "P607_CORRECTION_DOWNLOAD_PRIVACY_VALIDATE",
                int(file_document.is_private or 0) != 1,
            ),
            (
                "P607_CORRECTION_DOWNLOAD_FILE_ID_VALIDATE",
                str(file_document.name) != str(artifact.frappe_file_id),
            ),
            (
                "P607_CORRECTION_DOWNLOAD_FILE_NAME_VALIDATE",
                str(file_document.file_name) != str(artifact.file_name),
            ),
        )
        for code, failed in checks:
            with _correction_server_step(code, trace_id):
                if failed:
                    raise ToolingReferenceUnavailable()
        with _correction_server_step(
            "P607_CORRECTION_DOWNLOAD_SIZE_VALIDATE",
            trace_id,
        ):
            if len(content) != int(artifact.size_bytes):
                raise ToolingReferenceUnavailable()
        with _correction_server_step(
            "P607_CORRECTION_DOWNLOAD_DIGEST_VALIDATE",
            trace_id,
        ):
            if hashlib.sha256(content).hexdigest() != str(artifact.sha256):
                raise ToolingReferenceUnavailable()
        return ToolingImportBinaryOutcome(
            content=content,
            file_name=str(artifact.file_name),
            mime_type="text/csv",
            replayed=replayed,
        )

    def _create_reconciliation_command(
        self,
        project_id: UUID,
        batch_id: UUID,
        job_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int,
        expected_snapshot_hash: str,
        kind: str,
    ) -> ToolingImportCommandOutcome | None:
        if kind not in {"reconciliation", "rollback_eligibility"}:
            raise ValueError("unsupported reconciliation kind")
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        job = self._locked_job_for_project(project, source, job_id) if source else None
        if source is None or job is None:
            return None
        self._require_job_version(job, expected_version, expected_snapshot_hash)
        self._require_job_state(
            job,
            {
                ImportJobState.PARTIALLY_SUCCEEDED,
                ImportJobState.SUCCEEDED,
                ImportJobState.FAILED_RETRYABLE,
                ImportJobState.FAILED_FINAL,
            },
        )
        payload = {
            "batchGlobalId": str(batch_id),
            "jobGlobalId": str(job_id),
            "expectedVersion": expected_version,
            "expectedSnapshotHash": expected_snapshot_hash,
            "kind": kind,
        }
        operation = (
            "tooling_import_rollback.evaluate"
            if kind == "rollback_eligibility"
            else "tooling_import_reconciliation.create"
        )
        context = self._import_command_context(
            project,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        now = self._now()
        snapshot = self._build_reconciliation(project, source, job, kind, now)
        response_key = "rollbackEligibility" if kind == "rollback_eligibility" else "reconciliation"
        response = {response_key: _public_reconciliation(snapshot)}
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_reconciliation(project, source, snapshot)
            self._append_audit(
                operation=operation,
                global_id=snapshot.global_id,
                object_version=1,
                summary={
                    "jobGlobalId": str(job_id),
                    "jobSnapshotHash": str(job.snapshot_hash),
                    "kind": kind,
                    "targetCount": len(snapshot.items),
                    "discrepancyCount": sum(
                        1 for item in snapshot.items if item.state is not ReconciliationState.MATCHED
                    ),
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_reconciliation_revision",
                target_id=snapshot.global_id,
                response=response,
                now=now,
            )
        return ToolingImportCommandOutcome(response)

    def _build_reconciliation(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
        kind: str,
        now: datetime,
        *,
        lock_targets: bool = False,
    ) -> ReconciliationSnapshot:
        items: list[ReconciliationItem] = []
        for binding in self._target_bindings(project, source, job):
            observed_hash, downstream_count, exists = self._observe_binding(
                binding,
                for_update=lock_targets,
            )
            decision = evaluate_rollback(
                RollbackObservation(
                    action=str(binding.action),
                    created_by_batch=True,
                    exact_imported_version=(
                        exists and observed_hash == str(binding.target_snapshot_hash)
                    ),
                    downstream_reference_count=downstream_count,
                )
            )
            state = (
                rollback_item_state(decision)
                if kind == "rollback_eligibility"
                else (
                    ReconciliationState.MISSING
                    if not exists
                    else ReconciliationState.DOWNSTREAM_USED
                    if downstream_count
                    else ReconciliationState.MATCHED
                    if observed_hash == str(binding.target_snapshot_hash)
                    else ReconciliationState.CHANGED
                )
            )
            items.append(
                ReconciliationItem(
                    row_result_global_id=UUID(str(binding.row_result_global_id)),
                    target_object_type=str(binding.target_object_type),
                    target_global_id=UUID(str(binding.target_global_id)),
                    expected_snapshot_hash=str(binding.target_snapshot_hash),
                    observed_snapshot_hash=observed_hash,
                    downstream_reference_count=downstream_count,
                    state=state,
                )
            )
        return ReconciliationSnapshot(
            global_id=self._new_uuid(),
            job_global_id=UUID(str(job.global_id)),
            job_snapshot_hash=str(job.snapshot_hash),
            kind=kind,
            items=tuple(items),
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )

    def _target_bindings(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
    ) -> tuple[object, ...]:
        return self._bounded_documents(
            "NPI Tooling Import Target Binding",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "job_global_id": str(job.global_id),
            },
            maximum=_MAX_RESULTS,
            order_by="created_at asc",
        )

    @staticmethod
    def _observe_binding(
        binding: object,
        *,
        for_update: bool = False,
    ) -> tuple[str | None, int, bool]:
        loader = _optional_locked_doc if for_update else _optional_doc
        revision = loader(
            "NPI Engineering Part Revision",
            str(binding.target_global_id),
        )
        root = loader(
            "NPI Engineering Part",
            str(binding.target_root_global_id),
        )
        if revision is None or root is None:
            return None, 0, False
        exact_pointer = all(
            (
                str(root.current_revision_global_id) == str(revision.global_id),
                int(root.current_revision_number) == int(binding.target_version),
                str(root.current_revision_snapshot_hash) == str(revision.snapshot_hash),
                int(root.optimistic_version) == int(binding.target_version),
            )
        )
        downstream = sum(
            int(frappe.db.count(doctype, {fieldname: str(revision.global_id)}))
            for doctype, fieldname in _DEPENDENCY_FIELDS
        )
        return (
            str(revision.snapshot_hash) if exact_pointer else sha256_json({"changed": True}),
            downstream,
            True,
        )

    def _insert_reconciliation(
        self,
        project: object,
        source: ToolingImportSource,
        snapshot: ReconciliationSnapshot,
    ) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Import Reconciliation Revision",
                "global_id": str(snapshot.global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "job_global_id": str(snapshot.job_global_id),
                "job_snapshot_hash": snapshot.job_snapshot_hash,
                "kind": snapshot.kind,
                "item_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in snapshot.items]
                ),
                "reconciliation_snapshot": _canonical_json(snapshot.snapshot_payload()),
                "snapshot_hash": snapshot.snapshot_hash,
                "created_by_user_id": snapshot.created_by_user_id,
                "created_at": _database_datetime(snapshot.created_at),
                "request_id": str(snapshot.request_id),
                "trace_id": snapshot.trace_id,
            }
        ).insert()

    def _reconciliation_documents(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
    ) -> tuple[object, ...]:
        return self._bounded_documents(
            "NPI Tooling Import Reconciliation Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "job_global_id": str(job.global_id),
            },
            maximum=_MAX_RECONCILIATIONS,
            order_by="created_at asc",
        )

    def _reconciliation_for_job(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
        reconciliation_id: UUID,
        *,
        kind: str,
    ) -> object | None:
        row = _optional_doc(
            "NPI Tooling Import Reconciliation Revision",
            str(reconciliation_id),
        )
        if row is None or any(
            (
                str(row.global_id) != str(reconciliation_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.batch_global_id) != str(source.batch_global_id),
                str(row.job_global_id) != str(job.global_id),
                str(row.kind) != kind,
            )
        ):
            return None
        return row

    @staticmethod
    def _public_reconciliation_document(row: object) -> dict[str, object]:
        payload = _json_object(row.reconciliation_snapshot)
        if sha256_json(payload) != str(row.snapshot_hash):
            raise RuntimeError("The Tooling import reconciliation integrity drifted.")
        return {**payload, "snapshotHash": str(row.snapshot_hash)}

    def _delete_eligible_targets(
        self,
        project: object,
        source: ToolingImportSource,
        job: object,
        items: Sequence[Mapping[str, object]],
    ) -> None:
        allowed_result_ids = {str(item["rowResultGlobalId"]) for item in items}
        bindings = tuple(
            binding
            for binding in self._target_bindings(project, source, job)
            if str(binding.row_result_global_id) in allowed_result_ids
        )
        if len(bindings) != len(allowed_result_ids):
            raise ToolingReferenceUnavailable()
        targets = tuple(
            target
            for binding in bindings
            for target in (
                ("NPI Engineering Part Revision", str(binding.target_global_id)),
                ("NPI Engineering Part", str(binding.target_root_global_id)),
            )
        )
        with tooling_command_write(), tooling_import_rollback_targets(targets):
            for binding in bindings:
                frappe.delete_doc(
                    "NPI Engineering Part Revision",
                    str(binding.target_global_id),
                )
                frappe.delete_doc(
                    "NPI Engineering Part",
                    str(binding.target_root_global_id),
                )


def run_tooling_import_job(job_id: str, expected_snapshot_hash: str) -> None:
    """Reauthorize and process at most 25 exact rows per committed run."""

    require_tooling_import_routes_enabled()
    try:
        parsed_job_id = UUID(job_id)
    except (TypeError, ValueError, AttributeError) as error:
        raise RuntimeError("The Tooling import worker job identifier is invalid.") from error
    job = frappe.get_doc("NPI Tooling Import Job", str(parsed_job_id), for_update=True)
    if str(job.snapshot_hash) != expected_snapshot_hash or str(job.state) not in {
        "queued",
        "processing",
    }:
        return
    principal = authenticated_principal(str(job.actor_user_id))
    if principal.is_external or "System Manager" not in principal.roles:
        _fail_job_reauthorization(job)
        return
    repository = FrappeToolingImportExecutionRepository(
        principal=principal,
        request_id=str(job.request_id),
        trace_id=str(job.trace_id),
    )
    project_id = UUID(str(job.project_global_id))
    batch_id = UUID(str(job.batch_global_id))
    if not repository.authorize_scope(project_id, administer=True):
        _fail_job_reauthorization(job)
        return
    try:
        project = repository._locked_authorized_project(project_id)
        source = repository._source_for_project(project, batch_id) if project else None
        if project is None or source is None:
            raise ToolingReferenceUnavailable()
        repository._require_customer_scope(project, source.customer_scope_id)
        exact_job = repository._locked_job_for_project(project, source, parsed_job_id)
        if exact_job is None:
            raise ToolingReferenceUnavailable()
        repository._validated_workbook(project, source)
        preview_document = frappe.get_doc(
            "NPI Tooling Import Preview Revision",
            str(exact_job.preview_revision_global_id),
        )
        preview = repository._preview_value(source, preview_document)
        activation = repository._activation_for_preview(project, source, preview)
        if activation is None:
            raise ToolingReferenceUnavailable()
        mapping = repository._mapping_for_project(
            project,
            source,
            activation.mapping_revision_global_id,
        )
        if mapping is None or mapping.snapshot_hash != activation.mapping_snapshot_hash:
            raise ToolingReferenceUnavailable()
        corrections = repository._job_corrections(project, source, exact_job)
    except (
        frappe.DoesNotExistError,
        RequestValidationFailed,
        ToolingReferenceUnavailable,
    ):
        _fail_job_reauthorization(job)
        return

    history = repository._row_result_values(project, source, exact_job)
    processing = ToolingImportJobSnapshot(
        global_id=parsed_job_id,
        batch_global_id=batch_id,
        preview_global_id=preview.preview_global_id,
        preview_snapshot_hash=preview.snapshot_hash,
        attempt=int(exact_job.attempt),
        state=ImportJobState.PROCESSING,
        row_results=history,
        queued_at=_utc_datetime(exact_job.queued_at),
        updated_at=repository._now(),
        correction_artifact_global_id=_optional_uuid_value(
            exact_job.correction_artifact_global_id
        ),
        correction_artifact_snapshot_hash=(
            str(exact_job.correction_artifact_snapshot_hash)
            if exact_job.correction_artifact_snapshot_hash
            else None
        ),
    )
    with tooling_import_write():
        repository._apply_job_snapshot(
            exact_job,
            processing,
            int(exact_job.optimistic_version) + 1,
        )
    frappe.db.commit()

    selected = _rows_for_attempt(preview.rows, history, int(exact_job.attempt))
    for row in selected[:_MAX_ROWS_PER_RUN]:
        _execute_import_row(
            repository,
            project,
            source,
            exact_job,
            preview,
            mapping,
            row,
            corrections,
        )
    refreshed = frappe.get_doc("NPI Tooling Import Job", str(parsed_job_id), for_update=True)
    history = repository._row_result_values(project, source, refreshed)
    remaining = _rows_for_attempt(preview.rows, history, int(refreshed.attempt))
    if remaining:
        with tooling_import_write():
            repository._enqueue_job(parsed_job_id, str(refreshed.snapshot_hash))
        frappe.db.commit()
        return
    latest = latest_import_row_results(history)
    terminal_state = derive_job_state(tuple(item.state for item in latest))
    final = ToolingImportJobSnapshot(
        global_id=parsed_job_id,
        batch_global_id=batch_id,
        preview_global_id=preview.preview_global_id,
        preview_snapshot_hash=preview.snapshot_hash,
        attempt=int(refreshed.attempt),
        state=terminal_state,
        row_results=history,
        queued_at=_utc_datetime(refreshed.queued_at),
        updated_at=repository._now(),
        correction_artifact_global_id=_optional_uuid_value(
            refreshed.correction_artifact_global_id
        ),
        correction_artifact_snapshot_hash=(
            str(refreshed.correction_artifact_snapshot_hash)
            if refreshed.correction_artifact_snapshot_hash
            else None
        ),
    )
    with tooling_import_write():
        repository._apply_job_snapshot(
            refreshed,
            final,
            int(refreshed.optimistic_version) + 1,
        )
        repository._append_audit(
            operation="tooling_import_job.complete",
            global_id=parsed_job_id,
            object_version=int(refreshed.optimistic_version),
            summary={
                "attempt": final.attempt,
                "state": final.state.value,
                "resultCount": len(latest),
                "createdCount": sum(
                    1 for item in latest if item.state is ImportRowResultState.CREATED
                ),
                "failedRetryableCount": sum(
                    1
                    for item in latest
                    if item.state is ImportRowResultState.FAILED_RETRYABLE
                ),
                "failedFinalCount": sum(
                    1 for item in latest if item.state is ImportRowResultState.FAILED_FINAL
                ),
            },
        )
    frappe.db.commit()


def _execute_import_row(
    repository: FrappeToolingImportExecutionRepository,
    project: object,
    source: ToolingImportSource,
    job: object,
    preview: ToolingImportPreviewRevision,
    mapping: ToolingImportMappingRevision,
    row: PreviewRow,
    corrections: Mapping[tuple[str, int, str], str],
) -> None:
    effective = _corrected_row(row, mapping, corrections)
    now = repository._now()
    try:
        if effective.requires_confirmation:
            result = _failed_row_result(
                repository,
                effective,
                int(job.attempt),
                ImportRowResultState.CONFIRMATION_REQUIRED,
            )
            with tooling_import_write():
                repository._insert_row_result(project, source, job, result, now)
        else:
            errors = tuple(
                finding
                for field in effective.fields
                for finding in field.findings
                if finding.severity is FindingSeverity.ERROR
            )
            if errors or effective.action is PreviewAction.BLOCKED:
                state = (
                    ImportRowResultState.FAILED_RETRYABLE
                    if errors
                    else ImportRowResultState.FAILED_FINAL
                )
                result = _failed_row_result(repository, effective, int(job.attempt), state)
                with tooling_import_write():
                    repository._insert_row_result(project, source, job, result, now)
            else:
                repository._create_part_target(
                    project,
                    source,
                    job,
                    preview,
                    mapping,
                    effective,
                    now,
                )
        with tooling_import_write():
            _update_processing_job_snapshot(
                repository,
                project,
                source,
                job,
                preview,
                now,
            )
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        current_job = frappe.get_doc(
            "NPI Tooling Import Job",
            str(job.global_id),
            for_update=True,
        )
        failure = _unexpected_failed_row_result(
            repository,
            effective,
            int(current_job.attempt),
        )
        with tooling_import_write():
            failure_time = repository._now()
            repository._insert_row_result(
                project,
                source,
                current_job,
                failure,
                failure_time,
            )
            _update_processing_job_snapshot(
                repository,
                project,
                source,
                current_job,
                preview,
                failure_time,
            )
        frappe.db.commit()


def _update_processing_job_snapshot(
    repository: FrappeToolingImportExecutionRepository,
    project: object,
    source: ToolingImportSource,
    job: object,
    preview: ToolingImportPreviewRevision,
    now: datetime,
) -> None:
    history = repository._row_result_values(project, source, job)
    current = ToolingImportJobSnapshot(
        global_id=UUID(str(job.global_id)),
        batch_global_id=source.batch_global_id,
        preview_global_id=preview.preview_global_id,
        preview_snapshot_hash=preview.snapshot_hash,
        attempt=int(job.attempt),
        state=ImportJobState.PROCESSING,
        row_results=history,
        queued_at=_utc_datetime(job.queued_at),
        updated_at=now,
        correction_artifact_global_id=_optional_uuid_value(
            job.correction_artifact_global_id
        ),
        correction_artifact_snapshot_hash=(
            str(job.correction_artifact_snapshot_hash)
            if job.correction_artifact_snapshot_hash
            else None
        ),
    )
    repository._apply_job_snapshot(
        job,
        current,
        int(job.optimistic_version) + 1,
    )


def _fail_job_reauthorization(job: object) -> None:
    now = datetime.now(UTC)
    current = _job_snapshot_from_document(
        job,
        ImportJobState.FAILED_FINAL,
        now,
        row_results=_job_row_history(job),
        failure_code="worker_authorization_revoked",
        failure_message=(
            "The import worker lost its exact actor, Project, source, preview, or mapping authority."
        ),
    )
    with tooling_import_write():
        FrappeToolingImportExecutionRepository._apply_job_snapshot(
            job,
            current,
            int(job.optimistic_version) + 1,
        )
    frappe.db.commit()


# Methods attached below keep the repository class readable while remaining
# normal auditable Python functions rather than dynamic target payload hooks.
def _repository_insert_row_result(
    self: FrappeToolingImportExecutionRepository,
    project: object,
    source: ToolingImportSource,
    job: object,
    result: ImportRowResult,
    now: datetime,
) -> object:
    return frappe.get_doc(
        {
            "doctype": "NPI Tooling Import Row Result",
            "global_id": str(result.global_id),
            "result_key_hash": sha256_json(
                {
                    "jobGlobalId": str(job.global_id),
                    "worksheetName": result.worksheet_name,
                    "sourceRow": result.source_row,
                    "attempt": result.attempt,
                }
            ),
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "batch_global_id": str(source.batch_global_id),
            "job_global_id": str(job.global_id),
            "worksheet_name": result.worksheet_name,
            "source_row": result.source_row,
            "attempt": result.attempt,
            "state": result.state.value,
            "target_object_type": result.target_object_type,
            "target_global_id": (
                str(result.target_global_id) if result.target_global_id else None
            ),
            "target_snapshot_hash": result.target_snapshot_hash,
            "field_result_snapshot": _canonical_json(
                [item.snapshot_payload() for item in result.field_results]
            ),
            "row_result_snapshot": _canonical_json(result.snapshot_payload()),
            "snapshot_hash": result.snapshot_hash,
            "created_at": _database_datetime(now),
            "request_id": self.request_id,
            "trace_id": result.trace_id,
        }
    ).insert()


def _repository_create_part_target(
    self: FrappeToolingImportExecutionRepository,
    project: object,
    source: ToolingImportSource,
    job: object,
    preview: ToolingImportPreviewRevision,
    mapping: ToolingImportMappingRevision,
    row: PreviewRow,
    now: datetime,
) -> ImportRowResult:
    title_field = next(
        (
            field
            for field in row.fields
            if field.source_header.casefold() == "part name english"
        ),
        None,
    )
    if title_field is None or len(title_field.normalized_candidates) != 1:
        raise ToolingReferenceUnavailable()
    title = title_field.normalized_candidates[0]
    part_id = self._new_uuid()
    revision = EngineeringPartRevision(
        global_id=self._new_uuid(),
        part_global_id=part_id,
        tenant_id=str(project.tenant_id),
        originating_project_global_id=UUID(str(project.global_id)),
        revision_number=1,
        revision_label="IMPORT-1",
        title=title,
        reason="Controlled synthetic Tooling List import.",
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        created_by_user_id=str(job.actor_user_id),
        created_at=now,
        request_id=UUID(str(job.request_id)),
        trace_id=str(job.trace_id),
    )
    result = ImportRowResult(
        global_id=self._new_uuid(),
        worksheet_name=row.worksheet_name,
        source_row=row.source_row,
        attempt=int(job.attempt),
        state=ImportRowResultState.CREATED,
        target_object_type="engineering_part_revision",
        target_global_id=revision.global_id,
        target_snapshot_hash=revision.snapshot_hash,
        field_results=tuple(
            ImportFieldResult(
                source_ordinal=field.source_ordinal,
                source_header=field.source_header,
                result_code=(
                    "created" if field is title_field else "retained_provenance"
                ),
                message=(
                    "The field was imported."
                    if field is title_field
                    else "The source field was retained as import provenance."
                ),
                target_field="title" if field is title_field else None,
            )
            for field in row.fields
        ),
        trace_id=str(job.trace_id),
    )
    provenance_hash = sha256_json(
        {
            "batchGlobalId": str(source.batch_global_id),
            "worksheetName": row.worksheet_name,
            "sourceRow": row.source_row,
            "rawValueHashes": [field.raw_value_hash for field in row.fields],
            "transformationKeys": [field.transformation_key for field in row.fields],
            "mappingRevisionGlobalId": str(mapping.global_id),
            "mappingSnapshotHash": mapping.snapshot_hash,
            "previewSnapshotHash": preview.snapshot_hash,
        }
    )
    binding_id = self._new_uuid()
    binding_snapshot = {
        "schemaVersion": "tooling-import-target-binding.v1",
        "globalId": str(binding_id),
        "rowResultGlobalId": str(result.global_id),
        "batchGlobalId": str(source.batch_global_id),
        "jobGlobalId": str(job.global_id),
        "action": "create",
        "targetObjectType": "engineering_part_revision",
        "targetRootGlobalId": str(part_id),
        "targetGlobalId": str(revision.global_id),
        "targetVersion": 1,
        "targetSnapshotHash": revision.snapshot_hash,
        "mappingRevisionGlobalId": str(mapping.global_id),
        "mappingSnapshotHash": mapping.snapshot_hash,
        "provenanceHash": provenance_hash,
    }
    with tooling_command_write(), tooling_import_write():
        with _import_target_server_step(
            "P607_IMPORT_TARGET_ROOT_INSERT",
            self.trace_id,
        ):
            root = frappe.get_doc(
                {
                    "doctype": "NPI Engineering Part",
                    "global_id": str(part_id),
                    "tenant_id": str(project.tenant_id),
                    "originating_project_global_id": str(project.global_id),
                    "title": title,
                    "current_revision_global_id": None,
                    "current_revision_number": None,
                    "current_revision_snapshot_hash": None,
                    "optimistic_version": 1,
                }
            ).insert()
        with _import_target_server_step(
            "P607_IMPORT_TARGET_REVISION_INSERT",
            self.trace_id,
        ):
            self._insert_part_revision(revision)
        root.current_revision_global_id = str(revision.global_id)
        root.current_revision_number = 1
        root.current_revision_snapshot_hash = revision.snapshot_hash
        with _import_target_server_step(
            "P607_IMPORT_TARGET_ROOT_ADVANCE",
            self.trace_id,
        ):
            root.save()
        with _import_target_server_step(
            "P607_IMPORT_TARGET_ROW_RESULT_INSERT",
            self.trace_id,
        ):
            self._insert_row_result(project, source, job, result, now)
        with _import_target_server_step(
            "P607_IMPORT_TARGET_BINDING_INSERT",
            self.trace_id,
        ):
            frappe.get_doc(
                {
                    "doctype": "NPI Tooling Import Target Binding",
                    "global_id": str(binding_id),
                    "row_result_global_id": str(result.global_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "batch_global_id": str(source.batch_global_id),
                    "job_global_id": str(job.global_id),
                    "action": "create",
                    "target_object_type": "engineering_part_revision",
                    "target_root_global_id": str(part_id),
                    "target_global_id": str(revision.global_id),
                    "target_version": 1,
                    "target_snapshot_hash": revision.snapshot_hash,
                    "mapping_revision_global_id": str(mapping.global_id),
                    "mapping_snapshot_hash": mapping.snapshot_hash,
                    "provenance_hash": provenance_hash,
                    "binding_snapshot": _canonical_json(binding_snapshot),
                    "snapshot_hash": sha256_json(binding_snapshot),
                    "created_at": _database_datetime(now),
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                }
            ).insert()
    return result


@contextmanager
def _import_target_server_step(code: str, trace_id: str) -> Iterator[None]:
    """Record only a closed target-write stage, exception type and trace ID."""

    try:
        yield
    except Exception as error:
        try:
            exception_type = type(error).__name__
            if (
                code in _IMPORT_TARGET_DIAGNOSTIC_CODES
                and len(exception_type) <= 128
                and exception_type.isidentifier()
            ):
                from npi_core.api import record_safe_diagnostic

                record_safe_diagnostic(
                    code=code,
                    title="NPI Tooling import target substage failed",
                    exception_type=exception_type,
                    trace_id=trace_id,
                )
        except Exception:
            # Diagnostics cannot change row-result or transaction semantics.
            pass
        raise


@contextmanager
def _correction_server_step(code: str, trace_id: str) -> Iterator[None]:
    """Record only a closed correction stage, exception type and trace ID."""

    try:
        yield
    except Exception as error:
        try:
            exception_type = type(error).__name__
            if (
                code in _CORRECTION_DIAGNOSTIC_CODES
                and len(exception_type) <= 128
                and exception_type.isidentifier()
            ):
                from npi_core.api import record_safe_diagnostic

                record_safe_diagnostic(
                    code=code,
                    title="NPI Tooling import correction substage failed",
                    exception_type=exception_type,
                    trace_id=trace_id,
                )
        except Exception:
            # Diagnostics cannot change correction or transaction semantics.
            pass
        raise


def _repository_job_corrections(
    self: FrappeToolingImportExecutionRepository,
    project: object,
    source: ToolingImportSource,
    job: object,
) -> dict[tuple[str, int, str], str]:
    if (
        not job.correction_artifact_global_id
        and not job.correction_artifact_snapshot_hash
    ):
        return {}
    if (
        not job.correction_artifact_global_id
        or not job.correction_artifact_snapshot_hash
    ):
        raise ToolingReferenceUnavailable()
    artifact = self._artifact_for_job(
        project,
        source,
        job,
        UUID(str(job.correction_artifact_global_id)),
    )
    if (
        artifact is None
        or str(artifact.snapshot_hash)
        != str(job.correction_artifact_snapshot_hash)
    ):
        raise ToolingReferenceUnavailable()
    file_document = frappe.get_doc("File", str(artifact.frappe_file_id))
    content = self._verified_artifact_content(
        artifact,
        file_document,
        trace_id=self.trace_id,
    ).content
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    expected = ["worksheet_name", "source_row", "source_header", "corrected_value"]
    if reader.fieldnames != expected:
        raise ToolingReferenceUnavailable()
    result: dict[tuple[str, int, str], str] = {}
    for row in reader:
        entry = CorrectionEntry(
            worksheet_name=str(row["worksheet_name"]),
            source_row=int(row["source_row"]),
            source_header=str(row["source_header"]),
            corrected_value=str(row["corrected_value"]),
        )
        if entry.identity in result:
            raise ToolingReferenceUnavailable()
        result[entry.identity] = entry.corrected_value
    return result


FrappeToolingImportExecutionRepository._insert_row_result = _repository_insert_row_result
FrappeToolingImportExecutionRepository._create_part_target = _repository_create_part_target
FrappeToolingImportExecutionRepository._job_corrections = _repository_job_corrections


def _rows_for_attempt(
    rows: Sequence[PreviewRow],
    history: Sequence[ImportRowResult],
    attempt: int,
) -> tuple[PreviewRow, ...]:
    completed_current = {
        (item.worksheet_name, item.source_row)
        for item in history
        if item.attempt == attempt
    }
    latest = {
        (item.worksheet_name, item.source_row): item
        for item in latest_import_row_results(history)
    }
    return tuple(
        row
        for row in rows
        if (row.worksheet_name, row.source_row) not in completed_current
        and (
            attempt == 1
            or latest.get((row.worksheet_name, row.source_row)) is not None
            and latest[(row.worksheet_name, row.source_row)].state
            is ImportRowResultState.FAILED_RETRYABLE
        )
    )


def _corrected_row(
    row: PreviewRow,
    mapping: ToolingImportMappingRevision,
    corrections: Mapping[tuple[str, int, str], str],
) -> PreviewRow:
    entries = {item.source_header.casefold(): item for item in mapping.entries}
    fields = []
    for field in row.fields:
        corrected = corrections.get(
            (row.worksheet_name, row.source_row, field.source_header.casefold())
        )
        if corrected is None:
            fields.append(field)
            continue
        entry = entries.get(field.source_header.casefold())
        if entry is None:
            raise ToolingReferenceUnavailable()
        fields.append(transform_field(entry, corrected, ""))
    errors = any(
        finding.severity is FindingSeverity.ERROR
        for field in fields
        for finding in field.findings
    )
    confirmation = any(
        finding.severity is FindingSeverity.CONFIRMATION_REQUIRED
        for field in fields
        for finding in field.findings
    )
    action = PreviewAction.BLOCKED if errors or confirmation else PreviewAction.CREATE
    return replace(
        row,
        action=action,
        fields=tuple(fields),
        requires_confirmation=confirmation,
    )


def _failed_row_result(
    repository: FrappeToolingImportExecutionRepository,
    row: PreviewRow,
    attempt: int,
    state: ImportRowResultState,
) -> ImportRowResult:
    findings_by_ordinal: dict[int, tuple[object, FieldFinding]] = {}
    for field in row.fields:
        for finding in field.findings:
            if finding.severity in {
                FindingSeverity.ERROR,
                FindingSeverity.CONFIRMATION_REQUIRED,
            }:
                findings_by_ordinal.setdefault(field.source_ordinal, (field, finding))
    findings = list(findings_by_ordinal.values())
    if not findings:
        field = row.fields[0]
        findings = [
            (
                field,
                FieldFinding(
                    "execution_not_eligible",
                    FindingSeverity.ERROR,
                    "The preview row is not eligible for execution.",
                ),
            )
        ]
    return ImportRowResult(
        global_id=repository._new_uuid(),
        worksheet_name=row.worksheet_name,
        source_row=row.source_row,
        attempt=attempt,
        state=state,
        target_object_type=None,
        target_global_id=None,
        target_snapshot_hash=None,
        field_results=tuple(
            ImportFieldResult(
                source_ordinal=field.source_ordinal,
                source_header=field.source_header,
                result_code=finding.code,
                message=_finding_source_message(finding.code),
                target_field=None,
            )
            for field, finding in findings
        ),
        trace_id=repository.trace_id,
    )


def _unexpected_failed_row_result(
    repository: FrappeToolingImportExecutionRepository,
    row: PreviewRow,
    attempt: int,
) -> ImportRowResult:
    field = row.fields[0]
    return ImportRowResult(
        global_id=repository._new_uuid(),
        worksheet_name=row.worksheet_name,
        source_row=row.source_row,
        attempt=attempt,
        state=(
            ImportRowResultState.FAILED_RETRYABLE
            if attempt < 3
            else ImportRowResultState.FAILED_FINAL
        ),
        target_object_type=None,
        target_global_id=None,
        target_snapshot_hash=None,
        field_results=(
            ImportFieldResult(
                source_ordinal=field.source_ordinal,
                source_header=field.source_header,
                result_code="unexpected_retryable_failure",
                message=(
                    "The row could not be imported. Retry with the trace identifier."
                ),
                target_field=None,
            ),
        ),
        trace_id=repository.trace_id,
    )


def _fixture_mapping_entry(entry: MappingEntry) -> MappingEntry:
    if entry.source_header.casefold() == "part name english":
        return MappingEntry(
            source_ordinal=entry.source_ordinal,
            source_header=entry.source_header,
            disposition=MappingDisposition.CANDIDATE,
            target_object_candidate="engineering_part_revision",
            target_field_candidate="title",
            semantic_classification=SemanticClassification.DESCRIPTIVE,
            transformation_key="retain_raw.v1",
            validation_rule_keys=("required",),
        )
    return MappingEntry(
        source_ordinal=entry.source_ordinal,
        source_header=entry.source_header,
        disposition=MappingDisposition.CANDIDATE,
        target_object_candidate="import_provenance",
        target_field_candidate="raw_value",
        semantic_classification=SemanticClassification.UNCLASSIFIED,
        transformation_key="retain_raw.v1",
        validation_rule_keys=(),
    )


def _correction_csv(entries: Sequence[CorrectionEntry]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["worksheet_name", "source_row", "source_header", "corrected_value"])
    for item in entries:
        writer.writerow(
            [
                item.worksheet_name,
                item.source_row,
                item.source_header,
                item.corrected_value,
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _row_result_value(row: object) -> ImportRowResult:
    payload = _json_object(row.row_result_snapshot)
    fields = tuple(
        ImportFieldResult(
            source_ordinal=int(item["sourceOrdinal"]),
            source_header=str(item["sourceHeader"]),
            result_code=str(item["resultCode"]),
            message=str(item["message"]),
            target_field=(
                str(item["targetField"]) if item.get("targetField") is not None else None
            ),
        )
        for item in _json_array(payload["fieldResults"])
    )
    value = ImportRowResult(
        global_id=UUID(str(payload["globalId"])),
        worksheet_name=str(payload["worksheetName"]),
        source_row=int(payload["sourceRow"]),
        attempt=int(payload["attempt"]),
        state=ImportRowResultState(str(payload["state"])),
        target_object_type=(
            str(payload["targetObjectType"])
            if payload.get("targetObjectType") is not None
            else None
        ),
        target_global_id=(
            UUID(str(payload["targetGlobalId"]))
            if payload.get("targetGlobalId") is not None
            else None
        ),
        target_snapshot_hash=(
            str(payload["targetSnapshotHash"])
            if payload.get("targetSnapshotHash") is not None
            else None
        ),
        field_results=fields,
        trace_id=str(payload["traceId"]),
    )
    if value.snapshot_hash != str(row.snapshot_hash):
        raise RuntimeError("The Tooling import row result integrity drifted.")
    return value


def _job_snapshot_from_document(
    job: object,
    state: ImportJobState,
    now: datetime,
    *,
    row_results: Sequence[ImportRowResult] = (),
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> ToolingImportJobSnapshot:
    return ToolingImportJobSnapshot(
        global_id=UUID(str(job.global_id)),
        batch_global_id=UUID(str(job.batch_global_id)),
        preview_global_id=UUID(str(job.preview_global_id)),
        preview_snapshot_hash=str(job.preview_snapshot_hash),
        attempt=int(job.attempt),
        state=state,
        row_results=tuple(row_results),
        queued_at=_utc_datetime(job.queued_at),
        updated_at=now,
        correction_artifact_global_id=_optional_uuid_value(
            job.correction_artifact_global_id
        ),
        correction_artifact_snapshot_hash=(
            str(job.correction_artifact_snapshot_hash)
            if job.correction_artifact_snapshot_hash
            else None
        ),
        failure_code=failure_code,
        failure_message=failure_message,
        failure_trace_id=str(job.trace_id) if failure_code is not None else None,
    )


def _job_row_history(job: object) -> tuple[ImportRowResult, ...]:
    names = frappe.get_all(
        "NPI Tooling Import Row Result",
        filters={
            "tenant_id": str(job.tenant_id),
            "project_global_id": str(job.project_global_id),
            "batch_global_id": str(job.batch_global_id),
            "job_global_id": str(job.global_id),
        },
        pluck="name",
        order_by="attempt asc, source_row asc",
        limit_page_length=_MAX_RESULTS + 1,
    )
    if len(names) > _MAX_RESULTS:
        raise RuntimeError("The Tooling import row result collection exceeds its safe bound.")
    return tuple(
        _row_result_value(
            frappe.get_doc("NPI Tooling Import Row Result", str(name))
        )
        for name in names
    )


def _public_job(
    snapshot: ToolingImportJobSnapshot,
    *,
    optimistic_version: int,
) -> dict[str, object]:
    return {
        **_localized_job_payload(snapshot.snapshot_payload()),
        "optimisticVersion": optimistic_version,
        "snapshotHash": snapshot.snapshot_hash,
    }


def _optional_uuid_value(value: object) -> UUID | None:
    return UUID(str(value)) if value not in (None, "") else None


def _public_activation(value: FixtureMappingActivation) -> dict[str, object]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _public_reconciliation(value: ReconciliationSnapshot) -> dict[str, object]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _public_snapshot(value: object) -> dict[str, object]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _localized_job_payload(payload: Mapping[str, object]) -> dict[str, object]:
    rows = []
    for row in _json_array(payload.get("rowResults", [])):
        fields = [
            {
                **field,
                "message": _localized_field_result_message(
                    str(field.get("resultCode")),
                    str(field.get("message")),
                ),
            }
            for field in _json_array(row.get("fieldResults", []))
        ]
        rows.append({**row, "fieldResults": fields})
    result = {**payload, "rowResults": rows}
    failure = payload.get("failure")
    if isinstance(failure, Mapping):
        result["failure"] = {
            **failure,
            "message": _localized_job_failure_message(
                str(failure.get("code")),
                str(failure.get("message")),
            ),
        }
    return result


def _localized_field_result_message(code: str, stored_message: str) -> str:
    messages = {
        "created": ("The field was imported.", _("The field was imported.")),
        "retained_provenance": (
            "The source field was retained as import provenance.",
            _("The source field was retained as import provenance."),
        ),
        "unexpected_retryable_failure": (
            "The row could not be imported. Retry with the trace identifier.",
            _("The row could not be imported. Retry with the trace identifier."),
        ),
        "formula_error": (
            "Correct the workbook formula error.",
            _("Correct the workbook formula error."),
        ),
        "state_in_identifier": (
            "Confirm the state separated from the Tooling number.",
            _("Confirm the state separated from the Tooling number."),
        ),
        "tooling_number_missing": (
            "Enter a Tooling number or confirm a supported relationship.",
            _("Enter a Tooling number or confirm a supported relationship."),
        ),
        "mixed_or_invalid_unit": (
            "Enter one supported value and unit.",
            _("Enter one supported value and unit."),
        ),
        "mixed_tonnage_machine_type": (
            "Confirm clamp tonnage and machine type separately.",
            _("Confirm clamp tonnage and machine type separately."),
        ),
        "legacy_grade_uninterpreted": (
            "Legacy Grade is retained without inferred meaning.",
            _("Legacy Grade is retained without inferred meaning."),
        ),
        "relationship_confirmation_required": (
            "Confirm the proposed Tooling relationship.",
            _("Confirm the proposed Tooling relationship."),
        ),
        "required_value_missing": (
            "Enter the required source value.",
            _("Enter the required source value."),
        ),
        "unmapped_source_column": (
            "Confirm how the unmapped source column should be handled.",
            _("Confirm how the unmapped source column should be handled."),
        ),
        "execution_not_eligible": (
            "The preview row is not eligible for execution.",
            _("The preview row is not eligible for execution."),
        ),
    }
    try:
        source, localized = messages[code]
    except KeyError as error:
        raise ToolingReferenceUnavailable() from error
    if stored_message != source:
        raise RuntimeError("The Tooling import field result message integrity drifted.")
    return localized


def _localized_job_failure_message(code: str, stored_message: str) -> str:
    if code != "worker_authorization_revoked" or stored_message != (
        "The import worker lost its exact actor, Project, source, preview, or mapping authority."
    ):
        raise RuntimeError("The Tooling import job failure message integrity drifted.")
    return _(
        "The import worker lost its exact actor, Project, source, preview, or mapping authority."
    )


def _finding_source_message(code: str) -> str:
    messages = {
        "formula_error": "Correct the workbook formula error.",
        "state_in_identifier": "Confirm the state separated from the Tooling number.",
        "tooling_number_missing": "Enter a Tooling number or confirm a supported relationship.",
        "mixed_or_invalid_unit": "Enter one supported value and unit.",
        "mixed_tonnage_machine_type": "Confirm clamp tonnage and machine type separately.",
        "legacy_grade_uninterpreted": "Legacy Grade is retained without inferred meaning.",
        "relationship_confirmation_required": "Confirm the proposed Tooling relationship.",
        "required_value_missing": "Enter the required source value.",
        "unmapped_source_column": "Confirm how the unmapped source column should be handled.",
    }
    try:
        return messages[code]
    except KeyError as error:
        raise ToolingReferenceUnavailable() from error


def _same_eligibility_targets(
    frozen: Sequence[Mapping[str, object]],
    current: Sequence[Mapping[str, object]],
) -> bool:
    keys = (
        "rowResultGlobalId",
        "targetObjectType",
        "targetGlobalId",
        "expectedSnapshotHash",
    )
    frozen_identities = {
        tuple(str(item.get(key)) for key in keys)
        for item in frozen
    }
    current_identities = {
        tuple(str(item.get(key)) for key in keys)
        for item in current
    }
    return (
        len(frozen_identities) == len(frozen)
        and len(current_identities) == len(current)
        and frozen_identities == current_identities
    )


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _optional_locked_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name, for_update=True)
    except frappe.DoesNotExistError:
        return None


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise RuntimeError("The Tooling import execution snapshot must be an object.")
    return parsed


def _json_array(value: object) -> list[dict[str, Any]]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list) or any(not isinstance(item, dict) for item in parsed):
        raise RuntimeError("The Tooling import execution snapshot must be an array of objects.")
    return parsed


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def _utc_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
