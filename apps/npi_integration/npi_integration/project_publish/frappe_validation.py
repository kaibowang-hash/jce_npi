from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


WRITE_FLAG = "npi_erp_project_publish_write"


@dataclass(frozen=True, slots=True)
class ProjectPublishCapability:
    request_global_id: str


_CURRENT: ContextVar[ProjectPublishCapability | None] = ContextVar(
    "npi_erp_project_publish_capability",
    default=None,
)


@contextmanager
def project_publish_write(request_global_id: str) -> Iterator[ProjectPublishCapability]:
    if not isinstance(request_global_id, str) or not request_global_id:
        raise RuntimeError("ERP Project publication capability is invalid.")
    capability = ProjectPublishCapability(request_global_id)
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


def require_project_publish_write() -> None:
    if not getattr(frappe.flags, WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERP Project publication records can only be changed by the controlled integration service."
            ),
            frappe.PermissionError,
        )


def deny_project_publish_delete() -> None:
    frappe.throw(
        _("ERP Project publication history cannot be deleted."),
        frappe.PermissionError,
    )


def insert_support_document(
    document: Any,
    *,
    capability: ProjectPublishCapability,
) -> Any:
    _authorize(document, capability)
    return document.insert(ignore_permissions=True)


def save_support_document(
    document: Any,
    *,
    capability: ProjectPublishCapability,
) -> Any:
    _authorize(document, capability)
    return document.save(ignore_permissions=True)


def _authorize(document: Any, capability: ProjectPublishCapability) -> None:
    doctype = str(getattr(document, "doctype", ""))
    bound_request = str(
        getattr(document, "global_id", "")
        if doctype == "NPI ERP Project Publish Request"
        else getattr(document, "request_global_id", "")
    )
    if (
        _CURRENT.get() is not capability
        or not getattr(frappe.flags, WRITE_FLAG, False)
        or doctype
        not in {
            "NPI ERP Project Publish Request",
            "NPI ERP Project Publish Attempt",
            "NPI ERP Project Publish Result",
        }
        or bound_request != capability.request_global_id
    ):
        raise RuntimeError("ERP Project publication capability is invalid.")
