from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4, uuid5

import frappe
from frappe import _

from npi_core.controlled_evidence_validation import (
    canonical_snapshot_hash,
    has_controlled_file_write,
)
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import (
    PermissionDenied,
    RequestValidationFailed,
    VersionConflict,
)
from npi_core.foundation.security import Principal
from npi_core.gate_evidence.frappe_repository import FrappeGateEvidenceRepository
from npi_core.gate_review.domain import (
    AuthorityBinding,
    ClosureActionReference,
    CycleState,
    CycleTrigger,
    DecisionOutcome,
    DecisionSnapshot,
    DependencyEvaluator,
    ExceptionOutcome,
    ExceptionState,
    GateBlockerInput,
    GateDependencyInput,
    GateEvidenceInput,
    GateInputSnapshot,
    GateRequirementInput,
    ReviewCycle,
    ReviewDenied,
    ReviewException,
    ReviewOutcome,
    ReviewRecord,
    ReviewTransition,
    downstream_decision_is_current,
)
from npi_core.gate_review.frappe_policy_repository import (
    load_available_gate_review_policy_version,
    load_exact_gate_review_policy_version,
)
from npi_core.gate_review.frappe_validation import (
    GATE_REVIEW_COMMAND_FLAG,
    canonical_json_hash,
)
from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
    file_revision_source_snapshot,
    has_complete_file_revision_identity,
    has_live_private_file_identity,
)
from npi_core.npi_core.doctype.npi_gate_evidence_reference.npi_gate_evidence_reference import (
    wbs_item_source_snapshot,
)
from npi_core.project.domain import IdempotencyConflict

_MAX_CYCLES = 1000
_MAX_EXCEPTIONS = 256
_MAX_EVIDENCE = 255
_MAX_MEMBERS = 500
_MAX_POLICY_OPTIONS = 100
_MAX_BLOCKERS = 256
_MAX_CLOSURE_ACTIONS = 500
_MAX_DEPENDENCY_CHANGES = 1000
_DECISION_BLOCKED_CODES = frozenset(
    {
        "REVIEW_CYCLE_CLOSED",
        "GATE_INPUT_CHANGED",
        "DECISION_AUTHORITY_REQUIRED",
        "REVIEWS_INCOMPLETE",
        "FILE_EVIDENCE_UNSAFE",
        "GATE_BLOCKED",
        "REQUIRED_P0_EVIDENCE_MISSING",
        "REQUIRED_EVIDENCE_MISSING",
        "EXCEPTION_NOT_REQUIRED",
        "APPROVED_EXCEPTION_REQUIRED",
    }
)
GATE_REVIEW_COMMAND_OPERATIONS = frozenset(
    {
        "gate.review.start",
        "gate.review.submit",
        "gate.review.exception.request",
        "gate.review.exception.decide",
        "gate.review.decide",
        "gate.review.reopen",
    }
)
GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR = "npi-gate-review-dependency-system"
GATE_REVIEW_DEPENDENCY_INPUT_FLAG = "npi_gate_review_dependency_input_write"
_DEPENDENCY_SYSTEM_CAPABILITY = object()


@dataclass(frozen=True, slots=True)
class GateReviewCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


def _blocked_decision_readiness(
    outcomes: Sequence[DecisionOutcome],
    code: str,
) -> dict[str, list[Any]]:
    if code not in _DECISION_BLOCKED_CODES:
        raise ValueError("Gate decision readiness denial is not contracted.")
    return {
        "allowedOutcomes": [],
        "blockedReasons": [
            {"outcome": outcome.value, "code": code} for outcome in outcomes
        ],
    }


class FrappeGateReviewRepository:
    """Gate-root adapter; transport admission never grants business authority."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        _system_capability: object | None = None,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id
        self._dependency_system = (
            _system_capability is _DEPENDENCY_SYSTEM_CAPABILITY
            and self.actor == GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR
            and not principal.roles
            and not principal.project_access
            and not principal.is_external
        )

    def review_workspace(
        self, project_id: UUID, gate_id: UUID
    ) -> dict[str, Any] | None:
        project = _optional_doc("NPI Engineering Project", str(project_id))
        if project is None or not self._can_view_project(project, project_id):
            return None
        gate = _optional_doc("NPI Gate Shell", str(gate_id))
        if not _gate_matches(project, gate, gate_id):
            return None
        return self._workspace_for(project, gate)

    def command_receipt(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        operation: str,
        actor_key_hash: str,
    ) -> dict[str, object] | None:
        if operation not in GATE_REVIEW_COMMAND_OPERATIONS:
            raise ValueError("Gate review command receipt operation is unsupported.")
        locked = self._locked_project_gate(project_id, gate_id)
        if locked is None:
            return None
        project, gate = locked
        record = frappe.db.get_value(
            "NPI Gate Review Idempotency",
            {"actor_key_hash": actor_key_hash},
            [
                "actor",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "operation",
                "response_sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not record:
            return {
                "operation": operation,
                "status": "absent",
                "workspaceReloadRequired": True,
            }
        if (
            str(record.actor) != self.actor
            or str(record.tenant_id) != str(project.tenant_id)
            or str(record.project_global_id) != str(project.global_id)
            or str(record.gate_global_id) != str(gate.global_id)
            or str(record.operation) != operation
        ):
            return None
        if int(record.response_sealed or 0) != 1:
            raise RuntimeError("Committed Gate review command receipt is not sealed.")
        return {
            "operation": operation,
            "status": "completed",
            "workspaceReloadRequired": True,
        }

    def start_review(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        bindings: tuple[dict[str, Any], ...],
    ) -> GateReviewCommandOutcome | None:
        locked = self._locked_project_gate(project_id, gate_id)
        if locked is None:
            return None
        project, gate = locked
        if not self._is_internal_system_manager():
            raise PermissionDenied()
        state = str(gate.review_state or "not_started")
        cycle_document = (
            self._locked_current_cycle(project, gate)
            if state == "requires_review"
            else None
        )
        payload_hash = _payload_hash(
            {
                "operation": "gate.review.start",
                "projectId": project_id,
                "gateId": gate_id,
                "expectedGateVersion": expected_gate_version,
                "policyGlobalId": policy_global_id,
                "policyVersion": policy_version,
                "policySnapshotHash": policy_snapshot_hash,
                "bindings": bindings,
            }
        )
        replay = self._idempotency_replay(
            idempotency_key, payload_hash, project, gate, "gate.review.start"
        )
        if replay is not None:
            return GateReviewCommandOutcome(replay, True)
        self._require_gate_version(gate, expected_gate_version)
        policy = load_available_gate_review_policy_version(
            policy_global_id, policy_version, policy_snapshot_hash
        )
        if policy is None or not _policy_matches_gate(policy, gate):
            raise _field_problem(
                "policyGlobalId",
                _("Select an applicable published Gate Review Policy."),
            )
        now = datetime.now(UTC)
        frozen_bindings = self._resolve_bindings(project, bindings, now=now)
        current_input = self._build_current_input(project, gate)
        cycle = None
        if state == "not_started":
            cycle = ReviewCycle.start(
                gate_global_id=gate_id,
                project_global_id=project_id,
                tenant_id=str(project.tenant_id),
                cycle_number=1,
                trigger=CycleTrigger.MANUAL_START,
                policy=policy,
                bindings=frozen_bindings,
                input_snapshot=current_input,
            )
        elif state == "requires_review" and cycle_document is not None:
            cycle = self._hydrate_cycle(cycle_document, lock_exceptions=True)
            if (
                cycle.state is not CycleState.ACTIVE
                or cycle.version != 1
                or cycle.reviews
                or cycle.exceptions
                or cycle.decision is not None
                or cycle.policy != policy
                or cycle.bindings != frozen_bindings
                or cycle.input_snapshot != current_input
            ):
                raise VersionConflict()
        else:
            raise VersionConflict()
        with _controlled_review_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key, payload_hash, project, gate, "gate.review.start"
            )
            if state == "not_started":
                assert cycle is not None
                cycle_document = self._insert_cycle(
                    cycle, started_by=self.actor, started_at=now
                )
            assert cycle_document is not None
            self._set_gate_cycle(
                gate, cycle_document, policy=policy, review_state="in_review"
            )
            self._audit(
                "gate.review.start",
                UUID(str(cycle_document.global_id)),
                int(gate.optimistic_version),
                {"inputHash": current_input.snapshot_hash},
            )
            response = self._workspace_for(project, gate)
            self._seal_idempotency(receipt, response)
        return GateReviewCommandOutcome(response)

    def submit_review(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        *,
        idempotency_key: str,
        expected_cycle_version: int,
        expected_input_hash: str,
        step_key: str,
        outcome: str,
        opinion: str,
    ) -> GateReviewCommandOutcome | None:
        locked = self._locked_review_scope(project_id, gate_id, cycle_id)
        if locked is None:
            return None
        project, gate, cycle_document = locked
        payload_hash = _payload_hash(
            {
                "operation": "gate.review.submit",
                "projectId": project_id,
                "gateId": gate_id,
                "cycleId": cycle_id,
                "expectedCycleVersion": expected_cycle_version,
                "expectedInputHash": expected_input_hash,
                "stepKey": step_key,
                "outcome": outcome,
                "opinion": opinion,
            }
        )
        replay = self._idempotency_replay(
            idempotency_key, payload_hash, project, gate, "gate.review.submit"
        )
        if replay is not None:
            return GateReviewCommandOutcome(replay, True)
        self._require_in_review_state(gate)
        cycle = self._hydrate_cycle(cycle_document, lock_exceptions=True)
        try:
            step = next(
                value for value in cycle.selected_steps if value.key == step_key
            )
        except StopIteration as error:
            raise PermissionDenied() from error
        self._require_current_binding_actor(project, cycle, step.authority_slot)
        cycle.ensure_current_input(self._build_current_input(project, gate))
        updated = cycle.submit_review(
            step_key=step_key,
            actor_user_id=self.actor,
            outcome=ReviewOutcome(outcome),
            opinion=opinion,
            occurred_at=datetime.now(UTC),
            expected_version=expected_cycle_version,
            expected_input_hash=expected_input_hash,
        )
        record = updated.reviews[-1]
        with _controlled_review_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key, payload_hash, project, gate, "gate.review.submit"
            )
            record_document = self._insert_review_record(
                cycle, updated, record, step=step
            )
            self._update_cycle(cycle_document, updated)
            self._audit(
                "gate.review.submit",
                UUID(str(record_document.global_id)),
                updated.version,
                {"cycleId": str(cycle_id), "stepKey": step_key},
            )
            response = self._workspace_for(project, gate)
            self._seal_idempotency(receipt, response)
        return GateReviewCommandOutcome(response)

    def request_exception(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        *,
        idempotency_key: str,
        expected_cycle_version: int,
        expected_input_hash: str,
        requirement_global_id: UUID,
        requirement_key: str,
        kind: str,
        reason: str,
        risk: str,
        expires_at: datetime,
        closure_action_global_id: UUID,
    ) -> GateReviewCommandOutcome | None:
        locked = self._locked_review_scope(project_id, gate_id, cycle_id)
        if locked is None:
            return None
        project, gate, cycle_document = locked
        payload_hash = _payload_hash(
            {
                "operation": "gate.review.exception.request",
                "projectId": project_id,
                "gateId": gate_id,
                "cycleId": cycle_id,
                "expectedCycleVersion": expected_cycle_version,
                "expectedInputHash": expected_input_hash,
                "requirementGlobalId": requirement_global_id,
                "requirementKey": requirement_key,
                "kind": kind,
                "reason": reason,
                "risk": risk,
                "expiresAt": expires_at,
                "closureActionGlobalId": closure_action_global_id,
            }
        )
        replay = self._idempotency_replay(
            idempotency_key,
            payload_hash,
            project,
            gate,
            "gate.review.exception.request",
        )
        if replay is not None:
            return GateReviewCommandOutcome(replay, True)
        self._require_in_review_state(gate)
        cycle = self._hydrate_cycle(cycle_document, lock_exceptions=True)
        if not any(
            value.global_id == requirement_global_id
            and value.requirement_key == requirement_key
            for value in cycle.input_snapshot.requirements
        ):
            raise _field_problem(
                "requirementGlobalId",
                _("Select the exact requirement from this review cycle."),
            )
        requester = self._require_current_actor_member(project)
        cycle.ensure_current_input(self._build_current_input(project, gate))
        closure_action = self._require_closure_action(
            project,
            gate,
            closure_action_global_id,
            lock=True,
        )
        updated = cycle.request_exception(
            exception_global_id=uuid4(),
            requester_member_global_id=UUID(str(requester.global_id)),
            actor_user_id=self.actor,
            kind=kind,
            requirement_key=requirement_key,
            reason=reason,
            risk=risk,
            closure_action_ref=_closure_action_reference(closure_action),
            closure_action_kind="action",
            requested_at=datetime.now(UTC),
            expires_at=expires_at,
            expected_version=expected_cycle_version,
            expected_input_hash=expected_input_hash,
        )
        exception = updated.exceptions[-1]
        with _controlled_review_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                gate,
                "gate.review.exception.request",
            )
            self._insert_exception(exception)
            self._update_cycle(cycle_document, updated)
            self._audit(
                "gate.review.exception.request",
                exception.global_id,
                exception.version,
                {"cycleId": str(cycle_id), "requirementKey": requirement_key},
            )
            response = self._workspace_for(project, gate)
            self._seal_idempotency(receipt, response)
        return GateReviewCommandOutcome(response)

    def decide_exception(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        exception_id: UUID,
        *,
        idempotency_key: str,
        expected_cycle_version: int,
        expected_exception_version: int,
        expected_input_hash: str,
        outcome: str,
        opinion: str,
    ) -> GateReviewCommandOutcome | None:
        locked = self._locked_review_scope(
            project_id, gate_id, cycle_id, exception_id=exception_id
        )
        if locked is None:
            return None
        project, gate, cycle_document, exception_document = locked
        payload_hash = _payload_hash(
            {
                "operation": "gate.review.exception.decide",
                "projectId": project_id,
                "gateId": gate_id,
                "cycleId": cycle_id,
                "exceptionId": exception_id,
                "expectedCycleVersion": expected_cycle_version,
                "expectedExceptionVersion": expected_exception_version,
                "expectedInputHash": expected_input_hash,
                "outcome": outcome,
                "opinion": opinion,
            }
        )
        replay = self._idempotency_replay(
            idempotency_key,
            payload_hash,
            project,
            gate,
            "gate.review.exception.decide",
        )
        if replay is not None:
            return GateReviewCommandOutcome(replay, True)
        self._require_in_review_state(gate)
        cycle = self._hydrate_cycle(
            cycle_document,
            lock_exceptions=True,
            locked_exception=exception_document,
        )
        try:
            exception = next(
                value for value in cycle.exceptions if value.global_id == exception_id
            )
        except StopIteration:
            return None
        if not exception.closure_action_ref.is_exact:
            raise ReviewDenied(
                "APPROVED_EXCEPTION_REQUIRED",
                _(
                    "The closure action changed and the exception must be requested again."
                ),
            )
        self._require_current_binding_actor(
            project, cycle, exception.approval_authority_slot
        )
        cycle.ensure_current_input(self._build_current_input(project, gate))
        now = datetime.now(UTC)
        selected_outcome = ExceptionOutcome(outcome)
        if (
            selected_outcome is ExceptionOutcome.APPROVED
            and not self._closure_action_reference_is_current(
                project,
                gate,
                exception.closure_action_ref,
                lock=True,
            )
        ):
            raise ReviewDenied(
                "APPROVED_EXCEPTION_REQUIRED",
                _(
                    "The closure action changed and the exception must be requested again."
                ),
            )
        updated = cycle.decide_exception(
            exception_global_id=exception_id,
            actor_user_id=self.actor,
            outcome=selected_outcome,
            opinion=opinion,
            occurred_at=now,
            expected_version=expected_cycle_version,
            expected_input_hash=expected_input_hash,
            expected_exception_version=expected_exception_version,
        )
        decided = next(
            value for value in updated.exceptions if value.global_id == exception_id
        )
        with _controlled_review_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                gate,
                "gate.review.exception.decide",
            )
            self._update_exception(exception_document, decided)
            self._update_cycle(cycle_document, updated)
            event = self._insert_exception_decision_event(updated, decided, now=now)
            self._audit(
                "gate.review.exception.decide",
                exception_id,
                decided.version,
                {"cycleId": str(cycle_id), "eventId": str(event.global_id)},
            )
            response = self._workspace_for(project, gate)
            self._seal_idempotency(receipt, response)
        return GateReviewCommandOutcome(response)

    def decide_gate(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        expected_cycle_version: int,
        expected_input_hash: str,
        outcome: str,
    ) -> GateReviewCommandOutcome | None:
        locked = self._locked_review_scope(project_id, gate_id)
        if locked is None:
            return None
        project, gate, cycle_document = locked
        payload_hash = _payload_hash(
            {
                "operation": "gate.review.decide",
                "projectId": project_id,
                "gateId": gate_id,
                "expectedGateVersion": expected_gate_version,
                "expectedCycleVersion": expected_cycle_version,
                "expectedInputHash": expected_input_hash,
                "outcome": outcome,
            }
        )
        replay = self._idempotency_replay(
            idempotency_key, payload_hash, project, gate, "gate.review.decide"
        )
        if replay is not None:
            return GateReviewCommandOutcome(replay, True)
        self._require_in_review_state(gate)
        self._require_gate_version(gate, expected_gate_version)
        cycle = self._hydrate_cycle(cycle_document, lock_exceptions=True)
        self._require_current_binding_actor(
            project, cycle, cycle.policy.decision_authority_slot
        )
        current_input = self._build_current_input(project, gate)
        current_closure_action_refs = self._current_closure_action_references(
            project,
            gate,
            cycle,
            lock=True,
        )
        updated = cycle.decide(
            actor_user_id=self.actor,
            outcome=DecisionOutcome(outcome),
            occurred_at=datetime.now(UTC),
            expected_version=expected_cycle_version,
            expected_input_hash=expected_input_hash,
            current_input=current_input,
            current_closure_action_refs=current_closure_action_refs,
        )
        assert updated.decision is not None
        with _controlled_review_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key, payload_hash, project, gate, "gate.review.decide"
            )
            decision_document = self._insert_decision(updated.decision)
            self._update_cycle(cycle_document, updated)
            self._set_gate_decision(gate, cycle_document, decision_document)
            self._audit(
                "gate.review.decide",
                updated.decision.global_id,
                updated.version,
                {
                    "outcome": updated.decision.outcome.value,
                    "snapshotHash": str(decision_document.snapshot_hash),
                },
            )
            response = self._workspace_for(project, gate)
            self._seal_idempotency(receipt, response)
        return GateReviewCommandOutcome(response)

    def reopen_gate(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        expected_cycle_version: int,
        expected_input_hash: str,
        reason: str,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        bindings: tuple[dict[str, Any], ...],
    ) -> GateReviewCommandOutcome | None:
        locked = self._locked_review_scope(project_id, gate_id)
        if locked is None:
            return None
        project, gate, cycle_document = locked
        payload_hash = _payload_hash(
            {
                "operation": "gate.review.reopen",
                "projectId": project_id,
                "gateId": gate_id,
                "expectedGateVersion": expected_gate_version,
                "expectedCycleVersion": expected_cycle_version,
                "expectedInputHash": expected_input_hash,
                "reason": reason,
                "policyGlobalId": policy_global_id,
                "policyVersion": policy_version,
                "policySnapshotHash": policy_snapshot_hash,
                "bindings": bindings,
            }
        )
        replay = self._idempotency_replay(
            idempotency_key, payload_hash, project, gate, "gate.review.reopen"
        )
        if replay is not None:
            return GateReviewCommandOutcome(replay, True)
        self._require_gate_version(gate, expected_gate_version)
        cycle = self._hydrate_cycle(cycle_document, lock_exceptions=True)
        self._require_current_binding_actor(
            project, cycle, cycle.policy.reopen_authority_slot
        )
        policy = load_available_gate_review_policy_version(
            policy_global_id, policy_version, policy_snapshot_hash
        )
        if (
            policy is None
            or policy != cycle.policy
            or not _policy_matches_gate(policy, gate)
        ):
            raise _field_problem(
                "policyGlobalId", _("Select the current exact Gate Review Policy.")
            )
        now = datetime.now(UTC)
        transition = cycle.reopen(
            actor_user_id=self.actor,
            reason=reason,
            occurred_at=now,
            current_input=self._build_current_input(project, gate),
            current_bindings=self._resolve_bindings(project, bindings, now=now),
            gate_current_cycle_global_id=UUID(str(gate.current_review_cycle_global_id)),
            expected_version=expected_cycle_version,
            expected_input_hash=expected_input_hash,
        )
        with _controlled_review_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key, payload_hash, project, gate, "gate.review.reopen"
            )
            successor = self._persist_transition(
                project,
                gate,
                cycle_document,
                transition,
                review_state="in_review",
                reason=reason,
                occurred_at=now,
            )
            self._audit(
                "gate.review.reopen",
                transition.event.global_id,
                transition.current_cycle.version,
                {"successorCycleId": str(successor.global_id)},
            )
            response = self._workspace_for(project, gate)
            self._seal_idempotency(receipt, response)
        return GateReviewCommandOutcome(response)

    def refresh_gate_for_dependency_change_locked(
        self,
        project,
        gate,
        *,
        reason: str = "GATE_INPUT_CHANGED",
        occurred_at: datetime | None = None,
        initiated_by_user_id: str | None = None,
    ) -> bool:
        if not self._dependency_system:
            raise PermissionDenied()
        if str(gate.get("review_state") or "not_started") not in {
            "in_review",
            "decided",
            "requires_review",
        }:
            return False
        cycle_document = self._locked_current_cycle(project, gate)
        if cycle_document is None:
            raise ValueError("Persisted Gate current review cycle is unavailable.")
        cycle = self._hydrate_cycle(cycle_document, lock_exceptions=True)
        now = occurred_at or datetime.now(UTC)
        detected_input = self._build_current_input(project, gate)
        if detected_input.snapshot_hash == cycle.input_hash:
            return False
        with _controlled_review_write_scope():
            successor_cycle_id = uuid5(
                UUID(str(gate.global_id)),
                f"review-cycle:{cycle.cycle_number + 1}",
            )
            transition = cycle.invalidate_for_dependency_change(
                actor_user_id=self.actor,
                initiated_by_user_id=initiated_by_user_id,
                reason=reason,
                occurred_at=now,
                current_input=detected_input,
                current_bindings=tuple(
                    self._resolve_frozen_binding(project, binding, now=now)
                    for binding in cycle.bindings
                ),
                gate_current_cycle_global_id=UUID(
                    str(gate.current_review_cycle_global_id)
                ),
                expected_version=cycle.version,
                expected_input_hash=cycle.input_hash,
            )
            if transition.current_cycle.global_id != successor_cycle_id:
                raise ValueError("The Gate review successor identity drifted.")
            self._persist_transition(
                project,
                gate,
                cycle_document,
                transition,
                review_state="requires_review",
                reason=reason,
                occurred_at=now,
                initiated_by_user_id=initiated_by_user_id,
            )
            operation = (
                "gate.review.refresh"
                if transition.event.kind.value == "refreshed"
                else "gate.review.invalidate"
            )
            summary = {
                "oldInputHash": cycle.input_hash,
                "newInputHash": detected_input.snapshot_hash,
            }
            if initiated_by_user_id:
                summary["initiatedByUserId"] = initiated_by_user_id
            self._audit(
                operation,
                transition.event.global_id,
                transition.current_cycle.version,
                summary,
            )
        return True

    def refresh_gate_for_work_item_dependency_locked(
        self,
        project,
        gate,
        *,
        work_item_global_id: UUID,
        reason: str = "GATE_WORK_ITEM_CHANGED",
        occurred_at: datetime | None = None,
        initiated_by_user_id: str | None = None,
    ) -> bool:
        """Refresh one blocker or exact closure-action dependency under Gate locks."""
        if not self._dependency_system:
            raise PermissionDenied()
        if str(gate.get("review_state") or "not_started") not in {
            "in_review",
            "decided",
            "requires_review",
        }:
            return False
        now = occurred_at or datetime.now(UTC)
        cycle_document = self._locked_current_cycle(project, gate)
        if cycle_document is not None:
            cycle = self._hydrate_cycle(cycle_document, lock_exceptions=True)
            if self._closure_action_reference_drifted_locked(
                project,
                gate,
                cycle,
                work_item_global_id,
            ):
                # Authority substitution is a held business policy. Revalidate every
                # frozen binding before changing persisted input truth, and let a
                # failure surface to the background job without replacing anyone.
                tuple(
                    self._resolve_frozen_binding(project, binding, now=now)
                    for binding in cycle.bindings
                )
                gate.review_input_version = (
                    int(gate.get("review_input_version") or 1) + 1
                )
                with _controlled_dependency_input_write_scope():
                    return self.refresh_gate_for_dependency_change_locked(
                        project,
                        gate,
                        reason=reason,
                        occurred_at=now,
                        initiated_by_user_id=initiated_by_user_id,
                    )
        return self.refresh_gate_for_dependency_change_locked(
            project,
            gate,
            reason=reason,
            occurred_at=now,
            initiated_by_user_id=initiated_by_user_id,
        )

    @staticmethod
    def _closure_action_reference_drifted_locked(
        project,
        gate,
        cycle: ReviewCycle,
        work_item_global_id: UUID,
    ) -> bool:
        if cycle.state not in {CycleState.ACTIVE, CycleState.DECIDED}:
            return False
        decision_hashes = (
            set(cycle.decision.exception_hashes)
            if cycle.state is CycleState.DECIDED and cycle.decision is not None
            else None
        )
        references = tuple(
            value.closure_action_ref
            for value in cycle.exceptions
            if value.closure_action_ref.is_exact
            and value.closure_action_ref.global_id == work_item_global_id
            and (decision_hashes is None or value.snapshot_hash in decision_hashes)
        )
        if not references:
            return False
        try:
            document = frappe.get_doc(
                "NPI Domain Work Item",
                str(work_item_global_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            document = None
        current_reference = (
            _closure_action_reference(document)
            if document is not None
            and str(document.global_id) == str(work_item_global_id)
            and _closure_action_matches_scope(document, project, gate)
            else None
        )
        return any(reference != current_reference for reference in references)

    def _workspace_for(self, project, gate) -> dict[str, Any]:
        current_input = self._build_current_input(project, gate)
        cycle_document = self._current_cycle_document(project, gate)
        cycle = (
            self._hydrate_cycle(cycle_document, lock_exceptions=False)
            if cycle_document is not None
            else None
        )
        now = datetime.now(UTC)
        current_closure_action_refs = (
            self._current_closure_action_references(
                project,
                gate,
                cycle,
                lock=False,
            )
            if cycle is not None
            else {}
        )
        decision_current = bool(
            cycle is not None
            and cycle.state is CycleState.DECIDED
            and downstream_decision_is_current(
                cycle,
                gate_current_cycle_global_id=UUID(
                    str(gate.current_review_cycle_global_id)
                ),
                current_input=current_input,
                at=now,
                current_closure_action_refs=current_closure_action_refs,
            )
        )
        evidence = FrappeGateEvidenceRepository(
            principal=self.principal,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )._workspace_for(project, gate)
        decisions = self._decision_documents(project, gate)
        blockers = self._blocker_documents(project, gate)
        available_policies = self._available_policy_options(gate)
        closure_actions = self._closure_action_documents(project, gate)
        actor_member = self._current_actor_member(project)
        decision_readiness = self._decision_readiness(
            project,
            gate,
            cycle,
            current_input=current_input,
            actor_member=actor_member,
            at=now,
            current_closure_action_refs=current_closure_action_refs,
        )
        exception_request_options = self._exception_request_options(
            project,
            gate,
            cycle,
            current_input=current_input,
            closure_actions=closure_actions,
            actor_member=actor_member,
            at=now,
        )
        exception_allowed_outcomes = self._exception_allowed_outcomes(
            project,
            gate,
            cycle,
            current_input=current_input,
            actor_member=actor_member,
            at=now,
            current_closure_action_refs=current_closure_action_refs,
        )
        return {
            "project": {
                "globalId": str(UUID(str(project.global_id))),
                "businessCode": str(project.business_code),
                "title": str(project.title),
            },
            "gate": {
                "globalId": str(UUID(str(gate.global_id))),
                "key": str(gate.gate_key),
                "title": str(gate.title),
                "reviewState": str(gate.review_state or "not_started"),
                "version": int(gate.optimistic_version),
                "currentCycleGlobalId": _optional_uuid_text(
                    gate.current_review_cycle_global_id
                ),
                "latestDecisionGlobalId": _optional_uuid_text(
                    gate.latest_decision_snapshot_global_id
                ),
                "latestDecisionHash": (
                    str(gate.latest_decision_snapshot_hash)
                    if gate.latest_decision_snapshot_hash
                    else None
                ),
                "latestDecisionOutcome": (
                    str(gate.latest_decision_outcome)
                    if gate.latest_decision_outcome
                    else None
                ),
                "downstreamDecisionCurrent": decision_current,
            },
            "evidence": evidence,
            "activeCycle": (
                self._cycle_response(
                    cycle_document,
                    cycle,
                    review_open=(
                        str(gate.review_state or "not_started") == "in_review"
                        and current_input.snapshot_hash == cycle.input_hash
                    ),
                    exception_allowed_outcomes=exception_allowed_outcomes,
                )
                if cycle_document is not None and cycle is not None
                else None
            ),
            "decisions": [
                self._decision_response(
                    project,
                    gate,
                    document,
                    current=(
                        str(document.global_id)
                        == str(gate.latest_decision_snapshot_global_id or "")
                        and decision_current
                    ),
                )
                for document in decisions
            ],
            "decisionReadiness": decision_readiness,
            "exceptionRequestOptions": exception_request_options,
            "availablePolicies": available_policies,
            "eligibleMembers": [
                _member_response(member)
                for member in self._current_members(project, maximum=_MAX_MEMBERS)
            ],
            "eligibleClosureActions": [
                {
                    "globalId": str(UUID(str(document.global_id))),
                    "title": str(document.title),
                    "state": str(document.state_key),
                    "stateLabelSource": str(document.state_label_source),
                    "version": int(document.optimistic_version),
                }
                for document in closure_actions
            ],
            "blockers": [
                {
                    "globalId": str(UUID(str(document.global_id))),
                    "kind": str(document.kind),
                    "title": str(document.title),
                    "state": str(document.state_key),
                    "stateLabelSource": str(document.state_label_source),
                    "dueAt": _datetime_iso(document.due_at),
                    "owner": str(document.owner_user_id),
                }
                for document in blockers
            ],
            "dependencyChanges": self._dependency_changes(project, gate),
            "permissions": self._workspace_permissions(
                project,
                gate,
                cycle,
                available_policies=available_policies,
                decision_readiness=decision_readiness,
                exception_request_options=exception_request_options,
                exception_allowed_outcomes=exception_allowed_outcomes,
                current_input=current_input,
            ),
        }

    def _decision_readiness(
        self,
        project,
        gate,
        cycle: ReviewCycle | None,
        *,
        current_input: GateInputSnapshot,
        actor_member,
        at: datetime,
        current_closure_action_refs: Mapping[UUID, ClosureActionReference],
    ) -> dict[str, list[Any]]:
        outcomes = tuple(DecisionOutcome)
        if (
            str(gate.review_state or "not_started") != "in_review"
            or cycle is None
            or cycle.state is not CycleState.ACTIVE
        ):
            return _blocked_decision_readiness(outcomes, "REVIEW_CYCLE_CLOSED")
        if (
            not self._actor_has_frozen_binding(
                cycle,
                cycle.policy.decision_authority_slot,
                actor_member=actor_member,
            )
            or not self._has_command_transport_role()
        ):
            return _blocked_decision_readiness(outcomes, "DECISION_AUTHORITY_REQUIRED")

        allowed: list[str] = []
        blocked: list[dict[str, str]] = []
        for outcome in outcomes:
            try:
                cycle.decide(
                    actor_user_id=self.actor,
                    outcome=outcome,
                    occurred_at=at,
                    expected_version=cycle.version,
                    expected_input_hash=cycle.input_hash,
                    current_input=current_input,
                    current_closure_action_refs=current_closure_action_refs,
                )
            except ReviewDenied as problem:
                if problem.code not in _DECISION_BLOCKED_CODES:
                    raise ValueError(
                        "Gate decision readiness returned an uncontracted denial."
                    ) from problem
                blocked.append({"outcome": outcome.value, "code": problem.code})
            else:
                allowed.append(outcome.value)
        return {"allowedOutcomes": allowed, "blockedReasons": blocked}

    def _exception_request_options(
        self,
        project,
        gate,
        cycle: ReviewCycle | None,
        *,
        current_input: GateInputSnapshot,
        closure_actions: Sequence[Any],
        actor_member,
        at: datetime,
    ) -> list[dict[str, Any]]:
        if (
            str(gate.review_state or "not_started") != "in_review"
            or cycle is None
            or cycle.state is not CycleState.ACTIVE
            or actor_member is None
            or not self._has_command_transport_role()
            or not closure_actions
            or current_input.snapshot_hash != cycle.input_hash
            or not current_input.file_evidence_safe
        ):
            return []
        closure_action_ids = tuple(
            UUID(str(document.global_id)) for document in closure_actions
        )
        closure_action_refs = {
            UUID(str(document.global_id)): _closure_action_reference(document)
            for document in closure_actions
        }
        options: list[dict[str, Any]] = []
        for requirement in sorted(
            current_input.requirements,
            key=lambda value: str(value.global_id),
        ):
            if (
                requirement.priority not in {"P1", "P2"}
                or requirement.evidence_complete
            ):
                continue
            for rule in sorted(
                cycle.policy.exception_rules,
                key=lambda value: value.kind.casefold(),
            ):
                if requirement.requirement_key not in rule.eligible_requirement_keys:
                    continue
                try:
                    projected = cycle.request_exception(
                        exception_global_id=uuid5(
                            cycle.global_id,
                            (
                                "request-option:"
                                f"{actor_member.global_id}:"
                                f"{requirement.global_id}:{rule.kind}"
                            ),
                        ),
                        requester_member_global_id=UUID(str(actor_member.global_id)),
                        actor_user_id=self.actor,
                        kind=rule.kind,
                        requirement_key=requirement.requirement_key,
                        reason="Server eligibility projection.",
                        risk="Server eligibility projection.",
                        closure_action_ref=closure_action_refs[closure_action_ids[0]],
                        closure_action_kind="action",
                        requested_at=at,
                        expires_at=at + timedelta(days=rule.maximum_validity_days),
                        expected_version=cycle.version,
                        expected_input_hash=cycle.input_hash,
                    )
                except ReviewDenied:
                    continue
                projected_exception = projected.exceptions[-1]
                if (
                    projected_exception.requirement_global_id != requirement.global_id
                    or projected_exception.kind != rule.kind
                ):
                    raise ValueError(
                        "Gate exception request option projection drifted."
                    )
                options.append(
                    {
                        "requirementGlobalId": str(requirement.global_id),
                        "requirementKey": requirement.requirement_key,
                        "kind": rule.kind,
                        "maximumValidityDays": rule.maximum_validity_days,
                        "closureActionGlobalIds": [
                            str(identity) for identity in closure_action_ids
                        ],
                    }
                )
        return options

    def _exception_allowed_outcomes(
        self,
        project,
        gate,
        cycle: ReviewCycle | None,
        *,
        current_input: GateInputSnapshot,
        actor_member,
        at: datetime,
        current_closure_action_refs: Mapping[UUID, ClosureActionReference],
    ) -> dict[UUID, tuple[str, ...]]:
        if cycle is None:
            return {}
        result: dict[UUID, tuple[str, ...]] = {}
        review_open = (
            str(gate.review_state or "not_started") == "in_review"
            and cycle.state is CycleState.ACTIVE
            and current_input.snapshot_hash == cycle.input_hash
            and self._has_command_transport_role()
        )
        for value in cycle.exceptions:
            allowed: list[str] = []
            if not value.closure_action_ref.is_exact:
                result[value.global_id] = ()
                continue
            exact_approver = self._actor_has_frozen_binding(
                cycle,
                value.approval_authority_slot,
                actor_member=actor_member,
            )
            if (
                review_open
                and exact_approver
                and value.state is ExceptionState.PENDING
                and value.approval_user_id == self.actor
                and actor_member is not None
                and value.approval_member_global_id == UUID(str(actor_member.global_id))
                and value.requester_user_id != self.actor
                and value.requester_member_global_id
                != UUID(str(actor_member.global_id))
            ):
                for outcome in ExceptionOutcome:
                    if (
                        outcome is ExceptionOutcome.APPROVED
                        and current_closure_action_refs.get(value.global_id)
                        != value.closure_action_ref
                    ):
                        continue
                    try:
                        cycle.decide_exception(
                            exception_global_id=value.global_id,
                            actor_user_id=self.actor,
                            outcome=outcome,
                            opinion="Server eligibility projection.",
                            occurred_at=at,
                            expected_version=cycle.version,
                            expected_input_hash=cycle.input_hash,
                            expected_exception_version=value.version,
                        )
                    except ReviewDenied:
                        continue
                    else:
                        allowed.append(outcome.value)
            result[value.global_id] = tuple(allowed)
        return result

    def _actor_has_frozen_binding(
        self,
        cycle: ReviewCycle,
        slot: str,
        *,
        actor_member,
    ) -> bool:
        return bool(
            actor_member is not None
            and any(
                binding.slot.casefold() == slot.casefold()
                and binding.user_id == self.actor
                and binding.member_global_id == UUID(str(actor_member.global_id))
                for binding in cycle.bindings
            )
        )

    def _workspace_permissions(
        self,
        project,
        gate,
        cycle: ReviewCycle | None,
        *,
        available_policies: Sequence[Mapping[str, object]],
        decision_readiness: Mapping[str, object] | None = None,
        exception_request_options: Sequence[Mapping[str, object]] = (),
        exception_allowed_outcomes: Mapping[UUID, Sequence[str]] | None = None,
        current_input: GateInputSnapshot | None = None,
    ) -> dict[str, bool]:
        member = self._current_actor_member(project)

        def bound(slot: str) -> bool:
            return bool(
                cycle is not None
                and member is not None
                and any(
                    binding.slot.casefold() == slot.casefold()
                    and binding.user_id == self.actor
                    and binding.member_global_id == UUID(str(member.global_id))
                    for binding in cycle.bindings
                )
            )

        gate_state = str(gate.review_state or "not_started")
        transport_admitted = self._has_command_transport_role()
        review_open = gate_state == "in_review"
        active = review_open and cycle is not None and cycle.state is CycleState.ACTIVE
        decided = (
            gate_state == "decided"
            and cycle is not None
            and cycle.state is CycleState.DECIDED
        )
        exact_current_policy_available = _gate_policy_is_available(
            gate, available_policies
        )
        approved = (
            {
                record.step_key
                for record in cycle.reviews
                if record.outcome is ReviewOutcome.APPROVED
            }
            if cycle is not None
            else set()
        )
        reviewed = (
            {record.step_key for record in cycle.reviews}
            if cycle is not None
            else set()
        )
        can_review = bool(
            transport_admitted
            and active
            and cycle is not None
            and current_input is not None
            and current_input.snapshot_hash == cycle.input_hash
            and any(
                step.key not in reviewed
                and bound(step.authority_slot)
                and all(
                    prior.key in approved
                    for prior in cycle.selected_steps
                    if prior.sequence < step.sequence
                )
                for step in cycle.selected_steps
            )
        )
        return {
            "canView": True,
            "canStartReview": bool(
                self._is_internal_system_manager()
                and available_policies
                and (
                    gate_state == "not_started"
                    or (
                        gate_state == "requires_review"
                        and exact_current_policy_available
                    )
                )
            ),
            "canReview": can_review,
            "canRequestException": bool(
                transport_admitted and exception_request_options
            ),
            "canApproveException": bool(
                transport_admitted
                and exception_allowed_outcomes
                and any(exception_allowed_outcomes.values())
            ),
            "canDecide": bool(
                transport_admitted
                and decision_readiness
                and decision_readiness.get("allowedOutcomes")
            ),
            "canReopen": bool(
                transport_admitted
                and decided
                and cycle is not None
                and exact_current_policy_available
                and bound(cycle.policy.reopen_authority_slot)
            ),
        }

    def _cycle_response(
        self,
        document,
        cycle: ReviewCycle,
        *,
        review_open: bool,
        exception_allowed_outcomes: Mapping[UUID, Sequence[str]] | None = None,
    ) -> dict[str, Any]:
        bindings = {binding.slot.casefold(): binding for binding in cycle.bindings}
        records = {record.step_key: record for record in cycle.reviews}
        record_documents = {
            str(value.review_step_key): value
            for value in self._review_documents_from_document(document)
        }
        approved = {
            record.step_key
            for record in cycle.reviews
            if record.outcome is ReviewOutcome.APPROVED
        }
        steps: list[dict[str, Any]] = []
        for step in cycle.selected_steps:
            record = records.get(step.key)
            record_document = record_documents.get(step.key)
            state = (
                record.outcome.value
                if record is not None
                else (
                    "available"
                    if review_open
                    and cycle.state is CycleState.ACTIVE
                    and all(
                        prior.key in approved
                        for prior in cycle.selected_steps
                        if prior.sequence < step.sequence
                    )
                    else "waiting"
                )
            )
            binding = bindings[step.authority_slot.casefold()]
            steps.append(
                {
                    "stepKey": step.key,
                    "sequence": step.sequence,
                    "slot": step.authority_slot,
                    "assignedMember": _binding_member_response(binding),
                    "state": state,
                    "review": (
                        {
                            "globalId": str(UUID(str(record_document.global_id))),
                            "stepKey": record.step_key,
                            "outcome": record.outcome.value,
                            "opinion": record.opinion,
                            "actor": record.actor_user_id,
                            "reviewedAt": _datetime_iso(record.occurred_at),
                            "inputHash": record.reviewed_input_hash,
                            "snapshotHash": str(record_document.record_snapshot_hash),
                        }
                        if record is not None and record_document is not None
                        else None
                    ),
                }
            )
        exception_documents = {
            str(value.global_id): value
            for value in self._exception_documents_from_document(document, lock=False)
        }
        return {
            "globalId": str(cycle.global_id),
            "number": cycle.cycle_number,
            "trigger": cycle.trigger.value,
            "state": cycle.state.value,
            "version": cycle.version,
            "policyRef": _policy_ref(cycle.policy),
            "policyDefinition": _policy_option(cycle.policy),
            "inputHash": cycle.input_hash,
            "bindings": [
                value.canonical_dict()
                for value in sorted(
                    cycle.bindings, key=lambda binding: binding.slot.casefold()
                )
            ],
            "selectedSteps": steps,
            "exceptions": [
                self._exception_response(
                    value,
                    exception_documents[str(value.global_id)],
                    allowed_outcomes=(exception_allowed_outcomes or {}).get(
                        value.global_id, ()
                    ),
                )
                for value in cycle.exceptions
            ],
            "startedAt": _datetime_iso(document.started_at),
            "startedBy": str(document.started_by),
        }

    @staticmethod
    def _exception_response(
        value: ReviewException,
        document,
        *,
        allowed_outcomes: Sequence[str],
    ) -> dict[str, Any]:
        request_snapshot = _json_object(document.request_snapshot)
        request_schema_version = request_snapshot.get("schemaVersion")
        if type(request_schema_version) is not int or request_schema_version not in {
            1,
            2,
        }:
            raise ValueError("Persisted Gate exception request schema is unsupported.")
        if request_schema_version == 2 and not value.closure_action_ref.is_exact:
            raise ValueError("Persisted Gate exception request profile is invalid.")
        if not value.closure_action_ref.is_exact and allowed_outcomes:
            raise ValueError("Legacy Gate exception cannot expose command outcomes.")
        decision = None
        if value.state is not ExceptionState.PENDING:
            assert value.outcome is not None
            decision = {
                "outcome": value.outcome.value,
                "approver": {
                    "memberGlobalId": str(value.approval_member_global_id),
                    "userId": value.approval_user_id,
                    "displayName": _display_name(value.approval_user_id),
                },
                "opinion": value.decision_opinion,
                "decidedAt": _datetime_iso(value.decided_at),
                "snapshotHash": str(document.decision_snapshot_hash),
            }
        return {
            "globalId": str(value.global_id),
            "requirementGlobalId": str(value.requirement_global_id),
            "requirementKey": value.requirement_key,
            "kind": value.kind,
            "reason": value.reason,
            "risk": value.risk,
            "requester": {
                "memberGlobalId": str(value.requester_member_global_id),
                "userId": value.requester_user_id,
                "displayName": _display_name(value.requester_user_id),
            },
            "requestedAt": _datetime_iso(value.requested_at),
            "expiresAt": _datetime_iso(value.expires_at),
            "requestSchemaVersion": request_schema_version,
            "closureActionRef": value.closure_action_ref.canonical_dict(),
            "state": value.state.value,
            "allowedOutcomes": list(allowed_outcomes),
            "version": value.version,
            "requestSnapshotHash": str(document.request_snapshot_hash),
            "decision": decision,
        }

    def _dependency_changes(self, project, gate) -> list[dict[str, Any]]:
        documents = _bounded_documents(
            "NPI Gate Review Event",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "gate_global_id": str(gate.global_id),
                "event_type": ["in", ["invalidated", "refreshed"]],
            },
            order_by="occurred_at desc, global_id desc",
            maximum=_MAX_DEPENDENCY_CHANGES,
        )
        ordered = sorted(
            documents,
            key=lambda document: (
                _datetime_value(document.occurred_at),
                str(UUID(str(document.global_id))),
            ),
            reverse=True,
        )
        return [self._dependency_change_response(document) for document in ordered]

    @staticmethod
    def _dependency_change_response(document) -> dict[str, Any]:
        payload = _json_object(document.payload)
        _verify_json_hash(payload, str(document.payload_hash))
        expected_payload_keys = {
            "schemaVersion",
            "globalId",
            "eventKey",
            "tenantId",
            "projectGlobalId",
            "gateGlobalId",
            "cycleGlobalId",
            "successorCycleGlobalId",
            "actionGlobalId",
            "eventType",
            "actorUserId",
            "occurredAt",
            "requestId",
            "traceId",
            "detail",
        }
        if (
            set(payload) != expected_payload_keys
            or type(payload["schemaVersion"]) is not int
        ):
            raise ValueError("Persisted Gate dependency event payload is not closed.")
        required_text_fields = (
            "globalId",
            "eventKey",
            "tenantId",
            "projectGlobalId",
            "gateGlobalId",
            "cycleGlobalId",
            "successorCycleGlobalId",
            "eventType",
            "actorUserId",
            "occurredAt",
            "requestId",
            "traceId",
        )
        if any(
            not isinstance(payload[field], str) or not payload[field].strip()
            for field in required_text_fields
        ):
            raise ValueError("Persisted Gate dependency event payload text is invalid.")
        event_type = payload["eventType"]
        if event_type not in {"invalidated", "refreshed"}:
            raise ValueError("Persisted Gate dependency event type is invalid.")
        detail = payload["detail"]
        schema_version = payload["schemaVersion"]
        extended_detail_keys = {
            "reason",
            "oldInputHash",
            "newInputHash",
            "priorDecisionSnapshotGlobalId",
            "priorDecisionHash",
            "initiatedByUserId",
        }
        legacy_detail_keys = {
            "oldInputHash",
            "newInputHash",
            "priorDecisionSnapshotGlobalId",
            "priorDecisionHash",
        }
        if (
            not isinstance(detail, dict)
            or schema_version not in {1, 2}
            or (schema_version == 2 and set(detail) != extended_detail_keys)
            or (
                schema_version == 1
                and frozenset(detail)
                not in {
                    frozenset(legacy_detail_keys),
                    frozenset(extended_detail_keys),
                }
            )
        ):
            raise ValueError("Persisted Gate dependency event detail is not closed.")
        legacy_v1 = schema_version == 1 and set(detail) == legacy_detail_keys

        event_global_id = UUID(str(payload["globalId"]))
        project_global_id = UUID(str(payload["projectGlobalId"]))
        gate_global_id = UUID(str(payload["gateGlobalId"]))
        prior_cycle_global_id = UUID(str(payload["cycleGlobalId"]))
        successor_cycle_global_id = UUID(str(payload["successorCycleGlobalId"]))
        impact_action_global_id = (
            UUID(str(payload["actionGlobalId"]))
            if payload["actionGlobalId"] not in (None, "")
            else None
        )
        if payload["actionGlobalId"] not in (None, "") and not isinstance(
            payload["actionGlobalId"], str
        ):
            raise ValueError(
                "Persisted Gate dependency event impact action is invalid."
            )
        if prior_cycle_global_id == successor_cycle_global_id:
            raise ValueError(
                "Persisted Gate dependency event cycle lineage is invalid."
            )
        old_input_hash = _strict_sha256(
            detail["oldInputHash"], "old Gate review input hash"
        )
        new_input_hash = _strict_sha256(
            detail["newInputHash"], "new Gate review input hash"
        )
        if old_input_hash == new_input_hash:
            raise ValueError("Persisted Gate dependency event input did not change.")
        prior_decision_global_id = (
            UUID(str(detail["priorDecisionSnapshotGlobalId"]))
            if isinstance(detail["priorDecisionSnapshotGlobalId"], str)
            and detail["priorDecisionSnapshotGlobalId"].strip()
            else None
        )
        prior_decision_lineage_hash = (
            _strict_sha256(
                detail["priorDecisionHash"],
                "prior Gate decision lineage hash",
            )
            if isinstance(detail["priorDecisionHash"], str)
            and detail["priorDecisionHash"].strip()
            else None
        )
        if (
            detail["priorDecisionSnapshotGlobalId"] is not None
            and prior_decision_global_id is None
        ) or (
            detail["priorDecisionHash"] is not None
            and prior_decision_lineage_hash is None
        ):
            raise ValueError(
                "Persisted Gate dependency event decision lineage is invalid."
            )
        if (prior_decision_global_id is None) != (
            prior_decision_lineage_hash is None
        ) or (event_type == "invalidated" and prior_decision_global_id is None):
            raise ValueError(
                "Persisted Gate dependency event decision lineage is incomplete."
            )
        actor_user_id = payload["actorUserId"]
        initiated_by_user_id = None if legacy_v1 else detail["initiatedByUserId"]
        reason = "GATE_INPUT_CHANGED" if legacy_v1 else detail["reason"]
        if (
            not isinstance(reason, str)
            or not actor_user_id.strip()
            or len(actor_user_id) > 254
            or (
                initiated_by_user_id is not None
                and (
                    not isinstance(initiated_by_user_id, str)
                    or not initiated_by_user_id.strip()
                    or len(initiated_by_user_id) > 254
                )
            )
            or not reason.strip()
            or len(reason) > 140
        ):
            raise ValueError("Persisted Gate dependency event text is invalid.")
        occurred_at = _datetime_value(document.occurred_at)
        if (
            str(event_global_id) != str(UUID(str(document.global_id)))
            or str(project_global_id) != str(UUID(str(document.project_global_id)))
            or str(gate_global_id) != str(UUID(str(document.gate_global_id)))
            or str(prior_cycle_global_id) != str(UUID(str(document.cycle_global_id)))
            or str(successor_cycle_global_id)
            != str(UUID(str(document.successor_cycle_global_id)))
            or (
                str(impact_action_global_id)
                if impact_action_global_id is not None
                else None
            )
            != (
                str(UUID(str(document.action_global_id)))
                if document.action_global_id not in (None, "")
                else None
            )
            or event_type != str(document.event_type)
            or actor_user_id != str(document.actor_user_id)
            or str(payload["tenantId"]) != str(document.tenant_id)
            or str(payload["requestId"]) != str(document.request_id)
            or str(payload["traceId"]) != str(document.trace_id)
            or str(payload["eventKey"]) != str(document.event_key)
            or str(payload["eventKey"])
            != f"{prior_cycle_global_id}:{event_type}:{successor_cycle_global_id}"
            or str(payload["occurredAt"]) != _datetime_canonical(occurred_at)
            or event_global_id
            != uuid5(
                prior_cycle_global_id,
                f"{event_type}:{successor_cycle_global_id}:{new_input_hash}",
            )
        ):
            raise ValueError("Persisted Gate dependency event integrity failed.")
        return {
            "eventGlobalId": str(event_global_id),
            "eventType": event_type,
            "priorCycleGlobalId": str(prior_cycle_global_id),
            "successorCycleGlobalId": str(successor_cycle_global_id),
            "impactActionGlobalId": (
                str(impact_action_global_id)
                if impact_action_global_id is not None
                else None
            ),
            "oldInputHash": old_input_hash,
            "newInputHash": new_input_hash,
            "priorDecisionGlobalId": (
                str(prior_decision_global_id)
                if prior_decision_global_id is not None
                else None
            ),
            "priorDecisionLineageHash": prior_decision_lineage_hash,
            "actorUserId": actor_user_id,
            "initiatedByUserId": initiated_by_user_id,
            "occurredAt": _datetime_iso(occurred_at),
            "reason": reason,
        }

    def _available_policy_options(self, gate) -> list[dict[str, Any]]:
        names = frappe.get_all(
            "NPI Gate Review Policy Version",
            filters={
                "publication_state": "published",
                "gate_template_global_id": str(gate.gate_template_global_id),
                "gate_template_version": int(gate.gate_template_version),
                "gate_template_snapshot_hash": str(gate.gate_template_snapshot_hash),
            },
            pluck="name",
            order_by="policy_global_id asc, policy_version asc",
            limit_page_length=_MAX_POLICY_OPTIONS + 1,
        )
        if len(names) > _MAX_POLICY_OPTIONS:
            raise ValueError("Applicable Gate Review Policy collection is too large.")
        result: list[dict[str, Any]] = []
        for name in names:
            document = frappe.get_doc("NPI Gate Review Policy Version", name)
            policy = load_available_gate_review_policy_version(
                UUID(str(document.policy_global_id)),
                int(document.policy_version),
                str(document.snapshot_hash),
            )
            if policy is None:
                continue
            result.append(_policy_option(policy))
        return result

    def _build_current_input(self, project, gate) -> GateInputSnapshot:
        if int(gate.requirements_frozen or 0) != 1:
            raise ValueError("A Gate review requires frozen Gate requirements.")
        snapshot = _json_object(gate.requirement_snapshot)
        rows = snapshot.get("requirements")
        if (
            snapshot.get("schemaVersion") != 1
            or not isinstance(rows, list)
            or canonical_snapshot_hash(snapshot) != str(gate.requirement_snapshot_hash)
        ):
            raise ValueError("Persisted Gate requirement snapshot integrity failed.")
        references = _bounded_documents(
            "NPI Gate Evidence Reference",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "gate_global_id": str(gate.global_id),
            },
            order_by="global_id asc",
            maximum=_MAX_EVIDENCE,
        )
        by_requirement: dict[str, list[tuple[GateEvidenceInput, bool]]] = {}
        dependencies = [
            GateDependencyInput(
                kind=DependencyEvaluator.GATE_INPUT_SNAPSHOT,
                global_id=UUID(str(gate.global_id)),
                version=int(gate.review_input_version or 1),
                snapshot_hash=canonical_snapshot_hash(snapshot),
            )
        ]
        for reference in references:
            evidence, valid, dependency_hash = self._resolve_evidence_input(
                project, gate, reference
            )
            by_requirement.setdefault(str(reference.requirement_global_id), []).append(
                (evidence, valid)
            )
            dependencies.append(
                GateDependencyInput(
                    kind=DependencyEvaluator.GATE_INPUT_SNAPSHOT,
                    global_id=UUID(str(reference.global_id)),
                    version=evidence.source_version,
                    snapshot_hash=dependency_hash,
                )
            )
        requirements: list[GateRequirementInput] = []
        evidence_values: list[GateEvidenceInput] = []
        known: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("Persisted Gate requirement is invalid.")
            requirement_id = str(UUID(str(row["globalId"])))
            if requirement_id in known:
                raise ValueError("Persisted Gate requirement identity is duplicated.")
            known.add(requirement_id)
            resolved = by_requirement.get(requirement_id, [])
            evidence_values.extend(value for value, _valid in resolved)
            required = str(row.get("classification")) == "required"
            requirements.append(
                GateRequirementInput(
                    global_id=UUID(requirement_id),
                    requirement_key=str(row["key"]),
                    priority=str(row["priority"]),
                    source_version=1,
                    source_hash=_canonical_hash(row),
                    evidence_complete=(
                        not required or any(valid for _value, valid in resolved)
                    ),
                )
            )
        if set(by_requirement) - known:
            raise ValueError("Persisted Gate evidence has an unknown requirement.")
        return GateInputSnapshot(
            gate_global_id=UUID(str(gate.global_id)),
            project_global_id=UUID(str(project.global_id)),
            tenant_id=str(project.tenant_id),
            gate_version=int(gate.review_input_version or 1),
            requirements=tuple(requirements),
            evidence=tuple(evidence_values),
            blockers=tuple(
                GateBlockerInput(
                    global_id=UUID(str(document.global_id)),
                    version=int(document.optimistic_version),
                    state=str(document.state_key),
                    blocking=True,
                    terminal=False,
                )
                for document in self._blocker_documents(project, gate)
            ),
            dependencies=tuple(dependencies),
        )

    def _resolve_evidence_input(self, project, gate, reference):
        if (
            str(reference.tenant_id) != str(project.tenant_id)
            or str(reference.project_global_id) != str(project.global_id)
            or str(reference.gate_global_id) != str(gate.global_id)
        ):
            raise ValueError("Persisted Gate evidence scope is invalid.")
        kind = str(reference.evidence_kind)
        source_id = UUID(str(reference.source_global_id))
        stored_version = int(reference.source_version)
        stored_hash = str(reference.source_hash)
        live_version, live_hash = stored_version, stored_hash
        exact, file_safe, status = False, True, "unavailable"
        if kind == "wbs_item":
            source = _optional_doc("NPI WBS Item", str(source_id))
            if source is not None and _source_matches_project(source, project):
                live_version = int(source.optimistic_version)
                live_hash = canonical_snapshot_hash(wbs_item_source_snapshot(source))
                exact = live_version == stored_version and live_hash == stored_hash
                status = "exact" if exact else "drifted"
        elif kind == "file_revision":
            file_safe = False
            source = _optional_doc("NPI File Revision", str(source_id))
            if source is not None and _source_matches_project(source, project):
                live_version, live_hash = int(source.revision), str(source.sha256)
                complete = has_complete_file_revision_identity(source)
                private = complete and has_live_private_file_identity(source)
                scan = (
                    str(file_revision_source_snapshot(source).get("scanState"))
                    if private
                    else "unavailable"
                )
                exact = live_version == stored_version and live_hash == stored_hash
                file_safe = exact and private and scan == "clean"
                status = f"{'exact' if exact else 'drifted'}:{scan}"
        else:
            raise ValueError("Persisted Gate evidence kind is unsupported.")
        value = GateEvidenceInput(
            global_id=UUID(str(reference.global_id)),
            requirement_global_id=UUID(str(reference.requirement_global_id)),
            evidence_kind=kind,
            source_global_id=source_id,
            source_version=live_version,
            source_hash=live_hash,
            is_file=kind == "file_revision",
            file_safe=file_safe,
        )
        return (
            value,
            exact and file_safe,
            _canonical_hash(
                {
                    "referenceGlobalId": str(reference.global_id),
                    "sourceGlobalId": str(source_id),
                    "storedVersion": stored_version,
                    "storedHash": stored_hash,
                    "liveVersion": live_version,
                    "liveHash": live_hash,
                    "status": status,
                }
            ),
        )

    def _hydrate_cycle(
        self,
        document,
        *,
        lock_exceptions: bool,
        locked_exception=None,
    ) -> ReviewCycle:
        policy = load_exact_gate_review_policy_version(
            UUID(str(document.policy_global_id)),
            int(document.policy_version),
            str(document.policy_snapshot_hash),
        )
        if policy is None or _json_object(document.policy_snapshot) != (
            policy.canonical_dict()
        ):
            raise ValueError("Persisted Gate Review Policy integrity failed.")
        input_snapshot = _input_snapshot_from_payload(
            _json_object(document.input_snapshot)
        )
        if (
            input_snapshot.snapshot_hash != str(document.input_hash)
            or input_snapshot.gate_global_id != UUID(str(document.gate_global_id))
            or input_snapshot.project_global_id != UUID(str(document.project_global_id))
            or input_snapshot.tenant_id != str(document.tenant_id)
        ):
            raise ValueError("Persisted Gate review input integrity failed.")
        binding_payload = _json_array(document.authority_bindings)
        bindings = tuple(
            AuthorityBinding(
                slot=str(value["slot"]),
                member_global_id=UUID(str(value["memberGlobalId"])),
                user_id=str(value["userId"]),
                display_name=str(value["displayName"]),
            )
            for value in binding_payload
            if isinstance(value, dict)
        )
        if len(bindings) != len(binding_payload):
            raise ValueError("Persisted Gate review bindings are invalid.")
        reviews: list[ReviewRecord] = []
        for record in self._review_documents_from_document(document):
            _verify_json_hash(record.record_snapshot, str(record.record_snapshot_hash))
            if not _history_matches_cycle(record, document):
                raise ValueError("Persisted Gate review record scope drifted.")
            reviews.append(
                ReviewRecord(
                    step_key=str(record.review_step_key),
                    actor_user_id=str(record.actor_user_id),
                    outcome=ReviewOutcome(str(record.outcome)),
                    opinion=str(record.opinion),
                    occurred_at=_datetime_value(record.occurred_at),
                    reviewed_input_hash=str(record.reviewed_input_hash),
                    policy_version=int(record.policy_version),
                    policy_hash=str(record.policy_snapshot_hash),
                )
            )
        exception_documents = self._exception_documents_from_document(
            document,
            lock=lock_exceptions,
            locked_exception=locked_exception,
        )
        requirements = {value.global_id: value for value in input_snapshot.requirements}
        rules = {value.kind: value for value in policy.exception_rules}
        exceptions: list[ReviewException] = []
        for exception_document in exception_documents:
            request_snapshot = _json_object(exception_document.request_snapshot)
            _verify_json_hash(
                request_snapshot,
                str(exception_document.request_snapshot_hash),
            )
            if not _history_matches_cycle(exception_document, document):
                raise ValueError("Persisted Gate review exception scope drifted.")
            requirement = requirements.get(
                UUID(str(exception_document.requirement_global_id))
            )
            rule = rules.get(str(exception_document.exception_kind))
            if requirement is None or rule is None:
                raise ValueError("Persisted Gate review exception reference drifted.")
            state = ExceptionState(str(exception_document.state))
            if state is not ExceptionState.PENDING:
                _verify_json_hash(
                    exception_document.decision_snapshot,
                    str(exception_document.decision_snapshot_hash),
                )
            closure_action_ref = _exception_closure_action_reference(
                exception_document,
                request_snapshot,
            )
            exceptions.append(
                ReviewException(
                    global_id=UUID(str(exception_document.global_id)),
                    cycle_global_id=UUID(str(document.global_id)),
                    gate_global_id=UUID(str(document.gate_global_id)),
                    project_global_id=UUID(str(document.project_global_id)),
                    tenant_id=str(document.tenant_id),
                    policy_global_id=policy.policy_global_id,
                    kind=str(exception_document.exception_kind),
                    requirement_global_id=requirement.global_id,
                    requirement_key=str(exception_document.requirement_key),
                    requirement_priority=requirement.priority,
                    approval_authority_slot=str(
                        exception_document.approver_authority_slot
                    ),
                    approval_member_global_id=UUID(
                        str(exception_document.approver_member_global_id)
                    ),
                    approval_user_id=str(exception_document.approver_user_id),
                    requester_member_global_id=UUID(
                        str(exception_document.requester_member_global_id)
                    ),
                    requester_user_id=str(exception_document.requester_user_id),
                    reason=str(exception_document.reason),
                    risk=str(exception_document.risk),
                    closure_action_ref=closure_action_ref,
                    closure_action_kind=rule.required_closure_action_kind,
                    requested_at=_datetime_value(exception_document.requested_at),
                    expires_at=_datetime_value(exception_document.expires_at),
                    policy_version=policy.policy_version,
                    policy_hash=policy.snapshot_hash,
                    input_hash=input_snapshot.snapshot_hash,
                    version=int(exception_document.optimistic_version),
                    state=state,
                    outcome=(
                        ExceptionOutcome(state.value)
                        if state is not ExceptionState.PENDING
                        else None
                    ),
                    decision_actor_user_id=(
                        str(exception_document.approver_user_id)
                        if state is not ExceptionState.PENDING
                        else None
                    ),
                    decision_opinion=(
                        str(exception_document.approval_opinion)
                        if state is not ExceptionState.PENDING
                        else None
                    ),
                    decided_at=(
                        _datetime_value(exception_document.decided_at)
                        if state is not ExceptionState.PENDING
                        else None
                    ),
                )
            )
        decision = self._hydrate_decision(
            document,
            policy=policy,
            input_snapshot=input_snapshot,
            reviews=tuple(reviews),
            exceptions=tuple(exceptions),
        )
        cycle = ReviewCycle(
            global_id=UUID(str(document.global_id)),
            gate_global_id=UUID(str(document.gate_global_id)),
            project_global_id=UUID(str(document.project_global_id)),
            tenant_id=str(document.tenant_id),
            cycle_number=int(document.cycle_number),
            trigger=CycleTrigger(str(document.trigger)),
            policy=policy,
            bindings=bindings,
            selected_steps=tuple(
                step
                for step in policy.steps
                if step.selected(input_snapshot.requirement_priorities)
            ),
            input_snapshot=input_snapshot,
            version=int(document.optimistic_version),
            state=CycleState(str(document.state)),
            reviews=tuple(reviews),
            exceptions=tuple(exceptions),
            decision=decision,
            prior_cycle_global_id=(
                UUID(str(document.prior_cycle_global_id))
                if document.prior_cycle_global_id
                else None
            ),
            prior_decision_snapshot_global_id=(
                UUID(str(document.prior_decision_snapshot_global_id))
                if document.prior_decision_snapshot_global_id
                else None
            ),
            prior_decision_hash=(
                str(document.prior_decision_hash)
                if document.prior_decision_hash
                else None
            ),
        )
        if binding_payload != [
            value.canonical_dict() for value in cycle.bindings
        ] or _json_array(document.selected_steps) != [
            value.canonical_dict() for value in cycle.selected_steps
        ]:
            raise ValueError("Persisted Gate review cycle snapshot drifted.")
        return cycle

    def _hydrate_decision(
        self,
        cycle_document,
        *,
        policy,
        input_snapshot: GateInputSnapshot,
        reviews: tuple[ReviewRecord, ...],
        exceptions: tuple[ReviewException, ...],
    ) -> DecisionSnapshot | None:
        identity = uuid5(UUID(str(cycle_document.global_id)), "decision-snapshot")
        document = _optional_doc("NPI Gate Decision Snapshot", str(identity))
        state = CycleState(str(cycle_document.state))
        if document is None:
            if state not in {CycleState.ACTIVE, CycleState.SUPERSEDED}:
                raise ValueError("Closed Gate review cycle lacks its decision.")
            return None
        if state in {
            CycleState.ACTIVE,
            CycleState.SUPERSEDED,
        } or not _history_matches_cycle(document, cycle_document):
            raise ValueError("Persisted Gate decision scope drifted.")
        _verify_json_hash(document.decision_snapshot, str(document.snapshot_hash))
        persisted_input = _input_snapshot_from_payload(
            _json_object(document.input_snapshot)
        )
        review_hashes = tuple(value.snapshot_hash for value in reviews)
        exception_hashes = tuple(
            value.snapshot_hash
            for value in sorted(exceptions, key=lambda value: str(value.global_id))
        )
        if (
            persisted_input != input_snapshot
            or tuple(_json_array(document.review_hashes)) != review_hashes
            or tuple(_json_array(document.exception_hashes)) != exception_hashes
            or str(document.policy_snapshot_hash) != policy.snapshot_hash
        ):
            raise ValueError("Persisted Gate decision content drifted.")
        # Domain semantic hash chains decisions into successor cycles/events.
        # DocType snapshot_hash also seals request/trace and is the public hash.
        return DecisionSnapshot.build(
            tenant_id=str(cycle_document.tenant_id),
            project_global_id=UUID(str(cycle_document.project_global_id)),
            gate_global_id=UUID(str(cycle_document.gate_global_id)),
            cycle_global_id=UUID(str(cycle_document.global_id)),
            cycle_number=int(cycle_document.cycle_number),
            outcome=DecisionOutcome(str(document.outcome)),
            actor_user_id=str(document.actor_user_id),
            occurred_at=_datetime_value(document.occurred_at),
            policy_global_id=policy.policy_global_id,
            policy_version=policy.policy_version,
            policy_hash=policy.snapshot_hash,
            input_snapshot=input_snapshot,
            review_hashes=review_hashes,
            exception_hashes=exception_hashes,
            cycle_version=int(document.cycle_version),
        )

    def _insert_cycle(
        self, cycle: ReviewCycle, *, started_by: str, started_at: datetime
    ):
        prior = cycle.prior_cycle_global_id
        return frappe.get_doc(
            {
                "doctype": "NPI Gate Review Cycle",
                "global_id": str(cycle.global_id),
                "tenant_id": cycle.tenant_id,
                "project_global_id": str(cycle.project_global_id),
                "gate_global_id": str(cycle.gate_global_id),
                "gate_shell": str(cycle.gate_global_id),
                "cycle_number": cycle.cycle_number,
                "trigger": cycle.trigger.value,
                "policy_global_id": str(cycle.policy.policy_global_id),
                "policy_version": cycle.policy.policy_version,
                "policy_snapshot_hash": cycle.policy.snapshot_hash,
                "policy_snapshot": cycle.policy.canonical_dict(),
                "authority_bindings": [
                    value.canonical_dict() for value in cycle.bindings
                ],
                "selected_steps": [
                    value.canonical_dict() for value in cycle.selected_steps
                ],
                "input_snapshot": cycle.input_snapshot.canonical_dict(),
                "input_hash": cycle.input_hash,
                "prior_cycle_global_id": str(prior) if prior else None,
                "prior_decision_snapshot_global_id": (
                    str(cycle.prior_decision_snapshot_global_id)
                    if cycle.prior_decision_snapshot_global_id
                    else None
                ),
                "prior_decision_hash": cycle.prior_decision_hash,
                "state": cycle.state.value,
                "optimistic_version": cycle.version,
                "started_by": started_by,
                "started_at": _database_datetime(started_at),
            }
        ).insert()

    @staticmethod
    def _update_cycle(document, cycle: ReviewCycle) -> None:
        document.state = cycle.state.value
        document.optimistic_version = cycle.version
        document.save()

    def _insert_review_record(self, prior, current, record, *, step):
        binding = next(
            value
            for value in prior.bindings
            if value.slot.casefold() == step.authority_slot.casefold()
        )
        return frappe.get_doc(
            {
                "doctype": "NPI Gate Review Record",
                "global_id": str(uuid5(prior.global_id, f"review:{record.step_key}")),
                "tenant_id": prior.tenant_id,
                "project_global_id": str(prior.project_global_id),
                "gate_global_id": str(prior.gate_global_id),
                "cycle_global_id": str(prior.global_id),
                "cycle_number": prior.cycle_number,
                "policy_global_id": str(prior.policy.policy_global_id),
                "policy_version": prior.policy.policy_version,
                "policy_snapshot_hash": prior.policy.snapshot_hash,
                "review_step_key": step.key,
                "review_step_sequence": step.sequence,
                "authority_slot": step.authority_slot,
                "assigned_member_global_id": str(binding.member_global_id),
                "assigned_user_id": binding.user_id,
                "assigned_display_name": binding.display_name,
                "actor_user_id": record.actor_user_id,
                "outcome": record.outcome.value,
                "opinion": record.opinion,
                "occurred_at": _database_datetime(record.occurred_at),
                "reviewed_input_hash": record.reviewed_input_hash,
                "cycle_version_before": prior.version,
                "cycle_version_after": current.version,
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    @staticmethod
    def _insert_exception(value: ReviewException):
        return frappe.get_doc(
            {
                "doctype": "NPI Gate Review Exception",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "gate_global_id": str(value.gate_global_id),
                "cycle_global_id": str(value.cycle_global_id),
                "policy_global_id": str(value.policy_global_id),
                "policy_version": value.policy_version,
                "policy_snapshot_hash": value.policy_hash,
                "requirement_global_id": str(value.requirement_global_id),
                "requirement_key": value.requirement_key,
                "exception_kind": value.kind,
                "reason": value.reason,
                "risk": value.risk,
                "requester_member_global_id": str(value.requester_member_global_id),
                "requester_user_id": value.requester_user_id,
                "requested_at": _database_datetime(value.requested_at),
                "expires_at": _database_datetime(value.expires_at),
                "closure_action_global_id": str(value.closure_action_global_id),
                "closure_action_version": value.closure_action_ref.version,
                "closure_action_snapshot_hash": (
                    value.closure_action_ref.snapshot_hash
                ),
                "state": value.state.value,
                "approver_authority_slot": value.approval_authority_slot,
                "approver_member_global_id": str(value.approval_member_global_id),
                "approver_user_id": value.approval_user_id,
                "optimistic_version": value.version,
            }
        ).insert()

    @staticmethod
    def _update_exception(document, value: ReviewException) -> None:
        document.state = value.state.value
        document.approval_opinion = value.decision_opinion
        document.decided_at = _database_datetime(value.decided_at)
        document.optimistic_version = value.version
        document.save()

    def _insert_decision(self, value: DecisionSnapshot):
        return frappe.get_doc(
            {
                "doctype": "NPI Gate Decision Snapshot",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "gate_global_id": str(value.gate_global_id),
                "cycle_global_id": str(value.cycle_global_id),
                "cycle_number": value.cycle_number,
                "outcome": value.outcome.value,
                "actor_user_id": value.actor_user_id,
                "occurred_at": _database_datetime(value.occurred_at),
                "policy_global_id": str(value.policy_global_id),
                "policy_version": value.policy_version,
                "policy_snapshot_hash": value.policy_hash,
                "input_snapshot": value.input_snapshot.canonical_dict(),
                "input_hash": value.input_hash,
                "review_hashes": list(value.review_hashes),
                "exception_hashes": list(value.exception_hashes),
                "cycle_version": value.cycle_version,
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    def _insert_exception_decision_event(
        self, cycle: ReviewCycle, value: ReviewException, *, now: datetime
    ):
        exception_document = frappe.get_doc(
            "NPI Gate Review Exception", str(value.global_id)
        )
        event_id = uuid5(value.global_id, f"exception-decision:{value.version}")
        payload = {
            "schemaVersion": 1,
            "globalId": str(event_id),
            "eventKey": (
                f"{value.cycle_global_id}:exception_decided:{value.global_id}"
            ),
            "tenantId": value.tenant_id,
            "projectGlobalId": str(value.project_global_id),
            "gateGlobalId": str(value.gate_global_id),
            "cycleGlobalId": str(value.cycle_global_id),
            "successorCycleGlobalId": None,
            "actionGlobalId": None,
            "eventType": "exception_decided",
            "actorUserId": self.actor,
            "occurredAt": _datetime_canonical(now),
            "requestId": self.request_id,
            "traceId": self.trace_id,
            "detail": {
                "exceptionGlobalId": str(value.global_id),
                "state": value.state.value,
                "decisionSnapshotHash": str(exception_document.decision_snapshot_hash),
            },
        }
        return frappe.get_doc(
            {
                "doctype": "NPI Gate Review Event",
                "global_id": str(event_id),
                "event_key": payload["eventKey"],
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "gate_global_id": str(value.gate_global_id),
                "cycle_global_id": str(value.cycle_global_id),
                "event_type": "exception_decided",
                "actor_user_id": self.actor,
                "occurred_at": _database_datetime(now),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
                "payload": payload,
                "payload_hash": canonical_json_hash(payload),
            }
        ).insert()

    def _persist_transition(
        self,
        project,
        gate,
        prior_document,
        transition: ReviewTransition,
        *,
        review_state: str,
        reason: str,
        occurred_at: datetime,
        initiated_by_user_id: str | None = None,
    ):
        self._update_cycle(prior_document, transition.prior_cycle)
        successor = self._insert_cycle(
            transition.current_cycle,
            started_by=self.actor,
            started_at=occurred_at,
        )
        self._insert_transition_event(
            transition,
            tenant_id=str(project.tenant_id),
            reason=reason,
            occurred_at=occurred_at,
            initiated_by_user_id=initiated_by_user_id,
        )
        self._set_gate_cycle(
            gate,
            successor,
            policy=transition.current_cycle.policy,
            review_state=review_state,
        )
        return successor

    def _insert_transition_event(
        self,
        transition: ReviewTransition,
        *,
        tenant_id: str,
        reason: str,
        occurred_at: datetime,
        initiated_by_user_id: str | None,
    ):
        event = transition.event
        event_type = event.kind.value
        detail = (
            {
                "reason": reason,
                "priorDecisionSnapshotGlobalId": str(
                    event.prior_decision_snapshot_global_id
                ),
                "priorDecisionHash": event.prior_decision_hash,
            }
            if event_type == "reopened"
            else {
                "reason": reason,
                "oldInputHash": event.old_input_hash,
                "newInputHash": event.new_input_hash,
                "priorDecisionSnapshotGlobalId": (
                    str(event.prior_decision_snapshot_global_id)
                    if event.prior_decision_snapshot_global_id is not None
                    else None
                ),
                "priorDecisionHash": event.prior_decision_hash,
                "initiatedByUserId": initiated_by_user_id,
            }
        )
        event_key = (
            f"{event.old_cycle_global_id}:{event_type}:{event.new_cycle_global_id}"
        )
        payload = {
            "schemaVersion": 1 if event_type == "reopened" else 2,
            "globalId": str(event.global_id),
            "eventKey": event_key,
            "tenantId": tenant_id,
            "projectGlobalId": str(event.project_global_id),
            "gateGlobalId": str(event.gate_global_id),
            "cycleGlobalId": str(event.old_cycle_global_id),
            "successorCycleGlobalId": str(event.new_cycle_global_id),
            "actionGlobalId": None,
            "eventType": event_type,
            "actorUserId": event.actor_user_id,
            "occurredAt": _datetime_canonical(occurred_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
            "detail": detail,
        }
        return frappe.get_doc(
            {
                "doctype": "NPI Gate Review Event",
                "global_id": str(event.global_id),
                "event_key": event_key,
                "tenant_id": tenant_id,
                "project_global_id": str(event.project_global_id),
                "gate_global_id": str(event.gate_global_id),
                "cycle_global_id": str(event.old_cycle_global_id),
                "successor_cycle_global_id": str(event.new_cycle_global_id),
                "action_global_id": None,
                "event_type": event_type,
                "actor_user_id": event.actor_user_id,
                "occurred_at": _database_datetime(occurred_at),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
                "payload": payload,
                "payload_hash": canonical_json_hash(payload),
            }
        ).insert()

    @staticmethod
    def _set_gate_cycle(gate, cycle_document, *, policy, review_state: str):
        gate.review_state = review_state
        gate.current_review_cycle = str(cycle_document.global_id)
        gate.current_review_cycle_global_id = str(cycle_document.global_id)
        gate.review_policy_global_id = str(policy.policy_global_id)
        gate.review_policy_version = policy.policy_version
        gate.review_policy_snapshot_hash = policy.snapshot_hash
        gate.optimistic_version = int(gate.optimistic_version) + 1
        gate.save()

    @staticmethod
    def _set_gate_decision(gate, cycle_document, decision_document):
        gate.review_state = "decided"
        gate.current_review_cycle = str(cycle_document.global_id)
        gate.current_review_cycle_global_id = str(cycle_document.global_id)
        gate.latest_decision_snapshot = str(decision_document.global_id)
        gate.latest_decision_snapshot_global_id = str(decision_document.global_id)
        gate.latest_decision_snapshot_hash = str(decision_document.snapshot_hash)
        gate.latest_decision_outcome = str(decision_document.outcome)
        gate.optimistic_version = int(gate.optimistic_version) + 1
        gate.save()

    def _idempotency_replay(
        self,
        actor_key_hash: str,
        payload_hash: str,
        project,
        gate,
        operation: str,
    ) -> dict[str, Any] | None:
        record = frappe.db.get_value(
            "NPI Gate Review Idempotency",
            {"actor_key_hash": actor_key_hash},
            [
                "actor",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "operation",
                "payload_hash",
                "response_json",
                "response_sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not record:
            return None
        if (
            str(record.actor) != self.actor
            or str(record.tenant_id) != str(project.tenant_id)
            or str(record.project_global_id) != str(project.global_id)
            or str(record.gate_global_id) != str(gate.global_id)
            or str(record.operation) != operation
            or str(record.payload_hash) != payload_hash
        ):
            raise IdempotencyConflict()
        if int(record.response_sealed or 0) != 1:
            raise RuntimeError("Persisted Gate review idempotency is unsealed.")
        return _json_object(record.response_json)

    def _insert_idempotency(
        self,
        actor_key_hash: str,
        payload_hash: str,
        project,
        gate,
        operation: str,
    ):
        # Project→Gate locks serialize actor-key insert races; no rollback path
        # may destroy the outer transaction.
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Gate Review Idempotency",
                    "record_id": str(uuid4()),
                    "actor": self.actor,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "gate_global_id": str(gate.global_id),
                    "operation": operation,
                    "actor_key_hash": actor_key_hash,
                    "payload_hash": payload_hash,
                    "response_json": {},
                    "response_sealed": 0,
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError) as error:
            # Same-Project commands serialize on the Project row. A collision
            # here is therefore a cross-root reuse of the actor-scoped key,
            # which must fail closed without rolling back an outer transaction.
            raise IdempotencyConflict() from error

    @staticmethod
    def _seal_idempotency(document, response: Mapping[str, object]) -> None:
        document.response_json = dict(response)
        document.response_sealed = 1
        document.save()

    def _audit(
        self,
        operation: str,
        global_id: UUID,
        version: int,
        summary: Mapping[str, object],
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=version,
            result="updated",
            input_summary={
                **dict(summary),
                "requestId": self.request_id,
            },
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

    def _locked_project_gate(
        self, project_id: UUID, gate_id: UUID
    ) -> tuple[Any, Any] | None:
        try:
            project = frappe.get_doc(
                "NPI Engineering Project", str(project_id), for_update=True
            )
        except frappe.DoesNotExistError:
            return None
        if not self._tenant_matches(project):
            return None
        if (
            not self._is_internal_system_manager()
            and not self._dependency_system
            and self._current_actor_member(project) is None
        ):
            return None
        try:
            gate = frappe.get_doc("NPI Gate Shell", str(gate_id), for_update=True)
        except frappe.DoesNotExistError:
            return None
        if not _gate_matches(project, gate, gate_id):
            return None
        return project, gate

    def _locked_review_scope(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID | None = None,
        *,
        exception_id: UUID | None = None,
    ):
        locked = self._locked_project_gate(project_id, gate_id)
        if locked is None:
            return None
        project, gate = locked
        selected_cycle_id = cycle_id or (
            UUID(str(gate.current_review_cycle_global_id))
            if gate.current_review_cycle_global_id
            else None
        )
        if selected_cycle_id is None or str(gate.current_review_cycle_global_id) != str(
            selected_cycle_id
        ):
            return None
        try:
            cycle = frappe.get_doc(
                "NPI Gate Review Cycle",
                str(selected_cycle_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        if not _cycle_matches(project, gate, cycle, selected_cycle_id):
            return None
        if exception_id is None:
            return project, gate, cycle
        try:
            exception = frappe.get_doc(
                "NPI Gate Review Exception",
                str(exception_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        if not _history_matches_cycle(exception, cycle) or str(
            exception.global_id
        ) != str(exception_id):
            return None
        return project, gate, cycle, exception

    def _locked_current_cycle(self, project, gate):
        if not gate.current_review_cycle_global_id:
            return None
        try:
            document = frappe.get_doc(
                "NPI Gate Review Cycle",
                str(gate.current_review_cycle_global_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        return (
            document
            if _cycle_matches(
                project,
                gate,
                document,
                UUID(str(gate.current_review_cycle_global_id)),
            )
            else None
        )

    def _current_cycle_document(self, project, gate):
        if not gate.current_review_cycle_global_id:
            return None
        document = _optional_doc(
            "NPI Gate Review Cycle",
            str(gate.current_review_cycle_global_id),
        )
        return (
            document
            if document is not None
            and _cycle_matches(
                project,
                gate,
                document,
                UUID(str(gate.current_review_cycle_global_id)),
            )
            else None
        )

    def _can_view_project(self, project, project_id: UUID) -> bool:
        if not self._tenant_matches(project) or self.principal.is_external:
            return False
        return bool(
            self._is_internal_system_manager()
            or str(project.owner_user_id).casefold() == self.actor.casefold()
            or str(project_id) in self.principal.project_access
            or self._current_actor_member(project) is not None
        )

    def _tenant_matches(self, project) -> bool:
        return bool(
            not self.principal.is_external
            and self.principal.tenant_id
            and self.principal.tenant_id == str(project.tenant_id)
        )

    def _is_internal_system_manager(self) -> bool:
        return bool(
            not self.principal.is_external and "System Manager" in self.principal.roles
        )

    def _has_command_transport_role(self) -> bool:
        return bool(
            not self.principal.is_external and "NPI API User" in self.principal.roles
        )

    def _current_members(self, project, *, maximum: int) -> tuple[Any, ...]:
        documents = _bounded_documents(
            "NPI Project Member",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            order_by="global_id asc",
            maximum=maximum,
        )
        today = datetime.now(UTC).date()
        result = []
        for member in documents:
            if not _member_effective(member, today):
                continue
            user = frappe.db.get_value(
                "User",
                str(member.user_id),
                ["enabled", "user_type"],
                as_dict=True,
            )
            if (
                user
                and int(user.enabled or 0) == 1
                and str(user.user_type) == "System User"
            ):
                result.append(member)
        return tuple(result)

    def _current_actor_member(self, project):
        matches = [
            value
            for value in self._current_members(project, maximum=_MAX_MEMBERS)
            if str(value.user_id) == self.actor
        ]
        return matches[0] if len(matches) == 1 else None

    def _require_current_actor_member(self, project):
        member = self._current_actor_member(project)
        if member is None:
            raise PermissionDenied()
        return member

    def _resolve_bindings(
        self,
        project,
        values: Sequence[Mapping[str, object]],
        *,
        now: datetime,
    ) -> tuple[AuthorityBinding, ...]:
        result = []
        for value in values:
            member = _optional_doc("NPI Project Member", str(value["member_global_id"]))
            if member is None:
                raise _field_problem(
                    "bindings", _("Select current members from this Project.")
                )
            result.append(
                self._binding_from_member(project, str(value["slot"]), member, now=now)
            )
        return tuple(result)

    def _resolve_frozen_binding(
        self, project, binding: AuthorityBinding, *, now: datetime
    ) -> AuthorityBinding:
        member = _optional_doc("NPI Project Member", str(binding.member_global_id))
        if member is None:
            raise PermissionDenied()
        current = self._binding_from_member(project, binding.slot, member, now=now)
        if current.member_global_id != binding.member_global_id or (
            current.user_id != binding.user_id
        ):
            raise PermissionDenied()
        return current

    def _binding_from_member(self, project, slot: str, member, *, now: datetime):
        if (
            str(member.tenant_id) != str(project.tenant_id)
            or str(member.project_global_id) != str(project.global_id)
            or not _member_effective(member, now.date())
        ):
            raise PermissionDenied()
        user = frappe.db.get_value(
            "User",
            str(member.user_id),
            ["enabled", "user_type", "full_name"],
            as_dict=True,
        )
        if (
            not user
            or int(user.enabled or 0) != 1
            or str(user.user_type) != "System User"
        ):
            raise PermissionDenied()
        return AuthorityBinding(
            slot=slot,
            member_global_id=UUID(str(member.global_id)),
            user_id=str(member.user_id),
            display_name=(
                str(user.full_name).strip()
                if user.full_name and str(user.full_name).strip()
                else str(member.user_id)
            ),
        )

    def _require_current_binding_actor(
        self, project, cycle: ReviewCycle, slot: str
    ) -> None:
        try:
            binding = next(
                value
                for value in cycle.bindings
                if value.slot.casefold() == slot.casefold()
            )
        except StopIteration as error:
            raise PermissionDenied() from error
        if binding.user_id != self.actor:
            raise PermissionDenied()
        current = self._require_current_actor_member(project)
        if UUID(str(current.global_id)) != binding.member_global_id:
            raise PermissionDenied()

    @staticmethod
    def _require_gate_version(gate, expected: int) -> None:
        if type(expected) is not int or int(gate.optimistic_version) != expected:
            raise VersionConflict()

    @staticmethod
    def _require_in_review_state(gate) -> None:
        if str(gate.review_state or "not_started") != "in_review":
            raise VersionConflict()

    def _require_closure_action(
        self,
        project,
        gate,
        identity: UUID,
        *,
        lock: bool,
    ):
        document = self._closure_action_document(identity, lock=lock)
        if not _closure_action_matches_scope(document, project, gate):
            raise _field_problem(
                "closureActionGlobalId",
                _("Select a current same-Gate closure action."),
            )
        return document

    def _review_documents_from_document(self, cycle_document):
        return _bounded_documents(
            "NPI Gate Review Record",
            {
                "tenant_id": str(cycle_document.tenant_id),
                "project_global_id": str(cycle_document.project_global_id),
                "gate_global_id": str(cycle_document.gate_global_id),
                "cycle_global_id": str(cycle_document.global_id),
            },
            order_by="review_step_sequence asc, occurred_at asc, global_id asc",
            maximum=32,
        )

    def _exception_documents_from_document(
        self, cycle_document, *, lock: bool, locked_exception=None
    ):
        names = frappe.get_all(
            "NPI Gate Review Exception",
            filters={
                "tenant_id": str(cycle_document.tenant_id),
                "project_global_id": str(cycle_document.project_global_id),
                "gate_global_id": str(cycle_document.gate_global_id),
                "cycle_global_id": str(cycle_document.global_id),
            },
            pluck="name",
            order_by="requested_at asc, global_id asc",
            limit_page_length=_MAX_EXCEPTIONS + 1,
        )
        if len(names) > _MAX_EXCEPTIONS:
            raise ValueError("Gate review exception collection is too large.")
        existing = (
            {str(locked_exception.name): locked_exception}
            if locked_exception is not None
            else {}
        )
        return tuple(
            existing.get(str(name))
            or frappe.get_doc("NPI Gate Review Exception", name, for_update=lock)
            for name in names
        )

    def _decision_documents(self, project, gate):
        return _bounded_documents(
            "NPI Gate Decision Snapshot",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "gate_global_id": str(gate.global_id),
            },
            order_by="cycle_number asc, global_id asc",
            maximum=_MAX_CYCLES,
        )

    def _decision_response(self, project, gate, document, *, current: bool):
        cycle_document = _optional_doc(
            "NPI Gate Review Cycle",
            str(document.cycle_global_id),
        )
        if cycle_document is None or not _cycle_matches(
            project,
            gate,
            cycle_document,
            UUID(str(document.cycle_global_id)),
        ):
            raise ValueError("Persisted Gate decision cycle is unavailable.")
        cycle = self._hydrate_cycle(cycle_document, lock_exceptions=False)
        decision = cycle.decision
        if decision is None or str(decision.global_id) != str(document.global_id):
            raise ValueError("Persisted Gate decision domain lineage is unavailable.")
        persisted_snapshot = _json_object(document.decision_snapshot)
        expected_snapshot = {
            "schemaVersion": 1,
            "globalId": str(decision.global_id),
            "tenantId": decision.tenant_id,
            "projectGlobalId": str(decision.project_global_id),
            "gateGlobalId": str(decision.gate_global_id),
            "cycleGlobalId": str(decision.cycle_global_id),
            "cycleNumber": decision.cycle_number,
            "outcome": decision.outcome.value,
            "actorUserId": decision.actor_user_id,
            "occurredAt": _datetime_canonical(decision.occurred_at),
            "policyRef": _policy_ref(cycle.policy),
            "inputSnapshot": decision.input_snapshot.canonical_dict(),
            "inputHash": decision.input_hash,
            "reviewHashes": list(decision.review_hashes),
            "exceptionHashes": list(decision.exception_hashes),
            "cycleVersion": decision.cycle_version,
            "requestId": str(document.request_id),
            "traceId": str(document.trace_id),
        }
        if (
            persisted_snapshot != expected_snapshot
            or str(document.outcome) != decision.outcome.value
            or int(document.cycle_number) != decision.cycle_number
            or str(document.input_hash) != decision.input_hash
            or _json_object(document.input_snapshot)
            != decision.input_snapshot.canonical_dict()
            or tuple(_json_array(document.review_hashes)) != decision.review_hashes
            or tuple(_json_array(document.exception_hashes))
            != decision.exception_hashes
            or int(document.cycle_version) != decision.cycle_version
            or str(document.policy_global_id) != str(decision.policy_global_id)
            or int(document.policy_version) != decision.policy_version
            or str(document.policy_snapshot_hash) != decision.policy_hash
            or str(document.actor_user_id) != decision.actor_user_id
            or _datetime_value(document.occurred_at) != decision.occurred_at
        ):
            raise ValueError("Persisted Gate decision summary drifted.")
        _verify_json_hash(persisted_snapshot, str(document.snapshot_hash))
        return {
            "globalId": str(decision.global_id),
            "cycleGlobalId": str(decision.cycle_global_id),
            "outcome": decision.outcome.value,
            "inputHash": decision.input_hash,
            "snapshotHash": str(document.snapshot_hash),
            "decidedAt": _datetime_iso(decision.occurred_at),
            "decidedBy": decision.actor_user_id,
            "current": bool(current),
            "detail": {
                "lineageHash": decision.snapshot_hash,
                "cycleNumber": decision.cycle_number,
                "policyRef": _policy_ref(cycle.policy),
                "inputSnapshot": decision.input_snapshot.canonical_dict(),
                "reviewHashes": list(decision.review_hashes),
                "exceptionHashes": list(decision.exception_hashes),
                "cycleVersion": decision.cycle_version,
            },
        }

    def _blocker_documents(self, project, gate):
        return _bounded_documents(
            "NPI Domain Work Item",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "stage_global_id": str(gate.global_id),
                "blocking": 1,
                "state_terminal": 0,
            },
            order_by="due_at asc, global_id asc",
            maximum=_MAX_BLOCKERS,
        )

    def _closure_action_documents(self, project, gate):
        return _bounded_documents(
            "NPI Domain Work Item",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "stage_global_id": str(gate.global_id),
                "kind": "action",
                "state_terminal": 0,
            },
            order_by="due_at asc, global_id asc",
            maximum=_MAX_CLOSURE_ACTIONS,
        )

    def _current_closure_action_references(
        self,
        project,
        gate,
        cycle: ReviewCycle,
        *,
        lock: bool,
    ) -> dict[UUID, ClosureActionReference]:
        action_documents: dict[UUID, Any] = {}
        action_ids = sorted(
            {exception.closure_action_ref.global_id for exception in cycle.exceptions},
            key=str,
        )
        for action_id in action_ids:
            document = self._closure_action_document(action_id, lock=lock)
            if _closure_action_matches_scope(document, project, gate):
                action_documents[action_id] = document
        result: dict[UUID, ClosureActionReference] = {}
        for exception in cycle.exceptions:
            document = action_documents.get(exception.closure_action_ref.global_id)
            if document is not None:
                result[exception.global_id] = _closure_action_reference(document)
        return result

    @staticmethod
    def _closure_action_document(identity: UUID, *, lock: bool):
        try:
            return frappe.get_doc(
                "NPI Domain Work Item",
                str(identity),
                for_update=lock,
            )
        except frappe.DoesNotExistError:
            return None

    def _closure_action_reference_is_current(
        self,
        project,
        gate,
        expected: ClosureActionReference,
        *,
        lock: bool,
    ) -> bool:
        document = self._closure_action_document(
            expected.global_id,
            lock=lock,
        )
        return bool(
            _closure_action_matches_scope(document, project, gate)
            and _closure_action_reference(document) == expected
        )


def _input_snapshot_from_payload(payload: Mapping[str, object]) -> GateInputSnapshot:
    if set(payload) != {
        "schemaVersion",
        "gateGlobalId",
        "projectGlobalId",
        "tenantId",
        "gateVersion",
        "requirements",
        "evidence",
        "blockers",
        "dependencies",
    }:
        raise ValueError("Persisted Gate input snapshot is not closed.")
    requirements = _payload_list(payload, "requirements")
    evidence = _payload_list(payload, "evidence")
    blockers = _payload_list(payload, "blockers")
    dependencies = _payload_list(payload, "dependencies")
    value = GateInputSnapshot(
        gate_global_id=UUID(str(payload["gateGlobalId"])),
        project_global_id=UUID(str(payload["projectGlobalId"])),
        tenant_id=str(payload["tenantId"]),
        gate_version=int(payload["gateVersion"]),
        requirements=tuple(
            GateRequirementInput(
                global_id=UUID(str(item["globalId"])),
                requirement_key=str(item["requirementKey"]),
                priority=str(item["priority"]),
                source_version=int(item["sourceVersion"]),
                source_hash=str(item["sourceHash"]),
                evidence_complete=bool(item["evidenceComplete"]),
            )
            for item in requirements
        ),
        evidence=tuple(
            GateEvidenceInput(
                global_id=UUID(str(item["globalId"])),
                requirement_global_id=UUID(str(item["requirementGlobalId"])),
                evidence_kind=str(item["evidenceKind"]),
                source_global_id=UUID(str(item["sourceGlobalId"])),
                source_version=int(item["sourceVersion"]),
                source_hash=str(item["sourceHash"]),
                is_file=bool(item["isFile"]),
                file_safe=bool(item["fileSafe"]),
            )
            for item in evidence
        ),
        blockers=tuple(
            GateBlockerInput(
                global_id=UUID(str(item["globalId"])),
                version=int(item["version"]),
                state=str(item["state"]),
                blocking=bool(item["blocking"]),
                terminal=bool(item["terminal"]),
            )
            for item in blockers
        ),
        dependencies=tuple(
            GateDependencyInput(
                kind=DependencyEvaluator(str(item["kind"])),
                global_id=UUID(str(item["globalId"])),
                version=int(item["version"]),
                snapshot_hash=str(item["snapshotHash"]),
            )
            for item in dependencies
        ),
        schema_version=int(payload["schemaVersion"]),
    )
    if value.canonical_dict() != dict(payload):
        raise ValueError("Persisted Gate input snapshot is not canonical.")
    return value


def _payload_list(payload: Mapping[str, object], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("Persisted Gate input collection is invalid.")
    return value


def _gate_matches(project, gate, gate_id: UUID) -> bool:
    return bool(
        gate is not None
        and str(gate.global_id) == str(gate_id)
        and str(gate.project_global_id) == str(project.global_id)
        and str(gate.engineering_project) == str(project.global_id)
    )


def _cycle_matches(project, gate, cycle, cycle_id: UUID) -> bool:
    return bool(
        str(cycle.global_id) == str(cycle_id)
        and str(cycle.tenant_id) == str(project.tenant_id)
        and str(cycle.project_global_id) == str(project.global_id)
        and str(cycle.gate_global_id) == str(gate.global_id)
        and str(cycle.gate_shell) == str(gate.global_id)
    )


def _history_matches_cycle(document, cycle) -> bool:
    return bool(
        str(document.tenant_id) == str(cycle.tenant_id)
        and str(document.project_global_id) == str(cycle.project_global_id)
        and str(document.gate_global_id) == str(cycle.gate_global_id)
        and str(document.cycle_global_id) == str(cycle.global_id)
    )


def _policy_matches_gate(policy, gate) -> bool:
    return bool(
        policy.gate_template_global_id == UUID(str(gate.gate_template_global_id))
        and policy.gate_template_version == int(gate.gate_template_version)
        and policy.gate_template_hash == str(gate.gate_template_snapshot_hash)
    )


def _source_matches_project(source, project) -> bool:
    return bool(
        str(source.tenant_id) == str(project.tenant_id)
        and str(source.project_global_id) == str(project.global_id)
    )


def _exception_closure_action_reference(
    document,
    request_snapshot: Mapping[str, object],
) -> ClosureActionReference:
    """Read immutable v1/v2 requests without inventing historical revisions."""

    schema_version = request_snapshot.get("schemaVersion")
    if type(schema_version) is not int or schema_version not in {1, 2}:
        raise ValueError("Persisted Gate exception request schema is unsupported.")
    has_legacy_identity = "closureActionGlobalId" in request_snapshot
    has_exact_reference = "closureActionRef" in request_snapshot
    if has_legacy_identity == has_exact_reference or (
        schema_version == 2 and has_legacy_identity
    ):
        raise ValueError("Persisted Gate exception closure reference is invalid.")

    global_id = UUID(str(document.closure_action_global_id))
    version_value = _document_value(document, "closure_action_version")
    hash_value = _document_value(document, "closure_action_snapshot_hash")
    if has_legacy_identity:
        if version_value not in (None, "") or hash_value not in (None, ""):
            raise ValueError(
                "Persisted legacy Gate exception closure reference drifted."
            )
        closure_reference: dict[str, object] | str = str(global_id)
        result = ClosureActionReference(global_id, None, None)
    else:
        if version_value in (None, "") or hash_value in (None, ""):
            raise ValueError(
                "Persisted Gate exception closure reference is incomplete."
            )
        result = ClosureActionReference(
            global_id,
            int(version_value),
            _strict_sha256(hash_value, "closure action snapshot hash"),
        )
        closure_reference = result.canonical_dict()

    expected: dict[str, object] = {
        "schemaVersion": schema_version,
        "globalId": str(UUID(str(document.global_id))),
        "exceptionKey": str(document.exception_key),
        "tenantId": str(document.tenant_id),
        "projectGlobalId": str(UUID(str(document.project_global_id))),
        "gateGlobalId": str(UUID(str(document.gate_global_id))),
        "cycleGlobalId": str(UUID(str(document.cycle_global_id))),
        "policyRef": {
            "globalId": str(UUID(str(document.policy_global_id))),
            "version": int(document.policy_version),
            "snapshotHash": _strict_sha256(
                document.policy_snapshot_hash,
                "exception policy snapshot hash",
            ),
        },
        "requirementRef": {
            "globalId": str(UUID(str(document.requirement_global_id))),
            "key": str(document.requirement_key),
        },
        "kind": str(document.exception_kind),
        "reason": str(document.reason),
        "risk": str(document.risk),
        "requester": {
            "memberGlobalId": str(UUID(str(document.requester_member_global_id))),
            "userId": str(document.requester_user_id),
        },
        "requestedAt": _datetime_canonical(document.requested_at),
        "expiresAt": _datetime_canonical(document.expires_at),
        "approver": {
            "authoritySlot": str(document.approver_authority_slot),
            "memberGlobalId": str(UUID(str(document.approver_member_global_id))),
            "userId": str(document.approver_user_id),
        },
    }
    if has_legacy_identity:
        expected["closureActionGlobalId"] = closure_reference
    else:
        expected["closureActionRef"] = closure_reference
    if dict(request_snapshot) != expected:
        raise ValueError("Persisted Gate exception request snapshot drifted.")
    return result


def _closure_action_matches_scope(document, project, gate) -> bool:
    return bool(
        document is not None
        and str(document.tenant_id) == str(project.tenant_id)
        and str(document.project_global_id) == str(project.global_id)
        and str(document.stage_global_id) == str(gate.global_id)
        and str(document.kind) == "action"
        and str(document.source_system) == "NPI_ONE"
        and not bool(document.state_terminal)
    )


def _closure_action_reference(document) -> ClosureActionReference:
    snapshot = {
        "globalId": str(UUID(str(document.global_id))),
        "tenantId": str(document.tenant_id),
        "projectGlobalId": str(UUID(str(document.project_global_id))),
        "stageGlobalId": str(UUID(str(document.stage_global_id))),
        "kind": str(document.kind),
        "title": str(document.title),
        "detail": str(document.detail or ""),
        "wbsItemGlobalId": (
            str(UUID(str(document.wbs_item_global_id)))
            if document.wbs_item_global_id
            else None
        ),
        "ownerUserId": str(document.owner_user_id),
        "dueAt": _datetime_canonical(document.due_at),
        "severity": str(document.severity),
        "blocking": bool(document.blocking),
        "stateKey": str(document.state_key),
        "stateLabelSource": str(document.state_label_source),
        "stateTerminal": bool(document.state_terminal),
        "workPolicyRef": {
            "globalId": str(UUID(str(document.work_policy_global_id))),
            "version": int(document.work_policy_version),
            "snapshotHash": _strict_sha256(
                document.work_policy_snapshot_hash,
                "closure action Work Policy snapshot hash",
            ),
        },
        "relations": _json_array(document.relations),
        "evidenceReferences": _json_array(document.evidence_references),
        "sourceSystem": str(document.source_system),
        "optimisticVersion": int(document.optimistic_version),
    }
    return ClosureActionReference(
        global_id=UUID(snapshot["globalId"]),
        version=int(document.optimistic_version),
        snapshot_hash=_canonical_hash(snapshot),
    )


def _member_effective(member, at: date) -> bool:
    start = _date_value(member.effective_from)
    end = _date_value(member.effective_to) if member.effective_to else None
    return start <= at and (end is None or at <= end)


def _member_response(member) -> dict[str, str]:
    return {
        "memberGlobalId": str(UUID(str(member.global_id))),
        "userId": str(member.user_id),
        "displayName": _display_name(str(member.user_id)),
    }


def _binding_member_response(binding: AuthorityBinding) -> dict[str, str]:
    return {
        "memberGlobalId": str(binding.member_global_id),
        "userId": binding.user_id,
        "displayName": binding.display_name,
    }


def _policy_ref(policy) -> dict[str, object]:
    return {
        "globalId": str(policy.policy_global_id),
        "version": policy.policy_version,
        "snapshotHash": policy.snapshot_hash,
    }


def _policy_option(policy) -> dict[str, Any]:
    slots = [
        {"slot": step.authority_slot, "purpose": "review"} for step in policy.steps
    ]
    slots += [
        {"slot": policy.decision_authority_slot, "purpose": "decision"},
        {"slot": policy.reopen_authority_slot, "purpose": "reopen"},
    ]
    slots += [
        {
            "slot": rule.approval_authority_slot,
            "purpose": "exception",
        }
        for rule in policy.exception_rules
    ]
    unique = {(value["slot"], value["purpose"]): value for value in slots}
    return {
        "policyRef": _policy_ref(policy),
        "authoritySlots": [unique[key] for key in sorted(unique)],
        "exceptionRules": [value.canonical_dict() for value in policy.exception_rules],
    }


def _gate_policy_is_available(
    gate, available_policies: Sequence[Mapping[str, object]]
) -> bool:
    if (
        gate.review_policy_global_id in (None, "")
        or gate.review_policy_version in (None, "")
        or gate.review_policy_snapshot_hash in (None, "")
    ):
        return False
    try:
        expected = {
            "globalId": str(UUID(str(gate.review_policy_global_id))),
            "version": int(gate.review_policy_version),
            "snapshotHash": _strict_sha256(
                gate.review_policy_snapshot_hash,
                "Gate Review Policy snapshot hash",
            ),
        }
    except (TypeError, ValueError):
        return False
    return any(value.get("policyRef") == expected for value in available_policies)


def _display_name(user_id: str) -> str:
    value = frappe.db.get_value("User", user_id, "full_name")
    return str(value).strip() if value and str(value).strip() else user_id


def _bounded_documents(
    doctype: str,
    filters: Mapping[str, object],
    *,
    order_by: str,
    maximum: int,
) -> tuple[Any, ...]:
    names = frappe.get_all(
        doctype,
        filters=dict(filters),
        pluck="name",
        order_by=order_by,
        limit_page_length=maximum + 1,
    )
    if len(names) > maximum:
        raise ValueError(f"Persisted {doctype} collection exceeds its safe bound.")
    return tuple(frappe.get_doc(doctype, name) for name in names)


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _verify_json_hash(value: object, expected_hash: str) -> None:
    parsed = json.loads(value) if isinstance(value, str) else value
    if canonical_json_hash(parsed) != expected_hash:
        raise ValueError("Persisted controlled JSON hash integrity failed.")


def _strict_sha256(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Persisted {label} is invalid.")
    text = value
    if (
        len(text) != 64
        or text != text.lower()
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"Persisted {label} is invalid.")
    return text


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise TypeError("Persisted Gate review JSON must be an object.")
    return parsed


def _json_array(value: object) -> list[Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise TypeError("Persisted Gate review JSON must be an array.")
    return parsed


def _payload_hash(value: object) -> str:
    return _canonical_hash(_jsonable(value))


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(nested)
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_jsonable(nested) for nested in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _datetime_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _datetime_iso(value: object) -> str:
    return _datetime_value(value).isoformat().replace("+00:00", "Z")


def _datetime_canonical(value: object) -> str:
    return _datetime_value(value).isoformat()


def _database_datetime(value: object) -> str:
    return (
        _datetime_value(value)
        .replace(tzinfo=None)
        .isoformat(sep=" ", timespec="microseconds")
    )


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _optional_uuid_text(value: object) -> str | None:
    return str(UUID(str(value))) if value not in (None, "") else None


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def queue_gate_review_dependency_evaluation(
    document, method: str | None = None
) -> None:
    """Queue one post-commit Gate-root evaluation for each exact source reference."""
    controlled = (
        document.doctype == "NPI WBS Item"
        and bool(getattr(frappe.flags, "npi_project_work_command_write", False))
    ) or (document.doctype == "NPI File Revision" and has_controlled_file_write())
    if not controlled:
        return
    source_kind = "wbs_item" if document.doctype == "NPI WBS Item" else "file_revision"
    rows = frappe.get_all(
        "NPI Gate Evidence Reference",
        filters={
            "source_object_type": source_kind,
            "source_global_id": str(document.global_id),
        },
        fields=[
            "global_id",
            "tenant_id",
            "project_global_id",
            "gate_global_id",
            "source_object_type",
            "source_global_id",
        ],
        order_by="project_global_id asc, gate_global_id asc, global_id asc",
        limit_page_length=257,
    )
    if len(rows) > 256:
        raise ValueError("Gate dependency fan-out exceeds its safe bound.")
    _queue_gate_review_reference_rows(rows)


def _queue_gate_review_reference_rows(rows: Sequence[Any]) -> None:
    identities = sorted(
        {
            (
                str(row.global_id),
                str(row.tenant_id),
                str(row.project_global_id),
                str(row.gate_global_id),
                str(row.source_object_type),
                str(row.source_global_id),
            )
            for row in rows
        }
    )
    if len(identities) > 256:
        raise ValueError("Gate dependency fan-out exceeds its safe bound.")
    initiator = str(getattr(frappe.session, "user", "") or "").strip() or None
    for (
        reference_id,
        tenant_id,
        project_id,
        gate_id,
        reference_source_kind,
        source_global_id,
    ) in identities:
        frappe.enqueue(
            "npi_core.gate_review.frappe_repository.evaluate_gate_review_dependency",
            queue="short",
            enqueue_after_commit=True,
            reference_id=reference_id,
            tenant_id=tenant_id,
            project_id=project_id,
            gate_id=gate_id,
            source_kind=reference_source_kind,
            source_global_id=source_global_id,
            initiated_by_user_id=initiator,
        )


def queue_gate_review_file_dependency_evaluation(
    document, method: str | None = None
) -> None:
    """Map live Frappe File identity drift to exact Gate evidence references."""
    if str(getattr(document, "doctype", "")) != "File":
        return
    deleting = method == "on_trash"
    previous = None if deleting else document.get_doc_before_save()
    identity_fields = (
        "is_private",
        "is_remote_file",
        "file_url",
        "content_hash",
        "file_size",
        "file_name",
    )
    if (
        not deleting
        and previous is not None
        and all(
            _document_value(previous, field) == _document_value(document, field)
            for field in identity_fields
        )
    ):
        return
    file_id = str(_document_value(document, "name") or "").strip()
    if not file_id:
        return
    revision_names = frappe.get_all(
        "NPI File Revision",
        filters={"frappe_file_id": file_id},
        pluck="name",
        order_by="global_id asc",
        limit_page_length=257,
    )
    if len(revision_names) > 256:
        raise ValueError("File Revision dependency fan-out exceeds its safe bound.")
    rows: list[Any] = []
    for revision_name in revision_names:
        revision = _optional_doc("NPI File Revision", str(revision_name))
        if revision is None or str(revision.frappe_file_id) != file_id:
            continue
        remaining = 257 - len(rows)
        references = frappe.get_all(
            "NPI Gate Evidence Reference",
            filters={
                "source_object_type": "file_revision",
                "source_global_id": str(revision.global_id),
            },
            fields=[
                "global_id",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "source_object_type",
                "source_global_id",
            ],
            order_by="project_global_id asc, gate_global_id asc, global_id asc",
            limit_page_length=remaining,
        )
        rows.extend(references)
        if len(rows) > 256:
            raise ValueError("Gate dependency fan-out exceeds its safe bound.")
    _queue_gate_review_reference_rows(rows)


def evaluate_gate_review_dependency(
    *,
    reference_id: str,
    tenant_id: str,
    project_id: str,
    gate_id: str,
    source_kind: str,
    source_global_id: str,
    initiated_by_user_id: str | None = None,
) -> bool:
    """Run one post-commit evaluation with Project→Gate→Cycle→Exception locks."""
    if not _exact_dependency_reference(
        reference_id=reference_id,
        tenant_id=tenant_id,
        project_id=project_id,
        gate_id=gate_id,
        source_kind=source_kind,
        source_global_id=source_global_id,
    ):
        return False
    repository = _dependency_system_repository(
        tenant_id=tenant_id,
        request_id=str(
            uuid5(
                UUID(reference_id),
                f"dependency:{source_global_id}:{project_id}:{gate_id}",
            )
        ),
        trace_id=f"gate-review-dependency:{reference_id}:{gate_id}",
    )
    locked = repository._locked_project_gate(UUID(project_id), UUID(gate_id))
    if locked is None:
        return False
    project, gate = locked
    return repository.refresh_gate_for_dependency_change_locked(
        project,
        gate,
        reason="GATE_SOURCE_CHANGED",
        initiated_by_user_id=initiated_by_user_id,
    )


def queue_gate_review_work_item_evaluation(document, method: str | None = None) -> None:
    """Queue the before/after blocker or NPI action Gate union after commit."""
    del method
    if str(getattr(document, "doctype", "")) != "NPI Domain Work Item" or not bool(
        getattr(frappe.flags, "npi_project_work_command_write", False)
    ):
        return
    previous = document.get_doc_before_save()
    identities = tuple(
        identity
        for identity in (
            _gate_review_work_item_identity(previous),
            _gate_review_work_item_identity(document),
        )
        if identity is not None
    )
    gate_roots = sorted(set(identities))
    if len(gate_roots) > 2:
        raise ValueError("Work Item Gate dependency fan-out exceeds its safe bound.")
    initiator = str(getattr(frappe.session, "user", "") or "").strip() or None
    for tenant_id, project_id, gate_id in gate_roots:
        frappe.enqueue(
            "npi_core.gate_review.frappe_repository."
            "evaluate_gate_review_work_item_dependency",
            queue="short",
            enqueue_after_commit=True,
            work_item_id=str(document.global_id),
            tenant_id=tenant_id,
            project_id=project_id,
            gate_id=gate_id,
            observed_version=int(document.optimistic_version),
            initiated_by_user_id=initiator,
        )


def evaluate_gate_review_work_item_dependency(
    *,
    work_item_id: str,
    tenant_id: str,
    project_id: str,
    gate_id: str,
    observed_version: int,
    initiated_by_user_id: str | None = None,
) -> bool:
    """Recompute one exact Gate after any active-blocker membership/version change."""
    try:
        identities = (UUID(work_item_id), UUID(project_id), UUID(gate_id))
    except (TypeError, ValueError, AttributeError):
        return False
    if (
        any(value.int == 0 for value in identities)
        or type(observed_version) is not int
        or observed_version < 1
        or not isinstance(tenant_id, str)
        or not tenant_id.strip()
    ):
        return False
    repository = _dependency_system_repository(
        tenant_id=tenant_id,
        request_id=str(
            uuid5(
                identities[0],
                (f"work-item:{observed_version}:" f"{project_id}:{gate_id}"),
            )
        ),
        trace_id=(
            f"gate-review-work-item:{work_item_id}:" f"{observed_version}:{gate_id}"
        ),
    )
    locked = repository._locked_project_gate(identities[1], identities[2])
    if locked is None:
        return False
    project, gate = locked
    return repository.refresh_gate_for_work_item_dependency_locked(
        project,
        gate,
        work_item_global_id=identities[0],
        reason="GATE_WORK_ITEM_CHANGED",
        initiated_by_user_id=initiated_by_user_id,
    )


def refresh_gate_review_dependency_locked(
    project,
    gate,
    *,
    request_id: str,
    trace_id: str,
    reason: str,
    initiated_by_user_id: str | None,
) -> bool:
    """Refresh one already locked Gate through the private system capability."""
    return _dependency_system_repository(
        tenant_id=str(project.tenant_id),
        request_id=request_id,
        trace_id=trace_id,
    ).refresh_gate_for_dependency_change_locked(
        project,
        gate,
        reason=reason,
        initiated_by_user_id=initiated_by_user_id,
    )


def _dependency_system_repository(
    *,
    tenant_id: str,
    request_id: str,
    trace_id: str,
) -> FrappeGateReviewRepository:
    return FrappeGateReviewRepository(
        principal=Principal(
            user_id=GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR,
            roles=frozenset(),
            project_access={},
            is_external=False,
            tenant_id=tenant_id,
        ),
        request_id=request_id,
        trace_id=trace_id,
        _system_capability=_DEPENDENCY_SYSTEM_CAPABILITY,
    )


def _exact_dependency_reference(
    *,
    reference_id: str,
    tenant_id: str,
    project_id: str,
    gate_id: str,
    source_kind: str,
    source_global_id: str,
) -> bool:
    if source_kind not in {"wbs_item", "file_revision"}:
        return False
    try:
        identities = (
            UUID(reference_id),
            UUID(project_id),
            UUID(gate_id),
            UUID(source_global_id),
        )
    except (TypeError, ValueError, AttributeError):
        return False
    if any(value.int == 0 for value in identities):
        return False
    reference = _optional_doc("NPI Gate Evidence Reference", reference_id)
    return bool(
        reference is not None
        and str(reference.global_id) == reference_id
        and str(reference.tenant_id) == tenant_id
        and str(reference.project_global_id) == project_id
        and str(reference.gate_global_id) == gate_id
        and str(reference.source_object_type) == source_kind
        and str(reference.evidence_kind) == source_kind
        and str(reference.source_global_id) == source_global_id
    )


def _document_value(document, fieldname: str) -> object:
    if document is None:
        return None
    getter = getattr(document, "get", None)
    if callable(getter):
        return getter(fieldname)
    return getattr(document, fieldname, None)


def _gate_review_work_item_identity(
    document,
) -> tuple[str, str, str] | None:
    if (
        document is None
        or str(_document_value(document, "source_system")) != "NPI_ONE"
        or not _document_value(document, "stage_global_id")
        or not (
            (
                bool(_document_value(document, "blocking"))
                and not bool(_document_value(document, "state_terminal"))
            )
            or str(_document_value(document, "kind")) == "action"
        )
    ):
        return None
    try:
        project_id = str(UUID(str(_document_value(document, "project_global_id"))))
        gate_id = str(UUID(str(_document_value(document, "stage_global_id"))))
        work_item_id = UUID(str(_document_value(document, "global_id")))
    except (TypeError, ValueError, AttributeError):
        return None
    tenant_id = str(_document_value(document, "tenant_id") or "").strip()
    if work_item_id.int == 0 or not tenant_id:
        return None
    return tenant_id, project_id, gate_id


@contextmanager
def _controlled_dependency_input_write_scope() -> Iterator[None]:
    missing = object()
    previous = getattr(
        frappe.flags,
        GATE_REVIEW_DEPENDENCY_INPUT_FLAG,
        missing,
    )
    setattr(frappe.flags, GATE_REVIEW_DEPENDENCY_INPUT_FLAG, True)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, GATE_REVIEW_DEPENDENCY_INPUT_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, GATE_REVIEW_DEPENDENCY_INPUT_FLAG, previous)


@contextmanager
def _controlled_review_write_scope() -> Iterator[None]:
    names = (
        GATE_REVIEW_COMMAND_FLAG,
        "npi_project_command_write",
        "npi_project_work_command_write",
        "npi_audit_append",
    )
    missing = object()
    previous = {name: getattr(frappe.flags, name, missing) for name in names}
    for name in names:
        setattr(frappe.flags, name, True)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is missing:
                try:
                    delattr(frappe.flags, name)
                except AttributeError:
                    pass
            else:
                setattr(frappe.flags, name, value)
