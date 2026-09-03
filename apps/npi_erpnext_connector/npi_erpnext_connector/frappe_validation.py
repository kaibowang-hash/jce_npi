from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


DELIVERY_WRITE_FLAG = "npi_erp_authorization_delivery_write"


@dataclass(frozen=True, slots=True)
class DeliveryWriteCapability:
    delivery_id: str


_CURRENT: ContextVar[DeliveryWriteCapability | None] = ContextVar(
    "npi_erp_authorization_delivery_capability",
    default=None,
)


@contextmanager
def delivery_write(delivery_id: str) -> Iterator[DeliveryWriteCapability]:
    if not isinstance(delivery_id, str) or not delivery_id:
        raise RuntimeError("Authorization delivery capability is invalid.")
    capability = DeliveryWriteCapability(delivery_id)
    token = _CURRENT.set(capability)
    previous = getattr(frappe.flags, DELIVERY_WRITE_FLAG, None)
    setattr(frappe.flags, DELIVERY_WRITE_FLAG, True)
    try:
        yield capability
    finally:
        _CURRENT.reset(token)
        if previous is None:
            try:
                delattr(frappe.flags, DELIVERY_WRITE_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, DELIVERY_WRITE_FLAG, previous)


def require_delivery_write() -> None:
    if not getattr(frappe.flags, DELIVERY_WRITE_FLAG, False):
        frappe.throw(
            _(
                "Authorization deliveries can only be changed by the controlled sender."
            ),
            frappe.PermissionError,
        )


def deny_delivery_delete() -> None:
    frappe.throw(
        _("Authorization delivery history cannot be deleted."),
        frappe.PermissionError,
    )


def insert_delivery_document(
    document: Any,
    *,
    capability: DeliveryWriteCapability,
) -> Any:
    _authorize(document, capability)
    return document.insert(ignore_permissions=True)


def save_delivery_document(
    document: Any,
    *,
    capability: DeliveryWriteCapability,
) -> Any:
    _authorize(document, capability)
    return document.save(ignore_permissions=True)


def _authorize(document: Any, capability: DeliveryWriteCapability) -> None:
    document_id = str(getattr(document, "name", "") or "")
    event_id = str(getattr(document, "event_id", "") or "")
    if (
        _CURRENT.get() is not capability
        or not getattr(frappe.flags, DELIVERY_WRITE_FLAG, False)
        or str(getattr(document, "doctype", ""))
        != "NPI ERP Authorization Delivery"
        or capability.delivery_id not in {document_id, event_id}
    ):
        raise RuntimeError("Authorization delivery capability is invalid.")
