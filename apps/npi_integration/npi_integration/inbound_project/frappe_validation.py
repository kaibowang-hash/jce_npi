from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


INBOX_WRITE_FLAG = "npi_inbound_project_inbox_write"
SOURCE_BINDING_WRITE_FLAG = "npi_project_source_binding_write"
AUDIT_APPEND_FLAG = "npi_audit_append"
SYSTEM_SERVICE_USER = "Administrator"


@dataclass(frozen=True, slots=True)
class InboundProjectReplayWriteCapability:
    actor: str
    receipt_id: str


_CURRENT_REPLAY: ContextVar[InboundProjectReplayWriteCapability | None] = ContextVar(
    "npi_inbound_project_replay_capability",
    default=None,
)


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
def inbound_project_manual_replay_write(
    *,
    actor_user_id: str,
    receipt_id: str,
) -> Iterator[InboundProjectReplayWriteCapability]:
    """Authorize one actor-bound failed-retryable Inbox CAS without Admin fallback."""

    from npi_integration.integration_operations.frappe_validation import (
        integration_operation_manual_replay,
    )

    session_user = getattr(getattr(frappe, "session", None), "user", None)
    database = getattr(frappe, "db", None)
    get_value = getattr(database, "get_value", None)
    roles = set(frappe.get_roles(actor_user_id) or ())
    user = (
        get_value("User", actor_user_id, ["enabled", "user_type"], as_dict=True)
        if callable(get_value)
        else None
    )
    enabled = user.get("enabled") if isinstance(user, dict) else getattr(user, "enabled", None)
    user_type = (
        user.get("user_type")
        if isinstance(user, dict)
        else getattr(user, "user_type", None)
    )
    if (
        session_user != actor_user_id
        or actor_user_id.casefold() in {"guest", "administrator"}
        or not user
        or int(enabled or 0) != 1
        or str(user_type) != "System User"
        or "NPI API User" not in roles
    ):
        frappe.throw(
            _(
                "Inbound Project replay can only be requested by the controlled integration service."
            ),
            frappe.PermissionError,
        )
    capability = InboundProjectReplayWriteCapability(
        actor=actor_user_id,
        receipt_id=receipt_id,
    )
    token = _CURRENT_REPLAY.set(capability)
    try:
        with (
            integration_operation_manual_replay(
                actor_user_id=actor_user_id,
                operation_kind="receive_project_submission",
            ),
            _flag_scope(INBOX_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability
    finally:
        _CURRENT_REPLAY.reset(token)


def save_inbound_project_replay_document(
    document: Any,
    *,
    capability: InboundProjectReplayWriteCapability,
) -> Any:
    current = _CURRENT_REPLAY.get()
    if current is not capability:
        raise RuntimeError("Inbound Project replay capability is out of scope.")
    if (
        str(getattr(document, "doctype", "")) != "NPI Inbox Message"
        or str(getattr(document, "name", "")) != capability.receipt_id
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or not getattr(frappe.flags, INBOX_WRITE_FLAG, False)
    ):
        raise RuntimeError("Inbound Project replay write is outside its exact scope.")
    return document.save(ignore_permissions=True)


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
