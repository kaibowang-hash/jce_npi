from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
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
_TRACE_ID = "trace-0123456789abcdef0123456789abcdef"


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
            self.module,
            "MBOM_CREATE_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(
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

    def test_create_diagnostics_are_closed_by_default_without_header_or_log_read(self):
        self.assertFalse(self.module.MBOM_CREATE_DIAGNOSTICS_ENABLED)
        self.assertFalse(self.module.item_runtime.ITEM_CREATE_DIAGNOSTICS_ENABLED)
        self.assertFalse(
            self.module.item_runtime.REPLAY_TERMINAL_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.module.item_runtime.LEGACY_COLLECTION_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.module.item_runtime.LEGACY_QUERY_SERVER_DIAGNOSTICS_ENABLED
        )
        captured = {}

        def request(*_args, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                status=201,
                body={},
                headers={
                    "X-Request-ID": "request-id",
                    "Cache-Control": "private, no-store",
                },
                trace_id="trace-0123456789abcdef0123456789abcdef",
            )

        with patch.object(
            self.module.document_runtime,
            "command_headers",
            return_value={"X-Request-ID": "request-id"},
        ), patch.object(
            self.module.document_runtime,
            "request",
            side_effect=request,
        ):
            self.module.mbom_publish_request(
                object(),
                "http://127.0.0.1",
                self.module.mbom_publish_path(
                    "00000000-0000-0000-0000-000000000001"
                ),
                method="POST",
                payload={"fixed": True},
                csrf_token="csrf",
                idempotency_key=f"p8-04-synthetic-{self.module.FIXTURE_RUN_ID}",
                create_diagnostic=self.module.MBOM_CREATE_DIAGNOSTICS_ENABLED,
            )
        self.assertNotIn(
            self.module._CREATE_DIAGNOSTIC_HEADER,
            captured["request_headers"],
        )

        with patch.object(
            self.module.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader, self.assertRaises(RuntimeError):
            self.module.require_created_synthetic_batch(
                self._create_result(status=503),
                {"logs/npi_core.log": 0},
            )
        reader.assert_not_called()

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

    def test_fresh_runtime_keeps_diagnostic_hooks_guarded_and_closed(self):
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
        self.assertGreaterEqual(
            segment.count("if MBOM_CREATE_DIAGNOSTICS_ENABLED"),
            1,
        )

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

    def test_worker_downstream_checkpoint_has_one_context_per_allowlisted_stage(self):
        module = self.module
        self.assertFalse(module.MBOM_WORKER_DOWNSTREAM_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.MBOM_POST_DATETIME_WORKER_DIAGNOSTICS_ENABLED)
        self.assertTrue(module.MBOM_POST_MANIFEST_WORKER_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.MBOM_CREATE_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.item_runtime.ITEM_CREATE_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.item_runtime.REPLAY_TERMINAL_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.item_runtime.LEGACY_COLLECTION_DIAGNOSTICS_ENABLED)
        self.assertFalse(module.item_runtime.LEGACY_QUERY_SERVER_DIAGNOSTICS_ENABLED)
        fixed_stages = {
                "P804_WORKER_FIXTURE_VALIDATE",
                "P804_WORKER_REQUESTER_SESSION",
                "P804_WORKER_PROCESS_OUTBOX",
                "P804_WORKER_SESSION_RESTORE",
                "P804_WORKER_REQUEST_READ",
                "P804_WORKER_NODE_RESULTS_READ",
                "P804_WORKER_REQUEST_STATE",
                "P804_WORKER_NODE_CARDINALITY",
                "P804_WORKER_NODE_TRUTH",
                "P804_WORKER_TERMINAL_REPLAY",
                "P804_WORKER_REPLAY_SESSION_RESTORE",
                "P804_WORKER_TERMINAL_OUTCOME",
                "P804_WORKER_RECOVERABLE_QUERY",
                "P804_WORKER_RECOVERABLE_SET",
                "P804_WORKER_ADAPTER_COUNT",
                "P804_WORKER_MAPPING_COUNT",
                "P804_WORKER_FIXTURE_COMMIT",
        }
        outcome_codes = {
            "P804_WORKER_OUTCOME_NOT_CLAIMED",
            "P804_WORKER_OUTCOME_VALIDATED_MOCK",
            "P804_WORKER_OUTCOME_QUEUED",
            "P804_WORKER_OUTCOME_PROCESSING",
            "P804_WORKER_OUTCOME_PARTIALLY_SUCCEEDED",
            "P804_WORKER_OUTCOME_SUCCEEDED",
            "P804_WORKER_OUTCOME_FAILED_RETRYABLE",
            "P804_WORKER_OUTCOME_FAILED_FINAL",
            "P804_WORKER_OUTCOME_UNCERTAIN_AFTER_TIMEOUT",
            "P804_WORKER_OUTCOME_MAPPING_CONFLICT",
            "P804_WORKER_OUTCOME_NOT_MAPPING",
            "P804_WORKER_OUTCOME_STATE_MISSING",
            "P804_WORKER_OUTCOME_STATE_TYPE",
            "P804_WORKER_OUTCOME_STATE_UNKNOWN",
        }
        self.assertEqual(
            module._WORKER_DOWNSTREAM_DIAGNOSTIC_CODES,
            fixed_stages | outcome_codes,
        )
        not_claimed_stages = {
            "P804_NOT_CLAIMED_OUTBOX_READ",
            "P804_NOT_CLAIMED_OUTBOX_CONTRACT",
            "P804_NOT_CLAIMED_REQUEST_LINK",
            "P804_NOT_CLAIMED_REQUEST_READ",
            "P804_NOT_CLAIMED_REQUEST_REBUILD",
            "P804_NOT_CLAIMED_OUTBOX_BINDING",
            "P804_NOT_CLAIMED_PROFILE_ACTOR",
            "P804_NOT_CLAIMED_ACTOR_VALIDATE",
            "P804_NOT_CLAIMED_ROUTE_READ",
            "P804_NOT_CLAIMED_SERVICE_SCOPE",
            "P804_NOT_CLAIMED_OUTBOX_PENDING",
            "P804_NOT_CLAIMED_REQUEST_QUEUED",
            "P804_NOT_CLAIMED_GUARD_READ",
            "P804_NOT_CLAIMED_GUARD_ACTIVE",
        }
        self.assertEqual(
            module._WORKER_NOT_CLAIMED_PRECONDITION_CODES,
            not_claimed_stages,
        )
        closed_request_stages = {
            "P804_NOT_CLAIMED_OUTBOX_READ",
            "P804_NOT_CLAIMED_OUTBOX_CONTRACT",
            "P804_NOT_CLAIMED_REQUEST_LINK",
            "P804_NOT_CLAIMED_REQUEST_READ",
            "P804_NOT_CLAIMED_REQUEST_REBUILD",
        }
        post_datetime_stages = not_claimed_stages - closed_request_stages
        self.assertEqual(
            module._WORKER_POST_DATETIME_PRECONDITION_CODES,
            post_datetime_stages,
        )
        self.assertEqual(
            module._WORKER_POST_DATETIME_DIAGNOSTIC_CODES,
            fixed_stages | outcome_codes | post_datetime_stages,
        )
        closed_post_manifest_stages = {
            "P804_WORKER_FIXTURE_VALIDATE",
            "P804_WORKER_REQUESTER_SESSION",
        }
        post_manifest_stages = (
            fixed_stages | outcome_codes
        ) - closed_post_manifest_stages
        self.assertEqual(
            module._WORKER_POST_MANIFEST_CLOSED_CODES,
            closed_post_manifest_stages,
        )
        self.assertEqual(
            module._WORKER_POST_MANIFEST_DIAGNOSTIC_CODES,
            post_manifest_stages,
        )
        self.assertEqual(len(post_manifest_stages), 29)
        self.assertEqual(
            module._active_worker_diagnostic_codes(),
            post_manifest_stages,
        )
        with patch.object(
            module,
            "MBOM_POST_DATETIME_WORKER_DIAGNOSTICS_ENABLED",
            True,
        ):
            self.assertEqual(
                module._active_worker_diagnostic_codes(),
                fixed_stages | outcome_codes | post_datetime_stages,
            )
        exercise = self.source.split("def exercise_worker(", 1)[1].split(
            "\ndef ", 1
        )[0]
        local_runner = self.source.split("def run_local_bench_fixture(", 1)[1].split(
            "\ndef ", 1
        )[0]
        for code in fixed_stages:
            context = local_runner if code == "P804_WORKER_FIXTURE_COMMIT" else exercise
            with self.subTest(code=code):
                self.assertEqual(context.count(f'"{code}"'), 1)
                self.assertEqual(
                    self.source.count(f'"{code}"'),
                    3 if code in closed_post_manifest_stages else 2,
                )
        for code in outcome_codes:
            with self.subTest(code=code):
                self.assertEqual(self.source.count(f'"{code}"'), 1)
        preconditions = self.source.split(
            "def _verify_not_claimed_preconditions(", 1
        )[1].split("\ndef ", 1)[0]
        for code in not_claimed_stages:
            with self.subTest(code=code):
                self.assertEqual(preconditions.count(f'"{code}"'), 1)
                self.assertEqual(
                    self.source.count(f'"{code}"'),
                    3 if code in post_datetime_stages else 2,
                )
        with patch.object(
            module,
            "MBOM_POST_DATETIME_WORKER_DIAGNOSTICS_ENABLED",
            True,
        ):
            self.assertEqual(
                module._active_worker_diagnostic_codes()
                - module._WORKER_DOWNSTREAM_DIAGNOSTIC_CODES,
                post_datetime_stages,
            )
        self.assertNotIn("P804_WORKER_RESULT_OUTCOME", self.source)

    def test_worker_outcome_diagnostic_classifies_every_fixed_state_and_shape(self):
        module = self.module
        expected = {
            "not_claimed": "P804_WORKER_OUTCOME_NOT_CLAIMED",
            "validated_mock": "P804_WORKER_OUTCOME_VALIDATED_MOCK",
            "queued": "P804_WORKER_OUTCOME_QUEUED",
            "processing": "P804_WORKER_OUTCOME_PROCESSING",
            "partially_succeeded": "P804_WORKER_OUTCOME_PARTIALLY_SUCCEEDED",
            "succeeded": "P804_WORKER_OUTCOME_SUCCEEDED",
            "failed_retryable": "P804_WORKER_OUTCOME_FAILED_RETRYABLE",
            "failed_final": "P804_WORKER_OUTCOME_FAILED_FINAL",
            "uncertain_after_timeout": "P804_WORKER_OUTCOME_UNCERTAIN_AFTER_TIMEOUT",
            "mapping_conflict": "P804_WORKER_OUTCOME_MAPPING_CONFLICT",
        }
        self.assertEqual(module._WORKER_OUTCOME_DIAGNOSTIC_CODE_BY_STATE, expected)
        for state, code in expected.items():
            with self.subTest(state=state):
                self.assertEqual(
                    module._worker_outcome_diagnostic_code(
                        {"state": state, "privateId": "private-business-value"}
                    ),
                    code,
                )
        self.assertIsNone(
            module._worker_outcome_diagnostic_code(
                {"state": "synthetic_verified", "privateId": "private-business-value"}
            )
        )
        for result, code in (
            ([], "P804_WORKER_OUTCOME_NOT_MAPPING"),
            ({"privateId": "private-business-value"}, "P804_WORKER_OUTCOME_STATE_MISSING"),
            ({"state": 1}, "P804_WORKER_OUTCOME_STATE_TYPE"),
            ({"state": "private-business-value"}, "P804_WORKER_OUTCOME_STATE_UNKNOWN"),
        ):
            with self.subTest(code=code):
                diagnostic = module._worker_outcome_diagnostic_code(result)
                self.assertEqual(diagnostic, code)
                self.assertNotIn("private-business-value", diagnostic)

    def test_worker_outcome_is_first_checked_before_retained_truth_and_replay(self):
        exercise = self.source.split("def exercise_worker(", 1)[1].split(
            "\ndef ", 1
        )[0]
        outcome = exercise.index("_worker_outcome_diagnostic_code(result)")
        request_state = exercise.index('"P804_WORKER_REQUEST_STATE"')
        replay = exercise.index('"P804_WORKER_TERMINAL_REPLAY"')
        self.assertLess(outcome, request_state)
        self.assertLess(outcome, replay)
        self.assertEqual(exercise.count("_worker_outcome_diagnostic_code(result)"), 1)
        self.assertEqual(exercise.count("raise RuntimeError(\"P8-04 Synthetic worker outcome drifted\")"), 1)

    def test_not_claimed_preconditions_are_read_only_and_precede_one_worker_call(self):
        helper = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_verify_not_claimed_preconditions"
        )
        segment = ast.get_source_segment(self.source, helper) or ""
        for forbidden in (
            ".insert(",
            ".save(",
            ".commit(",
            "enqueue(",
            "adapter(",
            "requests.",
            "httpx.",
        ):
            self.assertNotIn(forbidden, segment)
        exercise = self.source.split("def exercise_worker(", 1)[1].split(
            "\ndef ", 1
        )[0]
        precheck = exercise.index("_verify_not_claimed_preconditions(")
        process = exercise.index("process_outbox_message(outbox_id)")
        self.assertLess(precheck, process)
        self.assertEqual(exercise.count("process_outbox_message(outbox_id)"), 2)
        self.assertEqual(exercise[:process].count("process_outbox_message(outbox_id)"), 0)

    def test_not_claimed_preconditions_record_exact_first_failure_and_restore_scope(self):
        module = self.module
        request_id = "00000000-0000-0000-0000-000000000002"
        outbox_id = "00000000-0000-0000-0000-000000000003"
        actor = "worker@example.invalid"
        requester = module.ACTOR_USER
        stages = tuple(sorted(module._WORKER_NOT_CLAIMED_PRECONDITION_CODES))

        def execute(failure: str | None):
            records: list[dict[str, object]] = []
            calls: list[str] = []
            original = RuntimeError("private actor id hash /tmp/private")
            outbox = SimpleNamespace(
                mbom_request_global_id=(
                    "00000000-0000-0000-0000-000000000099"
                    if failure == "P804_NOT_CLAIMED_REQUEST_LINK"
                    else request_id
                ),
                state=(
                    "processing"
                    if failure == "P804_NOT_CLAIMED_OUTBOX_PENDING"
                    else "pending"
                ),
            )
            value = SimpleNamespace(
                service_actor_user_id=(
                    None if failure == "P804_NOT_CLAIMED_PROFILE_ACTOR" else actor
                ),
                profile=SimpleNamespace(target_mode=SimpleNamespace(value="synthetic")),
                state=SimpleNamespace(
                    value=(
                        "processing"
                        if failure == "P804_NOT_CLAIMED_REQUEST_QUEUED"
                        else "queued"
                    )
                ),
            )
            route = SimpleNamespace(service_actor_user_id=actor)
            guard = object()
            frappe = types.ModuleType("frappe")
            frappe.session = SimpleNamespace(user=requester)

            def get_doc(doctype, _name):
                calls.append(f"read:{doctype}")
                if (
                    failure == "P804_NOT_CLAIMED_OUTBOX_READ"
                    and doctype == "NPI Outbox Message"
                ):
                    raise original
                if (
                    failure == "P804_NOT_CLAIMED_REQUEST_READ"
                    and doctype == "NPI MBOM Publish Request"
                ):
                    raise original
                return outbox if doctype == "NPI Outbox Message" else SimpleNamespace()

            frappe.get_doc = get_doc
            core = types.ModuleType("npi_core")
            core.__path__ = []
            api = types.ModuleType("npi_core.api")
            api.record_safe_diagnostic = lambda **values: records.append(values)
            integration = types.ModuleType("npi_integration")
            integration.__path__ = []
            package = types.ModuleType("npi_integration.mbom_publish")
            package.__path__ = []
            repository_module = types.ModuleType(
                "npi_integration.mbom_publish.frappe_repository"
            )
            validation_module = types.ModuleType(
                "npi_integration.mbom_publish.frappe_validation"
            )
            worker_repository_module = types.ModuleType(
                "npi_integration.mbom_publish.worker_repository"
            )

            def fail_or_call(stage: str, value_to_return=None):
                calls.append(stage)
                if failure == stage:
                    raise original
                return value_to_return

            repository_module._request_value = lambda *_args: fail_or_call(
                "P804_NOT_CLAIMED_REQUEST_REBUILD", value
            )
            validation_module.validate_mbom_service_actor = lambda _actor: fail_or_call(
                "P804_NOT_CLAIMED_ACTOR_VALIDATE"
            )

            @contextmanager
            def service_scope(_actor):
                calls.append("P804_NOT_CLAIMED_SERVICE_SCOPE")
                if failure == "P804_NOT_CLAIMED_SERVICE_SCOPE":
                    raise original
                previous = frappe.session.user
                frappe.session.user = actor
                try:
                    yield
                finally:
                    frappe.session.user = previous

            validation_module.mbom_service_actor_scope = service_scope
            worker_repository_module._is_mbom_outbox = lambda _row: (
                failure != "P804_NOT_CLAIMED_OUTBOX_CONTRACT"
            )
            worker_repository_module._project_for = lambda _row: object()
            worker_repository_module._require_outbox_binding = lambda *_args: fail_or_call(
                "P804_NOT_CLAIMED_OUTBOX_BINDING"
            )
            worker_repository_module._locked_guard = lambda _route: fail_or_call(
                "P804_NOT_CLAIMED_GUARD_READ", guard
            )
            worker_repository_module._require_active_guard = lambda *_args: fail_or_call(
                "P804_NOT_CLAIMED_GUARD_ACTIVE"
            )
            repository = SimpleNamespace(
                execution_route=lambda _event_id: fail_or_call(
                    "P804_NOT_CLAIMED_ROUTE_READ",
                    None
                    if failure == "P804_NOT_CLAIMED_ROUTE_READ"
                    else route,
                )
            )
            modules = {
                "frappe": frappe,
                "npi_core": core,
                "npi_core.api": api,
                "npi_integration": integration,
                "npi_integration.mbom_publish": package,
                "npi_integration.mbom_publish.frappe_repository": repository_module,
                "npi_integration.mbom_publish.frappe_validation": validation_module,
                "npi_integration.mbom_publish.worker_repository": worker_repository_module,
            }
            with patch.dict(sys.modules, modules), patch.object(
                module,
                "MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED",
                True,
            ):
                if failure is None:
                    module._verify_not_claimed_preconditions(
                        repository,
                        outbox_id=outbox_id,
                        request_id=request_id,
                        diagnostic_trace_id=_TRACE_ID,
                    )
                    raised = None
                else:
                    with self.assertRaises(RuntimeError) as caught:
                        module._verify_not_claimed_preconditions(
                            repository,
                            outbox_id=outbox_id,
                            request_id=request_id,
                            diagnostic_trace_id=_TRACE_ID,
                        )
                    raised = caught.exception
            return records, calls, raised, original, frappe.session.user

        records, calls, raised, _original, restored = execute(None)
        self.assertEqual(records, [])
        self.assertIsNone(raised)
        self.assertEqual(restored, requester)
        self.assertEqual(calls.count("P804_NOT_CLAIMED_SERVICE_SCOPE"), 1)
        for stage in stages:
            with self.subTest(stage=stage):
                records, _calls, raised, original, restored = execute(stage)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["code"], stage)
                self.assertEqual(records[0]["exception_type"], "RuntimeError")
                self.assertEqual(records[0]["trace_id"], _TRACE_ID)
                self.assertNotIn("private", str(records))
                self.assertEqual(restored, requester)
                if stage in {
                    "P804_NOT_CLAIMED_OUTBOX_READ",
                    "P804_NOT_CLAIMED_REQUEST_READ",
                    "P804_NOT_CLAIMED_REQUEST_REBUILD",
                    "P804_NOT_CLAIMED_OUTBOX_BINDING",
                    "P804_NOT_CLAIMED_ACTOR_VALIDATE",
                    "P804_NOT_CLAIMED_ROUTE_READ",
                    "P804_NOT_CLAIMED_SERVICE_SCOPE",
                    "P804_NOT_CLAIMED_GUARD_READ",
                    "P804_NOT_CLAIMED_GUARD_ACTIVE",
                }:
                    self.assertIs(raised, original)

    def test_worker_downstream_step_records_only_closed_tuple_and_reraises(self):
        records: list[dict[str, object]] = []
        package = types.ModuleType("npi_core")
        package.__path__ = []
        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **values: records.append(values)
        original = RuntimeError("private actor payload hash /tmp/private")
        with patch.dict(
            sys.modules,
            {"npi_core": package, "npi_core.api": api},
        ), patch.object(
            self.module,
            "MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED",
            True,
        ), self.assertRaises(RuntimeError) as raised:
            with self.module.worker_downstream_diagnostic_step(
                "P804_NOT_CLAIMED_OUTBOX_READ", _TRACE_ID
            ):
                raise original
        self.assertIs(raised.exception, original)
        self.assertEqual(
            records,
            [
                {
                    "code": "P804_NOT_CLAIMED_OUTBOX_READ",
                    "title": "NPI MBOM publish worker verifier stage failed",
                    "exception_type": "RuntimeError",
                    "trace_id": _TRACE_ID,
                }
            ],
        )
        for forbidden in ("private actor", "payload", "/tmp/private"):
            self.assertNotIn(forbidden, str(records))

        for code in sorted(self.module._WORKER_POST_DATETIME_PRECONDITION_CODES):
            records.clear()
            with self.subTest(post_datetime_code=code), patch.dict(
                sys.modules,
                {"npi_core": package, "npi_core.api": api},
            ), patch.object(
                self.module,
                "MBOM_POST_DATETIME_WORKER_DIAGNOSTICS_ENABLED",
                True,
            ), self.assertRaises(RuntimeError) as post_datetime:
                with self.module.worker_downstream_diagnostic_step(code, _TRACE_ID):
                    raise original
            self.assertIs(post_datetime.exception, original)
            self.assertEqual(records[0]["code"], code)
            self.assertNotIn("private", str(records))

        for code in sorted(self.module._WORKER_POST_MANIFEST_CLOSED_CODES):
            records.clear()
            with self.subTest(post_manifest_closed_code=code), patch.dict(
                sys.modules,
                {"npi_core": package, "npi_core.api": api},
            ), self.assertRaises(RuntimeError) as post_manifest_closed:
                with self.module.worker_downstream_diagnostic_step(code, _TRACE_ID):
                    raise original
            self.assertIs(post_manifest_closed.exception, original)
            self.assertEqual(records, [])

        with patch.dict(
            sys.modules,
            {"npi_core": package, "npi_core.api": api},
        ):
            with self.module.worker_downstream_diagnostic_step(
                "P804_WORKER_PROCESS_OUTBOX", _TRACE_ID
            ):
                pass
        self.assertEqual(records, [])

        for code in sorted(self.module._WORKER_POST_MANIFEST_DIAGNOSTIC_CODES):
            records.clear()
            with self.subTest(post_manifest_active_code=code), patch.dict(
                sys.modules,
                {"npi_core": package, "npi_core.api": api},
            ), self.assertRaises(RuntimeError) as post_manifest_active:
                with self.module.worker_downstream_diagnostic_step(code, _TRACE_ID):
                    raise original
            self.assertIs(post_manifest_active.exception, original)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["code"], code)
            self.assertEqual(records[0]["exception_type"], "RuntimeError")
            self.assertEqual(records[0]["trace_id"], _TRACE_ID)
            self.assertNotIn("private", str(records))

        closed_request_codes = (
            self.module._WORKER_NOT_CLAIMED_PRECONDITION_CODES
            - self.module._WORKER_POST_DATETIME_PRECONDITION_CODES
        )
        for code in sorted(closed_request_codes):
            records.clear()
            with self.subTest(closed_request_code=code), patch.dict(
                sys.modules,
                {"npi_core": package, "npi_core.api": api},
            ), self.assertRaises(RuntimeError) as closed_request:
                with self.module.worker_downstream_diagnostic_step(code, _TRACE_ID):
                    raise original
            self.assertIs(closed_request.exception, original)
            self.assertEqual(records, [])

        for enabled, code, trace_id in (
            (False, "P804_NOT_CLAIMED_OUTBOX_READ", _TRACE_ID),
            (True, "P804_WORKER_NOT_ALLOWED", _TRACE_ID),
            (True, "P804_NOT_CLAIMED_OUTBOX_READ", "trace-private"),
        ):
            records.clear()
            with self.subTest(enabled=enabled, code=code), patch.object(
                self.module,
                "MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED",
                enabled,
            ), patch.dict(
                sys.modules,
                {"npi_core": package, "npi_core.api": api},
            ), self.assertRaises(RuntimeError) as closed:
                with self.module.worker_downstream_diagnostic_step(code, trace_id):
                    raise original
            self.assertIs(closed.exception, original)
            self.assertEqual(records, [])

    def test_worker_trace_comes_only_from_shared_http_result(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_fresh"
        )
        segment = ast.get_source_segment(self.source, function) or ""
        self.assertIn('getattr(created, "trace_id", None)', segment)
        self.assertIn('"diagnostic_trace_id": diagnostic_trace_id', segment)
        self.assertNotIn("X-Trace-ID", segment)
        self.assertNotIn("headers", segment)

    def test_worker_log_reader_requires_one_exact_logical_record(self):
        module = self.module

        def read(
            records: list[dict[str, object]],
            site_records: list[dict[str, object]] | None = None,
            trace_id: str = _TRACE_ID,
        ):
            with tempfile.TemporaryDirectory() as directory:
                bench_path = Path(directory).resolve()
                paths = (
                    bench_path / "logs" / "npi_core.log",
                    bench_path
                    / "sites"
                    / module.SITE_NAME
                    / "logs"
                    / "npi_core.log",
                )
                for path in paths:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("prior safe log\n", encoding="utf-8")
                with patch.object(
                    module.item_runtime,
                    "BENCH_PATH",
                    bench_path,
                ):
                    cursors = module.item_runtime._replay_diagnostic_log_cursors()
                    for path, source_records in zip(
                        paths, (records, site_records or []), strict=True
                    ):
                        with path.open("a", encoding="utf-8") as log_file:
                            for record in source_records:
                                log_file.write(
                                    "private actor path payload "
                                    + json.dumps(record, separators=(",", ":"))
                                    + "\n"
                                )
                    return module._sanitized_worker_downstream_diagnostic(
                        trace_id, cursors
                    )

        valid = {
            "code": "P804_WORKER_PROCESS_OUTBOX",
            "exceptionType": "RuntimeError",
            "traceId": _TRACE_ID,
        }
        expected = ("RuntimeError", "P804_WORKER_PROCESS_OUTBOX", _TRACE_ID)
        self.assertEqual(read([valid]), expected)
        self.assertEqual(read([valid], [valid]), expected)
        self.assertIsNone(read([valid, valid]))
        self.assertIsNone(
            read([valid], [{**valid, "code": "P804_WORKER_SESSION_RESTORE"}])
        )
        for records in (
            [],
            [{**valid, "traceId": "trace-ffffffffffffffffffffffffffffffff"}],
            [{**valid, "code": "P804_WORKER_NOT_ALLOWED"}],
            [{**valid, "exceptionType": "Bad Type /tmp/private"}],
            [{**valid, "privateValue": "released MBOM"}],
        ):
            with self.subTest(records=records):
                self.assertIsNone(read(records))
        self.assertIsNone(read([valid], trace_id="trace-private"))

    def test_failed_worker_child_never_reads_output_and_only_renders_safe_tuple(self):
        completed = SimpleNamespace(returncode=1)
        private = "private actor payload hash /tmp/private"
        kwargs = {
            "fixture_run_id": private,
            "project_id": private,
            "request_id": private,
            "outbox_id": private,
            "diagnostic_trace_id": _TRACE_ID,
        }
        diagnostic = ("RuntimeError", "P804_WORKER_PROCESS_OUTBOX", _TRACE_ID)
        with patch.object(
            self.module.item_runtime,
            "_replay_diagnostic_log_cursors",
            return_value={"logs/npi_core.log": 0},
        ), patch.object(
            self.module,
            "_sanitized_worker_downstream_diagnostic",
            return_value=diagnostic,
        ) as reader, patch.object(
            self.module.subprocess,
            "run",
            return_value=completed,
        ) as failed_run, self.assertRaises(RuntimeError) as raised:
            self.module.run_bench_fixture("exercise_worker", kwargs)
        run_kwargs = failed_run.call_args.kwargs
        self.assertNotIn("capture_output", run_kwargs)
        self.assertIs(run_kwargs["stderr"], self.module.subprocess.DEVNULL)
        self.assertNotIn("stdout", vars(completed))
        self.assertNotIn("stderr", vars(completed))
        self.assertEqual(
            str(raised.exception),
            "P8-04 Bench fixture failed "
            "[diagnostic_code=P804_WORKER_PROCESS_OUTBOX; "
            f"exception_type=RuntimeError; trace_id={_TRACE_ID}]",
        )
        self.assertNotIn(private, str(raised.exception))
        reader.assert_called_once()

        with patch.object(
            self.module.item_runtime,
            "_replay_diagnostic_log_cursors",
            return_value=None,
        ), patch.object(
            self.module.subprocess,
            "run",
            return_value=completed,
        ), self.assertRaises(RuntimeError) as closed:
            self.module.run_bench_fixture("exercise_worker", kwargs)
        self.assertEqual(str(closed.exception), "P8-04 Bench fixture failed")
        self.assertNotIn(private, str(closed.exception))

    def test_successful_worker_child_result_is_read_only_after_zero_exit(self):
        expected = {"fixture": "complete", "count": 2}

        def complete_successfully(*_args, **kwargs):
            kwargs["stdout"].write("bench prelude\n")
            kwargs["stdout"].write(json.dumps(expected) + "\n")
            kwargs["stdout"].flush()
            return SimpleNamespace(returncode=0)

        with patch.object(
            self.module.item_runtime,
            "_replay_diagnostic_log_cursors",
            return_value={"logs/npi_core.log": 0},
        ) as cursor_reader, patch.object(
            self.module.subprocess,
            "run",
            side_effect=complete_successfully,
        ) as successful_run:
            result = self.module.run_bench_fixture(
                "exercise_worker", {"diagnostic_trace_id": _TRACE_ID}
            )
        self.assertEqual(result, expected)
        self.assertIs(
            successful_run.call_args.kwargs["stderr"],
            self.module.subprocess.DEVNULL,
        )
        cursor_reader.assert_called_once()

        with patch.object(
            self.module,
            "MBOM_POST_MANIFEST_WORKER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.module.item_runtime,
            "_replay_diagnostic_log_cursors",
        ) as dormant_cursor_reader, patch.object(
            self.module.subprocess,
            "run",
            side_effect=complete_successfully,
        ):
            self.assertEqual(
                self.module.run_bench_fixture(
                    "exercise_worker", {"diagnostic_trace_id": _TRACE_ID}
                ),
                expected,
            )
        dormant_cursor_reader.assert_not_called()

    def test_worker_fixture_commit_stage_records_and_preserves_commit_failure(self):
        records: list[dict[str, object]] = []
        package = types.ModuleType("npi_core")
        package.__path__ = []
        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **values: records.append(values)
        frappe = types.ModuleType("frappe")
        original = RuntimeError("private commit message /tmp/private")
        frappe.init = lambda **_kwargs: None
        frappe.connect = lambda: None
        frappe.set_user = lambda _user: None
        frappe.destroy = lambda: None
        frappe.db = SimpleNamespace(
            commit=lambda: (_ for _ in ()).throw(original),
            rollback=lambda: None,
        )
        kwargs = {
            "fixture_run_id": self.module.FIXTURE_RUN_ID,
            "project_id": "00000000-0000-0000-0000-000000000001",
            "request_id": "00000000-0000-0000-0000-000000000002",
            "outbox_id": "00000000-0000-0000-0000-000000000003",
            "diagnostic_trace_id": _TRACE_ID,
        }
        with patch.dict(
            sys.modules,
            {"frappe": frappe, "npi_core": package, "npi_core.api": api},
        ), patch.object(
            self.module,
            "MBOM_WORKER_DOWNSTREAM_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(
            self.module,
            "MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.module,
            "exercise_worker",
            return_value={"fixed": True},
        ), patch.object(
            self.module.document_runtime,
            "_validated_runtime_site",
        ), self.assertRaises(RuntimeError) as raised:
            self.module.run_local_bench_fixture("exercise_worker", kwargs)
        self.assertIs(raised.exception, original)
        self.assertEqual(records[0]["code"], "P804_WORKER_FIXTURE_COMMIT")
        self.assertNotIn("private commit", str(records))

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
