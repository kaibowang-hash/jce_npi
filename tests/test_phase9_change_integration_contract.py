from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVENT = json.loads(
    (ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8")
)
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
BFF = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")


class Phase9ChangeIntegrationContractTest(unittest.TestCase):
    def test_event_contract_adds_exact_signed_inbound_and_summary_types(self) -> None:
        event_types = EVENT["properties"]["event_type"]["enum"]
        expected = (
            "npi.erp-engineering-change.v1",
            "npi.change-implementation-summary.v1",
        )
        for event_type in expected:
            self.assertEqual(event_types.count(event_type), 1)
        conditions = {
            item.get("if", {})
            .get("properties", {})
            .get("event_type", {})
            .get("const"): item["then"]
            for item in EVENT["allOf"]
            if item.get("if", {})
            .get("properties", {})
            .get("event_type", {})
            .get("const")
        }
        inbound = conditions[expected[0]]["properties"]
        outbound = conditions[expected[1]]["properties"]
        self.assertEqual(inbound["source_system"]["const"], "ERPNEXT")
        self.assertEqual(inbound["target_system"]["const"], "NPI_ONE")
        self.assertEqual(
            inbound["payload"]["$ref"],
            "#/$defs/engineering_change_observation_event_v1",
        )
        self.assertEqual(outbound["source_system"]["const"], "NPI_ONE")
        self.assertEqual(outbound["target_system"]["const"], "ERPNEXT")
        self.assertEqual(
            outbound["payload"]["$ref"],
            "#/$defs/change_implementation_summary_v1",
        )
        for name in (
            "engineering_change_observation_event_v1",
            "change_implementation_summary_v1",
        ):
            schema = EVENT["$defs"][name]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_openapi_has_only_operation_specific_inbound_and_project_first_summary_routes(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        for path in (
            "/integration/erpnext/engineering-change-events:",
            "/projects/{projectId}/engineering-changes/{changeId}:request-implementation-summary:",
        ):
            self.assertEqual(paths.count(path), 1)
        for operation in (
            "acceptErpnextEngineeringChangeEvent",
            "requestEngineeringChangeImplementationSummary",
        ):
            self.assertEqual(paths.count(f"operationId: {operation}"), 1)
        self.assertIn("x-signature-scheme: hmac-sha256-v1", paths)
        self.assertIn("x-transaction-boundary: engineering-change-summary-request", paths)
        for forbidden in (
            "frappe.client",
            "targetDoctype",
            "targetMethod",
            "desiredStatus",
            "genericEngineeringChangeWriter",
        ):
            self.assertNotIn(forbidden, paths)

    def test_bff_forwards_exact_routes_without_browser_target_authority(self) -> None:
        for marker in (
            '"npi_integration.engineering_change_api.receive_engineering_change_event"',
            '"npi_integration.engineering_change_api."',
            '"request_change_implementation_summary"',
            '"/api/npi/v1/integration/erpnext/engineering-change-events"',
            'r"(?P<change_id>[^/:]+):request-implementation-summary$"',
        ):
            self.assertIn(marker, BFF)
        self.assertNotIn("frappe.client.set_value", BFF)

    def test_ownership_preserves_erp_formal_truth_and_npi_engineering_process_truth(self) -> None:
        for marker in (
            "  EngineeringChangeIntegrationInbox:\n    owner_system: NPI_ONE_ENGINEERING_CHANGE_INTEGRATION_SERVICE",
            "  EngineeringChangeImplementationSummaryRequest:\n    owner_system: NPI_ONE_ENGINEERING_CHANGE_INTEGRATION_SERVICE",
            "formal_change_identifier_raw_status_source_version_and_effectivity_transaction_truth: {owner: ERPNEXT",
            "effectivity_disposition_cost_and_closure_evidence: {owner: NPI_ONE_CHANGE_CONTROL_SERVICE",
            "raw_target_request_response_credentials_and_secrets: {owner: NEVER_PERSIST",
        ):
            self.assertIn(marker, OWNERSHIP)
        self.assertNotIn("owner: SHARED", OWNERSHIP)

    def test_p8_operations_are_read_only_for_p9_operation_specific_records(self) -> None:
        for kind in (
            "receive_engineering_change_event",
            "publish_change_implementation_summary",
        ):
            self.assertIn(kind, OPENAPI)
        repository = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/frappe_repository.py"
        ).read_text(encoding="utf-8")
        self.assertIn("IntegrationOperationKind.RECEIVE_ENGINEERING_CHANGE_EVENT", repository)
        self.assertIn("IntegrationOperationKind.PUBLISH_CHANGE_IMPLEMENTATION_SUMMARY", repository)
        self.assertIn("IntegrationOperationConflict", repository)


if __name__ == "__main__":
    unittest.main()
