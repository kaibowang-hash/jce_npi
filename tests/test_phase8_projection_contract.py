from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.projections.domain import (
    PROJECTION_DEFINITIONS,
    AdapterMode,
    ProjectionAvailability,
    ProjectionContext,
    ProjectionKind,
    ProjectionReaderResult,
    ProjectionScopeKind,
    canonical_payload_hash,
)
from tests.test_phase8_projection_domain import scope, uid, values


EVENT_SCHEMA = json.loads(
    (ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8")
)
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
NOW = datetime(2026, 8, 16, 2, 0, tzinfo=UTC)


def event(kind: ProjectionKind) -> dict[str, object]:
    definition = PROJECTION_DEFINITIONS[kind]
    selected_scope = scope(kind)
    result = ProjectionReaderResult(
        kind=kind,
        adapter_mode=AdapterMode.SANDBOX,
        source_environment="sandbox",
        source_object_id="SOURCE-SYNTHETIC-001",
        source_version="opaque-version",
        source_modified_at=NOW,
        availability=ProjectionAvailability.AVAILABLE,
        values=values(kind),
    )
    payload = result.event_payload(
        context=ProjectionContext(
            tenant_id="tenant-synthetic",
            project_global_id=uid(1),
            scope_kind=selected_scope,
            scope_global_id=(uid(1) if selected_scope is ProjectionScopeKind.PROJECT else uid(2)),
        ),
        received_at=NOW,
    )
    return {
        "event_id": str(uid(10)),
        "event_type": definition.event_type,
        "event_version": 1,
        "occurred_at": "2026-08-16T02:00:00Z",
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "global_id": str(uid(11)),
        "object_type": definition.source_object_type,
        "source_object_id": "SOURCE-SYNTHETIC-001",
        "object_version": 1,
        "correlation_id": str(uid(12)),
        "trace_id": "trace-synthetic",
        "actor": {"type": "service", "id": "projection-sandbox"},
        "payload_hash": canonical_payload_hash(payload),
        "payload": payload,
        "sensitivity": "internal",
    }


class Phase8ProjectionContractTest(unittest.TestCase):
    def test_all_seven_operation_specific_events_are_mapped_and_unknown_kind_fails_closed(self) -> None:
        event_types = set(EVENT_SCHEMA["properties"]["event_type"]["enum"])
        conditions = {
            condition.get("if", {}).get("properties", {}).get("event_type", {}).get("const"):
            condition.get("then", {}).get("properties", {})
            for condition in EVENT_SCHEMA["allOf"]
        }
        for kind in ProjectionKind:
            with self.subTest(kind=kind):
                candidate = event(kind)
                definition = PROJECTION_DEFINITIONS[kind]
                self.assertIn(definition.event_type, event_types)
                self.assertEqual(
                    conditions[definition.event_type]["object_type"]["const"],
                    definition.source_object_type,
                )
                self.assertEqual(
                    candidate["payload_hash"],
                    canonical_payload_hash(candidate["payload"]),
                )
        self.assertNotIn("erpnext.generic_doc.observed", event_types)

    def test_event_payload_is_closed_and_kind_scope_values_cannot_be_substituted(self) -> None:
        definitions = EVENT_SCHEMA["$defs"]
        base = definitions["erp_projection_observation_v1"]
        self.assertFalse(base["additionalProperties"])
        self.assertEqual(set(base["required"]), set(base["properties"]))
        for name in (
            "erp_master_values_v1",
            "erp_item_values_v1",
            "erp_tooling_cost_values_v1",
            "erp_project_cost_values_v1",
            "erp_quality_values_v1",
            "erp_tool_asset_values_v1",
            "erp_asset_movement_v1",
            "erp_asset_repair_v1",
            "erp_asset_spare_v1",
        ):
            with self.subTest(name=name):
                self.assertFalse(definitions[name]["additionalProperties"])
                self.assertEqual(
                    set(definitions[name]["required"]),
                    set(definitions[name]["properties"]),
                )
        common_projection_condition = next(
            condition
            for condition in EVENT_SCHEMA["allOf"]
            if condition.get("if", {}).get("properties", {}).get("event_type", {}).get("enum")
        )
        common_then = common_projection_condition["then"]
        self.assertEqual(common_then["properties"]["source_system"]["const"], "ERPNEXT")
        self.assertEqual(common_then["properties"]["target_system"]["const"], "NPI_ONE")
        self.assertEqual(common_then["properties"]["actor"]["properties"]["type"]["const"], "service")
        self.assertEqual(
            common_then["properties"]["correlation_id"],
            {"type": "string", "format": "uuid"},
        )
        self.assertEqual(
            common_then["properties"]["payload_hash"],
            {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        )
        self.assertEqual(
            common_then["properties"]["sensitivity"]["enum"],
            ["internal", "confidential"],
        )
        self.assertIn("source_object_id", common_then["required"])
        self.assertIn("correlation_id", common_then["required"])

    def test_openapi_activates_only_the_closed_project_read_route(self) -> None:
        for name in (
            "ERPProjectionKind",
            "ERPProjectionMasterValues",
            "ERPProjectionItemValues",
            "ERPProjectionToolingCostValues",
            "ERPProjectionProjectCostValues",
            "ERPProjectionQualityValues",
            "ERPProjectionToolAssetValues",
            "ERPProjectionCurrentTruth",
            "ERPProjectionItem",
            "ERPProjectionPermissions",
            "ERPProjectionCollection",
        ):
            self.assertIn(f"    {name}:\n", OPENAPI)
        schemas = OPENAPI[OPENAPI.index("  schemas:\n") :]
        self.assertIn("additionalProperties: false", schemas)
        self.assertIn("editable: { type: boolean, const: false }", schemas)
        self.assertIn("refresh: { type: boolean, const: false }", schemas)
        current_truth = schemas[schemas.index("    ERPProjectionCurrentTruth:\n") :]
        current_truth = current_truth[: current_truth.index("\n    ERPProjectionItem:")]
        for field in ("headGlobalId", "headOptimisticVersion", "headHash"):
            self.assertIn(field, current_truth)
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertEqual(paths.count("/projects/{projectId}/erp-projections:"), 1)
        route = paths[paths.index("  /projects/{projectId}/erp-projections:") :]
        route = route[: route.index("\n  /projects/{projectId}/work-context:")]
        self.assertIn("operationId: getProjectErpProjections", route)
        self.assertIn("This route never refreshes or mutates ERP or NPI", route)
        self.assertNotIn("post:", route)
        self.assertNotIn("put:", route)
        self.assertNotIn("delete:", route)
        self.assertNotIn("sourceObjectId", route)

    def test_ownership_keeps_business_truth_in_erp_and_projection_records_read_only(self) -> None:
        for marker in (
            "  Customer:\n    owner_system: ERPNEXT",
            "  Supplier:\n    owner_system: ERPNEXT",
            "  Item:\n    owner_system: ERPNEXT_AFTER_RELEASE",
            "  ToolingProcurementCostProjection:\n    owner_system: ERPNEXT",
            "  ToolAssetProjection:\n    owner_system: ERPNEXT",
            "  QualityInspection:\n    owner_system: ERPNEXT",
            "  ERPProjectionObservation:\n    owner_system: NPI_ONE_ERP_PROJECTION_SERVICE",
            "  ERPProjectionHead:\n    owner_system: NPI_ONE_ERP_PROJECTION_SERVICE",
            "credentials_raw_response_and_target_error_body: {owner: NEVER_PERSIST",
            "erp_business_fields: {owner: ERPNEXT, editable_in: [ERPNEXT]",
        ):
            self.assertIn(marker, OWNERSHIP)
        projection_sections = OWNERSHIP[
            OWNERSHIP.index("  ERPProjectionObservation:") :
            OWNERSHIP.index("  GateTemplate:")
        ]
        self.assertNotIn("editable_in: [NPI_ONE]", projection_sections)


if __name__ == "__main__":
    unittest.main()
