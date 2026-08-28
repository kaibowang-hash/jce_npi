from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

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


class MbomServiceActorUnavailable(RuntimeError):
    """Raised when the exact frozen MBOM service actor cannot be entered."""

_SUPPORT_WRITE_FLAGS = {
    "NPI MBOM Publish Request": MBOM_REQUEST_WRITE_FLAG,
    "NPI MBOM Publish Node": MBOM_NODE_WRITE_FLAG,
    "NPI MBOM Publish Command Idempotency": MBOM_IDEMPOTENCY_WRITE_FLAG,
    "NPI MBOM Publish Stream Guard": MBOM_STREAM_GUARD_WRITE_FLAG,
    "NPI MBOM Publish Attempt": MBOM_ATTEMPT_WRITE_FLAG,
    "NPI MBOM Publish Result": MBOM_RESULT_WRITE_FLAG,
    "NPI MBOM Publish Node Result": MBOM_RESULT_WRITE_FLAG,
    "NPI MBOM Mapping Observation": MBOM_MAPPING_WRITE_FLAG,
    "NPI MBOM Mapping Head": MBOM_MAPPING_WRITE_FLAG,
    "NPI Outbox Message": MBOM_OUTBOX_WRITE_FLAG,
}

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
_MANUAL_REPLAY_WRITES = frozenset(
    {
        ("NPI MBOM Publish Request", "save"),
        ("NPI MBOM Publish Node", "save"),
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
    _require_session_actor(requester_user_id)
    _require_internal_npi_api_user(requester_user_id)
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


def validate_mbom_service_actor(actor_user_id: str) -> None:
    """Fail closed unless the frozen actor is an enabled internal API user."""

    _require_internal_npi_api_user(actor_user_id)


@contextmanager
def mbom_service_actor_scope(service_actor_user_id: str) -> Iterator[None]:
    """Run one worker boundary as its frozen actor and always restore session."""

    try:
        _require_internal_npi_api_user(service_actor_user_id)
    except (RuntimeError, ValueError) as error:
        raise MbomServiceActorUnavailable(
            "The frozen MBOM service actor is unavailable."
        ) from error
    session = getattr(frappe, "session", None)
    previous_user = getattr(session, "user", None)
    set_user = getattr(frappe, "set_user", None)
    if not isinstance(previous_user, str) or not previous_user or not callable(set_user):
        raise MbomServiceActorUnavailable(
            "The MBOM worker user context is unavailable."
        )
    switched = previous_user != service_actor_user_id
    if switched:
        set_user(service_actor_user_id)
    try:
        yield
    finally:
        if switched:
            set_user(previous_user)


def insert_mbom_support_document(
    document: Any,
    *,
    capability: MbomSupportWriteCapability,
    ignore_links: bool = False,
) -> Any:
    """Insert one exact MBOM support row under the active capability."""

    _authorize_support_write(document, action="insert", capability=capability)
    if ignore_links and str(getattr(document, "doctype", "")) != "NPI MBOM Publish Request":
        raise RuntimeError("MBOM support insert ignore_links is outside its exact scope.")
    flags = getattr(document, "flags", None)
    previous_ignore_links = getattr(flags, "ignore_links", False) if flags else False
    if ignore_links and flags is None:
        raise RuntimeError("MBOM support insert link scope is unavailable.")
    if ignore_links:
        flags.ignore_links = True
    try:
        return document.insert(ignore_permissions=True)
    finally:
        if ignore_links:
            flags.ignore_links = previous_ignore_links


def save_mbom_support_document(
    document: Any,
    *,
    capability: MbomSupportWriteCapability,
) -> Any:
    """Save one exact MBOM support row under the active capability."""

    _authorize_support_write(document, action="save", capability=capability)
    return document.save(ignore_permissions=True)


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


@contextmanager
def mbom_manual_replay_write(
    service_actor_user_id: str,
) -> Iterator[MbomSupportWriteCapability]:
    """Authorize only a failed-retryable MBOM aggregate CAS back to queued."""

    from npi_integration.integration_operations.frappe_validation import (
        integration_operation_manual_replay,
    )

    _require_session_actor(service_actor_user_id)
    _require_internal_npi_api_user(service_actor_user_id)
    capability = _capability(
        service_actor_user_id,
        "manual_replay",
        _MANUAL_REPLAY_WRITES,
    )
    with _capability_scope(capability):
        with (
            integration_operation_manual_replay(
                actor_user_id=service_actor_user_id,
                operation_kind="publish_mbom",
            ),
            _flag_scope(MBOM_REQUEST_WRITE_FLAG),
            _flag_scope(MBOM_NODE_WRITE_FLAG),
            _flag_scope(MBOM_STREAM_GUARD_WRITE_FLAG),
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


def _authorize_support_write(
    document: Any,
    *,
    action: str,
    capability: MbomSupportWriteCapability,
) -> None:
    current = _CURRENT_CAPABILITY.get()
    if current is not capability:
        raise RuntimeError("MBOM support write capability is invalid or out of scope.")
    doctype = str(getattr(document, "doctype", ""))
    if (doctype, action) not in capability.allowed:
        raise RuntimeError("MBOM support write is outside the exact capability scope.")
    if getattr(getattr(frappe, "session", None), "user", None) != capability.actor:
        raise RuntimeError("MBOM support write actor drifted from the frozen scope.")
    flag = _SUPPORT_WRITE_FLAGS.get(doctype)
    if flag is None or not getattr(frappe.flags, flag, False):
        raise RuntimeError("MBOM support write controller flag is missing.")


def _require_session_actor(actor_user_id: str) -> None:
    if getattr(getattr(frappe, "session", None), "user", None) != actor_user_id:
        raise RuntimeError("MBOM publish authenticated requester does not match the session.")


def _require_internal_npi_api_user(actor_user_id: str) -> None:
    if not _is_internal_npi_api_user(actor_user_id):
        raise RuntimeError("MBOM publish actor is not an enabled internal NPI API User.")


def _is_internal_npi_api_user(actor_user_id: str) -> bool:
    if (
        not isinstance(actor_user_id, str)
        or not actor_user_id
        or actor_user_id.casefold() in {"guest", "administrator"}
    ):
        return False
    database = getattr(frappe, "db", None)
    get_value = getattr(database, "get_value", None)
    get_roles = getattr(frappe, "get_roles", None)
    if not callable(get_value) or not callable(get_roles):
        return False
    user = get_value(
        "User",
        actor_user_id,
        ["enabled", "user_type"],
        as_dict=True,
    )
    roles = frozenset(get_roles(actor_user_id)) if user else frozenset()
    enabled = user.get("enabled") if isinstance(user, dict) else getattr(user, "enabled", None)
    user_type = user.get("user_type") if isinstance(user, dict) else getattr(user, "user_type", None)
    return bool(
        user
        and int(enabled or 0) == 1
        and str(user_type) == "System User"
        and "NPI API User" in roles
    )


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
