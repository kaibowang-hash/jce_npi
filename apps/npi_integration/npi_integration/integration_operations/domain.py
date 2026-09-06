from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


INTEGRATION_OPERATIONS_SCHEMA_VERSION = 1
INTEGRATION_OPERATIONS_API_VERSION = "npi.integration-operations.v1"
INTEGRATION_ACTION_RECORDED_EVENT_TYPE = "npi.integration_action.recorded"
INTEGRATION_RECONCILIATION_OBSERVED_EVENT_TYPE = (
    "npi.integration_reconciliation.observed"
)

_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_FORBIDDEN_EVIDENCE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "rawbody",
        "rawpayload",
        "secret",
        "targetrequest",
        "targetresponse",
        "token",
    }
)


class IntegrationOperationsContractError(ValueError):
    """Raised when a P8-07 operation value is not exact and closed."""


class IntegrationOperationKind(StrEnum):
    RECEIVE_PROJECT_SUBMISSION = "receive_project_submission"
    PUBLISH_ITEM = "publish_item"
    PUBLISH_MBOM = "publish_mbom"
    CREATE_TOOL_ASSET = "create_tool_asset"
    UPDATE_TOOL_ASSET = "update_tool_asset"
    RECEIVE_ENGINEERING_CHANGE_EVENT = "receive_engineering_change_event"
    PUBLISH_CHANGE_IMPLEMENTATION_SUMMARY = (
        "publish_change_implementation_summary"
    )


class IntegrationActionKind(StrEnum):
    REPLAY = "replay"
    REQUEST_RECONCILIATION = "request_reconciliation"


class IntegrationActionOutcome(StrEnum):
    REPLAY_REQUESTED = "replay_requested"
    RECONCILIATION_REQUESTED = "reconciliation_requested"


class IntegrationViewState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    UNCERTAIN = "uncertain"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    QUARANTINED = "quarantined"
    UNAVAILABLE = "unavailable"


class IntegrationFaultClass(StrEnum):
    NONE = "none"
    RETRYABLE_BEFORE_UNCERTAIN_BOUNDARY = "retryable_before_uncertain_boundary"
    FINAL_BUSINESS_FAILURE = "final_business_failure"
    UNCERTAIN_AFTER_BOUNDARY = "uncertain_after_boundary"
    PARTIAL_RESULT = "partial_result"
    IDENTITY_CONFLICT = "identity_conflict"
    AUTHENTICITY_QUARANTINE = "authenticity_quarantine"
    TARGET_UNAVAILABLE = "target_unavailable"
    UNKNOWN_RAW_STATE = "unknown_raw_state"


class ReplayEligibilityReason(StrEnum):
    ELIGIBLE = "eligible"
    UNKNOWN_RAW_STATE = "unknown_raw_state"
    STATE_NOT_RETRYABLE = "state_not_retryable"
    UNCERTAIN_BOUNDARY = "uncertain_boundary"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    PARTIAL_RESULT = "partial_result"


class ReconciliationObservationState(StrEnum):
    CONFIRMED_SUCCEEDED = "confirmed_succeeded"
    CONFIRMED_FAILED = "confirmed_failed"
    STILL_UNCERTAIN = "still_uncertain"
    TARGET_UNAVAILABLE = "target_unavailable"


class ReconciliationObserverKind(StrEnum):
    TRUSTED_OPERATION_SERVICE = "trusted_operation_service"


class ReconciliationAuthority(StrEnum):
    NONE = "none"
    AUTHORITATIVE_SANDBOX = "authoritative_sandbox"


_OUTBOUND_STATES = {
    "validated_mock": IntegrationViewState.UNAVAILABLE,
    "queued": IntegrationViewState.QUEUED,
    "processing": IntegrationViewState.PROCESSING,
    "synthetic_verified": IntegrationViewState.UNAVAILABLE,
    "succeeded": IntegrationViewState.SUCCEEDED,
    "failed_retryable": IntegrationViewState.FAILED_RETRYABLE,
    "failed_final": IntegrationViewState.FAILED_FINAL,
    "uncertain_after_timeout": IntegrationViewState.UNCERTAIN,
    "mapping_conflict": IntegrationViewState.CONFLICT,
}
_RAW_STATE_MAP: dict[IntegrationOperationKind, dict[str, IntegrationViewState]] = {
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: {
        "pending": IntegrationViewState.QUEUED,
        "processing": IntegrationViewState.PROCESSING,
        "succeeded": IntegrationViewState.SUCCEEDED,
        "failed_retryable": IntegrationViewState.FAILED_RETRYABLE,
        "failed_final": IntegrationViewState.FAILED_FINAL,
        "quarantined": IntegrationViewState.QUARANTINED,
        "superseded": IntegrationViewState.CONFLICT,
        "received_after_creation": IntegrationViewState.SUCCEEDED,
    },
    IntegrationOperationKind.PUBLISH_ITEM: dict(_OUTBOUND_STATES),
    IntegrationOperationKind.PUBLISH_MBOM: {
        **_OUTBOUND_STATES,
        "partially_succeeded": IntegrationViewState.PARTIAL,
    },
    IntegrationOperationKind.CREATE_TOOL_ASSET: {
        **_OUTBOUND_STATES,
        "partially_succeeded": IntegrationViewState.PARTIAL,
    },
    IntegrationOperationKind.UPDATE_TOOL_ASSET: {
        **_OUTBOUND_STATES,
        "partially_succeeded": IntegrationViewState.PARTIAL,
    },
    IntegrationOperationKind.RECEIVE_ENGINEERING_CHANGE_EVENT: {
        "pending": IntegrationViewState.QUEUED,
        "processing": IntegrationViewState.PROCESSING,
        "succeeded": IntegrationViewState.SUCCEEDED,
        "failed_retryable": IntegrationViewState.FAILED_RETRYABLE,
        "failed_final": IntegrationViewState.FAILED_FINAL,
        "quarantined": IntegrationViewState.QUARANTINED,
        "superseded": IntegrationViewState.CONFLICT,
    },
    IntegrationOperationKind.PUBLISH_CHANGE_IMPLEMENTATION_SUMMARY: {
        **_OUTBOUND_STATES,
        "partially_succeeded": IntegrationViewState.PARTIAL,
        "identity_conflict": IntegrationViewState.CONFLICT,
    },
}
_DLQ_STATES = frozenset(
    {
        IntegrationViewState.FAILED_RETRYABLE,
        IntegrationViewState.FAILED_FINAL,
        IntegrationViewState.UNCERTAIN,
        IntegrationViewState.PARTIAL,
        IntegrationViewState.CONFLICT,
        IntegrationViewState.QUARANTINED,
    }
)
_FAULT_BY_STATE = {
    IntegrationViewState.QUEUED: IntegrationFaultClass.NONE,
    IntegrationViewState.PROCESSING: IntegrationFaultClass.NONE,
    IntegrationViewState.SUCCEEDED: IntegrationFaultClass.NONE,
    IntegrationViewState.FAILED_RETRYABLE: (
        IntegrationFaultClass.RETRYABLE_BEFORE_UNCERTAIN_BOUNDARY
    ),
    IntegrationViewState.FAILED_FINAL: IntegrationFaultClass.FINAL_BUSINESS_FAILURE,
    IntegrationViewState.UNCERTAIN: IntegrationFaultClass.UNCERTAIN_AFTER_BOUNDARY,
    IntegrationViewState.PARTIAL: IntegrationFaultClass.PARTIAL_RESULT,
    IntegrationViewState.CONFLICT: IntegrationFaultClass.IDENTITY_CONFLICT,
    IntegrationViewState.QUARANTINED: IntegrationFaultClass.AUTHENTICITY_QUARANTINE,
    IntegrationViewState.UNAVAILABLE: IntegrationFaultClass.TARGET_UNAVAILABLE,
}


@dataclass(frozen=True, slots=True)
class OperationStateClassification:
    operation_kind: IntegrationOperationKind
    raw_state: str
    shared_state: IntegrationViewState
    known_raw_state: bool

    def __post_init__(self) -> None:
        if not isinstance(self.operation_kind, IntegrationOperationKind):
            raise IntegrationOperationsContractError("operationKind is unsupported.")
        object.__setattr__(self, "raw_state", _code(self.raw_state, "rawState"))
        if not isinstance(self.shared_state, IntegrationViewState):
            raise IntegrationOperationsContractError("sharedState is unsupported.")
        expected = _RAW_STATE_MAP[self.operation_kind].get(self.raw_state)
        if self.known_raw_state != (expected is not None):
            raise IntegrationOperationsContractError(
                "Raw operation state knowledge does not match the closed inventory."
            )
        if expected is not None and self.shared_state is not expected:
            raise IntegrationOperationsContractError(
                "Raw operation state does not match its shared classification."
            )
        if expected is None and self.shared_state is not IntegrationViewState.UNAVAILABLE:
            raise IntegrationOperationsContractError(
                "Unknown raw operation state must fail closed as unavailable."
            )

    @property
    def logical_dlq(self) -> bool:
        return self.shared_state in _DLQ_STATES

    @property
    def fault_class(self) -> IntegrationFaultClass:
        if not self.known_raw_state:
            return IntegrationFaultClass.UNKNOWN_RAW_STATE
        return _FAULT_BY_STATE[self.shared_state]

    def payload(self) -> dict[str, object]:
        return {
            "operationKind": self.operation_kind.value,
            "rawState": self.raw_state,
            "sharedState": self.shared_state.value,
            "knownRawState": self.known_raw_state,
            "logicalDlq": self.logical_dlq,
            "faultClass": self.fault_class.value,
        }


def classify_operation_state(
    operation_kind: IntegrationOperationKind,
    raw_state: str,
) -> OperationStateClassification:
    if not isinstance(operation_kind, IntegrationOperationKind):
        raise IntegrationOperationsContractError("operationKind is unsupported.")
    normalized = _code(raw_state, "rawState")
    shared = _RAW_STATE_MAP[operation_kind].get(
        normalized,
        IntegrationViewState.UNAVAILABLE,
    )
    return OperationStateClassification(
        operation_kind=operation_kind,
        raw_state=normalized,
        shared_state=shared,
        known_raw_state=normalized in _RAW_STATE_MAP[operation_kind],
    )


@dataclass(frozen=True, slots=True)
class ReplayEligibility:
    eligible: bool
    reason: ReplayEligibilityReason

    def __post_init__(self) -> None:
        if not isinstance(self.reason, ReplayEligibilityReason):
            raise IntegrationOperationsContractError(
                "Replay eligibility reason is unsupported."
            )
        if self.eligible != (self.reason is ReplayEligibilityReason.ELIGIBLE):
            raise IntegrationOperationsContractError(
                "Replay eligibility and reason do not agree."
            )


def evaluate_replay_eligibility(
    classification: OperationStateClassification,
    *,
    uncertain_boundary: bool,
    reconciliation_required: bool,
    partial_result: bool,
) -> ReplayEligibility:
    if not isinstance(classification, OperationStateClassification):
        raise IntegrationOperationsContractError(
            "Replay classification is required."
        )
    if not classification.known_raw_state:
        reason = ReplayEligibilityReason.UNKNOWN_RAW_STATE
    elif classification.shared_state is not IntegrationViewState.FAILED_RETRYABLE:
        reason = ReplayEligibilityReason.STATE_NOT_RETRYABLE
    elif uncertain_boundary:
        reason = ReplayEligibilityReason.UNCERTAIN_BOUNDARY
    elif reconciliation_required:
        reason = ReplayEligibilityReason.RECONCILIATION_REQUIRED
    elif partial_result:
        reason = ReplayEligibilityReason.PARTIAL_RESULT
    else:
        reason = ReplayEligibilityReason.ELIGIBLE
    return ReplayEligibility(reason is ReplayEligibilityReason.ELIGIBLE, reason)


@dataclass(frozen=True, slots=True)
class IntegrationOperationReference:
    tenant_id: str
    project_global_id: UUID
    operation_kind: IntegrationOperationKind
    operation_global_id: UUID
    source_global_id: UUID
    operation_version: int
    raw_state: str
    shared_state: IntegrationViewState
    source_snapshot_hash: str
    target_idempotency_key_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _tenant(self.tenant_id))
        for fieldname in (
            "project_global_id",
            "operation_global_id",
            "source_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        if not isinstance(self.operation_kind, IntegrationOperationKind):
            raise IntegrationOperationsContractError("operationKind is unsupported.")
        object.__setattr__(
            self,
            "operation_version",
            _positive(self.operation_version, "operationVersion"),
        )
        classification = classify_operation_state(self.operation_kind, self.raw_state)
        if self.shared_state is not classification.shared_state:
            raise IntegrationOperationsContractError(
                "Operation reference state does not match the closed classifier."
            )
        for fieldname in (
            "source_snapshot_hash",
            "target_idempotency_key_hash",
        ):
            object.__setattr__(
                self,
                fieldname,
                _hash(getattr(self, fieldname), _camel(fieldname)),
            )

    @property
    def classification(self) -> OperationStateClassification:
        return classify_operation_state(self.operation_kind, self.raw_state)

    def payload(self) -> dict[str, object]:
        return {
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "operationKind": self.operation_kind.value,
            "operationGlobalId": str(self.operation_global_id),
            "sourceGlobalId": str(self.source_global_id),
            "operationVersion": self.operation_version,
            "rawState": self.raw_state,
            "sharedState": self.shared_state.value,
            "sourceSnapshotHash": self.source_snapshot_hash,
            "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
        }


@dataclass(frozen=True, slots=True)
class IntegrationActionReceipt:
    global_id: UUID
    operation: IntegrationOperationReference
    action_kind: IntegrationActionKind
    action_idempotency_key_hash: str
    expected_raw_state: str
    expected_version: int
    request_hash: str
    outcome_state: IntegrationActionOutcome
    outcome_reference_global_id: UUID | None
    response_snapshot: Mapping[str, Any]
    response_hash: str
    actor_user_id: str
    trace_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if not isinstance(self.operation, IntegrationOperationReference):
            raise IntegrationOperationsContractError(
                "An exact integration operation reference is required."
            )
        if not isinstance(self.action_kind, IntegrationActionKind):
            raise IntegrationOperationsContractError("actionKind is unsupported.")
        expected_outcome = {
            IntegrationActionKind.REPLAY: IntegrationActionOutcome.REPLAY_REQUESTED,
            IntegrationActionKind.REQUEST_RECONCILIATION: (
                IntegrationActionOutcome.RECONCILIATION_REQUESTED
            ),
        }[self.action_kind]
        if self.outcome_state is not expected_outcome:
            raise IntegrationOperationsContractError(
                "Action kind and recorded outcome do not agree."
            )
        if (
            self.action_kind is IntegrationActionKind.REPLAY
            and self.operation.classification.shared_state
            is not IntegrationViewState.FAILED_RETRYABLE
        ):
            raise IntegrationOperationsContractError(
                "Replay receipts require the exact failed_retryable owning state."
            )
        for fieldname in (
            "action_idempotency_key_hash",
            "request_hash",
            "response_hash",
        ):
            object.__setattr__(
                self,
                fieldname,
                _hash(getattr(self, fieldname), _camel(fieldname)),
            )
        expected_raw_state = _code(self.expected_raw_state, "expectedRawState")
        if expected_raw_state != self.operation.raw_state:
            raise IntegrationOperationsContractError(
                "Action expected state does not match the exact operation reference."
            )
        object.__setattr__(self, "expected_raw_state", expected_raw_state)
        expected_version = _positive(self.expected_version, "expectedVersion")
        if expected_version != self.operation.operation_version:
            raise IntegrationOperationsContractError(
                "Action expected version does not match the exact operation reference."
            )
        object.__setattr__(self, "expected_version", expected_version)
        if self.outcome_reference_global_id is not None:
            object.__setattr__(
                self,
                "outcome_reference_global_id",
                _uuid(self.outcome_reference_global_id, "outcomeReferenceGlobalId"),
            )
        response = _json_object(self.response_snapshot, "responseSnapshot")
        expected_response = {
            "actionGlobalId": str(self.global_id),
            "operationGlobalId": str(self.operation.operation_global_id),
            "outcomeState": self.outcome_state.value,
            "outcomeReferenceGlobalId": (
                str(self.outcome_reference_global_id)
                if self.outcome_reference_global_id
                else None
            ),
        }
        if response != expected_response:
            raise IntegrationOperationsContractError(
                "Action response snapshot must exactly match the immutable receipt outcome."
            )
        if canonical_hash(response) != self.response_hash:
            raise IntegrationOperationsContractError(
                "Action response hash does not match its safe response snapshot."
            )
        object.__setattr__(self, "response_snapshot", response)
        object.__setattr__(
            self,
            "actor_user_id",
            _text(self.actor_user_id, "actorUserId", 254, _ACTOR_PATTERN),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "traceId", 128, _TRACE_PATTERN),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))

    def payload(self) -> dict[str, object]:
        return {
            "schemaVersion": INTEGRATION_OPERATIONS_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "operation": self.operation.payload(),
            "actionKind": self.action_kind.value,
            "actionIdempotencyKeyHash": self.action_idempotency_key_hash,
            "expectedRawState": self.expected_raw_state,
            "expectedVersion": self.expected_version,
            "requestHash": self.request_hash,
            "outcomeState": self.outcome_state.value,
            "outcomeReferenceGlobalId": (
                str(self.outcome_reference_global_id)
                if self.outcome_reference_global_id
                else None
            ),
            "response": dict(self.response_snapshot),
            "responseHash": self.response_hash,
            "actorUserId": self.actor_user_id,
            "traceId": self.trace_id,
            "createdAt": _utc_text(self.created_at),
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.payload())


@dataclass(frozen=True, slots=True)
class IntegrationReconciliationObservation:
    global_id: UUID
    operation: IntegrationOperationReference
    action_receipt_global_id: UUID
    attempt_global_id: UUID | None
    state: ReconciliationObservationState
    observer_kind: ReconciliationObserverKind
    authority: ReconciliationAuthority
    response_authenticated: bool
    profile_id: str
    profile_version: int
    adapter_code: str
    evidence_snapshot: Mapping[str, Any]
    evidence_hash: str
    observer_id: str
    trace_id: str
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if not isinstance(self.operation, IntegrationOperationReference):
            raise IntegrationOperationsContractError(
                "An exact integration operation reference is required."
            )
        object.__setattr__(
            self,
            "action_receipt_global_id",
            _uuid(self.action_receipt_global_id, "actionReceiptGlobalId"),
        )
        if self.attempt_global_id is not None:
            object.__setattr__(
                self,
                "attempt_global_id",
                _uuid(self.attempt_global_id, "attemptGlobalId"),
            )
        if not isinstance(self.state, ReconciliationObservationState):
            raise IntegrationOperationsContractError(
                "reconciliationState is unsupported."
            )
        if self.observer_kind is not ReconciliationObserverKind.TRUSTED_OPERATION_SERVICE:
            raise IntegrationOperationsContractError(
                "Reconciliation observations require a trusted operation service."
            )
        if not isinstance(self.authority, ReconciliationAuthority):
            raise IntegrationOperationsContractError(
                "Reconciliation authority is unsupported."
            )
        if not isinstance(self.response_authenticated, bool):
            raise IntegrationOperationsContractError(
                "responseAuthenticated must be a boolean."
            )
        authoritative_state = self.state in {
            ReconciliationObservationState.CONFIRMED_SUCCEEDED,
            ReconciliationObservationState.CONFIRMED_FAILED,
        }
        if authoritative_state and (
            self.authority is not ReconciliationAuthority.AUTHORITATIVE_SANDBOX
            or not self.response_authenticated
        ):
            raise IntegrationOperationsContractError(
                "Confirmed reconciliation truth requires authenticated authoritative Sandbox evidence."
            )
        if self.state is ReconciliationObservationState.TARGET_UNAVAILABLE and (
            self.authority is not ReconciliationAuthority.NONE
            or self.response_authenticated
        ):
            raise IntegrationOperationsContractError(
                "Unavailable target truth cannot claim authoritative evidence."
            )
        object.__setattr__(
            self,
            "profile_id",
            _text(self.profile_id, "profileId", 128, _CODE_PATTERN),
        )
        object.__setattr__(
            self,
            "profile_version",
            _positive(self.profile_version, "profileVersion"),
        )
        object.__setattr__(
            self,
            "adapter_code",
            _text(self.adapter_code, "adapterCode", 140, _CODE_PATTERN),
        )
        evidence = _json_object(self.evidence_snapshot, "evidenceSnapshot")
        expected_evidence_keys = {
            "sourceSnapshotHash",
            "targetIdempotencyKeyHash",
            "resultReferenceHash",
        }
        if set(evidence) != expected_evidence_keys:
            raise IntegrationOperationsContractError(
                "Reconciliation evidence must contain only the fixed safe hash inventory."
            )
        if (
            evidence["sourceSnapshotHash"] != self.operation.source_snapshot_hash
            or evidence["targetIdempotencyKeyHash"]
            != self.operation.target_idempotency_key_hash
        ):
            raise IntegrationOperationsContractError(
                "Reconciliation evidence does not match the exact operation reference."
            )
        result_reference_hash = evidence["resultReferenceHash"]
        if result_reference_hash is not None:
            _hash(result_reference_hash, "resultReferenceHash")
        object.__setattr__(self, "evidence_hash", _hash(self.evidence_hash, "evidenceHash"))
        if canonical_hash(evidence) != self.evidence_hash:
            raise IntegrationOperationsContractError(
                "Reconciliation evidence hash does not match its safe snapshot."
            )
        object.__setattr__(self, "evidence_snapshot", evidence)
        object.__setattr__(
            self,
            "observer_id",
            _text(self.observer_id, "observerId", 254, _ACTOR_PATTERN),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "traceId", 128, _TRACE_PATTERN),
        )
        object.__setattr__(
            self,
            "observed_at",
            _aware_utc(self.observed_at, "observedAt"),
        )

    def payload(self) -> dict[str, object]:
        return {
            "schemaVersion": INTEGRATION_OPERATIONS_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "operation": self.operation.payload(),
            "actionReceiptGlobalId": str(self.action_receipt_global_id),
            "attemptGlobalId": (
                str(self.attempt_global_id) if self.attempt_global_id else None
            ),
            "reconciliationState": self.state.value,
            "observerKind": self.observer_kind.value,
            "authority": self.authority.value,
            "responseAuthenticated": self.response_authenticated,
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "adapterCode": self.adapter_code,
            "evidence": dict(self.evidence_snapshot),
            "evidenceHash": self.evidence_hash,
            "observerId": self.observer_id,
            "traceId": self.trace_id,
            "observedAt": _utc_text(self.observed_at),
        }

    @property
    def observation_hash(self) -> str:
        return canonical_hash(self.payload())


def canonical_hash(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping):
        raise IntegrationOperationsContractError("Canonical value must be an object.")
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as error:
        raise IntegrationOperationsContractError(
            "Canonical value is not JSON-safe."
        ) from error
    return hashlib.sha256(encoded).hexdigest()


def _json_object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise IntegrationOperationsContractError(f"{field} must be an object.")
    try:
        normalized = json.loads(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as error:
        raise IntegrationOperationsContractError(f"{field} is not JSON-safe.") from error
    if not isinstance(normalized, dict):
        raise IntegrationOperationsContractError(f"{field} must be an object.")
    _reject_forbidden_keys(normalized, field)
    return normalized


def _reject_forbidden_keys(value: object, field: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized in _FORBIDDEN_EVIDENCE_KEYS:
                raise IntegrationOperationsContractError(
                    f"{field} contains prohibited transport or secret material."
                )
            _reject_forbidden_keys(nested, field)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_keys(nested, field)


def _uuid(value: object, field: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise IntegrationOperationsContractError(
            f"{field} must be a valid global ID."
        ) from error
    if parsed.version not in {4, 5}:
        raise IntegrationOperationsContractError(
            f"{field} must be a UUIDv4 or UUIDv5 global ID."
        )
    return parsed


def _positive(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise IntegrationOperationsContractError(f"{field} must be a positive integer.")
    return value


def _text(
    value: object,
    field: str,
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
        raise IntegrationOperationsContractError(f"{field} is invalid.")
    return value


def _code(value: object, field: str) -> str:
    return _text(value, field, 140, _CODE_PATTERN)


def _hash(value: object, field: str) -> str:
    return _text(value, field, 64, _HASH_PATTERN)


def _tenant(value: object) -> str:
    return _text(value, "tenantId", 128, _TENANT_PATTERN)


def _aware_utc(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise IntegrationOperationsContractError(f"{field} must be timezone-aware.")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])
