from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.manufacturing_domain import (
    DesignReleaseBlockedReason,
    DesignReleaseEvidenceState,
    ErpActualCostRow,
    FormalSupplierReference,
    ManufacturingAuthorizationUnavailable,
    PlanningMoney,
    ProjectMemberResponsibility,
    ReleasedDocumentEvidence,
    ToolingManufacturingMilestone,
    ToolingManufacturingMilestoneObservation,
    ToolingManufacturingPlanRevision,
    ToolingMilestoneCategory,
    ToolingMilestoneEvidenceRole,
    ToolingMilestoneFileEvidence,
    ToolingMilestoneResponsibilityKind,
    ToolingPlanEvidence,
    ToolingPlanEvidenceRole,
    ToolingProcurementCostAvailable,
    ToolingProcurementCostUnavailable,
    ToolingSourcingStrategy,
    aggregate_actual_costs,
    design_release_capability,
    manufacturing_plan_from_snapshot,
    milestone_observation_from_snapshot,
    procurement_cost_projection_from_snapshot,
    validate_manufacturing_plan_successor,
    validate_milestone_observation_successor,
)


TENANT = "tenant-a"
PROJECT = UUID("d60e1aef-9b53-486e-95b1-4136ef72fdc5")
MASTER = UUID("8b93b720-2455-44ac-900d-56841f17ad28")
REVISION = UUID("83c7ab50-7709-4550-bf8f-9bfe50bd8f50")
PLAN = UUID("2af2497a-a031-469f-9290-448f8e2feea4")
PLAN_R1 = UUID("b6dc643b-3338-44e4-9763-1061b502c1fc")
PLAN_R2 = UUID("645218fa-57db-47e7-a730-a41d03c825bc")
MILESTONE_1 = UUID("db33a718-bc89-4262-8100-d2904225705b")
MILESTONE_2 = UUID("76556992-a0c7-480d-b8ef-e3a1eb1f8462")
OBSERVATION_1 = UUID("24450120-7a52-4766-9eb1-b83baff79343")
OBSERVATION_2 = UUID("f1eca6cd-7117-4a61-8f8b-d01432af27d3")
DOCUMENT_REVISION = UUID("c0c321ad-038b-40bf-a8cb-8e81e839c066")
MEMBER = UUID("87907c49-764c-41bd-8b31-d18f73a0e2bb")
NOW = datetime(2026, 8, 8, 11, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def member() -> ProjectMemberResponsibility:
    return ProjectMemberResponsibility(
        global_id=MEMBER,
        user_id="tooling.owner@example.invalid",
        optimistic_version=3,
    )


def released_document(
    revision_global_id: UUID = DOCUMENT_REVISION,
) -> ReleasedDocumentEvidence:
    return ReleasedDocumentEvidence(
        revision_global_id=revision_global_id,
        revision_snapshot_hash=HASH_A,
        lifecycle_global_id=UUID("ae5ebba8-8bee-434f-8602-a342ab675e96"),
        lifecycle_version=5,
        release_event_global_id=UUID("b1d365c5-6a34-4897-9898-d83fcff1b97f"),
        release_event_hash="e" * 64,
        release_snapshot_hash=HASH_B,
    )


def milestone(
    *,
    global_id: UUID = MILESTONE_1,
    sequence: int = 1,
    category: ToolingMilestoneCategory = ToolingMilestoneCategory.DESIGN,
    responsibility_kind: ToolingMilestoneResponsibilityKind = ToolingMilestoneResponsibilityKind.INTERNAL,
    responsible_member: ProjectMemberResponsibility | None = None,
    predecessors: tuple[UUID, ...] = (),
) -> ToolingManufacturingMilestone:
    return ToolingManufacturingMilestone(
        global_id=global_id,
        sequence=sequence,
        category=category,
        planned_start=date(2026, 8, 10),
        planned_finish=date(2026, 8, 12),
        responsibility_kind=responsibility_kind,
        responsible_member=(
            member()
            if responsible_member is None
            and responsibility_kind is ToolingMilestoneResponsibilityKind.INTERNAL
            else responsible_member
        ),
        predecessor_global_ids=predecessors,
    )


def plan(
    *,
    global_id: UUID = PLAN_R1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
    milestones: tuple[ToolingManufacturingMilestone, ...] | None = None,
) -> ToolingManufacturingPlanRevision:
    first = milestone()
    second = milestone(
        global_id=MILESTONE_2,
        sequence=2,
        category=ToolingMilestoneCategory.MATERIAL_PREPARATION,
        responsibility_kind=ToolingMilestoneResponsibilityKind.SUPPLIER,
        predecessors=(MILESTONE_1,),
    )
    return ToolingManufacturingPlanRevision(
        global_id=global_id,
        plan_global_id=PLAN,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        tooling_revision_global_id=REVISION,
        tooling_revision_snapshot_hash=HASH_A,
        plan_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        sourcing_strategy=ToolingSourcingStrategy.HYBRID,
        responsible_member=member(),
        engineering_estimate=PlanningMoney("100000.00", "CNY"),
        budget=PlanningMoney("120000", "CNY"),
        evidence=(
            ToolingPlanEvidence(
                role=ToolingPlanEvidenceRole.DFM,
                document=released_document(),
            ),
        ),
        design_release_evidence=(released_document(),),
        milestones=milestones or (first, second),
        reason="Record the immutable internal manufacturing plan.",
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=UUID("10e7aa34-982d-4c9b-bb99-e41df6507bf7"),
        trace_id="trace-p604-plan",
    )


def file_evidence() -> ToolingMilestoneFileEvidence:
    return ToolingMilestoneFileEvidence(
        global_id=UUID("58ed004e-2435-4d03-8c50-f2f460868e49"),
        role=ToolingMilestoneEvidenceRole.TECHNICAL_EVIDENCE,
        file_revision_global_id=UUID("7c31f6f8-53f7-4637-b9fb-b7ed60313498"),
        file_optimistic_version=2,
        frappe_content_hash="c" * 64,
        file_name="synthetic-progress.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256="d" * 64,
    )


def observation(
    *,
    global_id: UUID = OBSERVATION_1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
) -> ToolingManufacturingMilestoneObservation:
    selected = plan().milestones[1]
    return ToolingManufacturingMilestoneObservation(
        global_id=global_id,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        plan_revision_global_id=PLAN_R1,
        plan_revision_snapshot_hash=plan().snapshot_hash,
        milestone_global_id=selected.global_id,
        milestone_snapshot_hash=selected.snapshot_hash,
        observation_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        progress_percentage=35,
        actual_start=date(2026, 8, 10),
        actual_finish=None,
        risk="Material certificate is pending.",
        note="Internally reported observation for a supplier-responsible milestone.",
        evidence=(file_evidence(),),
        reported_by_member=member(),
        created_at=NOW,
        request_id=UUID("63a9995b-0dc2-48df-89eb-36ba89f4ce50"),
        trace_id="trace-p604-observation",
    )


def cost_row(
    *,
    source_row_id: str = "PINV-0001-L1",
    amount: str = "1000.00",
    cost_type_code: str = "RAW-MOLD-COST",
    currency: str = "CNY",
) -> ErpActualCostRow:
    return ErpActualCostRow(
        tooling_master_global_id=MASTER,
        source_row_id=source_row_id,
        source_row_version="5",
        supplier_source_object_id="SUP-0001",
        purchase_order_source_id="PO-0001",
        purchase_receipt_source_id="PR-0001",
        purchase_invoice_source_id="PINV-0001",
        actual_cost_source_id=f"ACT-{source_row_id}",
        cost_type_code=cost_type_code,
        posting_date=date(2026, 8, 8),
        currency=currency,
        amount=amount,
    )


class Phase6ToolingManufacturingDomainTest(unittest.TestCase):
    def test_plan_is_closed_hash_bound_and_does_not_claim_authority(self) -> None:
        value = plan()
        payload = value.snapshot_payload()
        self.assertEqual(manufacturing_plan_from_snapshot(payload), value)
        self.assertEqual(len(value.version_key_hash or ""), 64)
        self.assertEqual(len(value.snapshot_hash), 64)
        combined = json.dumps(payload, sort_keys=True).casefold()
        for forbidden in (
            "supplierid",
            "purchaseorder",
            "approved",
            "manufacturingauthorized",
            "lifecycle_state",
        ):
            self.assertNotIn(forbidden, combined)
        with self.assertRaises(RequestValidationFailed):
            manufacturing_plan_from_snapshot({**payload, "approved": True})

    def test_plan_successor_requires_exact_direct_tip(self) -> None:
        first = plan()
        second = plan(
            global_id=PLAN_R2,
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        validate_manufacturing_plan_successor(first, second)
        with self.assertRaises(RequestValidationFailed):
            validate_manufacturing_plan_successor(second, first)

    def test_planning_money_and_evidence_roles_fail_closed(self) -> None:
        self.assertEqual(PlanningMoney("100.00", "CNY").amount, "100.0")
        with self.assertRaises(RequestValidationFailed):
            PlanningMoney("100", "cny")
        with self.assertRaises(RequestValidationFailed):
            replace(plan(), budget=PlanningMoney("100", "USD"), version_key_hash=None)
        with self.assertRaises(RequestValidationFailed):
            replace(plan(), evidence=plan().evidence * 2, version_key_hash=None)
        conflicting = replace(released_document(), release_event_hash="f" * 64)
        with self.assertRaises(RequestValidationFailed):
            replace(
                plan(),
                evidence=(
                    ToolingPlanEvidence(ToolingPlanEvidenceRole.DFM, conflicting),
                ),
                version_key_hash=None,
            )

    def test_milestones_are_bounded_ordered_acyclic_and_responsibility_exact(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            plan(
                milestones=(
                    milestone(predecessors=(MILESTONE_2,)),
                    milestone(
                        global_id=MILESTONE_2,
                        sequence=2,
                        category=ToolingMilestoneCategory.MACHINING,
                        predecessors=(MILESTONE_1,),
                    ),
                )
            )
        with self.assertRaises(RequestValidationFailed):
            milestone(
                responsibility_kind=ToolingMilestoneResponsibilityKind.SUPPLIER,
                responsible_member=member(),
            )
        supplier = milestone(
            responsibility_kind=ToolingMilestoneResponsibilityKind.SUPPLIER,
        )
        self.assertIsNone(supplier.responsible_member)

    def test_design_release_and_manufacturing_authority_are_separate(self) -> None:
        released = released_document()
        satisfied = design_release_capability(
            ((released.revision_global_id, released.revision_snapshot_hash),),
            (released,),
        )
        self.assertEqual(satisfied.state, DesignReleaseEvidenceState.SATISFIED)
        self.assertIsNone(satisfied.reason_code)
        blocked = design_release_capability(
            ((released.revision_global_id, HASH_B),),
            (released,),
        )
        self.assertEqual(blocked.state, DesignReleaseEvidenceState.BLOCKED)
        self.assertEqual(
            blocked.reason_code,
            DesignReleaseBlockedReason.RELEASE_EVIDENCE_INCOMPLETE,
        )
        self.assertEqual(
            ManufacturingAuthorizationUnavailable().snapshot_payload(),
            {
                "state": "unavailable",
                "reasonCode": "tooling_lifecycle_policy_unavailable",
            },
        )
        with self.assertRaises(RequestValidationFailed):
            ManufacturingAuthorizationUnavailable(state="available")

    def test_observation_is_immutable_internal_reporter_truth(self) -> None:
        value = observation()
        payload = value.snapshot_payload()
        self.assertEqual(milestone_observation_from_snapshot(payload), value)
        self.assertEqual(payload["reportedByMember"]["userId"], member().user_id)
        combined = json.dumps(payload, sort_keys=True).casefold()
        for forbidden in ("supplieruser", "suppliersubmitted", "fileurl", "status"):
            self.assertNotIn(forbidden, combined)
        with self.assertRaises(RequestValidationFailed):
            milestone_observation_from_snapshot({**payload, "supplierSubmitted": True})

    def test_observation_successor_and_actual_dates_are_exact(self) -> None:
        first = observation()
        second = observation(
            global_id=OBSERVATION_2,
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        validate_milestone_observation_successor(first, second)
        with self.assertRaises(RequestValidationFailed):
            validate_milestone_observation_successor(second, first)
        with self.assertRaises(RequestValidationFailed):
            replace(first, actual_start=None, actual_finish=date(2026, 8, 12))

    def test_unavailable_erp_projection_is_the_default_closed_truth(self) -> None:
        unavailable = ToolingProcurementCostUnavailable()
        payload = unavailable.snapshot_payload()
        self.assertEqual(procurement_cost_projection_from_snapshot(payload), unavailable)
        self.assertEqual(payload["sourceSystem"], "ERPNEXT")
        self.assertEqual(payload["editableIn"], "ERPNEXT")
        with self.assertRaises(RequestValidationFailed):
            procurement_cost_projection_from_snapshot({**payload, "endpoint": "hidden"})
        with self.assertRaises(RequestValidationFailed):
            ToolingProcurementCostUnavailable(reason_code="connected")

    def test_available_erp_projection_retains_source_codes_and_exact_totals(self) -> None:
        rows = (
            cost_row(amount="1000"),
            cost_row(source_row_id="PINV-0001-L2", amount="250.50"),
            cost_row(
                source_row_id="PINV-0001-L3",
                amount="50",
                cost_type_code="FREIGHT-RAW",
            ),
        )
        summaries = aggregate_actual_costs(rows)
        self.assertEqual(
            [(value.cost_type_code, value.amount) for value in summaries],
            [("FREIGHT-RAW", "50.0"), ("RAW-MOLD-COST", "1250.5")],
        )
        available = ToolingProcurementCostAvailable(
            tooling_master_global_id=MASTER,
            observed_at=NOW,
            target_version="ERP-OBS-7",
            supplier=FormalSupplierReference(
                source_object_id="SUP-0001",
                target_version="3",
                supplier_code="SUP-0001",
                supplier_name="Synthetic Tooling Supplier",
            ),
            rows=rows,
            summaries=summaries,
        )
        self.assertEqual(
            procurement_cost_projection_from_snapshot(available.snapshot_payload()),
            available,
        )
        combined = json.dumps(available.snapshot_payload(), sort_keys=True).casefold()
        for forbidden in ("credential", "endpoint", "write", "retry", "dispatch"):
            self.assertNotIn(forbidden, combined)
        with self.assertRaises(RequestValidationFailed):
            replace(available, editable_in="NPI_ONE")

    def test_erp_projection_rejects_duplicate_currency_and_summary_mismatch(self) -> None:
        row = cost_row()
        with self.assertRaises(RequestValidationFailed):
            ToolingProcurementCostAvailable(
                tooling_master_global_id=MASTER,
                observed_at=NOW,
                target_version="ERP-OBS-7",
                supplier=FormalSupplierReference("SUP-0001", "3", "SUP-0001", "Supplier"),
                rows=(row, row),
                summaries=aggregate_actual_costs((row,)),
            )
        with self.assertRaises(RequestValidationFailed):
            ToolingProcurementCostAvailable(
                tooling_master_global_id=MASTER,
                observed_at=NOW,
                target_version="ERP-OBS-7",
                supplier=FormalSupplierReference("SUP-0001", "3", "SUP-0001", "Supplier"),
                rows=(row, cost_row(source_row_id="PINV-2-L1", currency="USD")),
                summaries=(),
            )
        with self.assertRaises(RequestValidationFailed):
            ToolingProcurementCostAvailable(
                tooling_master_global_id=MASTER,
                observed_at=NOW,
                target_version="ERP-OBS-7",
                supplier=FormalSupplierReference("SUP-0001", "3", "SUP-0001", "Supplier"),
                rows=(row,),
                summaries=(),
            )


if __name__ == "__main__":
    unittest.main()
