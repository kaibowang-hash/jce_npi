from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID


MBOM_PUBLISH_SCHEMA_VERSION = 2
MBOM_PUBLISH_EVENT_VERSION = 1
MBOM_PUBLISH_API_VERSION = "npi.erp-mbom-publish.v1"
MBOM_PUBLISH_OPERATION = "publish_released_mbom"
MBOM_PUBLISH_ACKNOWLEDGEMENT = (
    "I confirm this request uses the exact released EBOM topology, current Item "
    "readiness, MBOM expectations, and execution profile."
)
MBOM_REQUEST_EVENT_TYPE = "npi.mbom_publish_request.ready"
MBOM_RESULT_EVENT_TYPE = "erpnext.mbom_publish_result.observed"
MAX_MBOM_LINES = 500

_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_ENGINEERING_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_LINE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_UOM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,15}$")


class MbomPublishContractError(ValueError):
    """Raised when an MBOM execution value is not exactly contract-shaped."""


class MbomTargetMode(StrEnum):
    MOCK = "mock"
    SYNTHETIC = "synthetic"
    SANDBOX = "sandbox"


class MbomSourceRole(StrEnum):
    ASSEMBLY = "assembly"
    COMPONENT_ONLY = "component_only"


class ItemReadinessDisposition(StrEnum):
    ADVANCED = "advanced"
    NOT_READY = "not_ready"
    SYNTHETIC_REFERENCE = "synthetic_reference"


class MbomTargetSubmissionState(StrEnum):
    UNMAPPED_CREATE = "unmapped_create"
    EDITABLE_DRAFT = "editable_draft"
    SUBMITTED_IMMUTABLE = "submitted_immutable"


class MbomPublishIntent(StrEnum):
    CREATE_DRAFT = "create_draft"
    UPDATE_DRAFT = "update_draft"


class MbomPublishRequestState(StrEnum):
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


class MbomNodeResultState(StrEnum):
    SYNTHETIC_VERIFIED = "synthetic_verified"
    SUCCEEDED_AUTHORITATIVE = "succeeded_authoritative"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    BLOCKED_ITEM_MAPPING = "blocked_item_mapping"
    BLOCKED_SUBMITTED = "blocked_submitted"
    UNCERTAIN_AFTER_TIMEOUT = "uncertain_after_timeout"
    OBSERVED_CONFLICT = "observed_conflict"


class MbomResultAuthority(StrEnum):
    NONE = "none"
    SYNTHETIC = "synthetic"
    AUTHORITATIVE_SANDBOX = "authoritative_sandbox"


class MbomMappingDisposition(StrEnum):
    ADVANCE = "advance"
    NON_AUTHORITATIVE = "non_authoritative"
    EXPECTATION_CONFLICT = "expectation_conflict"
    SUBMITTED_BLOCK = "submitted_block"
    TARGET_IDENTITY_CONFLICT = "target_identity_conflict"
    RESULT_NOT_SUCCESS = "result_not_success"


class MbomFaultKind(StrEnum):
    NONE = "none"
    SOURCE_CONFLICT = "source_conflict"
    ITEM_MAPPING_NOT_READY = "item_mapping_not_ready"
    STALE_MAPPING = "stale_mapping"
    SUBMITTED_BOM = "submitted_bom"
    TIMEOUT_AFTER_POSSIBLE_COMMIT = "timeout_after_possible_commit"
    RATE_LIMITED = "rate_limited"
    TARGET_SERVER_ERROR = "target_server_error"
    BUSINESS_VALIDATION = "business_validation"
    RESPONSE_CONTRACT_INVALID = "response_contract_invalid"
    RESPONSE_AUTHENTICATION_INVALID = "response_authentication_invalid"
    TARGET_UNAVAILABLE = "target_unavailable"


@dataclass(frozen=True, slots=True)
class MbomSourceLine:
    line_global_id: UUID
    stable_line_key: str
    parent_line_key: str | None
    engineering_item_id: str
    quantity: str
    engineering_uom: str
    alternates: tuple[str, ...]
    effectivity: tuple[tuple[str, str], ...]
    attributes: tuple[tuple[str, str], ...]
    line_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "line_global_id", _uuid(self.line_global_id, "line.globalId"))
        object.__setattr__(
            self,
            "stable_line_key",
            _text(self.stable_line_key, "line.stableLineKey", 128, _LINE_KEY_PATTERN),
        )
        if self.parent_line_key is not None:
            object.__setattr__(
                self,
                "parent_line_key",
                _text(self.parent_line_key, "line.parentLineKey", 128, _LINE_KEY_PATTERN),
            )
        object.__setattr__(
            self,
            "engineering_item_id",
            _text(
                self.engineering_item_id,
                "line.engineeringItemId",
                128,
                _ENGINEERING_ID_PATTERN,
            ),
        )
        object.__setattr__(self, "quantity", _quantity(self.quantity, "line.quantity"))
        object.__setattr__(
            self,
            "engineering_uom",
            _text(self.engineering_uom, "line.engineeringUom", 16, _UOM_PATTERN),
        )
        object.__setattr__(
            self,
            "alternates",
            _unique_texts(self.alternates, "line.alternates", maximum=32),
        )
        object.__setattr__(self, "effectivity", _pairs(self.effectivity, "line.effectivity"))
        object.__setattr__(self, "attributes", _pairs(self.attributes, "line.attributes"))
        object.__setattr__(self, "line_hash", _hash(self.line_hash, "line.lineHash"))
        if self.parent_line_key == self.stable_line_key:
            raise MbomPublishContractError("A source line cannot be its own parent.")

    def canonical_mapping(self, role: MbomSourceRole) -> dict[str, object]:
        return {
            "lineGlobalId": str(self.line_global_id),
            "stableLineKey": self.stable_line_key,
            "parentLineKey": self.parent_line_key,
            "engineeringItemId": self.engineering_item_id,
            "quantity": self.quantity,
            "engineeringUom": self.engineering_uom,
            "alternates": list(self.alternates),
            "effectivity": dict(self.effectivity),
            "attributes": dict(self.attributes),
            "lineHash": self.line_hash,
            "sourceRole": role.value,
        }


@dataclass(frozen=True, slots=True)
class MbomSourceSnapshot:
    tenant_id: str
    project_global_id: UUID
    ebom_global_id: UUID
    phase5_publish_request_global_id: UUID
    phase5_publish_request_payload_hash: str
    publish_policy_global_id: UUID
    publish_policy_version: int
    publish_policy_snapshot_hash: str
    revision_global_id: UUID
    revision_number: int
    revision_snapshot_hash: str
    lifecycle_version: int
    release_event_global_id: UUID
    release_event_hash: str
    approval_evidence_ids: tuple[UUID, ...]
    released_at: datetime
    lines: tuple[MbomSourceLine, ...]
    source_stream_key_hash: str = ""
    topology_hash: str = ""
    source_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _tenant(self.tenant_id, "source.tenantId"))
        for fieldname in (
            "project_global_id",
            "ebom_global_id",
            "phase5_publish_request_global_id",
            "publish_policy_global_id",
            "revision_global_id",
            "release_event_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"source.{fieldname}"),
            )
        for fieldname in (
            "publish_policy_version",
            "revision_number",
            "lifecycle_version",
        ):
            object.__setattr__(
                self,
                fieldname,
                _positive(getattr(self, fieldname), f"source.{fieldname}"),
            )
        for fieldname in (
            "phase5_publish_request_payload_hash",
            "publish_policy_snapshot_hash",
            "revision_snapshot_hash",
            "release_event_hash",
        ):
            object.__setattr__(
                self,
                fieldname,
                _hash(getattr(self, fieldname), f"source.{fieldname}"),
            )
        approvals = _unique_uuids(
            self.approval_evidence_ids,
            "source.approvalEvidenceIds",
            maximum=32,
        )
        if self.release_event_global_id not in approvals:
            raise MbomPublishContractError(
                "source.approvalEvidenceIds must include the release event."
            )
        object.__setattr__(self, "approval_evidence_ids", approvals)
        object.__setattr__(self, "released_at", _aware_utc(self.released_at, "source.releasedAt"))
        raw_lines = tuple(self.lines)
        if not raw_lines or len(raw_lines) > MAX_MBOM_LINES:
            raise MbomPublishContractError("source.lines is outside the supported boundary.")
        if not all(isinstance(line, MbomSourceLine) for line in raw_lines):
            raise MbomPublishContractError("source.lines is invalid.")
        lines = tuple(sorted(raw_lines, key=lambda line: line.stable_line_key))
        keys = [line.stable_line_key for line in lines]
        if len(set(keys)) != len(keys):
            raise MbomPublishContractError("source stable line keys must be unique.")
        if len({line.line_global_id for line in lines}) != len(lines):
            raise MbomPublishContractError("source line identities must be unique.")
        key_set = set(keys)
        if any(line.parent_line_key not in key_set for line in lines if line.parent_line_key):
            raise MbomPublishContractError("source parent line is unavailable.")
        roots = [line for line in lines if line.parent_line_key is None]
        if len(roots) != 1:
            raise MbomPublishContractError("source topology must contain exactly one root.")
        _require_acyclic(lines)
        object.__setattr__(self, "lines", lines)
        stream_hash = canonical_hash(
            {
                "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
                "tenantId": self.tenant_id,
                "projectGlobalId": str(self.project_global_id),
                "ebomGlobalId": str(self.ebom_global_id),
            }
        )
        if self.source_stream_key_hash and _hash(
            self.source_stream_key_hash, "source.sourceStreamKeyHash"
        ) != stream_hash:
            raise MbomPublishContractError("source stream key hash does not match its identity.")
        object.__setattr__(self, "source_stream_key_hash", stream_hash)
        topology_hash = canonical_hash(self.topology_payload())
        if self.topology_hash and _hash(self.topology_hash, "source.topologyHash") != topology_hash:
            raise MbomPublishContractError("source topology hash does not match its exact graph.")
        object.__setattr__(self, "topology_hash", topology_hash)
        source_hash = canonical_hash(self.source_payload())
        if self.source_hash and _hash(self.source_hash, "source.sourceHash") != source_hash:
            raise MbomPublishContractError("source hash does not match its exact released evidence.")
        object.__setattr__(self, "source_hash", source_hash)

    @property
    def roles(self) -> dict[str, MbomSourceRole]:
        parents = {line.parent_line_key for line in self.lines if line.parent_line_key}
        return {
            line.stable_line_key: (
                MbomSourceRole.ASSEMBLY
                if line.stable_line_key in parents
                else MbomSourceRole.COMPONENT_ONLY
            )
            for line in self.lines
        }

    @property
    def assembly_line_keys(self) -> tuple[str, ...]:
        return tuple(key for key, role in self.roles.items() if role is MbomSourceRole.ASSEMBLY)

    @property
    def engineering_item_ids(self) -> tuple[str, ...]:
        return tuple(sorted({line.engineering_item_id for line in self.lines}))

    def assembly_source_key(self, stable_line_key: str) -> str:
        if self.roles.get(stable_line_key) is not MbomSourceRole.ASSEMBLY:
            raise MbomPublishContractError("Only an assembly line has an MBOM source key.")
        return canonical_hash(
            {
                "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
                "tenantId": self.tenant_id,
                "projectGlobalId": str(self.project_global_id),
                "ebomGlobalId": str(self.ebom_global_id),
                "stableLineKey": stable_line_key,
            }
        )

    def topology_payload(self) -> dict[str, object]:
        roles = self.roles
        return {
            "revisionGlobalId": str(self.revision_global_id),
            "revisionNumber": self.revision_number,
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "lines": [line.canonical_mapping(roles[line.stable_line_key]) for line in self.lines],
        }

    def source_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "ebomGlobalId": str(self.ebom_global_id),
            "phase5PublishRequestGlobalId": str(self.phase5_publish_request_global_id),
            "phase5PublishRequestPayloadHash": self.phase5_publish_request_payload_hash,
            "publishPolicyGlobalId": str(self.publish_policy_global_id),
            "publishPolicyVersion": self.publish_policy_version,
            "publishPolicySnapshotHash": self.publish_policy_snapshot_hash,
            "lifecycleVersion": self.lifecycle_version,
            "releaseEventGlobalId": str(self.release_event_global_id),
            "releaseEventHash": self.release_event_hash,
            "approvalEvidenceIds": [str(value) for value in self.approval_evidence_ids],
            "releasedAt": _utc_text(self.released_at),
            "topology": self.topology_payload(),
        }

    def canonical_mapping(self) -> dict[str, object]:
        return {
            **self.source_payload(),
            "sourceStreamKeyHash": self.source_stream_key_hash,
            "topologyHash": self.topology_hash,
            "sourceHash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class ItemMappingReadiness:
    engineering_item_id: str
    disposition: ItemReadinessDisposition
    item_stream_key_hash: str
    mapping_version: int
    formal_item_code: str | None = None
    target_version: str | None = None
    observation_hash: str | None = None
    authority: MbomResultAuthority = MbomResultAuthority.NONE
    response_authenticated: bool = False
    synthetic_item_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "engineering_item_id",
            _text(self.engineering_item_id, "itemReadiness.engineeringItemId", 128, _ENGINEERING_ID_PATTERN),
        )
        if not isinstance(self.disposition, ItemReadinessDisposition):
            raise MbomPublishContractError("itemReadiness.disposition is invalid.")
        object.__setattr__(
            self,
            "item_stream_key_hash",
            _hash(self.item_stream_key_hash, "itemReadiness.itemStreamKeyHash"),
        )
        object.__setattr__(
            self,
            "mapping_version",
            _nonnegative(self.mapping_version, "itemReadiness.mappingVersion"),
        )
        formal = _optional_text(self.formal_item_code, "itemReadiness.formalItemCode", 140, _CODE_PATTERN)
        target = _optional_text(self.target_version, "itemReadiness.targetVersion", 140)
        observation = _optional_hash(self.observation_hash, "itemReadiness.observationHash")
        synthetic = _optional_text(
            self.synthetic_item_reference,
            "itemReadiness.syntheticItemReference",
            140,
            _CODE_PATTERN,
        )
        object.__setattr__(self, "formal_item_code", formal)
        object.__setattr__(self, "target_version", target)
        object.__setattr__(self, "observation_hash", observation)
        object.__setattr__(self, "synthetic_item_reference", synthetic)
        if type(self.response_authenticated) is not bool:
            raise MbomPublishContractError("itemReadiness.responseAuthenticated must be boolean.")
        if self.disposition is ItemReadinessDisposition.ADVANCED:
            if (
                self.mapping_version < 1
                or not all((formal, target, observation))
                or self.authority is not MbomResultAuthority.AUTHORITATIVE_SANDBOX
                or not self.response_authenticated
                or synthetic is not None
            ):
                raise MbomPublishContractError(
                    "Advanced Item readiness requires exact authenticated authoritative mapping truth."
                )
        elif self.disposition is ItemReadinessDisposition.SYNTHETIC_REFERENCE:
            if (
                self.mapping_version != 0
                or any((formal, target, observation))
                or self.authority is not MbomResultAuthority.SYNTHETIC
                or self.response_authenticated
                or synthetic is None
                or not synthetic.startswith("synthetic-item-")
            ):
                raise MbomPublishContractError(
                    "Synthetic Item readiness must remain test-only and non-authoritative."
                )
        elif (
            self.mapping_version != 0
            or any((formal, target, observation, synthetic))
            or self.authority is not MbomResultAuthority.NONE
            or self.response_authenticated
        ):
            raise MbomPublishContractError("Not-ready Item truth cannot contain a formal or synthetic identity.")

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "engineeringItemId": self.engineering_item_id,
            "disposition": self.disposition.value,
            "itemStreamKeyHash": self.item_stream_key_hash,
            "mappingVersion": self.mapping_version,
            "formalItemCode": self.formal_item_code,
            "targetVersion": self.target_version,
            "observationHash": self.observation_hash,
            "authority": self.authority.value,
            "responseAuthenticated": self.response_authenticated,
            "syntheticItemReference": self.synthetic_item_reference,
        }


def synthetic_item_readiness(source: MbomSourceSnapshot) -> tuple[ItemMappingReadiness, ...]:
    return tuple(
        ItemMappingReadiness(
            engineering_item_id=engineering_item_id,
            disposition=ItemReadinessDisposition.SYNTHETIC_REFERENCE,
            item_stream_key_hash=_item_stream_key_hash(source, engineering_item_id),
            mapping_version=0,
            authority=MbomResultAuthority.SYNTHETIC,
            synthetic_item_reference=(
                "synthetic-item-"
                + canonical_hash(
                    {
                        "sourceHash": source.source_hash,
                        "engineeringItemId": engineering_item_id,
                    }
                )[:24]
            ),
        )
        for engineering_item_id in source.engineering_item_ids
    )


def item_mapping_set_hash(
    source: MbomSourceSnapshot,
    readiness: Sequence[ItemMappingReadiness],
    *,
    target_mode: MbomTargetMode,
) -> str:
    values = tuple(sorted(readiness, key=lambda value: value.engineering_item_id))
    if len(values) != len(source.engineering_item_ids) or {
        value.engineering_item_id for value in values
    } != set(source.engineering_item_ids):
        raise MbomPublishContractError("Item readiness must cover every exact engineering identity once.")
    if len({value.engineering_item_id for value in values}) != len(values):
        raise MbomPublishContractError("Item readiness contains duplicate engineering identity.")
    if any(
        value.item_stream_key_hash
        != _item_stream_key_hash(source, value.engineering_item_id)
        for value in values
    ):
        raise MbomPublishContractError(
            "Item readiness stream key does not match the exact P8-03 Item identity."
        )
    if target_mode is MbomTargetMode.SANDBOX and any(
        value.disposition is not ItemReadinessDisposition.ADVANCED for value in values
    ):
        raise MbomPublishContractError("Sandbox MBOM execution requires every Item mapping to be ready.")
    if target_mode is MbomTargetMode.SYNTHETIC and any(
        value.disposition is not ItemReadinessDisposition.SYNTHETIC_REFERENCE for value in values
    ):
        raise MbomPublishContractError("Synthetic MBOM execution requires only source-derived test references.")
    return canonical_hash(
        {
            "sourceHash": source.source_hash,
            "targetMode": target_mode.value,
            "items": [value.canonical_mapping() for value in values],
        }
    )


@dataclass(frozen=True, slots=True)
class MbomMappingExpectation:
    assembly_source_key: str
    stable_line_key: str
    mapping_version: int
    submission_state: MbomTargetSubmissionState
    formal_bom_id: str | None = None
    target_version: str | None = None
    observation_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "assembly_source_key", _hash(self.assembly_source_key, "mbomExpectation.assemblySourceKey"))
        object.__setattr__(self, "stable_line_key", _text(self.stable_line_key, "mbomExpectation.stableLineKey", 128, _LINE_KEY_PATTERN))
        object.__setattr__(self, "mapping_version", _nonnegative(self.mapping_version, "mbomExpectation.mappingVersion"))
        if not isinstance(self.submission_state, MbomTargetSubmissionState):
            raise MbomPublishContractError("mbomExpectation.submissionState is invalid.")
        formal = _optional_text(self.formal_bom_id, "mbomExpectation.formalBomId", 140, _CODE_PATTERN)
        target = _optional_text(self.target_version, "mbomExpectation.targetVersion", 140)
        observation = _optional_hash(self.observation_hash, "mbomExpectation.observationHash")
        object.__setattr__(self, "formal_bom_id", formal)
        object.__setattr__(self, "target_version", target)
        object.__setattr__(self, "observation_hash", observation)
        if self.mapping_version == 0:
            if self.submission_state is not MbomTargetSubmissionState.UNMAPPED_CREATE or any(
                (formal, target, observation)
            ):
                raise MbomPublishContractError("An unmapped MBOM create cannot contain target identity or state.")
        elif (
            self.submission_state is MbomTargetSubmissionState.UNMAPPED_CREATE
            or not all((formal, target, observation))
        ):
            raise MbomPublishContractError("A mapped MBOM expectation requires exact target truth.")

    @property
    def intent(self) -> MbomPublishIntent:
        return (
            MbomPublishIntent.CREATE_DRAFT
            if self.mapping_version == 0
            else MbomPublishIntent.UPDATE_DRAFT
        )

    @property
    def dispatch_blocked(self) -> bool:
        return self.submission_state is MbomTargetSubmissionState.SUBMITTED_IMMUTABLE

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "assemblySourceKey": self.assembly_source_key,
            "stableLineKey": self.stable_line_key,
            "mappingVersion": self.mapping_version,
            "submissionState": self.submission_state.value,
            "intent": self.intent.value,
            "formalBomId": self.formal_bom_id,
            "targetVersion": self.target_version,
            "observationHash": self.observation_hash,
        }


def mbom_mapping_set_hash(
    source: MbomSourceSnapshot,
    expectations: Sequence[MbomMappingExpectation],
) -> str:
    values = tuple(sorted(expectations, key=lambda value: value.stable_line_key))
    if len({value.stable_line_key for value in values}) != len(values):
        raise MbomPublishContractError("MBOM expectations contain a duplicate assembly line.")
    if {value.stable_line_key for value in values} != set(source.assembly_line_keys):
        raise MbomPublishContractError("MBOM expectations must cover every exact assembly once.")
    if any(
        value.assembly_source_key != source.assembly_source_key(value.stable_line_key)
        for value in values
    ):
        raise MbomPublishContractError("MBOM expectation source key does not match the exact assembly.")
    return canonical_hash(
        {
            "sourceHash": source.source_hash,
            "topologyHash": source.topology_hash,
            "assemblies": [value.canonical_mapping() for value in values],
        }
    )


@dataclass(frozen=True, slots=True)
class MbomExecutionProfileReference:
    profile_id: str
    profile_version: int
    target_mode: MbomTargetMode
    environment_code: str
    projection_policy_id: str
    projection_policy_version: int
    projection_policy_hash: str
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _text(self.profile_id, "profile.id", 128, _CODE_PATTERN))
        object.__setattr__(self, "profile_version", _positive(self.profile_version, "profile.version"))
        if not isinstance(self.target_mode, MbomTargetMode):
            raise MbomPublishContractError("profile.targetMode is unsupported.")
        object.__setattr__(self, "environment_code", _text(self.environment_code, "profile.environmentCode", 64, _CODE_PATTERN))
        object.__setattr__(self, "projection_policy_id", _text(self.projection_policy_id, "profile.projectionPolicyId", 128, _CODE_PATTERN))
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
class MbomPublishRequest:
    global_id: UUID
    source: MbomSourceSnapshot
    item_readiness: tuple[ItemMappingReadiness, ...]
    item_mapping_set_hash: str
    mbom_expectations: tuple[MbomMappingExpectation, ...]
    mbom_mapping_set_hash: str
    profile: MbomExecutionProfileReference
    actor_user_id: str
    service_actor_user_id: str | None
    request_id: UUID
    trace_id: str
    idempotency_key_hash: str
    target_idempotency_key_hash: str
    semantic_effect_hash: str
    state: MbomPublishRequestState
    dispatch_allowed: bool
    payload_hash: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "request.globalId"))
        if not isinstance(self.source, MbomSourceSnapshot):
            raise MbomPublishContractError("request.source is invalid.")
        if not isinstance(self.profile, MbomExecutionProfileReference):
            raise MbomPublishContractError("request.profile is invalid.")
        if type(self.item_readiness) is not tuple or not all(
            isinstance(value, ItemMappingReadiness) for value in self.item_readiness
        ):
            raise MbomPublishContractError("request.itemReadiness is invalid.")
        if type(self.mbom_expectations) is not tuple or not all(
            isinstance(value, MbomMappingExpectation) for value in self.mbom_expectations
        ):
            raise MbomPublishContractError("request.mbomExpectations is invalid.")
        readiness = tuple(
            sorted(self.item_readiness, key=lambda value: value.engineering_item_id)
        )
        expectations = tuple(
            sorted(self.mbom_expectations, key=lambda value: value.stable_line_key)
        )
        object.__setattr__(self, "item_readiness", readiness)
        object.__setattr__(self, "mbom_expectations", expectations)
        expected_item_hash = item_mapping_set_hash(
            self.source,
            readiness,
            target_mode=self.profile.target_mode,
        )
        expected_mbom_hash = mbom_mapping_set_hash(self.source, expectations)
        if _hash(self.item_mapping_set_hash, "request.itemMappingSetHash") != expected_item_hash:
            raise MbomPublishContractError(
                "request Item mapping-set hash does not match its exact readiness."
            )
        if _hash(self.mbom_mapping_set_hash, "request.mbomMappingSetHash") != expected_mbom_hash:
            raise MbomPublishContractError(
                "request MBOM mapping-set hash does not match its exact expectations."
            )
        object.__setattr__(self, "item_mapping_set_hash", expected_item_hash)
        object.__setattr__(self, "mbom_mapping_set_hash", expected_mbom_hash)
        object.__setattr__(
            self,
            "actor_user_id",
            _text(self.actor_user_id, "request.actorUserId", 254, _ACTOR_PATTERN),
        )
        service_actor = _optional_text(
            self.service_actor_user_id,
            "request.serviceActorUserId",
            254,
            _ACTOR_PATTERN,
        )
        object.__setattr__(self, "service_actor_user_id", service_actor)
        object.__setattr__(self, "request_id", _uuid(self.request_id, "request.requestId"))
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "request.traceId", 128, _TRACE_PATTERN),
        )
        object.__setattr__(
            self,
            "idempotency_key_hash",
            _hash(self.idempotency_key_hash, "request.idempotencyKeyHash"),
        )
        if not isinstance(self.state, MbomPublishRequestState):
            raise MbomPublishContractError("request.state is unsupported.")
        if type(self.dispatch_allowed) is not bool:
            raise MbomPublishContractError("request.dispatchAllowed must be boolean.")
        executable = self.profile.target_mode is not MbomTargetMode.MOCK
        if self.dispatch_allowed is not executable:
            raise MbomPublishContractError("request dispatch authority does not match target mode.")
        if executable and service_actor is None:
            raise MbomPublishContractError("Executable MBOM requests require an exact service actor.")
        if not executable and (
            service_actor is not None
            or self.state is not MbomPublishRequestState.VALIDATED_MOCK
        ):
            raise MbomPublishContractError(
                "Mock MBOM requests cannot freeze execution authority or target state."
            )
        if executable and self.state is MbomPublishRequestState.VALIDATED_MOCK:
            raise MbomPublishContractError("Executable MBOM request state is invalid.")
        if executable and any(value.dispatch_blocked for value in expectations):
            raise MbomPublishContractError("A submitted MBOM mapping cannot be updated or replaced.")
        semantic_effect = canonical_hash(
            {
                "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
                "operation": MBOM_PUBLISH_OPERATION,
                "sourceStreamKeyHash": self.source.source_stream_key_hash,
                "sourceHash": self.source.source_hash,
                "topologyHash": self.source.topology_hash,
                "itemMappingSetHash": expected_item_hash,
                "mbomMappingSetHash": expected_mbom_hash,
                "profile": self.profile.canonical_mapping(),
            }
        )
        if _hash(self.semantic_effect_hash, "request.semanticEffectHash") != semantic_effect:
            raise MbomPublishContractError(
                "request semantic effect hash does not match its exact target effect."
            )
        target_key = canonical_hash(
            {
                "operation": MBOM_PUBLISH_OPERATION,
                "semanticEffectHash": semantic_effect,
            }
        )
        if _hash(
            self.target_idempotency_key_hash,
            "request.targetIdempotencyKeyHash",
        ) != target_key:
            raise MbomPublishContractError(
                "request target idempotency key does not match its semantic effect."
            )
        object.__setattr__(self, "semantic_effect_hash", semantic_effect)
        object.__setattr__(self, "target_idempotency_key_hash", target_key)
        object.__setattr__(
            self,
            "created_at",
            _aware_utc(self.created_at, "request.createdAt"),
        )
        expected_payload_hash = canonical_hash(self._command_hash_payload())
        if self.payload_hash and _hash(
            self.payload_hash,
            "request.payloadHash",
        ) != expected_payload_hash:
            raise MbomPublishContractError(
                "request payload hash does not match the exact command."
            )
        object.__setattr__(self, "payload_hash", expected_payload_hash)

    def payload(self) -> dict[str, object]:
        return {
            "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
            "apiVersion": MBOM_PUBLISH_API_VERSION,
            "operation": MBOM_PUBLISH_OPERATION,
            "globalId": str(self.global_id),
            "source": self.source.canonical_mapping(),
            "itemReadiness": [value.canonical_mapping() for value in self.item_readiness],
            "itemMappingSetHash": self.item_mapping_set_hash,
            "mbomExpectations": [value.canonical_mapping() for value in self.mbom_expectations],
            "mbomMappingSetHash": self.mbom_mapping_set_hash,
            "profile": self.profile.canonical_mapping(),
            "actorUserId": self.actor_user_id,
            "serviceActorUserId": self.service_actor_user_id,
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "idempotencyKeyHash": self.idempotency_key_hash,
            "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
            "semanticEffectHash": self.semantic_effect_hash,
            "state": self.state.value,
            "dispatchAllowed": self.dispatch_allowed,
            "createdAt": _utc_text(self.created_at),
        }

    def _command_hash_payload(self) -> dict[str, object]:
        """Return the immutable create-time payload used by ``payload_hash``."""

        initial_state = (
            MbomPublishRequestState.VALIDATED_MOCK
            if self.profile.target_mode is MbomTargetMode.MOCK
            else MbomPublishRequestState.QUEUED
        )
        return {**self.payload(), "state": initial_state.value}

    def event_payload(self) -> dict[str, object]:
        if not self.dispatch_allowed or self.profile.target_mode is MbomTargetMode.MOCK:
            raise MbomPublishContractError("Mock MBOM requests cannot emit an execution event.")
        return {
            "schema_version": MBOM_PUBLISH_EVENT_VERSION,
            "api_version": MBOM_PUBLISH_API_VERSION,
            "operation": MBOM_PUBLISH_OPERATION,
            "request_global_id": str(self.global_id),
            "request_payload_hash": self.payload_hash,
            "project_global_id": str(self.source.project_global_id),
            "source_stream_key_hash": self.source.source_stream_key_hash,
            "source_hash": self.source.source_hash,
            "topology_hash": self.source.topology_hash,
            "item_mapping_set_hash": self.item_mapping_set_hash,
            "mbom_mapping_set_hash": self.mbom_mapping_set_hash,
            "assembly_count": len(self.source.assembly_line_keys),
            "target_mode": self.profile.target_mode.value,
            "profile_id": self.profile.profile_id,
            "profile_version": self.profile.profile_version,
            "profile_snapshot_hash": self.profile.snapshot_hash,
            "projection_policy_hash": self.profile.projection_policy_hash,
            "idempotency_key_hash": self.idempotency_key_hash,
            "target_idempotency_key_hash": self.target_idempotency_key_hash,
            "semantic_effect_hash": self.semantic_effect_hash,
        }


def create_mbom_publish_request(
    *,
    source: MbomSourceSnapshot,
    item_readiness: Sequence[ItemMappingReadiness],
    mbom_expectations: Sequence[MbomMappingExpectation],
    profile: MbomExecutionProfileReference,
    actor_user_id: str,
    service_actor_user_id: str | None,
    request_id: UUID,
    trace_id: str,
    idempotency_key_hash: str,
    global_id: UUID,
    created_at: datetime,
) -> MbomPublishRequest:
    if not source.assembly_line_keys:
        raise MbomPublishContractError("The exact released topology contains no assembly node.")
    readiness = tuple(sorted(item_readiness, key=lambda value: value.engineering_item_id))
    expectations = tuple(sorted(mbom_expectations, key=lambda value: value.stable_line_key))
    item_set_hash = item_mapping_set_hash(source, readiness, target_mode=profile.target_mode)
    mbom_set_hash = mbom_mapping_set_hash(source, expectations)
    if profile.target_mode is not MbomTargetMode.MOCK and any(
        value.dispatch_blocked for value in expectations
    ):
        raise MbomPublishContractError("A submitted MBOM mapping cannot be updated or replaced.")
    actor = _text(actor_user_id, "request.actorUserId", 254, _ACTOR_PATTERN)
    service_actor = _optional_text(
        service_actor_user_id,
        "request.serviceActorUserId",
        254,
        _ACTOR_PATTERN,
    )
    if profile.target_mode is not MbomTargetMode.MOCK and service_actor is None:
        raise MbomPublishContractError("Executable MBOM requests require an exact service actor.")
    request_uuid = _uuid(request_id, "request.requestId")
    global_uuid = _uuid(global_id, "request.globalId")
    trace = _text(trace_id, "request.traceId", 128, _TRACE_PATTERN)
    idempotency_hash = _hash(idempotency_key_hash, "request.idempotencyKeyHash")
    semantic_payload = {
        "schemaVersion": MBOM_PUBLISH_SCHEMA_VERSION,
        "operation": MBOM_PUBLISH_OPERATION,
        "sourceStreamKeyHash": source.source_stream_key_hash,
        "sourceHash": source.source_hash,
        "topologyHash": source.topology_hash,
        "itemMappingSetHash": item_set_hash,
        "mbomMappingSetHash": mbom_set_hash,
        "profile": profile.canonical_mapping(),
    }
    semantic_effect = canonical_hash(semantic_payload)
    target_key = canonical_hash(
        {
            "operation": MBOM_PUBLISH_OPERATION,
            "semanticEffectHash": semantic_effect,
        }
    )
    state = (
        MbomPublishRequestState.VALIDATED_MOCK
        if profile.target_mode is MbomTargetMode.MOCK
        else MbomPublishRequestState.QUEUED
    )
    return MbomPublishRequest(
        global_id=global_uuid,
        source=source,
        item_readiness=readiness,
        item_mapping_set_hash=item_set_hash,
        mbom_expectations=expectations,
        mbom_mapping_set_hash=mbom_set_hash,
        profile=profile,
        actor_user_id=actor,
        service_actor_user_id=service_actor,
        request_id=request_uuid,
        trace_id=trace,
        idempotency_key_hash=idempotency_hash,
        target_idempotency_key_hash=target_key,
        semantic_effect_hash=semantic_effect,
        state=state,
        dispatch_allowed=profile.target_mode is not MbomTargetMode.MOCK,
        payload_hash="",
        created_at=_aware_utc(created_at, "request.createdAt"),
    )


@dataclass(frozen=True, slots=True)
class MbomNodeObservation:
    stable_line_key: str
    assembly_source_key: str
    state: MbomNodeResultState
    authority: MbomResultAuthority
    response_authenticated: bool
    response_hash: str
    formal_bom_id: str | None = None
    target_version: str | None = None
    target_submission_state: MbomTargetSubmissionState | None = None
    fault_kind: MbomFaultKind = MbomFaultKind.NONE

    def __post_init__(self) -> None:
        object.__setattr__(self, "stable_line_key", _text(self.stable_line_key, "nodeResult.stableLineKey", 128, _LINE_KEY_PATTERN))
        object.__setattr__(self, "assembly_source_key", _hash(self.assembly_source_key, "nodeResult.assemblySourceKey"))
        object.__setattr__(self, "response_hash", _hash(self.response_hash, "nodeResult.responseHash"))
        if type(self.response_authenticated) is not bool:
            raise MbomPublishContractError("nodeResult.responseAuthenticated must be boolean.")
        if not isinstance(self.state, MbomNodeResultState):
            raise MbomPublishContractError("nodeResult.state is unsupported.")
        if not isinstance(self.authority, MbomResultAuthority):
            raise MbomPublishContractError("nodeResult.authority is unsupported.")
        if self.target_submission_state is not None and not isinstance(
            self.target_submission_state,
            MbomTargetSubmissionState,
        ):
            raise MbomPublishContractError("nodeResult.targetSubmissionState is unsupported.")
        if not isinstance(self.fault_kind, MbomFaultKind):
            raise MbomPublishContractError("nodeResult.faultKind is unsupported.")
        formal = _optional_text(self.formal_bom_id, "nodeResult.formalBomId", 140, _CODE_PATTERN)
        target = _optional_text(self.target_version, "nodeResult.targetVersion", 140)
        object.__setattr__(self, "formal_bom_id", formal)
        object.__setattr__(self, "target_version", target)
        if self.state is MbomNodeResultState.SUCCEEDED_AUTHORITATIVE:
            if (
                self.authority is not MbomResultAuthority.AUTHORITATIVE_SANDBOX
                or not self.response_authenticated
                or not all((formal, target))
                or self.target_submission_state is not MbomTargetSubmissionState.EDITABLE_DRAFT
                or self.fault_kind is not MbomFaultKind.NONE
            ):
                raise MbomPublishContractError(
                    "Successful MBOM node truth requires authenticated authoritative editable-draft result."
                )
        elif self.state is MbomNodeResultState.SYNTHETIC_VERIFIED:
            if (
                self.authority is not MbomResultAuthority.SYNTHETIC
                or self.response_authenticated
                or any((formal, target, self.target_submission_state))
                or self.fault_kind is not MbomFaultKind.NONE
            ):
                raise MbomPublishContractError("Synthetic MBOM proof cannot contain formal target truth.")
        elif (
            any((formal, target, self.target_submission_state))
            or self.authority is not MbomResultAuthority.NONE
            or self.response_authenticated
            or self.fault_kind is MbomFaultKind.NONE
        ):
            raise MbomPublishContractError(
                "Failed, blocked or uncertain MBOM node truth must remain non-authoritative with an exact fault."
            )
        if (
            self.state is MbomNodeResultState.UNCERTAIN_AFTER_TIMEOUT
            and self.fault_kind
            not in {
                MbomFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
                MbomFaultKind.RESPONSE_CONTRACT_INVALID,
            }
        ):
            raise MbomPublishContractError(
                "An uncertain MBOM node requires an exact possible-commit fault."
            )


def aggregate_node_results(results: Sequence[MbomNodeObservation]) -> MbomPublishRequestState:
    values = tuple(results)
    if not values:
        raise MbomPublishContractError("An MBOM aggregate requires at least one assembly result.")
    if not all(isinstance(value, MbomNodeObservation) for value in values):
        raise MbomPublishContractError("An MBOM aggregate contains invalid node truth.")
    if len({value.stable_line_key for value in values}) != len(values):
        raise MbomPublishContractError("An MBOM aggregate cannot contain duplicate assembly results.")
    counts = Counter(value.state for value in values)
    if len(counts) == 1:
        state = next(iter(counts))
        return {
            MbomNodeResultState.SYNTHETIC_VERIFIED: MbomPublishRequestState.SYNTHETIC_VERIFIED,
            MbomNodeResultState.SUCCEEDED_AUTHORITATIVE: MbomPublishRequestState.SUCCEEDED,
            MbomNodeResultState.FAILED_RETRYABLE: MbomPublishRequestState.FAILED_RETRYABLE,
            MbomNodeResultState.UNCERTAIN_AFTER_TIMEOUT: MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
            MbomNodeResultState.OBSERVED_CONFLICT: MbomPublishRequestState.MAPPING_CONFLICT,
            MbomNodeResultState.BLOCKED_SUBMITTED: MbomPublishRequestState.MAPPING_CONFLICT,
            MbomNodeResultState.BLOCKED_ITEM_MAPPING: MbomPublishRequestState.FAILED_FINAL,
            MbomNodeResultState.FAILED_FINAL: MbomPublishRequestState.FAILED_FINAL,
        }[state]
    if MbomNodeResultState.UNCERTAIN_AFTER_TIMEOUT in counts:
        return MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT
    return MbomPublishRequestState.PARTIALLY_SUCCEEDED


@dataclass(frozen=True, slots=True)
class CurrentMbomMapping:
    mapping_version: int
    formal_bom_id: str
    target_version: str
    submission_state: MbomTargetSubmissionState
    observation_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mapping_version", _positive(self.mapping_version, "currentMapping.mappingVersion"))
        object.__setattr__(self, "formal_bom_id", _text(self.formal_bom_id, "currentMapping.formalBomId", 140, _CODE_PATTERN))
        object.__setattr__(self, "target_version", _text(self.target_version, "currentMapping.targetVersion", 140))
        if not isinstance(self.submission_state, MbomTargetSubmissionState) or (
            self.submission_state is MbomTargetSubmissionState.UNMAPPED_CREATE
        ):
            raise MbomPublishContractError("A current MBOM mapping cannot be unmapped.")
        object.__setattr__(self, "observation_hash", _hash(self.observation_hash, "currentMapping.observationHash"))


def classify_mapping_observation(
    *,
    expectation: MbomMappingExpectation,
    current: CurrentMbomMapping | None,
    observation: MbomNodeObservation,
) -> MbomMappingDisposition:
    if not isinstance(expectation, MbomMappingExpectation) or (
        current is not None and not isinstance(current, CurrentMbomMapping)
    ) or not isinstance(observation, MbomNodeObservation):
        raise MbomPublishContractError("MBOM mapping comparison input is invalid.")
    if observation.state is not MbomNodeResultState.SUCCEEDED_AUTHORITATIVE:
        return MbomMappingDisposition.RESULT_NOT_SUCCESS
    if (
        observation.stable_line_key != expectation.stable_line_key
        or observation.assembly_source_key != expectation.assembly_source_key
    ):
        return MbomMappingDisposition.EXPECTATION_CONFLICT
    if (
        observation.authority is not MbomResultAuthority.AUTHORITATIVE_SANDBOX
        or not observation.response_authenticated
    ):
        return MbomMappingDisposition.NON_AUTHORITATIVE
    if expectation.dispatch_blocked:
        return MbomMappingDisposition.SUBMITTED_BLOCK
    if expectation.mapping_version == 0:
        if current is not None:
            return MbomMappingDisposition.EXPECTATION_CONFLICT
    elif current is None or (
        current.mapping_version,
        current.formal_bom_id,
        current.target_version,
        current.submission_state,
        current.observation_hash,
    ) != (
        expectation.mapping_version,
        expectation.formal_bom_id,
        expectation.target_version,
        expectation.submission_state,
        expectation.observation_hash,
    ):
        return MbomMappingDisposition.EXPECTATION_CONFLICT
    if expectation.formal_bom_id and observation.formal_bom_id != expectation.formal_bom_id:
        return MbomMappingDisposition.TARGET_IDENTITY_CONFLICT
    return MbomMappingDisposition.ADVANCE


@dataclass(frozen=True, slots=True)
class MbomFaultDecision:
    request_state: MbomPublishRequestState
    fault_kind: MbomFaultKind
    reconciliation_required: bool
    redispatch_allowed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.request_state, MbomPublishRequestState):
            raise MbomPublishContractError("fault.requestState is unsupported.")
        if not isinstance(self.fault_kind, MbomFaultKind):
            raise MbomPublishContractError("fault.kind is unsupported.")
        if type(self.reconciliation_required) is not bool or type(
            self.redispatch_allowed
        ) is not bool:
            raise MbomPublishContractError("fault directives must be boolean.")
        if self.redispatch_allowed:
            raise MbomPublishContractError("P8-04 never authorizes redispatch.")
        if self.request_state is MbomPublishRequestState.SUCCEEDED:
            if self.fault_kind is not MbomFaultKind.NONE or self.reconciliation_required:
                raise MbomPublishContractError("Successful MBOM truth cannot contain a fault.")
        elif self.fault_kind is MbomFaultKind.NONE:
            raise MbomPublishContractError("Failed MBOM truth requires an exact fault.")
        if self.request_state is MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT and (
            not self.reconciliation_required
            or self.fault_kind
            not in {
                MbomFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
                MbomFaultKind.RESPONSE_CONTRACT_INVALID,
            }
        ):
            raise MbomPublishContractError(
                "Uncertain MBOM truth requires reconciliation after possible target commit."
            )


def classify_adapter_fault(
    *,
    adapter_boundary_crossed: bool,
    timed_out: bool = False,
    http_status: int | None = None,
    response_contract_valid: bool = True,
    response_authenticated: bool = True,
) -> MbomFaultDecision:
    for value, path in (
        (adapter_boundary_crossed, "adapterBoundaryCrossed"),
        (timed_out, "timedOut"),
        (response_contract_valid, "responseContractValid"),
        (response_authenticated, "responseAuthenticated"),
    ):
        if type(value) is not bool:
            raise MbomPublishContractError(f"fault.{path} must be boolean.")
    if http_status is not None and (
        type(http_status) is not int or not 100 <= http_status <= 599
    ):
        raise MbomPublishContractError("fault.httpStatus is invalid.")
    if timed_out:
        if adapter_boundary_crossed:
            return MbomFaultDecision(
                MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
                MbomFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
                True,
                False,
            )
        return MbomFaultDecision(
            MbomPublishRequestState.FAILED_RETRYABLE,
            MbomFaultKind.TARGET_UNAVAILABLE,
            False,
            False,
        )
    if not response_contract_valid:
        return MbomFaultDecision(
            MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT if adapter_boundary_crossed else MbomPublishRequestState.FAILED_FINAL,
            MbomFaultKind.RESPONSE_CONTRACT_INVALID,
            adapter_boundary_crossed,
            False,
        )
    if not response_authenticated:
        return MbomFaultDecision(
            MbomPublishRequestState.FAILED_FINAL,
            MbomFaultKind.RESPONSE_AUTHENTICATION_INVALID,
            adapter_boundary_crossed,
            False,
        )
    if http_status == 429:
        return MbomFaultDecision(
            MbomPublishRequestState.FAILED_RETRYABLE,
            MbomFaultKind.RATE_LIMITED,
            False,
            False,
        )
    if http_status is None or 500 <= http_status <= 599:
        return MbomFaultDecision(
            MbomPublishRequestState.FAILED_RETRYABLE,
            (
                MbomFaultKind.TARGET_UNAVAILABLE
                if http_status is None
                else MbomFaultKind.TARGET_SERVER_ERROR
            ),
            adapter_boundary_crossed,
            False,
        )
    if 200 <= http_status <= 299:
        return MbomFaultDecision(
            MbomPublishRequestState.SUCCEEDED,
            MbomFaultKind.NONE,
            False,
            False,
        )
    if 300 <= http_status <= 399:
        return MbomFaultDecision(
            MbomPublishRequestState.FAILED_FINAL,
            MbomFaultKind.RESPONSE_CONTRACT_INVALID,
            adapter_boundary_crossed,
            False,
        )
    return MbomFaultDecision(
        MbomPublishRequestState.FAILED_FINAL,
        MbomFaultKind.BUSINESS_VALIDATION,
        False,
        False,
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _item_stream_key_hash(
    source: MbomSourceSnapshot,
    engineering_item_id: str,
) -> str:
    return canonical_hash(
        {
            "schemaVersion": 1,
            "tenantId": source.tenant_id,
            "projectGlobalId": str(source.project_global_id),
            "engineeringItemId": engineering_item_id,
        }
    )


def _require_acyclic(lines: Sequence[MbomSourceLine]) -> None:
    parents = {line.stable_line_key: line.parent_line_key for line in lines}
    for start in parents:
        seen: set[str] = set()
        current: str | None = start
        while current is not None:
            if current in seen:
                raise MbomPublishContractError("source topology must be acyclic.")
            seen.add(current)
            current = parents[current]


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID):
        raise MbomPublishContractError(f"{label} must be a canonical UUID.")
    return value


def _text(value: object, label: str, maximum: int, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise MbomPublishContractError(f"{label} is invalid.")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise MbomPublishContractError(f"{label} is invalid.")
    return value


def _optional_text(value: object, label: str, maximum: int, pattern: re.Pattern[str] | None = None) -> str | None:
    if value is None:
        return None
    return _text(value, label, maximum, pattern)


def _hash(value: object, label: str) -> str:
    return _text(value, label, 64, _HASH_PATTERN)


def _optional_hash(value: object, label: str) -> str | None:
    return None if value is None else _hash(value, label)


def _tenant(value: object, label: str) -> str:
    return _text(value, label, 128, _TENANT_PATTERN)


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise MbomPublishContractError(f"{label} must be a positive integer.")
    return value


def _nonnegative(value: object, label: str) -> int:
    if type(value) is not int or value < 0 or value > 2_147_483_647:
        raise MbomPublishContractError(f"{label} must be a non-negative integer.")
    return value


def _quantity(value: object, label: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise MbomPublishContractError(f"{label} is invalid.")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise MbomPublishContractError(f"{label} is invalid.") from error
    if not parsed.is_finite() or parsed <= 0 or parsed > Decimal("999999999999.999999"):
        raise MbomPublishContractError(f"{label} is invalid.")
    normalized = format(parsed.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _unique_texts(values: object, label: str, *, maximum: int) -> tuple[str, ...]:
    if type(values) is not tuple or len(values) > maximum:
        raise MbomPublishContractError(f"{label} is invalid.")
    normalized = tuple(_text(value, label, 128, _CODE_PATTERN) for value in values)
    if len(set(normalized)) != len(normalized):
        raise MbomPublishContractError(f"{label} contains duplicates.")
    return tuple(sorted(normalized))


def _pairs(values: object, label: str) -> tuple[tuple[str, str], ...]:
    if type(values) is not tuple or len(values) > 50:
        raise MbomPublishContractError(f"{label} is invalid.")
    normalized: list[tuple[str, str]] = []
    for pair in values:
        if type(pair) is not tuple or len(pair) != 2:
            raise MbomPublishContractError(f"{label} must contain key/value pairs.")
        normalized.append((_text(pair[0], label, 80, _CODE_PATTERN), _text(pair[1], label, 280)))
    if len({key for key, _ in normalized}) != len(normalized):
        raise MbomPublishContractError(f"{label} contains duplicate keys.")
    return tuple(sorted(normalized))


def _unique_uuids(values: object, label: str, *, maximum: int) -> tuple[UUID, ...]:
    if type(values) is not tuple or not values or len(values) > maximum:
        raise MbomPublishContractError(f"{label} is invalid.")
    normalized = tuple(_uuid(value, label) for value in values)
    if len(set(normalized)) != len(normalized):
        raise MbomPublishContractError(f"{label} contains duplicates.")
    return tuple(sorted(normalized, key=str))


def _aware_utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MbomPublishContractError(f"{label} must be timezone-aware.")
    return value.astimezone(UTC).replace(microsecond=0)


def _utc_text(value: datetime) -> str:
    return _aware_utc(value, "datetime").isoformat().replace("+00:00", "Z")
