from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import NoReturn
from uuid import UUID, uuid4


PROJECT_SOURCE_EVENT_SCHEMA_VERSION = 1
MAX_RAW_BODY_BYTES = 262_144
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_SOURCE_ID_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,255}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SURROGATE_PATTERN = re.compile(r"[\ud800-\udfff]")
_MAX_OBJECT_VERSION = 2_147_483_647


class ProjectSourceContractError(ValueError):
    """Raised when signed project-source input is not exactly contract-shaped."""


class ProjectSourceEventType(StrEnum):
    QUOTATION_SUBMITTED = "erpnext.quotation.submitted"
    SALES_ORDER_SUBMITTED = "erpnext.sales_order.submitted"


class ProjectSourceObjectType(StrEnum):
    QUOTATION = "Quotation"
    SALES_ORDER = "Sales Order"


PROJECT_SOURCE_EVENT_TYPES: Mapping[ProjectSourceEventType, ProjectSourceObjectType] = (
    MappingProxyType(
        {
            ProjectSourceEventType.QUOTATION_SUBMITTED: ProjectSourceObjectType.QUOTATION,
            ProjectSourceEventType.SALES_ORDER_SUBMITTED: ProjectSourceObjectType.SALES_ORDER,
        }
    )
)


class EventIdentityDisposition(StrEnum):
    DUPLICATE_EXACT = "duplicate_exact"
    CONFLICTED = "conflicted"


class SourceOrderDisposition(StrEnum):
    ADVANCE = "advance"
    SUPERSEDED = "superseded"
    DUPLICATE_EXACT = "duplicate_exact"
    CONFLICTED = "conflicted"
    RECEIVED_AFTER_CREATION = "received_after_creation"


@dataclass(frozen=True, slots=True)
class ProjectSourcePayload:
    title: str
    target_sop: str
    source_modified_at: str

    @classmethod
    def from_mapping(cls, value: object) -> ProjectSourcePayload:
        source = _closed_mapping(
            value,
            "payload",
            {
                "schema_version",
                "submission_state",
                "title",
                "target_sop",
                "source_modified_at",
            },
        )
        if _integer(source["schema_version"], "payload.schema_version") != 1:
            raise ProjectSourceContractError("payload.schema_version is unsupported.")
        if source["submission_state"] != "submitted":
            raise ProjectSourceContractError("payload.submission_state is unsupported.")
        return cls(
            title=_text(source["title"], "payload.title", 140),
            target_sop=_date_text(source["target_sop"], "payload.target_sop"),
            source_modified_at=_utc_text(
                source["source_modified_at"], "payload.source_modified_at"
            ),
        )

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "schema_version": PROJECT_SOURCE_EVENT_SCHEMA_VERSION,
            "submission_state": "submitted",
            "title": self.title,
            "target_sop": self.target_sop,
            "source_modified_at": self.source_modified_at,
        }


@dataclass(frozen=True, slots=True)
class InboundProjectEvent:
    event_id: UUID
    event_type: ProjectSourceEventType
    occurred_at: str
    global_id: UUID
    object_type: ProjectSourceObjectType
    source_object_id: str
    object_version: int
    correlation_id: UUID
    trace_id: str
    actor_id: str
    payload_hash: str
    payload: ProjectSourcePayload

    @classmethod
    def from_mapping(cls, value: object) -> InboundProjectEvent:
        source = _closed_mapping(
            value,
            "event",
            {
                "event_id",
                "event_type",
                "event_version",
                "occurred_at",
                "source_system",
                "target_system",
                "global_id",
                "object_type",
                "source_object_id",
                "object_version",
                "correlation_id",
                "trace_id",
                "actor",
                "payload_hash",
                "payload",
                "sensitivity",
            },
        )
        try:
            event_type = ProjectSourceEventType(source["event_type"])
            object_type = ProjectSourceObjectType(source["object_type"])
        except (TypeError, ValueError) as error:
            raise ProjectSourceContractError(
                "event_type or object_type is unsupported."
            ) from error
        if PROJECT_SOURCE_EVENT_TYPES[event_type] is not object_type:
            raise ProjectSourceContractError(
                "event_type does not match object_type."
            )
        if _integer(source["event_version"], "event_version") != 1:
            raise ProjectSourceContractError("event_version is unsupported.")
        if source["source_system"] != "ERPNEXT" or source["target_system"] != "NPI_ONE":
            raise ProjectSourceContractError("event system ownership is invalid.")
        if source["sensitivity"] != "confidential":
            raise ProjectSourceContractError("event sensitivity is invalid.")
        actor = _closed_mapping(source["actor"], "actor", {"type", "id"})
        if actor["type"] != "service":
            raise ProjectSourceContractError("event actor must be a service.")
        payload = ProjectSourcePayload.from_mapping(source["payload"])
        payload_hash = _hash(source["payload_hash"], "payload_hash")
        if payload_hash != canonical_json_hash(payload.canonical_mapping()):
            raise ProjectSourceContractError("payload_hash does not match payload.")
        return cls(
            event_id=_uuid(source["event_id"], "event_id"),
            event_type=event_type,
            occurred_at=_utc_text(source["occurred_at"], "occurred_at"),
            global_id=_uuid(source["global_id"], "global_id"),
            object_type=object_type,
            source_object_id=_pattern_text(
                source["source_object_id"],
                "source_object_id",
                _SOURCE_ID_PATTERN,
            ),
            object_version=_positive_integer(
                source["object_version"], "object_version"
            ),
            correlation_id=_uuid(source["correlation_id"], "correlation_id"),
            trace_id=_pattern_text(source["trace_id"], "trace_id", _TRACE_PATTERN),
            actor_id=_pattern_text(actor["id"], "actor.id", _ACTOR_PATTERN),
            payload_hash=payload_hash,
            payload=payload,
        )

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "event_version": PROJECT_SOURCE_EVENT_SCHEMA_VERSION,
            "occurred_at": self.occurred_at,
            "source_system": "ERPNEXT",
            "target_system": "NPI_ONE",
            "global_id": str(self.global_id),
            "object_type": self.object_type.value,
            "source_object_id": self.source_object_id,
            "object_version": self.object_version,
            "correlation_id": str(self.correlation_id),
            "trace_id": self.trace_id,
            "actor": {"type": "service", "id": self.actor_id},
            "payload_hash": self.payload_hash,
            "payload": self.payload.canonical_mapping(),
            "sensitivity": "confidential",
        }

    @property
    def canonical_event_hash(self) -> str:
        return canonical_json_hash(self.canonical_mapping())


@dataclass(frozen=True, slots=True)
class SourceStreamIdentity:
    tenant_id: str
    profile_id: str
    object_type: ProjectSourceObjectType
    source_object_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            _pattern_text(self.tenant_id, "tenant_id", _TENANT_PATTERN),
        )
        object.__setattr__(self, "profile_id", _identifier(self.profile_id, "profile_id"))
        if not isinstance(self.object_type, ProjectSourceObjectType):
            raise ProjectSourceContractError("object_type is unsupported.")
        object.__setattr__(
            self,
            "source_object_id",
            _pattern_text(
                self.source_object_id,
                "source_object_id",
                _SOURCE_ID_PATTERN,
            ),
        )

    @property
    def key_hash(self) -> str:
        return canonical_json_hash(
            {
                "tenant_id": self.tenant_id,
                "profile_id": self.profile_id,
                "object_type": self.object_type.value,
                "source_object_id": self.source_object_id,
            }
        )


@dataclass(frozen=True, slots=True)
class SourceHead:
    object_version: int
    payload_hash: str
    inbox_id: UUID

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "object_version",
            _positive_integer(self.object_version, "object_version"),
        )
        object.__setattr__(self, "payload_hash", _hash(self.payload_hash, "payload_hash"))
        object.__setattr__(self, "inbox_id", _uuid(self.inbox_id, "inbox_id"))


def classify_event_identity(
    existing_canonical_hash: object,
    candidate_canonical_hash: object,
) -> EventIdentityDisposition:
    existing = _hash(existing_canonical_hash, "existing_canonical_hash")
    candidate = _hash(candidate_canonical_hash, "candidate_canonical_hash")
    if existing == candidate:
        return EventIdentityDisposition.DUPLICATE_EXACT
    return EventIdentityDisposition.CONFLICTED


def classify_source_order(
    current: SourceHead | None,
    candidate: SourceHead,
    *,
    project_already_bound: bool = False,
) -> SourceOrderDisposition:
    if current is not None and not isinstance(current, SourceHead):
        raise ProjectSourceContractError("current source head is invalid.")
    if not isinstance(candidate, SourceHead):
        raise ProjectSourceContractError("candidate source head is invalid.")
    if type(project_already_bound) is not bool:
        raise ProjectSourceContractError("project binding state must be boolean.")
    if current is None or candidate.object_version > current.object_version:
        if project_already_bound:
            return SourceOrderDisposition.RECEIVED_AFTER_CREATION
        return SourceOrderDisposition.ADVANCE
    if candidate.object_version < current.object_version:
        return SourceOrderDisposition.SUPERSEDED
    if candidate.payload_hash == current.payload_hash:
        return SourceOrderDisposition.DUPLICATE_EXACT
    return SourceOrderDisposition.CONFLICTED


@dataclass(frozen=True, slots=True)
class ClaimLease:
    token: UUID
    claimed_at: datetime
    expires_at: datetime
    attempt_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "token", _uuid(self.token, "claim.token"))
        claimed = _aware_utc(self.claimed_at, "claim.claimed_at")
        expires = _aware_utc(self.expires_at, "claim.expires_at")
        if expires <= claimed:
            raise ProjectSourceContractError("claim expiry must follow claim time.")
        object.__setattr__(self, "claimed_at", claimed)
        object.__setattr__(self, "expires_at", expires)
        object.__setattr__(
            self,
            "attempt_count",
            _positive_integer(self.attempt_count, "claim.attempt_count"),
        )

    def is_live(self, now: datetime) -> bool:
        return _aware_utc(now, "now") < self.expires_at


def issue_claim(
    *,
    now: datetime,
    lease_seconds: int,
    previous_attempt_count: int = 0,
) -> ClaimLease:
    claimed = _aware_utc(now, "now")
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3_600:
        raise ProjectSourceContractError("lease_seconds is invalid.")
    if (
        type(previous_attempt_count) is not int
        or not 0 <= previous_attempt_count < _MAX_OBJECT_VERSION
    ):
        raise ProjectSourceContractError("previous_attempt_count is invalid.")
    return ClaimLease(
        token=uuid4(),
        claimed_at=claimed,
        expires_at=claimed + timedelta(seconds=lease_seconds),
        attempt_count=previous_attempt_count + 1,
    )


def parse_project_source_event(raw_body: bytes) -> InboundProjectEvent:
    value = parse_closed_json(raw_body)
    return InboundProjectEvent.from_mapping(value)


def parse_closed_json(raw_body: bytes) -> object:
    if not isinstance(raw_body, bytes):
        raise ProjectSourceContractError("raw body must be bytes.")
    if not 2 <= len(raw_body) <= MAX_RAW_BODY_BYTES:
        raise ProjectSourceContractError("raw body size is invalid.")
    try:
        source = raw_body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ProjectSourceContractError("raw body is not valid UTF-8.") from error
    try:
        value = json.loads(
            source,
            object_pairs_hook=_object_without_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, RecursionError) as error:
        raise ProjectSourceContractError("raw body is not valid closed JSON.") from error
    _validate_json_value(value, "event")
    return value


def canonical_json_bytes(value: object) -> bytes:
    normalized = _validate_json_value(value, "value")
    try:
        return json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise ProjectSourceContractError("value is not canonical JSON.") from error


def canonical_json_hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def raw_body_hash(raw_body: bytes) -> str:
    if not isinstance(raw_body, bytes):
        raise ProjectSourceContractError("raw body must be bytes.")
    return hashlib.sha256(raw_body).hexdigest()


def _object_without_duplicates(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProjectSourceContractError("JSON object contains a duplicate key.")
        result[key] = value
    return result


def _reject_float(_: str) -> NoReturn:
    raise ProjectSourceContractError("JSON floating-point values are not supported.")


def _reject_constant(_: str) -> NoReturn:
    raise ProjectSourceContractError("JSON non-finite values are not supported.")


def _validate_json_value(value: object, path: str) -> object:
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, str):
        if _SURROGATE_PATTERN.search(value):
            raise ProjectSourceContractError(f"{path} contains invalid Unicode.")
        return value
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or _SURROGATE_PATTERN.search(key):
                raise ProjectSourceContractError(f"{path} contains an invalid key.")
            if key in result:
                raise ProjectSourceContractError(f"{path} contains a duplicate key.")
            result[key] = _validate_json_value(item, f"{path}.{key}")
        return result
    if isinstance(value, list):
        return [
            _validate_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise ProjectSourceContractError(f"{path} contains an unsupported JSON value.")


def _closed_mapping(
    value: object,
    path: str,
    expected_keys: set[str],
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise ProjectSourceContractError(f"{path} keys do not match the contract.")
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or _SURROGATE_PATTERN.search(value)
    ):
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _pattern_text(
    value: object,
    path: str,
    pattern: re.Pattern[str],
) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _identifier(value: object, path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(
        r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$", value
    ) is None:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _integer(value: object, path: str) -> int:
    if type(value) is not int or not 0 <= value <= _MAX_OBJECT_VERSION:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _positive_integer(value: object, path: str) -> int:
    result = _integer(value, path)
    if result < 1:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return result


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, (str, UUID)):
        raise ProjectSourceContractError(f"{path} is invalid.")
    try:
        result = UUID(str(value))
    except ValueError as error:
        raise ProjectSourceContractError(f"{path} is invalid.") from error
    if isinstance(value, str) and str(result) != value:
        raise ProjectSourceContractError(f"{path} must be canonical.")
    return result


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _utc_text(value: object, path: str) -> str:
    if not isinstance(value, str) or _UTC_PATTERN.fullmatch(value) is None:
        raise ProjectSourceContractError(f"{path} is invalid.")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ProjectSourceContractError(f"{path} is invalid.") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _date_text(value: object, path: str) -> str:
    if not isinstance(value, str) or _DATE_PATTERN.fullmatch(value) is None:
        raise ProjectSourceContractError(f"{path} is invalid.")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ProjectSourceContractError(f"{path} is invalid.") from error
    if parsed.strftime("%Y-%m-%d") != value:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _aware_utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ProjectSourceContractError(f"{path} must be timezone-aware.")
    return value.astimezone(UTC)
