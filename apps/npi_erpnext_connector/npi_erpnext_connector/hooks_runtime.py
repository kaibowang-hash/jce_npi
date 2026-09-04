from __future__ import annotations

import hashlib

import frappe

from npi_erpnext_connector.config import sender_is_disabled


QUEUE_JOB = "npi_erpnext_connector.frappe_repository.enqueue_user_authorization"


def queue_user_change(document: object, method: str | None = None) -> None:
    del method
    _queue(str(getattr(document, "name", "") or ""))


def queue_user_permission_change(document: object, method: str | None = None) -> None:
    del method
    _queue(str(getattr(document, "user", "") or ""))


def _queue(target_user_id: str) -> None:
    if sender_is_disabled(frappe.conf) or not target_user_id:
        return
    frappe.enqueue(
        QUEUE_JOB,
        queue="short",
        enqueue_after_commit=True,
        job_id=_source_job_id(target_user_id),
        target_user_id=target_user_id,
    )


def _source_job_id(target_user_id: str) -> str:
    target_hash = hashlib.sha256(target_user_id.encode()).hexdigest()[:32]
    return f"npi-erp-auth-source-{target_hash}"
