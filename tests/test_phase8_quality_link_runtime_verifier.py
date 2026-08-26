from __future__ import annotations

import ast
import importlib
import json
import os
import sys
import tempfile
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
        self.assertIn("--read-diagnostic", completed.stdout)

    def test_diagnostic_stage_allowlist_is_exact_and_lexically_unique(self) -> None:
        expected = (
            "P806_QUALITY_BOOTSTRAP_SECRET",
            "P806_QUALITY_ADMIN_LOGIN",
            "P806_QUALITY_PROJECT_CONTEXT",
            "P806_QUALITY_ACTOR_LOGIN",
            "P806_QUALITY_CSRF",
            "P806_QUALITY_READINESS_HTTP",
            "P806_QUALITY_READINESS_SHAPE",
            "P806_QUALITY_PREPARE_PROJECTION",
            "P806_QUALITY_CURRENT_TRUTH",
            "P806_QUALITY_CREATE_HTTP",
            "P806_QUALITY_CREATE_SHAPE",
            "P806_QUALITY_REPLAY_HTTP",
            "P806_QUALITY_REPLAY_SHAPE",
            "P806_QUALITY_STALE_HTTP",
            "P806_QUALITY_LIST_HTTP",
            "P806_QUALITY_LIST_SHAPE",
            "P806_QUALITY_CLEANUP",
        )
        self.assertEqual(self.verifier.QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES, expected)
        source = (ROOT / "scripts/verify_quality_link_runtime.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        stages = [
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "quality_link_runtime_diagnostic_step"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ]
        self.assertEqual(len(stages), 17)
        self.assertEqual(set(stages), set(expected))

    def test_diagnostic_record_is_one_exact_safe_inner_stage(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                self.assertRaisesRegex(ValueError, "private-value"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_BOOTSTRAP_SECRET"
                ),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_ADMIN_LOGIN"
                ),
            ):
                raise ValueError("private-value")
            self.assertEqual(
                self.verifier.read_quality_link_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                ("ValueError", "P806_QUALITY_ADMIN_LOGIN", trace_id),
            )
            payload = path.read_text(encoding="utf-8")
            self.assertNotIn("private-value", payload)
            self.assertEqual(set(json.loads(payload)), {"code", "exceptionType", "traceId"})

    def test_diagnostic_reader_rejects_missing_duplicate_wrong_or_malformed_records(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        good = {
            "code": "P806_QUALITY_CREATE_HTTP",
            "exceptionType": "RuntimeError",
            "traceId": trace_id,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            self.assertIsNone(
                self.verifier.read_quality_link_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                )
            )
            cases = (
                json.dumps(good) + "\n" + json.dumps(good) + "\n",
                json.dumps({**good, "code": "P806_QUALITY_UNKNOWN"}) + "\n",
                json.dumps({**good, "traceId": "trace-ffffffffffffffffffffffffffffffff"}) + "\n",
                json.dumps({**good, "private": "not-safe"}) + "\n",
                "not-json\n",
            )
            for payload in cases:
                with self.subTest(payload=payload[:24]):
                    path.write_text(payload, encoding="utf-8")
                    self.assertIsNone(
                        self.verifier.read_quality_link_runtime_diagnostic(
                            path,
                            expected_trace=trace_id,
                        )
                    )

    def test_diagnostic_disabled_has_zero_file_or_behavior_effect(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                self.assertRaisesRegex(RuntimeError, "same-error"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_CREATE_HTTP"
                ),
            ):
                raise RuntimeError("same-error")
            self.assertFalse(path.exists())

    def test_runtime_shell_never_reads_failed_child_output_and_uses_strict_reader(self) -> None:
        source = (ROOT / "scripts/verify-frappe-runtime.sh").read_text(encoding="utf-8")
        self.assertIn(
            "run_quality_link_runtime_verifier >/dev/null 2>/dev/null",
            source,
        )
        self.assertIn("read_quality_link_runtime_diagnostic", source)
        self.assertIn("--expected-trace", source)
        self.assertIn("P8-06 formal quality link runtime diagnostic", source)

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
                self.verifier.run_fresh(
                    "http://npi.localhost",
                    "fixture-secret",
                    "administrator-secret",
                )
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
