from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import frappe

from npi_core.api import record_safe_diagnostic

from .adapters import (
    ItemAdapterRegistry,
    classify_item_adapter_response,
    failed_before_adapter_boundary_result,
    uncertain_item_adapter_result,
)
from .config import ItemExecutionProfile
from .worker_repository import (
    FrappeItemPublishWorkerRepository,
    ItemPublishWorkerFinalFailure,
    ItemPublishWorkerOutcome,
)


_PROFILE_RESOLVER_HOOK = "npi_item_publish_profile_resolver"
_ADAPTER_REGISTRY_HOOK = "npi_item_publish_adapter_registry"
_JOB_PATH = "npi_integration.item_publish.worker.process_outbox_message"


def process_outbox_message(outbox_event_id: str) -> dict[str, object]:
    """Process one operation-specific Item Outbox message outside the request."""
    try:
        parsed_event_id = UUID(str(outbox_event_id))
    except (TypeError, ValueError) as error:
        raise ValueError("Item Outbox event ID is invalid.") from error
    outcome = _execute_worker(
        outbox_event_id=parsed_event_id,
        repository=FrappeItemPublishWorkerRepository(),
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
        "mappingAdvanced": outcome.mapping_advanced,
    }
    if outcome.result_global_id is not None:
        result["resultGlobalId"] = str(outcome.result_global_id)
    return result


def recover_item_publish_outbox_messages() -> int:
    """Requeue only bounded pending/expired P8-03 work; never terminal replay."""
    repository = FrappeItemPublishWorkerRepository()
    event_ids = repository.recoverable_outbox_event_ids(now=datetime.now(UTC))
    queued = 0
    for event_id in event_ids:
        try:
            _enqueue(event_id)
        except Exception as error:
            _record_failure(
                "ITEM_PUBLISH_RECOVERY_ENQUEUE_FAILED",
                error,
                f"item-publish-recovery-{event_id}",
            )
        else:
            queued += 1
    return queued


def _execute_worker(
    *,
    outbox_event_id: UUID,
    repository: FrappeItemPublishWorkerRepository,
    profile_resolver: Callable[[str, UUID], ItemExecutionProfile | None],
    registry_resolver: Callable[[], ItemAdapterRegistry | None],
    clock: Callable[[], datetime],
) -> ItemPublishWorkerOutcome | None:
    claim = repository.claim(outbox_event_id, now=clock())
    if claim is None:
        _rollback_safely()
        return None
    _commit_or_raise("ITEM_PUBLISH_CLAIM_COMMIT_FAILED", claim.trace_id)

    if claim.recovered_after_adapter_boundary:
        result = uncertain_item_adapter_result(
            command=claim.command,
            observed_at=clock(),
            safe_error_code="ITEM_PUBLISH_RECOVERED_AFTER_ADAPTER_BOUNDARY",
        )
        outcome = repository.seal_result(
            claim,
            profile=None,
            result=result,
            now=clock(),
        )
        _commit_or_raise("ITEM_PUBLISH_RESULT_COMMIT_FAILED", claim.trace_id)
        return outcome

    profile: ItemExecutionProfile | None = None
    try:
        profile = repository.require_execution_profile(
            claim,
            profile_resolver(claim.tenant_id, claim.project_global_id),
        )
        registry = registry_resolver()
        adapter = (
            registry.resolve(profile)
            if isinstance(registry, ItemAdapterRegistry)
            else None
        )
        if adapter is None:
            raise ItemPublishWorkerFinalFailure(
                "ITEM_PUBLISH_ADAPTER_UNAVAILABLE"
            )
    except ItemPublishWorkerFinalFailure as error:
        _rollback_safely()
        result = failed_before_adapter_boundary_result(
            command=claim.command,
            observed_at=clock(),
            safe_error_code=error.code,
        )
        outcome = repository.seal_result(
            claim,
            profile=None,
            result=result,
            now=clock(),
        )
        _commit_or_raise("ITEM_PUBLISH_RESULT_COMMIT_FAILED", claim.trace_id)
        return outcome
    except Exception as error:
        _rollback_safely()
        _record_failure(
            "ITEM_PUBLISH_PROFILE_OR_REGISTRY_FAILED",
            error,
            claim.trace_id,
        )
        result = failed_before_adapter_boundary_result(
            command=claim.command,
            observed_at=clock(),
            safe_error_code="ITEM_PUBLISH_EXECUTION_CONFIGURATION_INVALID",
        )
        outcome = repository.seal_result(
            claim,
            profile=None,
            result=result,
            now=clock(),
        )
        _commit_or_raise("ITEM_PUBLISH_RESULT_COMMIT_FAILED", claim.trace_id)
        return outcome

    if not repository.mark_adapter_boundary(
        claim,
        profile=profile,
        now=clock(),
    ):
        _rollback_safely()
        raise RuntimeError("Item adapter boundary could not be sealed safely.")
    _commit_or_raise("ITEM_PUBLISH_BOUNDARY_COMMIT_FAILED", claim.trace_id)

    try:
        response = adapter(claim.command)
        classified = classify_item_adapter_response(
            profile=profile,
            command=claim.command,
            response=response,
            observed_at=clock(),
        )
    except Exception as error:
        _rollback_safely()
        _record_failure(
            "ITEM_PUBLISH_ADAPTER_OUTCOME_UNCERTAIN",
            error,
            claim.trace_id,
        )
        classified = uncertain_item_adapter_result(
            command=claim.command,
            observed_at=clock(),
            safe_error_code="ITEM_PUBLISH_ADAPTER_OUTCOME_UNCERTAIN",
        )
    outcome = repository.seal_result(
        claim,
        profile=profile,
        result=classified,
        now=clock(),
    )
    _commit_or_raise("ITEM_PUBLISH_RESULT_COMMIT_FAILED", claim.trace_id)
    return outcome


def _configured_profile(
    tenant_id: str,
    project_id: UUID,
) -> ItemExecutionProfile | None:
    resolver = _single_hook(_PROFILE_RESOLVER_HOOK)
    if resolver is None:
        return None
    profile = resolver(tenant_id, str(project_id))
    return profile if isinstance(profile, ItemExecutionProfile) else None


def _configured_registry() -> ItemAdapterRegistry | None:
    resolver = _single_hook(_ADAPTER_REGISTRY_HOOK)
    if resolver is None:
        return None
    registry = resolver()
    return registry if isinstance(registry, ItemAdapterRegistry) else None


def _single_hook(name: str) -> Callable[..., object] | None:
    hooks = frappe.get_hooks(name)
    values = [hooks] if isinstance(hooks, str) else list(hooks or ())
    if not values:
        return None
    if len(values) != 1 or not isinstance(values[0], str):
        raise RuntimeError("The Item execution hook is ambiguous.")
    resolver = frappe.get_attr(values[0])
    if not callable(resolver):
        raise RuntimeError("The Item execution hook is invalid.")
    return resolver


def _enqueue(outbox_event_id: UUID) -> None:
    frappe.enqueue(
        _JOB_PATH,
        queue="short",
        enqueue_after_commit=False,
        deduplicate=True,
        job_id=f"item-publish-{outbox_event_id}",
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
        title="NPI Item publish worker failure",
        exception_type=type(error).__name__,
        trace_id=trace_id,
    )


def _rollback_safely() -> None:
    try:
        frappe.db.rollback()
    except Exception:
        pass
