from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

import frappe
from frappe import _


QUALITY_LINK_REVISION_WRITE_FLAG = "npi_formal_quality_link_revision_write"
QUALITY_LINK_HEAD_WRITE_FLAG = "npi_formal_quality_link_head_write"
QUALITY_LINK_RECEIPT_WRITE_FLAG = "npi_formal_quality_link_receipt_write"


@dataclass(frozen=True, slots=True)
class QualityLinkWriteCapability:
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT: ContextVar[QualityLinkWriteCapability | None] = ContextVar("npi_formal_quality_link_capability", default=None)
_FLAGS = {
    "NPI Formal Quality Link Revision": QUALITY_LINK_REVISION_WRITE_FLAG,
    "NPI Formal Quality Link Head": QUALITY_LINK_HEAD_WRITE_FLAG,
    "NPI Formal Quality Link Command Idempotency": QUALITY_LINK_RECEIPT_WRITE_FLAG,
}


def require_quality_link_write(doctype: str, action: str) -> None:
    capability = _CURRENT.get()
    flag = _FLAGS.get(doctype)
    if flag is None or not getattr(frappe.flags, flag, False) or capability is None or (doctype, action) not in capability.allowed:
        frappe.throw(_("Formal quality link records can only be changed by the controlled quality-link service."), frappe.PermissionError)


def deny_quality_link_history_update() -> None:
    frappe.throw(_("Formal quality link history cannot be changed."), frappe.PermissionError)


def deny_quality_link_history_delete() -> None:
    frappe.throw(_("Formal quality link records cannot be deleted."), frappe.PermissionError)


@contextmanager
def quality_link_write_capability(*, scope: str, allowed: frozenset[tuple[str, str]]) -> Iterator[QualityLinkWriteCapability]:
    """Private dormant capability; checkpoint 1 has no repository caller."""

    if not allowed or any(item[0] not in _FLAGS or item[1] not in {"insert", "save"} for item in allowed):
        raise ValueError("Quality link capability is outside the closed support set.")
    capability = QualityLinkWriteCapability(scope=scope, allowed=allowed)
    token = _CURRENT.set(capability)
    missing = object()
    previous = {name: getattr(frappe.flags, name, missing) for name in {_FLAGS[item[0]] for item in allowed}}
    try:
        for name in previous:
            setattr(frappe.flags, name, True)
        yield capability
    finally:
        for name, value in previous.items():
            if value is missing:
                try:
                    delattr(frappe.flags, name)
                except AttributeError:
                    pass
            else:
                setattr(frappe.flags, name, value)
        _CURRENT.reset(token)
