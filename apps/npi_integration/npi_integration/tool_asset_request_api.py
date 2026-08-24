from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call, record_safe_diagnostic
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
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
from npi_integration.tool_asset_request.diagnostics import (
    p606_asset_create_diagnostics,
    p606_asset_create_step,
)
from npi_integration.tool_asset_request.problems import ToolAssetExecutionUnavailable


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
_PROFILE_RESOLVER_HOOK = "npi_tool_asset_execution_profile_resolver"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_EXECUTION_FIELDS = frozenset(
    {
        "acceptanceRevisionGlobalId",
        "expectedSourceHash",
        "expectedApprovalHash",
        "expectedMappingExpectationHash",
        "expectedProfileSnapshotHash",
        "acknowledgement",
    }
)
_CREATE_EXECUTION_ACKNOWLEDGEMENT = (
    "I confirm this request may create one formal ERP Asset only from the exact "
    "physical Tooling Set, separate business approval, mapping state, and execution profile."
)
_UPDATE_EXECUTION_ACKNOWLEDGEMENT = (
    "I confirm this request may update only the exact mapped ERP Asset from the "
    "physical Tooling Set, separate business approval, mapping state, and execution profile."
)


class _Outcome(Protocol):
    response: dict[str, Any]
    replayed: bool


class _ExecutionOutcome(Protocol):
    response: dict[str, Any] | None
    replayed: bool
    should_enqueue: bool
    outbox_event_id: UUID | None
    problem: NpiProblem | None


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

    def list_execution_requests(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        *,
        acceptance_revision_id: UUID | None = None,
    ) -> dict[str, Any] | None: ...

    def execution_request_detail(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        request_global_id: UUID,
    ) -> dict[str, Any] | None: ...

    def create_tool_asset_execution_request(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        **values: Any,
    ) -> _ExecutionOutcome | None: ...

    def update_tool_asset_execution_request(
        self,
        project_id: UUID,
        tooling_master_id: UUID,
        tooling_set_id: UUID,
        **values: Any,
    ) -> _ExecutionOutcome | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
    execution_profile_resolver: Callable[[str, UUID], object | None] | None,
) -> _Repository:
    from npi_integration.tool_asset_request.frappe_repository import (
        FrappeToolAssetRequestRepository,
    )

    return FrappeToolAssetRequestRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        execution_profile_resolver=execution_profile_resolver,
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
        with p606_asset_create_diagnostics(current_trace_id.get()):
            with p606_asset_create_step("P805_P606_ASSET_COMMAND_CONTEXT"):
                require_tooling_acceptance_assets_routes_enabled()
                actor = authenticated_user()
                require_csrf_token()
                principal = authenticated_principal(actor)
                if principal.is_external or "System Manager" not in principal.roles:
                    raise PermissionDenied()
            with p606_asset_create_step("P805_P606_ASSET_REPOSITORY_INIT"):
                request_id = _request_id()
                repository = _new_repository(principal, request_id)
                project_id = _opaque_route_uuid("project_id")
                master_id = _opaque_route_uuid("tooling_master_id")
                if not repository.authorize_scope(
                    project_id, master_id, administer=True
                ):
                    raise ToolingUnavailable()
            with p606_asset_create_step("P805_P606_ASSET_INPUT_PARSE"):
                reject_unexpected_request_fields(_CREATE_FIELDS, request_fields)
                require_request_fields(_CREATE_FIELDS, request_fields)
                if targetMode != "mock":
                    raise _field("targetMode", _("Select a supported value."))
                if acknowledgement != _ACKNOWLEDGEMENT:
                    raise _field(
                        "acknowledgement",
                        _("Confirm the exact local Mock-only boundary."),
                    )
                tooling_set_id = _opaque_route_uuid("tooling_set_id")
                values = {
                    "idempotency_key_hash": actor_idempotency_key_hash(
                        actor,
                        frappe.get_request_header("Idempotency-Key"),
                    ),
                    "acceptance_revision_id": _uuid(
                        acceptanceRevisionGlobalId,
                        "acceptanceRevisionGlobalId",
                    ),
                    "acceptance_version": _positive(
                        acceptanceVersion, "acceptanceVersion"
                    ),
                    "acceptance_snapshot_hash": _sha256(
                        acceptanceSnapshotHash,
                        "acceptanceSnapshotHash",
                    ),
                    "expected_master_snapshot_hash": _sha256(
                        expectedToolingMasterSnapshotHash,
                        "expectedToolingMasterSnapshotHash",
                    ),
                    "expected_set_snapshot_hash": _sha256(
                        expectedToolingSetSnapshotHash,
                        "expectedToolingSetSnapshotHash",
                    ),
                    "expected_binding_snapshot_hash": _sha256(
                        expectedBindingSnapshotHash,
                        "expectedBindingSnapshotHash",
                    ),
                    "expected_revision_number": _positive(
                        expectedToolingRevisionNumber,
                        "expectedToolingRevisionNumber",
                    ),
                    "expected_revision_snapshot_hash": _sha256(
                        expectedToolingRevisionSnapshotHash,
                        "expectedToolingRevisionSnapshotHash",
                    ),
                }
            outcome = repository.create_asset_request(
                project_id,
                master_id,
                tooling_set_id,
                **values,
            )
            with p606_asset_create_step("P805_P606_ASSET_OUTCOME_VALIDATE"):
                if outcome is None:
                    raise ToolingUnavailable()
                if type(outcome.replayed) is not bool or not isinstance(
                    outcome.response, dict
                ):
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


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tool_asset_execution_requests(
    acceptanceRevisionGlobalId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id, master_id, tooling_set_id = (
            _execution_query_context(request_fields)
        )
        response = repository.list_execution_requests(
            project_id,
            master_id,
            tooling_set_id,
            acceptance_revision_id=(
                _uuid(
                    acceptanceRevisionGlobalId,
                    "acceptanceRevisionGlobalId",
                )
                if acceptanceRevisionGlobalId is not None
                else None
            ),
        )
        if response is None:
            raise ToolAssetExecutionUnavailable()
        headers["X-Request-ID"] = request_id
        return _execution_response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tool_asset_execution_request(
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id, master_id, tooling_set_id = (
            _execution_query_context(request_fields)
        )
        response = repository.execution_request_detail(
            project_id,
            master_id,
            tooling_set_id,
            _opaque_route_uuid("tool_asset_execution_request_id"),
        )
        if response is None:
            raise ToolAssetExecutionUnavailable()
        headers["X-Request-ID"] = request_id
        return _execution_response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tool_asset_execution_request(
    acceptanceRevisionGlobalId: Any = None,
    expectedSourceHash: Any = None,
    expectedApprovalHash: Any = None,
    expectedMappingExpectationHash: Any = None,
    expectedProfileSnapshotHash: Any = None,
    acknowledgement: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _execution_command(
        operation="create_tool_asset",
        acknowledgement_expected=_CREATE_EXECUTION_ACKNOWLEDGEMENT,
        command_fields={
            **request_fields,
            "acceptanceRevisionGlobalId": acceptanceRevisionGlobalId,
            "expectedSourceHash": expectedSourceHash,
            "expectedApprovalHash": expectedApprovalHash,
            "expectedMappingExpectationHash": expectedMappingExpectationHash,
            "expectedProfileSnapshotHash": expectedProfileSnapshotHash,
            "acknowledgement": acknowledgement,
        },
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_tool_asset_execution_request(
    acceptanceRevisionGlobalId: Any = None,
    expectedSourceHash: Any = None,
    expectedApprovalHash: Any = None,
    expectedMappingExpectationHash: Any = None,
    expectedProfileSnapshotHash: Any = None,
    acknowledgement: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _execution_command(
        operation="update_tool_asset",
        acknowledgement_expected=_UPDATE_EXECUTION_ACKNOWLEDGEMENT,
        command_fields={
            **request_fields,
            "acceptanceRevisionGlobalId": acceptanceRevisionGlobalId,
            "expectedSourceHash": expectedSourceHash,
            "expectedApprovalHash": expectedApprovalHash,
            "expectedMappingExpectationHash": expectedMappingExpectationHash,
            "expectedProfileSnapshotHash": expectedProfileSnapshotHash,
            "acknowledgement": acknowledgement,
        },
    )


def _execution_command(
    *,
    operation: str,
    acknowledgement_expected: str,
    command_fields: dict[str, Any],
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }
    replayed = False

    def handle() -> dict[str, Any]:
        nonlocal replayed
        require_tooling_acceptance_assets_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        if principal.is_external or "NPI API User" not in principal.roles:
            raise PermissionDenied()
        request_id = _request_id()
        repository = _new_repository(principal, request_id)
        project_id = _opaque_route_uuid("project_id")
        if not repository.authorize_scope(project_id):
            raise ToolAssetExecutionUnavailable()
        reject_unexpected_request_fields(_EXECUTION_FIELDS, command_fields)
        require_request_fields(_EXECUTION_FIELDS, command_fields)
        if command_fields["acknowledgement"] != acknowledgement_expected:
            raise _field(
                "acknowledgement",
                _(
                    "Confirm the exact Tool Asset operation, source, business approval, mapping, and execution profile."
                ),
            )
        values = {
            "acceptance_revision_id": _uuid(
                command_fields["acceptanceRevisionGlobalId"],
                "acceptanceRevisionGlobalId",
            ),
            "expected_source_hash": _sha256(
                command_fields["expectedSourceHash"],
                "expectedSourceHash",
            ),
            "expected_approval_hash": _sha256(
                command_fields["expectedApprovalHash"],
                "expectedApprovalHash",
            ),
            "expected_mapping_expectation_hash": _sha256(
                command_fields["expectedMappingExpectationHash"],
                "expectedMappingExpectationHash",
            ),
            "expected_profile_snapshot_hash": _sha256(
                command_fields["expectedProfileSnapshotHash"],
                "expectedProfileSnapshotHash",
            ),
            "idempotency_key_hash": actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
            "acknowledgement": acknowledgement_expected,
        }
        if operation == "create_tool_asset":
            method = repository.create_tool_asset_execution_request
        elif operation == "update_tool_asset":
            method = repository.update_tool_asset_execution_request
        else:
            raise RuntimeError("The Tool Asset execution operation is invalid.")
        outcome = method(
            project_id,
            _opaque_route_uuid("tooling_master_id"),
            _opaque_route_uuid("tooling_set_id"),
            **values,
        )
        if outcome is None:
            raise ToolAssetExecutionUnavailable()
        if (
            type(outcome.replayed) is not bool
            or type(outcome.should_enqueue) is not bool
        ):
            raise RuntimeError("The Tool Asset execution command result is invalid.")
        try:
            frappe.db.commit()
        except Exception:
            try:
                frappe.db.rollback()
            except Exception:
                pass
            raise
        if outcome.problem is not None:
            if not isinstance(outcome.problem, NpiProblem):
                raise RuntimeError("The Tool Asset execution command problem is invalid.")
            raise outcome.problem
        response = _execution_response(outcome.response)
        if outcome.should_enqueue:
            if outcome.outbox_event_id is None:
                raise RuntimeError("The Tool Asset execution Outbox identity is unavailable.")
            try:
                _enqueue_after_commit(outcome.outbox_event_id)
            except Exception as error:
                record_safe_diagnostic(
                    code="TOOL_ASSET_EXECUTION_ENQUEUE_FAILED",
                    title="NPI Tool Asset execution enqueue failed",
                    exception_type=type(error).__name__,
                    trace_id=current_trace_id.get(),
                )
        replayed = outcome.replayed
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(replayed).lower()
        return response

    result = frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )
    if replayed and frappe.local.response.http_status_code == 201:
        frappe.local.response.http_status_code = 200
    return result


def _execution_query_context(
    request_fields: dict[str, Any],
) -> tuple[str, _Repository, UUID, UUID, UUID]:
    require_tooling_acceptance_assets_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    if principal.is_external:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ToolAssetExecutionUnavailable()
    reject_unexpected_request_fields(frozenset(), request_fields)
    return (
        request_id,
        repository,
        project_id,
        _opaque_route_uuid("tooling_master_id"),
        _opaque_route_uuid("tooling_set_id"),
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
        execution_profile_resolver=_configured_execution_profile,
    )


def _configured_execution_profile(
    tenant_id: str,
    project_id: UUID,
) -> object | None:
    resolver = _single_hook(_PROFILE_RESOLVER_HOOK)
    return None if resolver is None else resolver(tenant_id, str(project_id))


def _single_hook(name: str) -> Callable[..., Any] | None:
    hooks = frappe.get_hooks(name)
    values = [hooks] if isinstance(hooks, str) else list(hooks or ())
    if not values:
        return None
    if len(values) != 1 or not isinstance(values[0], str):
        raise RuntimeError("The Tool Asset execution profile resolver is ambiguous.")
    resolver = frappe.get_attr(values[0])
    if not callable(resolver):
        raise RuntimeError("The Tool Asset execution profile resolver is invalid.")
    return resolver


def _enqueue_after_commit(outbox_event_id: UUID) -> None:
    frappe.enqueue(
        "npi_integration.tool_asset_request.worker.process_outbox_message",
        queue="short",
        enqueue_after_commit=False,
        deduplicate=True,
        job_id=f"tool-asset-execution-{outbox_event_id}",
        outbox_event_id=str(outbox_event_id),
    )


def _execution_response(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The Tool Asset execution response is invalid.")
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


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise _field(path, _("Enter a positive whole number."))
    return value


def _sha256(value: object, path: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise _field(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


__all__ = [
    "create_tool_asset_execution_request",
    "create_tool_asset_request",
    "get_tool_asset_execution_request",
    "get_tool_asset_execution_requests",
    "get_tool_asset_request",
    "get_tool_asset_requests",
    "get_tooling_acceptance_assets",
    "update_tool_asset_execution_request",
]
