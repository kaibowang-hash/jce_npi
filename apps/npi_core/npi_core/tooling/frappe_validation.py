from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, TypeVar

import frappe
from frappe import _

from npi_core.foundation.errors import RequestValidationFailed


TOOLING_COMMAND_WRITE_FLAG = "npi_tooling_command_write"
AUDIT_APPEND_FLAG = "npi_audit_append"
_T = TypeVar("_T")


def require_tooling_command_write() -> None:
    if not getattr(frappe.flags, TOOLING_COMMAND_WRITE_FLAG, False):
        frappe.throw(
            _("Tooling records can only be changed through an authorized NPI command."),
            frappe.PermissionError,
        )


@contextmanager
def tooling_command_write() -> Iterator[None]:
    with _flag_scope(TOOLING_COMMAND_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
        yield


@contextmanager
def tooling_domain_validation() -> Iterator[None]:
    try:
        yield
    except RequestValidationFailed as error:
        message = error.title
        if error.field_errors:
            candidate = error.field_errors[0].get("message")
            if isinstance(candidate, str) and candidate:
                message = candidate
        frappe.throw(message, frappe.ValidationError)


def tooling_domain_value(factory: Callable[[], _T]) -> _T:
    with tooling_domain_validation():
        return factory()
    raise AssertionError("Frappe validation must raise.")


def deny_tooling_history_update() -> None:
    frappe.throw(_("Tooling history cannot be changed."), frappe.PermissionError)


def deny_tooling_history_delete(_document: object | None = None) -> None:
    frappe.throw(_("Tooling history cannot be deleted."), frappe.PermissionError)


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
