from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import frappe

from npi_core.documents.frappe_repository import _database_datetime
from npi_core.foundation.audit import create_audit_event

from .adapters import AdapterCommand
from .config import IntegrationProfile
from .domain import (
    ClassifiedResult,
    ExecutionProfileReference,
    SummaryState,
    TargetMode,
    canonical_hash,
    parse_inbound_event,
)
from .frappe_validation import (
    inbound_transaction_write,
    summary_claim_write,
    summary_result_write,
)


CLAIM_LEASE_SECONDS = 300
RECOVERY_BATCH_LIMIT = 100


def deterministic_summary_result_id(attempt_global_id: UUID) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"npi.change-implementation-summary.result.v1:{attempt_global_id}",
    )


@dataclass(frozen=True, slots=True)
class InboundExecutionRoute:
    receipt_id: UUID
    tenant_id: str
    project_global_id: UUID
    service_actor_user_id: str
    profile_reference: ExecutionProfileReference
    trace_id: str


@dataclass(frozen=True, slots=True)
class ClaimedInboundEvent:
    route: InboundExecutionRoute
    claim_token: UUID
    event: object


@dataclass(frozen=True, slots=True)
class SummaryExecutionRoute:
    event_id: UUID
    request_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    service_actor_user_id: str
    profile_reference: ExecutionProfileReference
    trace_id: str


@dataclass(frozen=True, slots=True)
class ClaimedSummary:
    route: SummaryExecutionRoute
    claim_token: UUID
    command: AdapterCommand
    recovered_after_adapter_boundary: bool


@dataclass(frozen=True, slots=True)
class SummaryWorkerOutcome:
    event_id: UUID
    request_global_id: UUID
    state: str
    result_global_id: UUID


class FrappeEngineeringChangeWorkerRepository:
    """Operation-specific P9-01C worker persistence; no generic writer seam."""

    def inbound_route(
        self,
        receipt_id: UUID,
        profile_resolver: Callable[[str, UUID], IntegrationProfile | None],
    ) -> InboundExecutionRoute | None:
        row = _optional_doc("NPI Engineering Change Inbox", receipt_id)
        if row is None or str(_value(row, "state")) not in {
            "pending",
            "processing",
            "failed_retryable",
        }:
            return None
        try:
            tenant_id = str(row.tenant_id)
            project_id = UUID(str(row.project_global_id))
            profile = profile_resolver(tenant_id, project_id)
            if not isinstance(profile, IntegrationProfile):
                return None
            if (
                profile.target_mode is TargetMode.DISABLED
                or profile.tenant_id != tenant_id
                or profile.project_global_id != str(project_id)
                or profile.reference
                != ExecutionProfileReference(
                    str(row.profile_id),
                    int(row.profile_version),
                    profile.target_mode,
                    str(row.profile_snapshot_hash),
                )
            ):
                return None
            return InboundExecutionRoute(
                receipt_id=receipt_id,
                tenant_id=tenant_id,
                project_global_id=project_id,
                service_actor_user_id=profile.service_actor_user_id,
                profile_reference=profile.reference,
                trace_id=str(row.trace_id),
            )
        except (TypeError, ValueError):
            return None

    def claim_inbound(
        self,
        route: InboundExecutionRoute,
        *,
        now: datetime,
    ) -> ClaimedInboundEvent | None:
        row = _optional_doc("NPI Engineering Change Inbox", route.receipt_id, lock=True)
        if row is None or not _inbound_route_matches(row, route):
            return None
        state = str(row.state)
        if state == "processing":
            expires = _aware(row.lease_expires_at)
            if _utc(now) < expires:
                return None
        elif state not in {"pending", "failed_retryable"}:
            return None
        event = parse_inbound_event(str(row.event_snapshot).encode("utf-8"))
        if (
            str(event.event_id) != str(row.event_id)
            or str(event.project_global_id) != str(row.project_global_id)
            or str(event.change_global_id) != str(row.change_global_id)
            or canonical_hash(event.envelope()) != str(row.canonical_event_hash)
        ):
            raise RuntimeError("Persisted Engineering Change event binding is invalid.")
        token = uuid4()
        claimed = _utc(now)
        with inbound_transaction_write(route.service_actor_user_id):
            row.state = "processing"
            row.claim_token = str(token)
            row.claimed_at = _database_datetime(claimed)
            row.lease_expires_at = _database_datetime(
                claimed + timedelta(seconds=CLAIM_LEASE_SECONDS)
            )
            row.attempt_count = int(row.attempt_count or 0) + 1
            row.last_error_code = None
            row.last_error_at = None
            row.save()
            _append_audit(
                actor=route.service_actor_user_id,
                trace_id=route.trace_id,
                operation="engineering_change.integration.claim",
                global_id=event.change_global_id,
                version=event.object_version,
                result="processing",
                summary={"eventId": str(event.event_id)},
            )
        return ClaimedInboundEvent(route, token, event)

    def finish_inbound(
        self,
        claim: ClaimedInboundEvent,
        *,
        state: str,
        observation_revision_global_id: UUID | None,
        observation_snapshot_hash: str | None,
        safe_error_code: str | None,
        now: datetime,
    ) -> bool:
        if state not in {"succeeded", "failed_retryable", "failed_final"}:
            raise ValueError("Inbound terminal state is invalid.")
        row = _optional_doc("NPI Engineering Change Inbox", claim.route.receipt_id, lock=True)
        if row is None or not _current_inbound_claim(row, claim):
            return False
        with inbound_transaction_write(claim.route.service_actor_user_id):
            row.state = state
            row.claim_token = None
            row.claimed_at = None
            row.lease_expires_at = None
            row.last_error_code = safe_error_code
            row.last_error_at = (
                _database_datetime(_utc(now)) if safe_error_code is not None else None
            )
            row.observation_revision_global_id = (
                str(observation_revision_global_id)
                if observation_revision_global_id is not None
                else None
            )
            row.observation_snapshot_hash = observation_snapshot_hash
            row.save()
            _append_audit(
                actor=claim.route.service_actor_user_id,
                trace_id=claim.route.trace_id,
                operation="engineering_change.integration.observe",
                global_id=claim.event.change_global_id,
                version=claim.event.object_version,
                result=state,
                summary={
                    "eventId": str(claim.event.event_id),
                    "safeErrorCode": safe_error_code,
                },
            )
        return True

    def summary_route(
        self,
        event_id: UUID,
        profile_resolver: Callable[[str, UUID], IntegrationProfile | None],
    ) -> SummaryExecutionRoute | None:
        outbox = _optional_doc("NPI Engineering Change Summary Outbox", event_id)
        if outbox is None or str(outbox.state) not in {"pending", "processing"}:
            return None
        request = _optional_doc(
            "NPI Engineering Change Summary Request",
            UUID(str(outbox.request_global_id)),
        )
        if request is None or not _summary_binding(outbox, request):
            return None
        try:
            tenant_id = str(request.tenant_id)
            project_id = UUID(str(request.project_global_id))
            profile = profile_resolver(tenant_id, project_id)
            if (
                not isinstance(profile, IntegrationProfile)
                or profile.target_mode is TargetMode.DISABLED
                or profile.tenant_id != tenant_id
                or profile.project_global_id != str(project_id)
                or profile.profile_id != str(request.profile_id)
                or profile.profile_version != int(request.profile_version)
                or profile.reference.snapshot_hash
                != str(request.profile_snapshot_hash)
                or profile.service_actor_user_id
                != str(request.service_actor_user_id)
            ):
                return None
            return SummaryExecutionRoute(
                event_id=event_id,
                request_global_id=UUID(str(request.global_id)),
                tenant_id=tenant_id,
                project_global_id=project_id,
                service_actor_user_id=str(request.service_actor_user_id),
                profile_reference=profile.reference,
                trace_id=str(request.trace_id),
            )
        except (TypeError, ValueError):
            return None

    def claim_summary(
        self,
        route: SummaryExecutionRoute,
        *,
        now: datetime,
    ) -> ClaimedSummary | None:
        outbox, request = _locked_summary(route)
        if outbox is None or request is None:
            return None
        state = str(outbox.state)
        recovered_after_boundary = False
        if state == "processing":
            if _utc(now) < _aware(outbox.lease_expires_at):
                return None
            recovered_after_boundary = bool(outbox.adapter_boundary_crossed)
        elif state != "pending":
            return None
        payload = _payload(outbox)
        attempt_number = int(outbox.attempt_count or 0) + (
            0 if recovered_after_boundary else 1
        )
        if recovered_after_boundary:
            attempt_id = UUID(str(outbox.last_attempt_global_id))
            token = UUID(str(outbox.claim_token))
            attempt = _optional_doc(
                "NPI Engineering Change Summary Attempt", attempt_id, lock=True
            )
            if attempt is None or not bool(attempt.adapter_boundary_crossed):
                raise RuntimeError("Persisted summary boundary evidence is invalid.")
        else:
            token = uuid4()
            attempt_id = uuid4()
        command = AdapterCommand(
            request_global_id=route.request_global_id,
            attempt_global_id=attempt_id,
            attempt_number=attempt_number,
            target_idempotency_key_hash=str(outbox.target_idempotency_key_hash),
            source_hash=str(outbox.source_hash),
            payload=payload,
        )
        claimed = _utc(now)
        with summary_claim_write(route.service_actor_user_id):
            if not recovered_after_boundary:
                frappe.get_doc(
                    {
                        "doctype": "NPI Engineering Change Summary Attempt",
                        "global_id": str(attempt_id),
                        "request_global_id": str(route.request_global_id),
                        "outbox_event_id": str(route.event_id),
                        "attempt_number": attempt_number,
                        "state": "started",
                        "adapter_boundary_crossed": 0,
                        "target_idempotency_key_hash": command.target_idempotency_key_hash,
                        "source_hash": command.source_hash,
                        "started_at": _database_datetime(claimed),
                    }
                ).insert()
                outbox.attempt_count = attempt_number
                outbox.last_attempt_global_id = str(attempt_id)
                outbox.claim_token = str(token)
                outbox.adapter_boundary_crossed = 0
            outbox.state = "processing"
            outbox.claimed_at = _database_datetime(claimed)
            outbox.lease_expires_at = _database_datetime(
                claimed + timedelta(seconds=CLAIM_LEASE_SECONDS)
            )
            outbox.last_error_code = None
            outbox.last_error_at = None
            outbox.save()
            request.state = "processing"
            request.updated_at = _database_datetime(claimed)
            request.save()
            _append_audit(
                actor=route.service_actor_user_id,
                trace_id=route.trace_id,
                operation="engineering_change.summary.claim",
                global_id=route.request_global_id,
                version=attempt_number,
                result="processing",
                summary={"outboxEventId": str(route.event_id)},
            )
        return ClaimedSummary(route, token, command, recovered_after_boundary)

    def require_execution_profile(
        self,
        claim: ClaimedSummary,
        profile: IntegrationProfile | None,
    ) -> IntegrationProfile:
        if (
            not isinstance(profile, IntegrationProfile)
            or profile.reference != claim.route.profile_reference
            or profile.tenant_id != claim.route.tenant_id
            or profile.project_global_id != str(claim.route.project_global_id)
            or profile.service_actor_user_id != claim.route.service_actor_user_id
            or profile.target_mode is TargetMode.DISABLED
        ):
            raise RuntimeError("Engineering Change execution profile is unavailable.")
        return profile

    def mark_adapter_boundary(
        self,
        claim: ClaimedSummary,
        *,
        now: datetime,
    ) -> bool:
        if claim.recovered_after_adapter_boundary:
            return False
        outbox, request, attempt = _current_summary_claim(claim)
        if outbox is None or request is None or attempt is None:
            return False
        with summary_claim_write(claim.route.service_actor_user_id):
            outbox.adapter_boundary_crossed = 1
            outbox.save()
            attempt.adapter_boundary_crossed = 1
            attempt.save()
            _append_audit(
                actor=claim.route.service_actor_user_id,
                trace_id=claim.route.trace_id,
                operation="engineering_change.summary.adapter_boundary",
                global_id=claim.route.request_global_id,
                version=claim.command.attempt_number,
                result="sealed",
                summary={"attemptGlobalId": str(claim.command.attempt_global_id)},
            )
        return True

    def seal_result(
        self,
        claim: ClaimedSummary,
        *,
        result: ClassifiedResult,
        now: datetime,
    ) -> SummaryWorkerOutcome:
        if not isinstance(result, ClassifiedResult):
            raise ValueError("Engineering Change result is invalid.")
        outbox, request, attempt = _current_summary_claim(claim)
        result_id = deterministic_summary_result_id(claim.command.attempt_global_id)
        existing = _optional_doc("NPI Engineering Change Summary Result", result_id)
        if existing is not None:
            if str(existing.result_hash) != canonical_hash(_result_snapshot(result)):
                raise RuntimeError("Persisted summary result identity is ambiguous.")
            return SummaryWorkerOutcome(
                claim.route.event_id,
                claim.route.request_global_id,
                str(existing.state),
                result_id,
            )
        if outbox is None or request is None or attempt is None:
            raise RuntimeError("Engineering Change summary claim is no longer current.")
        snapshot = _result_snapshot(result)
        observed = _utc(now)
        with summary_result_write(claim.route.service_actor_user_id):
            frappe.get_doc(
                {
                    "doctype": "NPI Engineering Change Summary Result",
                    "global_id": str(result_id),
                    "request_global_id": str(claim.route.request_global_id),
                    "outbox_event_id": str(claim.route.event_id),
                    "attempt_global_id": str(claim.command.attempt_global_id),
                    "state": result.state.value,
                    "fault_kind": result.fault.value,
                    "retry_directive": result.retry.value,
                    "response_hash": result.response_hash,
                    "response_authenticated": int(result.response_authenticated),
                    "response_contract_valid": int(result.response_contract_valid),
                    "retry_after_seconds": result.retry_after_seconds,
                    "observed_at": _database_datetime(observed),
                    "result_snapshot": _json(snapshot),
                    "result_hash": canonical_hash(snapshot),
                }
            ).insert()
            attempt.state = _attempt_state(result)
            attempt.completed_at = _database_datetime(observed)
            attempt.safe_error_code = (
                None if result.fault.value == "none" else result.fault.value
            )
            attempt.response_hash = result.response_hash
            attempt.save()
            for row in (outbox, request):
                row.state = result.state.value
                row.result_global_id = str(result_id)
                if row is outbox:
                    row.claim_token = None
                    row.claimed_at = None
                    row.lease_expires_at = None
                    row.last_error_code = (
                        None if result.fault.value == "none" else result.fault.value
                    )
                    row.last_error_at = (
                        None
                        if result.fault.value == "none"
                        else _database_datetime(observed)
                    )
                else:
                    row.updated_at = _database_datetime(observed)
                row.save()
            _append_audit(
                actor=claim.route.service_actor_user_id,
                trace_id=claim.route.trace_id,
                operation="engineering_change.summary.result",
                global_id=claim.route.request_global_id,
                version=claim.command.attempt_number,
                result=result.state.value,
                summary={
                    "faultKind": result.fault.value,
                    "retryDirective": result.retry.value,
                },
            )
        return SummaryWorkerOutcome(
            claim.route.event_id,
            claim.route.request_global_id,
            result.state.value,
            result_id,
        )

    def recoverable_inbox_ids(self, *, now: datetime) -> tuple[UUID, ...]:
        return _recoverable_ids(
            "NPI Engineering Change Inbox",
            key="receipt_id",
            now=now,
            include_failed_retryable=True,
        )

    def recoverable_summary_ids(self, *, now: datetime) -> tuple[UUID, ...]:
        return _recoverable_ids(
            "NPI Engineering Change Summary Outbox",
            key="event_id",
            now=now,
            include_failed_retryable=False,
        )


def _locked_summary(
    route: SummaryExecutionRoute,
) -> tuple[Any | None, Any | None]:
    outbox = _optional_doc(
        "NPI Engineering Change Summary Outbox", route.event_id, lock=True
    )
    request = _optional_doc(
        "NPI Engineering Change Summary Request", route.request_global_id, lock=True
    )
    if (
        outbox is None
        or request is None
        or not _summary_binding(outbox, request)
        or str(request.service_actor_user_id) != route.service_actor_user_id
        or str(request.trace_id) != route.trace_id
    ):
        return None, None
    return outbox, request


def _current_summary_claim(
    claim: ClaimedSummary,
) -> tuple[Any | None, Any | None, Any | None]:
    outbox, request = _locked_summary(claim.route)
    attempt = _optional_doc(
        "NPI Engineering Change Summary Attempt",
        claim.command.attempt_global_id,
        lock=True,
    )
    if (
        outbox is None
        or request is None
        or attempt is None
        or str(outbox.state) != "processing"
        or str(outbox.claim_token) != str(claim.claim_token)
        or str(outbox.last_attempt_global_id) != str(claim.command.attempt_global_id)
        or str(attempt.request_global_id) != str(claim.route.request_global_id)
        or str(attempt.outbox_event_id) != str(claim.route.event_id)
    ):
        return None, None, None
    return outbox, request, attempt


def _summary_binding(outbox: Any, request: Any) -> bool:
    return bool(
        str(outbox.event_id) == str(request.outbox_event_id)
        and str(outbox.request_global_id) == str(request.global_id)
        and str(outbox.tenant_id) == str(request.tenant_id)
        and str(outbox.project_global_id) == str(request.project_global_id)
        and str(outbox.change_global_id) == str(request.change_global_id)
        and str(outbox.revision_global_id) == str(request.revision_global_id)
        and str(outbox.source_hash) == str(request.source_hash)
        and str(outbox.profile_snapshot_hash) == str(request.profile_snapshot_hash)
        and str(outbox.service_actor_user_id) == str(request.service_actor_user_id)
        and str(outbox.trace_id) == str(request.trace_id)
        and str(outbox.target_idempotency_key_hash)
        == str(request.idempotency_key_hash)
    )


def _payload(outbox: Any) -> dict[str, object]:
    try:
        value = json.loads(str(outbox.payload))
    except json.JSONDecodeError as error:
        raise RuntimeError("Persisted summary payload is invalid.") from error
    if (
        not isinstance(value, dict)
        or canonical_hash(value) != str(outbox.payload_hash)
        or value.get("source_hash") != str(outbox.source_hash)
        or value.get("request_global_id") != str(outbox.request_global_id)
    ):
        raise RuntimeError("Persisted summary payload binding is invalid.")
    return value


def _inbound_route_matches(row: Any, route: InboundExecutionRoute) -> bool:
    return bool(
        str(row.receipt_id) == str(route.receipt_id)
        and str(row.tenant_id) == route.tenant_id
        and str(row.project_global_id) == str(route.project_global_id)
        and str(row.trace_id) == route.trace_id
        and str(row.profile_id) == route.profile_reference.profile_id
        and int(row.profile_version) == route.profile_reference.profile_version
        and str(row.profile_snapshot_hash) == route.profile_reference.snapshot_hash
    )


def _current_inbound_claim(row: Any, claim: ClaimedInboundEvent) -> bool:
    return bool(
        _inbound_route_matches(row, claim.route)
        and str(row.state) == "processing"
        and str(row.claim_token) == str(claim.claim_token)
    )


def _recoverable_ids(
    doctype: str,
    *,
    key: str,
    now: datetime,
    include_failed_retryable: bool,
) -> tuple[UUID, ...]:
    states = ["pending", "processing"]
    if include_failed_retryable:
        states.append("failed_retryable")
    names = frappe.get_all(
        doctype,
        filters={"state": ["in", states]},
        pluck="name",
        order_by="modified asc, name asc",
        limit_page_length=RECOVERY_BATCH_LIMIT,
    )
    values: list[UUID] = []
    current = _utc(now)
    for name in names:
        row = frappe.get_doc(doctype, str(name))
        if str(row.state) == "processing" and (
            not row.lease_expires_at or current < _aware(row.lease_expires_at)
        ):
            continue
        values.append(UUID(str(_value(row, key) or name)))
    return tuple(values)


def _append_audit(
    *,
    actor: str,
    trace_id: str,
    operation: str,
    global_id: UUID,
    version: int,
    result: str,
    summary: dict[str, object],
) -> None:
    event = create_audit_event(
        actor=actor,
        trace_id=trace_id,
        operation=operation,
        global_id=global_id,
        object_version=version,
        result=result,
        input_summary=summary,
    )
    frappe.get_doc(
        {
            "doctype": "NPI Audit Event",
            "event_id": str(event.event_id),
            "global_id": str(event.global_id),
            "object_version": event.object_version,
            "actor": event.actor,
            "trace_id": event.trace_id,
            "operation": event.operation,
            "result": event.result,
            "input_summary": dict(event.input_summary),
        }
    ).insert()


def _result_snapshot(result: ClassifiedResult) -> dict[str, object]:
    return {
        "state": result.state.value,
        "faultKind": result.fault.value,
        "retryDirective": result.retry.value,
        "responseHash": result.response_hash,
        "responseAuthenticated": result.response_authenticated,
        "responseContractValid": result.response_contract_valid,
        "retryAfterSeconds": result.retry_after_seconds,
    }


def _attempt_state(result: ClassifiedResult) -> str:
    if result.state in {SummaryState.SYNTHETIC_VERIFIED, SummaryState.SUCCEEDED}:
        return "observed_success"
    if result.state is SummaryState.PARTIALLY_SUCCEEDED:
        return "partial"
    if result.state is SummaryState.UNCERTAIN_AFTER_TIMEOUT:
        return "uncertain"
    return "observed_failure"


def _optional_doc(doctype: str, identity: UUID, *, lock: bool = False) -> Any | None:
    try:
        return frappe.get_doc(doctype, str(identity), for_update=lock)
    except frappe.DoesNotExistError:
        return None


def _aware(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise RuntimeError("Persisted lease time is invalid.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Worker time must be timezone-aware.")
    return value.astimezone(UTC)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _value(row: Any, name: str) -> Any:
    return row.get(name) if hasattr(row, "get") else getattr(row, name, None)
