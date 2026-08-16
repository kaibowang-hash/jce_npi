from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4


ITEM_PUBLISH_SCHEMA_VERSION = 1
ITEM_PUBLISH_API_VERSION = "npi.erp-item-publish.v1"
ITEM_PUBLISH_OPERATION = "publish_released_item"
ITEM_REQUEST_EVENT_TYPE = "npi.item_publish_request.ready"
ITEM_RESULT_EVENT_TYPE = "erpnext.item_publish_result.observed"
MAX_ITEM_OCCURRENCES = 500

_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_ENGINEERING_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_UOM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,15}$")


class ItemPublishContractError(ValueError):
    """Raised when an Item execution value is not exactly contract-shaped."""


class ItemTargetMode(StrEnum):
    MOCK = "mock"
    SYNTHETIC = "synthetic"
    SANDBOX = "sandbox"


class ItemPublishIntent(StrEnum):
    CREATE_ITEM = "create_item"
    UPDATE_ITEM_ENGINEERING_FIELDS = "update_item_engineering_fields"


class ItemPublishRequestState(StrEnum):
    VALIDATED_MOCK = "validated_mock"
    QUEUED = "queued"
    PROCESSING = "processing"
    SYNTHETIC_VERIFIED = "synthetic_verified"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    UNCERTAIN_AFTER_TIMEOUT = "uncertain_after_timeout"
    MAPPING_CONFLICT = "mapping_conflict"


class ItemPublishAttemptState(StrEnum):
    STARTED = "started"
    SYNTHETIC_VERIFIED = "synthetic_verified"
    OBSERVED_SUCCESS = "observed_success"
    OBSERVED_FAILURE = "observed_failure"
    UNCERTAIN = "uncertain"


class ItemPublishResultState(StrEnum):
    SYNTHETIC_VERIFIED = "synthetic_verified"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    UNCERTAIN_AFTER_TIMEOUT = "uncertain_after_timeout"


class ItemResultAuthority(StrEnum):
    NONE = "none"
    SYNTHETIC = "synthetic"
    AUTHORITATIVE_SANDBOX = "authoritative_sandbox"


class ItemFaultKind(StrEnum):
    NONE = "none"
    PAYLOAD_CONFLICT = "payload_conflict"
    SOURCE_ENGINEERING_ITEM_CONFLICT = "source_engineering_item_conflict"
    STALE_MAPPING = "stale_mapping"
    TIMEOUT_AFTER_POSSIBLE_COMMIT = "timeout_after_possible_commit"
    RATE_LIMITED = "rate_limited"
    TARGET_SERVER_ERROR = "target_server_error"
    BUSINESS_VALIDATION = "business_validation"
    RESPONSE_CONTRACT_INVALID = "response_contract_invalid"
    RESPONSE_AUTHENTICATION_INVALID = "response_authentication_invalid"
    TARGET_UNAVAILABLE = "target_unavailable"


class ItemRetryDirective(StrEnum):
    NONE = "none"
    REPLAY_SEALED_RESPONSE = "replay_sealed_response"
    REJECT_CONFLICT = "reject_conflict"
    RECONCILE_BEFORE_RETRY = "reconcile_before_retry"
    RETRY_AFTER = "retry_after"
    RETRY_SAME_IDEMPOTENCY = "retry_same_idempotency"
    MANUAL_CORRECTION = "manual_correction"


class ItemMappingDisposition(StrEnum):
    ADVANCE = "advance"
    NON_AUTHORITATIVE = "non_authoritative"
    EXPECTATION_CONFLICT = "expectation_conflict"
    TARGET_IDENTITY_CONFLICT = "target_identity_conflict"
    RESULT_NOT_SUCCESS = "result_not_success"


@dataclass(frozen=True, slots=True)
class ItemOccurrence:
    publish_node_global_id: UUID
    line_global_id: UUID
    engineering_item_id: str
    description: str
    engineering_uom: str
    attributes: tuple[tuple[str, str], ...]
    line_hash: str
    node_input_hash: str

    def __post_init__(self) -> None:
        for fieldname in ("publish_node_global_id", "line_global_id"):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"occurrence.{fieldname}"),
            )
        object.__setattr__(
            self,
            "engineering_item_id",
            _text(
                self.engineering_item_id,
                "occurrence.engineeringItemId",
                128,
                _ENGINEERING_ID_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "description",
            _text(self.description, "occurrence.description", 280),
        )
        object.__setattr__(
            self,
            "engineering_uom",
            _text(self.engineering_uom, "occurrence.engineeringUom", 16, _UOM_PATTERN),
        )
        object.__setattr__(
            self,
            "attributes",
            _attributes(self.attributes, "occurrence.attributes"),
        )
        for fieldname in ("line_hash", "node_input_hash"):
            object.__setattr__(
                self,
                fieldname,
                _hash(getattr(self, fieldname), f"occurrence.{fieldname}"),
            )

    @property
    def item_master_tuple(self) -> tuple[object, ...]:
        return (self.description, self.engineering_uom, self.attributes)

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "publishNodeGlobalId": str(self.publish_node_global_id),
            "lineGlobalId": str(self.line_global_id),
            "engineeringItemId": self.engineering_item_id,
            "description": self.description,
            "engineeringUom": self.engineering_uom,
            "attributes": dict(self.attributes),
            "lineHash": self.line_hash,
            "nodeInputHash": self.node_input_hash,
        }


@dataclass(frozen=True, slots=True)
class ReleasedItemSourceEvidence:
    publish_request_global_id: UUID
    publish_request_payload_hash: str
    publish_policy_global_id: UUID
    publish_policy_version: int
    publish_policy_snapshot_hash: str
    ebom_global_id: UUID
    ebom_version: int
    revision_global_id: UUID
    revision_number: int
    revision_snapshot_hash: str
    lifecycle_version: int
    release_event_global_id: UUID
    release_event_hash: str
    approval_evidence_ids: tuple[UUID, ...]
    released_at: datetime

    def __post_init__(self) -> None:
        for fieldname in (
            "publish_request_global_id",
            "publish_policy_global_id",
            "ebom_global_id",
            "revision_global_id",
            "release_event_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"releasedSource.{fieldname}"),
            )
        for fieldname in (
            "publish_policy_version",
            "ebom_version",
            "revision_number",
            "lifecycle_version",
        ):
            object.__setattr__(
                self,
                fieldname,
                _positive(getattr(self, fieldname), f"releasedSource.{fieldname}"),
            )
        for fieldname in (
            "publish_request_payload_hash",
            "publish_policy_snapshot_hash",
            "revision_snapshot_hash",
            "release_event_hash",
        ):
            object.__setattr__(
                self,
                fieldname,
                _hash(getattr(self, fieldname), f"releasedSource.{fieldname}"),
            )
        evidence = _unique_uuids(
            self.approval_evidence_ids,
            "releasedSource.approvalEvidenceIds",
            maximum=32,
        )
        if self.release_event_global_id not in evidence:
            raise ItemPublishContractError(
                "releasedSource.approvalEvidenceIds must include the release event."
            )
        object.__setattr__(self, "approval_evidence_ids", evidence)
        object.__setattr__(
            self,
            "released_at",
            _aware_utc(self.released_at, "releasedSource.releasedAt"),
        )

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "publishRequestGlobalId": str(self.publish_request_global_id),
            "publishRequestPayloadHash": self.publish_request_payload_hash,
            "publishPolicyGlobalId": str(self.publish_policy_global_id),
            "publishPolicyVersion": self.publish_policy_version,
            "publishPolicySnapshotHash": self.publish_policy_snapshot_hash,
            "ebomGlobalId": str(self.ebom_global_id),
            "ebomVersion": self.ebom_version,
            "revisionGlobalId": str(self.revision_global_id),
            "revisionNumber": self.revision_number,
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "lifecycleVersion": self.lifecycle_version,
            "releaseEventGlobalId": str(self.release_event_global_id),
            "releaseEventHash": self.release_event_hash,
            "approvalEvidenceIds": [str(value) for value in self.approval_evidence_ids],
            "releasedAt": _utc_text(self.released_at),
        }


@dataclass(frozen=True, slots=True)
class ItemSourceSnapshot:
    tenant_id: str
    project_global_id: UUID
    engineering_item_id: str
    selected_publish_node_global_id: UUID
    description: str
    engineering_uom: str
    attributes: tuple[tuple[str, str], ...]
    occurrences: tuple[ItemOccurrence, ...]
    stream_key_hash: str = ""
    source_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _tenant(self.tenant_id, "source.tenantId"))
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "source.projectGlobalId"),
        )
        object.__setattr__(
            self,
            "selected_publish_node_global_id",
            _uuid(
                self.selected_publish_node_global_id,
                "source.selectedPublishNodeGlobalId",
            ),
        )
        object.__setattr__(
            self,
            "engineering_item_id",
            _text(
                self.engineering_item_id,
                "source.engineeringItemId",
                128,
                _ENGINEERING_ID_PATTERN,
            ),
        )
        object.__setattr__(self, "description", _text(self.description, "source.description", 280))
        object.__setattr__(
            self,
            "engineering_uom",
            _text(self.engineering_uom, "source.engineeringUom", 16, _UOM_PATTERN),
        )
        object.__setattr__(self, "attributes", _attributes(self.attributes, "source.attributes"))
        raw_occurrences = tuple(self.occurrences)
        if not raw_occurrences or len(raw_occurrences) > MAX_ITEM_OCCURRENCES:
            raise ItemPublishContractError("source.occurrences is outside the supported boundary.")
        if not all(isinstance(value, ItemOccurrence) for value in raw_occurrences):
            raise ItemPublishContractError("source.occurrences is invalid.")
        occurrences = tuple(
            sorted(
                raw_occurrences,
                key=lambda value: str(value.publish_node_global_id),
            )
        )
        if len({value.publish_node_global_id for value in occurrences}) != len(occurrences):
            raise ItemPublishContractError("source publish-node identities must be unique.")
        if len({value.line_global_id for value in occurrences}) != len(occurrences):
            raise ItemPublishContractError("source line identities must be unique.")
        if self.selected_publish_node_global_id not in {
            value.publish_node_global_id for value in occurrences
        }:
            raise ItemPublishContractError("source selected node is not an exact occurrence.")
        if any(value.engineering_item_id != self.engineering_item_id for value in occurrences):
            raise ItemPublishContractError("source occurrences must use one exact engineering identity.")
        expected_item_fields = (self.description, self.engineering_uom, self.attributes)
        if any(value.item_master_tuple != expected_item_fields for value in occurrences):
            raise ItemPublishContractError("source occurrences contain divergent Item-master fields.")
        object.__setattr__(self, "occurrences", occurrences)
        stream_key = canonical_hash(
            {
                "schemaVersion": ITEM_PUBLISH_SCHEMA_VERSION,
                "tenantId": self.tenant_id,
                "projectGlobalId": str(self.project_global_id),
                "engineeringItemId": self.engineering_item_id,
            }
        )
        if self.stream_key_hash and _hash(self.stream_key_hash, "source.streamKeyHash") != stream_key:
            raise ItemPublishContractError("source stream key hash does not match its identity.")
        object.__setattr__(self, "stream_key_hash", stream_key)
        expected_source_hash = canonical_hash(self.source_payload())
        if self.source_hash and _hash(self.source_hash, "source.sourceHash") != expected_source_hash:
            raise ItemPublishContractError("source hash does not match its exact occurrences.")
        object.__setattr__(self, "source_hash", expected_source_hash)

    def source_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": ITEM_PUBLISH_SCHEMA_VERSION,
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "engineeringItemId": self.engineering_item_id,
            "selectedPublishNodeGlobalId": str(self.selected_publish_node_global_id),
            "itemMaster": {
                "description": self.description,
                "engineeringUom": self.engineering_uom,
                "attributes": dict(self.attributes),
            },
            "occurrences": [value.canonical_mapping() for value in self.occurrences],
        }

    def canonical_mapping(self) -> dict[str, object]:
        return {
            **self.source_payload(),
            "streamKeyHash": self.stream_key_hash,
            "sourceHash": self.source_hash,
        }


def group_item_source(
    *,
    tenant_id: str,
    project_global_id: UUID,
    selected_publish_node_global_id: UUID,
    occurrences: Sequence[ItemOccurrence],
) -> ItemSourceSnapshot:
    exact_occurrences = tuple(occurrences)
    if not exact_occurrences or not all(
        isinstance(value, ItemOccurrence) for value in exact_occurrences
    ):
        raise ItemPublishContractError("Item source occurrences are invalid.")
    selected_id = _uuid(selected_publish_node_global_id, "selectedPublishNodeGlobalId")
    selected = [value for value in exact_occurrences if value.publish_node_global_id == selected_id]
    if len(selected) != 1:
        raise ItemPublishContractError("The selected publish node is unavailable or ambiguous.")
    chosen = selected[0]
    grouped = tuple(
        value for value in exact_occurrences if value.engineering_item_id == chosen.engineering_item_id
    )
    if any(value.item_master_tuple != chosen.item_master_tuple for value in grouped):
        raise ItemPublishContractError("Repeated engineering identity has conflicting Item-master fields.")
    return ItemSourceSnapshot(
        tenant_id=tenant_id,
        project_global_id=project_global_id,
        engineering_item_id=chosen.engineering_item_id,
        selected_publish_node_global_id=selected_id,
        description=chosen.description,
        engineering_uom=chosen.engineering_uom,
        attributes=chosen.attributes,
        occurrences=grouped,
    )


@dataclass(frozen=True, slots=True)
class ItemMappingExpectation:
    mapping_version: int
    formal_item_code: str | None = None
    target_version: str | None = None
    observation_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mapping_version",
            _nonnegative(self.mapping_version, "mappingExpectation.mappingVersion"),
        )
        formal = _optional_text(self.formal_item_code, "mappingExpectation.formalItemCode", 140, _CODE_PATTERN)
        target = _optional_text(self.target_version, "mappingExpectation.targetVersion", 140)
        observation = _optional_hash(self.observation_hash, "mappingExpectation.observationHash")
        object.__setattr__(self, "formal_item_code", formal)
        object.__setattr__(self, "target_version", target)
        object.__setattr__(self, "observation_hash", observation)
        if self.mapping_version == 0 and any((formal, target, observation)):
            raise ItemPublishContractError("An unmapped create cannot contain target identity or version.")
        if self.mapping_version > 0 and not all((formal, target, observation)):
            raise ItemPublishContractError("A mapped update requires exact target and observation truth.")

    @property
    def intent(self) -> ItemPublishIntent:
        return (
            ItemPublishIntent.CREATE_ITEM
            if self.mapping_version == 0
            else ItemPublishIntent.UPDATE_ITEM_ENGINEERING_FIELDS
        )

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "mappingVersion": self.mapping_version,
            "formalItemCode": self.formal_item_code,
            "targetVersion": self.target_version,
            "observationHash": self.observation_hash,
        }


@dataclass(frozen=True, slots=True)
class ItemExecutionProfileReference:
    profile_id: str
    profile_version: int
    target_mode: ItemTargetMode
    environment_code: str
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _text(self.profile_id, "profile.id", 128, _CODE_PATTERN))
        object.__setattr__(self, "profile_version", _positive(self.profile_version, "profile.version"))
        if not isinstance(self.target_mode, ItemTargetMode):
            raise ItemPublishContractError("profile.targetMode is unsupported.")
        object.__setattr__(
            self,
            "environment_code",
            _text(self.environment_code, "profile.environmentCode", 64, _CODE_PATTERN),
        )
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "profile.snapshotHash"))

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "targetMode": self.target_mode.value,
            "environmentCode": self.environment_code,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ItemPublishRequest:
    global_id: UUID
    source: ItemSourceSnapshot
    released_evidence: ReleasedItemSourceEvidence
    profile: ItemExecutionProfileReference
    mapping_expectation: ItemMappingExpectation
    actor_user_id: str
    request_id: UUID
    trace_id: str
    idempotency_key_hash: str
    state: ItemPublishRequestState
    created_at: datetime
    payload_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "request.globalId"))
        if not isinstance(self.source, ItemSourceSnapshot):
            raise ItemPublishContractError("request.source is invalid.")
        if not isinstance(self.released_evidence, ReleasedItemSourceEvidence):
            raise ItemPublishContractError("request.releasedEvidence is invalid.")
        if not isinstance(self.profile, ItemExecutionProfileReference):
            raise ItemPublishContractError("request.profile is invalid.")
        if not isinstance(self.mapping_expectation, ItemMappingExpectation):
            raise ItemPublishContractError("request.mappingExpectation is invalid.")
        object.__setattr__(
            self,
            "actor_user_id",
            _text(self.actor_user_id, "request.actorUserId", 254, _ACTOR_PATTERN),
        )
        object.__setattr__(self, "request_id", _uuid(self.request_id, "request.requestId"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "request.traceId", 128, _TRACE_PATTERN))
        object.__setattr__(
            self,
            "idempotency_key_hash",
            _hash(self.idempotency_key_hash, "request.idempotencyKeyHash"),
        )
        if not isinstance(self.state, ItemPublishRequestState):
            raise ItemPublishContractError("request.state is unsupported.")
        expected_state = (
            ItemPublishRequestState.VALIDATED_MOCK
            if self.profile.target_mode is ItemTargetMode.MOCK
            else ItemPublishRequestState.QUEUED
        )
        if self.state is not expected_state:
            raise ItemPublishContractError("request initial state does not match target mode.")
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "request.createdAt"))
        expected_hash = canonical_hash(self.payload())
        if self.payload_hash and _hash(self.payload_hash, "request.payloadHash") != expected_hash:
            raise ItemPublishContractError("request payload hash does not match the exact command.")
        object.__setattr__(self, "payload_hash", expected_hash)

    @property
    def dispatch_allowed(self) -> bool:
        return self.profile.target_mode is not ItemTargetMode.MOCK

    @property
    def intent(self) -> ItemPublishIntent:
        return self.mapping_expectation.intent

    def payload(self) -> dict[str, object]:
        return {
            "schemaVersion": ITEM_PUBLISH_SCHEMA_VERSION,
            "apiVersion": ITEM_PUBLISH_API_VERSION,
            "operation": ITEM_PUBLISH_OPERATION,
            "source": self.source.canonical_mapping(),
            "releasedEvidence": self.released_evidence.canonical_mapping(),
            "profile": self.profile.canonical_mapping(),
            "mappingExpectation": self.mapping_expectation.canonical_mapping(),
            "intent": self.intent.value,
        }

    def event_payload(self) -> dict[str, object]:
        if not self.dispatch_allowed:
            raise ItemPublishContractError("Mock requests cannot create an Outbox event.")
        return {
            "schema_version": ITEM_PUBLISH_SCHEMA_VERSION,
            "api_version": ITEM_PUBLISH_API_VERSION,
            "operation": ITEM_PUBLISH_OPERATION,
            "request_global_id": str(self.global_id),
            "request_payload_hash": self.payload_hash,
            "project_global_id": str(self.source.project_global_id),
            "source_stream_key_hash": self.source.stream_key_hash,
            "source_hash": self.source.source_hash,
            "intent": self.intent.value,
            "expected_mapping_version": self.mapping_expectation.mapping_version,
            "expected_target_version": self.mapping_expectation.target_version,
            "target_mode": self.profile.target_mode.value,
            "profile_id": self.profile.profile_id,
            "profile_version": self.profile.profile_version,
            "profile_snapshot_hash": self.profile.snapshot_hash,
            "idempotency_key_hash": self.idempotency_key_hash,
        }


def create_item_publish_request(
    *,
    source: ItemSourceSnapshot,
    released_evidence: ReleasedItemSourceEvidence,
    profile: ItemExecutionProfileReference,
    mapping_expectation: ItemMappingExpectation,
    actor_user_id: str,
    request_id: UUID,
    trace_id: str,
    idempotency_key_hash: str,
    global_id: UUID | None = None,
    created_at: datetime | None = None,
) -> ItemPublishRequest:
    return ItemPublishRequest(
        global_id=global_id or uuid4(),
        source=source,
        released_evidence=released_evidence,
        profile=profile,
        mapping_expectation=mapping_expectation,
        actor_user_id=actor_user_id,
        request_id=request_id,
        trace_id=trace_id,
        idempotency_key_hash=idempotency_key_hash,
        state=(
            ItemPublishRequestState.VALIDATED_MOCK
            if profile.target_mode is ItemTargetMode.MOCK
            else ItemPublishRequestState.QUEUED
        ),
        created_at=created_at or datetime.now(UTC),
    )


@dataclass(frozen=True, slots=True)
class ItemAdapterObservation:
    request_global_id: UUID
    attempt_global_id: UUID
    attempt_number: int
    idempotency_key_hash: str
    source_hash: str
    expected_target_version: str | None
    state: ItemPublishResultState
    authority: ItemResultAuthority
    response_authenticated: bool
    response_hash: str
    observed_at: datetime
    formal_item_code: str | None = None
    target_version: str | None = None
    fault_kind: ItemFaultKind = ItemFaultKind.NONE

    def __post_init__(self) -> None:
        for fieldname in ("request_global_id", "attempt_global_id"):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), f"result.{fieldname}"))
        object.__setattr__(self, "attempt_number", _positive(self.attempt_number, "result.attemptNumber"))
        object.__setattr__(self, "idempotency_key_hash", _hash(self.idempotency_key_hash, "result.idempotencyKeyHash"))
        object.__setattr__(self, "source_hash", _hash(self.source_hash, "result.sourceHash"))
        object.__setattr__(
            self,
            "expected_target_version",
            _optional_text(self.expected_target_version, "result.expectedTargetVersion", 140),
        )
        if not isinstance(self.state, ItemPublishResultState):
            raise ItemPublishContractError("result.state is unsupported.")
        if not isinstance(self.authority, ItemResultAuthority):
            raise ItemPublishContractError("result.authority is unsupported.")
        if type(self.response_authenticated) is not bool:
            raise ItemPublishContractError("result.responseAuthenticated must be boolean.")
        object.__setattr__(self, "response_hash", _hash(self.response_hash, "result.responseHash"))
        object.__setattr__(self, "observed_at", _aware_utc(self.observed_at, "result.observedAt"))
        formal = _optional_text(self.formal_item_code, "result.formalItemCode", 140, _CODE_PATTERN)
        target = _optional_text(self.target_version, "result.targetVersion", 140)
        object.__setattr__(self, "formal_item_code", formal)
        object.__setattr__(self, "target_version", target)
        if not isinstance(self.fault_kind, ItemFaultKind):
            raise ItemPublishContractError("result.faultKind is unsupported.")
        authoritative_success = (
            self.state is ItemPublishResultState.SUCCEEDED
            and self.authority is ItemResultAuthority.AUTHORITATIVE_SANDBOX
            and self.response_authenticated
        )
        if authoritative_success:
            if not formal or not target or self.fault_kind is not ItemFaultKind.NONE:
                raise ItemPublishContractError("An authoritative success requires exact target identity and version.")
        elif formal or target:
            raise ItemPublishContractError("A non-authoritative or failed result cannot contain formal target identity.")
        if self.state is ItemPublishResultState.SYNTHETIC_VERIFIED:
            if (
                self.authority is not ItemResultAuthority.SYNTHETIC
                or self.response_authenticated
                or self.fault_kind is not ItemFaultKind.NONE
            ):
                raise ItemPublishContractError("Synthetic proof must remain non-authoritative and unauthenticated.")
        elif self.authority is ItemResultAuthority.SYNTHETIC:
            raise ItemPublishContractError("Synthetic authority is valid only for synthetic proof.")
        if (
            self.authority is ItemResultAuthority.AUTHORITATIVE_SANDBOX
            and not self.response_authenticated
        ) or (
            self.authority is ItemResultAuthority.NONE
            and self.response_authenticated
        ):
            raise ItemPublishContractError("Result authority must match response authentication.")
        if self.state is ItemPublishResultState.SUCCEEDED and not authoritative_success:
            raise ItemPublishContractError("Target success requires an authenticated authoritative Sandbox result.")
        if self.state is ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT and self.fault_kind is not ItemFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT:
            raise ItemPublishContractError("An uncertain timeout requires the exact timeout fault.")
        if self.state in {
            ItemPublishResultState.FAILED_RETRYABLE,
            ItemPublishResultState.FAILED_FINAL,
            ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT,
        } and self.fault_kind is ItemFaultKind.NONE:
            raise ItemPublishContractError("A failed or uncertain result requires an exact fault.")

    @property
    def is_authoritative_success(self) -> bool:
        return (
            self.state is ItemPublishResultState.SUCCEEDED
            and self.authority is ItemResultAuthority.AUTHORITATIVE_SANDBOX
            and self.response_authenticated
        )


@dataclass(frozen=True, slots=True)
class CurrentItemMapping:
    mapping_version: int
    formal_item_code: str
    target_version: str
    observation_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mapping_version", _positive(self.mapping_version, "mapping.mappingVersion"))
        object.__setattr__(self, "formal_item_code", _text(self.formal_item_code, "mapping.formalItemCode", 140, _CODE_PATTERN))
        object.__setattr__(self, "target_version", _text(self.target_version, "mapping.targetVersion", 140))
        object.__setattr__(self, "observation_hash", _hash(self.observation_hash, "mapping.observationHash"))


def classify_mapping_observation(
    *,
    expectation: ItemMappingExpectation,
    current: CurrentItemMapping | None,
    observation: ItemAdapterObservation,
) -> ItemMappingDisposition:
    if not observation.is_authoritative_success:
        return (
            ItemMappingDisposition.RESULT_NOT_SUCCESS
            if observation.state is not ItemPublishResultState.SYNTHETIC_VERIFIED
            else ItemMappingDisposition.NON_AUTHORITATIVE
        )
    current_version = 0 if current is None else current.mapping_version
    if current_version != expectation.mapping_version:
        return ItemMappingDisposition.EXPECTATION_CONFLICT
    if current is None:
        if expectation.formal_item_code is not None or expectation.target_version is not None:
            return ItemMappingDisposition.EXPECTATION_CONFLICT
        return ItemMappingDisposition.ADVANCE
    if (
        current.formal_item_code != expectation.formal_item_code
        or current.target_version != expectation.target_version
        or current.observation_hash != expectation.observation_hash
    ):
        return ItemMappingDisposition.EXPECTATION_CONFLICT
    if observation.formal_item_code != current.formal_item_code:
        return ItemMappingDisposition.TARGET_IDENTITY_CONFLICT
    return ItemMappingDisposition.ADVANCE


@dataclass(frozen=True, slots=True)
class ItemFaultClassification:
    request_state: ItemPublishRequestState
    fault_kind: ItemFaultKind
    retry_directive: ItemRetryDirective
    retryable: bool
    reconciliation_required: bool
    redispatch_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.request_state, ItemPublishRequestState):
            raise ItemPublishContractError("fault.requestState is unsupported.")
        if not isinstance(self.fault_kind, ItemFaultKind):
            raise ItemPublishContractError("fault.kind is unsupported.")
        if not isinstance(self.retry_directive, ItemRetryDirective):
            raise ItemPublishContractError("fault.retryDirective is unsupported.")
        for fieldname in ("retryable", "reconciliation_required", "redispatch_allowed"):
            if type(getattr(self, fieldname)) is not bool:
                raise ItemPublishContractError(f"fault.{fieldname} must be boolean.")
        if self.redispatch_allowed:
            raise ItemPublishContractError("P8-03 never authorizes redispatch.")


def classify_adapter_fault(
    *,
    adapter_boundary_crossed: bool,
    timed_out: bool = False,
    http_status: int | None = None,
    business_validation_failed: bool = False,
    response_contract_valid: bool = True,
    response_authenticated: bool = True,
) -> ItemFaultClassification:
    for value, path in (
        (adapter_boundary_crossed, "adapterBoundaryCrossed"),
        (timed_out, "timedOut"),
        (business_validation_failed, "businessValidationFailed"),
        (response_contract_valid, "responseContractValid"),
        (response_authenticated, "responseAuthenticated"),
    ):
        if type(value) is not bool:
            raise ItemPublishContractError(f"fault.{path} must be boolean.")
    if http_status is not None and (type(http_status) is not int or not 100 <= http_status <= 599):
        raise ItemPublishContractError("fault.httpStatus is invalid.")
    if timed_out:
        if adapter_boundary_crossed:
            return ItemFaultClassification(
                ItemPublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
                ItemFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
                ItemRetryDirective.RECONCILE_BEFORE_RETRY,
                False,
                True,
            )
        return ItemFaultClassification(
            ItemPublishRequestState.FAILED_RETRYABLE,
            ItemFaultKind.TARGET_UNAVAILABLE,
            ItemRetryDirective.RETRY_SAME_IDEMPOTENCY,
            True,
            False,
        )
    if not response_authenticated:
        return ItemFaultClassification(
            ItemPublishRequestState.FAILED_FINAL,
            ItemFaultKind.RESPONSE_AUTHENTICATION_INVALID,
            ItemRetryDirective.MANUAL_CORRECTION,
            False,
            adapter_boundary_crossed,
        )
    if not response_contract_valid:
        return ItemFaultClassification(
            ItemPublishRequestState.FAILED_FINAL,
            ItemFaultKind.RESPONSE_CONTRACT_INVALID,
            ItemRetryDirective.MANUAL_CORRECTION,
            False,
            adapter_boundary_crossed,
        )
    if business_validation_failed or (http_status is not None and 400 <= http_status < 500 and http_status != 429):
        return ItemFaultClassification(
            ItemPublishRequestState.FAILED_FINAL,
            ItemFaultKind.BUSINESS_VALIDATION,
            ItemRetryDirective.MANUAL_CORRECTION,
            False,
            False,
        )
    if http_status == 429:
        return ItemFaultClassification(
            ItemPublishRequestState.FAILED_RETRYABLE,
            ItemFaultKind.RATE_LIMITED,
            ItemRetryDirective.RETRY_AFTER,
            True,
            False,
        )
    if http_status is None or http_status >= 500:
        return ItemFaultClassification(
            ItemPublishRequestState.FAILED_RETRYABLE,
            ItemFaultKind.TARGET_SERVER_ERROR,
            ItemRetryDirective.RETRY_SAME_IDEMPOTENCY,
            True,
            False,
        )
    if 200 <= http_status < 300:
        return ItemFaultClassification(
            ItemPublishRequestState.SUCCEEDED,
            ItemFaultKind.NONE,
            ItemRetryDirective.NONE,
            False,
            False,
        )
    return ItemFaultClassification(
        ItemPublishRequestState.FAILED_FINAL,
        ItemFaultKind.RESPONSE_CONTRACT_INVALID,
        ItemRetryDirective.MANUAL_CORRECTION,
        False,
        adapter_boundary_crossed,
    )


@dataclass(frozen=True, slots=True)
class ItemClaimLease:
    token: UUID
    claimed_at: datetime
    expires_at: datetime
    attempt_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "token", _uuid(self.token, "claim.token"))
        claimed = _aware_utc(self.claimed_at, "claim.claimedAt")
        expires = _aware_utc(self.expires_at, "claim.expiresAt")
        if expires <= claimed:
            raise ItemPublishContractError("claim expiry must follow claim time.")
        object.__setattr__(self, "claimed_at", claimed)
        object.__setattr__(self, "expires_at", expires)
        object.__setattr__(self, "attempt_count", _positive(self.attempt_count, "claim.attemptCount"))

    def is_live(self, now: datetime) -> bool:
        return _aware_utc(now, "now") < self.expires_at


def issue_item_claim(
    *,
    now: datetime,
    lease_seconds: int,
    previous_attempt_count: int,
    token: UUID | None = None,
) -> ItemClaimLease:
    claimed = _aware_utc(now, "now")
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3_600:
        raise ItemPublishContractError("leaseSeconds is invalid.")
    previous = _nonnegative(previous_attempt_count, "previousAttemptCount")
    return ItemClaimLease(
        token=token or uuid4(),
        claimed_at=claimed,
        expires_at=claimed + timedelta(seconds=lease_seconds),
        attempt_count=previous + 1,
    )


def canonical_hash(value: object) -> str:
    try:
        canonical = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError, UnicodeError) as error:
        raise ItemPublishContractError("Canonical Item payload is invalid.") from error
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _uuid(value: object, path: str) -> UUID:
    try:
        parsed = value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ItemPublishContractError(f"{path} must be a canonical UUID.") from error
    if str(parsed) != str(value):
        raise ItemPublishContractError(f"{path} must be a canonical UUID.")
    return parsed


def _text(
    value: object,
    path: str,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ItemPublishContractError(f"{path} is invalid.")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ItemPublishContractError(f"{path} is invalid.")
    return value


def _optional_text(
    value: object,
    path: str,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str | None:
    if value is None:
        return None
    return _text(value, path, maximum, pattern)


def _tenant(value: object, path: str) -> str:
    return _text(value, path, 128, _TENANT_PATTERN)


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise ItemPublishContractError(f"{path} must be a lowercase SHA-256 value.")
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise ItemPublishContractError(f"{path} must be a positive whole number.")
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ItemPublishContractError(f"{path} cannot be negative.")
    return value


def _aware_utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ItemPublishContractError(f"{path} must include a timezone.")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _attributes(value: object, path: str) -> tuple[tuple[str, str], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ItemPublishContractError(f"{path} must be an immutable pair sequence.")
    if not all(
        isinstance(pair, Sequence)
        and not isinstance(pair, (str, bytes))
        and len(pair) == 2
        for pair in value
    ):
        raise ItemPublishContractError(f"{path} must contain key/value pairs.")
    unsorted_pairs = tuple((pair[0], pair[1]) for pair in value)
    for key, item in unsorted_pairs:
        _text(key, f"{path}.key", 64, _CODE_PATTERN)
        _text(item, f"{path}.{key}", 280)
    pairs = tuple(sorted(unsorted_pairs))
    if len(pairs) > 50 or len({key for key, _ in pairs}) != len(pairs):
        raise ItemPublishContractError(f"{path} must contain no more than 50 unique keys.")
    return pairs


def _unique_uuids(value: object, path: str, *, maximum: int) -> tuple[UUID, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ItemPublishContractError(f"{path} must be an array.")
    parsed = tuple(_uuid(item, path) for item in value)
    if not parsed or len(parsed) > maximum or len(set(parsed)) != len(parsed):
        raise ItemPublishContractError(f"{path} must contain unique bounded UUIDs.")
    return parsed
