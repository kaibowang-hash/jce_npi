from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


PROJECTION_WRITE_FLAG = "npi_authorization_projection_write"
AUDIT_APPEND_FLAG = "npi_audit_append"
LOCAL_USER_WRITE_FLAG = "npi_authorization_local_user_write"


@dataclass(frozen=True, slots=True)
class AuthorizationProjectionWriteCapability:
    actor: str
    target_user_id: str


_CURRENT: ContextVar[AuthorizationProjectionWriteCapability | None] = ContextVar(
    "npi_authorization_projection_capability",
    default=None,
)


def require_authorization_projection_write() -> None:
    if not getattr(frappe.flags, PROJECTION_WRITE_FLAG, False):
        frappe.throw(
            _(
                "Authorization projections can only be changed by the controlled integration service."
            ),
            frappe.PermissionError,
        )


def deny_authorization_projection_delete() -> None:
    frappe.throw(
        _("Authorization projection history cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def authorization_projection_write(
    actor: str,
    target_user_id: str,
) -> Iterator[AuthorizationProjectionWriteCapability]:
    require_service_actor(actor)
    capability = AuthorizationProjectionWriteCapability(
        actor=actor,
        target_user_id=target_user_id,
    )
    token = _CURRENT.set(capability)
    with (
        _flag_scope(PROJECTION_WRITE_FLAG),
        _flag_scope(AUDIT_APPEND_FLAG),
        _flag_scope(LOCAL_USER_WRITE_FLAG),
    ):
        try:
            yield capability
        finally:
            _CURRENT.reset(token)


def insert_projection_document(
    document: Any,
    *,
    capability: AuthorizationProjectionWriteCapability,
) -> Any:
    _authorize(document, capability)
    return document.insert(ignore_permissions=True)


def save_projection_document(
    document: Any,
    *,
    capability: AuthorizationProjectionWriteCapability,
) -> Any:
    _authorize(document, capability)
    return document.save(ignore_permissions=True)


def insert_projection_audit(
    document: Any,
    *,
    capability: AuthorizationProjectionWriteCapability,
) -> Any:
    if (
        _CURRENT.get() is not capability
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or str(getattr(document, "doctype", "")) != "NPI Audit Event"
        or not getattr(frappe.flags, AUDIT_APPEND_FLAG, False)
    ):
        raise RuntimeError("Authorization projection audit capability is invalid.")
    return document.insert(ignore_permissions=True)


def insert_provisioned_user(
    document: Any,
    *,
    capability: AuthorizationProjectionWriteCapability,
) -> Any:
    _authorize_local_user(document, capability, creating=True)
    result = document.insert(ignore_permissions=True)
    if (
        str(getattr(result, "name", "")) != capability.target_user_id
        or str(getattr(result, "user_type", "")) != "System User"
        or int(getattr(result, "enabled", 0) or 0) != 1
    ):
        raise RuntimeError("Provisioned local User state is invalid.")
    return result


def save_provisioned_user(
    document: Any,
    *,
    capability: AuthorizationProjectionWriteCapability,
) -> Any:
    _authorize_local_user(document, capability, creating=False)
    return document.save(ignore_permissions=True)


def _authorize(
    document: Any,
    capability: AuthorizationProjectionWriteCapability,
) -> None:
    if (
        _CURRENT.get() is not capability
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or str(getattr(document, "doctype", ""))
        != "NPI Authorization Projection"
        or not getattr(frappe.flags, PROJECTION_WRITE_FLAG, False)
    ):
        raise RuntimeError("Authorization projection write capability is invalid.")


def _authorize_local_user(
    document: Any,
    capability: AuthorizationProjectionWriteCapability,
    *,
    creating: bool,
) -> None:
    name = str(getattr(document, "name", "") or "")
    email = str(getattr(document, "email", "") or "")
    if (
        _CURRENT.get() is not capability
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or not getattr(frappe.flags, LOCAL_USER_WRITE_FLAG, False)
        or str(getattr(document, "doctype", "")) != "User"
        or email != capability.target_user_id
        or name not in {"", capability.target_user_id}
        or str(getattr(document, "new_password", "") or "")
    ):
        raise RuntimeError("Authorization local User capability is invalid.")
    if creating:
        roles = tuple(
            str(getattr(role, "role", None) or role.get("role", ""))
            for role in (getattr(document, "roles", None) or ())
        )
        if (
            int(getattr(document, "enabled", 0) or 0) != 1
            or int(getattr(document, "send_welcome_email", 1) or 0) != 0
            or str(getattr(document, "user_type", "")) != "System User"
            or roles != ("Desk User",)
        ):
            raise RuntimeError("Authorization local User creation is invalid.")


def require_service_actor(actor: str) -> None:
    session_user = getattr(getattr(frappe, "session", None), "user", None)
    record = frappe.db.get_value(
        "User",
        actor,
        ["enabled", "user_type"],
        as_dict=True,
    )
    enabled = record.get("enabled") if hasattr(record, "get") else None
    user_type = record.get("user_type") if hasattr(record, "get") else None
    if (
        not isinstance(actor, str)
        or not actor
        or actor != actor.strip()
        or actor.casefold() in {"guest", "administrator"}
        or session_user != actor
        or not record
        or int(enabled or 0) != 1
        or user_type != "System User"
        or "NPI API User" not in set(frappe.get_roles(actor) or ())
    ):
        frappe.throw(
            _(
                "Authorization projections can only be changed by the controlled integration service."
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
