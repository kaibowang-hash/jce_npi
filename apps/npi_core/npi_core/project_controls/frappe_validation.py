from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    ensure_uuid,
    sha256_json,
)


_CONTROLLED_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")


def require_project_control_write() -> None:
    if not getattr(frappe.flags, "npi_project_control_command_write", False):
        frappe.throw(
            _(
                "Project control records can only be changed through an authorized NPI project command."
            ),
            frappe.PermissionError,
        )


def require_my_work_projection_write() -> None:
    if not getattr(frappe.flags, "npi_my_work_projection_write", False):
        frappe.throw(
            _(
                "My Work assignments can only be changed by the controlled projection service."
            ),
            frappe.PermissionError,
        )


def deny_project_control_history_delete() -> None:
    frappe.throw(
        _("Controlled Project activity and governance history cannot be deleted."),
        frappe.PermissionError,
    )


def deny_my_work_projection_delete() -> None:
    frappe.throw(
        _(
            "My Work projection records are retained and deactivated instead of deleted."
        ),
        frappe.PermissionError,
    )


def normalize_uuid_fields(document, fieldnames: Iterable[str]) -> None:
    for fieldname in fieldnames:
        value = document.get(fieldname)
        if value:
            document.set(
                fieldname,
                ensure_uuid(value, _field_label(fieldname)),
            )


def require_positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        frappe.throw(
            _("{field} must be greater than zero.").format(field=label),
            frappe.ValidationError,
        )
    return value


def require_nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        frappe.throw(
            _("{field} cannot be negative.").format(field=label),
            frappe.ValidationError,
        )
    return value


def require_text(
    value: object,
    label: str,
    *,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        frappe.throw(
            _("{field} must be valid text.").format(field=label),
            frappe.ValidationError,
        )
    normalized = value.strip()
    if (not normalized and not allow_empty) or len(normalized) > maximum:
        frappe.throw(
            _("{field} must be valid text.").format(field=label),
            frappe.ValidationError,
        )
    return normalized


def require_controlled_key(value: object, label: str) -> str:
    normalized = require_text(value, label, maximum=64)
    if _CONTROLLED_KEY_PATTERN.fullmatch(normalized) is None:
        frappe.throw(
            _("{field} must be a valid controlled key.").format(field=label),
            frappe.ValidationError,
        )
    return normalized


def require_actor(value: object, label: str) -> str:
    if not isinstance(value, str) or _ACTOR_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a valid user identity.").format(field=label),
            frappe.ValidationError,
        )
    return value.casefold() if "@" in value else value


def require_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a lowercase SHA-256 hash.").format(field=label),
            frappe.ValidationError,
        )
    return value


def require_request_id(value: object) -> str:
    return ensure_uuid(value, _("Request ID"))


def require_trace_id(value: object) -> str:
    if not isinstance(value, str) or _TRACE_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("Trace ID must be a valid trace identity."),
            frappe.ValidationError,
        )
    return value


def canonical_datetime(value: object, label: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00").replace(" ", "T")
            )
        except ValueError:
            parsed = None
    else:
        parsed = None
    if parsed is None:
        frappe.throw(
            _("{field} must be a valid date and time.").format(field=label),
            frappe.ValidationError,
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (
        parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def json_value(
    value: object,
    *,
    expected_type: type,
    label: str,
) -> list[Any] | dict[str, Any]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, expected_type):
        expected = _("a JSON array") if expected_type is list else _("a JSON object")
        frappe.throw(
            _("{field} must be {expected}.").format(
                field=label,
                expected=expected,
            ),
            frappe.ValidationError,
        )
    return parsed


def canonicalize_json(
    value: object,
    *,
    expected_type: type,
    label: str,
) -> tuple[list[Any] | dict[str, Any], str]:
    parsed = json_value(value, expected_type=expected_type, label=label)
    return parsed, canonical_json(parsed)


def require_snapshot_hash(snapshot: object, snapshot_hash: object, label: str) -> str:
    actual = require_hash(snapshot_hash, label)
    if sha256_json(snapshot) != actual:
        frappe.throw(
            _("{field} does not match its canonical snapshot.").format(field=label),
            frappe.ValidationError,
        )
    return actual


def require_immutable_update(
    document,
    previous,
    fieldnames: Iterable[str],
) -> None:
    assert_immutable_fields(document, previous, fieldnames)


def _field_label(fieldname: str) -> str:
    labels = {
        "global_id": _("Global ID"),
        "record_id": _("Record ID"),
        "project_global_id": _("Project Global ID"),
        "policy_global_id": _("Policy Global ID"),
        "source_global_id": _("Source Global ID"),
        "template_global_id": _("Template Global ID"),
        "control_binding_global_id": _("Project Control Binding Global ID"),
        "current_health_assessment_global_id": _("Current Health Assessment Global ID"),
    }
    return labels.get(fieldname, _("Global ID"))
