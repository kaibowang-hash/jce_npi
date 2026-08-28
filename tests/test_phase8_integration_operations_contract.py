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


class Phase8IntegrationOperationsContractTest(unittest.TestCase):
    def test_two_versioned_events_are_additive_closed_and_internal(self) -> None:
        event_types = EVENT["properties"]["event_type"]["enum"]
        for event_type in (
            "npi.integration_action.recorded",
            "npi.integration_reconciliation.observed",
        ):
            self.assertEqual(event_types.count(event_type), 1)
        conditions = {
            condition.get("if", {})
            .get("properties", {})
            .get("event_type", {})
            .get("const"): condition.get("then", {})
            for condition in EVENT["allOf"]
            if condition.get("if", {})
            .get("properties", {})
            .get("event_type", {})
            .get("const")
        }
        action = conditions["npi.integration_action.recorded"]["properties"]
        observation = conditions["npi.integration_reconciliation.observed"][
            "properties"
        ]
        self.assertEqual(action["object_type"]["const"], "IntegrationActionReceipt")
        self.assertEqual(
            action["payload"]["$ref"],
            "#/$defs/integration_action_recorded_v1",
        )
        self.assertEqual(
            observation["object_type"]["const"],
            "IntegrationReconciliationObservation",
        )
        self.assertEqual(
            observation["payload"]["$ref"],
            "#/$defs/integration_reconciliation_observed_v1",
        )
        internal = next(
            condition["then"]
            for condition in EVENT["allOf"]
            if condition.get("if", {})
            .get("properties", {})
            .get("event_type", {})
            .get("anyOf")
            == [
                {"const": "npi.integration_action.recorded"},
                {"const": "npi.integration_reconciliation.observed"},
            ]
        )
        self.assertEqual(internal["properties"]["event_version"]["const"], 1)
        self.assertEqual(internal["properties"]["source_system"]["const"], "NPI_ONE")
        self.assertEqual(internal["properties"]["target_system"]["const"], "NPI_ONE")
        self.assertEqual(internal["properties"]["sensitivity"]["const"], "internal")

    def test_event_components_are_exact_and_carry_no_generic_target_authority(self) -> None:
        operation = EVENT["$defs"]["integration_operation_reference_v1"]
        action = EVENT["$defs"]["integration_action_recorded_v1"]
        observation = EVENT["$defs"]["integration_reconciliation_observed_v1"]
        for schema in (operation, action, observation):
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertEqual(
            operation["properties"]["operation_kind"]["enum"],
            [
                "receive_project_submission",
                "publish_item",
                "publish_mbom",
                "create_tool_asset",
                "update_tool_asset",
            ],
        )
        self.assertEqual(action["properties"]["schema_version"]["const"], 1)
        self.assertEqual(observation["properties"]["schema_version"]["const"], 1)
        serialized = json.dumps(
            {"operation": operation, "action": action, "observation": observation},
            sort_keys=True,
        ).casefold()
        for forbidden in (
            "endpoint",
            "target_method",
            "target_doctype",
            "desired_status",
            "raw_payload",
            "raw_response",
            "credential",
            "authorization",
            "cookie",
            "secret",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_openapi_activates_only_project_first_fixed_checkpoint_two_routes(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        fixed_paths = (
            "/projects/{projectId}/integration-operations:",
            "/projects/{projectId}/integration-operations/dlq:",
            "/projects/{projectId}/integration-operations/{operationKind}/{integrationOperationId}:",
            "/projects/{projectId}/integration-operations/receive-project-submissions/{integrationOperationId}:replay:",
            "/projects/{projectId}/integration-operations/receive-project-submissions/{integrationOperationId}:request-reconciliation:",
            "/projects/{projectId}/integration-operations/item-publishes/{integrationOperationId}:replay:",
            "/projects/{projectId}/integration-operations/item-publishes/{integrationOperationId}:request-reconciliation:",
            "/projects/{projectId}/integration-operations/mbom-publishes/{integrationOperationId}:replay:",
            "/projects/{projectId}/integration-operations/mbom-publishes/{integrationOperationId}:request-reconciliation:",
            "/projects/{projectId}/integration-operations/tool-asset-creates/{integrationOperationId}:replay:",
            "/projects/{projectId}/integration-operations/tool-asset-creates/{integrationOperationId}:request-reconciliation:",
            "/projects/{projectId}/integration-operations/tool-asset-updates/{integrationOperationId}:replay:",
            "/projects/{projectId}/integration-operations/tool-asset-updates/{integrationOperationId}:request-reconciliation:",
        )
        for path in fixed_paths:
            self.assertEqual(paths.count(path), 1)
        for forbidden in (
            "/integration-operations/{integrationOperationId}:replay",
            "/integration-operations/{integrationOperationId}:request-reconciliation",
            "replayIntegrationOperation",
            "requestIntegrationReconciliation",
            "targetMethod",
            "targetDoctype",
        ):
            self.assertNotIn(forbidden, paths)
        schemas = OPENAPI[OPENAPI.index("  schemas:\n") :]
        for name in (
            "IntegrationOperationKind",
            "IntegrationOperationViewState",
            "IntegrationOperationReference",
            "IntegrationOperationItemFields",
            "IntegrationOperationItem",
            "IntegrationOperationCollection",
            "IntegrationOperationAttempt",
            "IntegrationOperationResult",
            "IntegrationOperationDetail",
            "IntegrationOperationActionRequest",
            "IntegrationOperationActionResult",
            "IntegrationActionReceipt",
            "IntegrationReconciliationObservation",
        ):
            self.assertEqual(schemas.count(f"    {name}:\n"), 1)
        block = schemas[
            schemas.index("    IntegrationOperationKind:\n") : schemas.index(
                "    ProblemDetails:\n"
            )
        ].casefold()
        self.assertIn("server-resolved operation kind", block)
        self.assertIn("operator input cannot assert target success", block)
        self.assertIn("trusted_operation_service", block)
        self.assertIn("authoritative_sandbox", block)
        for forbidden in (
            "frappe.client",
            "ignore_permissions",
            "targetmethod",
            "targetdoctype",
            "desiredstatus",
            "authorizationheader",
        ):
            self.assertNotIn(forbidden, block)
        self.assertIn(
            "raw target bodies and sensitive transport material are prohibited",
            block,
        )
        self.assertNotIn("additionalproperties: true", block)
        self.assertIn(
            'unevaluatedproperties: false\n      allof:\n        - $ref: "#/components/schemas/integrationoperationitemfields"',
            block,
        )
        self.assertEqual(
            block.count(
                '$ref: "#/components/schemas/integrationoperationitemfields"'
            ),
            2,
        )
        self.assertNotIn("#/components/pathItems/", OPENAPI)
        self.assertEqual(OPENAPI.count("<<: *integration-replay-action"), 5)
        self.assertEqual(
            OPENAPI.count("<<: *integration-reconciliation-action"),
            5,
        )
        for operation_id in (
            "replayProjectSubmissionIntegrationOperation",
            "requestProjectSubmissionIntegrationOperationReconciliation",
            "replayItemPublishIntegrationOperation",
            "requestItemPublishIntegrationOperationReconciliation",
            "replayMbomPublishIntegrationOperation",
            "requestMbomPublishIntegrationOperationReconciliation",
            "replayToolAssetCreateIntegrationOperation",
            "requestToolAssetCreateIntegrationOperationReconciliation",
            "replayToolAssetUpdateIntegrationOperation",
            "requestToolAssetUpdateIntegrationOperationReconciliation",
        ):
            self.assertEqual(OPENAPI.count(f"operationId: {operation_id}"), 1)

    def test_ownership_keeps_original_operation_and_formal_target_truth_authoritative(self) -> None:
        for marker in (
            "  IntegrationOperationProjection:\n    owner_system: NPI_ONE_INTEGRATION_OPERATIONS_SERVICE",
            "  IntegrationActionReceipt:\n    owner_system: NPI_ONE_INTEGRATION_OPERATIONS_SERVICE",
            "  IntegrationReconciliationObservation:\n    owner_system: NPI_ONE_OPERATION_SPECIFIC_RECONCILIATION_SERVICE",
            "raw_operation_state_and_fault_code: {owner: P8_02_TO_P8_05_OPERATION_SPECIFIC_OWNER",
            "replay_and_reconciliation_authority: {owner: P8_02_TO_P8_05_OPERATION_SPECIFIC_OWNER",
            "reconciliation_request: {owner: NPI_ONE_INTEGRATION_OPERATIONS_SERVICE, editable_in: [], direction: NONE, conflict: OPERATOR_INTENT_ONLY_NEVER_TARGET_TRUTH}",
            "human_asserted_target_success_or_identity: {owner: NEVER_ACCEPT",
            "forward_state_or_mapping_change: {owner: P8_02_TO_P8_05_OPERATION_SPECIFIC_OWNER",
            "raw_target_request_response_credentials_and_secrets: {owner: NEVER_PERSIST",
        ):
            self.assertIn(marker, OWNERSHIP)

    def test_existing_operation_contracts_are_not_reinterpreted(self) -> None:
        self.assertEqual(
            EVENT["$defs"]["item_publish_request_ready_v1"]["properties"][
                "operation"
            ]["const"],
            "publish_released_item",
        )
        self.assertEqual(
            EVENT["$defs"]["mbom_publish_request_ready_v1"]["properties"][
                "operation"
            ]["const"],
            "publish_released_mbom",
        )
        self.assertEqual(
            EVENT["$defs"]["tool_asset_request_ready_v2"]["properties"][
                "operation"
            ]["enum"],
            ["create_tool_asset", "update_tool_asset"],
        )


if __name__ == "__main__":
    unittest.main()
