from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Iterator

import frappe
from frappe import _


def require_collaboration_write() -> None:
    if not getattr(frappe.flags, "npi_collaboration_command_write", False):
        frappe.throw(
            _("Collaboration records can only be changed by an authorized NPI operation."),
            frappe.PermissionError,
        )


def deny_collaboration_delete() -> None:
    frappe.throw(_("Controlled collaboration history cannot be deleted."), frappe.PermissionError)


def validate_uuid(value: object, label: str) -> str:
    from uuid import UUID

    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        frappe.throw(_("{field} must be a valid identifier.").format(field=label), frappe.ValidationError)
    raise AssertionError("Frappe validation must raise an exception.")


def validate_hash(value: object, label: str) -> str:
    import re

    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        frappe.throw(_("{field} must be a lowercase SHA-256 hash.").format(field=label), frappe.ValidationError)
    return value


def canonical_json(value: object, label: str, expected: type) -> tuple[object, str]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, expected):
        frappe.throw(_("{field} has an invalid structure.").format(field=label), frappe.ValidationError)
    return parsed, json.dumps(parsed, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def immutable_fields(document, fieldnames: Iterable[str]) -> None:
    previous = document.get_doc_before_save()
    if previous is None:
        return
    for fieldname in fieldnames:
        if document.get(fieldname) != previous.get(fieldname):
            frappe.throw(_("A protected field cannot be changed."), frappe.PermissionError)


def increment_version(document) -> None:
    previous = document.get_doc_before_save()
    document.optimistic_version = 1 if previous is None else int(previous.optimistic_version) + 1


@contextmanager
def collaboration_write_scope(*, audit: bool = False) -> Iterator[None]:
    flags = frappe.flags
    missing = object()
    previous_command = getattr(flags, "npi_collaboration_command_write", missing)
    previous_audit = getattr(flags, "npi_audit_append", missing)
    flags.npi_collaboration_command_write = True
    if audit:
        flags.npi_audit_append = True
    try:
        yield
    finally:
        _restore(flags, "npi_collaboration_command_write", previous_command, missing)
        if audit:
            _restore(flags, "npi_audit_append", previous_audit, missing)


def _restore(flags, name: str, previous: object, missing: object) -> None:
    if previous is missing:
        try:
            delattr(flags, name)
        except AttributeError:
            pass
    else:
        setattr(flags, name, previous)
