from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date

import frappe
from frappe import _

from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    ensure_uuid,
)


_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")


def require_project_work_command_write() -> None:
    """Deny Desk/resource writes to command-owned Project work records."""
    if not getattr(frappe.flags, "npi_project_work_command_write", False):
        frappe.throw(
            _(
                "Project work records can only be changed through an authorized NPI project command."
            ),
            frappe.PermissionError,
        )


def deny_project_work_history_delete() -> None:
    frappe.throw(
        _("Controlled Project work history cannot be deleted."),
        frappe.PermissionError,
    )


def normalize_uuid_fields(document, fieldnames: Iterable[str]) -> None:
    for fieldname in fieldnames:
        value = document.get(fieldname)
        if value:
            document.set(fieldname, ensure_uuid(value, _field_label(fieldname)))


def validate_project_identity(document) -> None:
    normalize_uuid_fields(document, ("global_id", "project_global_id"))
    if not document.tenant_id:
        frappe.throw(_("Tenant ID is required."), frappe.ValidationError)


def validate_key(value: object, label_source: str) -> str:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a valid controlled key.").format(
                field=label_source
            ),
            frappe.ValidationError,
        )
    return value


def validate_hash(value: object, label_source: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a lowercase SHA-256 hash.").format(
                field=label_source
            ),
            frappe.ValidationError,
        )
    return value


def validate_actor_identity(value: object) -> str:
    if not isinstance(value, str) or _ACTOR_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("Enter a valid value."),
            frappe.ValidationError,
        )
    return value


def validate_date_bounds(
    start_value: object,
    end_value: object,
    *,
    start_label: str,
    end_label: str,
) -> None:
    if not start_value or not end_value:
        return
    start = _date_value(start_value, start_label)
    end = _date_value(end_value, end_label)
    if end < start:
        frappe.throw(
            _(
                "{end_field} cannot be earlier than {start_field}."
            ).format(
                end_field=end_label,
                start_field=start_label,
            ),
            frappe.ValidationError,
        )


def advance_version(
    document,
    *,
    immutable_fields: Iterable[str],
) -> None:
    previous = document.get_doc_before_save()
    if previous is None:
        document.optimistic_version = 1
        return
    assert_immutable_fields(document, previous, immutable_fields)
    document.optimistic_version = int(previous.optimistic_version) + 1


def _date_value(value: object, label_source: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        frappe.throw(
            _("{field} must be a valid date.").format(field=label_source),
            frappe.ValidationError,
        )
    raise AssertionError("Frappe validation must raise an exception.")


def _field_label(fieldname: str) -> str:
    labels = {
        "global_id": _("Global ID"),
        "project_global_id": _("Project Global ID"),
        "policy_global_id": _("Policy Global ID"),
        "member_global_id": _("Member Global ID"),
        "original_member_global_id": _("Original Member Global ID"),
        "substitute_member_global_id": _("Substitute Member Global ID"),
        "context_global_id": _("Context Global ID"),
        "parent_global_id": _("Parent WBS Global ID"),
        "predecessor_global_id": _("Predecessor WBS Global ID"),
        "successor_global_id": _("Successor WBS Global ID"),
        "stage_global_id": _("Stage Global ID"),
        "work_policy_global_id": _("Work Policy Global ID"),
    }
    return labels.get(fieldname, _("Global ID"))
