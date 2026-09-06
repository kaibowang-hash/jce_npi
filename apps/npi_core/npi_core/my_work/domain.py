from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CURSOR_KEY_CONTEXT = b"npi-one:my-work:cursor:v1"
_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 500
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_BASE64URL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_UTC_INSTANT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_MAX_SORT_INSTANT = datetime.max.replace(tzinfo=UTC)


class MyWorkValidationError(ValueError):
    """Internal validation failure for a pure My Work domain value."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


class InvalidMyWorkCursor(ValueError):
    """One fail-closed error for malformed, forged, or mismatched cursors."""

    def __init__(self) -> None:
        super().__init__("The My Work cursor is invalid.")


class MyWorkSourceType(str, Enum):
    DOMAIN_WORK_ITEM = "domain_work_item"
    GATE_REVIEW_ASSIGNMENT = "gate_review_assignment"
    GATE_REVIEW_INVALIDATION = "gate_review_invalidation"


class MyWorkView(str, Enum):
    ALL = "all"
    TODAY = "today"
    OVERDUE = "overdue"
    APPROVALS = "approvals"
    BLOCKERS = "blockers"
    WAITING = "waiting"
    INTEGRATION = "integration"


class MyWorkCategory(str, Enum):
    TASK = "task"
    APPROVAL = "approval"
    BLOCKER = "blocker"
    RISK = "risk"
    ISSUE = "issue"
    DECISION = "decision"


class DomainWorkItemKind(str, Enum):
    RISK = "risk"
    ISSUE = "issue"
    ACTION = "action"
    DECISION_REQUEST = "decision_request"


class MyWorkStatus(str, Enum):
    READY = "ready"
    WAITING = "waiting"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"


class MyWorkDueState(str, Enum):
    OVERDUE = "overdue"
    TODAY = "today"
    UPCOMING = "upcoming"
    UNSCHEDULED = "unscheduled"


class MyWorkPriorityScheme(str, Enum):
    DOMAIN_SEVERITY = "domain_severity"
    GATE_REQUIREMENT_PRIORITY = "gate_requirement_priority"


class MyWorkTargetKind(str, Enum):
    MY_WORK_ITEM = "my_work_item"
    GATE_REVIEW = "gate_review"


class MyWorkCountAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class MyWorkUnavailableReason(str, Enum):
    SOURCE_NOT_AVAILABLE = "source_not_available"


_DOMAIN_CATEGORY = {
    DomainWorkItemKind.RISK: MyWorkCategory.RISK,
    DomainWorkItemKind.ISSUE: MyWorkCategory.ISSUE,
    DomainWorkItemKind.ACTION: MyWorkCategory.TASK,
    DomainWorkItemKind.DECISION_REQUEST: MyWorkCategory.DECISION,
}
_PRIORITY_VALUES = {
    MyWorkPriorityScheme.DOMAIN_SEVERITY: frozenset(
        {"low", "medium", "high", "critical"}
    ),
    MyWorkPriorityScheme.GATE_REQUIREMENT_PRIORITY: frozenset({"P0", "P1", "P2"}),
}


def _fail(path: str, message: str) -> MyWorkValidationError:
    return MyWorkValidationError(path, message)


def _enum(value: object, expected: type[Enum], path: str) -> None:
    if type(value) is not expected:
        raise _fail(path, "Select a supported value.")


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise _fail(path, "Enter a valid non-zero UUID.")
    return value


def _positive_int(value: object, path: str, *, maximum: int | None = None) -> int:
    if type(value) is not int or value < 1 or (maximum is not None and value > maximum):
        raise _fail(path, "Enter a positive integer within the supported range.")
    return value


def _non_negative_int(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _fail(path, "Enter a non-negative integer.")
    return value


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _fail(path, "Select a valid true or false value.")
    return value


def _instant(value: object, path: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise _fail(path, "Enter a timezone-aware date and time.")
    return value.astimezone(UTC)


def _time_zone(value: object, path: str = "timeZone") -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 64
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise _fail(path, "Enter a valid IANA time zone.")
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise _fail(path, "Enter a valid IANA time zone.") from error
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _instant_text(value: object, path: str) -> str:
    return (
        _instant(value, path).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _parse_instant(value: object, path: str) -> datetime:
    if type(value) is not str or _UTC_INSTANT_PATTERN.fullmatch(value) is None:
        raise _fail(path, "Enter a canonical UTC date and time.")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if _instant_text(parsed, path) != value:
        raise _fail(path, "Enter a canonical UTC date and time.")
    return parsed


def _uuid_text(value: object, path: str) -> UUID:
    if type(value) is not str:
        raise _fail(path, "Enter a canonical UUID.")
    parsed = UUID(value)
    if parsed.int == 0 or str(parsed) != value:
        raise _fail(path, "Enter a canonical UUID.")
    return parsed


@dataclass(frozen=True, slots=True)
class MyWorkPriority:
    scheme: MyWorkPriorityScheme
    value: str

    def __post_init__(self) -> None:
        _enum(self.scheme, MyWorkPriorityScheme, "priority.scheme")
        if (
            type(self.value) is not str
            or self.value not in _PRIORITY_VALUES[self.scheme]
        ):
            raise _fail(
                "priority.value",
                "Select a value from the exact priority vocabulary.",
            )

    def canonical_dict(self) -> dict[str, str]:
        return {"scheme": self.scheme.value, "value": self.value}


@dataclass(frozen=True, slots=True)
class MyWorkSourceReference:
    type: MyWorkSourceType
    global_id: UUID
    version: int

    def __post_init__(self) -> None:
        _enum(self.type, MyWorkSourceType, "source.type")
        _uuid(self.global_id, "source.globalId")
        _positive_int(self.version, "source.version")


@dataclass(frozen=True, slots=True)
class DomainWorkItemTarget:
    work_item_id: UUID
    kind: MyWorkTargetKind = field(
        default=MyWorkTargetKind.MY_WORK_ITEM,
        init=False,
    )

    def __post_init__(self) -> None:
        _uuid(self.work_item_id, "target.workItemId")


@dataclass(frozen=True, slots=True)
class GateReviewTarget:
    project_id: UUID
    gate_id: UUID
    kind: MyWorkTargetKind = field(
        default=MyWorkTargetKind.GATE_REVIEW,
        init=False,
    )

    def __post_init__(self) -> None:
        _uuid(self.project_id, "target.projectId")
        _uuid(self.gate_id, "target.gateId")


@dataclass(frozen=True, slots=True)
class MyWorkSortTuple:
    due_at: datetime | None
    item_id: UUID

    def __post_init__(self) -> None:
        if self.due_at is not None:
            object.__setattr__(
                self,
                "due_at",
                _instant(self.due_at, "last.dueAt"),
            )
        _uuid(self.item_id, "last.id")

    @property
    def key(self) -> tuple[bool, datetime, str]:
        return (
            self.due_at is None,
            self.due_at if self.due_at is not None else _MAX_SORT_INSTANT,
            str(self.item_id),
        )


@dataclass(frozen=True, slots=True)
class MyWorkItem:
    id: UUID
    project_global_id: UUID
    source: MyWorkSourceReference
    domain_kind: DomainWorkItemKind | None
    category: MyWorkCategory
    status: MyWorkStatus
    due_at: datetime | None
    priority: MyWorkPriority | None
    blocking: bool
    target: DomainWorkItemTarget | GateReviewTarget

    def __post_init__(self) -> None:
        _uuid(self.id, "id")
        _uuid(self.project_global_id, "projectGlobalId")
        if type(self.source) is not MyWorkSourceReference:
            raise _fail("source", "Enter a typed My Work source reference.")
        _enum(self.category, MyWorkCategory, "category")
        _enum(self.status, MyWorkStatus, "status")
        if self.due_at is not None:
            object.__setattr__(
                self,
                "due_at",
                _instant(self.due_at, "dueAt"),
            )
        if self.priority is not None and type(self.priority) is not MyWorkPriority:
            raise _fail("priority", "Enter a typed priority pair.")
        _boolean(self.blocking, "blocking")
        self._validate_source_contract()

    @property
    def sort_tuple(self) -> MyWorkSortTuple:
        return MyWorkSortTuple(self.due_at, self.id)

    def _validate_source_contract(self) -> None:
        if self.source.type is MyWorkSourceType.DOMAIN_WORK_ITEM:
            _enum(self.domain_kind, DomainWorkItemKind, "domainKind")
            if self.category is not _DOMAIN_CATEGORY[self.domain_kind]:
                raise _fail(
                    "category",
                    "The category must exactly map the Domain Work Item kind.",
                )
            if (
                type(self.target) is not DomainWorkItemTarget
                or self.target.work_item_id != self.source.global_id
            ):
                raise _fail(
                    "target",
                    "A Domain Work Item requires its typed work-item target.",
                )
            if (
                self.priority is not None
                and self.priority.scheme is not MyWorkPriorityScheme.DOMAIN_SEVERITY
            ):
                raise _fail(
                    "priority.scheme",
                    "A Domain Work Item retains the domain severity vocabulary.",
                )
            return

        if self.domain_kind is not None:
            raise _fail(
                "domainKind",
                "Gate review projections cannot declare a Domain Work Item kind.",
            )
        if (
            type(self.target) is not GateReviewTarget
            or self.target.project_id != self.project_global_id
            or self.target.gate_id != self.source.global_id
        ):
            raise _fail(
                "target",
                "Gate review work requires its typed Project and Gate target.",
            )
        if (
            self.priority is not None
            and self.priority.scheme
            is not MyWorkPriorityScheme.GATE_REQUIREMENT_PRIORITY
        ):
            raise _fail(
                "priority.scheme",
                "Gate review work retains the Gate requirement priority vocabulary.",
            )
        if self.source.type is MyWorkSourceType.GATE_REVIEW_ASSIGNMENT:
            if self.category is not MyWorkCategory.APPROVAL:
                raise _fail(
                    "category",
                    "A Gate review assignment is an approval projection.",
                )
            return
        if self.source.type is MyWorkSourceType.GATE_REVIEW_INVALIDATION:
            if self.category is not MyWorkCategory.BLOCKER or not self.blocking:
                raise _fail(
                    "category",
                    "A Gate review invalidation is a blocking blocker projection.",
                )
            return
        raise _fail("source.type", "Select a supported My Work source.")


@dataclass(frozen=True, slots=True)
class MyWorkQuery:
    view: MyWorkView
    project_global_id: UUID | None = None
    priority: MyWorkPriority | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        _enum(self.view, MyWorkView, "view")
        if self.project_global_id is not None:
            _uuid(self.project_global_id, "projectId")
        if self.priority is not None and type(self.priority) is not MyWorkPriority:
            raise _fail("priority", "Enter a typed priority pair.")
        _positive_int(self.limit, "limit", maximum=100)

    def identity_dict(self) -> dict[str, object]:
        return {
            "priority": (
                None if self.priority is None else self.priority.canonical_dict()
            ),
            "projectId": (
                None if self.project_global_id is None else str(self.project_global_id)
            ),
            "view": self.view.value,
        }


@dataclass(frozen=True, slots=True)
class AvailableMyWorkCount:
    value: int
    availability: MyWorkCountAvailability = field(
        default=MyWorkCountAvailability.AVAILABLE,
        init=False,
    )

    def __post_init__(self) -> None:
        _non_negative_int(self.value, "count.value")


@dataclass(frozen=True, slots=True)
class UnavailableMyWorkCount:
    availability: MyWorkCountAvailability = field(
        default=MyWorkCountAvailability.UNAVAILABLE,
        init=False,
    )
    reason: MyWorkUnavailableReason = field(
        default=MyWorkUnavailableReason.SOURCE_NOT_AVAILABLE,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class MyWorkCounts:
    all: AvailableMyWorkCount
    today: AvailableMyWorkCount
    overdue: AvailableMyWorkCount
    approvals: AvailableMyWorkCount
    blockers: AvailableMyWorkCount
    waiting: AvailableMyWorkCount
    integration: UnavailableMyWorkCount

    def __post_init__(self) -> None:
        available = (
            self.all,
            self.today,
            self.overdue,
            self.approvals,
            self.blockers,
            self.waiting,
        )
        if any(type(count) is not AvailableMyWorkCount for count in available):
            raise _fail("counts", "Every owned-source count must be available.")
        if type(self.integration) is not UnavailableMyWorkCount:
            raise _fail(
                "counts.integration",
                "Integration must remain explicitly unavailable.",
            )
        if any(count.value > self.all.value for count in available[1:]):
            raise _fail("counts", "A filtered count cannot exceed the all count.")


def _items(values: Iterable[MyWorkItem]) -> tuple[MyWorkItem, ...]:
    try:
        items = tuple(values)
    except TypeError as error:
        raise _fail("items", "Enter an iterable of typed My Work items.") from error
    if any(type(item) is not MyWorkItem for item in items):
        raise _fail("items", "Enter only typed My Work items.")
    if len({item.id for item in items}) != len(items):
        raise _fail("items", "My Work item IDs must be unique.")
    return items


def _base_match(
    item: MyWorkItem,
    *,
    project_global_id: UUID | None,
    priority: MyWorkPriority | None,
) -> bool:
    return (
        project_global_id is None or item.project_global_id == project_global_id
    ) and (priority is None or item.priority == priority)


def _view_match(
    item: MyWorkItem,
    view: MyWorkView,
    *,
    as_of: datetime,
    zone: ZoneInfo,
) -> bool:
    if view is MyWorkView.ALL:
        return True
    if view is MyWorkView.TODAY:
        return (
            item.due_at is not None
            and item.due_at.astimezone(zone).date() == as_of.astimezone(zone).date()
        )
    if view is MyWorkView.OVERDUE:
        return item.due_at is not None and item.due_at < as_of
    if view is MyWorkView.APPROVALS:
        return item.category is MyWorkCategory.APPROVAL
    if view is MyWorkView.BLOCKERS:
        return item.blocking
    if view is MyWorkView.WAITING:
        return item.status is MyWorkStatus.WAITING
    if view is MyWorkView.INTEGRATION:
        return False
    raise _fail("view", "Select a supported My Work view.")


def my_work_due_state(
    item: MyWorkItem,
    *,
    as_of: datetime,
    time_zone: str,
) -> MyWorkDueState:
    """Classify one due date at the response's fixed clock and actor time zone."""

    if type(item) is not MyWorkItem:
        raise _fail("item", "Enter a typed My Work item.")
    fixed_as_of = _instant(as_of, "asOf")
    zone = ZoneInfo(_time_zone(time_zone))
    if item.due_at is None:
        return MyWorkDueState.UNSCHEDULED
    if item.due_at < fixed_as_of:
        return MyWorkDueState.OVERDUE
    if item.due_at.astimezone(zone).date() == fixed_as_of.astimezone(zone).date():
        return MyWorkDueState.TODAY
    return MyWorkDueState.UPCOMING


def sort_my_work_items(
    values: Iterable[MyWorkItem],
) -> tuple[MyWorkItem, ...]:
    """Apply `(dueAt is null asc, dueAt asc, id asc)` exactly."""

    return tuple(sorted(_items(values), key=lambda item: item.sort_tuple.key))


def filter_my_work_items(
    values: Iterable[MyWorkItem],
    query: MyWorkQuery,
    *,
    as_of: datetime,
    time_zone: str,
    after: MyWorkSortTuple | None = None,
) -> tuple[MyWorkItem, ...]:
    """Filter, keyset-seek, canonically sort, and apply the bounded limit."""

    if type(query) is not MyWorkQuery:
        raise _fail("query", "Enter a typed My Work query.")
    fixed_as_of = _instant(as_of, "asOf")
    zone = ZoneInfo(_time_zone(time_zone))
    if after is not None and type(after) is not MyWorkSortTuple:
        raise _fail("after", "Enter a typed My Work sort tuple.")
    selected = (
        item
        for item in _items(values)
        if _base_match(
            item,
            project_global_id=query.project_global_id,
            priority=query.priority,
        )
        and _view_match(item, query.view, as_of=fixed_as_of, zone=zone)
    )
    ordered = sort_my_work_items(selected)
    if after is not None:
        ordered = tuple(item for item in ordered if item.sort_tuple.key > after.key)
    return ordered[: query.limit]


def calculate_my_work_counts(
    values: Iterable[MyWorkItem],
    *,
    as_of: datetime,
    time_zone: str,
    project_global_id: UUID | None = None,
    priority: MyWorkPriority | None = None,
) -> MyWorkCounts:
    """Count owned P4-05 sources; integration deliberately has no numeric value."""

    fixed_as_of = _instant(as_of, "asOf")
    zone = ZoneInfo(_time_zone(time_zone))
    if project_global_id is not None:
        _uuid(project_global_id, "projectId")
    if priority is not None and type(priority) is not MyWorkPriority:
        raise _fail("priority", "Enter a typed priority pair.")
    base = tuple(
        item
        for item in _items(values)
        if _base_match(
            item,
            project_global_id=project_global_id,
            priority=priority,
        )
    )

    def count(view: MyWorkView) -> AvailableMyWorkCount:
        return AvailableMyWorkCount(
            sum(_view_match(item, view, as_of=fixed_as_of, zone=zone) for item in base)
        )

    return MyWorkCounts(
        all=AvailableMyWorkCount(len(base)),
        today=count(MyWorkView.TODAY),
        overdue=count(MyWorkView.OVERDUE),
        approvals=count(MyWorkView.APPROVALS),
        blockers=count(MyWorkView.BLOCKERS),
        waiting=count(MyWorkView.WAITING),
        integration=UnavailableMyWorkCount(),
    )


def my_work_query_fingerprint(query: MyWorkQuery) -> str:
    """Fingerprint filter identity; page size is not a result-set identity."""

    if type(query) is not MyWorkQuery:
        raise _fail("query", "Enter a typed My Work query.")
    return hashlib.sha256(_canonical_json(query.identity_dict())).hexdigest()


@dataclass(frozen=True, slots=True)
class MyWorkCursor:
    as_of: datetime
    time_zone: str
    query_fingerprint: str
    last: MyWorkSortTuple

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _instant(self.as_of, "asOf"))
        object.__setattr__(
            self,
            "time_zone",
            _time_zone(self.time_zone),
        )
        if (
            type(self.query_fingerprint) is not str
            or _HASH_PATTERN.fullmatch(self.query_fingerprint) is None
        ):
            raise _fail("queryFingerprint", "Enter a SHA-256 query fingerprint.")
        if type(self.last) is not MyWorkSortTuple:
            raise _fail("last", "Enter a typed My Work sort tuple.")


@dataclass(frozen=True, slots=True)
class MyWorkCursorCodec:
    signing_key: bytes = field(repr=False)
    context: bytes = CURSOR_KEY_CONTEXT

    def __post_init__(self) -> None:
        if type(self.signing_key) is not bytes or len(self.signing_key) < 32:
            raise _fail(
                "signingKey",
                "Use an independently managed signing key of at least 32 bytes.",
            )
        if (
            type(self.context) is not bytes
            or not self.context
            or len(self.context) > 128
        ):
            raise _fail("context", "Enter a bounded cursor key context.")

    def encode(
        self,
        *,
        query: MyWorkQuery,
        as_of: datetime,
        time_zone: str,
        last: MyWorkSortTuple,
    ) -> str:
        if type(last) is not MyWorkSortTuple:
            raise _fail("last", "Enter a typed My Work sort tuple.")
        cursor = MyWorkCursor(
            as_of=as_of,
            time_zone=time_zone,
            query_fingerprint=my_work_query_fingerprint(query),
            last=last,
        )
        payload = _cursor_payload(cursor)
        encoded_payload = _base64url_encode(payload)
        signature = _base64url_encode(self._sign(payload))
        token = f"{encoded_payload}.{signature}"
        if len(token) > _MAX_CURSOR_LENGTH:
            raise _fail("cursor", "The generated cursor exceeds the API limit.")
        return token

    def decode(
        self,
        value: str,
        *,
        query: MyWorkQuery,
        expected_time_zone: str,
        expected_as_of: datetime | None = None,
    ) -> MyWorkCursor:
        try:
            if (
                type(value) is not str
                or not value
                or len(value) > _MAX_CURSOR_LENGTH
                or value.count(".") != 1
            ):
                raise ValueError
            encoded_payload, encoded_signature = value.split(".")
            payload = _base64url_decode(encoded_payload)
            signature = _base64url_decode(encoded_signature)
            if len(
                signature
            ) != hashlib.sha256().digest_size or not hmac.compare_digest(
                signature,
                self._sign(payload),
            ):
                raise ValueError
            document = json.loads(
                payload.decode("utf-8"),
                object_pairs_hook=_unique_object,
            )
            cursor = _cursor_from_document(document)
            if (
                cursor.query_fingerprint != my_work_query_fingerprint(query)
                or cursor.time_zone != _time_zone(expected_time_zone)
                or (
                    expected_as_of is not None
                    and cursor.as_of != _instant(expected_as_of, "asOf")
                )
                or _cursor_payload(cursor) != payload
                or _base64url_encode(payload) != encoded_payload
                or _base64url_encode(signature) != encoded_signature
            ):
                raise ValueError
            return cursor
        except (
            binascii.Error,
            json.JSONDecodeError,
            MyWorkValidationError,
            OverflowError,
            TypeError,
            UnicodeError,
            ValueError,
        ) as error:
            raise InvalidMyWorkCursor() from error

    def _sign(self, payload: bytes) -> bytes:
        scoped_key = hmac.new(
            self.signing_key,
            self.context,
            hashlib.sha256,
        ).digest()
        return hmac.new(scoped_key, payload, hashlib.sha256).digest()


def _cursor_payload(cursor: MyWorkCursor) -> bytes:
    return _canonical_json(
        {
            "asOf": _instant_text(cursor.as_of, "asOf"),
            "last": {
                "dueAt": (
                    None
                    if cursor.last.due_at is None
                    else _instant_text(cursor.last.due_at, "last.dueAt")
                ),
                "dueAtIsNull": cursor.last.due_at is None,
                "id": str(cursor.last.item_id),
            },
            "queryFingerprint": cursor.query_fingerprint,
            "timeZone": cursor.time_zone,
            "version": _CURSOR_VERSION,
        }
    )


def _cursor_from_document(value: object) -> MyWorkCursor:
    if (
        type(value) is not dict
        or set(value) != {"asOf", "last", "queryFingerprint", "timeZone", "version"}
        or type(value["version"]) is not int
        or value["version"] != _CURSOR_VERSION
        or type(value["last"]) is not dict
        or set(value["last"]) != {"dueAt", "dueAtIsNull", "id"}
        or type(value["last"]["dueAtIsNull"]) is not bool
    ):
        raise _fail("cursor", "Enter a valid cursor.")
    due_is_null = value["last"]["dueAtIsNull"]
    due_value = value["last"]["dueAt"]
    if due_is_null:
        if due_value is not None:
            raise _fail("cursor", "Enter a valid cursor.")
        due_at = None
    else:
        if due_value is None:
            raise _fail("cursor", "Enter a valid cursor.")
        due_at = _parse_instant(due_value, "last.dueAt")
    return MyWorkCursor(
        as_of=_parse_instant(value["asOf"], "asOf"),
        time_zone=_time_zone(value["timeZone"]),
        query_fingerprint=value["queryFingerprint"],
        last=MyWorkSortTuple(
            due_at=due_at,
            item_id=_uuid_text(value["last"]["id"], "last.id"),
        ),
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    if (
        type(value) is not str
        or not value
        or _BASE64URL_PATTERN.fullmatch(value) is None
    ):
        raise ValueError
    return base64.b64decode(
        value + ("=" * (-len(value) % 4)),
        altchars=b"-_",
        validate=True,
    )
