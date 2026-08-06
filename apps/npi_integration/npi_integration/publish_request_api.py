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
    require_publish_request_routes_enabled,
    require_request_fields,
    response_request_id,
)
from npi_integration.publish_request.domain import PublishRequestUnavailable


_HASH = re.compile(r"^[a-f0-9]{64}$")
_CREATE_FIELDS = frozenset(
    {
        "expectedEbomVersion",
        "expectedRevisionSnapshotHash",
        "expectedLifecycleVersion",
        "publishPolicyGlobalId",
        "publishPolicyVersion",
        "publishPolicySnapshotHash",
        "targetMode",
        "confirmed",
        "confirmationIntent",
        "reason",
    }
)


class _Outcome(Protocol):
    response: dict[str, Any]
    replayed: bool


class _Repository(Protocol):
    def authorize_scope(self, project_id: UUID, **values: Any) -> bool: ...
    def list_requests(
        self,
        project_id: UUID,
        ebom_id: UUID,
        revision_id: UUID,
    ) -> dict[str, Any] | None: ...
    def request_detail(
        self,
        project_id: UUID,
        ebom_id: UUID,
        revision_id: UUID,
        publish_request_id: UUID,
    ) -> dict[str, Any] | None: ...
    def create_request(
        self,
        project_id: UUID,
        ebom_id: UUID,
        revision_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...


def _repository_factory(
    *, principal: Principal, request_id: str, trace_id: str
) -> _Repository:
    from npi_integration.publish_request.frappe_repository import (
        FrappePublishRequestRepository,
    )

    return FrappePublishRequestRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_publish_requests(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(request_fields)
        ebom_id = _opaque_route_uuid("ebom_id")
        revision_id = _opaque_route_uuid("revision_id")
        response = repository.list_requests(project_id, ebom_id, revision_id)
        if response is None:
            raise PublishRequestUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_publish_request(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(request_fields)
        response = repository.request_detail(
            project_id,
            _opaque_route_uuid("ebom_id"),
            _opaque_route_uuid("revision_id"),
            _opaque_route_uuid("publish_request_id"),
        )
        if response is None:
            raise PublishRequestUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_publish_request(
    expectedEbomVersion: Any = None,
    expectedRevisionSnapshotHash: Any = None,
    expectedLifecycleVersion: Any = None,
    publishPolicyGlobalId: Any = None,
    publishPolicyVersion: Any = None,
    publishPolicySnapshotHash: Any = None,
    targetMode: Any = None,
    confirmed: Any = None,
    confirmationIntent: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        request_id, key_hash, repository, project_id = _command_context(
            request_fields
        )
        values = {
            "expected_ebom_version": _positive(
                expectedEbomVersion, "expectedEbomVersion"
            ),
            "expected_revision_snapshot_hash": _hash(
                expectedRevisionSnapshotHash,
                "expectedRevisionSnapshotHash",
            ),
            "expected_lifecycle_version": _positive(
                expectedLifecycleVersion,
                "expectedLifecycleVersion",
            ),
            "publish_policy_global_id": _uuid(
                publishPolicyGlobalId,
                "publishPolicyGlobalId",
            ),
            "publish_policy_version": _positive(
                publishPolicyVersion,
                "publishPolicyVersion",
            ),
            "publish_policy_snapshot_hash": _hash(
                publishPolicySnapshotHash,
                "publishPolicySnapshotHash",
            ),
            "reason": _text(reason, "reason", 280),
        }
        _exact(targetMode, "targetMode", "mock")
        if confirmed is not True:
            raise _field(
                "confirmed",
                _("Confirm validation of the exact released EBOM."),
            )
        _exact(
            confirmationIntent,
            "confirmationIntent",
            "validate_exact_released_ebom_for_item_mbom_publish",
        )
        outcome = repository.create_request(
            project_id,
            _opaque_route_uuid("ebom_id"),
            _opaque_route_uuid("revision_id"),
            idempotency_key_hash=key_hash,
            **values,
        )
        if outcome is None:
            raise PublishRequestUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The publish command replay result is invalid.")
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return _response(outcome.response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _query_context(
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID]:
    require_publish_request_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    repository = _new_repository(principal, response_request_id())
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise PublishRequestUnavailable()
    reject_unexpected_request_fields(frozenset(), request_fields)
    return _request_id(), repository, project_id


def _command_context(
    request_fields: dict[str, Any],
) -> tuple[str, str, _Repository, UUID]:
    require_publish_request_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()
    repository = _new_repository(principal, response_request_id())
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise PublishRequestUnavailable()
    reject_unexpected_request_fields(_CREATE_FIELDS, request_fields)
    require_request_fields(_CREATE_FIELDS, request_fields)
    return (
        _request_id(),
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
    )


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The publish request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _response(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The publish response is invalid.")
    return value


def _opaque_route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise PublishRequestUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise PublishRequestUnavailable()
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


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise _field(path, _("Enter a positive whole number."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field(path, _("Enter a lowercase SHA-256 value."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > maximum
    ):
        raise _field(path, _("Enter a bounded text value."))
    return value


def _exact(value: object, path: str, expected: str) -> str:
    if value != expected:
        raise _field(path, _("Select the required confirmation intent."))
    return expected


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
