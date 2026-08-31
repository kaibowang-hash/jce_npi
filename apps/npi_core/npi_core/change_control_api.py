from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.change_control.request_validation import (
    parse_formal_observation,
    parse_predecessor,
    parse_revision_content,
)
from npi_core.change_control.response_validation import (
    validate_change_command_response,
    validate_change_detail_response,
    validate_change_list_response,
)
from npi_core.foundation.errors import NpiProblem, PermissionDenied
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    response_request_id,
)


_CREATE_FIELDS = frozenset({"content"})
_REVISE_FIELDS = frozenset({"predecessor", "content"})
_OBSERVATION_FIELDS = frozenset({"predecessor", "formalChange"})
_CLOSE_FIELDS = frozenset({"predecessor"})


class ChangeControlRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "ENGINEERING_CHANGE_ROUTES_DISABLED",
            _("Engineering change control is temporarily unavailable."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


class EngineeringChangeUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(404, "ENGINEERING_CHANGE_UNAVAILABLE", _("The engineering change is unavailable for this Project."))


class _Repository(Protocol):
    def list_changes(self, project_id: UUID): ...
    def get_change(self, project_id: UUID, change_id: UUID): ...
    def create_change(self, project_id: UUID, **values: Any): ...
    def revise_change(self, project_id: UUID, change_id: UUID, **values: Any): ...
    def link_formal_observation(self, project_id: UUID, change_id: UUID, **values: Any): ...
    def close_change(self, project_id: UUID, change_id: UUID, **values: Any): ...


def _repository_factory(*, principal: Principal, request_id: str, trace_id: str) -> _Repository:
    from npi_core.change_control.frappe_repository import FrappeChangeControlRepository

    return FrappeChangeControlRepository(principal=principal, request_id=request_id, trace_id=trace_id)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_engineering_changes(**request_fields: Any) -> dict[str, Any] | None:
    project_id = _route_uuid("project_id")
    return _query(
        request_fields=request_fields,
        invoke=lambda repository: repository.list_changes(project_id),
        validate=lambda response: validate_change_list_response(response, project_global_id=str(project_id)),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_engineering_change(**request_fields: Any) -> dict[str, Any] | None:
    project_id = _route_uuid("project_id")
    change_id = _route_uuid("change_id")
    return _query(
        request_fields=request_fields,
        invoke=lambda repository: repository.get_change(project_id, change_id),
        validate=lambda response: validate_change_detail_response(
            response,
            project_global_id=str(project_id),
            change_global_id=str(change_id),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_engineering_change(content: Any = None, **request_fields: Any) -> dict[str, Any] | None:
    project_id = _route_uuid("project_id")
    return _command(
        operation="engineering_change.create",
        allowed_fields=_CREATE_FIELDS,
        request_fields=request_fields,
        success_status=201,
        project_id=project_id,
        change_id=None,
        invoke=lambda repository, key_hash: repository.create_change(
            project_id,
            idempotency_key_hash=key_hash,
            content=parse_revision_content(content),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def revise_engineering_change(predecessor: Any = None, content: Any = None, **request_fields: Any) -> dict[str, Any] | None:
    project_id = _route_uuid("project_id")
    change_id = _route_uuid("change_id")
    return _command(
        operation="engineering_change.revise",
        allowed_fields=_REVISE_FIELDS,
        request_fields=request_fields,
        success_status=200,
        project_id=project_id,
        change_id=change_id,
        invoke=lambda repository, key_hash: repository.revise_change(
            project_id,
            change_id,
            idempotency_key_hash=key_hash,
            content=parse_revision_content(content),
            **parse_predecessor(predecessor),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def link_engineering_change_formal_observation(predecessor: Any = None, formalChange: Any = None, **request_fields: Any) -> dict[str, Any] | None:
    project_id = _route_uuid("project_id")
    change_id = _route_uuid("change_id")
    return _command(
        operation="engineering_change.link_formal_observation",
        allowed_fields=_OBSERVATION_FIELDS,
        request_fields=request_fields,
        success_status=200,
        project_id=project_id,
        change_id=change_id,
        require_system_manager=True,
        invoke=lambda repository, key_hash: repository.link_formal_observation(
            project_id,
            change_id,
            idempotency_key_hash=key_hash,
            formal_change=parse_formal_observation(formalChange),
            **parse_predecessor(predecessor),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def close_engineering_change(predecessor: Any = None, **request_fields: Any) -> dict[str, Any] | None:
    project_id = _route_uuid("project_id")
    change_id = _route_uuid("change_id")
    return _command(
        operation="engineering_change.close",
        allowed_fields=_CLOSE_FIELDS,
        request_fields=request_fields,
        success_status=200,
        project_id=project_id,
        change_id=change_id,
        invoke=lambda repository, key_hash: repository.close_change(
            project_id,
            change_id,
            idempotency_key_hash=key_hash,
            **parse_predecessor(predecessor),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def engineering_change_routes_disabled(**_request_fields: Any) -> dict[str, Any] | None:
    return frappe_domain_call(
        lambda: (_ for _ in ()).throw(ChangeControlRoutesDisabled()),
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


def _query(*, request_fields: dict[str, Any], invoke, validate: Callable[[object], dict[str, Any]]) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        principal = _principal()
        reject_unexpected_request_fields(frozenset(), request_fields)
        request_id, repository = _new_repository(principal)
        response = invoke(repository)
        if response is None:
            raise EngineeringChangeUnavailable()
        headers["X-Request-ID"] = request_id
        return validate(response)

    return frappe_domain_call(handle, cache_control="private, no-store", response_headers=headers)


def _command(
    *,
    operation: str,
    allowed_fields: frozenset[str],
    request_fields: dict[str, Any],
    success_status: int,
    project_id: UUID,
    change_id: UUID | None,
    invoke,
    require_system_manager: bool = False,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id(), "Idempotency-Replayed": "false"}

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        _require_api_user(principal)
        if require_system_manager and "System Manager" not in principal.roles:
            raise PermissionDenied()
        reject_unexpected_request_fields(allowed_fields, request_fields)
        require_request_fields(allowed_fields, request_fields)
        request_id, repository = _new_repository(principal)
        outcome = invoke(repository, actor_idempotency_key_hash(actor, frappe.get_request_header("Idempotency-Key")))
        if outcome is None:
            raise EngineeringChangeUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The engineering change command response is invalid.")
        response = validate_change_command_response(
            operation,
            outcome.response,
            project_global_id=str(project_id),
            change_global_id=None if change_id is None else str(change_id),
        )
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=success_status,
        response_headers=headers,
    )


def _principal() -> Principal:
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    _require_api_user(principal)
    return principal


def _new_repository(principal: Principal) -> tuple[str, _Repository]:
    request_id = str(_uuid(frappe.get_request_header("X-Request-ID")))
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The engineering change request has no active trace identity.")
    return request_id, _repository_factory(principal=principal, request_id=request_id, trace_id=trace_id)


def _routes_are_disabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    value = configuration.get("npi_p9_01_routes_disabled") if hasattr(configuration, "get") else None
    return value is not False


def _require_routes_enabled() -> None:
    if _routes_are_disabled():
        raise ChangeControlRoutesDisabled()


def _require_api_user(principal: Principal) -> None:
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()


def _route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    return _uuid(value)


def _uuid(value: object) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise EngineeringChangeUnavailable() from error
    if str(parsed) != str(value).casefold() or parsed.int == 0:
        raise EngineeringChangeUnavailable()
    return parsed
