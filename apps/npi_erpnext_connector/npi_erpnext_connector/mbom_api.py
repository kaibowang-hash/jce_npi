from __future__ import annotations

import re

import frappe
from frappe import _

from npi_erpnext_connector import __version__
from npi_erpnext_connector.item_contract import canonical_hash
from npi_erpnext_connector.mbom_config import (
    MbomConfigurationError,
    load_mbom_profile,
    mbom_receiver_is_disabled,
)
from npi_erpnext_connector.mbom_contract import (
    MBOM_METHOD_PATH,
    MBOM_OPERATION,
    MbomCommand,
    MbomContractError,
    decode_mbom_command,
)
from npi_erpnext_connector.mbom_frappe import (
    MbomExecutionError,
    MbomExecutionResult,
    MbomNodeExecutionResult,
    execute_mbom_command,
)
from npi_erpnext_connector.receiver_security import (
    ReceiverAuthenticationError,
    business_actor_is_enabled,
    signed_response,
    verify_request,
)

SERVICE_ROLE = "NPI ERP MBOM Integration Service"
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@frappe.whitelist(methods=["POST"])
def publish_mbom(**ignored: object) -> dict[str, object]:
    del ignored
    actor, secret = _service_identity()
    request = getattr(frappe.local, "request", None)
    if request is None or not str(
        getattr(request, "content_type", "")
    ).casefold().startswith("application/json"):
        frappe.throw(
            _("Integration request content type is invalid."),
            frappe.ValidationError,
        )
    raw_body = request.get_data(cache=True, as_text=False)
    path = str(getattr(request, "path", ""))
    timestamp = str(request.headers.get("X-NPI-Timestamp", ""))
    signature = str(request.headers.get("X-NPI-Signature", ""))
    trace_id = str(request.headers.get("X-NPI-Trace-ID", ""))
    if _TRACE.fullmatch(trace_id) is None:
        frappe.throw(
            _("Integration request trace ID is invalid."), frappe.ValidationError
        )
    try:
        verify_request(
            secret=secret,
            path=path,
            timestamp=timestamp,
            signature=signature,
            body=raw_body,
        )
    except ReceiverAuthenticationError:
        frappe.throw(
            _("Integration request authentication failed."),
            frappe.PermissionError,
        )
    if path != MBOM_METHOD_PATH:
        frappe.throw(_("Integration request path is invalid."), frappe.PermissionError)
    try:
        command = decode_mbom_command(raw_body)
    except MbomContractError:
        frappe.throw(
            _("Integration MBOM request contract is invalid."),
            frappe.ValidationError,
        )
    if mbom_receiver_is_disabled(frappe.conf):
        return _failure(command, secret, "MBOM_PUBLISH_RECEIVER_DISABLED", 403)
    if not business_actor_is_enabled(command.actor_user_id, service_user=actor):
        return _failure(
            command,
            secret,
            "MBOM_PUBLISH_BUSINESS_ACTOR_UNAVAILABLE",
            403,
        )
    try:
        profile = load_mbom_profile(frappe.conf)
        result = execute_mbom_command(
            command,
            profile,
            service_user=actor,
            trace_id=trace_id,
        )
    except MbomConfigurationError:
        return _failure(command, secret, "MBOM_PUBLISH_CONFIGURATION_INVALID", 422)
    except MbomExecutionError as error:
        return _failure(command, secret, error.code, error.http_status)
    return _response(command, secret, result, status=200)


@frappe.whitelist(methods=["GET"])
def capabilities() -> dict[str, object]:
    actor = str(getattr(frappe.session, "user", "") or "")
    if actor == "Guest" or (
        actor != "Administrator" and SERVICE_ROLE not in frappe.get_roles(actor)
    ):
        raise frappe.PermissionError
    return {
        "appVersion": __version__,
        "supportedFrappeMajors": [15, 16],
        "operations": {
            "publishReleasedMbom": {
                "installed": True,
                "enabled": not mbom_receiver_is_disabled(frappe.conf),
            }
        },
    }


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
    if (
        not isinstance(api_key, str)
        or not api_key
        or not isinstance(secret, str)
        or not secret
    ):
        raise frappe.PermissionError
    return actor, f"{api_key}:{secret}"


def _failure(
    command: MbomCommand,
    secret: str,
    code: str,
    status: int,
) -> dict[str, object]:
    nodes = tuple(
        MbomNodeExecutionResult(
            node.stable_line_key,
            node.assembly_source_key,
            status,
            None,
            None,
            None,
            None,
            code,
        )
        for node in command.nodes
    )
    return _response(
        command,
        secret,
        MbomExecutionResult(nodes, False),
        status=status,
    )


def _response(
    command: MbomCommand,
    secret: str,
    result: MbomExecutionResult,
    *,
    status: int,
) -> dict[str, object]:
    nodes = []
    for value in result.nodes:
        node_core = {**value.mapping(), "exactReplay": result.exact_replay}
        nodes.append({**node_core, "responseHash": canonical_hash(node_core)})
    core = {
        "contractVersion": 1,
        "operation": MBOM_OPERATION,
        "requestGlobalId": command.request_global_id,
        "attemptGlobalId": command.attempt_global_id,
        "attemptNumber": command.attempt_number,
        "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        "sourceHash": command.source_hash,
        "topologyHash": command.topology_hash,
        "nodeManifestHash": command.node_manifest_hash,
        "nodes": nodes,
    }
    frappe.local.response.http_status_code = status
    return signed_response({**core, "responseHash": canonical_hash(core)}, secret)
