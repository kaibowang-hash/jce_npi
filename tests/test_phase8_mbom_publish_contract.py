from __future__ import annotations

import json
import re
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.mbom_publish.domain import (  # noqa: E402
    ItemMappingReadiness,
    ItemReadinessDisposition,
    MbomExecutionProfileReference,
    MbomMappingExpectation,
    MbomResultAuthority,
    MbomSourceLine,
    MbomSourceSnapshot,
    MbomTargetMode,
    MbomTargetSubmissionState,
    canonical_hash,
    create_mbom_publish_request,
)


EVENT = json.loads(
    (ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8")
)
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")


def uid(value: int) -> UUID:
    return UUID(int=value)


def request_event_payload() -> dict[str, object]:
    source = MbomSourceSnapshot(
        tenant_id="tenant-contract",
        project_global_id=uid(1),
        ebom_global_id=uid(2),
        phase5_publish_request_global_id=uid(3),
        phase5_publish_request_payload_hash="3" * 64,
        publish_policy_global_id=uid(4),
        publish_policy_version=1,
        publish_policy_snapshot_hash="4" * 64,
        revision_global_id=uid(5),
        revision_number=1,
        revision_snapshot_hash="5" * 64,
        lifecycle_version=1,
        release_event_global_id=uid(6),
        release_event_hash="6" * 64,
        approval_evidence_ids=(uid(6),),
        released_at=datetime(2026, 8, 21, 13, 0, tzinfo=UTC),
        lines=(
            MbomSourceLine(uid(10), "ROOT", None, "ENG-ROOT", "1", "Nos", (), (), (), "a" * 64),
            MbomSourceLine(uid(11), "LEAF", "ROOT", "ENG-LEAF", "2", "Nos", (), (), (), "b" * 64),
        ),
    )
    readiness = tuple(
        ItemMappingReadiness(
            engineering_item_id=item,
            disposition=ItemReadinessDisposition.SYNTHETIC_REFERENCE,
            item_stream_key_hash=canonical_hash(
                {
                    "schemaVersion": 1,
                    "tenantId": source.tenant_id,
                    "projectGlobalId": str(source.project_global_id),
                    "engineeringItemId": item,
                }
            ),
            mapping_version=0,
            authority=MbomResultAuthority.SYNTHETIC,
            synthetic_item_reference=f"synthetic-item-{'e' if index == 0 else 'f'}" + "0" * 23,
        )
        for index, item in enumerate(source.engineering_item_ids)
    )
    expectation = MbomMappingExpectation(
        assembly_source_key=source.assembly_source_key("ROOT"),
        stable_line_key="ROOT",
        mapping_version=0,
        submission_state=MbomTargetSubmissionState.UNMAPPED_CREATE,
    )
    profile = MbomExecutionProfileReference(
        profile_id="mbom-synthetic-v1",
        profile_version=1,
        target_mode=MbomTargetMode.SYNTHETIC,
        environment_code="disposable-test",
        projection_policy_id="mbom-projection-v1",
        projection_policy_version=1,
        projection_policy_hash="7" * 64,
        snapshot_hash="8" * 64,
    )
    return create_mbom_publish_request(
        source=source,
        item_readiness=readiness,
        mbom_expectations=(expectation,),
        profile=profile,
        actor_user_id="engineer@example.invalid",
        service_actor_user_id="worker@example.invalid",
        request_id=uid(20),
        trace_id="trace-mbom-contract-001",
        idempotency_key_hash="9" * 64,
        global_id=uid(21),
        created_at=datetime(2026, 8, 21, 13, 0, tzinfo=UTC),
    ).event_payload()


def schema_errors(payload: object, schema: dict[str, object]) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    properties = schema["properties"]
    required = set(schema["required"])
    assert isinstance(properties, dict)
    errors: list[str] = []
    if set(payload) != set(properties) or set(payload) != required:
        errors.append("payload keys are not exact")
    for name, specification in properties.items():
        if name not in payload:
            errors.append(f"missing {name}")
            continue
        assert isinstance(specification, dict)
        value = payload[name]
        if "const" in specification and value != specification["const"]:
            errors.append(f"wrong const {name}")
        if "enum" in specification and value not in specification["enum"]:
            errors.append(f"wrong enum {name}")
        pattern = specification.get("pattern")
        if pattern and isinstance(value, str) and re.fullmatch(str(pattern), value) is None:
            errors.append(f"wrong pattern {name}")
        expected_type = specification.get("type")
        if expected_type == "integer" and type(value) is not int:
            errors.append(f"wrong type {name}")
        if expected_type == "string" and type(value) is not str:
            errors.append(f"wrong type {name}")
    return errors


class Phase8MbomPublishContractTest(unittest.TestCase):
    def test_two_mbom_only_events_are_additive_closed_and_operation_specific(self) -> None:
        event_types = EVENT["properties"]["event_type"]["enum"]
        self.assertEqual(event_types.count("npi.mbom_publish_request.ready"), 1)
        self.assertEqual(event_types.count("erpnext.mbom_publish_result.observed"), 1)
        request = EVENT["$defs"]["mbom_publish_request_ready_v1"]
        result = EVENT["$defs"]["mbom_publish_result_observed_v1"]
        node = EVENT["$defs"]["mbom_publish_node_result_observed_v1"]
        for schema in (request, result, node):
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertEqual(request["properties"]["schema_version"]["const"], 1)
        self.assertEqual(request["properties"]["operation"]["const"], "publish_released_mbom")
        self.assertEqual(request["properties"]["target_mode"]["enum"], ["synthetic", "sandbox"])
        self.assertNotIn("mock", request["properties"]["target_mode"]["enum"])
        self.assertNotIn("endpoint", str(request).casefold())
        self.assertNotIn("credential", str(request).casefold())
        self.assertIn("partially_succeeded", result["properties"]["state"]["enum"])
        self.assertIn("uncertain_after_timeout", result["properties"]["state"]["enum"])

    def test_domain_request_event_matches_the_exact_event_schema(self) -> None:
        payload = request_event_payload()
        schema = EVENT["$defs"]["mbom_publish_request_ready_v1"]
        self.assertEqual(schema_errors(payload, schema), [])
        for mutation in (
            {**payload, "operation": "publish_released_item"},
            {**payload, "target_mode": "mock"},
            {key: value for key, value in payload.items() if key != "topology_hash"},
            {**payload, "endpoint": "https://forbidden.invalid"},
        ):
            self.assertTrue(schema_errors(mutation, schema))

    def test_authoritative_node_success_requires_authenticated_editable_draft_truth(self) -> None:
        schema = EVENT["$defs"]["mbom_publish_node_result_observed_v1"]
        branch = schema["allOf"][0]
        succeeded = branch["then"]["properties"]
        self.assertEqual(succeeded["authority"]["const"], "authoritative_sandbox")
        self.assertTrue(succeeded["response_authenticated"]["const"])
        self.assertEqual(succeeded["target_submission_state"]["const"], "editable_draft")
        self.assertEqual(succeeded["fault_kind"]["const"], "none")
        self.assertEqual(branch["else"]["properties"]["formal_bom_id"]["type"], "null")
        synthetic = schema["allOf"][1]["then"]["properties"]
        self.assertEqual(synthetic["authority"]["const"], "synthetic")
        self.assertFalse(synthetic["response_authenticated"]["const"])

    def test_openapi_adds_only_closed_components_and_no_mbom_route(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertNotIn("/mbom-publish-requests", paths)
        schemas = OPENAPI[OPENAPI.index("  schemas:\n") :]
        for name in (
            "MbomPublishSourceLine",
            "MbomPublishSourceSnapshot",
            "MbomItemMappingReadiness",
            "MbomMappingExpectation",
            "MbomExecutionProfileReference",
            "MbomPublishRequest",
            "MbomPublishNodeResult",
        ):
            self.assertEqual(schemas.count(f"    {name}:\n"), 1)
        mbom = schemas[
            schemas.index("    MbomPublishSha256:\n") : schemas.index("    ProblemDetails:\n")
        ].casefold()
        for forbidden in (
            "frappe.client.insert",
            "publish_released_ebom_item_mbom",
            "endpoint",
            "credential",
            "authorizationheader",
            "submit_bom",
        ):
            self.assertNotIn(forbidden, mbom)
        self.assertIn("local commit never means target acceptance", mbom)
        self.assertIn("authenticated authoritative sandbox editable-draft", mbom)

    def test_ownership_keeps_npi_execution_and_erp_bom_truth_separate(self) -> None:
        for marker in (
            "  MBOMPublishRequest:\n    owner_system: NPI_ONE",
            "  MBOMPublishNode:\n    owner_system: NPI_ONE",
            "  MBOMPublishCommandIdempotency:\n    owner_system: NPI_ONE_MBOM_PUBLISH_COMMAND",
            "  MBOMPublishOutboxMessage:\n    owner_system: NPI_ONE_MBOM_EXECUTION_SERVICE",
            "  MBOMPublishAttempt:\n    owner_system: NPI_ONE_MBOM_EXECUTION_SERVICE",
            "  MBOMPublishResult:\n    owner_system: SPLIT_BY_FIELD",
            "  MBOMPublishNodeResult:\n    owner_system: SPLIT_BY_FIELD",
            "  MBOMMappingObservation:\n    owner_system: SPLIT_BY_FIELD",
            "  MBOMMappingHead:\n    owner_system: NPI_ONE_INTEGRATION_PROJECTION",
            "formal_bom_id_target_version_submission_routing_and_manufacturing_lifecycle: {owner: ERPNEXT",
            "submitted_bom_successor_or_overwrite_authority: {owner: NONE",
            "retry_or_reconciliation_authority: {owner: FUTURE_P8_07_RETRY_POLICY",
            "synthetic_or_mock_formal_mapping: {owner: NONE",
        ):
            self.assertIn(marker, OWNERSHIP)

    def test_item_v1_event_contract_is_unchanged_and_not_reinterpreted(self) -> None:
        item = EVENT["$defs"]["item_publish_request_ready_v1"]
        self.assertEqual(item["properties"]["schema_version"]["const"], 1)
        self.assertEqual(item["properties"]["operation"]["const"], "publish_released_item")
        self.assertNotIn("topology_hash", item["properties"])
        self.assertNotIn("mbom_mapping_set_hash", item["properties"])


if __name__ == "__main__":
    unittest.main()
