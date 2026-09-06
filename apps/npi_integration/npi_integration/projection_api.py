from __future__ import annotations

from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.foundation.tracing import current_trace_id
from npi_core.project_api import ProjectUnavailable
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    response_request_id,
)
from npi_integration.projections.domain import ProjectionKind
from npi_integration.projections.frappe_repository import FrappeProjectionRepository
from npi_integration.projections.response import validate_project_projection_collection


_QUERY_FIELDS = frozenset({"kind"})


class ProjectionRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "ERP_PROJECTION_ROUTES_DISABLED",
            _("ERP projection access is temporarily unavailable."),
        )


def projection_routes_are_disabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p8_01_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_erp_projections(
    kind: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        request_id = _request_id()
        trace_id = current_trace_id.get()
        if trace_id is None:
            raise RuntimeError("The ERP projection query has no trace identity.")
        repository = FrappeProjectionRepository(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )
        project_id = _route_project_id()
        access = repository.authorize_project(project_id)
        if access is None:
            raise ProjectUnavailable()
        reject_unexpected_request_fields(_QUERY_FIELDS, request_fields)
        selected_kind = _kind_filter(kind)
        if projection_routes_are_disabled():
            raise ProjectionRoutesDisabled()
        response = validate_project_projection_collection(
            repository.project_collection(access, kind=selected_kind),
            expected_project_global_id=project_id,
        )
        headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _kind_filter(value: object) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise _field_problem("kind", _("Select a supported projection kind."))
    try:
        return ProjectionKind(value).value
    except ValueError as error:
        raise _field_problem(
            "kind", _("Select a supported projection kind.")
        ) from error


def _route_project_id() -> UUID:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    value = route_params.get("project_id") if hasattr(route_params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ProjectUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise ProjectUnavailable()
    return parsed


def _request_id() -> str:
    value = frappe.get_request_header("X-Request-ID")
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field_problem("requestId", _("Enter a valid request ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field_problem("requestId", _("Enter a valid request ID."))
    return str(parsed)


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
