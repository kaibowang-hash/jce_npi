from __future__ import annotations

import re
from datetime import date
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal, authorize_tenant
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import (
    CreateProjectCommand,
    ProjectInstantiationService,
    ProjectReferenceType,
    ProjectType,
    ReferenceSourceSystem,
    TypedReference,
    actor_idempotency_key_hash,
)
from npi_core.project.frappe_repository import FrappeProjectRepository
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    response_request_id,
)


_CREATE_FIELDS = frozenset(
    {
        "tenantId",
        "businessCode",
        "title",
        "projectType",
        "ownerUserId",
        "targetSop",
        "templateGlobalId",
        "templateVersion",
        "expectedVersion",
        "references",
    }
)
_REFERENCE_FIELDS = frozenset(
    {"type", "sourceSystem", "sourceObjectId", "globalId"}
)
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ProjectUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "PROJECT_UNAVAILABLE",
            _("The requested project is unavailable."),
        )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_project(
    tenantId: Any = None,
    businessCode: Any = None,
    title: Any = None,
    projectType: Any = None,
    ownerUserId: Any = None,
    targetSop: Any = None,
    templateGlobalId: Any = None,
    templateVersion: Any = None,
    expectedVersion: Any = None,
    references: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Create one Project draft and all Gate shells as an atomic BFF command."""
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        if not _is_internal_system_manager(principal):
            raise PermissionDenied()
        reject_unexpected_request_fields(_CREATE_FIELDS, request_fields)

        request_id = _request_id()
        raw_idempotency_key = frappe.get_request_header("Idempotency-Key")
        actor_key_hash = actor_idempotency_key_hash(actor, raw_idempotency_key)
        command = CreateProjectCommand(
            idempotency_key=actor_key_hash,
            tenant_id=tenantId,
            business_code=businessCode,
            title=title,
            project_type=_enum_value(ProjectType, projectType, "projectType"),
            owner_user_id=ownerUserId,
            target_sop=_date_value(targetSop, "targetSop"),
            template_global_id=_uuid_value(templateGlobalId, "templateGlobalId"),
            template_version=_positive_integer(templateVersion, "templateVersion"),
            expected_version=_positive_integer(expectedVersion, "expectedVersion"),
            references=_references_value(references),
        )
        authorize_tenant(principal, command.tenant_id)
        trace_id = current_trace_id.get()
        if trace_id is None:
            raise RuntimeError("The Project command has no active trace identity.")
        repository = FrappeProjectRepository(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )
        if repository.get_idempotency_record(command.idempotency_key) is None:
            _require_enabled_owner(command.owner_user_id)
        result = ProjectInstantiationService(repository).instantiate(command)
        cockpit = repository.project_cockpit(result.project.global_id)
        if cockpit is None:
            raise RuntimeError("The created Project could not be reloaded.")
        success_headers["X-Request-ID"] = request_id
        success_headers["Idempotency-Replayed"] = str(result.replayed).lower()
        return cockpit

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_cockpit(**request_fields: Any) -> dict[str, Any] | None:
    """Return an IDOR-safe live Project cockpit for its owner or an administrator."""
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        actor = authenticated_user()
        reject_unexpected_request_fields(frozenset(), request_fields)
        request_id = _request_id()
        project_global_id = _route_project_id()
        principal = authenticated_principal(actor)
        trace_id = current_trace_id.get()
        if trace_id is None:
            raise RuntimeError("The Project query has no active trace identity.")
        repository = FrappeProjectRepository(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )
        cockpit = repository.project_cockpit(project_global_id)
        if cockpit is None:
            raise ProjectUnavailable()
        success_headers["X-Request-ID"] = request_id
        return cockpit

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


def _is_internal_system_manager(principal: Principal) -> bool:
    return not principal.is_external and "System Manager" in principal.roles


def _require_enabled_owner(owner_user_id: str) -> None:
    enabled = frappe.db.get_value("User", owner_user_id, "enabled")
    if enabled != 1:
        raise _field_problem(
            "ownerUserId",
            _("Select an enabled project owner."),
        )


def _request_id() -> str:
    return str(
        _uuid_value(
            frappe.get_request_header("X-Request-ID"),
            "requestId",
        )
    )


def _route_project_id() -> UUID:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    project_id = (
        route_params.get("project_id")
        if hasattr(route_params, "get")
        else None
    )
    return _uuid_value(project_id, "projectId")


def _uuid_value(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise _field_problem(path, _("Enter a valid global ID."))
    if str(parsed) != value.casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _date_value(value: object, path: str) -> date:
    if not isinstance(value, str) or _DATE_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid date."))
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise _field_problem(path, _("Enter a valid date."))
    if parsed.isoformat() != value:
        raise _field_problem(path, _("Enter a valid date."))
    return parsed


def _enum_value(enum_type, value: object, path: str):
    if not isinstance(value, str):
        raise _field_problem(path, _("Select a supported value."))
    try:
        return enum_type(value)
    except ValueError:
        raise _field_problem(path, _("Select a supported value."))


def _references_value(value: object) -> tuple[TypedReference, ...]:
    if not isinstance(value, list) or len(value) > 100:
        raise _field_problem("references", _("Enter valid project references."))
    references: list[TypedReference] = []
    for index, item in enumerate(value):
        path = f"references[{index}]"
        if not isinstance(item, dict):
            raise _field_problem(path, _("Enter a valid project reference."))
        unexpected = sorted(set(item) - _REFERENCE_FIELDS)
        if unexpected:
            raise RequestValidationFailed(
                [
                    {
                        "path": f"{path}.{field}",
                        "message": _("This field is not allowed."),
                    }
                    for field in unexpected
                ]
            )
        missing = sorted(
            {"type", "sourceSystem", "sourceObjectId"} - set(item)
        )
        if missing:
            raise RequestValidationFailed(
                [
                    {
                        "path": f"{path}.{field}",
                        "message": _("This field is required."),
                    }
                    for field in missing
                ]
            )
        global_id = None
        if "globalId" in item:
            global_id = _uuid_value(item["globalId"], f"{path}.globalId")
        references.append(
            TypedReference(
                reference_type=_enum_value(
                    ProjectReferenceType,
                    item["type"],
                    f"{path}.type",
                ),
                source_system=_enum_value(
                    ReferenceSourceSystem,
                    item["sourceSystem"],
                    f"{path}.sourceSystem",
                ),
                source_object_id=item["sourceObjectId"],
                global_id=global_id,
            )
        )
    return tuple(references)


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
