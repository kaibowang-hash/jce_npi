from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVENT_SCHEMA = json.loads(
    (ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8")
)
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")


class Phase8InboundProjectContractTest(unittest.TestCase):
    def test_shared_event_schema_has_only_two_closed_project_source_events(self) -> None:
        event_types = set(EVENT_SCHEMA["properties"]["event_type"]["enum"])
        self.assertTrue(
            {
                "erpnext.quotation.submitted",
                "erpnext.sales_order.submitted",
            }.issubset(event_types)
        )
        self.assertNotIn("erpnext.generic_doc.submitted", event_types)
        payload = EVENT_SCHEMA["$defs"]["erp_project_source_submitted_v1"]
        self.assertFalse(payload["additionalProperties"])
        self.assertEqual(set(payload["required"]), set(payload["properties"]))
        common = next(
            condition
            for condition in EVENT_SCHEMA["allOf"]
            if condition.get("if", {}).get("properties", {}).get("event_type", {}).get("anyOf")
            == [
                {"const": "erpnext.quotation.submitted"},
                {"const": "erpnext.sales_order.submitted"},
            ]
        )["then"]
        self.assertEqual(common["properties"]["source_system"]["const"], "ERPNEXT")
        self.assertEqual(common["properties"]["target_system"]["const"], "NPI_ONE")
        self.assertEqual(common["properties"]["sensitivity"]["const"], "confidential")
        self.assertFalse(common["properties"]["causation_id"])
        self.assertFalse(common["properties"]["idempotency_key"])
        self.assertEqual(common["properties"]["actor"]["properties"]["type"]["const"], "service")
        self.assertEqual(
            set(common["required"]),
            {"target_system", "source_object_id", "correlation_id", "actor", "payload_hash", "sensitivity"},
        )

    def test_object_type_is_tied_to_each_event_and_source_version_is_positive(self) -> None:
        conditions = {
            condition.get("if", {}).get("properties", {}).get("event_type", {}).get("const"):
            condition.get("then", {}).get("properties", {})
            for condition in EVENT_SCHEMA["allOf"]
        }
        self.assertEqual(
            conditions["erpnext.quotation.submitted"]["object_type"]["const"],
            "Quotation",
        )
        self.assertEqual(
            conditions["erpnext.sales_order.submitted"]["object_type"]["const"],
            "Sales Order",
        )
        common = next(
            condition["then"]["properties"]
            for condition in EVENT_SCHEMA["allOf"]
            if condition.get("if", {}).get("properties", {}).get("event_type", {}).get("anyOf")
            == [
                {"const": "erpnext.quotation.submitted"},
                {"const": "erpnext.sales_order.submitted"},
            ]
        )
        self.assertEqual(common["object_version"]["minimum"], 1)
        self.assertEqual(common["event_version"]["const"], 1)

    def test_openapi_exposes_one_hmac_only_contract_without_session_or_generic_crud(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        marker = "  /integration/erpnext/project-source-events:"
        self.assertEqual(paths.count(marker), 1)
        route = paths[paths.index(marker) : paths.index("\n  /session/bootstrap:")]
        for expected in (
            "operationId: acceptErpnextProjectSourceEvent",
            "security: []",
            "X-Request-ID",
            "X-NPI-Key-ID",
            "X-NPI-Timestamp",
            "X-NPI-Signature",
            '"202":',
            '"401":',
            '"409":',
            '"413":',
            '"415":',
            '"422":',
            '"503":',
            "durable Inbox acceptance",
            "never Project creation",
        ):
            self.assertIn(expected, route)
        self.assertNotIn("CsrfToken", route)
        self.assertNotIn("sessionAuth", route)
        self.assertNotIn("doctype", route.casefold())
        schemas = OPENAPI[OPENAPI.index("  schemas:\n") :]
        for name in (
            "InboundProjectSourcePayload",
            "InboundProjectSourceEvent",
            "InboundProjectReceiptAccepted",
        ):
            self.assertIn(f"    {name}:\n", schemas)
        event_schema = schemas[
            schemas.index("    InboundProjectSourceEvent:\n") :
            schemas.index("    InboundProjectReceiptAccepted:\n")
        ]
        self.assertIn("additionalProperties: false", event_schema)
        self.assertNotIn("tenant", event_schema.casefold())
        self.assertNotIn("template", event_schema.casefold())
        self.assertNotIn("owner_user", event_schema)

    def test_ownership_has_one_way_source_truth_and_never_persisted_secrets(self) -> None:
        for marker in (
            "  ERPProjectSourceEvent:\n    owner_system: ERPNEXT",
            "  InboundProjectReceipt:\n    owner_system: NPI_ONE_INBOUND_PROJECT_SERVICE",
            "  ProjectSourceBinding:\n    owner_system: NPI_ONE_INBOUND_PROJECT_SERVICE",
            "  InboundProjectProfileAndPolicy:\n    owner_system: NPI_ONE_ADMIN",
            "raw_hmac_secret: {owner: EXTERNAL_SECRET_RESOLVER",
            "legacy_inbox_rows: {owner: LEGACY_INTEGRATION_HISTORY",
            "bound_project_version_payload_and_policy: {owner: NPI_ONE_INBOUND_PROJECT_SERVICE",
            "erp_project_source_binding_and_initial_draft_seed: {owner: NPI_ONE_INBOUND_PROJECT_SERVICE",
        ):
            self.assertIn(marker, OWNERSHIP)
        inbound = OWNERSHIP[
            OWNERSHIP.index("  ERPProjectSourceEvent:") :
            OWNERSHIP.index("  GateTemplate:")
        ]
        self.assertNotIn("editable_in: [NPI_ONE]", inbound)
        self.assertIn("NEVER_PERSIST", inbound)


if __name__ == "__main__":
    unittest.main()
