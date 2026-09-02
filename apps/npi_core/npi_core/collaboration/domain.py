from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Mapping, Sequence
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps this domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


SCHEMA_VERSION = 1
MAX_MEETING_ITEMS = 50
MAX_ATTENDEES = 100
MAX_NOTIFICATION_ROWS = 5_000
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class MeetingItemKind(StrEnum):
    ACTION = "action"
    DECISION_REQUEST = "decision_request"


class NotificationKind(StrEnum):
    DUE_REMINDER = "due_reminder"
    OVERDUE_ESCALATION = "overdue_escalation"
    CRITICAL_BLOCKER = "critical_blocker"
    GATE_ATTENTION = "gate_attention"


class EmailDeliveryState(StrEnum):
    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


NOTIFICATION_TITLE_SOURCES = {
    NotificationKind.DUE_REMINDER: "Work item due soon",
    NotificationKind.OVERDUE_ESCALATION: "Work item overdue",
    NotificationKind.CRITICAL_BLOCKER: "Critical blocker requires attention",
    NotificationKind.GATE_ATTENTION: "Gate review requires attention",
}


STANDARD_MEETING_TEMPLATE = {
    "globalId": "00000000-0000-4000-8000-000000000902",
    "key": "standard_npi_review",
    "version": 1,
    "titleSource": "Standard NPI review meeting",
    "sectionKeys": ["agenda", "discussion", "decisions"],
}


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


STANDARD_MEETING_TEMPLATE_HASH = canonical_hash(STANDARD_MEETING_TEMPLATE)


def field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def text(value: object, path: str, maximum: int, *, optional: bool = False) -> str | None:
    if optional and (value is None or value == ""):
        return None
    if not isinstance(value, str):
        raise field_problem(path, _("Enter a valid value."))
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise field_problem(path, _("Enter a valid value."))
    return normalized


def long_text(value: object, path: str, maximum: int, *, optional: bool = False) -> str | None:
    if optional and (value is None or value == ""):
        return None
    if not isinstance(value, str):
        raise field_problem(path, _("Enter a valid value."))
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise field_problem(path, _("Enter a valid value."))
    return normalized


def email(value: object, path: str) -> str:
    normalized = text(value, path, 254)
    assert isinstance(normalized, str)
    normalized = normalized.casefold()
    if _EMAIL.fullmatch(normalized) is None:
        raise field_problem(path, _("Enter a valid user ID."))
    return normalized


def aware_datetime(value: object, path: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise field_problem(path, _("Enter a valid UTC date and time.")) from None
    else:
        raise field_problem(path, _("Enter a valid UTC date and time."))
    if parsed.tzinfo is None:
        raise field_problem(path, _("Enter a valid UTC date and time."))
    return parsed.astimezone(UTC)


def template_reference(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"globalId", "version", "snapshotHash"}:
        raise field_problem("templateRef", _("Select the supported meeting template."))
    expected = {
        "globalId": STANDARD_MEETING_TEMPLATE["globalId"],
        "version": STANDARD_MEETING_TEMPLATE["version"],
        "snapshotHash": STANDARD_MEETING_TEMPLATE_HASH,
    }
    if dict(value) != expected:
        raise field_problem("templateRef", _("Select the supported meeting template."))
    return expected


@dataclass(frozen=True, slots=True)
class MeetingWorkItem:
    item_key: str
    kind: MeetingItemKind
    title: str
    detail: str | None
    owner_user_id: str
    due_at: datetime
    severity: str
    blocking: bool

    @classmethod
    def parse(cls, value: object, index: int) -> MeetingWorkItem:
        path = f"items[{index}]"
        required = {
            "itemKey",
            "kind",
            "title",
            "detail",
            "ownerUserId",
            "dueAt",
            "severity",
            "blocking",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise field_problem(path, _("Enter a valid meeting action or decision."))
        item_key = text(value["itemKey"], f"{path}.itemKey", 64)
        assert isinstance(item_key, str)
        if _KEY.fullmatch(item_key) is None:
            raise field_problem(f"{path}.itemKey", _("Enter a valid controlled key."))
        try:
            kind = MeetingItemKind(str(value["kind"]))
        except ValueError:
            raise field_problem(f"{path}.kind", _("Select an action or decision request.")) from None
        severity = str(value["severity"])
        if severity not in {"low", "medium", "high", "critical"}:
            raise field_problem(f"{path}.severity", _("Select a supported severity."))
        if type(value["blocking"]) is not bool:
            raise field_problem(f"{path}.blocking", _("Select true or false."))
        title = text(value["title"], f"{path}.title", 280)
        assert isinstance(title, str)
        return cls(
            item_key=item_key,
            kind=kind,
            title=title,
            detail=long_text(value["detail"], f"{path}.detail", 4_000, optional=True),
            owner_user_id=email(value["ownerUserId"], f"{path}.ownerUserId"),
            due_at=aware_datetime(value["dueAt"], f"{path}.dueAt"),
            severity=severity,
            blocking=value["blocking"],
        )

    def parent_input(self) -> dict[str, object]:
        return {
            "actionKey": self.item_key,
            "kind": self.kind.value,
            "title": self.title,
            "detail": self.detail,
            "ownerUserId": self.owner_user_id,
            "dueAt": self.due_at,
            "severity": self.severity,
            "blocking": self.blocking,
            "parentOperation": "meeting_minute.create",
        }


@dataclass(frozen=True, slots=True)
class MeetingDraft:
    template_ref: Mapping[str, object]
    title: str
    occurred_at: datetime
    attendee_user_ids: tuple[str, ...]
    sections: Mapping[str, str]
    items: tuple[MeetingWorkItem, ...]

    @classmethod
    def parse(
        cls,
        *,
        template_ref_value: object,
        title_value: object,
        occurred_at_value: object,
        attendee_values: object,
        section_values: object,
        item_values: object,
    ) -> MeetingDraft:
        template_ref = template_reference(template_ref_value)
        if not isinstance(attendee_values, Sequence) or isinstance(attendee_values, (str, bytes)):
            raise field_problem("attendeeUserIds", _("Select meeting attendees."))
        attendees = tuple(email(value, f"attendeeUserIds[{index}]") for index, value in enumerate(attendee_values))
        if not attendees or len(attendees) > MAX_ATTENDEES or len(attendees) != len(set(attendees)):
            raise field_problem("attendeeUserIds", _("Select 1 to 100 unique meeting attendees."))
        section_keys = tuple(STANDARD_MEETING_TEMPLATE["sectionKeys"])
        if not isinstance(section_values, Mapping) or set(section_values) != set(section_keys):
            raise field_problem("sections", _("Complete every meeting template section."))
        sections: dict[str, str] = {}
        for key in section_keys:
            value = long_text(section_values[key], f"sections.{key}", 8_000)
            assert isinstance(value, str)
            sections[key] = value
        if not isinstance(item_values, Sequence) or isinstance(item_values, (str, bytes)):
            raise field_problem("items", _("Add meeting actions or decisions."))
        items = tuple(MeetingWorkItem.parse(value, index) for index, value in enumerate(item_values))
        if len(items) > MAX_MEETING_ITEMS or len({item.item_key for item in items}) != len(items):
            raise field_problem("items", _("Meeting item keys must be unique and limited to 50."))
        title = text(title_value, "title", 280)
        assert isinstance(title, str)
        return cls(
            template_ref=template_ref,
            title=title,
            occurred_at=aware_datetime(occurred_at_value, "occurredAt"),
            attendee_user_ids=attendees,
            sections=sections,
            items=items,
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "templateRef": dict(self.template_ref),
            "title": self.title,
            "occurredAt": utc_text(self.occurred_at),
            "attendeeUserIds": list(self.attendee_user_ids),
            "sections": dict(self.sections),
            "items": [
                {
                    "itemKey": item.item_key,
                    "kind": item.kind.value,
                    "title": item.title,
                    "detail": item.detail,
                    "ownerUserId": item.owner_user_id,
                    "dueAt": utc_text(item.due_at),
                    "severity": item.severity,
                    "blocking": item.blocking,
                }
                for item in self.items
            ],
        }

    def minute_content(self) -> dict[str, object]:
        snapshot = self.snapshot()
        snapshot.pop("items")
        return snapshot


def notification_kind(assignment: Mapping[str, object], now: datetime) -> tuple[NotificationKind, bool] | None:
    if not bool(assignment.get("active", True)):
        return None
    due_value = assignment.get("due_at")
    if due_value is None or due_value == "":
        return None
    due_at = aware_datetime(due_value, "dueAt")
    current = aware_datetime(now, "now")
    if bool(assignment.get("blocking")) and assignment.get("priority_value") == "critical":
        return NotificationKind.CRITICAL_BLOCKER, True
    if due_at < current:
        return NotificationKind.OVERDUE_ESCALATION, False
    if assignment.get("category") == "approval" and due_at <= current + timedelta(days=7):
        return NotificationKind.GATE_ATTENTION, False
    if due_at <= current + timedelta(days=2):
        return NotificationKind.DUE_REMINDER, False
    return None


def notification_bucket(kind: NotificationKind, now: datetime, due_at: datetime) -> str:
    if kind is NotificationKind.OVERDUE_ESCALATION:
        return aware_datetime(now, "now").date().isoformat()
    return aware_datetime(due_at, "dueAt").date().isoformat()


def preference_email_kinds(value: object) -> tuple[NotificationKind, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise field_problem("emailKinds", _("Select supported notification email types."))
    allowed = {
        NotificationKind.DUE_REMINDER,
        NotificationKind.OVERDUE_ESCALATION,
        NotificationKind.GATE_ATTENTION,
    }
    try:
        result = tuple(NotificationKind(str(item)) for item in value)
    except ValueError:
        raise field_problem("emailKinds", _("Select supported notification email types.")) from None
    if any(item not in allowed for item in result) or len(result) != len(set(result)):
        raise field_problem("emailKinds", _("Select unique non-critical notification email types."))
    return tuple(sorted(result, key=str))


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
