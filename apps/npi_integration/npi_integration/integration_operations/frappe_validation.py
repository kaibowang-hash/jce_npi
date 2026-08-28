from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


ACTION_RECEIPT_WRITE_FLAG = "npi_integration_action_receipt_write"
RECONCILIATION_OBSERVATION_WRITE_FLAG = (
    "npi_integration_reconciliation_observation_write"
)
AUDIT_APPEND_FLAG = "npi_audit_append"


@dataclass(frozen=True, slots=True)
class IntegrationOperationsWriteCapability:
    actor: str
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT: ContextVar[IntegrationOperationsWriteCapability | None] = ContextVar(
    "npi_integration_operations_write_capability",
    default=None,
)
_CURRENT_MANUAL_REPLAY: ContextVar[tuple[str, str] | None] = ContextVar(
    "npi_integration_operations_manual_replay",
    default=None,
)
_FLAGS = {
    "NPI Integration Action Receipt": ACTION_RECEIPT_WRITE_FLAG,
    "NPI Integration Reconciliation Observation": (
        RECONCILIATION_OBSERVATION_WRITE_FLAG
    ),
}
INTEGRATION_OPERATIONS_SUPPORT_WRITES = frozenset(
    {
        ("NPI Integration Action Receipt", "insert"),
        ("NPI Integration Reconciliation Observation", "insert"),
    }
)


def require_integration_operations_write(doctype: str, action: str) -> None:
    capability = _CURRENT.get()
    flag = _FLAGS.get(doctype)
    if (
        flag is None
        or action != "insert"
        or capability is None
        or (doctype, action) not in capability.allowed
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or not getattr(frappe.flags, flag, False)
    ):
        frappe.throw(
            _(
                "Integration operation history can only be appended by the controlled operation service."
            ),
            frappe.PermissionError,
        )


def deny_integration_operations_history_update() -> None:
    frappe.throw(
        _("Integration operation history cannot be changed."),
        frappe.PermissionError,
    )


def deny_integration_operations_history_delete() -> None:
    frappe.throw(
        _("Integration operation history cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def integration_operations_write_capability(
    *,
    service_actor_user_id: str,
    scope: str,
    allowed: frozenset[tuple[str, str]],
) -> Iterator[IntegrationOperationsWriteCapability]:
    """Activate only the exact append-only support set; no writer is exposed here."""

    if not allowed or not allowed.issubset(INTEGRATION_OPERATIONS_SUPPORT_WRITES):
        raise ValueError(
            "Integration operation capability is outside the closed support set."
        )
    _require_service_actor(service_actor_user_id)
    capability = IntegrationOperationsWriteCapability(
        actor=service_actor_user_id,
        scope=_scope(scope),
        allowed=allowed,
    )
    token = _CURRENT.set(capability)
    missing = object()
    previous = {
        _FLAGS[doctype]: getattr(frappe.flags, _FLAGS[doctype], missing)
        for doctype, _action in allowed
    }
    try:
        for flag in previous:
            setattr(frappe.flags, flag, True)
        with _flag_scope(AUDIT_APPEND_FLAG):
            yield capability
    finally:
        for flag, value in previous.items():
            if value is missing:
                try:
                    delattr(frappe.flags, flag)
                except AttributeError:
                    pass
            else:
                setattr(frappe.flags, flag, value)
        _CURRENT.reset(token)


def insert_integration_operations_support_document(
    document: Any,
    *,
    capability: IntegrationOperationsWriteCapability,
) -> Any:
    """Insert one append-only support row under the exact active capability."""

    current = _CURRENT.get()
    if current is not capability:
        raise RuntimeError(
            "Integration operation write capability is invalid or out of scope."
        )
    doctype = str(getattr(document, "doctype", ""))
    if (doctype, "insert") not in capability.allowed:
        raise RuntimeError(
            "Integration operation support write is outside the exact capability scope."
        )
    if getattr(getattr(frappe, "session", None), "user", None) != capability.actor:
        raise RuntimeError(
            "Integration operation support write actor drifted from the frozen scope."
        )
    flag = _FLAGS.get(doctype)
    if flag is None or not getattr(frappe.flags, flag, False):
        raise RuntimeError(
            "Integration operation support write controller flag is missing."
        )
    return document.insert(ignore_permissions=True)


@contextmanager
def integration_operation_manual_replay(
    *,
    actor_user_id: str,
    operation_kind: str,
) -> Iterator[None]:
    """Mark one exact owning transition; owning capabilities still authorize writes."""

    _require_service_actor(actor_user_id)
    if operation_kind not in {
        "receive_project_submission",
        "publish_item",
        "publish_mbom",
        "create_tool_asset",
        "update_tool_asset",
    }:
        raise ValueError("Integration operation replay kind is unsupported.")
    token = _CURRENT_MANUAL_REPLAY.set((actor_user_id, operation_kind))
    try:
        yield
    finally:
        _CURRENT_MANUAL_REPLAY.reset(token)


def integration_operation_manual_replay_is_active(operation_kind: str) -> bool:
    value = _CURRENT_MANUAL_REPLAY.get()
    actor = getattr(getattr(frappe, "session", None), "user", None)
    return bool(value == (actor, operation_kind))


def _require_service_actor(service_actor_user_id: str) -> None:
    session_user = getattr(getattr(frappe, "session", None), "user", None)
    database = getattr(frappe, "db", None)
    get_value = getattr(database, "get_value", None)
    get_roles = getattr(frappe, "get_roles", None)
    user = (
        get_value(
            "User",
            service_actor_user_id,
            ["enabled", "user_type"],
            as_dict=True,
        )
        if callable(get_value)
        and isinstance(service_actor_user_id, str)
        and service_actor_user_id
        else None
    )
    enabled = user.get("enabled") if isinstance(user, dict) else getattr(user, "enabled", None)
    user_type = (
        user.get("user_type")
        if isinstance(user, dict)
        else getattr(user, "user_type", None)
    )
    if (
        not isinstance(service_actor_user_id, str)
        or not service_actor_user_id
        or service_actor_user_id != service_actor_user_id.strip()
        or service_actor_user_id.casefold() in {"guest", "administrator"}
        or session_user != service_actor_user_id
        or not user
        or int(enabled or 0) != 1
        or str(user_type) != "System User"
        or not callable(get_roles)
        or "NPI API User" not in set(get_roles(service_actor_user_id) or ())
    ):
        frappe.throw(
            _(
                "Integration operation history can only be appended by the controlled operation service."
            ),
            frappe.PermissionError,
        )


def _scope(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 160
    ):
        raise ValueError("Integration operation capability scope is invalid.")
    return value


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
