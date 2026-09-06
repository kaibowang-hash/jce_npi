from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Sequence
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import sha256_json
from npi_core.tooling.import_domain import RollbackDecision

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


FIXTURE_MAPPING_VERSION = "p6-07.synthetic-execution-mapping.v1"
CORRECTION_SCHEMA_VERSION = "tooling-import-correction.v1"
RECONCILIATION_SCHEMA_VERSION = "tooling-import-reconciliation.v1"
ROLLBACK_SCHEMA_VERSION = "tooling-import-rollback.v1"
_HASH = re.compile(r"^[a-f0-9]{64}$")
_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")


class ReconciliationState(StrEnum):
    MATCHED = "matched"
    MISSING = "missing"
    CHANGED = "changed"
    DOWNSTREAM_USED = "downstream_used"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True, slots=True)
class ExecutionFieldBinding:
    source_header: str
    target_object: str
    target_field: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_header", _text(self.source_header, "sourceHeader", 500))
        object.__setattr__(self, "target_object", _code_value(self.target_object, "targetObject"))
        object.__setattr__(self, "target_field", _code_value(self.target_field, "targetField"))

    def snapshot_payload(self) -> dict[str, str]:
        return {
            "sourceHeader": self.source_header,
            "targetObject": self.target_object,
            "targetField": self.target_field,
        }


@dataclass(frozen=True, slots=True)
class FixtureMappingActivation:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    batch_global_id: UUID
    source_snapshot_hash: str
    source_sha256: str
    customer_scope_id: str
    fixture_version: str
    mapping_revision_global_id: UUID
    mapping_snapshot_hash: str
    source_signature: str
    bindings: tuple[ExecutionFieldBinding, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "projectGlobalId"),
        )
        for field_name in (
            "global_id",
            "batch_global_id",
            "mapping_revision_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _uuid4(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        object.__setattr__(self, "source_snapshot_hash", _hash(self.source_snapshot_hash, "sourceSnapshotHash"))
        object.__setattr__(self, "source_sha256", _hash(self.source_sha256, "sourceSha256"))
        object.__setattr__(self, "customer_scope_id", _text(self.customer_scope_id, "customerScopeId", 128))
        object.__setattr__(self, "fixture_version", _code_value(self.fixture_version, "fixtureVersion"))
        if self.fixture_version != FIXTURE_MAPPING_VERSION:
            raise _problem("fixtureVersion", _("Select the controlled synthetic fixture mapping version."))
        object.__setattr__(self, "mapping_snapshot_hash", _hash(self.mapping_snapshot_hash, "mappingSnapshotHash"))
        object.__setattr__(self, "source_signature", _hash(self.source_signature, "sourceSignature"))
        bindings = tuple(self.bindings)
        if not bindings or any(not isinstance(item, ExecutionFieldBinding) for item in bindings):
            raise _problem("bindings", _("Fixture mapping bindings must use the controlled shape."))
        if len({item.source_header.casefold() for item in bindings}) != len(bindings):
            raise _problem("bindings", _("Fixture mapping source headers must be unique."))
        if bindings != (
            ExecutionFieldBinding(
                "Part Name English",
                "engineering_part_revision",
                "title",
            ),
        ):
            raise _problem(
                "bindings",
                _("Fixture execution may only create the controlled synthetic Part target."),
            )
        object.__setattr__(self, "bindings", bindings)
        object.__setattr__(self, "created_by_user_id", _text(self.created_by_user_id, "createdByUserId", 254))
        object.__setattr__(self, "created_at", _utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": "tooling-import-mapping-activation.v1",
            "globalId": str(self.global_id),
            "state": "approved_fixture",
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "batchGlobalId": str(self.batch_global_id),
            "sourceSnapshotHash": self.source_snapshot_hash,
            "sourceSha256": self.source_sha256,
            "customerScopeId": self.customer_scope_id,
            "fixtureVersion": self.fixture_version,
            "mappingRevisionGlobalId": str(self.mapping_revision_global_id),
            "mappingSnapshotHash": self.mapping_snapshot_hash,
            "sourceSignature": self.source_signature,
            "bindings": [item.snapshot_payload() for item in self.bindings],
            "createdByUserId": self.created_by_user_id,
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class CorrectionEntry:
    worksheet_name: str
    source_row: int
    source_header: str
    corrected_value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheet_name", _text(self.worksheet_name, "worksheetName", 255))
        if type(self.source_row) is not int or self.source_row < 1 or self.source_row > 1_048_576:
            raise _problem("sourceRow", _("Select a valid source row."))
        object.__setattr__(self, "source_header", _text(self.source_header, "sourceHeader", 500))
        if not isinstance(self.corrected_value, str) or len(self.corrected_value) > 32_767:
            raise _problem("correctedValue", _("Enter a bounded correction value."))
        if self.corrected_value.lstrip().startswith(("=", "+", "-", "@")):
            raise _problem(
                "correctedValue",
                _("Correction values cannot start with a spreadsheet formula marker."),
            )

    @property
    def identity(self) -> tuple[str, int, str]:
        return self.worksheet_name, self.source_row, self.source_header.casefold()


def validate_correction_entries(
    entries: Sequence[CorrectionEntry],
) -> tuple[CorrectionEntry, ...]:
    values = tuple(entries)
    if not values or len(values) > 5_000:
        raise _problem("corrections", _("Enter between one and 5,000 corrections."))
    if any(not isinstance(item, CorrectionEntry) for item in values):
        raise _problem("corrections", _("Corrections must use the controlled shape."))
    if len({item.identity for item in values}) != len(values):
        raise _problem("corrections", _("Correction fields must be unique."))
    return values


@dataclass(frozen=True, slots=True)
class ReconciliationItem:
    row_result_global_id: UUID
    target_object_type: str
    target_global_id: UUID
    expected_snapshot_hash: str
    observed_snapshot_hash: str | None
    downstream_reference_count: int
    state: ReconciliationState

    def __post_init__(self) -> None:
        object.__setattr__(self, "row_result_global_id", _uuid4(self.row_result_global_id, "rowResultGlobalId"))
        object.__setattr__(self, "target_object_type", _code_value(self.target_object_type, "targetObjectType"))
        object.__setattr__(self, "target_global_id", _uuid4(self.target_global_id, "targetGlobalId"))
        object.__setattr__(self, "expected_snapshot_hash", _hash(self.expected_snapshot_hash, "expectedSnapshotHash"))
        if self.observed_snapshot_hash is not None:
            object.__setattr__(self, "observed_snapshot_hash", _hash(self.observed_snapshot_hash, "observedSnapshotHash"))
        if type(self.downstream_reference_count) is not int or self.downstream_reference_count < 0:
            raise _problem("downstreamReferenceCount", _("Downstream reference count cannot be negative."))
        if not isinstance(self.state, ReconciliationState):
            raise _problem("state", _("Select a supported reconciliation state."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "rowResultGlobalId": str(self.row_result_global_id),
            "targetObjectType": self.target_object_type,
            "targetGlobalId": str(self.target_global_id),
            "expectedSnapshotHash": self.expected_snapshot_hash,
            "observedSnapshotHash": self.observed_snapshot_hash,
            "downstreamReferenceCount": self.downstream_reference_count,
            "state": self.state.value,
        }


@dataclass(frozen=True, slots=True)
class ReconciliationSnapshot:
    global_id: UUID
    job_global_id: UUID
    job_snapshot_hash: str
    kind: str
    items: tuple[ReconciliationItem, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        for field_name in ("global_id", "job_global_id", "request_id"):
            object.__setattr__(self, field_name, _uuid4(getattr(self, field_name), field_name))
        object.__setattr__(self, "job_snapshot_hash", _hash(self.job_snapshot_hash, "jobSnapshotHash"))
        if self.kind not in {"reconciliation", "rollback_eligibility", "rollback_result"}:
            raise _problem("kind", _("Select a supported import verification kind."))
        items = tuple(self.items)
        if any(not isinstance(item, ReconciliationItem) for item in items):
            raise _problem("items", _("Reconciliation items must use the controlled shape."))
        if len({item.row_result_global_id for item in items}) != len(items):
            raise _problem("items", _("Reconciliation target results must be unique."))
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "created_by_user_id", _text(self.created_by_user_id, "createdByUserId", 254))
        object.__setattr__(self, "created_at", _utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": RECONCILIATION_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "jobGlobalId": str(self.job_global_id),
            "jobSnapshotHash": self.job_snapshot_hash,
            "kind": self.kind,
            "items": [item.snapshot_payload() for item in self.items],
            "createdByUserId": self.created_by_user_id,
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


def rollback_item_state(decision: RollbackDecision) -> ReconciliationState:
    if decision.state.value == "allowed":
        return ReconciliationState.MATCHED
    if decision.reason_code == "downstream_reference_present":
        return ReconciliationState.DOWNSTREAM_USED
    if decision.reason_code == "imported_object_changed":
        return ReconciliationState.CHANGED
    return ReconciliationState.MISSING


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed(field_errors=[{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    try:
        parsed = value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _problem(path, _("Select a valid identifier.")) from error
    return parsed


def _uuid4(value: object, path: str) -> UUID:
    parsed = _uuid(value, path)
    if parsed.version != 4:
        raise _problem(path, _("Select a UUIDv4 identifier."))
    return parsed


def _text(value: object, path: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise _problem(path, _("Enter a bounded value."))
    return value.strip()


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _problem(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _code_value(value: object, path: str) -> str:
    if not isinstance(value, str) or _CODE.fullmatch(value) is None:
        raise _problem(path, _("Select a supported controlled code."))
    return value


def _utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a timezone-aware timestamp."))
    return value.astimezone(UTC)
