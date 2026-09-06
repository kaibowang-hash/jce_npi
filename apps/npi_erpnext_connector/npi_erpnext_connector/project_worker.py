from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

import frappe
from frappe import _

from .project_config import load_project_sender_profile, project_sender_is_disabled
from .project_repository import (
    DELIVERY_DOCTYPE,
    enqueue_project,
    get_project_delivery,
    list_reconciliation_projects,
    persist_project_mapping,
    restore_delivery_event,
    save_project_delivery,
)
from .project_transport import (
    PermanentProjectDeliveryError,
    RetryableProjectDeliveryError,
    get_project_receipt_status,
    submit_project_event,
)


MAX_ATTEMPTS = 20
RECOVERY_PAGE_SIZE = 100
DELIVERY_JOB = "npi_erpnext_connector.project_worker.deliver_project"
SOURCE_JOB = "npi_erpnext_connector.project_repository.enqueue_project"
AUTH_RECONCILIATION_JOB = "npi_erpnext_connector.worker.reconcile_all_users"
UTC = timezone.utc


def deliver_project(delivery_id: str) -> None:
    if project_sender_is_disabled(frappe.conf):
        return
    profile = load_project_sender_profile(frappe.conf)
    document = get_project_delivery(delivery_id)
    if str(document.status) not in {"pending", "retry", "accepted"}:
        return
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    next_attempt = _datetime(getattr(document, "next_attempt_at", None))
    if next_attempt is not None and next_attempt > now:
        return
    event = restore_delivery_event(document)
    try:
        if not getattr(document, "receipt_id", None):
            accepted = submit_project_event(profile, event)
            document.receipt_id = str(accepted.receipt_id)
            document.response_state = accepted.state
            document.status = "accepted"
            document.accepted_at = now
            document.last_attempt_at = now
            document.attempt_count = int(document.attempt_count or 0) + 1
            document.next_attempt_at = None
            document.last_error_code = None
            save_project_delivery(document)
        status = get_project_receipt_status(
            profile,
            UUID(str(document.receipt_id)),
        )
    except RetryableProjectDeliveryError as error:
        _record_retry(document, error.code, now)
        return
    except PermanentProjectDeliveryError as error:
        _record_permanent_failure(document, error.code, now)
        return

    document.response_state = status.state
    document.response_disposition = status.disposition
    if status.state in {"pending", "processing", "failed_retryable"}:
        _record_retry(document, status.error_code or status.state.upper(), now)
        return
    if status.state != "succeeded" or status.project_global_id is None:
        _record_permanent_failure(
            document,
            status.error_code or f"TARGET_{status.state.upper()}",
            now,
        )
        return
    document.target_project_global_id = str(status.project_global_id)
    document.status = "succeeded"
    document.completed_at = now
    document.next_attempt_at = None
    document.last_error_code = None
    mapping_created = persist_project_mapping(
        document,
        status.project_global_id,
        mapped_at=now.replace(tzinfo=UTC),
    )
    save_project_delivery(document)
    if mapping_created:
        frappe.enqueue(
            AUTH_RECONCILIATION_JOB,
            queue="short",
            enqueue_after_commit=True,
            job_id="npi-erp-auth-reconcile-after-project-map",
        )


def recover_project_deliveries() -> None:
    if project_sender_is_disabled(frappe.conf):
        return
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    rows = frappe.get_all(
        DELIVERY_DOCTYPE,
        filters={"status": ["in", ["pending", "retry", "accepted"]]},
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


def reconcile_projects() -> None:
    if project_sender_is_disabled(frappe.conf):
        return
    load_project_sender_profile(frappe.conf)
    for source_project_id in list_reconciliation_projects():
        frappe.enqueue(
            SOURCE_JOB,
            queue="short",
            enqueue_after_commit=True,
            job_id=_source_job_id(source_project_id),
            source_project_id=source_project_id,
        )


@frappe.whitelist(methods=["POST"])
def retry_failed_project_delivery(delivery_id: str) -> dict[str, str]:
    frappe.only_for("System Manager")
    if project_sender_is_disabled(frappe.conf):
        frappe.throw(_("Project sender is disabled."), frappe.PermissionError)
    document = get_project_delivery(delivery_id)
    if str(document.status) != "permanent_failure":
        frappe.throw(
            _("Only a permanently failed Project delivery can be retried."),
            frappe.ValidationError,
        )
    document.status = "retry"
    document.next_attempt_at = None
    document.last_error_code = None
    save_project_delivery(document)
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
        seconds = min(900, 15 * (2 ** (attempts - 1)))
        document.next_attempt_at = now + timedelta(seconds=seconds)
    save_project_delivery(document)


def _record_permanent_failure(document: object, code: str, now: datetime) -> None:
    document.status = "permanent_failure"
    document.attempt_count = int(getattr(document, "attempt_count", 0) or 0) + 1
    document.last_attempt_at = now
    document.next_attempt_at = None
    document.last_error_code = code
    save_project_delivery(document)


def _enqueue_delivery(delivery_id: str) -> None:
    frappe.enqueue(
        DELIVERY_JOB,
        queue="short",
        enqueue_after_commit=True,
        job_id=f"npi-erp-project-{delivery_id}",
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


def _source_job_id(source_project_id: str) -> str:
    source_hash = hashlib.sha256(source_project_id.encode("utf-8")).hexdigest()[:32]
    return f"npi-erp-project-source-{source_hash}"
