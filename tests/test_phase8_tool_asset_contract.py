from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENT = json.loads((ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8"))
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")


class Phase8ToolAssetContractTest(unittest.TestCase):
    def test_v2_events_are_additive_closed_and_operation_specific(self) -> None:
        event_types = EVENT["properties"]["event_type"]["enum"]
        self.assertEqual(event_types.count("npi.tool_asset_request.ready"), 1)
        self.assertEqual(event_types.count("erpnext.tool_asset_result.observed"), 1)
        request = EVENT["$defs"]["tool_asset_request_ready_v2"]
        result = EVENT["$defs"]["tool_asset_result_observed_v2"]
        for schema in (request, result):
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertEqual(request["properties"]["schema_version"]["const"], 2)
        self.assertEqual(request["properties"]["operation"]["enum"], ["create_tool_asset", "update_tool_asset"])
        self.assertNotIn("create_or_update_tool_asset", str(request))
        self.assertNotIn("endpoint", str(request).casefold())
        self.assertNotIn("credential", str(request).casefold())

    def test_result_schema_keeps_partial_uncertain_and_authoritative_success_distinct(self) -> None:
        result = EVENT["$defs"]["tool_asset_result_observed_v2"]
        self.assertIn("partially_succeeded", result["properties"]["state"]["enum"])
        self.assertIn("uncertain_after_timeout", result["properties"]["state"]["enum"])
        succeeded = result["allOf"][0]["then"]["properties"]
        self.assertEqual(succeeded["authority"]["const"], "authoritative_sandbox")
        self.assertTrue(succeeded["response_authenticated"]["const"])
        for branch in result["allOf"][1:]:
            state = branch["if"]["properties"]["state"]
            if state.get("const") == "synthetic_verified" or "uncertain_after_timeout" in state.get("enum", []):
                self.assertEqual(branch["then"]["properties"]["formal_asset_id"]["type"], "null")

    def test_openapi_adds_components_only_without_activating_routes(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertNotIn("tool-asset-execution-requests", paths)
        schemas = OPENAPI[OPENAPI.index("  schemas:\n") :]
        for name in ("ToolAssetExecutionOperation", "ToolAssetExecutionTargetMode", "ToolAssetExecutionSource", "ToolAssetBusinessApprovalReference", "ToolAssetMappingExpectationV2", "ToolAssetExecutionProfileReference", "ToolAssetExecutionRequestV2", "ToolAssetExecutionFieldResult"):
            self.assertEqual(schemas.count(f"    {name}:\n"), 1)
        block = schemas[schemas.index("    ToolAssetExecutionOperation:\n") : schemas.index("    ToolAssetFormalMappingUnavailable:\n")].casefold()
        for forbidden in ("frappe.client", "ignore_permissions", "endpoint", "credential", "submit", "move_asset", "repair_asset"):
            self.assertNotIn(forbidden, block)
        source = block[block.index("toolassetexecutionsource:") : block.index("toolassetbusinessapprovalreference:")]
        for exact_source_field in (
            "toolingmastertitle", "toolingrequirementkind", "toolingrevisionlabel",
            "acceptanceglobalid", "acceptancepredecessorglobalid",
            "acceptancepredecessorsnapshothash",
        ):
            self.assertIn(exact_source_field, source)

    def test_ownership_keeps_npi_intent_and_erp_asset_truth_separate(self) -> None:
        for marker in ("  ToolAssetExecutionRequest:\n    owner_system: NPI_ONE_TOOL_ASSET_EXECUTION_COMMAND", "  ToolAssetExecutionOutboxMessage:\n    owner_system: NPI_ONE_TOOL_ASSET_EXECUTION_SERVICE", "  ToolAssetExecutionAttempt:\n    owner_system: NPI_ONE_TOOL_ASSET_EXECUTION_SERVICE", "  ToolAssetExecutionResult:\n    owner_system: NPI_ONE_TOOL_ASSET_EXECUTION_SERVICE", "  ToolAssetMappingObservation:\n    owner_system: NPI_ONE_TOOL_ASSET_EXECUTION_SERVICE", "  ToolAssetMappingHead:\n    owner_system: NPI_ONE_TOOL_ASSET_EXECUTION_SERVICE", "formal_asset_identity_version_lifecycle_location_maintenance_repair_and_spares: {owner: ERPNEXT"):
            self.assertIn(marker, OWNERSHIP)
        self.assertIn("partial_uncertain_mock_and_synthetic_results", OWNERSHIP)
        self.assertIn("NEVER_ADVANCE_MAPPING", OWNERSHIP)

    def test_legacy_v1_contracts_remain_unchanged_and_distinct(self) -> None:
        legacy = EVENT["$defs"]["tooling_asset_request_ready_v1"]
        self.assertEqual(legacy["properties"]["operation"]["const"], "create_or_update_tool_asset")
        self.assertEqual(legacy["properties"]["schema_version"]["const"], 1)
        self.assertEqual(OPENAPI.count("const: create_or_update_tool_asset"), 1)


if __name__ == "__main__":
    unittest.main()
