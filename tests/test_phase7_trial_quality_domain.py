from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.engineering_controls_domain import (
    ToolingDefectActionState,
    ToolingDefectActionType,
    ToolingDefectContextKind,
    ToolingDefectDetectionContext,
    ToolingDefectRevision,
    ToolingDefectRootCauseState,
    ToolingDefectSeverity,
    ToolingDefectState,
)
from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility
from npi_core.trial.quality_domain import (
    TrialCavityMeasurement,
    TrialCavityResultRevision,
    TrialDefectAction,
    TrialDefectPredecessorKind,
    TrialDefectRevision,
    TrialDefectVerificationResult,
    TrialDefectVerificationRevision,
    TrialQualityComparisonState,
    TrialQualityEvidenceReference,
    TrialQualityMeasurementState,
    TrialQualityObservationSource,
    cavity_result_from_snapshot,
    trial_defect_from_snapshot,
    validate_cavity_result_successor,
    validate_trial_defect_successor,
    validate_trial_defect_verification,
    verification_from_snapshot,
)


def uid(value: int) -> UUID:
    return UUID(int=value)


NOW = datetime(2026, 8, 11, 2, 0, tzinfo=UTC)
TENANT = "tenant-a"
PROJECT = uid(1)
MASTER = uid(2)
ROUND = uid(3)
LOCK = uid(4)
SAMPLE = uid(5)
TOOLING_REVISION = uid(6)
TOOLING_SET = uid(7)
CAVITY = uid(8)
RESULT = uid(9)
RESULT_R1 = uid(10)
RESULT_R2 = uid(11)
DEFECT = uid(12)
DEFECT_R1 = uid(13)
DEFECT_R2 = uid(14)
ACTION = uid(15)
OWNER = uid(16)
VERIFIER = uid(17)
EVIDENCE = uid(18)
VERIFICATION = uid(19)
VERIFICATION_R1 = uid(20)
REQUEST = uid(21)


def member(global_id: UUID = OWNER) -> ProjectMemberResponsibility:
    return ProjectMemberResponsibility(
        global_id=global_id,
        user_id=f"member-{global_id.int}@example.invalid",
        optimistic_version=2,
    )


def evidence() -> TrialQualityEvidenceReference:
    return TrialQualityEvidenceReference(global_id=EVIDENCE, snapshot_hash="e" * 64)


def measurement(
    *,
    state: TrialQualityMeasurementState = TrialQualityMeasurementState.MEASURED,
    value: str | None = "10.1",
) -> TrialCavityMeasurement:
    return TrialCavityMeasurement(
        characteristic_key="critical_length",
        label="Critical length",
        unit="mm",
        nominal_value="10.0",
        lower_limit="9.8",
        upper_limit="10.2",
        required=True,
        state=state,
        value=value,
        source=TrialQualityObservationSource.MANUAL,
        observed_at=NOW,
        observed_by_user_id="metrology@example.invalid",
    )


def cavity_result(
    *,
    global_id: UUID = RESULT_R1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
    measurement_value: TrialCavityMeasurement | None = None,
) -> TrialCavityResultRevision:
    return TrialCavityResultRevision(
        global_id=global_id,
        cavity_result_global_id=RESULT,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        trial_round_global_id=ROUND,
        input_lock_revision_global_id=LOCK,
        input_lock_revision_snapshot_hash="1" * 64,
        sample_batch_revision_global_id=SAMPLE,
        sample_batch_revision_snapshot_hash="2" * 64,
        tooling_revision_global_id=TOOLING_REVISION,
        tooling_revision_snapshot_hash="3" * 64,
        tooling_set_global_id=TOOLING_SET,
        tooling_set_snapshot_hash="4" * 64,
        cavity_global_id=CAVITY,
        result_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        measurements=(measurement_value or measurement(),),
        evidence=(evidence(),),
        reason="Record the exact cavity result.",
        created_by_user_id="quality@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p703-cavity-result",
    )


def action(
    *,
    state: ToolingDefectActionState = ToolingDefectActionState.COMPLETED,
    responsible: UUID = OWNER,
    verification_id: UUID | None = None,
    verification_hash: str | None = None,
) -> TrialDefectAction:
    return TrialDefectAction(
        global_id=ACTION,
        action_type=ToolingDefectActionType.CORRECTIVE,
        state=state,
        detail="Correct the exact cavity condition.",
        responsible_member=member(responsible),
        due_date=date(2026, 8, 20),
        target_round_global_id=ROUND,
        target_round_optimistic_version=3,
        target_round_snapshot_hash="5" * 64,
        verification_revision_global_id=verification_id,
        verification_revision_snapshot_hash=verification_hash,
    )


def trial_defect(
    *,
    global_id: UUID = DEFECT_R1,
    version: int = 1,
    predecessor_kind: TrialDefectPredecessorKind | None = None,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
    state: ToolingDefectState = ToolingDefectState.OPEN,
    actions: tuple[TrialDefectAction, ...] = (),
) -> TrialDefectRevision:
    return TrialDefectRevision(
        global_id=global_id,
        defect_global_id=DEFECT,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        trial_round_global_id=ROUND,
        trial_round_optimistic_version=3,
        trial_round_snapshot_hash="5" * 64,
        input_lock_revision_global_id=LOCK,
        input_lock_revision_snapshot_hash="1" * 64,
        tooling_revision_global_id=TOOLING_REVISION,
        tooling_revision_snapshot_hash="3" * 64,
        tooling_set_global_id=TOOLING_SET,
        tooling_set_snapshot_hash="4" * 64,
        cavity_global_id=CAVITY,
        sample_batch_revision_global_id=SAMPLE,
        sample_batch_revision_snapshot_hash="2" * 64,
        defect_version=version,
        predecessor_kind=predecessor_kind,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        business_code="DEF-001",
        title="Short shot at cavity one",
        description="The bounded synthetic defect description.",
        category_key="short_shot",
        location="Gate edge",
        severity=ToolingDefectSeverity.HIGH,
        blocking=False,
        state=state,
        root_cause_state=ToolingDefectRootCauseState.PENDING,
        root_cause=None,
        responsible_member=None if state is ToolingDefectState.OPEN else member(),
        occurrence_count=2,
        actions=actions,
        evidence=(evidence(),),
        reason="Record one immutable Trial defect observation.",
        created_by_user_id="quality@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p703-defect",
    )


def verification(
    defect: TrialDefectRevision,
    result: TrialCavityResultRevision,
    *,
    verifier: UUID = VERIFIER,
) -> TrialDefectVerificationRevision:
    return TrialDefectVerificationRevision(
        global_id=VERIFICATION_R1,
        verification_global_id=VERIFICATION,
        attempt_sequence=1,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        defect_global_id=DEFECT,
        defect_revision_global_id=defect.global_id,
        defect_revision_snapshot_hash=defect.snapshot_hash,
        action_global_id=ACTION,
        target_round_global_id=ROUND,
        target_round_optimistic_version=3,
        target_round_snapshot_hash="5" * 64,
        verification_round_global_id=ROUND,
        verification_round_optimistic_version=3,
        verification_round_snapshot_hash="5" * 64,
        cavity_result_revision_global_id=result.global_id,
        cavity_result_revision_snapshot_hash=result.snapshot_hash,
        verifier_member=member(verifier),
        result=TrialDefectVerificationResult.PASS,
        finding="The corrected cavity result meets the exact specification.",
        observed_at=NOW,
        evidence=(evidence(),),
        created_by_user_id="quality@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p703-verification",
    )


def tooling_defect() -> ToolingDefectRevision:
    return ToolingDefectRevision(
        global_id=uid(30),
        defect_global_id=DEFECT,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        tooling_revision_global_id=TOOLING_REVISION,
        tooling_revision_snapshot_hash="3" * 64,
        cavity_global_id=CAVITY,
        cavity_identifier="CAV-01",
        defect_version=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        business_code="DEF-001",
        title="Tooling defect",
        description="The original Tooling observation.",
        category_key="short_shot",
        severity=ToolingDefectSeverity.HIGH,
        blocking=False,
        state=ToolingDefectState.OPEN,
        detection_context=ToolingDefectDetectionContext(
            kind=ToolingDefectContextKind.TOOLING_REVISION,
            global_id=TOOLING_REVISION,
            snapshot_hash="3" * 64,
        ),
        root_cause_state=ToolingDefectRootCauseState.PENDING,
        root_cause=None,
        responsible_member=None,
        target_round_label="T1",
        actions=(),
        evidence=(),
        reason="Create the original Tooling defect.",
        created_by_user_id="tooling@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p605-defect",
    )


class Phase7TrialQualityDomainTest(unittest.TestCase):
    def test_cavity_measurement_never_imputes_missing_as_zero_or_pass(self) -> None:
        measured = measurement()
        self.assertEqual(measured.comparison_state, TrialQualityComparisonState.WITHIN_SPEC)
        missing = measurement(
            state=TrialQualityMeasurementState.NOT_MEASURED,
            value=None,
        )
        self.assertEqual(missing.comparison_state, TrialQualityComparisonState.NOT_MEASURED)
        self.assertIsNone(missing.snapshot_payload()["value"])
        with self.assertRaises(RequestValidationFailed):
            measurement(
                state=TrialQualityMeasurementState.NOT_MEASURED,
                value="0",
            )

    def test_cavity_result_round_trip_and_successor_keep_exact_context(self) -> None:
        first = cavity_result()
        self.assertEqual(
            cavity_result_from_snapshot(first.snapshot_payload()).snapshot_hash,
            first.snapshot_hash,
        )
        second = cavity_result(
            global_id=RESULT_R2,
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
            measurement_value=measurement(value="9.9"),
        )
        validate_cavity_result_successor(first, second)
        with self.assertRaises(RequestValidationFailed):
            validate_cavity_result_successor(
                first,
                replace(second, cavity_global_id=uid(200)),
            )
        malformed = dict(first.snapshot_payload())
        malformed["qualityResult"] = "pass"
        with self.assertRaises(RequestValidationFailed):
            cavity_result_from_snapshot(malformed)

    def test_tooling_defect_continues_same_identity_without_a_second_aggregate(self) -> None:
        current = tooling_defect()
        successor = trial_defect(
            global_id=DEFECT_R2,
            version=2,
            predecessor_kind=TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION,
            predecessor_global_id=current.global_id,
            predecessor_snapshot_hash=current.snapshot_hash,
            state=ToolingDefectState.ASSIGNED,
        )
        validate_trial_defect_successor(current, successor)
        self.assertEqual(successor.defect_global_id, current.defect_global_id)
        with self.assertRaises(RequestValidationFailed):
            validate_trial_defect_successor(
                current,
                replace(successor, defect_global_id=uid(201)),
            )

    def test_trial_defect_successor_cannot_rebind_round_context_or_actions(self) -> None:
        first = trial_defect(state=ToolingDefectState.OPEN)
        second = trial_defect(
            global_id=DEFECT_R2,
            version=2,
            predecessor_kind=TrialDefectPredecessorKind.TRIAL_DEFECT_REVISION,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
            state=ToolingDefectState.ASSIGNED,
            actions=(action(state=ToolingDefectActionState.PLANNED),),
        )
        validate_trial_defect_successor(first, second)
        self.assertEqual(
            trial_defect_from_snapshot(second.snapshot_payload()).snapshot_hash,
            second.snapshot_hash,
        )
        with self.assertRaises(RequestValidationFailed):
            validate_trial_defect_successor(
                first,
                replace(second, input_lock_revision_global_id=uid(202)),
            )
        third = replace(
            second,
            global_id=uid(203),
            defect_version=3,
            predecessor_global_id=second.global_id,
            predecessor_snapshot_hash=second.snapshot_hash,
            state=ToolingDefectState.IN_PROGRESS,
            actions=(
                replace(
                    second.actions[0],
                    responsible_member=member(uid(204)),
                ),
            ),
            snapshot_hash="",
        )
        with self.assertRaises(RequestValidationFailed):
            validate_trial_defect_successor(second, third)

    def test_verification_is_exact_independent_and_does_not_close_the_defect(self) -> None:
        result = cavity_result()
        defect = trial_defect(
            global_id=DEFECT_R2,
            version=2,
            predecessor_kind=TrialDefectPredecessorKind.TRIAL_DEFECT_REVISION,
            predecessor_global_id=DEFECT_R1,
            predecessor_snapshot_hash="d" * 64,
            state=ToolingDefectState.IN_PROGRESS,
            actions=(action(),),
        )
        attempt = verification(defect, result)
        validate_trial_defect_verification(defect, result, attempt)
        self.assertEqual(defect.state, ToolingDefectState.IN_PROGRESS)
        self.assertEqual(
            verification_from_snapshot(attempt.snapshot_payload()).snapshot_hash,
            attempt.snapshot_hash,
        )
        with self.assertRaises(RequestValidationFailed):
            validate_trial_defect_verification(
                defect,
                result,
                verification(defect, result, verifier=OWNER),
            )
        missing_result = cavity_result(
            measurement_value=measurement(
                state=TrialQualityMeasurementState.NOT_MEASURED,
                value=None,
            )
        )
        with self.assertRaises(RequestValidationFailed):
            validate_trial_defect_verification(
                defect,
                missing_result,
                verification(defect, missing_result),
            )

    def test_external_effects_are_explicitly_unavailable_and_closed(self) -> None:
        defect = trial_defect()
        payload = defect.snapshot_payload()
        self.assertEqual(
            payload["externalEffects"],
            {
                "ncr": "unavailable",
                "qualityInspection": "unavailable",
                "gate": "unavailable",
                "toolingLifecycle": "unavailable",
            },
        )
        payload["externalEffects"] = {"ncr": "created"}
        with self.assertRaises(RequestValidationFailed):
            trial_defect_from_snapshot(payload)


if __name__ == "__main__":
    unittest.main()
