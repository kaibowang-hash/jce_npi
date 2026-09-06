from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

import frappe
from frappe import _

from npi_integration.authorization_projection.frappe_validation import (
    require_service_actor,
)
from npi_integration.master_data.domain import MasterCatalogKind


MASTER_DATA_WRITE_FLAG = "npi_erp_master_data_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


@dataclass(frozen=True, slots=True)
class MasterDataWriteCapability:
    actor: str
    kind: MasterCatalogKind


_CURRENT: ContextVar[MasterDataWriteCapability | None] = ContextVar(
    "npi_erp_master_data_capability",
    default=None,
)


@contextmanager
def master_data_write(
    actor: str,
    kind: MasterCatalogKind,
) -> Iterator[MasterDataWriteCapability]:
    require_service_actor(actor)
    if not isinstance(kind, MasterCatalogKind):
        raise RuntimeError("Master data capability is invalid.")
    capability = MasterDataWriteCapability(actor, kind)
    token = _CURRENT.set(capability)
    with _flag_scope(MASTER_DATA_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
        try:
            yield capability
        finally:
            _CURRENT.reset(token)


def require_master_data_write() -> None:
    if not getattr(frappe.flags, MASTER_DATA_WRITE_FLAG, False):
        frappe.throw(
            _(
                "ERPNext master data can only be changed by the controlled integration service."
            ),
            frappe.PermissionError,
        )


def deny_master_data_delete() -> None:
    frappe.throw(
        _("ERPNext master data synchronization history cannot be deleted."),
        frappe.PermissionError,
    )


def insert_master_document(
    document: Any,
    *,
    capability: MasterDataWriteCapability,
) -> Any:
    _authorize(document, capability)
    return document.insert(ignore_permissions=True)


def save_master_document(
    document: Any,
    *,
    capability: MasterDataWriteCapability,
) -> Any:
    _authorize(document, capability)
    return document.save(ignore_permissions=True)


def insert_master_audit(
    document: Any,
    *,
    capability: MasterDataWriteCapability,
) -> Any:
    if (
        _CURRENT.get() is not capability
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or str(getattr(document, "doctype", "")) != "NPI Audit Event"
        or not getattr(frappe.flags, AUDIT_APPEND_FLAG, False)
    ):
        raise RuntimeError("Master data audit capability is invalid.")
    return document.insert(ignore_permissions=True)


def _authorize(document: Any, capability: MasterDataWriteCapability) -> None:
    if (
        _CURRENT.get() is not capability
        or getattr(getattr(frappe, "session", None), "user", None)
        != capability.actor
        or not getattr(frappe.flags, MASTER_DATA_WRITE_FLAG, False)
        or str(getattr(document, "doctype", ""))
        not in {
            "NPI ERP Master Catalog Head",
            "NPI ERP Master Catalog Entry",
            "NPI ERP Master Snapshot",
        }
        or str(getattr(document, "catalog_kind", "")) != capability.kind.value
    ):
        raise RuntimeError("Master data write capability is invalid.")


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
