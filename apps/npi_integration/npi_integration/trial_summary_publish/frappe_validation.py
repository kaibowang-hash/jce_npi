from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _

WRITE_FLAG = "npi_trial_summary_delivery_write"


@dataclass(frozen=True, slots=True)
class TrialSummaryDeliveryCapability:
    request_global_id: str


_CURRENT: ContextVar[TrialSummaryDeliveryCapability | None] = ContextVar(
    "npi_trial_summary_delivery_capability",
    default=None,
)


@contextmanager
def delivery_write(request_global_id: str) -> Iterator[TrialSummaryDeliveryCapability]:
    if not isinstance(request_global_id, str) or not request_global_id:
        raise RuntimeError("Trial Summary delivery capability is invalid.")
    capability = TrialSummaryDeliveryCapability(request_global_id)
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


def require_delivery_write() -> None:
    if not getattr(frappe.flags, WRITE_FLAG, False):
        frappe.throw(
            _(
                "Trial Summary deliveries can only be changed by the controlled integration service."
            ),
            frappe.PermissionError,
        )


def deny_delivery_delete() -> None:
    frappe.throw(
        _("Trial Summary delivery history cannot be deleted."),
        frappe.PermissionError,
    )


def insert_support_document(
    document: Any,
    *,
    capability: TrialSummaryDeliveryCapability,
) -> Any:
    _authorize(document, capability)
    return document.insert(ignore_permissions=True)


def save_support_document(
    document: Any,
    *,
    capability: TrialSummaryDeliveryCapability,
) -> Any:
    _authorize(document, capability)
    return document.save(ignore_permissions=True)


def _authorize(document: Any, capability: TrialSummaryDeliveryCapability) -> None:
    doctype = str(getattr(document, "doctype", ""))
    bound_request = str(
        getattr(document, "global_id", "")
        if doctype == "NPI Trial Summary Delivery"
        else getattr(document, "delivery_global_id", "")
    )
    if (
        _CURRENT.get() is not capability
        or not getattr(frappe.flags, WRITE_FLAG, False)
        or doctype
        not in {"NPI Trial Summary Delivery", "NPI Trial Summary Delivery Attempt"}
        or bound_request != capability.request_global_id
    ):
        raise RuntimeError("Trial Summary delivery capability is invalid.")
