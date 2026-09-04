from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


INBOUND_EVENT_TYPE = "npi.erp-engineering-change.v1"
SUMMARY_EVENT_TYPE = "npi.change-implementation-summary.v1"
SUMMARY_API_VERSION = "npi.change-implementation-summary.v1"
SUMMARY_OPERATION = "record_change_implementation_summary"
FORMAL_CHANGE_DOCTYPE = "Engineering Change Request"
SCHEMA_VERSION = 1
MAX_RAW_BODY_BYTES = 262_144

_ACTOR = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class EngineeringChangeIntegrationError(ValueError):
    """Raised when a P9-01C value is not exact and closed."""


class TargetMode(StrEnum):
    DISABLED = "disabled"
    SYNTHETIC = "synthetic"
    SANDBOX = "sandbox"


class SummaryState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SYNTHETIC_VERIFIED = "synthetic_verified"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    UNCERTAIN_AFTER_TIMEOUT = "uncertain_after_timeout"
    IDENTITY_CONFLICT = "identity_conflict"


class FaultKind(StrEnum):
    NONE = "none"
    RATE_LIMITED = "rate_limited"
    TARGET_SERVER_ERROR = "target_server_error"
    BUSINESS_VALIDATION = "business_validation"
    RESPONSE_CONTRACT_INVALID = "response_contract_invalid"
    RESPONSE_AUTHENTICATION_INVALID = "response_authentication_invalid"
    TIMEOUT_AFTER_POSSIBLE_COMMIT = "timeout_after_possible_commit"
    PARTIAL_RESULT = "partial_result"
    IDENTITY_CONFLICT = "identity_conflict"
    TARGET_UNAVAILABLE = "target_unavailable"


class RetryDirective(StrEnum):
    NONE = "none"
    RETRY_AFTER = "retry_after"
    RETRY_SAME_IDEMPOTENCY = "retry_same_idempotency"
    RECONCILE_BEFORE_RETRY = "reconcile_before_retry"
    MANUAL_CORRECTION = "manual_correction"


@dataclass(frozen=True, slots=True)
class FormalChangeObservation:
    document_name: str
    raw_status: str
    source_version: str
    source_modified_at: datetime
    source_hash: str
    observed_at: datetime
    doctype: str = FORMAL_CHANGE_DOCTYPE

    def __post_init__(self) -> None:
        if self.doctype != FORMAL_CHANGE_DOCTYPE:
            raise EngineeringChangeIntegrationError("Formal change type is unsupported.")
        object.__setattr__(self, "document_name", _text(self.document_name, 140))
        object.__setattr__(self, "raw_status", _text(self.raw_status, 140))
        object.__setattr__(self, "source_version", _text(self.source_version, 140))
        object.__setattr__(self, "source_modified_at", _utc(self.source_modified_at))
        object.__setattr__(self, "source_hash", _hash(self.source_hash))
        object.__setattr__(self, "observed_at", _utc(self.observed_at))

    def payload(self) -> dict[str, object]:
        return {
            "doctype": self.doctype,
            "documentName": self.document_name,
            "rawStatus": self.raw_status,
            "sourceVersion": self.source_version,
            "sourceModifiedAt": utc_text(self.source_modified_at),
            "sourceHash": self.source_hash,
            "observedAt": utc_text(self.observed_at),
        }


@dataclass(frozen=True, slots=True)
class EngineeringChangeInboundEvent:
    event_id: UUID
    occurred_at: datetime
    global_id: UUID
    source_object_id: str
    object_version: int
    correlation_id: UUID
    trace_id: str
    actor_id: str
    tenant_id: str
    project_global_id: UUID
    change_global_id: UUID
    observation: FormalChangeObservation
    payload_hash: str

    def __post_init__(self) -> None:
        for fieldname in ("event_id", "global_id", "correlation_id", "project_global_id", "change_global_id"):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname)))
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at))
        object.__setattr__(self, "source_object_id", _text(self.source_object_id, 255))
        if self.source_object_id != self.observation.document_name:
            raise EngineeringChangeIntegrationError("Source identity does not match the formal change.")
        if type(self.object_version) is not int or self.object_version < 1:
            raise EngineeringChangeIntegrationError("Object version is invalid.")
        object.__setattr__(self, "trace_id", _pattern(self.trace_id, _TRACE))
        object.__setattr__(self, "actor_id", _pattern(self.actor_id, _ACTOR))
        object.__setattr__(self, "tenant_id", _pattern(self.tenant_id, _TENANT))
        if not isinstance(self.observation, FormalChangeObservation):
            raise EngineeringChangeIntegrationError("Formal observation is invalid.")
        object.__setattr__(self, "payload_hash", _hash(self.payload_hash))
        if self.payload_hash != canonical_hash(self.payload()):
            raise EngineeringChangeIntegrationError("Inbound event payload hash does not match.")

    def payload(self) -> dict[str, object]:
        return {
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "changeGlobalId": str(self.change_global_id),
            "formalChange": self.observation.payload(),
        }

    def envelope(self) -> dict[str, object]:
        return {
            "event_id": str(self.event_id),
            "event_type": INBOUND_EVENT_TYPE,
            "event_version": SCHEMA_VERSION,
            "occurred_at": utc_text(self.occurred_at),
            "source_system": "ERPNEXT",
            "target_system": "NPI_ONE",
            "global_id": str(self.global_id),
            "object_type": FORMAL_CHANGE_DOCTYPE,
            "source_object_id": self.source_object_id,
            "object_version": self.object_version,
            "idempotency_key": str(self.event_id),
            "correlation_id": str(self.correlation_id),
            "causation_id": None,
            "trace_id": self.trace_id,
            "actor": {"type": "service", "id": self.actor_id},
            "payload_hash": self.payload_hash,
            "payload": self.payload(),
            "sensitivity": "confidential",
        }


@dataclass(frozen=True, slots=True)
class ChangeImplementationSummary:
    tenant_id: str
    project_global_id: UUID
    change_global_id: UUID
    revision_global_id: UUID
    revision_number: int
    revision_snapshot_hash: str
    formal_change: FormalChangeObservation
    affected_versions_hash: str
    effectivity_hash: str
    disposition_hash: str
    revalidation_hash: str
    closure_evidence_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _pattern(self.tenant_id, _TENANT))
        for fieldname in ("project_global_id", "change_global_id", "revision_global_id"):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname)))
        if type(self.revision_number) is not int or self.revision_number < 1:
            raise EngineeringChangeIntegrationError("Revision number is invalid.")
        if not isinstance(self.formal_change, FormalChangeObservation):
            raise EngineeringChangeIntegrationError("Formal change observation is required.")
        for fieldname in (
            "revision_snapshot_hash", "affected_versions_hash", "effectivity_hash",
            "disposition_hash", "revalidation_hash", "closure_evidence_hash",
        ):
            object.__setattr__(self, fieldname, _hash(getattr(self, fieldname)))

    def payload(self) -> dict[str, object]:
        return {
            "api_version": SUMMARY_API_VERSION,
            "operation": SUMMARY_OPERATION,
            "tenant_id": self.tenant_id,
            "project_global_id": str(self.project_global_id),
            "change_global_id": str(self.change_global_id),
            "revision_global_id": str(self.revision_global_id),
            "revision_number": self.revision_number,
            "revision_snapshot_hash": self.revision_snapshot_hash,
            "formal_change": self.formal_change.payload(),
            "affected_versions_hash": self.affected_versions_hash,
            "effectivity_hash": self.effectivity_hash,
            "disposition_hash": self.disposition_hash,
            "revalidation_hash": self.revalidation_hash,
            "closure_evidence_hash": self.closure_evidence_hash,
        }

    @property
    def source_hash(self) -> str:
        return canonical_hash(self.payload())


@dataclass(frozen=True, slots=True)
class ExecutionProfileReference:
    profile_id: str
    profile_version: int
    target_mode: TargetMode
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _code(self.profile_id))
        if type(self.profile_version) is not int or self.profile_version < 1:
            raise EngineeringChangeIntegrationError("Profile version is invalid.")
        if not isinstance(self.target_mode, TargetMode):
            raise EngineeringChangeIntegrationError("Target mode is invalid.")
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash))


@dataclass(frozen=True, slots=True)
class SummaryRequest:
    global_id: UUID
    summary: ChangeImplementationSummary
    profile: ExecutionProfileReference
    actor_user_id: str
    service_actor_user_id: str
    request_id: UUID
    trace_id: str
    idempotency_key_hash: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id))
        if not isinstance(self.summary, ChangeImplementationSummary) or not isinstance(self.profile, ExecutionProfileReference):
            raise EngineeringChangeIntegrationError("Summary request source is invalid.")
        for fieldname in ("actor_user_id", "service_actor_user_id"):
            value = _pattern(getattr(self, fieldname), _ACTOR)
            if value.casefold() in {"guest", "administrator"}:
                raise EngineeringChangeIntegrationError("Summary actors must be scoped internal users.")
            object.__setattr__(self, fieldname, value)
        object.__setattr__(self, "request_id", _uuid(self.request_id))
        object.__setattr__(self, "trace_id", _pattern(self.trace_id, _TRACE))
        object.__setattr__(self, "idempotency_key_hash", _hash(self.idempotency_key_hash))
        object.__setattr__(self, "created_at", _utc(self.created_at))

    def event_payload(self) -> dict[str, object]:
        return {
            **self.summary.payload(),
            "request_global_id": str(self.global_id),
            "profile_id": self.profile.profile_id,
            "profile_version": self.profile.profile_version,
            "profile_snapshot_hash": self.profile.snapshot_hash,
            "source_hash": self.summary.source_hash,
        }


@dataclass(frozen=True, slots=True)
class AdapterResponse:
    http_status: int | None
    response_hash: str
    authenticated: bool
    contract_valid: bool
    partial: bool = False
    identity_conflict: bool = False
    retry_after_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.http_status is not None and (type(self.http_status) is not int or not 100 <= self.http_status <= 599):
            raise EngineeringChangeIntegrationError("Adapter status is invalid.")
        object.__setattr__(self, "response_hash", _hash(self.response_hash))
        for fieldname in ("authenticated", "contract_valid", "partial", "identity_conflict"):
            if type(getattr(self, fieldname)) is not bool:
                raise EngineeringChangeIntegrationError("Adapter response flags are invalid.")
        if self.retry_after_seconds is not None and (type(self.retry_after_seconds) is not int or not 1 <= self.retry_after_seconds <= 86_400):
            raise EngineeringChangeIntegrationError("Retry delay is invalid.")


@dataclass(frozen=True, slots=True)
class ClassifiedResult:
    state: SummaryState
    fault: FaultKind
    retry: RetryDirective
    response_hash: str
    observed_at: datetime
    response_authenticated: bool
    response_contract_valid: bool
    retry_after_seconds: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, SummaryState) or not isinstance(self.fault, FaultKind) or not isinstance(self.retry, RetryDirective):
            raise EngineeringChangeIntegrationError("Result classification is invalid.")
        object.__setattr__(self, "response_hash", _hash(self.response_hash))
        object.__setattr__(self, "observed_at", _utc(self.observed_at))
        if type(self.response_authenticated) is not bool or type(self.response_contract_valid) is not bool:
            raise EngineeringChangeIntegrationError("Result response evidence is invalid.")
        if self.state in {SummaryState.UNCERTAIN_AFTER_TIMEOUT, SummaryState.PARTIALLY_SUCCEEDED} and self.retry is not RetryDirective.RECONCILE_BEFORE_RETRY:
            raise EngineeringChangeIntegrationError("Uncertain results must reconcile before retry.")


def classify_adapter_response(response: AdapterResponse, *, observed_at: datetime) -> ClassifiedResult:
    if not isinstance(response, AdapterResponse):
        raise EngineeringChangeIntegrationError("Adapter response is invalid.")
    if not response.authenticated:
        values = (SummaryState.FAILED_FINAL, FaultKind.RESPONSE_AUTHENTICATION_INVALID, RetryDirective.MANUAL_CORRECTION)
    elif not response.contract_valid:
        values = (SummaryState.FAILED_FINAL, FaultKind.RESPONSE_CONTRACT_INVALID, RetryDirective.MANUAL_CORRECTION)
    elif response.identity_conflict or response.http_status == 409:
        values = (SummaryState.IDENTITY_CONFLICT, FaultKind.IDENTITY_CONFLICT, RetryDirective.MANUAL_CORRECTION)
    elif response.partial:
        values = (SummaryState.PARTIALLY_SUCCEEDED, FaultKind.PARTIAL_RESULT, RetryDirective.RECONCILE_BEFORE_RETRY)
    elif response.http_status == 429:
        values = (SummaryState.FAILED_RETRYABLE, FaultKind.RATE_LIMITED, RetryDirective.RETRY_AFTER)
    elif response.http_status is not None and 500 <= response.http_status <= 599:
        values = (SummaryState.FAILED_RETRYABLE, FaultKind.TARGET_SERVER_ERROR, RetryDirective.RETRY_SAME_IDEMPOTENCY)
    elif response.http_status is not None and 200 <= response.http_status <= 299:
        values = (SummaryState.SUCCEEDED, FaultKind.NONE, RetryDirective.NONE)
    else:
        values = (SummaryState.FAILED_FINAL, FaultKind.BUSINESS_VALIDATION, RetryDirective.MANUAL_CORRECTION)
    return ClassifiedResult(
        *values,
        response.response_hash,
        observed_at,
        response.authenticated,
        response.contract_valid,
        response.retry_after_seconds,
    )


def uncertain_result(*, response_hash: str, observed_at: datetime) -> ClassifiedResult:
    return ClassifiedResult(
        SummaryState.UNCERTAIN_AFTER_TIMEOUT,
        FaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
        RetryDirective.RECONCILE_BEFORE_RETRY,
        response_hash,
        observed_at,
        False,
        False,
    )


def parse_inbound_event(raw_body: bytes) -> EngineeringChangeInboundEvent:
    if not isinstance(raw_body, bytes) or not 2 <= len(raw_body) <= MAX_RAW_BODY_BYTES:
        raise EngineeringChangeIntegrationError("Inbound body size is invalid.")
    try:
        value = json.loads(raw_body.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EngineeringChangeIntegrationError("Inbound body is invalid.") from error
    expected = {
        "event_id", "event_type", "event_version", "occurred_at", "source_system",
        "target_system", "global_id", "object_type", "source_object_id",
        "object_version", "idempotency_key", "correlation_id", "causation_id",
        "trace_id", "actor", "payload_hash", "payload", "sensitivity",
    }
    record = _closed(value, expected)
    if (
        record["event_type"] != INBOUND_EVENT_TYPE
        or record["event_version"] != SCHEMA_VERSION
        or record["source_system"] != "ERPNEXT"
        or record["target_system"] != "NPI_ONE"
        or record["object_type"] != FORMAL_CHANGE_DOCTYPE
        or record["causation_id"] is not None
        or record["sensitivity"] != "confidential"
    ):
        raise EngineeringChangeIntegrationError("Inbound envelope is unsupported.")
    actor = _closed(record["actor"], {"type", "id"})
    if actor["type"] != "service":
        raise EngineeringChangeIntegrationError("Inbound actor is unsupported.")
    payload = _closed(record["payload"], {"tenantId", "projectGlobalId", "changeGlobalId", "formalChange"})
    formal = _closed(payload["formalChange"], {"doctype", "documentName", "rawStatus", "sourceVersion", "sourceModifiedAt", "sourceHash", "observedAt"})
    event = EngineeringChangeInboundEvent(
        event_id=_uuid(record["event_id"]), occurred_at=_datetime(record["occurred_at"]),
        global_id=_uuid(record["global_id"]), source_object_id=record["source_object_id"],
        object_version=record["object_version"], correlation_id=_uuid(record["correlation_id"]),
        trace_id=record["trace_id"], actor_id=actor["id"], tenant_id=payload["tenantId"],
        project_global_id=_uuid(payload["projectGlobalId"]), change_global_id=_uuid(payload["changeGlobalId"]),
        observation=FormalChangeObservation(
            doctype=formal["doctype"], document_name=formal["documentName"],
            raw_status=formal["rawStatus"], source_version=formal["sourceVersion"],
            source_modified_at=_datetime(formal["sourceModifiedAt"]), source_hash=formal["sourceHash"],
            observed_at=_datetime(formal["observedAt"]),
        ),
        payload_hash=record["payload_hash"],
    )
    if record["idempotency_key"] != str(event.event_id):
        raise EngineeringChangeIntegrationError("Inbound idempotency identity is invalid.")
    return event


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


def utc_text(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _closed(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise EngineeringChangeIntegrationError("Payload shape is invalid.")
    return dict(value)


def _unique_pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise EngineeringChangeIntegrationError("Duplicate JSON key is invalid.")
        result[key] = value
    return result


def _uuid(value: object) -> UUID:
    try:
        result = value if isinstance(value, UUID) else UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise EngineeringChangeIntegrationError("UUID is invalid.") from error
    if str(result) != str(value):
        raise EngineeringChangeIntegrationError("UUID must be canonical.")
    return result


def _datetime(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EngineeringChangeIntegrationError("Datetime is invalid.")
    try:
        return _utc(datetime.fromisoformat(value[:-1] + "+00:00"))
    except ValueError as error:
        raise EngineeringChangeIntegrationError("Datetime is invalid.") from error


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise EngineeringChangeIntegrationError("Datetime must be timezone-aware.")
    return value.astimezone(UTC)


def _text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise EngineeringChangeIntegrationError("Text value is invalid.")
    return value


def _pattern(value: object, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise EngineeringChangeIntegrationError("Patterned value is invalid.")
    return value


def _hash(value: object) -> str:
    return _pattern(value, _HASH)


def _code(value: object) -> str:
    return _pattern(value, _CODE)
