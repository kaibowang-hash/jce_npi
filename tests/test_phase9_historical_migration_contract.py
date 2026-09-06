from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")


def path_block(path: str) -> str:
    paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
    start = paths.index(f"  {path}:\n")
    match = re.search(r"\n  /[^\n]+:\n", paths[start + 1 :])
    return paths[start:] if match is None else paths[start : start + 1 + match.start()]


def schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase9HistoricalMigrationContractTest(unittest.TestCase):
    def test_surface_is_operation_specific_system_manager_and_non_production(self) -> None:
        operations = {
            "/administration/historical-migration-rehearsals": {"get", "post"},
            "/administration/historical-migration-rehearsals/{previewId}:execute": {"post"},
            "/administration/historical-migration-jobs/{jobId}": {"get"},
            "/administration/historical-migration-jobs/{jobId}/correction-artifacts": {"post"},
            "/administration/historical-migration-jobs/{jobId}/correction-artifact:content": {"post"},
            "/administration/historical-migration-jobs/{jobId}:reconcile": {"post"},
            "/administration/historical-migration-jobs/{jobId}:rollback": {"post"},
        }
        for path, methods in operations.items():
            with self.subTest(path=path):
                block = path_block(path)
                self.assertEqual(set(re.findall(r"^    (get|post):$", block, re.MULTILINE)), methods)
                self.assertIn("tags: [Administration]", block)
                self.assertIn("System Manager", block)
        self.assertIn("non-production", path_block("/administration/historical-migration-rehearsals").casefold())

    def test_commands_are_exact_idempotent_csrf_and_audited(self) -> None:
        for path in (
            "/administration/historical-migration-rehearsals",
            "/administration/historical-migration-rehearsals/{previewId}:execute",
            "/administration/historical-migration-jobs/{jobId}/correction-artifacts",
            "/administration/historical-migration-jobs/{jobId}:reconcile",
            "/administration/historical-migration-jobs/{jobId}:rollback",
        ):
            post = path_block(path).split("\n    post:\n", 1)[1]
            for parameter in ("IdempotencyKey", "RequestId", "CsrfToken"):
                self.assertIn(f"#/components/parameters/{parameter}", post)
            self.assertIn("x-transaction-boundary:", post)
            self.assertIn("x-audit-operation: historical_migration.", post)

    def test_requests_and_responses_are_closed_versioned_and_hash_bound(self) -> None:
        for name in (
            "CreateHistoricalMigrationPreview", "HistoricalMigrationVersionCommand",
            "HistoricalMigrationPreviewRow", "HistoricalMigrationPreview",
            "HistoricalMigrationRowResult", "HistoricalMigrationJob",
            "HistoricalMigrationCorrectionArtifact", "HistoricalMigrationReconciliation",
            "HistoricalMigrationRollback", "HistoricalMigrationWorkspace",
        ):
            self.assertIn("additionalProperties: false", schema(name), name)
        self.assertIn("historical-migration-preview.v1", schema("HistoricalMigrationPreview"))
        self.assertIn("historical-migration-job.v1", schema("HistoricalMigrationJob"))
        self.assertIn("productionContact: { type: boolean, const: false }", schema("HistoricalMigrationJob"))
        self.assertIn("targetRetained: { type: boolean, const: true }", schema("HistoricalMigrationRollbackItem"))

    def test_no_generic_writer_or_production_route_is_exposed(self) -> None:
        joined = "\n".join(
            (
                path_block("/administration/historical-migration-rehearsals"),
                schema("HistoricalMigrationWorkspace"),
                schema("CreateHistoricalMigrationPreview"),
            )
        ).casefold()
        for forbidden in ("doctype", "sql", "production endpoint", "target method"):
            self.assertNotIn(forbidden, joined)


if __name__ == "__main__":
    unittest.main()
