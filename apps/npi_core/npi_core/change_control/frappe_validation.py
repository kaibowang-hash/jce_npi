from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterable, Iterator
from uuid import UUID

import frappe
from frappe import _


CHANGE_COMMAND_WRITE_FLAG = "npi_change_control_command_write"
CHANGE_OBSERVATION_WRITE_FLAG = "npi_change_control_observation_write"
AUDIT_APPEND_FLAG = "npi_audit_append"
_HASH = re.compile(r"^[0-9a-f]{64}$")


def require_change_command_write() -> None:
    if not getattr(frappe.flags, CHANGE_COMMAND_WRITE_FLAG, False):
        frappe.throw(
            _(
                "Engineering change records can only be changed through an authorized command."
            ),
            frappe.PermissionError,
        )


def require_change_observation_write() -> None:
    require_change_command_write()
    if not getattr(frappe.flags, CHANGE_OBSERVATION_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERP engineering change observations can only be linked by the authorized integration service."
            ),
            frappe.PermissionError,
        )


@contextmanager
def change_command_write() -> Iterator[None]:
    with _flag_scope(CHANGE_COMMAND_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
        yield


@contextmanager
def change_observation_write() -> Iterator[None]:
    with change_command_write(), _flag_scope(CHANGE_OBSERVATION_WRITE_FLAG):
        yield


def deny_change_history_update() -> None:
    frappe.throw(
        _("Engineering change history cannot be changed."),
        frappe.PermissionError,
    )


def deny_change_history_delete(_document: object | None = None) -> None:
    frappe.throw(
        _("Engineering change history cannot be deleted."),
        frappe.PermissionError,
    )


def canonical_uuid(value: object, label: str) -> str:
    try:
        normalized = str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        frappe.throw(
            _("{field} must be a valid global ID.").format(field=label),
            frappe.ValidationError,
        )
    if normalized == str(UUID(int=0)) or str(value) != normalized:
        frappe.throw(
            _("{field} must be a canonical global ID.").format(field=label),
            frappe.ValidationError,
        )
    return normalized


def optional_uuid(value: object, label: str) -> str | None:
    return None if value in (None, "") else canonical_uuid(value, label)


def required_text(value: object, label: str, maximum: int = 140) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        frappe.throw(
            _("{field} must be a valid value.").format(field=label),
            frappe.ValidationError,
        )
    return value.strip()


def lowercase_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a lowercase SHA-256 hash.").format(field=label),
            frappe.ValidationError,
        )
    return value


def optional_sha256(value: object, label: str) -> str | None:
    return None if value in (None, "") else lowercase_sha256(value, label)


def positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        frappe.throw(
            _("{field} must be greater than zero.").format(field=label),
            frappe.ValidationError,
        )
    return value


def utc_datetime_text(value: object, label: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
    else:
        parsed = None
    if parsed is None:
        frappe.throw(
            _("{field} must be a valid date and time.").format(field=label),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: object, label: str, expected: type) -> tuple[object, str]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, expected):
        frappe.throw(
            _("{field} must be valid canonical JSON.").format(field=label),
            frappe.ValidationError,
        )
    return parsed, json.dumps(
        parsed,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def sha256_json(value: object) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assert_immutable_fields(
    document: object,
    previous: object,
    fields: Iterable[str],
) -> None:
    for fieldname in fields:
        if getattr(document, fieldname, None) != getattr(previous, fieldname, None):
            deny_change_history_update()


@contextmanager
def _flag_scope(flag_name: str) -> Iterator[None]:
    missing = object()
    previous = getattr(frappe.flags, flag_name, missing)
    setattr(frappe.flags, flag_name, True)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, flag_name)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, flag_name, previous)
