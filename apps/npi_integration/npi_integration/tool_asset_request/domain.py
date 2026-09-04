from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import TOOLING_SCHEMA_VERSION, ToolingRequirementKind, sha256_json

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


TOOL_ASSET_API_VERSION = "npi.tooling-asset.v1"
TOOL_ASSET_OPERATION = "create_or_update_tool_asset"
TOOL_ASSET_OWNED_FIELDS = (
    "tooling_master_title",
    "physical_set_serial",
    "tooling_requirement_kind",
    "source_tooling_revision",
    "acceptance_evidence_reference",
)

_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


class ToolAssetTargetMode(StrEnum):
    MOCK = "mock"


class ToolAssetRequestState(StrEnum):
    DRAFT = "draft"


class ToolAssetInputValidationState(StrEnum):
    VALIDATED_MOCK = "validated_mock"


class ToolAssetBusinessApprovalState(StrEnum):
    UNAVAILABLE = "unavailable"


class ToolAssetDispatchState(StrEnum):
    PROHIBITED = "prohibited"


class ToolAssetTargetResultState(StrEnum):
    NOT_REQUESTED = "not_requested"


@dataclass(frozen=True, slots=True)
class ToolAssetRequestInput:
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_master_title: str
    tooling_master_snapshot_hash: str
    tooling_set_global_id: UUID
    tooling_set_physical_serial: str
    tooling_set_snapshot_hash: str
    tooling_requirement_kind: ToolingRequirementKind
    set_revision_binding_global_id: UUID
    set_revision_binding_snapshot_hash: str
    tooling_revision_global_id: UUID
    tooling_revision_number: int
    tooling_revision_label: str
    tooling_revision_snapshot_hash: str
    acceptance_revision_global_id: UUID
    acceptance_version: int
    acceptance_snapshot_hash: str

    def __post_init__(self) -> None:
        for fieldname in (
            "project_global_id",
            "tooling_master_global_id",
            "tooling_set_global_id",
            "set_revision_binding_global_id",
            "tooling_revision_global_id",
            "acceptance_revision_global_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(
            self,
            "tooling_master_title",
            _text(self.tooling_master_title, "toolingMasterTitle", 140),
        )
        object.__setattr__(
            self,
            "tooling_set_physical_serial",
            _text(self.tooling_set_physical_serial, "toolingSetPhysicalSerial", 80),
        )
        object.__setattr__(
            self,
            "tooling_revision_label",
            _text(self.tooling_revision_label, "toolingRevisionLabel", 40),
        )
        for fieldname in (
            "tooling_master_snapshot_hash",
            "tooling_set_snapshot_hash",
            "set_revision_binding_snapshot_hash",
            "tooling_revision_snapshot_hash",
            "acceptance_snapshot_hash",
        ):
            object.__setattr__(self, fieldname, _hash(getattr(self, fieldname), _camel(fieldname)))
        if not isinstance(self.tooling_requirement_kind, ToolingRequirementKind):
            raise _field_problem("toolingRequirementKind", _("Select a supported Tooling Requirement kind."))
        for fieldname in (
            "tooling_revision_number",
            "acceptance_version",
        ):
            object.__setattr__(self, fieldname, _positive(getattr(self, fieldname), _camel(fieldname)))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingMasterTitle": self.tooling_master_title,
            "toolingMasterSnapshotHash": self.tooling_master_snapshot_hash,
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "toolingSetPhysicalSerial": self.tooling_set_physical_serial,
            "toolingSetSnapshotHash": self.tooling_set_snapshot_hash,
            "toolingRequirementKind": self.tooling_requirement_kind.value,
            "setRevisionBindingGlobalId": str(self.set_revision_binding_global_id),
            "setRevisionBindingSnapshotHash": self.set_revision_binding_snapshot_hash,
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionNumber": self.tooling_revision_number,
            "toolingRevisionLabel": self.tooling_revision_label,
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "acceptanceRevisionGlobalId": str(self.acceptance_revision_global_id),
            "acceptanceVersion": self.acceptance_version,
            "acceptanceSnapshotHash": self.acceptance_snapshot_hash,
            "ownedFieldsManifest": list(TOOL_ASSET_OWNED_FIELDS),
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class ToolAssetRequest:
    global_id: UUID
    tenant_id: str
    request_input: ToolAssetRequestInput
    target_mode: ToolAssetTargetMode
    request_state: ToolAssetRequestState
    input_validation_state: ToolAssetInputValidationState
    business_approval_state: ToolAssetBusinessApprovalState
    dispatch_state: ToolAssetDispatchState
    target_result_state: ToolAssetTargetResultState
    actor_user_id: str
    request_id: UUID
    trace_id: str
    idempotency_key_hash: str
    created_at: datetime
    api_version: str = TOOL_ASSET_API_VERSION
    operation: str = TOOL_ASSET_OPERATION

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "requestId"))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId", 128))
        if not isinstance(self.request_input, ToolAssetRequestInput):
            raise _field_problem("requestInput", _("Enter a valid Tool Asset request input."))
        expected_axes = (
            (self.target_mode, ToolAssetTargetMode.MOCK, "targetMode"),
            (self.request_state, ToolAssetRequestState.DRAFT, "requestState"),
            (
                self.input_validation_state,
                ToolAssetInputValidationState.VALIDATED_MOCK,
                "inputValidationState",
            ),
            (
                self.business_approval_state,
                ToolAssetBusinessApprovalState.UNAVAILABLE,
                "businessApprovalState",
            ),
            (self.dispatch_state, ToolAssetDispatchState.PROHIBITED, "dispatchState"),
            (
                self.target_result_state,
                ToolAssetTargetResultState.NOT_REQUESTED,
                "targetResultState",
            ),
        )
        for actual, expected, path in expected_axes:
            if actual is not expected:
                raise _field_problem(path, _("Phase 6 Tool Asset request truth is invalid."))
        if self.api_version != TOOL_ASSET_API_VERSION or self.operation != TOOL_ASSET_OPERATION:
            raise _field_problem("operation", _("The Tool Asset request operation is invalid."))
        object.__setattr__(self, "actor_user_id", _actor(self.actor_user_id, "actorUserId"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId", 128))
        object.__setattr__(
            self,
            "idempotency_key_hash",
            _hash(self.idempotency_key_hash, "idempotencyKeyHash"),
        )
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))

    @property
    def payload_hash(self) -> str:
        return sha256_json(
            {
                "apiVersion": self.api_version,
                "operation": self.operation,
                "targetMode": self.target_mode.value,
                "requestInput": self.request_input.snapshot_payload(),
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "apiVersion": self.api_version,
            "operation": self.operation,
            "targetMode": self.target_mode.value,
            "requestState": self.request_state.value,
            "inputValidationState": self.input_validation_state.value,
            "businessApprovalState": self.business_approval_state.value,
            "dispatchState": self.dispatch_state.value,
            "targetResultState": self.target_result_state.value,
            "requestInput": self.request_input.snapshot_payload(),
            "requestInputHash": self.request_input.snapshot_hash,
            "payloadHash": self.payload_hash,
            "actorUserId": self.actor_user_id,
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "idempotencyKeyHash": self.idempotency_key_hash,
            "createdAt": _utc_text(self.created_at),
            "formalAssetMapping": {
                "sourceSystem": "ERPNEXT",
                "editableIn": "ERPNEXT",
                "state": "unavailable",
                "reasonCode": "erp_asset_mapping_unavailable",
                "mappingCardinality": "zero_or_one_per_physical_set",
            },
            "targetResult": {
                "state": "not_requested",
                "reasonCode": "phase_6_dispatch_prohibited",
            },
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())

    def public_dict(self) -> dict[str, object]:
        return {**self.snapshot_payload(), "snapshotHash": self.snapshot_hash}


def create_mock_tool_asset_request(
    *,
    tenant_id: str,
    request_input: ToolAssetRequestInput,
    actor_user_id: str,
    request_id: UUID,
    trace_id: str,
    idempotency_key_hash: str,
    created_at: datetime,
    global_id: UUID | None = None,
) -> ToolAssetRequest:
    return ToolAssetRequest(
        global_id=global_id or uuid4(),
        tenant_id=tenant_id,
        request_input=request_input,
        target_mode=ToolAssetTargetMode.MOCK,
        request_state=ToolAssetRequestState.DRAFT,
        input_validation_state=ToolAssetInputValidationState.VALIDATED_MOCK,
        business_approval_state=ToolAssetBusinessApprovalState.UNAVAILABLE,
        dispatch_state=ToolAssetDispatchState.PROHIBITED,
        target_result_state=ToolAssetTargetResultState.NOT_REQUESTED,
        actor_user_id=actor_user_id,
        request_id=request_id,
        trace_id=trace_id,
        idempotency_key_hash=idempotency_key_hash,
        created_at=created_at,
    )


def tool_asset_request_from_snapshot(value: object) -> ToolAssetRequest:
    record = _record(value, {
        "globalId", "tenantId", "apiVersion", "operation", "targetMode", "requestState",
        "inputValidationState", "businessApprovalState", "dispatchState", "targetResultState",
        "requestInput", "requestInputHash", "payloadHash", "actorUserId", "requestId", "traceId",
        "idempotencyKeyHash", "createdAt", "formalAssetMapping", "targetResult",
    })
    input_record = _record(record["requestInput"], {
        "schemaVersion", "projectGlobalId", "toolingMasterGlobalId",
        "toolingMasterTitle", "toolingMasterSnapshotHash", "toolingSetGlobalId",
        "toolingSetPhysicalSerial", "toolingSetSnapshotHash", "toolingRequirementKind",
        "setRevisionBindingGlobalId", "setRevisionBindingSnapshotHash",
        "toolingRevisionGlobalId", "toolingRevisionNumber", "toolingRevisionLabel",
        "toolingRevisionSnapshotHash", "acceptanceRevisionGlobalId", "acceptanceVersion",
        "acceptanceSnapshotHash", "ownedFieldsManifest",
    })
    if input_record["schemaVersion"] != TOOLING_SCHEMA_VERSION or input_record["ownedFieldsManifest"] != list(TOOL_ASSET_OWNED_FIELDS):
        raise _field_problem("requestInput", _("The Tool Asset request input contract is invalid."))
    request_input = ToolAssetRequestInput(
        project_global_id=input_record["projectGlobalId"],
        tooling_master_global_id=input_record["toolingMasterGlobalId"],
        tooling_master_title=input_record["toolingMasterTitle"],
        tooling_master_snapshot_hash=input_record["toolingMasterSnapshotHash"],
        tooling_set_global_id=input_record["toolingSetGlobalId"],
        tooling_set_physical_serial=input_record["toolingSetPhysicalSerial"],
        tooling_set_snapshot_hash=input_record["toolingSetSnapshotHash"],
        tooling_requirement_kind=ToolingRequirementKind(input_record["toolingRequirementKind"]),
        set_revision_binding_global_id=input_record["setRevisionBindingGlobalId"],
        set_revision_binding_snapshot_hash=input_record["setRevisionBindingSnapshotHash"],
        tooling_revision_global_id=input_record["toolingRevisionGlobalId"],
        tooling_revision_number=input_record["toolingRevisionNumber"],
        tooling_revision_label=input_record["toolingRevisionLabel"],
        tooling_revision_snapshot_hash=input_record["toolingRevisionSnapshotHash"],
        acceptance_revision_global_id=input_record["acceptanceRevisionGlobalId"],
        acceptance_version=input_record["acceptanceVersion"],
        acceptance_snapshot_hash=input_record["acceptanceSnapshotHash"],
    )
    result = ToolAssetRequest(
        global_id=record["globalId"], tenant_id=record["tenantId"], request_input=request_input,
        target_mode=ToolAssetTargetMode(record["targetMode"]),
        request_state=ToolAssetRequestState(record["requestState"]),
        input_validation_state=ToolAssetInputValidationState(record["inputValidationState"]),
        business_approval_state=ToolAssetBusinessApprovalState(record["businessApprovalState"]),
        dispatch_state=ToolAssetDispatchState(record["dispatchState"]),
        target_result_state=ToolAssetTargetResultState(record["targetResultState"]),
        actor_user_id=record["actorUserId"], request_id=record["requestId"], trace_id=record["traceId"],
        idempotency_key_hash=record["idempotencyKeyHash"], created_at=record["createdAt"],
        api_version=record["apiVersion"], operation=record["operation"],
    )
    expected_mapping = {
        "sourceSystem": "ERPNEXT", "editableIn": "ERPNEXT", "state": "unavailable",
        "reasonCode": "erp_asset_mapping_unavailable",
        "mappingCardinality": "zero_or_one_per_physical_set",
    }
    expected_result = {"state": "not_requested", "reasonCode": "phase_6_dispatch_prohibited"}
    if record["requestInputHash"] != request_input.snapshot_hash or record["payloadHash"] != result.payload_hash:
        raise _field_problem("payloadHash", _("The Tool Asset request payload hash does not match."))
    if record["formalAssetMapping"] != expected_mapping or record["targetResult"] != expected_result:
        raise _field_problem("targetResult", _("The Tool Asset target result truth is invalid."))
    return result


def _record(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _field_problem("request", _("Enter a closed object with the required fields."))
    return value


def _uuid(value: object, path: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _field_problem(path, _("Enter a valid UUID.")) from error


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter valid text."))
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or any(ord(char) < 32 for char in normalized):
        raise _field_problem(path, _("Enter valid text."))
    return normalized


def _key(value: object, path: str, maximum: int = 128) -> str:
    text = _text(value, path, maximum)
    if not _KEY_PATTERN.fullmatch(text):
        raise _field_problem(path, _("Enter a valid stable key."))
    return text


def _actor(value: object, path: str) -> str:
    if not isinstance(value, str) or not _ACTOR_PATTERN.fullmatch(value):
        raise _field_problem(path, _("Enter a valid actor identity."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise _field_problem(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _datetime(value: object, path: str) -> datetime:
    if isinstance(value, str):
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            value = datetime.fromisoformat(candidate)
        except ValueError as error:
            raise _field_problem(path, _("Enter a timezone-aware datetime.")) from error
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise _field_problem(path, _("Enter a timezone-aware datetime."))
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item[:1].upper() + item[1:] for item in tail)


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed(field_errors=[{"path": path, "message": message}])
