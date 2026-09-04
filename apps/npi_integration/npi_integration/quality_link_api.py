from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Protocol
from typing import Iterator
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
    response_request_id,
)
from npi_integration.quality_link.domain import QualitySourceKind
from npi_integration.quality_link.problems import FormalQualityLinkUnavailable


_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_LINK_FIELDS = frozenset(
    {
        "sourceKind",
        "sourceGlobalId",
        "expectedSourceVersion",
        "expectedSourceSnapshotHash",
        "formalObservationGlobalId",
        "expectedProjectionHeadGlobalId",
        "expectedProjectionHeadVersion",
        "expectedProjectionHeadHash",
        "expectedLinkHeadVersion",
        "acknowledgement",
    }
)
_ACKNOWLEDGEMENT = (
    "I confirm this links only the exact observed formal quality reference. "
    "It does not write ERPNext or interpret a formal pass."
)
_RECONCILIATION_REASONS = {
    "current": {"linked_truth_current"},
    "drifted": {
        "linked_source_advanced",
        "linked_projection_advanced",
        "linked_source_and_projection_advanced",
    },
    "unavailable": {"current_truth_unavailable"},
}
QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_HEADER = (
    "X-NPI-P806-Quality-Create-Diagnostic"
)
QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_SCOPE = (
    "p8-06-quality-link-create-response-v1"
)
_CREATE_RESPONSE_DIAGNOSTIC_ACTIVE: ContextVar[bool] = ContextVar(
    "p806_quality_link_create_response_api_diagnostic",
    default=False,
)


@contextmanager
def quality_link_create_response_diagnostics(
    trace_id: str | None,
    *,
    active: bool,
) -> Iterator[None]:
    token = _CREATE_RESPONSE_DIAGNOSTIC_ACTIVE.set(active)
    try:
        if active:
            from npi_integration.quality_link.frappe_repository import (
                quality_link_create_response_diagnostics as server_scope,
            )

            with server_scope(trace_id, active=True):
                yield
        else:
            yield
    finally:
        _CREATE_RESPONSE_DIAGNOSTIC_ACTIVE.reset(token)


@contextmanager
def quality_link_create_response_step(code: str) -> Iterator[None]:
    if _CREATE_RESPONSE_DIAGNOSTIC_ACTIVE.get():
        from npi_integration.quality_link.frappe_repository import (
            quality_link_create_response_step as server_step,
        )

        with server_step(code):
            yield
        return
    yield


class _Outcome(Protocol):
    response: dict[str, Any]
    replayed: bool


class _Repository(Protocol):
    def authorize_scope(
        self,
        project_id: UUID,
        *,
        administer: bool = False,
    ) -> bool: ...

    def list_quality_links(self, project_id: UUID) -> dict[str, Any] | None: ...

    def quality_link_detail(
        self,
        project_id: UUID,
        link_head_id: UUID,
    ) -> dict[str, Any] | None: ...

    def link_observed_formal_quality_reference(
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
    from npi_integration.quality_link.frappe_repository import (
        FrappeFormalQualityLinkRepository,
    )

    return FrappeFormalQualityLinkRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_formal_quality_links(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(request_fields)
        response = repository.list_quality_links(project_id)
        if response is None:
            raise FormalQualityLinkUnavailable()
        headers["X-Request-ID"] = request_id
        return _query_response(
            response,
            project_id=project_id,
            collection=True,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_formal_quality_link(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(request_fields)
        response = repository.quality_link_detail(
            project_id,
            _opaque_route_uuid("formal_quality_link_id"),
        )
        if response is None:
            raise FormalQualityLinkUnavailable()
        headers["X-Request-ID"] = request_id
        return _query_response(
            response,
            project_id=project_id,
            collection=False,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def link_observed_formal_quality_reference(
    sourceKind: Any = None,
    sourceGlobalId: Any = None,
    expectedSourceVersion: Any = None,
    expectedSourceSnapshotHash: Any = None,
    formalObservationGlobalId: Any = None,
    expectedProjectionHeadGlobalId: Any = None,
    expectedProjectionHeadVersion: Any = None,
    expectedProjectionHeadHash: Any = None,
    expectedLinkHeadVersion: Any = None,
    acknowledgement: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }
    replayed = False

    def handle() -> dict[str, Any]:
        nonlocal replayed
        with quality_link_create_response_step("P806_QUALITY_CREATE_API_CSRF"):
            require_csrf_token()
        with quality_link_create_response_step("P806_QUALITY_CREATE_API_CONTEXT"):
            request_id, repository, project_id, actor = _context(
                request_fields,
                allowed_fields=_LINK_FIELDS,
            )
        with quality_link_create_response_step(
            "P806_QUALITY_CREATE_API_REQUEST_FIELDS"
        ):
            command_fields = {
                **request_fields,
                "sourceKind": sourceKind,
                "sourceGlobalId": sourceGlobalId,
                "expectedSourceVersion": expectedSourceVersion,
                "expectedSourceSnapshotHash": expectedSourceSnapshotHash,
                "formalObservationGlobalId": formalObservationGlobalId,
                "expectedProjectionHeadGlobalId": expectedProjectionHeadGlobalId,
                "expectedProjectionHeadVersion": expectedProjectionHeadVersion,
                "expectedProjectionHeadHash": expectedProjectionHeadHash,
                "expectedLinkHeadVersion": expectedLinkHeadVersion,
                "acknowledgement": acknowledgement,
            }
            reject_unexpected_request_fields(_LINK_FIELDS, command_fields)
            require_request_fields(_LINK_FIELDS, command_fields)
        with quality_link_create_response_step(
            "P806_QUALITY_CREATE_API_ACKNOWLEDGEMENT"
        ):
            if acknowledgement != _ACKNOWLEDGEMENT:
                raise _field(
                    "acknowledgement",
                    _("Confirm the exact observed quality-link boundary."),
                )
        with quality_link_create_response_step(
            "P806_QUALITY_CREATE_API_SOURCE_KIND"
        ):
            try:
                source_kind = QualitySourceKind(str(sourceKind))
            except (TypeError, ValueError) as error:
                raise _field("sourceKind", _("Select a supported value.")) from error
        with quality_link_create_response_step("P806_QUALITY_CREATE_API_INPUT_PARSE"):
            values = {
                "source_kind": source_kind,
                "source_global_id": _uuid(sourceGlobalId, "sourceGlobalId"),
                "expected_source_version": _positive(
                    expectedSourceVersion,
                    "expectedSourceVersion",
                ),
                "expected_source_snapshot_hash": _sha256(
                    expectedSourceSnapshotHash,
                    "expectedSourceSnapshotHash",
                ),
                "observation_global_id": _uuid(
                    formalObservationGlobalId,
                    "formalObservationGlobalId",
                ),
                "expected_projection_head_global_id": _uuid(
                    expectedProjectionHeadGlobalId,
                    "expectedProjectionHeadGlobalId",
                ),
                "expected_projection_head_version": _positive(
                    expectedProjectionHeadVersion,
                    "expectedProjectionHeadVersion",
                ),
                "expected_projection_head_hash": _sha256(
                    expectedProjectionHeadHash,
                    "expectedProjectionHeadHash",
                ),
                "expected_link_head_version": _nonnegative(
                    expectedLinkHeadVersion,
                    "expectedLinkHeadVersion",
                ),
                "idempotency_key_hash": actor_idempotency_key_hash(
                    actor,
                    frappe.get_request_header("Idempotency-Key"),
                ),
            }
        with quality_link_create_response_step(
            "P806_QUALITY_CREATE_API_REPOSITORY_COMMAND"
        ):
            outcome = repository.link_observed_formal_quality_reference(
                project_id,
                **values,
            )
        with quality_link_create_response_step("P806_QUALITY_CREATE_API_OUTCOME"):
            if outcome is None or type(outcome.replayed) is not bool:
                raise FormalQualityLinkUnavailable()
            if not isinstance(outcome.response, dict):
                raise RuntimeError("The formal quality link command result is invalid.")
        with quality_link_create_response_step("P806_QUALITY_CREATE_API_COMMIT"):
            try:
                frappe.db.commit()
            except Exception:
                try:
                    frappe.db.rollback()
                except Exception:
                    pass
                raise
        with quality_link_create_response_step("P806_QUALITY_CREATE_API_RESPONSE"):
            replayed = outcome.replayed
            headers["X-Request-ID"] = request_id
            headers["Idempotency-Replayed"] = str(replayed).lower()
            return _response(outcome.response)

    trace_id = frappe.get_request_header("X-Trace-ID")
    with quality_link_create_response_diagnostics(
        trace_id,
        active=_quality_link_create_response_diagnostic_active(trace_id),
    ):
        result = frappe_domain_call(
            handle,
            cache_control="private, no-store",
            success_status=201,
            response_headers=headers,
        )
    if replayed and frappe.local.response.http_status_code == 201:
        frappe.local.response.http_status_code = 200
    return result


def _quality_link_create_response_diagnostic_active(trace_id: object) -> bool:
    try:
        request = getattr(getattr(frappe, "local", None), "request", None)
        arguments = getattr(request, "args", None)
        route = getattr(frappe.flags, "npi_route_params", None)
        form = getattr(getattr(frappe, "local", None), "form_dict", None)
        return (
            frappe.get_request_header(
                QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_HEADER
            )
            == QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_SCOPE
            and frappe.get_request_header("X-Trace-ID") == trace_id
            and isinstance(trace_id, str)
            and re.fullmatch(r"trace-[a-f0-9]{32}", trace_id) is not None
            and getattr(request, "method", None) == "POST"
            and arguments is not None
            and list(arguments.keys()) == []
            and isinstance(route, dict)
            and set(route) == {"project_id"}
            and isinstance(form, dict)
            and set(form) == _LINK_FIELDS | {"cmd"}
            and form.get("cmd")
            == "npi_integration.quality_link_api.link_observed_formal_quality_reference"
        )
    except Exception:
        return False


def _query_context(
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID]:
    request_id, repository, project_id, _actor = _context(
        request_fields,
        allowed_fields=frozenset(),
    )
    reject_unexpected_request_fields(frozenset(), request_fields)
    return request_id, repository, project_id


def _context(
    request_fields: dict[str, Any],
    *,
    allowed_fields: frozenset[str],
) -> tuple[str, _Repository, UUID, str]:
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    if principal.is_external:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise FormalQualityLinkUnavailable()
    reject_unexpected_request_fields(allowed_fields, request_fields)
    return request_id, repository, project_id, actor


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The formal quality link request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _request_id() -> str:
    value = response_request_id()
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as error:
        raise RequestValidationFailed(
            {"X-Request-ID": _("Enter a valid request identifier.")}
        ) from error


def _opaque_route_uuid(name: str) -> UUID:
    raw = getattr(frappe.flags, "npi_route_params", {}).get(name)
    try:
        return UUID(str(raw))
    except (TypeError, ValueError) as error:
        raise FormalQualityLinkUnavailable() from error


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as error:
        raise _field(field, _("Enter a valid global identifier.")) from error


def _positive(value: Any, field: str) -> int:
    if type(value) is not int or value < 1:
        raise _field(field, _("Enter a positive whole number."))
    return value


def _nonnegative(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise _field(field, _("Enter zero or a positive whole number."))
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise _field(field, _("Enter a valid SHA-256 value."))
    return value


def _field(field: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed({field: message})


def _response(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The formal quality link response is invalid.")
    return value


def _query_response(
    value: object,
    *,
    project_id: UUID,
    collection: bool,
) -> dict[str, Any]:
    response = _response(value)
    expected_fields = {
        "projectGlobalId",
        "permissions",
        "items" if collection else "link",
    }
    if set(response) != expected_fields:
        raise RuntimeError("The formal quality link query response shape is invalid.")
    if str(response["projectGlobalId"]) != str(project_id):
        raise RuntimeError("The formal quality link query escaped its Project.")
    permissions = response["permissions"]
    if (
        not isinstance(permissions, dict)
        or set(permissions) != {"view", "link"}
        or permissions["view"] is not True
        or type(permissions["link"]) is not bool
    ):
        raise RuntimeError("The formal quality link query permissions are invalid.")
    if collection:
        items = response["items"]
        if not isinstance(items, list) or len(items) > 1_000:
            raise RuntimeError("The formal quality link collection is invalid.")
    else:
        items = [response["link"]]
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("The formal quality link item is invalid.")
        reconciliation = item.get("reconciliation")
        if not isinstance(reconciliation, dict) or set(reconciliation) != {
            "state",
            "reasonCode",
        }:
            raise RuntimeError("The formal quality link reconciliation is invalid.")
        state = reconciliation["state"]
        if (
            state not in _RECONCILIATION_REASONS
            or reconciliation["reasonCode"] not in _RECONCILIATION_REASONS[state]
        ):
            raise RuntimeError("The formal quality link reconciliation is invalid.")
    return response


__all__ = [
    "get_formal_quality_link",
    "get_formal_quality_links",
    "link_observed_formal_quality_reference",
]
