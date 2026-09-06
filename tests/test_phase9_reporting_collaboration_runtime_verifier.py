from __future__ import annotations

import ast
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_reporting_collaboration_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
RUN_ID = "0123456789abcdef0123456789abcdef"
PROJECT_ID = "00000000-0000-4000-8000-000000000902"
ACTOR = "npi-readiness-0123456789abcdef0123-manager@example.invalid"
LIMITED = "npi-document-0123456789abcdef0123-baseline@example.invalid"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_reporting_collaboration_runtime_contract", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError("P9-02 runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(
        os.environ,
        {
            "NPI_DOCUMENT_RUNTIME_RUN_ID": RUN_ID,
            "NPI_P9_02D_RUNTIME_ACTOR": ACTOR,
            "NPI_P9_02D_RUNTIME_LIMITED_ACTOR": LIMITED,
            "NPI_P9_02D_RUNTIME_PROJECT_ID": PROJECT_ID,
        },
        clear=False,
    ):
        spec.loader.exec_module(module)
    return module


class Phase9ReportingCollaborationRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_verifier()
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")

    def test_template_hash_and_fixture_identity_are_exact(self) -> None:
        sys.path.insert(0, str(ROOT / "apps" / "npi_core"))
        from npi_core.collaboration.domain import (
            STANDARD_MEETING_TEMPLATE,
            STANDARD_MEETING_TEMPLATE_HASH,
        )

        self.assertEqual(
            self.verifier.STANDARD_MEETING_TEMPLATE, STANDARD_MEETING_TEMPLATE
        )
        self.assertEqual(
            self.verifier.STANDARD_MEETING_TEMPLATE_HASH,
            STANDARD_MEETING_TEMPLATE_HASH,
        )
        self.assertEqual(self.verifier.PROJECT_ID, PROJECT_ID)
        self.assertEqual(self.verifier.ACTOR_USER, ACTOR)
        self.assertEqual(self.verifier.LIMITED_USER, LIMITED)

    def test_runtime_covers_required_truth_and_fault_boundaries(self) -> None:
        for literal in (
            '"/api/npi/v1/portfolio/projects"',
            '"/api/npi/v1/search"',
            '"/api/npi/v1/reports/kpis"',
            '"/api/npi/v1/administration/capabilities"',
            '"/api/npi/v1/notifications"',
            '"/api/npi/v1/me/preferences/notifications"',
            '"seed_notification"',
            '"email_queue_failed"',
            '"IDEMPOTENCY_KEY_CONFLICT"',
            '"VERSION_CONFLICT"',
            '"REPORTING_ROUTES_DISABLED"',
            '"crossProcessReplay"',
            '"routeRecovered"',
            '"cleanupComplete"',
            '"perf_counter_ns"',
            '"nearest-rank"',
            '"disposable-local-frappe-site"',
        ):
            self.assertIn(literal, self.source)
        self.assertIn('method="POST"', self.source)
        self.assertIn('"expectedVersion": 0', self.source)
        self.assertNotIn("JCE-Core", self.source)
        self.assertNotIn("ssh ", self.source)

    def test_performance_probe_has_fixed_samples_and_nearest_rank_p95(self) -> None:
        ticks = iter(
            value
            for index in range(22)
            for value in (index * 2_000_000, index * 2_000_000 + 1_000_000)
        )
        with patch.object(
            self.verifier,
            "_read",
            return_value=types.SimpleNamespace(body={"schemaVersion": 1}),
        ):
            evidence = self.verifier.measure_read_performance(
                object(),
                "http://127.0.0.1:8000",
                {"portfolio": ("/api/npi/v1/portfolio/projects", 3_000)},
                clock=lambda: next(ticks),
            )
        self.assertEqual(evidence["sampleCount"], 20)
        self.assertEqual(evidence["warmupCount"], 2)
        self.assertEqual(evidence["percentileMethod"], "nearest-rank")
        self.assertEqual(evidence["operations"]["portfolio"]["p95Ms"], 1.0)
        self.assertEqual(evidence["operations"]["portfolio"]["thresholdMs"], 3_000)

    def test_scheduler_fixture_is_bounded_and_restores_monkeypatches(self) -> None:
        seed = self.source[
            self.source.index("def _seed_notification") : self.source.index(
                "def _cleanup"
            )
        ]
        self.assertIn('if doctype == "NPI My Work Assignment"', seed)
        self.assertIn("frappe.get_all = original_get_all", seed)
        self.assertIn("frappe.sendmail = original_sendmail", seed)
        self.assertIn("second = refresh_due_notifications(now)", seed)
        forbidden_call = ".".join(("frappe", "db", "sql"))
        called_functions = {
            ast.unparse(node.func)
            for node in ast.walk(ast.parse(seed))
            if isinstance(node, ast.Call)
        }
        self.assertNotIn(forbidden_call, called_functions)

    def test_bench_child_output_is_unread_on_failure(self) -> None:
        tree = ast.parse(self.source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "run_bench_fixture"
        )
        text = ast.unparse(function)
        self.assertIn("stderr=subprocess.DEVNULL", text)
        self.assertLess(
            text.index("require(completed.returncode == 0"),
            text.index("output.seek(0)"),
        )

    def test_shell_owns_route_switch_restart_and_cleanup(self) -> None:
        for literal in (
            "reporting_collaboration_route_switch_state",
            "set_reporting_collaboration_route_switch false false",
            "set_reporting_collaboration_route_switch true true",
            "run_reporting_collaboration_runtime_verifier fresh",
            "run_reporting_collaboration_runtime_verifier replay-only",
            "run_reporting_collaboration_runtime_verifier disabled",
            "run_reporting_collaboration_runtime_verifier recovered",
            "run_reporting_collaboration_runtime_verifier cleanup",
            "restore_reporting_collaboration_route_switch",
        ):
            self.assertIn(literal, self.shell)
        block = self.shell[
            self.shell.index(
                "run_reporting_collaboration_runtime_verifier disabled"
            ) : self.shell.index(
                "run_reporting_collaboration_runtime_verifier cleanup"
            )
        ]
        self.assertGreaterEqual(block.count("stop_runtime_server"), 4)
        self.assertGreaterEqual(block.count("start_runtime_server"), 4)


if __name__ == "__main__":
    unittest.main()
