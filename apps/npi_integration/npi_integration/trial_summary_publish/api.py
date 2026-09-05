from __future__ import annotations

from datetime import UTC, datetime

import frappe
from frappe import _

from npi_core.request_security import require_csrf_token

from .domain import MAX_ATTEMPTS, TrialSummaryDeliveryError, parse_uuid
from .frappe_validation import delivery_write, save_support_document
from .service import ATTEMPT_DOCTYPE, DELIVERY_DOCTYPE, JOB_PATH
from .worker import RECONCILE_JOB_PATH


@frappe.whitelist(allow_guest=True, methods=["GET"])
def list_deliveries(
    trialRoundGlobalId: str | None = None,
    state: str | None = None,
    start: int | str = 0,
    limit: int | str = 50,
) -> dict[str, object]:
    project_id = _require_bff_system_manager()
    filters: dict[str, object] = {"project_global_id": project_id}
    if trialRoundGlobalId:
        filters["trial_round_global_id"] = _uuid(trialRoundGlobalId)
    if state:
        if state not in {
            "pending", "processing", "succeeded", "failed_retryable", "failed_final", "uncertain"
        }:
            frappe.throw(_("Trial Summary Delivery State is invalid."), frappe.ValidationError)
        filters["state"] = state
    page_start, page_limit = _page(start, limit)
    rows = frappe.get_all(
        DELIVERY_DOCTYPE,
        filters=filters,
        fields=[
            "global_id", "event_type", "tenant_id", "project_global_id",
            "trial_plan_global_id", "trial_round_global_id", "summary_global_id",
            "summary_revision_global_id", "summary_version", "source_hash",
            "source_snapshot_hash", "target_idempotency_key_hash", "actor_user_id",
            "trace_id", "state", "attempt_count", "profile_id", "profile_version",
            "profile_snapshot_hash", "environment_code", "service_actor_user_id",
            "projection_id", "fact_count", "response_hash", "last_http_status",
            "last_error_code", "next_retry_at", "created_at", "updated_at",
        ],
        order_by="created_at desc, global_id asc",
        start=page_start,
        page_length=page_limit,
    )
    return {
        "projectGlobalId": project_id,
        "items": [_public_delivery(row) for row in rows],
        "start": page_start,
        "limit": page_limit,
    }


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_delivery(**ignored: object) -> dict[str, object]:
    del ignored
    project_id = _require_bff_system_manager()
    delivery_id = _uuid(_route_value("delivery_id"))
    if not frappe.db.exists(DELIVERY_DOCTYPE, delivery_id):
        raise frappe.DoesNotExistError
    fields = [
        "global_id", "event_type", "tenant_id", "project_global_id",
        "trial_plan_global_id", "trial_round_global_id", "summary_global_id",
        "summary_revision_global_id", "summary_version", "source_hash",
        "source_snapshot_hash", "target_idempotency_key_hash", "actor_user_id",
        "trace_id", "state", "attempt_count", "profile_id", "profile_version",
        "profile_snapshot_hash", "environment_code", "service_actor_user_id",
        "projection_id", "fact_count", "response_hash", "last_http_status",
        "last_error_code", "next_retry_at", "created_at", "updated_at",
    ]
    delivery = frappe.db.get_value(
        DELIVERY_DOCTYPE,
        delivery_id,
        fields,
        as_dict=True,
    )
    if str(delivery.project_global_id) != project_id:
        raise frappe.DoesNotExistError
    attempts = frappe.get_all(
        ATTEMPT_DOCTYPE,
        filters={"delivery_global_id": delivery_id},
        fields=[
            "global_id", "attempt_number", "attempt_kind", "state",
            "adapter_boundary_crossed", "response_authenticated",
            "response_contract_valid", "http_status", "response_hash",
            "error_code", "trace_id", "started_at", "completed_at",
        ],
        order_by="attempt_number asc",
        page_length=MAX_ATTEMPTS + 1,
    )
    if len(attempts) > MAX_ATTEMPTS:
        frappe.throw(_("Trial Summary attempts exceed the safe bound."), frappe.ValidationError)
    return {
        "delivery": _public_delivery(delivery),
        "attempts": [_public_attempt(row) for row in attempts],
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def retry_delivery(**ignored: object) -> dict[str, object]:
    del ignored
    project_id = _require_bff_system_manager()
    require_csrf_token()
    delivery_id = _uuid(_route_value("delivery_id"))
    delivery = frappe.get_doc(DELIVERY_DOCTYPE, delivery_id, for_update=True)
    if str(delivery.project_global_id) != project_id:
        raise frappe.DoesNotExistError
    if delivery.state not in {"failed_retryable", "failed_final"}:
        frappe.throw(
            _("Only a failed Trial Summary delivery can be retried."),
            frappe.ValidationError,
        )
    if int(delivery.attempt_count or 0) >= MAX_ATTEMPTS:
        frappe.throw(
            _("The Trial Summary delivery attempt limit was reached."),
            frappe.ValidationError,
        )
    now = datetime.now(UTC).replace(tzinfo=None)
    with delivery_write(delivery_id) as capability:
        delivery.state = "pending"
        delivery.adapter_boundary_crossed = 0
        delivery.claim_token = None
        delivery.claimed_at = None
        delivery.lease_expires_at = None
        delivery.next_retry_at = None
        delivery.last_error_code = None
        delivery.updated_at = now
        save_support_document(delivery, capability=capability)
    frappe.enqueue(
        JOB_PATH,
        queue="short",
        enqueue_after_commit=True,
        job_name=f"trial-summary-delivery-{delivery_id}",
        delivery_global_id=delivery_id,
    )
    return {"deliveryGlobalId": delivery_id, "state": "pending"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def request_reconciliation(**ignored: object) -> dict[str, object]:
    del ignored
    project_id = _require_bff_system_manager()
    require_csrf_token()
    delivery_id = _uuid(_route_value("delivery_id"))
    values = frappe.db.get_value(
        DELIVERY_DOCTYPE,
        delivery_id,
        ["project_global_id", "state"],
        as_dict=True,
    )
    if not values or str(values.project_global_id) != project_id:
        raise frappe.DoesNotExistError
    state = values.state
    if state != "uncertain":
        frappe.throw(
            _("Only an uncertain Trial Summary delivery can be reconciled."),
            frappe.ValidationError,
        )
    frappe.enqueue(
        RECONCILE_JOB_PATH,
        queue="short",
        enqueue_after_commit=True,
        job_name=f"trial-summary-reconcile-{delivery_id}",
        delivery_global_id=delivery_id,
    )
    return {"deliveryGlobalId": delivery_id, "state": "uncertain", "reconciliationQueued": True}


def _require_bff_system_manager() -> str:
    if not bool(getattr(frappe.flags, "npi_bff_request", False)):
        raise frappe.PermissionError
    actor = str(getattr(frappe.session, "user", "") or "")
    if actor == "Guest" or (
        actor != "Administrator" and "System Manager" not in frappe.get_roles(actor)
    ):
        raise frappe.PermissionError
    return _uuid(_route_value("project_id"))


def _route_value(name: str) -> str:
    values = getattr(frappe.flags, "npi_route_params", None)
    value = values.get(name) if hasattr(values, "get") else None
    if not isinstance(value, str) or not value:
        raise frappe.DoesNotExistError
    return value


def _uuid(value: object) -> str:
    try:
        return parse_uuid(value, "globalId")
    except TrialSummaryDeliveryError as error:
        raise frappe.ValidationError(_("Global ID is invalid.")) from error


def _page(start: int | str, limit: int | str) -> tuple[int, int]:
    try:
        page_start = int(start)
        page_limit = int(limit)
    except (TypeError, ValueError) as error:
        raise frappe.ValidationError(_("The query page is invalid.")) from error
    if page_start < 0 or not 1 <= page_limit <= 100:
        frappe.throw(_("The query page is invalid."), frappe.ValidationError)
    return page_start, page_limit


def _public_delivery(value: object) -> dict[str, object]:
    pairs = (
        ("globalId", "global_id"),
        ("eventType", "event_type"),
        ("tenantId", "tenant_id"),
        ("projectGlobalId", "project_global_id"),
        ("trialPlanGlobalId", "trial_plan_global_id"),
        ("trialRoundGlobalId", "trial_round_global_id"),
        ("summaryGlobalId", "summary_global_id"),
        ("summaryRevisionGlobalId", "summary_revision_global_id"),
        ("summaryVersion", "summary_version"),
        ("sourceHash", "source_hash"),
        ("sourceSnapshotHash", "source_snapshot_hash"),
        ("targetIdempotencyKeyHash", "target_idempotency_key_hash"),
        ("actorUserId", "actor_user_id"),
        ("traceId", "trace_id"),
        ("state", "state"),
        ("attemptCount", "attempt_count"),
        ("profileId", "profile_id"),
        ("profileVersion", "profile_version"),
        ("profileSnapshotHash", "profile_snapshot_hash"),
        ("environmentCode", "environment_code"),
        ("serviceActorUserId", "service_actor_user_id"),
        ("projectionId", "projection_id"),
        ("factCount", "fact_count"),
        ("responseHash", "response_hash"),
        ("lastHttpStatus", "last_http_status"),
        ("lastErrorCode", "last_error_code"),
        ("nextRetryAt", "next_retry_at"),
        ("createdAt", "created_at"),
        ("updatedAt", "updated_at"),
    )
    result: dict[str, object] = {}
    for public, internal in pairs:
        item = getattr(value, internal, None)
        result[public] = _iso(item) if internal.endswith("_at") else item
    return result


def _public_attempt(value: object) -> dict[str, object]:
    pairs = (
        ("globalId", "global_id"),
        ("attemptNumber", "attempt_number"),
        ("attemptKind", "attempt_kind"),
        ("state", "state"),
        ("adapterBoundaryCrossed", "adapter_boundary_crossed"),
        ("responseAuthenticated", "response_authenticated"),
        ("responseContractValid", "response_contract_valid"),
        ("httpStatus", "http_status"),
        ("responseHash", "response_hash"),
        ("errorCode", "error_code"),
        ("traceId", "trace_id"),
        ("startedAt", "started_at"),
        ("completedAt", "completed_at"),
    )
    result: dict[str, object] = {}
    for public, internal in pairs:
        item = getattr(value, internal, None)
        if internal.endswith("_at"):
            item = _iso(item)
        elif internal in {
            "adapter_boundary_crossed",
            "response_authenticated",
            "response_contract_valid",
        }:
            item = bool(item)
        result[public] = item
    return result


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.isoformat().replace("+00:00", "Z")
    return str(value)
