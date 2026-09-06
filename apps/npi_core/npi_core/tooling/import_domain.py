from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Iterable, Mapping, Sequence
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import sha256_json

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


IMPORT_SCHEMA_VERSION = "tooling-import.v1"
INSPECTION_POLICY_VERSION = "tooling-xlsx-inspection.v1"
DETECTION_POLICY_VERSION = "tooling-list-detection.v1"
TRANSFORMATION_POLICY_VERSION = "tooling-list-transform.v1"
MAX_SOURCE_BYTES = 100_000_000
_HASH = re.compile(r"^[a-f0-9]{64}$")
_CONTENT_HASH = re.compile(r"^[a-f0-9]{32,128}$")
_ACTOR = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_CELL = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*$")
_SPLIT_MULTI = re.compile(r"\s*(?:\r?\n|\s+/\s+)\s*")
_NUMBER_UNIT = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*([A-Za-z]+)\s*$")
_FORMULA_ERROR_VALUES = {
    "#BLOCKED!",
    "#BUSY!",
    "#CALC!",
    "#CONNECT!",
    "#DATA!",
    "#DIV/0!",
    "#FIELD!",
    "#GETTING_DATA",
    "#N/A",
    "#NAME?",
    "#NULL!",
    "#NUM!",
    "#PYTHON!",
    "#REF!",
    "#SPILL!",
    "#UNKNOWN!",
    "#VALUE!",
}


class WorkbookRegionKind(StrEnum):
    TITLE = "title"
    HEADER = "header"
    DATA = "data"
    SHARED_TOOLING_MARKER = "shared_tooling_marker"
    SHARED_TOOLING_DATA = "shared_tooling_data"
    SUMMARY = "summary"
    SECTION = "section"


class MappingRevisionState(StrEnum):
    PROPOSAL = "proposal"
    APPROVED_FIXTURE = "approved_fixture"
    APPROVED_PRODUCTION = "approved_production"


class MappingDisposition(StrEnum):
    CANDIDATE = "candidate"
    UNMAPPED = "unmapped"


class SemanticClassification(StrEnum):
    UNCLASSIFIED = "unclassified"
    IDENTITY = "identity"
    DESCRIPTIVE = "descriptive"
    LEGACY_GRADE = "legacy_grade"
    RELATION_CANDIDATE = "relation_candidate"
    CALCULATED_UNVERIFIED = "calculated_unverified"


class FindingSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"
    CONFIRMATION_REQUIRED = "confirmation_required"


class PreviewAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    BLOCKED = "blocked"


class PreviewConfirmationKind(StrEnum):
    IMAGE_ANCHOR = "image_anchor"
    RELATIONSHIP = "relationship"


class ImportJobState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_DENIED = "rollback_denied"


class ImportRowResultState(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    CONFIRMATION_REQUIRED = "confirmation_required"


class RollbackDecisionState(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class ToolingImportSource:
    batch_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    customer_scope_id: str
    file_revision_global_id: UUID
    file_optimistic_version: int
    frappe_content_hash: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        for field_name in (
            "batch_global_id",
            "project_global_id",
            "file_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, field_name, _uuid(getattr(self, field_name), field_name))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        object.__setattr__(
            self, "customer_scope_id", _text(self.customer_scope_id, "customerScopeId", 128)
        )
        object.__setattr__(
            self,
            "file_optimistic_version",
            _positive(self.file_optimistic_version, "fileOptimisticVersion"),
        )
        object.__setattr__(
            self,
            "frappe_content_hash",
            _content_hash(self.frappe_content_hash, "frappeContentHash"),
        )
        object.__setattr__(self, "file_name", _text(self.file_name, "fileName", 255))
        if not self.file_name.lower().endswith(".xlsx"):
            raise _problem("fileName", _("Select an XLSX workbook."))
        object.__setattr__(self, "mime_type", _text(self.mime_type, "mimeType", 255))
        if self.mime_type not in {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream",
        }:
            raise _problem("mimeType", _("Select a supported XLSX media type."))
        object.__setattr__(self, "size_bytes", _positive(self.size_bytes, "sizeBytes"))
        if self.size_bytes > MAX_SOURCE_BYTES:
            raise _problem("sizeBytes", _("Workbook size exceeds the import limit."))
        object.__setattr__(self, "sha256", _sha256(self.sha256, "sha256"))
        if not _ACTOR.fullmatch(self.created_by_user_id):
            raise _problem("createdByUserId", _("Select a valid import actor."))
        object.__setattr__(self, "created_at", _utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": IMPORT_SCHEMA_VERSION,
            "batchGlobalId": str(self.batch_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "customerScopeId": self.customer_scope_id,
            "fileRevisionGlobalId": str(self.file_revision_global_id),
            "fileOptimisticVersion": self.file_optimistic_version,
            "frappeContentHash": self.frappe_content_hash,
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "createdByUserId": self.created_by_user_id,
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class DetectedColumn:
    ordinal: int
    source_header: str
    header_cell: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ordinal", _positive(self.ordinal, "column.ordinal"))
        object.__setattr__(self, "source_header", _text(self.source_header, "column.sourceHeader", 500))
        object.__setattr__(self, "header_cell", _text(self.header_cell, "column.headerCell", 32))
        if not _CELL.fullmatch(self.header_cell):
            raise _problem("column.headerCell", _("Provide a valid worksheet cell reference."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "sourceHeader": self.source_header,
            "headerCell": self.header_cell,
        }


@dataclass(frozen=True, slots=True)
class DetectedRegion:
    kind: WorkbookRegionKind
    first_row: int
    last_row: int
    evidence: str
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, WorkbookRegionKind):
            raise _problem("region.kind", _("Select a supported workbook region."))
        object.__setattr__(self, "first_row", _positive(self.first_row, "region.firstRow"))
        object.__setattr__(self, "last_row", _positive(self.last_row, "region.lastRow"))
        if self.last_row < self.first_row:
            raise _problem("region.lastRow", _("Region end cannot be before region start."))
        object.__setattr__(self, "evidence", _text(self.evidence, "region.evidence", 500))
        if type(self.requires_confirmation) is not bool:
            raise _problem("region.requiresConfirmation", _("Confirmation state must be true or false."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "firstRow": self.first_row,
            "lastRow": self.last_row,
            "evidence": self.evidence,
            "requiresConfirmation": self.requires_confirmation,
        }


@dataclass(frozen=True, slots=True)
class DetectedImageAnchor:
    anchor_key: str
    row: int | None
    column: int | None
    confidence: str
    candidate_source_row: int | None
    requires_confirmation: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor_key", _code(self.anchor_key, "imageAnchor.anchorKey"))
        if self.row is not None:
            object.__setattr__(self, "row", _positive(self.row, "imageAnchor.row"))
        if self.column is not None:
            object.__setattr__(self, "column", _positive(self.column, "imageAnchor.column"))
        if self.confidence not in {"high", "ambiguous"}:
            raise _problem("imageAnchor.confidence", _("Select a supported image-anchor confidence."))
        if self.candidate_source_row is not None:
            object.__setattr__(self, "candidate_source_row", _positive(self.candidate_source_row, "imageAnchor.candidateSourceRow"))
        if type(self.requires_confirmation) is not bool:
            raise _problem("imageAnchor.requiresConfirmation", _("Confirmation state must be true or false."))
        if self.confidence == "ambiguous" and not self.requires_confirmation:
            raise _problem("imageAnchor.requiresConfirmation", _("An ambiguous image anchor requires human confirmation."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "anchorKey": self.anchor_key,
            "row": self.row,
            "column": self.column,
            "confidence": self.confidence,
            "candidateSourceRow": self.candidate_source_row,
            "requiresConfirmation": self.requires_confirmation,
        }


@dataclass(frozen=True, slots=True)
class ToolingImportInspectionRevision:
    global_id: UUID
    source: ToolingImportSource
    inspection_version: int
    worksheet_name: str
    header_row: int
    columns: tuple[DetectedColumn, ...]
    regions: tuple[DetectedRegion, ...]
    formula_errors: tuple[tuple[str, str], ...]
    image_anchors: tuple[DetectedImageAnchor, ...]
    passive_report_hash: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if not isinstance(self.source, ToolingImportSource):
            raise _problem("source", _("Select an exact import source."))
        object.__setattr__(self, "inspection_version", _positive(self.inspection_version, "inspectionVersion"))
        object.__setattr__(self, "worksheet_name", _text(self.worksheet_name, "worksheetName", 255))
        object.__setattr__(self, "header_row", _positive(self.header_row, "headerRow"))
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "regions", tuple(self.regions))
        object.__setattr__(self, "formula_errors", tuple(self.formula_errors))
        object.__setattr__(self, "image_anchors", tuple(self.image_anchors))
        object.__setattr__(self, "passive_report_hash", _sha256(self.passive_report_hash, "passiveReportHash"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "createdAt"))
        if not self.columns:
            raise _problem("columns", _("Workbook inspection requires detected source columns."))
        if any(not isinstance(item, DetectedColumn) for item in self.columns):
            raise _problem("columns", _("Detected columns must use the controlled column shape."))
        if len({item.ordinal for item in self.columns}) != len(self.columns):
            raise _problem("columns", _("Detected source columns must be unique."))
        if any(not isinstance(item, DetectedRegion) for item in self.regions):
            raise _problem("regions", _("Detected regions must use the controlled region shape."))
        if not any(item.kind is WorkbookRegionKind.DATA for item in self.regions):
            raise _problem("regions", _("Workbook inspection requires a data region."))
        for cell, code in self.formula_errors:
            if not _CELL.fullmatch(cell) or not code or len(code) > 64:
                raise _problem("formulaErrors", _("Provide a valid formula error reference."))
        if any(not isinstance(item, DetectedImageAnchor) for item in self.image_anchors):
            raise _problem("imageAnchors", _("Detected images must use the controlled anchor shape."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": IMPORT_SCHEMA_VERSION,
            "inspectionPolicyVersion": INSPECTION_POLICY_VERSION,
            "detectionPolicyVersion": DETECTION_POLICY_VERSION,
            "globalId": str(self.global_id),
            "batchGlobalId": str(self.source.batch_global_id),
            "sourceSnapshotHash": self.source.snapshot_hash,
            "inspectionVersion": self.inspection_version,
            "worksheetName": self.worksheet_name,
            "headerRow": self.header_row,
            "sourceSignature": self.source_signature,
            "columns": [item.snapshot_payload() for item in self.columns],
            "regions": [item.snapshot_payload() for item in self.regions],
            "formulaErrors": [
                {"cell": cell, "errorCode": code} for cell, code in self.formula_errors
            ],
            "imageAnchors": [item.snapshot_payload() for item in self.image_anchors],
            "passiveReportHash": self.passive_report_hash,
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
        }

    @property
    def source_signature(self) -> str:
        return sha256_json([item.source_header for item in self.columns])

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class MappingEntry:
    source_ordinal: int
    source_header: str
    disposition: MappingDisposition
    target_object_candidate: str | None
    target_field_candidate: str | None
    semantic_classification: SemanticClassification
    transformation_key: str
    validation_rule_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ordinal", _positive(self.source_ordinal, "mappingEntry.sourceOrdinal"))
        object.__setattr__(self, "source_header", _text(self.source_header, "mappingEntry.sourceHeader", 500))
        if not isinstance(self.disposition, MappingDisposition):
            raise _problem("mappingEntry.disposition", _("Select a supported mapping disposition."))
        for field_name in ("target_object_candidate", "target_field_candidate"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _text(value, f"mappingEntry.{field_name}", 255))
        if self.disposition is MappingDisposition.UNMAPPED and (
            self.target_object_candidate is not None or self.target_field_candidate is not None
        ):
            raise _problem("mappingEntry.disposition", _("An unmapped source column cannot claim a target field."))
        if not isinstance(self.semantic_classification, SemanticClassification):
            raise _problem("mappingEntry.semanticClassification", _("Select a supported semantic classification."))
        object.__setattr__(self, "transformation_key", _code(self.transformation_key, "mappingEntry.transformationKey"))
        keys = tuple(_code(item, "mappingEntry.validationRuleKeys") for item in self.validation_rule_keys)
        if len(set(keys)) != len(keys):
            raise _problem("mappingEntry.validationRuleKeys", _("Validation rule keys must be unique."))
        object.__setattr__(self, "validation_rule_keys", keys)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sourceOrdinal": self.source_ordinal,
            "sourceHeader": self.source_header,
            "disposition": self.disposition.value,
            "targetObjectCandidate": self.target_object_candidate,
            "targetFieldCandidate": self.target_field_candidate,
            "semanticClassification": self.semantic_classification.value,
            "transformationKey": self.transformation_key,
            "validationRuleKeys": list(self.validation_rule_keys),
        }


@dataclass(frozen=True, slots=True)
class ToolingImportMappingRevision:
    global_id: UUID
    mapping_global_id: UUID
    source: ToolingImportSource
    inspection_global_id: UUID
    inspection_snapshot_hash: str
    mapping_version: int
    state: MappingRevisionState
    customer_scope_id: str
    template_key: str
    source_signature: str
    entries: tuple[MappingEntry, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(self, "mapping_global_id", _uuid(self.mapping_global_id, "mappingGlobalId"))
        if not isinstance(self.source, ToolingImportSource):
            raise _problem("source", _("Select an exact import source."))
        object.__setattr__(self, "inspection_global_id", _uuid(self.inspection_global_id, "inspectionGlobalId"))
        object.__setattr__(self, "inspection_snapshot_hash", _sha256(self.inspection_snapshot_hash, "inspectionSnapshotHash"))
        object.__setattr__(self, "mapping_version", _positive(self.mapping_version, "mappingVersion"))
        if not isinstance(self.state, MappingRevisionState):
            raise _problem("state", _("Select a supported mapping revision state."))
        object.__setattr__(self, "customer_scope_id", _text(self.customer_scope_id, "customerScopeId", 128))
        object.__setattr__(self, "template_key", _code(self.template_key, "templateKey"))
        object.__setattr__(self, "source_signature", _sha256(self.source_signature, "sourceSignature"))
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1_000))
        if not _ACTOR.fullmatch(self.created_by_user_id):
            raise _problem("createdByUserId", _("Select a valid mapping actor."))
        object.__setattr__(self, "created_at", _utc(self.created_at, "createdAt"))
        if not self.entries or len({item.source_ordinal for item in self.entries}) != len(self.entries):
            raise _problem("entries", _("Mapping entries must cover unique source columns."))
        if any(not isinstance(item, MappingEntry) for item in self.entries):
            raise _problem("entries", _("Mapping entries must use the controlled mapping shape."))
        if self.customer_scope_id != self.source.customer_scope_id:
            raise _problem(
                "customerScopeId",
                _("Mapping customer scope does not match the import source."),
            )
        if self.state is MappingRevisionState.APPROVED_PRODUCTION:
            raise _problem("state", _("Production mapping approval is unavailable."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": IMPORT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "mappingGlobalId": str(self.mapping_global_id),
            "batchGlobalId": str(self.source.batch_global_id),
            "sourceSnapshotHash": self.source.snapshot_hash,
            "inspectionGlobalId": str(self.inspection_global_id),
            "inspectionSnapshotHash": self.inspection_snapshot_hash,
            "mappingVersion": self.mapping_version,
            "state": self.state.value,
            "customerScopeId": self.customer_scope_id,
            "templateKey": self.template_key,
            "sourceSignature": self.source_signature,
            "entries": [item.snapshot_payload() for item in self.entries],
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class FieldFinding:
    code: str
    severity: FindingSeverity
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _code(self.code, "finding.code"))
        if not isinstance(self.severity, FindingSeverity):
            raise _problem("finding.severity", _("Select a supported import finding severity."))
        object.__setattr__(self, "message", _text(self.message, "finding.message", 1_000))

    def snapshot_payload(self) -> dict[str, object]:
        return {"code": self.code, "severity": self.severity.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class TransformedField:
    source_ordinal: int
    source_header: str
    raw_value: str
    raw_value_hash: str
    normalized_candidates: tuple[str, ...]
    state_candidate: str | None
    transformation_key: str
    findings: tuple[FieldFinding, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ordinal", _positive(self.source_ordinal, "field.sourceOrdinal"))
        object.__setattr__(self, "source_header", _text(self.source_header, "field.sourceHeader", 500))
        if not isinstance(self.raw_value, str) or len(self.raw_value) > 32_767:
            raise _problem("field.rawValue", _("Provide a bounded raw workbook value."))
        object.__setattr__(self, "raw_value_hash", _sha256(self.raw_value_hash, "field.rawValueHash"))
        candidates = tuple(self.normalized_candidates)
        if len(candidates) > 100 or any(not isinstance(item, str) or len(item) > 32_767 for item in candidates):
            raise _problem("field.normalizedCandidates", _("Provide bounded normalized candidates."))
        object.__setattr__(self, "normalized_candidates", candidates)
        if self.state_candidate not in {None, "new_tooling"}:
            raise _problem("field.stateCandidate", _("Select a supported separated state candidate."))
        object.__setattr__(self, "transformation_key", _code(self.transformation_key, "field.transformationKey"))
        findings = tuple(self.findings)
        if any(not isinstance(item, FieldFinding) for item in findings):
            raise _problem("field.findings", _("Provide controlled field findings."))
        object.__setattr__(self, "findings", findings)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sourceOrdinal": self.source_ordinal,
            "sourceHeader": self.source_header,
            "rawValue": self.raw_value,
            "rawValueHash": self.raw_value_hash,
            "normalizedCandidates": list(self.normalized_candidates),
            "stateCandidate": self.state_candidate,
            "transformationKey": self.transformation_key,
            "findings": [item.snapshot_payload() for item in self.findings],
        }


@dataclass(frozen=True, slots=True)
class PreviewRow:
    worksheet_name: str
    source_row: int
    action: PreviewAction
    fields: tuple[TransformedField, ...]
    reason_codes: tuple[str, ...]
    requires_confirmation: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheet_name", _text(self.worksheet_name, "row.worksheetName", 255))
        object.__setattr__(self, "source_row", _positive(self.source_row, "row.sourceRow"))
        if not isinstance(self.action, PreviewAction):
            raise _problem("row.action", _("Select a supported preview action."))
        fields = tuple(self.fields)
        if not fields or any(not isinstance(item, TransformedField) for item in fields):
            raise _problem("row.fields", _("Preview rows require controlled field outcomes."))
        if len({item.source_ordinal for item in fields}) != len(fields):
            raise _problem("row.fields", _("Preview row source fields must be unique."))
        object.__setattr__(self, "fields", fields)
        reasons = tuple(_code(item, "row.reasonCodes") for item in self.reason_codes)
        if len(set(reasons)) != len(reasons):
            raise _problem("row.reasonCodes", _("Preview row reason codes must be unique."))
        object.__setattr__(self, "reason_codes", reasons)
        if type(self.requires_confirmation) is not bool:
            raise _problem("row.requiresConfirmation", _("Confirmation state must be true or false."))
        if self.requires_confirmation and self.action is not PreviewAction.BLOCKED:
            raise _problem("row.action", _("A row requiring confirmation must remain blocked."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "worksheetName": self.worksheet_name,
            "sourceRow": self.source_row,
            "action": self.action.value,
            "fields": [item.snapshot_payload() for item in self.fields],
            "reasonCodes": list(self.reason_codes),
            "requiresConfirmation": self.requires_confirmation,
        }


@dataclass(frozen=True, slots=True)
class PreviewConfirmation:
    kind: PreviewConfirmationKind
    worksheet_name: str
    source_row: int
    anchor_key: str | None
    selected_target_object: str
    selected_target_global_id: UUID
    selected_target_snapshot_hash: str
    reason: str
    confirmed_by_user_id: str
    confirmed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PreviewConfirmationKind):
            raise _problem("confirmation.kind", _("Select a supported confirmation kind."))
        object.__setattr__(self, "worksheet_name", _text(self.worksheet_name, "confirmation.worksheetName", 255))
        object.__setattr__(self, "source_row", _positive(self.source_row, "confirmation.sourceRow"))
        if self.anchor_key is not None:
            object.__setattr__(self, "anchor_key", _code(self.anchor_key, "confirmation.anchorKey"))
        if self.kind is PreviewConfirmationKind.IMAGE_ANCHOR and self.anchor_key is None:
            raise _problem("confirmation.anchorKey", _("Select the exact image anchor."))
        if self.kind is PreviewConfirmationKind.RELATIONSHIP and self.anchor_key is not None:
            raise _problem("confirmation.anchorKey", _("A relationship confirmation cannot claim an image anchor."))
        if self.selected_target_object not in {"part_revision", "tooling_master"}:
            raise _problem("confirmation.selectedTargetObject", _("Select a supported confirmation target."))
        object.__setattr__(self, "selected_target_global_id", _uuid(self.selected_target_global_id, "confirmation.selectedTargetGlobalId"))
        object.__setattr__(self, "selected_target_snapshot_hash", _sha256(self.selected_target_snapshot_hash, "confirmation.selectedTargetSnapshotHash"))
        object.__setattr__(self, "reason", _text(self.reason, "confirmation.reason", 1_000))
        if not _ACTOR.fullmatch(self.confirmed_by_user_id):
            raise _problem("confirmation.confirmedByUserId", _("Select a valid confirmation actor."))
        object.__setattr__(self, "confirmed_at", _utc(self.confirmed_at, "confirmation.confirmedAt"))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "worksheetName": self.worksheet_name,
            "sourceRow": self.source_row,
            "anchorKey": self.anchor_key,
            "selectedTargetObject": self.selected_target_object,
            "selectedTargetGlobalId": str(self.selected_target_global_id),
            "selectedTargetSnapshotHash": self.selected_target_snapshot_hash,
            "reason": self.reason,
            "confirmedByUserId": self.confirmed_by_user_id,
            "confirmedAt": self.confirmed_at.isoformat().replace("+00:00", "Z"),
        }


@dataclass(frozen=True, slots=True)
class ToolingImportPreviewRevision:
    global_id: UUID
    preview_global_id: UUID
    preview_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    source: ToolingImportSource
    inspection_global_id: UUID
    inspection_snapshot_hash: str
    mapping_global_id: UUID
    mapping_snapshot_hash: str
    mapping_state: MappingRevisionState
    rows: tuple[PreviewRow, ...]
    confirmations: tuple[PreviewConfirmation, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(self, "preview_global_id", _uuid(self.preview_global_id, "previewGlobalId"))
        object.__setattr__(self, "preview_version", _positive(self.preview_version, "previewVersion"))
        if self.predecessor_global_id is not None:
            object.__setattr__(self, "predecessor_global_id", _uuid(self.predecessor_global_id, "predecessorGlobalId"))
        if self.predecessor_snapshot_hash is not None:
            object.__setattr__(self, "predecessor_snapshot_hash", _sha256(self.predecessor_snapshot_hash, "predecessorSnapshotHash"))
        if (self.predecessor_global_id is None) != (self.predecessor_snapshot_hash is None):
            raise _problem("predecessor", _("Preview predecessor identity and hash must be provided together."))
        if self.preview_version == 1 and self.predecessor_global_id is not None:
            raise _problem("predecessor", _("The first preview revision cannot have a predecessor."))
        if self.preview_version > 1 and self.predecessor_global_id is None:
            raise _problem("predecessor", _("A successor preview requires an exact predecessor."))
        if not isinstance(self.source, ToolingImportSource):
            raise _problem("source", _("Select an exact import source."))
        object.__setattr__(self, "inspection_global_id", _uuid(self.inspection_global_id, "inspectionGlobalId"))
        object.__setattr__(self, "inspection_snapshot_hash", _sha256(self.inspection_snapshot_hash, "inspectionSnapshotHash"))
        object.__setattr__(self, "mapping_global_id", _uuid(self.mapping_global_id, "mappingGlobalId"))
        object.__setattr__(self, "mapping_snapshot_hash", _sha256(self.mapping_snapshot_hash, "mappingSnapshotHash"))
        if not isinstance(self.mapping_state, MappingRevisionState):
            raise _problem("mappingState", _("Select a supported mapping revision state."))
        if self.mapping_state is MappingRevisionState.APPROVED_PRODUCTION:
            raise _problem("mappingState", _("Production mapping approval is unavailable."))
        object.__setattr__(self, "rows", tuple(self.rows))
        object.__setattr__(self, "confirmations", tuple(self.confirmations))
        object.__setattr__(self, "created_at", _utc(self.created_at, "createdAt"))
        if not self.rows:
            raise _problem("rows", _("Import preview requires at least one source row."))
        if any(not isinstance(item, PreviewRow) for item in self.rows):
            raise _problem("rows", _("Import preview rows must use the controlled preview shape."))
        if len({(item.worksheet_name, item.source_row) for item in self.rows}) != len(self.rows):
            raise _problem("rows", _("Import preview source rows must be unique."))
        if any(not isinstance(item, PreviewConfirmation) for item in self.confirmations):
            raise _problem("confirmations", _("Preview confirmations must use the controlled confirmation shape."))
        identities = {
            (item.kind, item.worksheet_name, item.source_row, item.anchor_key)
            for item in self.confirmations
        }
        if len(identities) != len(self.confirmations):
            raise _problem("confirmations", _("Preview confirmations must be unique."))

    @property
    def execution_eligible(self) -> bool:
        return (
            self.mapping_state is MappingRevisionState.APPROVED_FIXTURE
            and all(not row.requires_confirmation for row in self.rows)
            and any(row.action is not PreviewAction.BLOCKED for row in self.rows)
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": IMPORT_SCHEMA_VERSION,
            "transformationPolicyVersion": TRANSFORMATION_POLICY_VERSION,
            "globalId": str(self.global_id),
            "previewGlobalId": str(self.preview_global_id),
            "previewVersion": self.preview_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "batchGlobalId": str(self.source.batch_global_id),
            "sourceSnapshotHash": self.source.snapshot_hash,
            "inspectionGlobalId": str(self.inspection_global_id),
            "inspectionSnapshotHash": self.inspection_snapshot_hash,
            "mappingGlobalId": str(self.mapping_global_id),
            "mappingSnapshotHash": self.mapping_snapshot_hash,
            "mappingState": self.mapping_state.value,
            "executionEligible": self.execution_eligible,
            "rows": [item.snapshot_payload() for item in self.rows],
            "confirmations": [item.snapshot_payload() for item in self.confirmations],
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class ImportFieldResult:
    source_ordinal: int
    source_header: str
    result_code: str
    message: str
    target_field: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ordinal", _positive(self.source_ordinal, "fieldResult.sourceOrdinal"))
        object.__setattr__(self, "source_header", _text(self.source_header, "fieldResult.sourceHeader", 500))
        object.__setattr__(self, "result_code", _code(self.result_code, "fieldResult.resultCode"))
        object.__setattr__(self, "message", _text(self.message, "fieldResult.message", 1_000))
        if self.target_field is not None:
            object.__setattr__(self, "target_field", _text(self.target_field, "fieldResult.targetField", 255))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sourceOrdinal": self.source_ordinal,
            "sourceHeader": self.source_header,
            "resultCode": self.result_code,
            "message": self.message,
            "targetField": self.target_field,
        }


@dataclass(frozen=True, slots=True)
class ImportRowResult:
    global_id: UUID
    worksheet_name: str
    source_row: int
    attempt: int
    state: ImportRowResultState
    target_object_type: str | None
    target_global_id: UUID | None
    target_snapshot_hash: str | None
    field_results: tuple[ImportFieldResult, ...]
    trace_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "rowResult.globalId"))
        object.__setattr__(self, "worksheet_name", _text(self.worksheet_name, "rowResult.worksheetName", 255))
        object.__setattr__(self, "source_row", _positive(self.source_row, "rowResult.sourceRow"))
        object.__setattr__(self, "attempt", _positive(self.attempt, "rowResult.attempt"))
        if not isinstance(self.state, ImportRowResultState):
            raise _problem("rowResult.state", _("Select a supported import row result state."))
        if self.target_object_type is not None:
            object.__setattr__(self, "target_object_type", _code(self.target_object_type, "rowResult.targetObjectType"))
        if self.target_global_id is not None:
            object.__setattr__(self, "target_global_id", _uuid(self.target_global_id, "rowResult.targetGlobalId"))
        if self.target_snapshot_hash is not None:
            object.__setattr__(self, "target_snapshot_hash", _sha256(self.target_snapshot_hash, "rowResult.targetSnapshotHash"))
        field_results = tuple(self.field_results)
        if not field_results or any(
            not isinstance(item, ImportFieldResult) for item in field_results
        ):
            raise _problem(
                "rowResult.fieldResults",
                _("Import field results must use the controlled field shape."),
            )
        if len({item.source_ordinal for item in field_results}) != len(field_results):
            raise _problem(
                "rowResult.fieldResults",
                _("Import field results must cover unique source columns."),
            )
        object.__setattr__(self, "field_results", field_results)
        object.__setattr__(self, "trace_id", _text(self.trace_id, "rowResult.traceId", 128))
        has_target = self.target_object_type is not None or self.target_global_id is not None or self.target_snapshot_hash is not None
        if self.state in {ImportRowResultState.CREATED, ImportRowResultState.UPDATED}:
            if None in {self.target_object_type, self.target_global_id, self.target_snapshot_hash}:
                raise _problem("rowResult.target", _("A successful import row requires exact target truth."))
        elif has_target:
            raise _problem("rowResult.target", _("A non-mutating import row cannot claim target truth."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "worksheetName": self.worksheet_name,
            "sourceRow": self.source_row,
            "attempt": self.attempt,
            "state": self.state.value,
            "targetObjectType": self.target_object_type,
            "targetGlobalId": str(self.target_global_id) if self.target_global_id else None,
            "targetSnapshotHash": self.target_snapshot_hash,
            "fieldResults": [item.snapshot_payload() for item in self.field_results],
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class ToolingImportJobSnapshot:
    global_id: UUID
    batch_global_id: UUID
    preview_global_id: UUID
    preview_snapshot_hash: str
    attempt: int
    state: ImportJobState
    row_results: tuple[ImportRowResult, ...]
    queued_at: datetime
    updated_at: datetime
    correction_artifact_global_id: UUID | None = None
    correction_artifact_snapshot_hash: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    failure_trace_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "job.globalId"))
        object.__setattr__(self, "batch_global_id", _uuid(self.batch_global_id, "job.batchGlobalId"))
        object.__setattr__(self, "preview_global_id", _uuid(self.preview_global_id, "job.previewGlobalId"))
        object.__setattr__(self, "preview_snapshot_hash", _sha256(self.preview_snapshot_hash, "job.previewSnapshotHash"))
        object.__setattr__(self, "attempt", _positive(self.attempt, "job.attempt"))
        if not isinstance(self.state, ImportJobState):
            raise _problem("job.state", _("Select a supported Tooling import job state."))
        row_results = tuple(self.row_results)
        if any(not isinstance(item, ImportRowResult) for item in row_results):
            raise _problem(
                "job.rowResults",
                _("Import job rows must use the controlled result shape."),
            )
        identities = {
            (item.worksheet_name, item.source_row, item.attempt)
            for item in row_results
        }
        if len(identities) != len(row_results):
            raise _problem(
                "job.rowResults", _("Import job row results must be unique.")
            )
        object.__setattr__(self, "row_results", row_results)
        object.__setattr__(self, "queued_at", _utc(self.queued_at, "job.queuedAt"))
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "job.updatedAt"))
        if self.updated_at < self.queued_at:
            raise _problem("job.updatedAt", _("Job update time cannot be earlier than queue time."))
        if (self.correction_artifact_global_id is None) != (
            self.correction_artifact_snapshot_hash is None
        ):
            raise _problem(
                "job.correctionArtifact",
                _("Correction artifact identity and hash must be supplied together."),
            )
        if self.correction_artifact_global_id is not None:
            object.__setattr__(
                self,
                "correction_artifact_global_id",
                _uuid(
                    self.correction_artifact_global_id,
                    "job.correctionArtifactGlobalId",
                ),
            )
            object.__setattr__(
                self,
                "correction_artifact_snapshot_hash",
                _sha256(
                    self.correction_artifact_snapshot_hash,
                    "job.correctionArtifactSnapshotHash",
                ),
            )
            if self.attempt == 1:
                raise _problem(
                    "job.correctionArtifact",
                    _("The first import attempt cannot use a correction artifact."),
                )
        elif self.attempt > 1:
            raise _problem(
                "job.correctionArtifact",
                _("A retry attempt requires an exact correction artifact."),
            )
        failure_values = (
            self.failure_code,
            self.failure_message,
            self.failure_trace_id,
        )
        if any(value is not None for value in failure_values):
            if any(value is None for value in failure_values):
                raise _problem(
                    "job.failure",
                    _("Import job failure code, message and trace must be supplied together."),
                )
            if self.state is not ImportJobState.FAILED_FINAL:
                raise _problem(
                    "job.failure",
                    _("Only a final failed import job can record a job-level failure."),
                )
            object.__setattr__(self, "failure_code", _code(self.failure_code, "job.failure.code"))
            object.__setattr__(self, "failure_message", _text(self.failure_message, "job.failure.message", 1_000))
            object.__setattr__(self, "failure_trace_id", _text(self.failure_trace_id, "job.failure.traceId", 128))
        latest = latest_import_row_results(row_results)
        if self.state in {ImportJobState.QUEUED, ImportJobState.PROCESSING}:
            if self.state is ImportJobState.QUEUED and any(
                item.attempt == self.attempt for item in row_results
            ):
                raise _problem(
                    "job.rowResults",
                    _("A queued import attempt cannot already contain results."),
                )
        elif self.state in {ImportJobState.ROLLED_BACK, ImportJobState.ROLLBACK_DENIED}:
            if not latest:
                raise _problem("job.rowResults", _("A rollback result requires retained import row truth."))
        elif self.state is ImportJobState.FAILED_FINAL and self.failure_code is not None:
            # A worker may fail closed before or between bounded runs when its
            # preserved actor or exact source authority is revoked.
            pass
        elif self.state is not derive_job_state(tuple(item.state for item in latest)):
            raise _problem("job.state", _("Import job state does not match its row results."))

    def snapshot_payload(self) -> dict[str, object]:
        latest = latest_import_row_results(self.row_results)
        counts = {
            state.value: sum(1 for item in latest if item.state is state)
            for state in ImportRowResultState
        }
        return {
            "schemaVersion": IMPORT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "batchGlobalId": str(self.batch_global_id),
            "previewGlobalId": str(self.preview_global_id),
            "previewSnapshotHash": self.preview_snapshot_hash,
            "attempt": self.attempt,
            "state": self.state.value,
            "counts": counts,
            "rowResults": [item.snapshot_payload() for item in self.row_results],
            "queuedAt": self.queued_at.isoformat().replace("+00:00", "Z"),
            "updatedAt": self.updated_at.isoformat().replace("+00:00", "Z"),
            "correctionArtifactGlobalId": (
                str(self.correction_artifact_global_id)
                if self.correction_artifact_global_id is not None
                else None
            ),
            "correctionArtifactSnapshotHash": self.correction_artifact_snapshot_hash,
            "failure": (
                {
                    "code": self.failure_code,
                    "message": self.failure_message,
                    "traceId": self.failure_trace_id,
                }
                if self.failure_code is not None
                else None
            ),
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class RollbackObservation:
    action: str
    created_by_batch: bool
    exact_imported_version: bool
    downstream_reference_count: int

    def __post_init__(self) -> None:
        if self.action not in {"create", "update"}:
            raise _problem(
                "rollback.action", _("Rollback action must be create or update.")
            )
        if type(self.created_by_batch) is not bool or type(self.exact_imported_version) is not bool:
            raise _problem(
                "rollback.evidence",
                _("Rollback evidence states must be true or false."),
            )
        if type(self.downstream_reference_count) is not int or self.downstream_reference_count < 0:
            raise _problem(
                "rollback.downstreamReferenceCount",
                _("Downstream reference count cannot be negative."),
            )


@dataclass(frozen=True, slots=True)
class RollbackDecision:
    state: RollbackDecisionState
    reason_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.state, RollbackDecisionState):
            raise _problem(
                "rollback.state", _("Select a supported rollback decision.")
            )
        object.__setattr__(
            self,
            "reason_code",
            _code(self.reason_code, "rollback.reasonCode"),
        )


def source_from_snapshot(snapshot: Mapping[str, object]) -> ToolingImportSource:
    value = _mapping(snapshot, "sourceSnapshot")
    _require_schema(value)
    return ToolingImportSource(
        batch_global_id=_uuid(value.get("batchGlobalId"), "batchGlobalId"),
        tenant_id=str(value.get("tenantId", "")),
        project_global_id=_uuid(value.get("projectGlobalId"), "projectGlobalId"),
        customer_scope_id=str(value.get("customerScopeId", "")),
        file_revision_global_id=_uuid(value.get("fileRevisionGlobalId"), "fileRevisionGlobalId"),
        file_optimistic_version=value.get("fileOptimisticVersion"),
        frappe_content_hash=str(value.get("frappeContentHash", "")),
        file_name=str(value.get("fileName", "")),
        mime_type=str(value.get("mimeType", "")),
        size_bytes=value.get("sizeBytes"),
        sha256=str(value.get("sha256", "")),
        created_by_user_id=str(value.get("createdByUserId", "")),
        created_at=_payload_datetime(value.get("createdAt"), "createdAt"),
        request_id=_uuid(value.get("requestId"), "requestId"),
        trace_id=str(value.get("traceId", "")),
    )


def inspection_from_snapshot(
    source: ToolingImportSource,
    snapshot: Mapping[str, object],
) -> ToolingImportInspectionRevision:
    value = _mapping(snapshot, "inspectionSnapshot")
    _require_schema(value)
    columns = tuple(
        DetectedColumn(
            ordinal=item.get("ordinal"),
            source_header=str(item.get("sourceHeader", "")),
            header_cell=str(item.get("headerCell", "")),
        )
        for item in (
            _mapping(candidate, "columns")
            for candidate in _sequence(value.get("columns"), "columns")
        )
    )
    regions = tuple(
        DetectedRegion(
            kind=WorkbookRegionKind(str(item.get("kind", ""))),
            first_row=item.get("firstRow"),
            last_row=item.get("lastRow"),
            evidence=str(item.get("evidence", "")),
            requires_confirmation=item.get("requiresConfirmation"),
        )
        for item in (
            _mapping(candidate, "regions")
            for candidate in _sequence(value.get("regions"), "regions")
        )
    )
    errors = tuple(
        (str(item.get("cell", "")), str(item.get("errorCode", "")))
        for item in (
            _mapping(candidate, "formulaErrors")
            for candidate in _sequence(value.get("formulaErrors"), "formulaErrors")
        )
    )
    anchors = tuple(
        DetectedImageAnchor(
            anchor_key=str(item.get("anchorKey", "")),
            row=item.get("row"),
            column=item.get("column"),
            confidence=str(item.get("confidence", "")),
            candidate_source_row=item.get("candidateSourceRow"),
            requires_confirmation=item.get("requiresConfirmation"),
        )
        for item in (
            _mapping(candidate, "imageAnchors")
            for candidate in _sequence(value.get("imageAnchors"), "imageAnchors")
        )
    )
    result = ToolingImportInspectionRevision(
        global_id=_uuid(value.get("globalId"), "globalId"),
        source=source,
        inspection_version=value.get("inspectionVersion"),
        worksheet_name=str(value.get("worksheetName", "")),
        header_row=value.get("headerRow"),
        columns=columns,
        regions=regions,
        formula_errors=errors,
        image_anchors=anchors,
        passive_report_hash=str(value.get("passiveReportHash", "")),
        created_at=_payload_datetime(value.get("createdAt"), "createdAt"),
    )
    if result.snapshot_payload() != dict(value):
        raise _problem("inspectionSnapshot", _("Inspection snapshot integrity check failed."))
    return result


def mapping_from_snapshot(
    source: ToolingImportSource,
    snapshot: Mapping[str, object],
) -> ToolingImportMappingRevision:
    value = _mapping(snapshot, "mappingSnapshot")
    _require_schema(value)
    entries = tuple(
        MappingEntry(
            source_ordinal=item.get("sourceOrdinal"),
            source_header=str(item.get("sourceHeader", "")),
            disposition=MappingDisposition(str(item.get("disposition", ""))),
            target_object_candidate=(
                str(item.get("targetObjectCandidate"))
                if item.get("targetObjectCandidate") is not None
                else None
            ),
            target_field_candidate=(
                str(item.get("targetFieldCandidate"))
                if item.get("targetFieldCandidate") is not None
                else None
            ),
            semantic_classification=SemanticClassification(
                str(item.get("semanticClassification", ""))
            ),
            transformation_key=str(item.get("transformationKey", "")),
            validation_rule_keys=tuple(
                str(candidate)
                for candidate in _sequence(
                    item.get("validationRuleKeys"), "validationRuleKeys"
                )
            ),
        )
        for item in (
            _mapping(candidate, "entries")
            for candidate in _sequence(value.get("entries"), "entries")
        )
    )
    result = ToolingImportMappingRevision(
        global_id=_uuid(value.get("globalId"), "globalId"),
        mapping_global_id=_uuid(value.get("mappingGlobalId"), "mappingGlobalId"),
        source=source,
        inspection_global_id=_uuid(value.get("inspectionGlobalId"), "inspectionGlobalId"),
        inspection_snapshot_hash=str(value.get("inspectionSnapshotHash", "")),
        mapping_version=value.get("mappingVersion"),
        state=MappingRevisionState(str(value.get("state", ""))),
        customer_scope_id=str(value.get("customerScopeId", "")),
        template_key=str(value.get("templateKey", "")),
        source_signature=str(value.get("sourceSignature", "")),
        entries=entries,
        reason=str(value.get("reason", "")),
        created_by_user_id=str(value.get("createdByUserId", "")),
        created_at=_payload_datetime(value.get("createdAt"), "createdAt"),
    )
    if result.snapshot_payload() != dict(value):
        raise _problem("mappingSnapshot", _("Mapping snapshot integrity check failed."))
    return result


def preview_from_snapshot(
    source: ToolingImportSource,
    snapshot: Mapping[str, object],
) -> ToolingImportPreviewRevision:
    value = _mapping(snapshot, "previewSnapshot")
    _require_schema(value)
    rows = tuple(_preview_row_from_payload(item) for item in _sequence(value.get("rows"), "rows"))
    confirmations = tuple(
        PreviewConfirmation(
            kind=PreviewConfirmationKind(str(item.get("kind", ""))),
            worksheet_name=str(item.get("worksheetName", "")),
            source_row=item.get("sourceRow"),
            anchor_key=(str(item.get("anchorKey")) if item.get("anchorKey") is not None else None),
            selected_target_object=str(item.get("selectedTargetObject", "")),
            selected_target_global_id=_uuid(item.get("selectedTargetGlobalId"), "selectedTargetGlobalId"),
            selected_target_snapshot_hash=str(item.get("selectedTargetSnapshotHash", "")),
            reason=str(item.get("reason", "")),
            confirmed_by_user_id=str(item.get("confirmedByUserId", "")),
            confirmed_at=_payload_datetime(item.get("confirmedAt"), "confirmedAt"),
        )
        for item in (
            _mapping(candidate, "confirmations")
            for candidate in _sequence(value.get("confirmations"), "confirmations")
        )
    )
    result = ToolingImportPreviewRevision(
        global_id=_uuid(value.get("globalId"), "globalId"),
        preview_global_id=_uuid(value.get("previewGlobalId"), "previewGlobalId"),
        preview_version=value.get("previewVersion"),
        predecessor_global_id=(
            _uuid(value.get("predecessorGlobalId"), "predecessorGlobalId")
            if value.get("predecessorGlobalId") is not None
            else None
        ),
        predecessor_snapshot_hash=(
            str(value.get("predecessorSnapshotHash"))
            if value.get("predecessorSnapshotHash") is not None
            else None
        ),
        source=source,
        inspection_global_id=_uuid(value.get("inspectionGlobalId"), "inspectionGlobalId"),
        inspection_snapshot_hash=str(value.get("inspectionSnapshotHash", "")),
        mapping_global_id=_uuid(value.get("mappingGlobalId"), "mappingGlobalId"),
        mapping_snapshot_hash=str(value.get("mappingSnapshotHash", "")),
        mapping_state=MappingRevisionState(str(value.get("mappingState", ""))),
        rows=rows,
        confirmations=confirmations,
        created_at=_payload_datetime(value.get("createdAt"), "createdAt"),
    )
    if result.snapshot_payload() != dict(value):
        raise _problem("previewSnapshot", _("Preview snapshot integrity check failed."))
    return result


def _preview_row_from_payload(candidate: object) -> PreviewRow:
    item = _mapping(candidate, "rows")
    fields = tuple(
        TransformedField(
            source_ordinal=field.get("sourceOrdinal"),
            source_header=str(field.get("sourceHeader", "")),
            raw_value=str(field.get("rawValue", "")),
            raw_value_hash=str(field.get("rawValueHash", "")),
            normalized_candidates=tuple(
                str(value)
                for value in _sequence(
                    field.get("normalizedCandidates"), "normalizedCandidates"
                )
            ),
            state_candidate=(
                str(field.get("stateCandidate"))
                if field.get("stateCandidate") is not None
                else None
            ),
            transformation_key=str(field.get("transformationKey", "")),
            findings=tuple(
                FieldFinding(
                    code=str(finding.get("code", "")),
                    severity=FindingSeverity(str(finding.get("severity", ""))),
                    message=str(finding.get("message", "")),
                )
                for finding in (
                    _mapping(value, "findings")
                    for value in _sequence(field.get("findings"), "findings")
                )
            ),
        )
        for field in (
            _mapping(value, "fields")
            for value in _sequence(item.get("fields"), "fields")
        )
    )
    return PreviewRow(
        worksheet_name=str(item.get("worksheetName", "")),
        source_row=item.get("sourceRow"),
        action=PreviewAction(str(item.get("action", ""))),
        fields=fields,
        reason_codes=tuple(
            str(value) for value in _sequence(item.get("reasonCodes"), "reasonCodes")
        ),
        requires_confirmation=item.get("requiresConfirmation"),
    )


def detect_tooling_workbook(
    *,
    global_id: UUID,
    source: ToolingImportSource,
    validated_workbook: Mapping[str, object],
    expected_headers: Sequence[str],
    created_at: datetime,
) -> tuple[ToolingImportInspectionRevision, tuple[Mapping[str, object], ...]]:
    inspection = _mapping(validated_workbook.get("inspection"), "inspection")
    if inspection.get("sha256") != source.sha256:
        raise _problem("inspection.sha256", _("Workbook hash does not match the exact File Revision."))
    if (
        inspection.get("file_name") != source.file_name
        or inspection.get("input_bytes") != source.size_bytes
    ):
        raise _problem(
            "inspection.source",
            _("Workbook metadata does not match the exact File Revision."),
        )
    worksheets = _sequence(validated_workbook.get("worksheets"), "worksheets")
    if len(worksheets) != 1:
        raise _problem("worksheets", _("Select a workbook with exactly one Tooling List worksheet."))
    worksheet = _mapping(worksheets[0], "worksheet")
    rows = tuple(_mapping(item, "worksheet.rows") for item in _sequence(worksheet.get("rows"), "worksheet.rows"))
    expected = {_normalize_header(value): value for value in expected_headers}
    scored: list[tuple[int, int, Mapping[str, object]]] = []
    for row in rows:
        values = _row_values(row)
        score = sum(1 for value in values.values() if _normalize_header(value) in expected)
        scored.append((score, int(row.get("row", 0)), row))
    score, header_row, header = max(scored, default=(0, 0, {}), key=lambda item: (item[0], -item[1]))
    minimum = max(3, (len(expected_headers) * 4 + 4) // 5)
    if score < minimum:
        raise _problem("header", _("A complete Tooling List header could not be detected."))
    header_cells = _row_cells(header)
    columns = tuple(
        DetectedColumn(
            ordinal=int(cell["column"]),
            source_header=str(cell["value"]).strip(),
            header_cell=str(cell["reference"]),
        )
        for cell in header_cells
        if str(cell.get("value", "")).strip()
    )
    if len({_normalize_header(item.source_header) for item in columns}) != len(columns):
        raise _problem("columns", _("Detected source headers must be unique."))
    regions, data_rows = _detect_regions(rows, header_row)
    image_anchors = _detect_images(
        _sequence(inspection.get("floating_image_anchors", []), "floatingImageAnchors"),
        data_rows,
        columns,
    )
    formula_errors = tuple(
        (str(item.get("cell", "")), str(item.get("error", "FORMULA_ERROR")))
        for item in (
            _mapping(value, "formulaErrors")
            for value in _sequence(inspection.get("formula_errors", []), "formulaErrors")
        )
    )
    revision = ToolingImportInspectionRevision(
        global_id=global_id,
        source=source,
        inspection_version=1,
        worksheet_name=str(worksheet.get("name", "")),
        header_row=header_row,
        columns=columns,
        regions=regions,
        formula_errors=formula_errors,
        image_anchors=image_anchors,
        passive_report_hash=sha256_json(inspection),
        created_at=created_at,
    )
    return revision, data_rows


def build_mapping_proposal(
    *,
    global_id: UUID,
    mapping_global_id: UUID,
    inspection: ToolingImportInspectionRevision,
    reviewed_rows: Sequence[Mapping[str, str]],
    customer_scope_id: str,
    template_key: str,
    reason: str,
    actor: str,
    created_at: datetime,
) -> ToolingImportMappingRevision:
    reviewed: dict[str, Mapping[str, str]] = {}
    detected_headers = {
        _normalize_header(column.source_header) for column in inspection.columns
    }
    for row in reviewed_rows:
        source_column = _normalize_header(str(row.get("source_column", "")))
        if source_column in reviewed:
            raise _problem(
                "reviewedRows",
                _("Reviewed mapping source columns must be unique."),
            )
        if source_column not in detected_headers:
            raise _problem(
                "reviewedRows",
                _("Reviewed mapping contains an unknown source column."),
            )
        reviewed[source_column] = row
    entries: list[MappingEntry] = []
    for column in inspection.columns:
        row = reviewed.get(_normalize_header(column.source_header))
        if row is None:
            entries.append(
                MappingEntry(
                    column.ordinal,
                    column.source_header,
                    MappingDisposition.UNMAPPED,
                    None,
                    None,
                    SemanticClassification.UNCLASSIFIED,
                    "retain_raw.v1",
                    ("unmapped_source_column",),
                )
            )
            continue
        classification = _classification(column.source_header, row.get("target_object", ""))
        entries.append(
            MappingEntry(
                column.ordinal,
                column.source_header,
                MappingDisposition.CANDIDATE,
                row.get("target_object") or None,
                row.get("suggested_field") or None,
                classification,
                _transformation_key(column.source_header),
                _validation_keys(column.source_header),
            )
        )
    return ToolingImportMappingRevision(
        global_id=global_id,
        mapping_global_id=mapping_global_id,
        source=inspection.source,
        inspection_global_id=inspection.global_id,
        inspection_snapshot_hash=inspection.snapshot_hash,
        mapping_version=1,
        state=MappingRevisionState.PROPOSAL,
        customer_scope_id=customer_scope_id,
        template_key=template_key,
        source_signature=inspection.source_signature,
        entries=tuple(entries),
        reason=reason,
        created_by_user_id=actor,
        created_at=created_at,
    )


def build_preview(
    *,
    global_id: UUID,
    source: ToolingImportSource,
    inspection: ToolingImportInspectionRevision,
    mapping: ToolingImportMappingRevision,
    data_rows: Sequence[Mapping[str, object]],
    created_at: datetime,
) -> ToolingImportPreviewRevision:
    if source.snapshot_hash != inspection.source.snapshot_hash:
        raise _problem(
            "source",
            _("Import preview does not match the exact source snapshot."),
        )
    if mapping.source.snapshot_hash != source.snapshot_hash:
        raise _problem(
            "mapping.source",
            _("Import mapping does not match the exact source snapshot."),
        )
    if (
        mapping.inspection_global_id != inspection.global_id
        or mapping.inspection_snapshot_hash != inspection.snapshot_hash
    ):
        raise _problem(
            "mapping.inspection",
            _("Import mapping does not match the exact inspection revision."),
        )
    if mapping.source_signature != inspection.source_signature:
        raise _problem("mapping.sourceSignature", _("Mapping does not match the detected source columns."))
    entry_by_ordinal = {item.source_ordinal: item for item in mapping.entries}
    image_rows = {item.candidate_source_row for item in inspection.image_anchors if item.requires_confirmation}
    preview_rows: list[PreviewRow] = []
    for row in data_rows:
        source_row = int(row["row"])
        fields: list[TransformedField] = []
        reasons: set[str] = set()
        requires_confirmation = source_row in image_rows
        if requires_confirmation:
            reasons.add("image_confirmation_required")
        for cell in _row_cells(row):
            ordinal = int(cell["column"])
            entry = entry_by_ordinal.get(ordinal)
            if entry is None:
                continue
            transformed = transform_field(entry, str(cell.get("value", "")), str(cell.get("formula", "")))
            fields.append(transformed)
            reasons.update(item.code for item in transformed.findings)
            requires_confirmation = requires_confirmation or any(
                item.severity is FindingSeverity.CONFIRMATION_REQUIRED for item in transformed.findings
            )
        present = {item.source_ordinal for item in fields}
        for entry in mapping.entries:
            if entry.source_ordinal not in present:
                transformed = transform_field(entry, "", "")
                fields.append(transformed)
                reasons.update(item.code for item in transformed.findings)
        if mapping.state is MappingRevisionState.PROPOSAL:
            reasons.add("mapping_activation_unavailable")
        has_error = any(
            finding.severity is FindingSeverity.ERROR
            for field in fields
            for finding in field.findings
        )
        action = (
            PreviewAction.BLOCKED
            if has_error or requires_confirmation or mapping.state is MappingRevisionState.PROPOSAL
            else PreviewAction.CREATE
        )
        preview_rows.append(
            PreviewRow(
                worksheet_name=inspection.worksheet_name,
                source_row=source_row,
                action=action,
                fields=tuple(sorted(fields, key=lambda item: item.source_ordinal)),
                reason_codes=tuple(sorted(reasons)),
                requires_confirmation=requires_confirmation,
            )
        )
    return ToolingImportPreviewRevision(
        global_id=global_id,
        preview_global_id=global_id,
        preview_version=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        source=source,
        inspection_global_id=inspection.global_id,
        inspection_snapshot_hash=inspection.snapshot_hash,
        mapping_global_id=mapping.global_id,
        mapping_snapshot_hash=mapping.snapshot_hash,
        mapping_state=mapping.state,
        rows=tuple(preview_rows),
        confirmations=(),
        created_at=created_at,
    )


def confirm_preview(
    *,
    global_id: UUID,
    predecessor: ToolingImportPreviewRevision,
    confirmations: Sequence[PreviewConfirmation],
    created_at: datetime,
) -> ToolingImportPreviewRevision:
    """Create an immutable successor with exact human confirmation evidence."""

    additions = tuple(confirmations)
    if not additions:
        raise _problem("confirmations", _("Enter at least one preview confirmation."))
    existing = {
        (item.kind, item.worksheet_name, item.source_row, item.anchor_key)
        for item in predecessor.confirmations
    }
    if any(
        (item.kind, item.worksheet_name, item.source_row, item.anchor_key) in existing
        for item in additions
    ):
        raise _problem("confirmations", _("A preview confirmation cannot replace earlier evidence."))
    rows_by_identity = {
        (row.worksheet_name, row.source_row): row for row in predecessor.rows
    }
    for item in additions:
        row = rows_by_identity.get((item.worksheet_name, item.source_row))
        if row is None or not row.requires_confirmation:
            raise _problem("confirmations", _("Select a row that still requires confirmation."))

    all_confirmations = predecessor.confirmations + additions
    successor_rows: list[PreviewRow] = []
    for row in predecessor.rows:
        required: set[PreviewConfirmationKind] = set()
        if "image_confirmation_required" in row.reason_codes:
            required.add(PreviewConfirmationKind.IMAGE_ANCHOR)
        if any(
            finding.severity is FindingSeverity.CONFIRMATION_REQUIRED
            for field in row.fields
            for finding in field.findings
        ):
            required.add(PreviewConfirmationKind.RELATIONSHIP)
        provided = {
            item.kind
            for item in all_confirmations
            if item.worksheet_name == row.worksheet_name
            and item.source_row == row.source_row
        }
        resolved = bool(required) and required.issubset(provided)
        if not resolved:
            successor_rows.append(row)
            continue
        fields = tuple(
            replace(
                field,
                findings=tuple(
                    finding
                    for finding in field.findings
                    if finding.severity is not FindingSeverity.CONFIRMATION_REQUIRED
                ),
            )
            for field in row.fields
        )
        reasons = tuple(
            code
            for code in row.reason_codes
            if code not in {
                "image_confirmation_required",
                "relationship_confirmation_required",
                "unmapped_source_column",
            }
        )
        has_error = any(
            finding.severity is FindingSeverity.ERROR
            for field in fields
            for finding in field.findings
        )
        blocked = has_error or predecessor.mapping_state is MappingRevisionState.PROPOSAL
        successor_rows.append(
            PreviewRow(
                worksheet_name=row.worksheet_name,
                source_row=row.source_row,
                action=PreviewAction.BLOCKED if blocked else PreviewAction.CREATE,
                fields=fields,
                reason_codes=reasons,
                requires_confirmation=False,
            )
        )
    return ToolingImportPreviewRevision(
        global_id=global_id,
        preview_global_id=predecessor.preview_global_id,
        preview_version=predecessor.preview_version + 1,
        predecessor_global_id=predecessor.global_id,
        predecessor_snapshot_hash=predecessor.snapshot_hash,
        source=predecessor.source,
        inspection_global_id=predecessor.inspection_global_id,
        inspection_snapshot_hash=predecessor.inspection_snapshot_hash,
        mapping_global_id=predecessor.mapping_global_id,
        mapping_snapshot_hash=predecessor.mapping_snapshot_hash,
        mapping_state=predecessor.mapping_state,
        rows=tuple(successor_rows),
        confirmations=all_confirmations,
        created_at=created_at,
    )


def transform_field(entry: MappingEntry, raw_value: str, formula: str) -> TransformedField:
    value = raw_value.strip()
    findings: list[FieldFinding] = []
    normalized: tuple[str, ...] = (value,) if value else ()
    state_candidate: str | None = None
    header = _normalize_header(entry.source_header)
    if "#REF!" in formula or value in _FORMULA_ERROR_VALUES:
        normalized = ()
        findings.append(_finding("formula_error", FindingSeverity.ERROR, _("Correct the workbook formula error.")))
    elif entry.transformation_key == "split_multi_value.v1":
        normalized = tuple(item for item in (_clean(item) for item in _SPLIT_MULTI.split(value)) if item)
    elif entry.transformation_key == "separate_tooling_state.v1":
        candidates = [item for item in (_clean(item) for item in _SPLIT_MULTI.split(value)) if item]
        state_items = [item for item in candidates if item.casefold() == "new tooling"]
        normalized = tuple(item for item in candidates if item.casefold() != "new tooling")
        if state_items:
            state_candidate = "new_tooling"
            findings.append(_finding("state_in_identifier", FindingSeverity.WARNING, _("Confirm the state separated from the Tooling number.")))
        if value and not normalized:
            findings.append(_finding("tooling_number_missing", FindingSeverity.ERROR, _("Enter a Tooling number or confirm a supported relationship.")))
    elif entry.transformation_key == "parse_number_unit.v1" and value:
        match = _NUMBER_UNIT.fullmatch(value)
        if match is None:
            findings.append(_finding("mixed_or_invalid_unit", FindingSeverity.ERROR, _("Enter one supported value and unit.")))
        else:
            normalized = (match.group(1), match.group(2).casefold())
    elif entry.transformation_key == "parse_machine_requirement.v1" and value:
        number = re.search(r"\b\d+(?:\.\d+)?\s*[Tt]\b", value)
        normalized = tuple(item for item in (number.group(0) if number else "", value) if item)
        if number is None or any(word in value.casefold() for word in ("machine", "vertical", "dual-shot")):
            findings.append(_finding("mixed_tonnage_machine_type", FindingSeverity.WARNING, _("Confirm clamp tonnage and machine type separately.")))
    elif entry.semantic_classification is SemanticClassification.LEGACY_GRADE and value:
        findings.append(_finding("legacy_grade_uninterpreted", FindingSeverity.WARNING, _("Legacy Grade is retained without inferred meaning.")))
    elif entry.semantic_classification is SemanticClassification.RELATION_CANDIDATE and value:
        findings.append(_finding("relationship_confirmation_required", FindingSeverity.CONFIRMATION_REQUIRED, _("Confirm the proposed Tooling relationship.")))
    if "required" in entry.validation_rule_keys and not value:
        findings.append(_finding("required_value_missing", FindingSeverity.ERROR, _("Enter the required source value.")))
    if entry.disposition is MappingDisposition.UNMAPPED and value:
        findings.append(_finding("unmapped_source_column", FindingSeverity.CONFIRMATION_REQUIRED, _("Confirm how the unmapped source column should be handled.")))
    return TransformedField(
        source_ordinal=entry.source_ordinal,
        source_header=entry.source_header,
        raw_value=raw_value,
        raw_value_hash=sha256_json({"rawValue": raw_value}),
        normalized_candidates=normalized,
        state_candidate=state_candidate,
        transformation_key=entry.transformation_key,
        findings=tuple(findings),
    )


def derive_job_state(results: Sequence[ImportRowResultState]) -> ImportJobState:
    if not results:
        return ImportJobState.QUEUED
    states = set(results)
    if ImportRowResultState.CONFIRMATION_REQUIRED in states:
        return ImportJobState.FAILED_FINAL
    if ImportRowResultState.FAILED_FINAL in states:
        return ImportJobState.PARTIALLY_SUCCEEDED if states - {ImportRowResultState.FAILED_FINAL} else ImportJobState.FAILED_FINAL
    if ImportRowResultState.FAILED_RETRYABLE in states:
        return ImportJobState.PARTIALLY_SUCCEEDED if states - {ImportRowResultState.FAILED_RETRYABLE} else ImportJobState.FAILED_RETRYABLE
    return ImportJobState.SUCCEEDED


def latest_import_row_results(
    results: Sequence[ImportRowResult],
) -> tuple[ImportRowResult, ...]:
    """Return the latest immutable attempt for each exact workbook row."""

    latest: dict[tuple[str, int], ImportRowResult] = {}
    for result in results:
        key = (result.worksheet_name, result.source_row)
        previous = latest.get(key)
        if previous is None or result.attempt > previous.attempt:
            latest[key] = result
    return tuple(latest[key] for key in sorted(latest))


def evaluate_rollback(observation: RollbackObservation) -> RollbackDecision:
    if observation.action != "create":
        return RollbackDecision(RollbackDecisionState.DENIED, "pre_existing_object_requires_forward_correction")
    if not observation.created_by_batch:
        return RollbackDecision(RollbackDecisionState.DENIED, "object_not_created_by_batch")
    if not observation.exact_imported_version:
        return RollbackDecision(RollbackDecisionState.DENIED, "imported_object_changed")
    if observation.downstream_reference_count != 0:
        return RollbackDecision(RollbackDecisionState.DENIED, "downstream_reference_present")
    return RollbackDecision(RollbackDecisionState.ALLOWED, "unused_batch_created_object")


def _detect_regions(
    rows: Sequence[Mapping[str, object]], header_row: int
) -> tuple[tuple[DetectedRegion, ...], tuple[Mapping[str, object], ...]]:
    regions: list[DetectedRegion] = []
    if header_row > 1:
        regions.append(DetectedRegion(WorkbookRegionKind.TITLE, 1, header_row - 1, "rows_before_detected_header"))
    regions.append(DetectedRegion(WorkbookRegionKind.HEADER, header_row, header_row, "maximum_reviewed_header_match"))
    typed_rows: list[tuple[WorkbookRegionKind, Mapping[str, object]]] = []
    shared = False
    summary = False
    data_rows: list[Mapping[str, object]] = []
    for row in rows:
        number = int(row.get("row", 0))
        if number <= header_row:
            continue
        values = [value for value in _row_values(row).values() if value.strip()]
        joined = " ".join(values).casefold()
        if "shared tooling" in joined:
            kind = WorkbookRegionKind.SHARED_TOOLING_MARKER
            shared = True
        elif "summary" in joined:
            kind = WorkbookRegionKind.SUMMARY
            summary = True
        elif summary:
            kind = WorkbookRegionKind.SUMMARY
        elif len(values) >= 3:
            kind = WorkbookRegionKind.SHARED_TOOLING_DATA if shared else WorkbookRegionKind.DATA
            data_rows.append(row)
        else:
            kind = WorkbookRegionKind.SECTION
        typed_rows.append((kind, row))
    for kind, group in _group_regions(typed_rows):
        first = int(group[0].get("row", 0))
        last = int(group[-1].get("row", 0))
        regions.append(
            DetectedRegion(
                kind,
                first,
                last,
                "content_and_structure_detected",
                requires_confirmation=kind is WorkbookRegionKind.SECTION,
            )
        )
    if not any(item.kind is WorkbookRegionKind.DATA for item in regions):
        raise _problem("regions", _("Workbook inspection requires a primary data region."))
    return tuple(regions), tuple(data_rows)


def _detect_images(
    anchors: Sequence[object],
    data_rows: Sequence[Mapping[str, object]],
    columns: Sequence[DetectedColumn],
) -> tuple[DetectedImageAnchor, ...]:
    data_by_row = {int(item.get("row", 0)): item for item in data_rows}
    picture_columns = {item.ordinal for item in columns if _normalize_header(item.source_header) == "picture"}
    part_columns = {item.ordinal for item in columns if _normalize_header(item.source_header) == "part name english"}
    result: list[DetectedImageAnchor] = []
    for index, value in enumerate(anchors, start=1):
        anchor = _mapping(value, "floatingImageAnchor")
        row = int(anchor["zero_based_row"]) + 1 if anchor.get("zero_based_row") is not None else None
        column = int(anchor["zero_based_column"]) + 1 if anchor.get("zero_based_column") is not None else None
        source_row = data_by_row.get(row or -1)
        row_values = _row_values(source_row) if source_row else {}
        confident = bool(source_row and column in picture_columns and any(row_values.get(item, "").strip() for item in part_columns))
        result.append(
            DetectedImageAnchor(
                anchor_key=f"image-anchor-{index}",
                row=row,
                column=column,
                confidence="high" if confident else "ambiguous",
                candidate_source_row=row if source_row else None,
                requires_confirmation=not confident,
            )
        )
    return tuple(result)


def _classification(header: str, target_object: str) -> SemanticClassification:
    normalized = _normalize_header(header)
    if normalized in {"a", "b", "c"}:
        return SemanticClassification.LEGACY_GRADE
    if normalized in {"remarks", "picture"}:
        return SemanticClassification.RELATION_CANDIDATE
    if "result" in target_object.casefold() or normalized in {
        "calculated weight", "single-set daily output", "single-set daily assembly units",
        "total daily output", "total daily assembly units", "monthly capacity",
    }:
        return SemanticClassification.CALCULATED_UNVERIFIED
    if any(token in normalized for token in ("no.", "number", "p/n", "item")):
        return SemanticClassification.IDENTITY
    return SemanticClassification.DESCRIPTIVE


def _transformation_key(header: str) -> str:
    normalized = _normalize_header(header)
    if normalized in {"model", "sn p/n", "kw p/n", "th part number"}:
        return "split_multi_value.v1"
    if normalized == "kw tooling no.":
        return "separate_tooling_state.v1"
    if normalized in {"calculated weight", "actual weight", "runner weight", "allocated runner + net per cavity", "injection cycle seconds"}:
        return "parse_number_unit.v1"
    if normalized == "tonnage":
        return "parse_machine_requirement.v1"
    return "retain_raw.v1"


def _validation_keys(header: str) -> tuple[str, ...]:
    normalized = _normalize_header(header)
    keys: list[str] = []
    if normalized in {"item", "part name english", "model", "part material"}:
        keys.append("required")
    if normalized in {"a", "b", "c"}:
        keys.append("legacy_grade_no_inference")
    if normalized == "picture":
        keys.append("image_confirmation")
    if normalized == "unnamed trailing note":
        keys.append("unmapped_confirmation")
    return tuple(keys)


def _group_regions(
    values: Sequence[tuple[WorkbookRegionKind, Mapping[str, object]]]
) -> Iterable[tuple[WorkbookRegionKind, list[Mapping[str, object]]]]:
    current_kind: WorkbookRegionKind | None = None
    current: list[Mapping[str, object]] = []
    for kind, row in values:
        if current_kind is not None and kind is not current_kind:
            yield current_kind, current
            current = []
        current_kind = kind
        current.append(row)
    if current_kind is not None:
        yield current_kind, current


def _row_cells(row: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    return tuple(_mapping(item, "row.cells") for item in _sequence(row.get("cells", []), "row.cells"))


def _row_values(row: Mapping[str, object] | None) -> dict[int, str]:
    if row is None:
        return {}
    return {int(cell["column"]): str(cell.get("value", "")) for cell in _row_cells(row)}


def _normalize_header(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _finding(code: str, severity: FindingSeverity, message: str) -> FieldFinding:
    return FieldFinding(_code(code, "finding.code"), severity, message)


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _problem(path, _("Provide an object value."))
    return value


def _sequence(value: object, path: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise _problem(path, _("Provide a list value."))
    return value


def _uuid(value: object, path: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise _problem(path, _("Provide a valid UUID.")) from error


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value <= 0:
        raise _problem(path, _("Provide a positive whole number."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise _problem(path, _("Provide a valid bounded text value."))
    return value.strip()


def _sha256(value: object, path: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise _problem(path, _("Provide a lowercase SHA-256 value."))
    return value


def _content_hash(value: object, path: str) -> str:
    if not isinstance(value, str) or not _CONTENT_HASH.fullmatch(value):
        raise _problem(path, _("Provide a valid lowercase content hash."))
    return value


def _code(value: object, path: str) -> str:
    if not isinstance(value, str) or not _CODE.fullmatch(value):
        raise _problem(path, _("Provide a valid stable code."))
    return value


def _utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Provide a timezone-aware UTC date and time."))
    normalized = value.astimezone(UTC)
    return normalized


def _payload_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise _problem(path, _("Provide a timezone-aware UTC date and time."))
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _problem(path, _("Provide a timezone-aware UTC date and time.")) from error
    return _utc(parsed, path)


def _require_schema(value: Mapping[str, object]) -> None:
    if value.get("schemaVersion") != IMPORT_SCHEMA_VERSION:
        raise _problem("schemaVersion", _("Select a supported Tooling import snapshot."))


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed(field_errors=[{"path": path, "message": message}])
