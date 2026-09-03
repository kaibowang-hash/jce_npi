from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.request_security import (
    authenticated_user,
    configured_tenant_id,
    reject_unexpected_request_fields,
    response_request_id,
)
from npi_integration.authorization_projection.domain import (
    AuthorizationProjectionError,
    AuthorizationProjectionEvent,
)
from npi_integration.authorization_projection.frappe_repository import (
    FrappeAuthorizationProjectionRepository,
)
from npi_integration.authorization_projection.frappe_validation import (
    require_service_actor,
)


_FIELDS = frozenset(
    {
        "schemaVersion",
        "operation",
        "sourceSystem",
        "targetSystem",
        "objectType",
        "eventId",
        "sourceSubjectId",
        "targetUserId",
        "sourceVersion",
        "enabled",
        "roles",
        "projectAccess",
        "organizationScopes",
        "issuedAt",
        "expiresAt",
        "traceId",
        "payloadHash",
    }
)


class AuthorizationProjectionRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "AUTHORIZATION_PROJECTION_ROUTES_DISABLED",
            _("Authorization projection is temporarily unavailable."),
            retryable=True,
        )


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def replace_user_authorization(
    schemaVersion: Any = None,
    operation: Any = None,
    sourceSystem: Any = None,
    targetSystem: Any = None,
    objectType: Any = None,
    eventId: Any = None,
    sourceSubjectId: Any = None,
    targetUserId: Any = None,
    sourceVersion: Any = None,
    enabled: Any = None,
    roles: Any = None,
    projectAccess: Any = None,
    organizationScopes: Any = None,
    issuedAt: Any = None,
    expiresAt: Any = None,
    traceId: Any = None,
    payloadHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        if _routes_are_disabled():
            raise AuthorizationProjectionRoutesDisabled()
        actor = authenticated_user()
        require_service_actor(actor)
        reject_unexpected_request_fields(_FIELDS, request_fields)
        request_id = _request_id()
        event = _event(
            {
                "schemaVersion": schemaVersion,
                "operation": operation,
                "sourceSystem": sourceSystem,
                "targetSystem": targetSystem,
                "objectType": objectType,
                "eventId": eventId,
                "sourceSubjectId": sourceSubjectId,
                "targetUserId": targetUserId,
                "sourceVersion": sourceVersion,
                "enabled": enabled,
                "roles": _json_value(roles),
                "projectAccess": _json_value(projectAccess),
                "organizationScopes": _json_value(organizationScopes),
                "issuedAt": issuedAt,
                "expiresAt": expiresAt,
                "traceId": traceId,
                "payloadHash": payloadHash,
            }
        )
        repository = FrappeAuthorizationProjectionRepository(
            actor=actor,
            tenant_id=configured_tenant_id(),
            request_id=request_id,
            now=datetime.now(UTC),
        )
        try:
            outcome = repository.apply(event)
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
            frappe.db.rollback()
            outcome = repository.apply(event)
        headers["X-Request-ID"] = str(request_id)
        return {
            "projectionId": str(outcome.projection_id),
            "sourceVersion": outcome.source_version,
            "state": outcome.state,
            "projectionHash": outcome.projection_hash,
            "exactReplay": outcome.exact_replay,
            "localUserState": outcome.local_user_state,
            "localUserDisposition": outcome.local_user_disposition,
            "requestId": str(request_id),
            "traceId": event.trace_id,
        }

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _routes_are_disabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p9_04_authorization_projection_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def _request_id() -> UUID:
    value = frappe.get_request_header("X-Request-ID")
    try:
        request_id = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise RequestValidationFailed(
            [{"path": "requestId", "message": _("Enter a valid request ID.")}]
        ) from error
    if request_id.int == 0 or str(request_id) != str(value).casefold():
        raise RequestValidationFailed(
            [{"path": "requestId", "message": _("Enter a valid request ID.")}]
        )
    return request_id


def _event(value: object) -> AuthorizationProjectionEvent:
    try:
        return AuthorizationProjectionEvent.from_mapping(value)
    except AuthorizationProjectionError as error:
        raise RequestValidationFailed(
            [
                {
                    "path": "authorizationProjection",
                    "message": _("Enter a valid authorization projection."),
                }
            ]
        ) from error


def _json_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise RequestValidationFailed(
            [
                {
                    "path": "authorizationProjection",
                    "message": _("Enter a valid authorization projection."),
                }
            ]
        ) from error
