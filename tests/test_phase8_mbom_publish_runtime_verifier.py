from __future__ import annotations

import ast
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_mbom_publish_runtime.py"
SHELL = ROOT / "scripts/verify-frappe-runtime.sh"
WORKFLOW = ROOT / ".github/workflows/ci.yml"
SERVER_DIAGNOSTICS = (
    ROOT
    / "apps/npi_integration/npi_integration/mbom_publish/diagnostics.py"
)


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    name = "verify_mbom_publish_runtime_contract"
    saved = sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("MBOM runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": "0123456789abcdef0123456789abcdef"},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
        if saved is not None:
            sys.modules[name] = saved
    return module


class Phase8MbomPublishRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_verifier()
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_path_is_project_first_and_has_no_operation_selector(self):
        project = "00000000-0000-0000-0000-000000000001"
        request = "00000000-0000-0000-0000-000000000002"
        self.assertEqual(
            self.module.mbom_publish_path(project),
            f"/api/npi/v1/projects/{project}/mbom-publish-requests",
        )
        self.assertEqual(
            self.module.mbom_publish_path(project, request),
            f"/api/npi/v1/projects/{project}/mbom-publish-requests/{request}",
        )

    def test_profile_assertion_requires_exact_disposable_synthetic_shape(self):
        available = {
            "executionProfile": {
                "profileId": "mbom-synthetic-disposable-v1",
                "profileVersion": 1,
                "targetMode": "synthetic",
                "environmentCode": "disposable-test",
            },
            "permissions": {"canView": True, "canExecute": True},
        }
        self.module.assert_profile(available, available=True)
        self.module.assert_profile(
            {
                "executionProfile": None,
                "permissions": {"canView": True, "canExecute": False},
            },
            available=False,
        )
        with self.assertRaises(RuntimeError):
            self.module.assert_profile(
                {**available, "executionProfile": {**available["executionProfile"], "targetMode": "sandbox"}},
                available=True,
            )

    def test_no_formal_target_walker_fails_on_nested_id_or_version(self):
        self.module._assert_no_formal_target(
            {"nodes": [{"formalBomId": None, "targetVersion": None}]}
        )
        for value in (
            {"formalBomId": "BOM-1"},
            {"nodes": [{"targetVersion": "2"}]},
        ):
            with self.assertRaises(RuntimeError):
                self.module._assert_no_formal_target(value)

    def _create_result(
        self,
        *,
        status=201,
        request=...,
        request_id="00000000-0000-0000-0000-000000000001",
        outbox_id="00000000-0000-0000-0000-000000000002",
        trace_id="trace-0123456789abcdef0123456789abcdef",
    ):
        body = {
            "request": {"state": "queued", "private": "business-secret"}
            if request is ...
            else request,
            "requestGlobalId": request_id,
            "outboxEventId": outbox_id,
            "unexpected": "response-body-secret",
        }
        return SimpleNamespace(
            status=status,
            body=body,
            trace_id=trace_id,
        )

    def test_create_response_predicates_remain_fixed_and_first_failure_ordered(self):
        cases = (
            (
                self._create_result(
                    status=599,
                    request={"state": "failed-secret"},
                    request_id="request-secret",
                    outbox_id="outbox-secret",
                ),
                "P804_CREATE_RESPONSE_STATUS",
            ),
            (self._create_result(request=[]), "P804_CREATE_RESPONSE_SHAPE"),
            (
                self._create_result(request={"state": "failed-secret"}),
                "P804_CREATE_REQUEST_STATE",
            ),
            (
                self._create_result(request_id="request-secret"),
                "P804_CREATE_REQUEST_IDENTITY",
            ),
            (
                self._create_result(outbox_id="outbox-secret"),
                "P804_CREATE_OUTBOX_IDENTITY",
            ),
        )
        for result, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                self.assertEqual(
                    self.module._created_synthetic_batch_failure(result),
                    expected_code,
                )

    def test_create_server_tuple_is_the_only_diagnostic_output_and_does_not_leak(self):
        result = self._create_result(
            status=599,
            request={"state": "failed-secret"},
            request_id="request-secret",
            outbox_id="outbox-secret",
        )
        diagnostic = (
            "RuntimeError",
            "P804_CREATE_REQUEST_INSERT",
            "trace-0123456789abcdef0123456789abcdef",
        )
        with patch.object(
            self.module.item_runtime,
            "_sanitized_server_log_diagnostic",
            return_value=diagnostic,
        ) as reader:
            with self.assertRaisesRegex(
                RuntimeError,
                r"diagnostic_code=P804_CREATE_REQUEST_INSERT; "
                r"exception_type=RuntimeError; "
                r"trace_id=trace-0123456789abcdef0123456789abcdef",
            ) as raised:
                self.module.require_created_synthetic_batch(
                    result,
                    {"logs/npi_core.log": 0},
                )
        reader.assert_called_once_with(
            "trace-0123456789abcdef0123456789abcdef",
            {"logs/npi_core.log": 0},
            code_prefix="P804_CREATE_",
            allowed_codes=self.module._CREATE_SERVER_DIAGNOSTIC_CODES,
        )
        message = str(raised.exception)
        for forbidden in (
            "599",
            "business-secret",
            "response-body-secret",
            "failed-secret",
            "request-secret",
            "outbox-secret",
            "Traceback",
        ):
            self.assertNotIn(forbidden, message)

    def test_create_diagnostic_falls_back_to_constant_when_off_or_trace_is_untrusted(self):
        original = "P8-04 Synthetic command did not create one queued batch"
        for trace_id in (None, "trace-short", "trace-0123456789abcdef0123456789abcdeg"):
            with self.subTest(trace_id=trace_id):
                with self.assertRaises(RuntimeError) as raised:
                    self.module.require_created_synthetic_batch(
                        self._create_result(status=503, trace_id=trace_id)
                    )
                self.assertEqual(str(raised.exception), original)
        with patch.object(
            self.module.item_runtime,
            "_sanitized_server_log_diagnostic",
            return_value=None,
        ):
            with self.assertRaises(RuntimeError) as raised:
                self.module.require_created_synthetic_batch(
                    self._create_result(status=503),
                    {"logs/npi_core.log": 0},
                )
        self.assertEqual(str(raised.exception), original)
        with patch.object(self.module, "MBOM_CREATE_DIAGNOSTICS_ENABLED", False):
            with self.assertRaises(RuntimeError) as raised:
                self.module.require_created_synthetic_batch(
                    self._create_result(status=503)
                )
        self.assertEqual(str(raised.exception), original)

    def test_create_diagnostic_success_is_silent(self):
        self.assertIsNone(
            self.module.require_created_synthetic_batch(self._create_result())
        )

    def test_create_diagnostic_uses_shared_http_result_trace_only(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "require_created_synthetic_batch"
        )
        segment = ast.get_source_segment(self.source, function) or ""
        self.assertIn('getattr(result, "trace_id", None)', segment)
        self.assertNotIn("X-Trace-ID", segment)
        self.assertNotIn("headers", segment)
        self.assertNotIn("problem", segment.casefold())
        self.assertNotIn("json", segment.casefold())
        self.assertIn("_sanitized_server_log_diagnostic", segment)

    def test_create_scope_header_is_only_available_to_exact_synthetic_post(self):
        response = SimpleNamespace(
            status=201,
            body={},
            headers={
                "X-Request-ID": "request-id",
                "Cache-Control": "private, no-store",
            },
            trace_id="trace-0123456789abcdef0123456789abcdef",
        )
        captured = {}

        def request(*_args, **kwargs):
            captured.update(kwargs)
            return response

        path = self.module.mbom_publish_path(
            "00000000-0000-0000-0000-000000000001"
        )
        with patch.object(
            self.module.document_runtime,
            "command_headers",
            return_value={"X-Request-ID": "request-id"},
        ), patch.object(self.module.document_runtime, "request", side_effect=request):
            self.module.mbom_publish_request(
                object(),
                "http://127.0.0.1",
                path,
                method="POST",
                payload={"fixed": True},
                csrf_token="csrf",
                idempotency_key=(
                    f"p8-04-synthetic-{self.module.FIXTURE_RUN_ID}"
                ),
                create_diagnostic=True,
            )
        self.assertEqual(
            captured["request_headers"][self.module._CREATE_DIAGNOSTIC_HEADER],
            self.module._CREATE_DIAGNOSTIC_SCOPE,
        )
        for mutation in (
            {"method": "GET"},
            {"path": f"{path}/detail"},
            {"idempotency_key": "wrong"},
        ):
            values = {
                "method": "POST",
                "path": path,
                "idempotency_key": f"p8-04-synthetic-{self.module.FIXTURE_RUN_ID}",
                **mutation,
            }
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                self.module.mbom_publish_request(
                    object(),
                    "http://127.0.0.1",
                    values["path"],
                    method=values["method"],
                    payload={"fixed": True},
                    csrf_token="csrf",
                    idempotency_key=values["idempotency_key"],
                    create_diagnostic=True,
                )

    def test_fresh_runtime_captures_log_cursors_before_one_scoped_post(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_fresh"
        )
        segment = ast.get_source_segment(self.source, function) or ""
        cursor = segment.index("_replay_diagnostic_log_cursors()")
        post = segment.index("created = mbom_publish_request(")
        self.assertLess(cursor, post)
        self.assertEqual(
            segment.count("create_diagnostic=MBOM_CREATE_DIAGNOSTICS_ENABLED"),
            1,
        )
        self.assertEqual(segment.count("_replay_diagnostic_log_cursors()"), 1)

    def test_parent_and_server_create_allowlists_are_exactly_equal(self):
        tree = ast.parse(SERVER_DIAGNOSTICS.read_text(encoding="utf-8"))
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "MBOM_CREATE_SERVER_DIAGNOSTIC_CODES"
                for target in node.targets
            )
        )
        self.assertIsInstance(assignment.value, ast.Call)
        values = {
            node.value
            for node in ast.walk(assignment.value)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith("P804_CREATE_")
        }
        self.assertEqual(values, self.module._CREATE_SERVER_DIAGNOSTIC_CODES)
        self.assertNotIn("P804_CREATE_ENQUEUE", values)

    def test_bench_child_hides_stderr_and_drops_password_environment(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_bench_fixture"
        )
        segment = ast.get_source_segment(self.source, function) or ""
        self.assertIn("stderr=subprocess.DEVNULL", segment)
        self.assertIn("tempfile.TemporaryFile", segment)
        for secret in (
            "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
            "NPI_RUNTIME_FIXTURE_PASSWORD",
            "NPI_ADMINISTRATOR_PASSWORD",
            "NPI_DATABASE_ROOT_PASSWORD",
        ):
            self.assertIn(secret, segment)

    def test_fixture_allowlist_has_only_input_capture_and_worker_exercise(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "run_local_bench_fixture"
        )
        literals = {
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertIn("capture_inputs", literals)
        self.assertIn("exercise_worker", literals)
        self.assertNotIn("retry", literals)
        self.assertNotIn("reconcile", literals)

    def test_worker_fixture_proves_terminal_replay_and_zero_mapping_head(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "exercise_worker"
        )
        segment = ast.get_source_segment(self.source, function) or ""
        self.assertEqual(segment.count("process_outbox_message(outbox_id)"), 2)
        self.assertIn('"NPI MBOM Mapping Head"', segment)
        self.assertIn('"not_claimed"', segment)
        self.assertIn('"synthetic_verified"', segment)

    def test_verifier_has_no_target_network_or_production_identity(self):
        for forbidden in (
            "erpnext.sandbox",
            "erpnext.production",
            "requests.",
            "httpx.",
            "formal_bom_id =",
            "submit_bom",
        ):
            self.assertNotIn(forbidden, self.source.casefold())

    def test_shell_runs_disabled_then_exact_marker_fresh_and_cleans_environment(self):
        shell = SHELL.read_text(encoding="utf-8")
        for marker in (
            "run_mbom_publish_runtime_verifier disabled",
            "run_mbom_publish_runtime_verifier fresh",
            "NPI_P8_04_RUNTIME_MARKER=npi-one-mbom-publish-disposable-v1",
            "clear_mbom_publish_runtime_environment",
            "mbom_publish_runtime_environment_active=true",
        ):
            self.assertIn(marker, shell)

    def test_workflow_governs_p8_04_visual_and_current_runtime_scope(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        visual_spec = "tests/e2e/p8-04-mbom-publish-live.spec.ts"
        self.assertEqual(workflow.count(visual_spec), 2)
        self.assertIn(
            "frontend/tests/e2e/p8-04-mbom-publish-live.spec.ts-snapshots/p8-04-*-linux.png",
            workflow,
        )
        self.assertIn(
            "P5 controlled runtime through P8-04 MBOM command and Outbox worker",
            workflow,
        )
        self.assertIn(
            "Verify cumulative P5 through P8-04 MBOM integration runtime",
            workflow,
        )
        self.assertIn("printf 'scope=p5-01-through-p8-04\\n'", workflow)
        self.assertIn(
            "printf 'predecessor_scope=p5-01-through-p8-03\\n'", workflow
        )
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --projection-only", workflow
        )
        self.assertIn("p8-integration-runtime-${{ github.run_id }}", workflow)


if __name__ == "__main__":
    unittest.main()
