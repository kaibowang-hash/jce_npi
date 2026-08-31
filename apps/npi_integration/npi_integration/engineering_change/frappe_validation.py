from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

import frappe
from frappe import _


INBOX_WRITE_FLAG = "npi_engineering_change_inbox_write"
REQUEST_WRITE_FLAG = "npi_engineering_change_summary_request_write"
OUTBOX_WRITE_FLAG = "npi_engineering_change_summary_outbox_write"
ATTEMPT_WRITE_FLAG = "npi_engineering_change_summary_attempt_write"
RESULT_WRITE_FLAG = "npi_engineering_change_summary_result_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


@dataclass(frozen=True, slots=True)
class ChangeIntegrationWriteCapability:
    actor: str
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT: ContextVar[ChangeIntegrationWriteCapability | None] = ContextVar(
    "npi_engineering_change_integration_capability", default=None
)
_FLAGS = {
    "NPI Engineering Change Inbox": INBOX_WRITE_FLAG,
    "NPI Engineering Change Summary Request": REQUEST_WRITE_FLAG,
    "NPI Engineering Change Summary Outbox": OUTBOX_WRITE_FLAG,
    "NPI Engineering Change Summary Attempt": ATTEMPT_WRITE_FLAG,
    "NPI Engineering Change Summary Result": RESULT_WRITE_FLAG,
}
_INBOUND = frozenset({("NPI Engineering Change Inbox", "insert"), ("NPI Engineering Change Inbox", "save")})
_REQUEST = frozenset({("NPI Engineering Change Summary Request", "insert"), ("NPI Engineering Change Summary Outbox", "insert")})
_CLAIM = frozenset({
    ("NPI Engineering Change Summary Request", "save"),
    ("NPI Engineering Change Summary Outbox", "save"),
    ("NPI Engineering Change Summary Attempt", "insert"),
    ("NPI Engineering Change Summary Attempt", "save"),
})
_RESULT = frozenset({
    ("NPI Engineering Change Summary Request", "save"),
    ("NPI Engineering Change Summary Outbox", "save"),
    ("NPI Engineering Change Summary Attempt", "save"),
    ("NPI Engineering Change Summary Result", "insert"),
})


def require_inbox_write(action: str) -> None:
    _require_write(
        "NPI Engineering Change Inbox",
        action,
        INBOX_WRITE_FLAG,
        _("Engineering Change Inbox history can only be changed by the authenticated intake service."),
    )


def require_request_write(action: str) -> None:
    _require_write(
        "NPI Engineering Change Summary Request",
        action,
        REQUEST_WRITE_FLAG,
        _("Engineering Change summary requests can only be changed through an authorized command."),
    )


def require_outbox_write(action: str) -> None:
    _require_write(
        "NPI Engineering Change Summary Outbox",
        action,
        OUTBOX_WRITE_FLAG,
        _("Engineering Change summary Outbox messages can only be changed by the controlled execution service."),
    )


def require_attempt_write(action: str) -> None:
    _require_write(
        "NPI Engineering Change Summary Attempt",
        action,
        ATTEMPT_WRITE_FLAG,
        _("Engineering Change summary attempts can only be changed by the controlled execution service."),
    )


def require_result_write(action: str) -> None:
    _require_write(
        "NPI Engineering Change Summary Result",
        action,
        RESULT_WRITE_FLAG,
        _("Engineering Change summary results can only be appended by the controlled execution service."),
    )


def deny_history_update() -> None:
    frappe.throw(_("Engineering Change integration history cannot be changed."), frappe.PermissionError)


def deny_history_delete() -> None:
    frappe.throw(_("Engineering Change integration history cannot be deleted."), frappe.PermissionError)


@contextmanager
def service_actor_scope(actor: str) -> Iterator[None]:
    _require_internal_actor(actor)
    previous = str(getattr(frappe.session, "user", ""))
    frappe.set_user(actor)
    try:
        _require_session_actor(actor)
        yield
    finally:
        frappe.set_user(previous)


@contextmanager
def inbound_transaction_write(actor: str) -> Iterator[ChangeIntegrationWriteCapability]:
    with _write_scope(actor, "inbound", _INBOUND, (INBOX_WRITE_FLAG, AUDIT_APPEND_FLAG)) as capability:
        yield capability


@contextmanager
def summary_request_write(actor: str) -> Iterator[ChangeIntegrationWriteCapability]:
    with _write_scope(
        actor,
        "request",
        _REQUEST,
        (REQUEST_WRITE_FLAG, OUTBOX_WRITE_FLAG, AUDIT_APPEND_FLAG),
        service_actor=False,
    ) as capability:
        yield capability


@contextmanager
def summary_claim_write(actor: str) -> Iterator[ChangeIntegrationWriteCapability]:
    with _write_scope(actor, "claim", _CLAIM, (REQUEST_WRITE_FLAG, OUTBOX_WRITE_FLAG, ATTEMPT_WRITE_FLAG, AUDIT_APPEND_FLAG)) as capability:
        yield capability


@contextmanager
def summary_result_write(actor: str) -> Iterator[ChangeIntegrationWriteCapability]:
    with _write_scope(actor, "result", _RESULT, (REQUEST_WRITE_FLAG, OUTBOX_WRITE_FLAG, ATTEMPT_WRITE_FLAG, RESULT_WRITE_FLAG, AUDIT_APPEND_FLAG)) as capability:
        yield capability


def assert_capability(capability: ChangeIntegrationWriteCapability, doctype: str, action: str) -> None:
    current = _CURRENT.get()
    if current is not capability or (doctype, action) not in capability.allowed or _FLAGS.get(doctype) is None:
        frappe.throw(_("Engineering Change integration write authority is invalid."), frappe.PermissionError)
    _require_session_actor(capability.actor)


@contextmanager
def _write_scope(
    actor: str,
    scope: str,
    allowed: frozenset[tuple[str, str]],
    flags: tuple[str, ...],
    *,
    service_actor: bool = True,
) -> Iterator[ChangeIntegrationWriteCapability]:
    _require_session_actor(actor)
    if service_actor:
        _require_internal_actor(actor)
    else:
        _require_request_actor(actor)
    capability = ChangeIntegrationWriteCapability(actor, scope, allowed)
    token = _CURRENT.set(capability)
    previous: list[tuple[str, object]] = []
    missing = object()
    try:
        for flag in flags:
            value = getattr(frappe.flags, flag, missing)
            previous.append((flag, value))
            setattr(frappe.flags, flag, True)
        yield capability
    finally:
        for flag, value in reversed(previous):
            if value is missing:
                delattr(frappe.flags, flag)
            else:
                setattr(frappe.flags, flag, value)
        _CURRENT.reset(token)


def _require_flag(flag: str, message: str) -> None:
    if getattr(frappe.flags, flag, False) is not True:
        frappe.throw(message, frappe.PermissionError)


def _require_write(doctype: str, action: str, flag: str, message: str) -> None:
    _require_flag(flag, message)
    capability = _CURRENT.get()
    if capability is None:
        frappe.throw(message, frappe.PermissionError)
    assert_capability(capability, doctype, action)


def _require_session_actor(actor: str) -> None:
    if not isinstance(actor, str) or str(getattr(frappe.session, "user", "")).casefold() != actor.casefold():
        frappe.throw(_("The Engineering Change integration actor is unavailable."), frappe.PermissionError)


def _require_internal_actor(actor: str) -> None:
    if not isinstance(actor, str) or not actor or actor.casefold() in {"guest", "administrator"}:
        frappe.throw(_("The Engineering Change integration actor is invalid."), frappe.PermissionError)
    roles = {str(value) for value in frappe.get_roles(actor)}
    if "NPI API User" not in roles or "System Manager" not in roles:
        frappe.throw(_("The Engineering Change integration actor lacks the required role."), frappe.PermissionError)


def _require_request_actor(actor: str) -> None:
    if not isinstance(actor, str) or not actor or actor.casefold() in {"guest", "administrator"}:
        frappe.throw(_("The Engineering Change integration actor is invalid."), frappe.PermissionError)
    if "NPI API User" not in {str(value) for value in frappe.get_roles(actor)}:
        frappe.throw(
            _("The Engineering Change integration actor lacks the required role."),
            frappe.PermissionError,
        )
