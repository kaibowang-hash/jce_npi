from __future__ import annotations

import ast
import importlib
import json
import os
import re
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_integration_operations_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"
PROJECT_ID = "aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa"


class Headers(dict[str, str]):
    def __init__(self, values: dict[str, str], media_type: str) -> None:
        super().__init__(values)
        self.media_type = media_type

    def get_content_type(self) -> str:
        return self.media_type

sys.path[:0] = [
    str(ROOT / "scripts"),
    str(ROOT / "apps" / "npi_core"),
    str(ROOT / "apps" / "npi_integration"),
]


def load_verifier():
    with patch.dict(
        os.environ,
        {"NPI_DOCUMENT_RUNTIME_RUN_ID": FIXTURE_RUN_ID},
        clear=False,
    ):
        module = importlib.import_module("verify_integration_operations_runtime")
        return importlib.reload(module)


class Phase8IntegrationOperationsRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_verifier()

    def test_fixture_identities_are_stable_uuid4_values_and_disjoint(self) -> None:
        first = self.verifier._fixture_uuid("retryable-request")
        repeated = self.verifier._fixture_uuid("retryable-request")
        other = self.verifier._fixture_uuid("retryable-outbox")
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, other)
        self.assertEqual(first.version, 4)
        self.assertEqual(UUID(str(first)), first)
        self.assertRegex(
            self.verifier._fixture_trace("retryable"),
            r"^trace-[a-f0-9]{32}$",
        )
        self.assertRegex(self.verifier._fixture_hash("retryable"), r"^[a-f0-9]{64}$")

    def test_paths_are_project_scoped_and_actions_are_operation_specific(self) -> None:
        operation_id = str(self.verifier._fixture_uuid("operation"))
        self.assertEqual(
            self.verifier._collection_path(PROJECT_ID),
            f"/api/npi/v1/projects/{PROJECT_ID}/integration-operations",
        )
        self.assertEqual(
            self.verifier._collection_path(PROJECT_ID, dlq=True),
            f"/api/npi/v1/projects/{PROJECT_ID}/integration-operations/dlq",
        )
        self.assertEqual(
            self.verifier._detail_path(PROJECT_ID, "publish_item", operation_id),
            f"/api/npi/v1/projects/{PROJECT_ID}/integration-operations/"
            f"publish_item/{operation_id}",
        )
        self.assertEqual(
            self.verifier._action_path(
                PROJECT_ID,
                "publish_item",
                operation_id,
                "request-reconciliation",
            ),
            f"/api/npi/v1/projects/{PROJECT_ID}/integration-operations/"
            f"item-publishes/{operation_id}:request-reconciliation",
        )
        with self.assertRaises(RuntimeError):
            self.verifier._action_path(PROJECT_ID, "publish_item", operation_id, "delete")
        with self.assertRaises(RuntimeError):
            self.verifier._action_path(PROJECT_ID, "unknown", operation_id, "replay")

    def test_runtime_project_identity_is_the_canonical_deterministic_uuid5(self) -> None:
        self.assertEqual(self.verifier._require_project_id(PROJECT_ID), PROJECT_ID)
        for invalid in (
            "11111111-1111-4111-8111-111111111111",
            PROJECT_ID.upper(),
            "not-a-uuid",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                self.verifier._require_project_id(invalid)

    def test_runtime_environment_is_exact_and_uses_a_distinct_worker(self) -> None:
        exact = {
            "NPI_P8_07_RUNTIME_ENABLED": "1",
            "NPI_P8_07_RUNTIME_MARKER": self.verifier.RUNTIME_MARKER,
            "NPI_P8_07_RUNTIME_PROJECT_ID": PROJECT_ID,
            "NPI_P8_07_RUNTIME_REQUESTER": self.verifier.ACTOR_USER,
            "NPI_P8_07_RUNTIME_WORKER": "worker@example.invalid",
        }
        with patch.dict(os.environ, exact, clear=True):
            self.assertEqual(
                self.verifier._require_active_environment(PROJECT_ID),
                "worker@example.invalid",
            )
        for key, value in (
            ("NPI_P8_07_RUNTIME_ENABLED", "0"),
            ("NPI_P8_07_RUNTIME_MARKER", "wrong"),
            ("NPI_P8_07_RUNTIME_PROJECT_ID", str(self.verifier._fixture_uuid("foreign"))),
            ("NPI_P8_07_RUNTIME_REQUESTER", "other@example.invalid"),
            ("NPI_P8_07_RUNTIME_WORKER", self.verifier.ACTOR_USER),
        ):
            with self.subTest(key=key), patch.dict(os.environ, {**exact, key: value}, clear=True):
                with self.assertRaises(RuntimeError):
                    self.verifier._require_active_environment(PROJECT_ID)

    def test_safe_response_scanner_rejects_restricted_keys_recursively(self) -> None:
        self.verifier._assert_safe(
            {"items": [{"operationGlobalId": PROJECT_ID}], "permissions": {"canReplay": True}}
        )
        for key in (
            "authorization",
            "Cookie",
            "request_body",
            "response-body",
            "targetRequest",
            "privateToken",
        ):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.verifier._assert_safe({"outer": [{key: "withheld"}]})

    def test_request_binds_request_identity_cache_control_and_safe_body(self) -> None:
        response = SimpleNamespace(
            status=200,
            headers={"X-Request-ID": "p807-list", "Cache-Control": "private, no-store"},
            body={"items": []},
        )
        with patch.object(
            self.verifier.document_runtime,
            "query_headers",
            return_value={"X-Request-ID": "p807-list"},
        ), patch.object(
            self.verifier.document_runtime,
            "request",
            return_value=response,
        ) as request:
            self.assertIs(
                self.verifier._request(object(), "http://127.0.0.1", "/safe", label="list"),
                response,
            )
        self.assertEqual(request.call_args.kwargs["method"], "GET")
        self.assertIsNone(request.call_args.kwargs["payload"])

        unsafe = SimpleNamespace(
            status=200,
            headers=response.headers,
            body={"targetResponse": "withheld"},
        )
        with patch.object(
            self.verifier.document_runtime,
            "query_headers",
            return_value={"X-Request-ID": "p807-list"},
        ), patch.object(self.verifier.document_runtime, "request", return_value=unsafe):
            with self.assertRaises(RuntimeError):
                self.verifier._request(object(), "http://127.0.0.1", "/safe", label="list")

    def test_disabled_probe_requires_the_fixed_disabled_problem(self) -> None:
        response = SimpleNamespace(
            status=503,
            headers=Headers(
                {
                    "X-Request-ID": "11111111-1111-4111-8111-111111111112",
                    "X-Trace-ID": "trace-p807-disabled",
                    "Cache-Control": "private, no-store",
                },
                "application/problem+json",
            ),
            body={
                "status": 503,
                "code": "INTEGRATION_OPERATIONS_ROUTES_DISABLED",
                "traceId": "trace-p807-disabled",
            },
        )
        with patch.object(self.verifier, "login", return_value=object()), patch.object(
            self.verifier,
            "_request",
            return_value=response,
        ), patch.object(self.verifier, "validate_problem") as validate:
            self.assertEqual(
                self.verifier.run_disabled_probe("http://127.0.0.1", "secret", PROJECT_ID),
                {"routesDisabled": True},
            )
        validate.assert_called_once_with(
            validate.call_args.args[0],
            503,
            "INTEGRATION_OPERATIONS_ROUTES_DISABLED",
        )

    def test_default_disabled_diagnostic_codes_are_fixed_and_value_free(self) -> None:
        expected = {
            "P807_DEFAULT_DISABLED_LOGIN",
            "P807_DEFAULT_DISABLED_HTTP",
            "P807_DEFAULT_DISABLED_REQUEST_ID",
            "P807_DEFAULT_DISABLED_CACHE_CONTROL",
            "P807_DEFAULT_DISABLED_RESPONSE_SAFE",
            "P807_DEFAULT_DISABLED_STATUS",
            "P807_DEFAULT_DISABLED_BODY_STATUS",
            "P807_DEFAULT_DISABLED_CODE",
            "P807_DEFAULT_DISABLED_MEDIA_TYPE",
            "P807_DEFAULT_DISABLED_TRACE",
            "P807_DEFAULT_DISABLED_ENVELOPE",
            "P807_DEFAULT_DISABLED_CONTRACT",
        }
        self.assertFalse(self.verifier.DEFAULT_DISABLED_DIAGNOSTICS_ENABLED)
        self.assertEqual(self.verifier._DEFAULT_DISABLED_DIAGNOSTIC_CODES, expected)
        self.assertTrue(all(re.fullmatch(r"P807_DEFAULT_DISABLED_[A-Z_]+", code) for code in expected))
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("result.status, file=sys.stderr", source)
        self.assertNotIn("result.body, file=sys.stderr", source)
        with patch("builtins.print") as emitted:
            self.verifier._record_default_disabled_diagnostic("P807_DEFAULT_DISABLED_STATUS")
        emitted.assert_not_called()
        with patch.object(
            self.verifier,
            "DEFAULT_DISABLED_DIAGNOSTICS_ENABLED",
            True,
        ), patch("builtins.print") as emitted:
            self.verifier._record_default_disabled_diagnostic("P807_DEFAULT_DISABLED_STATUS")
        emitted.assert_called_once_with("P807_DEFAULT_DISABLED_STATUS", file=self.verifier.sys.stderr)

    def test_default_disabled_diagnostic_classifies_ordered_contract_boundaries(self) -> None:
        base = {
            "status": 503,
            "code": "INTEGRATION_OPERATIONS_ROUTES_DISABLED",
            "traceId": "trace-p807-disabled",
        }
        cases = (
            ("P807_DEFAULT_DISABLED_STATUS", {"result_status": 200}),
            ("P807_DEFAULT_DISABLED_BODY_STATUS", {"body": {**base, "status": 500}}),
            ("P807_DEFAULT_DISABLED_CODE", {"body": {**base, "code": "OTHER"}}),
            ("P807_DEFAULT_DISABLED_MEDIA_TYPE", {"media_type": "application/json"}),
            ("P807_DEFAULT_DISABLED_TRACE", {"body": {**base, "traceId": "trace-other"}}),
            ("P807_DEFAULT_DISABLED_ENVELOPE", {"body": {**base, "message": "withheld"}}),
        )
        for expected, change in cases:
            with self.subTest(expected=expected):
                response = SimpleNamespace(
                    status=change.get("result_status", 503),
                    headers=Headers(
                        {
                            "X-Request-ID": "11111111-1111-4111-8111-111111111112",
                            "X-Trace-ID": "trace-p807-disabled",
                            "Cache-Control": "private, no-store",
                        },
                        change.get("media_type", "application/problem+json"),
                    ),
                    body=change.get("body", dict(base)),
                )
                with patch.object(self.verifier, "login", return_value=object()), patch.object(
                    self.verifier,
                    "_request",
                    return_value=response,
                ), patch.object(
                    self.verifier,
                    "_record_default_disabled_diagnostic",
                ) as record, self.assertRaises(RuntimeError):
                    self.verifier.run_disabled_probe(
                        "http://127.0.0.1",
                        "secret",
                        PROJECT_ID,
                    )
                record.assert_called_once_with(expected, label="disabled")

    def test_default_disabled_diagnostic_classifies_login_and_request_boundaries(self) -> None:
        with patch.object(
            self.verifier,
            "login",
            side_effect=RuntimeError("withheld"),
        ), patch.object(
            self.verifier,
            "_record_default_disabled_diagnostic",
        ) as record, self.assertRaises(RuntimeError):
            self.verifier.run_disabled_probe("http://127.0.0.1", "secret", PROJECT_ID)
        record.assert_called_once_with("P807_DEFAULT_DISABLED_LOGIN")

        with patch.object(
            self.verifier.document_runtime,
            "query_headers",
            return_value={"X-Request-ID": "p807-list"},
        ), patch.object(
            self.verifier.document_runtime,
            "request",
            side_effect=RuntimeError("withheld"),
        ), patch.object(
            self.verifier,
            "_record_default_disabled_diagnostic",
        ) as record, self.assertRaises(RuntimeError):
            self.verifier._request(
                object(),
                "http://127.0.0.1",
                "/safe",
                label="disabled",
            )
        record.assert_called_once_with("P807_DEFAULT_DISABLED_HTTP", label="disabled")

        request_cases = (
            (
                "P807_DEFAULT_DISABLED_REQUEST_ID",
                {"X-Request-ID": "wrong", "Cache-Control": "private, no-store"},
                {"items": []},
            ),
            (
                "P807_DEFAULT_DISABLED_CACHE_CONTROL",
                {"X-Request-ID": "p807-list", "Cache-Control": "public"},
                {"items": []},
            ),
            (
                "P807_DEFAULT_DISABLED_RESPONSE_SAFE",
                {"X-Request-ID": "p807-list", "Cache-Control": "private, no-store"},
                {"privateToken": "withheld"},
            ),
        )
        for expected, headers, body in request_cases:
            with self.subTest(expected=expected), patch.object(
                self.verifier.document_runtime,
                "query_headers",
                return_value={"X-Request-ID": "p807-list"},
            ), patch.object(
                self.verifier.document_runtime,
                "request",
                return_value=SimpleNamespace(headers=headers, body=body),
            ), patch.object(
                self.verifier,
                "_record_default_disabled_diagnostic",
            ) as record, self.assertRaises(RuntimeError):
                self.verifier._request(
                    object(),
                    "http://127.0.0.1",
                    "/safe",
                    label="disabled",
                )
            record.assert_called_once_with(expected, label="disabled")

    def test_failed_bench_child_never_reads_stdout_or_stderr(self) -> None:
        class FailedOutput:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def seek(self, *_args):
                raise AssertionError("failed child stdout was read")

            def __iter__(self):
                raise AssertionError("failed child stdout was read")

        completed = SimpleNamespace(returncode=1)
        with patch.object(
            self.verifier.tempfile,
            "TemporaryFile",
            return_value=FailedOutput(),
        ), patch.object(
            self.verifier.subprocess,
            "run",
            return_value=completed,
        ) as child, self.assertRaises(RuntimeError) as raised:
            self.verifier.run_bench_fixture("snapshot", {"private": "withheld"})
        self.assertEqual(str(raised.exception), "P8-07 Bench fixture failed")
        self.assertIs(child.call_args.kwargs["stderr"], self.verifier.subprocess.DEVNULL)
        self.assertNotIn("capture_output", child.call_args.kwargs)
        self.assertNotIn("stdout", vars(completed))
        self.assertNotIn("stderr", vars(completed))

    def test_successful_bench_child_reads_one_json_object_after_zero_exit(self) -> None:
        expected = {"historyCardinalityStable": True}

        def complete(*_args, **kwargs):
            kwargs["stdout"].write(json.dumps(expected) + "\n")
            kwargs["stdout"].flush()
            return SimpleNamespace(returncode=0)

        with patch.object(self.verifier.subprocess, "run", side_effect=complete) as child:
            result = self.verifier.run_bench_fixture("verify_counts", {"safe": True})
        self.assertEqual(result, expected)
        self.assertIs(child.call_args.kwargs["stderr"], self.verifier.subprocess.DEVNULL)

    def test_bench_fixture_dispatch_is_closed_and_transactional(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        local = source[source.index("def run_local_bench_fixture(") : source.index("\ndef main(")]
        for method in (
            "append_observation",
            "seed_retryable",
            "snapshot",
            "verify_and_cleanup",
            "verify_counts",
        ):
            self.assertIn(f'"{method}": {method}', local)
        self.assertIn('require(method in fixtures, "P8-07 Bench fixture is unavailable")', local)
        self.assertLess(local.index("frappe.connect()"), local.index("fixtures[method](**kwargs)"))
        self.assertLess(local.index("frappe.db.rollback()"), local.index("raise"))
        self.assertIn("frappe.destroy()", local)

    def test_runtime_fixture_has_no_target_network_or_direct_sql(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        network_names = {"requests", "httpx", "urllib3", "socket"}
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(network_names.isdisjoint(imports))
        direct_sql = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sql"
        ]
        self.assertEqual(direct_sql, [])
        seed = source[source.index("def seed_retryable(") : source.index("\ndef snapshot(")]
        self.assertIn("failed_before_adapter_boundary_result", seed)
        self.assertIn('safe_error_code="P807_DISPOSABLE_TARGET_UNAVAILABLE"', seed)
        self.assertIn('return {"failedRetryable": True, "networkContactCount": 0, "seeded": True}', seed)

    def test_cleanup_is_exact_and_only_runs_after_immutable_history_checks(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        cleanup = source[
            source.index("def verify_and_cleanup(") : source.index("\ndef run_bench_fixture(")
        ]
        self.assertLess(cleanup.index("action.save()"), cleanup.index('frappe.db.delete('))
        self.assertLess(cleanup.index("observation.save()"), cleanup.index('frappe.db.delete('))
        for doctype in (
            "NPI Integration Reconciliation Observation",
            "NPI Integration Action Receipt",
            "NPI Audit Event",
            "NPI Item Publish Result",
            "NPI Item Publish Attempt",
            "NPI Outbox Message",
            "NPI Item Publish Request",
            "NPI Item Publish Stream Guard",
        ):
            self.assertIn(f'"{doctype}"', cleanup)
        self.assertNotIn("delete_doc", cleanup)
        self.assertIn('"global_id": ["in", operation_ids]', cleanup)
        self.assertIn('"operation_global_id": ["in", operation_ids]', cleanup)

    def test_shell_orders_disabled_fresh_replay_recovery_migration_and_cleanup(self) -> None:
        shell = SHELL.read_text(encoding="utf-8")
        runtime = shell[shell.index("run_integration_operations_runtime_verifier disabled") :]
        markers = (
            "run_integration_operations_runtime_verifier disabled",
            "run_integration_operations_runtime_verifier fresh",
            "run_integration_operations_runtime_verifier replay-only",
            "set_integration_operations_route_switch true true",
            "run_integration_operations_runtime_verifier recovered",
            'for _migration_attempt in 1 2; do',
            "run_integration_operations_runtime_verifier post-migration-cleanup",
            "if ! verify_integration_operations_runtime_log_redaction; then",
        )
        positions = [runtime.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("integration_operations_route_disable_config_changed=false", shell)
        self.assertIn("restore_integration_operations_route_switch", shell)
        self.assertIn("clear_integration_operations_runtime_environment", shell)

    def test_shell_redaction_contract_never_reports_runtime_child_output(self) -> None:
        shell = SHELL.read_text(encoding="utf-8")
        report = shell[
            shell.index("report_integration_operations_runtime_failure() {") :
            shell.index("\n}\n\nverify_integration_operations_runtime_log_redaction()")
        ]
        redaction = shell[
            shell.index("verify_integration_operations_runtime_log_redaction() {") :
            shell.index("\n}\n\n", shell.index("verify_integration_operations_runtime_log_redaction() {") + 1)
        ]
        self.assertNotIn("cat ", report)
        self.assertNotIn("tail ", report)
        self.assertNotIn("stdout", report.casefold())
        self.assertNotIn("stderr", report.casefold())
        self.assertIn("private value leaked", redaction.casefold())
        self.assertIn("grep", redaction)

    def test_cli_modes_are_mutually_exclusive_and_fixture_mode_is_closed(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        main = source[source.index("def main()") :]
        self.assertIn("<= 1", main)
        for flag in (
            "--disabled-probe",
            "--replay-only",
            "--recovered-probe",
            "--post-migration-cleanup",
            "--bench-fixture",
            "--fixture-kwargs",
        ):
            self.assertIn(flag, main)
        self.assertIn("arguments.base_url is None", main)
        self.assertIn("arguments.project_id is None", main)


if __name__ == "__main__":
    unittest.main()
