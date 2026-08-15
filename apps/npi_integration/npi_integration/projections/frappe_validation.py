from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import frappe
from frappe import _


PROJECTION_OBSERVATION_WRITE_FLAG = "npi_erp_projection_observation_write"
PROJECTION_HEAD_WRITE_FLAG = "npi_erp_projection_head_write"


def require_projection_observation_write() -> None:
    if not getattr(frappe.flags, PROJECTION_OBSERVATION_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERP projection observations can only be appended by the controlled projection service."
            ),
            frappe.PermissionError,
        )


def require_projection_head_write() -> None:
    if not getattr(frappe.flags, PROJECTION_HEAD_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERP projection heads can only be changed by the controlled projection service."
            ),
            frappe.PermissionError,
        )


def deny_projection_observation_update() -> None:
    frappe.throw(
        _("ERP projection observation history cannot be changed."),
        frappe.PermissionError,
    )


def deny_projection_history_delete() -> None:
    frappe.throw(
        _("ERP projection observation and head records cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def projection_observation_write() -> Iterator[None]:
    with _flag_scope(PROJECTION_OBSERVATION_WRITE_FLAG):
        yield


@contextmanager
def projection_head_write() -> Iterator[None]:
    with _flag_scope(PROJECTION_HEAD_WRITE_FLAG):
        yield


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
