from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


ITEM_OUTBOX_WRITE_FLAG = "npi_item_outbox_write"
ITEM_REQUEST_WRITE_FLAG = "npi_item_publish_request_write"
ITEM_IDEMPOTENCY_WRITE_FLAG = "npi_item_publish_idempotency_write"
ITEM_ATTEMPT_WRITE_FLAG = "npi_item_publish_attempt_write"
ITEM_RESULT_WRITE_FLAG = "npi_item_publish_result_write"
ITEM_MAPPING_WRITE_FLAG = "npi_item_mapping_write"
ITEM_STREAM_GUARD_WRITE_FLAG = "npi_item_publish_stream_guard_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


@dataclass(frozen=True, slots=True)
class ItemSupportWriteCapability:
    """Opaque capability for one bounded support-DocType write scope."""

    actor: str
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT_SUPPORT_CAPABILITY: ContextVar[
    ItemSupportWriteCapability | None
] = ContextVar("npi_item_support_write_capability", default=None)
_SUPPORT_WRITE_FLAGS = {
    "NPI Item Publish Request": ITEM_REQUEST_WRITE_FLAG,
    "NPI Item Publish Command Idempotency": ITEM_IDEMPOTENCY_WRITE_FLAG,
    "NPI Outbox Message": ITEM_OUTBOX_WRITE_FLAG,
    "NPI Item Publish Stream Guard": ITEM_STREAM_GUARD_WRITE_FLAG,
    "NPI Item Publish Attempt": ITEM_ATTEMPT_WRITE_FLAG,
    "NPI Item Publish Result": ITEM_RESULT_WRITE_FLAG,
    "NPI Item Mapping Observation": ITEM_MAPPING_WRITE_FLAG,
    "NPI Item Mapping Head": ITEM_MAPPING_WRITE_FLAG,
}
_REQUEST_SUPPORT_WRITES = frozenset(
    {
        ("NPI Item Publish Request", "insert"),
        ("NPI Item Publish Command Idempotency", "insert"),
        ("NPI Outbox Message", "insert"),
        ("NPI Item Publish Stream Guard", "insert"),
        ("NPI Item Publish Stream Guard", "save"),
    }
)
_CLAIM_SUPPORT_WRITES = frozenset(
    {
        ("NPI Item Publish Attempt", "insert"),
        ("NPI Item Publish Request", "save"),
        ("NPI Outbox Message", "save"),
        ("NPI Item Publish Attempt", "save"),
        ("NPI Item Publish Stream Guard", "save"),
    }
)
_RESULT_SUPPORT_WRITES = frozenset(
    {
        ("NPI Item Publish Result", "insert"),
        ("NPI Item Mapping Observation", "insert"),
        ("NPI Item Mapping Head", "insert"),
        ("NPI Item Publish Request", "save"),
        ("NPI Outbox Message", "save"),
        ("NPI Item Publish Attempt", "save"),
        ("NPI Item Mapping Head", "save"),
        ("NPI Item Publish Stream Guard", "save"),
    }
)
_MAPPING_SUPPORT_WRITES = frozenset(
    {
        ("NPI Item Mapping Observation", "insert"),
        ("NPI Item Mapping Head", "insert"),
        ("NPI Item Mapping Head", "save"),
    }
)
_MANUAL_REPLAY_SUPPORT_WRITES = frozenset(
    {
        ("NPI Item Publish Request", "save"),
        ("NPI Outbox Message", "save"),
        ("NPI Item Publish Stream Guard", "save"),
    }
)


class ItemServiceActorUnavailable(RuntimeError):
    """Raised when a frozen worker actor cannot be used safely."""


def require_item_outbox_write() -> None:
    _require_flag(
        ITEM_OUTBOX_WRITE_FLAG,
        _("Item publish Outbox messages can only be changed by the controlled Item execution service."),
    )


def require_item_request_write() -> None:
    _require_flag(
        ITEM_REQUEST_WRITE_FLAG,
        _("Item publish requests can only be changed through an authorized NPI command."),
    )


def require_item_idempotency_write() -> None:
    _require_flag(
        ITEM_IDEMPOTENCY_WRITE_FLAG,
        _("Item publish idempotency records can only be changed through an authorized NPI command."),
    )


def require_item_attempt_write() -> None:
    _require_flag(
        ITEM_ATTEMPT_WRITE_FLAG,
        _("Item publish attempts can only be changed by the controlled Item execution service."),
    )


def require_item_result_write() -> None:
    _require_flag(
        ITEM_RESULT_WRITE_FLAG,
        _("Item publish results can only be appended by the controlled Item execution service."),
    )


def require_item_mapping_write() -> None:
    _require_flag(
        ITEM_MAPPING_WRITE_FLAG,
        _("Item mapping records can only be changed by the controlled Item execution service."),
    )


def require_item_stream_guard_write() -> None:
    _require_flag(
        ITEM_STREAM_GUARD_WRITE_FLAG,
        _(
            "Item publish stream guards can only be changed by the controlled Item execution service."
        ),
    )


def deny_item_history_update() -> None:
    frappe.throw(
        _("Item publish execution history cannot be changed."),
        frappe.PermissionError,
    )


def deny_item_history_delete() -> None:
    frappe.throw(
        _("Item publish execution history cannot be deleted."),
        frappe.PermissionError,
    )


def deny_legacy_outbox_promotion() -> None:
    frappe.throw(
        _("Legacy Outbox messages cannot be promoted into Item execution."),
        frappe.PermissionError,
    )


@contextmanager
def item_request_transaction_write(
    requester_user_id: str,
) -> Iterator[ItemSupportWriteCapability]:
    """Authorize one requester-owned command/idempotency/Outbox transaction."""

    _require_authenticated_requester(requester_user_id)
    capability = ItemSupportWriteCapability(
        actor=requester_user_id,
        scope="request",
        allowed=_REQUEST_SUPPORT_WRITES,
    )
    with _capability_scope(capability):
        with (
            _flag_scope(ITEM_REQUEST_WRITE_FLAG),
            _flag_scope(ITEM_IDEMPOTENCY_WRITE_FLAG),
            _flag_scope(ITEM_OUTBOX_WRITE_FLAG),
            _flag_scope(ITEM_STREAM_GUARD_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability


@contextmanager
def item_claim_write(
    service_actor_user_id: str,
) -> Iterator[ItemSupportWriteCapability]:
    """Authorize one frozen-service-actor claim transaction."""

    _require_session_actor(service_actor_user_id)
    _require_internal_npi_api_user(service_actor_user_id)
    capability = ItemSupportWriteCapability(
        actor=service_actor_user_id,
        scope="claim",
        allowed=_CLAIM_SUPPORT_WRITES,
    )
    with _capability_scope(capability):
        with (
            _flag_scope(ITEM_OUTBOX_WRITE_FLAG),
            _flag_scope(ITEM_STREAM_GUARD_WRITE_FLAG),
            _flag_scope(ITEM_REQUEST_WRITE_FLAG),
            _flag_scope(ITEM_ATTEMPT_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability


@contextmanager
def item_result_transaction_write(
    service_actor_user_id: str,
) -> Iterator[ItemSupportWriteCapability]:
    """Authorize one frozen-service-actor result transaction."""

    _require_session_actor(service_actor_user_id)
    _require_internal_npi_api_user(service_actor_user_id)
    capability = ItemSupportWriteCapability(
        actor=service_actor_user_id,
        scope="result",
        allowed=_RESULT_SUPPORT_WRITES,
    )
    with _capability_scope(capability):
        with (
            _flag_scope(ITEM_OUTBOX_WRITE_FLAG),
            _flag_scope(ITEM_STREAM_GUARD_WRITE_FLAG),
            _flag_scope(ITEM_REQUEST_WRITE_FLAG),
            _flag_scope(ITEM_ATTEMPT_WRITE_FLAG),
            _flag_scope(ITEM_RESULT_WRITE_FLAG),
            _flag_scope(ITEM_MAPPING_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability


@contextmanager
def item_manual_replay_write(
    service_actor_user_id: str,
) -> Iterator[ItemSupportWriteCapability]:
    """Authorize only a failed-retryable Item request CAS back to queued."""

    from npi_integration.integration_operations.frappe_validation import (
        integration_operation_manual_replay,
    )

    _require_session_actor(service_actor_user_id)
    _require_internal_npi_api_user(service_actor_user_id)
    capability = ItemSupportWriteCapability(
        actor=service_actor_user_id,
        scope="manual_replay",
        allowed=_MANUAL_REPLAY_SUPPORT_WRITES,
    )
    with _capability_scope(capability):
        with (
            integration_operation_manual_replay(
                actor_user_id=service_actor_user_id,
                operation_kind="publish_item",
            ),
            _flag_scope(ITEM_OUTBOX_WRITE_FLAG),
            _flag_scope(ITEM_STREAM_GUARD_WRITE_FLAG),
            _flag_scope(ITEM_REQUEST_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability


@contextmanager
def item_mapping_write(
    service_actor_user_id: str,
) -> Iterator[ItemSupportWriteCapability]:
    """Authorize one frozen-service-actor mapping append."""

    _require_session_actor(service_actor_user_id)
    _require_internal_npi_api_user(service_actor_user_id)
    capability = ItemSupportWriteCapability(
        actor=service_actor_user_id,
        scope="mapping",
        allowed=_MAPPING_SUPPORT_WRITES,
    )
    with _capability_scope(capability):
        with _flag_scope(ITEM_MAPPING_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
            yield capability


@contextmanager
def item_service_actor_scope(service_actor_user_id: str) -> Iterator[None]:
    """Run worker execution as the exact frozen service actor and restore user."""

    _require_internal_npi_api_user(service_actor_user_id)
    session = getattr(frappe, "session", None)
    previous_user = getattr(session, "user", None)
    set_user = getattr(frappe, "set_user", None)
    if not isinstance(previous_user, str) or not previous_user or not callable(set_user):
        raise RuntimeError("Item publish worker user context is unavailable.")
    switched_user = previous_user != service_actor_user_id
    if switched_user:
        set_user(service_actor_user_id)
    try:
        yield
    finally:
        if switched_user:
            set_user(previous_user)


def insert_item_support_document(
    document: Any,
    *,
    capability: ItemSupportWriteCapability,
    ignore_links: bool = False,
) -> Any:
    """Insert one allowlisted support document under its exact capability."""

    _authorize_support_write(document, action="insert", capability=capability)
    if ignore_links and str(getattr(document, "doctype", "")) != "NPI Item Publish Request":
        raise RuntimeError("Item support insert ignore_links is outside its exact scope.")
    flags = getattr(document, "flags", None)
    previous_ignore_links = getattr(flags, "ignore_links", False) if flags else False
    if ignore_links and flags is None:
        raise RuntimeError("Item support insert link scope is unavailable.")
    if ignore_links:
        flags.ignore_links = True
    try:
        return document.insert(ignore_permissions=True)
    finally:
        if ignore_links:
            flags.ignore_links = previous_ignore_links


def save_item_support_document(
    document: Any,
    *,
    capability: ItemSupportWriteCapability,
) -> Any:
    """Save one allowlisted support document under its exact capability."""

    _authorize_support_write(document, action="save", capability=capability)
    return document.save(ignore_permissions=True)


@contextmanager
def _capability_scope(capability: ItemSupportWriteCapability) -> Iterator[None]:
    token = _CURRENT_SUPPORT_CAPABILITY.set(capability)
    try:
        yield
    finally:
        _CURRENT_SUPPORT_CAPABILITY.reset(token)


def _authorize_support_write(
    document: Any,
    *,
    action: str,
    capability: ItemSupportWriteCapability,
) -> None:
    current = _CURRENT_SUPPORT_CAPABILITY.get()
    if current is not capability:
        raise RuntimeError("Item support write capability is invalid or out of scope.")
    doctype = str(getattr(document, "doctype", ""))
    if (doctype, action) not in capability.allowed:
        raise RuntimeError("Item support write is outside the exact capability scope.")
    session_user = getattr(getattr(frappe, "session", None), "user", None)
    if session_user != capability.actor:
        raise RuntimeError("Item support write actor drifted from the frozen scope.")
    flag = _SUPPORT_WRITE_FLAGS.get(doctype)
    if flag is None or not getattr(frappe.flags, flag, False):
        raise RuntimeError("Item support write controller flag is missing.")


def _require_authenticated_requester(requester_user_id: str) -> None:
    _require_session_actor(requester_user_id)
    _require_internal_npi_api_user(requester_user_id)


def _require_session_actor(actor_user_id: str) -> None:
    session_user = getattr(getattr(frappe, "session", None), "user", None)
    if session_user != actor_user_id:
        raise RuntimeError("Item publish authenticated requester does not match the session.")


def _require_internal_npi_api_user(actor_user_id: str) -> None:
    if not _is_internal_npi_api_user(actor_user_id):
        raise ItemServiceActorUnavailable(
            "Item publish actor is not an enabled internal NPI API User."
        )


def validate_item_service_actor(actor_user_id: str) -> None:
    """Fail closed unless the frozen actor is an enabled internal API user."""

    _require_internal_npi_api_user(actor_user_id)


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
    return bool(
        user
        and int(_field(user, "enabled") or 0) == 1
        and str(_field(user, "user_type")) == "System User"
        and "NPI API User" in roles
    )


def _field(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def validate_one_way_transition(
    before: object,
    after: object,
    *,
    allowed: dict[str, frozenset[str]],
    label: str,
) -> None:
    previous = str(before or "")
    current = str(after or "")
    if current == previous:
        return
    if current not in allowed.get(previous, frozenset()):
        frappe.throw(
            _("{record} state transition is invalid.").format(record=label),
            frappe.ValidationError,
        )


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
