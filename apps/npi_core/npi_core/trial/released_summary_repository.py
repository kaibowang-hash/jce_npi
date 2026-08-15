from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.documents.frappe_validation import canonical_json
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.tooling.engineering_controls_domain import defect_revision_from_snapshot
from npi_core.trial.domain import TrialRound, trial_plan_from_snapshot
from npi_core.trial.execution_domain import (
    actual_revision_from_snapshot,
    input_lock_from_snapshot,
    sample_batch_from_snapshot,
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
    cavity_result_from_snapshot,
    trial_defect_from_snapshot,
    verification_from_snapshot,
)
from npi_core.trial.released_summary_domain import (
    ReleasedTrialSummaryConflict,
    ReleasedTrialSummaryFactValueState,
    ReleasedTrialSummaryRevision,
    ReleasedTrialSummarySourceKind,
    ReleasedTrialSummarySourceReference,
    ReleasedTrialSummaryUnavailable,
    build_released_trial_summary_projection,
    build_released_trial_summary_redaction_manifest,
    released_trial_summary_from_snapshot,
    validate_released_trial_summary_successor,
)
from npi_core.trial.review_domain import (
    TrialComparisonCellState,
    TrialConclusionRevision,
    TrialConclusionRevisionState,
    TrialDefectSourceKind,
)
from npi_core.trial.review_repository import FrappeTrialReviewRepository


_MAX_SUMMARIES = 10_000


@dataclass(frozen=True, slots=True)
class _ReleasedSummaryGraph:
    manifest: tuple[ReleasedTrialSummarySourceReference, ...]
    facts: Mapping[str, object]


class FrappeReleasedTrialSummaryRepository(FrappeTrialReviewRepository):
    """Project-first immutable P7-07 summary aggregate."""

    def summary_workspace(
        self,
        project_id: UUID,
        round_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        pair = self._execution_round(project, round_id)
        if pair is None:
            return None
        return self._summary_workspace_for(project, pair[1])

    def retain_summary(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_round_snapshot_hash: str,
        conclusion_revision_id: UUID,
        expected_conclusion_version: int,
        expected_conclusion_snapshot_hash: str,
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedRoundSnapshotHash": expected_round_snapshot_hash,
            "conclusionRevisionGlobalId": conclusion_revision_id,
            "expectedConclusionVersion": expected_conclusion_version,
            "expectedConclusionSnapshotHash": expected_conclusion_snapshot_hash,
            "reason": reason,
        }
        project, replay, payload_hash = self._summary_command_start(
            project_id,
            "released_trial_summary.retain",
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        pair = self._locked_exact_round(
            project,
            round_id,
            expected_round_optimistic_version,
            expected_round_snapshot_hash,
        )
        trial_round = pair[1]
        if self._summary_history(project, round_id, lock_tip=True):
            raise ReleasedTrialSummaryConflict()
        conclusion = self._exact_current_decided_conclusion(
            project,
            trial_round,
            conclusion_revision_id,
            expected_conclusion_version,
            expected_conclusion_snapshot_hash,
        )
        graph = self._exact_source_graph(project, trial_round, conclusion)
        now = datetime.now(UTC)
        summary_id = uuid4()
        value = self._build_revision(
            project,
            trial_round,
            conclusion,
            graph,
            global_id=summary_id,
            summary_global_id=summary_id,
            summary_version=1,
            predecessor=None,
            reason=reason,
            now=now,
        )
        return self._persist_summary(
            project,
            trial_round,
            value,
            operation="released_trial_summary.retain",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            now=now,
        )

    def revise_summary(
        self,
        project_id: UUID,
        round_id: UUID,
        summary_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_round_snapshot_hash: str,
        conclusion_revision_id: UUID,
        expected_conclusion_version: int,
        expected_conclusion_snapshot_hash: str,
        predecessor_revision_id: UUID,
        expected_predecessor_version: int,
        expected_predecessor_snapshot_hash: str,
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "summaryGlobalId": summary_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedRoundSnapshotHash": expected_round_snapshot_hash,
            "conclusionRevisionGlobalId": conclusion_revision_id,
            "expectedConclusionVersion": expected_conclusion_version,
            "expectedConclusionSnapshotHash": expected_conclusion_snapshot_hash,
            "predecessorRevisionGlobalId": predecessor_revision_id,
            "expectedPredecessorVersion": expected_predecessor_version,
            "expectedPredecessorSnapshotHash": expected_predecessor_snapshot_hash,
            "reason": reason,
        }
        project, replay, payload_hash = self._summary_command_start(
            project_id,
            "released_trial_summary.revise",
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        pair = self._locked_exact_round(
            project,
            round_id,
            expected_round_optimistic_version,
            expected_round_snapshot_hash,
        )
        trial_round = pair[1]
        history = self._summary_history(project, round_id, lock_tip=True)
        if not history:
            raise ReleasedTrialSummaryUnavailable()
        predecessor = history[-1]
        if predecessor.summary_global_id != summary_id:
            raise ReleasedTrialSummaryUnavailable()
        if any(
            (
                predecessor.global_id != predecessor_revision_id,
                predecessor.summary_version != expected_predecessor_version,
                predecessor.snapshot_hash != expected_predecessor_snapshot_hash,
            )
        ):
            raise ReleasedTrialSummaryConflict()
        conclusion = self._exact_current_decided_conclusion(
            project,
            trial_round,
            conclusion_revision_id,
            expected_conclusion_version,
            expected_conclusion_snapshot_hash,
        )
        graph = self._exact_source_graph(project, trial_round, conclusion)
        now = datetime.now(UTC)
        value = self._build_revision(
            project,
            trial_round,
            conclusion,
            graph,
            global_id=uuid4(),
            summary_global_id=predecessor.summary_global_id,
            summary_version=predecessor.summary_version + 1,
            predecessor=predecessor,
            reason=reason,
            now=now,
        )
        validate_released_trial_summary_successor(predecessor, value)
        return self._persist_summary(
            project,
            trial_round,
            value,
            operation="released_trial_summary.revise",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            now=now,
        )

    def _summary_command_start(self, project_id, operation, key_hash, payload):
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None, None, ""
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(project, operation, key_hash, payload_hash)
        if replay is None:
            if not self._is_internal_system_manager():
                return None, None, ""
            require_mutable_project(project)
        return project, replay, payload_hash

    def _locked_exact_round(self, project, round_id, version, snapshot_hash):
        pair = self._execution_round(project, round_id, for_update=True)
        if pair is None:
            raise ReleasedTrialSummaryUnavailable()
        if (
            pair[1].optimistic_version != version
            or pair[1].snapshot_hash != snapshot_hash
        ):
            raise ReleasedTrialSummaryConflict()
        return pair

    def _exact_current_decided_conclusion(
        self,
        project,
        trial_round: TrialRound,
        revision_id: UUID,
        version: int,
        snapshot_hash: str,
    ) -> TrialConclusionRevision:
        history = self._conclusion_history(project, trial_round.global_id)
        if not history:
            raise ReleasedTrialSummaryUnavailable()
        stable_ids = {value.conclusion_global_id for value in history}
        if len(stable_ids) != 1:
            raise RuntimeError("Persisted Trial conclusion has multiple stable streams.")
        current = history[-1]
        if any(
            (
                current.global_id != revision_id,
                current.conclusion_version != version,
                current.snapshot_hash != snapshot_hash,
                current.state
                not in {
                    TrialConclusionRevisionState.APPROVED,
                    TrialConclusionRevisionState.REJECTED,
                },
                current.trial_round_optimistic_version
                != trial_round.optimistic_version,
                current.trial_round_snapshot_hash != trial_round.snapshot_hash,
            )
        ):
            raise ReleasedTrialSummaryConflict()
        return current

    def _exact_source_graph(
        self,
        project,
        trial_round: TrialRound,
        conclusion: TrialConclusionRevision,
    ) -> _ReleasedSummaryGraph:
        try:
            comparison = self._exact_comparison(
                project,
                trial_round.global_id,
                conclusion.comparison_snapshot.global_id,
                conclusion.comparison_snapshot.snapshot_hash,
            )
            references = tuple(
                self._exact_reference_revision(
                    project,
                    trial_round.global_id,
                    reference.global_id,
                    reference.snapshot_hash,
                )
                for reference in conclusion.review_references
            )
        except Exception as error:
            if error.__class__.__name__ in {"TrialReviewUnavailable", "TrialReviewConflict"}:
                raise ReleasedTrialSummaryConflict() from error
            raise
        target = next(
            (
                value
                for value in comparison.sources
                if value.trial_round_global_id == trial_round.global_id
            ),
            None,
        )
        if target is None or any(
            (
                target is not comparison.sources[-1],
                target.trial_plan_revision.global_id
                != trial_round.trial_plan_revision_global_id,
                target.trial_plan_revision.snapshot_hash
                != trial_round.trial_plan_revision_snapshot_hash,
            )
        ):
            raise ReleasedTrialSummaryConflict()

        plan = self._exact_value(
            project,
            trial_round.global_id,
            "NPI Trial Plan Revision",
            target.trial_plan_revision.global_id,
            target.trial_plan_revision.snapshot_hash,
            "plan_snapshot",
            trial_plan_from_snapshot,
            round_scoped=False,
        )
        input_lock = (
            self._exact_value(
                project,
                trial_round.global_id,
                "NPI Trial Input Lock Revision",
                target.input_lock_revision.global_id,
                target.input_lock_revision.snapshot_hash,
                "lock_snapshot",
                input_lock_from_snapshot,
            )
            if target.input_lock_revision
            else None
        )
        actual = (
            self._exact_value(
                project,
                trial_round.global_id,
                "NPI Trial Actual Revision",
                target.actual_revision.global_id,
                target.actual_revision.snapshot_hash,
                "actual_snapshot",
                actual_revision_from_snapshot,
            )
            if target.actual_revision
            else None
        )
        samples = tuple(
            self._exact_value(
                project,
                trial_round.global_id,
                "NPI Trial Sample Batch Revision",
                exact.global_id,
                exact.snapshot_hash,
                "sample_snapshot",
                sample_batch_from_snapshot,
            )
            for exact in target.sample_revisions
        )
        cavities = tuple(
            self._exact_value(
                project,
                trial_round.global_id,
                "NPI Trial Cavity Result Revision",
                tip.revision.global_id,
                tip.revision.snapshot_hash,
                "cavity_result_snapshot",
                cavity_result_from_snapshot,
            )
            for tip in target.cavity_results
        )
        tooling_defect_tips = tuple(
            tip for tip in target.defect_tips if tip.source_kind is TrialDefectSourceKind.TOOLING
        )
        tooling_defects = tuple(
            self._exact_value(
                project,
                trial_round.global_id,
                "NPI Tooling Defect Revision",
                tip.revision.global_id,
                tip.revision.snapshot_hash,
                "defect_snapshot",
                defect_revision_from_snapshot,
                round_scoped=False,
            )
            for tip in tooling_defect_tips
        )
        if any(
            value.tooling_master_global_id != trial_round.tooling_master_global_id
            for value in tooling_defects
        ):
            raise ReleasedTrialSummaryConflict()
        trial_defect_tips = tuple(
            tip for tip in target.defect_tips if tip.source_kind is TrialDefectSourceKind.TRIAL
        )
        defects = tuple(
            self._exact_value(
                project,
                trial_round.global_id,
                "NPI Trial Defect Revision",
                tip.revision.global_id,
                tip.revision.snapshot_hash,
                "trial_defect_snapshot",
                trial_defect_from_snapshot,
            )
            for tip in trial_defect_tips
        )
        verifications = []
        verification_ids = set()
        for defect in defects:
            for action in defect.actions:
                if action.verification_revision_global_id is None:
                    continue
                key = (
                    action.verification_revision_global_id,
                    action.verification_revision_snapshot_hash,
                )
                if key in verification_ids:
                    continue
                verification_ids.add(key)
                verification = self._exact_value(
                    project,
                    trial_round.global_id,
                    "NPI Trial Defect Verification Revision",
                    key[0],
                    key[1],
                    "verification_snapshot",
                    verification_from_snapshot,
                    verification_round_scoped=True,
                )
                if verification.defect_revision_global_id != defect.global_id:
                    raise ReleasedTrialSummaryConflict()
                verifications.append(verification)

        manifest = [
            self._source(ReleasedTrialSummarySourceKind.TRIAL_PLAN_REVISION, plan),
            ReleasedTrialSummarySourceReference(
                ReleasedTrialSummarySourceKind.TRIAL_ROUND,
                trial_round.global_id,
                trial_round.optimistic_version,
                trial_round.snapshot_hash,
            ),
        ]
        if input_lock is not None:
            manifest.append(
                self._source(ReleasedTrialSummarySourceKind.TRIAL_INPUT_LOCK_REVISION, input_lock)
            )
        if actual is not None:
            manifest.append(self._source(ReleasedTrialSummarySourceKind.TRIAL_ACTUAL_REVISION, actual))
        manifest.extend(
            self._source(ReleasedTrialSummarySourceKind.TRIAL_SAMPLE_BATCH_REVISION, value)
            for value in samples
        )
        manifest.extend(
            self._source(ReleasedTrialSummarySourceKind.TRIAL_CAVITY_RESULT_REVISION, value)
            for value in cavities
        )
        manifest.extend(
            self._source(ReleasedTrialSummarySourceKind.TOOLING_DEFECT_REVISION, value)
            for value in tooling_defects
        )
        manifest.extend(
            self._source(ReleasedTrialSummarySourceKind.TRIAL_DEFECT_REVISION, value)
            for value in defects
        )
        manifest.extend(
            self._source(
                ReleasedTrialSummarySourceKind.TRIAL_DEFECT_VERIFICATION_REVISION,
                value,
            )
            for value in verifications
        )
        manifest.append(
            ReleasedTrialSummarySourceReference(
                ReleasedTrialSummarySourceKind.TRIAL_ROUND_COMPARISON_SNAPSHOT,
                comparison.global_id,
                1,
                comparison.snapshot_hash,
            )
        )
        manifest.extend(
            self._source(
                ReleasedTrialSummarySourceKind.TRIAL_REVIEW_REFERENCE_REVISION,
                value,
            )
            for value in references
        )
        manifest.append(
            self._source(
                ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION,
                conclusion,
            )
        )
        order = {kind: index for index, kind in enumerate(ReleasedTrialSummarySourceKind)}
        exact_manifest = tuple(
            sorted(manifest, key=lambda value: (order[value.kind], str(value.global_id)))
        )
        return _ReleasedSummaryGraph(
            exact_manifest,
            self._presentation_facts(
                exact_manifest,
                comparison,
                target,
                actual,
                samples,
                cavities,
                tooling_defects,
                defects,
                verifications,
                references,
                conclusion,
            ),
        )

    def _exact_value(
        self,
        project,
        round_id: UUID,
        doctype: str,
        global_id: UUID,
        snapshot_hash: str,
        snapshot_field: str,
        factory: Callable[[object], Any],
        *,
        round_scoped: bool = True,
        verification_round_scoped: bool = False,
    ):
        document = _optional_doc(doctype, str(global_id))
        if document is None:
            raise ReleasedTrialSummaryConflict()
        try:
            value = factory(_json_object(getattr(document, snapshot_field)))
        except Exception as error:
            raise ReleasedTrialSummaryConflict() from error
        value_round = getattr(value, "trial_round_global_id", None)
        if verification_round_scoped:
            value_round = getattr(value, "target_round_global_id", None)
        if any(
            (
                value.global_id != global_id,
                value.snapshot_hash != snapshot_hash,
                value.snapshot_hash != str(document.snapshot_hash),
                value.tenant_id != str(project.tenant_id),
                value.project_global_id != UUID(str(project.global_id)),
                round_scoped and value_round != round_id,
            )
        ):
            raise ReleasedTrialSummaryConflict()
        return value

    @staticmethod
    def _source(kind: ReleasedTrialSummarySourceKind, value: Any):
        version_fields = {
            ReleasedTrialSummarySourceKind.TRIAL_PLAN_REVISION: "plan_version",
            ReleasedTrialSummarySourceKind.TRIAL_INPUT_LOCK_REVISION: "lock_version",
            ReleasedTrialSummarySourceKind.TRIAL_ACTUAL_REVISION: "actual_version",
            ReleasedTrialSummarySourceKind.TRIAL_SAMPLE_BATCH_REVISION: "sample_version",
            ReleasedTrialSummarySourceKind.TRIAL_CAVITY_RESULT_REVISION: "result_version",
            ReleasedTrialSummarySourceKind.TOOLING_DEFECT_REVISION: "defect_version",
            ReleasedTrialSummarySourceKind.TRIAL_DEFECT_REVISION: "defect_version",
            ReleasedTrialSummarySourceKind.TRIAL_DEFECT_VERIFICATION_REVISION: "attempt_sequence",
            ReleasedTrialSummarySourceKind.TRIAL_REVIEW_REFERENCE_REVISION: "reference_version",
            ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION: "conclusion_version",
        }
        return ReleasedTrialSummarySourceReference(
            kind,
            value.global_id,
            int(getattr(value, version_fields[kind])),
            value.snapshot_hash,
        )

    def _presentation_facts(
        self,
        manifest,
        comparison,
        target,
        actual,
        samples,
        cavities,
        tooling_defects,
        defects,
        verifications,
        references,
        conclusion,
    ) -> dict[str, object]:
        by_id = {value.global_id: value for value in manifest}
        comparison_source = by_id[comparison.global_id]
        conclusion_source = by_id[conclusion.global_id]

        def refs(*ids: UUID | None):
            values = {by_id[value] for value in ids if value in by_id}
            if not values:
                values = {comparison_source}
            positions = {value: index for index, value in enumerate(manifest)}
            return [value.snapshot_payload() for value in sorted(values, key=positions.__getitem__)]

        def fact(key, state, value, unit, *source_ids):
            return {
                "factKey": key,
                "valueState": state.value,
                "value": value,
                "unit": unit,
                "sourceReferences": refs(*source_ids),
            }

        input_changes = []
        for row in comparison.input_rows:
            cell = row.cells[-1]
            input_changes.append(
                fact(
                    f"input.{row.semantic_key}",
                    ReleasedTrialSummaryFactValueState.INFORMATIONAL,
                    f"{row.change_state.value}:{cell.canonical_value or ''}",
                    None,
                    cell.source_revision.global_id if cell.source_revision else comparison.global_id,
                )
            )
        actual_parameters = []
        if actual is not None:
            for value in actual.parameters:
                state = (
                    ReleasedTrialSummaryFactValueState.MEASURED
                    if value.state.value == "measured"
                    else ReleasedTrialSummaryFactValueState.NOT_MEASURED
                )
                actual_parameters.append(
                    fact(
                        f"actual.parameter.{value.definition_key}",
                        state,
                        value.value,
                        value.unit,
                        actual.global_id,
                    )
                )
        sample_facts = [
            fact(
                f"sample.{value.sample_batch_global_id}",
                ReleasedTrialSummaryFactValueState.INFORMATIONAL,
                value.quantity,
                value.unit,
                value.global_id,
            )
            for value in samples
        ]
        cavity_facts = []
        for cavity in cavities:
            for value in cavity.measurements:
                state = (
                    ReleasedTrialSummaryFactValueState.MEASURED
                    if value.state.value == "measured"
                    else ReleasedTrialSummaryFactValueState.NOT_MEASURED
                )
                cavity_facts.append(
                    fact(
                        f"cavity.{cavity.cavity_global_id}.{value.characteristic_key}",
                        state,
                        value.value,
                        value.unit,
                        cavity.global_id,
                    )
                )
        verification_by_defect = {}
        for value in verifications:
            verification_by_defect.setdefault(value.defect_revision_global_id, []).append(value.global_id)
        tooling_defect_facts = []
        for value in tooling_defects:
            defect_state = (
                ReleasedTrialSummaryFactValueState.CLOSED
                if value.state.value == "closed"
                else ReleasedTrialSummaryFactValueState.OPEN
            )
            tooling_defect_facts.append(
                fact(
                    f"toolingDefect.{value.defect_global_id}",
                    defect_state,
                    value.business_code,
                    None,
                    value.global_id,
                )
            )
            tooling_defect_facts.extend(
                fact(
                    f"toolingDefect.{value.defect_global_id}.action.{action.global_id}",
                    ReleasedTrialSummaryFactValueState.INFORMATIONAL,
                    f"{action.action_type.value}:{action.state.value}:{action.detail}",
                    None,
                    value.global_id,
                )
                for action in value.actions
            )
        trial_defect_facts = []
        for value in defects:
            defect_state = (
                ReleasedTrialSummaryFactValueState.CLOSED
                if value.state.value == "closed"
                else ReleasedTrialSummaryFactValueState.OPEN
            )
            verification_sources = verification_by_defect.get(value.global_id, ())
            trial_defect_facts.append(
                fact(
                    f"defect.{value.defect_global_id}",
                    defect_state,
                    value.business_code,
                    None,
                    value.global_id,
                    *verification_sources,
                )
            )
            trial_defect_facts.extend(
                fact(
                    f"defect.{value.defect_global_id}.action.{action.global_id}",
                    ReleasedTrialSummaryFactValueState.INFORMATIONAL,
                    f"{action.action_type.value}:{action.state.value}:{action.detail}",
                    None,
                    value.global_id,
                    action.verification_revision_global_id,
                )
                for action in value.actions
            )
        verification_facts = [
            fact(
                f"defectVerification.{value.verification_global_id}.{value.attempt_sequence}",
                (
                    ReleasedTrialSummaryFactValueState.SATISFIED
                    if value.result.value == "pass"
                    else ReleasedTrialSummaryFactValueState.FAILED
                ),
                value.result.value,
                None,
                value.global_id,
                value.defect_revision_global_id,
            )
            for value in verifications
        ]
        comparison_facts = []
        for row in comparison.metric_rows:
            cell = row.cells[-1]
            state = {
                TrialComparisonCellState.MEASURED: ReleasedTrialSummaryFactValueState.MEASURED,
                TrialComparisonCellState.NOT_MEASURED: ReleasedTrialSummaryFactValueState.NOT_MEASURED,
                TrialComparisonCellState.UNAVAILABLE: ReleasedTrialSummaryFactValueState.UNAVAILABLE,
            }[cell.state]
            comparison_facts.append(
                fact(
                    f"comparison.{row.metric_kind.value}.{row.metric_key}.{row.cavity_global_id or 'all'}",
                    state,
                    cell.value,
                    cell.unit,
                    cell.source_revision.global_id if cell.source_revision else comparison.global_id,
                    comparison.global_id,
                )
            )
        controlled_references = [
            fact(
                f"reference.{value.reference_global_id}",
                ReleasedTrialSummaryFactValueState.INFORMATIONAL,
                value.reference_kind.value,
                None,
                value.global_id,
            )
            for value in references
        ]
        blocker_facts = [
            fact(
                f"blocker.{index}.{value.code.value}",
                ReleasedTrialSummaryFactValueState.FAILED,
                value.source_key,
                None,
                conclusion_source.global_id,
            )
            for index, value in enumerate(conclusion.blockers, start=1)
        ]
        return {
            "inputChanges": input_changes,
            "actualParameters": actual_parameters,
            "samples": sample_facts,
            "cavityResults": cavity_facts,
            "defects": (
                tooling_defect_facts + trial_defect_facts + verification_facts
            ),
            "comparison": comparison_facts,
            "controlledReferences": controlled_references,
            "blockers": blocker_facts,
        }

    def _build_revision(
        self,
        project,
        trial_round,
        conclusion,
        graph,
        *,
        global_id,
        summary_global_id,
        summary_version,
        predecessor,
        reason,
        now,
    ):
        conclusion_source = next(
            value
            for value in graph.manifest
            if value.kind is ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION
        )
        projection = build_released_trial_summary_projection(
            project_global_id=UUID(str(project.global_id)),
            trial_plan_global_id=trial_round.trial_plan_global_id,
            trial_round_global_id=trial_round.global_id,
            conclusion_revision=conclusion_source,
            conclusion_state=conclusion.state,
            conclusion_code=conclusion.conclusion_code,
            source_manifest=graph.manifest,
            facts=graph.facts,
        )
        return ReleasedTrialSummaryRevision(
            global_id=global_id,
            summary_global_id=summary_global_id,
            tenant_id=str(project.tenant_id),
            project_global_id=UUID(str(project.global_id)),
            trial_plan_global_id=trial_round.trial_plan_global_id,
            trial_round_global_id=trial_round.global_id,
            summary_version=summary_version,
            predecessor_global_id=predecessor.global_id if predecessor else None,
            predecessor_snapshot_hash=predecessor.snapshot_hash if predecessor else None,
            trial_round_optimistic_version=trial_round.optimistic_version,
            trial_round_snapshot_hash=trial_round.snapshot_hash,
            trial_plan_revision_global_id=trial_round.trial_plan_revision_global_id,
            trial_plan_revision_snapshot_hash=trial_round.trial_plan_revision_snapshot_hash,
            conclusion_revision_global_id=conclusion.global_id,
            conclusion_version=conclusion.conclusion_version,
            conclusion_snapshot_hash=conclusion.snapshot_hash,
            conclusion_state=conclusion.state,
            conclusion_code=conclusion.conclusion_code,
            source_manifest=graph.manifest,
            presentation_projection=projection,
            redaction_manifest=build_released_trial_summary_redaction_manifest(),
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )

    def _summary_history(self, project, round_id, *, lock_tip=False):
        names = frappe.get_all(
            "NPI Released Trial Summary Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "trial_round_global_id": str(round_id),
            },
            pluck="name",
            order_by="summary_global_id asc, summary_version asc, global_id asc",
            limit_page_length=_MAX_SUMMARIES + 1,
        )
        if len(names) > _MAX_SUMMARIES:
            raise RuntimeError("Persisted Released Trial Summary collection exceeds its safe bound.")
        values = []
        for index, name in enumerate(names):
            document = frappe.get_doc(
                "NPI Released Trial Summary Revision",
                str(name),
                for_update=bool(lock_tip and index == len(names) - 1),
            )
            value = released_trial_summary_from_snapshot(_json_object(document.summary_snapshot))
            if any(
                (
                    value.global_id != UUID(str(document.global_id)),
                    value.tenant_id != str(project.tenant_id),
                    value.project_global_id != UUID(str(project.global_id)),
                    value.trial_round_global_id != round_id,
                    value.snapshot_hash != str(document.snapshot_hash),
                )
            ):
                raise RuntimeError("Persisted Released Trial Summary integrity failed.")
            values.append(value)
        stable_ids = {value.summary_global_id for value in values}
        if len(stable_ids) > 1:
            raise RuntimeError("Persisted Released Trial Summary has multiple stable streams.")
        if values:
            if values[0].summary_version != 1:
                raise RuntimeError("Persisted Released Trial Summary stream does not start at one.")
            for predecessor, successor in zip(values, values[1:], strict=False):
                validate_released_trial_summary_successor(predecessor, successor)
        return tuple(values)

    def _summary_workspace_for(self, project, trial_round):
        history = self._summary_history(project, trial_round.global_id)
        conclusions = self._conclusion_history(project, trial_round.global_id)
        current_conclusion = conclusions[-1] if conclusions else None
        current_decided = (
            current_conclusion
            if current_conclusion
            and current_conclusion.state
            in {TrialConclusionRevisionState.APPROVED, TrialConclusionRevisionState.REJECTED}
            and current_conclusion.trial_round_optimistic_version
            == trial_round.optimistic_version
            and current_conclusion.trial_round_snapshot_hash == trial_round.snapshot_hash
            else None
        )
        current = history[-1] if history else None
        can_manage = self._is_internal_system_manager()
        return {
            "projectGlobalId": str(project.global_id),
            "trialRound": _round_response(trial_round),
            "summaryRevisions": [
                value.snapshot_payload() | {"snapshotHash": value.snapshot_hash}
                for value in history
            ],
            "currentSummaryRevisionGlobalId": str(current.global_id) if current else None,
            "currentDecidedConclusion": (
                {
                    "globalId": str(current_decided.global_id),
                    "conclusionVersion": current_decided.conclusion_version,
                    "snapshotHash": current_decided.snapshot_hash,
                    "state": current_decided.state.value,
                    "conclusionCode": current_decided.conclusion_code.value,
                }
                if current_decided
                else None
            ),
            "permissions": {
                "view": True,
                "retain": can_manage and current_decided is not None and not history,
                "revise": (
                    can_manage
                    and current_decided is not None
                    and current is not None
                    and current_decided.global_id != current.conclusion_revision_global_id
                    and current_decided.conclusion_version > current.conclusion_version
                ),
                "requiresExactRound": True,
                "requiresExactConclusion": True,
                "requiresExactPredecessor": True,
            },
            "controlledOutput": {
                "sourceObjectType": "released_trial_summary",
                "sourceGlobalId": str(current.global_id) if current else None,
                "sourceVersion": current.summary_version if current else None,
                "mapping": "unavailable",
            },
            "holds": {
                "formalRelease": "unavailable",
                "customerApproval": "unavailable",
                "signature": "unavailable",
                "productionAcceptance": "unavailable",
                "gateDecision": "unavailable",
                "externalProjection": "unavailable",
            },
        }

    def _persist_summary(
        self,
        project,
        trial_round,
        value,
        *,
        operation,
        idempotency_key_hash,
        payload_hash,
        now,
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
            self._insert_summary(value)
            self._append_audit(
                operation=operation,
                global_id=value.global_id,
                object_version=value.summary_version,
                summary={
                    "projectId": str(project.global_id),
                    "trialRoundGlobalId": str(trial_round.global_id),
                    "predecessorGlobalId": (
                        str(value.predecessor_global_id) if value.predecessor_global_id else None
                    ),
                    "conclusionRevisionGlobalId": str(value.conclusion_revision_global_id),
                    "conclusionSnapshotHash": value.conclusion_snapshot_hash,
                    "sourceManifestHash": value.source_manifest_hash,
                    "presentationProjectionHash": value.presentation_projection_hash,
                    "redactionRuleCodes": list(
                        value.redaction_manifest["appliedRuleCodes"]
                    ),
                    "requestId": self.request_id,
                },
            )
            response = self._summary_workspace_for(project, trial_round)
            self._seal_receipt(
                receipt,
                target_object_type="released_trial_summary_revision",
                target_global_id=value.global_id,
                response=response,
                updated_at=now,
            )
        return TrialExecutionCommandOutcome(response)

    @staticmethod
    def _insert_summary(value):
        payload = value.snapshot_payload()
        frappe.get_doc(
            {
                "doctype": "NPI Released Trial Summary Revision",
                "global_id": str(value.global_id),
                "summary_global_id": str(value.summary_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_plan_global_id": str(value.trial_plan_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "summary_version": value.summary_version,
                "predecessor_global_id": (
                    str(value.predecessor_global_id) if value.predecessor_global_id else None
                ),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "trial_round_optimistic_version": value.trial_round_optimistic_version,
                "trial_round_snapshot_hash": value.trial_round_snapshot_hash,
                "trial_plan_revision_global_id": str(value.trial_plan_revision_global_id),
                "trial_plan_revision_snapshot_hash": value.trial_plan_revision_snapshot_hash,
                "conclusion_revision": str(value.conclusion_revision_global_id),
                "conclusion_revision_global_id": str(value.conclusion_revision_global_id),
                "conclusion_version": value.conclusion_version,
                "conclusion_snapshot_hash": value.conclusion_snapshot_hash,
                "conclusion_state": value.conclusion_state.value,
                "conclusion_code": value.conclusion_code.value,
                "source_manifest": canonical_json(payload["sourceManifest"]),
                "source_manifest_hash": value.source_manifest_hash,
                "presentation_projection": canonical_json(payload["presentationProjection"]),
                "presentation_projection_hash": value.presentation_projection_hash,
                "redaction_manifest": canonical_json(payload["redactionManifest"]),
                "redaction_manifest_hash": value.redaction_manifest_hash,
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "summary_snapshot": canonical_json(
                    payload | {"snapshotHash": value.snapshot_hash}
                ),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()
