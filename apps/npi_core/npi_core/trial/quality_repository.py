from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.tooling.engineering_controls_domain import (
    ToolingDefectRevision,
    defect_revision_from_snapshot,
    validate_tooling_defect_successor,
)
from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility
from npi_core.trial.domain import TrialRound, TrialRoundState
from npi_core.trial.execution_domain import TrialEvidenceRole, TrialLockedReferenceKind
from npi_core.trial.execution_repository import (
    FrappeTrialExecutionRepository,
    TrialExecutionCommandOutcome,
)
from npi_core.trial.frappe_repository import (
    _database_datetime,
    _json_object,
    _optional_doc,
    _payload_hash,
    _round_response,
)
from npi_core.trial.frappe_validation import trial_command_write
from npi_core.trial.quality_diagnostics import quality_type_error_stage
from npi_core.trial.quality_domain import (
    TrialCavityMeasurement,
    TrialCavityResultRevision,
    TrialDefectAction,
    TrialDefectPredecessorKind,
    TrialDefectRevision,
    TrialDefectVerificationResult,
    TrialDefectVerificationRevision,
    TrialQualityConflict,
    TrialQualityEvidenceReference,
    TrialQualityReferenceUnavailable,
    cavity_result_from_snapshot,
    trial_defect_from_snapshot,
    validate_cavity_result_successor,
    validate_trial_defect_successor,
    validate_trial_defect_verification,
    verification_from_snapshot,
)


_MAX_CAVITY_RESULTS = 5_000
_MAX_DEFECTS = 5_000
_MAX_VERIFICATIONS = 5_000


def _member_effective_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


class FrappeTrialQualityRepository(FrappeTrialExecutionRepository):
    """Project-first P7-03 quality boundary with one P6/P7 defect tip."""

    def quality_workspace(
        self,
        project_id: UUID,
        round_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        round_pair = self._execution_round(project, round_id)
        if round_pair is None:
            return None
        return self._quality_workspace_for(project, round_pair[1])

    def create_cavity_result(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_round_snapshot_hash: str,
        expected_input_lock_revision_id: UUID,
        expected_input_lock_revision_snapshot_hash: str,
        sample_batch_revision_id: UUID,
        expected_sample_batch_revision_snapshot_hash: str,
        cavity_id: UUID,
        measurements: Sequence[Mapping[str, Any]],
        evidence: Sequence[Mapping[str, Any]],
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedRoundSnapshotHash": expected_round_snapshot_hash,
            "expectedInputLockRevisionGlobalId": expected_input_lock_revision_id,
            "expectedInputLockRevisionSnapshotHash": expected_input_lock_revision_snapshot_hash,
            "sampleBatchRevisionGlobalId": sample_batch_revision_id,
            "expectedSampleBatchRevisionSnapshotHash": expected_sample_batch_revision_snapshot_hash,
            "cavityGlobalId": cavity_id,
            "measurements": measurements,
            "evidence": evidence,
            "reason": reason,
        }
        project, replay, payload_hash = self._command_start(
            project_id,
            "trial_cavity_result.create",
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        trial_round, input_lock = self._exact_running_context(
            project,
            round_id,
            expected_round_optimistic_version,
            expected_round_snapshot_hash,
            expected_input_lock_revision_id,
            expected_input_lock_revision_snapshot_hash,
        )
        sample = self._exact_quality_sample(
            project,
            round_id,
            sample_batch_revision_id,
            expected_sample_batch_revision_snapshot_hash,
            cavity_id,
        )
        tooling_revision, tooling_set = self._locked_tooling_context(input_lock, cavity_id)
        exact_evidence = self._exact_quality_evidence(
            project,
            round_id,
            evidence,
            sample_revision_id=sample.global_id,
            require_measurement_report=True,
        )
        if self._cavity_result_chain(project, round_id, cavity_id=cavity_id):
            raise TrialQualityConflict()
        now = datetime.now(UTC)
        value = TrialCavityResultRevision(
            global_id=uuid4(),
            cavity_result_global_id=uuid4(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            trial_round_global_id=round_id,
            input_lock_revision_global_id=input_lock.global_id,
            input_lock_revision_snapshot_hash=input_lock.snapshot_hash,
            sample_batch_revision_global_id=sample.global_id,
            sample_batch_revision_snapshot_hash=sample.snapshot_hash,
            tooling_revision_global_id=tooling_revision.global_id,
            tooling_revision_snapshot_hash=tooling_revision.snapshot_hash,
            tooling_set_global_id=tooling_set.global_id,
            tooling_set_snapshot_hash=tooling_set.snapshot_hash,
            cavity_global_id=cavity_id,
            result_version=1,
            predecessor_global_id=None,
            predecessor_snapshot_hash=None,
            measurements=self._cavity_measurements(measurements),
            evidence=exact_evidence,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        return self._persist_quality_command(
            project,
            trial_round,
            operation="trial_cavity_result.create",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_cavity_result_revision",
            target=value,
            insert=self._insert_cavity_result,
            now=now,
        )

    def revise_cavity_result(
        self,
        project_id: UUID,
        round_id: UUID,
        cavity_result_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_round_snapshot_hash: str,
        expected_input_lock_revision_id: UUID,
        expected_input_lock_revision_snapshot_hash: str,
        expected_revision_id: UUID,
        expected_revision_snapshot_hash: str,
        expected_result_version: int,
        measurements: Sequence[Mapping[str, Any]],
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "cavityResultGlobalId": cavity_result_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedRoundSnapshotHash": expected_round_snapshot_hash,
            "expectedInputLockRevisionGlobalId": expected_input_lock_revision_id,
            "expectedInputLockRevisionSnapshotHash": expected_input_lock_revision_snapshot_hash,
            "expectedRevisionGlobalId": expected_revision_id,
            "expectedRevisionSnapshotHash": expected_revision_snapshot_hash,
            "expectedResultVersion": expected_result_version,
            "measurements": measurements,
            "reason": reason,
        }
        project, replay, payload_hash = self._command_start(
            project_id,
            "trial_cavity_result.revise",
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        trial_round, input_lock = self._exact_running_context(
            project,
            round_id,
            expected_round_optimistic_version,
            expected_round_snapshot_hash,
            expected_input_lock_revision_id,
            expected_input_lock_revision_snapshot_hash,
        )
        chain = self._cavity_result_chain(
            project,
            round_id,
            cavity_result_id=cavity_result_id,
            for_update=True,
        )
        if not chain:
            raise TrialQualityReferenceUnavailable()
        predecessor = chain[-1]
        if any(
            (
                predecessor.global_id != expected_revision_id,
                predecessor.snapshot_hash != expected_revision_snapshot_hash,
                predecessor.result_version != expected_result_version,
                predecessor.input_lock_revision_global_id != input_lock.global_id,
                predecessor.input_lock_revision_snapshot_hash != input_lock.snapshot_hash,
            )
        ):
            raise TrialQualityConflict()
        now = datetime.now(UTC)
        value = TrialCavityResultRevision(
            global_id=uuid4(),
            cavity_result_global_id=predecessor.cavity_result_global_id,
            tenant_id=predecessor.tenant_id,
            project_global_id=predecessor.project_global_id,
            trial_round_global_id=predecessor.trial_round_global_id,
            input_lock_revision_global_id=predecessor.input_lock_revision_global_id,
            input_lock_revision_snapshot_hash=predecessor.input_lock_revision_snapshot_hash,
            sample_batch_revision_global_id=predecessor.sample_batch_revision_global_id,
            sample_batch_revision_snapshot_hash=predecessor.sample_batch_revision_snapshot_hash,
            tooling_revision_global_id=predecessor.tooling_revision_global_id,
            tooling_revision_snapshot_hash=predecessor.tooling_revision_snapshot_hash,
            tooling_set_global_id=predecessor.tooling_set_global_id,
            tooling_set_snapshot_hash=predecessor.tooling_set_snapshot_hash,
            cavity_global_id=predecessor.cavity_global_id,
            result_version=predecessor.result_version + 1,
            predecessor_global_id=predecessor.global_id,
            predecessor_snapshot_hash=predecessor.snapshot_hash,
            measurements=self._cavity_measurements(measurements),
            evidence=predecessor.evidence,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        validate_cavity_result_successor(predecessor, value)
        return self._persist_quality_command(
            project,
            trial_round,
            operation="trial_cavity_result.revise",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_cavity_result_revision",
            target=value,
            insert=self._insert_cavity_result,
            now=now,
        )

    def create_defect(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        defect_id: UUID | None,
        predecessor: Mapping[str, Any] | None,
        **values: Any,
    ) -> TrialExecutionCommandOutcome | None:
        if (
            predecessor is not None
            and predecessor["kind"] is not TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION
        ):
            raise TrialQualityConflict()
        return self._append_defect(
            project_id,
            round_id,
            defect_id=defect_id,
            predecessor=predecessor,
            operation="trial_defect.create",
            idempotency_key_hash=idempotency_key_hash,
            values=values,
        )

    def revise_defect(
        self,
        project_id: UUID,
        round_id: UUID,
        defect_id: UUID,
        *,
        idempotency_key_hash: str,
        predecessor: Mapping[str, Any],
        **values: Any,
    ) -> TrialExecutionCommandOutcome | None:
        if predecessor["kind"] is not TrialDefectPredecessorKind.TRIAL_DEFECT_REVISION:
            raise TrialQualityConflict()
        return self._append_defect(
            project_id,
            round_id,
            defect_id=defect_id,
            predecessor=predecessor,
            operation="trial_defect.revise",
            idempotency_key_hash=idempotency_key_hash,
            values=values,
        )

    def verify_defect(
        self,
        project_id: UUID,
        round_id: UUID,
        defect_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_defect_revision_id: UUID,
        expected_defect_revision_snapshot_hash: str,
        action_id: UUID,
        verification_id: UUID | None,
        expected_attempt_sequence: int | None,
        target_round_id: UUID,
        expected_target_round_optimistic_version: int,
        expected_target_round_snapshot_hash: str,
        cavity_result_revision_id: UUID,
        expected_cavity_result_revision_snapshot_hash: str,
        verifier_member: Mapping[str, Any],
        result: TrialDefectVerificationResult,
        finding: str,
        observed_at: datetime,
        evidence: Sequence[Mapping[str, Any]],
    ) -> TrialExecutionCommandOutcome | None:
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "defectGlobalId": defect_id,
            "expectedDefectRevisionGlobalId": expected_defect_revision_id,
            "expectedDefectRevisionSnapshotHash": expected_defect_revision_snapshot_hash,
            "actionGlobalId": action_id,
            "verificationGlobalId": verification_id,
            "expectedAttemptSequence": expected_attempt_sequence,
            "targetRoundGlobalId": target_round_id,
            "expectedTargetRoundOptimisticVersion": expected_target_round_optimistic_version,
            "expectedTargetRoundSnapshotHash": expected_target_round_snapshot_hash,
            "cavityResultRevisionGlobalId": cavity_result_revision_id,
            "expectedCavityResultRevisionSnapshotHash": expected_cavity_result_revision_snapshot_hash,
            "verifierMember": verifier_member,
            "result": result.value,
            "finding": finding,
            "observedAt": observed_at,
            "evidence": evidence,
        }
        project, replay, payload_hash = self._command_start(
            project_id,
            "trial_defect.verify",
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        round_pair = self._execution_round(project, round_id, for_update=True)
        if round_pair is None:
            raise TrialQualityReferenceUnavailable()
        trial_round = round_pair[1]
        if any(
            (
                target_round_id != round_id,
                trial_round.current_state is not TrialRoundState.RUNNING,
                trial_round.optimistic_version != expected_target_round_optimistic_version,
                trial_round.snapshot_hash != expected_target_round_snapshot_hash,
            )
        ):
            raise TrialQualityConflict()
        defect_chain = self._trial_defect_chain(project, defect_id=defect_id, for_update=True)
        if not defect_chain:
            raise TrialQualityReferenceUnavailable()
        defect = defect_chain[-1]
        if (
            defect.global_id != expected_defect_revision_id
            or defect.snapshot_hash != expected_defect_revision_snapshot_hash
        ):
            raise TrialQualityConflict()
        cavity_result = self._exact_cavity_result(
            project,
            round_id,
            cavity_result_revision_id,
            expected_cavity_result_revision_snapshot_hash,
        )
        exact_verifier = self._exact_member(project, verifier_member)
        exact_evidence = self._exact_quality_evidence(
            project,
            round_id,
            evidence,
            sample_revision_id=cavity_result.sample_batch_revision_global_id,
            require_measurement_report=False,
        )
        previous = self._verification_chain(
            project,
            defect_id=defect_id,
            verification_id=verification_id,
            for_update=True,
        )
        if verification_id is None:
            if expected_attempt_sequence is not None:
                raise TrialQualityConflict()
            stable_id, attempt = uuid4(), 1
        else:
            if not previous or previous[-1].attempt_sequence != expected_attempt_sequence:
                raise TrialQualityConflict()
            if any(
                (
                    previous[-1].defect_global_id != defect_id,
                    previous[-1].action_global_id != action_id,
                    previous[-1].target_round_global_id != target_round_id,
                )
            ):
                raise TrialQualityConflict()
            stable_id, attempt = verification_id, previous[-1].attempt_sequence + 1
        now = datetime.now(UTC)
        value = TrialDefectVerificationRevision(
            global_id=uuid4(),
            verification_global_id=stable_id,
            attempt_sequence=attempt,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            defect_global_id=defect_id,
            defect_revision_global_id=defect.global_id,
            defect_revision_snapshot_hash=defect.snapshot_hash,
            action_global_id=action_id,
            target_round_global_id=target_round_id,
            target_round_optimistic_version=trial_round.optimistic_version,
            target_round_snapshot_hash=trial_round.snapshot_hash,
            verification_round_global_id=round_id,
            verification_round_optimistic_version=trial_round.optimistic_version,
            verification_round_snapshot_hash=trial_round.snapshot_hash,
            cavity_result_revision_global_id=cavity_result.global_id,
            cavity_result_revision_snapshot_hash=cavity_result.snapshot_hash,
            verifier_member=exact_verifier,
            result=result,
            finding=finding,
            observed_at=observed_at,
            evidence=exact_evidence,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        validate_trial_defect_verification(defect, cavity_result, value)
        return self._persist_quality_command(
            project,
            trial_round,
            operation="trial_defect.verify",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_defect_verification_revision",
            target=value,
            insert=self._insert_verification,
            now=now,
        )

    def _append_defect(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        defect_id: UUID | None,
        predecessor: Mapping[str, Any] | None,
        operation: str,
        idempotency_key_hash: str,
        values: Mapping[str, Any],
    ) -> TrialExecutionCommandOutcome | None:
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "defectGlobalId": defect_id,
            "predecessor": predecessor,
            **values,
        }
        project, replay, payload_hash = self._command_start(
            project_id,
            operation,
            idempotency_key_hash,
            payload,
        )
        if project is None or replay is not None:
            return None if project is None else TrialExecutionCommandOutcome(replay, replayed=True)
        trial_round, input_lock = self._exact_running_context(
            project,
            round_id,
            values["expected_round_optimistic_version"],
            values["expected_round_snapshot_hash"],
            values["expected_input_lock_revision_id"],
            values["expected_input_lock_revision_snapshot_hash"],
        )
        tooling_revision, tooling_set = self._locked_tooling_context(
            input_lock,
            values["cavity_id"],
        )
        sample = None
        if values["sample_batch_revision_id"] is not None:
            sample = self._exact_quality_sample(
                project,
                round_id,
                values["sample_batch_revision_id"],
                values["expected_sample_batch_revision_snapshot_hash"],
                values["cavity_id"],
            )
        stable_id, exact_predecessor = self._exact_defect_tip(
            project,
            trial_round.tooling_master_global_id,
            defect_id,
            predecessor,
        )
        with quality_type_error_stage("P703_QUALITY_MEMBER_RESOLVE", self.trace_id):
            exact_member = (
                None
                if values["responsible_member"] is None
                else self._exact_member(project, values["responsible_member"])
            )
        with quality_type_error_stage("P703_QUALITY_ACTION_RESOLVE", self.trace_id):
            actions = self._exact_actions(
                project,
                trial_round.tooling_master_global_id,
                exact_predecessor,
                values["actions"],
            )
        evidence = self._merged_defect_evidence(
            project,
            round_id,
            exact_predecessor,
            values["evidence"],
            sample.global_id if sample else None,
        )
        now = datetime.now(UTC)
        with quality_type_error_stage("P703_QUALITY_DEFECT_BUILD", self.trace_id):
            value = TrialDefectRevision(
                global_id=uuid4(),
                defect_global_id=stable_id,
                tenant_id=str(project.tenant_id),
                project_global_id=project_id,
                tooling_master_global_id=trial_round.tooling_master_global_id,
                trial_round_global_id=round_id,
                trial_round_optimistic_version=trial_round.optimistic_version,
                trial_round_snapshot_hash=trial_round.snapshot_hash,
                input_lock_revision_global_id=input_lock.global_id,
                input_lock_revision_snapshot_hash=input_lock.snapshot_hash,
                tooling_revision_global_id=tooling_revision.global_id,
                tooling_revision_snapshot_hash=tooling_revision.snapshot_hash,
                tooling_set_global_id=tooling_set.global_id,
                tooling_set_snapshot_hash=tooling_set.snapshot_hash,
                cavity_global_id=values["cavity_id"],
                sample_batch_revision_global_id=sample.global_id if sample else None,
                sample_batch_revision_snapshot_hash=sample.snapshot_hash if sample else None,
                defect_version=(
                    1
                    if exact_predecessor is None
                    else exact_predecessor.defect_version + 1
                ),
                predecessor_kind=(
                    None
                    if exact_predecessor is None
                    else (
                        TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION
                        if isinstance(exact_predecessor, ToolingDefectRevision)
                        else TrialDefectPredecessorKind.TRIAL_DEFECT_REVISION
                    )
                ),
                predecessor_global_id=(
                    exact_predecessor.global_id if exact_predecessor else None
                ),
                predecessor_snapshot_hash=(
                    exact_predecessor.snapshot_hash if exact_predecessor else None
                ),
                business_code=values["business_code"],
                title=values["title"],
                description=values["description"],
                category_key=values["category_key"],
                location=values["location"],
                severity=values["severity"],
                blocking=values["blocking"],
                state=values["state"],
                root_cause_state=values["root_cause_state"],
                root_cause=values["root_cause"],
                responsible_member=exact_member,
                occurrence_count=values["occurrence_count"],
                actions=actions,
                evidence=evidence,
                reason=values["reason"],
                created_by_user_id=self.actor,
                created_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
            )
        if exact_predecessor is not None:
            with quality_type_error_stage(
                "P703_QUALITY_DEFECT_SUCCESSOR_VALIDATE",
                self.trace_id,
            ):
                validate_trial_defect_successor(exact_predecessor, value)
        return self._persist_quality_command(
            project,
            trial_round,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
            target_type="trial_defect_revision",
            target=value,
            insert=self._insert_defect,
            now=now,
        )

    def _command_start(self, project_id, operation, key_hash, payload):
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None, None, ""
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(project, operation, key_hash, payload_hash)
        if replay is None:
            require_mutable_project(project)
        return project, replay, payload_hash

    def _persist_quality_command(
        self,
        project,
        trial_round,
        *,
        operation,
        idempotency_key_hash,
        payload_hash,
        target_type,
        target,
        insert,
        now,
    ) -> TrialExecutionCommandOutcome:
        with trial_command_write():
            with quality_type_error_stage(
                "P703_QUALITY_RECEIPT_INSERT",
                self.trace_id,
            ):
                receipt = self._insert_receipt(
                    project,
                    operation=operation,
                    idempotency_key_hash=idempotency_key_hash,
                    payload_hash=payload_hash,
                    created_at=now,
                )
            if isinstance(receipt, dict):
                return TrialExecutionCommandOutcome(receipt, replayed=True)
            with quality_type_error_stage("P703_QUALITY_TARGET_INSERT", self.trace_id):
                insert(target)
            with quality_type_error_stage("P703_QUALITY_AUDIT_APPEND", self.trace_id):
                self._append_audit(
                    operation=operation,
                    global_id=target.global_id,
                    object_version=(
                        target.result_version
                        if isinstance(target, TrialCavityResultRevision)
                        else (
                            target.defect_version
                            if isinstance(target, TrialDefectRevision)
                            else target.attempt_sequence
                        )
                    ),
                    summary={
                        "projectId": str(project.global_id),
                        "trialRoundGlobalId": str(trial_round.global_id),
                        "snapshotHash": target.snapshot_hash,
                        "requestId": self.request_id,
                    },
                )
            with quality_type_error_stage("P703_QUALITY_RESPONSE_BUILD", self.trace_id):
                response = self._quality_workspace_for(project, trial_round)
            with quality_type_error_stage("P703_QUALITY_RECEIPT_SEAL", self.trace_id):
                self._seal_receipt(
                    receipt,
                    target_object_type=target_type,
                    target_global_id=target.global_id,
                    response=response,
                    updated_at=now,
                )
        return TrialExecutionCommandOutcome(response)

    def _exact_running_context(
        self,
        project,
        round_id,
        expected_round_version,
        expected_round_hash,
        expected_lock_id,
        expected_lock_hash,
    ):
        round_pair = self._execution_round(project, round_id, for_update=True)
        if round_pair is None:
            raise TrialQualityReferenceUnavailable()
        trial_round = round_pair[1]
        if any(
            (
                trial_round.current_state is not TrialRoundState.RUNNING,
                trial_round.optimistic_version != expected_round_version,
                trial_round.snapshot_hash != expected_round_hash,
            )
        ):
            raise TrialQualityConflict()
        input_lock = self._current_input_lock(project, round_id, for_update=True)
        if (
            input_lock is None
            or input_lock.global_id != expected_lock_id
            or input_lock.snapshot_hash != expected_lock_hash
        ):
            raise TrialQualityConflict()
        return trial_round, input_lock

    @staticmethod
    def _locked_tooling_context(input_lock, cavity_id):
        by_kind: dict[TrialLockedReferenceKind, list[Any]] = {}
        for reference in input_lock.references:
            by_kind.setdefault(reference.kind, []).append(reference)
        required = (
            TrialLockedReferenceKind.TOOLING_REVISION,
            TrialLockedReferenceKind.TOOLING_SET,
            TrialLockedReferenceKind.CAVITY,
        )
        if any(len(by_kind.get(kind, ())) != 1 for kind in required):
            raise TrialQualityReferenceUnavailable()
        if by_kind[TrialLockedReferenceKind.CAVITY][0].global_id != cavity_id:
            raise TrialQualityReferenceUnavailable()
        return (
            by_kind[TrialLockedReferenceKind.TOOLING_REVISION][0],
            by_kind[TrialLockedReferenceKind.TOOLING_SET][0],
        )

    def _exact_quality_sample(self, project, round_id, revision_id, snapshot_hash, cavity_id):
        sample = self._exact_sample_revision(project, round_id, revision_id)
        if (
            sample is None
            or sample.snapshot_hash != snapshot_hash
            or cavity_id not in sample.cavity_global_ids
        ):
            raise TrialQualityReferenceUnavailable()
        return sample

    def _exact_quality_evidence(
        self,
        project,
        round_id,
        supplied,
        *,
        sample_revision_id,
        require_measurement_report,
    ) -> tuple[TrialQualityEvidenceReference, ...]:
        available = {value.global_id: value for value in self._evidence_history(project, round_id)}
        exact = []
        for reference in supplied:
            value = available.get(reference["global_id"])
            if (
                value is None
                or value.snapshot_hash != reference["snapshot_hash"]
                or (
                    value.sample_batch_revision_global_id is not None
                    and value.sample_batch_revision_global_id != sample_revision_id
                )
            ):
                raise TrialQualityReferenceUnavailable()
            exact.append(
                TrialQualityEvidenceReference(
                    global_id=value.global_id,
                    snapshot_hash=value.snapshot_hash,
                )
            )
        if require_measurement_report and not any(
            available[value.global_id].role is TrialEvidenceRole.MEASUREMENT_REPORT
            and available[value.global_id].sample_batch_revision_global_id == sample_revision_id
            for value in exact
        ):
            raise TrialQualityReferenceUnavailable()
        return tuple(exact)

    def _merged_defect_evidence(
        self,
        project,
        round_id,
        predecessor,
        supplied,
        sample_revision_id,
    ):
        retained = predecessor.evidence if isinstance(predecessor, TrialDefectRevision) else ()
        new_values = self._exact_quality_evidence(
            project,
            round_id,
            supplied,
            sample_revision_id=sample_revision_id,
            require_measurement_report=False,
        )
        merged = {value.global_id: value for value in retained}
        for value in new_values:
            if value.global_id in merged and merged[value.global_id] != value:
                raise TrialQualityConflict()
            merged[value.global_id] = value
        return tuple(merged.values())

    def _exact_member(self, project, supplied) -> ProjectMemberResponsibility:
        member = _optional_doc("NPI Project Member", str(supplied["global_id"]))
        if member is None:
            raise TrialQualityReferenceUnavailable()
        today = datetime.now(UTC).date()
        effective_from = _member_effective_date(
            getattr(member, "effective_from", None)
        )
        if any(
            (
                str(member.global_id) != str(supplied["global_id"]),
                str(member.tenant_id) != str(project.tenant_id),
                str(member.project_global_id) != str(project.global_id),
                int(member.optimistic_version) != supplied["optimistic_version"],
                getattr(member, "effective_to", None) not in (None, ""),
                effective_from is None or effective_from > today,
            )
        ):
            raise TrialQualityReferenceUnavailable()
        return ProjectMemberResponsibility(
            global_id=UUID(str(member.global_id)),
            user_id=str(member.user_id),
            optimistic_version=int(member.optimistic_version),
        )

    def _exact_actions(self, project, tooling_master_id, predecessor, supplied):
        retained = (
            {value.global_id: value for value in predecessor.actions}
            if isinstance(predecessor, TrialDefectRevision)
            else {}
        )
        result = dict(retained)
        for item in supplied:
            global_id = item["global_id"] or uuid4()
            member = self._exact_member(project, item["responsible_member"])
            target_pair = self._execution_round(project, item["target_round_id"])
            if target_pair is None:
                raise TrialQualityReferenceUnavailable()
            target = target_pair[1]
            if (
                target.tooling_master_global_id != tooling_master_id
                or target.optimistic_version != item["target_round_optimistic_version"]
                or target.snapshot_hash != item["target_round_snapshot_hash"]
            ):
                raise TrialQualityConflict()
            verification_id = item["verification_revision_id"]
            verification_hash = item["verification_revision_snapshot_hash"]
            if verification_id is not None:
                if not isinstance(predecessor, TrialDefectRevision):
                    raise TrialQualityReferenceUnavailable()
                document = _optional_doc(
                    "NPI Trial Defect Verification Revision",
                    str(verification_id),
                )
                if document is None:
                    raise TrialQualityReferenceUnavailable()
                verification = verification_from_snapshot(_json_object(document.verification_snapshot))
                chain = self._verification_chain(
                    project,
                    defect_id=verification.defect_global_id,
                    verification_id=verification.verification_global_id,
                )
                if any(
                    (
                        verification.snapshot_hash != str(document.snapshot_hash),
                        verification.snapshot_hash != verification_hash,
                        verification.tenant_id != str(project.tenant_id),
                        verification.project_global_id != UUID(str(project.global_id)),
                        verification.defect_global_id != predecessor.defect_global_id,
                        verification.action_global_id != global_id,
                        verification.target_round_global_id != target.global_id,
                        verification.target_round_optimistic_version
                        != target.optimistic_version,
                        verification.target_round_snapshot_hash != target.snapshot_hash,
                        verification.result is not TrialDefectVerificationResult.PASS,
                        not chain or chain[-1].global_id != verification.global_id,
                    )
                ):
                    raise TrialQualityReferenceUnavailable()
            result[global_id] = TrialDefectAction(
                global_id=global_id,
                action_type=item["action_type"],
                state=item["state"],
                detail=item["detail"],
                responsible_member=member,
                due_date=item["due_date"],
                target_round_global_id=target.global_id,
                target_round_optimistic_version=target.optimistic_version,
                target_round_snapshot_hash=target.snapshot_hash,
                verification_revision_global_id=verification_id,
                verification_revision_snapshot_hash=verification_hash,
            )
        return tuple(result.values())

    def _cavity_measurements(self, values):
        return tuple(
            TrialCavityMeasurement(
                **value,
                observed_by_user_id=self.actor,
            )
            for value in values
        )

    def _exact_defect_tip(self, project, tooling_master_id, defect_id, expected):
        if defect_id is None:
            if expected is not None:
                raise TrialQualityConflict()
            return uuid4(), None
        p6 = self._tooling_defect_chain(project, tooling_master_id, defect_id=defect_id)
        p7 = self._trial_defect_chain(project, defect_id=defect_id, for_update=True)
        current = p7[-1] if p7 else (p6[-1] if p6 else None)
        if current is None or expected is None:
            raise TrialQualityConflict()
        kind = (
            TrialDefectPredecessorKind.TRIAL_DEFECT_REVISION
            if isinstance(current, TrialDefectRevision)
            else TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION
        )
        if any(
            (
                expected["kind"] is not kind,
                expected["global_id"] != current.global_id,
                expected["snapshot_hash"] != current.snapshot_hash,
                expected["defect_version"] != current.defect_version,
            )
        ):
            raise TrialQualityConflict()
        return defect_id, current

    def _cavity_result_chain(
        self,
        project,
        round_id,
        *,
        cavity_result_id=None,
        cavity_id=None,
        for_update=False,
    ):
        filters = self._quality_filters(project, trial_round_global_id=round_id)
        if cavity_result_id is not None:
            filters["cavity_result_global_id"] = str(cavity_result_id)
        if cavity_id is not None:
            filters["cavity_global_id"] = str(cavity_id)
        documents = self._quality_documents(
            "NPI Trial Cavity Result Revision",
            filters,
            "result_version asc, global_id asc",
            _MAX_CAVITY_RESULTS,
            for_update,
        )
        values = tuple(
            cavity_result_from_snapshot(_json_object(value.cavity_result_snapshot))
            for value in documents
        )
        if any(
            parsed.snapshot_hash != str(document.snapshot_hash)
            for parsed, document in zip(values, documents, strict=True)
        ):
            raise RuntimeError("Persisted Trial cavity result integrity failed.")
        self._validate_cavity_chains(values)
        return values

    def _trial_defect_chain(self, project, *, defect_id=None, for_update=False):
        filters = self._quality_filters(project)
        if defect_id is not None:
            filters["defect_global_id"] = str(defect_id)
        documents = self._quality_documents(
            "NPI Trial Defect Revision",
            filters,
            "defect_global_id asc, defect_version asc, global_id asc",
            _MAX_DEFECTS,
            for_update,
        )
        values = tuple(
            trial_defect_from_snapshot(_json_object(value.trial_defect_snapshot))
            for value in documents
        )
        if any(
            parsed.snapshot_hash != str(document.snapshot_hash)
            for parsed, document in zip(values, documents, strict=True)
        ):
            raise RuntimeError("Persisted Trial defect integrity failed.")
        self._validate_trial_defect_chains(project, values)
        return values

    def _tooling_defect_chain(self, project, tooling_master_id, *, defect_id=None):
        filters = self._quality_filters(
            project,
            tooling_master_global_id=tooling_master_id,
        )
        if defect_id is not None:
            filters["defect_global_id"] = str(defect_id)
        documents = self._quality_documents(
            "NPI Tooling Defect Revision",
            filters,
            "defect_global_id asc, defect_version asc, global_id asc",
            _MAX_DEFECTS,
            False,
        )
        values = tuple(
            defect_revision_from_snapshot(_json_object(value.defect_snapshot))
            for value in documents
        )
        if any(
            parsed.snapshot_hash != str(document.snapshot_hash)
            for parsed, document in zip(values, documents, strict=True)
        ):
            raise RuntimeError("Persisted Tooling defect integrity failed.")
        groups: dict[UUID, list[ToolingDefectRevision]] = {}
        for value in values:
            groups.setdefault(value.defect_global_id, []).append(value)
        for chain in groups.values():
            if chain[0].defect_version != 1:
                raise RuntimeError("Persisted Tooling defect chain does not start at one.")
            for current, successor in zip(chain, chain[1:], strict=False):
                validate_tooling_defect_successor(current, successor)
        return values

    def _verification_chain(self, project, *, defect_id=None, verification_id=None, for_update=False):
        filters = self._quality_filters(project)
        if defect_id is not None:
            filters["defect_global_id"] = str(defect_id)
        if verification_id is not None:
            filters["verification_global_id"] = str(verification_id)
        documents = self._quality_documents(
            "NPI Trial Defect Verification Revision",
            filters,
            "verification_global_id asc, attempt_sequence asc, global_id asc",
            _MAX_VERIFICATIONS,
            for_update,
        )
        values = tuple(
            verification_from_snapshot(_json_object(value.verification_snapshot))
            for value in documents
        )
        if any(
            parsed.snapshot_hash != str(document.snapshot_hash)
            for parsed, document in zip(values, documents, strict=True)
        ):
            raise RuntimeError("Persisted Trial verification integrity failed.")
        groups: dict[UUID, list[TrialDefectVerificationRevision]] = {}
        for value in values:
            groups.setdefault(value.verification_global_id, []).append(value)
        for chain in groups.values():
            if [item.attempt_sequence for item in chain] != list(range(1, len(chain) + 1)):
                raise RuntimeError("Persisted Trial verification chain is not contiguous.")
        return values

    def _quality_documents(self, doctype, filters, order_by, maximum, for_update):
        names = frappe.get_all(
            doctype,
            filters=filters,
            pluck="name",
            order_by=order_by,
            limit_page_length=maximum + 1,
        )
        if len(names) > maximum:
            raise RuntimeError(f"Persisted {doctype} collection exceeds its safe bound.")
        return tuple(
            frappe.get_doc(doctype, str(name), for_update=for_update)
            for name in names
        )

    @staticmethod
    def _quality_filters(project, **values):
        return {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            **{key: str(value) for key, value in values.items()},
        }

    @staticmethod
    def _validate_cavity_chains(values):
        groups: dict[UUID, list[TrialCavityResultRevision]] = {}
        context_owners: dict[tuple[UUID, UUID], UUID] = {}
        for value in values:
            groups.setdefault(value.cavity_result_global_id, []).append(value)
            context = (value.trial_round_global_id, value.cavity_global_id)
            owner = context_owners.setdefault(context, value.cavity_result_global_id)
            if owner != value.cavity_result_global_id:
                raise RuntimeError("Persisted Trial cavity context has multiple result identities.")
        for chain in groups.values():
            if chain[0].result_version != 1:
                raise RuntimeError("Persisted Trial cavity result chain does not start at one.")
            for current, successor in zip(chain, chain[1:], strict=False):
                validate_cavity_result_successor(current, successor)

    def _validate_trial_defect_chains(self, project, values):
        groups: dict[UUID, list[TrialDefectRevision]] = {}
        for value in values:
            groups.setdefault(value.defect_global_id, []).append(value)
        for defect_id, chain in groups.items():
            first = chain[0]
            if first.defect_version == 1:
                if first.predecessor_kind is not None:
                    raise RuntimeError("Persisted Trial defect chain has an invalid first tip.")
            else:
                p6 = self._tooling_defect_chain(
                    project,
                    first.tooling_master_global_id,
                    defect_id=defect_id,
                )
                if not p6:
                    raise RuntimeError("Persisted Trial defect chain lost its Tooling predecessor.")
                validate_trial_defect_successor(p6[-1], first)
            for current, successor in zip(chain, chain[1:], strict=False):
                validate_trial_defect_successor(current, successor)

    def _exact_cavity_result(self, project, round_id, revision_id, snapshot_hash):
        document = _optional_doc("NPI Trial Cavity Result Revision", str(revision_id))
        if document is None:
            raise TrialQualityReferenceUnavailable()
        value = cavity_result_from_snapshot(_json_object(document.cavity_result_snapshot))
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
            raise TrialQualityReferenceUnavailable()
        return value

    def _quality_workspace_for(self, project, trial_round: TrialRound):
        cavity_results = self._cavity_result_chain(project, trial_round.global_id)
        trial_defects = self._trial_defect_chain(project)
        relevant_ids = {
            value.defect_global_id
            for value in trial_defects
            if value.trial_round_global_id == trial_round.global_id
        }
        tooling_defects = self._tooling_defect_chain(
            project,
            trial_round.tooling_master_global_id,
        )
        relevant_ids.update(value.defect_global_id for value in tooling_defects)
        defects = tuple(
            value for value in (*tooling_defects, *trial_defects) if value.defect_global_id in relevant_ids
        )
        verifications = tuple(
            value
            for value in self._verification_chain(project)
            if value.defect_global_id in relevant_ids
        )
        can_change = self._is_internal_system_manager() and trial_round.current_state is TrialRoundState.RUNNING
        return {
            "projectGlobalId": str(project.global_id),
            "trialRound": _round_response(trial_round),
            "cavityResultRevisions": [self._snapshot_response(value) for value in cavity_results],
            "defectRevisions": [
                {
                    "source": "trial" if isinstance(value, TrialDefectRevision) else "tooling",
                    "revision": self._snapshot_response(value),
                }
                for value in defects
            ],
            "verificationRevisions": [self._snapshot_response(value) for value in verifications],
            "cavityFilters": self._cavity_filters(cavity_results, trial_defects),
            "pareto": self._pareto(trial_defects),
            "permissions": {
                "view": True,
                "recordCavityResult": can_change,
                "manageDefects": can_change,
                "verifyDefects": can_change,
            },
            "externalEffects": {
                "ncr": "unavailable",
                "qualityInspection": "unavailable",
                "gate": "unavailable",
                "toolingLifecycle": "unavailable",
            },
        }

    @staticmethod
    def _snapshot_response(value):
        return value.snapshot_payload() | {
            "versionKeyHash": value.version_key_hash,
            "snapshotHash": value.snapshot_hash,
        }

    @staticmethod
    def _cavity_filters(results, defects):
        ids = {value.cavity_global_id for value in results}
        ids.update(value.cavity_global_id for value in defects)
        return [{"globalId": str(value)} for value in sorted(ids, key=str)]

    @staticmethod
    def _pareto(defects):
        tips: dict[tuple[UUID, UUID, UUID], TrialDefectRevision] = {}
        for value in defects:
            key = (
                value.defect_global_id,
                value.trial_round_global_id,
                value.cavity_global_id,
            )
            if key not in tips or tips[key].defect_version < value.defect_version:
                tips[key] = value
        rows: dict[tuple[str, str, str], int] = {}
        for value in tips.values():
            key = (value.category_key, value.severity.value, str(value.cavity_global_id))
            rows[key] = rows.get(key, 0) + value.occurrence_count
        return [
            {
                "categoryKey": key[0],
                "severity": key[1],
                "cavityGlobalId": key[2],
                "count": count,
            }
            for key, count in sorted(rows.items(), key=lambda item: (-item[1], item[0]))
        ]

    @staticmethod
    def _insert_cavity_result(value):
        frappe.get_doc(
            {
                "doctype": "NPI Trial Cavity Result Revision",
                "global_id": str(value.global_id),
                "cavity_result_global_id": str(value.cavity_result_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "input_lock_revision": str(value.input_lock_revision_global_id),
                "input_lock_revision_global_id": str(value.input_lock_revision_global_id),
                "input_lock_revision_snapshot_hash": value.input_lock_revision_snapshot_hash,
                "sample_batch_revision": str(value.sample_batch_revision_global_id),
                "sample_batch_revision_global_id": str(value.sample_batch_revision_global_id),
                "sample_batch_revision_snapshot_hash": value.sample_batch_revision_snapshot_hash,
                "tooling_revision": str(value.tooling_revision_global_id),
                "tooling_revision_global_id": str(value.tooling_revision_global_id),
                "tooling_revision_snapshot_hash": value.tooling_revision_snapshot_hash,
                "tooling_set": str(value.tooling_set_global_id),
                "tooling_set_global_id": str(value.tooling_set_global_id),
                "tooling_set_snapshot_hash": value.tooling_set_snapshot_hash,
                "cavity_global_id": str(value.cavity_global_id),
                "result_version": value.result_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "measurement_snapshot": [item.snapshot_payload() for item in value.measurements],
                "evidence_snapshot": [item.snapshot_payload() for item in value.evidence],
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "cavity_result_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_defect(value):
        frappe.get_doc(
            {
                "doctype": "NPI Trial Defect Revision",
                "global_id": str(value.global_id),
                "defect_global_id": str(value.defect_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master": str(value.tooling_master_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "trial_round_optimistic_version": value.trial_round_optimistic_version,
                "trial_round_snapshot_hash": value.trial_round_snapshot_hash,
                "input_lock_revision": str(value.input_lock_revision_global_id),
                "input_lock_revision_global_id": str(value.input_lock_revision_global_id),
                "input_lock_revision_snapshot_hash": value.input_lock_revision_snapshot_hash,
                "tooling_revision": str(value.tooling_revision_global_id),
                "tooling_revision_global_id": str(value.tooling_revision_global_id),
                "tooling_revision_snapshot_hash": value.tooling_revision_snapshot_hash,
                "tooling_set": str(value.tooling_set_global_id),
                "tooling_set_global_id": str(value.tooling_set_global_id),
                "tooling_set_snapshot_hash": value.tooling_set_snapshot_hash,
                "cavity_global_id": str(value.cavity_global_id),
                "sample_batch_revision": str(value.sample_batch_revision_global_id) if value.sample_batch_revision_global_id else None,
                "sample_batch_revision_global_id": str(value.sample_batch_revision_global_id) if value.sample_batch_revision_global_id else None,
                "sample_batch_revision_snapshot_hash": value.sample_batch_revision_snapshot_hash,
                "defect_version": value.defect_version,
                "predecessor_kind": value.predecessor_kind.value if value.predecessor_kind else None,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "business_code": value.business_code,
                "title": value.title,
                "description": value.description,
                "category_key": value.category_key,
                "location": value.location,
                "severity": value.severity.value,
                "blocking": value.blocking,
                "state": value.state.value,
                "root_cause_state": value.root_cause_state.value,
                "root_cause": value.root_cause,
                "responsible_member": str(value.responsible_member.global_id) if value.responsible_member else None,
                "responsible_member_global_id": str(value.responsible_member.global_id) if value.responsible_member else None,
                "occurrence_count": value.occurrence_count,
                "action_snapshot": [item.snapshot_payload() for item in value.actions],
                "evidence_snapshot": [item.snapshot_payload() for item in value.evidence],
                "external_effect_snapshot": value.snapshot_payload()["externalEffects"],
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "trial_defect_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_verification(value):
        frappe.get_doc(
            {
                "doctype": "NPI Trial Defect Verification Revision",
                "global_id": str(value.global_id),
                "verification_global_id": str(value.verification_global_id),
                "version_key_hash": value.version_key_hash,
                "attempt_sequence": value.attempt_sequence,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "defect_global_id": str(value.defect_global_id),
                "defect_revision": str(value.defect_revision_global_id),
                "defect_revision_global_id": str(value.defect_revision_global_id),
                "defect_revision_snapshot_hash": value.defect_revision_snapshot_hash,
                "action_global_id": str(value.action_global_id),
                "target_round": str(value.target_round_global_id),
                "target_round_global_id": str(value.target_round_global_id),
                "target_round_optimistic_version": value.target_round_optimistic_version,
                "target_round_snapshot_hash": value.target_round_snapshot_hash,
                "verification_round": str(value.verification_round_global_id),
                "verification_round_global_id": str(value.verification_round_global_id),
                "verification_round_optimistic_version": value.verification_round_optimistic_version,
                "verification_round_snapshot_hash": value.verification_round_snapshot_hash,
                "cavity_result_revision": str(value.cavity_result_revision_global_id),
                "cavity_result_revision_global_id": str(value.cavity_result_revision_global_id),
                "cavity_result_revision_snapshot_hash": value.cavity_result_revision_snapshot_hash,
                "verifier_member": str(value.verifier_member.global_id),
                "verifier_member_global_id": str(value.verifier_member.global_id),
                "result": value.result.value,
                "finding": value.finding,
                "observed_at": _database_datetime(value.observed_at),
                "evidence_snapshot": [item.snapshot_payload() for item in value.evidence],
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "verification_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()
