from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
BFF = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")


def _schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase6ToolingManufacturingContractTest(unittest.TestCase):
    OBJECT_SCHEMAS = (
        "ToolingProjectMemberResponsibility",
        "ToolingPlanningMoney",
        "ToolingReleasedDocumentEvidence",
        "ToolingManufacturingPlanEvidence",
        "ToolingManufacturingMilestone",
        "ToolingManufacturingPlanRevision",
        "ToolingMilestoneFileEvidence",
        "ToolingManufacturingMilestoneObservation",
        "ToolingDesignReleaseEvidenceCapability",
        "ToolingManufacturingAuthorizationUnavailable",
        "ToolingFormalSupplierReference",
        "ToolingErpActualCostRow",
        "ToolingErpActualCostSummary",
        "ToolingProcurementCostUnavailable",
        "ToolingProcurementCostAvailable",
    )

    def test_foundation_schemas_are_closed_but_routes_are_not_active(self) -> None:
        for name in self.OBJECT_SCHEMAS:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", _schema(name))
        projection = _schema("ToolingProcurementCostProjection")
        self.assertIn("ToolingProcurementCostUnavailable", projection)
        self.assertIn("ToolingProcurementCostAvailable", projection)
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertNotIn("/manufacturing-plans", paths)
        for command in (
            "get_tooling_manufacturing_plans",
            "create_tooling_manufacturing_plan",
            "create_tooling_manufacturing_milestone_observation",
            "tooling_manufacturing_routes_are_disabled",
        ):
            self.assertNotIn(command, BFF)

    def test_plan_contract_separates_design_release_from_manufacturing_authority(self) -> None:
        plan = _schema("ToolingManufacturingPlanRevision")
        released = _schema("ToolingReleasedDocumentEvidence")
        capability = _schema("ToolingDesignReleaseEvidenceCapability")
        authorization = _schema("ToolingManufacturingAuthorizationUnavailable")
        for marker in (
            "toolingRevisionGlobalId:", "sourcingStrategy:",
            "engineeringEstimate:", "budget:", "designReleaseEvidence:",
            "milestones:",
        ):
            self.assertIn(marker, plan)
        for marker in (
            "lifecycleGlobalId:", "lifecycleVersion:", "releaseEventGlobalId:",
            "releaseEventHash:", "releaseSnapshotHash:",
        ):
            self.assertIn(marker, released)
        self.assertIn("enum: [satisfied, blocked]", capability)
        self.assertIn("const: tooling_lifecycle_policy_unavailable", authorization)
        combined = "\n".join((plan, capability, authorization)).casefold()
        for forbidden in ("approvedfunding", "g3pass", "supplierid", "purchaseorderid"):
            self.assertNotIn(forbidden, combined)

    def test_milestone_contract_is_internal_reporter_and_clean_reference_only(self) -> None:
        milestone = _schema("ToolingManufacturingMilestone")
        observation = _schema("ToolingManufacturingMilestoneObservation")
        evidence = _schema("ToolingMilestoneFileEvidence")
        for category in (
            "design", "material_preparation", "heat_treatment", "machining",
            "assembly", "trial_preparation", "delivery",
        ):
            self.assertIn(category, milestone)
        self.assertIn("responsibilityKind: { type: string, enum: [internal, supplier] }", milestone)
        self.assertIn("reportedByMember:", observation)
        self.assertNotIn("supplierSubmitted", observation)
        self.assertIn("fileRevisionGlobalId:", evidence)
        self.assertIn("frappeContentHash:", evidence)
        self.assertNotIn("fileUrl:", evidence)

    def test_erp_projection_is_closed_read_only_exact_source_truth(self) -> None:
        unavailable = _schema("ToolingProcurementCostUnavailable")
        available = _schema("ToolingProcurementCostAvailable")
        row = _schema("ToolingErpActualCostRow")
        self.assertIn("const: erp_projection_unavailable", unavailable)
        for schema in (unavailable, available):
            self.assertIn("const: ERPNEXT", schema)
            self.assertIn("editableIn:", schema)
        for marker in (
            "supplierSourceObjectId:", "purchaseOrderSourceId:",
            "purchaseReceiptSourceId:", "purchaseInvoiceSourceId:",
            "actualCostSourceId:", "costTypeCode:", "sourceRowVersion:",
        ):
            self.assertIn(marker, row)
        combined = "\n".join((unavailable, available, row)).casefold()
        for forbidden in ("credential", "endpoint", "writecapability", "dispatch", "retry"):
            self.assertNotIn(forbidden, combined)

    def test_ownership_contract_keeps_npi_and_erp_authority_separate(self) -> None:
        for object_name in (
            "ToolingManufacturingPlanRevision",
            "ToolingManufacturingMilestoneObservation",
            "ToolingProcurementCostProjection",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        self.assertIn("internal_sourcing_engineering_estimate_budget_and_responsibility: {owner: NPI_ONE_TOOLING_MANUFACTURING_COMMAND", OWNERSHIP)
        self.assertIn("exact_released_planning_and_design_document_evidence: {owner: NPI_ONE_DOCUMENT_RELEASE_COMMAND", OWNERSHIP)
        self.assertIn("tooling_lifecycle_and_manufacturing_authority: {owner: FUTURE_APPROVED_TOOLING_POLICY", OWNERSHIP)
        self.assertIn("formal_supplier_purchase_order_receipt_invoice_and_actual_cost: {owner: ERPNEXT", OWNERSHIP)
        self.assertIn("production_projection_connection_and_reconciliation: {owner: FUTURE_PHASE_8_INTEGRATION_ADAPTER", OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
