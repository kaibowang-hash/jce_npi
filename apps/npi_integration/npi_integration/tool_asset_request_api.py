from __future__ import annotations

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
    require_tooling_acceptance_assets_routes_enabled,
    response_request_id,
)
from npi_core.tooling.domain import ToolingUnavailable


_CREATE_FIELDS = frozenset(
    {
        "targetMode",
        "acceptanceRevisionGlobalId",
        "acceptanceVersion",
        "acceptanceSnapshotHash",
        "expectedToolingMasterSnapshotHash",
        "expectedToolingSetSnapshotHash",
        "expectedBindingSnapshotHash",
        "expectedToolingRevisionNumber",
        "expectedToolingRevisionSnapshotHash",
        "acknowledgement",
    }
)
_ACKNOWLEDGEMENT = (
    "I confirm this only validates a local Mock draft. It does not approve "
    "Tooling, contact ERPNext or create an Asset."
)


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

    def acceptance_asset_context(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None: ...

    def list_asset_requests(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
    ) -> dict[str, Any] | None: ...

    def asset_request_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        asset_request_id: UUID,
    ) -> dict[str, Any] | None: ...

    def create_asset_request(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        **values: Any,
    ) -> _Outcome | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from npi_integration.tool_asset_request.frappe_repository import (
        FrappeToolAssetRequestRepository,
    )

    return FrappeToolAssetRequestRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_acceptance_assets(
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _query(
        request_fields,
        lambda repository, project_id, master_id: (
            repository.acceptance_asset_context(project_id, master_id)
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tool_asset_requests(**request_fields: Any) -> dict[str, Any] | None:
    return _query(
        request_fields,
        lambda repository, project_id, master_id: (
            repository.list_asset_requests(project_id, master_id)
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tool_asset_request(**request_fields: Any) -> dict[str, Any] | None:
    return _query(
        request_fields,
        lambda repository, project_id, master_id: repository.asset_request_detail(
            project_id,
            master_id,
            _opaque_route_uuid("asset_request_id"),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tool_asset_request(
    targetMode: Any = None,
    acceptanceRevisionGlobalId: Any = None,
    acceptanceVersion: Any = None,
    acceptanceSnapshotHash: Any = None,
    expectedToolingMasterSnapshotHash: Any = None,
    expectedToolingSetSnapshotHash: Any = None,
    expectedBindingSnapshotHash: Any = None,
    expectedToolingRevisionNumber: Any = None,
    expectedToolingRevisionSnapshotHash: Any = None,
    acknowledgement: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        require_tooling_acceptance_assets_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        if principal.is_external or "System Manager" not in principal.roles:
            raise PermissionDenied()
        request_id = _request_id()
        repository = _new_repository(principal, request_id)
        project_id = _opaque_route_uuid("project_id")
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id, administer=True):
            raise ToolingUnavailable()
        reject_unexpected_request_fields(_CREATE_FIELDS, request_fields)
        require_request_fields(_CREATE_FIELDS, request_fields)
        if targetMode != "mock":
            raise _field("targetMode", _("Select a supported value."))
        if acknowledgement != _ACKNOWLEDGEMENT:
            raise _field(
                "acknowledgement",
                _("Confirm the exact local Mock-only boundary."),
            )
        outcome = repository.create_asset_request(
            project_id,
            master_id,
            _opaque_route_uuid("tooling_set_id"),
            idempotency_key_hash=actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
            acceptance_revision_id=_uuid(
                acceptanceRevisionGlobalId,
                "acceptanceRevisionGlobalId",
            ),
            acceptance_version=_positive(acceptanceVersion, "acceptanceVersion"),
            acceptance_snapshot_hash=_sha256(
                acceptanceSnapshotHash,
                "acceptanceSnapshotHash",
            ),
            expected_master_snapshot_hash=_sha256(
                expectedToolingMasterSnapshotHash,
                "expectedToolingMasterSnapshotHash",
            ),
            expected_set_snapshot_hash=_sha256(
                expectedToolingSetSnapshotHash,
                "expectedToolingSetSnapshotHash",
            ),
            expected_binding_snapshot_hash=_sha256(
                expectedBindingSnapshotHash,
                "expectedBindingSnapshotHash",
            ),
            expected_revision_number=_positive(
                expectedToolingRevisionNumber,
                "expectedToolingRevisionNumber",
            ),
            expected_revision_snapshot_hash=_sha256(
                expectedToolingRevisionSnapshotHash,
                "expectedToolingRevisionSnapshotHash",
            ),
        )
        if outcome is None:
            raise ToolingUnavailable()
        if type(outcome.replayed) is not bool or not isinstance(outcome.response, dict):
            raise RuntimeError("The Tool Asset command result is invalid.")
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return outcome.response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _query(request_fields: dict[str, Any], operation) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_tooling_acceptance_assets_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        request_id = _request_id()
        repository = _new_repository(principal, request_id)
        project_id = _opaque_route_uuid("project_id")
        master_id = _opaque_route_uuid("tooling_master_id")
        if not repository.authorize_scope(project_id, master_id):
            raise ToolingUnavailable()
        reject_unexpected_request_fields(frozenset(), request_fields)
        response = operation(repository, project_id, master_id)
        if response is None or not isinstance(response, dict):
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Tool Asset request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


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


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise _field(path, _("Enter a positive whole number."))
    return value


def _sha256(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise _field(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
