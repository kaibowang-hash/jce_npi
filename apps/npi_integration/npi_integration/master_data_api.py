from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    configured_tenant_id,
    reject_unexpected_request_fields,
    response_request_id,
)
from npi_integration.authorization_projection.frappe_validation import (
    require_service_actor,
)
from npi_integration.master_data.domain import (
    MasterCatalogKind,
    MasterDataContractError,
    MasterSnapshotEvent,
)
from npi_integration.master_data.frappe_repository import (
    MAX_QUERY_LIMIT,
    MAX_QUERY_OFFSET,
    apply_snapshot,
    catalog_collection,
)


_PUT_FIELDS = frozenset(
    {
        "schemaVersion",
        "operation",
        "sourceSystem",
        "targetSystem",
        "eventId",
        "catalogKind",
        "sourceEnvironment",
        "sourceVersion",
        "sourceModifiedAt",
        "records",
        "issuedAt",
        "traceId",
        "payloadHash",
    }
)
_GET_FIELDS = frozenset({"kind", "query", "limit", "offset", "projectId"})


class MasterDataRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "ERP_MASTER_DATA_ROUTES_DISABLED",
            _("ERPNext master data synchronization is temporarily unavailable."),
            retryable=True,
        )


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def replace_master_catalog(
    schemaVersion: Any = None,
    operation: Any = None,
    sourceSystem: Any = None,
    targetSystem: Any = None,
    eventId: Any = None,
    catalogKind: Any = None,
    sourceEnvironment: Any = None,
    sourceVersion: Any = None,
    sourceModifiedAt: Any = None,
    records: Any = None,
    issuedAt: Any = None,
    traceId: Any = None,
    payloadHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, object]:
        if _routes_are_disabled():
            raise MasterDataRoutesDisabled()
        actor = authenticated_user()
        require_service_actor(actor)
        reject_unexpected_request_fields(_PUT_FIELDS, request_fields)
        request_id = _request_id()
        try:
            event = MasterSnapshotEvent.from_mapping(
                {
                    "schemaVersion": schemaVersion,
                    "operation": operation,
                    "sourceSystem": sourceSystem,
                    "targetSystem": targetSystem,
                    "eventId": eventId,
                    "catalogKind": catalogKind,
                    "sourceEnvironment": sourceEnvironment,
                    "sourceVersion": sourceVersion,
                    "sourceModifiedAt": sourceModifiedAt,
                    "records": _json_value(records),
                    "issuedAt": issuedAt,
                    "traceId": traceId,
                    "payloadHash": payloadHash,
                }
            )
        except MasterDataContractError as error:
            raise RequestValidationFailed(
                [
                    {
                        "path": "masterDataSnapshot",
                        "message": _("Enter a valid ERPNext master data snapshot."),
                    }
                ]
            ) from error
        try:
            outcome = apply_snapshot(
                event,
                actor=actor,
                tenant_id=configured_tenant_id(),
                request_id=request_id,
                now=datetime.now(UTC),
            )
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
            frappe.db.rollback()
            outcome = apply_snapshot(
                event,
                actor=actor,
                tenant_id=configured_tenant_id(),
                request_id=request_id,
                now=datetime.now(UTC),
            )
        headers["X-Request-ID"] = str(request_id)
        return {
            "snapshotId": str(outcome.snapshot_id),
            "catalogKind": event.kind.value,
            "sourceVersion": outcome.source_version,
            "recordCount": outcome.record_count,
            "payloadHash": outcome.payload_hash,
            "exactReplay": outcome.exact_replay,
            "requestId": str(request_id),
            "traceId": event.trace_id,
        }

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_master_catalog(
    kind: Any = None,
    query: Any = None,
    limit: Any = None,
    offset: Any = None,
    projectId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, object]:
        principal = authenticated_principal()
        if principal.is_external:
            raise PermissionDenied()
        reject_unexpected_request_fields(_GET_FIELDS, request_fields)
        headers["X-Request-ID"] = str(_request_id())
        try:
            selected_kind = MasterCatalogKind(kind)
        except (TypeError, ValueError) as error:
            raise _problem("kind", _("Select a supported ERPNext master data type.")) from error
        selected_query = _query(query)
        selected_limit = _integer(limit, default=100, minimum=1, maximum=MAX_QUERY_LIMIT)
        selected_offset = _integer(
            offset, default=0, minimum=0, maximum=MAX_QUERY_OFFSET
        )
        return catalog_collection(
            tenant_id=str(principal.tenant_id),
            kind=selected_kind,
            query=selected_query,
            limit=selected_limit,
            offset=selected_offset,
            allowed_source_keys=_project_source_keys(principal, selected_kind, projectId),
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _project_source_keys(principal, kind, project_id):
    allowed = _allowed_source_keys(principal, kind)
    if project_id is None:
        return allowed
    from npi_core.project.frappe_repository import FrappeProjectRepository
    from npi_core.foundation.tracing import current_trace_id
    from npi_core.project_api import ProjectUnavailable

    try:
        identifier = UUID(str(project_id))
        if str(identifier) != project_id or identifier.int == 0:
            raise ValueError()
    except (ValueError, TypeError, AttributeError) as error:
        raise _problem("projectId", _("Enter a valid project ID.")) from error
    repository = FrappeProjectRepository(
        principal=principal, request_id=str(_request_id()),
        trace_id=current_trace_id.get(),
    )
    cockpit = repository.project_cockpit(identifier)
    if cockpit is None:
        raise ProjectUnavailable()
    if kind is MasterCatalogKind.CUSTOMER:
        keys = frozenset(
            value["sourceObjectId"] for value in cockpit["references"]
            if value["type"] == "customer" and value["sourceSystem"] == "ERPNEXT"
        )
        return keys if allowed is None else allowed & keys
    return allowed


def _routes_are_disabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    return not (
        hasattr(configuration, "get")
        and configuration.get("npi_erp_master_data_routes_disabled") is False
    )


def _allowed_source_keys(principal: object, kind: MasterCatalogKind) -> frozenset[str] | None:
    roles = getattr(principal, "roles", frozenset())
    if "System Manager" in roles:
        return None
    scope_kind = {
        MasterCatalogKind.CUSTOMER: "Customer",
        MasterCatalogKind.SUPPLIER: "Supplier",
    }.get(kind)
    if scope_kind is None:
        return None
    scopes = getattr(principal, "organization_scopes", {})
    values = scopes.get(scope_kind, frozenset()) if hasattr(scopes, "get") else ()
    return frozenset(str(value) for value in values)


def _request_id() -> UUID:
    value = frappe.get_request_header("X-Request-ID")
    try:
        request_id = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _problem("requestId", _("Enter a valid request ID.")) from error
    if request_id.int == 0 or str(request_id) != str(value).casefold():
        raise _problem("requestId", _("Enter a valid request ID."))
    return request_id


def _query(value: object) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or value != value.strip() or len(value) > 100:
        raise _problem("query", _("Enter a valid master data search."))
    return value


def _integer(value: object, *, default: int, minimum: int, maximum: int) -> int:
    if value in (None, ""):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise _problem("page", _("Enter a valid master data page.")) from error
    if str(result) != str(value) or not minimum <= result <= maximum:
        raise _problem("page", _("Enter a valid master data page."))
    return result


def _json_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise RequestValidationFailed(
            [
                {
                    "path": "masterDataSnapshot",
                    "message": _("Enter a valid ERPNext master data snapshot."),
                }
            ]
        ) from error


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
