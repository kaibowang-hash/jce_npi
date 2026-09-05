from __future__ import annotations

from datetime import datetime, timedelta, timezone

import frappe
from frappe import _

from npi_erpnext_connector.master_data_config import (
    load_master_data_profile,
    master_data_sender_is_disabled,
)
from npi_erpnext_connector.master_data_domain import MasterCatalogKind
from npi_erpnext_connector.master_data_repository import (
    DELIVERY_DOCTYPE,
    enqueue_master_catalog,
    get_delivery,
    restore_delivery_event,
    save_delivery,
)
from npi_erpnext_connector.master_data_transport import (
    PermanentMasterDataDeliveryError,
    RetryableMasterDataDeliveryError,
    deliver_master_snapshot,
)


MAX_ATTEMPTS = 20
RECOVERY_PAGE_SIZE = 100
UTC = timezone.utc


def deliver_master_data(delivery_id: str) -> None:
    if master_data_sender_is_disabled(frappe.conf):
        return
    profile = load_master_data_profile(frappe.conf)
    document = get_delivery(delivery_id)
    if str(document.status) not in {"pending", "retry"}:
        return
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    next_attempt = _datetime(getattr(document, "next_attempt_at", None))
    if next_attempt is not None and next_attempt > now:
        return
    event = restore_delivery_event(document)
    try:
        receipt = deliver_master_snapshot(profile, event)
    except RetryableMasterDataDeliveryError as error:
        _record_retry(document, error.code, now)
        return
    except PermanentMasterDataDeliveryError as error:
        _record_final(document, error.code, now)
        return
    document.status = "delivered"
    document.attempt_count = int(document.attempt_count or 0) + 1
    document.last_attempt_at = now
    document.delivered_at = now
    document.next_attempt_at = None
    document.last_error_code = None
    document.target_snapshot_id = receipt.snapshot_id
    document.response_payload_hash = receipt.payload_hash
    save_delivery(document)


def recover_master_data_deliveries() -> None:
    if master_data_sender_is_disabled(frappe.conf):
        return
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    rows = frappe.get_all(
        DELIVERY_DOCTYPE,
        filters={"status": ["in", ["pending", "retry"]]},
        or_filters=[
            ["next_attempt_at", "is", "not set"],
            ["next_attempt_at", "<=", now],
        ],
        fields=["name", "next_attempt_at"],
        order_by="creation asc",
        page_length=RECOVERY_PAGE_SIZE,
    )
    for row in rows:
        next_attempt = _datetime(row.get("next_attempt_at"))
        if next_attempt is None or next_attempt <= now:
            frappe.enqueue(
                "npi_erpnext_connector.master_data_worker.deliver_master_data",
                queue="short",
                enqueue_after_commit=True,
                job_id=f"npi-erp-master-{row['name']}",
                delivery_id=str(row["name"]),
            )


def reconcile_master_catalogs() -> None:
    if master_data_sender_is_disabled(frappe.conf):
        return
    load_master_data_profile(frappe.conf)
    for kind in MasterCatalogKind:
        frappe.enqueue(
            "npi_erpnext_connector.master_data_repository.enqueue_master_catalog",
            queue="short",
            enqueue_after_commit=True,
            job_id=f"npi-erp-master-source-{kind.value}",
            catalog_kind=kind.value,
        )


@frappe.whitelist(methods=["POST"])
def retry_failed_master_data_delivery(delivery_id: str) -> dict[str, str]:
    frappe.only_for("System Manager")
    if master_data_sender_is_disabled(frappe.conf):
        frappe.throw(_("Master data sender is disabled."), frappe.PermissionError)
    document = get_delivery(delivery_id)
    if str(document.status) != "permanent_failure":
        frappe.throw(
            _("Only a permanently failed master data delivery can be retried."),
            frappe.ValidationError,
        )
    document.status = "retry"
    document.next_attempt_at = None
    document.last_error_code = None
    save_delivery(document)
    frappe.enqueue(
        "npi_erpnext_connector.master_data_worker.deliver_master_data",
        queue="short",
        enqueue_after_commit=True,
        job_id=f"npi-erp-master-{delivery_id}",
        delivery_id=delivery_id,
    )
    return {"deliveryId": str(document.name), "status": "retry"}


def _record_retry(document: object, code: str, now: datetime) -> None:
    attempts = int(getattr(document, "attempt_count", 0) or 0) + 1
    document.attempt_count = attempts
    document.last_attempt_at = now
    document.last_error_code = code
    if attempts >= MAX_ATTEMPTS:
        document.status = "permanent_failure"
        document.next_attempt_at = None
    else:
        document.status = "retry"
        document.next_attempt_at = now + timedelta(
            seconds=min(1800, 15 * (2 ** (attempts - 1)))
        )
    save_delivery(document)


def _record_final(document: object, code: str, now: datetime) -> None:
    document.status = "permanent_failure"
    document.attempt_count = int(getattr(document, "attempt_count", 0) or 0) + 1
    document.last_attempt_at = now
    document.next_attempt_at = None
    document.last_error_code = code
    save_delivery(document)


def _datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is not None:
        result = result.astimezone(UTC).replace(tzinfo=None)
    return result
