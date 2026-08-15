from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.engineering_controls_domain import ToolingDefectState
from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility
from npi_core.trial.review_domain import (
    TrialCavityResultTip,
    TrialComparisonCellState,
    TrialComparisonMetricKind,
    TrialComparisonState,
    TrialComparisonUnitState,
    TrialConclusionBlockerCode,
    TrialConclusionCapability,
    TrialConclusionCode,
    TrialConclusionPolicyVersion,
    TrialConclusionRevision,
    TrialConclusionRevisionState,
    TrialDefectSourceKind,
    TrialDefectTip,
    TrialDefectTrendState,
    TrialExactReference,
    TrialInputChangeState,
    TrialInputComparisonCell,
    TrialInputComparisonRow,
    TrialMetricComparisonCell,
    TrialMetricComparisonRow,
    TrialPolicyAuthorityBinding,
    TrialReviewReferenceKind,
    TrialReviewReferenceRevision,
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


def uid(value: int) -> UUID:
    return UUID(int=value)


NOW = datetime(2026, 8, 11, 4, 0, tzinfo=UTC)
TENANT = "tenant-a"
PROJECT = uid(1)
PLAN = uid(2)
PLAN_REVISION = uid(3)
POLICY = uid(4)
POLICY_R1 = uid(5)
ROUND_1 = uid(6)
ROUND_2 = uid(7)
CAVITY = uid(8)
COMPARISON = uid(9)
REFERENCE = uid(10)
REFERENCE_R1 = uid(11)
CONCLUSION = uid(12)
CONCLUSION_R1 = uid(13)
REQUEST = uid(14)
TOOLING_MASTER = uid(15)


def exact(value: int, marker: str = "a") -> TrialExactReference:
    return TrialExactReference(uid(value), marker * 64)


def policy() -> TrialConclusionPolicyVersion:
    return TrialConclusionPolicyVersion(
        global_id=POLICY_R1,
        policy_global_id=POLICY,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        trial_plan_global_id=PLAN,
        trial_plan_revision_global_id=PLAN_REVISION,
        trial_plan_revision_snapshot_hash="1" * 64,
        policy_version=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        required_parameter_keys=("injection_pressure",),
        required_dimension_keys=(f"{CAVITY}:critical_length",),
        required_reference_kinds=(TrialReviewReferenceKind.CONTROLLED_QUALITY_REPORT,),
        require_cavity_results=True,
        block_on_open_blocking_defects=True,
        block_on_unverified_required_actions=True,
        allowed_conclusion_codes=tuple(TrialConclusionCode),
        out_of_spec_blocking_codes=(TrialConclusionCode.PASS,),
        authority_bindings=(
            TrialPolicyAuthorityBinding(
                member=ProjectMemberResponsibility(
                    global_id=uid(16),
                    user_id="trial-authority@example.invalid",
                    optimistic_version=3,
                ),
                capabilities=tuple(TrialConclusionCapability),
            ),
        ),
        published_by_user_id="policy-owner@example.invalid",
        published_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p704-policy",
    )


def source(
    sequence: int,
    round_id: UUID,
    *,
    defects: tuple[TrialDefectTip, ...] = (),
    complete: bool = True,
) -> TrialRoundComparisonSource:
    offset = sequence * 20
    return TrialRoundComparisonSource(
        sequence=sequence,
        trial_round_global_id=round_id,
        trial_round_optimistic_version=sequence + 2,
        trial_round_snapshot_hash=str(sequence) * 64,
        trial_plan_revision=exact(100 + offset, "b"),
        input_lock_revision=exact(101 + offset, "c") if complete else None,
        actual_revision=exact(102 + offset, "d") if complete else None,
        sample_revisions=(exact(103 + offset, "e"),),
        cavity_results=(TrialCavityResultTip(CAVITY, exact(104 + offset, "f")),)
        if complete
        else (),
        defect_tips=defects,
    )


def measured(
    round_id: UUID,
    value: str,
    *,
    unit: str = "MPa",
    source_id: int = 200,
    lower: str | None = None,
    upper: str | None = None,
) -> TrialMetricComparisonCell:
    return TrialMetricComparisonCell(
        trial_round_global_id=round_id,
        state=TrialComparisonCellState.MEASURED,
        value=value,
        unit=unit,
        lower_limit=lower,
        upper_limit=upper,
        source_revision=exact(source_id, "6"),
    )


def unavailable(round_id: UUID) -> TrialMetricComparisonCell:
    return TrialMetricComparisonCell(
        trial_round_global_id=round_id,
        state=TrialComparisonCellState.UNAVAILABLE,
        value=None,
        unit=None,
        lower_limit=None,
        upper_limit=None,
        source_revision=None,
    )


def comparison(
    *,
    sources: tuple[TrialRoundComparisonSource, ...] | None = None,
    pressure_target: TrialMetricComparisonCell | None = None,
    dimension_target: TrialMetricComparisonCell | None = None,
) -> TrialRoundComparisonSnapshot:
    source_values = sources or (source(1, ROUND_1), source(2, ROUND_2))
    input_revision_1 = source_values[0].input_lock_revision
    input_revision_2 = source_values[1].input_lock_revision
    rows = (
        TrialInputComparisonRow(
            semantic_key="material.grade",
            cells=(
                TrialInputComparisonCell(ROUND_1, "ABS-A", input_revision_1),
                TrialInputComparisonCell(
                    ROUND_2,
                    "ABS-B" if input_revision_2 else None,
                    input_revision_2,
                ),
            ),
        ),
        TrialInputComparisonRow(
            semantic_key="parameter.hold_time",
            cells=(
                TrialInputComparisonCell(ROUND_1, None, None),
                TrialInputComparisonCell(
                    ROUND_2,
                    "4.5" if input_revision_2 else None,
                    input_revision_2,
                ),
            ),
        ),
    )
    metrics = (
        TrialMetricComparisonRow(
            TrialComparisonMetricKind.PARAMETER,
            "injection_pressure",
            None,
            (
                measured(ROUND_1, "80", source_id=210),
                pressure_target or measured(ROUND_2, "82", source_id=211),
            ),
        ),
        TrialMetricComparisonRow(
            TrialComparisonMetricKind.DIMENSION,
            "critical_length",
            CAVITY,
            (
                measured(
                    ROUND_1,
                    "10.10",
                    unit="mm",
                    source_id=212,
                    lower="9.8",
                    upper="10.2",
                ),
                dimension_target
                or measured(
                    ROUND_2,
                    "10.05",
                    unit="mm",
                    source_id=213,
                    lower="9.8",
                    upper="10.2",
                ),
            ),
        ),
        TrialMetricComparisonRow(
            TrialComparisonMetricKind.CYCLE_TIME,
            "cycle_time",
            None,
            (unavailable(ROUND_1), unavailable(ROUND_2)),
        ),
        TrialMetricComparisonRow(
            TrialComparisonMetricKind.YIELD,
            "yield",
            None,
            (unavailable(ROUND_1), unavailable(ROUND_2)),
        ),
    )
    return TrialRoundComparisonSnapshot(
        global_id=COMPARISON,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        trial_plan_global_id=PLAN,
        target_round_global_id=ROUND_2,
        policy_revision=TrialExactReference(POLICY_R1, policy().snapshot_hash),
        sources=source_values,
        input_rows=rows,
        metric_rows=metrics,
        created_by_user_id="trial-engineer@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p704-comparison",
    )


def reference(snapshot: TrialRoundComparisonSnapshot) -> TrialReviewReferenceRevision:
    return TrialReviewReferenceRevision(
        global_id=REFERENCE_R1,
        reference_global_id=REFERENCE,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        trial_round_global_id=ROUND_2,
        comparison_snapshot=TrialExactReference(snapshot.global_id, snapshot.snapshot_hash),
        reference_kind=TrialReviewReferenceKind.CONTROLLED_QUALITY_REPORT,
        reference_version=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        part_revision=exact(300, "7"),
        tooling_master_global_id=TOOLING_MASTER,
        tooling_revision=exact(301, "8"),
        tooling_set=exact(302, "9"),
        file_revision=exact(303, "a"),
        effective_from=date(2026, 8, 11),
        effective_to=None,
        reason="Bind the controlled quality report without granting approval authority.",
        created_by_user_id="quality@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p704-reference",
    )


def conclusion(
    snapshot: TrialRoundComparisonSnapshot,
    review_reference: TrialReviewReferenceRevision,
) -> TrialConclusionRevision:
    references = (review_reference,)
    return TrialConclusionRevision(
        global_id=CONCLUSION_R1,
        conclusion_global_id=CONCLUSION,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        trial_round_global_id=ROUND_2,
        trial_round_optimistic_version=snapshot.sources[-1].trial_round_optimistic_version,
        trial_round_snapshot_hash=snapshot.sources[-1].trial_round_snapshot_hash,
        conclusion_version=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        state=TrialConclusionRevisionState.SUBMITTED,
        conclusion_code=TrialConclusionCode.PASS,
        policy_revision=TrialExactReference(POLICY_R1, policy().snapshot_hash),
        comparison_snapshot=TrialExactReference(snapshot.global_id, snapshot.snapshot_hash),
        review_references=(
            TrialExactReference(review_reference.global_id, review_reference.snapshot_hash),
        ),
        blockers=(),
        summary_input=build_one_page_summary_input(
            snapshot,
            references,
            TrialConclusionCode.PASS,
            TrialConclusionRevisionState.SUBMITTED,
        ),
        proposed_next_work=("Prepare the next controlled production-readiness review.",),
        proposed_gate_effect="No automatic Gate effect; this remains a proposal.",
        proposed_npi_effect="No automatic NPI readiness effect; this remains a proposal.",
        reason="Submit the exact Trial review evidence for an authorized decision.",
        created_by_user_id="trial-engineer@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p704-conclusion",
    )


class Phase7TrialReviewDomainTest(unittest.TestCase):
    def test_policy_is_closed_hash_exact_and_has_explicit_authority(self) -> None:
        value = policy()
        self.assertEqual(policy_from_snapshot(value.snapshot_payload()), value)
        self.assertEqual(
            {capability for binding in value.authority_bindings for capability in binding.capabilities},
            set(TrialConclusionCapability),
        )
        restricted = replace(
            value,
            global_id=uid(401),
            allowed_conclusion_codes=(TrialConclusionCode.PASS,),
            out_of_spec_blocking_codes=(TrialConclusionCode.PASS,),
            snapshot_hash="",
        )
        self.assertEqual(restricted.allowed_conclusion_codes, (TrialConclusionCode.PASS,))
        with self.assertRaises(RequestValidationFailed):
            replace(
                restricted,
                out_of_spec_blocking_codes=(TrialConclusionCode.MATERIAL_CHANGE,),
                snapshot_hash="",
            )
        restricted_comparison = replace(
            comparison(),
            policy_revision=TrialExactReference(restricted.global_id, restricted.snapshot_hash),
            snapshot_hash="",
        )
        with self.assertRaises(RequestValidationFailed):
            derive_conclusion_blockers(
                restricted,
                restricted_comparison,
                (),
                TrialConclusionCode.MATERIAL_CHANGE,
            )
        successor = replace(
            value,
            global_id=uid(402),
            policy_version=2,
            predecessor_global_id=value.global_id,
            predecessor_snapshot_hash=value.snapshot_hash,
            snapshot_hash="",
        )
        validate_conclusion_policy_successor(value, successor)

    def test_multi_round_comparison_derives_changes_and_keeps_missing_metrics_unavailable(self) -> None:
        value = comparison()
        states = {row.semantic_key: row.change_state for row in value.input_rows}
        self.assertEqual(states["material.grade"], TrialInputChangeState.CHANGED)
        self.assertEqual(states["parameter.hold_time"], TrialInputChangeState.ADDED)
        for kind in (
            TrialComparisonMetricKind.CYCLE_TIME,
            TrialComparisonMetricKind.YIELD,
        ):
            row = next(item for item in value.metric_rows if item.metric_kind is kind)
            self.assertEqual(row.unit_state, TrialComparisonUnitState.UNAVAILABLE)
            self.assertEqual(row.cells[-1].comparison_state, TrialComparisonState.UNAVAILABLE)
            self.assertIsNone(row.cells[-1].value)
            self.assertIsNone(row.cells[-1].source_revision)
        self.assertEqual(comparison_from_snapshot(value.snapshot_payload()), value)

    def test_metric_delta_refuses_to_compare_different_units(self) -> None:
        row = TrialMetricComparisonRow(
            TrialComparisonMetricKind.PARAMETER,
            "back_pressure",
            None,
            (
                measured(ROUND_1, "5", unit="MPa", source_id=410),
                measured(ROUND_2, "50", unit="bar", source_id=411),
            ),
        )
        self.assertEqual(row.unit_state, TrialComparisonUnitState.UNIT_MISMATCH)
        self.assertEqual(row.deltas, (None, None))
        with self.assertRaises(RequestValidationFailed):
            TrialMetricComparisonCell(
                ROUND_2,
                TrialComparisonCellState.UNAVAILABLE,
                "0",
                None,
                None,
                None,
                None,
            )
        with self.assertRaises(RequestValidationFailed):
            TrialInputComparisonCell(ROUND_2, "ABS-B", None)

    def test_dimension_unavailable_sentinel_never_invents_a_cavity_identity(self) -> None:
        row = TrialMetricComparisonRow(
            TrialComparisonMetricKind.DIMENSION,
            "unavailable",
            None,
            (unavailable(ROUND_1), unavailable(ROUND_2)),
        )
        self.assertIsNone(row.cavity_global_id)
        self.assertEqual(row.unit_state, TrialComparisonUnitState.UNAVAILABLE)
        with self.assertRaises(RequestValidationFailed):
            TrialMetricComparisonRow(
                TrialComparisonMetricKind.DIMENSION,
                "critical_length",
                None,
                (unavailable(ROUND_1), unavailable(ROUND_2)),
            )
        with self.assertRaises(RequestValidationFailed):
            TrialMetricComparisonRow(
                TrialComparisonMetricKind.DIMENSION,
                "unavailable",
                None,
                (
                    unavailable(ROUND_1),
                    measured(ROUND_2, "10.1", unit="mm", source_id=412),
                ),
            )

    def test_defect_trends_are_derived_from_exact_round_tips(self) -> None:
        continued = uid(420)
        reopened = uid(421)
        resolved = uid(422)
        new = uid(423)

        def defect(defect_id: UUID, state: ToolingDefectState, revision_id: int) -> TrialDefectTip:
            return TrialDefectTip(
                defect_id,
                TrialDefectSourceKind.TRIAL,
                exact(revision_id, "b"),
                state,
                False,
                0,
            )

        sources = (
            source(
                1,
                ROUND_1,
                defects=(
                    defect(continued, ToolingDefectState.OPEN, 430),
                    defect(reopened, ToolingDefectState.CLOSED, 431),
                    defect(resolved, ToolingDefectState.OPEN, 432),
                ),
            ),
            source(
                2,
                ROUND_2,
                defects=(
                    defect(continued, ToolingDefectState.IN_PROGRESS, 433),
                    defect(reopened, ToolingDefectState.REOPENED, 434),
                    defect(resolved, ToolingDefectState.CLOSED, 435),
                    defect(new, ToolingDefectState.OPEN, 436),
                ),
            ),
        )
        trends = dict(comparison(sources=sources).defect_trends)
        self.assertEqual(trends[continued], TrialDefectTrendState.CONTINUED)
        self.assertEqual(trends[reopened], TrialDefectTrendState.REOPENED)
        self.assertEqual(trends[resolved], TrialDefectTrendState.RESOLVED)
        self.assertEqual(trends[new], TrialDefectTrendState.NEW)

    def test_server_derives_every_policy_blocker_from_exact_sources(self) -> None:
        blocking_defect = TrialDefectTip(
            uid(440),
            TrialDefectSourceKind.TRIAL,
            exact(441, "c"),
            ToolingDefectState.OPEN,
            True,
            2,
        )
        sources = (
            source(1, ROUND_1),
            source(2, ROUND_2, defects=(blocking_defect,), complete=False),
        )
        missing_pressure = TrialMetricComparisonCell(
            ROUND_2,
            TrialComparisonCellState.NOT_MEASURED,
            None,
            "MPa",
            None,
            None,
            exact(442, "d"),
        )
        out_of_spec_dimension = measured(
            ROUND_2,
            "10.5",
            unit="mm",
            source_id=443,
            lower="9.8",
            upper="10.2",
        )
        snapshot = comparison(
            sources=sources,
            pressure_target=missing_pressure,
            dimension_target=out_of_spec_dimension,
        )
        codes = {
            value.code
            for value in derive_conclusion_blockers(
                policy(),
                snapshot,
                (),
                TrialConclusionCode.PASS,
            )
        }
        self.assertEqual(
            codes,
            {
                TrialConclusionBlockerCode.MISSING_INPUT_LOCK,
                TrialConclusionBlockerCode.MISSING_ACTUAL,
                TrialConclusionBlockerCode.REQUIRED_PARAMETER_NOT_MEASURED,
                TrialConclusionBlockerCode.MISSING_CAVITY_RESULT,
                TrialConclusionBlockerCode.OPEN_BLOCKING_DEFECT,
                TrialConclusionBlockerCode.REQUIRED_ACTION_NOT_VERIFIED,
                TrialConclusionBlockerCode.REQUIRED_REVIEW_REFERENCE_UNAVAILABLE,
                TrialConclusionBlockerCode.OUT_OF_SPEC_BLOCKING,
            },
        )

    def test_controlled_evidence_is_versioned_but_never_grants_approval(self) -> None:
        snapshot = comparison()
        first = reference(snapshot)
        self.assertEqual(first.snapshot_payload()["approvalAuthority"], "unavailable")
        self.assertEqual(review_reference_from_snapshot(first.snapshot_payload()), first)
        successor = replace(
            first,
            global_id=uid(450),
            reference_version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
            file_revision=exact(451, "d"),
            reason="Replace the exact controlled file revision.",
            snapshot_hash="",
        )
        validate_review_reference_successor(first, successor)
        invalid = replace(successor, tooling_set=exact(452, "e"), snapshot_hash="")
        with self.assertRaises(RequestValidationFailed):
            validate_review_reference_successor(first, invalid)
        tampered = copy.deepcopy(first.snapshot_payload())
        tampered["approvalAuthority"] = "customer_approved"
        with self.assertRaises(RequestValidationFailed):
            review_reference_from_snapshot(tampered)

    def test_conclusion_binds_exact_sources_and_decision_cannot_drift(self) -> None:
        snapshot = comparison()
        review = reference(snapshot)
        submitted = conclusion(snapshot, review)
        self.assertEqual(
            derive_conclusion_blockers(
                policy(),
                snapshot,
                (review,),
                TrialConclusionCode.PASS,
            ),
            (),
        )
        validate_conclusion_sources(policy(), snapshot, (review,), submitted)
        unrelated = replace(
            review,
            global_id=uid(459),
            reference_global_id=uid(458),
            project_global_id=uid(457),
            snapshot_hash="",
        )
        with self.assertRaises(RequestValidationFailed):
            validate_conclusion_sources(policy(), snapshot, (review, unrelated), submitted)
        self.assertEqual(conclusion_from_snapshot(submitted.snapshot_payload()), submitted)
        approved = replace(
            submitted,
            global_id=uid(460),
            trial_round_optimistic_version=(
                submitted.trial_round_optimistic_version + 1
            ),
            trial_round_snapshot_hash="e" * 64,
            conclusion_version=2,
            predecessor_global_id=submitted.global_id,
            predecessor_snapshot_hash=submitted.snapshot_hash,
            state=TrialConclusionRevisionState.APPROVED,
            summary_input=build_one_page_summary_input(
                snapshot,
                (review,),
                TrialConclusionCode.PASS,
                TrialConclusionRevisionState.APPROVED,
            ),
            reason="Approve the exact submitted Trial conclusion.",
            snapshot_hash="",
        )
        validate_conclusion_successor(submitted, approved)
        validate_conclusion_sources(policy(), snapshot, (review,), approved)
        stale_round = replace(
            approved,
            global_id=uid(461),
            conclusion_version=3,
            predecessor_global_id=approved.global_id,
            predecessor_snapshot_hash=approved.snapshot_hash,
            state=TrialConclusionRevisionState.REOPENED,
            summary_input=build_one_page_summary_input(
                snapshot,
                (review,),
                TrialConclusionCode.PASS,
                TrialConclusionRevisionState.REOPENED,
            ),
            snapshot_hash="",
        )
        with self.assertRaises(RequestValidationFailed):
            validate_conclusion_successor(approved, stale_round)
        reopened = replace(
            stale_round,
            trial_round_optimistic_version=(
                approved.trial_round_optimistic_version + 1
            ),
            trial_round_snapshot_hash="f" * 64,
            snapshot_hash="",
        )
        validate_conclusion_successor(approved, reopened)
        drifted_sources = replace(
            reopened,
            proposed_next_work=("Replace the frozen submitted work.",),
            snapshot_hash="",
        )
        with self.assertRaises(RequestValidationFailed):
            validate_conclusion_successor(approved, drifted_sources)

    def test_closed_snapshot_rejects_tampered_derived_or_external_truth(self) -> None:
        snapshot = comparison()
        comparison_payload = copy.deepcopy(snapshot.snapshot_payload())
        comparison_payload["formalErpQuality"] = "passed"
        with self.assertRaises(RequestValidationFailed):
            comparison_from_snapshot(comparison_payload)
        review = reference(snapshot)
        value = conclusion(snapshot, review)
        payload = copy.deepcopy(value.snapshot_payload())
        payload["externalEffects"]["gate"] = "approved"
        with self.assertRaises(RequestValidationFailed):
            conclusion_from_snapshot(payload)
        summary_payload = copy.deepcopy(value.snapshot_payload())
        summary_payload["summaryInput"]["formalErpQuality"] = "passed"
        with self.assertRaises(RequestValidationFailed):
            conclusion_from_snapshot(summary_payload)


if __name__ == "__main__":
    unittest.main()
