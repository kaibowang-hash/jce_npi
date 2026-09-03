from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_core.historical_migration import bundle


class Phase9HistoricalMigrationSecurityTest(unittest.TestCase):
    def test_archive_limits_and_formula_defence_are_fixed_constants(self) -> None:
        self.assertEqual(bundle.MAX_BUNDLE_BYTES, 20_000_000)
        self.assertEqual(bundle.MAX_MEMBER_BYTES, 8_000_000)
        self.assertEqual(bundle.MAX_ROWS_PER_MEMBER, 2_000)
        self.assertEqual(bundle.MAX_COMPRESSION_RATIO, 100)
        source = inspect.getsource(bundle)
        for marker in ("flag_bits & 0x1", "compress_size", 'startswith(("=", "+", "-", "@"))'):
            self.assertIn(marker, source)

    def test_backend_has_no_network_production_or_generic_writer_escape(self) -> None:
        paths = tuple((ROOT / "apps/npi_core/npi_core/historical_migration").glob("*.py")) + (
            ROOT / "apps/npi_core/npi_core/historical_migration_api.py",
        )
        joined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for forbidden in (
            "requests.", "httpx.", "paramiko", "subprocess", "os.system",
            "frappe.db." + "sql", "ignore_permissions", "bench console",
            "frappe.client." + "insert", "frappe.client." + "set_value",
        ):
            self.assertNotIn(forbidden, joined)
        self.assertNotIn("doctype: Any", joined)
        self.assertIn("productionContact", joined)
        self.assertIn("npi_p9_05_non_production_rehearsal", joined)

    def test_worker_reauthorizes_actor_source_preview_and_hash_before_rows(self) -> None:
        source = (ROOT / "apps/npi_core/npi_core/historical_migration/frappe_repository.py").read_text(encoding="utf-8")
        worker = source[source.index("def run_historical_migration_job") : source.index("def _fail_job")]
        positions = [
            worker.index("authenticated_principal"),
            worker.index("preview.snapshot_hash"),
            worker.index("repository._load_source"),
            worker.index("inspection.manifest_hash"),
            worker.index("repository._execute_row"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("frappe.db.rollback()", worker)
        self.assertIn("FAILED_RETRYABLE", source)
        self.assertNotIn('Principal("Administrator"', source)
        ast.parse(source)

    def test_governed_write_scope_is_the_only_audit_append_boundary(self) -> None:
        source = (ROOT / "apps/npi_core/npi_core/historical_migration/frappe_validation.py").read_text(encoding="utf-8")
        self.assertIn('frappe.flags.npi_audit_append = True', source)
        self.assertIn('delattr(frappe.flags, "npi_audit_append")', source)

    def test_reconciliation_and_rollback_reject_incomplete_jobs(self) -> None:
        source = (ROOT / "apps/npi_core/npi_core/historical_migration/frappe_repository.py").read_text(encoding="utf-8")
        self.assertIn("Only a completed rehearsal job can be reconciled.", source)
        self.assertIn(
            "Only a completed rehearsal job can be evaluated for rollback.", source
        )

    def test_correction_contains_no_source_or_target_business_values(self) -> None:
        source = (ROOT / "apps/npi_core/npi_core/historical_migration/frappe_repository.py").read_text(encoding="utf-8")
        correction = source[source.index("def _correction_csv") : source.index("def _result_list")]
        for allowed in ("family", "source_key", "finding_code", "corrected_value"):
            self.assertIn(allowed, correction)
        for forbidden in ("sourceValue", "targetValue", "endpoint", "token", "cookie"):
            self.assertNotIn(forbidden, correction)


if __name__ == "__main__":
    unittest.main()
