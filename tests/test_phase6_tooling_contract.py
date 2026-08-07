from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
BFF = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")


def _schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase6ToolingContractTest(unittest.TestCase):
    def test_foundation_schemas_are_closed_and_no_route_is_active(self) -> None:
        schema_names = (
            "ToolingExternalReference",
            "EngineeringPartRevisionReference",
            "EngineeringPartSummary",
            "ToolingRequirementSummary",
            "ToolingMasterSummary",
            "ToolingApplicabilitySummary",
            "ToolingPermissions",
            "ToolingDownstreamCapability",
            "ToolingProjectCockpit",
            "CreateEngineeringPart",
            "CreateEngineeringPartRevision",
            "CreateToolingRequirement",
            "CreateToolingMaster",
            "CreateToolingApplicability",
        )
        for name in schema_names:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", _schema(name))
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertNotIn("/projects/{projectId}/tooling", paths)
        self.assertNotIn("tooling_api", BFF)

    def test_browser_requests_cannot_supply_server_owned_truth(self) -> None:
        requests = "\n".join(
            _schema(name)
            for name in (
                "CreateEngineeringPart",
                "CreateEngineeringPartRevision",
                "CreateToolingRequirement",
                "CreateToolingMaster",
                "CreateToolingApplicability",
            )
        )
        for forbidden in (
            "tenantId:", "actorUserId:", "snapshotHash:",
            "relationshipKeyHash:", "sourceSystem:", "assetId:",
            "lifecycleState:", "setCount:", "doctype:",
        ):
            self.assertNotIn(forbidden, requests)

    def test_shared_master_applicability_is_versioned_and_exact(self) -> None:
        applicability = _schema("ToolingApplicabilitySummary")
        cockpit = _schema("ToolingProjectCockpit")
        for marker in (
            "relationshipGlobalId:", "relationshipKeyHash:",
            "toolingMasterGlobalId:", "part:", "version:",
            "predecessorGlobalId:", "effectiveFrom:", "effectiveTo:",
            "snapshotHash:",
        ):
            self.assertIn(marker, applicability)
        self.assertNotIn("setCount:", applicability)
        self.assertNotIn("lifecycleState:", applicability)
        self.assertIn("masters:", cockpit)
        self.assertNotIn("\n        master:", cockpit)

    def test_later_capabilities_are_explicitly_unavailable(self) -> None:
        capability = _schema("ToolingDownstreamCapability")
        permissions = _schema("ToolingPermissions")
        self.assertIn("const: unavailable", capability)
        self.assertIn("lifecycle_policy_unavailable", capability)
        self.assertIn("transitionLifecycle: { type: boolean, const: false }", permissions)

    def test_exact_ownership_rows_preserve_npi_erp_boundary(self) -> None:
        for object_name in (
            "EngineeringPart", "EngineeringPartRevision", "ToolingRequirement",
            "ToolingMaster", "ToolingApplicability", "ToolingCommandIdempotency",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        self.assertIn("formal_item_mapping: {owner: ERPNEXT", OWNERSHIP)
        self.assertIn("formal_asset_id_state_location_shot_count_and_maintenance: {owner: ERPNEXT", OWNERSHIP)
        self.assertIn("lifecycle_state_and_authority: {owner: FUTURE_APPROVED_TOOLING_POLICY", OWNERSHIP)
        self.assertIn("raw_idempotency_key:", OWNERSHIP)
        self.assertIn("conflict: NEVER_PERSIST", OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
