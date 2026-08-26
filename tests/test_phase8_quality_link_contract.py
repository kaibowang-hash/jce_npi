from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "contracts/npi-api.openapi.yaml"
OWNERSHIP_PATH = ROOT / "contracts/data-ownership.yaml"


class Phase8QualityLinkContractTest(unittest.TestCase):
    def test_components_are_closed_and_activate_no_route_or_event(self) -> None:
        contract = OPENAPI_PATH.read_text(encoding="utf-8")
        schemas = contract[contract.index("  schemas:\n") :]
        names = ("FormalQualityLinkSourceReference", "FormalQualityObservationReference", "FormalQualityLinkRevision", "FormalQualityLinkHead", "FormalQualityLinkCommandIdentity")
        for index, name in enumerate(names):
            self.assertEqual(schemas.count(f"    {name}:\n"), 1)
            start = schemas.index(f"    {name}:\n")
            end = schemas.index(f"    {names[index + 1]}:\n") if index + 1 < len(names) else schemas.index("    ControlledPrintSourceReference:\n")
            self.assertIn("additionalProperties: false", schemas[start:end])
        paths = contract.split("\ncomponents:", 1)[0]
        self.assertNotIn("formal-quality", paths)
        events = (ROOT / "contracts/integration-event.schema.json").read_text(encoding="utf-8")
        self.assertNotIn("formal_quality_link", events)

    def test_formal_observation_component_is_exact_current_raw_truth(self) -> None:
        contract = OPENAPI_PATH.read_text(encoding="utf-8")
        schema = contract[contract.index("    FormalQualityObservationReference:\n") : contract.index("    FormalQualityLinkRevision:\n")]
        for marker in ("projectionKind: { type: string, const: formal_quality_status }", "sourceSystem: { type: string, const: ERPNEXT }", "availability: { type: string, const: available }", "freshness: { type: string, const: fresh }", "disposition: { type: string, const: applied_current }"):
            self.assertIn(marker, schema)
        self.assertNotIn("pass", schema.casefold())

    def test_ownership_keeps_erp_truth_and_npi_link_history_separate(self) -> None:
        ownership = OWNERSHIP_PATH.read_text(encoding="utf-8")
        for marker in ("  FormalQualityLinkRevision:\n    owner_system: NPI_ONE_QUALITY_LINK_SERVICE", "  QualityInspection:\n    owner_system: ERPNEXT", "UNAVAILABLE_RAW_CODES_ARE_NOT_PASS", "  ERPProjectionHead:\n    owner_system: NPI_ONE_ERP_PROJECTION_SERVICE"):
            self.assertIn(marker, ownership)


if __name__ == "__main__":
    unittest.main()
