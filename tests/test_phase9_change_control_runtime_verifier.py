from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_engineering_change_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
API = ROOT / "apps" / "npi_core" / "npi_core" / "change_control_api.py"
REPOSITORY = (
    ROOT
    / "apps"
    / "npi_core"
    / "npi_core"
    / "change_control"
    / "frappe_repository.py"
)
INTEGRATION_API = (
    ROOT / "apps" / "npi_integration" / "npi_integration" / "engineering_change_api.py"
)
INTEGRATION_REPOSITORY = (
    ROOT
    / "apps"
    / "npi_integration"
    / "npi_integration"
    / "engineering_change"
    / "frappe_repository.py"
)
RUN_ID = "0123456789abcdef0123456789abcdef"
PROJECT_ID = "00000000-0000-5000-8000-000000009101"
REQUESTER = "p9-requester@example.invalid"
WORKER = "p9-worker@example.invalid"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_engineering_change_runtime_contract", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError("P9-01 runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(
        os.environ,
        {
            "NPI_DOCUMENT_RUNTIME_RUN_ID": RUN_ID,
            "NPI_P9_01C_RUNTIME_PROJECT_ID": PROJECT_ID,
            "NPI_P9_01C_RUNTIME_REQUESTER": REQUESTER,
            "NPI_P9_01C_RUNTIME_WORKER": WORKER,
            "NPI_P9_01C_RUNTIME_SECRET": "a" * 64,
        },
        clear=False,
    ):
        spec.loader.exec_module(module)
    return module


class Phase9ChangeControlRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_verifier()
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")
        cls.api_source = API.read_text(encoding="utf-8")
        cls.repository_source = REPOSITORY.read_text(encoding="utf-8")
        cls.integration_api_source = INTEGRATION_API.read_text(encoding="utf-8")
        cls.integration_repository_source = INTEGRATION_REPOSITORY.read_text(
            encoding="utf-8"
        )

    def test_fixture_content_is_exact_closed_and_version_ready(self) -> None:
        draft = self.verifier.revision_content(complete=False)
        complete = self.verifier.revision_content(complete=True)
        self.assertEqual(
            [item["category"] for item in draft["impactAssessments"]],
            list(self.verifier.IMPACT_CATEGORIES),
        )
        self.assertEqual(len(draft["impactAssessments"]), 12)
        self.assertIsNone(draft["closureEvidence"])
        self.assertEqual(complete["effectivityRules"][0]["kind"], "date")
        self.assertEqual(
            complete["revalidationRequirements"][0]["state"], "satisfied"
        )
        self.assertTrue(
            all(
                complete["closureEvidence"][name]
                for name in (
                    "newVersionsReleased",
                    "erpUpdateObserved",
                    "oldVersionsWithdrawn",
                    "effectivityValidated",
                    "dispositionsExecuted",
                )
            )
        )

    def test_inbound_envelope_has_exact_identity_and_canonical_hash(self) -> None:
        with patch.dict(
            os.environ,
            {"NPI_P9_01C_RUNTIME_PROJECT_ID": PROJECT_ID},
            clear=False,
        ):
            event = self.verifier._inbound_event(
                "00000000-0000-4000-8000-000000009102"
            )
        self.assertEqual(event["event_type"], "npi.erp-engineering-change.v1")
        self.assertEqual(event["source_system"], "ERPNEXT")
        self.assertEqual(event["target_system"], "NPI_ONE")
        self.assertEqual(event["object_type"], "Engineering Change Request")
        self.assertEqual(event["idempotency_key"], event["event_id"])
        self.assertEqual(
            event["payload_hash"], self.verifier.canonical_hash(event["payload"])
        )

    def test_identity_is_deterministic_and_request_headers_are_bounded(self) -> None:
        self.assertEqual(
            self.verifier.deterministic_uuid("same"),
            self.verifier.deterministic_uuid("same"),
        )
        headers = self.verifier._request_headers(
            "command", csrf_token="csrf", idempotency_key="idempotency-key"
        )
        self.assertTrue(self.verifier._uuid(headers["X-Request-ID"]))
        self.assertRegex(headers["X-Trace-ID"], r"^[A-Za-z0-9._:-]{8,128}$")
        self.assertEqual(headers["X-Frappe-CSRF-Token"], "csrf")
        self.assertEqual(headers["Idempotency-Key"], "idempotency-key")

    def test_runtime_covers_closed_lifecycle_replay_and_operation_truth(self) -> None:
        for literal in (
            '"engineering_change.create"',
            '"engineering_change.revise"',
            '"ready_to_close"',
            '"engineering_change.close"',
            '"receive_engineering_change_event"',
            '"publish_change_implementation_summary"',
            '"synthetic_verified"',
            '"crossProcessReplay"',
            '"routeRecovered"',
            '"cleanupComplete"',
        ):
            self.assertIn(literal, self.source)

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

    def test_diagnostic_codes_are_exact_unique_and_cover_fresh_child_boundaries(
        self,
    ) -> None:
        tree = ast.parse(self.source)
        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith("P901_CHANGE_")
        ]
        self.assertEqual(
            set(literals), set(self.verifier.ENGINEERING_CHANGE_RUNTIME_DIAGNOSTIC_CODES)
        )
        self.assertFalse(self.verifier.ENGINEERING_CHANGE_RUNTIME_DIAGNOSTICS_ENABLED)
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_FULL_BOUNDARY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_INPUT_BOUNDARY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_LOCAL_FIXTURE_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_MARKER_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_REVISE_OUTCOME_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_ROOT_SAVE_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_OPTIONAL_EMPTY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_INBOUND_FULL_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_MARKER_REPAIR_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_SERVICE_ACTOR_REPAIR_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_INBOX_INSERT_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_DATETIME_REPAIR_DIAGNOSTICS_ENABLED
        )
        self.assertEqual(
            sum(
                (
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_FULL_BOUNDARY_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_INPUT_BOUNDARY_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_LOCAL_FIXTURE_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_MARKER_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_REVISE_OUTCOME_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_ROOT_SAVE_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_OPTIONAL_EMPTY_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_INBOUND_FULL_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_MARKER_REPAIR_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_SERVICE_ACTOR_REPAIR_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_INBOX_INSERT_DIAGNOSTICS_ENABLED,
                    self.verifier.ENGINEERING_CHANGE_RUNTIME_POST_DATETIME_REPAIR_DIAGNOSTICS_ENABLED,
                )
            ),
            0,
        )
        self.assertEqual(len(self.verifier.ENGINEERING_CHANGE_RUNTIME_DIAGNOSTIC_CODES), 144)
        server_codes = set(
            self.verifier.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_CODES
        ) | set(self.verifier.ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_CODES)
        self.assertEqual(len(server_codes), 65)
        self.assertTrue(
            all(
                literals.count(code) == 1
                if code in server_codes
                else literals.count(code) == 2
                for code in set(literals)
            )
        )
        server_literals = [
            node.value
            for source in (
                self.api_source,
                self.repository_source,
                self.integration_api_source,
                self.integration_repository_source,
            )
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in server_codes
        ]
        self.assertEqual(set(server_literals), server_codes)
        self.assertTrue(
            all(
                server_literals.count(code) == (
                    3
                    if code == "P901_CHANGE_INBOUND_REPOSITORY_INBOX_INSERT"
                    else 2
                )
                for code in server_codes
            )
        )

    def test_full_boundary_records_base_exception_without_overwriting_inner(self) -> None:
        trace = self.verifier.engineering_change_runtime_diagnostic_trace()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
            with patch.dict(
                os.environ,
                {"NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": str(path)},
                clear=False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                True,
            ):
                with self.verifier.engineering_change_runtime_diagnostic_scope(trace):
                    with self.assertRaises(SystemExit):
                        with self.verifier.engineering_change_runtime_diagnostic_step(
                            "P901_CHANGE_FRESH_PARENT"
                        ):
                            raise SystemExit(1)
            with patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                True,
            ):
                self.assertEqual(
                    self.verifier.read_engineering_change_runtime_diagnostic(
                        path, expected_trace=trace
                    ),
                    ("SystemExit", "P901_CHANGE_FRESH_PARENT", trace),
                )

    def test_failed_inner_write_leaves_outer_fallback_available(self) -> None:
        trace = self.verifier.engineering_change_runtime_diagnostic_trace()
        original_write = self.verifier._write_engineering_change_runtime_diagnostic
        attempts = 0

        def flaky_write(record: dict[str, str]) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("controlled diagnostic write failure")
            original_write(record)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
            with patch.dict(
                os.environ,
                {"NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": str(path)},
                clear=False,
            ), patch.object(
                self.verifier,
                "_write_engineering_change_runtime_diagnostic",
                side_effect=flaky_write,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                True,
            ):
                with self.verifier.engineering_change_runtime_diagnostic_scope(trace):
                    self.verifier._record_engineering_change_runtime_diagnostic(
                        "P901_CHANGE_CREATE_HTTP", RuntimeError("restricted")
                    )
                    self.verifier._record_engineering_change_runtime_diagnostic(
                        "P901_CHANGE_FRESH_PARENT", RuntimeError("restricted")
                    )
            self.assertEqual(attempts, 2)
            with patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                True,
            ):
                self.assertEqual(
                    self.verifier.read_engineering_change_runtime_diagnostic(
                        path, expected_trace=trace
                    ),
                    ("RuntimeError", "P901_CHANGE_FRESH_PARENT", trace),
                )

    def test_diagnostic_record_is_exact_o_excl_and_strictly_read(self) -> None:
        trace = self.verifier.engineering_change_runtime_diagnostic_trace()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
            with patch.dict(
                os.environ,
                {"NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": str(path)},
                clear=False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                True,
            ):
                with self.verifier.engineering_change_runtime_diagnostic_scope(trace):
                    self.verifier._record_engineering_change_runtime_diagnostic(
                        "P901_CHANGE_CREATE_HTTP", RuntimeError("restricted")
                    )
                    self.verifier._record_engineering_change_runtime_diagnostic(
                        "P901_CHANGE_CLOSE_HTTP", ValueError("must-not-overwrite")
                    )
            with patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                True,
            ):
                self.assertEqual(
                    self.verifier.read_engineering_change_runtime_diagnostic(
                        path, expected_trace=trace
                    ),
                    ("RuntimeError", "P901_CHANGE_CREATE_HTTP", trace),
                )
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(record), {"code", "exceptionType", "traceId"})
            self.assertNotIn("restricted", path.read_text(encoding="utf-8"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIsNone(
                self.verifier.read_engineering_change_runtime_diagnostic(
                    path, expected_trace="trace-" + "f" * 32
                )
            )

    def test_all_off_diagnostics_are_dormant_and_do_not_read(self) -> None:
        trace = self.verifier.engineering_change_runtime_diagnostic_trace()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
            with patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_ROOT_SAVE_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_OPTIONAL_EMPTY_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_INBOUND_FULL_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_MARKER_REPAIR_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_SERVICE_ACTOR_REPAIR_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_INBOX_INSERT_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_DATETIME_REPAIR_DIAGNOSTICS_ENABLED",
                False,
            ):
                with self.verifier.engineering_change_runtime_diagnostic_scope(trace):
                    self.verifier._record_engineering_change_runtime_diagnostic(
                        "P901_CHANGE_CREATE_HTTP", RuntimeError("restricted")
                    )
                self.assertFalse(path.exists())
                self.assertIsNone(
                    self.verifier.read_engineering_change_runtime_diagnostic(
                        path, expected_trace=trace
                    )
                )

    def test_revise_outcome_status_classes_are_fixed_and_complete(self) -> None:
        cases = (
            (0, "P901_CHANGE_REVISE_STATUS_INVALID"),
            (101, "P901_CHANGE_REVISE_STATUS_INFORMATIONAL"),
            (201, "P901_CHANGE_REVISE_STATUS_SUCCESS_NON_200"),
            (302, "P901_CHANGE_REVISE_STATUS_REDIRECTION"),
            (409, "P901_CHANGE_REVISE_STATUS_CLIENT_ERROR"),
            (500, "P901_CHANGE_REVISE_STATUS_SERVER_ERROR"),
        )
        for status, expected_code in cases:
            with patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED",
                True,
            ), self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
                trace = self.verifier.engineering_change_runtime_diagnostic_trace()
                result = self.verifier.HttpResult(status, {}, {})
                with patch.dict(
                    os.environ,
                    {"NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": str(path)},
                    clear=False,
                ), patch.object(
                    self.verifier,
                    "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                    True,
                ), patch.object(self.verifier, "request", return_value=result):
                    with self.verifier.engineering_change_runtime_diagnostic_scope(trace):
                        with self.assertRaises(RuntimeError):
                            self.verifier._revise_command(
                                object(),
                                self.verifier.RUNTIME_BASE_URL,
                                "/bounded",
                                {},
                                csrf_token="csrf",
                                idempotency_key="key",
                            )
                with patch.object(
                    self.verifier,
                    "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
                    True,
                ):
                    self.assertEqual(
                        self.verifier.read_engineering_change_runtime_diagnostic(
                            path, expected_trace=trace
                        ),
                        ("RuntimeError", expected_code, trace),
                    )

    def test_revise_outcome_success_preserves_response(self) -> None:
        headers = self.verifier._request_headers(
            "revise", csrf_token="csrf", idempotency_key="key"
        )
        result = self.verifier.HttpResult(
            200,
            {
                "X-Request-ID": headers["X-Request-ID"],
                "Cache-Control": "private, no-store",
                "Idempotency-Replayed": "false",
            },
            {"operation": "engineering_change.revise"},
        )
        with patch.object(self.verifier, "request", return_value=result):
            self.assertEqual(
                self.verifier._revise_command(
                    object(),
                    self.verifier.RUNTIME_BASE_URL,
                    "/bounded",
                    {},
                    csrf_token="csrf",
                    idempotency_key="key",
                ),
                result.body,
            )

    def test_inbound_status_classes_and_server_header_are_fixed(self) -> None:
        cases = (
            (0, "P901_CHANGE_INBOUND_STATUS_INVALID"),
            (101, "P901_CHANGE_INBOUND_STATUS_INFORMATIONAL"),
            (200, "P901_CHANGE_INBOUND_STATUS_SUCCESS_UNEXPECTED"),
            (302, "P901_CHANGE_INBOUND_STATUS_REDIRECTION"),
            (409, "P901_CHANGE_INBOUND_STATUS_CLIENT_ERROR"),
            (500, "P901_CHANGE_INBOUND_STATUS_SERVER_ERROR"),
        )
        with patch.dict(
            os.environ,
            {"NPI_P9_01C_RUNTIME_PROJECT_ID": PROJECT_ID},
            clear=False,
        ):
            event = self.verifier._inbound_event(
                "00000000-0000-4000-8000-000000009102"
            )
        for status, expected_code in cases:
            with patch.object(
                self.verifier,
                "ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED",
                True,
            ), self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
                trace = self.verifier.engineering_change_runtime_diagnostic_trace()
                with patch.dict(
                    os.environ,
                    {"NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": str(path)},
                    clear=False,
                ), patch.object(
                    self.verifier,
                    "request",
                    return_value=self.verifier.HttpResult(status, {}, {}),
                ):
                    with self.verifier.engineering_change_runtime_diagnostic_scope(trace):
                        with self.assertRaises(RuntimeError):
                            self.verifier._send_inbound(
                                self.verifier.RUNTIME_BASE_URL,
                                event,
                                "a" * 64,
                                replayed=False,
                            )
                self.assertEqual(
                    self.verifier.read_engineering_change_runtime_diagnostic(
                        path, expected_trace=trace
                    ),
                    ("RuntimeError", expected_code, trace),
                )

        captured: list[dict[str, str]] = []
        request_id = self.verifier.deterministic_uuid("request:inbound")
        response = self.verifier.HttpResult(
            202,
            {
                "X-Request-ID": request_id,
                "Cache-Control": "no-store",
                "Idempotency-Replayed": "false",
            },
            {"state": "pending"},
        )

        def fake_request(*_args, **kwargs):
            captured.append(dict(kwargs["request_headers"]))
            return response

        trace = self.verifier.engineering_change_runtime_diagnostic_trace()
        with patch.object(
            self.verifier,
            "ENGINEERING_CHANGE_RUNTIME_POST_RAW_BODY_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(self.verifier, "request", side_effect=fake_request):
            with self.verifier.engineering_change_runtime_diagnostic_scope(trace):
                self.assertEqual(
                    self.verifier._send_inbound(
                        self.verifier.RUNTIME_BASE_URL,
                        event,
                        "a" * 64,
                        replayed=False,
                    ),
                    response.body,
                )
        self.assertEqual(
            captured[0][
                self.verifier.ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_HEADER
            ],
            self.verifier.ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_SCOPE,
        )
        self.assertEqual(
            captured[0][
                self.verifier.ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_TRACE_HEADER
            ],
            trace,
        )

    def test_revise_server_header_is_exact_scope_and_trace_only_when_active(self) -> None:
        trace = self.verifier.engineering_change_runtime_diagnostic_trace()
        captured: list[dict[str, str]] = []
        expected = self.verifier._request_headers(
            "revise", csrf_token="csrf", idempotency_key="key"
        )
        result = self.verifier.HttpResult(
            200,
            {
                "X-Request-ID": expected["X-Request-ID"],
                "Cache-Control": "private, no-store",
                "Idempotency-Replayed": "false",
            },
            {"operation": "engineering_change.revise"},
        )

        def fake_request(*_args, **kwargs):
            captured.append(dict(kwargs["request_headers"]))
            return result

        with patch.object(
            self.verifier,
            "ENGINEERING_CHANGE_RUNTIME_REVISE_SERVER_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(self.verifier, "request", side_effect=fake_request):
            with self.verifier.engineering_change_runtime_diagnostic_scope(trace):
                self.verifier._revise_command(
                    object(),
                    self.verifier.RUNTIME_BASE_URL,
                    "/bounded",
                    {},
                    csrf_token="csrf",
                    idempotency_key="key",
                )
            self.verifier._revise_command(
                object(),
                self.verifier.RUNTIME_BASE_URL,
                "/bounded",
                {},
                csrf_token="csrf",
                idempotency_key="key",
            )
        self.assertEqual(
            captured[0][
                self.verifier.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_HEADER
            ],
            self.verifier.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_SCOPE,
        )
        self.assertEqual(
            captured[0][
                self.verifier.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_TRACE_HEADER
            ],
            trace,
        )
        self.assertNotIn(
            self.verifier.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_HEADER,
            captured[1],
        )
        self.assertNotIn(
            self.verifier.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_TRACE_HEADER,
            captured[1],
        )

    def test_shell_binds_diagnostic_path_before_the_p9_server_starts(self) -> None:
        export_function = self.shell[
            self.shell.index("export_engineering_change_runtime_environment()") :
            self.shell.index("clear_engineering_change_runtime_environment()")
        ]
        self.assertIn("NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH", export_function)
        sequence = self.shell[
            self.shell.index("# P9-01 reuses") :
            self.shell.index(
                "# Insert one marker-gated",
                self.shell.index("# P9-01 reuses"),
            )
        ]
        self.assertLess(
            sequence.index("export_engineering_change_runtime_environment"),
            sequence.index("start_runtime_server"),
        )

    def test_diagnostic_reader_fails_closed_for_unknown_or_malformed_records(
        self,
    ) -> None:
        trace = self.verifier.engineering_change_runtime_diagnostic_trace()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p9-01-engineering-change-runtime-diagnostic.json"
            for payload in (
                "{}\n",
                json.dumps(
                    {
                        "code": "P901_CHANGE_UNKNOWN",
                        "exceptionType": "RuntimeError",
                        "traceId": trace,
                    }
                )
                + "\n",
                json.dumps(
                    {
                        "code": "P901_CHANGE_CREATE_HTTP",
                        "exceptionType": "RuntimeError",
                        "traceId": trace,
                        "message": "restricted",
                    }
                )
                + "\n",
            ):
                path.write_text(payload, encoding="utf-8")
                self.assertIsNone(
                    self.verifier.read_engineering_change_runtime_diagnostic(
                        path, expected_trace=trace
                    )
                )

    def test_shell_reports_only_the_strict_diagnostic_reader_result(self) -> None:
        self.assertIn(
            'export NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH="${RUNNER_TEMP:-/tmp}/p9-01-engineering-change-runtime-diagnostic.json"',
            self.shell,
        )
        self.assertIn("read_engineering_change_runtime_diagnostic()", self.shell)
        self.assertIn("--diagnostic-trace", self.shell)
        self.assertIn("--read-diagnostic", self.shell)
        report = self.shell[
            self.shell.index("report_engineering_change_runtime_failure()") :
        ]
        self.assertIn(
            'P9-01 Engineering Change runtime diagnostic [${diagnostic}]', report
        )
        self.assertNotIn("tail -", report.split("}", 1)[0])

    def test_cleanup_is_project_and_exact_fixture_bounded(self) -> None:
        tree = ast.parse(self.source)
        cleanup = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_cleanup"
        )
        text = ast.unparse(cleanup)
        self.assertIn("project_global_id", text)
        self.assertIn("CHANGE_TITLE", text)
        self.assertNotIn("frappe" + ".db.sql", text)
        for doctype in (
            "NPI Engineering Change",
            "NPI Engineering Change Revision",
            "NPI Engineering Change Event",
            "NPI Engineering Change Inbox",
            "NPI Engineering Change Summary Request",
            "NPI Engineering Change Summary Outbox",
            "NPI Engineering Change Summary Attempt",
            "NPI Engineering Change Summary Result",
            "NPI Engineering Change Idempotency",
            "NPI Audit Event",
        ):
            self.assertIn(doctype, text)
        self.assertIn("engineering_change.%", text)
        self.assertIn("remaining == 0", text)

    def test_shell_owns_default_disable_restart_recovery_and_restoration(self) -> None:
        sequence = self.shell[
            self.shell.index("# P9-01 reuses") : self.shell.index(
                "# Insert one marker-gated", self.shell.index("# P9-01 reuses")
            )
        ]
        ordered = (
            "run_engineering_change_runtime_verifier disabled",
            "set_engineering_change_route_switch false false",
            "run_engineering_change_runtime_verifier fresh",
            "run_engineering_change_runtime_verifier replay-only",
            "set_engineering_change_route_switch true true",
            "run_engineering_change_runtime_verifier recovered",
            "run_engineering_change_runtime_verifier cleanup",
            "restore_engineering_change_route_switch",
        )
        positions = [sequence.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("set_runtime_disposable_marker", sequence)
        self.assertNotIn("restore_runtime_disposable_marker", sequence)
        self.assertEqual(
            self.verifier.RUNTIME_MARKER,
            "npi-one-local-runtime-disposable-v1",
        )
        self.assertIn(
            "engineering_change_route_disable_original_state", self.shell
        )
        self.assertIn(
            "Failed to restore the P9-01 route-disable switch to absent.",
            self.shell,
        )

    def test_shell_never_activates_a_production_target(self) -> None:
        self.assertNotIn("JCE-Core", self.shell)

    def test_runtime_reuses_the_retained_readiness_service_actor(self) -> None:
        self.assertEqual(
            self.verifier.EXPECTED_WORKER_USER,
            self.verifier.readiness_runtime.ACTOR_USER,
        )
        self.assertIn(
            'engineering_change_runtime_worker="npi-readiness-${document_runtime_run_id:0:20}-manager@example.invalid"',
            self.shell,
        )
        self.assertIn(
            'export NPI_P9_01C_RUNTIME_WORKER="${engineering_change_runtime_worker}"',
            self.shell,
        )
        self.assertNotIn(
            'export NPI_P9_01C_RUNTIME_WORKER="${inbound_project_runtime_actor}"',
            self.shell,
        )
        self.assertNotIn("ssh ", self.shell)
        self.assertNotIn("bench --site jce.1", self.shell)
        self.assertNotIn("npi-one-engineering-change-disposable-v1", self.shell)


if __name__ == "__main__":
    unittest.main()
