from __future__ import annotations

import re

import frappe
from frappe import _

from npi_erpnext_connector import __version__
from npi_erpnext_connector.item_config import (
    ItemConfigurationError,
    load_item_profile,
    receiver_is_disabled,
)
from npi_erpnext_connector.item_contract import (
    CONTRACT_VERSION,
    ItemCommand,
    ItemContractError,
    canonical_hash,
    decode_item_command,
)
from npi_erpnext_connector.item_frappe import ItemExecutionError, execute_item_command
from npi_erpnext_connector.receiver_security import (
    ReceiverAuthenticationError,
    business_actor_is_enabled,
    signed_response,
    verify_request,
)

SERVICE_ROLE = "NPI ERP Integration Service"
ITEM_METHOD_PATH = "/api/method/npi_erpnext_connector.item_api.publish_item"
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@frappe.whitelist(methods=["POST"])
def publish_item(**ignored: object) -> dict[str, object]:
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
            _("Integration request trace ID is invalid."),
            frappe.ValidationError,
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
    if path != ITEM_METHOD_PATH:
        frappe.throw(
            _("Integration request path is invalid."),
            frappe.PermissionError,
        )
    try:
        command = decode_item_command(raw_body)
    except ItemContractError:
        frappe.throw(
            _("Integration Item request contract is invalid."),
            frappe.ValidationError,
        )
    if receiver_is_disabled(frappe.conf):
        return _failure(command, secret, "ITEM_PUBLISH_RECEIVER_DISABLED", 403)
    if not business_actor_is_enabled(command.actor_user_id, service_user=actor):
        return _failure(
            command,
            secret,
            "ITEM_PUBLISH_BUSINESS_ACTOR_UNAVAILABLE",
            403,
        )
    try:
        profile = load_item_profile(frappe.conf)
        result = execute_item_command(
            command,
            profile,
            service_user=actor,
            trace_id=trace_id,
        )
    except ItemConfigurationError:
        return _failure(command, secret, "ITEM_PUBLISH_CONFIGURATION_INVALID", 422)
    except ItemExecutionError as error:
        return _failure(command, secret, error.code, error.http_status)
    return _success(
        command,
        secret,
        result.formal_item_code,
        result.target_version,
        result.mapping_version,
        result.exact_replay,
    )


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
            "publishReleasedItem": {
                "installed": True,
                "enabled": not receiver_is_disabled(frappe.conf),
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
    user = frappe.db.get_value(
        "User",
        actor,
        ["enabled", "user_type"],
        as_dict=True,
    )
    if not user or user.get("enabled") != 1 or user.get("user_type") != "Website User":
        raise frappe.PermissionError
    user_document = frappe.get_doc("User", actor)
    secret = user_document.get_password(
        "api_secret",
        raise_exception=False,
    )
    api_key = getattr(user_document, "api_key", None)
    if (
        not isinstance(api_key, str)
        or not api_key
        or not isinstance(secret, str)
        or not secret
    ):
        raise frappe.PermissionError
    return actor, f"{api_key}:{secret}"


def _success(
    command: ItemCommand,
    secret: str,
    formal_item_code: str,
    target_version: str,
    mapping_version: int,
    exact_replay: bool,
) -> dict[str, object]:
    return _response(
        command,
        secret,
        status=200,
        formal_item_code=formal_item_code,
        target_version=target_version,
        mapping_version=mapping_version,
        exact_replay=exact_replay,
        error_code=None,
    )


def _failure(
    command: ItemCommand,
    secret: str,
    error_code: str,
    status: int,
) -> dict[str, object]:
    return _response(
        command,
        secret,
        status=status,
        formal_item_code=None,
        target_version=None,
        mapping_version=None,
        exact_replay=False,
        error_code=error_code,
    )


def _response(
    command: ItemCommand,
    secret: str,
    *,
    status: int,
    formal_item_code: str | None,
    target_version: str | None,
    mapping_version: int | None,
    exact_replay: bool,
    error_code: str | None,
) -> dict[str, object]:
    core = {
        "contractVersion": CONTRACT_VERSION,
        "operation": "publish_released_item",
        "requestGlobalId": command.request_global_id,
        "attemptGlobalId": command.attempt_global_id,
        "attemptNumber": command.attempt_number,
        "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        "sourceHash": command.source_hash,
        "httpStatus": status,
        "formalItemCode": formal_item_code,
        "targetVersion": target_version,
        "mappingVersion": mapping_version,
        "exactReplay": exact_replay,
        "errorCode": error_code,
    }
    frappe.local.response.http_status_code = status
    return signed_response({**core, "responseHash": canonical_hash(core)}, secret)
