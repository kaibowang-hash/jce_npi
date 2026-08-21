from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import frappe

from npi_core.api import record_safe_diagnostic

from .adapters import (
    MbomAdapterRegistry,
    classify_mbom_adapter_response,
    failed_before_mbom_adapter_boundary_result,
    uncertain_mbom_adapter_result,
)
from .config import MbomExecutionProfile
from .frappe_validation import MbomServiceActorUnavailable, mbom_service_actor_scope
from .worker_repository import (
    FrappeMbomPublishWorkerRepository,
    MbomPublishWorkerFinalFailure,
    MbomPublishWorkerOutcome,
)


_PROFILE_RESOLVER_HOOK = "npi_mbom_publish_profile_resolver"
_ADAPTER_REGISTRY_HOOK = "npi_mbom_publish_adapter_registry"
_JOB_PATH = "npi_integration.mbom_publish.worker.process_outbox_message"


def process_outbox_message(outbox_event_id: str) -> dict[str, object]:
    try:
        parsed_event_id = UUID(str(outbox_event_id))
    except (TypeError, ValueError) as error:
        raise ValueError("MBOM Outbox event ID is invalid.") from error
    outcome = _execute_worker(
        outbox_event_id=parsed_event_id,
        repository=FrappeMbomPublishWorkerRepository(),
        profile_resolver=_configured_profile,
        registry_resolver=_configured_registry,
        clock=lambda: datetime.now(UTC),
    )
    if outcome is None:
        return {"outboxEventId": str(parsed_event_id), "state": "not_claimed"}
    result: dict[str, object] = {
        "outboxEventId": str(outcome.outbox_event_id),
        "requestGlobalId": str(outcome.request_global_id),
        "state": outcome.state,
        "disposition": outcome.disposition,
        "mappingAdvancedCount": outcome.mapping_advanced_count,
    }
    if outcome.result_global_id is not None:
        result["resultGlobalId"] = str(outcome.result_global_id)
    return result


def recover_mbom_publish_outbox_messages() -> int:
    """Requeue only bounded pending/expired MBOM work; never terminal replay."""

    repository = FrappeMbomPublishWorkerRepository()
    event_ids = repository.recoverable_outbox_event_ids(now=datetime.now(UTC))
    queued = 0
    for event_id in event_ids:
        try:
            _enqueue(event_id)
        except Exception as error:
            _record_failure(
                "MBOM_PUBLISH_RECOVERY_ENQUEUE_FAILED",
                error,
                f"mbom-publish-recovery-{event_id}",
            )
        else:
            queued += 1
    return queued


def _execute_worker(
    *,
    outbox_event_id: UUID,
    repository: FrappeMbomPublishWorkerRepository,
    profile_resolver: Callable[[str, UUID], MbomExecutionProfile | None],
    registry_resolver: Callable[[], MbomAdapterRegistry | None],
    clock: Callable[[], datetime],
) -> MbomPublishWorkerOutcome | None:
    route_reader = getattr(repository, "execution_route", None)
    if not callable(route_reader):
        _rollback_safely()
        _record_failure(
            "MBOM_PUBLISH_EXECUTION_ROUTE_UNAVAILABLE",
            RuntimeError("MBOM execution route reader is unavailable."),
            str(outbox_event_id),
        )
        return None
    try:
        route = route_reader(outbox_event_id)
    except Exception as error:
        _rollback_safely()
        _record_failure("MBOM_PUBLISH_EXECUTION_ROUTE_INVALID", error, str(outbox_event_id))
        return None
    actor = getattr(route, "service_actor_user_id", None)
    if not isinstance(actor, str) or not actor:
        _rollback_safely()
        _record_failure(
            "MBOM_PUBLISH_EXECUTION_ROUTE_INVALID",
            RuntimeError("MBOM execution route has no frozen service actor."),
            str(outbox_event_id),
        )
        return None
    try:
        with mbom_service_actor_scope(actor):
            return _execute_worker_in_service_scope(
                outbox_event_id=outbox_event_id,
                repository=repository,
                profile_resolver=profile_resolver,
                registry_resolver=registry_resolver,
                clock=clock,
                expected_route=route,
            )
    except MbomServiceActorUnavailable as error:
        _rollback_safely()
        _record_failure(
            "MBOM_PUBLISH_SERVICE_ACTOR_UNAVAILABLE", error, str(outbox_event_id)
        )
        return None


def _execute_worker_in_service_scope(
    *, outbox_event_id, repository, profile_resolver, registry_resolver, clock, expected_route
):
    claim = repository.claim(outbox_event_id, now=clock(), expected_route=expected_route)
    if claim is None:
        _rollback_safely()
        return None
    _commit_or_raise("MBOM_PUBLISH_CLAIM_COMMIT_FAILED", claim.trace_id)
    if claim.recovered_after_adapter_boundary:
        result = uncertain_mbom_adapter_result(
            command=claim.command,
            safe_error_code="MBOM_PUBLISH_RECOVERED_AFTER_ADAPTER_BOUNDARY",
        )
        return _persist_observed_result_without_redispatch(
            repository, claim, profile=None, result=result, now=clock()
        )

    profile = None
    try:
        profile = repository.require_execution_profile(
            claim, profile_resolver(claim.tenant_id, claim.project_global_id)
        )
        registry = registry_resolver()
        adapter = registry.resolve(profile) if isinstance(registry, MbomAdapterRegistry) else None
        if adapter is None:
            raise MbomPublishWorkerFinalFailure("MBOM_PUBLISH_ADAPTER_UNAVAILABLE")
    except MbomPublishWorkerFinalFailure as error:
        _rollback_safely()
        result = failed_before_mbom_adapter_boundary_result(
            command=claim.command, safe_error_code=error.code
        )
        return _persist_observed_result_without_redispatch(
            repository, claim, profile=None, result=result, now=clock()
        )
    except Exception as error:
        _rollback_safely()
        _record_failure("MBOM_PUBLISH_PROFILE_OR_REGISTRY_FAILED", error, claim.trace_id)
        result = failed_before_mbom_adapter_boundary_result(
            command=claim.command,
            safe_error_code="MBOM_PUBLISH_EXECUTION_CONFIGURATION_INVALID",
        )
        return _persist_observed_result_without_redispatch(
            repository, claim, profile=None, result=result, now=clock()
        )

    if not repository.mark_adapter_boundary(claim, profile=profile, now=clock()):
        _rollback_safely()
        raise RuntimeError("MBOM adapter boundary could not be sealed safely.")
    _commit_or_raise("MBOM_PUBLISH_BOUNDARY_COMMIT_FAILED", claim.trace_id)
    try:
        response = adapter(claim.command)
        classified = classify_mbom_adapter_response(
            profile=profile, command=claim.command, response=response, observed_at=clock()
        )
    except Exception as error:
        _rollback_safely()
        _record_failure("MBOM_PUBLISH_ADAPTER_OUTCOME_UNCERTAIN", error, claim.trace_id)
        classified = uncertain_mbom_adapter_result(
            command=claim.command,
            safe_error_code="MBOM_PUBLISH_ADAPTER_OUTCOME_UNCERTAIN",
        )
    return _persist_observed_result_without_redispatch(
        repository, claim, profile=profile, result=classified, now=clock()
    )


def _persist_observed_result_without_redispatch(
    repository, claim, *, profile, result, now
):
    commit_attempted = False
    try:
        outcome = repository.seal_result(claim, profile=profile, result=result, now=now)
        commit_attempted = True
        _commit_or_raise("MBOM_PUBLISH_RESULT_COMMIT_FAILED", claim.trace_id)
        return outcome
    except Exception as first_error:
        if not commit_attempted:
            _rollback_safely()
            _record_failure(
                "MBOM_PUBLISH_RESULT_PERSISTENCE_FAILED", first_error, claim.trace_id
            )
        recover = getattr(repository, "recover_or_seal_result", None)
        if not callable(recover):
            raise
        recovery_commit_attempted = False
        try:
            outcome = recover(claim, profile=profile, result=result, now=now)
            recovery_commit_attempted = True
            _commit_or_raise("MBOM_PUBLISH_RESULT_RECOVERY_COMMIT_FAILED", claim.trace_id)
            return outcome
        except Exception as recovery_error:
            if not recovery_commit_attempted:
                _rollback_safely()
                _record_failure(
                    "MBOM_PUBLISH_RESULT_RECOVERY_FAILED", recovery_error, claim.trace_id
                )
            raise


def _configured_profile(tenant_id: str, project_id: UUID) -> MbomExecutionProfile | None:
    resolver = _single_hook(_PROFILE_RESOLVER_HOOK)
    if resolver is None:
        return None
    value = resolver(tenant_id, str(project_id))
    return value if isinstance(value, MbomExecutionProfile) else None


def _configured_registry() -> MbomAdapterRegistry | None:
    resolver = _single_hook(_ADAPTER_REGISTRY_HOOK)
    if resolver is None:
        return None
    value = resolver()
    return value if isinstance(value, MbomAdapterRegistry) else None


def _single_hook(name: str) -> Callable[..., object] | None:
    values = tuple(frappe.get_hooks(name) or ())
    if len(values) != 1 or not isinstance(values[0], str):
        return None
    value = frappe.get_attr(values[0])
    return value if callable(value) else None


def _enqueue(outbox_event_id: UUID) -> None:
    frappe.enqueue(
        _JOB_PATH,
        queue="short",
        job_id=f"mbom-publish-{outbox_event_id}",
        enqueue_after_commit=True,
        outbox_event_id=str(outbox_event_id),
    )


def _commit_or_raise(code: str, trace_id: str) -> None:
    try:
        frappe.db.commit()
    except Exception as error:
        _rollback_safely()
        _record_failure(code, error, trace_id)
        raise


def _record_failure(code: str, error: Exception, trace_id: str) -> None:
    record_safe_diagnostic(
        code=code,
        title="NPI MBOM publish worker failed",
        exception_type=type(error).__name__,
        trace_id=trace_id,
    )


def _rollback_safely() -> None:
    try:
        frappe.db.rollback()
    except Exception:
        pass
