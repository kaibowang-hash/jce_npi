from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

import frappe
from frappe import _

from npi_core.documents.frappe_validation import utc_datetime_text
from npi_core.project.frappe_validation import ensure_uuid


_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,99}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


def require_grid_personalization_write() -> None:
    if not getattr(frappe.flags, "npi_grid_personalization_write", False):
        frappe.throw(
            _(
                "Grid personalization records can only be changed through an authorized NPI command."
            ),
            frappe.PermissionError,
        )


def deny_grid_personalization_delete() -> None:
    frappe.throw(
        _("Grid personalization and published view history cannot be deleted."),
        frappe.PermissionError,
    )


def normalize_uuid_fields(document, fieldnames: Iterable[str]) -> None:
    for fieldname in fieldnames:
        value = document.get(fieldname)
        if value:
            normalized = ensure_uuid(value, _label(fieldname))
            if UUID(normalized).int == 0:
                frappe.throw(
                    _("{field} must not be the nil UUID.").format(
                        field=_label(fieldname)
                    ),
                    frappe.ValidationError,
                )
            document.set(fieldname, normalized)


def require_tenant_id(value: object) -> str:
    if type(value) is not str or _TENANT_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("Tenant ID must be a valid tenant identity."),
            frappe.ValidationError,
        )
    return value


def require_positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        frappe.throw(
            _("{field} must be greater than zero.").format(field=label),
            frappe.ValidationError,
        )
    return value


def require_hash(value: object, label: str) -> str:
    if type(value) is not str or _HASH_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a lowercase SHA-256 hash.").format(field=label),
            frappe.ValidationError,
        )
    return value


def require_actor(value: object, label: str) -> str:
    if type(value) is not str or _ACTOR_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a valid user identity.").format(field=label),
            frappe.ValidationError,
        )
    return value


def require_trace_id(value: object) -> str:
    if type(value) is not str or _TRACE_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("Trace ID must be a valid trace identity."),
            frappe.ValidationError,
        )
    return value


def require_reason_code(value: object) -> str:
    if type(value) is not str or _REASON_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("Authority Reason Code must be a valid controlled key."),
            frappe.ValidationError,
        )
    return value


def canonical_utc_datetime_text(value: object, label: str) -> str:
    normalized = utc_datetime_text(value, label)
    parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    return (
        parsed.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def frappe_utc_datetime_text(value: object, label: str) -> str:
    canonical = canonical_utc_datetime_text(value, label)
    parsed = datetime.fromisoformat(canonical.replace("Z", "+00:00"))
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def require_immutable_fields(
    document,
    previous,
    fieldnames: Iterable[str],
) -> None:
    for fieldname in fieldnames:
        current_value = document.get(fieldname)
        previous_value = previous.get(fieldname)
        if fieldname.endswith("_at"):
            label = _label(fieldname)
            current_value = canonical_utc_datetime_text(
                current_value,
                label,
            )
            previous_value = canonical_utc_datetime_text(
                previous_value,
                label,
            )
        if current_value != previous_value:
            frappe.throw(
                _("A protected field cannot be changed."),
                frappe.ValidationError,
            )


def throw_domain_validation(error: Exception) -> None:
    message = getattr(error, "message", None)
    frappe.throw(
        message if isinstance(message, str) else _("Enter a valid value."),
        frappe.ValidationError,
    )


def _label(fieldname: str) -> str:
    labels = {
        "global_id": _("Global ID"),
        "project_global_id": _("Project Global ID"),
        "current_revision_global_id": _("Current Revision Global ID"),
        "published_view_global_id": _("Published View Global ID"),
        "prior_revision_global_id": _("Prior Revision Global ID"),
        "restored_from_revision_global_id": _(
            "Restored From Revision Global ID"
        ),
        "created_at": _("Created At"),
        "last_changed_at": _("Last Changed At"),
        "published_at": _("Published At"),
        "request_id": _("Request ID"),
    }
    return labels.get(fieldname, _("Global ID"))
