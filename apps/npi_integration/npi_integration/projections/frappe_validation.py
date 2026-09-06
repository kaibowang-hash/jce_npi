from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


PROJECTION_OBSERVATION_WRITE_FLAG = "npi_erp_projection_observation_write"
PROJECTION_HEAD_WRITE_FLAG = "npi_erp_projection_head_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


@dataclass(frozen=True, slots=True)
class ProjectionSupportWriteCapability:
    actor: str
    allowed: frozenset[tuple[str, str]]


PROJECTION_REPOSITORY_WRITES = frozenset(
    {
        ("NPI ERP Projection Observation", "insert"),
        ("NPI ERP Projection Head", "insert"),
        ("NPI ERP Projection Head", "save"),
    }
)
_CURRENT_SUPPORT_CAPABILITY: ContextVar[ProjectionSupportWriteCapability | None] = (
    ContextVar("npi_projection_support_write_capability", default=None)
)
_SUPPORT_FLAGS = {
    "NPI ERP Projection Observation": PROJECTION_OBSERVATION_WRITE_FLAG,
    "NPI ERP Projection Head": PROJECTION_HEAD_WRITE_FLAG,
}


def require_projection_observation_write() -> None:
    if not getattr(frappe.flags, PROJECTION_OBSERVATION_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERP projection observations can only be appended by the controlled projection service."
            ),
            frappe.PermissionError,
        )


def require_projection_head_write() -> None:
    if not getattr(frappe.flags, PROJECTION_HEAD_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERP projection heads can only be changed by the controlled projection service."
            ),
            frappe.PermissionError,
        )


def deny_projection_observation_update() -> None:
    frappe.throw(
        _("ERP projection observation history cannot be changed."),
        frappe.PermissionError,
    )


def deny_projection_history_delete() -> None:
    frappe.throw(
        _("ERP projection observation and head records cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def projection_observation_write() -> Iterator[None]:
    with _flag_scope(PROJECTION_OBSERVATION_WRITE_FLAG):
        yield


@contextmanager
def projection_head_write() -> Iterator[None]:
    with _flag_scope(PROJECTION_HEAD_WRITE_FLAG):
        yield


@contextmanager
def projection_repository_write(
    service_actor_user_id: str,
) -> Iterator[ProjectionSupportWriteCapability]:
    """Authorize one observation, head and structural audit transaction."""

    _require_projection_service_actor(service_actor_user_id)
    capability = ProjectionSupportWriteCapability(
        actor=service_actor_user_id,
        allowed=PROJECTION_REPOSITORY_WRITES,
    )
    token = _CURRENT_SUPPORT_CAPABILITY.set(capability)
    try:
        with (
            _flag_scope(PROJECTION_OBSERVATION_WRITE_FLAG),
            _flag_scope(PROJECTION_HEAD_WRITE_FLAG),
            _flag_scope(AUDIT_APPEND_FLAG),
        ):
            yield capability
    finally:
        _CURRENT_SUPPORT_CAPABILITY.reset(token)


def insert_projection_support_document(
    document: Any,
    *,
    capability: ProjectionSupportWriteCapability,
) -> Any:
    """Insert one exact projection support row under the active capability."""

    _authorize_projection_support_write(
        document,
        action="insert",
        capability=capability,
    )
    return document.insert(ignore_permissions=True)


def save_projection_support_document(
    document: Any,
    *,
    capability: ProjectionSupportWriteCapability,
) -> Any:
    """Save one exact projection head under the active capability."""

    _authorize_projection_support_write(
        document,
        action="save",
        capability=capability,
    )
    return document.save(ignore_permissions=True)


def _require_projection_service_actor(service_actor_user_id: str) -> None:
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
                "ERP projection heads can only be changed by the controlled projection service."
            ),
            frappe.PermissionError,
        )


def _authorize_projection_support_write(
    document: Any,
    *,
    action: str,
    capability: ProjectionSupportWriteCapability,
) -> None:
    doctype = str(getattr(document, "doctype", ""))
    flag = _SUPPORT_FLAGS.get(doctype)
    if (
        _CURRENT_SUPPORT_CAPABILITY.get() is not capability
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or (doctype, action) not in capability.allowed
        or flag is None
        or not getattr(frappe.flags, flag, False)
    ):
        frappe.throw(
            _(
                "ERP projection heads can only be changed by the controlled projection service."
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
