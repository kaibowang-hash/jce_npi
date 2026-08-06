from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from npi_core.foundation.errors import RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


PUBLISH_REQUEST_SCHEMA_VERSION = 1
PUBLISH_REQUEST_API_VERSION = "npi.erp-publish.v1"
PUBLISH_OPERATION = "publish_released_ebom_item_mbom"
MAX_PUBLISH_NODES = 500

_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_LINE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_UOM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,15}$")


def sha256_json(value: object) -> str:
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PublishTargetMode(StrEnum):
    MOCK = "mock"
    SANDBOX = "sandbox"


class PublishRequestState(StrEnum):
    VALIDATED = "validated"
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    UNCERTAIN_AFTER_TIMEOUT = "uncertain_after_timeout"
    MANUAL_INTERVENTION = "manual_intervention"


class PublishNodeOperation(StrEnum):
    CREATE_ITEM = "create_item"
    UPDATE_ITEM_ENGINEERING_FIELDS = "update_item_engineering_fields"
    CREATE_OR_UPDATE_MBOM = "create_or_update_mbom"


class PublishMappingState(StrEnum):
    UNMAPPED = "unmapped"
    CURRENT = "current"
    STALE = "stale"
    CONFLICT = "conflict"


class PublishNodeResultState(StrEnum):
    VALIDATED = "validated"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    UNCERTAIN_AFTER_TIMEOUT = "uncertain_after_timeout"
    BLOCKED_MAPPING = "blocked_mapping"
    TARGET_UNAVAILABLE = "target_unavailable"


class TargetFaultKind(StrEnum):
    DUPLICATE_REQUEST = "duplicate_request"
    PAYLOAD_CONFLICT = "payload_conflict"
    TIMEOUT_AFTER_POSSIBLE_COMMIT = "timeout_after_possible_commit"
    RATE_LIMITED = "rate_limited"
    TARGET_SERVER_ERROR = "target_server_error"
    BUSINESS_VALIDATION = "business_validation"
    PARTIAL_NODE_SUCCESS = "partial_node_success"
    STALE_MAPPING = "stale_mapping"
    TARGET_UNAVAILABLE = "target_unavailable"
    RESTART_REPLAY = "restart_replay"


class FutureRetryDirective(StrEnum):
    NONE = "none"
    REPLAY_SEALED_RESPONSE = "replay_sealed_response"
    REJECT_PAYLOAD_CONFLICT = "reject_payload_conflict"
    RECONCILE_BEFORE_RETRY = "reconcile_before_retry"
    RETRY_AFTER = "retry_after"
    RETRY_SAME_IDEMPOTENCY = "retry_same_idempotency"
    MANUAL_CORRECTION = "manual_correction"
    RETRY_FAILED_NODES_ONLY = "retry_failed_nodes_only"
    RESOLVE_MAPPING = "resolve_mapping"
    REPLAY_ORIGINAL_REQUEST = "replay_original_request"


@dataclass(frozen=True, slots=True)
class PublishPolicyReference:
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "policy.globalId"))
        object.__setattr__(self, "version", _positive(self.version, "policy.version"))
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "policy.snapshotHash"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ReleasedEbomEvidence:
    project_global_id: UUID
    ebom_global_id: UUID
    ebom_version: int
    revision_global_id: UUID
    revision_number: int
    revision_snapshot_hash: str
    lifecycle_version: int
    release_event_global_id: UUID
    release_event_hash: str
    ebom_policy_global_id: UUID
    ebom_policy_version: int
    ebom_policy_snapshot_hash: str
    approval_evidence_ids: tuple[UUID, ...]
    released_at: datetime

    def __post_init__(self) -> None:
        for fieldname in (
            "project_global_id",
            "ebom_global_id",
            "revision_global_id",
            "release_event_global_id",
            "ebom_policy_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"releasedEbom.{fieldname}"),
            )
        for fieldname in (
            "ebom_version",
            "revision_number",
            "lifecycle_version",
            "ebom_policy_version",
        ):
            object.__setattr__(
                self,
                fieldname,
                _positive(getattr(self, fieldname), f"releasedEbom.{fieldname}"),
            )
        for fieldname in (
            "revision_snapshot_hash",
            "release_event_hash",
            "ebom_policy_snapshot_hash",
        ):
            object.__setattr__(
                self,
                fieldname,
                _hash(getattr(self, fieldname), f"releasedEbom.{fieldname}"),
            )
        evidence = _unique_uuids(
            self.approval_evidence_ids,
            "releasedEbom.approvalEvidenceIds",
            maximum=32,
        )
        if self.release_event_global_id not in evidence:
            raise _field_problem(
                "releasedEbom.approvalEvidenceIds",
                _("Include the exact EBOM release event as approval evidence."),
            )
        object.__setattr__(self, "approval_evidence_ids", evidence)
        object.__setattr__(
            self,
            "released_at",
            _aware_utc(self.released_at, "releasedEbom.releasedAt"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "projectGlobalId": str(self.project_global_id),
            "ebomGlobalId": str(self.ebom_global_id),
            "ebomVersion": self.ebom_version,
            "revisionGlobalId": str(self.revision_global_id),
            "revisionNumber": self.revision_number,
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "lifecycleVersion": self.lifecycle_version,
            "releaseEventGlobalId": str(self.release_event_global_id),
            "releaseEventHash": self.release_event_hash,
            "ebomPolicyGlobalId": str(self.ebom_policy_global_id),
            "ebomPolicyVersion": self.ebom_policy_version,
            "ebomPolicySnapshotHash": self.ebom_policy_snapshot_hash,
            "approvalEvidenceIds": [str(value) for value in self.approval_evidence_ids],
            "releasedAt": _utc_text(self.released_at),
        }


@dataclass(frozen=True, slots=True)
class PublishLineInput:
    global_id: UUID
    line_key: str
    parent_line_key: str | None
    engineering_item_id: str
    description: str
    quantity: str
    engineering_uom: str
    alternate_for_line_key: str | None = None
    alternate_group_key: str | None = None
    effectivity_start: str | None = None
    effectivity_end: str | None = None
    attributes: tuple[tuple[str, str], ...] = ()
    line_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "line.globalId"))
        object.__setattr__(
            self,
            "line_key",
            _text(self.line_key, "line.lineKey", 64, _LINE_KEY_PATTERN),
        )
        for fieldname in (
            "parent_line_key",
            "alternate_for_line_key",
            "alternate_group_key",
        ):
            object.__setattr__(
                self,
                fieldname,
                _optional_text(
                    getattr(self, fieldname),
                    f"line.{fieldname}",
                    64,
                    _LINE_KEY_PATTERN,
                ),
            )
        object.__setattr__(
            self,
            "engineering_item_id",
            _text(
                self.engineering_item_id,
                "line.engineeringItemId",
                128,
                _KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "description",
            _text(self.description, "line.description", 280),
        )
        object.__setattr__(self, "quantity", _quantity(self.quantity, "line.quantity"))
        object.__setattr__(
            self,
            "engineering_uom",
            _text(self.engineering_uom, "line.engineeringUom", 16, _UOM_PATTERN),
        )
        for fieldname in ("effectivity_start", "effectivity_end"):
            object.__setattr__(
                self,
                fieldname,
                _optional_text(getattr(self, fieldname), f"line.{fieldname}", 10),
            )
        attributes = tuple(sorted(self.attributes))
        if len(attributes) > 50 or len({key for key, _value in attributes}) != len(attributes):
            raise _field_problem(
                "line.attributes",
                _("Use no more than 50 unique engineering attributes."),
            )
        for key, value in attributes:
            _text(key, "line.attributes.key", 64, _LINE_KEY_PATTERN)
            _text(value, f"line.attributes.{key}", 280)
        object.__setattr__(self, "attributes", attributes)
        expected = sha256_json(self.snapshot_payload())
        if self.line_hash and _hash(self.line_hash, "line.lineHash") != expected:
            raise _field_problem(
                "line.lineHash",
                _("The EBOM line hash does not match its exact content."),
            )
        object.__setattr__(self, "line_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "lineKey": self.line_key,
            "parentLineKey": self.parent_line_key,
            "engineeringItemId": self.engineering_item_id,
            "description": self.description,
            "quantity": self.quantity,
            "engineeringUom": self.engineering_uom,
            "alternateForLineKey": self.alternate_for_line_key,
            "alternateGroupKey": self.alternate_group_key,
            "effectivityStart": self.effectivity_start,
            "effectivityEnd": self.effectivity_end,
            "attributes": dict(self.attributes),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.snapshot_payload(), "lineHash": self.line_hash}


@dataclass(frozen=True, slots=True)
class MappingObservation:
    state: PublishMappingState = PublishMappingState.UNMAPPED
    version: int = 0
    formal_item_code: str | None = None
    formal_mbom_id: str | None = None
    target_version: str | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, PublishMappingState):
            raise _field_problem("mapping.state", _("Select a supported mapping state."))
        object.__setattr__(self, "version", _nonnegative(self.version, "mapping.version"))
        for fieldname in ("formal_item_code", "formal_mbom_id", "target_version"):
            object.__setattr__(
                self,
                fieldname,
                _optional_text(getattr(self, fieldname), f"mapping.{fieldname}", 140),
            )
        if self.state is PublishMappingState.UNMAPPED and any(
            (self.formal_item_code, self.formal_mbom_id, self.target_version)
        ):
            raise _field_problem(
                "mapping",
                _("An unmapped node cannot contain formal ERP identifiers."),
            )
        if self.state is PublishMappingState.CURRENT and not self.formal_item_code:
            raise _field_problem(
                "mapping.formalItemCode",
                _("A current mapping requires its formal Item identifier."),
            )
        if self.observed_at is not None:
            object.__setattr__(
                self,
                "observed_at",
                _aware_utc(self.observed_at, "mapping.observedAt"),
            )

    def canonical_dict(self, *, expose_target_identifiers: bool) -> dict[str, object]:
        return {
            "state": self.state.value,
            "version": self.version,
            "formalItemCode": self.formal_item_code if expose_target_identifiers else None,
            "formalMbomId": self.formal_mbom_id if expose_target_identifiers else None,
            "targetVersion": self.target_version if expose_target_identifiers else None,
            "observedAt": _utc_text(self.observed_at) if self.observed_at else None,
        }


@dataclass(frozen=True, slots=True)
class PublishNodeResult:
    global_id: UUID
    node_global_id: UUID
    node_input_hash: str
    attempt_number: int
    state: PublishNodeResultState
    fault_kind: TargetFaultKind | None
    future_retry_directive: FutureRetryDirective
    future_retryable: bool
    reconciliation_required: bool
    retry_after_required: bool
    occurred_at: datetime
    result_hash: str
    formal_item_code: str | None = None
    formal_mbom_id: str | None = None
    target_version: str | None = None
    phase5_dispatch_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "result.globalId"))
        object.__setattr__(
            self,
            "node_global_id",
            _uuid(self.node_global_id, "result.nodeGlobalId"),
        )
        object.__setattr__(
            self,
            "node_input_hash",
            _hash(self.node_input_hash, "result.nodeInputHash"),
        )
        object.__setattr__(
            self,
            "attempt_number",
            _nonnegative(self.attempt_number, "result.attemptNumber"),
        )
        if not isinstance(self.state, PublishNodeResultState):
            raise _field_problem("result.state", _("Select a supported node state."))
        if self.fault_kind is not None and not isinstance(self.fault_kind, TargetFaultKind):
            raise _field_problem("result.faultKind", _("Select a supported target fault."))
        if not isinstance(self.future_retry_directive, FutureRetryDirective):
            raise _field_problem(
                "result.futureRetryDirective",
                _("Select a supported future retry directive."),
            )
        if self.attempt_number != 0 or self.state not in {
            PublishNodeResultState.VALIDATED,
            PublishNodeResultState.BLOCKED_MAPPING,
        }:
            raise _field_problem(
                "result.state",
                _("Phase 5 node results can record Mock validation only."),
            )
        expected_fault = (
            None
            if self.state is PublishNodeResultState.VALIDATED
            else TargetFaultKind.STALE_MAPPING
        )
        expected_directive = (
            FutureRetryDirective.NONE
            if self.state is PublishNodeResultState.VALIDATED
            else FutureRetryDirective.RESOLVE_MAPPING
        )
        if (
            self.fault_kind is not expected_fault
            or self.future_retry_directive is not expected_directive
            or self.future_retryable
            or self.reconciliation_required
            is not (self.state is PublishNodeResultState.BLOCKED_MAPPING)
            or self.retry_after_required
            or self.phase5_dispatch_allowed
            or self.formal_item_code
            or self.formal_mbom_id
            or self.target_version
        ):
            raise _field_problem(
                "result",
                _("The Mock node result contains unsupported execution truth."),
            )
        object.__setattr__(
            self,
            "occurred_at",
            _aware_utc(self.occurred_at, "result.occurredAt"),
        )
        expected_hash = sha256_json(self.payload(expose_target_identifiers=True))
        if _hash(self.result_hash, "result.resultHash") != expected_hash:
            raise _field_problem(
                "result.resultHash",
                _("The node result hash does not match its exact content."),
            )

    def payload(self, *, expose_target_identifiers: bool) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "nodeGlobalId": str(self.node_global_id),
            "nodeInputHash": self.node_input_hash,
            "attemptNumber": self.attempt_number,
            "state": self.state.value,
            "faultKind": self.fault_kind.value if self.fault_kind else None,
            "futureRetryDirective": self.future_retry_directive.value,
            "futureRetryable": self.future_retryable,
            "reconciliationRequired": self.reconciliation_required,
            "retryAfterRequired": self.retry_after_required,
            "phase5DispatchAllowed": False,
            "formalItemCode": self.formal_item_code
            if expose_target_identifiers
            else None,
            "formalMbomId": self.formal_mbom_id
            if expose_target_identifiers
            else None,
            "targetVersion": self.target_version if expose_target_identifiers else None,
            "occurredAt": _utc_text(self.occurred_at),
        }

    def canonical_dict(self, *, expose_target_identifiers: bool) -> dict[str, object]:
        return {
            **self.payload(expose_target_identifiers=expose_target_identifiers),
            "resultHash": self.result_hash,
        }


@dataclass(frozen=True, slots=True)
class PublishRequestNode:
    global_id: UUID
    request_global_id: UUID
    line: PublishLineInput
    mapping: MappingObservation
    operations: tuple[PublishNodeOperation, ...]
    result_state: PublishNodeResultState
    input_hash: str
    results: tuple[PublishNodeResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "node.globalId"))
        object.__setattr__(
            self,
            "request_global_id",
            _uuid(self.request_global_id, "node.requestGlobalId"),
        )
        if not isinstance(self.line, PublishLineInput) or not isinstance(
            self.mapping, MappingObservation
        ):
            raise _field_problem("node", _("The publish node input is invalid."))
        if not isinstance(self.result_state, PublishNodeResultState):
            raise _field_problem("node.resultState", _("Select a supported node state."))
        expected_operations = _operations_for_mapping(self.mapping)
        if self.operations != expected_operations:
            raise _field_problem(
                "node.operations",
                _("The node operations do not match its exact mapping state."),
            )
        expected_state = (
            PublishNodeResultState.BLOCKED_MAPPING
            if self.mapping.state in {PublishMappingState.STALE, PublishMappingState.CONFLICT}
            else PublishNodeResultState.VALIDATED
        )
        if self.result_state is not expected_state:
            raise _field_problem(
                "node.resultState",
                _("The node result does not match its mapping validation."),
            )
        expected_hash = sha256_json(self.input_payload())
        if _hash(self.input_hash, "node.inputHash") != expected_hash:
            raise _field_problem(
                "node.inputHash",
                _("The publish node hash does not match its exact input."),
            )
        if len(self.results) != 1:
            raise _field_problem(
                "node.results",
                _("Phase 5 requires one exact Mock validation result per node."),
            )
        result = self.results[0]
        if (
            result.node_global_id != self.global_id
            or result.node_input_hash != self.input_hash
            or result.state is not self.result_state
        ):
            raise _field_problem(
                "node.results",
                _("The node result does not match its exact publish input."),
            )

    def input_payload(self) -> dict[str, object]:
        return {
            "line": self.line.canonical_dict(),
            "mapping": self.mapping.canonical_dict(expose_target_identifiers=True),
            "operations": [operation.value for operation in self.operations],
        }

    def canonical_dict(self, *, expose_target_identifiers: bool) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "line": self.line.canonical_dict(),
            "mapping": self.mapping.canonical_dict(
                expose_target_identifiers=expose_target_identifiers
            ),
            "operations": [operation.value for operation in self.operations],
            "resultState": self.result_state.value,
            "inputHash": self.input_hash,
            "results": [
                result.canonical_dict(
                    expose_target_identifiers=expose_target_identifiers
                )
                for result in self.results
            ],
        }


@dataclass(frozen=True, slots=True)
class PublishRequest:
    global_id: UUID
    policy: PublishPolicyReference
    evidence: ReleasedEbomEvidence
    target_mode: PublishTargetMode
    actor_user_id: str
    request_id: UUID
    trace_id: str
    idempotency_key_hash: str
    state: PublishRequestState
    nodes: tuple[PublishRequestNode, ...]
    payload_hash: str
    created_at: datetime
    dispatch_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "request.globalId"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "request.requestId"))
        if not isinstance(self.policy, PublishPolicyReference) or not isinstance(
            self.evidence, ReleasedEbomEvidence
        ):
            raise _field_problem("request", _("The publish request evidence is invalid."))
        if not isinstance(self.target_mode, PublishTargetMode):
            raise _field_problem("request.targetMode", _("Select a supported target mode."))
        if not isinstance(self.state, PublishRequestState):
            raise _field_problem("request.state", _("Select a supported request state."))
        object.__setattr__(
            self,
            "actor_user_id",
            _text(self.actor_user_id, "request.actorUserId", 254, _ACTOR_PATTERN),
        )
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
        if not self.nodes or len(self.nodes) > MAX_PUBLISH_NODES:
            raise _field_problem(
                "request.nodes",
                _("Include between 1 and 500 exact EBOM nodes."),
            )
        if len({node.global_id for node in self.nodes}) != len(self.nodes) or len(
            {node.line.global_id for node in self.nodes}
        ) != len(self.nodes):
            raise _field_problem(
                "request.nodes",
                _("Each publish request node and EBOM line must be unique."),
            )
        if any(node.request_global_id != self.global_id for node in self.nodes):
            raise _field_problem(
                "request.nodes",
                _("Each publish node must belong to the exact request."),
            )
        expected_state = _aggregate_state(self.nodes)
        if self.state is not expected_state:
            raise _field_problem(
                "request.state",
                _("The request state does not match its node validation results."),
            )
        if self.dispatch_allowed:
            raise _field_problem(
                "request.dispatchAllowed",
                _("ERP dispatch is unavailable in this Phase 5 boundary."),
            )
        if self.target_mode is PublishTargetMode.MOCK:
            if self.state is PublishRequestState.SUCCEEDED or any(
                node.result_state is PublishNodeResultState.SUCCEEDED for node in self.nodes
            ):
                raise _field_problem(
                    "request.state",
                    _("Mock validation cannot report ERP execution success."),
                )
        object.__setattr__(
            self,
            "created_at",
            _aware_utc(self.created_at, "request.createdAt"),
        )
        expected_hash = sha256_json(self.payload())
        if _hash(self.payload_hash, "request.payloadHash") != expected_hash:
            raise _field_problem(
                "request.payloadHash",
                _("The publish request hash does not match its exact input."),
            )

    def payload(self) -> dict[str, object]:
        return _request_payload(
            policy=self.policy,
            evidence=self.evidence,
            target_mode=self.target_mode,
            nodes=self.nodes,
        )

    def public_dict(self) -> dict[str, object]:
        expose_target_identifiers = self.target_mode is not PublishTargetMode.MOCK
        return {
            "globalId": str(self.global_id),
            "operation": PUBLISH_OPERATION,
            "apiVersion": PUBLISH_REQUEST_API_VERSION,
            "policy": self.policy.canonical_dict(),
            "releasedEbom": self.evidence.canonical_dict(),
            "targetMode": self.target_mode.value,
            "state": self.state.value,
            "dispatchAllowed": False,
            "actorUserId": self.actor_user_id,
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "payloadHash": self.payload_hash,
            "ownedFields": [
                "engineering_item_id",
                "engineering_description",
                "ebom_hierarchy",
                "engineering_quantity",
                "engineering_uom",
                "alternates",
                "effectivity",
                "engineering_attributes",
            ],
            "nodes": [
                node.canonical_dict(
                    expose_target_identifiers=expose_target_identifiers
                )
                for node in self.nodes
            ],
            "capabilities": {
                "view": True,
                "create": True,
                "dispatch": False,
                "retry": False,
                "reconcile": False,
            },
            "createdAt": _utc_text(self.created_at),
        }


@dataclass(frozen=True, slots=True)
class FaultClassification:
    kind: TargetFaultKind
    request_state: PublishRequestState
    affected_node_state: PublishNodeResultState | None
    future_retry_directive: FutureRetryDirective
    future_retryable: bool
    reconciliation_required: bool
    retry_after_required: bool
    phase5_dispatch_allowed: bool = False

    def __post_init__(self) -> None:
        if self.phase5_dispatch_allowed:
            raise _field_problem(
                "fault.phase5DispatchAllowed",
                _("Fault evidence cannot enable Phase 5 ERP dispatch."),
            )


def create_mock_publish_request(
    *,
    policy: PublishPolicyReference,
    evidence: ReleasedEbomEvidence,
    lines: Sequence[PublishLineInput],
    actor_user_id: str,
    request_id: UUID,
    trace_id: str,
    idempotency_key_hash: str,
    mappings: Mapping[UUID, MappingObservation] | None = None,
    global_id: UUID | None = None,
    created_at: datetime | None = None,
) -> PublishRequest:
    request_global_id = global_id or uuid4()
    exact_lines = tuple(lines)
    if not exact_lines or len(exact_lines) > MAX_PUBLISH_NODES:
        raise _field_problem(
            "lines",
            _("Include between 1 and 500 exact released EBOM lines."),
        )
    if len({line.global_id for line in exact_lines}) != len(exact_lines) or len(
        {line.line_key for line in exact_lines}
    ) != len(exact_lines):
        raise _field_problem(
            "lines",
            _("Each released EBOM line identity must be unique."),
        )
    observations = dict(mappings or {})
    if set(observations) - {line.global_id for line in exact_lines}:
        raise _field_problem(
            "mappings",
            _("A mapping observation does not belong to the exact EBOM revision."),
        )
    created = created_at or datetime.now(UTC)
    nodes: list[PublishRequestNode] = []
    for line in sorted(exact_lines, key=lambda value: value.line_key):
        mapping = observations.get(line.global_id, MappingObservation())
        operations = _operations_for_mapping(mapping)
        result_state = (
            PublishNodeResultState.BLOCKED_MAPPING
            if mapping.state in {PublishMappingState.STALE, PublishMappingState.CONFLICT}
            else PublishNodeResultState.VALIDATED
        )
        node_payload = {
            "line": line.canonical_dict(),
            "mapping": mapping.canonical_dict(expose_target_identifiers=True),
            "operations": [operation.value for operation in operations],
        }
        node_global_id = uuid4()
        node_input_hash = sha256_json(node_payload)
        result_state_fault = (
            None
            if result_state is PublishNodeResultState.VALIDATED
            else TargetFaultKind.STALE_MAPPING
        )
        result_directive = (
            FutureRetryDirective.NONE
            if result_state is PublishNodeResultState.VALIDATED
            else FutureRetryDirective.RESOLVE_MAPPING
        )
        result_global_id = uuid4()
        result_payload = {
            "globalId": str(result_global_id),
            "nodeGlobalId": str(node_global_id),
            "nodeInputHash": node_input_hash,
            "attemptNumber": 0,
            "state": result_state.value,
            "faultKind": result_state_fault.value if result_state_fault else None,
            "futureRetryDirective": result_directive.value,
            "futureRetryable": False,
            "reconciliationRequired": result_state
            is PublishNodeResultState.BLOCKED_MAPPING,
            "retryAfterRequired": False,
            "phase5DispatchAllowed": False,
            "formalItemCode": None,
            "formalMbomId": None,
            "targetVersion": None,
            "occurredAt": _utc_text(created),
        }
        result = PublishNodeResult(
            global_id=result_global_id,
            node_global_id=node_global_id,
            node_input_hash=node_input_hash,
            attempt_number=0,
            state=result_state,
            fault_kind=result_state_fault,
            future_retry_directive=result_directive,
            future_retryable=False,
            reconciliation_required=result_state
            is PublishNodeResultState.BLOCKED_MAPPING,
            retry_after_required=False,
            occurred_at=created,
            result_hash=sha256_json(result_payload),
        )
        nodes.append(
            PublishRequestNode(
                global_id=node_global_id,
                request_global_id=request_global_id,
                line=line,
                mapping=mapping,
                operations=operations,
                result_state=result_state,
                input_hash=node_input_hash,
                results=(result,),
            )
        )
    state = _aggregate_state(tuple(nodes))
    payload_hash = sha256_json(
        _request_payload(
            policy=policy,
            evidence=evidence,
            target_mode=PublishTargetMode.MOCK,
            nodes=tuple(nodes),
        )
    )
    return PublishRequest(
        global_id=request_global_id,
        policy=policy,
        evidence=evidence,
        target_mode=PublishTargetMode.MOCK,
        actor_user_id=actor_user_id,
        request_id=request_id,
        trace_id=trace_id,
        idempotency_key_hash=idempotency_key_hash,
        state=state,
        nodes=tuple(nodes),
        payload_hash=payload_hash,
        created_at=created,
    )


def classify_target_fault(kind: TargetFaultKind) -> FaultClassification:
    if not isinstance(kind, TargetFaultKind):
        raise _field_problem("fault.kind", _("Select a supported target fault."))
    values = {
        TargetFaultKind.DUPLICATE_REQUEST: (
            PublishRequestState.VALIDATED,
            None,
            FutureRetryDirective.REPLAY_SEALED_RESPONSE,
            False,
            False,
            False,
        ),
        TargetFaultKind.PAYLOAD_CONFLICT: (
            PublishRequestState.FAILED_FINAL,
            PublishNodeResultState.FAILED_FINAL,
            FutureRetryDirective.REJECT_PAYLOAD_CONFLICT,
            False,
            False,
            False,
        ),
        TargetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT: (
            PublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
            PublishNodeResultState.UNCERTAIN_AFTER_TIMEOUT,
            FutureRetryDirective.RECONCILE_BEFORE_RETRY,
            False,
            True,
            False,
        ),
        TargetFaultKind.RATE_LIMITED: (
            PublishRequestState.FAILED_RETRYABLE,
            PublishNodeResultState.FAILED_RETRYABLE,
            FutureRetryDirective.RETRY_AFTER,
            True,
            False,
            True,
        ),
        TargetFaultKind.TARGET_SERVER_ERROR: (
            PublishRequestState.FAILED_RETRYABLE,
            PublishNodeResultState.FAILED_RETRYABLE,
            FutureRetryDirective.RETRY_SAME_IDEMPOTENCY,
            True,
            False,
            False,
        ),
        TargetFaultKind.BUSINESS_VALIDATION: (
            PublishRequestState.FAILED_FINAL,
            PublishNodeResultState.FAILED_FINAL,
            FutureRetryDirective.MANUAL_CORRECTION,
            False,
            False,
            False,
        ),
        TargetFaultKind.PARTIAL_NODE_SUCCESS: (
            PublishRequestState.PARTIALLY_SUCCEEDED,
            PublishNodeResultState.FAILED_RETRYABLE,
            FutureRetryDirective.RETRY_FAILED_NODES_ONLY,
            True,
            False,
            False,
        ),
        TargetFaultKind.STALE_MAPPING: (
            PublishRequestState.MANUAL_INTERVENTION,
            PublishNodeResultState.BLOCKED_MAPPING,
            FutureRetryDirective.RESOLVE_MAPPING,
            False,
            True,
            False,
        ),
        TargetFaultKind.TARGET_UNAVAILABLE: (
            PublishRequestState.FAILED_RETRYABLE,
            PublishNodeResultState.TARGET_UNAVAILABLE,
            FutureRetryDirective.RETRY_SAME_IDEMPOTENCY,
            True,
            False,
            False,
        ),
        TargetFaultKind.RESTART_REPLAY: (
            PublishRequestState.VALIDATED,
            None,
            FutureRetryDirective.REPLAY_ORIGINAL_REQUEST,
            False,
            False,
            False,
        ),
    }
    state, node_state, directive, retryable, reconcile, retry_after = values[kind]
    return FaultClassification(
        kind=kind,
        request_state=state,
        affected_node_state=node_state,
        future_retry_directive=directive,
        future_retryable=retryable,
        reconciliation_required=reconcile,
        retry_after_required=retry_after,
    )


def _operations_for_mapping(
    mapping: MappingObservation,
) -> tuple[PublishNodeOperation, ...]:
    if mapping.state is PublishMappingState.UNMAPPED:
        return (
            PublishNodeOperation.CREATE_ITEM,
            PublishNodeOperation.CREATE_OR_UPDATE_MBOM,
        )
    if mapping.state is PublishMappingState.CURRENT:
        return (
            PublishNodeOperation.UPDATE_ITEM_ENGINEERING_FIELDS,
            PublishNodeOperation.CREATE_OR_UPDATE_MBOM,
        )
    return ()


def _aggregate_state(nodes: Sequence[PublishRequestNode]) -> PublishRequestState:
    if any(node.result_state is PublishNodeResultState.BLOCKED_MAPPING for node in nodes):
        return PublishRequestState.MANUAL_INTERVENTION
    return PublishRequestState.VALIDATED


def _request_payload(
    *,
    policy: PublishPolicyReference,
    evidence: ReleasedEbomEvidence,
    target_mode: PublishTargetMode,
    nodes: Sequence[PublishRequestNode],
) -> dict[str, object]:
    return {
        "schemaVersion": PUBLISH_REQUEST_SCHEMA_VERSION,
        "apiVersion": PUBLISH_REQUEST_API_VERSION,
        "operation": PUBLISH_OPERATION,
        "policy": policy.canonical_dict(),
        "releasedEbom": evidence.canonical_dict(),
        "targetMode": target_mode.value,
        "nodes": [node.input_payload() for node in nodes],
    }


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID):
        raise _field_problem(path, _("Use a valid UUID."))
    return value


def _positive(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _field_problem(path, _("Use a positive integer."))
    return value


def _nonnegative(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _field_problem(path, _("Use a non-negative integer."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Use a lowercase SHA-256 hash."))
    return value


def _text(
    value: object,
    path: str,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or (pattern is not None and pattern.fullmatch(value) is None)
    ):
        raise _field_problem(path, _("Use a valid value."))
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


def _quantity(value: object, path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None:
        raise _field_problem(path, _("Use a canonical positive quantity."))
    if value.startswith("0") and value not in {"0"} and not value.startswith("0."):
        raise _field_problem(path, _("Use a canonical positive quantity."))
    if value == "0" or value.startswith("0.") and set(value[2:]) <= {"0"}:
        raise _field_problem(path, _("Use a canonical positive quantity."))
    if "." in value and value.endswith("0"):
        raise _field_problem(path, _("Use a canonical positive quantity."))
    return value


def _unique_uuids(values: object, path: str, *, maximum: int) -> tuple[UUID, ...]:
    if not isinstance(values, tuple) or not values or len(values) > maximum:
        raise _field_problem(path, _("Include a bounded set of exact UUID values."))
    result = tuple(_uuid(value, path) for value in values)
    if len(set(result)) != len(result):
        raise _field_problem(path, _("Use each exact UUID only once."))
    return result


def _aware_utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _field_problem(path, _("Use an explicit UTC date and time."))
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
