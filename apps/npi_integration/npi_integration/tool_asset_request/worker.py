from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import frappe

from npi_core.api import record_safe_diagnostic

from .adapters import (
    ToolAssetAdapterRegistry,
    classify_tool_asset_adapter_response,
    failed_before_tool_asset_adapter_boundary_result,
    uncertain_tool_asset_adapter_result,
)
from .config import ToolAssetExecutionProfile
from .execution_frappe_validation import ToolAssetServiceActorUnavailable, tool_asset_service_actor_scope
from .worker_repository import FrappeToolAssetWorkerRepository, ToolAssetWorkerFinalFailure, ToolAssetWorkerOutcome


_PROFILE_RESOLVER_HOOK = "npi_tool_asset_execution_profile_resolver"
_ADAPTER_REGISTRY_HOOK = "npi_tool_asset_adapter_registry"
_JOB_PATH = "npi_integration.tool_asset_request.worker.process_outbox_message"


def process_outbox_message(outbox_event_id: str) -> dict[str, object]:
    try:
        parsed = UUID(str(outbox_event_id))
    except (TypeError, ValueError) as error:
        raise ValueError("Tool Asset Outbox event ID is invalid.") from error
    outcome = _execute_worker(outbox_event_id=parsed, repository=FrappeToolAssetWorkerRepository(), profile_resolver=_configured_profile, registry_resolver=_configured_registry, clock=lambda: datetime.now(UTC))
    if outcome is None:
        return {"outboxEventId": str(parsed), "state": "not_claimed"}
    return {"outboxEventId": str(outcome.outbox_event_id), "requestGlobalId": str(outcome.request_global_id), "resultGlobalId": str(outcome.result_global_id), "state": outcome.state, "disposition": outcome.disposition, "mappingAdvanced": outcome.mapping_advanced}


def recover_tool_asset_outbox_messages() -> int:
    repository = FrappeToolAssetWorkerRepository()
    queued = 0
    for event_id in repository.recoverable_outbox_event_ids(now=datetime.now(UTC)):
        try:
            _enqueue(event_id)
        except Exception as error:
            _record_failure("TOOL_ASSET_RECOVERY_ENQUEUE_FAILED", error, f"tool-asset-recovery-{event_id}")
        else:
            queued += 1
    return queued


def _execute_worker(*, outbox_event_id: UUID, repository, profile_resolver: Callable[[str, UUID], ToolAssetExecutionProfile | None], registry_resolver: Callable[[], ToolAssetAdapterRegistry | None], clock: Callable[[], datetime]) -> ToolAssetWorkerOutcome | None:
    try:
        route = repository.execution_route(outbox_event_id)
    except Exception as error:
        _rollback_safely()
        _record_failure("TOOL_ASSET_EXECUTION_ROUTE_INVALID", error, str(outbox_event_id))
        return None
    try:
        with tool_asset_service_actor_scope(route.service_actor_user_id):
            claim = repository.claim(outbox_event_id, now=clock(), expected_route=route)
            if claim is None:
                _rollback_safely()
                return None
            _commit_or_raise("TOOL_ASSET_CLAIM_COMMIT_FAILED", claim.trace_id)
            if claim.recovered_after_adapter_boundary:
                result = uncertain_tool_asset_adapter_result(command=claim.command, safe_error_code="TOOL_ASSET_RECOVERED_AFTER_ADAPTER_BOUNDARY")
                return _persist(repository, claim, profile=None, result=result, now=clock())
            try:
                profile = repository.require_execution_profile(claim, profile_resolver(claim.tenant_id, claim.project_global_id))
                registry = registry_resolver()
                adapter = registry.resolve(profile, claim.request.operation) if isinstance(registry, ToolAssetAdapterRegistry) else None
                if adapter is None:
                    raise ToolAssetWorkerFinalFailure("TOOL_ASSET_ADAPTER_UNAVAILABLE")
            except ToolAssetWorkerFinalFailure as error:
                _rollback_safely()
                result = failed_before_tool_asset_adapter_boundary_result(command=claim.command, safe_error_code=error.code)
                return _persist(repository, claim, profile=None, result=result, now=clock())
            except Exception as error:
                _rollback_safely()
                _record_failure("TOOL_ASSET_PROFILE_OR_REGISTRY_FAILED", error, claim.trace_id)
                result = failed_before_tool_asset_adapter_boundary_result(command=claim.command, safe_error_code="TOOL_ASSET_EXECUTION_CONFIGURATION_INVALID")
                return _persist(repository, claim, profile=None, result=result, now=clock())
            if not repository.mark_adapter_boundary(claim, profile=profile, now=clock()):
                _rollback_safely()
                raise RuntimeError("Tool Asset adapter boundary could not be sealed safely.")
            _commit_or_raise("TOOL_ASSET_BOUNDARY_COMMIT_FAILED", claim.trace_id)
            try:
                response = adapter(claim.command)
                result = classify_tool_asset_adapter_response(profile=profile, command=claim.command, response=response, observed_at=clock())
            except Exception as error:
                _rollback_safely()
                _record_failure("TOOL_ASSET_ADAPTER_OUTCOME_UNCERTAIN", error, claim.trace_id)
                result = uncertain_tool_asset_adapter_result(command=claim.command, safe_error_code="TOOL_ASSET_ADAPTER_OUTCOME_UNCERTAIN")
            return _persist(repository, claim, profile=profile, result=result, now=clock())
    except ToolAssetServiceActorUnavailable as error:
        _rollback_safely()
        _record_failure("TOOL_ASSET_SERVICE_ACTOR_UNAVAILABLE", error, str(outbox_event_id))
        return None


def _persist(repository, claim, *, profile, result, now):
    committed = False
    try:
        outcome = repository.seal_result(claim, profile=profile, result=result, now=now)
        committed = True
        _commit_or_raise("TOOL_ASSET_RESULT_COMMIT_FAILED", claim.trace_id)
        return outcome
    except Exception as first_error:
        if not committed:
            _rollback_safely()
            _record_failure("TOOL_ASSET_RESULT_PERSISTENCE_FAILED", first_error, claim.trace_id)
        recover = getattr(repository, "recover_or_seal_result", None)
        if not callable(recover):
            raise
        outcome = recover(claim, profile=profile, result=result, now=now)
        _commit_or_raise("TOOL_ASSET_RESULT_RECOVERY_COMMIT_FAILED", claim.trace_id)
        return outcome


def _configured_profile(tenant_id: str, project_id: UUID) -> ToolAssetExecutionProfile | None:
    resolver = _single_hook(_PROFILE_RESOLVER_HOOK)
    value = resolver(tenant_id, str(project_id)) if resolver else None
    return value if isinstance(value, ToolAssetExecutionProfile) else None


def _configured_registry() -> ToolAssetAdapterRegistry | None:
    resolver = _single_hook(_ADAPTER_REGISTRY_HOOK)
    value = resolver() if resolver else None
    return value if isinstance(value, ToolAssetAdapterRegistry) else None


def _single_hook(name: str):
    values = tuple(frappe.get_hooks(name) or ())
    if len(values) != 1 or not isinstance(values[0], str):
        return None
    value = frappe.get_attr(values[0])
    return value if callable(value) else None


def _enqueue(event_id: UUID) -> None:
    frappe.enqueue(_JOB_PATH, queue="short", job_id=f"tool-asset-{event_id}", enqueue_after_commit=True, outbox_event_id=str(event_id))


def _commit_or_raise(code: str, trace_id: str) -> None:
    try:
        frappe.db.commit()
    except Exception as error:
        _rollback_safely()
        _record_failure(code, error, trace_id)
        raise


def _record_failure(code: str, error: Exception, trace_id: str) -> None:
    record_safe_diagnostic(code=code, title="NPI Tool Asset worker failed", exception_type=type(error).__name__, trace_id=trace_id)


def _rollback_safely() -> None:
    try:
        frappe.db.rollback()
    except Exception:
        pass
