from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


WRITE_FLAG = "npi_erp_project_publish_execution_write"


@dataclass(frozen=True, slots=True)
class ProjectPublishExecutionCapability:
    request_global_id: str


_CURRENT: ContextVar[ProjectPublishExecutionCapability | None] = ContextVar(
    "npi_erp_project_publish_execution_capability",
    default=None,
)


@contextmanager
def project_publish_execution_write(request_global_id: str) -> Iterator[ProjectPublishExecutionCapability]:
    if not isinstance(request_global_id, str) or not request_global_id:
        raise RuntimeError("ERP Project publication execution capability is invalid.")
    capability = ProjectPublishExecutionCapability(request_global_id)
    token = _CURRENT.set(capability)
    previous = getattr(frappe.flags, WRITE_FLAG, None)
    setattr(frappe.flags, WRITE_FLAG, True)
    try:
        yield capability
    finally:
        _CURRENT.reset(token)
        if previous is None:
            try:
                delattr(frappe.flags, WRITE_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, WRITE_FLAG, previous)


def require_project_publish_execution_write() -> None:
    if not getattr(frappe.flags, WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERP Project publication records can only be changed by the controlled operation."
            ),
            frappe.PermissionError,
        )


def deny_project_publish_execution_delete() -> None:
    frappe.throw(
        _("ERP Project publication history cannot be deleted."),
        frappe.PermissionError,
    )


def insert_target(document: Any, *, capability: ProjectPublishExecutionCapability) -> Any:
    _authorize(document, capability, target=True)
    return document.insert(ignore_permissions=True)


def insert_support(document: Any, *, capability: ProjectPublishExecutionCapability) -> Any:
    _authorize(document, capability, target=False)
    return document.insert(ignore_permissions=True)


def _authorize(document: Any, capability: ProjectPublishExecutionCapability, *, target: bool) -> None:
    doctype = str(getattr(document, "doctype", ""))
    bound_request = str(getattr(document, "request_global_id", "") or getattr(document, "last_request_global_id", "") or "")
    if _CURRENT.get() is not capability or not getattr(frappe.flags, WRITE_FLAG, False):
        raise RuntimeError("ERP Project publication execution capability is invalid.")
    if target:
        if doctype != "Project":
            raise RuntimeError("ERP Project publication target is invalid.")
    elif doctype not in {"NPI ERP Project Publish Mapping", "NPI ERP Project Publish Receipt"} or bound_request != capability.request_global_id:
        raise RuntimeError("ERP Project publication support scope is invalid.")
