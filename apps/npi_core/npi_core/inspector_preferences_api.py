from __future__ import annotations

from typing import Any

import frappe

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import (
    PermissionDenied,
    RequestValidationFailed,
)
from npi_core.inspector_preferences.domain import (
    InspectorPreference,
    InspectorPreferenceValidationError,
)
from npi_core.inspector_preferences.frappe_repository import (
    FrappeInspectorPreferenceRepository,
)
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_project_collaboration_routes_enabled,
    require_request_fields,
    response_request_id,
)


_PUT_FIELDS = frozenset({"schemaVersion", "widthPx", "collapsed"})


def _repository_factory(
    *,
    actor_user_id: str,
) -> FrappeInspectorPreferenceRepository:
    return FrappeInspectorPreferenceRepository(actor_user_id=actor_user_id)


def _repository() -> FrappeInspectorPreferenceRepository:
    require_project_collaboration_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    if principal.is_external:
        raise PermissionDenied()
    return _repository_factory(actor_user_id=actor)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_work_inspector_preference(
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        repository = _repository()
        reject_unexpected_request_fields(frozenset(), request_fields)
        loaded = repository.load()
        return loaded.preference.response_dict(
            recovery_reason=loaded.recovery_reason,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def set_my_work_inspector_preference(
    schemaVersion: Any = None,
    widthPx: Any = None,
    collapsed: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        repository = _repository()
        require_csrf_token()
        reject_unexpected_request_fields(_PUT_FIELDS, request_fields)
        require_request_fields(_PUT_FIELDS, request_fields)
        try:
            preference = InspectorPreference.parse(
                {
                    "schemaVersion": schemaVersion,
                    "widthPx": widthPx,
                    "collapsed": collapsed,
                }
            )
        except InspectorPreferenceValidationError as error:
            raise RequestValidationFailed(
                [{"path": error.path, "message": error.message}]
            ) from error
        saved = repository.save(preference)
        return saved.response_dict(recovery_reason=None)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )
