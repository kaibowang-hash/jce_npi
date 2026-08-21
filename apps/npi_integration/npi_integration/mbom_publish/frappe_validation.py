from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

import frappe
from frappe import _


MBOM_OUTBOX_WRITE_FLAG = "npi_mbom_outbox_write"
MBOM_REQUEST_WRITE_FLAG = "npi_mbom_publish_request_write"
MBOM_NODE_WRITE_FLAG = "npi_mbom_publish_node_write"
MBOM_IDEMPOTENCY_WRITE_FLAG = "npi_mbom_publish_idempotency_write"
MBOM_STREAM_GUARD_WRITE_FLAG = "npi_mbom_publish_stream_guard_write"
MBOM_ATTEMPT_WRITE_FLAG = "npi_mbom_publish_attempt_write"
MBOM_RESULT_WRITE_FLAG = "npi_mbom_publish_result_write"
MBOM_MAPPING_WRITE_FLAG = "npi_mbom_mapping_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


@dataclass(frozen=True, slots=True)
class MbomSupportWriteCapability:
    """Opaque capability for one bounded MBOM support-DocType write scope."""

    actor: str
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT_CAPABILITY: ContextVar[MbomSupportWriteCapability | None] = ContextVar(
    "npi_mbom_support_write_capability",
    default=None,
)

_REQUEST_WRITES = frozenset(
    {
        ("NPI MBOM Publish Request", "insert"),
        ("NPI MBOM Publish Node", "insert"),
        ("NPI MBOM Publish Command Idempotency", "insert"),
        ("NPI MBOM Publish Stream Guard", "insert"),
        ("NPI MBOM Publish Stream Guard", "save"),
        ("NPI Outbox Message", "insert"),
    }
)
_CLAIM_WRITES = frozenset(
    {
        ("NPI MBOM Publish Request", "save"),
        ("NPI MBOM Publish Node", "save"),
        ("NPI MBOM Publish Attempt", "insert"),
        ("NPI MBOM Publish Attempt", "save"),
        ("NPI MBOM Publish Stream Guard", "save"),
        ("NPI Outbox Message", "save"),
    }
)
_RESULT_WRITES = frozenset(
    {
        ("NPI MBOM Publish Request", "save"),
        ("NPI MBOM Publish Node", "save"),
        ("NPI MBOM Publish Attempt", "save"),
        ("NPI MBOM Publish Result", "insert"),
        ("NPI MBOM Publish Node Result", "insert"),
        ("NPI MBOM Mapping Observation", "insert"),
        ("NPI MBOM Mapping Head", "insert"),
        ("NPI MBOM Mapping Head", "save"),
        ("NPI MBOM Publish Stream Guard", "save"),
        ("NPI Outbox Message", "save"),
    }
)


def require_mbom_outbox_write() -> None:
    _require_flag(
        MBOM_OUTBOX_WRITE_FLAG,
        _("MBOM publish Outbox messages can only be changed by the controlled MBOM execution service."),
    )


def require_mbom_request_write() -> None:
    _require_flag(
        MBOM_REQUEST_WRITE_FLAG,
        _("MBOM publish requests can only be changed through an authorized NPI command."),
    )


def require_mbom_node_write() -> None:
    _require_flag(
        MBOM_NODE_WRITE_FLAG,
        _("MBOM publish nodes can only be changed through the controlled MBOM execution service."),
    )


def require_mbom_idempotency_write() -> None:
    _require_flag(
        MBOM_IDEMPOTENCY_WRITE_FLAG,
        _("MBOM publish idempotency records can only be changed through an authorized NPI command."),
    )


def require_mbom_stream_guard_write() -> None:
    _require_flag(
        MBOM_STREAM_GUARD_WRITE_FLAG,
        _("MBOM publish stream guards can only be changed by the controlled MBOM execution service."),
    )


def require_mbom_attempt_write() -> None:
    _require_flag(
        MBOM_ATTEMPT_WRITE_FLAG,
        _("MBOM publish attempts can only be changed by the controlled MBOM execution service."),
    )


def require_mbom_result_write() -> None:
    _require_flag(
        MBOM_RESULT_WRITE_FLAG,
        _("MBOM publish results can only be appended by the controlled MBOM execution service."),
    )


def require_mbom_mapping_write() -> None:
    _require_flag(
        MBOM_MAPPING_WRITE_FLAG,
        _("MBOM mapping records can only be changed by the controlled MBOM execution service."),
    )


def deny_mbom_history_update() -> None:
    frappe.throw(
        _("MBOM publish execution history cannot be changed."),
        frappe.PermissionError,
    )


def deny_mbom_history_delete() -> None:
    frappe.throw(
        _("MBOM publish execution history cannot be deleted."),
        frappe.PermissionError,
    )


def deny_outbox_operation_conversion() -> None:
    frappe.throw(
        _("Outbox messages cannot be converted between Item and MBOM execution."),
        frappe.PermissionError,
    )


def require_mbom_capability(doctype: str, action: str) -> None:
    capability = _CURRENT_CAPABILITY.get()
    if capability is None or (doctype, action) not in capability.allowed:
        frappe.throw(
            _("This MBOM support record is outside the active execution capability."),
            frappe.PermissionError,
        )


@contextmanager
def mbom_request_transaction_write(
    requester_user_id: str,
) -> Iterator[MbomSupportWriteCapability]:
    capability = _capability(requester_user_id, "request", _REQUEST_WRITES)
    with _capability_scope(capability):
        with (
            _flag_scope(MBOM_REQUEST_WRITE_FLAG),
            _flag_scope(MBOM_NODE_WRITE_FLAG),
            _flag_scope(MBOM_IDEMPOTENCY_WRITE_FLAG),
            _flag_scope(MBOM_STREAM_GUARD_WRITE_FLAG),
            _flag_scope(MBOM_OUTBOX_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability


@contextmanager
def mbom_claim_write(
    service_actor_user_id: str,
) -> Iterator[MbomSupportWriteCapability]:
    capability = _capability(service_actor_user_id, "claim", _CLAIM_WRITES)
    with _capability_scope(capability):
        with (
            _flag_scope(MBOM_REQUEST_WRITE_FLAG),
            _flag_scope(MBOM_NODE_WRITE_FLAG),
            _flag_scope(MBOM_STREAM_GUARD_WRITE_FLAG),
            _flag_scope(MBOM_ATTEMPT_WRITE_FLAG),
            _flag_scope(MBOM_OUTBOX_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability


@contextmanager
def mbom_result_transaction_write(
    service_actor_user_id: str,
) -> Iterator[MbomSupportWriteCapability]:
    capability = _capability(service_actor_user_id, "result", _RESULT_WRITES)
    with _capability_scope(capability):
        with (
            _flag_scope(MBOM_REQUEST_WRITE_FLAG),
            _flag_scope(MBOM_NODE_WRITE_FLAG),
            _flag_scope(MBOM_STREAM_GUARD_WRITE_FLAG),
            _flag_scope(MBOM_ATTEMPT_WRITE_FLAG),
            _flag_scope(MBOM_RESULT_WRITE_FLAG),
            _flag_scope(MBOM_MAPPING_WRITE_FLAG),
            _flag_scope(MBOM_OUTBOX_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability


def _capability(
    actor: str,
    scope: str,
    allowed: frozenset[tuple[str, str]],
) -> MbomSupportWriteCapability:
    if (
        not isinstance(actor, str)
        or not actor
        or actor != actor.strip()
        or actor.casefold() in {"guest", "administrator"}
    ):
        frappe.throw(
            _("The MBOM execution actor is unavailable."),
            frappe.PermissionError,
        )
    return MbomSupportWriteCapability(actor=actor, scope=scope, allowed=allowed)


@contextmanager
def _capability_scope(
    capability: MbomSupportWriteCapability,
) -> Iterator[None]:
    token = _CURRENT_CAPABILITY.set(capability)
    try:
        yield
    finally:
        _CURRENT_CAPABILITY.reset(token)


def _require_flag(name: str, message: str) -> None:
    if not getattr(frappe.flags, name, False):
        frappe.throw(message, frappe.PermissionError)


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
