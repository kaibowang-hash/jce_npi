from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_ebom_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    saved_document_runtime = sys.modules.pop("verify_document_runtime", None)
    spec = importlib.util.spec_from_file_location(
        "verify_ebom_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("EBOM runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": FIXTURE_RUN_ID},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
        sys.modules.pop("verify_document_runtime", None)
        if saved_document_runtime is not None:
            sys.modules["verify_document_runtime"] = saved_document_runtime
    return module


class Phase5EngineeringBomRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_is_bounded_and_synthetic(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertRegex(module.POLICY_ID, r"^[a-f0-9-]{36}$")
        self.assertEqual(module.POLICY_VERSION_KEY, f"{module.POLICY_ID}:1")
        self.assertEqual(module.SYNTHETIC_NAMESPACE, "synthetic_ebom")
        self.assertTrue(
            module.ENGINEERING_BOM_KEY.startswith(
                f"{module.SYNTHETIC_NAMESPACE}-"
            )
        )
        self.assertIn(
            '"synthetic_namespace": SYNTHETIC_NAMESPACE',
            self.source,
        )
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertNotEqual(module.ACTOR_USER, module.UNRELATED_USER)
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("ERP-", self.source)

    def test_payloads_are_closed_to_npi_owned_ebom_truth(self) -> None:
        module = self.module
        policy_hash = "a" * 64
        payload = module.create_payload(policy_hash)
        self.assertEqual(
            set(payload),
            {
                "policyGlobalId",
                "policyVersion",
                "policySnapshotHash",
                "engineeringBomKey",
                "title",
                "reason",
                "effectivityNote",
                "lines",
            },
        )
        self.assertEqual(
            set(payload["lines"][0]),
            {
                "lineKey",
                "engineeringItemId",
                "description",
                "quantity",
                "engineeringUom",
                "effectivityStart",
                "attributes",
            },
        )
        revision = module.revision_payload(
            policy_hash,
            predecessor_id="10000000-0000-4000-8000-000000000001",
            predecessor_hash="b" * 64,
        )
        self.assertEqual(revision["expectedEbomVersion"], 2)
        self.assertEqual(len(revision["lines"]), 2)
        serialized = json.dumps({"create": payload, "revision": revision})
        for forbidden in (
            "itemCode",
            "stockUom",
            "manufacturingRouting",
            "formalMbom",
            "erpnext",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.casefold(), serialized.casefold())

    def test_diagnostic_is_exact_allowlisted_and_sanitized(self) -> None:
        module = self.module
        trace_id = "trace-" + ("a" * 32)
        expected_codes = {
            "P504_RUNTIME_EMPTY_WORKSPACE",
            "P504_RUNTIME_POLICY_FIXTURE",
            "P504_RUNTIME_POLICY_ROOT_BUILD_FIXTURE",
            "P504_RUNTIME_POLICY_ROOT_INSERT_FIXTURE",
            "P504_RUNTIME_POLICY_VERSION_BUILD_FIXTURE",
            "P504_RUNTIME_POLICY_VERSION_INSERT_FIXTURE",
            "P504_RUNTIME_POLICY_VERSION_PUBLISH_FIXTURE",
            "P504_RUNTIME_POLICY_PERSISTENCE_FIXTURE",
            "P504_RUNTIME_SCHEMA_FIXTURE",
            "P504_RUNTIME_GUEST_AUTHORIZATION",
            "P504_RUNTIME_UNRELATED_AUTHORIZATION",
            "P504_RUNTIME_CREATE",
            "P504_CREATE_COMMAND_CONTEXT",
            "P504_CREATE_INPUT_PARSE",
            "P504_CREATE_PROJECT_LOCK",
            "P504_CREATE_POLICY_LOAD",
            "P504_CREATE_POLICY_AUTHORITY",
            "P504_CREATE_PAYLOAD_HASH",
            "P504_CREATE_IDEMPOTENCY_REPLAY",
            "P504_CREATE_PROJECT_MUTABILITY",
            "P504_CREATE_DOMAIN_BUILD",
            "P504_CREATE_TRANSACTION_SCOPE",
            "P504_CREATE_RECEIPT_INSERT",
            "P504_CREATE_ROOT_INSERT",
            "P504_CREATE_REVISION_INSERT",
            "P504_CREATE_LINE_INSERT",
            "P504_CREATE_LIFECYCLE_INSERT",
            "P504_CREATE_ROOT_PROJECTION_SAVE",
            "P504_CREATE_AUDIT_APPEND",
            "P504_CREATE_RESPONSE_BUILD",
            "P504_CREATE_RECEIPT_SEAL",
            "P504_CREATE_API_RESPONSE",
            "P504_RUNTIME_CREATE_REPLAY",
            "P504_RUNTIME_IDEMPOTENCY_CONFLICT",
            "P504_RUNTIME_INVALID_REVISION_ROLLBACK",
            "P504_RUNTIME_SUCCESSOR_REVISION",
            "P504_RUNTIME_COMPARISON",
            "P504_RUNTIME_SUBMIT_REVIEW",
            "P504_TRANSITION_COMMAND_CONTEXT",
            "P504_TRANSITION_INPUT_PARSE",
            "P504_TRANSITION_PROJECT_LOCK",
            "P504_TRANSITION_POLICY_LOAD",
            "P504_TRANSITION_POLICY_AUTHORITY",
            "P504_TRANSITION_PAYLOAD_HASH",
            "P504_TRANSITION_IDEMPOTENCY_REPLAY",
            "P504_TRANSITION_PROJECT_MUTABILITY",
            "P504_TRANSITION_ROOT_VERSION",
            "P504_TRANSITION_REVISION_LOAD",
            "P504_TRANSITION_REVISION_HASH",
            "P504_TRANSITION_LIFECYCLE_LOAD",
            "P504_TRANSITION_LIFECYCLE_VERSION",
            "P504_TRANSITION_DOMAIN_BUILD",
            "P504_TRANSITION_TRANSACTION_SCOPE",
            "P504_TRANSITION_RECEIPT_INSERT",
            "P504_TRANSITION_EVENT_INSERT",
            "P504_TRANSITION_LIFECYCLE_PROJECTION_SAVE",
            "P504_TRANSITION_AUDIT_APPEND",
            "P504_TRANSITION_RESPONSE_BUILD",
            "P504_TRANSITION_RECEIPT_SEAL",
            "P504_TRANSITION_API_RESPONSE",
            "P504_RUNTIME_REVIEW",
            "P504_RUNTIME_RELEASE",
            "P504_RUNTIME_STALE_TRANSITION",
            "P504_RUNTIME_FINAL_WORKSPACE",
            "P504_RUNTIME_ROUTE_DISABLED",
            "P504_RUNTIME_ROUTE_RECOVERED",
            "P504_RUNTIME_PREDECESSOR_ROUTE_ISOLATION",
            "P504_RUNTIME_REPLAY_CREATE",
            "P504_RUNTIME_REPLAY_RELEASE",
        }
        self.assertEqual(set(module._RUNTIME_STAGE_CODES), expected_codes)
        error = module.RuntimeStageFailure(
            "P504_RUNTIME_CREATE",
            trace_id,
            exception_type="ValidationError",
        )
        self.assertEqual(
            module.runtime_stage_diagnostic(error),
            (
                "[diagnostic_code=P504_RUNTIME_CREATE; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for invalid_code, invalid_trace, invalid_type in (
            ("NOT_ALLOWED", trace_id, "ValidationError"),
            ("P504_RUNTIME_CREATE", "trace-secret", "ValidationError"),
            ("P504_RUNTIME_CREATE", trace_id, "bad type"),
        ):
            with self.subTest(
                code=invalid_code,
                trace=invalid_trace,
                exception_type=invalid_type,
            ), self.assertRaises(ValueError):
                module.RuntimeStageFailure(
                    invalid_code,
                    invalid_trace,
                    exception_type=invalid_type,
                )

    def test_http_failure_discards_unvalidated_body_and_type(self) -> None:
        module = self.module
        trace_id = "trace-" + ("b" * 32)
        result = module.HttpResult(
            status=500,
            headers={},
            body={
                "exc_type": "bad type /tmp/private",
                "exception": "sensitive server traceback",
                "message": "database secret",
            },
            request_id="10000000-0000-4000-8000-000000000001",
            trace_id=trace_id,
        )
        with self.assertRaises(module.RuntimeStageFailure) as failure:
            module.require_stage_status(
                result,
                {201},
                "P504_RUNTIME_CREATE",
            )
        self.assertEqual(failure.exception.exception_type, "HttpStatusError")
        diagnostic = module.runtime_stage_diagnostic(failure.exception)
        self.assertNotIn("traceback", diagnostic)
        self.assertNotIn("database", diagnostic)
        self.assertNotIn("/tmp", diagnostic)
        invalid_trace = module.HttpResult(
            status=500,
            headers={},
            body={},
            request_id="10000000-0000-4000-8000-000000000001",
            trace_id="not-a-trace",
        )
        with self.assertRaisesRegex(ValueError, "trace identity"):
            module.require_stage_status(
                invalid_trace,
                {201},
                "P504_RUNTIME_CREATE",
            )

    def test_comparison_fixture_covers_exact_change_categories(self) -> None:
        before = self.module.initial_lines()
        after = self.module.successor_lines()
        self.assertEqual([line["lineKey"] for line in before], ["10"])
        self.assertEqual([line["lineKey"] for line in after], ["10", "20"])
        self.assertNotEqual(before[0]["quantity"], after[0]["quantity"])
        self.assertNotEqual(before[0]["description"], after[0]["description"])
        self.assertNotEqual(before[0]["attributes"], after[0]["attributes"])

    def test_schema_fixture_is_metadata_only_and_fail_closed(self) -> None:
        required = (
            "NPI EBOM Policy",
            "NPI EBOM Policy Version",
            "NPI Engineering BOM",
            "NPI Engineering BOM Revision",
            "NPI Engineering BOM Line",
            "NPI EBOM Revision Lifecycle",
            "NPI EBOM Lifecycle Event",
            "NPI EBOM Command Idempotency",
        )
        self.assertEqual(self.module.EBOM_DOCTYPES, required)
        for doctype in required:
            with self.subTest(doctype=doctype):
                self.assertIn(f'"{doctype}"', self.source)
        self.assertIn("cached=False", self.source)
        self.assertIn('environment.pop(variable, None)', self.source)
        self.assertNotIn("frappe.db.set_value", self.source)
        self.assertNotIn("frappe.db." + "sql(", self.source)

    def test_policy_fixture_uses_closed_admin_boundary_without_raw_rest(self) -> None:
        self.assertIn(
            '"provision_ebom_runtime_policy": provision_ebom_runtime_policy',
            self.source,
        )
        self.assertIn("with ebom_policy_write():", self.source)
        self.assertIn("frappe.db.commit()", self.source)
        self.assertIn("frappe.db.rollback()", self.source)
        self.assertNotIn("create_resource(", self.source)
        self.assertNotIn("update_resource(", self.source)
        self.assertNotIn("ignore_" + "permissions", self.source)

    def test_policy_fixture_result_is_exact_and_actor_bound(self) -> None:
        module = self.module
        project_id = "10000000-0000-4000-8000-000000000001"
        result = {
            "fixtureRunId": module.FIXTURE_RUN_ID,
            "policyGlobalId": module.POLICY_ID,
            "policyVersionKey": module.POLICY_VERSION_KEY,
            "publicationState": "published",
            "snapshotHash": "a" * 64,
        }
        with patch.object(module, "run_bench_fixture", return_value=result) as call:
            policy_hash = module.ensure_policy(project_id=project_id)
        self.assertEqual(policy_hash, "a" * 64)
        call.assert_called_once_with(
            "provision_ebom_runtime_policy",
            {
                "fixture_run_id": module.FIXTURE_RUN_ID,
                "project_id": project_id,
                "actor_user_id": module.ACTOR_USER,
            },
        )
        with patch.object(
            module,
            "run_bench_fixture",
            return_value={"snapshotHash": "sensitive invalid result"},
        ), self.assertRaises(module.RuntimeStageFailure) as failure:
            module.ensure_policy(project_id=project_id)
        self.assertEqual(
            failure.exception.code,
            "P504_RUNTIME_POLICY_FIXTURE",
        )
        self.assertEqual(
            failure.exception.exception_type,
            "ResponseShapeError",
        )
        self.assertRegex(failure.exception.trace_id, r"^trace-[a-f0-9]{32}$")

    def test_policy_fixture_substage_diagnostic_is_validated_and_sanitized(
        self,
    ) -> None:
        module = self.module
        code = "P504_RUNTIME_POLICY_VERSION_INSERT_FIXTURE"
        trace_id = module.document_runtime.fixture_trace_id(code)
        stderr = (
            "sensitive traceback and /tmp/private path\n"
            f"[diagnostic_code={code}; exc_type=ValidationError; "
            f"trace_id={trace_id}]\n"
        )
        failure = module.bench_fixture_stage_failure(
            "provision_ebom_runtime_policy",
            stderr,
        )
        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure.code, code)
        self.assertEqual(failure.exception_type, "ValidationError")
        self.assertEqual(failure.trace_id, trace_id)
        diagnostic = module.runtime_stage_diagnostic(failure)
        self.assertNotIn("traceback", diagnostic)
        self.assertNotIn("/tmp", diagnostic)
        self.assertNotIn("private", diagnostic)

        for invalid in (
            stderr.replace(code, "P504_RUNTIME_CREATE"),
            stderr.replace(trace_id, "trace-" + ("f" * 32)),
            stderr + "unexpected trailing content\n",
        ):
            with self.subTest(stderr=invalid):
                self.assertIsNone(
                    module.bench_fixture_stage_failure(
                        "provision_ebom_runtime_policy",
                        invalid,
                    )
                )

    def test_policy_fixture_stage_maps_only_validated_exception_type(self) -> None:
        module = self.module
        code = "P504_RUNTIME_POLICY_ROOT_INSERT_FIXTURE"

        def fail() -> None:
            raise ValueError("sensitive database message")

        with self.assertRaises(module.RuntimeStageFailure) as failure:
            module.policy_fixture_stage(code, fail)
        self.assertEqual(failure.exception.code, code)
        self.assertEqual(failure.exception.exception_type, "ValueError")
        self.assertEqual(
            failure.exception.trace_id,
            module.document_runtime.fixture_trace_id(code),
        )
        self.assertNotIn(
            "sensitive",
            module.runtime_stage_diagnostic(failure.exception),
        )

    def test_policy_fixture_subprocess_relays_only_validated_diagnostic(self) -> None:
        module = self.module
        code = "P504_RUNTIME_POLICY_VERSION_PUBLISH_FIXTURE"
        trace_id = module.document_runtime.fixture_trace_id(code)
        completed = Mock(
            returncode=1,
            stdout="sensitive stdout",
            stderr=(
                "sensitive traceback\n"
                f"[diagnostic_code={code}; exc_type=ValidationError; "
                f"trace_id={trace_id}]\n"
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            bench_path = Path(directory).resolve()
            (bench_path / "sites").mkdir()
            with patch.object(module, "BENCH_PATH", bench_path), patch.object(
                module.subprocess,
                "run",
                return_value=completed,
            ), self.assertRaises(module.RuntimeStageFailure) as failure:
                module.run_bench_fixture(
                    "provision_ebom_runtime_policy",
                    {"fixture_run_id": module.FIXTURE_RUN_ID},
                )
        self.assertEqual(failure.exception.code, code)
        self.assertEqual(failure.exception.exception_type, "ValidationError")
        self.assertEqual(failure.exception.trace_id, trace_id)
        diagnostic = module.runtime_stage_diagnostic(failure.exception)
        self.assertNotIn("sensitive", diagnostic)
        self.assertNotIn("traceback", diagnostic)

    def test_runtime_shell_migrates_twice_and_restores_p504_switch(self) -> None:
        required_fragments = (
            'npi_p5_04_routes_disabled "${value}"',
            "for _migration_attempt in 1 2",
            "run_engineering_bom_runtime_verifier fresh",
            "run_engineering_bom_route_probe disabled",
            "run_engineering_bom_route_probe recovered",
            "run_engineering_bom_runtime_verifier replay-only",
            "restore_engineering_bom_route_switch",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.shell)
        self.assertIn(
            'engineering_bom_route_disable_original_state}" != "absent"',
            self.shell,
        )
        self.assertLess(
            self.shell.index("run_document_runtime_verifier fresh"),
            self.shell.index("run_engineering_bom_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_engineering_bom_runtime_verifier replay-only"),
            self.shell.index("run_document_runtime_verifier replay-only"),
        )

    def test_manual_lane_records_cumulative_p505_scope_without_secrets(self) -> None:
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        required_fragments = (
            "P5 controlled document runtime and P6 Tooling through export",
            "bash scripts/verify-frappe-runtime.sh --tooling-only",
            "scope=p5-01-through-p6-08",
            "predecessor_scope=p5-01-through-p6-07",
            "predecessor_command=bash scripts/verify-frappe-runtime.sh --document-only",
            "p6-tooling-runtime-${{ github.run_id }}",
            "docker compose down --volumes",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertNotIn("core." + "whjichen.cn", runtime_job)

    def test_command_propagates_exact_idempotency_header(self) -> None:
        result = self.module.HttpResult(
            status=201,
            headers={"Idempotency-Replayed": "false"},
            body={},
            request_id="10000000-0000-4000-8000-000000000001",
            trace_id="trace-" + ("c" * 32),
        )
        with patch.object(self.module, "ebom_request", return_value=result) as call:
            actual = self.module.command(
                Mock(),
                "http://127.0.0.1:8003",
                "csrf-" + ("a" * 48),
                "/api/npi/v1/projects/project/eboms",
                {"value": True},
                self.module.CREATE_KEY,
                "P504_RUNTIME_CREATE",
            )
        self.assertIs(actual, result)
        self.assertEqual(call.call_args.kwargs["idempotency_key"], self.module.CREATE_KEY)
        self.assertEqual(call.call_args.kwargs["csrf_token"], "csrf-" + ("a" * 48))

    def test_create_request_activates_only_the_closed_diagnostic_header(self) -> None:
        module = self.module
        request_id = "10000000-0000-4000-8000-000000000001"
        trace_id = "trace-" + ("d" * 32)
        raw = Mock(
            status=201,
            headers={
                "X-Request-ID": request_id,
                "Cache-Control": "private, no-store",
            },
            body={},
        )
        headers = {
            "Idempotency-Key": module.CREATE_KEY,
            "X-Request-ID": request_id,
            "X-Trace-ID": trace_id,
        }
        with patch.object(
            module.document_runtime,
            "command_headers",
            return_value=headers,
        ), patch.object(
            module.document_runtime,
            "request",
            return_value=raw,
        ) as request:
            result = module.ebom_request(
                Mock(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/eboms",
                method="POST",
                payload={"value": True},
                csrf_token="csrf-" + ("a" * 48),
                idempotency_key=module.CREATE_KEY,
                create_diagnostic=True,
            )
        self.assertEqual(result.status, 201)
        sent = request.call_args.kwargs["request_headers"]
        self.assertEqual(
            sent[module._CREATE_DIAGNOSTIC_HEADER],
            module._CREATE_DIAGNOSTIC_SCOPE,
        )
        self.assertEqual(
            set(sent),
            {
                "Idempotency-Key",
                "X-Request-ID",
                "X-Trace-ID",
                "X-NPI-Diagnostic-Scope",
            },
        )

    def test_transition_request_activates_only_the_closed_diagnostic_header(
        self,
    ) -> None:
        module = self.module
        request_id = "10000000-0000-4000-8000-000000000001"
        trace_id = "trace-" + ("f" * 32)
        raw = Mock(
            status=201,
            headers={
                "X-Request-ID": request_id,
                "Cache-Control": "private, no-store",
            },
            body={},
        )
        headers = {
            "Idempotency-Key": module.SUBMIT_KEY,
            "X-Request-ID": request_id,
            "X-Trace-ID": trace_id,
        }
        with patch.object(
            module.document_runtime,
            "command_headers",
            return_value=headers,
        ), patch.object(
            module.document_runtime,
            "request",
            return_value=raw,
        ) as request:
            result = module.ebom_request(
                Mock(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/eboms/ebom/revisions/revision:submit-review",
                method="POST",
                payload={"value": True},
                csrf_token="csrf-" + ("a" * 48),
                idempotency_key=module.SUBMIT_KEY,
                transition_diagnostic=True,
            )
        self.assertEqual(result.status, 201)
        sent = request.call_args.kwargs["request_headers"]
        self.assertEqual(
            sent[module._TRANSITION_DIAGNOSTIC_HEADER],
            module._TRANSITION_DIAGNOSTIC_SCOPE,
        )
        self.assertEqual(
            set(sent),
            {
                "Idempotency-Key",
                "X-Request-ID",
                "X-Trace-ID",
                "X-NPI-Diagnostic-Scope",
            },
        )

    def test_autonomous_recovery_closes_diagnostics_before_final_gate(self) -> None:
        run_fresh_source = self.source.split("def run_fresh(", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertNotIn("\n            diagnostic=True", run_fresh_source)
        self.assertNotIn("create_diagnostic=True", run_fresh_source)
        self.assertNotIn("transition_diagnostic=True", run_fresh_source)

    def test_create_server_log_diagnostic_is_exact_and_sanitized(self) -> None:
        module = self.module
        trace_id = "trace-" + ("e" * 32)
        code = "P504_CREATE_ROOT_INSERT"
        record = json.dumps(
            {
                "code": code,
                "exceptionType": "ValidationError",
                "traceId": trace_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            bench = Path(directory).resolve()
            logs = bench / "logs"
            logs.mkdir()
            (logs / "npi_core.log").write_text(
                "sensitive prefix " + record + "\n",
                encoding="utf-8",
            )
            with patch.object(module, "BENCH_PATH", bench):
                diagnostic = module._sanitized_create_server_diagnostic(trace_id)
        self.assertEqual(
            diagnostic,
            ("ValidationError", code, trace_id),
        )
        failure_result = module.HttpResult(
            status=500,
            headers={},
            body={"message": "sensitive database"},
            request_id="10000000-0000-4000-8000-000000000001",
            trace_id=trace_id,
        )
        with patch.object(
            module,
            "_sanitized_create_server_diagnostic",
            return_value=diagnostic,
        ), self.assertRaises(module.RuntimeStageFailure) as failure:
            module.require_create_status(failure_result)
        self.assertEqual(failure.exception.code, code)
        sanitized = module.runtime_stage_diagnostic(failure.exception)
        self.assertNotIn("sensitive", sanitized)
        self.assertNotIn("database", sanitized)

    def test_transition_server_log_diagnostic_is_exact_and_sanitized(self) -> None:
        module = self.module
        trace_id = "trace-" + ("9" * 32)
        code = "P504_TRANSITION_EVENT_INSERT"
        record = json.dumps(
            {
                "code": code,
                "exceptionType": "ValidationError",
                "traceId": trace_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            bench = Path(directory).resolve()
            logs = bench / "logs"
            logs.mkdir()
            (logs / "npi_core.log").write_text(
                "sensitive prefix " + record + "\n",
                encoding="utf-8",
            )
            with patch.object(module, "BENCH_PATH", bench):
                diagnostic = module._sanitized_transition_server_diagnostic(
                    trace_id
                )
        self.assertEqual(diagnostic, ("ValidationError", code, trace_id))
        failure_result = module.HttpResult(
            status=500,
            headers={},
            body={"message": "sensitive database"},
            request_id="10000000-0000-4000-8000-000000000001",
            trace_id=trace_id,
        )
        with patch.object(
            module,
            "_sanitized_transition_server_diagnostic",
            return_value=diagnostic,
        ), self.assertRaises(module.RuntimeStageFailure) as failure:
            module.require_transition_status(
                failure_result,
                "P504_RUNTIME_SUBMIT_REVIEW",
            )
        self.assertEqual(failure.exception.code, code)
        sanitized = module.runtime_stage_diagnostic(failure.exception)
        self.assertNotIn("sensitive", sanitized)
        self.assertNotIn("database", sanitized)


if __name__ == "__main__":
    unittest.main()
