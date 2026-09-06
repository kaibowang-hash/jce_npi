from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
EVENT = json.loads(
    (ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8")
)


def schema(name: str) -> str:
    start = OPENAPI.split(f"    {name}:\n", 1)[1]
    match = re.search(r"\n    [A-Za-z][A-Za-z0-9]+:\n", start)
    return start if match is None else start[: match.start()]


class Phase5PublishRequestContractTest(unittest.TestCase):
    PATH = (
        "/projects/{projectId}/eboms/{ebomId}/revisions/{revisionId}/"
        "publish-requests"
    )

    def test_operation_specific_routes_replace_generic_create_and_retry(self) -> None:
        section = OPENAPI.split(f"  {self.PATH}:\n", 1)[1].split(
            "\ncomponents:\n", 1
        )[0]
        self.assertIn("operationId: listEngineeringBomPublishRequests", section)
        self.assertIn("operationId: createEngineeringBomPublishRequest", section)
        self.assertIn("operationId: getEngineeringBomPublishRequest", section)
        self.assertIn(
            "x-business-authority: exact-publish-request-policy-requester",
            section,
        )
        self.assertIn(
            "x-transaction-boundary: ebom-publish-request-input-mapping-result",
            section,
        )
        self.assertIn("x-audit-operation: ebom.publish_request.create", section)
        for header in ("IdempotencyKey", "RequestId", "CsrfToken"):
            self.assertIn(f'#/components/parameters/{header}', section)
        self.assertNotIn("/execution-requests:", OPENAPI)
        self.assertNotIn("retryExecutionRequest", OPENAPI)
        self.assertNotIn("CreateExecutionRequest", OPENAPI)

    def test_browser_create_schema_is_closed_and_cannot_select_operation_or_payload(self) -> None:
        request = schema("CreateEngineeringBomPublishRequest")
        self.assertIn("additionalProperties: false", request)
        self.assertIn("expectedEbomVersion", request)
        self.assertIn("expectedRevisionSnapshotHash", request)
        self.assertIn("expectedLifecycleVersion", request)
        self.assertIn("publishPolicySnapshotHash", request)
        self.assertIn("const: mock", request)
        self.assertIn("const: true", request)
        self.assertIn(
            "const: validate_exact_released_ebom_for_item_mbom_publish",
            request,
        )
        self.assertNotIn("payload:", request)
        self.assertNotIn("operation:", request)
        self.assertNotIn("approvalEvidenceIds", request)

    def test_response_binds_exact_release_evidence_and_per_node_truth(self) -> None:
        request = schema("EngineeringBomPublishRequest")
        evidence = schema("ReleasedEngineeringBomPublishEvidence")
        node = schema("EngineeringBomPublishNode")
        result = schema("EngineeringBomPublishNodeResult")
        mapping = schema("EngineeringBomPublishMappingObservation")

        for value in (request, evidence, node, result, mapping):
            self.assertIn("additionalProperties: false", value)
        for exact in (
            "revisionSnapshotHash",
            "lifecycleVersion",
            "releaseEventGlobalId",
            "releaseEventHash",
            "approvalEvidenceIds",
            "ebomPolicySnapshotHash",
        ):
            self.assertIn(exact, evidence)
        self.assertIn("const: publish_released_ebom_item_mbom", request)
        self.assertIn("const: npi.erp-publish.v1", request)
        self.assertIn("dispatchAllowed", request)
        self.assertIn("const: false", request)
        self.assertIn("maxItems: 500", request)
        for operation in (
            "create_item",
            "update_item_engineering_fields",
            "create_or_update_mbom",
        ):
            self.assertIn(operation, node)
        self.assertIn("results", node)
        self.assertIn("futureRetryDirective", result)
        self.assertIn("reconciliationRequired", result)
        self.assertIn("retryAfterRequired", result)
        self.assertIn("phase5DispatchAllowed", result)
        self.assertIn("nodeGlobalId", result)
        self.assertIn("nodeInputHash", result)
        self.assertIn('formalItemCode: { type: "null" }', mapping)
        self.assertIn('formalMbomId: { type: "null" }', mapping)
        self.assertIn('formalItemCode: { type: "null" }', result)
        self.assertIn('formalMbomId: { type: "null" }', result)

    def test_mock_contract_cannot_claim_queued_or_succeeded_request_state(self) -> None:
        request = schema("EngineeringBomPublishRequest")
        self.assertIn("targetMode: { type: string, const: mock }", request)
        self.assertIn("state: { type: string, enum: [validated, manual_intervention] }", request)
        for forbidden in ("queued", "processing", "succeeded", "partially_succeeded"):
            self.assertNotIn(forbidden, request)
        capabilities = schema("EngineeringBomPublishCapabilities")
        for name in ("dispatch", "retry", "reconcile"):
            self.assertRegex(capabilities, rf"{name}: \{{ type: boolean, const: false \}}")

    def test_ownership_keeps_formal_identifiers_and_execution_outside_npi(self) -> None:
        for object_name in (
            "EngineeringBOMPublishPolicy:",
            "EngineeringBOMPublishPolicyVersion:",
            "EngineeringBOMPublishRequest:",
            "EngineeringBOMPublishNode:",
            "EngineeringBOMPublishMappingObservation:",
            "EngineeringBOMPublishNodeResult:",
            "EngineeringBOMPublishCommandIdempotency:",
        ):
            self.assertIn(object_name, OWNERSHIP)
        section = OWNERSHIP.split("  EngineeringBOMPublishRequest:\n", 1)[1].split(
            "\n  Tooling:\n", 1
        )[0]
        self.assertIn("FUTURE_PHASE_8_INTEGRATION_ADAPTER", section)
        self.assertIn("ERPNEXT_TO_NPI", section)
        self.assertIn("TARGET_CONFIRMATION_REQUIRED", section)
        self.assertIn("IMMUTABLE_MAPPING", section)
        self.assertNotIn("editable_in: [NPI_ONE]", section)

    def test_future_event_contracts_are_closed_and_never_carry_credentials(self) -> None:
        definitions = EVENT["$defs"]
        ready = definitions["engineering_bom_publish_request_ready_v1"]
        observed = definitions["engineering_bom_publish_result_observed_v1"]
        self.assertFalse(ready["additionalProperties"])
        self.assertFalse(observed["additionalProperties"])
        self.assertEqual(ready["properties"]["target_mode"]["const"], "sandbox")
        self.assertEqual(
            ready["properties"]["operation"]["const"],
            "publish_released_ebom_item_mbom",
        )
        serialized = json.dumps(definitions, sort_keys=True).casefold()
        for forbidden in (
            "credential",
            "password",
            "secret",
            "authorization",
            "cookie",
            "production",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("node_input_hash", serialized)
        self.assertIn("request_payload_hash", serialized)


if __name__ == "__main__":
    unittest.main()
