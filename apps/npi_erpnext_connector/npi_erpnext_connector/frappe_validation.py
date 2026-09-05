from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _


DELIVERY_WRITE_FLAG = "npi_erp_authorization_delivery_write"
ITEM_EXECUTION_WRITE_FLAG = "npi_erp_item_execution_write"
MBOM_EXECUTION_WRITE_FLAG = "npi_erp_mbom_execution_write"
TOOL_ASSET_EXECUTION_WRITE_FLAG = "npi_erp_tool_asset_execution_write"
PROJECT_DELIVERY_WRITE_FLAG = "npi_erp_project_delivery_write"
TRIAL_SUMMARY_EXECUTION_WRITE_FLAG = "npi_erp_trial_summary_execution_write"


@dataclass(frozen=True, slots=True)
class DeliveryWriteCapability:
    delivery_id: str


_CURRENT: ContextVar[DeliveryWriteCapability | None] = ContextVar(
    "npi_erp_authorization_delivery_capability",
    default=None,
)


@dataclass(frozen=True, slots=True)
class ProjectDeliveryWriteCapability:
    delivery_id: str


_PROJECT_DELIVERY_CURRENT: ContextVar[ProjectDeliveryWriteCapability | None] = (
    ContextVar(
        "npi_erp_project_delivery_capability",
        default=None,
    )
)


@dataclass(frozen=True, slots=True)
class ItemExecutionWriteCapability:
    request_global_id: str


_ITEM_CURRENT: ContextVar[ItemExecutionWriteCapability | None] = ContextVar(
    "npi_erp_item_execution_capability",
    default=None,
)


@dataclass(frozen=True, slots=True)
class MbomExecutionWriteCapability:
    request_global_id: str


_MBOM_CURRENT: ContextVar[MbomExecutionWriteCapability | None] = ContextVar(
    "npi_erp_mbom_execution_capability",
    default=None,
)


@dataclass(frozen=True, slots=True)
class ToolAssetExecutionWriteCapability:
    request_global_id: str


_TOOL_ASSET_CURRENT: ContextVar[ToolAssetExecutionWriteCapability | None] = (
    ContextVar(
        "npi_erp_tool_asset_execution_capability",
        default=None,
    )
)


@dataclass(frozen=True, slots=True)
class TrialSummaryExecutionWriteCapability:
    request_global_id: str


_TRIAL_SUMMARY_CURRENT: ContextVar[TrialSummaryExecutionWriteCapability | None] = (
    ContextVar(
        "npi_erp_trial_summary_execution_capability",
        default=None,
    )
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


@contextmanager
def project_delivery_write(
    delivery_id: str,
) -> Iterator[ProjectDeliveryWriteCapability]:
    if not isinstance(delivery_id, str) or not delivery_id:
        raise RuntimeError("Project delivery capability is invalid.")
    capability = ProjectDeliveryWriteCapability(delivery_id)
    token = _PROJECT_DELIVERY_CURRENT.set(capability)
    previous = getattr(frappe.flags, PROJECT_DELIVERY_WRITE_FLAG, None)
    setattr(frappe.flags, PROJECT_DELIVERY_WRITE_FLAG, True)
    try:
        yield capability
    finally:
        _PROJECT_DELIVERY_CURRENT.reset(token)
        if previous is None:
            try:
                delattr(frappe.flags, PROJECT_DELIVERY_WRITE_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, PROJECT_DELIVERY_WRITE_FLAG, previous)


def require_project_delivery_write() -> None:
    if not getattr(frappe.flags, PROJECT_DELIVERY_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERPNext Project integration records can only be changed by the controlled sender."
            ),
            frappe.PermissionError,
        )


def deny_project_delivery_delete() -> None:
    frappe.throw(
        _("ERPNext Project integration history cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def item_execution_write(
    request_global_id: str,
) -> Iterator[ItemExecutionWriteCapability]:
    if not isinstance(request_global_id, str) or not request_global_id:
        raise RuntimeError("Item execution capability is invalid.")
    capability = ItemExecutionWriteCapability(request_global_id)
    token = _ITEM_CURRENT.set(capability)
    previous = getattr(frappe.flags, ITEM_EXECUTION_WRITE_FLAG, None)
    setattr(frappe.flags, ITEM_EXECUTION_WRITE_FLAG, True)
    try:
        yield capability
    finally:
        _ITEM_CURRENT.reset(token)
        if previous is None:
            try:
                delattr(frappe.flags, ITEM_EXECUTION_WRITE_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, ITEM_EXECUTION_WRITE_FLAG, previous)


def require_item_execution_write() -> None:
    if not getattr(frappe.flags, ITEM_EXECUTION_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERPNext Item integration records can only be changed by the controlled operation."
            ),
            frappe.PermissionError,
        )


def deny_item_execution_delete() -> None:
    frappe.throw(
        _("ERPNext Item integration history cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def mbom_execution_write(
    request_global_id: str,
) -> Iterator[MbomExecutionWriteCapability]:
    if not isinstance(request_global_id, str) or not request_global_id:
        raise RuntimeError("MBOM execution capability is invalid.")
    capability = MbomExecutionWriteCapability(request_global_id)
    token = _MBOM_CURRENT.set(capability)
    previous = getattr(frappe.flags, MBOM_EXECUTION_WRITE_FLAG, None)
    setattr(frappe.flags, MBOM_EXECUTION_WRITE_FLAG, True)
    try:
        yield capability
    finally:
        _MBOM_CURRENT.reset(token)
        if previous is None:
            try:
                delattr(frappe.flags, MBOM_EXECUTION_WRITE_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, MBOM_EXECUTION_WRITE_FLAG, previous)


def require_mbom_execution_write() -> None:
    if not getattr(frappe.flags, MBOM_EXECUTION_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERPNext MBOM integration records can only be changed by the controlled operation."
            ),
            frappe.PermissionError,
        )


def deny_mbom_execution_delete() -> None:
    frappe.throw(
        _("ERPNext MBOM integration history cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def tool_asset_execution_write(
    request_global_id: str,
) -> Iterator[ToolAssetExecutionWriteCapability]:
    if not isinstance(request_global_id, str) or not request_global_id:
        raise RuntimeError("Tool Asset execution capability is invalid.")
    capability = ToolAssetExecutionWriteCapability(request_global_id)
    token = _TOOL_ASSET_CURRENT.set(capability)
    previous = getattr(frappe.flags, TOOL_ASSET_EXECUTION_WRITE_FLAG, None)
    setattr(frappe.flags, TOOL_ASSET_EXECUTION_WRITE_FLAG, True)
    try:
        yield capability
    finally:
        _TOOL_ASSET_CURRENT.reset(token)
        if previous is None:
            try:
                delattr(frappe.flags, TOOL_ASSET_EXECUTION_WRITE_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, TOOL_ASSET_EXECUTION_WRITE_FLAG, previous)


def require_tool_asset_execution_write() -> None:
    if not getattr(frappe.flags, TOOL_ASSET_EXECUTION_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERPNext Tool Asset integration records can only be changed by the controlled operation."
            ),
            frappe.PermissionError,
        )


def deny_tool_asset_execution_delete() -> None:
    frappe.throw(
        _("ERPNext Tool Asset integration history cannot be deleted."),
        frappe.PermissionError,
    )


@contextmanager
def trial_summary_execution_write(
    request_global_id: str,
) -> Iterator[TrialSummaryExecutionWriteCapability]:
    if not isinstance(request_global_id, str) or not request_global_id:
        raise RuntimeError("Trial Summary execution capability is invalid.")
    capability = TrialSummaryExecutionWriteCapability(request_global_id)
    token = _TRIAL_SUMMARY_CURRENT.set(capability)
    previous = getattr(frappe.flags, TRIAL_SUMMARY_EXECUTION_WRITE_FLAG, None)
    setattr(frappe.flags, TRIAL_SUMMARY_EXECUTION_WRITE_FLAG, True)
    try:
        yield capability
    finally:
        _TRIAL_SUMMARY_CURRENT.reset(token)
        if previous is None:
            try:
                delattr(frappe.flags, TRIAL_SUMMARY_EXECUTION_WRITE_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, TRIAL_SUMMARY_EXECUTION_WRITE_FLAG, previous)


def require_trial_summary_execution_write() -> None:
    if not getattr(frappe.flags, TRIAL_SUMMARY_EXECUTION_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERPNext Trial Summary projection records can only be changed by the controlled operation."
            ),
            frappe.PermissionError,
        )


def deny_trial_summary_execution_delete() -> None:
    frappe.throw(
        _("ERPNext Trial Summary projection history cannot be deleted."),
        frappe.PermissionError,
    )


def insert_item_target_document(
    document: Any,
    *,
    capability: ItemExecutionWriteCapability,
) -> Any:
    _authorize_item_target(document, capability)
    return document.insert(ignore_permissions=True)


def save_item_target_document(
    document: Any,
    *,
    capability: ItemExecutionWriteCapability,
) -> Any:
    _authorize_item_target(document, capability)
    return document.save(ignore_permissions=True)


def insert_item_support_document(
    document: Any,
    *,
    capability: ItemExecutionWriteCapability,
) -> Any:
    _authorize_item_support(document, capability)
    return document.insert(ignore_permissions=True)


def save_item_support_document(
    document: Any,
    *,
    capability: ItemExecutionWriteCapability,
) -> Any:
    _authorize_item_support(document, capability)
    return document.save(ignore_permissions=True)


def insert_mbom_target_document(
    document: Any,
    *,
    capability: MbomExecutionWriteCapability,
) -> Any:
    _authorize_mbom_target(document, capability)
    return document.insert(ignore_permissions=True)


def save_mbom_target_document(
    document: Any,
    *,
    capability: MbomExecutionWriteCapability,
) -> Any:
    _authorize_mbom_target(document, capability)
    return document.save(ignore_permissions=True)


def insert_mbom_support_document(
    document: Any,
    *,
    capability: MbomExecutionWriteCapability,
) -> Any:
    _authorize_mbom_support(document, capability)
    return document.insert(ignore_permissions=True)


def save_mbom_support_document(
    document: Any,
    *,
    capability: MbomExecutionWriteCapability,
) -> Any:
    _authorize_mbom_support(document, capability)
    return document.save(ignore_permissions=True)


def insert_tool_asset_target_document(
    document: Any,
    *,
    capability: ToolAssetExecutionWriteCapability,
) -> Any:
    _authorize_tool_asset_target(document, capability)
    return document.insert(ignore_permissions=True)


def save_tool_asset_target_document(
    document: Any,
    *,
    capability: ToolAssetExecutionWriteCapability,
) -> Any:
    _authorize_tool_asset_target(document, capability)
    return document.save(ignore_permissions=True)


def insert_tool_asset_support_document(
    document: Any,
    *,
    capability: ToolAssetExecutionWriteCapability,
) -> Any:
    _authorize_tool_asset_support(document, capability)
    return document.insert(ignore_permissions=True)


def save_tool_asset_support_document(
    document: Any,
    *,
    capability: ToolAssetExecutionWriteCapability,
) -> Any:
    _authorize_tool_asset_support(document, capability)
    return document.save(ignore_permissions=True)


def insert_trial_summary_support_document(
    document: Any,
    *,
    capability: TrialSummaryExecutionWriteCapability,
) -> Any:
    _authorize_trial_summary_support(document, capability)
    return document.insert(ignore_permissions=True)


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


def insert_project_delivery_document(
    document: Any,
    *,
    capability: ProjectDeliveryWriteCapability,
) -> Any:
    _authorize_project_support(document, capability)
    return document.insert(ignore_permissions=True)


def save_project_delivery_document(
    document: Any,
    *,
    capability: ProjectDeliveryWriteCapability,
) -> Any:
    _authorize_project_support(document, capability)
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


def _authorize_project_support(
    document: Any,
    capability: ProjectDeliveryWriteCapability,
) -> None:
    document_id = str(getattr(document, "name", "") or "")
    event_id = str(getattr(document, "event_id", "") or "")
    source_project_id = str(getattr(document, "source_project_id", "") or "")
    if (
        _PROJECT_DELIVERY_CURRENT.get() is not capability
        or not getattr(frappe.flags, PROJECT_DELIVERY_WRITE_FLAG, False)
        or str(getattr(document, "doctype", ""))
        not in {"NPI ERP Project Delivery", "NPI ERP Project Mapping"}
        or capability.delivery_id
        not in {document_id, event_id, source_project_id}
    ):
        raise RuntimeError("Project delivery capability is invalid.")


def _authorize_item_target(
    document: Any,
    capability: ItemExecutionWriteCapability,
) -> None:
    if (
        _ITEM_CURRENT.get() is not capability
        or not getattr(frappe.flags, ITEM_EXECUTION_WRITE_FLAG, False)
        or str(getattr(document, "doctype", "")) != "Item"
    ):
        raise RuntimeError("Item execution capability is invalid.")


def _authorize_item_support(
    document: Any,
    capability: ItemExecutionWriteCapability,
) -> None:
    doctype = str(getattr(document, "doctype", ""))
    bound_request = str(
        getattr(document, "request_global_id", "")
        or getattr(document, "last_request_global_id", "")
        or ""
    )
    if (
        _ITEM_CURRENT.get() is not capability
        or not getattr(frappe.flags, ITEM_EXECUTION_WRITE_FLAG, False)
        or doctype not in {"NPI ERP Item Mapping", "NPI ERP Item Operation Receipt"}
        or bound_request != capability.request_global_id
    ):
        raise RuntimeError("Item execution capability is invalid.")


def _authorize_mbom_target(
    document: Any,
    capability: MbomExecutionWriteCapability,
) -> None:
    if (
        _MBOM_CURRENT.get() is not capability
        or not getattr(frappe.flags, MBOM_EXECUTION_WRITE_FLAG, False)
        or str(getattr(document, "doctype", "")) != "BOM"
    ):
        raise RuntimeError("MBOM execution capability is invalid.")


def _authorize_mbom_support(
    document: Any,
    capability: MbomExecutionWriteCapability,
) -> None:
    doctype = str(getattr(document, "doctype", ""))
    bound_request = str(
        getattr(document, "request_global_id", "")
        or getattr(document, "last_request_global_id", "")
        or ""
    )
    if (
        _MBOM_CURRENT.get() is not capability
        or not getattr(frappe.flags, MBOM_EXECUTION_WRITE_FLAG, False)
        or doctype
        not in {"NPI ERP MBOM Mapping", "NPI ERP MBOM Operation Receipt"}
        or bound_request != capability.request_global_id
    ):
        raise RuntimeError("MBOM execution capability is invalid.")


def _authorize_tool_asset_target(
    document: Any,
    capability: ToolAssetExecutionWriteCapability,
) -> None:
    if (
        _TOOL_ASSET_CURRENT.get() is not capability
        or not getattr(frappe.flags, TOOL_ASSET_EXECUTION_WRITE_FLAG, False)
        or str(getattr(document, "doctype", "")) != "Asset"
    ):
        raise RuntimeError("Tool Asset execution capability is invalid.")


def _authorize_tool_asset_support(
    document: Any,
    capability: ToolAssetExecutionWriteCapability,
) -> None:
    doctype = str(getattr(document, "doctype", ""))
    bound_request = str(
        getattr(document, "request_global_id", "")
        or getattr(document, "last_request_global_id", "")
        or ""
    )
    if (
        _TOOL_ASSET_CURRENT.get() is not capability
        or not getattr(frappe.flags, TOOL_ASSET_EXECUTION_WRITE_FLAG, False)
        or doctype
        not in {
            "NPI ERP Tool Asset Mapping",
            "NPI ERP Tool Asset Operation Receipt",
        }
        or bound_request != capability.request_global_id
    ):
        raise RuntimeError("Tool Asset execution capability is invalid.")


def _authorize_trial_summary_support(
    document: Any,
    capability: TrialSummaryExecutionWriteCapability,
) -> None:
    doctype = str(getattr(document, "doctype", ""))
    bound_request = str(getattr(document, "request_global_id", "") or "")
    if (
        _TRIAL_SUMMARY_CURRENT.get() is not capability
        or not getattr(frappe.flags, TRIAL_SUMMARY_EXECUTION_WRITE_FLAG, False)
        or doctype not in {"NPI ERP Trial Summary", "NPI ERP Trial Summary Fact"}
        or bound_request != capability.request_global_id
    ):
        raise RuntimeError("Trial Summary execution capability is invalid.")
