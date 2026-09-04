from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
import unittest
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.item_publish.domain import (  # noqa: E402
    ItemExecutionProfileReference,
    ItemMappingExpectation,
    ItemOccurrence,
    ItemTargetMode,
    ReleasedItemSourceEvidence,
    create_item_publish_request,
    group_item_source,
)


EVENT = json.loads(
    (ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8")
)
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")


def _uuid(value: int) -> UUID:
    return UUID(int=value)


def _non_mock_item_event_payload() -> dict[str, object]:
    occurrence = ItemOccurrence(
        publish_node_global_id=_uuid(1),
        line_global_id=_uuid(101),
        engineering_item_id="ENG-ITEM-001",
        description="Synthetic engineering item",
        engineering_uom="Nos",
        attributes=(("material", "PA66"),),
        line_hash="1" * 64,
        node_input_hash="2" * 64,
    )
    source = group_item_source(
        tenant_id="tenant-contract",
        project_global_id=_uuid(2),
        selected_publish_node_global_id=occurrence.publish_node_global_id,
        occurrences=(occurrence,),
    )
    released_evidence = ReleasedItemSourceEvidence(
        publish_request_global_id=_uuid(3),
        publish_request_payload_hash="3" * 64,
        publish_policy_global_id=_uuid(4),
        publish_policy_version=2,
        publish_policy_snapshot_hash="4" * 64,
        ebom_global_id=_uuid(5),
        ebom_version=3,
        revision_global_id=_uuid(6),
        revision_number=3,
        revision_snapshot_hash="5" * 64,
        lifecycle_version=4,
        release_event_global_id=_uuid(7),
        release_event_hash="6" * 64,
        approval_evidence_ids=(_uuid(7),),
        released_at=datetime(2026, 8, 16, 13, 0, tzinfo=UTC),
    )
    profile = ItemExecutionProfileReference(
        profile_id="item-synthetic-contract-v1",
        profile_version=1,
        target_mode=ItemTargetMode.SYNTHETIC,
        environment_code="disposable-test",
        snapshot_hash="7" * 64,
    )
    request = create_item_publish_request(
        source=source,
        released_evidence=released_evidence,
        profile=profile,
        mapping_expectation=ItemMappingExpectation(0),
        actor_user_id="requester@example.invalid",
        service_actor_user_id="worker@example.invalid",
        request_id=_uuid(8),
        trace_id="trace-item-contract-001",
        idempotency_key_hash="8" * 64,
        global_id=_uuid(9),
        created_at=datetime(2026, 8, 16, 13, 0, tzinfo=UTC),
    )
    return request.event_payload()


def _schema_errors(payload: object, schema: dict[str, object]) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    properties = schema["properties"]
    assert isinstance(properties, dict)
    required = set(schema["required"])
    errors: list[str] = []
    if set(payload) != set(properties):
        errors.append("payload keys are not exactly the schema properties")
    if set(payload) != required:
        errors.append("payload keys are not exactly the schema required fields")

    def matches_type(value: object, expected: str) -> bool:
        return {
            "string": type(value) is str,
            "integer": type(value) is int,
            "null": value is None,
            "boolean": type(value) is bool,
        }.get(expected, True)

    for name, specification in properties.items():
        if name not in payload:
            errors.append(f"missing {name}")
            continue
        assert isinstance(specification, dict)
        value = payload[name]
        expected_type = specification.get("type")
        if isinstance(expected_type, str) and not matches_type(value, expected_type):
            errors.append(f"wrong type for {name}")
        elif isinstance(expected_type, list) and not any(
            matches_type(value, candidate) for candidate in expected_type
        ):
            errors.append(f"wrong type for {name}")
        if "const" in specification and value != specification["const"]:
            errors.append(f"wrong const for {name}")
        if "enum" in specification and value not in specification["enum"]:
            errors.append(f"wrong enum for {name}")
        pattern = specification.get("pattern")
        if isinstance(pattern, str) and isinstance(value, str) and not re.fullmatch(
            pattern, value
        ):
            errors.append(f"wrong pattern for {name}")
    return errors


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
            "service_actor_user_id",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_real_non_mock_event_payload_is_closed_and_rejects_shape_drift(self) -> None:
        schema = EVENT["$defs"]["item_publish_request_ready_v1"]
        payload = _non_mock_item_event_payload()
        self.assertEqual(_schema_errors(payload, schema), [])
        self.assertRegex(payload["semantic_source_effect_hash"], r"^[a-f0-9]{64}$")

        missing = dict(payload)
        del missing["semantic_source_effect_hash"]
        self.assertTrue(_schema_errors(missing, schema))

        extra = dict(payload)
        extra["service_actor_user_id"] = "worker@example.invalid"
        self.assertTrue(_schema_errors(extra, schema))

        wrong_type = dict(payload)
        wrong_type["profile_version"] = "1"
        self.assertTrue(_schema_errors(wrong_type, schema))

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

    def test_openapi_activates_only_fixed_project_first_item_routes(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        base = "/projects/{projectId}/item-publish-requests"
        self.assertEqual(paths.count(f"  {base}:\n"), 1)
        self.assertEqual(
            paths.count(f"  {base}/{{itemPublishRequestId}}:\n"),
            1,
        )
        self.assertIn("operationId: listItemPublishRequests", paths)
        self.assertIn("operationId: createItemPublishRequest", paths)
        self.assertIn("operationId: getItemPublishRequest", paths)
        self.assertNotIn("retryItemPublishRequest", paths)
        self.assertNotIn("reconcileItemPublishRequest", paths)
        schemas = OPENAPI[OPENAPI.index("  schemas:\n") :]
        for name in (
            "CreateItemPublishRequest",
            "ItemPublishSourceSnapshot",
            "ItemPublishReleasedEvidence",
            "ItemPublishProfileReference",
            "ItemPublishMappingExpectation",
            "ItemPublishRequest",
            "ItemPublishRequestList",
            "ItemPublishRequestDetail",
            "ItemPublishAttempt",
            "ItemPublishResult",
            "ItemMappingObservation",
            "ItemMappingHead",
            "ItemPublishPermissions",
        ):
            self.assertIn(f"    {name}:\n", schemas)
        item = schemas[
            schemas.index("    ItemPublishSha256:\n") : schemas.index(
                "    MbomPublishSha256:\n"
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
        create = item[
            item.index("    createitempublishrequest:\n") : item.index(
                "    itempublishsourcefilters:\n"
            )
        ]
        for required in (
            "publishrequestglobalid",
            "selectedpublishnodeglobalid",
            "expectedmappingversion",
            "acknowledgement",
        ):
            self.assertIn(required, create)
        for forbidden in (
            "tenantid",
            "actoruserid",
            "targetmode",
            "operation:",
            "formalitemcode",
            "targetversion",
            "payloadhash",
        ):
            self.assertNotIn(forbidden, create)
        item_list = item[
            item.index("    itempublishrequestlist:\n") : item.index(
                "    itempublishrequestdetail:\n"
            )
        ]
        self.assertIn("mappingexpectation", item_list)
        self.assertIn("mapping expectation", item_list)

    def test_openapi_closes_legacy_and_current_item_request_state_matrix(self) -> None:
        item = OPENAPI[
            OPENAPI.index("    ItemPublishRequest:\n") : OPENAPI.index(
                "    ItemPublishAttempt:\n"
            )
        ]
        self.assertIn("      allOf:\n", item)
        self.assertIn("legacyReadOnly: { const: true }", item)
        self.assertIn("current: { const: false }", item)
        self.assertIn("state: { const: queued }", item)
        self.assertIn("dispatchAllowed: { const: false }", item)
        self.assertIn('outboxEventId: { type: \"null\" }', item)
        self.assertIn('resultGlobalId: { type: \"null\" }', item)
        self.assertIn("optimisticVersion: { const: 1 }", item)
        self.assertIn("not: { const: mock }", item)
        self.assertIn("legacyReadOnly: { const: false }", item)
        self.assertIn("current: { const: true }", item)

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
