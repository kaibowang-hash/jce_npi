from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import frappe
from frappe import _


INBOX_WRITE_FLAG = "npi_inbound_project_inbox_write"
SOURCE_BINDING_WRITE_FLAG = "npi_project_source_binding_write"
AUDIT_APPEND_FLAG = "npi_audit_append"
SYSTEM_SERVICE_USER = "Administrator"


def require_inbox_write() -> None:
    if not getattr(frappe.flags, INBOX_WRITE_FLAG, False):
        frappe.throw(
            _(
                "Inbound Project receipts can only be changed by the controlled integration service."
            ),
            frappe.PermissionError,
        )


def require_source_binding_write() -> None:
    if not getattr(frappe.flags, SOURCE_BINDING_WRITE_FLAG, False):
        frappe.throw(
            _(
                "Project source bindings can only be changed by the controlled integration service."
            ),
            frappe.PermissionError,
        )


def deny_legacy_inbox_update() -> None:
    frappe.throw(
        _("Legacy Inbox history cannot be promoted or changed."),
        frappe.PermissionError,
    )


def deny_inbound_project_delete() -> None:
    frappe.throw(
        _("Inbound Project receipt and source-binding history cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def inbox_write() -> Iterator[None]:
    with _flag_scope(INBOX_WRITE_FLAG):
        yield


@contextmanager
def source_binding_write() -> Iterator[None]:
    with _flag_scope(SOURCE_BINDING_WRITE_FLAG):
        yield


@contextmanager
def inbound_project_repository_write() -> Iterator[None]:
    # These support-only DocTypes intentionally grant no business CRUD. Only
    # this non-whitelisted repository scope enters the built-in system user,
    # and the caller's request/job identity is restored on every exit path.
    previous_user = getattr(frappe.session, "user", None)
    if not isinstance(previous_user, str) or not previous_user:
        raise RuntimeError("Inbound Project repository user context is unavailable.")
    switched_user = previous_user != SYSTEM_SERVICE_USER
    if switched_user:
        frappe.set_user(SYSTEM_SERVICE_USER)
    try:
        with (
            _flag_scope(INBOX_WRITE_FLAG),
            _flag_scope(SOURCE_BINDING_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield
    finally:
        if switched_user:
            frappe.set_user(previous_user)


@contextmanager
def _flag_scope(name: str) -> Iterator[None]:
    missing = object()
    previous = getattr(frappe.flags, name, missing)
    setattr(frappe.flags, name, True)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, name)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, name, previous)
