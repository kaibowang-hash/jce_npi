from __future__ import annotations

from typing import Any

import frappe

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.grid_personalization.controller import (
    GridPersonalizationController,
    PersonalGridPreferenceRepository,
)
from npi_core.grid_personalization.domain import GridPersonalizationValidationError
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_project_collaboration_routes_enabled,
    require_request_fields,
    response_request_id,
)


_PUT_FIELDS = frozenset(
    {
        "expectedVersion",
        "tableSchemaVersion",
        "viewId",
        "layout",
        "filter",
        "saveFilter",
        "favoriteViewIds",
        "recentViewIds",
        "defaultProjectId",
    }
)


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> PersonalGridPreferenceRepository:
    from npi_core.grid_personalization.frappe_repository import (
        FrappeGridPersonalizationRepository,
    )

    return FrappeGridPersonalizationRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _controller(request_id: str) -> GridPersonalizationController:
    require_project_collaboration_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    if principal.is_external:
        raise PermissionDenied()
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The grid personalization request has no trace identity.")
    repository = _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    return GridPersonalizationController(repository)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_work_grid_preferences(
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        controller = _controller(success_headers["X-Request-ID"])
        reject_unexpected_request_fields(frozenset(), request_fields)
        return controller.get()

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def set_my_work_grid_preferences(
    expectedVersion: Any = None,
    tableSchemaVersion: Any = None,
    viewId: Any = None,
    layout: Any = None,
    filter: Any = None,
    saveFilter: Any = None,
    favoriteViewIds: Any = None,
    recentViewIds: Any = None,
    defaultProjectId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        controller = _controller(success_headers["X-Request-ID"])
        require_csrf_token()
        reject_unexpected_request_fields(_PUT_FIELDS, request_fields)
        require_request_fields(_PUT_FIELDS, request_fields)
        try:
            return controller.put(
                expected_preference_version=expectedVersion,
                table_schema_version=tableSchemaVersion,
                view_id=viewId,
                layout=layout,
                filter_snapshot=filter,
                save_filter=saveFilter,
                favorite_view_ids=favoriteViewIds,
                recent_view_ids=recentViewIds,
                default_project_id=defaultProjectId,
            )
        except GridPersonalizationValidationError as error:
            raise RequestValidationFailed(
                [{"path": error.path, "message": error.message}]
            ) from error

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )
