from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")


def path_block(path: str, next_path: str) -> str:
    return CONTRACT.split(f"  {path}:\n", 1)[1].split(f"\n  {next_path}:\n", 1)[0]


def schema(name: str) -> str:
    start = CONTRACT.split(f"    {name}:\n", 1)[1]
    match = re.search(r"\n    [A-Za-z][A-Za-z0-9]+:\n", start)
    return start if match is None else start[: match.start()]


class Phase5EngineeringBomContractTest(unittest.TestCase):
    def test_routes_are_exact_and_do_not_offer_mutable_latest_comparison(self) -> None:
        operations = {
            "/projects/{projectId}/eboms": (
                "listEngineeringBoms",
                "createEngineeringBom",
            ),
            "/projects/{projectId}/eboms/{ebomId}": ("getEngineeringBom",),
            "/projects/{projectId}/eboms/{ebomId}/revisions": (
                "createEngineeringBomRevision",
            ),
            "/projects/{projectId}/eboms/{ebomId}/revisions/{revisionId}:submit-review": (
                "submitEngineeringBomReview",
            ),
            "/projects/{projectId}/eboms/{ebomId}/revisions/{revisionId}:review": (
                "reviewEngineeringBomRevision",
            ),
            "/projects/{projectId}/eboms/{ebomId}/revisions/{revisionId}:release": (
                "releaseEngineeringBomRevision",
            ),
        }
        for path, expected in operations.items():
            with self.subTest(path=path):
                value = CONTRACT.split(f"  {path}:\n", 1)[1].split("\n  /", 1)[0]
                for operation in expected:
                    self.assertIn(f"operationId: {operation}", value)
        compare = path_block(
            "/projects/{projectId}/eboms/{ebomId}/compare",
            "/tooling/{toolingId}/cockpit",
        )
        self.assertIn("operationId: compareEngineeringBomRevisions", compare)
        self.assertIn("name: fromRevisionId", compare)
        self.assertIn("name: toRevisionId", compare)
        self.assertNotIn("latest", compare.casefold())

    def test_commands_bind_actor_authority_transaction_audit_and_replay_headers(self) -> None:
        section = CONTRACT.split("  /projects/{projectId}/eboms:\n", 1)[1].split(
            "\n  /tooling/{toolingId}/cockpit:\n", 1
        )[0]
        for authority in (
            "exact-ebom-policy-creator",
            "exact-ebom-policy-review-submitter",
            "exact-ebom-policy-reviewer",
            "exact-ebom-policy-release-authority",
        ):
            self.assertIn(authority, section)
        self.assertIn("x-transaction-boundary: engineering-bom-root-revision", section)
        self.assertIn("x-transaction-boundary: engineering-bom-lifecycle", section)
        for operation in (
            "ebom.create",
            "ebom.revise",
            "ebom.submit_review",
            "ebom.review",
            "ebom.release",
        ):
            self.assertIn(f"x-audit-operation: {operation}", section)
        response = schema("EngineeringBomCommandResult")
        self.assertIn("Idempotency-Replayed", response)
        self.assertIn("private, no-store", response)

    def test_request_and_response_schemas_are_closed_and_bounded(self) -> None:
        names = (
            "CreateEngineeringBom",
            "CreateEngineeringBomRevision",
            "SubmitEngineeringBomReview",
            "ReviewEngineeringBomRevision",
            "ReleaseEngineeringBomRevision",
            "EngineeringBomSummary",
            "EngineeringBomRevision",
            "EngineeringBomList",
            "EngineeringBomDetail",
            "EngineeringBomCommand",
            "EngineeringBomDifference",
            "EngineeringBomComparison",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", schema(name))
        self.assertIn("maxItems: 500", schema("CreateEngineeringBom"))
        self.assertIn("maxItems: 2500", schema("EngineeringBomComparison"))
        release = schema("ReleaseEngineeringBomRevision")
        self.assertIn("const: true", release)
        self.assertIn("const: release_exact_ebom_revision", release)

    def test_contract_exposes_no_formal_erp_or_browser_asserted_identity(self) -> None:
        section = CONTRACT.split("    EngineeringBomPolicyReference:\n", 1)[1].split(
            "\n    ToolingCockpit:\n", 1
        )[0].casefold()
        for forbidden in (
            "itemcode",
            "item_code",
            "stockuom",
            "stock_uom",
            "mbomid",
            "routingid",
            "creatoruserids",
            "releaseauthorityuserids",
            "fileurl",
        ):
            self.assertNotIn(forbidden, section)


if __name__ == "__main__":
    unittest.main()
