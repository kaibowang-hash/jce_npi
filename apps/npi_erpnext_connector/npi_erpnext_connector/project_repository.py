from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from uuid import UUID

import frappe

from .frappe_validation import (
    insert_project_delivery_document,
    project_delivery_write,
    save_project_delivery_document,
)
from .project_config import load_project_sender_profile, project_sender_is_disabled
from .project_domain import (
    ProjectSenderError,
    SourceProject,
    build_project_source_event,
    canonical_json,
    restore_project_source_event,
)


DELIVERY_DOCTYPE = "NPI ERP Project Delivery"
MAPPING_DOCTYPE = "NPI ERP Project Mapping"
DELIVERY_JOB = "npi_erpnext_connector.project_worker.deliver_project"
MAX_RECONCILIATION_PROJECTS = 1_000
UTC = timezone.utc


def enqueue_project(source_project_id: str) -> str | None:
    if project_sender_is_disabled(frappe.conf):
        return None
    profile = load_project_sender_profile(frappe.conf)
    if frappe.db.exists(MAPPING_DOCTYPE, source_project_id):
        return None
    source = _load_source_project(source_project_id)
    latest = _latest_delivery(source_project_id)
    if latest and latest.get("source_snapshot_hash") == source.snapshot_hash:
        if latest.get("status") in {"pending", "retry", "accepted"}:
            _enqueue_delivery(str(latest["name"]))
        return str(latest["name"])
    source_version = int(latest.get("source_version") or 0) + 1 if latest else 1
    event = build_project_source_event(
        source,
        source_version=source_version,
        occurred_at=datetime.now(UTC),
        service_actor_id=profile.service_actor_id,
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
    raise RuntimeError("Project delivery concurrency recovery failed.")


def list_reconciliation_projects() -> tuple[str, ...]:
    rows = frappe.get_all(
        "Project",
        filters={"status": "Open"},
        fields=["name"],
        order_by="name asc",
        page_length=MAX_RECONCILIATION_PROJECTS + 1,
    )
    if len(rows) > MAX_RECONCILIATION_PROJECTS:
        raise ProjectSenderError(
            "ERPNext Project reconciliation exceeds the fixed bound."
        )
    return tuple(str(row["name"]) for row in rows)


def get_project_delivery(delivery_id: str):
    return frappe.get_doc(DELIVERY_DOCTYPE, delivery_id)


def restore_delivery_event(delivery: object):
    return restore_project_source_event(
        getattr(delivery, "event_json", None),
        request_id=getattr(delivery, "request_id", None),
        source_project_id=getattr(delivery, "source_project_id", None),
        source_version=getattr(delivery, "source_version", None),
        source_snapshot_hash=getattr(delivery, "source_snapshot_hash", None),
        event_hash=getattr(delivery, "event_hash", None),
    )


def save_project_delivery(delivery: object) -> None:
    with project_delivery_write(str(getattr(delivery, "name", ""))) as capability:
        save_project_delivery_document(delivery, capability=capability)


def persist_project_mapping(
    delivery: object,
    target_project_global_id: UUID,
    *,
    mapped_at: datetime,
) -> bool:
    source_project_id = str(getattr(delivery, "source_project_id", "") or "")
    existing = frappe.db.get_value(
        MAPPING_DOCTYPE,
        source_project_id,
        ["target_project_global_id", "receipt_id", "event_id", "source_version"],
        as_dict=True,
    )
    expected = {
        "target_project_global_id": str(target_project_global_id),
        "receipt_id": str(getattr(delivery, "receipt_id", "")),
        "event_id": str(getattr(delivery, "event_id", "")),
        "source_version": int(getattr(delivery, "source_version", 0) or 0),
    }
    if existing:
        observed = {
            "target_project_global_id": str(existing.get("target_project_global_id")),
            "receipt_id": str(existing.get("receipt_id")),
            "event_id": str(existing.get("event_id")),
            "source_version": int(existing.get("source_version") or 0),
        }
        if observed != expected:
            raise ProjectSenderError("ERPNext Project mapping conflicts with history.")
        return False
    document = frappe.get_doc(
        {
            "doctype": MAPPING_DOCTYPE,
            "source_project_id": source_project_id,
            **expected,
            "mapped_at": _naive_utc(mapped_at),
        }
    )
    with project_delivery_write(source_project_id) as capability:
        insert_project_delivery_document(document, capability=capability)
    return True


def persisted_project_map() -> dict[str, str]:
    rows = frappe.get_all(
        MAPPING_DOCTYPE,
        fields=["source_project_id", "target_project_global_id"],
        order_by="source_project_id asc",
        page_length=MAX_RECONCILIATION_PROJECTS + 1,
    )
    if len(rows) > MAX_RECONCILIATION_PROJECTS:
        raise ProjectSenderError("ERPNext Project mapping count exceeds the fixed bound.")
    result: dict[str, str] = {}
    for row in rows:
        source = str(row.get("source_project_id") or "")
        target = str(row.get("target_project_global_id") or "")
        if not source or not target or source in result:
            raise ProjectSenderError("ERPNext Project mapping is invalid.")
        result[source] = target
    return result


def _load_source_project(source_project_id: str) -> SourceProject:
    row = frappe.db.get_value(
        "Project",
        source_project_id,
        ["name", "project_name", "status", "expected_end_date", "owner", "modified"],
        as_dict=True,
    )
    if not row:
        raise ProjectSenderError("ERPNext Project is unavailable.")
    return SourceProject(
        source_project_id=str(row.get("name") or ""),
        title=str(row.get("project_name") or row.get("name") or "").strip(),
        status=str(row.get("status") or ""),
        target_sop=_date(row.get("expected_end_date")),
        source_modified_at=_datetime(row.get("modified")),
        source_owner_user_id=str(row.get("owner") or ""),
    )


def _insert_delivery(event):
    document = frappe.get_doc(
        {
            "doctype": DELIVERY_DOCTYPE,
            "event_id": str(event.event_id),
            "stream_key": hashlib.sha256(
                f"{event.source_project_id}:{event.source_version}".encode("utf-8")
            ).hexdigest(),
            "source_project_id": event.source_project_id,
            "source_version": event.source_version,
            "source_snapshot_hash": event.source_snapshot_hash,
            "event_hash": event.event_hash,
            "event_json": canonical_json(event.event),
            "request_id": str(event.request_id),
            "trace_id": event.trace_id,
            "status": "pending",
            "attempt_count": 0,
        }
    )
    with project_delivery_write(str(event.event_id)) as capability:
        return insert_project_delivery_document(document, capability=capability)


def _latest_delivery(source_project_id: str) -> dict[str, object] | None:
    rows = frappe.get_all(
        DELIVERY_DOCTYPE,
        filters={"source_project_id": source_project_id},
        fields=["name", "source_version", "source_snapshot_hash", "status"],
        order_by="source_version desc",
        page_length=1,
    )
    return dict(rows[0]) if rows else None


def _delivery_by_event(event_id: str) -> dict[str, object] | None:
    row = frappe.db.get_value(
        DELIVERY_DOCTYPE,
        event_id,
        ["name", "status"],
        as_dict=True,
    )
    return dict(row) if row else None


def _enqueue_delivery(delivery_id: str) -> None:
    frappe.enqueue(
        DELIVERY_JOB,
        queue="short",
        enqueue_after_commit=True,
        job_id=f"npi-erp-project-{delivery_id}",
        delivery_id=delivery_id,
    )


def _date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ProjectSenderError("ERPNext Project target date is invalid.")


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ProjectSenderError(
                "ERPNext Project modified time is invalid."
            ) from error
    else:
        raise ProjectSenderError("ERPNext Project modified time is invalid.")
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _naive_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ProjectSenderError("ERPNext Project mapping time is invalid.")
    return value.astimezone(UTC).replace(tzinfo=None, microsecond=0)
