from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import frappe

from .domain import EVENT_TYPE, ProjectSource, canonical_json
from .frappe_validation import insert_support_document, project_publish_write


REQUEST_DOCTYPE = "NPI ERP Project Publish Request"
ATTEMPT_DOCTYPE = "NPI ERP Project Publish Attempt"
RESULT_DOCTYPE = "NPI ERP Project Publish Result"
JOB_PATH = "npi_integration.project_publish.worker.process_request"


def queue_engineering_project(document: object, method: str | None = None) -> None:
    """Persist the NPI-to-ERPNext Project request in the Project transaction."""

    del method
    if getattr(frappe.flags, "npi_project_source_binding_write", False):
        return
    create_request_for_project(document, enqueue=True)


def create_request_for_project(document: object, *, enqueue: bool) -> str | None:
    project_global_id = str(getattr(document, "global_id", "") or "")
    tenant_id = str(getattr(document, "tenant_id", "") or "")
    if not project_global_id or not tenant_id:
        raise RuntimeError("Engineering Project publication identity is unavailable.")
    inbound = frappe.db.exists(
        "NPI Project Source Binding",
        {
            "tenant_id": tenant_id,
            "source_system": "ERPNEXT",
            "target_system": "NPI_ONE",
            "source_object_type": "Project",
            "bound_project_global_id": project_global_id,
            "stream_state": "bound",
        },
    )
    if inbound:
        return None
    existing = frappe.db.get_value(
        REQUEST_DOCTYPE,
        {"project_global_id": project_global_id},
        ["name", "source_hash"],
        as_dict=True,
    )
    source = ProjectSource(
        tenant_id=tenant_id,
        project_global_id=project_global_id,
        business_code=str(getattr(document, "business_code", "") or ""),
        title=str(getattr(document, "title", "") or ""),
        project_type=str(getattr(document, "project_type", "") or ""),
        target_sop=_date_text(getattr(document, "target_sop", None)),
        actor_user_id=str(getattr(document, "owner_user_id", "") or "").casefold(),
        source_version=int(getattr(document, "optimistic_version", 0) or 0),
    )
    if existing:
        if str(existing.source_hash) != source.source_hash:
            raise RuntimeError("Engineering Project publication identity conflicts.")
        return str(existing.name)
    request_global_id = str(uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)
    with project_publish_write(request_global_id) as capability:
        request = frappe.get_doc(
            {
                "doctype": REQUEST_DOCTYPE,
                "global_id": request_global_id,
                "event_type": EVENT_TYPE,
                "tenant_id": source.tenant_id,
                "project_global_id": source.project_global_id,
                "source_version": source.source_version,
                "source_snapshot": canonical_json(source.snapshot),
                "source_hash": source.source_hash,
                "target_idempotency_key_hash": source.target_idempotency_key_hash,
                "actor_user_id": source.actor_user_id,
                "trace_id": f"project-publish-{request_global_id}",
                "state": "pending",
                "attempt_count": 0,
                "adapter_boundary_crossed": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        insert_support_document(request, capability=capability)
    if enqueue:
        _enqueue(request_global_id, after_commit=True)
    return request_global_id


def _enqueue(request_global_id: str, *, after_commit: bool = False) -> None:
    frappe.enqueue(
        JOB_PATH,
        queue="short",
        enqueue_after_commit=after_commit,
        job_id=f"npi-erp-project-publish-{request_global_id}",
        request_global_id=request_global_id,
    )


def _date_text(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())[:10]
    return str(value or "")
