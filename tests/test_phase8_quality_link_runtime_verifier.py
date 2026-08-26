from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]


class Phase8QualityLinkRuntimeVerifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = importlib.reload(importlib.import_module("verify_quality_link_runtime"))

    def test_runtime_is_disposable_network_free_and_uses_only_existing_routes(self) -> None:
        source = (ROOT / "scripts/verify_quality_link_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("httpx", source)
        self.assertNotIn("urllib.request", source)
        for route in (
            "/npi-readiness",
            "/formal-quality-links:link-observed-reference",
            "/formal-quality-links",
        ):
            self.assertIn(route, source)
        for marker in (
            '"targetTraffic": 0',
            '"cleaned": True',
            '"staleRejected": True',
            "Idempotency-Replayed",
        ):
            self.assertIn(marker, source)

    def test_acknowledgement_and_source_scope_are_exact_and_never_map_pass(self) -> None:
        self.assertEqual(
            self.verifier.ACKNOWLEDGEMENT,
            "I confirm this links only the exact observed formal quality reference. "
            "It does not write ERPNext or interpret a formal pass.",
        )
        source = (ROOT / "scripts/verify_quality_link_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"sourceKind": "readiness_assessment"', source)
        self.assertIn("ProjectionScopeKind.READINESS", source)
        self.assertNotIn('"pass": True', source)
        self.assertNotIn("ignore_permissions", source)

    def test_http_body_reader_fails_closed_without_leaking_body(self) -> None:
        result = types.SimpleNamespace(status=200, body={"closed": True})
        self.assertEqual(self.verifier._body(result, status=200), {"closed": True})
        with self.assertRaisesRegex(RuntimeError, "HTTP boundary drifted"):
            self.verifier._body(types.SimpleNamespace(status=500, body={"secret": "x"}), status=200)
        with self.assertRaisesRegex(RuntimeError, "not an object"):
            self.verifier._body(types.SimpleNamespace(status=200, body=["x"]), status=200)

    def test_cli_help_is_executable_without_frappe_or_secret_environment(self) -> None:
        import subprocess

        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_quality_link_runtime.py"), "--help"],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "scripts")},
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("--base-url", completed.stdout)

    def test_bench_fixture_allowlist_and_arguments_are_closed(self) -> None:
        source = (ROOT / "scripts/verify_quality_link_runtime.py").read_text(encoding="utf-8")
        self.assertIn('method in {"prepare_projection", "cleanup"}', source)
        self.assertIn("P8-06 fixture arguments are invalid", source)
        self.assertIn("frappe.db.rollback()", source)
        self.assertIn("frappe.destroy()", source)

    def test_prepared_projection_is_cleaned_when_runtime_proof_fails(self) -> None:
        workspace = types.SimpleNamespace(
            status=200,
            body={
                "currentRevision": {
                    "instanceGlobalId": "10000000-0000-4000-8000-000000000001",
                },
            },
        )
        with (
            patch.object(self.verifier, "secret_from_environment", return_value="secret"),
            patch.object(self.verifier, "login", side_effect=[object(), object()]),
            patch.object(
                self.verifier.document_runtime,
                "fixture_project",
                return_value=("10000000-0000-4000-8000-000000000002", {}),
            ),
            patch.object(self.verifier, "bootstrap_csrf", return_value="csrf"),
            patch.object(
                self.verifier.document_runtime,
                "npi_request",
                return_value=workspace,
            ),
            patch.object(
                self.verifier,
                "run_bench_fixture",
                side_effect=[{"item": {}}, {"cleaned": True}],
            ) as fixture,
            patch.object(
                self.verifier,
                "_exercise_link",
                side_effect=RuntimeError("synthetic proof failure"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic proof failure"):
                self.verifier.run_fresh("http://npi.localhost", "fixture-secret")
        self.assertEqual(
            fixture.call_args_list,
            [
                call(
                    "prepare_projection",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                    },
                ),
                call(
                    "cleanup",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                    },
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
