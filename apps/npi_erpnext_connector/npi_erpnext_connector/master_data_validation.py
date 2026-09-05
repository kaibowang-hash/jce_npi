from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


MASTER_DATA_DELIVERY_WRITE_FLAG = "npi_erp_master_data_delivery_write"


@dataclass(frozen=True, slots=True)
class MasterDataDeliveryWriteCapability:
    delivery_id: str


_CURRENT: ContextVar[MasterDataDeliveryWriteCapability | None] = ContextVar(
    "npi_erp_master_data_delivery_capability",
    default=None,
)


@contextmanager
def master_data_delivery_write(
    delivery_id: str,
) -> Iterator[MasterDataDeliveryWriteCapability]:
    if not isinstance(delivery_id, str) or not delivery_id:
        raise RuntimeError("Master data delivery capability is invalid.")
    capability = MasterDataDeliveryWriteCapability(delivery_id)
    token = _CURRENT.set(capability)
    missing = object()
    previous = getattr(frappe.flags, MASTER_DATA_DELIVERY_WRITE_FLAG, missing)
    setattr(frappe.flags, MASTER_DATA_DELIVERY_WRITE_FLAG, True)
    try:
        yield capability
    finally:
        _CURRENT.reset(token)
        if previous is missing:
            try:
                delattr(frappe.flags, MASTER_DATA_DELIVERY_WRITE_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, MASTER_DATA_DELIVERY_WRITE_FLAG, previous)


def require_master_data_delivery_write() -> None:
    if not getattr(frappe.flags, MASTER_DATA_DELIVERY_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERPNext master data deliveries can only be changed by the controlled integration service."
            ),
            frappe.PermissionError,
        )


def deny_master_data_delivery_delete() -> None:
    frappe.throw(
        _("ERPNext master data delivery history cannot be deleted."),
        frappe.PermissionError,
    )


def insert_master_data_delivery_document(
    document: Any,
    *,
    capability: MasterDataDeliveryWriteCapability,
) -> Any:
    _authorize(document, capability)
    return document.insert(ignore_permissions=True)


def save_master_data_delivery_document(
    document: Any,
    *,
    capability: MasterDataDeliveryWriteCapability,
) -> Any:
    _authorize(document, capability)
    return document.save(ignore_permissions=True)


def _authorize(
    document: Any,
    capability: MasterDataDeliveryWriteCapability,
) -> None:
    if (
        _CURRENT.get() is not capability
        or not getattr(frappe.flags, MASTER_DATA_DELIVERY_WRITE_FLAG, False)
        or str(getattr(document, "doctype", "")) != "NPI ERP Master Data Delivery"
        or str(getattr(document, "name", "") or getattr(document, "event_id", ""))
        != capability.delivery_id
    ):
        raise RuntimeError("Master data delivery capability is invalid.")
