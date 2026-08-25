from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator
from uuid import UUID

import frappe
from frappe import _


TOOL_ASSET_EXECUTION_REQUEST_WRITE_FLAG = "npi_tool_asset_execution_request_write"
TOOL_ASSET_EXECUTION_IDEMPOTENCY_WRITE_FLAG = "npi_tool_asset_execution_idempotency_write"
TOOL_ASSET_EXECUTION_STREAM_WRITE_FLAG = "npi_tool_asset_execution_stream_write"
TOOL_ASSET_EXECUTION_ATTEMPT_WRITE_FLAG = "npi_tool_asset_execution_attempt_write"
TOOL_ASSET_EXECUTION_RESULT_WRITE_FLAG = "npi_tool_asset_execution_result_write"
TOOL_ASSET_EXECUTION_MAPPING_WRITE_FLAG = "npi_tool_asset_execution_mapping_write"
TOOL_ASSET_EXECUTION_OUTBOX_WRITE_FLAG = "npi_tool_asset_execution_outbox_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


@dataclass(frozen=True, slots=True)
class ToolAssetSupportWriteCapability:
    actor: str
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT_CAPABILITY: ContextVar[ToolAssetSupportWriteCapability | None] = ContextVar(
    "npi_tool_asset_support_write_capability",
    default=None,
)


_SUPPORT_FLAGS = {
    "NPI Tool Asset Request": TOOL_ASSET_EXECUTION_REQUEST_WRITE_FLAG,
    "NPI Tool Asset Command Idempotency": TOOL_ASSET_EXECUTION_IDEMPOTENCY_WRITE_FLAG,
    "NPI Tool Asset Stream Guard": TOOL_ASSET_EXECUTION_STREAM_WRITE_FLAG,
    "NPI Tool Asset Attempt": TOOL_ASSET_EXECUTION_ATTEMPT_WRITE_FLAG,
    "NPI Tool Asset Result": TOOL_ASSET_EXECUTION_RESULT_WRITE_FLAG,
    "NPI Tool Asset Field Result": TOOL_ASSET_EXECUTION_RESULT_WRITE_FLAG,
    "NPI Tool Asset Mapping Observation": TOOL_ASSET_EXECUTION_MAPPING_WRITE_FLAG,
    "NPI Tool Asset Mapping Head": TOOL_ASSET_EXECUTION_MAPPING_WRITE_FLAG,
    "NPI Outbox Message": TOOL_ASSET_EXECUTION_OUTBOX_WRITE_FLAG,
}

_REQUEST_WRITES = frozenset(
    {
        ("NPI Tool Asset Request", "insert"),
        ("NPI Tool Asset Command Idempotency", "insert"),
        ("NPI Tool Asset Stream Guard", "insert"),
        ("NPI Tool Asset Stream Guard", "save"),
        ("NPI Outbox Message", "insert"),
    }
)
_CLAIM_WRITES = frozenset(
    {
        ("NPI Tool Asset Request", "save"),
        ("NPI Tool Asset Attempt", "insert"),
        ("NPI Tool Asset Attempt", "save"),
        ("NPI Tool Asset Stream Guard", "save"),
        ("NPI Outbox Message", "save"),
    }
)
_RESULT_WRITES = frozenset(
    {
        ("NPI Tool Asset Request", "save"),
        ("NPI Tool Asset Attempt", "save"),
        ("NPI Tool Asset Result", "insert"),
        ("NPI Tool Asset Field Result", "insert"),
        ("NPI Tool Asset Mapping Observation", "insert"),
        ("NPI Tool Asset Mapping Head", "insert"),
        ("NPI Tool Asset Mapping Head", "save"),
        ("NPI Tool Asset Stream Guard", "save"),
        ("NPI Outbox Message", "save"),
    }
)


class ToolAssetServiceActorUnavailable(RuntimeError):
    """Raised when the frozen Tool Asset service actor cannot be entered."""


def require_tool_asset_execution_request_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_REQUEST_WRITE_FLAG, _("Tool Asset execution requests can only be changed through an authorized NPI command."))


def require_tool_asset_execution_idempotency_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_IDEMPOTENCY_WRITE_FLAG, _("Tool Asset execution idempotency records can only be changed through an authorized NPI command."))


def require_tool_asset_execution_stream_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_STREAM_WRITE_FLAG, _("Tool Asset execution stream guards can only be changed by the controlled execution service."))


def require_tool_asset_execution_attempt_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_ATTEMPT_WRITE_FLAG, _("Tool Asset execution attempts can only be changed by the controlled execution service."))


def require_tool_asset_execution_result_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_RESULT_WRITE_FLAG, _("Tool Asset execution results can only be appended by the controlled execution service."))


def require_tool_asset_execution_mapping_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_MAPPING_WRITE_FLAG, _("Tool Asset mapping records can only be changed by the controlled execution service."))


def require_tool_asset_execution_outbox_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_OUTBOX_WRITE_FLAG, _("Tool Asset execution Outbox messages can only be changed by the controlled execution service."))


def require_tool_asset_execution_capability(doctype: str, action: str) -> None:
    capability = _CURRENT_CAPABILITY.get()
    if capability is None or (doctype, action) not in capability.allowed:
        frappe.throw(_("This Tool Asset support record is outside the active execution capability."), frappe.PermissionError)


def deny_tool_asset_execution_history_update() -> None:
    frappe.throw(_("Tool Asset execution history cannot be changed."), frappe.PermissionError)


def deny_tool_asset_execution_history_delete() -> None:
    frappe.throw(_("Tool Asset execution history cannot be deleted."), frappe.PermissionError)


def deny_tool_asset_outbox_conversion() -> None:
    frappe.throw(_("Outbox messages cannot be converted between Item, MBOM and Tool Asset execution."), frappe.PermissionError)


@contextmanager
def _tool_asset_support_write(
    actor: str,
    scope: str,
    allowed: frozenset[tuple[str, str]],
) -> Iterator[ToolAssetSupportWriteCapability]:
    """Enter one exact internal support-DocType write capability."""

    capability = ToolAssetSupportWriteCapability(actor=actor, scope=scope, allowed=allowed)
    token = _CURRENT_CAPABILITY.set(capability)
    names = {_SUPPORT_FLAGS[doctype] for doctype, _action in allowed}
    previous = {name: getattr(frappe.flags, name, None) for name in names}
    try:
        for name in names:
            setattr(frappe.flags, name, True)
        yield capability
    finally:
        for name, value in previous.items():
            if value is None:
                try:
                    delattr(frappe.flags, name)
                except AttributeError:
                    pass
            else:
                setattr(frappe.flags, name, value)
        _CURRENT_CAPABILITY.reset(token)


@contextmanager
def tool_asset_request_transaction_write(
    requester_user_id: str,
) -> Iterator[ToolAssetSupportWriteCapability]:
    """Authorize only the atomic Tool Asset request landing writes."""

    _require_requester(requester_user_id)
    with _tool_asset_support_write(
        requester_user_id,
        "request",
        _REQUEST_WRITES,
    ) as capability, _flag_scope(AUDIT_APPEND_FLAG):
        yield capability


def validate_tool_asset_service_actor(actor_user_id: str) -> None:
    _require_internal_service_actor(actor_user_id)


@contextmanager
def tool_asset_service_actor_scope(service_actor_user_id: str) -> Iterator[None]:
    try:
        _require_internal_service_actor(service_actor_user_id)
    except (RuntimeError, ValueError) as error:
        raise ToolAssetServiceActorUnavailable("The frozen Tool Asset service actor is unavailable.") from error
    session = getattr(frappe, "session", None)
    previous = getattr(session, "user", None)
    set_user = getattr(frappe, "set_user", None)
    if not isinstance(previous, str) or not previous or not callable(set_user):
        raise ToolAssetServiceActorUnavailable("The Tool Asset worker user context is unavailable.")
    switched = previous != service_actor_user_id
    if switched:
        set_user(service_actor_user_id)
    try:
        yield
    finally:
        if switched:
            set_user(previous)


@contextmanager
def tool_asset_claim_write(service_actor_user_id: str) -> Iterator[ToolAssetSupportWriteCapability]:
    with _tool_asset_support_write(service_actor_user_id, "claim", _CLAIM_WRITES) as capability, _flag_scope(AUDIT_APPEND_FLAG):
        yield capability


@contextmanager
def tool_asset_result_transaction_write(service_actor_user_id: str) -> Iterator[ToolAssetSupportWriteCapability]:
    with _tool_asset_support_write(service_actor_user_id, "result", _RESULT_WRITES) as capability, _flag_scope(AUDIT_APPEND_FLAG):
        yield capability


def insert_tool_asset_support_document(
    document: Any,
    *,
    capability: ToolAssetSupportWriteCapability,
    defer_request_outbox_link: bool = False,
) -> Any:
    """Insert one exact Tool Asset support row under the active capability."""

    _authorize_support_write(document, "insert", capability)
    if defer_request_outbox_link:
        outbox_event_id = getattr(document, "outbox_event_id", None)
        try:
            canonical_outbox_event_id = (
                isinstance(outbox_event_id, str)
                and str(UUID(outbox_event_id)) == outbox_event_id
            )
        except (AttributeError, TypeError, ValueError):
            canonical_outbox_event_id = False
        if (
            str(getattr(document, "doctype", "")) != "NPI Tool Asset Request"
            or int(getattr(document, "schema_version", 0) or 0) != 2
            or int(getattr(document, "dispatch_allowed", 0) or 0) != 1
            or not canonical_outbox_event_id
            or getattr(document, "result_global_id", None) not in (None, "")
        ):
            raise RuntimeError(
                "Tool Asset request Outbox link deferral is outside its exact scope."
            )
    flags = getattr(document, "flags", None)
    previous_ignore_links = getattr(flags, "ignore_links", False) if flags else False
    if defer_request_outbox_link and flags is None:
        raise RuntimeError("Tool Asset request Outbox link scope is unavailable.")
    if defer_request_outbox_link:
        flags.ignore_links = True
    try:
        return document.insert(ignore_permissions=True)
    finally:
        if defer_request_outbox_link:
            flags.ignore_links = previous_ignore_links


def save_tool_asset_support_document(
    document: Any,
    *,
    capability: ToolAssetSupportWriteCapability,
) -> Any:
    """Save one exact Tool Asset support row under the active capability."""

    _authorize_support_write(document, "save", capability)
    return document.save(ignore_permissions=True)


def insert_tool_asset_audit_document(
    document: Any,
    *,
    capability: ToolAssetSupportWriteCapability,
) -> Any:
    """Append one audit row under the exact request transaction capability."""

    if (
        _CURRENT_CAPABILITY.get() is not capability
        or str(getattr(document, "doctype", "")) != "NPI Audit Event"
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or not getattr(frappe.flags, AUDIT_APPEND_FLAG, False)
    ):
        raise RuntimeError("Tool Asset audit append is outside the exact capability scope.")
    return document.insert(ignore_permissions=True)


def _authorize_support_write(
    document: Any,
    action: str,
    capability: ToolAssetSupportWriteCapability,
) -> None:
    if _CURRENT_CAPABILITY.get() is not capability:
        raise RuntimeError("Tool Asset support write capability is invalid or out of scope.")
    doctype = str(getattr(document, "doctype", ""))
    if (doctype, action) not in capability.allowed:
        raise RuntimeError("Tool Asset support write is outside the exact capability scope.")
    if getattr(getattr(frappe, "session", None), "user", None) != capability.actor:
        raise RuntimeError("Tool Asset support write actor drifted from the frozen scope.")
    flag = _SUPPORT_FLAGS.get(doctype)
    if flag is None or not getattr(frappe.flags, flag, False):
        raise RuntimeError("Tool Asset support write controller flag is missing.")


def _require_requester(requester_user_id: str) -> None:
    if (
        not isinstance(requester_user_id, str)
        or not requester_user_id
        or requester_user_id != requester_user_id.strip()
        or requester_user_id.casefold() in {"guest", "administrator"}
        or getattr(getattr(frappe, "session", None), "user", None)
        != requester_user_id
    ):
        frappe.throw(_("The Tool Asset execution requester is unavailable."), frappe.PermissionError)
    get_value = getattr(getattr(frappe, "db", None), "get_value", None)
    get_roles = getattr(frappe, "get_roles", None)
    if (
        not callable(get_value)
        or not callable(get_roles)
        or int(get_value("User", requester_user_id, "enabled") or 0) != 1
        or "NPI API User" not in set(get_roles(requester_user_id) or ())
    ):
        frappe.throw(_("The Tool Asset execution requester is unavailable."), frappe.PermissionError)


def _require_internal_service_actor(actor_user_id: str) -> None:
    if not isinstance(actor_user_id, str) or not actor_user_id or actor_user_id.casefold() in {"guest", "administrator"}:
        raise RuntimeError("Tool Asset service actor is invalid.")
    get_value = getattr(getattr(frappe, "db", None), "get_value", None)
    get_roles = getattr(frappe, "get_roles", None)
    if not callable(get_value) or not callable(get_roles):
        raise RuntimeError("Tool Asset service actor lookup is unavailable.")
    user = get_value("User", actor_user_id, ["enabled", "user_type"], as_dict=True)
    enabled = user.get("enabled") if isinstance(user, dict) else getattr(user, "enabled", None)
    user_type = user.get("user_type") if isinstance(user, dict) else getattr(user, "user_type", None)
    if not user or int(enabled or 0) != 1 or str(user_type) != "System User" or "NPI API User" not in set(get_roles(actor_user_id) or ()):
        raise RuntimeError("Tool Asset service actor is unavailable.")


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


def _require_flag(name: str, message: str) -> None:
    if not getattr(frappe.flags, name, False):
        frappe.throw(message, frappe.PermissionError)
