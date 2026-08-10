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


class Phase7TrialQualityContractTest(unittest.TestCase):
    def test_checkpoint_one_adds_closed_read_models_without_live_paths(self) -> None:
        for name in (
            "TrialQualityEvidenceReference",
            "TrialCavityMeasurement",
            "TrialCavityResultRevision",
            "TrialDefectAction",
            "TrialDefectExternalEffects",
            "TrialDefectRevision",
            "TrialDefectVerificationRevision",
        ):
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", schema(name))
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertNotIn(
            "/projects/{projectId}/trial-rounds/{trialRoundId}/quality:",
            paths,
        )
        self.assertNotIn("createTrialCavityResult", paths)
        self.assertNotIn("createTrialDefectVerification", paths)

    def test_cavity_result_uses_exact_sample_cavity_and_explicit_missing_state(self) -> None:
        measurement = schema("TrialCavityMeasurement")
        result = schema("TrialCavityResultRevision")
        for marker in (
            "state: { type: string, enum: [measured, not_measured] }",
            "comparisonState: { type: string, readOnly: true, enum: [not_measured, within_spec, out_of_spec] }",
            'source: { type: string, const: manual }',
        ):
            self.assertIn(marker, measurement)
        for field in (
            "trialRoundGlobalId:",
            "inputLockRevisionGlobalId:",
            "sampleBatchRevisionGlobalId:",
            "toolingRevisionGlobalId:",
            "toolingSetGlobalId:",
            "cavityGlobalId:",
            "predecessorSnapshotHash:",
        ):
            self.assertIn(field, result)
        for forbidden in ("qualityResult:", "approvedResult:", "ncrGlobalId:"):
            self.assertNotIn(forbidden, result)

    def test_one_defect_identity_has_cross_store_tip_and_exact_target_round(self) -> None:
        defect = schema("TrialDefectRevision")
        action = schema("TrialDefectAction")
        self.assertIn(
            "enum: [tooling_defect_revision, trial_defect_revision]",
            defect,
        )
        self.assertIn("defectGlobalId:", defect)
        self.assertIn("predecessorGlobalId:", defect)
        self.assertIn("predecessorSnapshotHash:", defect)
        self.assertNotIn("targetRoundLabel:", action)
        for field in (
            "targetRoundGlobalId:",
            "targetRoundOptimisticVersion:",
            "targetRoundSnapshotHash:",
        ):
            self.assertIn(field, action)

    def test_independent_verification_is_exact_and_has_no_automatic_effect(self) -> None:
        verification = schema("TrialDefectVerificationRevision")
        for field in (
            "defectRevisionGlobalId:",
            "actionGlobalId:",
            "targetRoundGlobalId:",
            "verificationRoundGlobalId:",
            "cavityResultRevisionGlobalId:",
            "verifierMember:",
            "result: { type: string, enum: [pass, fail] }",
        ):
            self.assertIn(field, verification)
        self.assertIn("never closes a defect by itself", verification)
        for forbidden in ("closeDefect:", "gateResult:", "ncrResult:"):
            self.assertNotIn(forbidden, verification)
        external = schema("TrialDefectExternalEffects")
        self.assertEqual(external.count("const: unavailable"), 4)

    def test_ownership_preserves_npi_truth_and_external_holds(self) -> None:
        for object_name in (
            "TrialCavityResultRevision",
            "TrialDefectRevision",
            "TrialDefectVerificationRevision",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        for boundary in (
            "conflict: SINGLE_LOGICAL_DEFECT_NO_FORK",
            "conflict: EXPLICIT_NO_ZERO_OR_PASS_IMPUTATION",
            "conflict: EXPLICIT_SUCCESSOR_REQUIRED",
            "conflict: UNAVAILABLE_IN_P7_03",
        ):
            self.assertIn(boundary, OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
