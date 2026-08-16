from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import frappe

from npi_core.api import record_safe_diagnostic

from .config import InboundProjectProfile
from .worker_repository import (
    FrappeInboundProjectWorkerRepository,
    InboundProjectFinalFailure,
    InboundProjectWorkerOutcome,
)


_PROFILE_RESOLVER_HOOK = "npi_inbound_project_profile_resolver"
_JOB_PATH = "npi_integration.inbound_project.worker.process_inbox_message"


def process_inbox_message(receipt_id: str) -> dict[str, object]:
    """Process one receipt outside the webhook request and inside bounded leases."""
    try:
        parsed_receipt_id = UUID(str(receipt_id))
    except (TypeError, ValueError) as error:
        raise ValueError("Inbound Project receipt ID is invalid.") from error
    outcome = _execute_worker(
        receipt_id=parsed_receipt_id,
        repository=FrappeInboundProjectWorkerRepository(),
        profile_resolver=_configured_profile,
        clock=lambda: datetime.now(UTC),
    )
    if outcome is None:
        return {"receiptId": str(parsed_receipt_id), "state": "not_claimed"}
    result: dict[str, object] = {
        "receiptId": str(outcome.receipt_id),
        "state": outcome.state,
        "disposition": outcome.disposition,
    }
    if outcome.project_global_id is not None:
        result["projectGlobalId"] = str(outcome.project_global_id)
        result["replayed"] = outcome.replayed
    return result


def recover_inbound_project_receipts() -> int:
    """Requeue only bounded pending or expired P8-02 claims; no generic replay."""
    repository = FrappeInboundProjectWorkerRepository()
    receipt_ids = repository.recoverable_receipt_ids(now=datetime.now(UTC))
    queued = 0
    for receipt_id in receipt_ids:
        try:
            _enqueue(receipt_id)
        except Exception as error:
            _record_failure(
                "INBOUND_PROJECT_RECOVERY_ENQUEUE_FAILED",
                error,
                f"inbound-recovery-{receipt_id}",
            )
        else:
            queued += 1
    return queued


def _execute_worker(
    *,
    receipt_id: UUID,
    repository: FrappeInboundProjectWorkerRepository,
    profile_resolver: Callable[[], InboundProjectProfile | None],
    clock: Callable[[], datetime],
) -> InboundProjectWorkerOutcome | None:
    now = clock()
    claim = repository.claim(receipt_id, now=now)
    if claim is None:
        _rollback_safely()
        return None
    _commit_claim(claim.trace_id)

    try:
        try:
            profile = profile_resolver()
        except Exception as error:
            raise InboundProjectFinalFailure(
                "INBOUND_PROJECT_PROFILE_UNAVAILABLE"
            ) from error
        outcome = repository.process_claim(claim, profile=profile, now=clock())
    except InboundProjectFinalFailure as error:
        _rollback_safely()
        return _persist_failure(
            repository=repository,
            claim=claim,
            code=error.code,
            retryable=False,
            now=clock(),
            error=error,
        )
    except Exception as error:
        _rollback_safely()
        return _persist_failure(
            repository=repository,
            claim=claim,
            code="INBOUND_PROJECT_UNEXPECTED_WORKER_FAILURE",
            retryable=True,
            now=clock(),
            error=error,
        )
    try:
        frappe.db.commit()
    except Exception as error:
        # A commit error has an ambiguous outcome. Do not overwrite a possibly
        # committed success; an uncommitted claim will expire and be recovered.
        _rollback_safely()
        _record_failure(
            "INBOUND_PROJECT_RESULT_COMMIT_FAILED", error, claim.trace_id
        )
        raise
    return outcome


def _persist_failure(
    *,
    repository: FrappeInboundProjectWorkerRepository,
    claim: Any,
    code: str,
    retryable: bool,
    now: datetime,
    error: Exception,
) -> InboundProjectWorkerOutcome:
    _record_failure(code, error, claim.trace_id)
    marked = repository.mark_failure(
        claim,
        code=code,
        retryable=retryable,
        now=now,
    )
    if not marked:
        _rollback_safely()
        raise RuntimeError("Inbound Project claim could not be failed safely.")
    try:
        frappe.db.commit()
    except Exception as commit_error:
        _rollback_safely()
        _record_failure(
            "INBOUND_PROJECT_FAILURE_COMMIT_FAILED",
            commit_error,
            claim.trace_id,
        )
        raise
    state = "failed_retryable" if retryable else "failed_final"
    return InboundProjectWorkerOutcome(
        receipt_id=claim.receipt_id,
        state=state,
        disposition=state,
    )


def _commit_claim(trace_id: str) -> None:
    try:
        frappe.db.commit()
    except Exception as error:
        _rollback_safely()
        _record_failure("INBOUND_PROJECT_CLAIM_COMMIT_FAILED", error, trace_id)
        raise


def _configured_profile() -> InboundProjectProfile | None:
    hooks = frappe.get_hooks(_PROFILE_RESOLVER_HOOK)
    values = [hooks] if isinstance(hooks, str) else list(hooks or ())
    if not values:
        return None
    if len(values) != 1 or not isinstance(values[0], str):
        raise RuntimeError("Inbound Project profile resolver hook is ambiguous.")
    resolver = frappe.get_attr(values[0])
    if not callable(resolver):
        raise RuntimeError("Inbound Project profile resolver hook is invalid.")
    profile = resolver()
    return profile if isinstance(profile, InboundProjectProfile) else None


def _enqueue(receipt_id: UUID) -> None:
    frappe.enqueue(
        _JOB_PATH,
        queue="short",
        enqueue_after_commit=False,
        deduplicate=True,
        job_id=f"inbound-project-{receipt_id}",
        receipt_id=str(receipt_id),
    )


def _record_failure(code: str, error: Exception, trace_id: str) -> None:
    record_safe_diagnostic(
        code=code,
        title="NPI inbound Project worker failure",
        exception_type=type(error).__name__,
        trace_id=trace_id,
    )


def _rollback_safely() -> None:
    try:
        frappe.db.rollback()
    except Exception:
        pass
