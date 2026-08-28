from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

import frappe
from frappe import _


ACTION_RECEIPT_WRITE_FLAG = "npi_integration_action_receipt_write"
RECONCILIATION_OBSERVATION_WRITE_FLAG = (
    "npi_integration_reconciliation_observation_write"
)


@dataclass(frozen=True, slots=True)
class IntegrationOperationsWriteCapability:
    actor: str
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT: ContextVar[IntegrationOperationsWriteCapability | None] = ContextVar(
    "npi_integration_operations_write_capability",
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


def _require_service_actor(service_actor_user_id: str) -> None:
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
