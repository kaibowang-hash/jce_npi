from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import frappe

from .domain import EVENT_TYPE, canonical_json, delivery_source
from .frappe_validation import delivery_write, insert_support_document

DELIVERY_DOCTYPE = "NPI Trial Summary Delivery"
ATTEMPT_DOCTYPE = "NPI Trial Summary Delivery Attempt"
JOB_PATH = "npi_integration.trial_summary_publish.worker.process_delivery"


def queue_released_trial_summary(document: object, method: str | None = None) -> None:
    """Append one Outbox row in the source revision transaction."""

    del method
    create_delivery_for_summary(document, enqueue=True)


def create_delivery_for_summary(document: object, *, enqueue: bool) -> str:
    """Create one idempotent delivery, including migration-safe backfill."""

    source = delivery_source(document)
    existing = frappe.db.get_value(
        DELIVERY_DOCTYPE,
        {"summary_revision_global_id": source.summary_revision_global_id},
        ["name", "source_hash"],
        as_dict=True,
    )
    if existing:
        if str(existing.source_hash) != source.source_hash:
            raise RuntimeError("Released Trial Summary delivery identity conflicts.")
        return str(existing.name)
    request_global_id = str(uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)
    with delivery_write(request_global_id) as capability:
        delivery = frappe.get_doc(
            {
                "doctype": DELIVERY_DOCTYPE,
                "global_id": request_global_id,
                "event_type": EVENT_TYPE,
                "tenant_id": source.tenant_id,
                "project_global_id": source.project_global_id,
                "trial_plan_global_id": source.trial_plan_global_id,
                "trial_round_global_id": source.trial_round_global_id,
                "summary_global_id": source.summary_global_id,
                "summary_revision_global_id": source.summary_revision_global_id,
                "summary_version": source.summary_version,
                "source_snapshot": canonical_json(source.source),
                "source_hash": source.source_hash,
                "source_snapshot_hash": source.source_snapshot_hash,
                "target_idempotency_key_hash": source.target_idempotency_key_hash,
                "actor_user_id": source.actor_user_id,
                "trace_id": source.trace_id,
                "state": "pending",
                "attempt_count": 0,
                "adapter_boundary_crossed": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        insert_support_document(delivery, capability=capability)
    if enqueue:
        frappe.enqueue(
            JOB_PATH,
            queue="short",
            enqueue_after_commit=True,
            job_name=f"trial-summary-delivery-{request_global_id}",
            delivery_global_id=request_global_id,
        )
    return request_global_id
