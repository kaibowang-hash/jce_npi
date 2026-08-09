from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import (
    ToolingIdempotencyConflict,
    ToolingReferenceUnavailable,
    ToolingVersionConflict,
    sha256_json,
)
from npi_core.tooling.frappe_repository import FrappeToolingRepository
from npi_core.tooling.import_domain import (
    DETECTION_POLICY_VERSION,
    INSPECTION_POLICY_VERSION,
    TRANSFORMATION_POLICY_VERSION,
    PreviewConfirmation,
    PreviewConfirmationKind,
    ToolingImportInspectionRevision,
    ToolingImportMappingRevision,
    ToolingImportPreviewRevision,
    ToolingImportSource,
    build_mapping_proposal,
    build_preview,
    confirm_preview,
    detect_tooling_workbook,
    inspection_from_snapshot,
    mapping_from_snapshot,
    preview_from_snapshot,
    source_from_snapshot,
)
from npi_core.tooling.import_frappe_validation import tooling_import_write
from npi_core.tooling.import_mapping_catalog import (
    REVIEWED_MAPPING_CANDIDATES,
    reviewed_mapping_rows,
)
from npi_core.tooling.xlsx_inspector import (
    WorkbookRejected,
    read_validated_workbook_bytes,
)


_MAX_BATCHES = 200
_MAX_REVISIONS = 500
_MAX_ARCHIVE_ENTRIES = 10_000
_MAX_UNCOMPRESSED_BYTES = 50_000_000


@dataclass(frozen=True, slots=True)
class ToolingImportCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class FrappeToolingImportRepository(FrappeToolingRepository):
    """Project-first adapter for inspect/map/preview import metadata only."""

    def __init__(
        self,
        *,
        mapping_authority: Callable[[ToolingImportSource], Mapping[str, str]] | None = None,
        **values: object,
    ) -> None:
        super().__init__(**values)
        self._mapping_authority = mapping_authority or self._unavailable_mapping_authority

    def tooling_import_batches(self, project_id: UUID) -> dict[str, object] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        rows = self._bounded_documents(
            "NPI Tooling Import Batch",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            maximum=_MAX_BATCHES,
            order_by="created_at desc",
        )
        return {
            "projectGlobalId": str(project.global_id),
            "permissions": self._import_permissions(),
            "mappingAuthority": self._unavailable_mapping_authority(None),
            "batches": [_public_snapshot(self._source_value(row)) for row in rows],
        }

    def tooling_import_batch_detail(
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
        inspections = self._inspection_values(project, source)
        mappings = self._mapping_values(project, source)
        previews = self._preview_values(project, source)
        return {
            "projectGlobalId": str(project.global_id),
            "permissions": self._import_permissions(),
            "mappingAuthority": dict(self._mapping_authority(source)),
            "batch": _public_snapshot(source),
            "inspections": [_public_snapshot(value) for value in inspections],
            "mappingProposals": [_public_snapshot(value) for value in mappings],
            "previews": [_public_snapshot(value) for value in previews],
        }

    def create_tooling_import_batch(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        customer_scope_id: str,
        file_revision_id: UUID,
        file_optimistic_version: int,
        frappe_content_hash: str,
        sha256: str,
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        self._require_customer_scope(project, customer_scope_id)
        file_revision = self._file_revision_for_project(project, file_revision_id)
        if file_revision is None or any(
            (
                int(file_revision.optimistic_version) != file_optimistic_version,
                str(file_revision.frappe_content_hash) != frappe_content_hash,
                str(file_revision.sha256) != sha256,
            )
        ):
            raise ToolingReferenceUnavailable()
        payload = {
            "customerScopeId": customer_scope_id,
            "fileRevisionGlobalId": str(file_revision_id),
            "fileOptimisticVersion": file_optimistic_version,
            "frappeContentHash": frappe_content_hash,
            "sha256": sha256,
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_batch.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        now = self._now()
        value = ToolingImportSource(
            batch_global_id=self._new_uuid(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            customer_scope_id=customer_scope_id,
            file_revision_global_id=file_revision_id,
            file_optimistic_version=file_optimistic_version,
            frappe_content_hash=frappe_content_hash,
            file_name=str(file_revision.file_name),
            mime_type=str(file_revision.mime_type),
            size_bytes=int(file_revision.size_bytes),
            sha256=sha256,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        response = {
            "batch": _public_snapshot(value),
            "mappingAuthority": dict(self._mapping_authority(value)),
        }
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_batch.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_source(value)
            self._append_audit(
                operation="tooling_import_batch.create",
                global_id=value.batch_global_id,
                object_version=1,
                summary={
                    "projectGlobalId": str(project_id),
                    "fileRevisionGlobalId": str(file_revision_id),
                    "sourceSnapshotHash": value.snapshot_hash,
                    "sourceSha256": value.sha256,
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_batch",
                target_id=value.batch_global_id,
                response=response,
                now=now,
            )
        return ToolingImportCommandOutcome(response)

    def create_tooling_import_inspection(
        self,
        project_id: UUID,
        batch_id: UUID,
        *,
        idempotency_key_hash: str,
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        if source is None:
            return None
        payload = {
            "batchGlobalId": str(batch_id),
            "sourceSnapshotHash": source.snapshot_hash,
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_inspection.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        validated = self._validated_workbook(project, source)
        now = self._now()
        value, _data_rows = detect_tooling_workbook(
            global_id=self._new_uuid(),
            source=source,
            validated_workbook=validated,
            expected_headers=self._expected_headers(),
            created_at=now,
        )
        response = {"inspection": _public_snapshot(value)}
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_inspection.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_inspection(project, value)
            self._append_audit(
                operation="tooling_import_inspection.create",
                global_id=value.global_id,
                object_version=value.inspection_version,
                summary={
                    "batchGlobalId": str(batch_id),
                    "sourceSnapshotHash": source.snapshot_hash,
                    "inspectionSnapshotHash": value.snapshot_hash,
                    "columnCount": len(value.columns),
                    "regionCount": len(value.regions),
                    "formulaErrorCount": len(value.formula_errors),
                    "imageAnchorCount": len(value.image_anchors),
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_inspection_revision",
                target_id=value.global_id,
                response=response,
                now=now,
            )
        return ToolingImportCommandOutcome(response)

    def create_tooling_import_mapping_proposal(
        self,
        project_id: UUID,
        batch_id: UUID,
        *,
        idempotency_key_hash: str,
        inspection_id: UUID,
        inspection_snapshot_hash: str,
        template_key: str,
        reason: str,
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        if source is None:
            return None
        inspection = self._inspection_for_project(project, source, inspection_id)
        if inspection is None:
            return None
        if inspection.snapshot_hash != inspection_snapshot_hash:
            raise ToolingVersionConflict()
        payload = {
            "batchGlobalId": str(batch_id),
            "inspectionGlobalId": str(inspection_id),
            "inspectionSnapshotHash": inspection_snapshot_hash,
            "templateKey": template_key,
            "reason": reason,
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_mapping.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        now = self._now()
        value = build_mapping_proposal(
            global_id=self._new_uuid(),
            mapping_global_id=self._new_uuid(),
            inspection=inspection,
            reviewed_rows=reviewed_mapping_rows(),
            customer_scope_id=source.customer_scope_id,
            template_key=template_key,
            reason=reason,
            actor=self.actor,
            created_at=now,
        )
        response = {
            "mappingProposal": _public_snapshot(value),
            "mappingAuthority": dict(self._mapping_authority(source)),
        }
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_mapping.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_mapping(project, value)
            self._append_audit(
                operation="tooling_import_mapping.create",
                global_id=value.global_id,
                object_version=value.mapping_version,
                summary={
                    "batchGlobalId": str(batch_id),
                    "inspectionSnapshotHash": inspection.snapshot_hash,
                    "mappingSnapshotHash": value.snapshot_hash,
                    "mappingState": value.state.value,
                    "entryCount": len(value.entries),
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_mapping_revision",
                target_id=value.global_id,
                response=response,
                now=now,
            )
        return ToolingImportCommandOutcome(response)

    def create_tooling_import_preview(
        self,
        project_id: UUID,
        batch_id: UUID,
        *,
        idempotency_key_hash: str,
        inspection_id: UUID,
        inspection_snapshot_hash: str,
        mapping_id: UUID,
        mapping_snapshot_hash: str,
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        if source is None:
            return None
        inspection = self._inspection_for_project(project, source, inspection_id)
        mapping = self._mapping_for_project(project, source, mapping_id)
        if inspection is None or mapping is None:
            return None
        if (
            inspection.snapshot_hash != inspection_snapshot_hash
            or mapping.snapshot_hash != mapping_snapshot_hash
        ):
            raise ToolingVersionConflict()
        payload = {
            "batchGlobalId": str(batch_id),
            "inspectionGlobalId": str(inspection_id),
            "inspectionSnapshotHash": inspection_snapshot_hash,
            "mappingGlobalId": str(mapping_id),
            "mappingSnapshotHash": mapping_snapshot_hash,
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_preview.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        exact_inspection, data_rows = detect_tooling_workbook(
            global_id=inspection.global_id,
            source=source,
            validated_workbook=self._validated_workbook(project, source),
            expected_headers=self._expected_headers(),
            created_at=inspection.created_at,
        )
        if exact_inspection.snapshot_hash != inspection.snapshot_hash:
            raise ToolingReferenceUnavailable()
        now = self._now()
        value = build_preview(
            global_id=self._new_uuid(),
            source=source,
            inspection=inspection,
            mapping=mapping,
            data_rows=data_rows,
            created_at=now,
        )
        response = {
            "preview": _public_snapshot(value),
            "mappingAuthority": dict(self._mapping_authority(source)),
        }
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_preview.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_preview(project, value)
            self._append_audit(
                operation="tooling_import_preview.create",
                global_id=value.global_id,
                object_version=value.preview_version,
                summary={
                    "batchGlobalId": str(batch_id),
                    "inspectionSnapshotHash": inspection.snapshot_hash,
                    "mappingSnapshotHash": mapping.snapshot_hash,
                    "previewSnapshotHash": value.snapshot_hash,
                    "rowCount": len(value.rows),
                    "confirmationRequiredCount": sum(
                        1 for row in value.rows if row.requires_confirmation
                    ),
                    "executionEligible": value.execution_eligible,
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_preview_revision",
                target_id=value.global_id,
                response=response,
                now=now,
            )
        return ToolingImportCommandOutcome(response)

    def create_tooling_import_confirmation(
        self,
        project_id: UUID,
        batch_id: UUID,
        preview_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_version: int,
        expected_snapshot_hash: str,
        confirmations: Sequence[Mapping[str, object]],
    ) -> ToolingImportCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        source = self._source_for_project(project, batch_id)
        if source is None:
            return None
        payload = {
            "batchGlobalId": str(batch_id),
            "previewGlobalId": str(preview_id),
            "expectedVersion": expected_version,
            "expectedSnapshotHash": expected_snapshot_hash,
            "confirmations": [dict(item) for item in confirmations],
        }
        context = self._import_command_context(
            project,
            operation="tooling_import_confirmation.create",
            idempotency_key_hash=idempotency_key_hash,
            payload=payload,
        )
        if isinstance(context, dict):
            return ToolingImportCommandOutcome(context, replayed=True)
        receipt_key, payload_hash = context
        predecessor = self._latest_preview_for_project(project, source, preview_id)
        if predecessor is None:
            return None
        if (
            predecessor.preview_version != expected_version
            or predecessor.snapshot_hash != expected_snapshot_hash
        ):
            raise ToolingVersionConflict()
        now = self._now()
        exact = tuple(
            self._confirmation_value(project, predecessor, item, now)
            for item in confirmations
        )
        value = confirm_preview(
            global_id=self._new_uuid(),
            predecessor=predecessor,
            confirmations=exact,
            created_at=now,
        )
        response = {
            "preview": _public_snapshot(value),
            "mappingAuthority": dict(self._mapping_authority(source)),
        }
        with tooling_import_write():
            receipt = self._insert_import_receipt(
                project,
                receipt_key=receipt_key,
                operation="tooling_import_confirmation.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            self._insert_preview(project, value)
            self._append_audit(
                operation="tooling_import_confirmation.create",
                global_id=value.global_id,
                object_version=value.preview_version,
                summary={
                    "previewGlobalId": str(value.preview_global_id),
                    "predecessorSnapshotHash": predecessor.snapshot_hash,
                    "previewSnapshotHash": value.snapshot_hash,
                    "confirmationCount": len(exact),
                    "executionEligible": value.execution_eligible,
                },
            )
            self._seal_import_receipt(
                receipt,
                target_type="tooling_import_preview_revision",
                target_id=value.global_id,
                response=response,
                now=now,
            )
        return ToolingImportCommandOutcome(response)

    def _source_for_project(
        self,
        project: object,
        batch_id: UUID,
    ) -> ToolingImportSource | None:
        row = _optional_doc("NPI Tooling Import Batch", str(batch_id))
        if row is None or any(
            (
                str(row.global_id) != str(batch_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
            )
        ):
            return None
        return self._source_value(row)

    @staticmethod
    def _source_value(row: object) -> ToolingImportSource:
        value = source_from_snapshot(_json_object(row.source_snapshot))
        if value.snapshot_hash != str(row.snapshot_hash):
            raise RuntimeError("The Tooling import source snapshot integrity drifted.")
        return value

    def _inspection_values(
        self,
        project: object,
        source: ToolingImportSource,
    ) -> tuple[ToolingImportInspectionRevision, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Import Inspection Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
            },
            maximum=_MAX_REVISIONS,
            order_by="inspection_version asc",
        )
        return tuple(self._inspection_value(source, row) for row in rows)

    @staticmethod
    def _inspection_value(
        source: ToolingImportSource,
        row: object,
    ) -> ToolingImportInspectionRevision:
        value = inspection_from_snapshot(source, _json_object(row.inspection_snapshot))
        if value.snapshot_hash != str(row.snapshot_hash):
            raise RuntimeError("The Tooling import inspection snapshot integrity drifted.")
        return value

    def _inspection_for_project(
        self,
        project: object,
        source: ToolingImportSource,
        inspection_id: UUID,
    ) -> ToolingImportInspectionRevision | None:
        row = _optional_doc("NPI Tooling Import Inspection Revision", str(inspection_id))
        if row is None or any(
            (
                str(row.global_id) != str(inspection_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.batch_global_id) != str(source.batch_global_id),
                str(row.source_snapshot_hash) != source.snapshot_hash,
            )
        ):
            return None
        return self._inspection_value(source, row)

    def _mapping_values(
        self,
        project: object,
        source: ToolingImportSource,
    ) -> tuple[ToolingImportMappingRevision, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Import Mapping Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
            },
            maximum=_MAX_REVISIONS,
            order_by="created_at asc",
        )
        return tuple(self._mapping_value(source, row) for row in rows)

    @staticmethod
    def _mapping_value(
        source: ToolingImportSource,
        row: object,
    ) -> ToolingImportMappingRevision:
        value = mapping_from_snapshot(source, _json_object(row.mapping_snapshot))
        if value.snapshot_hash != str(row.snapshot_hash):
            raise RuntimeError("The Tooling import mapping snapshot integrity drifted.")
        return value

    def _mapping_for_project(
        self,
        project: object,
        source: ToolingImportSource,
        mapping_id: UUID,
    ) -> ToolingImportMappingRevision | None:
        row = _optional_doc("NPI Tooling Import Mapping Revision", str(mapping_id))
        if row is None or any(
            (
                str(row.global_id) != str(mapping_id),
                str(row.tenant_id) != str(project.tenant_id),
                str(row.project_global_id) != str(project.global_id),
                str(row.batch_global_id) != str(source.batch_global_id),
                str(row.source_snapshot_hash) != source.snapshot_hash,
            )
        ):
            return None
        return self._mapping_value(source, row)

    def _preview_values(
        self,
        project: object,
        source: ToolingImportSource,
    ) -> tuple[ToolingImportPreviewRevision, ...]:
        rows = self._bounded_documents(
            "NPI Tooling Import Preview Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
            },
            maximum=_MAX_REVISIONS,
            order_by="created_at asc",
        )
        return tuple(self._preview_value(source, row) for row in rows)

    @staticmethod
    def _preview_value(
        source: ToolingImportSource,
        row: object,
    ) -> ToolingImportPreviewRevision:
        value = preview_from_snapshot(source, _json_object(row.preview_snapshot))
        if value.snapshot_hash != str(row.snapshot_hash):
            raise RuntimeError("The Tooling import preview snapshot integrity drifted.")
        return value

    def _latest_preview_for_project(
        self,
        project: object,
        source: ToolingImportSource,
        preview_id: UUID,
    ) -> ToolingImportPreviewRevision | None:
        rows = self._bounded_documents(
            "NPI Tooling Import Preview Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(source.batch_global_id),
                "preview_global_id": str(preview_id),
            },
            maximum=_MAX_REVISIONS,
            order_by="preview_version asc",
        )
        if not rows:
            return None
        values = tuple(self._preview_value(source, row) for row in rows)
        for index, value in enumerate(values, start=1):
            if value.preview_version != index:
                raise RuntimeError("The Tooling import preview chain is not contiguous.")
            if index > 1 and (
                value.predecessor_global_id != values[index - 2].global_id
                or value.predecessor_snapshot_hash != values[index - 2].snapshot_hash
            ):
                raise RuntimeError("The Tooling import preview chain integrity drifted.")
        return values[-1]

    def _validated_workbook(
        self,
        project: object,
        source: ToolingImportSource,
    ) -> dict[str, object]:
        revision = self._file_revision_for_project(project, source.file_revision_global_id)
        if revision is None or any(
            (
                int(revision.optimistic_version) != source.file_optimistic_version,
                str(revision.frappe_content_hash) != source.frappe_content_hash,
                str(revision.sha256) != source.sha256,
                str(revision.file_name) != source.file_name,
                int(revision.size_bytes) != source.size_bytes,
            )
        ):
            raise ToolingReferenceUnavailable()
        file_document = frappe.get_doc("File", str(revision.frappe_file_id))
        content = file_document.get_content()
        if not isinstance(content, bytes) or any(
            (
                len(content) != source.size_bytes,
                hashlib.sha256(content).hexdigest() != source.sha256,
            )
        ):
            raise ToolingReferenceUnavailable()
        try:
            return read_validated_workbook_bytes(
                content,
                file_name=source.file_name,
                max_entries=_MAX_ARCHIVE_ENTRIES,
                max_uncompressed_bytes=_MAX_UNCOMPRESSED_BYTES,
            )
        except WorkbookRejected as error:
            raise RequestValidationFailed(
                field_errors=[
                    {
                        "path": "fileRevisionGlobalId",
                        "message": _("The XLSX workbook failed passive safety inspection."),
                    }
                ]
            ) from error

    def _confirmation_value(
        self,
        project: object,
        predecessor: ToolingImportPreviewRevision,
        item: Mapping[str, object],
        now: datetime,
    ) -> PreviewConfirmation:
        kind = PreviewConfirmationKind(str(item["kind"]))
        target_id = UUID(str(item["selectedTargetGlobalId"]))
        target_hash = str(item["selectedTargetSnapshotHash"])
        target_object = str(item["selectedTargetObject"])
        if target_object == "part_revision":
            target = self._part_revision_for_project(
                project,
                target_id,
                require_current=True,
            )
        elif target_object == "tooling_master":
            target = self._master_for_project(project, target_id)
        else:
            target = None
        if target is None or str(target.snapshot_hash) != target_hash:
            raise ToolingReferenceUnavailable()
        worksheet_name = str(item["worksheetName"])
        source_row = int(item["sourceRow"])
        anchor_key = str(item["anchorKey"]) if item.get("anchorKey") is not None else None
        if kind is PreviewConfirmationKind.IMAGE_ANCHOR:
            inspection = self._inspection_for_project(
                project,
                predecessor.source,
                predecessor.inspection_global_id,
            )
            if inspection is None or not any(
                anchor.anchor_key == anchor_key
                and anchor.candidate_source_row == source_row
                and anchor.requires_confirmation
                for anchor in inspection.image_anchors
            ):
                raise ToolingReferenceUnavailable()
        return PreviewConfirmation(
            kind=kind,
            worksheet_name=worksheet_name,
            source_row=source_row,
            anchor_key=anchor_key,
            selected_target_object=target_object,
            selected_target_global_id=target_id,
            selected_target_snapshot_hash=target_hash,
            reason=str(item["reason"]),
            confirmed_by_user_id=self.actor,
            confirmed_at=now,
        )

    @staticmethod
    def _expected_headers() -> tuple[str, ...]:
        return tuple(item[0] for item in REVIEWED_MAPPING_CANDIDATES)

    @staticmethod
    def _require_customer_scope(project: object, customer_scope_id: str) -> None:
        matches = [
            row
            for row in project.references
            if str(row.reference_type) == "customer"
            and str(row.source_object_id) == customer_scope_id
        ]
        if len(matches) != 1:
            raise ToolingReferenceUnavailable()

    def _import_permissions(self) -> dict[str, bool]:
        manage = self._is_internal_system_manager()
        return {
            "view": True,
            "registerSource": manage,
            "inspect": manage,
            "createMappingProposal": manage,
            "createPreview": manage,
            "confirmPreview": manage,
            "activateProductionMapping": False,
            "execute": False,
        }

    @staticmethod
    def _unavailable_mapping_authority(
        _source: ToolingImportSource | None,
    ) -> dict[str, str]:
        return {
            "state": "unavailable",
            "reasonCode": "production_mapping_unavailable",
        }

    def _import_command_context(
        self,
        project: object,
        *,
        operation: str,
        idempotency_key_hash: str,
        payload: Mapping[str, object],
    ) -> tuple[str, str] | dict[str, Any]:
        payload_hash = sha256_json(
            {
                "actorUserId": self.actor.casefold(),
                "operation": operation,
                "projectGlobalId": str(project.global_id),
                "tenantId": str(project.tenant_id),
                "payload": dict(payload),
            }
        )
        receipt_key = sha256_json(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "actorUserId": self.actor.casefold(),
                "operation": operation,
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )
        replay = self._import_receipt_replay(
            project,
            receipt_key=receipt_key,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        return replay if replay is not None else (receipt_key, payload_hash)

    def _import_receipt_replay(
        self,
        project: object,
        *,
        receipt_key: str,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        row = frappe.db.get_value(
            "NPI Tooling Import Command Idempotency",
            {"receipt_key": receipt_key},
            [
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
                "target_object_type",
                "target_global_id",
                "response_payload",
                "response_hash",
                "sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not row:
            return None
        expected = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "actor_user_id": self.actor,
            "operation": operation,
            "idempotency_key_hash": idempotency_key_hash,
            "payload_hash": payload_hash,
        }
        if any(str(_record_value(row, key)) != value for key, value in expected.items()):
            raise ToolingIdempotencyConflict()
        response = _json_object(_record_value(row, "response_payload"))
        if any(
            (
                int(_record_value(row, "sealed") or 0) != 1,
                not _record_value(row, "target_object_type"),
                not _record_value(row, "target_global_id"),
                str(_record_value(row, "response_hash")) != sha256_json(response),
            )
        ):
            raise RuntimeError("The Tooling import receipt integrity drifted.")
        return response

    def _insert_import_receipt(
        self,
        project: object,
        *,
        receipt_key: str,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
        now: datetime,
    ) -> object:
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Tooling Import Command Idempotency",
                    "global_id": str(self._new_uuid()),
                    "receipt_key": receipt_key,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "actor_user_id": self.actor,
                    "operation": operation,
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "target_object_type": None,
                    "target_global_id": None,
                    "response_payload": _canonical_json({}),
                    "response_hash": None,
                    "sealed": 0,
                    "created_at": _database_datetime(now),
                    "updated_at": _database_datetime(now),
                }
            ).insert()
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError) as error:
            raise ToolingIdempotencyConflict() from error

    @staticmethod
    def _seal_import_receipt(
        receipt: object,
        *,
        target_type: str,
        target_id: UUID,
        response: Mapping[str, object],
        now: datetime,
    ) -> None:
        receipt.target_object_type = target_type
        receipt.target_global_id = str(target_id)
        receipt.response_payload = _canonical_json(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(now)
        receipt.save()

    @staticmethod
    def _insert_source(value: ToolingImportSource) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Import Batch",
                "global_id": str(value.batch_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "customer_scope_id": value.customer_scope_id,
                "file_revision_global_id": str(value.file_revision_global_id),
                "file_optimistic_version": value.file_optimistic_version,
                "frappe_content_hash": value.frappe_content_hash,
                "file_name": value.file_name,
                "mime_type": value.mime_type,
                "size_bytes": value.size_bytes,
                "sha256": value.sha256,
                "source_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
            }
        ).insert()

    def _insert_inspection(
        self,
        project: object,
        value: ToolingImportInspectionRevision,
    ) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Import Inspection Revision",
                "global_id": str(value.global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(value.source.batch_global_id),
                "source_snapshot_hash": value.source.snapshot_hash,
                "inspection_version": value.inspection_version,
                "inspection_policy_version": INSPECTION_POLICY_VERSION,
                "detection_policy_version": DETECTION_POLICY_VERSION,
                "worksheet_name": value.worksheet_name,
                "header_row": value.header_row,
                "source_signature": value.source_signature,
                "column_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.columns]
                ),
                "region_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.regions]
                ),
                "formula_error_snapshot": _canonical_json(
                    [
                        {"cell": cell, "errorCode": code}
                        for cell, code in value.formula_errors
                    ]
                ),
                "image_anchor_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.image_anchors]
                ),
                "passive_report_hash": value.passive_report_hash,
                "inspection_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
                "created_by_user_id": self.actor,
                "created_at": _database_datetime(value.created_at),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    def _insert_mapping(
        self,
        project: object,
        value: ToolingImportMappingRevision,
    ) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Import Mapping Revision",
                "global_id": str(value.global_id),
                "mapping_global_id": str(value.mapping_global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(value.source.batch_global_id),
                "source_snapshot_hash": value.source.snapshot_hash,
                "inspection_global_id": str(value.inspection_global_id),
                "inspection_snapshot_hash": value.inspection_snapshot_hash,
                "mapping_version": value.mapping_version,
                "state": value.state.value,
                "customer_scope_id": value.customer_scope_id,
                "template_key": value.template_key,
                "source_signature": value.source_signature,
                "entry_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.entries]
                ),
                "reason": value.reason,
                "version_key_hash": sha256_json(
                    {
                        "mappingGlobalId": str(value.mapping_global_id),
                        "mappingVersion": value.mapping_version,
                    }
                ),
                "mapping_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    def _insert_preview(
        self,
        project: object,
        value: ToolingImportPreviewRevision,
    ) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Tooling Import Preview Revision",
                "global_id": str(value.global_id),
                "preview_global_id": str(value.preview_global_id),
                "preview_version": value.preview_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id)
                    if value.predecessor_global_id
                    else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "batch_global_id": str(value.source.batch_global_id),
                "source_snapshot_hash": value.source.snapshot_hash,
                "inspection_global_id": str(value.inspection_global_id),
                "inspection_snapshot_hash": value.inspection_snapshot_hash,
                "mapping_global_id": str(value.mapping_global_id),
                "mapping_snapshot_hash": value.mapping_snapshot_hash,
                "mapping_state": value.mapping_state.value,
                "transformation_policy_version": TRANSFORMATION_POLICY_VERSION,
                "execution_eligible": value.execution_eligible,
                "row_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.rows]
                ),
                "confirmation_snapshot": _canonical_json(
                    [item.snapshot_payload() for item in value.confirmations]
                ),
                "version_key_hash": sha256_json(
                    {
                        "previewGlobalId": str(value.preview_global_id),
                        "previewVersion": value.preview_version,
                    }
                ),
                "preview_snapshot": _canonical_json(value.snapshot_payload()),
                "snapshot_hash": value.snapshot_hash,
                "created_by_user_id": self.actor,
                "created_at": _database_datetime(value.created_at),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise RuntimeError("The Tooling import snapshot must be an object.")
    return parsed


def _database_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")


def _record_value(record: object, fieldname: str) -> object:
    return record.get(fieldname) if hasattr(record, "get") else getattr(record, fieldname)


def _public_snapshot(value: object) -> dict[str, object]:
    payload = dict(value.snapshot_payload())
    payload["snapshotHash"] = value.snapshot_hash
    return payload
