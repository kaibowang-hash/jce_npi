from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_historical_migration_runtime.py"
SHELL = ROOT / "scripts/verify-frappe-runtime.sh"
RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_historical_migration_runtime_contract", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError("P9-05 runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(os.environ, {"NPI_DOCUMENT_RUNTIME_RUN_ID": RUN_ID}, clear=False):
        spec.loader.exec_module(module)
    return module


class HistoricalMigrationRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_verifier()
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")

    def test_fixture_is_deterministic_synthetic_and_has_no_production_transport(self) -> None:
        self.assertEqual(self.verifier.FIXTURE_RUN_ID, RUN_ID)
        self.assertEqual(
            self.verifier.deterministic_uuid("same"),
            self.verifier.deterministic_uuid("same"),
        )
        self.assertIn("@example.invalid", self.source)
        self.assertIn('"productionContact": False', self.source)
        self.assertNotIn("JCE-Core", self.source)
        self.assertNotIn("ssh ", self.source)

    def test_runtime_covers_closed_bundle_partial_replay_correction_and_rollback(self) -> None:
        for literal in (
            '"projects.csv"',
            '"tooling_mappings.csv"',
            '"file_index.csv"',
            '"npi_references.csv"',
            '"partially_succeeded"',
            '"exactReplay"',
            '"staleRejected"',
            '"correctionSha256"',
            '"reconciliationReplay"',
            '"rollbackDecision"',
            "frappe.db.rollback()",
        ):
            self.assertIn(literal, self.source)
        self.assertNotIn("frappe.db" + ".sql", self.source)

    def test_bench_child_output_is_unread_on_failure(self) -> None:
        function = self.source[
            self.source.index("def run_bench_fixture") : self.source.index(
                "def run_local_bench_fixture"
            )
        ]
        self.assertIn("stderr=subprocess.DEVNULL", function)
        self.assertLess(
            function.index("completed.returncode == 0"),
            function.index("output.seek(0)"),
        )

    def test_cumulative_gate_invokes_runtime_once(self) -> None:
        marker = "run_historical_migration_runtime_verifier"
        self.assertEqual(self.shell.count(f"{marker}()"), 1)
        self.assertEqual(
            self.shell.count(f"if ! {marker} >/dev/null 2>/dev/null; then"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
