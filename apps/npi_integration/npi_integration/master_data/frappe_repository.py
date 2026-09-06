from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid5

import frappe

from npi_core.foundation.errors import VersionConflict
from npi_integration.master_data.domain import (
    MAX_RECORDS,
    MasterCatalogKind,
    MasterRecord,
    MasterSnapshotEvent,
    canonical_json,
)
from npi_integration.master_data.frappe_validation import (
    insert_master_audit,
    insert_master_document,
    master_data_write,
    save_master_document,
)


HEAD_DOCTYPE = "NPI ERP Master Catalog Head"
ENTRY_DOCTYPE = "NPI ERP Master Catalog Entry"
SNAPSHOT_DOCTYPE = "NPI ERP Master Snapshot"
MAX_QUERY_LIMIT = 200
MAX_QUERY_OFFSET = 50_000
AUDIT_NAMESPACE = UUID("955fffd4-46b2-43f4-b160-9c52c1af08a8")


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    snapshot_id: UUID
    source_version: int
    record_count: int
    payload_hash: str
    exact_replay: bool


def apply_snapshot(
    event: MasterSnapshotEvent,
    *,
    actor: str,
    tenant_id: str,
    request_id: UUID,
    now: datetime,
) -> ApplyOutcome:
    current = _aware_utc(now)
    issued = _stored_utc(event.issued_at)
    if issued > current + timedelta(minutes=5):
        raise VersionConflict()
    snapshot_id = event.snapshot_id(tenant_id)
    existing_snapshot = _optional_doc(SNAPSHOT_DOCTYPE, str(snapshot_id))
    if existing_snapshot is not None:
        if (
            str(existing_snapshot.event_id) == str(event.event_id)
            and str(existing_snapshot.event_hash) == event.event_hash
            and str(existing_snapshot.payload_hash) == event.payload_hash
            and int(existing_snapshot.source_version) == event.source_version
            and int(existing_snapshot.record_count) == len(event.records)
        ):
            return ApplyOutcome(
                snapshot_id,
                event.source_version,
                len(event.records),
                event.payload_hash,
                True,
            )
        raise VersionConflict()

    head_id = event.head_id(tenant_id)
    head = _locked_doc(HEAD_DOCTYPE, str(head_id))
    if head is not None and event.source_version <= int(head.source_version):
        raise VersionConflict()

    existing_entries = {
        str(row["global_id"]): str(row["name"])
        for row in frappe.get_all(
            ENTRY_DOCTYPE,
            filters={"tenant_id": tenant_id, "catalog_kind": event.kind.value},
            fields=["name", "global_id"],
            order_by="name asc",
            page_length=10_001,
        )
    }
    if len(existing_entries) > 10_000:
        raise RuntimeError("ERPNext master data entry count exceeds the safe bound.")

    with master_data_write(actor, event.kind) as capability:
        snapshot = frappe.get_doc(
            {
                "doctype": SNAPSHOT_DOCTYPE,
                "global_id": str(snapshot_id),
                "tenant_id": tenant_id,
                "catalog_kind": event.kind.value,
                "source_environment": event.source_environment,
                "event_id": str(event.event_id),
                "event_hash": event.event_hash,
                "source_version": event.source_version,
                "source_modified_at": _naive_utc(event.source_modified_at),
                "record_count": len(event.records),
                "payload_hash": event.payload_hash,
                "records_json": canonical_json(
                    [record.mapping() for record in event.records]
                ),
                "source_trace_id": event.trace_id,
                "request_id": str(request_id),
                "applied_at": current.replace(tzinfo=None, microsecond=0),
            }
        )
        insert_master_document(snapshot, capability=capability)

        seen: set[str] = set()
        for record in event.records:
            entry_id = str(event.entry_id(tenant_id, record.source_key))
            seen.add(entry_id)
            values = _entry_values(
                event,
                record,
                tenant_id=tenant_id,
                snapshot_id=snapshot_id,
            )
            name = existing_entries.get(entry_id)
            if name is None:
                entry = frappe.get_doc(
                    {"doctype": ENTRY_DOCTYPE, "global_id": entry_id, **values}
                )
                insert_master_document(entry, capability=capability)
            else:
                entry = frappe.get_doc(ENTRY_DOCTYPE, name)
                entry.update(values)
                save_master_document(entry, capability=capability)

        for entry_id, name in existing_entries.items():
            if entry_id in seen:
                continue
            entry = frappe.get_doc(ENTRY_DOCTYPE, name)
            entry.enabled = 0
            entry.present_in_source = 0
            entry.source_version = event.source_version
            entry.snapshot_id = str(snapshot_id)
            save_master_document(entry, capability=capability)

        head_values = {
            "tenant_id": tenant_id,
            "catalog_kind": event.kind.value,
            "source_environment": event.source_environment,
            "source_version": event.source_version,
            "source_modified_at": _naive_utc(event.source_modified_at),
            "current_snapshot_id": str(snapshot_id),
            "current_event_id": str(event.event_id),
            "payload_hash": event.payload_hash,
            "record_count": len(event.records),
            "last_synchronized_at": current.replace(tzinfo=None, microsecond=0),
        }
        if head is None:
            head = frappe.get_doc(
                {"doctype": HEAD_DOCTYPE, "global_id": str(head_id), **head_values}
            )
            insert_master_document(head, capability=capability)
        else:
            head.update(head_values)
            save_master_document(head, capability=capability)

        audit = frappe.get_doc(
            {
                "doctype": "NPI Audit Event",
                "event_id": str(uuid5(AUDIT_NAMESPACE, str(event.event_id))),
                "global_id": str(snapshot_id),
                "object_version": event.source_version,
                "actor": actor,
                "trace_id": event.trace_id,
                "operation": "replace_erp_master_catalog",
                "result": "applied",
                "input_summary": {
                    "catalogKind": event.kind.value,
                    "recordCount": len(event.records),
                    "payloadHash": event.payload_hash,
                },
            }
        )
        insert_master_audit(audit, capability=capability)

    return ApplyOutcome(
        snapshot_id,
        event.source_version,
        len(event.records),
        event.payload_hash,
        False,
    )


def catalog_collection(
    *,
    tenant_id: str,
    kind: MasterCatalogKind,
    query: str | None,
    limit: int,
    offset: int,
    allowed_source_keys: frozenset[str] | None,
) -> dict[str, object]:
    if not isinstance(kind, MasterCatalogKind):
        raise ValueError("Master catalog kind is invalid.")
    if type(limit) is not int or not 1 <= limit <= MAX_QUERY_LIMIT:
        raise ValueError("Master catalog page limit is invalid.")
    if type(offset) is not int or not 0 <= offset <= MAX_QUERY_OFFSET:
        raise ValueError("Master catalog page offset is invalid.")
    if allowed_source_keys is not None and (
        not isinstance(allowed_source_keys, frozenset)
        or any(not isinstance(value, str) or not value for value in allowed_source_keys)
    ):
        raise ValueError("Master catalog access scope is invalid.")
    filters: dict[str, object] = {
        "tenant_id": tenant_id,
        "catalog_kind": kind.value,
        "present_in_source": 1,
    }
    if allowed_source_keys is not None:
        filters["source_key"] = ["in", tuple(sorted(allowed_source_keys))]
    or_filters = None
    if query:
        pattern = f"%{query}%"
        or_filters = {"source_key": ["like", pattern], "display_name": ["like", pattern]}
    rows: list[Any] = []
    total = 0
    if allowed_source_keys is None or allowed_source_keys:
        matches = frappe.get_all(
            ENTRY_DOCTYPE,
            filters=filters,
            or_filters=or_filters,
            fields=["name"],
            order_by="source_key asc",
            page_length=MAX_RECORDS + 1,
        )
        if len(matches) > MAX_RECORDS:
            raise RuntimeError("ERPNext master data query exceeds the safe bound.")
        total = len(matches)
        rows = frappe.get_all(
            ENTRY_DOCTYPE,
            filters=filters,
            or_filters=or_filters,
            fields=[
                "source_key",
                "display_name",
                "enabled",
                "group_key",
                "parent_key",
                "stock_uom",
                "is_group",
                "is_stock_item",
                "source_modified_at",
                "source_version",
            ],
            order_by="source_key asc",
            start=offset,
            page_length=limit,
        )
    head = frappe.db.get_value(
        HEAD_DOCTYPE,
        {"tenant_id": tenant_id, "catalog_kind": kind.value},
        ["source_version", "source_modified_at", "last_synchronized_at", "record_count"],
        as_dict=True,
    )
    return {
        "schemaVersion": 1,
        "catalogKind": kind.value,
        "sourceVersion": int(head.get("source_version") or 0) if head else 0,
        "sourceModifiedAt": _api_time(head.get("source_modified_at")) if head else None,
        "lastSynchronizedAt": _api_time(head.get("last_synchronized_at")) if head else None,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_api_entry(kind, row) for row in rows],
    }


def _entry_values(
    event: MasterSnapshotEvent,
    record: MasterRecord,
    *,
    tenant_id: str,
    snapshot_id: UUID,
) -> dict[str, object]:
    values = record.values
    return {
        "tenant_id": tenant_id,
        "catalog_kind": event.kind.value,
        "source_key": record.source_key,
        "display_name": str(values["displayName"]),
        "enabled": int(bool(values["enabled"])),
        "present_in_source": 1,
        "group_key": values.get("groupKey"),
        "parent_key": values.get("parentKey"),
        "stock_uom": values.get("stockUom"),
        "is_group": int(bool(values.get("isGroup", False))),
        "is_stock_item": int(bool(values.get("isStockItem", False))),
        "source_modified_at": _naive_utc(str(values["sourceModifiedAt"])),
        "source_version": event.source_version,
        "snapshot_id": str(snapshot_id),
        "source_hash": record.source_hash,
    }


def _api_entry(kind: MasterCatalogKind, row: Any) -> dict[str, object]:
    result: dict[str, object] = {
        "sourceKey": str(row.get("source_key")),
        "displayName": str(row.get("display_name")),
        "enabled": bool(row.get("enabled")),
        "sourceModifiedAt": _api_time(row.get("source_modified_at")),
    }
    if kind in {MasterCatalogKind.CUSTOMER, MasterCatalogKind.SUPPLIER, MasterCatalogKind.MACHINE}:
        result["groupKey"] = row.get("group_key") or None
    elif kind is MasterCatalogKind.ITEM_GROUP:
        result["parentKey"] = row.get("parent_key") or None
        result["isGroup"] = bool(row.get("is_group"))
    else:
        result["groupKey"] = str(row.get("group_key") or "")
        result["stockUom"] = str(row.get("stock_uom") or "")
        result["isStockItem"] = bool(row.get("is_stock_item"))
    return result


def _locked_doc(doctype: str, name: str):
    locked = frappe.db.get_value(doctype, name, "name", for_update=True)
    return frappe.get_doc(doctype, name) if locked else None


def _optional_doc(doctype: str, name: str):
    return frappe.get_doc(doctype, name) if frappe.db.exists(doctype, name) else None


def _stored_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _naive_utc(value: object) -> datetime:
    return _stored_utc(value).replace(tzinfo=None, microsecond=0)


def _aware_utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Master data server time must be timezone aware.")
    return value.astimezone(UTC)


def _api_time(value: object) -> str:
    return _stored_utc(value).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
