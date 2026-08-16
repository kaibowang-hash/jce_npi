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


class Phase8ItemPublishContractTest(unittest.TestCase):
    def test_two_item_only_events_are_additive_closed_and_operation_specific(self) -> None:
        event_types = set(EVENT["properties"]["event_type"]["enum"])
        self.assertTrue(
            {
                "npi.item_publish_request.ready",
                "erpnext.item_publish_result.observed",
            }.issubset(event_types)
        )
        conditions = {
            condition.get("if", {})
            .get("properties", {})
            .get("event_type", {})
            .get("const"): condition.get("then", {})
            for condition in EVENT["allOf"]
        }
        request = conditions["npi.item_publish_request.ready"]
        result = conditions["erpnext.item_publish_result.observed"]
        self.assertEqual(request["properties"]["source_system"]["const"], "NPI_ONE")
        self.assertEqual(request["properties"]["target_system"]["const"], "ERPNEXT")
        self.assertEqual(request["properties"]["object_type"]["const"], "ItemPublishRequest")
        self.assertEqual(result["properties"]["source_system"]["const"], "ERPNEXT")
        self.assertEqual(result["properties"]["target_system"]["const"], "NPI_ONE")
        self.assertEqual(result["properties"]["object_type"]["const"], "ItemPublishRequest")
        self.assertEqual(
            request["properties"]["payload"]["$ref"],
            "#/$defs/item_publish_request_ready_v1",
        )
        self.assertEqual(
            result["properties"]["payload"]["$ref"],
            "#/$defs/item_publish_result_observed_v1",
        )

    def test_request_event_has_exact_item_fields_and_no_mbom_or_transport_authority(self) -> None:
        schema = EVENT["$defs"]["item_publish_request_ready_v1"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertEqual(schema["properties"]["api_version"]["const"], "npi.erp-item-publish.v1")
        self.assertEqual(schema["properties"]["operation"]["const"], "publish_released_item")
        self.assertEqual(schema["properties"]["target_mode"]["enum"], ["synthetic", "sandbox"])
        serialized = json.dumps(schema, sort_keys=True).casefold()
        for forbidden in (
            "mbom",
            "quantity",
            "effectivity",
            "endpoint",
            "method",
            "doctype",
            "secret",
            "credential",
            "authorization",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_result_event_requires_authenticated_authoritative_truth_for_formal_identity(self) -> None:
        schema = EVENT["$defs"]["item_publish_result_observed_v1"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        succeeded = next(
            branch
            for branch in schema["allOf"]
            if branch["if"]["properties"]["state"]["const"] == "succeeded"
        )
        truth = succeeded["then"]["properties"]
        self.assertEqual(truth["authority"]["const"], "authoritative_sandbox")
        self.assertTrue(truth["response_authenticated"]["const"])
        self.assertEqual(truth["formal_item_code"]["type"], "string")
        self.assertEqual(truth["target_version"]["type"], "string")
        self.assertEqual(succeeded["else"]["properties"]["formal_item_code"]["type"], "null")
        synthetic = next(
            branch
            for branch in schema["allOf"]
            if branch["if"]["properties"]["state"]["const"] == "synthetic_verified"
        )["then"]["properties"]
        self.assertEqual(synthetic["authority"]["const"], "synthetic")
        self.assertFalse(synthetic["response_authenticated"]["const"])

    def test_openapi_adds_item_schemas_without_activating_item_routes(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertNotIn("/item-publish-requests", paths)
        schemas = OPENAPI[OPENAPI.index("  schemas:\n") :]
        for name in (
            "ItemPublishSourceSnapshot",
            "ItemPublishReleasedEvidence",
            "ItemPublishProfileReference",
            "ItemPublishMappingExpectation",
            "ItemPublishRequest",
            "ItemPublishAttempt",
            "ItemPublishResult",
            "ItemMappingObservation",
            "ItemMappingHead",
            "ItemPublishPermissions",
        ):
            self.assertIn(f"    {name}:\n", schemas)
        item = schemas[
            schemas.index("    ItemPublishSha256:\n") : schemas.index(
                "    ProblemDetails:\n"
            )
        ].casefold()
        for forbidden in (
            "publish_released_ebom_item_mbom",
            "formalmbom",
            "endpoint",
            "secret",
            "credential",
            "authorizationheader",
        ):
            self.assertNotIn(forbidden, item)
        self.assertIn("local commit does not mean target acceptance or success", item)
        self.assertIn("authenticated authoritative sandbox success", item)

    def test_ownership_separates_npi_execution_truth_from_erp_item_master_truth(self) -> None:
        for marker in (
            "  ItemPublishRequest:\n    owner_system: NPI_ONE",
            "  ItemPublishCommandIdempotency:\n    owner_system: NPI_ONE_ITEM_PUBLISH_COMMAND",
            "  ItemPublishOutboxMessage:\n    owner_system: NPI_ONE_ITEM_EXECUTION_SERVICE",
            "  ItemPublishAttempt:\n    owner_system: NPI_ONE_ITEM_EXECUTION_SERVICE",
            "  ItemPublishResult:\n    owner_system: SPLIT_BY_FIELD",
            "  ItemMappingObservation:\n    owner_system: SPLIT_BY_FIELD",
            "  ItemMappingHead:\n    owner_system: NPI_ONE_INTEGRATION_PROJECTION",
            "formal_item_code_stock_uom_item_group_naming_and_target_version: {owner: ERPNEXT",
            "raw_idempotency_key: {owner: REQUEST_TRANSPORT",
            "raw_secret_authorization_header_and_arbitrary_response_body: {owner: SECRET_AND_TRANSPORT_BOUNDARY",
            "legacy_outbox_execution_authority: {owner: NONE",
            "retry_or_reconciliation_authority: {owner: FUTURE_P8_07_RETRY_POLICY",
            "synthetic_or_mock_formal_mapping: {owner: NONE",
        ):
            self.assertIn(marker, OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
