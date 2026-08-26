from __future__ import annotations

import re
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
        return _response(response)

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
        return _response(response)

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
        require_csrf_token()
        request_id, repository, project_id, actor = _context(
            request_fields,
            allowed_fields=_LINK_FIELDS,
        )
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
        if acknowledgement != _ACKNOWLEDGEMENT:
            raise _field(
                "acknowledgement",
                _("Confirm the exact observed quality-link boundary."),
            )
        try:
            source_kind = QualitySourceKind(str(sourceKind))
        except (TypeError, ValueError) as error:
            raise _field("sourceKind", _("Select a supported value.")) from error
        outcome = repository.link_observed_formal_quality_reference(
            project_id,
            source_kind=source_kind,
            source_global_id=_uuid(sourceGlobalId, "sourceGlobalId"),
            expected_source_version=_positive(
                expectedSourceVersion,
                "expectedSourceVersion",
            ),
            expected_source_snapshot_hash=_sha256(
                expectedSourceSnapshotHash,
                "expectedSourceSnapshotHash",
            ),
            observation_global_id=_uuid(
                formalObservationGlobalId,
                "formalObservationGlobalId",
            ),
            expected_projection_head_global_id=_uuid(
                expectedProjectionHeadGlobalId,
                "expectedProjectionHeadGlobalId",
            ),
            expected_projection_head_version=_positive(
                expectedProjectionHeadVersion,
                "expectedProjectionHeadVersion",
            ),
            expected_projection_head_hash=_sha256(
                expectedProjectionHeadHash,
                "expectedProjectionHeadHash",
            ),
            expected_link_head_version=_nonnegative(
                expectedLinkHeadVersion,
                "expectedLinkHeadVersion",
            ),
            idempotency_key_hash=actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
        )
        if outcome is None or type(outcome.replayed) is not bool:
            raise FormalQualityLinkUnavailable()
        if not isinstance(outcome.response, dict):
            raise RuntimeError("The formal quality link command result is invalid.")
        try:
            frappe.db.commit()
        except Exception:
            try:
                frappe.db.rollback()
            except Exception:
                pass
            raise
        replayed = outcome.replayed
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(replayed).lower()
        return _response(outcome.response)

    result = frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )
    if replayed and frappe.local.response.http_status_code == 201:
        frappe.local.response.http_status_code = 200
    return result


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


__all__ = [
    "get_formal_quality_link",
    "get_formal_quality_links",
    "link_observed_formal_quality_reference",
]
