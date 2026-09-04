from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


QUALITY_LINK_REVISION_WRITE_FLAG = "npi_formal_quality_link_revision_write"
QUALITY_LINK_HEAD_WRITE_FLAG = "npi_formal_quality_link_head_write"
QUALITY_LINK_RECEIPT_WRITE_FLAG = "npi_formal_quality_link_receipt_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


@dataclass(frozen=True, slots=True)
class QualityLinkWriteCapability:
    actor: str
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT: ContextVar[QualityLinkWriteCapability | None] = ContextVar(
    "npi_formal_quality_link_capability",
    default=None,
)
_FLAGS = {
    "NPI Formal Quality Link Revision": QUALITY_LINK_REVISION_WRITE_FLAG,
    "NPI Formal Quality Link Head": QUALITY_LINK_HEAD_WRITE_FLAG,
    "NPI Formal Quality Link Command Idempotency": QUALITY_LINK_RECEIPT_WRITE_FLAG,
}
QUALITY_LINK_COMMAND_WRITES = frozenset(
    {
        ("NPI Formal Quality Link Revision", "insert"),
        ("NPI Formal Quality Link Head", "insert"),
        ("NPI Formal Quality Link Head", "save"),
        ("NPI Formal Quality Link Command Idempotency", "insert"),
        ("NPI Formal Quality Link Command Idempotency", "save"),
    }
)


def require_quality_link_write(doctype: str, action: str) -> None:
    capability = _CURRENT.get()
    flag = _FLAGS.get(doctype)
    if (
        flag is None
        or not getattr(frappe.flags, flag, False)
        or capability is None
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or (doctype, action) not in capability.allowed
    ):
        frappe.throw(
            _(
                "Formal quality link records can only be changed by the controlled quality-link service."
            ),
            frappe.PermissionError,
        )


def deny_quality_link_history_update() -> None:
    frappe.throw(_("Formal quality link history cannot be changed."), frappe.PermissionError)


def deny_quality_link_history_delete() -> None:
    frappe.throw(_("Formal quality link records cannot be deleted."), frappe.PermissionError)


@contextmanager
def quality_link_write_capability(
    *,
    service_actor_user_id: str,
    scope: str,
    allowed: frozenset[tuple[str, str]],
) -> Iterator[QualityLinkWriteCapability]:
    """Private request-local capability; callers cannot bypass DocType guards."""

    if not allowed or any(
        item[0] not in _FLAGS or item[1] not in {"insert", "save"}
        for item in allowed
    ):
        raise ValueError("Quality link capability is outside the closed support set.")
    _require_quality_link_service_actor(service_actor_user_id)
    capability = QualityLinkWriteCapability(
        actor=service_actor_user_id,
        scope=scope,
        allowed=allowed,
    )
    token = _CURRENT.set(capability)
    missing = object()
    previous = {
        name: getattr(frappe.flags, name, missing)
        for name in {_FLAGS[item[0]] for item in allowed}
    }
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


@contextmanager
def quality_link_command_write(
    *,
    service_actor_user_id: str,
    scope: str,
) -> Iterator[QualityLinkWriteCapability]:
    """Expose only the fixed CP2 append/head/receipt transaction write set."""

    with quality_link_write_capability(
        service_actor_user_id=service_actor_user_id,
        scope=scope,
        allowed=QUALITY_LINK_COMMAND_WRITES,
    ) as capability, _flag_scope(AUDIT_APPEND_FLAG):
        yield capability


def insert_quality_link_support_document(
    document: Any,
    *,
    capability: QualityLinkWriteCapability,
) -> Any:
    """Insert one exact quality-link support row under its active capability."""

    _authorize_quality_link_support_write(
        document,
        action="insert",
        capability=capability,
    )
    return document.insert(ignore_permissions=True)


def save_quality_link_support_document(
    document: Any,
    *,
    capability: QualityLinkWriteCapability,
) -> Any:
    """Save one exact quality-link support row under its active capability."""

    _authorize_quality_link_support_write(
        document,
        action="save",
        capability=capability,
    )
    return document.save(ignore_permissions=True)


def _require_quality_link_service_actor(service_actor_user_id: str) -> None:
    session_user = getattr(getattr(frappe, "session", None), "user", None)
    get_roles = getattr(frappe, "get_roles", None)
    if (
        not isinstance(service_actor_user_id, str)
        or not service_actor_user_id
        or service_actor_user_id != service_actor_user_id.strip()
        or service_actor_user_id.casefold() in {"guest", "administrator"}
        or session_user != service_actor_user_id
        or not callable(get_roles)
        or "NPI API User" not in set(get_roles(service_actor_user_id) or ())
    ):
        frappe.throw(
            _(
                "Formal quality link records can only be changed by the controlled quality-link service."
            ),
            frappe.PermissionError,
        )


def _authorize_quality_link_support_write(
    document: Any,
    *,
    action: str,
    capability: QualityLinkWriteCapability,
) -> None:
    doctype = str(getattr(document, "doctype", ""))
    flag = _FLAGS.get(doctype)
    if (
        _CURRENT.get() is not capability
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or (doctype, action) not in capability.allowed
        or flag is None
        or not getattr(frappe.flags, flag, False)
    ):
        frappe.throw(
            _(
                "Formal quality link records can only be changed by the controlled quality-link service."
            ),
            frappe.PermissionError,
        )


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
