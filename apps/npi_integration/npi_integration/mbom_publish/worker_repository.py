from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import frappe

from npi_core.documents.frappe_repository import _database_datetime, _json_array, _json_object
from npi_core.foundation.audit import create_audit_event

from .adapters import (
    ClassifiedMbomAdapterResult,
    MbomAdapterCommand,
    MbomAdapterNodeCommand,
)
from .config import MbomExecutionProfile
from .domain import (
    MBOM_PUBLISH_OPERATION,
    MBOM_PUBLISH_SCHEMA_VERSION,
    MBOM_REQUEST_EVENT_TYPE,
    CurrentMbomMapping,
    MbomFaultKind,
    MbomMappingDisposition,
    MbomNodeObservation,
    MbomNodeResultState,
    MbomPublishRequest,
    MbomPublishRequestState,
    MbomResultAuthority,
    MbomTargetMode,
    MbomTargetSubmissionState,
    aggregate_node_results,
    canonical_hash,
    classify_mapping_observation,
)
from .frappe_repository import _request_value
from .frappe_validation import (
    insert_mbom_support_document,
    mbom_claim_write,
    mbom_result_transaction_write,
    save_mbom_support_document,
    validate_mbom_service_actor,
)


CLAIM_LEASE_SECONDS = 300
RECOVERY_BATCH_LIMIT = 100
_ACTIVE_STATES = frozenset(
    {
        MbomPublishRequestState.QUEUED.value,
        MbomPublishRequestState.PROCESSING.value,
        MbomPublishRequestState.FAILED_RETRYABLE.value,
        MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT.value,
        MbomPublishRequestState.MAPPING_CONFLICT.value,
    }
)
_TERMINAL_OUTBOX_STATES = frozenset(
    {
        "partially_succeeded",
        "succeeded",
        "failed_retryable",
        "failed_final",
        "uncertain",
        "mapping_conflict",
    }
)


def deterministic_mbom_result_id(attempt_global_id: UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f"npi.mbom.publish.result.v1:{attempt_global_id}")


def deterministic_mbom_node_result_id(
    attempt_global_id: UUID, stable_line_key: str
) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"npi.mbom.publish.node-result.v1:{attempt_global_id}:{stable_line_key}",
    )


@dataclass(frozen=True, slots=True)
class MbomPublishExecutionRoute:
    outbox_event_id: UUID
    request_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    source_stream_key_hash: str
    service_actor_user_id: str
    target_idempotency_key_hash: str
    semantic_effect_hash: str


@dataclass(frozen=True, slots=True)
class ClaimedMbomPublishMessage:
    outbox_event_id: UUID
    request_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trace_id: str
    claim_token: UUID
    lease_expires_at: datetime
    command: MbomAdapterCommand
    profile_reference: object
    service_actor_user_id: str
    expired_recovery: bool
    recovered_after_adapter_boundary: bool


@dataclass(frozen=True, slots=True)
class MbomPublishWorkerOutcome:
    outbox_event_id: UUID
    request_global_id: UUID
    state: str
    disposition: str
    result_global_id: UUID | None = None
    mapping_advanced_count: int = 0


class MbomPublishWorkerFinalFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _project_for(row: Any) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=str(_value(row, "tenant_id")),
        global_id=UUID(str(_value(row, "project_global_id"))),
    )


def _read_execution_route(outbox_event_id: UUID) -> MbomPublishExecutionRoute | None:
    try:
        outbox = frappe.get_doc("NPI Outbox Message", str(outbox_event_id))
    except frappe.DoesNotExistError:
        return None
    if not _is_mbom_outbox(outbox):
        return None
    request_id = _value(outbox, "mbom_request_global_id")
    if not request_id:
        return None
    try:
        request = frappe.get_doc("NPI MBOM Publish Request", str(request_id))
        value = _request_value(_project_for(request), request)
        _require_outbox_binding(outbox, value)
        actor = value.service_actor_user_id
        if value.profile.target_mode is MbomTargetMode.MOCK or not actor:
            return None
        validate_mbom_service_actor(actor)
        return MbomPublishExecutionRoute(
            outbox_event_id,
            value.global_id,
            value.source.tenant_id,
            value.source.project_global_id,
            value.source.source_stream_key_hash,
            actor,
            str(value.target_idempotency_key_hash),
            value.semantic_effect_hash,
        )
    except (frappe.DoesNotExistError, RuntimeError, ValueError):
        return None


class FrappeMbomPublishWorkerRepository:
    """Persist one P8-04 batch attempt with no generic replay authority."""

    def execution_route(self, outbox_event_id: UUID) -> MbomPublishExecutionRoute | None:
        return _read_execution_route(outbox_event_id)

    def claim(
        self,
        outbox_event_id: UUID,
        *,
        now: datetime,
        lease_seconds: int = CLAIM_LEASE_SECONDS,
        expected_route: MbomPublishExecutionRoute | None = None,
    ) -> ClaimedMbomPublishMessage | None:
        route = _read_execution_route(outbox_event_id)
        if route is None:
            return None
        if expected_route is not None and route != expected_route:
            raise RuntimeError("MBOM execution route changed before claim.")
        guard = _locked_guard(route)
        outbox = _optional_locked_doc("NPI Outbox Message", str(outbox_event_id))
        if outbox is None or not _is_mbom_outbox(outbox):
            return None
        request = _required_locked_request(outbox)
        value = _request_value(_project_for(request), request)
        _require_outbox_binding(outbox, value)
        state = str(_value(outbox, "state"))
        if state in _TERMINAL_OUTBOX_STATES:
            _require_terminal_guard(guard, value)
            return None
        _require_active_guard(guard, value)
        if value.service_actor_user_id != route.service_actor_user_id:
            raise RuntimeError("MBOM service actor binding changed before claim.")
        expired = False
        recovered_after_boundary = False
        previous_attempt = None
        if state == "processing":
            expires_at = _datetime_value(_value(outbox, "lease_expires_at"))
            if _aware_utc(now) < expires_at:
                return None
            expired = True
            previous_attempt = _required_attempt(outbox)
            _require_attempt_binding(previous_attempt, outbox, value)
            recovered_after_boundary = bool(_value(outbox, "adapter_boundary_crossed"))
            if recovered_after_boundary != bool(
                _value(previous_attempt, "adapter_boundary_crossed")
            ):
                raise RuntimeError("Persisted MBOM adapter-boundary evidence is inconsistent.")
        elif state != "pending":
            return None
        elif value.state is not MbomPublishRequestState.QUEUED:
            raise RuntimeError("Persisted MBOM request and Outbox states are inconsistent.")

        claimed_at = _aware_utc(now)
        previous_count = int(_value(outbox, "attempt_count") or 0)
        if recovered_after_boundary:
            attempt = previous_attempt
            assert attempt is not None
            token = UUID(str(_value(attempt, "claim_token")))
            attempt_number = int(_value(attempt, "attempt_number"))
            expires_at = claimed_at
            command = _command_from_attempt(attempt, value)
        else:
            attempt_number = previous_count + 1
            token = uuid4()
            expires_at = claimed_at.replace(microsecond=0) + timedelta(
                seconds=lease_seconds
            )
            if previous_attempt is not None:
                _finish_expired_attempt(previous_attempt, claimed_at)
            command = _command(value, request, attempt_number=attempt_number)

        with mbom_claim_write(route.service_actor_user_id) as capability:
            if previous_attempt is not None and not recovered_after_boundary:
                save_mbom_support_document(previous_attempt, capability=capability)
            outbox.state = "processing"
            outbox.disposition = (
                "recover_uncertain" if recovered_after_boundary else "processing"
            )
            outbox.claim_token = str(token)
            outbox.claimed_at = _database_datetime(claimed_at)
            outbox.lease_expires_at = _database_datetime(expires_at)
            if not recovered_after_boundary:
                outbox.attempt_count = attempt_number
                outbox.mbom_last_attempt_global_id = str(command.attempt_global_id)
                outbox.adapter_boundary_crossed = 0
                _insert_attempt(outbox, value, command, token, claimed_at, capability)
            outbox.last_error_code = None
            outbox.last_error_at = None
            outbox.mbom_result_global_id = None
            save_mbom_support_document(outbox, capability=capability)
            if value.state is MbomPublishRequestState.QUEUED:
                request.state = MbomPublishRequestState.PROCESSING.value
                request.optimistic_version = int(_value(request, "optimistic_version") or 0) + 1
                request.updated_at = _database_datetime(claimed_at)
                save_mbom_support_document(request, capability=capability)
            for node in _locked_assembly_nodes(value.global_id):
                if str(_value(node, "state")) == "queued":
                    node.state = "processing"
                    node.optimistic_version = int(_value(node, "optimistic_version") or 0) + 1
                    node.updated_at = _database_datetime(claimed_at)
                    save_mbom_support_document(node, capability=capability)
            _set_guard_active(guard, value, "processing", claimed_at, capability)
            _append_audit(
                value,
                "mbom_publish.claim_recovered" if expired else "mbom_publish.claim",
                "processing",
                {
                    "attemptGlobalId": str(command.attempt_global_id),
                    "attemptNumber": attempt_number,
                    "expiredRecovery": expired,
                    "recoveredAfterAdapterBoundary": recovered_after_boundary,
                },
            )
        return ClaimedMbomPublishMessage(
            outbox_event_id,
            value.global_id,
            value.source.tenant_id,
            value.source.project_global_id,
            value.trace_id,
            token,
            expires_at,
            command,
            value.profile,
            route.service_actor_user_id,
            expired,
            recovered_after_boundary,
        )

    def require_execution_profile(
        self,
        claim: ClaimedMbomPublishMessage,
        profile: MbomExecutionProfile | None,
    ) -> MbomExecutionProfile:
        if (
            not isinstance(profile, MbomExecutionProfile)
            or profile.reference != claim.profile_reference
            or profile.tenant_id != claim.tenant_id
            or profile.project_global_id != str(claim.project_global_id)
            or profile.target_mode is MbomTargetMode.MOCK
            or MBOM_PUBLISH_OPERATION not in profile.allowed_operations
            or profile.service_actor_user_id != claim.service_actor_user_id
        ):
            raise MbomPublishWorkerFinalFailure("MBOM_PUBLISH_EXECUTION_PROFILE_UNAVAILABLE")
        try:
            validate_mbom_service_actor(profile.service_actor_user_id)
        except (RuntimeError, ValueError) as error:
            raise MbomPublishWorkerFinalFailure(
                "MBOM_PUBLISH_EXECUTION_PROFILE_UNAVAILABLE"
            ) from error
        return profile

    def mark_adapter_boundary(
        self,
        claim: ClaimedMbomPublishMessage,
        *,
        profile: MbomExecutionProfile,
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
        crossed = _aware_utc(now)
        with mbom_claim_write(claim.service_actor_user_id) as capability:
            outbox.adapter_boundary_crossed = 1
            outbox.disposition = "adapter_boundary_crossed"
            save_mbom_support_document(outbox, capability=capability)
            attempt.adapter_boundary_crossed = 1
            attempt.transport_disposition = "adapter_boundary_crossed"
            _set_attempt_snapshot(attempt)
            save_mbom_support_document(attempt, capability=capability)
            _append_audit_from_claim(
                claim,
                "mbom_publish.adapter_boundary",
                "crossed",
                {"crossedAt": _utc_text(crossed)},
            )
        return True

    def seal_result(
        self,
        claim: ClaimedMbomPublishMessage,
        *,
        profile: MbomExecutionProfile | None,
        result: ClassifiedMbomAdapterResult,
        now: datetime,
        _allow_existing: bool = False,
    ) -> MbomPublishWorkerOutcome:
        outbox, request, attempt, guard = _required_current_claim(claim)
        value = _request_value(_project_for(request), request)
        if profile is not None:
            self.require_execution_profile(claim, profile)
        elif result.authority is not MbomResultAuthority.NONE or result.state in {
            MbomPublishRequestState.SYNTHETIC_VERIFIED,
            MbomPublishRequestState.SUCCEEDED,
        }:
            raise RuntimeError("An MBOM result without a profile cannot claim target truth.")
        expected_keys = tuple(node.stable_line_key for node in claim.command.nodes)
        if (
            not isinstance(result, ClassifiedMbomAdapterResult)
            or tuple(node.stable_line_key for node in result.observations) != expected_keys
        ):
            raise RuntimeError("MBOM result does not match the frozen node manifest.")
        observed_at = _aware_utc(now)
        result_id = deterministic_mbom_result_id(claim.command.attempt_global_id)
        existing = _existing_result(result_id)
        if existing is not None:
            if not _allow_existing or not _existing_result_matches(existing, claim):
                raise RuntimeError("Existing MBOM result evidence is inconsistent.")
            return MbomPublishWorkerOutcome(
                claim.outbox_event_id,
                claim.request_global_id,
                str(_value(existing, "state")),
                "already_sealed",
                result_id,
                0,
            )

        nodes = {str(_value(node, "stable_line_key")): node for node in _locked_assembly_nodes(value.global_id)}
        expectations = {item.stable_line_key: item for item in value.mbom_expectations}
        final_observations: list[MbomNodeObservation] = []
        mapping_actions: list[
            tuple[Any, Any, Any, MbomMappingDisposition, MbomNodeObservation]
        ] = []
        with mbom_result_transaction_write(claim.service_actor_user_id) as capability:
            for observation in result.observations:
                node = nodes.get(observation.stable_line_key)
                expectation = expectations.get(observation.stable_line_key)
                if node is None or expectation is None:
                    raise RuntimeError("MBOM result references an unavailable assembly node.")
                current_row, current = _locked_current_mapping(value, expectation)
                disposition = (
                    MbomMappingDisposition.SUBMITTED_BLOCK
                    if observation.state is MbomNodeResultState.BLOCKED_SUBMITTED
                    else classify_mapping_observation(
                        expectation=expectation,
                        current=current,
                        observation=observation,
                    )
                )
                final = observation
                if disposition is MbomMappingDisposition.SUBMITTED_BLOCK:
                    final = _conflict_observation(
                        observation,
                        MbomNodeResultState.BLOCKED_SUBMITTED,
                        MbomFaultKind.SUBMITTED_BOM,
                    )
                elif disposition in {
                    MbomMappingDisposition.EXPECTATION_CONFLICT,
                    MbomMappingDisposition.TARGET_IDENTITY_CONFLICT,
                }:
                    final = _conflict_observation(
                        observation,
                        MbomNodeResultState.OBSERVED_CONFLICT,
                        MbomFaultKind.STALE_MAPPING,
                    )
                final_observations.append(final)
                mapping_actions.append(
                    (node, current_row, expectation, disposition, observation)
                )

            final_values = tuple(final_observations)
            aggregate_state = aggregate_node_results(final_values)
            aggregate_authority = (
                MbomResultAuthority.SYNTHETIC
                if all(item.authority is MbomResultAuthority.SYNTHETIC for item in final_values)
                else (
                    MbomResultAuthority.AUTHORITATIVE_SANDBOX
                    if all(
                        item.authority is MbomResultAuthority.AUTHORITATIVE_SANDBOX
                        for item in final_values
                    )
                    else MbomResultAuthority.NONE
                )
            )
            node_rows: list[tuple[Any, UUID, MbomNodeObservation, str]] = []
            for final, (node, _head, _expectation, _disposition, _original) in zip(
                final_values, mapping_actions, strict=True
            ):
                node_result_id = deterministic_mbom_node_result_id(
                    claim.command.attempt_global_id, final.stable_line_key
                )
                snapshot = _node_result_snapshot(
                    claim, result_id, node_result_id, node, final, observed_at
                )
                node_rows.append((node, node_result_id, final, canonical_hash(snapshot)))

            node_set_hash = canonical_hash(
                [
                    {"globalId": str(node_id), "nodeResultHash": digest}
                    for _node, node_id, _final, digest in node_rows
                ]
            )
            result_snapshot = {
                "schemaVersion": 1,
                "globalId": str(result_id),
                "requestGlobalId": str(claim.request_global_id),
                "outboxEventId": str(claim.outbox_event_id),
                "attemptGlobalId": str(claim.command.attempt_global_id),
                "attemptNumber": claim.command.attempt_number,
                "sourceHash": claim.command.source_hash,
                "topologyHash": claim.command.topology_hash,
                "itemMappingSetHash": claim.command.item_mapping_set_hash,
                "mbomMappingSetHash": claim.command.mbom_mapping_set_hash,
                "state": aggregate_state.value,
                "authority": aggregate_authority.value,
                "responseAuthenticated": all(
                    item.response_authenticated for item in final_values
                ),
                "responseHash": result.response_hash,
                "faultKind": _aggregate_fault(final_values).value,
                "nodeResultSetHash": node_set_hash,
                "observedAt": _utc_text(observed_at),
            }
            result_hash = canonical_hash(result_snapshot)
            insert_mbom_support_document(
                frappe.get_doc(
                    {
                        "doctype": "NPI MBOM Publish Result",
                        "global_id": str(result_id),
                        "request_global_id": str(claim.request_global_id),
                        "outbox_event_id": str(claim.outbox_event_id),
                        "attempt_global_id": str(claim.command.attempt_global_id),
                        "attempt_number": claim.command.attempt_number,
                        "source_hash": claim.command.source_hash,
                        "topology_hash": claim.command.topology_hash,
                        "item_mapping_set_hash": claim.command.item_mapping_set_hash,
                        "mbom_mapping_set_hash": claim.command.mbom_mapping_set_hash,
                        "state": aggregate_state.value,
                        "authority": aggregate_authority.value,
                        "response_authenticated": int(
                            all(item.response_authenticated for item in final_values)
                        ),
                        "response_hash": result.response_hash,
                        "fault_kind": _aggregate_fault(final_values).value,
                        "node_result_set_hash": node_set_hash,
                        "result_snapshot": result_snapshot,
                        "result_hash": result_hash,
                        "observed_at": _database_datetime(observed_at),
                    }
                ),
                capability=capability,
            )

            # Insert the aggregate Result before its linked node children. The
            # hashes were computed first, so link validation and immutable
            # result-set evidence are both exact in the same transaction.
            for node, node_result_id, final, node_hash in node_rows:
                snapshot = _node_result_snapshot(
                    claim, result_id, node_result_id, node, final, observed_at
                )
                if canonical_hash(snapshot) != node_hash:
                    raise RuntimeError("MBOM node result snapshot drifted before insert.")
                insert_mbom_support_document(
                    frappe.get_doc(
                        {
                            "doctype": "NPI MBOM Publish Node Result",
                            "global_id": str(node_result_id),
                            "request_global_id": str(claim.request_global_id),
                            "result_global_id": str(result_id),
                            "attempt_global_id": str(claim.command.attempt_global_id),
                            "node_global_id": str(_value(node, "global_id")),
                            "stable_line_key": final.stable_line_key,
                            "assembly_source_key": final.assembly_source_key,
                            "state": final.state.value,
                            "authority": final.authority.value,
                            "response_authenticated": int(final.response_authenticated),
                            "response_hash": final.response_hash,
                            "formal_bom_id": final.formal_bom_id,
                            "target_version": final.target_version,
                            "target_submission_state": (
                                final.target_submission_state.value
                                if final.target_submission_state
                                else None
                            ),
                            "fault_kind": final.fault_kind.value,
                            "node_result_snapshot": snapshot,
                            "node_result_hash": node_hash,
                            "observed_at": _database_datetime(observed_at),
                        }
                    ),
                    capability=capability,
                )

            advanced = 0
            for final, (
                node,
                head,
                expectation,
                disposition,
                original,
            ), (_n, node_id, _f, node_hash) in zip(
                final_values, mapping_actions, node_rows, strict=True
            ):
                if profile is not None:
                    if original.authority in {
                        MbomResultAuthority.SYNTHETIC,
                        MbomResultAuthority.AUTHORITATIVE_SANDBOX,
                    }:
                        if _record_mapping_observation(
                            value=value,
                            claim=claim,
                            profile=profile,
                            result_id=result_id,
                            node_result_id=node_id,
                            node_result_hash=node_hash,
                            observation=original,
                            expectation=expectation,
                            current_head=head,
                            disposition=disposition,
                            now=observed_at,
                            capability=capability,
                        ):
                            advanced += 1
                node.state = final.state.value
                node.result_global_id = str(node_id)
                node.optimistic_version = int(_value(node, "optimistic_version") or 0) + 1
                node.updated_at = _database_datetime(observed_at)
                save_mbom_support_document(node, capability=capability)

            _finish_attempt(attempt, result, aggregate_state, observed_at)
            save_mbom_support_document(attempt, capability=capability)
            request.state = aggregate_state.value
            request.result_global_id = str(result_id)
            request.optimistic_version = int(_value(request, "optimistic_version") or 0) + 1
            request.updated_at = _database_datetime(observed_at)
            save_mbom_support_document(request, capability=capability)
            outbox.state = _outbox_state(aggregate_state)
            outbox.disposition = result.transport_disposition
            outbox.mbom_result_global_id = str(result_id)
            outbox.last_error_code = result.safe_error_code
            outbox.last_error_at = (
                _database_datetime(observed_at) if result.safe_error_code else None
            )
            outbox.lease_expires_at = None
            save_mbom_support_document(outbox, capability=capability)
            _set_guard_terminal(guard, value, aggregate_state.value, observed_at, capability)
            _append_audit(
                value,
                "mbom_publish.result_observed",
                aggregate_state.value,
                {
                    "attemptGlobalId": str(claim.command.attempt_global_id),
                    "nodeResultSetHash": node_set_hash,
                    "resultGlobalId": str(result_id),
                    "resultHash": result_hash,
                },
            )
        return MbomPublishWorkerOutcome(
            claim.outbox_event_id,
            claim.request_global_id,
            aggregate_state.value,
            result.transport_disposition,
            result_id,
            advanced,
        )

    def recover_or_seal_result(self, claim, *, profile, result, now):
        return self.seal_result(
            claim,
            profile=profile,
            result=result,
            now=now,
            _allow_existing=True,
        )

    def recoverable_outbox_event_ids(self, *, now: datetime) -> tuple[UUID, ...]:
        rows = frappe.get_all(
            "NPI Outbox Message",
            filters={
                "schema_version": MBOM_PUBLISH_SCHEMA_VERSION,
                "event_type": MBOM_REQUEST_EVENT_TYPE,
                "operation": MBOM_PUBLISH_OPERATION,
                "state": ["in", ["pending", "processing"]],
            },
            fields=["event_id", "state", "lease_expires_at"],
            order_by="creation asc",
            limit=RECOVERY_BATCH_LIMIT,
        )
        current = _aware_utc(now)
        values: list[UUID] = []
        for row in rows:
            state = str(_value(row, "state"))
            if state == "pending" or (
                state == "processing"
                and _value(row, "lease_expires_at")
                and _datetime_value(_value(row, "lease_expires_at")) <= current
            ):
                values.append(UUID(str(_value(row, "event_id"))))
        return tuple(values)


def _command(
    value: MbomPublishRequest, request: Any, *, attempt_number: int
) -> MbomAdapterCommand:
    nodes = _locked_assembly_nodes(value.global_id)
    expectations = {item.stable_line_key: item for item in value.mbom_expectations}
    command_nodes = tuple(
        MbomAdapterNodeCommand.from_expectation(
            expectations[str(_value(node, "stable_line_key"))],
            node_global_id=UUID(str(_value(node, "global_id"))),
            node_snapshot={
                "line": _json_object(_value(node, "line_snapshot")),
                "itemReadiness": _json_object(_value(node, "item_readiness_snapshot")),
                "mbomExpectation": _json_object(_value(node, "mbom_expectation_snapshot")),
            },
        )
        for node in nodes
    )
    return MbomAdapterCommand(
        request_global_id=value.global_id,
        attempt_global_id=uuid4(),
        attempt_number=attempt_number,
        target_idempotency_key_hash=str(value.target_idempotency_key_hash),
        source_hash=value.source.source_hash,
        topology_hash=value.source.topology_hash,
        item_mapping_set_hash=value.item_mapping_set_hash,
        mbom_mapping_set_hash=value.mbom_mapping_set_hash,
        node_manifest_hash=str(_value(_outbox_for_request(value.global_id), "mbom_node_manifest_hash")),
        request_snapshot=value.payload(),
        nodes=command_nodes,
    )


def _command_from_attempt(attempt: Any, value: MbomPublishRequest) -> MbomAdapterCommand:
    snapshot = _json_object(_value(attempt, "request_snapshot"))
    if canonical_hash(snapshot) != str(_value(attempt, "request_snapshot_hash")):
        raise RuntimeError("Persisted MBOM attempt snapshot is invalid.")
    request = _required_locked_request(_outbox_for_request(value.global_id))
    command = _command(value, request, attempt_number=int(_value(attempt, "attempt_number")))
    restored = replace(
        command, attempt_global_id=UUID(str(_value(attempt, "global_id")))
    )
    if restored.snapshot() != snapshot:
        raise RuntimeError("Persisted MBOM attempt command binding is invalid.")
    return restored


def _insert_attempt(outbox, value, command, token, now, capability) -> None:
    snapshot = command.snapshot()
    attempt_snapshot = {
        "globalId": str(command.attempt_global_id),
        "requestGlobalId": str(value.global_id),
        "outboxEventId": str(_value(outbox, "event_id")),
        "attemptNumber": command.attempt_number,
        "claimToken": str(token),
        "state": "started",
        "adapterBoundaryCrossed": False,
        "requestSnapshotHash": canonical_hash(snapshot),
        "startedAt": _utc_text(now),
    }
    insert_mbom_support_document(
        frappe.get_doc(
            {
                "doctype": "NPI MBOM Publish Attempt",
                "global_id": str(command.attempt_global_id),
                "request_global_id": str(value.global_id),
                "outbox_event_id": str(_value(outbox, "event_id")),
                "attempt_number": command.attempt_number,
                "claim_token": str(token),
                "target_idempotency_key_hash": command.target_idempotency_key_hash,
                "source_hash": command.source_hash,
                "topology_hash": command.topology_hash,
                "item_mapping_set_hash": command.item_mapping_set_hash,
                "mbom_mapping_set_hash": command.mbom_mapping_set_hash,
                "node_manifest_hash": command.node_manifest_hash,
                "profile_id": value.profile.profile_id,
                "profile_version": value.profile.profile_version,
                "state": "started",
                "adapter_boundary_crossed": 0,
                "request_snapshot": snapshot,
                "request_snapshot_hash": canonical_hash(snapshot),
                "started_at": _database_datetime(now),
                "attempt_snapshot": attempt_snapshot,
                "attempt_hash": canonical_hash(attempt_snapshot),
            }
        ),
        capability=capability,
    )


def _finish_expired_attempt(attempt: Any, now: datetime) -> None:
    if bool(_value(attempt, "adapter_boundary_crossed")):
        return
    attempt.state = "observed_failure"
    attempt.transport_disposition = "expired_before_boundary"
    attempt.fault_kind = MbomFaultKind.TARGET_UNAVAILABLE.value
    attempt.reconciliation_required = 0
    attempt.safe_error_code = "MBOM_PUBLISH_EXPIRED_BEFORE_BOUNDARY"
    attempt.finished_at = _database_datetime(now)
    _set_attempt_snapshot(attempt)


def _finish_attempt(attempt, result, state, now) -> None:
    attempt.state = {
        MbomPublishRequestState.SYNTHETIC_VERIFIED: "synthetic_verified",
        MbomPublishRequestState.SUCCEEDED: "observed_success",
        MbomPublishRequestState.PARTIALLY_SUCCEEDED: "observed_partial",
        MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT: "uncertain",
    }.get(state, "observed_failure")
    attempt.transport_disposition = result.transport_disposition
    attempt.response_hash = result.response_hash
    attempt.fault_kind = _aggregate_fault(result.observations).value
    attempt.reconciliation_required = int(result.reconciliation_required)
    attempt.safe_error_code = result.safe_error_code
    attempt.finished_at = _database_datetime(now)
    _set_attempt_snapshot(attempt)


def _set_attempt_snapshot(attempt: Any) -> None:
    snapshot = {
        "globalId": str(_value(attempt, "global_id")),
        "requestGlobalId": str(_value(attempt, "request_global_id")),
        "outboxEventId": str(_value(attempt, "outbox_event_id")),
        "attemptNumber": int(_value(attempt, "attempt_number")),
        "claimToken": str(_value(attempt, "claim_token")),
        "state": str(_value(attempt, "state")),
        "adapterBoundaryCrossed": bool(_value(attempt, "adapter_boundary_crossed")),
        "requestSnapshotHash": str(_value(attempt, "request_snapshot_hash")),
        "transportDisposition": _value(attempt, "transport_disposition"),
        "responseHash": _value(attempt, "response_hash"),
        "faultKind": _value(attempt, "fault_kind"),
        "reconciliationRequired": bool(_value(attempt, "reconciliation_required")),
        "safeErrorCode": _value(attempt, "safe_error_code"),
        "startedAt": _utc_text(_datetime_value(_value(attempt, "started_at"))),
        "finishedAt": (
            _utc_text(_datetime_value(_value(attempt, "finished_at")))
            if _value(attempt, "finished_at")
            else None
        ),
    }
    attempt.attempt_snapshot = snapshot
    attempt.attempt_hash = canonical_hash(snapshot)


def _node_result_snapshot(claim, result_id, node_result_id, node, observation, now):
    return {
        "schemaVersion": 1,
        "globalId": str(node_result_id),
        "requestGlobalId": str(claim.request_global_id),
        "resultGlobalId": str(result_id),
        "attemptGlobalId": str(claim.command.attempt_global_id),
        "nodeGlobalId": str(_value(node, "global_id")),
        "stableLineKey": observation.stable_line_key,
        "assemblySourceKey": observation.assembly_source_key,
        "state": observation.state.value,
        "authority": observation.authority.value,
        "responseAuthenticated": observation.response_authenticated,
        "responseHash": observation.response_hash,
        "formalBomId": observation.formal_bom_id,
        "targetVersion": observation.target_version,
        "targetSubmissionState": (
            observation.target_submission_state.value
            if observation.target_submission_state
            else None
        ),
        "faultKind": observation.fault_kind.value,
        "observedAt": _utc_text(now),
    }


def _locked_current_mapping(value, expectation):
    name = frappe.db.get_value(
        "NPI MBOM Mapping Head",
        {"assembly_source_key": expectation.assembly_source_key},
        "name",
    )
    if not name:
        return None, None
    row = _optional_locked_doc("NPI MBOM Mapping Head", str(name))
    if row is None:
        raise RuntimeError("Current MBOM mapping head is unavailable.")
    if (
        str(_value(row, "tenant_id")) != value.source.tenant_id
        or str(_value(row, "project_global_id"))
        != str(value.source.project_global_id)
        or str(_value(row, "ebom_global_id")) != str(value.source.ebom_global_id)
        or str(_value(row, "assembly_source_key"))
        != expectation.assembly_source_key
        or str(_value(row, "stable_line_key")) != expectation.stable_line_key
    ):
        raise RuntimeError("Current MBOM mapping head is invalid.")
    snapshot = _json_object(_value(row, "head_snapshot"))
    expected = {
        "schemaVersion": 1,
        "globalId": str(_value(row, "global_id")),
        "tenantId": value.source.tenant_id,
        "projectGlobalId": str(value.source.project_global_id),
        "ebomGlobalId": str(value.source.ebom_global_id),
        "assemblySourceKey": expectation.assembly_source_key,
        "stableLineKey": expectation.stable_line_key,
        "mappingVersion": int(_value(row, "mapping_version")),
        "formalBomId": str(_value(row, "formal_bom_id")),
        "targetVersion": str(_value(row, "target_version")),
        "targetSubmissionState": str(_value(row, "target_submission_state")),
        "currentObservationGlobalId": str(_value(row, "current_observation")),
        "currentObservationHash": str(_value(row, "current_observation_hash")),
        "updatedAt": _utc_text(_datetime_value(_value(row, "updated_at"))),
    }
    if snapshot != expected or canonical_hash(snapshot) != str(_value(row, "head_hash")):
        raise RuntimeError("Current MBOM mapping head is invalid.")
    return row, CurrentMbomMapping(
        int(_value(row, "mapping_version")),
        str(_value(row, "formal_bom_id")),
        str(_value(row, "target_version")),
        MbomTargetSubmissionState(str(_value(row, "target_submission_state"))),
        str(_value(row, "current_observation_hash")),
    )


def _record_mapping_observation(
    *, value, claim, profile, result_id, node_result_id, node_result_hash,
    observation, expectation, current_head, disposition, now, capability
) -> bool:
    previous_version = 0 if current_head is None else int(_value(current_head, "mapping_version"))
    previous_hash = None if current_head is None else str(_value(current_head, "current_observation_hash"))
    observation_id = uuid4()
    advances = (
        disposition is MbomMappingDisposition.ADVANCE
        and observation.authority is MbomResultAuthority.AUTHORITATIVE_SANDBOX
    )
    cas_savepoint = "mbom_publish_mapping_cas"
    use_savepoint = bool(
        advances
        and current_head is None
        and callable(getattr(frappe.db, "savepoint", None))
    )
    if advances and current_head is None and not use_savepoint:
        raise RuntimeError("MBOM first-head CAS requires a database savepoint.")
    if use_savepoint:
        frappe.db.savepoint(cas_savepoint)
    recorded_disposition = (
        "advanced"
        if advances
        else (
            "non_authoritative"
            if observation.authority is MbomResultAuthority.SYNTHETIC
            else (
                "blocked_submitted"
                if disposition is MbomMappingDisposition.SUBMITTED_BLOCK
                else "observed_conflict"
            )
        )
    )
    mapping_version = previous_version + (1 if advances else 0)
    snapshot = {
        "schemaVersion": 1,
        "globalId": str(observation_id),
        "tenantId": value.source.tenant_id,
        "projectGlobalId": str(value.source.project_global_id),
        "ebomGlobalId": str(value.source.ebom_global_id),
        "assemblySourceKey": observation.assembly_source_key,
        "stableLineKey": observation.stable_line_key,
        "mappingVersion": mapping_version,
        "formalBomId": observation.formal_bom_id,
        "targetVersion": observation.target_version,
        "targetSubmissionState": (
            observation.target_submission_state.value
            if observation.target_submission_state
            else None
        ),
        "requestGlobalId": str(claim.request_global_id),
        "outboxEventId": str(claim.outbox_event_id),
        "attemptGlobalId": str(claim.command.attempt_global_id),
        "resultGlobalId": str(result_id),
        "nodeResultGlobalId": str(node_result_id),
        "profileId": profile.profile_id,
        "profileVersion": profile.profile_version,
        "environmentCode": profile.environment_code,
        "authority": observation.authority.value,
        "disposition": recorded_disposition,
        "previousMappingVersion": previous_version,
        "previousObservationHash": previous_hash,
        "targetResultHash": node_result_hash,
        "observedAt": _utc_text(now),
    }
    observation_hash = canonical_hash(snapshot)
    insert_mbom_support_document(
        frappe.get_doc(
            {
                "doctype": "NPI MBOM Mapping Observation",
                "global_id": str(observation_id),
                "tenant_id": value.source.tenant_id,
                "project_global_id": str(value.source.project_global_id),
                "ebom_global_id": str(value.source.ebom_global_id),
                "assembly_source_key": observation.assembly_source_key,
                "stable_line_key": observation.stable_line_key,
                "mapping_version": mapping_version,
                "formal_bom_id": observation.formal_bom_id,
                "target_version": observation.target_version,
                "target_submission_state": (
                    observation.target_submission_state.value
                    if observation.target_submission_state
                    else None
                ),
                "request_global_id": str(claim.request_global_id),
                "outbox_event_id": str(claim.outbox_event_id),
                "attempt_global_id": str(claim.command.attempt_global_id),
                "result_global_id": str(result_id),
                "node_result_global_id": str(node_result_id),
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
                "environment_code": profile.environment_code,
                "authority": observation.authority.value,
                "disposition": recorded_disposition,
                "previous_mapping_version": previous_version,
                "previous_observation_hash": previous_hash,
                "target_result_hash": node_result_hash,
                "observation_snapshot": snapshot,
                "observation_hash": observation_hash,
                "observed_at": _database_datetime(now),
            }
        ),
        capability=capability,
    )
    if not advances:
        return False
    head_id = uuid4() if current_head is None else UUID(str(_value(current_head, "global_id")))
    head_snapshot = {
        "schemaVersion": 1,
        "globalId": str(head_id),
        "tenantId": value.source.tenant_id,
        "projectGlobalId": str(value.source.project_global_id),
        "ebomGlobalId": str(value.source.ebom_global_id),
        "assemblySourceKey": observation.assembly_source_key,
        "stableLineKey": observation.stable_line_key,
        "mappingVersion": mapping_version,
        "formalBomId": observation.formal_bom_id,
        "targetVersion": observation.target_version,
        "targetSubmissionState": observation.target_submission_state.value,
        "currentObservationGlobalId": str(observation_id),
        "currentObservationHash": observation_hash,
        "updatedAt": _utc_text(now),
    }
    values = {
        "global_id": str(head_id),
        "tenant_id": value.source.tenant_id,
        "project_global_id": str(value.source.project_global_id),
        "ebom_global_id": str(value.source.ebom_global_id),
        "assembly_source_key": observation.assembly_source_key,
        "stable_line_key": observation.stable_line_key,
        "mapping_version": mapping_version,
        "formal_bom_id": observation.formal_bom_id,
        "target_version": observation.target_version,
        "target_submission_state": observation.target_submission_state.value,
        "current_observation": str(observation_id),
        "current_observation_hash": observation_hash,
        "head_snapshot": head_snapshot,
        "head_hash": canonical_hash(head_snapshot),
        "updated_at": _database_datetime(now),
    }
    if current_head is None:
        try:
            insert_mbom_support_document(
                frappe.get_doc({"doctype": "NPI MBOM Mapping Head", **values}),
                capability=capability,
            )
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
            frappe.db.rollback(save_point=cas_savepoint)
            latest_head, latest = _locked_current_mapping(value, expectation)
            if latest_head is None or latest is None:
                raise RuntimeError("MBOM mapping-head race left no legal current head.")
            _record_mapping_observation(
                value=value,
                claim=claim,
                profile=profile,
                result_id=result_id,
                node_result_id=node_result_id,
                node_result_hash=node_result_hash,
                observation=observation,
                expectation=expectation,
                current_head=latest_head,
                disposition=MbomMappingDisposition.EXPECTATION_CONFLICT,
                now=now,
                capability=capability,
            )
            return False
    else:
        # The locked head is the CAS compare point; submitted and stale truth
        # were rejected before this mutation.
        for key, item in values.items():
            setattr(current_head, key, item)
        save_mbom_support_document(current_head, capability=capability)
    return True


def _conflict_observation(observation, state, fault):
    return MbomNodeObservation(
        observation.stable_line_key,
        observation.assembly_source_key,
        state,
        MbomResultAuthority.NONE,
        False,
        observation.response_hash,
        fault_kind=fault,
    )


def _required_current_claim(claim):
    outbox = _optional_locked_doc("NPI Outbox Message", str(claim.outbox_event_id))
    if (
        outbox is None
        or not _is_mbom_outbox(outbox)
        or str(_value(outbox, "state")) != "processing"
        or str(_value(outbox, "claim_token")) != str(claim.claim_token)
        or str(_value(outbox, "mbom_last_attempt_global_id"))
        != str(claim.command.attempt_global_id)
        or int(_value(outbox, "attempt_count")) != claim.command.attempt_number
    ):
        raise RuntimeError("MBOM Outbox claim is no longer current.")
    request = _required_locked_request(outbox)
    value = _request_value(_project_for(request), request)
    _require_outbox_binding(outbox, value)
    attempt = _required_attempt(outbox)
    _require_attempt_binding(attempt, outbox, value)
    guard = _locked_guard(
        MbomPublishExecutionRoute(
            claim.outbox_event_id,
            claim.request_global_id,
            claim.tenant_id,
            claim.project_global_id,
            value.source.source_stream_key_hash,
            claim.service_actor_user_id,
            str(value.target_idempotency_key_hash),
            value.semantic_effect_hash,
        )
    )
    _require_active_guard(guard, value)
    return outbox, request, attempt, guard


def _required_locked_request(outbox):
    request = _optional_locked_doc(
        "NPI MBOM Publish Request", str(_value(outbox, "mbom_request_global_id"))
    )
    if request is None:
        raise RuntimeError("Persisted MBOM publish request is unavailable.")
    return request


def _required_attempt(outbox):
    attempt = _optional_locked_doc(
        "NPI MBOM Publish Attempt", str(_value(outbox, "mbom_last_attempt_global_id"))
    )
    if attempt is None:
        raise RuntimeError("Persisted MBOM publish attempt is unavailable.")
    return attempt


def _require_attempt_binding(attempt, outbox, value):
    if (
        str(_value(attempt, "request_global_id")) != str(value.global_id)
        or str(_value(attempt, "outbox_event_id")) != str(_value(outbox, "event_id"))
        or int(_value(attempt, "attempt_number")) != int(_value(outbox, "attempt_count"))
        or str(_value(attempt, "source_hash")) != value.source.source_hash
        or str(_value(attempt, "topology_hash")) != value.source.topology_hash
        or str(_value(attempt, "item_mapping_set_hash")) != value.item_mapping_set_hash
        or str(_value(attempt, "mbom_mapping_set_hash")) != value.mbom_mapping_set_hash
        or str(_value(attempt, "node_manifest_hash"))
        != str(_value(outbox, "mbom_node_manifest_hash"))
    ):
        raise RuntimeError("Persisted MBOM publish attempt binding is invalid.")


def _require_outbox_binding(outbox, value):
    if (
        str(_value(outbox, "mbom_request_global_id")) != str(value.global_id)
        or str(_value(outbox, "source_hash")) != value.source.source_hash
        or str(_value(outbox, "mbom_topology_hash")) != value.source.topology_hash
        or str(_value(outbox, "item_mapping_set_hash")) != value.item_mapping_set_hash
        or str(_value(outbox, "mbom_mapping_set_hash")) != value.mbom_mapping_set_hash
        or str(_value(outbox, "target_idempotency_key_hash"))
        != str(value.target_idempotency_key_hash)
        or str(_value(outbox, "semantic_effect_hash")) != value.semantic_effect_hash
        or str(_value(outbox, "service_actor_user_id")) != str(value.service_actor_user_id)
    ):
        raise RuntimeError("Persisted MBOM Outbox binding is invalid.")


def _locked_guard(route):
    name = frappe.db.get_value(
        "NPI MBOM Publish Stream Guard",
        {"source_stream_key_hash": route.source_stream_key_hash},
        "name",
    )
    if not name:
        raise RuntimeError("The MBOM source stream guard is unavailable.")
    guard = _optional_locked_doc("NPI MBOM Publish Stream Guard", str(name))
    if guard is None:
        raise RuntimeError("The MBOM source stream guard is unavailable.")
    if (
        str(_value(guard, "tenant_id")) != route.tenant_id
        or str(_value(guard, "project_global_id")) != str(route.project_global_id)
        or str(_value(guard, "source_stream_key_hash")) != route.source_stream_key_hash
    ):
        raise RuntimeError("Persisted MBOM source stream guard binding is invalid.")
    return guard


def _require_active_guard(guard, value):
    if (
        str(_value(guard, "active_request_global_id")) != str(value.global_id)
        or str(_value(guard, "active_target_idempotency_key_hash"))
        != str(value.target_idempotency_key_hash)
        or str(_value(guard, "active_state")) not in _ACTIVE_STATES
    ):
        raise RuntimeError("Persisted MBOM source stream guard active binding is invalid.")


def _require_terminal_guard(guard, value):
    if (
        _value(guard, "active_request_global_id")
        or _value(guard, "active_target_idempotency_key_hash")
        or _value(guard, "active_state")
        or str(_value(guard, "last_request_global_id")) != str(value.global_id)
        or str(_value(guard, "last_target_idempotency_key_hash"))
        != str(value.target_idempotency_key_hash)
        or str(_value(guard, "last_state")) != value.state.value
    ):
        raise RuntimeError("Persisted MBOM terminal retained binding is invalid.")


def _set_guard_active(guard, value, state, now, capability):
    guard.active_request_global_id = str(value.global_id)
    guard.active_target_idempotency_key_hash = value.target_idempotency_key_hash
    guard.active_state = state
    guard.optimistic_version = int(_value(guard, "optimistic_version") or 0) + 1
    guard.updated_at = _database_datetime(now)
    save_mbom_support_document(guard, capability=capability)


def _set_guard_terminal(guard, value, state, now, capability):
    guard.active_request_global_id = None
    guard.active_target_idempotency_key_hash = None
    guard.active_state = None
    guard.last_request_global_id = str(value.global_id)
    guard.last_target_idempotency_key_hash = value.target_idempotency_key_hash
    guard.last_state = state
    guard.blocked_reason_code = (
        "MBOM_PUBLISH_RECONCILIATION_REQUIRED"
        if state in {"uncertain_after_timeout", "mapping_conflict"}
        else None
    )
    guard.optimistic_version = int(_value(guard, "optimistic_version") or 0) + 1
    guard.updated_at = _database_datetime(now)
    save_mbom_support_document(guard, capability=capability)


def _locked_assembly_nodes(request_id):
    names = frappe.get_all(
        "NPI MBOM Publish Node",
        filters={"request_global_id": str(request_id), "source_role": "assembly"},
        pluck="name",
        order_by="stable_line_key asc",
    )
    return tuple(
        node
        for name in names
        if (node := _optional_locked_doc("NPI MBOM Publish Node", str(name))) is not None
    )


def _outbox_for_request(request_id):
    name = frappe.db.get_value(
        "NPI Outbox Message", {"mbom_request_global_id": str(request_id)}, "name"
    )
    if not name:
        raise RuntimeError("Persisted MBOM Outbox message is unavailable.")
    outbox = _optional_locked_doc("NPI Outbox Message", str(name))
    if outbox is None:
        raise RuntimeError("Persisted MBOM Outbox message is unavailable.")
    return outbox


def _existing_result(result_id):
    try:
        return frappe.get_doc("NPI MBOM Publish Result", str(result_id))
    except frappe.DoesNotExistError:
        return None


def _existing_result_matches(row, claim):
    return bool(
        str(_value(row, "global_id")) == str(deterministic_mbom_result_id(claim.command.attempt_global_id))
        and str(_value(row, "attempt_global_id")) == str(claim.command.attempt_global_id)
        and str(_value(row, "request_global_id")) == str(claim.request_global_id)
        and str(_value(row, "outbox_event_id")) == str(claim.outbox_event_id)
        and canonical_hash(_json_object(_value(row, "result_snapshot")))
        == str(_value(row, "result_hash"))
    )


def _aggregate_fault(values):
    return next(
        (value.fault_kind for value in values if value.fault_kind is not MbomFaultKind.NONE),
        MbomFaultKind.NONE,
    )


def _outbox_state(state):
    return {
        MbomPublishRequestState.SYNTHETIC_VERIFIED: "succeeded",
        MbomPublishRequestState.SUCCEEDED: "succeeded",
        MbomPublishRequestState.PARTIALLY_SUCCEEDED: "partially_succeeded",
        MbomPublishRequestState.FAILED_RETRYABLE: "failed_retryable",
        MbomPublishRequestState.FAILED_FINAL: "failed_final",
        MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT: "uncertain",
        MbomPublishRequestState.MAPPING_CONFLICT: "mapping_conflict",
    }[state]


def _is_mbom_outbox(row):
    return bool(
        int(_value(row, "schema_version") or 0) == MBOM_PUBLISH_SCHEMA_VERSION
        and str(_value(row, "event_type")) == MBOM_REQUEST_EVENT_TYPE
        and str(_value(row, "operation")) == MBOM_PUBLISH_OPERATION
        and int(_value(row, "object_version") or 0) == 1
    )


def _optional_locked_doc(doctype, name):
    try:
        return frappe.get_doc(doctype, name, for_update=True)
    except frappe.DoesNotExistError:
        return None


def _append_audit(value, operation, result, summary):
    event = create_audit_event(
        actor=str(value.service_actor_user_id),
        trace_id=value.trace_id,
        operation=operation,
        global_id=value.global_id,
        object_version=1,
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


def _append_audit_from_claim(claim, operation, result, summary):
    value = SimpleNamespace(
        service_actor_user_id=claim.service_actor_user_id,
        trace_id=claim.trace_id,
        global_id=claim.request_global_id,
    )
    _append_audit(value, operation, result, summary)


def _value(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def _aware_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("MBOM worker time must be timezone-aware.")
    return value.astimezone(UTC)


def _datetime_value(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("Persisted MBOM worker time is invalid.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_text(value):
    return _aware_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")
