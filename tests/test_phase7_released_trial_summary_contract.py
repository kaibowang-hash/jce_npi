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


class Phase7ReleasedTrialSummaryContractTest(unittest.TestCase):
    def test_checkpoint_two_schemas_and_exact_routes_are_closed(self) -> None:
        names = (
            "ReleasedTrialSummarySourceReference",
            "ReleasedTrialSummaryFact",
            "ReleasedTrialSummaryPresentationFacts",
            "ReleasedTrialSummaryExternalEffects",
            "ReleasedTrialSummaryPresentationProjection",
            "ReleasedTrialSummaryRedactionManifest",
            "ReleasedTrialSummaryRevision",
            "RetainReleasedTrialSummary",
            "ReviseReleasedTrialSummary",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", schema(name))
        for name in (
            "ReleasedTrialSummaryWorkspace",
            "ReleasedTrialSummaryPermissions",
            "ReleasedTrialSummaryControlledOutput",
            "ReleasedTrialSummaryAuthorityHolds",
        ):
            self.assertIn("additionalProperties: false", schema(name))
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertEqual(paths.count("released-trial-summaries:"), 1)
        self.assertEqual(paths.count("released-trial-summaries/{summaryId}:revise:"), 1)
        for marker in (
            "operationId: getReleasedTrialSummaries",
            "operationId: retainReleasedTrialSummary",
            "operationId: reviseReleasedTrialSummary",
            "x-audit-operation: released_trial_summary.retain",
            "x-audit-operation: released_trial_summary.revise",
            "technical-system-manager-only-no-formal-release-authority",
        ):
            self.assertIn(marker, paths)

    def test_revision_contract_is_append_only_exact_source_and_decided_only(self) -> None:
        revision = schema("ReleasedTrialSummaryRevision")
        for marker in (
            "summaryGlobalId:",
            "summaryVersion:",
            "predecessorGlobalId:",
            "trialRoundOptimisticVersion:",
            "trialPlanRevisionGlobalId:",
            "conclusionRevisionGlobalId:",
            "sourceManifest:",
            "presentationProjection:",
            "redactionManifest:",
            "sourceManifestHash:",
            "presentationProjectionHash:",
        ):
            self.assertIn(marker, revision)
        self.assertIn("enum: [approved, rejected]", revision)
        self.assertNotIn("submitted", revision)
        self.assertNotIn("reopened", revision)

    def test_projection_is_url_free_bounded_and_carries_explicit_unavailable_effects(self) -> None:
        projection = schema("ReleasedTrialSummaryPresentationProjection")
        self.assertIn("maxItems: 25000", projection)
        self.assertIn("overflow fails and is never truncated", projection)
        effects = schema("ReleasedTrialSummaryExternalEffects")
        self.assertEqual(effects.count("const: unavailable"), 5)
        redaction = schema("ReleasedTrialSummaryRedactionManifest")
        for marker in (
            "exclude_credentials",
            "exclude_file_content",
            "exclude_private_locators",
            "exclude_provider_payloads",
            "exclude_unapproved_external_projection",
        ):
            self.assertIn(marker, redaction)

    def test_command_bodies_accept_only_exact_expected_truth_and_reason(self) -> None:
        retain = schema("RetainReleasedTrialSummary")
        revise = schema("ReviseReleasedTrialSummary")
        for marker in (
            "expectedRoundOptimisticVersion:",
            "expectedRoundSnapshotHash:",
            "conclusionRevisionGlobalId:",
            "expectedConclusionVersion:",
            "expectedConclusionSnapshotHash:",
            "reason:",
        ):
            self.assertIn(marker, retain)
            self.assertIn(marker, revise)
        for marker in (
            "predecessorRevisionGlobalId:",
            "expectedPredecessorVersion:",
            "expectedPredecessorSnapshotHash:",
        ):
            self.assertIn(marker, revise)
        for forbidden in (
            "tenantId:",
            "actorUserId:",
            "sourceManifest:",
            "presentationProjection:",
            "redactionManifest:",
            "externalEvent:",
        ):
            self.assertNotIn(forbidden, retain)
            self.assertNotIn(forbidden, revise)

    def test_ownership_keeps_npi_snapshot_print_policy_and_external_projection_separate(self) -> None:
        self.assertIn("  ReleasedTrialSummaryRevision:\n", OWNERSHIP)
        for boundary in (
            "conflict: APPEND_ONLY_EXACT_CURRENT_TIP",
            "conflict: EXACT_SOURCE_IDENTITIES_VERSIONS_AND_HASHES_WIN",
            "conflict: CLOSED_SERVER_DERIVED_NO_TRUNCATION",
            "conflict: EXACT_RETAINED_REVISION_ONLY",
            "conflict: NOT_INSTALLED_BY_P7_07",
            "conflict: UNAVAILABLE_UNDER_DR_REC_009",
            "conflict: NO_AUTOMATIC_MUTATION_OR_AUTHORITY",
        ):
            self.assertIn(boundary, OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
