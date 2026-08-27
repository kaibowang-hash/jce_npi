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
        self.verifier.QUALITY_LINK_POST_TIMESTAMP_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            False
        )
        self.verifier.QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            False
        )
        self.verifier.QUALITY_LINK_POST_REPLAY_FINAL_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            False
        )

    def read_full_boundary_diagnostic(
        self,
        path: Path,
        *,
        expected_trace: str,
    ) -> tuple[str, str, str] | None:
        with (
            patch.object(
                self.verifier,
                "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                False,
            ),
            patch.object(
                self.verifier,
                "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                False,
            ),
            patch.object(
                self.verifier,
                "QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED",
                False,
            ),
            patch.object(
                self.verifier,
                "QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED",
                False,
            ),
            patch.object(
                self.verifier,
                "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                True,
            ),
        ):
            return self.verifier.read_quality_link_runtime_diagnostic(
                path,
                expected_trace=expected_trace,
            )

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

    def test_link_runtime_create_201_and_replay_200_are_exact(self) -> None:
        body = {"sealed": True}
        first = types.SimpleNamespace(
            status=201,
            headers={"Idempotency-Replayed": "false"},
            body=body,
        )
        replay = types.SimpleNamespace(
            status=200,
            headers={"Idempotency-Replayed": "true"},
            body=dict(body),
        )
        stale = types.SimpleNamespace(status=409, headers={}, body={})
        listed = types.SimpleNamespace(
            status=200,
            headers={},
            body={"permissions": {"view": True, "link": True}, "items": [{}]},
        )
        with (
            patch.object(
                self.verifier,
                "_create_response_request",
                return_value=first,
            ),
            patch.object(
                self.verifier.document_runtime,
                "npi_request",
                side_effect=[replay, stale, listed],
            ) as request,
            patch.object(
                self.verifier.item_runtime,
                "_replay_diagnostic_log_cursors",
            ) as cursors,
            patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
            ) as reader,
        ):
            result = self.verifier._exercise_link(
                actor=object(),
                actor_csrf="csrf",
                base_url="http://npi.localhost",
                current={"instanceVersion": 1, "snapshotHash": "a" * 64},
                item={
                    "currentTruth": {
                        "observationGlobalId": "observation",
                        "headGlobalId": "head",
                        "headOptimisticVersion": 1,
                        "headHash": "b" * 64,
                    }
                },
                project_id="project",
                readiness_id="readiness",
            )
        self.assertEqual(
            result,
            {
                "linked": True,
                "replayed": True,
                "staleRejected": True,
                "targetTraffic": 0,
                "cleaned": True,
            },
        )
        self.assertEqual(request.call_count, 3)
        cursors.assert_not_called()
        reader.assert_not_called()

    def test_link_runtime_replay_status_body_and_header_fail_closed(self) -> None:
        body = {"sealed": True}
        first = types.SimpleNamespace(
            status=201,
            headers={"Idempotency-Replayed": "false"},
            body=body,
        )
        cases = (
            types.SimpleNamespace(
                status=201,
                headers={"Idempotency-Replayed": "true"},
                body=dict(body),
            ),
            types.SimpleNamespace(
                status=200,
                headers={"Idempotency-Replayed": "true"},
                body={"sealed": False},
            ),
            types.SimpleNamespace(
                status=200,
                headers={"Idempotency-Replayed": "false"},
                body=dict(body),
            ),
        )
        for replay in cases:
            with (
                self.subTest(replay=replay),
                patch.object(
                    self.verifier,
                    "_create_response_request",
                    return_value=first,
                ),
                patch.object(
                    self.verifier.document_runtime,
                    "npi_request",
                    return_value=replay,
                ),
                self.assertRaises(RuntimeError),
            ):
                self.verifier._exercise_link(
                    actor=object(),
                    actor_csrf="csrf",
                    base_url="http://npi.localhost",
                    current={"instanceVersion": 1, "snapshotHash": "a" * 64},
                    item={
                        "currentTruth": {
                            "observationGlobalId": "observation",
                            "headGlobalId": "head",
                            "headOptimisticVersion": 1,
                            "headHash": "b" * 64,
                        }
                    },
                    project_id="project",
                    readiness_id="readiness",
                )

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
        self.verifier.QUALITY_LINK_POST_REPLAY_FINAL_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            True
        )
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
        self.assertFalse(
            self.verifier.QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_POST_TIMESTAMP_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
        )
        self.assertTrue(
            self.verifier.QUALITY_LINK_POST_REPLAY_FINAL_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED
        )
        activations = (
            self.verifier.QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_TIMESTAMP_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
            self.verifier.QUALITY_LINK_POST_REPLAY_FINAL_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
        )
        self.assertEqual(sum(activations), 1)
        self.assertEqual(self.verifier.QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES, expected)
        combined_codes = (
            frozenset(self.verifier.QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES)
            .union(self.verifier.QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES)
            .union(self.verifier.QUALITY_LINK_PREPARE_BOOTSTRAP_CODES)
            .union(self.verifier.QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES)
            .union(self.verifier.QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES)
        )
        self.assertEqual(
            self.verifier._active_quality_link_runtime_diagnostic_codes(),
            combined_codes,
        )
        self.assertEqual(len(combined_codes), 92)
        self.assertTrue(
            set(self.verifier.QUALITY_LINK_CREATE_RESPONSE_PARENT_CODES).isdisjoint(
                self.verifier._active_quality_link_runtime_diagnostic_codes()
            )
        )
        self.assertTrue(self.verifier._prepare_projection_diagnostics_enabled())
        source = (ROOT / "scripts/verify_quality_link_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False",
            source,
        )
        self.assertIn(
            "QUALITY_LINK_POST_TIMESTAMP_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False",
            source,
        )
        self.assertIn(
            "QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False",
            source,
        )
        self.assertIn(
            "QUALITY_LINK_POST_REPLAY_FINAL_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False",
            source,
        )
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
        self.assertTrue(set(expected).issubset(stages))
        self.assertTrue(all(stages.count(code) == 1 for code in expected))

    def test_create_response_parent_classes_are_closed_and_value_free(self) -> None:
        expected = {
            None: "P806_QUALITY_CREATE_STATUS_INVALID",
            0: "P806_QUALITY_CREATE_STATUS_INVALID",
            99: "P806_QUALITY_CREATE_STATUS_INVALID",
            100: "P806_QUALITY_CREATE_STATUS_INFORMATIONAL",
            200: "P806_QUALITY_CREATE_STATUS_SUCCESS_NON_201",
            201: None,
            299: "P806_QUALITY_CREATE_STATUS_SUCCESS_NON_201",
            300: "P806_QUALITY_CREATE_STATUS_REDIRECTION",
            400: "P806_QUALITY_CREATE_STATUS_CLIENT_ERROR",
            500: "P806_QUALITY_CREATE_STATUS_SERVER_ERROR",
            600: "P806_QUALITY_CREATE_STATUS_INVALID",
        }
        self.assertEqual(
            {value: self.verifier._create_response_parent_code(value) for value in expected},
            expected,
        )
        source = (ROOT / "scripts/verify_quality_link_runtime.py").read_text(
            encoding="utf-8"
        )
        create = source[
            source.index("def _create_response_request") : source.index("def _body")
        ]
        self.assertLess(
            create.index("parent_code = _create_response_parent_code"),
            create.index('getattr(result, "body", None)'),
        )

    def test_post_write_full_boundary_falls_back_to_outer_without_prepare(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED = True
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = self.verifier.quality_link_runtime_diagnostic_trace()
        headers = {
            "X-Request-ID": self.verifier.document_runtime.fixture_request_id(
                self.verifier.IDEMPOTENCY_KEY
            ),
            "Cache-Control": "private, no-store",
        }
        cases = (
            (None, {}),
            (100, {}),
            (200, {}),
            (300, {}),
            (400, {}),
            (500, {}),
            (201, []),
        )
        self.assertFalse(self.verifier._prepare_projection_diagnostics_enabled())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            for status, body in cases:
                path.unlink(missing_ok=True)
                result = types.SimpleNamespace(
                    status=status,
                    headers=headers,
                    body=body,
                )
                with (
                    self.subTest(status=status),
                    patch.dict(
                        os.environ,
                        {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                        clear=False,
                    ),
                    patch.object(
                        self.verifier.document_runtime,
                        "request",
                        return_value=result,
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
                    ) as reader,
                    self.assertRaises(RuntimeError),
                    self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                    self.verifier.quality_link_runtime_diagnostic_step(
                        "P806_QUALITY_CREATE_HTTP"
                    ),
                ):
                    self.verifier._create_response_request(
                        object(),
                        "http://npi.localhost",
                        "/api/npi/v1/projects/project/formal-quality-links:link-observed-reference",
                        actor_csrf="csrf",
                        payload={"opaque": True},
                    )
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("RuntimeError", "P806_QUALITY_CREATE_HTTP", trace_id),
                )
                if status == 201:
                    reader.assert_not_called()
                else:
                    reader.assert_called_once()

    def test_post_write_full_boundary_records_each_outer_with_exact_safe_shape(
        self,
    ) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED = True
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            for code in self.verifier.QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES:
                with (
                    self.subTest(code=code),
                    patch.dict(
                        os.environ,
                        {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                        clear=False,
                    ),
                    self.assertRaisesRegex(RuntimeError, "same-private-error"),
                    self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                    self.verifier.quality_link_runtime_diagnostic_step(code),
                ):
                    raise RuntimeError("same-private-error")
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("RuntimeError", code, trace_id),
                )
                payload = path.read_text(encoding="utf-8")
                self.assertNotIn("same-private-error", payload)
                self.assertEqual(
                    set(json.loads(payload)),
                    {"code", "exceptionType", "traceId"},
                )
                path.unlink()

    def test_post_write_full_boundary_prepare_failure_never_reads_child_output(
        self,
    ) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED = True
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"

        class UnreadOutput:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def seek(self, *_args):
                raise AssertionError("failed child stdout was read")

            def __iter__(self):
                raise AssertionError("failed child stdout was read")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                patch.object(
                    self.verifier.tempfile,
                    "TemporaryFile",
                    return_value=UnreadOutput(),
                ),
                patch.object(
                    self.verifier.subprocess,
                    "run",
                    return_value=types.SimpleNamespace(returncode=1),
                ) as child,
                patch.object(
                    self.verifier.item_runtime,
                    "_replay_diagnostic_log_cursors",
                ) as cursors,
                self.assertRaisesRegex(RuntimeError, "Bench fixture failed"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_PREPARE_PROJECTION"
                ),
            ):
                self.verifier.run_bench_fixture(
                    "prepare_projection",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                    },
                )
            self.assertEqual(
                self.verifier.read_quality_link_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                ("RuntimeError", "P806_QUALITY_PREPARE_PROJECTION", trace_id),
            )
            cursors.assert_not_called()
            self.assertIs(
                child.call_args.kwargs["stderr"],
                self.verifier.subprocess.DEVNULL,
            )

    def test_create_response_server_allowlist_matches_repository_source(self) -> None:
        repository_source = (
            ROOT
            / "apps/npi_integration/npi_integration/quality_link/frappe_repository.py"
        ).read_text(encoding="utf-8")
        api_source = (
            ROOT / "apps/npi_integration/npi_integration/quality_link_api.py"
        ).read_text(encoding="utf-8")
        assignment = next(
            node
            for node in ast.parse(repository_source).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_CODES"
                for target in node.targets
            )
        )
        repository_codes = {
            element.value
            for element in assignment.value.args[0].elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }
        self.assertEqual(
            repository_codes,
            self.verifier.QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES,
        )
        self.assertEqual(len(self.verifier.QUALITY_LINK_CREATE_RESPONSE_PARENT_CODES), 7)
        self.assertEqual(len(repository_codes), 27)
        stages = [
            node.args[0].value
            for node in ast.walk(ast.parse(api_source + "\n" + repository_source))
            if isinstance(node, ast.Call)
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "quality_link_create_response_step"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "quality_link_create_response_step"
                )
            )
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ]
        self.assertEqual(set(stages), repository_codes)
        self.assertTrue(all(stages.count(code) == 1 for code in repository_codes))

    def test_create_response_server_tuple_wins_parent_and_failed_body_is_unread(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED = True
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = self.verifier.quality_link_runtime_diagnostic_trace()
        server_code = "P806_QUALITY_CREATE_REPOSITORY_PROJECT"
        result = types.SimpleNamespace(
            status=500,
            headers={
                "X-Request-ID": self.verifier.document_runtime.fixture_request_id(
                    self.verifier.IDEMPOTENCY_KEY
                ),
                "Cache-Control": "private, no-store",
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                patch.object(
                    self.verifier.document_runtime,
                    "request",
                    return_value=result,
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
                self.assertRaisesRegex(RuntimeError, "HTTP class drifted"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
            ):
                self.verifier._create_response_request(
                    object(),
                    "http://npi.localhost",
                    "/api/npi/v1/projects/project/formal-quality-links:link-observed-reference",
                    actor_csrf="csrf",
                    payload={"opaque": True},
                )
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                    False,
                ),
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
                code_prefix="P806_QUALITY_CREATE_",
                allowed_codes=self.verifier.QUALITY_LINK_CREATE_RESPONSE_SERVER_CODES,
            )

    def test_parent_downstream_falls_back_to_outer_create_without_server_tuple(self) -> None:
        trace_id = self.verifier.quality_link_runtime_diagnostic_trace()
        result = types.SimpleNamespace(
            status=500,
            headers={
                "X-Request-ID": self.verifier.document_runtime.fixture_request_id(
                    self.verifier.IDEMPOTENCY_KEY
                ),
                "Cache-Control": "private, no-store",
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                patch.object(
                    self.verifier.document_runtime,
                    "request",
                    return_value=result,
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
                self.assertRaisesRegex(RuntimeError, "HTTP class drifted"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_CREATE_HTTP"
                ),
            ):
                self.verifier._create_response_request(
                    object(),
                    "http://npi.localhost",
                    "/api/npi/v1/projects/project/formal-quality-links:link-observed-reference",
                    actor_csrf="csrf",
                    payload={"opaque": True},
                )
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                    False,
                ),
            ):
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("RuntimeError", "P806_QUALITY_CREATE_HTTP", trace_id),
                )

    def test_parent_downstream_records_each_outer_stage_with_exact_safe_shape(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            for code in self.verifier.QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES:
                with (
                    self.subTest(code=code),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                        True,
                    ),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                        False,
                    ),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                        False,
                    ),
                    patch.dict(
                        os.environ,
                        {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                        clear=False,
                    ),
                    self.assertRaisesRegex(RuntimeError, "same-private-error"),
                    self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                    self.verifier.quality_link_runtime_diagnostic_step(code),
                ):
                    raise RuntimeError("same-private-error")
                with (
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                        True,
                    ),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                        False,
                    ),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                        False,
                    ),
                ):
                    self.assertEqual(
                        self.verifier.read_quality_link_runtime_diagnostic(
                            path,
                            expected_trace=trace_id,
                        ),
                        ("RuntimeError", code, trace_id),
                    )
                self.assertNotIn(
                    "same-private-error",
                    path.read_text(encoding="utf-8"),
                )
                path.unlink()

    def test_parent_downstream_prepare_failure_never_reads_child_output(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"

        class UnreadOutput:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def seek(self, *_args):
                raise AssertionError("failed child stdout was read")

            def __iter__(self):
                raise AssertionError("failed child stdout was read")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                patch.object(
                    self.verifier.tempfile,
                    "TemporaryFile",
                    return_value=UnreadOutput(),
                ),
                patch.object(
                    self.verifier.subprocess,
                    "run",
                    return_value=types.SimpleNamespace(returncode=1),
                ) as child,
                patch.object(
                    self.verifier.item_runtime,
                    "_replay_diagnostic_log_cursors",
                ) as cursors,
                self.assertRaisesRegex(RuntimeError, "Bench fixture failed"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_PREPARE_PROJECTION"
                ),
            ):
                self.verifier.run_bench_fixture(
                    "prepare_projection",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                    },
                )
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                    False,
                ),
            ):
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("RuntimeError", "P806_QUALITY_PREPARE_PROJECTION", trace_id),
                )
            cursors.assert_not_called()
            self.assertIs(
                child.call_args.kwargs["stderr"],
                self.verifier.subprocess.DEVNULL,
            )

    def test_create_response_success_preserves_shape_and_default_path(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED = True
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        headers = {
            "X-Request-ID": self.verifier.document_runtime.fixture_request_id(
                self.verifier.IDEMPOTENCY_KEY
            ),
            "Cache-Control": "private, no-store",
        }
        result = types.SimpleNamespace(status=201, headers=headers, body={"ok": True})
        trace_id = self.verifier.quality_link_runtime_diagnostic_trace()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                patch.object(
                    self.verifier.document_runtime,
                    "request",
                    return_value=result,
                ) as request,
                patch.object(
                    self.verifier.item_runtime,
                    "_replay_diagnostic_log_cursors",
                    return_value={"logs/npi_core.log": 0},
                ),
                patch.object(
                    self.verifier.item_runtime,
                    "_sanitized_server_log_diagnostic",
                ) as success_reader,
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_CREATE_HTTP"
                ),
            ):
                outcome = self.verifier._create_response_request(
                    object(),
                    "http://npi.localhost",
                    "/path",
                    actor_csrf="csrf",
                    payload={"opaque": True},
                )
            self.assertFalse(path.exists())
            success_reader.assert_not_called()
        self.assertEqual(outcome.body, {"ok": True})
        sent_headers = request.call_args.kwargs["request_headers"]
        self.assertEqual(
            sent_headers[self.verifier.QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_HEADER],
            self.verifier.QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_SCOPE,
        )
        self.assertEqual(
            sent_headers["X-Trace-ID"],
            self.verifier.quality_link_runtime_diagnostic_trace(),
        )
        self.assertEqual(
            set(sent_headers),
            {
                "Idempotency-Key",
                "X-Frappe-CSRF-Token",
                "X-Request-ID",
                "X-Trace-ID",
                self.verifier.QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTIC_HEADER,
            },
        )
        self.assertEqual(request.call_args.args[1:], ("http://npi.localhost", "/path"))
        self.assertEqual(request.call_args.kwargs["method"], "POST")
        self.assertEqual(request.call_args.kwargs["payload"], {"opaque": True})
        with (
            patch.object(
                self.verifier,
                "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                False,
            ),
            patch.object(
                self.verifier,
                "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                False,
            ),
            patch.object(
                self.verifier,
                "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                False,
            ),
            patch.object(
                self.verifier.document_runtime,
                "npi_request",
                return_value=result,
            ) as default_request,
            patch.object(
                self.verifier.item_runtime,
                "_replay_diagnostic_log_cursors",
            ) as cursors,
            patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
            ) as reader,
        ):
            self.verifier._create_response_request(
                object(),
                "http://npi.localhost",
                "/path",
                actor_csrf="csrf",
                payload={"opaque": True},
            )
        default_request.assert_called_once()
        cursors.assert_not_called()
        reader.assert_not_called()

    def test_all_diagnostics_off_keeps_trace_cursor_and_reader_dormant(self) -> None:
        verifier = importlib.reload(self.verifier)
        verifier.QUALITY_LINK_POST_REPLAY_FINAL_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            False
        )
        activations = (
            verifier.QUALITY_LINK_RUNTIME_STAGE_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_PREPARE_BOOTSTRAP_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_TIMESTAMP_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
            verifier.QUALITY_LINK_POST_REPLAY_FINAL_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED,
        )
        result = types.SimpleNamespace(status=201, headers={}, body={"ok": True})
        self.assertEqual(sum(activations), 0)
        self.assertFalse(verifier._prepare_projection_diagnostics_enabled())
        with (
            patch.object(
                verifier.document_runtime,
                "npi_request",
                return_value=result,
            ) as request,
            patch.object(verifier, "quality_link_runtime_diagnostic_trace") as trace,
            patch.object(
                verifier.item_runtime,
                "_replay_diagnostic_log_cursors",
            ) as cursors,
            patch.object(
                verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
            ) as reader,
        ):
            returned = verifier._create_response_request(
                object(),
                "http://npi.localhost",
                "/path",
                actor_csrf="csrf",
                payload={"opaque": True},
            )
        self.assertIs(returned, result)
        request.assert_called_once()
        trace.assert_not_called()
        cursors.assert_not_called()
        reader.assert_not_called()

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

    def test_combined_boundary_records_outer_parent_and_bootstrap_exactly(self) -> None:
        self.verifier.QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            True
        )
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        cases = tuple(
            (code, False)
            for code in self.verifier.QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES
        ) + tuple(
            (code, False)
            for code in self.verifier.QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES
        ) + tuple(
            (code, True)
            for code in self.verifier.QUALITY_LINK_PREPARE_BOOTSTRAP_CODES
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            for code, bootstrap in cases:
                path.unlink(missing_ok=True)
                step = (
                    self.verifier._prepare_bootstrap_diagnostic_step(
                        "prepare_projection",
                        code,
                    )
                    if bootstrap
                    else self.verifier.quality_link_runtime_diagnostic_step(code)
                )
                with (
                    self.subTest(code=code),
                    patch.dict(
                        os.environ,
                        {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                        clear=False,
                    ),
                    self.assertRaisesRegex(ValueError, "private-value"),
                    self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                    step,
                ):
                    raise ValueError("private-value")
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("ValueError", code, trace_id),
                )
                payload = path.read_text(encoding="utf-8")
                self.assertEqual(
                    set(json.loads(payload)),
                    {"code", "exceptionType", "traceId"},
                )
                self.assertNotIn("private-value", payload)

    def test_combined_boundary_bootstrap_inner_wins_parent_and_outer(self) -> None:
        self.verifier.QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            True
        )
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        code = "P806_QUALITY_PREPARE_BOOTSTRAP_INIT"
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
                    "P806_QUALITY_PREPARE_PROJECTION"
                ),
                self.verifier._prepare_parent_diagnostic_step(
                    "prepare_projection",
                    "P806_QUALITY_PREPARE_PARENT_CHILD_STATUS",
                ),
                self.verifier._prepare_bootstrap_diagnostic_step(
                    "prepare_projection",
                    code,
                ),
            ):
                raise ValueError("private-value")
            self.assertEqual(
                self.verifier.read_quality_link_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                ("ValueError", code, trace_id),
            )
            self.assertNotIn("private-value", path.read_text(encoding="utf-8"))

    def test_combined_boundary_server_wins_parent_fallback_is_unread(
        self,
    ) -> None:
        self.verifier.QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            True
        )
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        server_code = "P806_QUALITY_PROJECTION_SCOPE"

        class UnreadOutput:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def seek(self, *_args):
                raise AssertionError("failed child stdout was read")

            def __iter__(self):
                raise AssertionError("failed child stdout was read")

        with tempfile.TemporaryDirectory() as directory:
            for server_tuple, expected in (
                (
                    ("ValueError", server_code, trace_id),
                    ("ValueError", server_code, trace_id),
                ),
                (
                    None,
                    (
                        "RuntimeError",
                        "P806_QUALITY_PREPARE_PARENT_CHILD_STATUS",
                        trace_id,
                    ),
                ),
            ):
                path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
                path.unlink(missing_ok=True)
                with (
                    self.subTest(server_tuple=server_tuple),
                    patch.object(
                        self.verifier.tempfile,
                        "TemporaryFile",
                        return_value=UnreadOutput(),
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
                        return_value=server_tuple,
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
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    expected,
                )
                reader.assert_called_once_with(
                    trace_id,
                    {"logs/npi_core.log": 0},
                    code_prefix="P806_QUALITY_",
                    allowed_codes=self.verifier.QUALITY_LINK_PREPARE_PROJECTION_SERVER_CODES,
                )
                self.assertIs(
                    child.call_args.kwargs["stderr"],
                    self.verifier.subprocess.DEVNULL,
                )

    def test_combined_boundary_create_server_wins_outer_and_success_zero(self) -> None:
        self.verifier.QUALITY_LINK_POST_REPLAY_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = (
            True
        )
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        headers = {
            "X-Request-ID": self.verifier.document_runtime.fixture_request_id(
                self.verifier.IDEMPOTENCY_KEY
            ),
            "Cache-Control": "private, no-store",
        }
        server_code = "P806_QUALITY_CREATE_REPOSITORY_PROJECT"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            for server_tuple, expected in (
                (
                    ("ValueError", server_code, trace_id),
                    ("ValueError", server_code, trace_id),
                ),
                (
                    None,
                    ("RuntimeError", "P806_QUALITY_CREATE_HTTP", trace_id),
                ),
            ):
                path.unlink(missing_ok=True)
                result = types.SimpleNamespace(status=500, headers=headers, body={})
                with (
                    self.subTest(server_tuple=server_tuple),
                    patch.dict(
                        os.environ,
                        {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                        clear=False,
                    ),
                    patch.object(
                        self.verifier.document_runtime,
                        "request",
                        return_value=result,
                    ),
                    patch.object(
                        self.verifier.item_runtime,
                        "_replay_diagnostic_log_cursors",
                        return_value={"logs/npi_core.log": 0},
                    ),
                    patch.object(
                        self.verifier.item_runtime,
                        "_sanitized_server_log_diagnostic",
                        return_value=server_tuple,
                    ),
                    self.assertRaisesRegex(RuntimeError, "HTTP class drifted"),
                    self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                    self.verifier.quality_link_runtime_diagnostic_step(
                        "P806_QUALITY_CREATE_HTTP"
                    ),
                ):
                    self.verifier._create_response_request(
                        object(),
                        "http://npi.localhost",
                        "/path",
                        actor_csrf="csrf",
                        payload={"opaque": True},
                    )
                self.assertEqual(
                    self.verifier.read_quality_link_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    expected,
                )

            path.unlink(missing_ok=True)
            result = types.SimpleNamespace(
                status=201,
                headers=headers,
                body={"ok": True},
            )
            with (
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                patch.object(
                    self.verifier.document_runtime,
                    "request",
                    return_value=result,
                ) as request,
                patch.object(self.verifier.item_runtime, "_replay_diagnostic_log_cursors"),
                patch.object(
                    self.verifier.item_runtime,
                    "_sanitized_server_log_diagnostic",
                ) as reader,
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_CREATE_HTTP"
                ),
            ):
                value = self.verifier._create_response_request(
                    object(),
                    "http://npi.localhost",
                    "/path",
                    actor_csrf="csrf",
                    payload={"opaque": True},
                )
            self.assertEqual(value.status, 201)
            self.assertEqual(value.body, {"ok": True})
            request.assert_called_once()
            reader.assert_not_called()
            self.assertFalse(path.exists())

    def test_full_boundary_records_each_parent_with_exact_safe_shape(
        self,
    ) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            for code in self.verifier.QUALITY_LINK_PREPARE_PROJECTION_PARENT_CODES:
                with (
                    self.subTest(code=code),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                        False,
                    ),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                        False,
                    ),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                        True,
                    ),
                    patch.dict(
                        os.environ,
                        {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                        clear=False,
                    ),
                    self.assertRaisesRegex(RuntimeError, "same-private-error"),
                    self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                    self.verifier.quality_link_runtime_diagnostic_step(code),
                ):
                    raise RuntimeError("same-private-error")
                self.assertEqual(
                    self.read_full_boundary_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("RuntimeError", code, trace_id),
                )
                payload = path.read_text(encoding="utf-8")
                self.assertNotIn("same-private-error", payload)
                self.assertEqual(
                    set(json.loads(payload)),
                    {"code", "exceptionType", "traceId"},
                )
                path.unlink()

    def test_full_boundary_records_each_outer_with_exact_safe_shape(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            for code in self.verifier.QUALITY_LINK_RUNTIME_DIAGNOSTIC_CODES:
                with (
                    self.subTest(code=code),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                        False,
                    ),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                        False,
                    ),
                    patch.object(
                        self.verifier,
                        "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                        True,
                    ),
                    patch.dict(
                        os.environ,
                        {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                        clear=False,
                    ),
                    self.assertRaisesRegex(RuntimeError, "same-private-error"),
                    self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                    self.verifier.quality_link_runtime_diagnostic_step(code),
                ):
                    raise RuntimeError("same-private-error")
                self.assertEqual(
                    self.read_full_boundary_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("RuntimeError", code, trace_id),
                )
                payload = path.read_text(encoding="utf-8")
                self.assertNotIn("same-private-error", payload)
                self.assertEqual(
                    set(json.loads(payload)),
                    {"code", "exceptionType", "traceId"},
                )
                path.unlink()

    def test_full_boundary_bootstrap_inner_wins_outer(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        bootstrap_code = "P806_QUALITY_PREPARE_BOOTSTRAP_INIT"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                self.assertRaisesRegex(ValueError, "same-private-error"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_PREPARE_PROJECTION"
                ),
                self.verifier._prepare_bootstrap_diagnostic_step(
                    "prepare_projection",
                    bootstrap_code,
                ),
            ):
                raise ValueError("same-private-error")
            self.assertEqual(
                self.read_full_boundary_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                ("ValueError", bootstrap_code, trace_id),
            )
            self.assertNotIn(
                "same-private-error",
                path.read_text(encoding="utf-8"),
            )

    def test_full_boundary_cursor_gap_falls_back_to_outer(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
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
                    side_effect=RuntimeError("same-private-error"),
                ),
                self.assertRaisesRegex(RuntimeError, "same-private-error"),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_PREPARE_PROJECTION"
                ),
            ):
                self.verifier.run_bench_fixture(
                    "prepare_projection",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                        "diagnostic_trace_id": trace_id,
                    },
                )
            self.assertEqual(
                self.read_full_boundary_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                ("RuntimeError", "P806_QUALITY_PREPARE_PROJECTION", trace_id),
            )
            self.assertNotIn(
                "same-private-error",
                path.read_text(encoding="utf-8"),
            )

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
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_PERMISSION_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_RECEIPT_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_PARENT_DOWNSTREAM_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_PROJECTION_PERMISSION_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED",
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

    def test_full_boundary_success_has_zero_record_or_behavior_effect(
        self,
    ) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ),
                self.verifier.quality_link_runtime_diagnostic_scope(trace_id),
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_CURRENT_TRUTH"
                ),
            ):
                value = {"unchanged": True}
            self.assertEqual(value, {"unchanged": True})
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

    def test_full_boundary_prefers_one_strict_server_tuple(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        server_code = "P806_QUALITY_PROJECTION_SCOPE"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
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
            self.assertEqual(
                self.read_full_boundary_diagnostic(
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

    def test_full_boundary_falls_back_without_child_output_read(self) -> None:
        self.verifier.QUALITY_LINK_POST_WRITE_PREPARE_FULL_DIAGNOSTICS_ENABLED = False
        self.verifier.QUALITY_LINK_COMBINED_BOUNDARY_DIAGNOSTICS_ENABLED = False
        trace_id = "trace-0123456789abcdef0123456789abcdef"

        class UnreadOutput:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def seek(self, *_args):
                raise AssertionError("failed child stdout was read")

            def __iter__(self):
                raise AssertionError("failed child stdout was read")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p8-06-quality-link-runtime-diagnostic.json"
            with (
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_CREATE_RESPONSE_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_POST_WRITE_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    False,
                ),
                patch.object(
                    self.verifier,
                    "QUALITY_LINK_FULL_BOUNDARY_DIAGNOSTICS_ENABLED",
                    True,
                ),
                patch.object(
                    self.verifier.tempfile,
                    "TemporaryFile",
                    return_value=UnreadOutput(),
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
                self.verifier.quality_link_runtime_diagnostic_step(
                    "P806_QUALITY_PREPARE_PROJECTION"
                ),
            ):
                self.verifier.run_bench_fixture(
                    "prepare_projection",
                    {
                        "project_id": "10000000-0000-4000-8000-000000000002",
                        "readiness_id": "10000000-0000-4000-8000-000000000001",
                        "diagnostic_trace_id": trace_id,
                    },
                )
            self.assertEqual(
                self.read_full_boundary_diagnostic(
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
