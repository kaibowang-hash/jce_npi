from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid5

import frappe

from npi_core.foundation.audit import create_audit_event

from .adapters import ClassifiedToolAssetAdapterResult, ToolAssetAdapterCommand
from .config import ToolAssetExecutionProfile
from .diagnostics import tool_asset_process_stage_step
from .execution_domain import (
    TOOL_ASSET_EXECUTION_API_VERSION,
    TOOL_ASSET_EXECUTION_SCHEMA_VERSION,
    TOOL_ASSET_OUTBOX_SCHEMA_VERSION,
    TOOL_ASSET_REQUEST_EVENT_TYPE,
    ToolAssetExecutionContractError,
    ToolAssetExecutionOperation,
    ToolAssetExecutionRequest,
    ToolAssetExecutionRequestState,
    ToolAssetMappingDisposition,
    ToolAssetResultAuthority,
    canonical_hash,
    classify_mapping_result,
    tool_asset_execution_request_from_mapping,
)
from .execution_frappe_validation import (
    insert_tool_asset_audit_document,
    insert_tool_asset_support_document,
    save_tool_asset_support_document,
    tool_asset_claim_write,
    tool_asset_result_transaction_write,
)


CLAIM_LEASE_SECONDS = 300
RECOVERY_BATCH_LIMIT = 100
_RESULT_NAMESPACE = UUID("6877d7c3-aebc-4a17-a022-4959df87e13e")
_FIELD_NAMESPACE = UUID("23f53be5-fffb-42ad-b5b5-bbe805f8a9ec")
_OBSERVATION_NAMESPACE = UUID("5dc174fd-f5ab-4c5a-a181-a11ef9d67c76")
_ACTIVE_STATES = frozenset({"pending", "processing"})
_TERMINAL_STATES = frozenset({"partially_succeeded", "succeeded", "failed_retryable", "failed_final", "uncertain", "mapping_conflict"})


def deterministic_tool_asset_result_id(attempt_global_id: UUID) -> UUID:
    return uuid5(_RESULT_NAMESPACE, str(attempt_global_id))


def deterministic_tool_asset_field_result_id(attempt_global_id: UUID, field_code: str) -> UUID:
    return uuid5(_FIELD_NAMESPACE, f"{attempt_global_id}:{field_code}")


@dataclass(frozen=True, slots=True)
class ToolAssetExecutionRoute:
    tenant_id: str
    project_global_id: UUID
    service_actor_user_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class ClaimedToolAssetMessage:
    outbox_event_id: UUID
    request_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    service_actor_user_id: str
    trace_id: str
    claim_token: UUID
    attempt_global_id: UUID
    attempt_number: int
    command: ToolAssetAdapterCommand
    request: ToolAssetExecutionRequest
    recovered_after_adapter_boundary: bool


@dataclass(frozen=True, slots=True)
class ToolAssetWorkerOutcome:
    outbox_event_id: UUID
    request_global_id: UUID
    state: str
    disposition: str
    mapping_advanced: bool
    result_global_id: UUID


class ToolAssetWorkerFinalFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class FrappeToolAssetWorkerRepository:
    def execution_route(self, outbox_event_id: UUID) -> ToolAssetExecutionRoute:
        row = _required_outbox(outbox_event_id, lock=False)
        _require_tool_asset_outbox(row)
        return ToolAssetExecutionRoute(str(row.tenant_id), UUID(str(row.project_global_id)), str(row.service_actor_user_id), str(row.trace_id))

    def claim(self, outbox_event_id: UUID, *, now: datetime, expected_route: ToolAssetExecutionRoute) -> ClaimedToolAssetMessage | None:
        now = _aware_utc(now)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_OUTBOX"):
            outbox = _required_outbox(outbox_event_id, lock=True)
            _require_tool_asset_outbox(outbox)
        if (str(outbox.tenant_id), str(outbox.project_global_id), str(outbox.service_actor_user_id), str(outbox.trace_id)) != (expected_route.tenant_id, str(expected_route.project_global_id), expected_route.service_actor_user_id, expected_route.trace_id):
            raise RuntimeError("Tool Asset execution route changed after authorization.")
        if str(outbox.state) in _TERMINAL_STATES:
            _require_terminal_truth(outbox)
            return None
        if str(outbox.state) not in _ACTIVE_STATES:
            raise RuntimeError("Tool Asset Outbox state is invalid.")
        expired = str(outbox.state) == "processing" and _aware_utc(outbox.lease_expires_at) <= now
        if str(outbox.state) == "processing" and not expired:
            return None
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_REQUEST"):
            request_row = _required_doc("NPI Tool Asset Request", outbox.tool_asset_request_global_id, lock=True)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_REQUEST_REBUILD"):
            request = _request_value(request_row)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_BINDINGS"):
            _require_bindings(outbox, request_row, request)
        recovered_after_boundary = bool(expired and outbox.adapter_boundary_crossed)
        attempt_number = int(outbox.attempt_count or 0) + 1
        claim_token = frappe.generate_hash(length=32)
        claim_uuid = uuid5(_RESULT_NAMESPACE, f"claim:{outbox_event_id}:{attempt_number}:{claim_token}")
        attempt_id = uuid5(_RESULT_NAMESPACE, f"attempt:{outbox_event_id}:{attempt_number}")
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_COMMAND_BUILD"):
            command = ToolAssetAdapterCommand(
                request_global_id=request.global_id,
                attempt_global_id=attempt_id,
                attempt_number=attempt_number,
                operation=request.operation,
                target_idempotency_key_hash=str(outbox.target_idempotency_key_hash),
                source_hash=request.source.source_hash,
                mapping_expectation=request.mapping_expectation,
                request_snapshot=request.canonical_mapping(),
            )
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_TRANSACTION"), tool_asset_claim_write(expected_route.service_actor_user_id) as capability:
            if expired and getattr(outbox, "tool_asset_last_attempt_global_id", None):
                old = _required_doc("NPI Tool Asset Attempt", outbox.tool_asset_last_attempt_global_id, lock=True)
                old.state = "uncertain" if outbox.adapter_boundary_crossed else "observed_failure"
                old.finished_at = _db_datetime(now)
                old.reconciliation_required = int(bool(outbox.adapter_boundary_crossed))
                old.safe_error_code = "TOOL_ASSET_EXPIRED_AFTER_BOUNDARY" if outbox.adapter_boundary_crossed else "TOOL_ASSET_EXPIRED_BEFORE_BOUNDARY"
                _set_attempt_snapshot(old)
                with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_EXPIRED_ATTEMPT_SAVE"):
                    save_tool_asset_support_document(old, capability=capability)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_ATTEMPT_BUILD"):
                attempt = frappe.get_doc({
                    "doctype": "NPI Tool Asset Attempt", "global_id": str(attempt_id),
                    "request_global_id": str(request.global_id), "outbox_event_id": str(outbox_event_id),
                    "attempt_number": attempt_number, "claim_token": str(claim_uuid),
                    "operation": request.operation.value, "target_idempotency_key_hash": str(outbox.target_idempotency_key_hash),
                    "source_hash": request.source.source_hash,
                    "mapping_expectation_hash": canonical_hash(request.mapping_expectation.canonical_mapping()),
                    "profile_id": request.profile.profile_id, "profile_version": request.profile.profile_version,
                    "profile_snapshot_hash": request.profile.snapshot_hash, "state": "started",
                    "adapter_boundary_crossed": int(recovered_after_boundary), "request_snapshot": command.snapshot,
                    "request_snapshot_hash": command.snapshot_hash, "reconciliation_required": int(recovered_after_boundary),
                    "started_at": _db_datetime(now),
                })
                _set_attempt_snapshot(attempt)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_ATTEMPT_INSERT"):
                insert_tool_asset_support_document(attempt, capability=capability)
            outbox.state = "processing"
            outbox.attempt_count = attempt_number
            outbox.claim_token = str(claim_uuid)
            outbox.claimed_at = _db_datetime(now)
            outbox.lease_expires_at = _db_datetime(now + timedelta(seconds=CLAIM_LEASE_SECONDS))
            outbox.tool_asset_last_attempt_global_id = str(attempt_id)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_OUTBOX_SAVE"):
                save_tool_asset_support_document(outbox, capability=capability)
            request_row.execution_state = ToolAssetExecutionRequestState.PROCESSING.value
            request_row.optimistic_version = int(request_row.optimistic_version or 0) + 1
            request_row.updated_at = _db_datetime(now)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_REQUEST_SAVE"):
                save_tool_asset_support_document(request_row, capability=capability)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_AUDIT"):
                _append_worker_audit(claim_actor=expected_route.service_actor_user_id, trace_id=expected_route.trace_id, request_global_id=request.global_id, operation="tool_asset_execution.claim", result="recovered_after_boundary" if recovered_after_boundary else "claimed", summary={"attemptNumber": attempt_number, "operation": request.operation.value}, capability=capability)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_CLAIM_RETURN"):
            return ClaimedToolAssetMessage(outbox_event_id, request.global_id, expected_route.tenant_id, expected_route.project_global_id, expected_route.service_actor_user_id, expected_route.trace_id, claim_uuid, attempt_id, attempt_number, command, request, recovered_after_boundary)

    @staticmethod
    def require_execution_profile(claim: ClaimedToolAssetMessage, profile: ToolAssetExecutionProfile | None) -> ToolAssetExecutionProfile:
        if not isinstance(profile, ToolAssetExecutionProfile) or profile.reference != claim.request.profile or profile.tenant_id != claim.tenant_id or profile.project_global_id != str(claim.project_global_id) or not profile.permits(claim.request.actor_user_id, claim.request.operation.value):
            raise ToolAssetWorkerFinalFailure("TOOL_ASSET_PROFILE_UNAVAILABLE")
        return profile

    def mark_adapter_boundary(self, claim: ClaimedToolAssetMessage, *, profile: ToolAssetExecutionProfile, now: datetime) -> bool:
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_BOUNDARY_PROFILE"):
            if not isinstance(profile, ToolAssetExecutionProfile) or profile.reference != claim.request.profile:
                raise RuntimeError("Tool Asset adapter profile changed before the boundary.")
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_BOUNDARY_CURRENT_CLAIM"):
            outbox, attempt = _required_current_claim(claim)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_BOUNDARY_TRANSACTION"), tool_asset_claim_write(claim.service_actor_user_id) as capability:
            outbox.adapter_boundary_crossed = 1
            attempt.adapter_boundary_crossed = 1
            _set_attempt_snapshot(attempt)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_BOUNDARY_ATTEMPT_SAVE"):
                save_tool_asset_support_document(attempt, capability=capability)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_BOUNDARY_OUTBOX_SAVE"):
                save_tool_asset_support_document(outbox, capability=capability)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_BOUNDARY_AUDIT"):
                _append_worker_audit(claim_actor=claim.service_actor_user_id, trace_id=claim.trace_id, request_global_id=claim.request_global_id, operation="tool_asset_execution.adapter_boundary", result="sealed", summary={"attemptNumber": claim.attempt_number, "operation": claim.request.operation.value}, capability=capability)
        return True

    def seal_result(self, claim: ClaimedToolAssetMessage, *, profile: ToolAssetExecutionProfile | None, result: ClassifiedToolAssetAdapterResult, now: datetime) -> ToolAssetWorkerOutcome:
        now = _aware_utc(now)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_PROFILE"):
            _require_result_profile(claim, profile, result)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_CURRENT_CLAIM"):
            outbox, attempt = _required_current_claim(claim)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_REQUEST"):
            request_row = _required_doc("NPI Tool Asset Request", claim.request_global_id, lock=True)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_BINDINGS"):
            _require_bindings(outbox, request_row, claim.request)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_RESULT_LOOKUP"):
            result_id = deterministic_tool_asset_result_id(claim.attempt_global_id)
            existing = _optional_doc("NPI Tool Asset Result", result_id, lock=True)
        if existing is not None:
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_EXISTING_OUTCOME"):
                return _existing_outcome(existing, claim)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_PREPARE"):
            field_payloads = [value.canonical_mapping() for value in result.fields]
            field_set_hash = canonical_hash(field_payloads)
            mapping_disposition = classify_mapping_result(
                claim.request.mapping_expectation,
                result_state=result.state,
                authority=result.authority,
                response_authenticated=result.authority.value == "authoritative_sandbox",
                observed_formal_asset_id=result.formal_asset_id,
                observed_previous_mapping_version=claim.request.mapping_expectation.mapping_version,
            )
            mapping_disposition = _validated_mapping_disposition(claim, mapping_disposition)
            effective_state = (
                ToolAssetExecutionRequestState.MAPPING_CONFLICT
                if result.state is ToolAssetExecutionRequestState.SUCCEEDED
                and mapping_disposition is not ToolAssetMappingDisposition.ADVANCE
                else result.state
            )
            observation_id = uuid5(_OBSERVATION_NAMESPACE, str(result_id))
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_TRANSACTION"), tool_asset_result_transaction_write(claim.service_actor_user_id) as capability:
            result_snapshot = {
                "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION, "globalId": str(result_id),
                "requestGlobalId": str(claim.request_global_id), "outboxEventId": str(claim.outbox_event_id),
                "attemptGlobalId": str(claim.attempt_global_id), "attemptNumber": claim.attempt_number,
                "operation": claim.request.operation.value, "sourceHash": claim.request.source.source_hash,
                "mappingExpectationHash": canonical_hash(claim.request.mapping_expectation.canonical_mapping()),
                "state": effective_state.value, "authority": result.authority.value,
                "responseAuthenticated": result.authority.value == "authoritative_sandbox",
                "responseHash": result.response_hash, "faultKind": result.fault_kind.value,
                "fieldResultSetHash": field_set_hash, "formalAssetId": result.formal_asset_id,
                "targetVersion": result.target_version, "observedAt": _utc_text(now),
            }
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_RESULT_BUILD"):
                result_doc = frappe.get_doc({
                    "doctype": "NPI Tool Asset Result", **_snake_result(result_snapshot),
                    "result_snapshot": result_snapshot, "result_hash": canonical_hash(result_snapshot),
                })
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_RESULT_INSERT"):
                insert_tool_asset_support_document(result_doc, capability=capability)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_FIELD_INSERT"):
                for value in result.fields:
                    field_id = deterministic_tool_asset_field_result_id(claim.attempt_global_id, value.field_code)
                    snapshot = {"schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION, "globalId": str(field_id), "requestGlobalId": str(claim.request_global_id), "resultGlobalId": str(result_id), "attemptGlobalId": str(claim.attempt_global_id), **value.canonical_mapping(), "observedAt": _utc_text(now)}
                    insert_tool_asset_support_document(frappe.get_doc({"doctype": "NPI Tool Asset Field Result", **_snake_field(snapshot), "observation_hash": canonical_hash(value.canonical_mapping()), "field_result_snapshot": snapshot, "field_result_hash": canonical_hash(snapshot)}), capability=capability)
            mapping_advanced = mapping_disposition is ToolAssetMappingDisposition.ADVANCE
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_MAPPING"):
                self._record_mapping(claim, result, result_id, observation_id, mapping_disposition, now, capability)
            attempt.state = _attempt_state(effective_state)
            attempt.transport_disposition = result.transport_disposition
            attempt.response_hash = result.response_hash
            attempt.fault_kind = result.fault_kind.value
            attempt.reconciliation_required = int(result.reconciliation_required)
            attempt.safe_error_code = result.safe_error_code
            attempt.finished_at = _db_datetime(now)
            _set_attempt_snapshot(attempt)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_ATTEMPT_SAVE"):
                save_tool_asset_support_document(attempt, capability=capability)
            request_row.execution_state = effective_state.value
            request_row.result_global_id = str(result_id)
            request_row.optimistic_version = int(request_row.optimistic_version or 0) + 1
            request_row.updated_at = _db_datetime(now)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_REQUEST_SAVE"):
                save_tool_asset_support_document(request_row, capability=capability)
            outbox.state = _outbox_state(effective_state)
            outbox.tool_asset_result_global_id = str(result_id)
            outbox.disposition = mapping_disposition.value
            outbox.last_error_code = result.safe_error_code
            outbox.last_error_at = _db_datetime(now) if result.safe_error_code else None
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_OUTBOX_SAVE"):
                save_tool_asset_support_document(outbox, capability=capability)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_GUARD"):
                _release_guard(claim, effective_state, now, capability)
            with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_AUDIT"):
                _append_worker_audit(claim_actor=claim.service_actor_user_id, trace_id=claim.trace_id, request_global_id=claim.request_global_id, operation="tool_asset_execution.result.observe", result=effective_state.value, summary={"attemptNumber": claim.attempt_number, "disposition": mapping_disposition.value, "mappingAdvanced": mapping_advanced, "responseHash": result.response_hash}, capability=capability)
        with tool_asset_process_stage_step("P805_TOOL_ASSET_PROCESS_SEAL_OUTCOME"):
            return ToolAssetWorkerOutcome(claim.outbox_event_id, claim.request_global_id, effective_state.value, mapping_disposition.value, mapping_advanced, result_id)

    def recover_or_seal_result(self, claim: ClaimedToolAssetMessage, *, profile: ToolAssetExecutionProfile | None, result: ClassifiedToolAssetAdapterResult, now: datetime) -> ToolAssetWorkerOutcome:
        return self.seal_result(claim, profile=profile, result=result, now=now)

    def recoverable_outbox_event_ids(self, *, now: datetime) -> tuple[UUID, ...]:
        rows = frappe.get_all("NPI Outbox Message", filters={"schema_version": TOOL_ASSET_OUTBOX_SCHEMA_VERSION, "event_type": TOOL_ASSET_REQUEST_EVENT_TYPE, "state": ["in", ["pending", "processing"]]}, fields=["event_id", "state", "lease_expires_at"], order_by="creation asc", limit=RECOVERY_BATCH_LIMIT)
        values: list[UUID] = []
        for row in rows:
            if str(_value(row, "state")) == "pending" or (_value(row, "lease_expires_at") and _aware_utc(_value(row, "lease_expires_at")) <= _aware_utc(now)):
                values.append(UUID(str(_value(row, "event_id"))))
        return tuple(values)

    @staticmethod
    def _record_mapping(claim, result, result_id, observation_id, disposition, now, capability) -> None:
        expectation = claim.request.mapping_expectation
        head = _mapping_head(claim.request.source.source_stream_key_hash, lock=True)
        snapshot = {
            "schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION, "globalId": str(observation_id),
            "tenantId": claim.tenant_id, "projectGlobalId": str(claim.project_global_id),
            "toolingSetGlobalId": str(claim.request.source.tooling_set_global_id),
            "sourceStreamKeyHash": claim.request.source.source_stream_key_hash,
            "requestGlobalId": str(claim.request_global_id), "resultGlobalId": str(result_id),
            "attemptGlobalId": str(claim.attempt_global_id), "operation": claim.request.operation.value,
            "sourceHash": claim.request.source.source_hash,
            "mappingExpectationHash": canonical_hash(expectation.canonical_mapping()),
            "previousMappingVersion": expectation.mapping_version,
            "previousFormalAssetId": expectation.formal_asset_id, "previousTargetVersion": expectation.target_version,
            "previousObservationHash": expectation.observation_hash,
            "observedFormalAssetId": result.formal_asset_id, "observedTargetVersion": result.target_version,
            "authority": result.authority.value, "responseAuthenticated": result.authority.value == "authoritative_sandbox",
            "responseHash": result.response_hash, "disposition": disposition.value, "observedAt": _utc_text(now),
        }
        observation_hash = canonical_hash(snapshot)
        insert_tool_asset_support_document(frappe.get_doc({"doctype": "NPI Tool Asset Mapping Observation", **_snake_observation(snapshot), "observation_snapshot": snapshot, "observation_hash": observation_hash}), capability=capability)
        if disposition is not ToolAssetMappingDisposition.ADVANCE:
            return
        version = expectation.mapping_version + 1
        head_snapshot = {"schemaVersion": TOOL_ASSET_EXECUTION_SCHEMA_VERSION, "globalId": str(claim.request.source.tooling_set_global_id), "tenantId": claim.tenant_id, "projectGlobalId": str(claim.project_global_id), "toolingSetGlobalId": str(claim.request.source.tooling_set_global_id), "sourceStreamKeyHash": claim.request.source.source_stream_key_hash, "mappingVersion": version, "formalAssetId": result.formal_asset_id, "targetVersion": result.target_version, "currentObservationGlobalId": str(observation_id), "currentObservationHash": observation_hash, "updatedAt": _utc_text(now)}
        values = {"global_id": str(claim.request.source.tooling_set_global_id), "tenant_id": claim.tenant_id, "project_global_id": str(claim.project_global_id), "tooling_set_global_id": str(claim.request.source.tooling_set_global_id), "source_stream_key_hash": claim.request.source.source_stream_key_hash, "mapping_version": version, "formal_asset_id": result.formal_asset_id, "target_version": result.target_version, "current_observation": str(observation_id), "current_observation_hash": observation_hash, "head_snapshot": head_snapshot, "head_hash": canonical_hash(head_snapshot), "updated_at": _db_datetime(now)}
        if head is None:
            insert_tool_asset_support_document(frappe.get_doc({"doctype": "NPI Tool Asset Mapping Head", **values}), capability=capability)
        else:
            for key, value in values.items():
                setattr(head, key, value)
            save_tool_asset_support_document(head, capability=capability)


def _required_current_claim(claim: ClaimedToolAssetMessage):
    outbox = _required_outbox(claim.outbox_event_id, lock=True)
    if str(outbox.state) != "processing" or str(outbox.claim_token) != str(claim.claim_token) or str(outbox.tool_asset_last_attempt_global_id) != str(claim.attempt_global_id):
        raise RuntimeError("Tool Asset claim is no longer current.")
    return outbox, _required_doc("NPI Tool Asset Attempt", claim.attempt_global_id, lock=True)


def _require_result_profile(claim, profile, result):
    if not isinstance(result, ClassifiedToolAssetAdapterResult):
        raise RuntimeError("Tool Asset classified result is invalid.")
    if profile is None:
        if result.authority is not ToolAssetResultAuthority.NONE:
            raise RuntimeError("Tool Asset result authority has no execution profile.")
        return
    if not isinstance(profile, ToolAssetExecutionProfile) or profile.reference != claim.request.profile:
        raise RuntimeError("Tool Asset result profile binding is invalid.")
    expected = {
        "synthetic": ToolAssetResultAuthority.SYNTHETIC,
        "sandbox": ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX,
    }.get(profile.target_mode.value)
    if result.authority not in {ToolAssetResultAuthority.NONE, expected}:
        raise RuntimeError("Tool Asset result authority does not match its profile.")


def _require_bindings(outbox, row, request) -> None:
    if (str(outbox.tool_asset_request_global_id), str(outbox.tenant_id), str(outbox.project_global_id), str(outbox.tooling_set_global_id), str(outbox.source_stream_key_hash), str(outbox.source_hash), str(outbox.tool_asset_mapping_expectation_hash), str(outbox.profile_snapshot_hash), str(outbox.operation)) != (str(request.global_id), request.source.tenant_id, str(request.source.project_global_id), str(request.source.tooling_set_global_id), request.source.source_stream_key_hash, request.source.source_hash, canonical_hash(request.mapping_expectation.canonical_mapping()), request.profile.snapshot_hash, request.operation.value):
        raise RuntimeError("Tool Asset Outbox binding is invalid.")
    if str(row.global_id) != str(request.global_id) or str(row.payload_hash) != request.payload_hash:
        raise RuntimeError("Tool Asset request binding is invalid.")


def _require_terminal_truth(outbox) -> None:
    request_row = _required_doc("NPI Tool Asset Request", outbox.tool_asset_request_global_id, lock=True)
    request = _request_value(request_row)
    _require_bindings(outbox, request_row, request)
    result = _required_doc("NPI Tool Asset Result", outbox.tool_asset_result_global_id, lock=True)
    if str(result.request_global_id) != str(request.global_id) or str(request_row.result_global_id) != str(result.global_id):
        raise RuntimeError("Terminal Tool Asset result binding is invalid.")
    name = frappe.db.get_value("NPI Tool Asset Stream Guard", {"source_stream_key_hash": request.source.source_stream_key_hash}, "name")
    guard = _required_doc("NPI Tool Asset Stream Guard", name, lock=True) if name else None
    if guard is None or getattr(guard, "active_request_global_id", None) or str(guard.last_request_global_id) != str(request.global_id) or str(guard.last_state) != str(request_row.execution_state):
        raise RuntimeError("Terminal Tool Asset stream truth is invalid.")


def _require_tool_asset_outbox(row) -> None:
    if int(row.schema_version or 0) != TOOL_ASSET_OUTBOX_SCHEMA_VERSION or str(row.event_type) != TOOL_ASSET_REQUEST_EVENT_TYPE:
        raise RuntimeError("Tool Asset Outbox envelope is invalid.")


def _request_value(row) -> ToolAssetExecutionRequest:
    try:
        value = tool_asset_execution_request_from_mapping(_json(row.request_snapshot))
    except ToolAssetExecutionContractError as error:
        raise RuntimeError("Persisted Tool Asset request is invalid.") from error
    return value


def _required_outbox(event_id, *, lock):
    return _required_doc("NPI Outbox Message", event_id, lock=lock)


def _required_doc(doctype, name, *, lock):
    try:
        return frappe.get_doc(doctype, str(name), for_update=lock)
    except frappe.DoesNotExistError as error:
        raise RuntimeError(f"Required {doctype} is unavailable.") from error


def _optional_doc(doctype, name, *, lock):
    try:
        return frappe.get_doc(doctype, str(name), for_update=lock)
    except frappe.DoesNotExistError:
        return None


def _mapping_head(stream_hash, *, lock):
    name = frappe.db.get_value("NPI Tool Asset Mapping Head", {"source_stream_key_hash": stream_hash}, "name")
    return _optional_doc("NPI Tool Asset Mapping Head", name, lock=lock) if name else None


def _validated_mapping_disposition(claim, disposition):
    if disposition is not ToolAssetMappingDisposition.ADVANCE:
        return disposition
    expectation = claim.request.mapping_expectation
    head = _mapping_head(claim.request.source.source_stream_key_hash, lock=True)
    if expectation.mapping_version == 0:
        head_matches = head is None
    else:
        head_matches = bool(
            head is not None
            and str(head.tenant_id) == claim.tenant_id
            and str(head.project_global_id) == str(claim.project_global_id)
            and str(head.tooling_set_global_id) == str(claim.request.source.tooling_set_global_id)
            and int(head.mapping_version) == expectation.mapping_version
            and str(head.formal_asset_id) == str(expectation.formal_asset_id)
            and str(head.target_version) == str(expectation.target_version)
            and str(head.current_observation_hash) == str(expectation.observation_hash)
        )
    if not head_matches:
        return ToolAssetMappingDisposition.EXPECTATION_CONFLICT
    try:
        from npi_integration.projections.frappe_repository import FrappeProjectionConsumerReader

        projection = FrappeProjectionConsumerReader().read_tool_asset_status(
            project_global_id=claim.project_global_id,
            tooling_master_global_id=claim.request.source.tooling_master_global_id,
        )
    except Exception:
        return ToolAssetMappingDisposition.EXPECTATION_CONFLICT
    if expectation.mapping_version == 0:
        projection_matches = projection is None
    else:
        projection_matches = isinstance(projection, dict) and (
            str(projection.get("toolingSetGlobalId")), projection.get("mappingVersion"),
            str(projection.get("formalAssetId")), str(projection.get("targetVersion")),
        ) == (
            str(claim.request.source.tooling_set_global_id), expectation.mapping_version,
            str(expectation.formal_asset_id), str(expectation.target_version),
        )
    return disposition if projection_matches else ToolAssetMappingDisposition.EXPECTATION_CONFLICT


def _release_guard(claim, state, now, capability):
    name = frappe.db.get_value("NPI Tool Asset Stream Guard", {"source_stream_key_hash": claim.request.source.source_stream_key_hash}, "name")
    if not name:
        raise RuntimeError("Tool Asset stream guard is unavailable.")
    guard = _required_doc("NPI Tool Asset Stream Guard", name, lock=True)
    if str(guard.active_request_global_id) != str(claim.request_global_id):
        raise RuntimeError("Tool Asset stream guard binding is invalid.")
    guard.active_request_global_id = None
    guard.active_target_idempotency_key_hash = None
    guard.active_state = None
    guard.last_request_global_id = str(claim.request_global_id)
    guard.last_target_idempotency_key_hash = claim.command.target_idempotency_key_hash
    guard.last_state = state.value
    guard.optimistic_version = int(guard.optimistic_version or 0) + 1
    guard.updated_at = _db_datetime(now)
    save_tool_asset_support_document(guard, capability=capability)


def _existing_outcome(row, claim):
    if str(row.attempt_global_id) != str(claim.attempt_global_id) or str(row.request_global_id) != str(claim.request_global_id):
        raise RuntimeError("Existing Tool Asset result binding is invalid.")
    return ToolAssetWorkerOutcome(claim.outbox_event_id, claim.request_global_id, str(row.state), "replayed_terminal", False, UUID(str(row.global_id)))


def _set_attempt_snapshot(attempt):
    snapshot = {key: _value(attempt, key) for key in ("global_id", "request_global_id", "outbox_event_id", "attempt_number", "claim_token", "operation", "target_idempotency_key_hash", "source_hash", "mapping_expectation_hash", "profile_id", "profile_version", "profile_snapshot_hash", "state", "adapter_boundary_crossed", "request_snapshot_hash", "transport_disposition", "response_hash", "fault_kind", "reconciliation_required", "safe_error_code", "started_at", "finished_at")}
    snapshot["started_at"] = _db_datetime(snapshot["started_at"])
    if snapshot["finished_at"] not in (None, ""):
        snapshot["finished_at"] = _db_datetime(snapshot["finished_at"])
    attempt.attempt_snapshot = snapshot
    attempt.attempt_hash = canonical_hash(snapshot)


def _append_worker_audit(*, claim_actor, trace_id, request_global_id, operation, result, summary, capability):
    event = create_audit_event(actor=claim_actor, trace_id=trace_id, operation=operation, global_id=request_global_id, object_version=1, result=result, input_summary=summary)
    insert_tool_asset_audit_document(frappe.get_doc({"doctype":"NPI Audit Event", "event_id":str(event.event_id), "global_id":str(event.global_id), "object_version":event.object_version, "actor":event.actor, "trace_id":event.trace_id, "operation":event.operation, "result":event.result, "input_summary":dict(event.input_summary)}), capability=capability)


def _snake_result(v):
    return {"global_id": v["globalId"], "request_global_id": v["requestGlobalId"], "outbox_event_id": v["outboxEventId"], "attempt_global_id": v["attemptGlobalId"], "attempt_number": v["attemptNumber"], "operation": v["operation"], "source_hash": v["sourceHash"], "mapping_expectation_hash": v["mappingExpectationHash"], "state": v["state"], "authority": v["authority"], "response_authenticated": int(v["responseAuthenticated"]), "response_hash": v["responseHash"], "fault_kind": v["faultKind"], "field_result_set_hash": v["fieldResultSetHash"], "formal_asset_id": v["formalAssetId"], "target_version": v["targetVersion"], "observed_at": v["observedAt"]}


def _snake_field(v):
    return {"global_id": v["globalId"], "request_global_id": v["requestGlobalId"], "result_global_id": v["resultGlobalId"], "attempt_global_id": v["attemptGlobalId"], "field_code": v["fieldCode"], "state": v["state"], "authority": v["authority"], "response_authenticated": int(v["responseAuthenticated"]), "response_hash": v["responseHash"], "fault_kind": v["faultKind"], "observed_at": v["observedAt"]}


def _snake_observation(v):
    pairs = {"globalId":"global_id","tenantId":"tenant_id","projectGlobalId":"project_global_id","toolingSetGlobalId":"tooling_set_global_id","sourceStreamKeyHash":"source_stream_key_hash","requestGlobalId":"request_global_id","resultGlobalId":"result_global_id","attemptGlobalId":"attempt_global_id","operation":"operation","sourceHash":"source_hash","mappingExpectationHash":"mapping_expectation_hash","previousMappingVersion":"previous_mapping_version","previousFormalAssetId":"previous_formal_asset_id","previousTargetVersion":"previous_target_version","previousObservationHash":"previous_observation_hash","observedFormalAssetId":"observed_formal_asset_id","observedTargetVersion":"observed_target_version","authority":"authority","responseAuthenticated":"response_authenticated","responseHash":"response_hash","disposition":"disposition","observedAt":"observed_at"}
    return {target: (int(v[source]) if source == "responseAuthenticated" else v[source]) for source, target in pairs.items()}


def _attempt_state(state):
    return {ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED:"synthetic_verified", ToolAssetExecutionRequestState.SUCCEEDED:"observed_success", ToolAssetExecutionRequestState.PARTIALLY_SUCCEEDED:"observed_partial", ToolAssetExecutionRequestState.UNCERTAIN_AFTER_TIMEOUT:"uncertain"}.get(state, "observed_failure")


def _outbox_state(state):
    return "uncertain" if state is ToolAssetExecutionRequestState.UNCERTAIN_AFTER_TIMEOUT else state.value


def _json(value):
    return json.loads(value) if isinstance(value, str) else dict(value)


def _value(row, key):
    return row.get(key) if isinstance(row, dict) else getattr(row, key, None)


def _aware_utc(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise RuntimeError("Tool Asset datetime is invalid.") from error
    if not isinstance(value, datetime):
        raise RuntimeError("Tool Asset datetime is invalid.")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _db_datetime(value):
    return _aware_utc(value).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")


def _utc_text(value):
    return _aware_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")
