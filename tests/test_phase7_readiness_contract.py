from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")


def schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase7ReadinessContractTest(unittest.TestCase):
    def test_checkpoint_one_adds_closed_schemas_without_routes(self) -> None:
        for name in (
            "ReadinessApplicabilitySelector",
            "ReadinessCategoryDefinition",
            "ReadinessEvidenceRequirement",
            "ReadinessItemDefinition",
            "ReadinessTemplateVersion",
            "ReadinessExactReference",
            "ReadinessProjectSnapshot",
            "ReadinessMemberReference",
            "ReadinessGateReference",
            "ReadinessSourceReference",
            "ReadinessItemSnapshot",
            "ReadinessScore",
            "ReadinessBlocker",
            "ReadinessEvaluation",
            "ReadinessInstanceRevision",
        ):
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", schema(name))
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertNotIn("/npi-readiness", paths)
        self.assertNotIn("/projects/{projectId}/npi-readiness", paths)

    def test_template_contract_is_explicit_configuration_without_defaults(self) -> None:
        template = schema("ReadinessTemplateVersion")
        for marker in (
            "projectTypes:",
            "customerReferenceKeys:",
            "industryKeys:",
            "categories:",
            "items:",
            "Metadata installs no production default row.",
        ):
            self.assertIn(marker, template if marker in template else schema("ReadinessApplicabilitySelector"))
        item = schema("ReadinessItemDefinition")
        self.assertIn("blockingLevel:", item)
        self.assertIn("gateKey:", item)
        self.assertIn("completionRule:", item)
        self.assertIn("evidenceRequirements:", item)

    def test_external_sources_are_unavailable_without_caller_authority(self) -> None:
        source = schema("ReadinessSourceReference")
        for marker in (
            "erp_material_specification",
            "erp_quality_result",
            "erp_run_at_rate",
            "erp_hr_qualification",
            "erp_supplier_execution",
            "identity-free unavailable external provider",
        ):
            self.assertIn(marker, source)
        self.assertIn("enum: [satisfied, failed, unavailable]", source)

    def test_score_and_blocker_contract_cannot_mutate_gate(self) -> None:
        evaluation = schema("ReadinessEvaluation")
        self.assertIn("const: readiness-score.v1", evaluation)
        self.assertIn("blockers:", evaluation)
        blocker = schema("ReadinessBlocker")
        self.assertIn("incomplete_p0", blocker)
        self.assertIn("failed_mandatory_quality", blocker)
        self.assertIn("dominant regardless of score", blocker)
        instance = schema("ReadinessInstanceRevision")
        self.assertIn("no Gate, Work Item, risk, Tooling, handover or external mutation", instance)

    def test_ownership_keeps_fact_layers_and_gate_authority_separate(self) -> None:
        for object_name in (
            "NpiReadinessTemplate",
            "NpiReadinessTemplateVersion",
            "NpiReadinessInstanceRevision",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        for boundary in (
            "conflict: NOT_INSTALLED_BY_METADATA",
            "conflict: CONFIGURATION_NOT_GLOBAL_HARDCODE",
            "conflict: UNAVAILABLE_NO_CALLER_STATUS",
            "conflict: EXACT_ITEM_SNAPSHOT_WINS",
            "conflict: GATE_POLICY_REMAINS_INDEPENDENT",
            "conflict: NO_AUTOMATIC_MUTATION_IN_P7_05",
        ):
            self.assertIn(boundary, OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
