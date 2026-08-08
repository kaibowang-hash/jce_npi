from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import frappe
from frappe import _


TOOL_ASSET_REQUEST_WRITE_FLAG = "npi_tool_asset_request_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


def require_tool_asset_request_write() -> None:
    if not getattr(frappe.flags, TOOL_ASSET_REQUEST_WRITE_FLAG, False):
        frappe.throw(
            _("Tool Asset requests can only be changed through an authorized NPI command."),
            frappe.PermissionError,
        )


@contextmanager
def tool_asset_request_write() -> Iterator[None]:
    with _flag_scope(TOOL_ASSET_REQUEST_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
        yield


def deny_tool_asset_history_update() -> None:
    frappe.throw(_("Tool Asset request history cannot be changed."), frappe.PermissionError)


def deny_tool_asset_history_delete(_document: object | None = None) -> None:
    frappe.throw(_("Tool Asset request history cannot be deleted."), frappe.PermissionError)


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
