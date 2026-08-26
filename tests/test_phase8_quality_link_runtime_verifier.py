from __future__ import annotations

import ast
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
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
        self.assertFalse(self.verifier.QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED)
        self.assertFalse(
            self.verifier.QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED
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

    def test_prepare_projection_allowlists_are_exact_and_lexically_unique(self) -> None:
        parent = self.verifier.QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES
        bootstrap = self.verifier.QUALITY_LINK_PREPARE_BOOTSTRAP_CODES
        server = self.verifier.QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES
        self.assertEqual(len(parent), 4)
        self.assertEqual(len(bootstrap), 5)
        self.assertEqual(len(server), 39)
        self.assertTrue(set(parent).isdisjoint(server))
        self.assertTrue(set(parent).isdisjoint(bootstrap))
        self.assertTrue(set(bootstrap).isdisjoint(server))
        verifier_source = (
            ROOT / "scripts/verify_quality_link_runtime.py"
        ).read_text(encoding="utf-8")
        repository_source = (
            ROOT
            / "apps/npi_integration/npi_integration/projections/frappe_repository.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(verifier_source + "\n" + repository_source)
        parent_stages = [
            node.args[1].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_prepare_parent_diagnostic_step"
            and len(node.args) == 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ]
        bootstrap_stages = [
            node.args[1].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_prepare_bootstrap_diagnostic_step"
            and len(node.args) == 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ]
        server_stages = [
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "quality_link_prepare_projection_step"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "quality_link_prepare_projection_step"
                )
            )
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ]
        self.assertEqual(len(parent_stages), len(parent))
        self.assertEqual(set(parent_stages), set(parent))
        self.assertEqual(len(bootstrap_stages), len(bootstrap))
        self.assertEqual(set(bootstrap_stages), set(bootstrap))
        self.assertEqual(
            sorted(parent, key=verifier_source.index),
            list(parent),
        )
        self.assertEqual(len(server_stages), len(server))
        self.assertEqual(set(server_stages), set(server))
        assignment = next(
            node
            for node in ast.parse(repository_source).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id
                == "QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTIC_CODES"
                for target in node.targets
            )
        )
        repository_codes = {
            element.value
            for element in assignment.value.args[0].elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }
        self.assertEqual(repository_codes, server)

    def test_prepare_bootstrap_records_init_before_frappe_flags_exist(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        private = "private-value"
        frappe = types.ModuleType("frappe")

        def fail_init(**_kwargs) -> None:
            raise ValueError(private)

        frappe.init = fail_init
        repository = types.ModuleType(
            "npi_integration.projections.frappe_repository"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.dict(
                    sys.modules,
                    {
                        "frappe": frappe,
                        "npi_integration.projections.frappe_repository": repository,
                    },
                ),
                patch.dict(
                    os.environ,
                    {
                        self.verifier._DIAGNOSTIC_PATH_ENV: str(path),
                        self.verifier._PREPARE_PROJECTION_DIAGNOSTIC_ENV:
                        self.verifier._PREPARE_PROJECTION_DIAGNOSTIC_SCOPE,
                    },
                    clear=False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
                    True,
                ),
                self.assertRaisesRegex(ValueError, private),
            ):
                self.verifier.run_scoped_local_bench_fixture(
                    "prepare_projection",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                        "diagnostic_trace_id": trace_id,
                    },
                )
            with patch.object(
                self.verifier,
                "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
                True,
            ):
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    (
                        "ValueError",
                        "P806_QUALITY_PREPARE_BOOTSTRAP_INIT",
                        trace_id,
                    ),
                )
            self.assertNotIn(private, path.read_text(encoding="utf-8"))

    def test_prepare_bootstrap_wrong_scope_or_trace_is_dormant(self) -> None:
        valid_trace = "trace-0123456789abcdef0123456789abcdef"
        error = RuntimeError("same-private-error")
        with tempfile.TemporaryDirectory() as directory:
            for scope, trace_id in (
                ("wrong-scope", valid_trace),
                (self.verifier._PREPARE_PROJECTION_DIAGNOSTIC_SCOPE, "trace-invalid"),
            ):
                path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
                path.unlink(missing_ok=True)
                with (
                    self.subTest(scope=scope, trace_id=trace_id),
                    patch.dict(
                        os.environ,
                        {
                            self.verifier._DIAGNOSTIC_PATH_ENV: str(path),
                            self.verifier._PREPARE_PROJECTION_DIAGNOSTIC_ENV: scope,
                        },
                        clear=False,
                    ),
                    patch.object(
                        self.verifier,
                        "run_local_bench_fixture",
                        side_effect=error,
                    ),
                    self.assertRaises(RuntimeError) as raised,
                ):
                    self.verifier.run_scoped_local_bench_fixture(
                        "prepare_projection",
                        {"diagnostic_trace_id": trace_id},
                    )
                self.assertIs(raised.exception, error)
                self.assertFalse(path.exists())

    def test_prepare_bootstrap_binds_repository_context_only_after_init(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        events: list[str] = []

        class FreshFrappe(types.ModuleType):
            initialized = False

            def __getattribute__(self, name: str):
                if name == "flags" and not object.__getattribute__(
                    self,
                    "initialized",
                ):
                    raise RuntimeError("frappe flags are not bound")
                return super().__getattribute__(name)

        frappe = FreshFrappe("frappe")

        def init(**_kwargs) -> None:
            events.append("init")
            frappe.initialized = True
            frappe.flags = types.SimpleNamespace()
            frappe.local = types.SimpleNamespace(initialised=True)

        frappe.init = init
        frappe.connect = lambda: events.append("connect")
        frappe.set_user = lambda _user: events.append("set-user")
        frappe.destroy = lambda: events.append("destroy")
        frappe.db = types.SimpleNamespace(
            commit=lambda: events.append("commit"),
            rollback=lambda: events.append("rollback"),
        )
        repository = types.ModuleType(
            "npi_integration.projections.frappe_repository"
        )
        repository._QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTIC_FLAG = (
            "npi_p806_quality_prepare_projection_diagnostic"
        )

        @contextmanager
        def diagnostics(active_trace: str):
            events.append("context")
            setattr(
                frappe.flags,
                repository._QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTIC_FLAG,
                {"trace_id": active_trace, "recorded": False},
            )
            try:
                yield
            finally:
                delattr(
                    frappe.flags,
                    repository._QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTIC_FLAG,
                )

        @contextmanager
        def step(_code: str):
            yield

        repository.quality_link_prepare_projection_diagnostics = diagnostics
        repository.quality_link_prepare_projection_step = step
        with (
            patch.dict(
                sys.modules,
                {
                    "frappe": frappe,
                    "npi_integration.projections.frappe_repository": repository,
                },
            ),
            patch.dict(
                os.environ,
                {
                    self.verifier._PREPARE_PROJECTION_DIAGNOSTIC_ENV:
                    self.verifier._PREPARE_PROJECTION_DIAGNOSTIC_SCOPE,
                },
                clear=False,
            ),
            patch.object(
                self.verifier.document_runtime,
                "_validated_runtime_site",
            ),
            patch.object(
                self.verifier,
                "prepare_projection",
                return_value={"prepared": True},
            ),
            patch("builtins.print"),
        ):
            self.verifier.run_scoped_local_bench_fixture(
                "prepare_projection",
                {
                    "project_id": "10000000-0000-4000-8000-000000000002",
                    "readiness_id": "10000000-0000-4000-8000-000000000001",
                    "diagnostic_trace_id": trace_id,
                },
            )
        self.assertLess(events.index("init"), events.index("context"))
        self.assertLess(events.index("context"), events.index("connect"))
        self.assertEqual(events[-2:], ["commit", "destroy"])

    def test_diagnostic_record_is_one_exact_safe_inner_stage(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                self.assertRaisesRegex(ValueError, "private-value"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_PREPARE_PARENT_SUBPROCESS"
                ),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_PREPARE_PARENT_CHILD_STATUS"
                ),
            ):
                raise ValueError("private-value")
            with patch.object(
                self.verifier,
                "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
                True,
            ):
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    (
                        "ValueError",
                        "P806_QUALITY_PREPARE_PARENT_CHILD_STATUS",
                        trace_id,
                    ),
                )
            payload = path.read_text(encoding="utf-8")
            self.assertNotIn("private-value", payload)
            self.assertEqual(set(json.loads(payload)), {"code", "exceptionType", "traceId"})

    def test_diagnostic_reader_rejects_missing_duplicate_wrong_or_malformed_records(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        good = {
            "code": "P806_QUALITY_PREPARE_PARENT_RESULT_SHAPE",
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
                    "QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
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
                    "P806_QUALITY_PREPARE_PARENT_RESULT_SHAPE"
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
        self.assertIn(
            'NPI_P806_QUALITY_PREPARE_PROJECTION_DIAGNOSTIC_SCOPE="p8-06-quality-link-prepare-projection-v1"',
            source,
        )

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

    def test_failed_prepare_child_prefers_one_strict_server_tuple(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        server_code = "P806_QUALITY_PROJECTION_SCOPE"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                patch.object(
                    self.verifier.item_runtime,
                    "_replay_diagnostic_log_cursors",
                    return_value={"logs/npi_core.log": 0},
                ),
                patch.object(
                    self.verifier.item_runtime,
                    "_sanitized_server_log_diagnostic",
                    return_value=("ValueError", server_code, trace_id),
                ) as reader,
                patch.object(
                    self.verifier.subprocess,
                    "run",
                    return_value=types.SimpleNamespace(returncode=1),
                ) as child,
                self.assertRaisesRegex(RuntimeError, "Bench fixture failed"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
            ):
                self.verifier.run_bench_fixture(
                    "prepare_projection",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                        "diagnostic_trace_id": trace_id,
                    },
                )
            with patch.object(
                self.verifier,
                "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
                True,
            ):
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("ValueError", server_code, trace_id),
                )
            reader.assert_called_once_with(
                trace_id,
                {"logs/npi_core.log": 0},
                code_prefix="P806_QUALITY_",
                allowed_codes=self.verifier.QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES,
            )
            self.assertIs(child.call_args.kwargs["stderr"], self.verifier.subprocess.DEVNULL)

    def test_failed_prepare_child_falls_back_to_parent_without_output_read(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                patch.object(
                    self.verifier.item_runtime,
                    "_replay_diagnostic_log_cursors",
                    return_value={"logs/npi_core.log": 0},
                ),
                patch.object(
                    self.verifier.item_runtime,
                    "_sanitized_server_log_diagnostic",
                    return_value=None,
                ),
                patch.object(
                    self.verifier.subprocess,
                    "run",
                    return_value=types.SimpleNamespace(returncode=1),
                ),
                self.assertRaisesRegex(RuntimeError, "Bench fixture failed"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
            ):
                self.verifier.run_bench_fixture(
                    "prepare_projection",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                        "diagnostic_trace_id": trace_id,
                    },
                )
            with patch.object(
                self.verifier,
                "QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED",
                True,
            ):
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    (
                        "RuntimeError",
                        "P806_QUALITY_PREPARE_PARENT_CHILD_STATUS",
                        trace_id,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
