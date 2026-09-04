from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import frappe

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
from npi_core.trial.released_summary_domain import (
    ReleasedTrialSummaryRoutesDisabled,
    ReleasedTrialSummaryUnavailable,
    released_trial_summary_from_snapshot,
    validate_released_trial_summary_successor,
)
from npi_core.trial.released_summary_validation import (
    RETAIN_RELEASED_SUMMARY_FIELDS,
    REVISE_RELEASED_SUMMARY_FIELDS,
    retain_released_summary_values,
    revise_released_summary_values,
)


class _Repository(Protocol):
    def summary_workspace(self, project_id: UUID, round_id: UUID): ...
    def retain_summary(self, project_id: UUID, round_id: UUID, **values: Any): ...
    def revise_summary(
        self,
        project_id: UUID,
        round_id: UUID,
        summary_id: UUID,
        **values: Any,
    ): ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from npi_core.trial.released_summary_repository import (
        FrappeReleasedTrialSummaryRepository,
    )

    return FrappeReleasedTrialSummaryRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_released_trial_summaries(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        _require_role(principal)
        reject_unexpected_request_fields(frozenset(), request_fields)
        request_id, repository = _new_repository(principal)
        project_id = _route_uuid("project_id")
        round_id = _route_uuid("trial_round_id")
        response = repository.summary_workspace(project_id, round_id)
        if response is None:
            raise ReleasedTrialSummaryUnavailable()
        headers["X-Request-ID"] = request_id
        return _validated_response(response, project_id, round_id)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def retain_released_trial_summary(**request_fields: Any) -> dict[str, Any] | None:
    return _command(
        allowed_fields=RETAIN_RELEASED_SUMMARY_FIELDS,
        request_fields=request_fields,
        invoke=lambda repository, project_id, round_id, _summary_id, key_hash: (
            repository.retain_summary(
                project_id,
                round_id,
                idempotency_key_hash=key_hash,
                **retain_released_summary_values(request_fields),
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def revise_released_trial_summary(**request_fields: Any) -> dict[str, Any] | None:
    return _command(
        allowed_fields=REVISE_RELEASED_SUMMARY_FIELDS,
        request_fields=request_fields,
        require_summary_id=True,
        invoke=lambda repository, project_id, round_id, summary_id, key_hash: (
            repository.revise_summary(
                project_id,
                round_id,
                summary_id,
                idempotency_key_hash=key_hash,
                **revise_released_summary_values(request_fields),
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def released_trial_summary_routes_disabled(
    **_request_fields: Any,
) -> dict[str, Any] | None:
    def handle() -> dict[str, Any]:
        raise ReleasedTrialSummaryRoutesDisabled()

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


def _command(
    *,
    allowed_fields: frozenset[str],
    request_fields: dict[str, Any],
    invoke,
    require_summary_id: bool = False,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        # Keep the switch and identity checks ahead of caller-controlled body parsing.
        _require_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        _require_command_role(principal)
        reject_unexpected_request_fields(allowed_fields, request_fields)
        require_request_fields(allowed_fields, request_fields)
        request_id, repository = _new_repository(principal)
        project_id = _route_uuid("project_id")
        round_id = _route_uuid("trial_round_id")
        summary_id = _route_uuid("summary_id") if require_summary_id else None
        outcome = invoke(
            repository,
            project_id,
            round_id,
            summary_id,
            actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
        )
        if outcome is None:
            raise ReleasedTrialSummaryUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The Released Trial Summary replay response is invalid.")
        response = _validated_response(outcome.response, project_id, round_id)
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _new_repository(principal: Principal) -> tuple[str, _Repository]:
    request_id = str(_canonical_uuid(frappe.get_request_header("X-Request-ID")))
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Released Trial Summary request has no trace identity.")
    return request_id, _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _validated_response(
    value: object,
    project_id: UUID,
    round_id: UUID,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "projectGlobalId",
        "trialRound",
        "summaryRevisions",
        "currentSummaryRevisionGlobalId",
        "currentDecidedConclusion",
        "permissions",
        "controlledOutput",
        "holds",
    }:
        raise RuntimeError("The Released Trial Summary response is invalid.")
    trial_round = value["trialRound"]
    if (
        value["projectGlobalId"] != str(project_id)
        or not isinstance(trial_round, dict)
        or trial_round.get("globalId") != str(round_id)
    ):
        raise RuntimeError("The Released Trial Summary response escaped its route scope.")
    revisions = value["summaryRevisions"]
    if not isinstance(revisions, list) or len(revisions) > 10_000:
        raise RuntimeError("The Released Trial Summary response is not bounded.")
    parsed = [released_trial_summary_from_snapshot(item) for item in revisions]
    if any(
        item.project_global_id != project_id or item.trial_round_global_id != round_id
        for item in parsed
    ):
        raise RuntimeError("The Released Trial Summary response escaped its route scope.")
    if len({item.summary_global_id for item in parsed}) > 1:
        raise RuntimeError("The Released Trial Summary response has multiple streams.")
    if parsed and parsed[0].summary_version != 1:
        raise RuntimeError("The Released Trial Summary response does not start at one.")
    for predecessor, successor in zip(parsed, parsed[1:], strict=False):
        validate_released_trial_summary_successor(predecessor, successor)
    current_id = value["currentSummaryRevisionGlobalId"]
    if (not parsed and current_id is not None) or (
        parsed and current_id != str(parsed[-1].global_id)
    ):
        raise RuntimeError("The Released Trial Summary response has an invalid current tip.")
    conclusion = value["currentDecidedConclusion"]
    if conclusion is not None:
        if (
            not isinstance(conclusion, dict)
            or set(conclusion)
            != {
                "globalId",
                "conclusionVersion",
                "snapshotHash",
                "state",
                "conclusionCode",
            }
            or type(conclusion["conclusionVersion"]) is not int
            or conclusion["conclusionVersion"] < 1
            or conclusion["state"] not in {"approved", "rejected"}
            or conclusion["conclusionCode"]
            not in {
                "pass",
                "conditional_pass",
                "tooling_change",
                "design_change",
                "process_tuning",
                "material_change",
                "cancelled",
            }
            or len(str(conclusion["snapshotHash"])) != 64
        ):
            raise RuntimeError("The current Trial conclusion response is invalid.")
        try:
            UUID(str(conclusion["globalId"]))
        except (TypeError, ValueError, AttributeError) as error:
            raise RuntimeError("The current Trial conclusion response is invalid.") from error
    if set(value["permissions"]) != {
        "view",
        "retain",
        "revise",
        "requiresExactRound",
        "requiresExactConclusion",
        "requiresExactPredecessor",
    } or not all(type(item) is bool for item in value["permissions"].values()):
        raise RuntimeError("The Released Trial Summary permissions are invalid.")
    if set(value["controlledOutput"]) != {
        "sourceObjectType",
        "sourceGlobalId",
        "sourceVersion",
        "mapping",
    } or (
        value["controlledOutput"]["sourceObjectType"] != "released_trial_summary"
        or value["controlledOutput"]["mapping"] != "unavailable"
        or (
            parsed
            and (
                value["controlledOutput"]["sourceGlobalId"]
                != str(parsed[-1].global_id)
                or value["controlledOutput"]["sourceVersion"]
                != parsed[-1].summary_version
            )
        )
        or (
            not parsed
            and (
                value["controlledOutput"]["sourceGlobalId"] is not None
                or value["controlledOutput"]["sourceVersion"] is not None
            )
        )
    ):
        raise RuntimeError("The Released Trial Summary print source is invalid.")
    if set(value["holds"]) != {
        "formalRelease",
        "customerApproval",
        "signature",
        "productionAcceptance",
        "gateDecision",
        "externalProjection",
    } or set(value["holds"].values()) != {"unavailable"}:
        raise RuntimeError("The Released Trial Summary authority holds are invalid.")
    return value


def _routes_are_disabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_07_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def _require_routes_enabled() -> None:
    if _routes_are_disabled():
        raise ReleasedTrialSummaryRoutesDisabled()


def _require_role(principal: Principal) -> None:
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()


def _require_command_role(principal: Principal) -> None:
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()


def _route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        result = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ReleasedTrialSummaryUnavailable() from error
    if str(result) != str(value).casefold():
        raise ReleasedTrialSummaryUnavailable()
    return result


def _canonical_uuid(value: object) -> UUID:
    try:
        result = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise RequestValidationFailed(
            [{"path": "requestId", "message": frappe._("Enter a valid global ID.")}]
        ) from error
    if str(result) != str(value).casefold():
        raise RequestValidationFailed(
            [{"path": "requestId", "message": frappe._("Enter a valid global ID.")}]
        )
    return result
