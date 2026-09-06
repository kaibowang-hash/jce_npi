from __future__ import annotations

import re

import frappe
from frappe import _

from npi_erpnext_connector import __version__
from npi_erpnext_connector.project_publish_config import ProjectReceiverConfigurationError, load_receiver_profile, receiver_is_disabled
from npi_erpnext_connector.project_publish_contract import CONTRACT_VERSION, OPERATION, RECONCILE_OPERATION, ProjectPublishContractError, ProjectPublishCommand, ProjectReconcileCommand, canonical_hash, decode_publish_command, decode_reconcile_command
from npi_erpnext_connector.project_publish_frappe import ProjectPublishExecutionError, execute_project_command, receipt_for
from npi_erpnext_connector.receiver_security import ReceiverAuthenticationError, business_actor_is_enabled, signed_response, verify_request


SERVICE_ROLE = "NPI ERP Integration Service"
PUBLISH_PATH = "/api/method/npi_erpnext_connector.project_publish_api.publish_project"
RECONCILE_PATH = "/api/method/npi_erpnext_connector.project_publish_api.reconcile_project"
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@frappe.whitelist(methods=["POST"])
def publish_project(**ignored: object) -> dict[str, object]:
    del ignored
    actor, secret, raw_body, trace_id = _authenticated_request(PUBLISH_PATH)
    try:
        command = decode_publish_command(raw_body)
    except ProjectPublishContractError:
        frappe.throw(_("Integration Project request contract is invalid."), frappe.ValidationError)
    if receiver_is_disabled(frappe.conf):
        return _publish_response(command, secret, 403, None, None, False, "PROJECT_PUBLISH_RECEIVER_DISABLED")
    if not business_actor_is_enabled(command.actor_user_id, service_user=actor):
        return _publish_response(command, secret, 403, None, None, False, "PROJECT_PUBLISH_BUSINESS_ACTOR_UNAVAILABLE")
    try:
        result = execute_project_command(command, load_receiver_profile(frappe.conf), service_user=actor, trace_id=trace_id)
    except ProjectReceiverConfigurationError:
        return _publish_response(command, secret, 422, None, None, False, "PROJECT_PUBLISH_CONFIGURATION_INVALID")
    except ProjectPublishExecutionError as error:
        return _publish_response(command, secret, error.http_status, None, None, False, error.code)
    return _publish_response(command, secret, 200, result.formal_project_id, result.target_version, result.exact_replay, None)


@frappe.whitelist(methods=["POST"])
def reconcile_project(**ignored: object) -> dict[str, object]:
    del ignored
    _actor, secret, raw_body, _trace_id = _authenticated_request(RECONCILE_PATH)
    try:
        command = decode_reconcile_command(raw_body)
    except ProjectPublishContractError:
        frappe.throw(_("Integration Project reconciliation contract is invalid."), frappe.ValidationError)
    if receiver_is_disabled(frappe.conf):
        return _reconcile_response(command, secret, 403, False, None, None, "PROJECT_PUBLISH_RECEIVER_DISABLED")
    try:
        result = receipt_for(command.target_idempotency_key_hash, command.source_hash)
    except ProjectPublishExecutionError as error:
        return _reconcile_response(command, secret, error.http_status, False, None, None, error.code)
    return _reconcile_response(command, secret, 200, result is not None, result.formal_project_id if result else None, result.target_version if result else None, None)


@frappe.whitelist(methods=["GET"])
def capabilities() -> dict[str, object]:
    actor = str(getattr(frappe.session, "user", "") or "")
    if actor == "Guest" or (actor != "Administrator" and SERVICE_ROLE not in frappe.get_roles(actor)):
        raise frappe.PermissionError
    return {"appVersion": __version__, "supportedFrappeMajors": [15, 16], "operations": {"createErpProject": {"installed": True, "enabled": not receiver_is_disabled(frappe.conf)}, "reconcileErpProject": {"installed": True, "enabled": not receiver_is_disabled(frappe.conf)}}}


def _authenticated_request(expected_path: str) -> tuple[str, str, bytes, str]:
    actor, secret = _service_identity()
    request = getattr(frappe.local, "request", None)
    if request is None or not str(getattr(request, "content_type", "")).casefold().startswith("application/json"):
        frappe.throw(_("Integration request content type is invalid."), frappe.ValidationError)
    raw_body = request.get_data(cache=True, as_text=False)
    path = str(getattr(request, "path", ""))
    trace_id = str(request.headers.get("X-NPI-Trace-ID", ""))
    if path != expected_path or _TRACE.fullmatch(trace_id) is None:
        frappe.throw(_("Integration request path or trace ID is invalid."), frappe.PermissionError)
    try:
        verify_request(secret=secret, path=path, timestamp=str(request.headers.get("X-NPI-Timestamp", "")), signature=str(request.headers.get("X-NPI-Signature", "")), body=raw_body)
    except ReceiverAuthenticationError:
        frappe.throw(_("Integration request authentication failed."), frappe.PermissionError)
    return actor, secret, raw_body, trace_id


def _service_identity() -> tuple[str, str]:
    actor = str(getattr(frappe.session, "user", "") or "")
    if not actor or actor in {"Guest", "Administrator"} or SERVICE_ROLE not in frappe.get_roles(actor):
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


def _publish_response(command: ProjectPublishCommand, secret: str, status: int, formal: str | None, version: str | None, exact: bool, error: str | None) -> dict[str, object]:
    core = {"contractVersion": CONTRACT_VERSION, "operation": OPERATION, "requestGlobalId": command.request_global_id, "attemptGlobalId": command.attempt_global_id, "attemptNumber": command.attempt_number, "targetIdempotencyKeyHash": command.target_idempotency_key_hash, "sourceHash": command.source_hash, "httpStatus": status, "formalProjectId": formal, "targetVersion": version, "exactReplay": exact, "errorCode": error}
    return _response(core, secret, status)


def _reconcile_response(command: ProjectReconcileCommand, secret: str, status: int, found: bool, formal: str | None, version: str | None, error: str | None) -> dict[str, object]:
    core = {"contractVersion": CONTRACT_VERSION, "operation": RECONCILE_OPERATION, "requestGlobalId": command.request_global_id, "attemptGlobalId": command.attempt_global_id, "targetIdempotencyKeyHash": command.target_idempotency_key_hash, "sourceHash": command.source_hash, "httpStatus": status, "found": found, "formalProjectId": formal, "targetVersion": version, "errorCode": error}
    return _response(core, secret, status)


def _response(core: dict[str, object], secret: str, status: int) -> dict[str, object]:
    frappe.local.response.http_status_code = status
    return signed_response({**core, "responseHash": canonical_hash(core)}, secret)
