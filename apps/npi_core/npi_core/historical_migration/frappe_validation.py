from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

import frappe
from frappe import _


_write_scope: ContextVar[bool] = ContextVar(
    "npi_historical_migration_write_scope", default=False
)


@contextmanager
def historical_migration_write() -> Iterator[None]:
    missing = object()
    previous_audit = getattr(frappe.flags, "npi_audit_append", missing)
    frappe.flags.npi_audit_append = True
    token: Token[bool] = _write_scope.set(True)
    try:
        yield
    finally:
        _write_scope.reset(token)
        if previous_audit is missing:
            try:
                delattr(frappe.flags, "npi_audit_append")
            except AttributeError:
                pass
        else:
            frappe.flags.npi_audit_append = previous_audit


def require_historical_migration_write() -> None:
    if _write_scope.get() is not True:
        frappe.throw(
            _("Historical migration records can only change through the governed commands."),
            frappe.PermissionError,
        )


def deny_historical_migration_delete() -> None:
    frappe.throw(
        _("Historical migration evidence cannot be deleted."),
        frappe.PermissionError,
    )
