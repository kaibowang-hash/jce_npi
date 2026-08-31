from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import frappe

from npi_core.api import record_safe_diagnostic
from npi_core.change_control.frappe_repository import FrappeChangeControlRepository
from npi_core.change_control.request_validation import parse_formal_observation
from npi_core.change_control.response_validation import (
    validate_change_command_response,
    validate_change_detail_response,
)
from npi_core.foundation.errors import NpiProblem, VersionConflict
from npi_core.foundation.security import Principal, ProjectAccess

from .adapters import AdapterRegistry
from .config import IntegrationProfile
from .domain import (
    FaultKind,
    RetryDirective,
    SummaryState,
    TargetMode,
    canonical_hash,
    classify_adapter_response,
    uncertain_result,
)
from .frappe_validation import service_actor_scope
from .worker_repository import (
    FrappeEngineeringChangeWorkerRepository,
    SummaryWorkerOutcome,
)


_PROFILE_HOOK = "npi_engineering_change_profile_resolver"
_REGISTRY_HOOK = "npi_engineering_change_adapter_registry"
_INBOX_JOB = "npi_integration.engineering_change.worker.process_engineering_change_inbox"
_SUMMARY_JOB = "npi_integration.engineering_change.worker.execute_change_implementation_summary"


def process_engineering_change_inbox(receipt_id: str) -> dict[str, object]:
    identity = _uuid(receipt_id, "Engineering Change Inbox receipt")
    repository = FrappeEngineeringChangeWorkerRepository()
    route = repository.inbound_route(identity, _configured_profile)
    if route is None:
        return {"receiptId": str(identity), "state": "not_claimed"}
    try:
        with service_actor_scope(route.service_actor_user_id):
            claim = repository.claim_inbound(route, now=datetime.now(UTC))
            if claim is None:
                _rollback_safely()
                return {"receiptId": str(identity), "state": "not_claimed"}
            _commit_or_raise("ENGINEERING_CHANGE_INBOUND_CLAIM_COMMIT_FAILED", route.trace_id)
            return _apply_inbound_observation(repository, claim)
    except Exception as error:
        _rollback_safely()
        _record("ENGINEERING_CHANGE_INBOUND_WORKER_FAILED", error, route.trace_id)
        return {"receiptId": str(identity), "state": "failed_closed"}


def execute_change_implementation_summary(event_id: str) -> dict[str, object]:
    identity = _uuid(event_id, "Engineering Change summary event")
    repository = FrappeEngineeringChangeWorkerRepository()
    route = repository.summary_route(identity, _configured_profile)
    if route is None:
        return {"outboxEventId": str(identity), "state": "not_claimed"}
    try:
        with service_actor_scope(route.service_actor_user_id):
            claim = repository.claim_summary(route, now=datetime.now(UTC))
            if claim is None:
                _rollback_safely()
                return {"outboxEventId": str(identity), "state": "not_claimed"}
            _commit_or_raise("ENGINEERING_CHANGE_SUMMARY_CLAIM_COMMIT_FAILED", route.trace_id)
            if claim.recovered_after_adapter_boundary:
                result = uncertain_result(
                    response_hash=canonical_hash(
                        {
                            "attemptGlobalId": str(claim.command.attempt_global_id),
                            "outcome": "recovered_after_adapter_boundary",
                        }
                    ),
                    observed_at=datetime.now(UTC),
                )
            else:
                try:
                    profile = repository.require_execution_profile(
                        claim,
                        _configured_profile(
                            route.tenant_id, route.project_global_id
                        ),
                    )
                    registry = _configured_registry()
                    adapter = (
                        registry.resolve(profile) if registry is not None else None
                    )
                except Exception as error:
                    _record(
                        "ENGINEERING_CHANGE_SUMMARY_PROFILE_UNAVAILABLE",
                        error,
                        route.trace_id,
                    )
                    profile = None
                    adapter = None
                if adapter is None:
                    result = _failed_before_boundary(claim, datetime.now(UTC))
                else:
                    if not repository.mark_adapter_boundary(claim, now=datetime.now(UTC)):
                        raise RuntimeError("Engineering Change adapter boundary could not be sealed.")
                    _commit_or_raise(
                        "ENGINEERING_CHANGE_SUMMARY_BOUNDARY_COMMIT_FAILED",
                        route.trace_id,
                    )
                    try:
                        result = classify_adapter_response(
                            adapter(claim.command), observed_at=datetime.now(UTC)
                        )
                        if (
                            profile is not None
                            and profile.target_mode is TargetMode.SYNTHETIC
                            and result.state is SummaryState.SUCCEEDED
                        ):
                            result = replace(
                                result, state=SummaryState.SYNTHETIC_VERIFIED
                            )
                    except Exception as error:
                        _rollback_safely()
                        _record(
                            "ENGINEERING_CHANGE_SUMMARY_OUTCOME_UNCERTAIN",
                            error,
                            route.trace_id,
                        )
                        result = uncertain_result(
                            response_hash=canonical_hash(
                                {
                                    "attemptGlobalId": str(
                                        claim.command.attempt_global_id
                                    ),
                                    "outcome": "adapter_exception_after_boundary",
                                }
                            ),
                            observed_at=datetime.now(UTC),
                        )
            outcome = repository.seal_result(
                claim, result=result, now=datetime.now(UTC)
            )
            _commit_or_raise("ENGINEERING_CHANGE_SUMMARY_RESULT_COMMIT_FAILED", route.trace_id)
            return _summary_response(outcome)
    except Exception as error:
        _rollback_safely()
        _record("ENGINEERING_CHANGE_SUMMARY_WORKER_FAILED", error, route.trace_id)
        return {"outboxEventId": str(identity), "state": "failed_closed"}


def recover_engineering_change_work() -> int:
    """Requeue only pending or expired work; terminal/uncertain rows stay still."""

    repository = FrappeEngineeringChangeWorkerRepository()
    now = datetime.now(UTC)
    queued = 0
    for receipt_id in repository.recoverable_inbox_ids(now=now):
        if _enqueue(_INBOX_JOB, "engineering-change-inbox", "receipt_id", receipt_id):
            queued += 1
    for event_id in repository.recoverable_summary_ids(now=now):
        if _enqueue(_SUMMARY_JOB, "engineering-change-summary", "event_id", event_id):
            queued += 1
    return queued


def _apply_inbound_observation(repository, claim) -> dict[str, object]:
    event = claim.event
    core = FrappeChangeControlRepository(
        principal=Principal(
            user_id=claim.route.service_actor_user_id,
            roles=frozenset({"NPI API User", "System Manager"}),
            project_access={str(event.project_global_id): ProjectAccess.ADMINISTER},
            tenant_id=event.tenant_id,
        ),
        request_id=str(event.event_id),
        trace_id=event.trace_id,
    )
    try:
        detail = core.get_change(event.project_global_id, event.change_global_id)
        if detail is None:
            raise RuntimeError("Engineering Change target is unavailable.")
        detail = validate_change_detail_response(
            detail,
            project_global_id=str(event.project_global_id),
            change_global_id=str(event.change_global_id),
        )
        current = detail["currentRevision"]
        observed = event.observation.payload()
        if current["formalChange"] == observed:
            revision_id = UUID(str(current["globalId"]))
            snapshot_hash = str(current["snapshotHash"])
        else:
            outcome = core.link_formal_observation(
                event.project_global_id,
                event.change_global_id,
                idempotency_key_hash=canonical_hash(
                    {"engineeringChangeEventId": str(event.event_id)}
                ),
                expected_revision=int(current["revision"]),
                expected_revision_global_id=UUID(str(current["globalId"])),
                expected_revision_snapshot_hash=str(current["snapshotHash"]),
                formal_change=parse_formal_observation(observed),
            )
            if outcome is None:
                raise RuntimeError("Engineering Change observation was not applied.")
            response = validate_change_command_response(
                "engineering_change.link_formal_observation",
                outcome.response,
                project_global_id=str(event.project_global_id),
                change_global_id=str(event.change_global_id),
            )
            revision_id = UUID(str(response["currentRevision"]["globalId"]))
            snapshot_hash = str(response["currentRevision"]["snapshotHash"])
        if not repository.finish_inbound(
            claim,
            state="succeeded",
            observation_revision_global_id=revision_id,
            observation_snapshot_hash=snapshot_hash,
            safe_error_code=None,
            now=datetime.now(UTC),
        ):
            raise RuntimeError("Engineering Change Inbox claim changed during apply.")
        _commit_or_raise(
            "ENGINEERING_CHANGE_INBOUND_RESULT_COMMIT_FAILED", claim.route.trace_id
        )
        return {
            "receiptId": str(claim.route.receipt_id),
            "state": "succeeded",
            "observationRevisionGlobalId": str(revision_id),
        }
    except (NpiProblem, VersionConflict, ValueError) as error:
        return _finish_inbound_failure(repository, claim, error, retryable=False)
    except Exception as error:
        return _finish_inbound_failure(repository, claim, error, retryable=True)


def _finish_inbound_failure(repository, claim, error: Exception, *, retryable: bool):
    _rollback_safely()
    code = (
        "ENGINEERING_CHANGE_INBOUND_RETRYABLE"
        if retryable
        else "ENGINEERING_CHANGE_INBOUND_REJECTED"
    )
    _record(code, error, claim.route.trace_id)
    if not repository.finish_inbound(
        claim,
        state="failed_retryable" if retryable else "failed_final",
        observation_revision_global_id=None,
        observation_snapshot_hash=None,
        safe_error_code=code,
        now=datetime.now(UTC),
    ):
        raise RuntimeError("Engineering Change Inbox failure could not be sealed.")
    _commit_or_raise("ENGINEERING_CHANGE_INBOUND_FAILURE_COMMIT_FAILED", claim.route.trace_id)
    return {"receiptId": str(claim.route.receipt_id), "state": "failed_retryable" if retryable else "failed_final"}


def _failed_before_boundary(claim, observed_at: datetime):
    from .domain import ClassifiedResult

    return ClassifiedResult(
        SummaryState.FAILED_FINAL,
        FaultKind.TARGET_UNAVAILABLE,
        RetryDirective.MANUAL_CORRECTION,
        canonical_hash(
            {
                "attemptGlobalId": str(claim.command.attempt_global_id),
                "outcome": "adapter_unavailable_before_boundary",
            }
        ),
        observed_at,
        False,
        False,
    )


def _configured_profile(
    tenant_id: str, project_id: UUID
) -> IntegrationProfile | None:
    resolver = _single_hook(_PROFILE_HOOK)
    value = resolver(tenant_id, str(project_id)) if resolver is not None else None
    return value if isinstance(value, IntegrationProfile) else None


def _configured_registry() -> AdapterRegistry | None:
    resolver = _single_hook(_REGISTRY_HOOK)
    value = resolver() if resolver is not None else None
    return value if isinstance(value, AdapterRegistry) else None


def _single_hook(name: str) -> Callable[..., object] | None:
    values = frappe.get_hooks(name)
    hooks = [values] if isinstance(values, str) else list(values or ())
    if not hooks:
        return None
    if len(hooks) != 1 or not isinstance(hooks[0], str):
        raise RuntimeError("Engineering Change integration hook is ambiguous.")
    resolver = frappe.get_attr(hooks[0])
    if not callable(resolver):
        raise RuntimeError("Engineering Change integration hook is invalid.")
    return resolver


def _enqueue(job: str, prefix: str, argument: str, identity: UUID) -> bool:
    try:
        frappe.enqueue(
            job,
            queue="short",
            enqueue_after_commit=False,
            deduplicate=True,
            job_id=f"{prefix}-{identity}",
            **{argument: str(identity)},
        )
    except Exception as error:
        _record(f"{prefix.upper().replace('-', '_')}_RECOVERY_ENQUEUE_FAILED", error, str(identity))
        return False
    return True


def _summary_response(outcome: SummaryWorkerOutcome) -> dict[str, object]:
    return {
        "outboxEventId": str(outcome.event_id),
        "requestGlobalId": str(outcome.request_global_id),
        "state": outcome.state,
        "resultGlobalId": str(outcome.result_global_id),
    }


def _uuid(value: object, label: str) -> UUID:
    try:
        result = UUID(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} ID is invalid.") from error
    if str(result) != str(value):
        raise ValueError(f"{label} ID is invalid.")
    return result


def _commit_or_raise(code: str, trace_id: str) -> None:
    try:
        frappe.db.commit()
    except Exception as error:
        _rollback_safely()
        _record(code, error, trace_id)
        raise


def _rollback_safely() -> None:
    try:
        frappe.db.rollback()
    except Exception:
        pass


def _record(code: str, error: Exception, trace_id: str) -> None:
    record_safe_diagnostic(
        code=code,
        title="NPI Engineering Change integration worker failed",
        exception_type=type(error).__name__,
        trace_id=trace_id,
    )
