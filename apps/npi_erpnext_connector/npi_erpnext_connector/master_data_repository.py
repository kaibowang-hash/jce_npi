from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import frappe

from npi_erpnext_connector.master_data_validation import (
    insert_master_data_delivery_document,
    master_data_delivery_write,
    save_master_data_delivery_document,
)
from npi_erpnext_connector.master_data_config import (
    load_master_data_profile,
    master_data_sender_is_disabled,
)
from npi_erpnext_connector.master_data_domain import (
    MAX_RECORDS,
    MasterCatalogKind,
    MasterDataSenderError,
    SourceMasterSnapshot,
    build_event,
    canonical_json,
    restore_event,
    utc_text,
)


DELIVERY_DOCTYPE = "NPI ERP Master Data Delivery"
DELIVERY_JOB = "npi_erpnext_connector.master_data_worker.deliver_master_data"
UTC = timezone.utc
MASTER_DATA_REFRESH_INTERVAL = timedelta(hours=1)
_SOURCE_DOCTYPES = {
    MasterCatalogKind.CUSTOMER: "Customer",
    MasterCatalogKind.SUPPLIER: "Supplier",
    MasterCatalogKind.ITEM_GROUP: "Item Group",
    MasterCatalogKind.ITEM: "Item",
    MasterCatalogKind.MACHINE: "Workstation",
}
_SOURCE_FIELDS = {
    MasterCatalogKind.MACHINE: (
        "name", "workstation_name", "disabled", "workstation_type", "modified",
    ),
    MasterCatalogKind.CUSTOMER: (
        "name",
        "customer_name",
        "disabled",
        "customer_group",
        "modified",
    ),
    MasterCatalogKind.SUPPLIER: (
        "name",
        "supplier_name",
        "disabled",
        "supplier_group",
        "modified",
    ),
    MasterCatalogKind.ITEM_GROUP: (
        "name",
        "item_group_name",
        "parent_item_group",
        "is_group",
        "modified",
    ),
    MasterCatalogKind.ITEM: (
        "name",
        "item_name",
        "disabled",
        "item_group",
        "stock_uom",
        "is_stock_item",
        "modified",
    ),
}


def enqueue_master_catalog(catalog_kind: str) -> str | None:
    if master_data_sender_is_disabled(frappe.conf):
        return None
    profile = load_master_data_profile(frappe.conf)
    kind = MasterCatalogKind(catalog_kind)
    snapshot = load_source_snapshot(kind)
    now = datetime.now(UTC)
    latest = _latest_delivery(kind)
    if latest and latest.get("source_snapshot_hash") == snapshot.snapshot_hash:
        if latest.get("status") in {"pending", "retry"}:
            _enqueue_delivery(str(latest["name"]))
            return str(latest["name"])
        if latest.get("status") == "delivered" and _delivered_snapshot_is_fresh(
            latest.get("delivered_at"),
            now=now,
        ):
            return str(latest["name"])
    version = int(latest.get("source_version") or 0) + 1 if latest else 1
    event = build_event(
        snapshot,
        source_version=version,
        issued_at=now,
        source_environment=profile.environment_code,
    )
    for attempt in range(2):
        try:
            delivery = _insert_delivery(event)
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
            frappe.db.rollback()
            if attempt == 0:
                existing = _delivery_by_event(str(event.event_id))
                if existing:
                    _enqueue_delivery(str(existing["name"]))
                    return str(existing["name"])
                continue
            raise
        _enqueue_delivery(str(delivery.name))
        return str(delivery.name)
    raise RuntimeError("Master data delivery concurrency recovery failed.")


def load_source_snapshot(kind: MasterCatalogKind) -> SourceMasterSnapshot:
    doctype = _SOURCE_DOCTYPES[kind]
    fields = list(_SOURCE_FIELDS[kind])
    if kind is MasterCatalogKind.MACHINE:
        # v15 installations may predate Workstation's optional disabled field.
        meta = frappe.get_meta(doctype)
        fields = [field for field in fields if field in {"name", "modified"} or meta.has_field(field)]
    rows = frappe.get_all(
        doctype,
        fields=fields,
        order_by="name asc",
        page_length=MAX_RECORDS + 1,
    )
    if len(rows) > MAX_RECORDS:
        raise MasterDataSenderError("Master catalog exceeds the safe bound.")
    records = tuple(_record(kind, row) for row in rows)
    source_modified_at = max(
        (_datetime(row.get("modified")) for row in rows),
        default=datetime(1970, 1, 1, tzinfo=UTC),
    )
    return SourceMasterSnapshot(kind, source_modified_at, records)


def get_delivery(delivery_id: str):
    return frappe.get_doc(DELIVERY_DOCTYPE, delivery_id)


def save_delivery(delivery: object) -> None:
    with master_data_delivery_write(str(getattr(delivery, "name", ""))) as capability:
        save_master_data_delivery_document(delivery, capability=capability)


def restore_delivery_event(delivery: object):
    return restore_event(
        getattr(delivery, "event_json", None),
        request_id=getattr(delivery, "request_id", None),
        source_snapshot_hash=getattr(delivery, "source_snapshot_hash", None),
        event_hash=getattr(delivery, "event_hash", None),
    )


def _record(kind: MasterCatalogKind, row: object) -> dict[str, object]:
    source_key = _text(row.get("name"), "ERPNext master data key")
    modified = utc_text(_datetime(row.get("modified")))
    if kind is MasterCatalogKind.MACHINE:
        return {
            "sourceKey": source_key,
            "displayName": _display_text(row.get("workstation_name") or source_key, "Workstation name"),
            "enabled": not bool(row.get("disabled")),
            "groupKey": _optional_text(row.get("workstation_type")),
            "sourceModifiedAt": modified,
        }
    if kind is MasterCatalogKind.CUSTOMER:
        return {
            "sourceKey": source_key,
            "displayName": _display_text(
                row.get("customer_name") or source_key, "Customer name"
            ),
            "enabled": not bool(row.get("disabled")),
            "groupKey": _optional_text(row.get("customer_group")),
            "sourceModifiedAt": modified,
        }
    if kind is MasterCatalogKind.SUPPLIER:
        return {
            "sourceKey": source_key,
            "displayName": _display_text(
                row.get("supplier_name") or source_key, "Supplier name"
            ),
            "enabled": not bool(row.get("disabled")),
            "groupKey": _optional_text(row.get("supplier_group")),
            "sourceModifiedAt": modified,
        }
    if kind is MasterCatalogKind.ITEM_GROUP:
        return {
            "sourceKey": source_key,
            "displayName": _display_text(
                row.get("item_group_name") or source_key, "Item Group name"
            ),
            "enabled": True,
            "parentKey": _optional_text(row.get("parent_item_group")),
            "isGroup": bool(row.get("is_group")),
            "sourceModifiedAt": modified,
        }
    return {
        "sourceKey": source_key,
        "displayName": _display_text(row.get("item_name") or source_key, "Item name"),
        "enabled": not bool(row.get("disabled")),
        "groupKey": _text(row.get("item_group"), "Item Group"),
        "stockUom": _text(row.get("stock_uom"), "Stock UOM"),
        "isStockItem": bool(row.get("is_stock_item")),
        "sourceModifiedAt": modified,
    }


def _insert_delivery(event):
    document = frappe.get_doc(
        {
            "doctype": DELIVERY_DOCTYPE,
            "event_id": str(event.event_id),
            "stream_key": hashlib.sha256(
                f"{event.kind.value}:{event.source_version}".encode("utf-8")
            ).hexdigest(),
            "catalog_kind": event.kind.value,
            "source_version": event.source_version,
            "source_snapshot_hash": event.source_snapshot_hash,
            "event_hash": event.event_hash,
            "event_json": canonical_json(event.event),
            "request_id": str(event.request_id),
            "trace_id": event.trace_id,
            "record_count": len(event.event["records"]),
            "status": "pending",
            "attempt_count": 0,
        }
    )
    with master_data_delivery_write(str(event.event_id)) as capability:
        return insert_master_data_delivery_document(document, capability=capability)


def _latest_delivery(kind: MasterCatalogKind) -> dict[str, object] | None:
    rows = frappe.get_all(
        DELIVERY_DOCTYPE,
        filters={"catalog_kind": kind.value},
        fields=[
            "name",
            "source_version",
            "source_snapshot_hash",
            "status",
            "delivered_at",
        ],
        order_by="source_version desc",
        page_length=1,
    )
    return dict(rows[0]) if rows else None


def _delivered_snapshot_is_fresh(value: object, *, now: datetime) -> bool:
    if value in (None, ""):
        return False
    delivered_at = _datetime(value)
    if delivered_at > now + timedelta(minutes=5):
        raise MasterDataSenderError("Master data delivery time is invalid.")
    return delivered_at >= now - MASTER_DATA_REFRESH_INTERVAL


def _delivery_by_event(event_id: str) -> dict[str, object] | None:
    row = frappe.db.get_value(DELIVERY_DOCTYPE, event_id, ["name", "status"], as_dict=True)
    return dict(row) if row else None


def _enqueue_delivery(delivery_id: str) -> None:
    frappe.enqueue(
        DELIVERY_JOB,
        queue="short",
        enqueue_after_commit=True,
        job_id=f"npi-erp-master-{delivery_id}",
        delivery_id=delivery_id,
    )


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as error:
            raise MasterDataSenderError("Master data modified time is invalid.") from error
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _text(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise MasterDataSenderError(f"{label} is invalid.")
    return value


def _display_text(value: object, label: str) -> str:
    if isinstance(value, str):
        value = "".join(
            " " if ord(character) < 32 or ord(character) == 127 else character
            for character in value
        ).strip(" ")
    return _text(value, label)


def _optional_text(value: object) -> str | None:
    return None if value in (None, "") else _text(value, "Master data reference")
