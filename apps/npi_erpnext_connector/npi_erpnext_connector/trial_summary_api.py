from __future__ import annotations

import re
from uuid import UUID

import frappe
from frappe import _

from npi_erpnext_connector.receiver_security import (
    ReceiverAuthenticationError,
    signed_response,
    verify_request,
)
from npi_erpnext_connector.trial_summary_config import receiver_is_disabled
from npi_erpnext_connector.trial_summary_contract import (
    CONTRACT_VERSION,
    OPERATION,
    RECONCILE_OPERATION,
    TrialSummaryCommand,
    TrialSummaryContractError,
    canonical_hash,
    decode_reconcile_command,
    decode_trial_summary_command,
)
from npi_erpnext_connector.trial_summary_frappe import (
    FACT_DOCTYPE,
    SUMMARY_DOCTYPE,
    TrialSummaryExecutionError,
    execute_trial_summary_command,
    receipt_for,
)

SERVICE_ROLE = "NPI ERP Trial Summary Integration Service"
VIEWER_ROLE = "NPI ERP Trial Summary Viewer"
PUBLISH_METHOD_PATH = (
    "/api/method/npi_erpnext_connector.trial_summary_api.publish_trial_summary"
)
RECONCILE_METHOD_PATH = (
    "/api/method/npi_erpnext_connector.trial_summary_api.reconcile_trial_summary"
)
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@frappe.whitelist(methods=["POST"])
def publish_trial_summary(**ignored: object) -> dict[str, object]:
    del ignored
    actor, secret, body = _authenticated_request(PUBLISH_METHOD_PATH)
    try:
        command = decode_trial_summary_command(body)
    except TrialSummaryContractError:
        frappe.throw(
            _("Integration Trial Summary request contract is invalid."),
            frappe.ValidationError,
        )
    if receiver_is_disabled(frappe.conf):
        return _publish_response(
            command,
            secret,
            status=403,
            projection_id=None,
            fact_count=None,
            exact_replay=False,
            error_code="TRIAL_SUMMARY_RECEIVER_DISABLED",
        )
    try:
        result = execute_trial_summary_command(
            command,
            service_user=actor,
            trace_id=_trace_id(),
        )
    except TrialSummaryExecutionError as error:
        return _publish_response(
            command,
            secret,
            status=error.http_status,
            projection_id=None,
            fact_count=None,
            exact_replay=False,
            error_code=error.code,
        )
    return _publish_response(
        command,
        secret,
        status=200,
        projection_id=result.projection_id,
        fact_count=result.fact_count,
        exact_replay=result.exact_replay,
        error_code=None,
    )


@frappe.whitelist(methods=["POST"])
def reconcile_trial_summary(**ignored: object) -> dict[str, object]:
    del ignored
    _, secret, body = _authenticated_request(RECONCILE_METHOD_PATH)
    try:
        command = decode_reconcile_command(body)
    except TrialSummaryContractError:
        frappe.throw(
            _("Integration Trial Summary reconciliation contract is invalid."),
            frappe.ValidationError,
        )
    if receiver_is_disabled(frappe.conf):
        return _reconcile_response(
            command,
            secret,
            status=403,
            found=False,
            projection_id=None,
            fact_count=None,
            error_code="TRIAL_SUMMARY_RECEIVER_DISABLED",
        )
    try:
        result = receipt_for(
            command.target_idempotency_key_hash,
            command.source_hash,
        )
    except TrialSummaryExecutionError as error:
        return _reconcile_response(
            command,
            secret,
            status=error.http_status,
            found=False,
            projection_id=None,
            fact_count=None,
            error_code=error.code,
        )
    return _reconcile_response(
        command,
        secret,
        status=200,
        found=result is not None,
        projection_id=result.projection_id if result else None,
        fact_count=result.fact_count if result else None,
        error_code=None,
    )


@frappe.whitelist(methods=["GET"])
def list_trial_summaries(
    project_global_id: str | None = None,
    trial_round_global_id: str | None = None,
    conclusion_state: str | None = None,
    start: int | str = 0,
    limit: int | str = 50,
) -> dict[str, object]:
    _require_viewer()
    filters: dict[str, object] = {}
    if project_global_id:
        filters["project_global_id"] = _uuid(project_global_id)
    if trial_round_global_id:
        filters["trial_round_global_id"] = _uuid(trial_round_global_id)
    if conclusion_state:
        if conclusion_state not in {"approved", "rejected"}:
            frappe.throw(_("Trial Conclusion State is invalid."), frappe.ValidationError)
        filters["conclusion_state"] = conclusion_state
    page_start, page_limit = _page(start, limit)
    rows = frappe.get_all(
        SUMMARY_DOCTYPE,
        filters=filters,
        fields=[
            "summary_revision_global_id",
            "summary_global_id",
            "project_global_id",
            "trial_plan_global_id",
            "trial_round_global_id",
            "summary_version",
            "predecessor_global_id",
            "projection_purpose",
            "formal_mp_acceptance",
            "conclusion_state",
            "conclusion_code",
            "fact_count",
            "source_actor_user_id",
            "source_created_at",
            "received_at",
        ],
        order_by="source_created_at desc, summary_revision_global_id asc",
        start=page_start,
        page_length=page_limit,
    )
    return {"items": rows, "start": page_start, "limit": page_limit}


@frappe.whitelist(methods=["GET"])
def get_trial_summary(summary_revision_global_id: str) -> dict[str, object]:
    _require_viewer()
    revision_id = _uuid(summary_revision_global_id)
    if not frappe.db.exists(SUMMARY_DOCTYPE, revision_id):
        raise frappe.DoesNotExistError
    summary = frappe.db.get_value(
        SUMMARY_DOCTYPE,
        revision_id,
        [
            "summary_revision_global_id",
            "summary_global_id",
            "tenant_id",
            "project_global_id",
            "trial_plan_global_id",
            "trial_round_global_id",
            "summary_version",
            "predecessor_global_id",
            "projection_purpose",
            "formal_mp_acceptance",
            "conclusion_state",
            "conclusion_code",
            "source_snapshot_hash",
            "source_manifest_hash",
            "presentation_projection_hash",
            "redaction_manifest_hash",
            "presentation_projection",
            "redaction_manifest",
            "fact_count",
            "source_actor_user_id",
            "source_created_at",
            "received_at",
        ],
        as_dict=True,
    )
    facts = frappe.get_all(
        FACT_DOCTYPE,
        filters={"summary_revision_global_id": revision_id},
        fields=[
            "fact_global_id",
            "fact_group",
            "fact_type",
            "fact_key",
            "value_state",
            "value_text",
            "value_json",
            "unit",
            "source_references",
            "source_references_hash",
        ],
        order_by="fact_group asc, fact_key asc",
        page_length=25_001,
    )
    if len(facts) > 25_000:
        frappe.throw(_("Trial Summary facts exceed the safe bound."), frappe.ValidationError)
    return {"summary": summary, "facts": facts}


@frappe.whitelist(methods=["GET"])
def list_trial_defects(
    project_global_id: str | None = None,
    trial_round_global_id: str | None = None,
    value_state: str | None = None,
    start: int | str = 0,
    limit: int | str = 50,
) -> dict[str, object]:
    _require_viewer()
    filters: dict[str, object] = {
        "fact_type": ["in", ["trial_defect", "tooling_defect"]]
    }
    if project_global_id:
        filters["project_global_id"] = _uuid(project_global_id)
    if trial_round_global_id:
        filters["trial_round_global_id"] = _uuid(trial_round_global_id)
    if value_state:
        if value_state not in {"open", "closed"}:
            frappe.throw(
                _("Trial Summary Fact Value State is invalid."),
                frappe.ValidationError,
            )
        filters["value_state"] = value_state
    page_start, page_limit = _page(start, limit)
    rows = frappe.get_all(
        FACT_DOCTYPE,
        filters=filters,
        fields=[
            "fact_global_id",
            "summary_revision_global_id",
            "project_global_id",
            "trial_round_global_id",
            "fact_type",
            "fact_key",
            "value_state",
            "value_text",
            "source_references_hash",
        ],
        order_by="creation desc, fact_global_id asc",
        start=page_start,
        page_length=page_limit,
    )
    return {"items": rows, "start": page_start, "limit": page_limit}


def _authenticated_request(expected_path: str) -> tuple[str, str, bytes]:
    actor, secret = _service_identity()
    request = getattr(frappe.local, "request", None)
    if request is None or not str(
        getattr(request, "content_type", "")
    ).casefold().startswith("application/json"):
        frappe.throw(
            _("Integration request content type is invalid."),
            frappe.ValidationError,
        )
    body = request.get_data(cache=True, as_text=False)
    path = str(getattr(request, "path", ""))
    trace_id = str(request.headers.get("X-NPI-Trace-ID", ""))
    if _TRACE.fullmatch(trace_id) is None:
        frappe.throw(_("Integration request trace ID is invalid."), frappe.ValidationError)
    try:
        verify_request(
            secret=secret,
            path=path,
            timestamp=str(request.headers.get("X-NPI-Timestamp", "")),
            signature=str(request.headers.get("X-NPI-Signature", "")),
            body=body,
        )
    except ReceiverAuthenticationError:
        frappe.throw(_("Integration request authentication failed."), frappe.PermissionError)
    if path != expected_path:
        frappe.throw(_("Integration request path is invalid."), frappe.PermissionError)
    return actor, secret, body


def _trace_id() -> str:
    return str(frappe.local.request.headers.get("X-NPI-Trace-ID", ""))


def _service_identity() -> tuple[str, str]:
    actor = str(getattr(frappe.session, "user", "") or "")
    if (
        not actor
        or actor in {"Guest", "Administrator"}
        or SERVICE_ROLE not in frappe.get_roles(actor)
    ):
        raise frappe.PermissionError
    user = frappe.db.get_value("User", actor, ["enabled", "user_type"], as_dict=True)
    if not user or user.get("enabled") != 1 or user.get("user_type") != "Website User":
        raise frappe.PermissionError
    document = frappe.get_doc("User", actor)
    secret = document.get_password("api_secret", raise_exception=False)
    api_key = getattr(document, "api_key", None)
    if not isinstance(api_key, str) or not api_key or not isinstance(secret, str) or not secret:
        raise frappe.PermissionError
    return actor, f"{api_key}:{secret}"


def _require_viewer() -> None:
    actor = str(getattr(frappe.session, "user", "") or "")
    roles = set(frappe.get_roles(actor)) if actor and actor != "Guest" else set()
    if actor == "Guest" or (actor != "Administrator" and not roles.intersection({"System Manager", VIEWER_ROLE})):
        raise frappe.PermissionError
    if not frappe.has_permission(SUMMARY_DOCTYPE, ptype="read", user=actor):
        raise frappe.PermissionError


def _publish_response(
    command: TrialSummaryCommand,
    secret: str,
    *,
    status: int,
    projection_id: str | None,
    fact_count: int | None,
    exact_replay: bool,
    error_code: str | None,
) -> dict[str, object]:
    core = {
        "contractVersion": CONTRACT_VERSION,
        "operation": OPERATION,
        "requestGlobalId": command.request_global_id,
        "attemptGlobalId": command.attempt_global_id,
        "attemptNumber": command.attempt_number,
        "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        "sourceHash": command.source_hash,
        "httpStatus": status,
        "projectionId": projection_id,
        "factCount": fact_count,
        "exactReplay": exact_replay,
        "errorCode": error_code,
    }
    frappe.local.response.http_status_code = status
    return signed_response({**core, "responseHash": canonical_hash(core)}, secret)


def _reconcile_response(
    command: object,
    secret: str,
    *,
    status: int,
    found: bool,
    projection_id: str | None,
    fact_count: int | None,
    error_code: str | None,
) -> dict[str, object]:
    core = {
        "contractVersion": CONTRACT_VERSION,
        "operation": RECONCILE_OPERATION,
        "requestGlobalId": command.request_global_id,
        "attemptGlobalId": command.attempt_global_id,
        "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        "sourceHash": command.source_hash,
        "httpStatus": status,
        "found": found,
        "projectionId": projection_id,
        "factCount": fact_count,
        "errorCode": error_code,
    }
    frappe.local.response.http_status_code = status
    return signed_response({**core, "responseHash": canonical_hash(core)}, secret)


def _uuid(value: object) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise frappe.ValidationError(_("Global ID is invalid.")) from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        frappe.throw(_("Global ID is invalid."), frappe.ValidationError)
    return str(parsed)


def _page(start: int | str, limit: int | str) -> tuple[int, int]:
    try:
        page_start = int(start)
        page_limit = int(limit)
    except (TypeError, ValueError) as error:
        raise frappe.ValidationError(_("The query page is invalid.")) from error
    if page_start < 0 or not 1 <= page_limit <= 100:
        frappe.throw(_("The query page is invalid."), frappe.ValidationError)
    return page_start, page_limit
