from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import frappe

from npi_core.documents.frappe_repository import _database_datetime, _json_object
from npi_core.foundation.audit import create_audit_event

from .adapters import (
    ClassifiedItemAdapterResult,
    ItemAdapterCommand,
)
from .config import ItemExecutionProfile
from .domain import (
    ITEM_PUBLISH_API_VERSION,
    ITEM_PUBLISH_OPERATION,
    ITEM_PUBLISH_SCHEMA_VERSION,
    ITEM_REQUEST_EVENT_TYPE,
    CurrentItemMapping,
    ItemExecutionProfileReference,
    ItemMappingDisposition,
    ItemMappingExpectation,
    ItemPublishAttemptState,
    ItemPublishRequest,
    ItemPublishRequestState,
    ItemPublishResultState,
    ItemResultAuthority,
    ItemTargetMode,
    ReleasedItemSourceEvidence,
    canonical_hash,
    classify_mapping_observation,
    issue_item_claim,
)
from .frappe_repository import (
    _evidence_value,
    _source_value,
    _stream_guard_supported,
)
from .frappe_validation import (
    insert_item_support_document,
    item_claim_write,
    item_result_transaction_write,
    save_item_support_document,
    validate_item_service_actor,
)


CLAIM_LEASE_SECONDS = 300
RECOVERY_BATCH_LIMIT = 100
_STREAM_ACTIVE_STATES = frozenset(
    {
        ItemPublishRequestState.QUEUED.value,
        ItemPublishRequestState.PROCESSING.value,
        ItemPublishRequestState.FAILED_RETRYABLE.value,
        ItemPublishRequestState.UNCERTAIN_AFTER_TIMEOUT.value,
        ItemPublishRequestState.MAPPING_CONFLICT.value,
    }
)
_STREAM_RETAINED_STATES = frozenset(
    {
        ItemPublishRequestState.SYNTHETIC_VERIFIED.value,
        ItemPublishRequestState.SUCCEEDED.value,
        ItemPublishRequestState.FAILED_FINAL.value,
    }
)


def deterministic_item_result_id(attempt_global_id: UUID) -> UUID:
    """Derive one immutable Result identity from one attempt identity."""

    return uuid5(
        NAMESPACE_URL,
        f"npi.item.publish.result.v1:{attempt_global_id}",
    )


_deterministic_result_id = deterministic_item_result_id


@dataclass(frozen=True, slots=True)
class ClaimedItemPublishMessage:
    outbox_event_id: UUID
    request_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trace_id: str
    claim_token: UUID
    lease_expires_at: datetime
    command: ItemAdapterCommand
    profile_reference: ItemExecutionProfileReference
    service_actor_user_id: str
    expired_recovery: bool
    recovered_after_adapter_boundary: bool


@dataclass(frozen=True, slots=True)
class ItemPublishExecutionRoute:
    """Read-only, non-secret routing identity for one executable Outbox row."""

    outbox_event_id: UUID
    request_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    source_stream_key_hash: str
    profile_reference: ItemExecutionProfileReference
    service_actor_user_id: str
    target_idempotency_key_hash: str
    semantic_effect_hash: str


@dataclass(frozen=True, slots=True)
class ItemPublishWorkerOutcome:
    outbox_event_id: UUID
    request_global_id: UUID
    state: str
    disposition: str
    result_global_id: UUID | None = None
    mapping_advanced: bool = False


class ItemPublishWorkerFinalFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _CurrentItemClaimNotCurrent(RuntimeError):
    pass


def _read_execution_route(
    outbox_event_id: UUID,
) -> ItemPublishExecutionRoute | None:
    """Read and validate only immutable route identity; never write or execute."""

    try:
        outbox = frappe.get_doc("NPI Outbox Message", str(outbox_event_id))
    except frappe.DoesNotExistError:
        return None
    if not _is_item_outbox(outbox):
        return None
    request_id = _value(outbox, "request_global_id")
    if not request_id:
        return None
    try:
        request = frappe.get_doc("NPI Item Publish Request", str(request_id))
        value = _request_value(request)
        _require_outbox_binding(outbox, request, value)
        actor = value.service_actor_user_id
        if value.profile.target_mode is ItemTargetMode.MOCK or not actor:
            return None
        validate_item_service_actor(actor)
        return ItemPublishExecutionRoute(
            outbox_event_id=outbox_event_id,
            request_global_id=value.global_id,
            tenant_id=value.source.tenant_id,
            project_global_id=value.source.project_global_id,
            source_stream_key_hash=value.source.stream_key_hash,
            profile_reference=value.profile,
            service_actor_user_id=actor,
            target_idempotency_key_hash=str(value.target_idempotency_key_hash),
            semantic_effect_hash=value.semantic_effect_hash,
        )
    except (frappe.DoesNotExistError, RuntimeError, ValueError):
        # A malformed or legacy route is not executable.  The worker boundary
        # treats the absent route as a closed failure, never as a fallback.
        return None


def _locked_guard_for_route(route: Any | None) -> Any | None:
    if route is None or not _stream_guard_supported():
        return None
    stream_hash = str(_value(route, "source_stream_key_hash"))
    if not stream_hash:
        raise RuntimeError("Persisted Item execution route has no source stream.")
    name = frappe.db.get_value(
        "NPI Item Publish Stream Guard",
        {"source_stream_key_hash": stream_hash},
        "name",
    )
    if not name:
        raise RuntimeError("The Item source stream guard is unavailable.")
    guard = _optional_locked_doc(
        "NPI Item Publish Stream Guard",
        str(name),
    )
    if guard is None:
        raise RuntimeError("The Item source stream guard is unavailable.")
    if (
        str(_value(guard, "source_stream_key_hash")) != stream_hash
        or str(_value(guard, "tenant_id")) != str(_value(route, "tenant_id"))
        or str(_value(guard, "project_global_id"))
        != str(_value(route, "project_global_id"))
    ):
        raise RuntimeError("Persisted Item source stream guard binding is invalid.")
    return guard


def _require_guard_active_binding(
    guard: Any | None,
    value: ItemPublishRequest,
    *,
    allow_state: frozenset[str] = _STREAM_ACTIVE_STATES,
) -> None:
    if guard is None:
        return
    if (
        str(_value(guard, "active_request_global_id")) != str(value.global_id)
        or str(_value(guard, "active_target_idempotency_key_hash"))
        != str(value.target_idempotency_key_hash)
        or str(_value(guard, "active_state")) not in allow_state
    ):
        raise RuntimeError("Persisted Item source stream guard active binding is invalid.")


def _set_guard_active_state(
    guard: Any | None,
    *,
    request_global_id: UUID,
    target_idempotency_key_hash: str,
    state: str | None,
    now: datetime,
    capability: object,
) -> None:
    if guard is None:
        return
    if state is None:
        guard.active_request_global_id = None
        guard.active_target_idempotency_key_hash = None
        guard.active_state = None
    else:
        guard.active_request_global_id = str(request_global_id)
        guard.active_target_idempotency_key_hash = target_idempotency_key_hash
        guard.active_state = state
    guard.optimistic_version = int(_value(guard, "optimistic_version") or 0) + 1
    guard.updated_at = _database_datetime(_aware_utc(now))
    save_item_support_document(guard, capability=capability)


def _set_guard_retained_state(
    guard: Any,
    *,
    request_global_id: UUID,
    target_idempotency_key_hash: str,
    state: str,
    now: datetime,
    capability: object,
) -> None:
    guard.active_request_global_id = None
    guard.active_target_idempotency_key_hash = None
    guard.active_state = None
    guard.last_request_global_id = str(request_global_id)
    guard.last_target_idempotency_key_hash = target_idempotency_key_hash
    guard.last_state = state
    guard.optimistic_version = int(_value(guard, "optimistic_version") or 0) + 1
    guard.updated_at = _database_datetime(_aware_utc(now))
    save_item_support_document(guard, capability=capability)


def _request_state_for_observation(state: ItemPublishResultState) -> str:
    return {
        ItemPublishResultState.SYNTHETIC_VERIFIED: (
            ItemPublishRequestState.SYNTHETIC_VERIFIED.value
        ),
        ItemPublishResultState.SUCCEEDED: ItemPublishRequestState.SUCCEEDED.value,
        ItemPublishResultState.FAILED_RETRYABLE: (
            ItemPublishRequestState.FAILED_RETRYABLE.value
        ),
        ItemPublishResultState.FAILED_FINAL: (
            ItemPublishRequestState.FAILED_FINAL.value
        ),
        ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT: (
            ItemPublishRequestState.UNCERTAIN_AFTER_TIMEOUT.value
        ),
    }[state]


class FrappeItemPublishWorkerRepository:
    """Persist one P8-03 attempt without granting generic replay authority."""

    def execution_route(
        self,
        outbox_event_id: UUID,
    ) -> ItemPublishExecutionRoute | None:
        """Return immutable routing identity without claiming or writing work."""

        return _read_execution_route(outbox_event_id)

    def claim(
        self,
        outbox_event_id: UUID,
        *,
        now: datetime,
        lease_seconds: int = CLAIM_LEASE_SECONDS,
        expected_route: ItemPublishExecutionRoute | None = None,
    ) -> ClaimedItemPublishMessage | None:
        # Re-read the immutable route inside the frozen service-actor scope,
        # then acquire the source-stream guard before touching Outbox/Request/
        # Attempt rows.  A route TOCTOU never falls back to an unbound claim.
        route = _read_execution_route(outbox_event_id)
        if route is None:
            return None
        if expected_route is not None and route != expected_route:
            raise RuntimeError("Item execution route changed before claim.")
        guard = _locked_guard_for_route(route)
        outbox = _optional_locked_doc("NPI Outbox Message", str(outbox_event_id))
        if outbox is None or not _is_item_outbox(outbox):
            return None
        request = _required_locked_request(outbox)
        value = _request_value(request)
        _require_outbox_binding(outbox, request, value)
        _require_guard_active_binding(guard, value)
        if value.service_actor_user_id != route.service_actor_user_id:
            raise RuntimeError("Item service actor binding changed before claim.")
        state = str(_value(outbox, "state"))
        if (
            state == "pending"
            and value.state is not ItemPublishRequestState.QUEUED
        ) or (
            state == "processing"
            and value.state is not ItemPublishRequestState.PROCESSING
        ):
            raise RuntimeError(
                "Persisted Item request and Outbox states are inconsistent."
            )
        expired_recovery = False
        recovered_after_boundary = False
        previous_attempt = None
        if state == "processing":
            expires_at = _datetime_value(_value(outbox, "lease_expires_at"))
            if _aware_utc(now) < expires_at:
                return None
            expired_recovery = True
            previous_attempt = _required_attempt(outbox)
            _require_attempt_binding(previous_attempt, outbox, value)
            recovered_after_boundary = bool(
                _value(outbox, "adapter_boundary_crossed")
            )
            if recovered_after_boundary != bool(
                _value(previous_attempt, "adapter_boundary_crossed")
            ):
                raise RuntimeError(
                    "Persisted Item adapter-boundary evidence is inconsistent."
                )
        elif state != "pending":
            return None

        claimed = _aware_utc(now)
        previous_count = int(_value(outbox, "attempt_count") or 0)
        if recovered_after_boundary:
            lease = issue_item_claim(
                now=claimed,
                lease_seconds=lease_seconds,
                previous_attempt_count=max(0, previous_count - 1),
            )
            attempt = previous_attempt
            assert attempt is not None
            command = _command_from_attempt(attempt, value)
        else:
            lease = issue_item_claim(
                now=claimed,
                lease_seconds=lease_seconds,
                previous_attempt_count=previous_count,
            )
            if previous_attempt is not None:
                _finish_expired_pre_boundary_attempt(previous_attempt, claimed)
            attempt_id = uuid4()
            command = _command(value, attempt_id, lease.attempt_count)
            attempt = None

        with item_claim_write(value.service_actor_user_id) as capability:
            if guard is not None:
                _set_guard_active_state(
                    guard,
                    request_global_id=value.global_id,
                    target_idempotency_key_hash=str(value.target_idempotency_key_hash),
                    state=(
                        "processing"
                        if not recovered_after_boundary
                        else "uncertain_after_timeout"
                    ),
                    now=claimed,
                    capability=capability,
                )
            if previous_attempt is not None and not recovered_after_boundary:
                save_item_support_document(previous_attempt, capability=capability)
            outbox.state = "processing"
            outbox.disposition = (
                "recover_uncertain"
                if recovered_after_boundary
                else "processing"
            )
            outbox.claim_token = str(lease.token)
            outbox.claimed_at = _database_datetime(lease.claimed_at)
            outbox.lease_expires_at = _database_datetime(lease.expires_at)
            if not recovered_after_boundary:
                outbox.attempt_count = lease.attempt_count
                outbox.last_attempt_global_id = str(command.attempt_global_id)
                outbox.adapter_boundary_crossed = 0
                _insert_attempt(
                    outbox,
                    value,
                    command,
                    claimed,
                    capability=capability,
                )
            outbox.last_error_code = None
            outbox.last_error_at = None
            outbox.result_global_id = None
            save_item_support_document(outbox, capability=capability)
            if value.state is ItemPublishRequestState.QUEUED:
                request.state = ItemPublishRequestState.PROCESSING.value
                request.optimistic_version = int(request.optimistic_version) + 1
                request.updated_at = _database_datetime(claimed)
                save_item_support_document(request, capability=capability)
            _append_audit(
                actor=value.service_actor_user_id,
                trace_id=value.trace_id,
                operation=(
                    "item_publish.claim_recovered_uncertain"
                    if recovered_after_boundary
                    else (
                        "item_publish.claim_recovered"
                        if expired_recovery
                        else "item_publish.claim"
                    )
                ),
                global_id=value.global_id,
                object_version=int(request.optimistic_version),
                result="processing",
                summary={
                    "attemptGlobalId": str(command.attempt_global_id),
                    "attemptNumber": command.attempt_number,
                    "expiredRecovery": expired_recovery,
                    "outboxEventId": str(outbox_event_id),
                    "recoveredAfterAdapterBoundary": recovered_after_boundary,
                    "sourceStreamKeyHash": value.source.stream_key_hash,
                },
            )
        return ClaimedItemPublishMessage(
            outbox_event_id=outbox_event_id,
            request_global_id=value.global_id,
            tenant_id=value.source.tenant_id,
            project_global_id=value.source.project_global_id,
            trace_id=value.trace_id,
            claim_token=lease.token,
            lease_expires_at=lease.expires_at,
            command=command,
            profile_reference=value.profile,
            service_actor_user_id=str(value.service_actor_user_id),
            expired_recovery=expired_recovery,
            recovered_after_adapter_boundary=recovered_after_boundary,
        )

    def require_execution_profile(
        self,
        claim: ClaimedItemPublishMessage,
        profile: ItemExecutionProfile | None,
    ) -> ItemExecutionProfile:
        if (
            not isinstance(profile, ItemExecutionProfile)
            or profile.reference != claim.profile_reference
            or profile.snapshot_hash != claim.profile_reference.snapshot_hash
            or profile.tenant_id != claim.tenant_id
            or profile.project_global_id != str(claim.project_global_id)
            or profile.target_mode is ItemTargetMode.MOCK
            or ITEM_PUBLISH_OPERATION not in profile.allowed_operations
            or profile.service_actor_user_id != claim.service_actor_user_id
            or not _service_actor_available(profile.service_actor_user_id)
        ):
            raise ItemPublishWorkerFinalFailure(
                "ITEM_PUBLISH_EXECUTION_PROFILE_UNAVAILABLE"
            )
        return profile

    def mark_adapter_boundary(
        self,
        claim: ClaimedItemPublishMessage,
        *,
        profile: ItemExecutionProfile,
        now: datetime,
    ) -> bool:
        if claim.recovered_after_adapter_boundary:
            return False
        self.require_execution_profile(claim, profile)
        outbox, _request, attempt, _guard = _required_current_claim(claim)
        if bool(_value(outbox, "adapter_boundary_crossed")) or bool(
            _value(attempt, "adapter_boundary_crossed")
        ):
            return False
        crossed_at = _aware_utc(now)
        with item_claim_write(claim.service_actor_user_id) as capability:
            outbox.adapter_boundary_crossed = 1
            outbox.disposition = "adapter_boundary_crossed"
            save_item_support_document(outbox, capability=capability)
            attempt.adapter_boundary_crossed = 1
            attempt.connect_timeout_seconds = profile.connect_timeout_seconds
            attempt.read_timeout_seconds = profile.read_timeout_seconds
            attempt.transport_disposition = "adapter_boundary_crossed"
            _set_attempt_snapshot(attempt)
            save_item_support_document(attempt, capability=capability)
            _append_audit(
                actor=claim.service_actor_user_id,
                trace_id=claim.trace_id,
                operation="item_publish.adapter_boundary",
                global_id=claim.request_global_id,
                object_version=claim.command.attempt_number,
                result="crossed",
                summary={
                    "attemptGlobalId": str(claim.command.attempt_global_id),
                    "attemptNumber": claim.command.attempt_number,
                    "crossedAt": _utc_text(crossed_at),
                    "outboxEventId": str(claim.outbox_event_id),
                    "targetIdempotencyKeyHash": (
                        claim.command.target_idempotency_key_hash
                    ),
                },
            )
        return True

    def seal_result(
        self,
        claim: ClaimedItemPublishMessage,
        *,
        profile: ItemExecutionProfile | None,
        result: ClassifiedItemAdapterResult,
        now: datetime,
        _allow_existing: bool = False,
    ) -> ItemPublishWorkerOutcome:
        outbox, request, attempt, guard, historical = _required_claim_for_seal(claim)
        value = _request_value(request)
        # `_required_claim_for_seal` is the sole active-or-retained guard
        # validation point.  Historical crossed-boundary evidence is allowed
        # after the current attempt has reached a terminal state; rechecking
        # only the active binding here would reject that late immutable result.
        observation = result.observation
        if profile is None:
            if observation.authority is not ItemResultAuthority.NONE or observation.state in {
                ItemPublishResultState.SYNTHETIC_VERIFIED,
                ItemPublishResultState.SUCCEEDED,
            }:
                raise RuntimeError(
                    "An Item adapter result without a profile cannot claim target truth."
                )
        else:
            self.require_execution_profile(claim, profile)
        if (
            observation.request_global_id != claim.request_global_id
            or observation.attempt_global_id
            != claim.command.attempt_global_id
            or observation.attempt_number != claim.command.attempt_number
            or observation.idempotency_key_hash
            != claim.command.target_idempotency_key_hash
            or observation.source_hash != claim.command.source_hash
        ):
            raise RuntimeError("Item adapter result binding is inconsistent.")
        boundary_crossed = bool(_value(outbox, "adapter_boundary_crossed"))
        if observation.state in {
            ItemPublishResultState.SYNTHETIC_VERIFIED,
            ItemPublishResultState.SUCCEEDED,
            ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT,
        } and not boundary_crossed:
            raise RuntimeError("Item adapter result lacks a durable boundary.")

        current_row, current = _locked_current_mapping(value)
        mapping_disposition = classify_mapping_observation(
            expectation=value.mapping_expectation,
            current=current,
            observation=observation,
        )
        mapping_advanced = mapping_disposition is ItemMappingDisposition.ADVANCE
        mapping_conflict = observation.is_authoritative_success and not mapping_advanced
        result_id = deterministic_item_result_id(claim.command.attempt_global_id)
        result_snapshot = _result_snapshot(
            claim,
            observation,
            result_id=result_id,
        )
        result_hash = canonical_hash(result_snapshot)
        existing_result = _existing_result_for_attempt(
            claim.command.attempt_global_id,
        )
        existing_observation = (
            _mapping_observation_for_result(result_id)
            if existing_result is not None
            else None
        )
        if existing_result is not None:
            if not _result_row_matches(
                existing_result,
                claim=claim,
                expected_snapshot=result_snapshot,
                expected_hash=result_hash,
            ):
                raise RuntimeError("Persisted Item result truth is inconsistent.")
            if not _allow_existing:
                raise RuntimeError("An Item result already exists for this attempt.")
        completed_at = _aware_utc(now)
        with item_result_transaction_write(claim.service_actor_user_id) as capability:
            if existing_result is None:
                _insert_result(
                    claim,
                    observation,
                    result_id=result_id,
                    result_snapshot=result_snapshot,
                    result_hash=result_hash,
                    capability=capability,
                )
            if observation.is_authoritative_success and existing_observation is None:
                assert profile is not None
                mapping_disposition = _record_authoritative_mapping(
                    value=value,
                    claim=claim,
                    profile=profile,
                    observation=observation,
                    result_id=result_id,
                    result_snapshot=result_snapshot,
                    result_hash=result_hash,
                    current_row=current_row,
                    current=current,
                    mapping_disposition=mapping_disposition,
                    now=completed_at,
                    capability=capability,
                )
            elif existing_observation is not None:
                mapping_disposition = (
                    ItemMappingDisposition.ADVANCE
                    if str(_value(existing_observation, "disposition")) == "advanced"
                    else ItemMappingDisposition.EXPECTATION_CONFLICT
                )
            if observation.is_authoritative_success:
                mapping_advanced = mapping_disposition is ItemMappingDisposition.ADVANCE
                mapping_conflict = not mapping_advanced
            guard_state = (
                ItemPublishRequestState.MAPPING_CONFLICT.value
                if mapping_conflict
                else _request_state_for_observation(observation.state)
            )
            if guard is not None and not historical:
                if guard_state in _STREAM_ACTIVE_STATES:
                    _set_guard_active_state(
                        guard,
                        request_global_id=claim.request_global_id,
                        target_idempotency_key_hash=claim.command.target_idempotency_key_hash,
                        state=guard_state,
                        now=completed_at,
                        capability=capability,
                    )
                else:
                    _set_guard_retained_state(
                        guard,
                        request_global_id=claim.request_global_id,
                        target_idempotency_key_hash=claim.command.target_idempotency_key_hash,
                        state=guard_state,
                        now=completed_at,
                        capability=capability,
                    )
            _finish_attempt(
                attempt,
                observation=observation,
                classified=result,
                finished_at=completed_at,
            )
            save_item_support_document(attempt, capability=capability)
            request_state = (
                ItemPublishRequestState.MAPPING_CONFLICT
                if mapping_conflict
                else ItemPublishRequestState(observation.state.value)
            )
            if not historical:
                request.state = request_state.value
                request.result_global_id = str(result_id)
                request.optimistic_version = int(request.optimistic_version) + 1
                request.updated_at = _database_datetime(completed_at)
                save_item_support_document(request, capability=capability)
                outbox.state = _outbox_state(observation.state)
                outbox.disposition = (
                    "mapping_conflict"
                    if mapping_conflict
                    else observation.state.value
                )
                outbox.result_global_id = str(result_id)
                outbox.last_error_code = result.safe_error_code
                outbox.last_error_at = (
                    _database_datetime(completed_at)
                    if result.safe_error_code
                    else None
                )
                save_item_support_document(outbox, capability=capability)
            _append_audit(
                actor=(
                    profile.service_actor_user_id
                    if profile is not None
                    else claim.service_actor_user_id
                ),
                trace_id=claim.trace_id,
                operation=(
                    "item_publish.complete_historical_evidence"
                    if historical
                    else "item_publish.complete"
                ),
                global_id=claim.request_global_id,
                object_version=int(request.optimistic_version),
                result=request_state.value,
                summary={
                    "attemptGlobalId": str(claim.command.attempt_global_id),
                    "attemptNumber": claim.command.attempt_number,
                    "authority": observation.authority.value,
                    "faultKind": observation.fault_kind.value,
                    "mappingDisposition": mapping_disposition.value,
                    "outboxEventId": str(claim.outbox_event_id),
                    "reconciliationRequired": result.reconciliation_required,
                    "responseHash": observation.response_hash,
                    "resultGlobalId": str(result_id),
                    "sourceStreamKeyHash": value.source.stream_key_hash,
                },
            )
        return ItemPublishWorkerOutcome(
            outbox_event_id=claim.outbox_event_id,
            request_global_id=claim.request_global_id,
            state=request_state.value,
            disposition=(
                ("mapping_conflict" if mapping_conflict else observation.state.value)
                if historical
                else str(outbox.disposition)
            ),
            result_global_id=result_id,
            mapping_advanced=mapping_advanced,
        )

    def recover_or_seal_result(
        self,
        claim: ClaimedItemPublishMessage,
        *,
        profile: ItemExecutionProfile | None,
        result: ClassifiedItemAdapterResult,
        now: datetime,
    ) -> ItemPublishWorkerOutcome:
        """Retry only local evidence persistence for the same attempt."""

        return self.seal_result(
            claim,
            profile=profile,
            result=result,
            now=now,
            _allow_existing=True,
        )

    def recoverable_outbox_event_ids(
        self,
        *,
        now: datetime,
        limit: int = RECOVERY_BATCH_LIMIT,
    ) -> tuple[UUID, ...]:
        if type(limit) is not int or not 1 <= limit <= RECOVERY_BATCH_LIMIT:
            raise ValueError("Item Outbox recovery batch limit is invalid.")
        common = {
            "schema_version": ITEM_PUBLISH_SCHEMA_VERSION,
            "event_type": ITEM_REQUEST_EVENT_TYPE,
            "operation": ITEM_PUBLISH_OPERATION,
        }
        rows = frappe.get_all(
            "NPI Outbox Message",
            filters={**common, "state": "pending"},
            fields=["name"],
            order_by="creation asc, name asc",
            limit_page_length=limit,
        )
        remaining = limit - len(rows)
        if remaining:
            rows.extend(
                frappe.get_all(
                    "NPI Outbox Message",
                    filters=[
                        ["schema_version", "=", ITEM_PUBLISH_SCHEMA_VERSION],
                        ["event_type", "=", ITEM_REQUEST_EVENT_TYPE],
                        ["operation", "=", ITEM_PUBLISH_OPERATION],
                        ["state", "=", "processing"],
                        ["lease_expires_at", "<=", _database_datetime(now)],
                    ],
                    fields=["name"],
                    order_by="lease_expires_at asc, name asc",
                    limit_page_length=remaining,
                )
            )
        return tuple(UUID(str(_value(row, "name"))) for row in rows)


def _request_value(row: Any) -> ItemPublishRequest:
    source = _source_value(_json_object(row.source_snapshot))
    evidence: ReleasedItemSourceEvidence = _evidence_value(
        _json_object(row.released_evidence_snapshot)
    )
    profile = ItemExecutionProfileReference(
        profile_id=str(row.profile_id),
        profile_version=int(row.profile_version),
        target_mode=ItemTargetMode(str(row.target_mode)),
        environment_code=str(row.environment_code),
        snapshot_hash=str(row.profile_snapshot_hash),
    )
    expectation = ItemMappingExpectation(
        int(row.expected_mapping_version),
        row.expected_formal_item_code or None,
        row.expected_target_version or None,
        row.expected_mapping_observation_hash or None,
    )
    value = ItemPublishRequest(
        global_id=UUID(str(row.global_id)),
        source=source,
        released_evidence=evidence,
        profile=profile,
        mapping_expectation=expectation,
        actor_user_id=str(row.actor_user_id),
        request_id=UUID(str(row.request_id)),
        trace_id=str(row.trace_id),
        idempotency_key_hash=str(row.idempotency_key_hash),
        state=ItemPublishRequestState(str(row.state)),
        created_at=_datetime_value(row.created_at),
        payload_hash=str(row.payload_hash),
        target_idempotency_key_hash=(
            str(row.target_idempotency_key_hash)
            if getattr(row, "target_idempotency_key_hash", None)
            else None
        ),
        semantic_source_effect_hash=(
            str(row.semantic_source_effect_hash)
            if getattr(row, "semantic_source_effect_hash", None)
            else ""
        ),
        service_actor_user_id=(
            str(row.service_actor_user_id)
            if getattr(row, "service_actor_user_id", None)
            else None
        ),
        semantic_effect_hash=(
            str(row.semantic_effect_hash)
            if getattr(row, "semantic_effect_hash", None)
            else ""
        ),
    )
    if (
        int(row.schema_version) != ITEM_PUBLISH_SCHEMA_VERSION
        or str(row.api_version) != ITEM_PUBLISH_API_VERSION
        or str(row.operation) != ITEM_PUBLISH_OPERATION
        or str(row.tenant_id) != source.tenant_id
        or str(row.project_global_id) != str(source.project_global_id)
        or str(row.source_stream_key_hash) != source.stream_key_hash
        or str(row.engineering_item_id) != source.engineering_item_id
        or str(row.source_hash) != source.source_hash
        or str(row.released_evidence_hash)
        != canonical_hash(evidence.canonical_mapping())
        or not bool(row.dispatch_allowed)
        or not row.outbox_event_id
        or not getattr(row, "semantic_source_effect_hash", None)
        or str(getattr(row, "semantic_source_effect_hash", ""))
        != value.semantic_source_effect_hash
        or int(row.optimistic_version) < 1
    ):
        raise RuntimeError("Persisted Item publish request is invalid.")
    return value


def _require_outbox_binding(
    outbox: Any,
    request: Any,
    value: ItemPublishRequest,
) -> None:
    payload = _json_object(outbox.payload)
    expected = value.event_payload()
    if (
        payload != expected
        or canonical_hash(payload) != str(outbox.payload_hash)
        or str(outbox.global_id) != str(value.global_id)
        or str(outbox.request_global_id) != str(value.global_id)
        or str(outbox.tenant_id) != value.source.tenant_id
        or str(outbox.project_global_id) != str(value.source.project_global_id)
        or str(outbox.profile_id) != value.profile.profile_id
        or int(outbox.profile_version) != value.profile.profile_version
        or str(outbox.profile_snapshot_hash) != value.profile.snapshot_hash
        or str(outbox.source_stream_key_hash) != value.source.stream_key_hash
        or str(outbox.source_hash) != value.source.source_hash
        or int(outbox.expected_mapping_version)
        != value.mapping_expectation.mapping_version
        or (outbox.expected_target_version or None)
        != value.mapping_expectation.target_version
        or str(outbox.actor_user_id) != value.actor_user_id
        or str(outbox.request_id) != str(value.request_id)
        or str(outbox.idempotency_key_hash) != value.idempotency_key_hash
        or str(getattr(outbox, "target_idempotency_key_hash", ""))
        != str(value.target_idempotency_key_hash)
        or str(getattr(outbox, "semantic_source_effect_hash", ""))
        != value.semantic_source_effect_hash
        or str(getattr(outbox, "service_actor_user_id", ""))
        != str(value.service_actor_user_id)
        or str(getattr(outbox, "semantic_effect_hash", ""))
        != value.semantic_effect_hash
        or str(request.outbox_event_id) != str(outbox.event_id)
    ):
        raise RuntimeError("Persisted Item Outbox binding is invalid.")


def _command(
    value: ItemPublishRequest,
    attempt_id: UUID,
    attempt_number: int,
) -> ItemAdapterCommand:
    return ItemAdapterCommand(
        request_global_id=value.global_id,
        attempt_global_id=attempt_id,
        attempt_number=attempt_number,
        target_idempotency_key_hash=str(value.target_idempotency_key_hash),
        source_hash=value.source.source_hash,
        source_snapshot=value.source.canonical_mapping(),
        intent=value.intent,
        expected_mapping_version=value.mapping_expectation.mapping_version,
        expected_target_version=value.mapping_expectation.target_version,
    )


def _command_from_attempt(attempt: Any, value: ItemPublishRequest) -> ItemAdapterCommand:
    snapshot = _json_object(attempt.request_snapshot)
    command = _command(
        value,
        UUID(str(attempt.global_id)),
        int(attempt.attempt_number),
    )
    if (
        snapshot != command.snapshot()
        or canonical_hash(snapshot) != str(attempt.request_snapshot_hash)
        or str(attempt.target_idempotency_key_hash)
        != command.target_idempotency_key_hash
    ):
        raise RuntimeError("Persisted Item attempt request is invalid.")
    return command


def _insert_attempt(
    outbox: Any,
    value: ItemPublishRequest,
    command: ItemAdapterCommand,
    now: datetime,
    *,
    capability: object,
) -> None:
    request_snapshot = command.snapshot()
    attempt_snapshot = {
        "schemaVersion": 1,
        "globalId": str(command.attempt_global_id),
        "requestGlobalId": str(command.request_global_id),
        "outboxEventId": str(outbox.event_id),
        "attemptNumber": command.attempt_number,
        "claimToken": str(outbox.claim_token),
        "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        "sourceHash": command.source_hash,
        "profileId": value.profile.profile_id,
        "profileVersion": value.profile.profile_version,
        "state": ItemPublishAttemptState.STARTED.value,
        "adapterBoundaryCrossed": False,
        "connectTimeoutSeconds": None,
        "readTimeoutSeconds": None,
        "requestSnapshotHash": canonical_hash(request_snapshot),
        "transportDisposition": "started",
        "targetStatusCode": None,
        "responseHash": None,
        "faultKind": None,
        "reconciliationRequired": False,
        "safeErrorCode": None,
        "startedAt": _utc_text(now),
        "finishedAt": None,
    }
    insert_item_support_document(
        frappe.get_doc(
            {
                "doctype": "NPI Item Publish Attempt",
                "global_id": str(command.attempt_global_id),
                "request_global_id": str(command.request_global_id),
                "outbox_event_id": str(outbox.event_id),
                "attempt_number": command.attempt_number,
                "claim_token": str(outbox.claim_token),
                "target_idempotency_key_hash": command.target_idempotency_key_hash,
                "source_hash": command.source_hash,
                "profile_id": value.profile.profile_id,
                "profile_version": value.profile.profile_version,
                "state": ItemPublishAttemptState.STARTED.value,
                "adapter_boundary_crossed": 0,
                "request_snapshot": request_snapshot,
                "request_snapshot_hash": canonical_hash(request_snapshot),
                "transport_disposition": "started",
                "reconciliation_required": 0,
                "started_at": _database_datetime(now),
                "attempt_snapshot": attempt_snapshot,
                "attempt_hash": canonical_hash(attempt_snapshot),
            }
        ),
        capability=capability,
    )


def _finish_expired_pre_boundary_attempt(attempt: Any, now: datetime) -> None:
    attempt.state = ItemPublishAttemptState.OBSERVED_FAILURE.value
    attempt.transport_disposition = "expired_before_boundary"
    attempt.fault_kind = "target_unavailable"
    attempt.reconciliation_required = 0
    attempt.safe_error_code = "ITEM_PUBLISH_LEASE_EXPIRED_BEFORE_BOUNDARY"
    attempt.finished_at = _database_datetime(now)
    _set_attempt_snapshot(attempt)


def _set_attempt_snapshot(attempt: Any) -> None:
    snapshot = {
        "schemaVersion": 1,
        "globalId": str(attempt.global_id),
        "requestGlobalId": str(attempt.request_global_id),
        "outboxEventId": str(attempt.outbox_event_id),
        "attemptNumber": int(attempt.attempt_number),
        "claimToken": str(attempt.claim_token),
        "targetIdempotencyKeyHash": str(attempt.target_idempotency_key_hash),
        "sourceHash": str(attempt.source_hash),
        "profileId": str(attempt.profile_id),
        "profileVersion": int(attempt.profile_version),
        "state": str(attempt.state),
        "adapterBoundaryCrossed": bool(attempt.adapter_boundary_crossed),
        "connectTimeoutSeconds": attempt.connect_timeout_seconds or None,
        "readTimeoutSeconds": attempt.read_timeout_seconds or None,
        "requestSnapshotHash": str(attempt.request_snapshot_hash),
        "transportDisposition": attempt.transport_disposition or None,
        "targetStatusCode": attempt.target_status_code or None,
        "responseHash": attempt.response_hash or None,
        "faultKind": attempt.fault_kind or None,
        "reconciliationRequired": bool(attempt.reconciliation_required),
        "safeErrorCode": attempt.safe_error_code or None,
        "startedAt": _utc_text(_datetime_value(attempt.started_at)),
        "finishedAt": (
            _utc_text(_datetime_value(attempt.finished_at))
            if attempt.finished_at
            else None
        ),
    }
    attempt.attempt_snapshot = snapshot
    attempt.attempt_hash = canonical_hash(snapshot)


def _finish_attempt(
    attempt: Any,
    *,
    observation: Any,
    classified: ClassifiedItemAdapterResult,
    finished_at: datetime,
) -> None:
    attempt.state = {
        ItemPublishResultState.SYNTHETIC_VERIFIED: (
            ItemPublishAttemptState.SYNTHETIC_VERIFIED.value
        ),
        ItemPublishResultState.SUCCEEDED: (
            ItemPublishAttemptState.OBSERVED_SUCCESS.value
        ),
        ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT: (
            ItemPublishAttemptState.UNCERTAIN.value
        ),
    }.get(observation.state, ItemPublishAttemptState.OBSERVED_FAILURE.value)
    attempt.transport_disposition = classified.transport_disposition
    attempt.target_status_code = classified.target_status_code
    attempt.response_hash = observation.response_hash
    attempt.fault_kind = observation.fault_kind.value
    attempt.reconciliation_required = int(classified.reconciliation_required)
    attempt.safe_error_code = classified.safe_error_code
    attempt.finished_at = _database_datetime(finished_at)
    _set_attempt_snapshot(attempt)


def _result_snapshot(
    claim: ClaimedItemPublishMessage,
    observation: Any,
    *,
    result_id: UUID,
) -> dict[str, object]:
    observed_at = _aware_utc(observation.observed_at).replace(microsecond=0)
    return {
        "schemaVersion": 1,
        "globalId": str(result_id),
        "requestGlobalId": str(claim.request_global_id),
        "outboxEventId": str(claim.outbox_event_id),
        "attemptGlobalId": str(observation.attempt_global_id),
        "attemptNumber": observation.attempt_number,
        "idempotencyKeyHash": observation.idempotency_key_hash,
        "sourceHash": observation.source_hash,
        "expectedTargetVersion": observation.expected_target_version,
        "state": observation.state.value,
        "authority": observation.authority.value,
        "responseAuthenticated": observation.response_authenticated,
        "responseHash": observation.response_hash,
        "formalItemCode": observation.formal_item_code,
        "targetVersion": observation.target_version,
        "faultKind": observation.fault_kind.value,
        "observedAt": _utc_text(observed_at),
    }


def _insert_result(
    claim: ClaimedItemPublishMessage,
    observation: Any,
    *,
    result_id: UUID,
    result_snapshot: dict[str, object],
    result_hash: str,
    capability: object,
) -> None:
    # Result snapshots use second precision, so persist the exact same
    # canonical instant in Frappe instead of retaining adapter microseconds
    # that would make the reloaded snapshot fail validation.
    observed_at = _aware_utc(observation.observed_at).replace(microsecond=0)
    insert_item_support_document(
        frappe.get_doc(
            {
                "doctype": "NPI Item Publish Result",
                "global_id": str(result_id),
                "request_global_id": str(claim.request_global_id),
                "outbox_event_id": str(claim.outbox_event_id),
                "attempt_global_id": str(observation.attempt_global_id),
                "attempt_number": observation.attempt_number,
                "idempotency_key_hash": observation.idempotency_key_hash,
                "source_hash": observation.source_hash,
                "expected_target_version": observation.expected_target_version,
                "state": observation.state.value,
                "authority": observation.authority.value,
                "response_authenticated": int(observation.response_authenticated),
                "response_hash": observation.response_hash,
                "formal_item_code": observation.formal_item_code,
                "target_version": observation.target_version,
                "fault_kind": observation.fault_kind.value,
                "result_snapshot": result_snapshot,
                "result_hash": result_hash,
                "observed_at": _database_datetime(observed_at),
            }
        ),
        capability=capability,
    )


def _existing_result_for_attempt(attempt_global_id: UUID) -> Any | None:
    if not _stream_guard_supported():
        return None
    name = frappe.db.get_value(
        "NPI Item Publish Result",
        {"attempt_global_id": str(attempt_global_id)},
        "name",
    )
    if not name:
        return None
    return frappe.get_doc("NPI Item Publish Result", str(name))


def _result_row_matches(
    row: Any,
    *,
    claim: ClaimedItemPublishMessage,
    expected_snapshot: dict[str, object],
    expected_hash: str,
) -> bool:
    snapshot = _json_object(_value(row, "result_snapshot"))
    return bool(
        str(_value(row, "global_id"))
        == expected_snapshot["globalId"]
        and str(_value(row, "attempt_global_id"))
        == str(claim.command.attempt_global_id)
        and str(_value(row, "request_global_id"))
        == str(claim.request_global_id)
        and str(_value(row, "outbox_event_id"))
        == str(claim.outbox_event_id)
        and str(_value(row, "result_hash")) == expected_hash
        and snapshot == expected_snapshot
        and canonical_hash(snapshot) == str(_value(row, "result_hash"))
    )


def _mapping_observation_for_result(result_id: UUID) -> Any | None:
    if not _stream_guard_supported():
        return None
    name = frappe.db.get_value(
        "NPI Item Mapping Observation",
        {"result_global_id": str(result_id)},
        "name",
    )
    if not name:
        return None
    return frappe.get_doc("NPI Item Mapping Observation", str(name))


def _locked_current_mapping(
    value: ItemPublishRequest,
) -> tuple[Any | None, CurrentItemMapping | None]:
    name = frappe.db.get_value(
        "NPI Item Mapping Head",
        {"source_stream_key_hash": value.source.stream_key_hash},
        "name",
    )
    if not name:
        return None, None
    row = _optional_locked_doc("NPI Item Mapping Head", str(name))
    if row is None:
        raise RuntimeError("Current Item mapping head is unavailable.")
    snapshot = _json_object(row.head_snapshot)
    expected = {
        "schemaVersion": 1,
        "globalId": str(row.global_id),
        "tenantId": str(row.tenant_id),
        "projectGlobalId": str(row.project_global_id),
        "sourceStreamKeyHash": str(row.source_stream_key_hash),
        "engineeringItemId": str(row.engineering_item_id),
        "mappingVersion": int(row.mapping_version),
        "formalItemCode": str(row.formal_item_code),
        "targetVersion": str(row.target_version),
        "currentObservationGlobalId": str(row.current_observation),
        "currentObservationHash": str(row.current_observation_hash),
        "updatedAt": _utc_text(_datetime_value(row.updated_at)),
    }
    if (
        str(row.tenant_id) != value.source.tenant_id
        or str(row.project_global_id) != str(value.source.project_global_id)
        or str(row.source_stream_key_hash) != value.source.stream_key_hash
        or str(row.engineering_item_id) != value.source.engineering_item_id
        or snapshot != expected
        or canonical_hash(expected) != str(row.head_hash)
    ):
        raise RuntimeError("Current Item mapping head is invalid.")
    return row, CurrentItemMapping(
        int(row.mapping_version),
        str(row.formal_item_code),
        str(row.target_version),
        str(row.current_observation_hash),
    )


def _record_authoritative_mapping(
    *,
    value: ItemPublishRequest,
    claim: ClaimedItemPublishMessage,
    profile: ItemExecutionProfile,
    observation: Any,
    result_id: UUID,
    result_snapshot: dict[str, object],
    result_hash: str,
    current_row: Any | None,
    current: CurrentItemMapping | None,
    mapping_disposition: ItemMappingDisposition,
    now: datetime,
    capability: object,
) -> ItemMappingDisposition:
    """Append evidence first, then CAS the authoritative mapping head.

    The Result is inserted by the outer terminal transaction.  Only a unique
    conflict from a *first-head insert* is recoverable here: the local mapping
    savepoint removes the provisional Observation, the winner Head is locked,
    and a new observed-conflict Observation is appended.  Observation errors
    and all existing-head save errors are deliberately allowed to propagate.
    """

    def append_observation(
        *,
        observation_id: UUID,
        mapping_version: int,
        previous_hash: str | None,
        disposition: str,
    ) -> str:
        snapshot = {
            "schemaVersion": 1,
            "globalId": str(observation_id),
            "tenantId": value.source.tenant_id,
            "projectGlobalId": str(value.source.project_global_id),
            "sourceStreamKeyHash": value.source.stream_key_hash,
            "engineeringItemId": value.source.engineering_item_id,
            "mappingVersion": mapping_version,
            "formalItemCode": observation.formal_item_code,
            "targetVersion": observation.target_version,
            "requestGlobalId": str(claim.request_global_id),
            "outboxEventId": str(claim.outbox_event_id),
            "attemptGlobalId": str(observation.attempt_global_id),
            "resultGlobalId": str(result_id),
            "profileId": profile.profile_id,
            "profileVersion": profile.profile_version,
            "environmentCode": profile.environment_code,
            "authority": ItemResultAuthority.AUTHORITATIVE_SANDBOX.value,
            "disposition": disposition,
            "previousMappingVersion": mapping_version - 1,
            "previousObservationHash": previous_hash,
            "targetResultHash": result_hash,
            "observedAt": _utc_text(now),
        }
        observation_hash = canonical_hash(snapshot)
        insert_item_support_document(
            frappe.get_doc(
                {
                    "doctype": "NPI Item Mapping Observation",
                    "global_id": str(observation_id),
                    "tenant_id": value.source.tenant_id,
                    "project_global_id": str(value.source.project_global_id),
                    "source_stream_key_hash": value.source.stream_key_hash,
                    "engineering_item_id": value.source.engineering_item_id,
                    "mapping_version": mapping_version,
                    "formal_item_code": observation.formal_item_code,
                    "target_version": observation.target_version,
                    "request_global_id": str(claim.request_global_id),
                    "outbox_event_id": str(claim.outbox_event_id),
                    "attempt_global_id": str(observation.attempt_global_id),
                    "result_global_id": str(result_id),
                    "profile_id": profile.profile_id,
                    "profile_version": profile.profile_version,
                    "environment_code": profile.environment_code,
                    "authority": ItemResultAuthority.AUTHORITATIVE_SANDBOX.value,
                    "disposition": disposition,
                    "previous_mapping_version": mapping_version - 1,
                    "previous_observation_hash": previous_hash,
                    "target_result_snapshot": result_snapshot,
                    "target_result_hash": result_hash,
                    "observation_snapshot": snapshot,
                    "observation_hash": observation_hash,
                    "observed_at": _database_datetime(now),
                }
            ),
            capability=capability,
        )
        return observation_hash

    previous_version = 0 if current is None else current.mapping_version
    previous_hash = None if current is None else current.observation_hash
    observation_id = uuid4()
    mapping_version = previous_version + 1
    if mapping_disposition is not ItemMappingDisposition.ADVANCE:
        append_observation(
            observation_id=observation_id,
            mapping_version=mapping_version,
            previous_hash=previous_hash,
            disposition="observed_conflict",
        )
        return mapping_disposition

    cas_savepoint = "item_publish_mapping_cas"
    use_savepoint = callable(getattr(frappe.db, "savepoint", None))
    if use_savepoint:
        frappe.db.savepoint(cas_savepoint)

    # Observation is the first mapping write.  Its unique/controller/link
    # failures are not head races and must remain visible to the caller.
    observation_hash = append_observation(
        observation_id=observation_id,
        mapping_version=mapping_version,
        previous_hash=previous_hash,
        disposition="advanced",
    )
    head = current_row
    head_id = UUID(str(head.global_id)) if head is not None else uuid4()
    head_snapshot = {
        "schemaVersion": 1,
        "globalId": str(head_id),
        "tenantId": value.source.tenant_id,
        "projectGlobalId": str(value.source.project_global_id),
        "sourceStreamKeyHash": value.source.stream_key_hash,
        "engineeringItemId": value.source.engineering_item_id,
        "mappingVersion": mapping_version,
        "formalItemCode": observation.formal_item_code,
        "targetVersion": observation.target_version,
        "currentObservationGlobalId": str(observation_id),
        "currentObservationHash": observation_hash,
        "updatedAt": _utc_text(now),
    }
    values = {
        "global_id": str(head_id),
        "tenant_id": value.source.tenant_id,
        "project_global_id": str(value.source.project_global_id),
        "source_stream_key_hash": value.source.stream_key_hash,
        "engineering_item_id": value.source.engineering_item_id,
        "mapping_version": mapping_version,
        "formal_item_code": observation.formal_item_code,
        "target_version": observation.target_version,
        "current_observation": str(observation_id),
        "current_observation_hash": observation_hash,
        "head_snapshot": head_snapshot,
        "head_hash": canonical_hash(head_snapshot),
        "updated_at": _database_datetime(now),
    }
    if head is not None:
        # A unique failure on an existing Head save is unrelated to first-head
        # creation and therefore intentionally re-raises unchanged.
        for key, item in values.items():
            setattr(head, key, item)
        save_item_support_document(head, capability=capability)
        return ItemMappingDisposition.ADVANCE

    try:
        insert_item_support_document(
            frappe.get_doc({"doctype": "NPI Item Mapping Head", **values}),
            capability=capability,
        )
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        if not use_savepoint:
            raise
        frappe.db.rollback(save_point=cas_savepoint)
        latest_row, latest = _locked_current_mapping(value)
        if latest is None or latest_row is None:
            raise RuntimeError("Mapping head race left no legal source-stream head.")
        append_observation(
            observation_id=uuid4(),
            mapping_version=latest.mapping_version + 1,
            previous_hash=latest.observation_hash,
            disposition="observed_conflict",
        )
        return ItemMappingDisposition.EXPECTATION_CONFLICT
    return ItemMappingDisposition.ADVANCE


def _required_current_claim(
    claim: ClaimedItemPublishMessage,
) -> tuple[Any, Any, Any, Any | None]:
    route = _read_execution_route(claim.outbox_event_id)
    if route is None:
        raise RuntimeError("Item execution route is unavailable for this claim.")
    guard = _locked_guard_for_route(route)
    outbox = _optional_locked_doc("NPI Outbox Message", str(claim.outbox_event_id))
    if (
        outbox is None
        or not _is_item_outbox(outbox)
        or str(_value(outbox, "state")) != "processing"
        or str(_value(outbox, "claim_token")) != str(claim.claim_token)
        or str(_value(outbox, "last_attempt_global_id"))
        != str(claim.command.attempt_global_id)
        or int(_value(outbox, "attempt_count")) != claim.command.attempt_number
    ):
        raise _CurrentItemClaimNotCurrent("Item Outbox claim is no longer current.")
    request = _required_locked_request(outbox)
    attempt = _required_attempt(outbox)
    value = _request_value(request)
    _require_outbox_binding(outbox, request, value)
    _require_attempt_binding(attempt, outbox, value)
    _require_guard_active_binding(guard, value)
    return outbox, request, attempt, guard


def _required_claim_for_seal(
    claim: ClaimedItemPublishMessage,
) -> tuple[Any, Any, Any, Any | None, bool]:
    """Return the current claim or a post-boundary legacy evidence claim.

    Historical duplicate claims are never execution claims.  They may only
    finalize the adapter evidence that already crossed the durable boundary;
    the caller deliberately skips Outbox/Request mutation for that path.
    """

    try:
        outbox, request, attempt, guard = _required_current_claim(claim)
        return outbox, request, attempt, guard, False
    except _CurrentItemClaimNotCurrent as current_error:
        route = _read_execution_route(claim.outbox_event_id)
        if route is None:
            raise current_error
        guard = _locked_guard_for_route(route)
        outbox = _optional_locked_doc("NPI Outbox Message", str(claim.outbox_event_id))
        if outbox is None or not _is_item_outbox(outbox):
            raise current_error
        request = _required_locked_request(outbox)
        value = _request_value(request)
        _require_outbox_binding(outbox, request, value)
        if not bool(_value(outbox, "adapter_boundary_crossed")):
            raise current_error
        attempt = _optional_locked_doc(
            "NPI Item Publish Attempt",
            str(claim.command.attempt_global_id),
        )
        if attempt is None:
            raise current_error
        _require_historical_attempt_binding(attempt, outbox, value, claim)
        try:
            _require_guard_active_binding(guard, value)
        except RuntimeError:
            if not _guard_retained_binding(guard, value):
                raise
        return outbox, request, attempt, guard, True


def _required_locked_request(outbox: Any) -> Any:
    request = _optional_locked_doc(
        "NPI Item Publish Request", str(outbox.request_global_id)
    )
    if request is None:
        raise RuntimeError("Persisted Item publish request is unavailable.")
    return request


def _required_attempt(outbox: Any) -> Any:
    attempt_id = _value(outbox, "last_attempt_global_id")
    if not attempt_id:
        raise RuntimeError("Persisted Item publish attempt is unavailable.")
    attempt = _optional_locked_doc("NPI Item Publish Attempt", str(attempt_id))
    if attempt is None:
        raise RuntimeError("Persisted Item publish attempt is unavailable.")
    return attempt


def _require_historical_attempt_binding(
    attempt: Any,
    outbox: Any,
    value: ItemPublishRequest,
    claim: ClaimedItemPublishMessage,
) -> None:
    if (
        str(attempt.global_id) != str(claim.command.attempt_global_id)
        or str(attempt.request_global_id) != str(value.global_id)
        or str(attempt.outbox_event_id) != str(outbox.event_id)
        or int(attempt.attempt_number) < 1
        or str(attempt.source_hash) != value.source.source_hash
        or str(attempt.target_idempotency_key_hash)
        != str(value.target_idempotency_key_hash)
        or str(attempt.claim_token) != str(claim.claim_token)
        or not bool(attempt.adapter_boundary_crossed)
    ):
        raise RuntimeError("Persisted legacy Item claim evidence is invalid.")


def _guard_retained_binding(guard: Any | None, value: ItemPublishRequest) -> bool:
    if guard is None:
        return True
    return bool(
        not _value(guard, "active_request_global_id")
        and not _value(guard, "active_target_idempotency_key_hash")
        and not _value(guard, "active_state")
        and str(_value(guard, "last_request_global_id")) == str(value.global_id)
        and str(_value(guard, "last_target_idempotency_key_hash"))
        == str(value.target_idempotency_key_hash)
        and str(_value(guard, "last_state")) in _STREAM_RETAINED_STATES
    )


def _require_attempt_binding(
    attempt: Any,
    outbox: Any,
    value: ItemPublishRequest,
) -> None:
    if (
        str(attempt.global_id) != str(outbox.last_attempt_global_id)
        or str(attempt.request_global_id) != str(value.global_id)
        or str(attempt.outbox_event_id) != str(outbox.event_id)
        or int(attempt.attempt_number) != int(outbox.attempt_count)
        or str(attempt.source_hash) != value.source.source_hash
        or str(attempt.target_idempotency_key_hash)
        != str(value.target_idempotency_key_hash)
        or str(attempt.profile_id) != value.profile.profile_id
        or int(attempt.profile_version) != value.profile.profile_version
        or str(attempt.state) != ItemPublishAttemptState.STARTED.value
    ):
        raise RuntimeError("Persisted Item publish attempt binding is invalid.")


def _service_actor_available(actor: str) -> bool:
    try:
        validate_item_service_actor(actor)
    except (RuntimeError, ValueError):
        return False
    return True


def _outbox_state(state: ItemPublishResultState) -> str:
    return {
        ItemPublishResultState.SYNTHETIC_VERIFIED: "succeeded",
        ItemPublishResultState.SUCCEEDED: "succeeded",
        ItemPublishResultState.FAILED_RETRYABLE: "failed_retryable",
        ItemPublishResultState.FAILED_FINAL: "failed_final",
        ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT: "uncertain",
    }[state]


def _is_item_outbox(row: Any) -> bool:
    return bool(
        int(_value(row, "schema_version") or 0) == ITEM_PUBLISH_SCHEMA_VERSION
        and str(_value(row, "event_type")) == ITEM_REQUEST_EVENT_TYPE
        and str(_value(row, "operation")) == ITEM_PUBLISH_OPERATION
        and int(_value(row, "object_version") or 0) == 1
    )


def _optional_locked_doc(doctype: str, name: str) -> Any | None:
    try:
        return frappe.get_doc(doctype, name, for_update=True)
    except frappe.DoesNotExistError:
        return None


def _append_audit(
    *,
    actor: str,
    trace_id: str,
    operation: str,
    global_id: UUID,
    object_version: int,
    result: str,
    summary: dict[str, object],
) -> None:
    event = create_audit_event(
        actor=actor,
        trace_id=trace_id,
        operation=operation,
        global_id=global_id,
        object_version=object_version,
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


def _value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Item worker time must be timezone-aware.")
    return value.astimezone(UTC)


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("Persisted Item worker time is invalid.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return _aware_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")
