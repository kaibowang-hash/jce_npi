from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import (
    NpiProblem,
    PermissionDenied,
    RequestValidationFailed,
)
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.production_transition.request_validation import (
    AcknowledgementIntent,
    CreateObservationRequest,
    CreatePolicyRequest,
    EditPolicyRequest,
    HandoverContentRequest,
    NextPolicyVersionRequest,
    ObservationRevisionRequest,
    PublishPolicyRequest,
    ReviseHandoverRequest,
    parse_acknowledgement_intent,
    parse_create_handover_request,
    parse_create_observation_request,
    parse_create_policy_request,
    parse_edit_policy_request,
    parse_next_policy_version_request,
    parse_observation_revision_request,
    parse_publish_policy_request,
    parse_revise_handover_request,
)
from npi_core.production_transition.response_validation import (
    validate_command_response,
    validate_policy_catalog_response,
    validate_workspace_response,
)
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    response_request_id,
)


_CREATE_POLICY_FIELDS = frozenset({"policyCode", "title", "definition"})
_EDIT_POLICY_FIELDS = frozenset(
    {"expectedOptimisticVersion", "title", "definition"}
)
_PUBLISH_POLICY_FIELDS = frozenset(
    {"expectedOptimisticVersion", "expectedSnapshotHash"}
)
_NEXT_POLICY_VERSION_FIELDS = frozenset(
    {"expectedPublishedVersion", "expectedPublishedSnapshotHash"}
)
_HANDOVER_CONTENT_FIELDS = frozenset(
    {
        "expectedProjectVersion",
        "policy",
        "slotAssignments",
        "manifestSources",
        "reason",
    }
)
_REVISE_HANDOVER_FIELDS = frozenset(
    {"expectedRevisionGlobalId", "expectedSnapshotHash", "content"}
)
_ACKNOWLEDGEMENT_FIELDS = frozenset(
    {"expectedRevisionGlobalId", "expectedSnapshotHash", "slotKey", "intent"}
)
_CREATE_OBSERVATION_FIELDS = frozenset(
    {
        "expectedProjectVersion",
        "policy",
        "handover",
        "contextSources",
        "retrospectiveSources",
        "retrospectiveNote",
        "reason",
    }
)
_REVISE_OBSERVATION_FIELDS = frozenset(
    {
        "expectedRevisionGlobalId",
        "expectedSnapshotHash",
        "contextSources",
        "retrospectiveSources",
        "retrospectiveNote",
        "reason",
    }
)


class ProductionTransitionRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "PRODUCTION_TRANSITION_ROUTES_DISABLED",
            _("The request could not be completed."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


class ProductionTransitionUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "PRODUCTION_TRANSITION_UNAVAILABLE",
            _("The related Project is unavailable."),
        )


class ProductionTransitionPolicyUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "PRODUCTION_TRANSITION_POLICY_UNAVAILABLE",
            _("The Production Transition Policy is unavailable."),
        )


class _CommandOutcome(Protocol):
    response: object
    replayed: object
    target_global_id: object


class _Repository(Protocol):
    def policy_catalog(self, project_id: UUID) -> dict[str, Any] | None: ...

    def create_policy(
        self,
        *,
        idempotency_key_hash: str,
        request: CreatePolicyRequest,
    ) -> _CommandOutcome | None: ...

    def edit_policy(
        self,
        policy_id: UUID,
        policy_version: int,
        *,
        idempotency_key_hash: str,
        request: EditPolicyRequest,
    ) -> _CommandOutcome | None: ...

    def publish_policy(
        self,
        policy_id: UUID,
        policy_version: int,
        *,
        idempotency_key_hash: str,
        request: PublishPolicyRequest,
    ) -> _CommandOutcome | None: ...

    def create_policy_version(
        self,
        policy_id: UUID,
        *,
        idempotency_key_hash: str,
        request: NextPolicyVersionRequest,
    ) -> _CommandOutcome | None: ...

    def production_transition_workspace(
        self,
        project_id: UUID,
    ) -> dict[str, Any] | None: ...

    def create_handover(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        request: HandoverContentRequest,
    ) -> _CommandOutcome | None: ...

    def revise_handover(
        self,
        project_id: UUID,
        handover_id: UUID,
        *,
        idempotency_key_hash: str,
        request: ReviseHandoverRequest,
    ) -> _CommandOutcome | None: ...

    def acknowledge_handover(
        self,
        project_id: UUID,
        handover_id: UUID,
        handover_version: int,
        *,
        idempotency_key_hash: str,
        request: AcknowledgementIntent,
    ) -> _CommandOutcome | None: ...

    def create_observation(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        request: CreateObservationRequest,
    ) -> _CommandOutcome | None: ...

    def revise_observation(
        self,
        project_id: UUID,
        observation_id: UUID,
        *,
        idempotency_key_hash: str,
        request: ObservationRevisionRequest,
    ) -> _CommandOutcome | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from npi_core.production_transition.frappe_repository import (
        FrappeProductionTransitionRepository,
    )

    return FrappeProductionTransitionRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def list_eligible_production_transition_policies(
    projectId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        _require_api_user(principal)
        reject_unexpected_request_fields(frozenset({"projectId"}), request_fields)
        require_request_fields(frozenset({"projectId"}), request_fields)
        project_id = _uuid(projectId, "projectId")
        request_id, repository = _new_repository(principal)
        response = repository.policy_catalog(project_id)
        if response is None:
            raise ProductionTransitionUnavailable()
        headers["X-Request-ID"] = request_id
        return validate_policy_catalog_response(
            response,
            project_global_id=str(project_id),
            tenant_id=principal.tenant_id,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_production_transition_policy_draft(
    policyCode: Any = None,
    title: Any = None,
    definition: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {"policyCode": policyCode, "title": title, "definition": definition}
    return _command(
        allowed_fields=_CREATE_POLICY_FIELDS,
        required_fields=_CREATE_POLICY_FIELDS,
        request_fields=request_fields,
        success_status=201,
        unavailable=ProductionTransitionPolicyUnavailable,
        administrator=True,
        parse_request=lambda: parse_create_policy_request(values, path=""),
        invoke=lambda repository, key_hash, request: repository.create_policy(
            idempotency_key_hash=key_hash,
            request=request,
        ),
        validate_response=lambda outcome, _request, principal: validate_command_response(
            "production_transition_policy.create",
            outcome.response,
            target_global_id=outcome.target_global_id,
            tenant_id=principal.tenant_id,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def edit_production_transition_policy_draft(
    expectedOptimisticVersion: Any = None,
    title: Any = None,
    definition: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedOptimisticVersion": expectedOptimisticVersion,
        "title": title,
        "definition": definition,
    }
    return _command(
        allowed_fields=_EDIT_POLICY_FIELDS,
        required_fields=_EDIT_POLICY_FIELDS,
        request_fields=request_fields,
        success_status=200,
        unavailable=ProductionTransitionPolicyUnavailable,
        administrator=True,
        parse_request=lambda: parse_edit_policy_request(values, path=""),
        invoke=lambda repository, key_hash, request: repository.edit_policy(
            _route_uuid("policy_id", ProductionTransitionPolicyUnavailable),
            _route_positive("policy_version", ProductionTransitionPolicyUnavailable),
            idempotency_key_hash=key_hash,
            request=request,
        ),
        validate_response=lambda outcome, _request, principal: validate_command_response(
            "production_transition_policy.edit",
            outcome.response,
            target_global_id=outcome.target_global_id,
            tenant_id=principal.tenant_id,
            policy_global_id=_route_uuid(
                "policy_id", ProductionTransitionPolicyUnavailable
            ),
            policy_version=_route_positive(
                "policy_version", ProductionTransitionPolicyUnavailable
            ),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def publish_production_transition_policy_version(
    expectedOptimisticVersion: Any = None,
    expectedSnapshotHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedOptimisticVersion": expectedOptimisticVersion,
        "expectedSnapshotHash": expectedSnapshotHash,
    }
    return _command(
        allowed_fields=_PUBLISH_POLICY_FIELDS,
        required_fields=_PUBLISH_POLICY_FIELDS,
        request_fields=request_fields,
        success_status=200,
        unavailable=ProductionTransitionPolicyUnavailable,
        administrator=True,
        parse_request=lambda: parse_publish_policy_request(values, path=""),
        invoke=lambda repository, key_hash, request: repository.publish_policy(
            _route_uuid("policy_id", ProductionTransitionPolicyUnavailable),
            _route_positive("policy_version", ProductionTransitionPolicyUnavailable),
            idempotency_key_hash=key_hash,
            request=request,
        ),
        validate_response=lambda outcome, request, principal: validate_command_response(
            "production_transition_policy.publish",
            outcome.response,
            target_global_id=outcome.target_global_id,
            tenant_id=principal.tenant_id,
            policy_global_id=_route_uuid(
                "policy_id", ProductionTransitionPolicyUnavailable
            ),
            policy_version=_route_positive(
                "policy_version", ProductionTransitionPolicyUnavailable
            ),
            policy_snapshot_hash=request.expected_snapshot_hash,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_next_production_transition_policy_version(
    expectedPublishedVersion: Any = None,
    expectedPublishedSnapshotHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedPublishedVersion": expectedPublishedVersion,
        "expectedPublishedSnapshotHash": expectedPublishedSnapshotHash,
    }
    return _command(
        allowed_fields=_NEXT_POLICY_VERSION_FIELDS,
        required_fields=_NEXT_POLICY_VERSION_FIELDS,
        request_fields=request_fields,
        success_status=201,
        unavailable=ProductionTransitionPolicyUnavailable,
        administrator=True,
        parse_request=lambda: parse_next_policy_version_request(values, path=""),
        invoke=lambda repository, key_hash, request: repository.create_policy_version(
            _route_uuid("policy_id", ProductionTransitionPolicyUnavailable),
            idempotency_key_hash=key_hash,
            request=request,
        ),
        validate_response=lambda outcome, request, principal: validate_command_response(
            "production_transition_policy.next_version",
            outcome.response,
            target_global_id=outcome.target_global_id,
            tenant_id=principal.tenant_id,
            policy_global_id=_route_uuid(
                "policy_id", ProductionTransitionPolicyUnavailable
            ),
            policy_version=request.expected_published_version,
            policy_snapshot_hash=request.expected_published_snapshot_hash,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_production_transition_workspace(
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        _require_api_user(principal)
        reject_unexpected_request_fields(frozenset(), request_fields)
        project_id = _route_uuid("project_id", ProductionTransitionUnavailable)
        request_id, repository = _new_repository(principal)
        response = repository.production_transition_workspace(project_id)
        if response is None:
            raise ProductionTransitionUnavailable()
        headers["X-Request-ID"] = request_id
        return validate_workspace_response(
            response,
            project_global_id=str(project_id),
            tenant_id=principal.tenant_id,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_production_handover_package(
    expectedProjectVersion: Any = None,
    policy: Any = None,
    slotAssignments: Any = None,
    manifestSources: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedProjectVersion": expectedProjectVersion,
        "policy": policy,
        "slotAssignments": slotAssignments,
        "manifestSources": manifestSources,
        "reason": reason,
    }
    return _project_command(
        allowed_fields=_HANDOVER_CONTENT_FIELDS,
        required_fields=_HANDOVER_CONTENT_FIELDS,
        request_fields=request_fields,
        success_status=201,
        administrator=True,
        parse_request=lambda: parse_create_handover_request(values, path=""),
        invoke=lambda repository, project_id, key_hash, request: (
            repository.create_handover(
                project_id,
                idempotency_key_hash=key_hash,
                request=request,
            )
        ),
        validate_response=lambda outcome, request, project_id, principal: (
            validate_command_response(
                "production_handover.create",
                outcome.response,
                target_global_id=outcome.target_global_id,
                tenant_id=principal.tenant_id,
                project_global_id=project_id,
                policy_global_id=request.policy.policy_global_id,
                policy_version=request.policy.policy_version,
                policy_snapshot_hash=request.policy.policy_snapshot_hash,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def revise_production_handover_package(
    expectedRevisionGlobalId: Any = None,
    expectedSnapshotHash: Any = None,
    content: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedRevisionGlobalId": expectedRevisionGlobalId,
        "expectedSnapshotHash": expectedSnapshotHash,
        "content": content,
    }
    return _project_command(
        allowed_fields=_REVISE_HANDOVER_FIELDS,
        required_fields=_REVISE_HANDOVER_FIELDS,
        request_fields=request_fields,
        success_status=201,
        administrator=True,
        parse_request=lambda: parse_revise_handover_request(values, path=""),
        invoke=lambda repository, project_id, key_hash, request: (
            repository.revise_handover(
                project_id,
                _route_uuid("handover_id", ProductionTransitionUnavailable),
                idempotency_key_hash=key_hash,
                request=request,
            )
        ),
        validate_response=lambda outcome, request, project_id, principal: (
            validate_command_response(
                "production_handover.revise",
                outcome.response,
                target_global_id=outcome.target_global_id,
                tenant_id=principal.tenant_id,
                project_global_id=project_id,
                handover_global_id=_route_uuid(
                    "handover_id", ProductionTransitionUnavailable
                ),
                expected_revision_global_id=request.expected_revision_global_id,
                expected_snapshot_hash=request.expected_snapshot_hash,
                policy_global_id=request.content.policy.policy_global_id,
                policy_version=request.content.policy.policy_version,
                policy_snapshot_hash=request.content.policy.policy_snapshot_hash,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def acknowledge_production_handover_slot(
    expectedRevisionGlobalId: Any = None,
    expectedSnapshotHash: Any = None,
    slotKey: Any = None,
    intent: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedRevisionGlobalId": expectedRevisionGlobalId,
        "expectedSnapshotHash": expectedSnapshotHash,
        "slotKey": slotKey,
        "intent": intent,
    }
    return _project_command(
        allowed_fields=_ACKNOWLEDGEMENT_FIELDS,
        required_fields=_ACKNOWLEDGEMENT_FIELDS,
        request_fields=request_fields,
        success_status=201,
        administrator=False,
        parse_request=lambda: parse_acknowledgement_intent(values, path=""),
        invoke=lambda repository, project_id, key_hash, request: (
            repository.acknowledge_handover(
                project_id,
                _route_uuid("handover_id", ProductionTransitionUnavailable),
                _route_positive(
                    "handover_version", ProductionTransitionUnavailable
                ),
                idempotency_key_hash=key_hash,
                request=request,
            )
        ),
        validate_response=lambda outcome, request, project_id, principal: (
            validate_command_response(
                "production_handover.acknowledge",
                outcome.response,
                target_global_id=outcome.target_global_id,
                tenant_id=principal.tenant_id,
                project_global_id=project_id,
                handover_global_id=_route_uuid(
                    "handover_id", ProductionTransitionUnavailable
                ),
                handover_version=_route_positive(
                    "handover_version", ProductionTransitionUnavailable
                ),
                handover_revision_global_id=request.expected_revision_global_id,
                handover_snapshot_hash=request.expected_snapshot_hash,
                expected_revision_global_id=request.expected_revision_global_id,
                expected_snapshot_hash=request.expected_snapshot_hash,
                slot_key=request.slot_key,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_observation_period(
    expectedProjectVersion: Any = None,
    policy: Any = None,
    handover: Any = None,
    contextSources: Any = None,
    retrospectiveSources: Any = None,
    retrospectiveNote: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedProjectVersion": expectedProjectVersion,
        "policy": policy,
        "handover": handover,
        "contextSources": contextSources,
        "retrospectiveSources": retrospectiveSources,
        "retrospectiveNote": retrospectiveNote,
        "reason": reason,
    }
    return _project_command(
        allowed_fields=_CREATE_OBSERVATION_FIELDS,
        required_fields=_CREATE_OBSERVATION_FIELDS,
        request_fields=request_fields,
        success_status=201,
        administrator=True,
        parse_request=lambda: parse_create_observation_request(values, path=""),
        invoke=lambda repository, project_id, key_hash, request: (
            repository.create_observation(
                project_id,
                idempotency_key_hash=key_hash,
                request=request,
            )
        ),
        validate_response=_validate_observation_create_response,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def revise_observation_period(
    expectedRevisionGlobalId: Any = None,
    expectedSnapshotHash: Any = None,
    contextSources: Any = None,
    retrospectiveSources: Any = None,
    retrospectiveNote: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedRevisionGlobalId": expectedRevisionGlobalId,
        "expectedSnapshotHash": expectedSnapshotHash,
        "contextSources": contextSources,
        "retrospectiveSources": retrospectiveSources,
        "retrospectiveNote": retrospectiveNote,
        "reason": reason,
    }
    return _project_command(
        allowed_fields=_REVISE_OBSERVATION_FIELDS,
        required_fields=_REVISE_OBSERVATION_FIELDS,
        request_fields=request_fields,
        success_status=201,
        administrator=True,
        parse_request=lambda: parse_observation_revision_request(
            values,
            successor=True,
            path="",
        ),
        invoke=lambda repository, project_id, key_hash, request: (
            repository.revise_observation(
                project_id,
                _route_uuid("observation_id", ProductionTransitionUnavailable),
                idempotency_key_hash=key_hash,
                request=request,
            )
        ),
        validate_response=lambda outcome, request, project_id, principal: (
            validate_command_response(
                "observation_period.revise",
                outcome.response,
                target_global_id=outcome.target_global_id,
                tenant_id=principal.tenant_id,
                project_global_id=project_id,
                observation_global_id=_route_uuid(
                    "observation_id", ProductionTransitionUnavailable
                ),
                expected_revision_global_id=request.expected_revision_global_id,
                expected_snapshot_hash=request.expected_snapshot_hash,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET", "POST", "PUT"])
def production_transition_routes_disabled(
    **_request_fields: Any,
) -> dict[str, Any] | None:
    def handle() -> dict[str, Any]:
        raise ProductionTransitionRoutesDisabled()

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


def _command(
    *,
    allowed_fields: frozenset[str],
    required_fields: frozenset[str],
    request_fields: dict[str, Any],
    success_status: int,
    unavailable: type[NpiProblem],
    administrator: bool,
    parse_request: Callable[[], Any],
    invoke: Callable[[_Repository, str, Any], _CommandOutcome | None],
    validate_response: Callable[[_CommandOutcome, Any, Principal], dict[str, Any]],
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        _require_command_role(principal, administrator=administrator)
        reject_unexpected_request_fields(allowed_fields, request_fields)
        require_request_fields(required_fields, request_fields)
        parsed_request = parse_request()
        request_id, repository = _new_repository(principal)
        outcome = invoke(
            repository,
            actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
            parsed_request,
        )
        if outcome is None:
            raise unavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The production-transition command outcome is invalid.")
        response = validate_response(outcome, parsed_request, principal)
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=success_status,
        response_headers=headers,
    )


def _project_command(
    *,
    allowed_fields: frozenset[str],
    required_fields: frozenset[str],
    request_fields: dict[str, Any],
    success_status: int,
    administrator: bool,
    parse_request: Callable[[], Any],
    invoke: Callable[[_Repository, UUID, str, Any], _CommandOutcome | None],
    validate_response: Callable[
        [_CommandOutcome, Any, UUID, Principal],
        dict[str, Any],
    ],
) -> dict[str, Any] | None:
    project_id = lambda: _route_uuid("project_id", ProductionTransitionUnavailable)
    return _command(
        allowed_fields=allowed_fields,
        required_fields=required_fields,
        request_fields=request_fields,
        success_status=success_status,
        unavailable=ProductionTransitionUnavailable,
        administrator=administrator,
        parse_request=parse_request,
        invoke=lambda repository, key_hash, request: invoke(
            repository,
            project_id(),
            key_hash,
            request,
        ),
        validate_response=lambda outcome, request, principal: validate_response(
            outcome,
            request,
            project_id(),
            principal,
        ),
    )


def _validate_observation_create_response(
    outcome: _CommandOutcome,
    request: CreateObservationRequest,
    project_id: UUID,
    principal: Principal,
) -> dict[str, Any]:
    handover = request.handover
    return validate_command_response(
        "observation_period.create",
        outcome.response,
        target_global_id=outcome.target_global_id,
        tenant_id=principal.tenant_id,
        project_global_id=project_id,
        policy_global_id=request.policy.policy_global_id,
        policy_version=request.policy.policy_version,
        policy_snapshot_hash=request.policy.policy_snapshot_hash,
        handover_global_id=(handover.handover_global_id if handover else None),
        handover_version=(handover.handover_version if handover else None),
        handover_revision_global_id=(
            handover.handover_revision_global_id if handover else None
        ),
        handover_snapshot_hash=(handover.handover_snapshot_hash if handover else None),
    )


def _new_repository(principal: Principal) -> tuple[str, _Repository]:
    request_id = str(_uuid(frappe.get_request_header("X-Request-ID"), "requestId"))
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The production-transition request has no trace identity.")
    return request_id, _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _routes_are_disabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_06_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def _require_routes_enabled() -> None:
    if _routes_are_disabled():
        raise ProductionTransitionRoutesDisabled()


def _require_api_user(principal: Principal) -> None:
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()


def _require_command_role(principal: Principal, *, administrator: bool) -> None:
    if administrator:
        if principal.is_external or "System Manager" not in principal.roles:
            raise PermissionDenied()
        return
    _require_api_user(principal)


def _route_uuid(name: str, unavailable: type[NpiProblem]) -> UUID:
    value = _route_value(name)
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise unavailable() from error
    if str(parsed) != str(value).casefold():
        raise unavailable()
    return parsed


def _route_positive(name: str, unavailable: type[NpiProblem]) -> int:
    value = _route_value(name)
    if not isinstance(value, str) or not value.isdecimal():
        raise unavailable()
    parsed = int(value)
    if parsed < 1 or str(parsed) != value:
        raise unavailable()
    return parsed


def _route_value(name: str) -> object:
    params = getattr(frappe.flags, "npi_route_params", None)
    return params.get(name) if hasattr(params, "get") else None


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != value.casefold():
        raise _field(path, _("Enter a valid global ID."))
    return parsed


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
