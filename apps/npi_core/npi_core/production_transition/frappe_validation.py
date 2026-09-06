from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import frappe
from frappe import _


PRODUCTION_TRANSITION_COMMAND_WRITE_FLAG = "npi_production_transition_command_write"
PRODUCTION_TRANSITION_POLICY_VERSION_WRITE_FLAG = (
    "npi_production_transition_policy_version_write"
)
AUDIT_APPEND_FLAG = "npi_audit_append"


def require_production_transition_command_write() -> None:
    if not getattr(frappe.flags, PRODUCTION_TRANSITION_COMMAND_WRITE_FLAG, False):
        frappe.throw(
            _(
                "NPI production transition records can only be changed through an authorized command."
            ),
            frappe.PermissionError,
        )


def require_production_transition_policy_version_write() -> None:
    require_production_transition_command_write()
    if not getattr(
        frappe.flags,
        PRODUCTION_TRANSITION_POLICY_VERSION_WRITE_FLAG,
        False,
    ):
        frappe.throw(
            _(
                "NPI production transition policy versions can only be changed through the guarded policy repository."
            ),
            frappe.PermissionError,
        )


@contextmanager
def production_transition_command_write() -> Iterator[None]:
    with _flag_scope(PRODUCTION_TRANSITION_COMMAND_WRITE_FLAG), _flag_scope(
        AUDIT_APPEND_FLAG
    ):
        yield


@contextmanager
def production_transition_policy_version_write() -> Iterator[None]:
    with production_transition_command_write(), _flag_scope(
        PRODUCTION_TRANSITION_POLICY_VERSION_WRITE_FLAG
    ):
        yield


def deny_production_transition_history_update() -> None:
    frappe.throw(
        _("NPI production transition history cannot be changed."),
        frappe.PermissionError,
    )


def deny_production_transition_history_delete(
    _document: object | None = None,
) -> None:
    frappe.throw(
        _("NPI production transition history cannot be deleted."),
        frappe.PermissionError,
    )


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
