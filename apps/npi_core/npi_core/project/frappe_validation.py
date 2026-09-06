from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.errors import RequestValidationFailed


def ensure_uuid(value: object, field_label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        frappe.throw(
            _("{field} must be a valid UUID.").format(field=field_label),
            frappe.ValidationError,
        )


def assert_immutable_fields(document, previous, fields: Iterable[str]) -> None:
    for fieldname in fields:
        if document.get(fieldname) != previous.get(fieldname):
            frappe.throw(
                _("A protected field cannot be changed."),
                frappe.ValidationError,
            )


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def throw_domain_validation(error: RequestValidationFailed) -> None:
    """Expose a domain validation failure through the Frappe save boundary."""
    message = error.field_errors[0].get("message") if error.field_errors else None
    frappe.throw(message or _("Enter a valid value."), frappe.ValidationError)


def require_project_command_write() -> None:
    """Deny Desk/resource CRUD; only the authorized command adapter sets this flag."""
    if not getattr(frappe.flags, "npi_project_command_write", False):
        frappe.throw(
            _("Project records can only be changed through an authorized NPI project command."),
            frappe.PermissionError,
        )


def deny_standalone_child_write() -> None:
    """Force child-table mutations through the validated aggregate root."""
    frappe.throw(
        _("A child row can only be changed through its parent aggregate."),
        frappe.PermissionError,
    )


def deny_controlled_history_delete() -> None:
    """Keep Project command, snapshot, and audit history append-only."""
    frappe.throw(
        _("Controlled NPI history cannot be deleted."),
        frappe.PermissionError,
    )
