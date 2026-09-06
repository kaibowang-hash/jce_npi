from __future__ import annotations

from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.project_api import ProjectUnavailable
from npi_core.project_controls.frappe_repository import (
    FrappeProjectControlsRepository,
    ProjectControlCommandOutcome,
)
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_project_collaboration_routes_enabled,
    require_request_fields,
    require_csrf_token,
    response_request_id,
)


_BIND_FIELDS = frozenset({"expectedProjectVersion", "policyRef", "bindings"})
_ASSESS_FIELDS = frozenset(
    {
        "expectedProjectVersion",
        "measurements",
        "reason",
        "recoveryPlan",
    }
)
_TRANSITION_FIELDS = frozenset({"expectedProjectVersion", "action", "reason"})
_COMMENT_FIELDS = frozenset({"body", "mentions", "attachments", "objectLinks"})
_FOLLOW_FIELDS = frozenset({"expectedVersion"})
_ACTIVITY_FIELDS = frozenset({"cursor", "limit"})
_PROJECT_LEARNING_QUERY_FIELDS = frozenset({"kind", "search", "learningId", "limit"})
_CREATE_LEARNING_FIELDS = frozenset(
    {"kind", "title", "content", "recommendation", "tags"}
)
_LEARNING_SEARCH_FIELDS = frozenset(
    {
        "kind",
        "tag",
        "search",
        "projectId",
        "templateGlobalId",
        "templateVersion",
        "limit",
    }
)
_TRANSPORT_ROLE = "NPI API User"


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_controls(**request_fields: Any) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_project_collaboration_routes_enabled()
        reject_unexpected_request_fields(frozenset(), request_fields)
        repository, request_id = _query_repository()
        response = repository.controls(_route_project_id())
        if response is None:
            raise ProjectUnavailable()
        success_headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def bind_project_control_policy(
    expectedProjectVersion: Any = None,
    policyRef: Any = None,
    bindings: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command_call(
        allowed_fields=_BIND_FIELDS,
        request_fields=request_fields,
        system_manager_only=True,
        operation=lambda repository, key: repository.bind_policy(
            _route_project_id(),
            idempotency_key=key,
            expected_project_version=expectedProjectVersion,
            policy_ref=policyRef,
            bindings=bindings,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def assess_project_health(
    expectedProjectVersion: Any = None,
    measurements: Any = None,
    reason: Any = None,
    recoveryPlan: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command_call(
        allowed_fields=_ASSESS_FIELDS,
        request_fields=request_fields,
        operation=lambda repository, key: repository.assess_health(
            _route_project_id(),
            idempotency_key=key,
            expected_project_version=expectedProjectVersion,
            measurements=measurements,
            reason=reason,
            recovery_plan=recoveryPlan,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def transition_project(
    expectedProjectVersion: Any = None,
    action: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command_call(
        allowed_fields=_TRANSITION_FIELDS,
        request_fields=request_fields,
        operation=lambda repository, key: repository.transition(
            _route_project_id(),
            idempotency_key=key,
            expected_project_version=expectedProjectVersion,
            action=action,
            reason=reason,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_activity(
    cursor: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_project_collaboration_routes_enabled()
        reject_unexpected_request_fields(_ACTIVITY_FIELDS, request_fields)
        repository, request_id = _query_repository()
        response = repository.activity(
            _route_project_id(),
            cursor=cursor,
            limit=_query_integer(limit, "limit", default=50),
        )
        if response is None:
            raise ProjectUnavailable()
        success_headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def add_project_comment(
    body: Any = None,
    mentions: Any = None,
    attachments: Any = None,
    objectLinks: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command_call(
        allowed_fields=_COMMENT_FIELDS,
        request_fields=request_fields,
        success_status=201,
        operation=lambda repository, key: repository.add_comment(
            _route_project_id(),
            idempotency_key=key,
            body=body,
            mentions=mentions,
            attachments=attachments,
            object_links=objectLinks,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def follow_project(
    expectedVersion: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _follow_call(
        active=True,
        expected_version=expectedVersion,
        request_fields=request_fields,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def unfollow_project(
    expectedVersion: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _follow_call(
        active=False,
        expected_version=expectedVersion,
        request_fields=request_fields,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_learning(
    kind: Any = None,
    search: Any = None,
    learningId: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_project_collaboration_routes_enabled()
        reject_unexpected_request_fields(
            _PROJECT_LEARNING_QUERY_FIELDS,
            request_fields,
        )
        repository, request_id = _query_repository()
        response = repository.project_learning(
            _route_project_id(),
            kind=kind,
            search=search,
            learning_id=learningId,
            limit=_query_integer(limit, "limit", default=50),
        )
        if response is None:
            raise ProjectUnavailable()
        success_headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_project_learning(
    kind: Any = None,
    title: Any = None,
    content: Any = None,
    recommendation: Any = None,
    tags: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command_call(
        allowed_fields=_CREATE_LEARNING_FIELDS,
        request_fields=request_fields,
        success_status=201,
        operation=lambda repository, key: repository.create_learning(
            _route_project_id(),
            idempotency_key=key,
            kind=kind,
            title=title,
            content=content,
            recommendation=recommendation,
            tags=tags,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def search_project_learning(
    kind: Any = None,
    tag: Any = None,
    search: Any = None,
    projectId: Any = None,
    templateGlobalId: Any = None,
    templateVersion: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        repository, request_id = _query_repository(internal_only=True)
        reject_unexpected_request_fields(
            _LEARNING_SEARCH_FIELDS,
            request_fields,
        )
        project_id = _optional_uuid(projectId, "projectId")
        response = repository.search_learning(
            kind=kind,
            tag=tag,
            search=search,
            project_id=project_id,
            # Secondary filter parsing remains inside the repository after an
            # optional exact Project authorization anchor is resolved.
            template_global_id=templateGlobalId,
            template_version=templateVersion,
            limit=_query_integer(limit, "limit", default=50),
        )
        if response is None:
            raise ProjectUnavailable()
        success_headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


def _follow_call(
    *,
    active: bool,
    expected_version: object,
    request_fields: dict[str, Any],
) -> dict[str, Any] | None:
    return _command_call(
        allowed_fields=_FOLLOW_FIELDS,
        request_fields=request_fields,
        operation=lambda repository, key: repository.set_following(
            _route_project_id(),
            idempotency_key=key,
            expected_version=expected_version,  # type: ignore[arg-type]
            active=active,
        ),
    )


def _command_call(
    *,
    allowed_fields: frozenset[str],
    request_fields: dict[str, Any],
    operation,
    success_status: int = 200,
    system_manager_only: bool = False,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        repository, idempotency_key, request_id = _command_repository(
            system_manager_only=system_manager_only,
        )
        reject_unexpected_request_fields(allowed_fields, request_fields)
        require_request_fields(allowed_fields, request_fields)
        outcome = operation(repository, idempotency_key)
        if outcome is None:
            raise ProjectUnavailable()
        assert isinstance(outcome, ProjectControlCommandOutcome)
        success_headers["X-Request-ID"] = request_id
        success_headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return outcome.response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=success_status,
        response_headers=success_headers,
    )


def _query_repository(
    *,
    internal_only: bool = False,
) -> tuple[FrappeProjectControlsRepository, str]:
    require_project_collaboration_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    if internal_only and principal.is_external:
        raise PermissionDenied()
    request_id = _request_id()
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Project control query has no trace identity.")
    return (
        FrappeProjectControlsRepository(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        ),
        request_id,
    )


def _command_repository(
    *,
    system_manager_only: bool = False,
) -> tuple[
    FrappeProjectControlsRepository,
    str,
    str,
]:
    require_project_collaboration_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    required_role = "System Manager" if system_manager_only else _TRANSPORT_ROLE
    if principal.is_external or required_role not in principal.roles:
        raise PermissionDenied()
    request_id = _request_id()
    idempotency_key = actor_idempotency_key_hash(
        actor,
        frappe.get_request_header("Idempotency-Key"),
    )
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Project control command has no trace identity.")
    return (
        FrappeProjectControlsRepository(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        ),
        idempotency_key,
        request_id,
    )


def _route_project_id() -> UUID:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    value = route_params.get("project_id") if hasattr(route_params, "get") else None
    parsed = _optional_uuid(value, "projectId")
    if parsed is None:
        raise _field_problem("projectId", _("Enter a valid global ID."))
    return parsed


def _request_id() -> str:
    value = frappe.get_request_header("X-Request-ID")
    parsed = _optional_uuid(value, "requestId")
    if parsed is None:
        raise _field_problem("requestId", _("Enter a valid request ID."))
    return str(parsed)


def _optional_uuid(value: object, path: str) -> UUID | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise _field_problem(path, _("Enter a valid global ID."))
    if str(parsed) != value.casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _query_integer(value: object, path: str, *, default: int) -> int:
    if value is None or value == "":
        return default
    parsed = _optional_query_integer(value, path, maximum=100)
    assert parsed is not None
    return parsed


def _optional_query_integer(
    value: object,
    path: str,
    *,
    maximum: int = 2_147_483_647,
) -> int | None:
    if value is None or value == "":
        return None
    if type(value) is int:
        parsed = value
    elif (
        isinstance(value, str)
        and len(value) <= 10
        and value.isascii()
        and value.isdigit()
    ):
        try:
            parsed = int(value)
        except ValueError as error:
            raise _field_problem(
                path,
                _("Enter a positive integer."),
            ) from error
        if str(parsed) != value:
            raise _field_problem(path, _("Enter a positive integer."))
    else:
        raise _field_problem(path, _("Enter a positive integer."))
    if parsed < 1 or parsed > maximum:
        raise _field_problem(path, _("Enter a positive integer."))
    return parsed


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
