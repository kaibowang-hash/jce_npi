from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, TypeVar
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.errors import RequestValidationFailed


TOOLING_COMMAND_WRITE_FLAG = "npi_tooling_command_write"
TOOLING_IMPORT_ROLLBACK_TARGETS_FLAG = "npi_tooling_import_rollback_targets"
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


def tooling_import_rollback_delete_allowed(document: object) -> bool:
    """Allow only the exact target set frozen by an eligible import rollback."""

    if not getattr(frappe.flags, TOOLING_COMMAND_WRITE_FLAG, False):
        return False
    targets = getattr(frappe.flags, TOOLING_IMPORT_ROLLBACK_TARGETS_FLAG, ())
    identity = (
        str(getattr(document, "doctype", "")),
        str(getattr(document, "name", "")),
    )
    return identity in set(targets)


@contextmanager
def tooling_import_rollback_targets(
    targets: tuple[tuple[str, str], ...],
) -> Iterator[None]:
    allowed_doctypes = {
        "NPI Engineering Part",
        "NPI Engineering Part Revision",
    }
    try:
        identities_are_exact = all(
            doctype in allowed_doctypes and str(UUID(name)) == name
            for doctype, name in targets
        )
    except (TypeError, ValueError, AttributeError):
        identities_are_exact = False
    if (
        not targets
        or len(set(targets)) != len(targets)
        or not identities_are_exact
    ):
        frappe.throw(
            _("Select exact unique Tooling import rollback targets."),
            frappe.PermissionError,
        )
    with _flag_scope(TOOLING_IMPORT_ROLLBACK_TARGETS_FLAG):
        frappe.flags.npi_tooling_import_rollback_targets = tuple(targets)
        yield


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
