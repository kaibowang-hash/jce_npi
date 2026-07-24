from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import frappe
from frappe import _


GATE_REVIEW_COMMAND_FLAG = "npi_gate_review_command_write"

_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def ensure_uuid(value: object, field_label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError):
        frappe.throw(
            _("{field} must be a valid UUID.").format(field=field_label),
            frappe.ValidationError,
        )
    raise AssertionError("Frappe validation must raise an exception.")


def controlled_key(value: object, field_label: str) -> str:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a valid controlled key.").format(field=field_label),
            frappe.ValidationError,
        )
    return value


def lowercase_sha256(value: object, field_label: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a lowercase SHA-256 hash.").format(field=field_label),
            frappe.ValidationError,
        )
    return value


def positive_integer(value: object, field_label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        frappe.throw(
            _("{field} must be greater than zero.").format(field=field_label),
            frappe.ValidationError,
        )
    return value


def required_text(
    value: object,
    field_label: str,
    *,
    maximum: int = 2000,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > maximum
    ):
        frappe.throw(
            _("{field} must contain a valid value.").format(field=field_label),
            frappe.ValidationError,
        )
    return value.strip()


def canonical_json(
    value: object,
    field_label: str,
    *,
    expected_type: type[dict] | type[list],
) -> tuple[Any, str]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        if not isinstance(parsed, expected_type):
            raise ValueError
        encoded = json.dumps(
            parsed,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        frappe.throw(
            _("{field} must contain valid canonical JSON.").format(field=field_label),
            frappe.ValidationError,
        )
    return parsed, encoded


def canonical_json_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def canonical_datetime(value: object, field_label: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            frappe.throw(
                _("{field} must be a valid date and time.").format(field=field_label),
                frappe.ValidationError,
            )
    else:
        frappe.throw(
            _("{field} must be a valid date and time.").format(field=field_label),
            frappe.ValidationError,
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def assert_immutable_fields(
    document: object,
    previous: object,
    fields: Iterable[str],
) -> None:
    for fieldname in fields:
        if _value(document, fieldname) != _value(previous, fieldname):
            frappe.throw(
                _("A protected Gate review field cannot be changed."),
                frappe.ValidationError,
            )


def require_gate_review_command_write() -> None:
    """Deny generic Desk/resource writes to controlled Gate review history."""
    if not getattr(frappe.flags, GATE_REVIEW_COMMAND_FLAG, False):
        frappe.throw(
            _(
                "Gate review history can only be changed through an authorized NPI Gate command."
            ),
            frappe.PermissionError,
        )


def deny_gate_review_history_delete() -> None:
    """Gate review history is retained permanently, including rejected records."""
    frappe.throw(
        _("Controlled Gate review history cannot be deleted."),
        frappe.PermissionError,
    )


def _value(document: object, fieldname: str) -> object:
    getter = getattr(document, "get", None)
    if callable(getter):
        return getter(fieldname)
    return getattr(document, fieldname, None)
