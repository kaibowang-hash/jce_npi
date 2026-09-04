from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.engineering_controls_domain import (
    CapacityInputProvenance,
    CapacityProvenanceKind,
    ProcessComparisonRuleSnapshot,
    ToolingCapacityLineInput,
    ToolingCapacityScenarioRevision,
    ToolingDefectAction,
    ToolingDefectActionState,
    ToolingDefectActionType,
    ToolingDefectContextKind,
    ToolingDefectDetectionContext,
    ToolingDefectEvidenceRole,
    ToolingDefectFileEvidence,
    ToolingDefectRevision,
    ToolingDefectRootCauseState,
    ToolingDefectSeverity,
    ToolingDefectState,
    ToolingHealthUnavailable,
    ToolingProcessComparisonState,
    ToolingProcessContextEvidence,
    ToolingProcessContextKind,
    ToolingProcessLayer,
    ToolingProcessMetric,
    ToolingProcessMetricCode,
    ToolingProcessProfileRevision,
    ToolingProcessValueKind,
    capacity_scenario_from_snapshot,
    compare_process_metric,
    defect_revision_from_snapshot,
    process_profile_from_snapshot,
    tooling_health_from_snapshot,
    validate_capacity_scenario_successor,
    validate_process_profile_successor,
    validate_tooling_defect_successor,
)
from npi_core.tooling.manufacturing_domain import (
    ProjectMemberResponsibility,
    ReleasedDocumentEvidence,
)


TENANT = "tenant-a"
PROJECT = UUID("10000000-0000-4000-8000-000000000001")
MASTER = UUID("10000000-0000-4000-8000-000000000002")
REVISION = UUID("10000000-0000-4000-8000-000000000003")
PART_1 = UUID("10000000-0000-4000-8000-000000000004")
PART_2 = UUID("10000000-0000-4000-8000-000000000005")
APP_1 = UUID("10000000-0000-4000-8000-000000000006")
APP_2 = UUID("10000000-0000-4000-8000-000000000007")
MEMBER = UUID("10000000-0000-4000-8000-000000000008")
DEFECT = UUID("10000000-0000-4000-8000-000000000009")
PROFILE = UUID("10000000-0000-4000-8000-000000000010")
SCENARIO = UUID("10000000-0000-4000-8000-000000000011")
NOW = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def member() -> ProjectMemberResponsibility:
    return ProjectMemberResponsibility(
        global_id=MEMBER,
        user_id="engineer@example.invalid",
        optimistic_version=2,
    )


def file_evidence(
    *,
    global_id: UUID = UUID("20000000-0000-4000-8000-000000000001"),
    role: ToolingDefectEvidenceRole = ToolingDefectEvidenceRole.DETECTION,
) -> ToolingDefectFileEvidence:
    return ToolingDefectFileEvidence(
        global_id=global_id,
        role=role,
        file_revision_global_id=UUID("20000000-0000-4000-8000-000000000002"),
        file_optimistic_version=3,
        frappe_content_hash="c" * 64,
        file_name="synthetic-defect.pdf",
        mime_type="application/pdf",
        size_bytes=512,
        sha256="d" * 64,
    )


def defect_action(
    *, state: ToolingDefectActionState = ToolingDefectActionState.PLANNED
) -> ToolingDefectAction:
    evidence = (
        file_evidence(
            global_id=UUID("20000000-0000-4000-8000-000000000003"),
            role=ToolingDefectEvidenceRole.ACTION,
        ),
    ) if state is ToolingDefectActionState.VERIFIED else ()
    return ToolingDefectAction(
        global_id=UUID("20000000-0000-4000-8000-000000000004"),
        action_type=ToolingDefectActionType.CORRECTIVE,
        state=state,
        detail="Correct the exact cavity insert fit.",
        responsible_member=member(),
        due_date=date(2026, 8, 20),
        evidence=evidence,
    )


def defect(
    *,
    global_id: UUID = UUID("30000000-0000-4000-8000-000000000001"),
    version: int = 1,
    predecessor: ToolingDefectRevision | None = None,
    state: ToolingDefectState = ToolingDefectState.OPEN,
    action_state: ToolingDefectActionState = ToolingDefectActionState.PLANNED,
    reason: str = "Record the exact Tooling defect.",
) -> ToolingDefectRevision:
    evidence = predecessor.evidence if predecessor is not None else (file_evidence(),)
    if state is ToolingDefectState.CLOSED:
        evidence = (*evidence, file_evidence(
            global_id=UUID("30000000-0000-4000-8000-000000000002"),
            role=ToolingDefectEvidenceRole.VERIFICATION,
        ))
    return ToolingDefectRevision(
        global_id=global_id,
        defect_global_id=DEFECT,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        tooling_revision_global_id=REVISION,
        tooling_revision_snapshot_hash=HASH_A,
        cavity_global_id=UUID("30000000-0000-4000-8000-000000000003"),
        cavity_identifier="CAV-01",
        defect_version=version,
        predecessor_global_id=None if predecessor is None else predecessor.global_id,
        predecessor_snapshot_hash=None if predecessor is None else predecessor.snapshot_hash,
        business_code="DEF-001",
        title="Cavity flash",
        description="Flash was observed at the exact cavity insert.",
        category_key="appearance.flash",
        severity=ToolingDefectSeverity.HIGH,
        blocking=False,
        state=state,
        detection_context=ToolingDefectDetectionContext(
            kind=ToolingDefectContextKind.TOOLING_REVISION,
            global_id=REVISION,
            snapshot_hash=HASH_A,
        ),
        root_cause_state=ToolingDefectRootCauseState.PENDING,
        root_cause=None,
        responsible_member=None if state is ToolingDefectState.OPEN else member(),
        target_round_label="T1",
        actions=(defect_action(state=action_state),),
        evidence=evidence,
        reason=reason,
        created_by_user_id="engineer@example.invalid",
        created_at=NOW,
        request_id=UUID(f"40000000-0000-4000-8000-{version:012d}"),
        trace_id=f"trace-p605-defect-{version}",
    )


def rule() -> ProcessComparisonRuleSnapshot:
    return ProcessComparisonRuleSnapshot(
        global_id=UUID("50000000-0000-4000-8000-000000000001"),
        rule_version=1,
        unit="s",
        minimum="29.5",
        maximum="30.5",
    )


def metric(
    *,
    global_id: UUID = UUID("50000000-0000-4000-8000-000000000002"),
    value: str = "30",
    comparison_rule: ProcessComparisonRuleSnapshot | None = None,
) -> ToolingProcessMetric:
    return ToolingProcessMetric(
        global_id=global_id,
        code=ToolingProcessMetricCode.CYCLE_TIME,
        value_kind=ToolingProcessValueKind.NUMERIC,
        numeric_value=value,
        text_value=None,
        unit="s",
        comparison_rule=comparison_rule,
    )


def profile(
    *,
    global_id: UUID = UUID("50000000-0000-4000-8000-000000000003"),
    version: int = 1,
    predecessor: ToolingProcessProfileRevision | None = None,
    layer: ToolingProcessLayer = ToolingProcessLayer.CUSTOMER_STANDARD,
) -> ToolingProcessProfileRevision:
    context_kind = {
        ToolingProcessLayer.CUSTOMER_STANDARD: ToolingProcessContextKind.RELEASED_DOCUMENT,
        ToolingProcessLayer.TRIAL_ACTUAL: ToolingProcessContextKind.TRIAL_MEASUREMENT,
        ToolingProcessLayer.APPROVED_BASELINE: ToolingProcessContextKind.APPROVED_TRIAL,
    }[layer]
    source_global_id = UUID("50000000-0000-4000-8000-000000000004")
    released_document = (
        ReleasedDocumentEvidence(
            revision_global_id=source_global_id,
            revision_snapshot_hash=HASH_B,
            lifecycle_global_id=UUID("50000000-0000-4000-8000-000000000020"),
            lifecycle_version=2,
            release_event_global_id=UUID("50000000-0000-4000-8000-000000000021"),
            release_event_hash="c" * 64,
            release_snapshot_hash="d" * 64,
        )
        if layer is ToolingProcessLayer.CUSTOMER_STANDARD
        else None
    )
    return ToolingProcessProfileRevision(
        global_id=global_id,
        profile_global_id=PROFILE,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        tooling_revision_global_id=REVISION,
        tooling_revision_snapshot_hash=HASH_A,
        layer=layer,
        profile_version=version,
        predecessor_global_id=None if predecessor is None else predecessor.global_id,
        predecessor_snapshot_hash=None if predecessor is None else predecessor.snapshot_hash,
        context=ToolingProcessContextEvidence(
            kind=context_kind,
            global_id=source_global_id,
            snapshot_hash=HASH_B,
            released_document=released_document,
            approval_event_global_id=(
                UUID("50000000-0000-4000-8000-000000000005")
                if layer is ToolingProcessLayer.APPROVED_BASELINE
                else None
            ),
            approval_event_hash=HASH_A if layer is ToolingProcessLayer.APPROVED_BASELINE else None,
        ),
        effective_from=date(2026, 8, 8),
        metrics=(metric(comparison_rule=rule() if layer is ToolingProcessLayer.CUSTOMER_STANDARD else None),),
        reason="Record the exact process fact layer.",
        created_by_user_id="engineer@example.invalid",
        created_at=NOW,
        request_id=UUID(f"60000000-0000-4000-8000-{version:012d}"),
        trace_id=f"trace-p605-profile-{version}",
    )


def provenance(
    kind: CapacityProvenanceKind = CapacityProvenanceKind.SCENARIO_ASSUMPTION,
) -> CapacityInputProvenance:
    source_id = {
        CapacityProvenanceKind.CUSTOMER_STANDARD: PROFILE,
        CapacityProvenanceKind.TOOLING_REVISION: REVISION,
        CapacityProvenanceKind.TOOLING_APPLICABILITY: APP_1,
        CapacityProvenanceKind.TOOLING_SET_SELECTION: UUID("90000000-0000-4000-8000-000000000010"),
        CapacityProvenanceKind.SCENARIO_ASSUMPTION: None,
    }[kind]
    return CapacityInputProvenance(
        kind=kind,
        global_id=source_id,
        snapshot_hash=HASH_A,
    )


def capacity_line(
    *,
    global_id: UUID = UUID("70000000-0000-4000-8000-000000000001"),
    part: UUID = PART_1,
    applicability: UUID = APP_1,
    cycle: str = "30",
    usage: str = "2",
) -> ToolingCapacityLineInput:
    return ToolingCapacityLineInput(
        global_id=global_id,
        part_revision_global_id=part,
        part_revision_snapshot_hash=HASH_A,
        applicability_global_id=applicability,
        applicability_snapshot_hash=HASH_B,
        available_hours_per_day="20",
        working_days_per_month=25,
        oee_ratio="0.8",
        yield_ratio="0.95",
        cycle_seconds=cycle,
        cavity_count=2,
        usage_per_assembly=usage,
        effective_set_count=1,
        selected_tooling_set_global_ids=(),
        cycle_provenance=provenance(),
        cavity_provenance=provenance(CapacityProvenanceKind.TOOLING_REVISION),
        usage_provenance=provenance(CapacityProvenanceKind.TOOLING_APPLICABILITY),
        set_provenance=provenance(CapacityProvenanceKind.SCENARIO_ASSUMPTION),
    )


def scenario(
    *,
    global_id: UUID = UUID("70000000-0000-4000-8000-000000000002"),
    version: int = 1,
    predecessor: ToolingCapacityScenarioRevision | None = None,
    lines: tuple[ToolingCapacityLineInput, ...] | None = None,
) -> ToolingCapacityScenarioRevision:
    return ToolingCapacityScenarioRevision(
        global_id=global_id,
        scenario_global_id=SCENARIO,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        scenario_version=version,
        predecessor_global_id=None if predecessor is None else predecessor.global_id,
        predecessor_snapshot_hash=None if predecessor is None else predecessor.snapshot_hash,
        title="Synthetic monthly capacity",
        effective_from=date(2026, 8, 8),
        target_monthly_assembly_units="50000",
        lines=lines or (
            capacity_line(),
            capacity_line(
                global_id=UUID("70000000-0000-4000-8000-000000000003"),
                part=PART_2,
                applicability=APP_2,
                cycle="40",
                usage="1",
            ),
        ),
        reason="Calculate an explicit capacity scenario.",
        created_by_user_id="engineer@example.invalid",
        created_at=NOW,
        request_id=UUID(f"80000000-0000-4000-8000-{version:012d}"),
        trace_id=f"trace-p605-capacity-{version}",
    )


class Phase6ToolingEngineeringControlsDomainTest(unittest.TestCase):
    def test_defect_is_closed_hash_bound_and_trial_remains_unavailable(self) -> None:
        value = defect()
        self.assertEqual(defect_revision_from_snapshot(value.snapshot_payload()), value)
        payload = value.snapshot_payload()
        self.assertEqual(payload["trialReference"], {
            "state": "unavailable",
            "reasonCode": "trial_context_unavailable",
        })
        self.assertFalse(payload["blocking"])
        self.assertEqual(payload["severity"], "high")
        combined = json.dumps(payload, sort_keys=True).casefold()
        for forbidden in ("gateid", "gatepassed", "toolinglifecycle", "trialglobalid"):
            self.assertNotIn(forbidden, combined)
        with self.assertRaises(RequestValidationFailed):
            defect_revision_from_snapshot({**payload, "approved": True})

    def test_defect_successor_enforces_sequence_and_retains_actions(self) -> None:
        values = [defect()]
        for index, state in enumerate(
            (
                ToolingDefectState.ASSIGNED,
                ToolingDefectState.IN_PROGRESS,
                ToolingDefectState.READY_FOR_VERIFICATION,
                ToolingDefectState.CLOSED,
            ),
            start=2,
        ):
            action_state = (
                ToolingDefectActionState.COMPLETED
                if state is ToolingDefectState.CLOSED
                else ToolingDefectActionState.PLANNED
            )
            next_value = defect(
                global_id=UUID(f"30000000-0000-4000-8000-{index:012d}"),
                version=index,
                predecessor=values[-1],
                state=state,
                action_state=action_state,
            )
            validate_tooling_defect_successor(values[-1], next_value)
            values.append(next_value)
        reopened = defect(
            global_id=UUID("30000000-0000-4000-8000-000000000006"),
            version=6,
            predecessor=values[-1],
            state=ToolingDefectState.REOPENED,
            action_state=ToolingDefectActionState.COMPLETED,
            reason="Reopen after the defect recurred.",
        )
        validate_tooling_defect_successor(values[-1], reopened)
        skipped = replace(values[0], global_id=UUID("30000000-0000-4000-8000-000000000007"), defect_version=2, predecessor_global_id=values[0].global_id, predecessor_snapshot_hash=values[0].snapshot_hash, state=ToolingDefectState.CLOSED, responsible_member=member(), evidence=(file_evidence(role=ToolingDefectEvidenceRole.VERIFICATION),), actions=(defect_action(state=ToolingDefectActionState.COMPLETED),))
        with self.assertRaises(RequestValidationFailed):
            validate_tooling_defect_successor(values[0], skipped)

    def test_defect_close_and_action_verification_require_evidence(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            defect(state=ToolingDefectState.ASSIGNED)
        with self.assertRaises(RequestValidationFailed):
            replace(
                defect(),
                state=ToolingDefectState.CLOSED,
                responsible_member=member(),
                actions=(defect_action(state=ToolingDefectActionState.COMPLETED),),
            )
        with self.assertRaises(RequestValidationFailed):
            ToolingDefectAction(
                global_id=UUID("20000000-0000-4000-8000-000000000005"),
                action_type=ToolingDefectActionType.CORRECTIVE,
                state=ToolingDefectActionState.VERIFIED,
                detail="Verify the corrective action.",
                responsible_member=member(),
                due_date=date(2026, 8, 20),
                evidence=(),
            )

    def test_process_profiles_are_layer_specific_and_hash_bound(self) -> None:
        standard = profile()
        self.assertEqual(process_profile_from_snapshot(standard.snapshot_payload()), standard)
        successor = profile(
            global_id=UUID("50000000-0000-4000-8000-000000000006"),
            version=2,
            predecessor=standard,
        )
        validate_process_profile_successor(standard, successor)
        for layer in (ToolingProcessLayer.TRIAL_ACTUAL, ToolingProcessLayer.APPROVED_BASELINE):
            self.assertEqual(process_profile_from_snapshot(profile(layer=layer).snapshot_payload()).layer, layer)
        with self.assertRaises(RequestValidationFailed):
            replace(standard, layer=ToolingProcessLayer.TRIAL_ACTUAL)

    def test_process_comparison_returns_all_textual_states_without_color_claim(self) -> None:
        reference = metric(comparison_rule=rule())
        missing = compare_process_metric(ToolingProcessLayer.CUSTOMER_STANDARD, reference, None)
        self.assertEqual(missing.state, ToolingProcessComparisonState.NOT_MEASURED)
        within = compare_process_metric(
            ToolingProcessLayer.CUSTOMER_STANDARD,
            reference,
            metric(global_id=UUID("50000000-0000-4000-8000-000000000007"), value="30.25"),
        )
        self.assertEqual(within.state, ToolingProcessComparisonState.WITHIN_TOLERANCE)
        self.assertEqual(within.delta, "0.25")
        self.assertEqual(
            within.snapshot_payload()["visualSemantics"],
            {"state": "unavailable", "reasonCode": "variance_exception_color_policy_unavailable"},
        )
        outside = compare_process_metric(
            ToolingProcessLayer.CUSTOMER_STANDARD,
            reference,
            metric(global_id=UUID("50000000-0000-4000-8000-000000000008"), value="31"),
        )
        self.assertEqual(outside.state, ToolingProcessComparisonState.OUTSIDE_TOLERANCE)
        unavailable = compare_process_metric(
            ToolingProcessLayer.CUSTOMER_STANDARD,
            replace(reference, comparison_rule=None),
            metric(global_id=UUID("50000000-0000-4000-8000-000000000009"), value="31"),
        )
        self.assertEqual(unavailable.state, ToolingProcessComparisonState.UNAVAILABLE)

    def test_capacity_formula_is_explicit_recomputed_and_tamper_evident(self) -> None:
        value = scenario()
        payload = value.snapshot_payload()
        self.assertEqual(payload["formulaVersion"], "capacity.v1")
        self.assertEqual(payload["roundingRule"], "decimal-6-half-even")
        self.assertEqual(capacity_scenario_from_snapshot(payload), value)
        first = value.results[0]
        self.assertEqual(first.parts_per_day, "3648.000000")
        self.assertEqual(first.parts_per_month, "91200.000000")
        self.assertEqual(first.assembly_units_per_month, "45600.000000")
        self.assertEqual(value.scenario_assembly_units_per_month, "45600.000000")
        self.assertEqual(value.gap, "4400.000000")
        tampered = json.loads(json.dumps(payload))
        tampered["result"]["gap"] = "0.000000"
        with self.assertRaises(RequestValidationFailed):
            capacity_scenario_from_snapshot(tampered)

    def test_capacity_successor_and_input_boundaries_fail_closed(self) -> None:
        first = scenario()
        self.assertEqual(
            replace(first.lines[0], available_hours_per_day="-0").available_hours_per_day,
            "0.0",
        )
        changed_line = replace(first.lines[0], oee_ratio="0.9")
        second = scenario(
            global_id=UUID("70000000-0000-4000-8000-000000000004"),
            version=2,
            predecessor=first,
            lines=(changed_line, first.lines[1]),
        )
        validate_capacity_scenario_successor(first, second)
        self.assertNotEqual(first.snapshot_hash, second.snapshot_hash)
        self.assertNotEqual(first.results[0].parts_per_day, second.results[0].parts_per_day)
        with self.assertRaises(RequestValidationFailed):
            replace(first.lines[0], available_hours_per_day="22.5", cycle_seconds="0")
        with self.assertRaises(RequestValidationFailed):
            replace(
                first.lines[0],
                effective_set_count=2,
                selected_tooling_set_global_ids=(UUID("90000000-0000-4000-8000-000000000001"),),
            )

    def test_health_default_is_explicit_unavailable_and_closed(self) -> None:
        value = ToolingHealthUnavailable()
        self.assertEqual(tooling_health_from_snapshot(value.snapshot_payload()), value)
        payload = value.snapshot_payload()
        self.assertEqual(payload["shotCount"]["state"], "unavailable")  # type: ignore[index]
        self.assertEqual(payload["healthScore"]["state"], "unavailable")  # type: ignore[index]
        with self.assertRaises(RequestValidationFailed):
            tooling_health_from_snapshot({**payload, "score": 100})


if __name__ == "__main__":
    unittest.main()
