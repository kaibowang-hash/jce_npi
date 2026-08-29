from __future__ import annotations

import ast
import importlib
import json
import os
import re
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
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

    def setUp(self) -> None:
        # Existing diagnostic contract tests intentionally exercise the prior
        # response-only activation. The current action-entry activation is
        # tested explicitly through action_server_diagnostics().
        self.previous_response_activation = patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            True,
        )
        self.current_action_activation = patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED",
            False,
        )
        self.current_action_entry_activation = patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED",
            False,
        )
        self.post_action_actor_activation = patch.object(
            self.verifier,
            "POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        )
        self.previous_response_activation.start()
        self.current_action_activation.start()
        self.current_action_entry_activation.start()
        self.post_action_actor_activation.start()

    def tearDown(self) -> None:
        self.post_action_actor_activation.stop()
        self.current_action_entry_activation.stop()
        self.current_action_activation.stop()
        self.previous_response_activation.stop()

    @contextmanager
    def action_server_diagnostics(self):
        with patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED",
            True,
        ):
            yield

    @contextmanager
    def post_action_actor_diagnostics(self):
        with patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED",
            True,
        ):
            yield

    @contextmanager
    def collection_response_diagnostics(self):
        with patch.object(
            self.verifier,
            "COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(
            self.verifier,
            "POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ):
            yield

    @contextmanager
    def collection_server_diagnostics(self):
        with patch.object(
            self.verifier,
            "COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            True,
        ):
            yield

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

    def test_runtime_operation_and_action_identities_accept_canonical_uuid4_or_uuid5(self) -> None:
        operation_id = str(self.verifier._fixture_uuid("operation"))
        self.assertEqual(self.verifier._require_global_id(operation_id), operation_id)
        self.assertEqual(self.verifier._require_global_id(PROJECT_ID), PROJECT_ID)
        for invalid in (
            operation_id.upper(),
            "11111111-1111-1111-8111-111111111111",
            "not-a-uuid",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                self.verifier._require_global_id(invalid)

        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(source.count("_require_project_id(uncertain_operation_id)"), 0)
        self.assertEqual(source.count("_require_project_id(operation_id)"), 0)
        self.assertEqual(source.count("_require_project_id(action_receipt_id)"), 0)
        self.assertEqual(source.count("_require_global_id(uncertain_operation_id)"), 3)
        self.assertEqual(source.count("_require_global_id(operation_id)"), 1)
        self.assertEqual(source.count("_require_global_id(action_receipt_id)"), 1)

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
        self.assertEqual(
            self.verifier.ACTION_ACTOR_USER,
            self.verifier.readiness_runtime.ACTOR_USER,
        )
        self.assertTrue(self.verifier.ACTION_ACTOR_USER.endswith("@example.invalid"))
        self.assertNotEqual(
            self.verifier.ACTION_ACTOR_USER,
            self.verifier.ACTOR_USER,
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

    def test_actions_use_the_retained_dual_role_actor_and_reader_stays_read_only(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        readiness_source = (
            ROOT / "scripts" / "verify_readiness_runtime.py"
        ).read_text(encoding="utf-8")
        fresh = source[source.index("def run_fresh(") : source.index("\ndef run_replay(")]
        replay = source[source.index("def run_replay(") : source.index("\ndef run_recovered(")]
        self.assertEqual(fresh.count("_action(\n            action_actor,"), 4)
        self.assertEqual(fresh.count("csrf_token=action_csrf"), 4)
        self.assertNotIn("_action(\n            actor,", fresh)
        self.assertEqual(replay.count("_action(\n        action_actor,"), 2)
        self.assertEqual(replay.count("csrf_token=action_csrf"), 2)
        self.assertNotIn("_action(\n        actor,", replay)
        self.assertIn("actor = login(base_url, ACTOR_USER, fixture_password)", fresh)
        self.assertIn(
            "action_actor = login(base_url, ACTION_ACTOR_USER, fixture_password)",
            fresh,
        )
        self.assertIn(
            "action_actor = login(base_url, ACTION_ACTOR_USER, fixture_password)",
            replay,
        )
        self.assertIn(
            'expected_roles = {"Desk User", "NPI API User", "System Manager"}',
            readiness_source,
        )

    def test_post_action_actor_diagnostic_is_the_only_default_activation(self) -> None:
        assignments = {
            node.targets[0].id: node.value.value
            for node in ast.parse(SCRIPT.read_text(encoding="utf-8")).body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.endswith("_DIAGNOSTICS_ENABLED")
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, bool)
        }
        self.assertEqual(len(assignments), 14)
        self.assertEqual(
            {name for name, value in assignments.items() if value is True},
            {"POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED"},
        )

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
            self.verifier,
            "POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
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

    def test_collection_server_request_binds_exact_scope_and_trace(self) -> None:
        response = SimpleNamespace(
            status=200,
            headers={
                "X-Request-ID": "p807-list",
                "Cache-Control": "private, no-store",
            },
            body={"items": []},
        )
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        with self.collection_server_diagnostics(), patch.object(
            self.verifier.document_runtime,
            "query_headers",
            return_value={"X-Request-ID": "p807-list"},
        ), patch.object(
            self.verifier.document_runtime,
            "request",
            return_value=response,
        ) as request, self.verifier.fresh_runtime_diagnostic_scope(trace_id):
            self.verifier._request(
                object(),
                "http://127.0.0.1",
                "/safe",
                label="fresh-list",
            )
        headers = request.call_args.kwargs["request_headers"]
        self.assertEqual(headers["X-Trace-ID"], trace_id)
        self.assertEqual(
            headers[self.verifier._COLLECTION_SERVER_DIAGNOSTIC_HEADER],
            self.verifier._COLLECTION_SERVER_DIAGNOSTIC_SCOPE,
        )

        with patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier.document_runtime,
            "query_headers",
            return_value={"X-Request-ID": "p807-list"},
        ), patch.object(
            self.verifier.document_runtime,
            "request",
            return_value=response,
        ) as dormant_request, self.verifier.fresh_runtime_diagnostic_scope(trace_id):
            self.verifier._request(
                object(),
                "http://127.0.0.1",
                "/safe",
                label="fresh-list",
            )
        dormant_headers = dormant_request.call_args.kwargs["request_headers"]
        self.assertNotIn("X-Trace-ID", dormant_headers)
        self.assertNotIn(
            self.verifier._COLLECTION_SERVER_DIAGNOSTIC_HEADER,
            dormant_headers,
        )

    def test_uncertain_action_request_binds_only_the_exact_scope_and_trace(self) -> None:
        response = SimpleNamespace(
            status=409,
            headers={
                "X-Request-ID": "p807-action",
                "Cache-Control": "private, no-store",
            },
            body={},
        )
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        with self.action_server_diagnostics(), patch.object(
            self.verifier.document_runtime,
            "command_headers",
            return_value={"X-Request-ID": "p807-action"},
        ), patch.object(
            self.verifier.document_runtime,
            "request",
            return_value=response,
        ) as request, self.verifier.fresh_runtime_diagnostic_scope(trace_id):
            self.verifier._request(
                object(),
                "http://127.0.0.1",
                "/safe",
                label="uncertain-replay",
                method="POST",
                payload={"expectedRawState": "uncertain_after_timeout"},
                csrf_token="csrf",
                idempotency_key="fixed-key",
            )
        headers = request.call_args.kwargs["request_headers"]
        self.assertEqual(headers["X-Trace-ID"], trace_id)
        self.assertEqual(
            headers[self.verifier._ACTION_SERVER_DIAGNOSTIC_HEADER],
            self.verifier._ACTION_SERVER_DIAGNOSTIC_SCOPE,
        )
        self.assertNotIn(self.verifier._COLLECTION_SERVER_DIAGNOSTIC_HEADER, headers)

        with patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier.document_runtime,
            "command_headers",
            return_value={"X-Request-ID": "p807-action"},
        ), patch.object(
            self.verifier.document_runtime,
            "request",
            return_value=response,
        ) as dormant, self.verifier.fresh_runtime_diagnostic_scope(trace_id):
            self.verifier._request(
                object(),
                "http://127.0.0.1",
                "/safe",
                label="uncertain-replay",
                method="POST",
                payload={},
                csrf_token="csrf",
                idempotency_key="fixed-key",
            )
        dormant_headers = dormant.call_args.kwargs["request_headers"]
        self.assertNotIn("X-Trace-ID", dormant_headers)
        self.assertNotIn(
            self.verifier._ACTION_SERVER_DIAGNOSTIC_HEADER,
            dormant_headers,
        )

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

    def test_collection_server_diagnostic_codes_are_exact_and_lexically_unique(self) -> None:
        with self.action_server_diagnostics():
            self.assertFalse(self.verifier.FRESH_COMBINED_DIAGNOSTICS_ENABLED)
            self.assertFalse(self.verifier.COLLECTION_SHAPE_DIAGNOSTICS_ENABLED)
            self.assertFalse(self.verifier.COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED)
            self.assertFalse(self.verifier.POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED)
            self.assertFalse(self.verifier.COLLECTION_SERVER_DIAGNOSTICS_ENABLED)
            self.assertFalse(
                self.verifier.POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED
            )
            self.assertFalse(
                self.verifier.POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED
            )
            self.assertFalse(
                self.verifier.POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED
            )
            self.assertFalse(
                self.verifier.POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED
            )
            self.assertFalse(
                self.verifier.UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED
            )
            self.assertFalse(
                self.verifier.UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED
            )
            self.assertTrue(
                self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
            )
            self.assertFalse(self.verifier.DEFAULT_DISABLED_DIAGNOSTICS_ENABLED)
        self.assertEqual(len(self.verifier.FRESH_RUNTIME_DIAGNOSTIC_CODES), 45)
        self.assertEqual(len(self.verifier.FRESH_FIXTURE_DIAGNOSTIC_CODES), 52)
        self.assertEqual(len(self.verifier.COLLECTION_SHAPE_DIAGNOSTIC_CODES), 5)
        self.assertEqual(len(self.verifier.COLLECTION_RESPONSE_DIAGNOSTIC_CODES), 7)
        self.assertEqual(
            len(self.verifier.COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES),
            4,
        )
        self.assertEqual(len(self.verifier.COLLECTION_SERVER_DIAGNOSTIC_CODES), 46)
        self.assertEqual(
            len(self.verifier.UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES),
            12,
        )
        self.assertEqual(
            len(self.verifier.UNCERTAIN_REPLAY_ACTION_SERVER_DIAGNOSTIC_CODES),
            22,
        )
        self.assertEqual(
            len(self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES),
            11,
        )
        with self.action_server_diagnostics():
            codes = self.verifier._active_fresh_runtime_diagnostic_codes()
            self.assertEqual(len(codes), 199)
            self.assertEqual(
                codes,
                frozenset(self.verifier.FRESH_RUNTIME_DIAGNOSTIC_CODES).union(
                    self.verifier.FRESH_FIXTURE_DIAGNOSTIC_CODES,
                    self.verifier.COLLECTION_RESPONSE_DIAGNOSTIC_CODES,
                    self.verifier.COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES,
                    self.verifier.COLLECTION_SERVER_DIAGNOSTIC_CODES,
                    self.verifier.UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES,
                    self.verifier.UNCERTAIN_REPLAY_ACTION_SERVER_DIAGNOSTIC_CODES,
                    self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES,
                ),
            )
        with patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier.item_runtime,
            "_sanitized_server_log_diagnostic",
        ) as reader:
            self.assertEqual(
                self.verifier._active_fresh_runtime_diagnostic_codes(),
                frozenset(),
            )
            self.assertFalse(
                self.verifier._record_collection_server_diagnostic(
                    self.verifier.fresh_runtime_diagnostic_trace(),
                    {"logs/npi_core.log": 0},
                )
            )
        reader.assert_not_called()
        self.assertTrue(all(re.fullmatch(r"P807_[A-Z_]+", code) for code in codes))
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertTrue(
            all(
                source.count(f'"{code}"') == 1
                for code in self.verifier.COLLECTION_SERVER_DIAGNOSTIC_CODES
            )
        )

        self.assertTrue(
            all(
                source.count(f'"{code}"') == 1
                for code in self.verifier.UNCERTAIN_REPLAY_ACTION_SERVER_DIAGNOSTIC_CODES
            )
        )
        self.assertTrue(
            all(
                source.count(f'"{code}"') == 1
                for code in self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES
            )
        )
        self.assertNotIn("str(error)", source)
        self.assertNotIn("repr(error)", source)
        self.assertTrue(
            all(
                source.count(f'"{code}"') == 1
                for code in self.verifier.COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES
            )
        )
        self.assertTrue(
            all(
                source.count(f'"{code}"') == 1
                for code in self.verifier.UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES
            )
        )

        repository_path = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/frappe_repository.py"
        )
        repository_tree = ast.parse(repository_path.read_text(encoding="utf-8"))
        assignment = next(
            node
            for node in repository_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id
                == "INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_CODES"
                for target in node.targets
            )
        )
        self.assertIsInstance(assignment.value, ast.Call)
        repository_codes = ast.literal_eval(assignment.value.args[0])
        self.assertEqual(
            frozenset(self.verifier.COLLECTION_SERVER_DIAGNOSTIC_CODES),
            frozenset(repository_codes),
        )
        api_source = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/api.py"
        ).read_text(encoding="utf-8")
        api_tree = ast.parse(api_source)
        entry_assignment = next(
            node
            for node in api_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id
                == "INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES"
                for target in node.targets
            )
        )
        self.assertEqual(
            tuple(self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES),
            ast.literal_eval(entry_assignment.value),
        )
        self.assertTrue(
            all(
                api_source.count(f'"{code}"') == 1
                for code in self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES
            )
        )
        self.assertEqual(
            api_source.count(self.verifier._COLLECTION_SERVER_DIAGNOSTIC_HEADER),
            1,
        )
        self.assertEqual(
            api_source.count(self.verifier._COLLECTION_SERVER_DIAGNOSTIC_SCOPE),
            1,
        )

    def test_post_action_actor_diagnostic_reuses_exact_199_full_boundary(self) -> None:
        with self.post_action_actor_diagnostics():
            self.assertTrue(
                self.verifier.POST_ACTION_ACTOR_COMBINED_DIAGNOSTICS_ENABLED
            )
            self.assertFalse(
                self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED
            )
            codes = self.verifier._active_fresh_runtime_diagnostic_codes()
            self.assertEqual(len(codes), 199)
            self.assertTrue(self.verifier._collection_server_diagnostics_enabled())
            self.assertTrue(self.verifier._action_server_diagnostics_enabled())
            self.assertEqual(
                codes,
                frozenset(self.verifier.FRESH_RUNTIME_DIAGNOSTIC_CODES).union(
                    self.verifier.FRESH_FIXTURE_DIAGNOSTIC_CODES,
                    self.verifier.COLLECTION_RESPONSE_DIAGNOSTIC_CODES,
                    self.verifier.COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES,
                    self.verifier.COLLECTION_SERVER_DIAGNOSTIC_CODES,
                    self.verifier.UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTIC_CODES,
                    self.verifier.UNCERTAIN_REPLAY_ACTION_SERVER_DIAGNOSTIC_CODES,
                    self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES,
                ),
            )
            with patch.object(
                self.verifier,
                "UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED",
                True,
            ):
                self.assertEqual(
                    self.verifier._active_fresh_runtime_diagnostic_codes(),
                    frozenset(),
                )
                self.assertFalse(
                    self.verifier._fresh_runtime_diagnostics_enabled()
                )

    def test_collection_membership_records_the_first_project_containment_mismatch(self) -> None:
        required = tuple(self.verifier._REQUIRED_COLLECTION_KINDS)
        codes = tuple(self.verifier.COLLECTION_MEMBERSHIP_DIAGNOSTIC_CODES)
        expected = tuple(self.verifier._EXPECTED_COLLECTION_MEMBERSHIP)
        self.assertEqual(
            required,
            ("publish_item", "publish_mbom", "create_tool_asset"),
        )
        self.assertEqual(len(codes), 4)
        self.assertEqual(tuple(code for code, _, _ in expected), codes)
        cases = (
            (
                "P807_FRESH_COLLECTION_INBOUND_ABSENT",
                ["receive_project_submission", *required],
            ),
            *(
                (code, [kind for kind in required if kind != missing])
                for code, missing in zip(codes[1:], required, strict=True)
            ),
        )
        for expected_code, operation_kinds in cases:
            with (
                self.subTest(expected=expected_code),
                self.collection_server_diagnostics(),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
                trace_id = self.verifier.fresh_runtime_diagnostic_trace()
                with patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ), self.verifier.fresh_runtime_diagnostic_scope(trace_id), self.assertRaises(
                    RuntimeError
                ):
                    self.verifier._require_collection_kinds(
                        [{"operationKind": kind} for kind in operation_kinds]
                    )
                self.assertEqual(
                    self.verifier.read_fresh_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("RuntimeError", expected_code, trace_id),
                )

        with (
            self.collection_server_diagnostics(),
            tempfile.TemporaryDirectory() as directory,
        ):
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            trace_id = self.verifier.fresh_runtime_diagnostic_trace()
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id):
                self.verifier._require_collection_kinds(
                    [{"operationKind": kind} for kind in required]
                )
            self.assertFalse(path.exists())

        with patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTICS_ENABLED",
            False,
        ):
            self.verifier._require_collection_kinds(
                [{"operationKind": kind} for kind in required]
            )
            with self.assertRaises(RuntimeError):
                self.verifier._require_collection_kinds(
                    [
                        {"operationKind": "receive_project_submission"},
                        *({"operationKind": kind} for kind in required),
                    ]
                )

    def test_fresh_diagnostic_activations_are_mutually_exclusive(self) -> None:
        with patch.object(
            self.verifier,
            "FRESH_COMBINED_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(
            self.verifier,
            "COLLECTION_SHAPE_DIAGNOSTICS_ENABLED",
            True,
        ), patch.object(
            self.verifier,
            "COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ):
            self.assertEqual(self.verifier._active_fresh_runtime_diagnostic_codes(), frozenset())
            self.assertFalse(self.verifier._fresh_runtime_diagnostics_enabled())
        with self.collection_server_diagnostics(), patch.object(
            self.verifier,
            "COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
            True,
        ):
            self.assertEqual(
                self.verifier._active_fresh_runtime_diagnostic_codes(),
                frozenset(),
            )
            self.assertFalse(self.verifier._collection_server_diagnostics_enabled())

    def test_collection_shape_subpredicates_record_the_first_exact_boundary(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        valid_body = {
            "projectGlobalId": PROJECT_ID,
            "permissions": {"view": True},
            "items": [],
        }
        cases = (
            (
                "P807_COLLECTION_STATUS",
                SimpleNamespace(status=503, body=dict(valid_body)),
            ),
            (
                "P807_COLLECTION_PROJECT",
                SimpleNamespace(status=200, body={**valid_body, "projectGlobalId": "wrong"}),
            ),
            (
                "P807_COLLECTION_PERMISSIONS",
                SimpleNamespace(status=200, body={**valid_body, "permissions": None}),
            ),
            (
                "P807_COLLECTION_ITEMS",
                SimpleNamespace(status=200, body={**valid_body, "items": {}}),
            ),
            (
                "P807_COLLECTION_ITEM_SHAPES",
                SimpleNamespace(status=200, body={**valid_body, "items": [None]}),
            ),
        )
        for expected, result in cases:
            with self.subTest(expected=expected), patch.object(
                self.verifier,
                "COLLECTION_SHAPE_DIAGNOSTICS_ENABLED",
                True,
            ), patch.object(
                self.verifier,
                "COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "POST_UUID_COLLECTION_SERVER_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "POST_UUID_COLLECTION_MEMBERSHIP_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "POST_MEMBERSHIP_COMBINED_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "POST_OPERATION_ID_COMBINED_DIAGNOSTICS_ENABLED",
                False,
            ), patch.object(
                self.verifier,
                "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
                False,
            ), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
                with patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ), self.verifier.fresh_runtime_diagnostic_scope(trace_id), self.assertRaises(
                    RuntimeError
                ):
                    self.verifier._items(result, project_id=PROJECT_ID)
                diagnostic = self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                )
                self.assertIsNotNone(diagnostic)
                self.assertEqual(diagnostic[1], expected)

    def test_collection_response_classifies_status_without_recording_value(self) -> None:
        cases = (
            ("P807_COLLECTION_STATUS_INVALID", None),
            ("P807_COLLECTION_STATUS_INFORMATIONAL", 101),
            ("P807_COLLECTION_STATUS_OTHER_SUCCESS", 201),
            ("P807_COLLECTION_STATUS_REDIRECTION", 301),
            ("P807_COLLECTION_STATUS_CLIENT_ERROR", 401),
            ("P807_COLLECTION_STATUS_SERVER_ERROR", 501),
            ("P807_COLLECTION_STATUS_OUT_OF_RANGE", 601),
        )
        valid_body = {
            "projectGlobalId": PROJECT_ID,
            "permissions": {"view": True},
            "items": [],
        }
        for expected, status in cases:
            with self.subTest(expected=expected), self.collection_response_diagnostics(), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
                trace_id = self.verifier.fresh_runtime_diagnostic_trace()
                with patch.dict(
                    os.environ,
                    {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                    clear=False,
                ), self.verifier.fresh_runtime_diagnostic_scope(trace_id), self.assertRaises(
                    RuntimeError
                ):
                    self.verifier._items(
                        SimpleNamespace(status=status, body=dict(valid_body)),
                        project_id=PROJECT_ID,
                    )
                diagnostic = self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                )
                self.assertIsNotNone(diagnostic)
                self.assertEqual(diagnostic[1], expected)

    def test_uncertain_replay_response_records_only_the_first_safe_predicate(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        valid_body = {
            "status": 409,
            "code": "INTEGRATION_OPERATION_CONFLICT",
            "traceId": trace_id,
        }

        def result(
            *,
            status: object = 409,
            body: dict[str, object] | None = None,
            media_type: str = "application/problem+json",
            header_trace: str = trace_id,
        ) -> SimpleNamespace:
            return SimpleNamespace(
                status=status,
                body=dict(valid_body if body is None else body),
                headers=Headers({"X-Trace-ID": header_trace}, media_type),
            )

        cases = (
            ("P807_UNCERTAIN_REPLAY_STATUS_INVALID", result(status=None)),
            ("P807_UNCERTAIN_REPLAY_STATUS_INFORMATIONAL", result(status=101)),
            ("P807_UNCERTAIN_REPLAY_STATUS_SUCCESS", result(status=201)),
            ("P807_UNCERTAIN_REPLAY_STATUS_REDIRECTION", result(status=301)),
            (
                "P807_UNCERTAIN_REPLAY_STATUS_OTHER_CLIENT_ERROR",
                result(status=401),
            ),
            ("P807_UNCERTAIN_REPLAY_STATUS_SERVER_ERROR", result(status=501)),
            ("P807_UNCERTAIN_REPLAY_STATUS_OUT_OF_RANGE", result(status=601)),
            (
                "P807_UNCERTAIN_REPLAY_BODY_STATUS",
                result(body={**valid_body, "status": 410}),
            ),
            (
                "P807_UNCERTAIN_REPLAY_CODE",
                result(body={**valid_body, "code": "WRONG"}),
            ),
            (
                "P807_UNCERTAIN_REPLAY_MEDIA_TYPE",
                result(media_type="application/json"),
            ),
            (
                "P807_UNCERTAIN_REPLAY_TRACE",
                result(header_trace="trace-00000000000000000000000000000000"),
            ),
            (
                "P807_UNCERTAIN_REPLAY_ENVELOPE",
                result(body={**valid_body, "message": "withheld"}),
            ),
        )
        for expected, response in cases:
            with (
                self.subTest(expected=expected),
                self.collection_server_diagnostics(),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
                with (
                    patch.dict(
                        os.environ,
                        {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                        clear=False,
                    ),
                    self.verifier.fresh_runtime_diagnostic_scope(trace_id),
                    self.assertRaises(RuntimeError),
                ):
                    self.verifier._validate_uncertain_replay_problem(response)
                self.assertEqual(
                    self.verifier.read_fresh_runtime_diagnostic(
                        path,
                        expected_trace=trace_id,
                    ),
                    ("RuntimeError", expected, trace_id),
                )
                self.assertNotIn("withheld", path.read_text(encoding="utf-8"))

        with (
            self.collection_server_diagnostics(),
            tempfile.TemporaryDirectory() as directory,
        ):
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id):
                self.verifier._validate_uncertain_replay_problem(result())
            self.assertFalse(path.exists())

        with patch.object(
            self.verifier,
            "UNCERTAIN_REPLAY_RESPONSE_DIAGNOSTICS_ENABLED",
            False,
        ), patch.object(self.verifier, "validate_problem") as validate:
            response = result()
            self.verifier._validate_uncertain_replay_problem(response)
        validate.assert_called_once_with(
            response,
            409,
            "INTEGRATION_OPERATION_CONFLICT",
        )

    def test_collection_server_tuple_wins_and_parent_status_is_fallback(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        result = SimpleNamespace(status=500, body={})
        cursors = {"logs/npi_core.log": 0, "sites/npi.localhost/logs/npi_core.log": 0}
        with (
            self.collection_server_diagnostics(),
            tempfile.TemporaryDirectory() as directory,
        ):
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=(
                    "ValidationError",
                    "P807_COLLECTION_MBOM_VALUE",
                    trace_id,
                ),
            ) as reader, self.assertRaises(RuntimeError):
                self.verifier._items(
                    result,
                    project_id=PROJECT_ID,
                    diagnostic_cursors=cursors,
                )
            self.assertEqual(
                self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                ("ValidationError", "P807_COLLECTION_MBOM_VALUE", trace_id),
            )
            self.assertEqual(reader.call_args.args, (trace_id, cursors))
            self.assertEqual(
                reader.call_args.kwargs,
                {
                    "code_prefix": "P807_COLLECTION_",
                    "allowed_codes": frozenset(
                        self.verifier.COLLECTION_SERVER_DIAGNOSTIC_CODES
                    ),
                },
            )

        with (
            self.collection_server_diagnostics(),
            tempfile.TemporaryDirectory() as directory,
        ):
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=None,
            ), self.assertRaises(RuntimeError):
                self.verifier._items(
                    result,
                    project_id=PROJECT_ID,
                    diagnostic_cursors=cursors,
                )
            self.assertEqual(
                self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                ("RuntimeError", "P807_COLLECTION_STATUS_SERVER_ERROR", trace_id),
            )

    def test_action_server_tuple_wins_and_safe_status_is_fallback(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        result = SimpleNamespace(status=404, body={})
        cursors = {
            "logs/npi_core.log": 0,
            "sites/npi.localhost/logs/npi_core.log": 0,
        }
        with (
            self.action_server_diagnostics(),
            tempfile.TemporaryDirectory() as directory,
        ):
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=(
                    "IntegrationOperationsUnavailable",
                    "P807_ACTION_API_CONTEXT",
                    trace_id,
                ),
            ) as reader, self.assertRaises(RuntimeError):
                self.verifier._validate_uncertain_replay_problem(
                    result,
                    diagnostic_cursors=cursors,
                )
            self.assertEqual(
                self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                (
                    "IntegrationOperationsUnavailable",
                    "P807_ACTION_API_CONTEXT",
                    trace_id,
                ),
            )
            self.assertEqual(reader.call_args.args, (trace_id, cursors))
            self.assertEqual(
                reader.call_args.kwargs,
                {
                    "code_prefix": "P807_ACTION_",
                    "allowed_codes": frozenset(
                        self.verifier.UNCERTAIN_REPLAY_ACTION_SERVER_DIAGNOSTIC_CODES
                    ).union(
                        self.verifier.UNCERTAIN_REPLAY_ACTION_ENTRY_DIAGNOSTIC_CODES
                    ),
                },
            )

        with (
            self.action_server_diagnostics(),
            tempfile.TemporaryDirectory() as directory,
        ):
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id), patch.object(
                self.verifier.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=None,
            ), self.assertRaises(RuntimeError):
                self.verifier._validate_uncertain_replay_problem(
                    result,
                    diagnostic_cursors=cursors,
                )
            self.assertEqual(
                self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                (
                    "RuntimeError",
                    "P807_UNCERTAIN_REPLAY_STATUS_OTHER_CLIENT_ERROR",
                    trace_id,
                ),
            )

    def test_fresh_diagnostic_is_exact_three_key_o_excl_and_inner_wins(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        with self.collection_response_diagnostics(), tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id):
                self.verifier._record_fresh_runtime_diagnostic(
                    "P807_SEED_REQUEST_INSERT",
                    RuntimeError("withheld inner"),
                )
                self.verifier._record_fresh_runtime_diagnostic(
                    "P807_FRESH_SEED",
                    ValueError("withheld outer"),
                )
            self.assertEqual(
                self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                ),
                ("RuntimeError", "P807_SEED_REQUEST_INSERT", trace_id),
            )
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(record), {"code", "exceptionType", "traceId"})
            self.assertNotIn("withheld", path.read_text(encoding="utf-8"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_fresh_diagnostic_reader_fails_closed(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        valid = {
            "code": "P807_FRESH_SEED",
            "exceptionType": "RuntimeError",
            "traceId": trace_id,
        }
        invalid_records = (
            {},
            {**valid, "extra": "forbidden"},
            {**valid, "code": "P807_UNKNOWN"},
            {**valid, "exceptionType": "bad type"},
            {**valid, "traceId": "trace-00000000000000000000000000000000"},
        )
        with self.collection_response_diagnostics(), tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            for record in invalid_records:
                with self.subTest(record=record):
                    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
                    self.assertIsNone(
                        self.verifier.read_fresh_runtime_diagnostic(
                            path,
                            expected_trace=trace_id,
                        )
                    )
            path.write_text(json.dumps(valid) + "\n" + json.dumps(valid) + "\n", encoding="utf-8")
            self.assertIsNone(
                self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                )
            )
            path.write_bytes(b"{" + b"x" * self.verifier._DIAGNOSTIC_RECORD_LIMIT + b"}")
            self.assertIsNone(
                self.verifier.read_fresh_runtime_diagnostic(
                    path,
                    expected_trace=trace_id,
                )
            )

    def test_fresh_diagnostic_step_rethrows_same_exception_and_restores_scope(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        error = RuntimeError("withheld")
        with self.collection_response_diagnostics(), tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ):
                with self.assertRaises(RuntimeError) as raised:
                    with self.verifier.fresh_runtime_diagnostic_scope(trace_id):
                        with self.verifier.fresh_runtime_diagnostic_step("P807_FRESH_LOGIN"):
                            raise error
                self.assertIs(raised.exception, error)
            self.assertIsNone(self.verifier._DIAGNOSTIC_STATE.get())

    def test_fresh_diagnostic_success_writes_no_record(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        with self.collection_response_diagnostics(), tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            with patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id):
                with self.verifier.fresh_runtime_diagnostic_step("P807_FRESH_LOGIN"):
                    pass
            self.assertFalse(path.exists())

    def test_bench_child_diagnostic_environment_is_parent_owned(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        captured: dict[str, str] = {}

        def complete(*_args, **kwargs):
            captured.update(kwargs["env"])
            kwargs["stdout"].write('{"safe":true}\n')
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            ambient = {
                self.verifier._DIAGNOSTIC_PATH_ENV: str(path),
                self.verifier._DIAGNOSTIC_SCOPE_ENV: "ambient-wrong",
                self.verifier._DIAGNOSTIC_TRACE_ENV: "trace-00000000000000000000000000000000",
            }
            with patch.dict(os.environ, ambient, clear=False), patch.object(
                self.verifier.subprocess,
                "run",
                side_effect=complete,
            ):
                result = self.verifier.run_bench_fixture("snapshot", {"safe": True})
            self.assertEqual(result, {"safe": True})
            self.assertNotIn(self.verifier._DIAGNOSTIC_PATH_ENV, captured)
            self.assertNotIn(self.verifier._DIAGNOSTIC_SCOPE_ENV, captured)
            self.assertNotIn(self.verifier._DIAGNOSTIC_TRACE_ENV, captured)

            captured.clear()
            with self.collection_response_diagnostics(), patch.dict(
                os.environ,
                {self.verifier._DIAGNOSTIC_PATH_ENV: str(path)},
                clear=False,
            ), self.verifier.fresh_runtime_diagnostic_scope(trace_id), patch.object(
                self.verifier.subprocess,
                "run",
                side_effect=complete,
            ):
                result = self.verifier.run_bench_fixture("snapshot", {"safe": True})
            self.assertEqual(result, {"safe": True})
            self.assertEqual(captured[self.verifier._DIAGNOSTIC_PATH_ENV], str(path))
            self.assertEqual(captured[self.verifier._DIAGNOSTIC_SCOPE_ENV], self.verifier._DIAGNOSTIC_SCOPE)
            self.assertEqual(captured[self.verifier._DIAGNOSTIC_TRACE_ENV], trace_id)

    def test_scoped_child_requires_exact_scope_trace_and_path(self) -> None:
        trace_id = self.verifier.fresh_runtime_diagnostic_trace()
        states: list[object] = []

        def observe(_method, _kwargs):
            states.append(self.verifier._DIAGNOSTIC_STATE.get())

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.verifier._DIAGNOSTIC_FILE_NAME
            exact = {
                self.verifier._DIAGNOSTIC_PATH_ENV: str(path),
                self.verifier._DIAGNOSTIC_SCOPE_ENV: self.verifier._DIAGNOSTIC_SCOPE,
                self.verifier._DIAGNOSTIC_TRACE_ENV: trace_id,
            }
            with self.collection_response_diagnostics(), patch.dict(
                os.environ,
                exact,
                clear=False,
            ), patch.object(
                self.verifier,
                "run_local_bench_fixture",
                side_effect=observe,
            ):
                self.verifier.run_scoped_local_bench_fixture("snapshot", {})
            self.assertEqual(states[-1], {"trace_id": trace_id, "recorded": False})

            with self.collection_response_diagnostics(), patch.dict(
                os.environ,
                {**exact, self.verifier._DIAGNOSTIC_SCOPE_ENV: "wrong"},
                clear=False,
            ), patch.object(
                self.verifier,
                "run_local_bench_fixture",
                side_effect=observe,
            ):
                self.verifier.run_scoped_local_bench_fixture("snapshot", {})
            self.assertIsNone(states[-1])

    def test_fresh_main_emits_only_the_strict_safe_tuple_on_failure(self) -> None:
        error = RuntimeError("restricted message")

        def fail(_arguments):
            self.verifier._record_fresh_runtime_diagnostic(
                "P807_FRESH_SEED",
                error,
            )
            raise error

        argv = [
            str(SCRIPT),
            "--base-url",
            "http://127.0.0.1:8000",
            "--project-id",
            PROJECT_ID,
        ]
        with self.collection_response_diagnostics(), patch.dict(
            os.environ,
            {self.verifier._DIAGNOSTIC_PATH_ENV: "/tmp/preserved-ambient-path"},
            clear=False,
        ), patch.object(sys, "argv", argv), patch.object(
            self.verifier,
            "_run_requested_runtime",
            side_effect=fail,
        ), patch("builtins.print") as emitted:
            self.assertEqual(self.verifier.main(), 1)
            self.assertEqual(
                os.environ[self.verifier._DIAGNOSTIC_PATH_ENV],
                "/tmp/preserved-ambient-path",
            )
        rendered = " ".join(str(value) for call in emitted.call_args_list for value in call.args)
        self.assertIn("diagnostic_code=P807_FRESH_SEED", rendered)
        self.assertIn("exception_type=RuntimeError", rendered)
        self.assertIn(self.verifier.fresh_runtime_diagnostic_trace(), rendered)
        self.assertNotIn("restricted message", rendered)

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
