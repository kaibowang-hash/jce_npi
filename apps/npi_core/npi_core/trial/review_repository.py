from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.documents.frappe_validation import canonical_json
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.tooling.engineering_controls_domain import (
    ToolingDefectActionState,
    ToolingDefectState,
)
from npi_core.trial.domain import (
    TrialRound,
    TrialRoundState,
    transition_trial_round,
)
from npi_core.trial.execution_domain import (
    TrialLockedReferenceKind,
    TrialMeasurementState,
    TrialParameterValueKind,
)
from npi_core.trial.execution_repository import TrialExecutionCommandOutcome
from npi_core.trial.frappe_repository import (
    _database_datetime,
    _json_object,
    _optional_doc,
    _payload_hash,
    _round_response,
)
from npi_core.trial.frappe_validation import trial_command_write
from npi_core.trial.quality_domain import (
    TrialQualityMeasurementState,
)
from npi_core.trial.quality_repository import FrappeTrialQualityRepository
from npi_core.trial.review_domain import (
    TrialCavityResultTip,
    TrialComparisonCellState,
    TrialComparisonMetricKind,
    TrialConclusionCapability,
    TrialConclusionRevision,
    TrialConclusionRevisionState,
    TrialDefectSourceKind,
    TrialDefectTip,
    TrialExactReference,
    TrialInputComparisonCell,
    TrialInputComparisonRow,
    TrialMetricComparisonCell,
    TrialMetricComparisonRow,
    TrialReviewConflict,
    TrialReviewReferenceRevision,
    TrialReviewUnavailable,
    TrialRoundComparisonSnapshot,
    TrialRoundComparisonSource,
    build_one_page_summary_input,
    comparison_from_snapshot,
    conclusion_from_snapshot,
    derive_conclusion_blockers,
    policy_from_snapshot,
    review_reference_from_snapshot,
    validate_conclusion_policy_successor,
    validate_conclusion_sources,
    validate_conclusion_successor,
    validate_review_reference_successor,
)


_MAX_POLICIES = 1_000
_MAX_COMPARISONS = 5_000
_MAX_REFERENCES = 10_000
_MAX_CONCLUSIONS = 10_000


class FrappeTrialReviewRepository(FrappeTrialQualityRepository):
    """Project-first P7-04 review boundary with exact immutable sources."""

    def review_workspace(self, project_id: UUID, round_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        pair = self._execution_round(project, round_id)
        if pair is None:
            return None
        return self._review_workspace_for(project, pair[1])

    def begin_analysis(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        policy_revision_id: UUID,
        expected_policy_revision_snapshot_hash: str,
        expected_round_optimistic_version: int,
        expected_round_snapshot_hash: str,
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "policyRevisionGlobalId": policy_revision_id,
            "expectedPolicyRevisionSnapshotHash": expected_policy_revision_snapshot_hash,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedRoundSnapshotHash": expected_round_snapshot_hash,
            "reason": reason,
        }
        project, replay, payload_hash = self._review_command_start(
            project_id,
            "trial_round.begin_analysis",
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        document, trial_round, _policy = self._exact_review_context(
            project,
            round_id,
            policy_revision_id,
            expected_policy_revision_snapshot_hash,
            expected_round_optimistic_version,
            expected_round_snapshot_hash,
            TrialConclusionCapability.SUBMIT,
            {TrialRoundState.RUNNING},
        )
        now = datetime.now(UTC)
        successor, event = transition_trial_round(
            trial_round,
            event_global_id=uuid4(),
            to_state=TrialRoundState.ANALYSIS,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        return self._persist_review_command(
            project,
            document,
            successor,
            operation="trial_round.begin_analysis",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_round_lifecycle_event",
            target=event,
            insert=self._insert_round_event,
            lifecycle_event=None,
            now=now,
        )

    def create_comparison(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        policy_revision_id: UUID,
        expected_policy_revision_snapshot_hash: str,
        expected_round_optimistic_version: int,
        expected_round_snapshot_hash: str,
        rounds: Sequence[Mapping[str, Any]],
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "policyRevisionGlobalId": policy_revision_id,
            "expectedPolicyRevisionSnapshotHash": expected_policy_revision_snapshot_hash,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedRoundSnapshotHash": expected_round_snapshot_hash,
            "rounds": rounds,
            "reason": reason,
        }
        project, replay, payload_hash = self._review_command_start(
            project_id,
            "trial_comparison.create",
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        document, target, policy = self._exact_review_context(
            project,
            round_id,
            policy_revision_id,
            expected_policy_revision_snapshot_hash,
            expected_round_optimistic_version,
            expected_round_snapshot_hash,
            TrialConclusionCapability.SUBMIT,
            {TrialRoundState.ANALYSIS},
        )
        if rounds[-1]["global_id"] != round_id:
            raise TrialReviewConflict()
        sources = []
        contexts = []
        for sequence, expected in enumerate(rounds, 1):
            pair = self._execution_round(project, expected["global_id"])
            if pair is None:
                raise TrialReviewUnavailable()
            value = pair[1]
            if any(
                (
                    value.trial_plan_global_id != target.trial_plan_global_id,
                    value.optimistic_version != expected["optimistic_version"],
                    value.snapshot_hash != expected["snapshot_hash"],
                    value.current_state is TrialRoundState.CANCELLED,
                )
            ):
                raise TrialReviewConflict()
            context = self._comparison_source_context(project, value)
            contexts.append(context)
            sources.append(self._comparison_source(sequence, value, context))
        now = datetime.now(UTC)
        comparison = TrialRoundComparisonSnapshot(
            global_id=uuid4(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            trial_plan_global_id=target.trial_plan_global_id,
            target_round_global_id=round_id,
            policy_revision=TrialExactReference(policy.global_id, policy.snapshot_hash),
            sources=tuple(sources),
            input_rows=self._input_rows(tuple(sources), tuple(contexts)),
            metric_rows=self._metric_rows(tuple(sources), tuple(contexts)),
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        return self._persist_review_command(
            project,
            document,
            target,
            operation="trial_comparison.create",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_round_comparison_snapshot",
            target=comparison,
            insert=self._insert_comparison,
            now=now,
        )

    def create_review_reference(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        **values: Any,
    ) -> TrialExecutionCommandOutcome | None:
        operation = (
            "trial_review_reference.revise"
            if values["reference_predecessor"] is not None
            else "trial_review_reference.create"
        )
        payload = {"projectId": project_id, "trialRoundId": round_id, **values}
        project, replay, payload_hash = self._review_command_start(
            project_id,
            operation,
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        document, trial_round, _policy = self._exact_review_context_from_values(
            project,
            round_id,
            values,
            TrialConclusionCapability.SUBMIT,
            {TrialRoundState.ANALYSIS},
        )
        comparison = self._exact_comparison(
            project,
            round_id,
            values["comparison_snapshot_id"],
            values["expected_comparison_snapshot_hash"],
        )
        predecessor = self._reference_predecessor(project, round_id, values["reference_predecessor"])
        self._validate_controlled_reference_sources(project, trial_round, values)
        now = datetime.now(UTC)
        reference = TrialReviewReferenceRevision(
            global_id=uuid4(),
            reference_global_id=(predecessor.reference_global_id if predecessor else uuid4()),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            trial_round_global_id=round_id,
            comparison_snapshot=TrialExactReference(comparison.global_id, comparison.snapshot_hash),
            reference_kind=values["reference_kind"],
            reference_version=(predecessor.reference_version + 1 if predecessor else 1),
            predecessor_global_id=(predecessor.global_id if predecessor else None),
            predecessor_snapshot_hash=(predecessor.snapshot_hash if predecessor else None),
            part_revision=TrialExactReference(**values["part_revision"]),
            tooling_master_global_id=values["tooling_master_id"],
            tooling_revision=TrialExactReference(**values["tooling_revision"]),
            tooling_set=TrialExactReference(**values["tooling_set"]),
            file_revision=TrialExactReference(**values["file_revision"]),
            effective_from=values["effective_from"],
            effective_to=values["effective_to"],
            reason=values["reason"],
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor:
            validate_review_reference_successor(predecessor, reference)
        return self._persist_review_command(
            project,
            document,
            trial_round,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_review_reference_revision",
            target=reference,
            insert=self._insert_review_reference,
            now=now,
        )

    def submit_conclusion(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        **values: Any,
    ) -> TrialExecutionCommandOutcome | None:
        payload = {"projectId": project_id, "trialRoundId": round_id, **values}
        project, replay, payload_hash = self._review_command_start(
            project_id,
            "trial_conclusion.submit",
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        document, trial_round, policy = self._exact_review_context_from_values(
            project,
            round_id,
            values,
            TrialConclusionCapability.SUBMIT,
            {TrialRoundState.ANALYSIS},
        )
        comparison = self._exact_comparison(
            project,
            round_id,
            values["comparison_snapshot_id"],
            values["expected_comparison_snapshot_hash"],
        )
        references = tuple(
            self._exact_reference_revision(project, round_id, item["global_id"], item["snapshot_hash"])
            for item in values["review_references"]
        )
        predecessor = self._conclusion_predecessor(project, round_id, values["conclusion_predecessor"])
        if predecessor and predecessor.state is not TrialConclusionRevisionState.REOPENED:
            raise TrialReviewConflict()
        now = datetime.now(UTC)
        successor_round, event = transition_trial_round(
            trial_round,
            event_global_id=uuid4(),
            to_state=TrialRoundState.SUBMITTED,
            reason=values["reason"],
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        state = TrialConclusionRevisionState.SUBMITTED
        blockers = derive_conclusion_blockers(policy, comparison, references, values["conclusion_code"])
        conclusion = TrialConclusionRevision(
            global_id=uuid4(),
            conclusion_global_id=(predecessor.conclusion_global_id if predecessor else uuid4()),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            trial_round_global_id=round_id,
            trial_round_optimistic_version=successor_round.optimistic_version,
            trial_round_snapshot_hash=successor_round.snapshot_hash,
            conclusion_version=(predecessor.conclusion_version + 1 if predecessor else 1),
            predecessor_global_id=(predecessor.global_id if predecessor else None),
            predecessor_snapshot_hash=(predecessor.snapshot_hash if predecessor else None),
            state=state,
            conclusion_code=values["conclusion_code"],
            policy_revision=TrialExactReference(policy.global_id, policy.snapshot_hash),
            comparison_snapshot=TrialExactReference(comparison.global_id, comparison.snapshot_hash),
            review_references=tuple(TrialExactReference(value.global_id, value.snapshot_hash) for value in references),
            blockers=blockers,
            summary_input=build_one_page_summary_input(comparison, references, values["conclusion_code"], state),
            proposed_next_work=values["proposed_next_work"],
            proposed_gate_effect=values["proposed_gate_effect"],
            proposed_npi_effect=values["proposed_npi_effect"],
            reason=values["reason"],
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor:
            validate_conclusion_successor(predecessor, conclusion)
        validate_conclusion_sources(policy, comparison, references, conclusion)
        return self._persist_review_command(
            project,
            document,
            successor_round,
            operation="trial_conclusion.submit",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_conclusion_revision",
            target=conclusion,
            insert=self._insert_conclusion,
            lifecycle_event=event,
            now=now,
        )

    def decide_conclusion(
        self,
        project_id: UUID,
        round_id: UUID,
        conclusion_id: UUID,
        *,
        idempotency_key_hash: str,
        **values: Any,
    ) -> TrialExecutionCommandOutcome | None:
        return self._transition_conclusion(
            project_id,
            round_id,
            conclusion_id,
            idempotency_key_hash=idempotency_key_hash,
            operation="trial_conclusion.decide",
            capability=TrialConclusionCapability.DECIDE,
            requested_state=values["decision"],
            expected_round_states={TrialRoundState.SUBMITTED},
            values=values,
        )

    def reopen_conclusion(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        **values: Any,
    ) -> TrialExecutionCommandOutcome | None:
        return self._transition_conclusion(
            project_id,
            round_id,
            values["conclusion_id"],
            idempotency_key_hash=idempotency_key_hash,
            operation="trial_conclusion.reopen",
            capability=TrialConclusionCapability.REOPEN,
            requested_state=TrialConclusionRevisionState.REOPENED,
            expected_round_states={
                TrialRoundState.SUBMITTED,
                TrialRoundState.APPROVED,
                TrialRoundState.REJECTED,
            },
            values=values,
        )

    def _transition_conclusion(
        self,
        project_id,
        round_id,
        conclusion_id,
        *,
        idempotency_key_hash,
        operation,
        capability,
        requested_state,
        expected_round_states,
        values,
    ):
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "conclusionGlobalId": conclusion_id,
            **values,
        }
        project, replay, payload_hash = self._review_command_start(
            project_id, operation, idempotency_key_hash, payload
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        document, trial_round, _policy = self._exact_review_context_from_values(
            project,
            round_id,
            values,
            capability,
            expected_round_states,
        )
        predecessor = self._exact_conclusion_revision(
            project,
            round_id,
            values["expected_conclusion_revision_id"],
            values["expected_conclusion_revision_snapshot_hash"],
        )
        if (
            predecessor.conclusion_global_id != conclusion_id
            or predecessor.conclusion_version != values["expected_conclusion_version"]
            or self._conclusion_chain(project, round_id, conclusion_id)[-1] != predecessor
        ):
            raise TrialReviewConflict()
        round_state = {
            TrialConclusionRevisionState.APPROVED: TrialRoundState.APPROVED,
            TrialConclusionRevisionState.REJECTED: TrialRoundState.REJECTED,
            TrialConclusionRevisionState.REOPENED: TrialRoundState.ANALYSIS,
        }[requested_state]
        now = datetime.now(UTC)
        successor_round, event = transition_trial_round(
            trial_round,
            event_global_id=uuid4(),
            to_state=round_state,
            reason=values["reason"],
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        conclusion = TrialConclusionRevision(
            global_id=uuid4(),
            conclusion_global_id=predecessor.conclusion_global_id,
            tenant_id=predecessor.tenant_id,
            project_global_id=predecessor.project_global_id,
            trial_round_global_id=predecessor.trial_round_global_id,
            trial_round_optimistic_version=predecessor.trial_round_optimistic_version,
            trial_round_snapshot_hash=predecessor.trial_round_snapshot_hash,
            conclusion_version=predecessor.conclusion_version + 1,
            predecessor_global_id=predecessor.global_id,
            predecessor_snapshot_hash=predecessor.snapshot_hash,
            state=requested_state,
            conclusion_code=predecessor.conclusion_code,
            policy_revision=predecessor.policy_revision,
            comparison_snapshot=predecessor.comparison_snapshot,
            review_references=predecessor.review_references,
            blockers=predecessor.blockers,
            summary_input={**predecessor.summary_input, "conclusionState": requested_state.value},
            proposed_next_work=predecessor.proposed_next_work,
            proposed_gate_effect=predecessor.proposed_gate_effect,
            proposed_npi_effect=predecessor.proposed_npi_effect,
            reason=values["reason"],
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        validate_conclusion_successor(predecessor, conclusion)
        return self._persist_review_command(
            project,
            document,
            successor_round,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_conclusion_revision",
            target=conclusion,
            insert=self._insert_conclusion,
            lifecycle_event=event,
            now=now,
        )

    def _review_command_start(self, project_id, operation, key_hash, payload):
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None, None, ""
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(project, operation, key_hash, payload_hash)
        if replay is None:
            require_mutable_project(project)
        return project, replay, payload_hash

    def _exact_review_context_from_values(
        self,
        project,
        round_id,
        values,
        capability,
        expected_states,
    ):
        return self._exact_review_context(
            project,
            round_id,
            values["policy_revision_id"],
            values["expected_policy_revision_snapshot_hash"],
            values["expected_round_optimistic_version"],
            values["expected_round_snapshot_hash"],
            capability,
            expected_states,
        )

    def _exact_review_context(
        self,
        project,
        round_id,
        policy_revision_id,
        policy_hash,
        round_version,
        round_hash,
        capability,
        expected_states,
    ):
        pair = self._execution_round(project, round_id, for_update=True)
        if pair is None:
            raise TrialReviewUnavailable()
        document, trial_round = pair
        if any(
            (
                trial_round.optimistic_version != round_version,
                trial_round.snapshot_hash != round_hash,
                trial_round.current_state not in expected_states,
            )
        ):
            raise TrialReviewConflict()
        policy = self._exact_policy(
            project,
            trial_round,
            policy_revision_id,
            policy_hash,
            capability,
        )
        return document, trial_round, policy

    def _exact_policy(self, project, trial_round, revision_id, snapshot_hash, capability):
        document = _optional_doc("NPI Trial Conclusion Policy Version", str(revision_id))
        if document is None:
            raise TrialReviewUnavailable()
        policy = policy_from_snapshot(_json_object(document.policy_snapshot))
        if any(
            (
                policy.global_id != revision_id,
                policy.snapshot_hash != str(document.snapshot_hash),
                policy.snapshot_hash != snapshot_hash,
                policy.tenant_id != str(project.tenant_id),
                policy.project_global_id != UUID(str(project.global_id)),
                policy.trial_plan_global_id != trial_round.trial_plan_global_id,
                policy.trial_plan_revision_global_id
                != trial_round.trial_plan_revision_global_id,
                policy.trial_plan_revision_snapshot_hash
                != trial_round.trial_plan_revision_snapshot_hash,
            )
        ):
            raise TrialReviewConflict()
        bindings = [
            binding
            for binding in policy.authority_bindings
            if binding.member.user_id.casefold() == self.actor.casefold()
            and capability in binding.capabilities
        ]
        if len(bindings) != 1 or not self._is_internal_system_manager():
            raise TrialReviewUnavailable()
        exact_member = self._exact_member(
            project,
            {
                "global_id": bindings[0].member.global_id,
                "user_id": bindings[0].member.user_id,
                "optimistic_version": bindings[0].member.optimistic_version,
            },
        )
        if exact_member != bindings[0].member:
            raise TrialReviewConflict()
        return policy

    def _comparison_source_context(self, project, trial_round):
        input_lock = self._current_input_lock(project, trial_round.global_id, for_update=False)
        actual = self._current_actual(project, trial_round.global_id, for_update=False)
        samples = self._sample_history(project, trial_round.global_id)
        sample_tips = {}
        for value in samples:
            current = sample_tips.get(value.sample_batch_global_id)
            if current is None or current.sample_version < value.sample_version:
                sample_tips[value.sample_batch_global_id] = value
        cavities = self._cavity_result_chain(project, trial_round.global_id)
        cavity_tips = {}
        for value in cavities:
            current = cavity_tips.get(value.cavity_global_id)
            if current is None or current.result_version < value.result_version:
                cavity_tips[value.cavity_global_id] = value
        return {
            "input_lock": input_lock,
            "actual": actual,
            "samples": tuple(sample_tips.values()),
            "cavities": tuple(cavity_tips.values()),
            "defects": self._round_defect_tips(project, trial_round),
        }

    @staticmethod
    def _comparison_source(sequence, trial_round, context):
        return TrialRoundComparisonSource(
            sequence=sequence,
            trial_round_global_id=trial_round.global_id,
            trial_round_optimistic_version=trial_round.optimistic_version,
            trial_round_snapshot_hash=trial_round.snapshot_hash,
            trial_plan_revision=TrialExactReference(
                trial_round.trial_plan_revision_global_id,
                trial_round.trial_plan_revision_snapshot_hash,
            ),
            input_lock_revision=(
                TrialExactReference(context["input_lock"].global_id, context["input_lock"].snapshot_hash)
                if context["input_lock"]
                else None
            ),
            actual_revision=(
                TrialExactReference(context["actual"].global_id, context["actual"].snapshot_hash)
                if context["actual"]
                else None
            ),
            sample_revisions=tuple(
                TrialExactReference(value.global_id, value.snapshot_hash)
                for value in context["samples"]
            ),
            cavity_results=tuple(
                TrialCavityResultTip(
                    value.cavity_global_id,
                    TrialExactReference(value.global_id, value.snapshot_hash),
                )
                for value in context["cavities"]
            ),
            defect_tips=context["defects"],
        )

    def _round_defect_tips(self, project, trial_round):
        tips: dict[UUID, tuple[Any, TrialDefectSourceKind]] = {}
        for value in self._tooling_defect_chain(project, trial_round.tooling_master_global_id):
            current = tips.get(value.defect_global_id)
            if current is None or current[0].defect_version < value.defect_version:
                tips[value.defect_global_id] = (value, TrialDefectSourceKind.TOOLING)
        for value in self._trial_defect_chain(project):
            if value.trial_round_global_id != trial_round.global_id:
                continue
            current = tips.get(value.defect_global_id)
            if current is None or current[0].defect_version < value.defect_version:
                tips[value.defect_global_id] = (value, TrialDefectSourceKind.TRIAL)
        return tuple(
            TrialDefectTip(
                defect_global_id=value.defect_global_id,
                source_kind=source,
                revision=TrialExactReference(value.global_id, value.snapshot_hash),
                state=value.state,
                blocking=value.blocking,
                required_actions_unverified=sum(
                    action.state is not ToolingDefectActionState.VERIFIED
                    for action in value.actions
                ),
            )
            for value, source in tips.values()
        )

    @staticmethod
    def _input_rows(sources, contexts):
        values_by_round = []
        for source, context in zip(sources, contexts, strict=True):
            lock = context["input_lock"]
            values: dict[str, str] = {
                "trial_plan_revision": json.dumps(
                    source.trial_plan_revision.snapshot_payload(),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            }
            if lock:
                material = lock.material.snapshot_payload()
                for key in (
                    "sourceSystem",
                    "sourceObjectId",
                    "lotBatchCode",
                    "label",
                    "color",
                    "additive",
                ):
                    if material.get(key) is not None:
                        values[f"material.{key}"] = str(material[key])
                for reference in lock.references:
                    values[f"reference.{reference.kind.value}"] = json.dumps(
                        reference.snapshot_payload(), sort_keys=True, separators=(",", ":")
                    )
                for definition in lock.parameter_definitions:
                    values[f"parameter.{definition.key}"] = json.dumps(
                        definition.snapshot_payload(), sort_keys=True, separators=(",", ":")
                    )
            values_by_round.append(values)
        keys = sorted({key for values in values_by_round for key in values})
        return tuple(
            TrialInputComparisonRow(
                semantic_key=key,
                cells=tuple(
                    TrialInputComparisonCell(
                        trial_round_global_id=source.trial_round_global_id,
                        canonical_value=values.get(key),
                        source_revision=(
                            source.trial_plan_revision
                            if key == "trial_plan_revision"
                            else source.input_lock_revision
                        )
                        if values.get(key) is not None
                        else None,
                    )
                    for source, values in zip(sources, values_by_round, strict=True)
                ),
            )
            for key in keys
        )

    def _metric_rows(self, sources, contexts):
        definitions = []
        observations = []
        dimensions = []
        for context in contexts:
            lock = context["input_lock"]
            actual = context["actual"]
            definitions.append({value.key: value for value in lock.parameter_definitions} if lock else {})
            observations.append({value.definition_key: value for value in actual.parameters} if actual else {})
            dimension_values = {}
            for cavity in context["cavities"]:
                for measurement in cavity.measurements:
                    dimension_values[(cavity.cavity_global_id, measurement.characteristic_key)] = (
                        cavity,
                        measurement,
                    )
            dimensions.append(dimension_values)

        parameter_keys = sorted(
            {
                key
                for source in definitions
                for key, definition in source.items()
                if definition.value_kind
                in {TrialParameterValueKind.DECIMAL, TrialParameterValueKind.INTEGER}
            }
        )
        rows = [
            TrialMetricComparisonRow(
                metric_kind=TrialComparisonMetricKind.PARAMETER,
                metric_key=key,
                cavity_global_id=None,
                cells=tuple(
                    self._parameter_cell(source, context, definition.get(key), observation.get(key))
                    for source, context, definition, observation in zip(
                        sources, contexts, definitions, observations, strict=True
                    )
                ),
            )
            for key in parameter_keys
        ]
        if not rows:
            rows.append(self._unavailable_metric_row(TrialComparisonMetricKind.PARAMETER, "unavailable", sources))

        dimension_keys = sorted(
            {key for values in dimensions for key in values},
            key=lambda value: (str(value[0]), value[1]),
        )
        rows.extend(
            TrialMetricComparisonRow(
                metric_kind=TrialComparisonMetricKind.DIMENSION,
                metric_key=key,
                cavity_global_id=cavity_id,
                cells=tuple(
                    self._dimension_cell(source, values.get((cavity_id, key)))
                    for source, values in zip(sources, dimensions, strict=True)
                ),
            )
            for cavity_id, key in dimension_keys
        )
        if not dimension_keys:
            rows.append(
                self._unavailable_metric_row(
                    TrialComparisonMetricKind.DIMENSION,
                    "unavailable",
                    sources,
                    cavity_global_id=None,
                )
            )
        for kind, key in (
            (TrialComparisonMetricKind.CYCLE_TIME, "cycle_time"),
            (TrialComparisonMetricKind.YIELD, "yield"),
        ):
            if any(key in values for values in definitions):
                rows.append(
                    TrialMetricComparisonRow(
                        metric_kind=kind,
                        metric_key=key,
                        cavity_global_id=None,
                        cells=tuple(
                            self._parameter_cell(source, context, definition.get(key), observation.get(key))
                            for source, context, definition, observation in zip(
                                sources, contexts, definitions, observations, strict=True
                            )
                        ),
                    )
                )
            else:
                rows.append(self._unavailable_metric_row(kind, key, sources))
        return tuple(rows)

    @staticmethod
    def _parameter_cell(source, context, definition, observation):
        if definition is None or context["actual"] is None:
            return TrialMetricComparisonCell(
                source.trial_round_global_id,
                TrialComparisonCellState.UNAVAILABLE,
                None,
                None,
                None,
                None,
                None,
            )
        reference = TrialExactReference(context["actual"].global_id, context["actual"].snapshot_hash)
        if observation is None or observation.state is TrialMeasurementState.NOT_MEASURED:
            return TrialMetricComparisonCell(
                source.trial_round_global_id,
                TrialComparisonCellState.NOT_MEASURED,
                None,
                definition.unit,
                definition.lower_limit,
                definition.upper_limit,
                reference,
            )
        try:
            Decimal(str(observation.value))
        except (InvalidOperation, TypeError, ValueError):
            return TrialMetricComparisonCell(
                source.trial_round_global_id,
                TrialComparisonCellState.UNAVAILABLE,
                None,
                None,
                None,
                None,
                None,
            )
        return TrialMetricComparisonCell(
            source.trial_round_global_id,
            TrialComparisonCellState.MEASURED,
            str(observation.value),
            observation.unit,
            definition.lower_limit,
            definition.upper_limit,
            reference,
        )

    @staticmethod
    def _dimension_cell(source, value):
        if value is None:
            return TrialMetricComparisonCell(
                source.trial_round_global_id,
                TrialComparisonCellState.UNAVAILABLE,
                None,
                None,
                None,
                None,
                None,
            )
        cavity, measurement = value
        reference = TrialExactReference(cavity.global_id, cavity.snapshot_hash)
        state = (
            TrialComparisonCellState.MEASURED
            if measurement.state is TrialQualityMeasurementState.MEASURED
            else TrialComparisonCellState.NOT_MEASURED
        )
        return TrialMetricComparisonCell(
            source.trial_round_global_id,
            state,
            measurement.value,
            measurement.unit,
            measurement.lower_limit,
            measurement.upper_limit,
            reference,
        )

    @staticmethod
    def _unavailable_metric_row(kind, key, sources, cavity_global_id=None):
        return TrialMetricComparisonRow(
            metric_kind=kind,
            metric_key=key,
            cavity_global_id=cavity_global_id,
            cells=tuple(
                TrialMetricComparisonCell(
                    source.trial_round_global_id,
                    TrialComparisonCellState.UNAVAILABLE,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
                for source in sources
            ),
        )

    def _reference_predecessor(self, project, round_id, expected):
        if expected is None:
            return None
        predecessor = self._exact_reference_revision(
            project,
            round_id,
            expected["revision_id"],
            expected["snapshot_hash"],
        )
        chain = self._reference_chain(project, round_id, expected["stable_id"])
        if (
            predecessor.reference_global_id != expected["stable_id"]
            or predecessor.reference_version != expected["version"]
            or not chain
            or chain[-1] != predecessor
        ):
            raise TrialReviewConflict()
        return predecessor

    def _conclusion_predecessor(self, project, round_id, expected):
        if expected is None:
            if self._conclusion_history(project, round_id):
                raise TrialReviewConflict()
            return None
        predecessor = self._exact_conclusion_revision(
            project,
            round_id,
            expected["revision_id"],
            expected["snapshot_hash"],
        )
        chain = self._conclusion_chain(project, round_id, expected["stable_id"])
        if (
            predecessor.conclusion_global_id != expected["stable_id"]
            or predecessor.conclusion_version != expected["version"]
            or not chain
            or chain[-1] != predecessor
        ):
            raise TrialReviewConflict()
        return predecessor

    def _validate_controlled_reference_sources(self, project, trial_round, values):
        part = self._exact_snapshot_document(
            project,
            "NPI Engineering Part Revision",
            values["part_revision"],
            "originating_project_global_id",
        )
        master = _optional_doc("NPI Tooling Master", str(values["tooling_master_id"]))
        revision = self._exact_snapshot_document(
            project,
            "NPI Tooling Revision",
            values["tooling_revision"],
            "project_global_id",
        )
        tooling_set = self._exact_snapshot_document(
            project,
            "NPI Tooling Set",
            values["tooling_set"],
            "project_global_id",
        )
        file_revision = _optional_doc("NPI File Revision", str(values["file_revision"]["global_id"]))
        if file_revision is not None:
            from npi_core.trial.execution_repository import (
                _file_revision_source_snapshot,
                _has_live_private_file_identity,
            )

            file_hash = _payload_hash(_file_revision_source_snapshot(file_revision))
            file_valid = all(
                (
                    str(file_revision.global_id) == str(values["file_revision"]["global_id"]),
                    str(file_revision.tenant_id) == str(project.tenant_id),
                    str(file_revision.project_global_id) == str(project.global_id),
                    str(file_revision.scan_state) == "clean",
                    int(file_revision.is_private or 0) == 1,
                    _has_live_private_file_identity(file_revision),
                    file_hash == values["file_revision"]["snapshot_hash"],
                )
            )
        else:
            file_valid = False
        if any(
            (
                part is None,
                master is None,
                revision is None,
                tooling_set is None,
                not file_valid,
                str(getattr(master, "global_id", "")) != str(values["tooling_master_id"]),
                str(getattr(master, "tenant_id", "")) != str(project.tenant_id),
                str(getattr(revision, "tooling_master_global_id", ""))
                != str(values["tooling_master_id"]),
                str(getattr(tooling_set, "tooling_master_global_id", ""))
                != str(values["tooling_master_id"]),
                trial_round.tooling_master_global_id != values["tooling_master_id"],
            )
        ):
            raise TrialReviewUnavailable()

    @staticmethod
    def _exact_snapshot_document(project, doctype, exact, project_field):
        document = _optional_doc(doctype, str(exact["global_id"]))
        if document is None:
            return None
        snapshot_hash = str(getattr(document, "snapshot_hash", ""))
        return (
            document
            if all(
                (
                    str(document.global_id) == str(exact["global_id"]),
                    str(document.tenant_id) == str(project.tenant_id),
                    str(getattr(document, project_field, "")) == str(project.global_id),
                    snapshot_hash == exact["snapshot_hash"],
                )
            )
            else None
        )

    def _exact_comparison(self, project, round_id, revision_id, snapshot_hash):
        document = _optional_doc("NPI Trial Round Comparison Snapshot", str(revision_id))
        if document is None:
            raise TrialReviewUnavailable()
        value = comparison_from_snapshot(_json_object(document.comparison_snapshot))
        if any(
            (
                value.global_id != revision_id,
                value.snapshot_hash != str(document.snapshot_hash),
                value.snapshot_hash != snapshot_hash,
                value.tenant_id != str(project.tenant_id),
                value.project_global_id != UUID(str(project.global_id)),
                value.target_round_global_id != round_id,
            )
        ):
            raise TrialReviewConflict()
        return value

    def _exact_reference_revision(self, project, round_id, revision_id, snapshot_hash):
        document = _optional_doc("NPI Trial Review Reference Revision", str(revision_id))
        if document is None:
            raise TrialReviewUnavailable()
        value = review_reference_from_snapshot(_json_object(document.reference_snapshot))
        if any(
            (
                value.global_id != revision_id,
                value.snapshot_hash != str(document.snapshot_hash),
                value.snapshot_hash != snapshot_hash,
                value.tenant_id != str(project.tenant_id),
                value.project_global_id != UUID(str(project.global_id)),
                value.trial_round_global_id != round_id,
            )
        ):
            raise TrialReviewConflict()
        return value

    def _exact_conclusion_revision(self, project, round_id, revision_id, snapshot_hash):
        document = _optional_doc("NPI Trial Conclusion Revision", str(revision_id))
        if document is None:
            raise TrialReviewUnavailable()
        value = conclusion_from_snapshot(_json_object(document.conclusion_snapshot))
        if any(
            (
                value.global_id != revision_id,
                value.snapshot_hash != str(document.snapshot_hash),
                value.snapshot_hash != snapshot_hash,
                value.tenant_id != str(project.tenant_id),
                value.project_global_id != UUID(str(project.global_id)),
                value.trial_round_global_id != round_id,
            )
        ):
            raise TrialReviewConflict()
        return value

    def _policy_history(self, project, plan_id):
        values = self._review_history(
            project,
            "NPI Trial Conclusion Policy Version",
            {"trial_plan_global_id": str(plan_id)},
            "policy_global_id asc, policy_version asc, global_id asc",
            _MAX_POLICIES,
            "policy_snapshot",
            policy_from_snapshot,
        )
        groups = {}
        for value in values:
            groups.setdefault(value.policy_global_id, []).append(value)
        for chain in groups.values():
            if chain[0].policy_version != 1:
                raise RuntimeError("Persisted Trial conclusion policy chain does not start at one.")
            for current, successor in zip(chain, chain[1:], strict=False):
                validate_conclusion_policy_successor(current, successor)
        return tuple(values)

    def _comparison_history(self, project, round_id):
        return tuple(
            self._review_history(
                project,
                "NPI Trial Round Comparison Snapshot",
                {"target_round_global_id": str(round_id)},
                "created_at asc, global_id asc",
                _MAX_COMPARISONS,
                "comparison_snapshot",
                comparison_from_snapshot,
            )
        )

    def _reference_history(self, project, round_id):
        values = self._review_history(
            project,
            "NPI Trial Review Reference Revision",
            {"trial_round_global_id": str(round_id)},
            "reference_global_id asc, reference_version asc, global_id asc",
            _MAX_REFERENCES,
            "reference_snapshot",
            review_reference_from_snapshot,
        )
        groups = {}
        for value in values:
            groups.setdefault(value.reference_global_id, []).append(value)
        for chain in groups.values():
            if chain[0].reference_version != 1:
                raise RuntimeError("Persisted Trial review reference chain does not start at one.")
            for current, successor in zip(chain, chain[1:], strict=False):
                validate_review_reference_successor(current, successor)
        return tuple(values)

    def _reference_chain(self, project, round_id, stable_id):
        return tuple(
            value
            for value in self._reference_history(project, round_id)
            if value.reference_global_id == stable_id
        )

    def _conclusion_history(self, project, round_id):
        values = self._review_history(
            project,
            "NPI Trial Conclusion Revision",
            {"trial_round_global_id": str(round_id)},
            "conclusion_global_id asc, conclusion_version asc, global_id asc",
            _MAX_CONCLUSIONS,
            "conclusion_snapshot",
            conclusion_from_snapshot,
        )
        groups = {}
        for value in values:
            groups.setdefault(value.conclusion_global_id, []).append(value)
        for chain in groups.values():
            if chain[0].conclusion_version != 1:
                raise RuntimeError("Persisted Trial conclusion chain does not start at one.")
            for current, successor in zip(chain, chain[1:], strict=False):
                validate_conclusion_successor(current, successor)
        return tuple(values)

    def _conclusion_chain(self, project, round_id, stable_id):
        return tuple(
            value
            for value in self._conclusion_history(project, round_id)
            if value.conclusion_global_id == stable_id
        )

    @staticmethod
    def _review_history(project, doctype, filters, order_by, maximum, field, factory):
        names = frappe.get_all(
            doctype,
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                **filters,
            },
            pluck="name",
            order_by=order_by,
            limit_page_length=maximum + 1,
        )
        if len(names) > maximum:
            raise RuntimeError(f"Persisted {doctype} collection exceeds its safe bound.")
        values = []
        for name in names:
            document = frappe.get_doc(doctype, str(name))
            value = factory(_json_object(getattr(document, field)))
            if any(
                (
                    value.tenant_id != str(project.tenant_id),
                    value.project_global_id != UUID(str(project.global_id)),
                    value.snapshot_hash != str(document.snapshot_hash),
                    str(value.global_id) != str(document.global_id),
                )
            ):
                raise RuntimeError(f"Persisted {doctype} integrity failed.")
            values.append(value)
        return values

    def _review_workspace_for(self, project, trial_round: TrialRound):
        policies = self._policy_history(project, trial_round.trial_plan_global_id)
        comparisons = self._comparison_history(project, trial_round.global_id)
        references = self._reference_history(project, trial_round.global_id)
        conclusions = self._conclusion_history(project, trial_round.global_id)
        current_member = self._current_actor_member(project)
        capabilities = set()
        if current_member and self._is_internal_system_manager():
            for policy in policies:
                for binding in policy.authority_bindings:
                    if binding.member == self._member_value(current_member):
                        capabilities.update(binding.capabilities)
        return {
            "projectGlobalId": str(project.global_id),
            "trialRound": _round_response(trial_round),
            "policyVersions": [self._snapshot_response(value) for value in policies],
            "comparisonSnapshots": [self._snapshot_response(value) for value in comparisons],
            "reviewReferenceRevisions": [self._snapshot_response(value) for value in references],
            "conclusionRevisions": [self._snapshot_response(value) for value in conclusions],
            "permissions": {
                "view": True,
                "requiresExactPolicyRevision": True,
                "beginAnalysis": (
                    trial_round.current_state is TrialRoundState.RUNNING
                    and TrialConclusionCapability.SUBMIT in capabilities
                ),
                "createComparison": (
                    trial_round.current_state is TrialRoundState.ANALYSIS
                    and TrialConclusionCapability.SUBMIT in capabilities
                ),
                "manageReviewReferences": (
                    trial_round.current_state is TrialRoundState.ANALYSIS
                    and TrialConclusionCapability.SUBMIT in capabilities
                ),
                "submitConclusion": (
                    trial_round.current_state is TrialRoundState.ANALYSIS
                    and TrialConclusionCapability.SUBMIT in capabilities
                ),
                "decideConclusion": (
                    trial_round.current_state is TrialRoundState.SUBMITTED
                    and TrialConclusionCapability.DECIDE in capabilities
                ),
                "reopenConclusion": (
                    trial_round.current_state
                    in {TrialRoundState.SUBMITTED, TrialRoundState.APPROVED, TrialRoundState.REJECTED}
                    and TrialConclusionCapability.REOPEN in capabilities
                ),
            },
            "externalEffects": {
                "formalErpQuality": "unavailable",
                "customerSignature": "unavailable",
                "gate": "unavailable",
                "npiReadiness": "unavailable",
                "toolingLifecycle": "unavailable",
                "nextWork": "proposal_only",
            },
        }

    @staticmethod
    def _member_value(document):
        from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility

        return ProjectMemberResponsibility(
            global_id=UUID(str(document.global_id)),
            user_id=str(document.user_id),
            optimistic_version=int(document.optimistic_version),
        )

    @staticmethod
    def _snapshot_response(value):
        result = value.snapshot_payload() | {"snapshotHash": value.snapshot_hash}
        version_key = getattr(value, "version_key_hash", None)
        if version_key:
            result["versionKeyHash"] = version_key
        return result

    def _persist_review_command(
        self,
        project,
        round_document,
        trial_round,
        *,
        operation,
        idempotency_key_hash,
        payload_hash,
        target_type,
        target,
        insert,
        now,
        lifecycle_event=None,
    ):
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if isinstance(receipt, dict):
                return TrialExecutionCommandOutcome(receipt, replayed=True)
            insert(target)
            if lifecycle_event is not None:
                self._insert_round_event(lifecycle_event)
            if lifecycle_event is not None or target_type == "trial_round_lifecycle_event":
                self._save_round(round_document, trial_round)
            version = (
                target.event_version
                if target_type == "trial_round_lifecycle_event"
                else getattr(
                    target,
                    "conclusion_version",
                    getattr(target, "reference_version", 1),
                )
            )
            self._append_audit(
                operation=operation,
                global_id=target.global_id,
                object_version=version,
                summary={
                    "projectId": str(project.global_id),
                    "trialRoundGlobalId": str(trial_round.global_id),
                    "snapshotHash": target.snapshot_hash,
                    "requestId": self.request_id,
                },
            )
            response = self._review_workspace_for(project, trial_round)
            self._seal_receipt(
                receipt,
                target_object_type=target_type,
                target_global_id=target.global_id,
                response=response,
                updated_at=now,
            )
        return TrialExecutionCommandOutcome(response)

    @staticmethod
    def _insert_comparison(value):
        payload = value.snapshot_payload()
        frappe.get_doc(
            {
                "doctype": "NPI Trial Round Comparison Snapshot",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_plan_global_id": str(value.trial_plan_global_id),
                "target_round": str(value.target_round_global_id),
                "target_round_global_id": str(value.target_round_global_id),
                "policy_revision": str(value.policy_revision.global_id),
                "policy_revision_global_id": str(value.policy_revision.global_id),
                "policy_revision_snapshot_hash": value.policy_revision.snapshot_hash,
                "source_snapshot": canonical_json(payload["sources"]),
                "input_comparison_snapshot": canonical_json(payload["inputRows"]),
                "metric_comparison_snapshot": canonical_json(payload["metricRows"]),
                "defect_trend_snapshot": canonical_json(payload["defectTrends"]),
                "formal_erp_quality": "unavailable",
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "comparison_snapshot": canonical_json(payload),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_review_reference(value):
        payload = value.snapshot_payload()
        frappe.get_doc(
            {
                "doctype": "NPI Trial Review Reference Revision",
                "global_id": str(value.global_id),
                "reference_global_id": str(value.reference_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "comparison_snapshot_revision": str(value.comparison_snapshot.global_id),
                "comparison_snapshot_global_id": str(value.comparison_snapshot.global_id),
                "comparison_snapshot_hash": value.comparison_snapshot.snapshot_hash,
                "reference_kind": value.reference_kind.value,
                "reference_version": value.reference_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "part_revision_global_id": str(value.part_revision.global_id),
                "part_revision_snapshot_hash": value.part_revision.snapshot_hash,
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "tooling_revision": str(value.tooling_revision.global_id),
                "tooling_revision_global_id": str(value.tooling_revision.global_id),
                "tooling_revision_snapshot_hash": value.tooling_revision.snapshot_hash,
                "tooling_set": str(value.tooling_set.global_id),
                "tooling_set_global_id": str(value.tooling_set.global_id),
                "tooling_set_snapshot_hash": value.tooling_set.snapshot_hash,
                "file_revision": str(value.file_revision.global_id),
                "file_revision_global_id": str(value.file_revision.global_id),
                "file_revision_snapshot_hash": value.file_revision.snapshot_hash,
                "effective_from": value.effective_from.isoformat() if value.effective_from else None,
                "effective_to": value.effective_to.isoformat() if value.effective_to else None,
                "approval_authority": "unavailable",
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "reference_snapshot": payload,
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_conclusion(value):
        payload = value.snapshot_payload()
        frappe.get_doc(
            {
                "doctype": "NPI Trial Conclusion Revision",
                "global_id": str(value.global_id),
                "conclusion_global_id": str(value.conclusion_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "trial_round_optimistic_version": value.trial_round_optimistic_version,
                "trial_round_snapshot_hash": value.trial_round_snapshot_hash,
                "conclusion_version": value.conclusion_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "state": value.state.value,
                "conclusion_code": value.conclusion_code.value,
                "policy_revision": str(value.policy_revision.global_id),
                "policy_revision_global_id": str(value.policy_revision.global_id),
                "policy_revision_snapshot_hash": value.policy_revision.snapshot_hash,
                "comparison_snapshot_revision": str(value.comparison_snapshot.global_id),
                "comparison_snapshot_global_id": str(value.comparison_snapshot.global_id),
                "comparison_snapshot_hash": value.comparison_snapshot.snapshot_hash,
                "review_reference_snapshot": payload["reviewReferences"],
                "blocker_snapshot": payload["blockers"],
                "summary_input_snapshot": value.summary_input,
                "proposed_next_work_snapshot": list(value.proposed_next_work),
                "proposed_gate_effect": value.proposed_gate_effect,
                "proposed_npi_effect": value.proposed_npi_effect,
                "external_effect_snapshot": payload["externalEffects"],
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "conclusion_snapshot": payload,
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()
