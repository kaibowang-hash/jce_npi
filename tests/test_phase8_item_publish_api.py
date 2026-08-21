from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

PROJECT_ID = "00000000-0000-4000-8000-000000008301"
PHASE5_REQUEST_ID = "00000000-0000-4000-8000-000000008302"
PUBLISH_NODE_ID = "00000000-0000-4000-8000-000000008303"
ITEM_REQUEST_ID = "00000000-0000-4000-8000-000000008304"
OUTBOX_ID = "00000000-0000-4000-8000-000000008305"
REQUEST_ID = "00000000-0000-4000-8000-000000008306"
ACKNOWLEDGEMENT = (
    "I confirm this request uses the exact released Item source and current "
    "execution profile."
)

class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self, owner: "Phase8ItemPublishApiTest") -> None:
        self.owner = owner
        self.fail_commit = False

    def get_value(self, doctype: str, name: str, fieldname: str) -> object | None:
        if doctype == "User" and fieldname == "user_type":
            return self.owner.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def commit(self) -> None:
        self.owner.events.append("commit")
        if self.fail_commit:
            raise RuntimeError("synthetic commit failure with private detail")

    def rollback(self) -> None:
        self.owner.events.append("rollback")


class MockRepository:
    def __init__(self, owner: "Phase8ItemPublishApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []
        self.outcome = owner.outcome()

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.owner.events.append("authorize")
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def list_item_publish_requests(self, *args: object, **kwargs: Any):
        self.owner.events.append("list")
        self.calls.append(("list", args, kwargs))
        return copy.deepcopy(self.owner.list_response)

    def item_publish_request_detail(self, *args: object, **kwargs: Any):
        self.owner.events.append("detail")
        self.calls.append(("detail", args, kwargs))
        return copy.deepcopy(self.owner.detail_response)

    def create_item_publish_request(self, *args: object, **kwargs: Any):
        self.owner.events.append("create")
        self.calls.append(("create", args, kwargs))
        return self.outcome


class Phase8ItemPublishApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_integration.item_publish.diagnostics",
        "npi_integration.item_publish.frappe_repository",
        "npi_integration.item_publish_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[str] = []
        self.enqueued: list[dict[str, object]] = []
        self.safe_logs: list[object] = []
        self.headers = {
            "Idempotency-Key": "p8-item-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-p803-item-api-0001",
        }
        self.roles = {
            "publisher@example.invalid": ["NPI API User"],
            "viewer@example.invalid": [],
            "external@example.invalid": ["NPI API User"],
        }
        self.user_types = {
            "publisher@example.invalid": "System User",
            "viewer@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(
            user="publisher@example.invalid"
        )
        self.frappe.conf = AttrDict(npi_tenant_id="TENANT-A")
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "item_publish_request_id": ITEM_REQUEST_ID,
            },
        )
        self.frappe.local = types.SimpleNamespace(
            response=AttrDict(),
            form_dict=AttrDict(),
            request=types.SimpleNamespace(path="/", method="GET"),
        )
        self.frappe.request = self.frappe.local.request
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_roles = lambda user: self.roles.get(user, [])
        self.frappe.get_hooks = lambda _name: []
        self.frappe.get_attr = lambda _path: None
        self.frappe.db = StubDatabase(self)
        self.frappe.DoesNotExistError = type(
            "DoesNotExistError", (Exception,), {}
        )
        self.frappe.DuplicateEntryError = type(
            "DuplicateEntryError", (Exception,), {}
        )
        self.frappe.UniqueValidationError = type(
            "UniqueValidationError", (Exception,), {}
        )
        self.frappe.log_error = lambda **values: self.safe_logs.append(values)
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda *args, **kwargs: self.safe_logs.append((args, kwargs))
        )
        self.frappe.enqueue = lambda *args, **kwargs: (
            self.events.append("enqueue"),
            self.enqueued.append({"args": args, **kwargs}),
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist
        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: "csrf-" + "a" * 48
        self.frappe.sessions = sessions
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.sessions"] = sessions

        self.api = importlib.import_module("npi_integration.item_publish_api")
        self.router = importlib.import_module("npi_core.bff")
        self.detail_response = {
            "requestGlobalId": ITEM_REQUEST_ID,
            "request": {
                "globalId": ITEM_REQUEST_ID,
                "state": "queued",
                "dispatchAllowed": True,
                "legacyReadOnly": False,
                "current": True,
            },
            "currentMapping": None,
            "attempts": [],
            "result": None,
            "permissions": {"canView": True, "canExecute": True},
        }
        self.list_response = {
            "projectGlobalId": PROJECT_ID,
            "sourceFilters": {
                "publishRequestGlobalId": None,
                "selectedPublishNodeGlobalId": None,
            },
            "permissions": {"canView": True, "canExecute": True},
            "executionProfile": None,
            "mappingExpectation": None,
            "items": [],
        }
        self.repository = MockRepository(self)
        self.factories: list[dict[str, Any]] = []

        def factory(**values: Any):
            self.factories.append(values)
            return self.repository

        self.api._repository_factory = factory

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def outcome(
        self,
        *,
        replayed: bool = False,
        should_enqueue: bool = True,
        problem=None,
    ):
        return types.SimpleNamespace(
            response=(None if problem else copy.deepcopy(self.detail_response)),
            replayed=replayed,
            should_enqueue=should_enqueue,
            outbox_event_id=(UUID(OUTBOX_ID) if should_enqueue else None),
            problem=problem,
        )

    @staticmethod
    def payload() -> dict[str, object]:
        return {
            "publishRequestGlobalId": PHASE5_REQUEST_ID,
            "selectedPublishNodeGlobalId": PUBLISH_NODE_ID,
            "expectedMappingVersion": 0,
            "acknowledgement": ACKNOWLEDGEMENT,
        }

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def test_queries_authorize_project_before_secondary_resolution(self) -> None:
        filters = {
            "publishRequestGlobalId": PHASE5_REQUEST_ID,
            "selectedPublishNodeGlobalId": PUBLISH_NODE_ID,
        }
        result = self.call(self.api.get_item_publish_requests, filters)
        self.assertEqual(result, self.list_response)
        self.assertEqual(self.events, ["authorize", "list"])
        call = self.repository.calls[-1]
        self.assertEqual(str(call[2]["publish_request_id"]), PHASE5_REQUEST_ID)
        self.assertEqual(
            str(call[2]["selected_publish_node_id"]),
            PUBLISH_NODE_ID,
        )

        self.events.clear()
        self.repository.calls.clear()
        result = self.call(self.api.get_item_publish_request)
        self.assertEqual(result, self.detail_response)
        self.assertEqual(self.events, ["authorize", "detail"])
        self.assertEqual(str(self.repository.calls[-1][1][1]), ITEM_REQUEST_ID)

    def test_detail_preserves_mapping_conflict_request_and_success_result_states(self) -> None:
        self.detail_response = {
            **self.detail_response,
            "request": {
                **self.detail_response["request"],
                "state": "mapping_conflict",
            },
            "currentMapping": {
                "mappingVersion": 1,
                "formalItemCode": "ITEM-SANDBOX-0001",
                "targetVersion": "1",
                "observationHash": "a" * 64,
            },
            "result": {
                "state": "succeeded",
                "authority": "authoritative_sandbox",
                "responseAuthenticated": True,
            },
        }
        result = self.call(self.api.get_item_publish_request)
        self.assertEqual(result["request"]["state"], "mapping_conflict")
        self.assertEqual(result["result"]["state"], "succeeded")
        self.assertEqual(result["result"]["authority"], "authoritative_sandbox")
        self.assertTrue(result["result"]["responseAuthenticated"])
        self.assertEqual(result["currentMapping"]["mappingVersion"], 1)

    def test_new_command_commits_before_enqueue_and_returns_only_local_acceptance(self) -> None:
        result = self.call(self.api.create_item_publish_request, self.payload())
        self.assertEqual(result, self.detail_response)
        self.assertEqual(
            self.events,
            ["authorize", "create", "commit", "enqueue"],
        )
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "false",
        )
        call = self.repository.calls[-1]
        self.assertEqual(str(call[1][0]), PROJECT_ID)
        self.assertEqual(str(call[2]["publish_request_id"]), PHASE5_REQUEST_ID)
        self.assertEqual(
            str(call[2]["selected_publish_node_id"]),
            PUBLISH_NODE_ID,
        )
        self.assertEqual(call[2]["expected_mapping_version"], 0)
        self.assertEqual(len(call[2]["idempotency_key_hash"]), 64)
        self.assertNotIn("Idempotency-Key", repr(call))
        self.assertEqual(self.enqueued[0]["enqueue_after_commit"], False)
        self.assertEqual(self.enqueued[0]["deduplicate"], True)
        self.assertEqual(
            self.enqueued[0]["outbox_event_id"],
            OUTBOX_ID,
        )

    def test_exact_replay_returns_200_without_reenqueue(self) -> None:
        self.repository.outcome = self.outcome(
            replayed=True,
            should_enqueue=False,
        )
        result = self.call(self.api.create_item_publish_request, self.payload())
        self.assertEqual(result, self.detail_response)
        self.assertEqual(self.events, ["authorize", "create", "commit"])
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )

    def test_mock_commit_has_no_outbox_enqueue_or_target_effect(self) -> None:
        mock_response = copy.deepcopy(self.detail_response)
        mock_response["request"]["state"] = "validated_mock"
        mock_response["request"]["dispatchAllowed"] = False
        self.repository.outcome = self.outcome(should_enqueue=False)
        self.repository.outcome = types.SimpleNamespace(
            response=mock_response,
            replayed=False,
            should_enqueue=False,
            outbox_event_id=None,
            problem=None,
        )
        result = self.call(self.api.create_item_publish_request, self.payload())
        self.assertEqual(result["request"]["state"], "validated_mock")
        self.assertEqual(self.events, ["authorize", "create", "commit"])
        self.assertFalse(self.enqueued)

    def test_conflict_audit_outcome_commits_before_problem_response(self) -> None:
        problem = self.api.ItemPublishUnavailable()
        self.repository.outcome = self.outcome(
            should_enqueue=False,
            problem=problem,
        )
        result = self.call(self.api.create_item_publish_request, self.payload())
        self.assertEqual(result["code"], "ITEM_PUBLISH_REQUEST_UNAVAILABLE")
        self.assertEqual(result["status"], 404)
        self.assertEqual(
            self.events,
            ["authorize", "create", "commit", "rollback"],
        )
        self.assertFalse(self.enqueued)

    def test_commit_failure_never_responds_success_or_enqueues(self) -> None:
        self.frappe.db.fail_commit = True
        result = self.call(self.api.create_item_publish_request, self.payload())
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(result["status"], 500)
        self.assertNotIn("private detail", repr(result))
        self.assertIn("rollback", self.events)
        self.assertFalse(self.enqueued)

    def test_create_diagnostic_is_closed_response_neutral_and_sanitized(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.item_publish.diagnostics"
        )
        self.headers["X-Trace-ID"] = "trace-" + "8" * 32
        self.headers[diagnostics.ITEM_CREATE_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.ITEM_CREATE_SERVER_DIAGNOSTIC_SCOPE
        )

        def fail(*_args: object, **_kwargs: Any):
            raise RuntimeError("private released Item value")

        self.repository.create_item_publish_request = fail
        result = self.call(self.api.create_item_publish_request, self.payload())

        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertNotIn("private released Item value", repr(self.safe_logs))
        records = [
            value
            for value in self.safe_logs
            if isinstance(value, dict) and "message" in value
        ]
        self.assertTrue(records)
        diagnostic_messages = [str(value["message"]) for value in records]
        self.assertTrue(
            any(
                "P803_CREATE_REPOSITORY_COMMAND" in value
                and '"exceptionType":"RuntimeError"' in value
                and '"traceId":"trace-' + "8" * 32 + '"' in value
                for value in diagnostic_messages
            )
        )
        self.assertFalse(
            hasattr(self.frappe.flags, "npi_p803_item_create_diagnostic")
        )

    def test_legacy_query_diagnostic_is_scoped_response_neutral_and_restored(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.item_publish.diagnostics"
        )
        trace_id = "trace-" + "9" * 32
        self.headers["X-Trace-ID"] = trace_id
        self.headers[diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_SCOPE
        )
        original = RuntimeError("private actor payload /tmp/private")

        def fail(*_args: object, **_kwargs: Any):
            raise original

        self.repository.list_item_publish_requests = fail
        result = self.call(self.api.get_item_publish_requests)
        self.headers.pop(diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER)
        without_diagnostic = self.call(self.api.get_item_publish_requests)
        self.assertEqual(result, without_diagnostic)
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertNotIn(str(original), repr(result))
        rendered_logs = repr(self.safe_logs)
        self.assertIn("P803_LEGACY_QUERY_REPOSITORY", rendered_logs)
        self.assertIn('"exceptionType":"RuntimeError"', rendered_logs)
        self.assertIn(f'"traceId":"{trace_id}"', rendered_logs)
        self.assertNotIn(str(original), rendered_logs)
        self.assertFalse(
            hasattr(self.frappe.flags, "npi_p803_item_legacy_query_diagnostic")
        )

    def test_legacy_query_diagnostic_records_only_innermost_and_reraises_same(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.item_publish.diagnostics"
        )
        trace_id = "trace-" + "a" * 32
        self.headers[diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_SCOPE
        )
        previous = {"trace_id": "trace-" + "b" * 32, "recorded": False}
        setattr(
            self.frappe.flags,
            "npi_p803_item_legacy_query_diagnostic",
            previous,
        )
        original = ValueError("private business value")
        with self.assertRaises(ValueError) as failure:
            with diagnostics.item_legacy_query_server_diagnostics(trace_id):
                with diagnostics.item_legacy_query_server_step(
                    "P803_LEGACY_QUERY_REPOSITORY"
                ):
                    with diagnostics.item_legacy_query_server_step(
                        "P803_LEGACY_QUERY_ROWS"
                    ):
                        raise original
        self.assertIs(failure.exception, original)
        self.assertIs(
            self.frappe.flags.npi_p803_item_legacy_query_diagnostic,
            previous,
        )
        rendered_logs = repr(self.safe_logs)
        diagnostic_records = [
            value
            for value in self.safe_logs
            if isinstance(value, dict)
            and "P803_LEGACY_QUERY_ROWS" in str(value.get("message", ""))
        ]
        self.assertEqual(len(diagnostic_records), 1)
        self.assertNotIn("P803_LEGACY_QUERY_REPOSITORY", rendered_logs)
        self.assertNotIn(str(original), rendered_logs)

        self.safe_logs.clear()
        self.headers.pop(diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER)
        with self.assertRaises(ValueError):
            with diagnostics.item_legacy_query_server_diagnostics(trace_id):
                with diagnostics.item_legacy_query_server_step(
                    "P803_LEGACY_QUERY_ROWS"
                ):
                    raise original
        self.assertNotIn("P803_LEGACY_QUERY_", repr(self.safe_logs))

    def test_legacy_query_scope_does_not_activate_create_or_detail(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.item_publish.diagnostics"
        )
        self.headers["X-Trace-ID"] = "trace-" + "c" * 32
        self.headers[diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_SCOPE
        )

        def fail(*_args: object, **_kwargs: Any):
            raise RuntimeError("private query failure")

        self.repository.item_publish_request_detail = fail
        self.call(self.api.get_item_publish_request)
        self.assertNotIn("P803_LEGACY_QUERY_", repr(self.safe_logs))

        self.safe_logs.clear()
        self.repository.create_item_publish_request = fail
        self.call(self.api.create_item_publish_request, self.payload())
        self.assertNotIn("P803_LEGACY_QUERY_", repr(self.safe_logs))

    def test_legacy_query_wrong_scope_and_invalid_trace_are_closed(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.item_publish.diagnostics"
        )

        def fail(*_args: object, **_kwargs: Any):
            raise RuntimeError("private query failure /tmp/private")

        self.repository.list_item_publish_requests = fail
        baseline = self.call(self.api.get_item_publish_requests)
        self.safe_logs.clear()

        self.headers[diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER] = (
            "p803-legacy-query-wrong"
        )
        wrong_scope = self.call(self.api.get_item_publish_requests)
        self.assertEqual(wrong_scope, baseline)
        self.assertNotIn("P803_LEGACY_QUERY_", repr(self.safe_logs))
        self.safe_logs.clear()

        self.headers[diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_SCOPE
        )
        with patch.object(
            self.api,
            "current_trace_id",
            types.SimpleNamespace(get=lambda: "trace-private-invalid"),
        ):
            invalid_trace = self.call(self.api.get_item_publish_requests)
        self.assertEqual(invalid_trace, baseline)
        self.assertNotIn("P803_LEGACY_QUERY_", repr(self.safe_logs))
        self.assertNotIn("private query failure", repr(invalid_trace))

    def test_legacy_query_handler_stage_codes_are_unique(self) -> None:
        source = Path(self.api.__file__).read_text(encoding="utf-8")
        handler = source.split("def get_item_publish_requests(", 1)[1].split(
            "\n\n@frappe.whitelist", 1
        )[0]
        for code in (
            "P803_LEGACY_QUERY_CONTEXT",
            "P803_LEGACY_QUERY_REPOSITORY",
            "P803_LEGACY_QUERY_RESPONSE",
        ):
            self.assertEqual(handler.count(f'"{code}"'), 1)

    def test_authorization_csrf_and_project_scope_precede_body_validation(self) -> None:
        self.repository.scope = False
        result = self.call(
            self.api.create_item_publish_request,
            {"operation": "protected"},
        )
        self.assertEqual(result["code"], "ITEM_PUBLISH_REQUEST_UNAVAILABLE")
        self.assertEqual(self.events, ["authorize", "rollback"])

        self.events.clear()
        self.repository.scope = True
        self.frappe.session.user = "viewer@example.invalid"
        result = self.call(self.api.create_item_publish_request, self.payload())
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        self.assertEqual(self.events, ["rollback"])

        self.events.clear()
        self.frappe.session.user = "publisher@example.invalid"
        self.headers.pop("X-Frappe-CSRF-Token")
        result = self.call(self.api.create_item_publish_request, self.payload())
        self.assertEqual(result["code"], "CSRF_TOKEN_INVALID")
        self.assertEqual(self.events, ["rollback"])

    def test_command_contract_rejects_caller_target_authority_and_bad_expectations(self) -> None:
        cases = (
            {**self.payload(), "targetMode": "sandbox"},
            {**self.payload(), "formalItemCode": "ITEM-CALLER-001"},
            {**self.payload(), "expectedMappingVersion": -1},
            {**self.payload(), "acknowledgement": "publish latest"},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                self.events.clear()
                result = self.call(self.api.create_item_publish_request, payload)
                self.assertEqual(result["code"], "VALIDATION_FAILED")
                self.assertEqual(self.events[0], "authorize")
                self.assertNotIn("create", self.events)

    def test_profile_hook_is_absent_by_default_and_requires_one_callable(self) -> None:
        self.assertIsNone(self.api._configured_profile("TENANT-A", UUID(PROJECT_ID)))
        self.frappe.get_hooks = lambda _name: ["fixture.resolve_profile"]
        observed: list[tuple[str, str]] = []

        def resolver(tenant_id: str, project_id: str):
            observed.append((tenant_id, project_id))
            return "synthetic-profile"

        self.frappe.get_attr = lambda _path: resolver
        self.assertEqual(
            self.api._configured_profile("TENANT-A", UUID(PROJECT_ID)),
            "synthetic-profile",
        )
        self.assertEqual(observed, [("TENANT-A", PROJECT_ID)])
        self.frappe.get_hooks = lambda _name: ["one", "two"]
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            self.api._configured_profile("TENANT-A", UUID(PROJECT_ID))

    def test_stream_conflict_problems_are_explicitly_non_retryable(self) -> None:
        from npi_integration.item_publish.problems import (
            ItemPublishEffectRetained,
            ItemPublishStreamActive,
            ItemPublishStreamReconciliationRequired,
        )

        for problem_type, code in (
            (ItemPublishStreamActive, "ITEM_PUBLISH_STREAM_ACTIVE"),
            (ItemPublishEffectRetained, "ITEM_PUBLISH_EFFECT_RETAINED"),
            (
                ItemPublishStreamReconciliationRequired,
                "ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED",
            ),
        ):
            with self.subTest(code=code):
                problem = problem_type()
                self.assertEqual(problem.code, code)
                self.assertEqual(problem.status, 409)
                self.assertFalse(problem.retryable)

    def test_router_maps_only_fixed_project_first_methods(self) -> None:
        base = f"/api/npi/v1/projects/{PROJECT_ID}/item-publish-requests"
        routes = (
            (
                "GET",
                base,
                "npi_integration.item_publish_api.get_item_publish_requests",
            ),
            (
                "POST",
                base,
                "npi_integration.item_publish_api.create_item_publish_request",
            ),
            (
                "GET",
                f"{base}/{ITEM_REQUEST_ID}",
                "npi_integration.item_publish_api.get_item_publish_request",
            ),
        )
        for method, path, expected in routes:
            with self.subTest(method=method, path=path):
                self.frappe.local.request.method = method
                self.frappe.local.request.path = path
                self.frappe.local.form_dict = AttrDict()
                self.frappe.flags = types.SimpleNamespace()
                self.router.route_request()
                self.assertEqual(self.frappe.local.form_dict.cmd, expected)
                self.assertTrue(
                    self.router._requires_project_request_id(method, path)
                )

        for method, path in (
            ("PUT", base),
            ("POST", f"{base}/{ITEM_REQUEST_ID}"),
            ("GET", base + "/" + ITEM_REQUEST_ID + ":retry"),
        ):
            with self.subTest(method=method, path=path):
                self.frappe.local.request.method = method
                self.frappe.local.request.path = path
                self.frappe.local.form_dict = AttrDict()
                self.frappe.flags = types.SimpleNamespace()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    "npi_core.bff.route_not_found",
                )


if __name__ == "__main__":
    unittest.main()
