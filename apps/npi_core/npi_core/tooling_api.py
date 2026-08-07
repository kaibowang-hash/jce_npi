from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    require_tooling_routes_enabled,
    response_request_id,
)
from npi_core.tooling.domain import ToolingRequirementKind, ToolingUnavailable
from npi_core.tooling.diagnostics import (
    applicability_create_server_diagnostics,
    applicability_create_server_step,
    part_create_server_diagnostics,
    part_create_server_step,
)


_PART_FIELDS = frozenset({"title", "revisionLabel", "reason"})
_PART_REVISION_FIELDS = frozenset(
    {"expectedVersion", "revisionLabel", "title", "reason"}
)
_REQUIREMENT_FIELDS = frozenset(
    {"kind", "title", "reason", "targetPartRevisionGlobalId", "targetDate"}
)
_REQUIREMENT_REQUIRED = frozenset({"kind", "title", "reason"})
_MASTER_FIELDS = frozenset({"title"})
_APPLICABILITY_FIELDS = frozenset(
    {
        "toolingMasterGlobalId",
        "partRevisionGlobalId",
        "product",
        "model",
        "relationshipGlobalId",
        "expectedVersion",
        "effectiveFrom",
        "effectiveTo",
        "reason",
    }
)
_APPLICABILITY_REQUIRED = frozenset(
    {"toolingMasterGlobalId", "partRevisionGlobalId", "effectiveFrom", "reason"}
)
_REFERENCE_FIELDS = frozenset({"sourceSystem", "sourceObjectId"})
_REFERENCE_SYSTEMS = frozenset({"NPI_ONE", "ERPNEXT"})


class _Outcome(Protocol):
    response: dict[str, Any]
    replayed: bool


class _Repository(Protocol):
    def authorize_scope(
        self,
        project_id: UUID,
        tooling_master_id: UUID | None = None,
        *,
        administer: bool = False,
    ) -> bool: ...

    def cockpit(self, project_id: UUID) -> dict[str, Any] | None: ...
    def master_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None: ...
    def create_part(self, project_id: UUID, **values: Any) -> _Outcome | None: ...
    def create_part_revision(
        self,
        project_id: UUID,
        part_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_requirement(
        self,
        project_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...
    def create_master(self, project_id: UUID, **values: Any) -> _Outcome | None: ...
    def create_applicability(
        self,
        project_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from npi_core.tooling.frappe_repository import FrappeToolingRepository

    return FrappeToolingRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_cockpit(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(
            frozenset(),
            request_fields,
        )
        response = repository.cockpit(project_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_master(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(
            frozenset(),
            request_fields,
        )
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        response = repository.master_detail(project_id, master_id)
        if response is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_engineering_part(
    title: Any = None,
    revisionLabel: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = lambda: {
        "title": _text(title, "title", 140),
        "revision_label": _text(revisionLabel, "revisionLabel", 40),
        "reason": _text(reason, "reason", 500),
    }
    return _command(
        _PART_FIELDS,
        _PART_FIELDS,
        request_fields,
        values,
        lambda repository, project_id, parsed: repository.create_part(
            project_id,
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_engineering_part_revision(
    expectedVersion: Any = None,
    revisionLabel: Any = None,
    title: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = lambda: {
        "expected_version": _positive(expectedVersion, "expectedVersion"),
        "revision_label": _text(revisionLabel, "revisionLabel", 40),
        "title": _text(title, "title", 140),
        "reason": _text(reason, "reason", 500),
    }
    return _command(
        _PART_REVISION_FIELDS,
        _PART_REVISION_FIELDS,
        request_fields,
        values,
        lambda repository, project_id, parsed: repository.create_part_revision(
            project_id,
            _opaque_route_uuid("part_id"),
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_requirement(
    kind: Any = None,
    title: Any = None,
    reason: Any = None,
    targetPartRevisionGlobalId: Any = None,
    targetDate: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = lambda: {
        "kind": _requirement_kind(kind),
        "title": _text(title, "title", 140),
        "reason": _text(reason, "reason", 500),
        "target_part_revision_id": _optional_uuid(
            targetPartRevisionGlobalId,
            "targetPartRevisionGlobalId",
        ),
        "target_date": _optional_date(targetDate, "targetDate"),
    }
    return _command(
        _REQUIREMENT_FIELDS,
        _REQUIREMENT_REQUIRED,
        request_fields,
        values,
        lambda repository, project_id, parsed: repository.create_requirement(
            project_id,
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_master(
    title: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _MASTER_FIELDS,
        _MASTER_FIELDS,
        request_fields,
        lambda: {"title": _text(title, "title", 140)},
        lambda repository, project_id, parsed: repository.create_master(
            project_id,
            **parsed,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_applicability(
    toolingMasterGlobalId: Any = None,
    partRevisionGlobalId: Any = None,
    product: Any = None,
    model: Any = None,
    relationshipGlobalId: Any = None,
    expectedVersion: Any = None,
    effectiveFrom: Any = None,
    effectiveTo: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    def values() -> dict[str, Any]:
        relationship_id = _optional_uuid(
            relationshipGlobalId,
            "relationshipGlobalId",
        )
        expected_version = _optional_positive(expectedVersion, "expectedVersion")
        if (relationship_id is None) != (expected_version is None):
            raise _field(
                "relationshipGlobalId",
                _("Supply the relationship identity and expected version together."),
            )
        return {
            "tooling_master_id": _uuid(
                toolingMasterGlobalId,
                "toolingMasterGlobalId",
            ),
            "part_revision_id": _uuid(
                partRevisionGlobalId,
                "partRevisionGlobalId",
            ),
            "product": _reference(product, "product"),
            "model": _reference(model, "model"),
            "relationship_id": relationship_id,
            "expected_version": expected_version,
            "effective_from": _date(effectiveFrom, "effectiveFrom"),
            "effective_to": _optional_date(effectiveTo, "effectiveTo"),
            "reason": _text(reason, "reason", 500),
        }

    return _command(
        _APPLICABILITY_FIELDS,
        _APPLICABILITY_REQUIRED,
        request_fields,
        values,
        lambda repository, project_id, parsed: repository.create_applicability(
            project_id,
            **parsed,
        ),
        applicability_create_diagnostic=True,
    )


def _query_context(
    allowed: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID]:
    require_tooling_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    return request_id, repository, project_id


def _command_context(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, str, _Repository, UUID]:
    require_tooling_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id, administer=True):
        raise ToolingUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    require_request_fields(required, request_fields)
    return (
        request_id,
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
    )


def _command(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    values,
    operation,
    *,
    applicability_create_diagnostic: bool = False,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        with part_create_server_diagnostics(
            current_trace_id.get()
        ), applicability_create_server_diagnostics(
            current_trace_id.get(),
            route_enabled=applicability_create_diagnostic,
        ):
            with part_create_server_step(
                "P601_PART_CREATE_COMMAND_CONTEXT"
            ), applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_COMMAND_CONTEXT"
            ):
                request_id, key_hash, repository, project_id = _command_context(
                    allowed,
                    required,
                    request_fields,
                )
            with part_create_server_step(
                "P601_PART_CREATE_INPUT_PARSE"
            ), applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_INPUT_PARSE"
            ):
                parsed = values()
            parsed["idempotency_key_hash"] = key_hash
            with part_create_server_step(
                "P601_PART_CREATE_API_RESPONSE"
            ), applicability_create_server_step(
                "P601_APPLICABILITY_CREATE_API_RESPONSE"
            ):
                outcome = operation(repository, project_id, parsed)
                if outcome is None:
                    raise ToolingUnavailable()
                if type(outcome.replayed) is not bool:
                    raise RuntimeError("The Tooling command replay result is invalid.")
                headers["X-Request-ID"] = request_id
                headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
                return _response(outcome.response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Tooling request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _response(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The Tooling response is invalid.")
    return value


def _opaque_route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ToolingUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise ToolingUnavailable()
    return parsed


def _request_id() -> str:
    return str(_uuid(frappe.get_request_header("X-Request-ID"), "requestId"))


def _uuid(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field(path, _("Enter a canonical global ID."))
    return parsed


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else _uuid(value, path)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise _field(path, _("Enter a positive whole number."))
    return value


def _optional_positive(value: object, path: str) -> int | None:
    return None if value in (None, "") else _positive(value, path)


def _text(value: object, path: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > maximum
    ):
        raise _field(path, _("Enter a bounded text value."))
    return value


def _requirement_kind(value: object) -> ToolingRequirementKind:
    try:
        return ToolingRequirementKind(str(value))
    except ValueError as error:
        raise _field("kind", _("Select a supported value.")) from error


def _date(value: object, path: str) -> date:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid effectivity date."))
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise _field(path, _("Enter a valid effectivity date.")) from error
    if parsed.isoformat() != value:
        raise _field(path, _("Enter a canonical effectivity date."))
    return parsed


def _optional_date(value: object, path: str) -> date | None:
    return None if value in (None, "") else _date(value, path)


def _reference(value: object, path: str) -> dict[str, str] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, Mapping) or set(value) != _REFERENCE_FIELDS:
        raise _field(path, _("Select a supported value."))
    source_system = value.get("sourceSystem")
    if source_system not in _REFERENCE_SYSTEMS:
        raise _field(f"{path}.sourceSystem", _("Select a supported value."))
    return {
        "sourceSystem": str(source_system),
        "sourceObjectId": _text(
            value.get("sourceObjectId"),
            f"{path}.sourceObjectId",
            128,
        ),
    }


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
