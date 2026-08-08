from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
EVENT = json.loads((ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8"))
BFF = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
API = (ROOT / "apps/npi_core/npi_core/tooling_api.py").read_text(encoding="utf-8")


def schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase6ToolingAcceptanceContractTest(unittest.TestCase):
    CLOSED_SCHEMAS = (
        "ToolingAcceptanceFileEvidenceInput",
        "ToolingAcceptanceChecklistItemInput",
        "ToolingAssetActionEvidenceInput",
        "ToolingSpareRecommendationInput",
        "ToolingRepairEvidenceInput",
        "CreateToolingAcceptanceEvidenceRevision",
        "CreateToolAssetRequest",
        "ToolingAcceptanceFileEvidence",
        "ToolingAcceptanceChecklistItem",
        "ToolingAssetActionEvidence",
        "ToolingSpareRecommendation",
        "ToolingRepairEvidence",
        "ToolingAcceptanceCategoryCoverage",
        "ToolingAcceptanceEvidenceRevision",
        "ToolAssetProjectionUnavailable",
        "ToolAssetMovementObservation",
        "ToolAssetRepairObservation",
        "ToolAssetSpareInventoryObservation",
        "ToolAssetProjectionAvailable",
        "ToolAssetRequestInput",
        "ToolAssetFormalMappingUnavailable",
        "ToolAssetTargetNotRequested",
        "ToolAssetRequest",
        "ToolAssetRequestCollection",
        "ToolingAcceptanceAssetPermissions",
        "ToolingAcceptanceAssetContext",
        "ToolingAcceptanceEvidenceCommand",
    )

    def test_checkpoint_one_contract_is_closed_but_runtime_routes_are_not_active(self) -> None:
        for name in self.CLOSED_SCHEMAS:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", schema(name))
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        for marker in (
            "/acceptance-assets:",
            "/acceptance-revisions:",
            "/asset-requests:",
            "getToolingAcceptanceAssets",
            "createToolingAcceptanceEvidenceRevision",
            "createToolAssetRequest",
            "getToolAssetRequest",
        ):
            self.assertIn(marker, paths)
        self.assertNotIn("create_tooling_acceptance_evidence_revision", BFF + API)
        self.assertNotIn("create_tool_asset_request", BFF + API)

    def test_checklist_has_every_required_category_without_approval_input(self) -> None:
        item = schema("ToolingAcceptanceChecklistItemInput")
        create = schema("CreateToolingAcceptanceEvidenceRevision")
        for category in (
            "technical", "quality", "cycle_capacity", "spares_maintenance",
            "documents", "warranty_responsibility", "cost", "safety_interface",
            "asset_location",
        ):
            self.assertIn(category, item)
        for disposition in (
            "evidence_recorded", "evidence_missing", "not_applicable_asserted",
        ):
            self.assertIn(disposition, item)
        combined = (item + create).casefold()
        for forbidden in (
            "approved:", "accepted:", "gateid", "lifecyclestate", "trialresult",
            "officialqualityresult",
        ):
            self.assertNotIn(forbidden, combined)

    def test_asset_request_is_operation_specific_mock_draft_and_cannot_claim_target_truth(self) -> None:
        create = schema("CreateToolAssetRequest")
        request_input = schema("ToolAssetRequestInput")
        result = schema("ToolAssetRequest")
        self.assertIn("const: mock", create)
        self.assertIn("const: create_or_update_tool_asset", result)
        self.assertIn("const: draft", result)
        self.assertIn("const: validated_mock", result)
        self.assertIn("businessApprovalState: { type: string, const: unavailable }", result)
        self.assertIn("dispatchState: { type: string, const: prohibited }", result)
        self.assertIn("targetResultState: { type: string, const: not_requested }", result)
        for forbidden in (
            "operation:", "payload:", "formalAssetId:", "assetState:",
            "location:", "succeeded", "endpoint", "credential",
        ):
            self.assertNotIn(forbidden, create)
        self.assertNotIn("/execution-requests:", OPENAPI)
        self.assertNotIn("CreateExecutionRequest", OPENAPI)
        self.assertIn("toolingRevisionLabel:", request_input)
        self.assertIn("tooling_requirement_kind", request_input)
        for invented_field in (
            "toolingMasterBusinessCode", "toolingRevisionCode",
            "setRevisionBindingVersion", "expectedBindingVersion",
        ):
            self.assertNotIn(invented_field, OPENAPI)

    def test_projection_and_ownership_keep_physical_set_and_erpnext_truth(self) -> None:
        unavailable = schema("ToolAssetProjectionUnavailable")
        available = schema("ToolAssetProjectionAvailable")
        for marker in (
            "const: ERPNEXT", "const: unavailable",
            "const: zero_or_one_per_physical_set",
        ):
            self.assertIn(marker, unavailable)
        for marker in (
            "toolingSetGlobalId:", "formalAssetId:", "assetState:",
            "currentLocation:", "shotCount:", "maintenanceDue:",
            "movements:", "repairs:", "spares:",
        ):
            self.assertIn(marker, available)
        for object_name in (
            "ToolingAcceptanceEvidenceRevision", "ToolAssetRequest",
            "ToolAssetCommandIdempotency", "ToolAssetProjection",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        self.assertIn("zero_or_one_mapping_per_physical_set", OWNERSHIP)
        self.assertIn("owner: ERPNEXT", OWNERSHIP)
        self.assertIn("owner: FUTURE_APPROVED_TOOLING_POLICY", OWNERSHIP)

    def test_future_event_contract_is_closed_and_not_a_phase_six_dispatch_claim(self) -> None:
        definitions = EVENT["$defs"]
        command = definitions["tooling_asset_request_ready_v1"]
        result = definitions["tooling_asset_result_observed_v1"]
        self.assertFalse(command["additionalProperties"])
        self.assertFalse(result["additionalProperties"])
        self.assertEqual(command["properties"]["operation"]["const"], "create_or_update_tool_asset")
        self.assertEqual(command["properties"]["target_mode"]["const"], "sandbox")
        self.assertIn("business_approval_evidence_id", command["required"])
        self.assertIn("tooling_set_global_id", result["required"])
        self.assertIn("formal_asset_id", result["required"])
        self.assertNotIn("mock", json.dumps(command))


if __name__ == "__main__":
    unittest.main()
