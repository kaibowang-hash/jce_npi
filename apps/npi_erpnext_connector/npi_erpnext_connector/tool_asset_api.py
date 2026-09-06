from __future__ import annotations

import re

import frappe
from frappe import _

from npi_erpnext_connector import __version__
from npi_erpnext_connector.item_contract import canonical_hash
from npi_erpnext_connector.receiver_security import (
    ReceiverAuthenticationError,
    business_actor_is_enabled,
    signed_response,
    verify_request,
)
from npi_erpnext_connector.tool_asset_config import (
    CREATE_DISABLED_KEY,
    UPDATE_DISABLED_KEY,
    ToolAssetConfigurationError,
    load_tool_asset_profile,
    operation_is_disabled,
)
from npi_erpnext_connector.tool_asset_contract import (
    CREATE_OPERATION,
    OWNED_FIELDS,
    TOOL_ASSET_METHOD_PATH,
    UPDATE_OPERATION,
    ToolAssetCommand,
    ToolAssetContractError,
    decode_tool_asset_command,
)
from npi_erpnext_connector.tool_asset_frappe import (
    ToolAssetExecutionError,
    ToolAssetExecutionResult,
    execute_tool_asset_command,
)

SERVICE_ROLE = "NPI ERP Tool Asset Integration Service"
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@frappe.whitelist(methods=["POST"])
def upsert_npi_tool_asset_v1(**ignored: object) -> dict[str, object]:
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
    if path != TOOL_ASSET_METHOD_PATH:
        frappe.throw(_("Integration request path is invalid."), frappe.PermissionError)
    try:
        command = decode_tool_asset_command(raw_body)
    except ToolAssetContractError:
        frappe.throw(
            _("Integration Tool Asset request contract is invalid."),
            frappe.ValidationError,
        )
    if operation_is_disabled(frappe.conf, command.operation):
        return _failure(command, secret, "TOOL_ASSET_RECEIVER_DISABLED", 403)
    if not business_actor_is_enabled(command.actor_user_id, service_user=actor):
        return _failure(
            command,
            secret,
            "TOOL_ASSET_BUSINESS_ACTOR_UNAVAILABLE",
            403,
        )
    try:
        profile = load_tool_asset_profile(frappe.conf)
        result = execute_tool_asset_command(
            command,
            profile,
            service_user=actor,
            trace_id=trace_id,
        )
    except ToolAssetConfigurationError:
        return _failure(command, secret, "TOOL_ASSET_CONFIGURATION_INVALID", 422)
    except ToolAssetExecutionError as error:
        return _failure(command, secret, error.code, error.http_status)
    except frappe.ValidationError:
        return _failure(command, secret, "TOOL_ASSET_BUSINESS_VALIDATION", 422)
    return _response(command, secret, result)


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
            "createToolAsset": {
                "installed": True,
                "enabled": not operation_is_disabled(
                    frappe.conf,
                    CREATE_OPERATION,
                ),
                "configurationKey": CREATE_DISABLED_KEY,
            },
            "updateToolAsset": {
                "installed": True,
                "enabled": not operation_is_disabled(
                    frappe.conf,
                    UPDATE_OPERATION,
                ),
                "configurationKey": UPDATE_DISABLED_KEY,
            },
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
    user = frappe.db.get_value(
        "User",
        actor,
        ["enabled", "user_type"],
        as_dict=True,
    )
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
    command: ToolAssetCommand,
    secret: str,
    code: str,
    status: int,
) -> dict[str, object]:
    return _response(
        command,
        secret,
        ToolAssetExecutionResult(status, None, None, None, code, False),
    )


def _response(
    command: ToolAssetCommand,
    secret: str,
    result: ToolAssetExecutionResult,
) -> dict[str, object]:
    fields = []
    for code in OWNED_FIELDS:
        field_core = {
            "fieldCode": code,
            "httpStatus": result.http_status,
            "errorCode": result.error_code,
            "exactReplay": result.exact_replay,
        }
        fields.append({**field_core, "responseHash": canonical_hash(field_core)})
    core = {
        "contractVersion": 1,
        "operation": command.operation,
        "requestGlobalId": command.request_global_id,
        "attemptGlobalId": command.attempt_global_id,
        "attemptNumber": command.attempt_number,
        "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        "sourceHash": command.source_hash,
        "httpStatus": result.http_status,
        "formalAssetId": result.formal_asset_id,
        "targetVersion": result.target_version,
        "mappingVersion": result.mapping_version,
        "errorCode": result.error_code,
        "exactReplay": result.exact_replay,
        "fields": fields,
    }
    frappe.local.response.http_status_code = result.http_status
    return signed_response({**core, "responseHash": canonical_hash(core)}, secret)
