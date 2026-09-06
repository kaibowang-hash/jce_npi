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


class Phase7TrialReviewContractTest(unittest.TestCase):
    def test_checkpoint_two_exposes_only_closed_project_first_review_routes(self) -> None:
        for name in (
            "TrialReviewExactReference",
            "TrialConclusionAuthorityBinding",
            "TrialConclusionPolicyVersion",
            "TrialReviewCavityResultTip",
            "TrialReviewDefectTip",
            "TrialRoundComparisonSource",
            "TrialInputComparisonCell",
            "TrialInputComparisonRow",
            "TrialMetricComparisonCell",
            "TrialMetricComparisonRow",
            "TrialDefectTrend",
            "TrialRoundComparisonSnapshot",
            "TrialReviewReferenceRevision",
            "TrialConclusionBlocker",
            "TrialOnePageSummaryInput",
            "TrialConclusionExternalEffects",
            "TrialConclusionRevision",
            "BeginTrialAnalysis",
            "TrialComparisonRoundInput",
            "CreateTrialRoundComparison",
            "CreateTrialReviewReferenceRevision",
            "SubmitTrialConclusion",
            "DecideTrialConclusion",
            "ReopenTrialConclusion",
            "TrialReviewPermissions",
            "TrialReviewExternalEffects",
            "TrialReviewWorkspace",
        ):
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", schema(name))
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        for required in (
            "/projects/{projectId}/trial-rounds/{trialRoundId}/review:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}:begin-analysis:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/comparisons:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/review-references:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/conclusions:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/conclusions/{conclusionId}:decide:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}:reopen:",
            "operationId: submitTrialConclusion",
            "operationId: decideTrialConclusion",
        ):
            self.assertIn(required, paths)
        for forbidden in (
            "/trial-rounds/{trialRoundId}/review-references/{referenceId}",
            "/trial-rounds/{trialRoundId}/conclusions/{conclusionId}:delete",
            "latestPolicy",
            "rawDoctype",
        ):
            self.assertNotIn(forbidden, paths)

    def test_comparison_contract_binds_exact_round_sources_and_explicit_missing_truth(self) -> None:
        source = schema("TrialRoundComparisonSource")
        for marker in (
            "trialRoundOptimisticVersion:",
            "trialRoundSnapshotHash:",
            "trialPlanRevision:",
            "inputLockRevision:",
            "actualRevision:",
            "sampleRevisions:",
            "cavityResults:",
            "defects:",
        ):
            self.assertIn(marker, source)
        cell = schema("TrialMetricComparisonCell")
        self.assertIn("enum: [measured, not_measured, unavailable]", cell)
        self.assertIn("sourceRevision:", cell)
        comparison = schema("TrialRoundComparisonSnapshot")
        self.assertIn("minItems: 2", comparison)
        self.assertIn("formalErpQuality: { type: string, readOnly: true, const: unavailable }", comparison)
        self.assertIn("never imputed as zero", comparison)

    def test_policy_and_conclusion_are_versioned_authority_bound_and_non_mutating(self) -> None:
        policy = schema("TrialConclusionPolicyVersion")
        for marker in (
            "policyVersion:",
            "predecessorSnapshotHash:",
            "requiredReferenceKinds:",
            "outOfSpecBlockingCodes:",
            "authorityBindings:",
        ):
            self.assertIn(marker, policy)
        self.assertIn(
            "enum: [submit, decide, reopen]",
            schema("TrialConclusionAuthorityBinding"),
        )
        conclusion = schema("TrialConclusionRevision")
        for marker in (
            "trialRoundOptimisticVersion:",
            "trialRoundSnapshotHash:",
            "conclusionVersion:",
            "policyRevision:",
            "comparisonSnapshot:",
            "reviewReferences:",
            "blockers:",
            "summaryInput:",
        ):
            self.assertIn(marker, conclusion)
        effects = schema("TrialConclusionExternalEffects")
        self.assertEqual(effects.count("const: unavailable"), 5)
        self.assertIn("nextWork: { type: string, const: proposal_only }", effects)

    def test_reference_evidence_never_claims_approval(self) -> None:
        reference = schema("TrialReviewReferenceRevision")
        for marker in (
            "comparisonSnapshot:",
            "partRevision:",
            "toolingMasterGlobalId:",
            "toolingRevision:",
            "toolingSet:",
            "fileRevision:",
            "approvalAuthority: { type: string, readOnly: true, const: unavailable }",
        ):
            self.assertIn(marker, reference)
        self.assertIn("Presence never grants customer", reference)

    def test_ownership_keeps_external_authorities_separate(self) -> None:
        for object_name in (
            "TrialConclusionPolicyVersion",
            "TrialRoundComparisonSnapshot",
            "TrialReviewReferenceRevision",
            "TrialConclusionRevision",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        for boundary in (
            "conflict: EXPLICIT_UNAVAILABLE_NO_ZERO_IMPUTATION",
            "conflict: UNAVAILABLE_IN_P7_04",
            "conflict: EVIDENCE_IS_NOT_APPROVAL_UNAVAILABLE_IN_P7_04",
            "conflict: EXPLICIT_IMMUTABLE_SUCCESSOR_REQUIRED",
            "conflict: PROPOSAL_ONLY_NO_EXTERNAL_MUTATION",
            "conflict: NOT_INSTALLED_BY_METADATA",
        ):
            self.assertIn(boundary, OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
