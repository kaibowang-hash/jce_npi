from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_core.historical_migration.domain import (
    BundleInspection,
    MigrationAction,
    MigrationFamily,
    MigrationFinding,
    MigrationRow,
    TargetObservation,
    build_preview,
    sha256_json,
)


class Resolver:
    def observe(self, row: MigrationRow) -> TargetObservation:
        return TargetObservation(action=MigrationAction.CREATE)


def source_row(*, findings=()) -> MigrationRow:
    return MigrationRow(
        family=MigrationFamily.PROJECT,
        ordinal=2,
        source_key="project-01",
        values=(("source_key", "project-01"), ("title", "Historical mold")),
        findings=tuple(findings),
    )


class Phase9HistoricalMigrationDomainTest(unittest.TestCase):
    def test_preview_identity_hash_and_summary_are_immutable_and_deterministic(self) -> None:
        inspection = BundleInspection(
            bundle_id=UUID(int=1), source_system="LEGACY_NPI", source_sha256="a" * 64,
            manifest_hash="b" * 64, predecessor_manifest_hash=None, rows=(source_row(),),
        )
        preview = build_preview(
            inspection, Resolver(), source_file_revision_global_id=UUID(int=2),
            source_file_optimistic_version=3, tenant_id="tenant-a", actor="owner@example.invalid",
            created_at=datetime(2026, 9, 3, 9, tzinfo=UTC), request_id=UUID(int=4), trace_id="trace-p9-05",
        )
        self.assertEqual(preview.summary(), {"create": 1, "link": 0, "skip": 0, "blocked": 0})
        self.assertEqual(preview.snapshot_hash, sha256_json(preview.snapshot_payload()))
        self.assertEqual(preview.response()["snapshotHash"], preview.snapshot_hash)

    def test_source_findings_force_blocked_preview_without_resolver_override(self) -> None:
        finding = MigrationFinding("invalid_owner", "owner_user_id", "Owner unavailable")
        inspection = BundleInspection(
            bundle_id=UUID(int=1), source_system="LEGACY_NPI", source_sha256="a" * 64,
            manifest_hash="b" * 64, predecessor_manifest_hash=None,
            rows=(source_row(findings=(finding,)),),
        )
        preview = build_preview(
            inspection, Resolver(), source_file_revision_global_id=UUID(int=2),
            source_file_optimistic_version=1, tenant_id="tenant-a", actor="owner@example.invalid",
            created_at=datetime(2026, 9, 3, 9, tzinfo=UTC), request_id=UUID(int=4), trace_id="trace-p9-05",
        )
        self.assertTrue(preview.blocked)
        self.assertEqual(preview.rows[0].action, MigrationAction.BLOCKED)
        self.assertEqual(preview.rows[0].findings, (finding,))


if __name__ == "__main__":
    unittest.main()
