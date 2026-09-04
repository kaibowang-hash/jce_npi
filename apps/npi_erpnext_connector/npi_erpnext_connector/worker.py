from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import frappe
from frappe import _

from npi_erpnext_connector.config import load_profile, sender_is_disabled
from npi_erpnext_connector.frappe_repository import (
    DOCTYPE,
    enqueue_user_authorization,
    get_delivery,
    list_reconciliation_users,
    restore_event,
)
from npi_erpnext_connector.frappe_validation import (
    delivery_write,
    save_delivery_document,
)
from npi_erpnext_connector.transport import (
    PermanentDeliveryError,
    RetryableDeliveryError,
    deliver,
)


MAX_ATTEMPTS = 10
RECOVERY_PAGE_SIZE = 100
DELIVERY_JOB = "npi_erpnext_connector.worker.deliver_pending"
SOURCE_JOB = "npi_erpnext_connector.frappe_repository.enqueue_user_authorization"


def deliver_pending(delivery_id: str) -> None:
    if sender_is_disabled(frappe.conf):
        return
    profile = load_profile(frappe.conf)
    document = get_delivery(delivery_id)
    if str(document.status) not in {"pending", "retry"}:
        return
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    next_attempt = _datetime(getattr(document, "next_attempt_at", None))
    if next_attempt is not None and next_attempt > now:
        return
    event = restore_event(document)
    try:
        receipt = deliver(profile, event)
    except RetryableDeliveryError as error:
        _record_retry(document, error.code, now)
        return
    except PermanentDeliveryError as error:
        _record_permanent_failure(document, error.code, now)
        return
    document.status = "delivered"
    document.attempt_count = int(document.attempt_count or 0) + 1
    document.last_attempt_at = now
    document.delivered_at = now
    document.next_attempt_at = None
    document.last_error_code = None
    document.response_projection_hash = receipt.projection_hash
    document.response_state = receipt.state
    document.local_user_state = receipt.local_user_state
    document.local_user_disposition = receipt.local_user_disposition
    _save(document)


def recover_pending_deliveries() -> None:
    if sender_is_disabled(frappe.conf):
        return
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    rows = frappe.get_all(
        DOCTYPE,
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
            _enqueue_delivery(str(row["name"]))


def reconcile_all_users() -> None:
    if sender_is_disabled(frappe.conf):
        return
    load_profile(frappe.conf)
    for target_user_id in list_reconciliation_users():
        frappe.enqueue(
            SOURCE_JOB,
            queue="short",
            enqueue_after_commit=True,
            job_id=_source_job_id(target_user_id),
            target_user_id=target_user_id,
        )


@frappe.whitelist(methods=["POST"])
def retry_failed_delivery(delivery_id: str) -> dict[str, str]:
    frappe.only_for("System Manager")
    if sender_is_disabled(frappe.conf):
        frappe.throw(_("Authorization sender is disabled."), frappe.PermissionError)
    document = get_delivery(delivery_id)
    if str(document.status) != "permanent_failure":
        frappe.throw(
            _("Only a permanently failed authorization delivery can be retried."),
            frappe.ValidationError,
        )
    document.status = "retry"
    document.next_attempt_at = None
    document.last_error_code = None
    _save(document)
    _enqueue_delivery(str(document.name))
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
        seconds = min(3600, 30 * (2 ** (attempts - 1)))
        document.next_attempt_at = now + timedelta(seconds=seconds)
    _save(document)


def _record_permanent_failure(document: object, code: str, now: datetime) -> None:
    document.status = "permanent_failure"
    document.attempt_count = int(getattr(document, "attempt_count", 0) or 0) + 1
    document.last_attempt_at = now
    document.next_attempt_at = None
    document.last_error_code = code
    _save(document)


def _save(document: object) -> None:
    with delivery_write(str(getattr(document, "name", ""))) as capability:
        save_delivery_document(document, capability=capability)


def _enqueue_delivery(delivery_id: str) -> None:
    frappe.enqueue(
        DELIVERY_JOB,
        queue="short",
        enqueue_after_commit=True,
        job_id=f"npi-erp-auth-{delivery_id}",
        delivery_id=delivery_id,
    )


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


def _source_job_id(target_user_id: str) -> str:
    target_hash = hashlib.sha256(target_user_id.encode()).hexdigest()[:32]
    return f"npi-erp-auth-source-{target_hash}"
