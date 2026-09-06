from __future__ import annotations

import re

import frappe
from frappe import _

from npi_erpnext_connector.engineering_change_config import receiver_is_disabled
from npi_erpnext_connector.engineering_change_contract import (
    CONTRACT_VERSION,
    OPERATION,
    EngineeringChangeContractError,
    EngineeringChangeSummaryCommand,
    canonical_hash,
    decode_summary_command,
)
from npi_erpnext_connector.engineering_change_frappe import (
    SUMMARY_DOCTYPE,
    EngineeringChangeExecutionError,
    execute_summary_command,
)
from npi_erpnext_connector.receiver_security import (
    ReceiverAuthenticationError,
    signed_response,
    verify_request,
)

SERVICE_ROLE = "NPI ERP Engineering Change Integration Service"
VIEWER_ROLE = "NPI ERP Engineering Change Summary Viewer"
SUMMARY_METHOD_PATH = (
    "/api/method/npi_erpnext_connector.engineering_change_api."
    "record_change_implementation_summary"
)
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@frappe.whitelist(methods=["POST"])
def record_change_implementation_summary(**ignored: object) -> dict[str, object]:
    del ignored
    actor, secret, raw_body, trace_id = _authenticated_request(SUMMARY_METHOD_PATH)
    try:
        command = decode_summary_command(raw_body)
    except EngineeringChangeContractError:
        frappe.throw(
            _("Integration Engineering Change summary contract is invalid."),
            frappe.ValidationError,
        )
    if receiver_is_disabled(frappe.conf):
        return _response(
            command,
            secret,
            status=403,
            projection_id=None,
            exact_replay=False,
            partial=False,
            retry_after_seconds=None,
            error_code="ENGINEERING_CHANGE_SUMMARY_RECEIVER_DISABLED",
        )
    try:
        result = execute_summary_command(
            command,
            service_user=actor,
            trace_id=trace_id,
        )
    except EngineeringChangeExecutionError as error:
        return _response(
            command,
            secret,
            status=error.http_status,
            projection_id=None,
            exact_replay=False,
            partial=False,
            retry_after_seconds=None,
            error_code=error.code,
        )
    return _response(
        command,
        secret,
        status=200,
        projection_id=result.projection_id,
        exact_replay=result.exact_replay,
        partial=False,
        retry_after_seconds=None,
        error_code=None,
    )


@frappe.whitelist(methods=["GET"])
def list_change_implementation_summaries(
    project_global_id: str | None = None,
    formal_change_document_name: str | None = None,
    start: int | str = 0,
    limit: int | str = 50,
) -> dict[str, object]:
    _require_viewer()
    filters: dict[str, object] = {}
    if project_global_id:
        filters["project_global_id"] = _bounded_text(project_global_id, 36)
    if formal_change_document_name:
        filters["formal_change_document_name"] = _bounded_text(
            formal_change_document_name, 140
        )
    page_start, page_limit = _page(start, limit)
    rows = frappe.get_all(
        SUMMARY_DOCTYPE,
        filters=filters,
        fields=[
            "revision_global_id",
            "project_global_id",
            "change_global_id",
            "revision_number",
            "formal_change_document_name",
            "formal_change_raw_status",
            "source_actor_user_id",
            "received_at",
        ],
        order_by="received_at desc, revision_global_id asc",
        start=page_start,
        page_length=page_limit,
    )
    return {"items": rows, "start": page_start, "limit": page_limit}


def _authenticated_request(path: str) -> tuple[str, str, bytes, str]:
    actor = str(getattr(frappe.session, "user", "") or "")
    if (
        not actor
        or actor in {"Guest", "Administrator"}
        or SERVICE_ROLE not in frappe.get_roles(actor)
    ):
        raise frappe.PermissionError
    user = frappe.db.get_value(
        "User",
        actor,
        ["enabled", "user_type"],
        as_dict=True,
    )
    if not user or user.get("enabled") != 1 or user.get("user_type") != "Website User":
        raise frappe.PermissionError
    user_document = frappe.get_doc("User", actor)
    api_secret = user_document.get_password("api_secret", raise_exception=False)
    api_key = getattr(user_document, "api_key", None)
    if not isinstance(api_key, str) or not api_key or not isinstance(api_secret, str) or not api_secret:
        raise frappe.PermissionError
    request = getattr(frappe.local, "request", None)
    if request is None or not str(
        getattr(request, "content_type", "")
    ).casefold().startswith("application/json"):
        frappe.throw(
            _("Integration request content type is invalid."),
            frappe.ValidationError,
        )
    raw_body = request.get_data(cache=True, as_text=False)
    request_path = str(getattr(request, "path", ""))
    timestamp = str(request.headers.get("X-NPI-Timestamp", ""))
    signature = str(request.headers.get("X-NPI-Signature", ""))
    trace_id = str(request.headers.get("X-NPI-Trace-ID", ""))
    if request_path != path or _TRACE.fullmatch(trace_id) is None:
        frappe.throw(
            _("Integration request path or trace ID is invalid."),
            frappe.PermissionError,
        )
    secret = f"{api_key}:{api_secret}"
    try:
        verify_request(
            secret=secret,
            path=request_path,
            timestamp=timestamp,
            signature=signature,
            body=raw_body,
        )
    except ReceiverAuthenticationError:
        frappe.throw(
            _("Integration request authentication failed."),
            frappe.PermissionError,
        )
    return actor, secret, raw_body, trace_id


def _response(
    command: EngineeringChangeSummaryCommand,
    secret: str,
    *,
    status: int,
    projection_id: str | None,
    exact_replay: bool,
    partial: bool,
    retry_after_seconds: int | None,
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
        "summaryProjectionId": projection_id,
        "exactReplay": exact_replay,
        "partial": partial,
        "retryAfterSeconds": retry_after_seconds,
        "errorCode": error_code,
    }
    frappe.local.response.http_status_code = status
    return signed_response({**core, "responseHash": canonical_hash(core)}, secret)


def _require_viewer() -> None:
    actor = str(getattr(frappe.session, "user", "") or "")
    roles = set(frappe.get_roles(actor)) if actor and actor != "Guest" else set()
    if actor != "Administrator" and VIEWER_ROLE not in roles and "System Manager" not in roles:
        raise frappe.PermissionError


def _page(start: int | str, limit: int | str) -> tuple[int, int]:
    try:
        page_start = int(start)
        page_limit = int(limit)
    except (TypeError, ValueError) as error:
        raise frappe.ValidationError from error
    if page_start < 0 or not 1 <= page_limit <= 200:
        raise frappe.ValidationError
    return page_start, page_limit


def _bounded_text(value: object, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise frappe.ValidationError
    return value
