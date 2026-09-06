from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


TOOL_ASSET_EXECUTION_SCHEMA_VERSION = 2
TOOL_ASSET_OUTBOX_SCHEMA_VERSION = 3
TOOL_ASSET_EXECUTION_API_VERSION = "npi.erp-tool-asset.v1"
CREATE_TOOL_ASSET = "create_tool_asset"
UPDATE_TOOL_ASSET = "update_tool_asset"
TOOL_ASSET_EXECUTION_OPERATIONS = (CREATE_TOOL_ASSET, UPDATE_TOOL_ASSET)
TOOL_ASSET_REQUEST_EVENT_TYPE = "npi.tool_asset_request.ready"
TOOL_ASSET_RESULT_EVENT_TYPE = "erpnext.tool_asset_result.observed"
TOOL_ASSET_OWNED_FIELDS = (
    "tooling_master_title",
    "physical_set_serial",
    "tooling_requirement_kind",
    "source_tooling_revision",
    "acceptance_evidence_reference",
)
TOOLING_REQUIREMENT_KINDS = frozenset(
    {
        "new_tool",
        "customer_owned_intake",
        "copy_or_additional_set",
        "modification",
        "repair",
        "capacity_need",
    }
)

_ACTOR = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class ToolAssetExecutionContractError(ValueError):
    """Raised when Tool Asset execution truth is not exactly contract-shaped."""


class ToolAssetExecutionOperation(StrEnum):
    CREATE = CREATE_TOOL_ASSET
    UPDATE = UPDATE_TOOL_ASSET


class ToolAssetExecutionTargetMode(StrEnum):
    MOCK = "mock"
    SYNTHETIC = "synthetic"
    SANDBOX = "sandbox"


class ToolAssetExecutionRequestState(StrEnum):
    VALIDATED_MOCK = "validated_mock"
    QUEUED = "queued"
    PROCESSING = "processing"
    SYNTHETIC_VERIFIED = "synthetic_verified"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    UNCERTAIN_AFTER_TIMEOUT = "uncertain_after_timeout"
    MAPPING_CONFLICT = "mapping_conflict"


class ToolAssetApprovalState(StrEnum):
    UNAVAILABLE = "unavailable"
    VERIFIED = "verified"


class ToolAssetResultAuthority(StrEnum):
    NONE = "none"
    SYNTHETIC = "synthetic"
    AUTHORITATIVE_SANDBOX = "authoritative_sandbox"


class ToolAssetFieldResultState(StrEnum):
    SYNTHETIC_VERIFIED = "synthetic_verified"
    SUCCEEDED_AUTHORITATIVE = "succeeded_authoritative"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    UNCERTAIN_AFTER_TIMEOUT = "uncertain_after_timeout"
    OBSERVED_CONFLICT = "observed_conflict"


class ToolAssetFaultKind(StrEnum):
    NONE = "none"
    SOURCE_CONFLICT = "source_conflict"
    APPROVAL_UNAVAILABLE = "approval_unavailable"
    STALE_MAPPING = "stale_mapping"
    TIMEOUT_AFTER_POSSIBLE_COMMIT = "timeout_after_possible_commit"
    RATE_LIMITED = "rate_limited"
    TARGET_SERVER_ERROR = "target_server_error"
    BUSINESS_VALIDATION = "business_validation"
    RESPONSE_CONTRACT_INVALID = "response_contract_invalid"
    RESPONSE_AUTHENTICATION_INVALID = "response_authentication_invalid"
    TARGET_UNAVAILABLE = "target_unavailable"


class ToolAssetMappingDisposition(StrEnum):
    ADVANCE = "advance"
    NON_AUTHORITATIVE = "non_authoritative"
    EXPECTATION_CONFLICT = "expectation_conflict"
    TARGET_IDENTITY_CONFLICT = "target_identity_conflict"
    RESULT_NOT_COMPLETE = "result_not_complete"


@dataclass(frozen=True, slots=True)
class ToolAssetSourceSnapshot:
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_master_title: str
    tooling_master_snapshot_hash: str
    tooling_set_global_id: UUID
    tooling_set_physical_serial: str
    tooling_set_snapshot_hash: str
    tooling_requirement_kind: str
    set_revision_binding_global_id: UUID
    set_revision_binding_snapshot_hash: str
    tooling_revision_global_id: UUID
    tooling_revision_number: int
    tooling_revision_label: str
    tooling_revision_snapshot_hash: str
    acceptance_revision_global_id: UUID
    acceptance_global_id: UUID
    acceptance_version: int
    acceptance_predecessor_global_id: UUID | None
    acceptance_predecessor_snapshot_hash: str | None
    acceptance_snapshot_hash: str
    accepted_at: datetime
    source_stream_key_hash: str = ""
    source_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "source.tenantId", 128, _TENANT))
        for name in (
            "project_global_id",
            "tooling_master_global_id",
            "tooling_set_global_id",
            "set_revision_binding_global_id",
            "tooling_revision_global_id",
            "acceptance_revision_global_id",
            "acceptance_global_id",
        ):
            object.__setattr__(self, name, _uuid(getattr(self, name), f"source.{name}"))
        for name in (
            "tooling_master_snapshot_hash",
            "tooling_set_snapshot_hash",
            "set_revision_binding_snapshot_hash",
            "tooling_revision_snapshot_hash",
            "acceptance_snapshot_hash",
        ):
            object.__setattr__(self, name, _hash(getattr(self, name), f"source.{name}"))
        object.__setattr__(self, "tooling_set_physical_serial", _text(self.tooling_set_physical_serial, "source.toolingSetPhysicalSerial", 80, _CODE))
        object.__setattr__(self, "tooling_master_title", _text(self.tooling_master_title, "source.toolingMasterTitle", 140))
        if self.tooling_requirement_kind not in TOOLING_REQUIREMENT_KINDS:
            raise ToolAssetExecutionContractError("source.toolingRequirementKind is invalid.")
        object.__setattr__(self, "tooling_revision_label", _text(self.tooling_revision_label, "source.toolingRevisionLabel", 40))
        object.__setattr__(self, "tooling_revision_number", _positive(self.tooling_revision_number, "source.toolingRevisionNumber"))
        object.__setattr__(self, "acceptance_version", _positive(self.acceptance_version, "source.acceptanceVersion"))
        predecessor_supplied = self.acceptance_predecessor_global_id is not None or self.acceptance_predecessor_snapshot_hash is not None
        if self.acceptance_version == 1 and predecessor_supplied:
            raise ToolAssetExecutionContractError("the first acceptance revision cannot contain a predecessor.")
        if self.acceptance_version > 1 and not (
            self.acceptance_predecessor_global_id is not None
            and self.acceptance_predecessor_snapshot_hash is not None
        ):
            raise ToolAssetExecutionContractError("an acceptance successor requires its exact predecessor.")
        if self.acceptance_predecessor_global_id is not None:
            object.__setattr__(self, "acceptance_predecessor_global_id", _uuid(self.acceptance_predecessor_global_id, "source.acceptancePredecessorGlobalId"))
        if self.acceptance_predecessor_snapshot_hash is not None:
            object.__setattr__(self, "acceptance_predecessor_snapshot_hash", _hash(self.acceptance_predecessor_snapshot_hash, "source.acceptancePredecessorSnapshotHash"))
        object.__setattr__(self, "accepted_at", _datetime(self.accepted_at, "source.acceptedAt"))
        stream = canonical_hash(
            {
                "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
                "tenantId": self.tenant_id,
                "projectGlobalId": str(self.project_global_id),
                "toolingSetGlobalId": str(self.tooling_set_global_id),
            }
        )
        if self.source_stream_key_hash and _hash(self.source_stream_key_hash, "source.sourceStreamKeyHash") != stream:
            raise ToolAssetExecutionContractError("source stream key hash does not match the physical Set identity.")
        object.__setattr__(self, "source_stream_key_hash", stream)
        digest = canonical_hash(self.source_payload())
        if self.source_hash and _hash(self.source_hash, "source.sourceHash") != digest:
            raise ToolAssetExecutionContractError("source hash does not match the exact Tooling evidence.")
        object.__setattr__(self, "source_hash", digest)

    def source_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingMasterTitle": self.tooling_master_title,
            "toolingMasterSnapshotHash": self.tooling_master_snapshot_hash,
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "toolingSetPhysicalSerial": self.tooling_set_physical_serial,
            "toolingSetSnapshotHash": self.tooling_set_snapshot_hash,
            "toolingRequirementKind": self.tooling_requirement_kind,
            "setRevisionBindingGlobalId": str(self.set_revision_binding_global_id),
            "setRevisionBindingSnapshotHash": self.set_revision_binding_snapshot_hash,
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionNumber": self.tooling_revision_number,
            "toolingRevisionLabel": self.tooling_revision_label,
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "acceptanceRevisionGlobalId": str(self.acceptance_revision_global_id),
            "acceptanceGlobalId": str(self.acceptance_global_id),
            "acceptanceVersion": self.acceptance_version,
            "acceptancePredecessorGlobalId": str(self.acceptance_predecessor_global_id) if self.acceptance_predecessor_global_id else None,
            "acceptancePredecessorSnapshotHash": self.acceptance_predecessor_snapshot_hash,
            "acceptanceSnapshotHash": self.acceptance_snapshot_hash,
            "acceptedAt": _utc_text(self.accepted_at),
            "ownedFieldsManifest": list(TOOL_ASSET_OWNED_FIELDS),
        }

    def canonical_mapping(self) -> dict[str, object]:
        return {
            **self.source_payload(),
            "sourceStreamKeyHash": self.source_stream_key_hash,
            "sourceHash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class ToolAssetBusinessApprovalReference:
    state: ToolAssetApprovalState
    policy_id: str | None = None
    policy_version: int | None = None
    policy_hash: str | None = None
    evidence_reference: str | None = None
    evidence_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, ToolAssetApprovalState):
            raise ToolAssetExecutionContractError("approval state is invalid.")
        supplied = (
            self.policy_id,
            self.policy_version,
            self.policy_hash,
            self.evidence_reference,
            self.evidence_hash,
        )
        if self.state is ToolAssetApprovalState.UNAVAILABLE:
            if any(value is not None for value in supplied):
                raise ToolAssetExecutionContractError("unavailable approval cannot contain inferred approval evidence.")
            return
        object.__setattr__(self, "policy_id", _text(self.policy_id, "approval.policyId", 128, _CODE))
        object.__setattr__(self, "policy_version", _positive(self.policy_version, "approval.policyVersion"))
        object.__setattr__(self, "policy_hash", _hash(self.policy_hash, "approval.policyHash"))
        object.__setattr__(self, "evidence_reference", _text(self.evidence_reference, "approval.evidenceReference", 140, _CODE))
        object.__setattr__(self, "evidence_hash", _hash(self.evidence_hash, "approval.evidenceHash"))

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "policyId": self.policy_id,
            "policyVersion": self.policy_version,
            "policyHash": self.policy_hash,
            "evidenceReference": self.evidence_reference,
            "evidenceHash": self.evidence_hash,
        }


@dataclass(frozen=True, slots=True)
class ToolAssetMappingExpectation:
    operation: ToolAssetExecutionOperation
    source_stream_key_hash: str
    mapping_version: int
    formal_asset_id: str | None = None
    target_version: str | None = None
    observation_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.operation, ToolAssetExecutionOperation):
            raise ToolAssetExecutionContractError("mapping operation is invalid.")
        object.__setattr__(self, "source_stream_key_hash", _hash(self.source_stream_key_hash, "mapping.sourceStreamKeyHash"))
        object.__setattr__(self, "mapping_version", _nonnegative(self.mapping_version, "mapping.mappingVersion"))
        if self.operation is ToolAssetExecutionOperation.CREATE:
            if self.mapping_version != 0 or any(value is not None for value in (self.formal_asset_id, self.target_version, self.observation_hash)):
                raise ToolAssetExecutionContractError("create_tool_asset requires an exact unmapped expectation.")
            return
        object.__setattr__(self, "formal_asset_id", _text(self.formal_asset_id, "mapping.formalAssetId", 140, _CODE))
        object.__setattr__(self, "target_version", _text(self.target_version, "mapping.targetVersion", 140))
        object.__setattr__(self, "observation_hash", _hash(self.observation_hash, "mapping.observationHash"))
        if self.mapping_version < 1:
            raise ToolAssetExecutionContractError("update_tool_asset requires a current mapping version.")

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "operation": self.operation.value,
            "sourceStreamKeyHash": self.source_stream_key_hash,
            "mappingVersion": self.mapping_version,
            "formalAssetId": self.formal_asset_id,
            "targetVersion": self.target_version,
            "observationHash": self.observation_hash,
        }


@dataclass(frozen=True, slots=True)
class ToolAssetExecutionProfileReference:
    profile_id: str
    profile_version: int
    target_mode: ToolAssetExecutionTargetMode
    environment_code: str
    projection_policy_id: str
    projection_policy_version: int
    projection_policy_hash: str
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _text(self.profile_id, "profile.profileId", 128, _CODE))
        object.__setattr__(self, "profile_version", _positive(self.profile_version, "profile.profileVersion"))
        if not isinstance(self.target_mode, ToolAssetExecutionTargetMode):
            raise ToolAssetExecutionContractError("profile target mode is invalid.")
        object.__setattr__(self, "environment_code", _text(self.environment_code, "profile.environmentCode", 64, _CODE))
        object.__setattr__(self, "projection_policy_id", _text(self.projection_policy_id, "profile.projectionPolicyId", 128, _CODE))
        object.__setattr__(self, "projection_policy_version", _positive(self.projection_policy_version, "profile.projectionPolicyVersion"))
        object.__setattr__(self, "projection_policy_hash", _hash(self.projection_policy_hash, "profile.projectionPolicyHash"))
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "profile.snapshotHash"))

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "targetMode": self.target_mode.value,
            "environmentCode": self.environment_code,
            "projectionPolicyId": self.projection_policy_id,
            "projectionPolicyVersion": self.projection_policy_version,
            "projectionPolicyHash": self.projection_policy_hash,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ToolAssetExecutionRequest:
    global_id: UUID
    source: ToolAssetSourceSnapshot
    approval: ToolAssetBusinessApprovalReference
    mapping_expectation: ToolAssetMappingExpectation
    profile: ToolAssetExecutionProfileReference
    state: ToolAssetExecutionRequestState
    actor_user_id: str
    request_id: UUID
    trace_id: str
    idempotency_key_hash: str
    created_at: datetime
    optimistic_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "request.globalId"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "request.requestId"))
        for value, label, kind in (
            (self.source, "source", ToolAssetSourceSnapshot),
            (self.approval, "approval", ToolAssetBusinessApprovalReference),
            (self.mapping_expectation, "mappingExpectation", ToolAssetMappingExpectation),
            (self.profile, "profile", ToolAssetExecutionProfileReference),
        ):
            if not isinstance(value, kind):
                raise ToolAssetExecutionContractError(f"request.{label} is invalid.")
        if self.mapping_expectation.source_stream_key_hash != self.source.source_stream_key_hash:
            raise ToolAssetExecutionContractError("mapping expectation is outside the exact physical Set stream.")
        if not isinstance(self.state, ToolAssetExecutionRequestState):
            raise ToolAssetExecutionContractError("request state is invalid.")
        if self.profile.target_mode is ToolAssetExecutionTargetMode.MOCK:
            if self.approval.state is not ToolAssetApprovalState.UNAVAILABLE or self.state is not ToolAssetExecutionRequestState.VALIDATED_MOCK:
                raise ToolAssetExecutionContractError("Mock Tool Asset requests must remain unapproved validated evidence.")
        elif self.state is ToolAssetExecutionRequestState.VALIDATED_MOCK:
            raise ToolAssetExecutionContractError("Only Mock requests may use validated_mock state.")
        if self.profile.target_mode is ToolAssetExecutionTargetMode.SYNTHETIC and self.state in {
            ToolAssetExecutionRequestState.PARTIALLY_SUCCEEDED,
            ToolAssetExecutionRequestState.SUCCEEDED,
            ToolAssetExecutionRequestState.MAPPING_CONFLICT,
        }:
            raise ToolAssetExecutionContractError("Synthetic Tool Asset execution cannot contain authoritative target truth.")
        if self.profile.target_mode is ToolAssetExecutionTargetMode.SANDBOX and self.state is ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED:
            raise ToolAssetExecutionContractError("Sandbox Tool Asset execution cannot contain synthetic result truth.")
        if self.profile.target_mode is ToolAssetExecutionTargetMode.SANDBOX and self.approval.state is not ToolAssetApprovalState.VERIFIED:
            raise ToolAssetExecutionContractError("Sandbox Tool Asset execution requires separate verified business approval.")
        object.__setattr__(self, "actor_user_id", _text(self.actor_user_id, "request.actorUserId", 254, _ACTOR))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "request.traceId", 128, _TRACE))
        object.__setattr__(self, "idempotency_key_hash", _hash(self.idempotency_key_hash, "request.idempotencyKeyHash"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "request.createdAt"))
        object.__setattr__(self, "optimistic_version", _positive(self.optimistic_version, "request.optimisticVersion"))

    @property
    def operation(self) -> ToolAssetExecutionOperation:
        return self.mapping_expectation.operation

    @property
    def payload_hash(self) -> str:
        return canonical_hash(
            {
                "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
                "apiVersion": TOOL_ASSET_EXECUTION_API_VERSION,
                "operation": self.operation.value,
                "source": self.source.canonical_mapping(),
                "approval": self.approval.canonical_mapping(),
                "mappingExpectation": self.mapping_expectation.canonical_mapping(),
                "profile": self.profile.canonical_mapping(),
            }
        )

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
            "apiVersion": TOOL_ASSET_EXECUTION_API_VERSION,
            "globalId": str(self.global_id),
            "operation": self.operation.value,
            "tenantId": self.source.tenant_id,
            "projectGlobalId": str(self.source.project_global_id),
            "source": self.source.canonical_mapping(),
            "approval": self.approval.canonical_mapping(),
            "mappingExpectation": self.mapping_expectation.canonical_mapping(),
            "profile": self.profile.canonical_mapping(),
            "state": self.state.value,
            "actorUserId": self.actor_user_id,
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "idempotencyKeyHash": self.idempotency_key_hash,
            "payloadHash": self.payload_hash,
            "optimisticVersion": self.optimistic_version,
            "createdAt": _utc_text(self.created_at),
        }


def tool_asset_execution_request_from_mapping(record: Mapping[str, object]) -> ToolAssetExecutionRequest:
    """Rebuild one closed request snapshot and prove its canonical equality."""

    try:
        supplied = _closed_mapping(
            record,
            {
                "schemaVersion", "apiVersion", "globalId", "operation",
                "tenantId", "projectGlobalId", "source", "approval",
                "mappingExpectation", "profile", "state", "actorUserId",
                "requestId", "traceId", "idempotencyKeyHash", "payloadHash",
                "optimisticVersion", "createdAt",
            },
            "request",
        )
        if supplied["schemaVersion"] != TOOL_ASSET_EXECUTION_SCHEMA_VERSION or supplied["apiVersion"] != TOOL_ASSET_EXECUTION_API_VERSION:
            raise ToolAssetExecutionContractError("request version is invalid.")
        source = tool_asset_source_from_mapping(_mapping_value(supplied["source"], "request.source"))
        if supplied["tenantId"] != source.tenant_id or supplied["projectGlobalId"] != str(source.project_global_id):
            raise ToolAssetExecutionContractError("request source context is invalid.")
        approval_record = _closed_mapping(
            _mapping_value(supplied["approval"], "request.approval"),
            {"state", "policyId", "policyVersion", "policyHash", "evidenceReference", "evidenceHash"},
            "request.approval",
        )
        approval = ToolAssetBusinessApprovalReference(
            state=ToolAssetApprovalState(approval_record["state"]),
            policy_id=approval_record["policyId"],
            policy_version=approval_record["policyVersion"],
            policy_hash=approval_record["policyHash"],
            evidence_reference=approval_record["evidenceReference"],
            evidence_hash=approval_record["evidenceHash"],
        )
        mapping_record = _closed_mapping(
            _mapping_value(supplied["mappingExpectation"], "request.mappingExpectation"),
            {"operation", "sourceStreamKeyHash", "mappingVersion", "formalAssetId", "targetVersion", "observationHash"},
            "request.mappingExpectation",
        )
        expectation = ToolAssetMappingExpectation(
            operation=ToolAssetExecutionOperation(mapping_record["operation"]),
            source_stream_key_hash=mapping_record["sourceStreamKeyHash"],
            mapping_version=mapping_record["mappingVersion"],
            formal_asset_id=mapping_record["formalAssetId"],
            target_version=mapping_record["targetVersion"],
            observation_hash=mapping_record["observationHash"],
        )
        profile_record = _closed_mapping(
            _mapping_value(supplied["profile"], "request.profile"),
            {"profileId", "profileVersion", "targetMode", "environmentCode", "projectionPolicyId", "projectionPolicyVersion", "projectionPolicyHash", "snapshotHash"},
            "request.profile",
        )
        profile = ToolAssetExecutionProfileReference(
            profile_id=profile_record["profileId"],
            profile_version=profile_record["profileVersion"],
            target_mode=ToolAssetExecutionTargetMode(profile_record["targetMode"]),
            environment_code=profile_record["environmentCode"],
            projection_policy_id=profile_record["projectionPolicyId"],
            projection_policy_version=profile_record["projectionPolicyVersion"],
            projection_policy_hash=profile_record["projectionPolicyHash"],
            snapshot_hash=profile_record["snapshotHash"],
        )
        value = ToolAssetExecutionRequest(
            global_id=supplied["globalId"],
            source=source,
            approval=approval,
            mapping_expectation=expectation,
            profile=profile,
            state=ToolAssetExecutionRequestState(supplied["state"]),
            actor_user_id=supplied["actorUserId"],
            request_id=supplied["requestId"],
            trace_id=supplied["traceId"],
            idempotency_key_hash=supplied["idempotencyKeyHash"],
            created_at=_iso_datetime(supplied["createdAt"], "request.createdAt"),
            optimistic_version=supplied["optimisticVersion"],
        )
    except ToolAssetExecutionContractError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise ToolAssetExecutionContractError("request snapshot is invalid.") from error
    if value.operation.value != supplied["operation"] or value.canonical_mapping() != supplied:
        raise ToolAssetExecutionContractError("request snapshot does not match its canonical truth.")
    return value


def tool_asset_source_from_mapping(record: Mapping[str, object]) -> ToolAssetSourceSnapshot:
    """Rebuild one closed exact physical-Set source snapshot."""

    try:
        supplied = _closed_mapping(
            record,
            {
                "schemaVersion", "tenantId", "projectGlobalId",
                "toolingMasterGlobalId", "toolingMasterTitle",
                "toolingMasterSnapshotHash", "toolingSetGlobalId",
                "toolingSetPhysicalSerial", "toolingSetSnapshotHash",
                "toolingRequirementKind", "setRevisionBindingGlobalId",
                "setRevisionBindingSnapshotHash", "toolingRevisionGlobalId",
                "toolingRevisionNumber", "toolingRevisionLabel",
                "toolingRevisionSnapshotHash", "acceptanceRevisionGlobalId",
                "acceptanceGlobalId", "acceptanceVersion",
                "acceptancePredecessorGlobalId",
                "acceptancePredecessorSnapshotHash", "acceptanceSnapshotHash",
                "acceptedAt", "ownedFieldsManifest", "sourceStreamKeyHash",
                "sourceHash",
            },
            "source",
        )
        if supplied["schemaVersion"] != TOOL_ASSET_EXECUTION_SCHEMA_VERSION or supplied["ownedFieldsManifest"] != list(TOOL_ASSET_OWNED_FIELDS):
            raise ToolAssetExecutionContractError("source version or owned-field manifest is invalid.")
        value = ToolAssetSourceSnapshot(
            tenant_id=supplied["tenantId"],
            project_global_id=supplied["projectGlobalId"],
            tooling_master_global_id=supplied["toolingMasterGlobalId"],
            tooling_master_title=supplied["toolingMasterTitle"],
            tooling_master_snapshot_hash=supplied["toolingMasterSnapshotHash"],
            tooling_set_global_id=supplied["toolingSetGlobalId"],
            tooling_set_physical_serial=supplied["toolingSetPhysicalSerial"],
            tooling_set_snapshot_hash=supplied["toolingSetSnapshotHash"],
            tooling_requirement_kind=supplied["toolingRequirementKind"],
            set_revision_binding_global_id=supplied["setRevisionBindingGlobalId"],
            set_revision_binding_snapshot_hash=supplied["setRevisionBindingSnapshotHash"],
            tooling_revision_global_id=supplied["toolingRevisionGlobalId"],
            tooling_revision_number=supplied["toolingRevisionNumber"],
            tooling_revision_label=supplied["toolingRevisionLabel"],
            tooling_revision_snapshot_hash=supplied["toolingRevisionSnapshotHash"],
            acceptance_revision_global_id=supplied["acceptanceRevisionGlobalId"],
            acceptance_global_id=supplied["acceptanceGlobalId"],
            acceptance_version=supplied["acceptanceVersion"],
            acceptance_predecessor_global_id=supplied["acceptancePredecessorGlobalId"],
            acceptance_predecessor_snapshot_hash=supplied["acceptancePredecessorSnapshotHash"],
            acceptance_snapshot_hash=supplied["acceptanceSnapshotHash"],
            accepted_at=_iso_datetime(supplied["acceptedAt"], "source.acceptedAt"),
            source_stream_key_hash=supplied["sourceStreamKeyHash"],
            source_hash=supplied["sourceHash"],
        )
    except ToolAssetExecutionContractError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise ToolAssetExecutionContractError("source snapshot is invalid.") from error
    if value.canonical_mapping() != supplied:
        raise ToolAssetExecutionContractError("source snapshot does not match its canonical truth.")
    return value


@dataclass(frozen=True, slots=True)
class ToolAssetFieldResult:
    field_code: str
    state: ToolAssetFieldResultState
    authority: ToolAssetResultAuthority
    response_authenticated: bool
    response_hash: str
    fault_kind: ToolAssetFaultKind

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_code", _text(self.field_code, "fieldResult.fieldCode", 128, _CODE))
        if not isinstance(self.state, ToolAssetFieldResultState) or not isinstance(self.authority, ToolAssetResultAuthority) or not isinstance(self.fault_kind, ToolAssetFaultKind):
            raise ToolAssetExecutionContractError("field result enum is invalid.")
        if type(self.response_authenticated) is not bool:
            raise ToolAssetExecutionContractError("field result authentication must be boolean.")
        object.__setattr__(self, "response_hash", _hash(self.response_hash, "fieldResult.responseHash"))
        if self.state is ToolAssetFieldResultState.SUCCEEDED_AUTHORITATIVE:
            if self.authority is not ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX or not self.response_authenticated or self.fault_kind is not ToolAssetFaultKind.NONE:
                raise ToolAssetExecutionContractError("successful field truth requires authenticated Sandbox authority.")
        elif self.state is ToolAssetFieldResultState.SYNTHETIC_VERIFIED:
            if self.authority is not ToolAssetResultAuthority.SYNTHETIC or self.response_authenticated or self.fault_kind is not ToolAssetFaultKind.NONE:
                raise ToolAssetExecutionContractError("synthetic field proof cannot contain authoritative target truth.")
        elif self.authority is not ToolAssetResultAuthority.NONE or self.response_authenticated or self.fault_kind is ToolAssetFaultKind.NONE:
            raise ToolAssetExecutionContractError("failed, conflicted or uncertain field truth requires one non-authoritative fault.")
        if self.state is ToolAssetFieldResultState.UNCERTAIN_AFTER_TIMEOUT and self.fault_kind not in {
            ToolAssetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
            ToolAssetFaultKind.RESPONSE_CONTRACT_INVALID,
        }:
            raise ToolAssetExecutionContractError("uncertain field truth requires an exact possible-commit fault.")

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "fieldCode": self.field_code,
            "state": self.state.value,
            "authority": self.authority.value,
            "responseAuthenticated": self.response_authenticated,
            "responseHash": self.response_hash,
            "faultKind": self.fault_kind.value,
        }


def aggregate_field_results(results: tuple[ToolAssetFieldResult, ...]) -> ToolAssetExecutionRequestState:
    if type(results) is not tuple or not results or not all(isinstance(value, ToolAssetFieldResult) for value in results):
        raise ToolAssetExecutionContractError("field results must be one immutable non-empty set.")
    codes = [value.field_code for value in results]
    if len(codes) != len(set(codes)):
        raise ToolAssetExecutionContractError("field result codes must be unique.")
    states = {value.state for value in results}
    if states == {ToolAssetFieldResultState.SYNTHETIC_VERIFIED}:
        return ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED
    if states == {ToolAssetFieldResultState.SUCCEEDED_AUTHORITATIVE}:
        return ToolAssetExecutionRequestState.SUCCEEDED
    if ToolAssetFieldResultState.UNCERTAIN_AFTER_TIMEOUT in states:
        return ToolAssetExecutionRequestState.UNCERTAIN_AFTER_TIMEOUT
    if ToolAssetFieldResultState.OBSERVED_CONFLICT in states:
        return ToolAssetExecutionRequestState.MAPPING_CONFLICT
    if ToolAssetFieldResultState.FAILED_FINAL in states and len(states) == 1:
        return ToolAssetExecutionRequestState.FAILED_FINAL
    if ToolAssetFieldResultState.FAILED_RETRYABLE in states and len(states) == 1:
        return ToolAssetExecutionRequestState.FAILED_RETRYABLE
    return ToolAssetExecutionRequestState.PARTIALLY_SUCCEEDED


def classify_mapping_result(
    expectation: ToolAssetMappingExpectation,
    *,
    result_state: ToolAssetExecutionRequestState,
    authority: ToolAssetResultAuthority,
    response_authenticated: bool,
    observed_formal_asset_id: str | None,
    observed_previous_mapping_version: int,
) -> ToolAssetMappingDisposition:
    if result_state is not ToolAssetExecutionRequestState.SUCCEEDED:
        return ToolAssetMappingDisposition.RESULT_NOT_COMPLETE
    if authority is not ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX or response_authenticated is not True:
        return ToolAssetMappingDisposition.NON_AUTHORITATIVE
    if observed_previous_mapping_version != expectation.mapping_version:
        return ToolAssetMappingDisposition.EXPECTATION_CONFLICT
    observed = _text(observed_formal_asset_id, "result.formalAssetId", 140, _CODE)
    if expectation.operation is ToolAssetExecutionOperation.UPDATE and observed != expectation.formal_asset_id:
        return ToolAssetMappingDisposition.TARGET_IDENTITY_CONFLICT
    return ToolAssetMappingDisposition.ADVANCE


def classify_adapter_fault(
    *,
    adapter_boundary_crossed: bool,
    timeout: bool = False,
    status_code: int | None = None,
    business_rejected: bool = False,
    response_contract_valid: bool = True,
    response_authenticated: bool = True,
) -> ToolAssetFaultKind:
    if type(adapter_boundary_crossed) is not bool or type(timeout) is not bool:
        raise ToolAssetExecutionContractError("adapter fault flags must be boolean.")
    if timeout:
        return ToolAssetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT if adapter_boundary_crossed else ToolAssetFaultKind.TARGET_UNAVAILABLE
    if status_code == 429:
        return ToolAssetFaultKind.RATE_LIMITED
    if status_code is not None and status_code >= 500:
        return ToolAssetFaultKind.TARGET_SERVER_ERROR
    if business_rejected:
        return ToolAssetFaultKind.BUSINESS_VALIDATION
    if not response_contract_valid:
        return ToolAssetFaultKind.RESPONSE_CONTRACT_INVALID
    if not response_authenticated:
        return ToolAssetFaultKind.RESPONSE_AUTHENTICATION_INVALID
    return ToolAssetFaultKind.NONE


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _uuid(value: object, path: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ToolAssetExecutionContractError(f"{path} must be a UUID.") from error


def _text(value: object, path: str, maximum: int, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or value != value.strip() or not value or len(value) > maximum or (pattern is not None and pattern.fullmatch(value) is None):
        raise ToolAssetExecutionContractError(f"{path} is invalid.")
    return value


def _hash(value: object, path: str) -> str:
    return _text(value, path, 64, _HASH)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise ToolAssetExecutionContractError(f"{path} must be positive.")
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ToolAssetExecutionContractError(f"{path} must be nonnegative.")
    return value


def _datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ToolAssetExecutionContractError(f"{path} must be timezone-aware.")
    return value.astimezone(UTC)


def _iso_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ToolAssetExecutionContractError(f"{path} must be a canonical UTC datetime.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ToolAssetExecutionContractError(f"{path} must be a canonical UTC datetime.") from error
    if _utc_text(parsed) != value:
        raise ToolAssetExecutionContractError(f"{path} must be a canonical UTC datetime.")
    return parsed


def _mapping_value(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ToolAssetExecutionContractError(f"{path} must be an object.")
    return value


def _closed_mapping(
    value: Mapping[str, object],
    expected_keys: set[str],
    path: str,
) -> dict[str, object]:
    supplied = dict(_mapping_value(value, path))
    if set(supplied) != expected_keys:
        raise ToolAssetExecutionContractError(f"{path} fields are invalid.")
    return supplied


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
