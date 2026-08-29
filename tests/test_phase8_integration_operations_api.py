from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "00000000-0000-4000-8000-00000000d701"
OPERATION = "00000000-0000-4000-8000-00000000d702"
REQUEST = "00000000-0000-4000-8000-00000000d703"


class FakeRepository:
    def __init__(self, owner: "Phase8IntegrationOperationsApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def authorize_scope(self, *args: object, **kwargs: object) -> bool:
        self.owner.events.append("authorize")
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def list_operations(self, *args: object, **kwargs: object):
        self.owner.events.append("list")
        self.calls.append(("list", args, kwargs))
        return copy.deepcopy(self.owner.collection)

    def operation_detail(self, *args: object, **kwargs: object):
        self.owner.events.append("detail")
        self.calls.append(("detail", args, kwargs))
        return copy.deepcopy(self.owner.detail)

    def request_action(self, *args: object, **kwargs: object):
        self.owner.events.append("action")
        self.calls.append(("action", args, kwargs))
        return types.SimpleNamespace(
            replayed=self.owner.replayed,
            response=copy.deepcopy(self.owner.action_response),
        )


class Phase8IntegrationOperationsApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.foundation.errors",
        "npi_core.foundation.security",
        "npi_core.foundation.tracing",
        "npi_core.project.domain",
        "npi_core.request_security",
        "npi_integration.integration_operations.api",
        "npi_integration.integration_operations.problems",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[str] = []
        self.diagnostics: list[dict[str, object]] = []
        self.replayed = False
        self.external = False
        self.headers = {
            "Idempotency-Key": "p8-07-integration-action-0001",
            "X-Request-ID": REQUEST,
        }
        self.collection = {
            "projectGlobalId": PROJECT,
            "permissions": {"view": True, "act": True},
            "items": [],
            "nextCursor": None,
        }
        self.detail = {
            "projectGlobalId": PROJECT,
            "permissions": {"view": True, "act": True},
            "operation": {"operationGlobalId": OPERATION},
        }
        self.action_response = {
            "actionGlobalId": "00000000-0000-4000-8000-00000000d704",
            "operationGlobalId": OPERATION,
            "outcomeState": "replay_requested",
            "outcomeReferenceGlobalId": "00000000-0000-4000-8000-00000000d705",
        }

        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value
        frappe.flags = types.SimpleNamespace(
            npi_route_params={
                "project_id": PROJECT,
                "operation_kind": "publish_item",
                "integration_operation_id": OPERATION,
            }
        )
        frappe.session = types.SimpleNamespace(user="operator@example.invalid")
        frappe.conf = {"npi_p8_07_routes_disabled": False}
        frappe.local = types.SimpleNamespace(
            response=types.SimpleNamespace(http_status_code=200),
            form_dict={},
            request=types.SimpleNamespace(method="GET", args={}),
        )
        frappe.get_request_header = lambda name: self.headers.get(name)
        frappe.db = types.SimpleNamespace(
            commit=lambda: self.events.append("commit"),
            rollback=lambda: self.events.append("rollback"),
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        frappe.whitelist = whitelist
        self.frappe = frappe
        sys.modules["frappe"] = frappe

        errors = types.ModuleType("npi_core.foundation.errors")

        class NpiProblem(Exception):
            def __init__(
                self,
                status: int = 500,
                code: str = "PROBLEM",
                title: object = None,
                detail: object = None,
                retryable: bool = False,
            ) -> None:
                super().__init__(title)
                self.status = status
                self.code = code
                self.title = title
                self.detail = detail
                self.retryable = retryable

        class PermissionDenied(NpiProblem):
            pass

        class RequestValidationFailed(NpiProblem):
            def __init__(self, fields: object):
                super().__init__(422, "REQUEST_VALIDATION_FAILED", fields)
                self.fields = fields

        errors.NpiProblem = NpiProblem
        errors.PermissionDenied = PermissionDenied
        errors.RequestValidationFailed = RequestValidationFailed
        sys.modules[errors.__name__] = errors

        api = types.ModuleType("npi_core.api")

        def domain_call(handle, *, success_status=200, response_headers=None, **_kwargs):
            result = handle()
            frappe.local.response.http_status_code = success_status
            frappe.local.response.headers = dict(response_headers or {})
            return result

        api.frappe_domain_call = domain_call
        api.record_safe_diagnostic = lambda **values: self.diagnostics.append(values)
        sys.modules[api.__name__] = api
        security = types.ModuleType("npi_core.foundation.security")
        security.Principal = object
        sys.modules[security.__name__] = security
        tracing = types.ModuleType("npi_core.foundation.tracing")
        tracing.current_trace_id = ContextVar(
            "p807-integration-api-trace",
            default="trace-p807-integration-api",
        )
        sys.modules[tracing.__name__] = tracing
        project = types.ModuleType("npi_core.project.domain")
        project.actor_idempotency_key_hash = (
            lambda actor, key: "a" * 64 if actor and key else None
        )
        sys.modules[project.__name__] = project

        request_security = types.ModuleType("npi_core.request_security")
        request_security.authenticated_user = lambda: frappe.session.user
        request_security.authenticated_principal = lambda _actor: types.SimpleNamespace(
            is_external=self.external,
            roles=frozenset({"System Manager", "NPI API User"}),
            tenant_id="tenant-p807",
            user_id=frappe.session.user,
        )
        request_security.require_csrf_token = lambda: self.events.append("csrf")
        request_security.response_request_id = lambda: REQUEST

        def reject(allowed, supplied):
            unexpected = (
                set(frappe.local.form_dict) | set(supplied)
            ) - set(allowed) - {"cmd"}
            if unexpected:
                raise RequestValidationFailed(
                    {name: "unexpected" for name in sorted(unexpected)}
                )

        def require(required, supplied):
            missing = [name for name in required if supplied.get(name) is None]
            if missing:
                raise RequestValidationFailed({name: "required" for name in missing})

        request_security.reject_unexpected_request_fields = reject
        request_security.require_request_fields = require
        sys.modules[request_security.__name__] = request_security

        self.repository = FakeRepository(self)
        self.module = importlib.import_module(
            "npi_integration.integration_operations.api"
        )
        self.factory = patch.object(
            self.module,
            "_repository_factory",
            return_value=self.repository,
        )
        self.factory.start()

    def tearDown(self) -> None:
        self.factory.stop()
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def call_action(self, function=None, **overrides: object):
        payload = {"expectedRawState": "failed_retryable", "expectedVersion": 3}
        payload.update(overrides)
        self.frappe.local.form_dict = dict(payload)
        return (function or self.module.replay_publish_item)(**payload)

    def test_project_first_list_dlq_and_detail_use_only_fixed_scope(self) -> None:
        result = self.module.get_integration_operations(
            operationKind="publish_item",
            sharedState="failed_retryable",
            cursor=None,
            limit=25,
        )
        self.assertEqual(result, self.collection)
        call = self.repository.calls[-1]
        self.assertEqual(call[0], "list")
        self.assertEqual(call[1], (UUID(PROJECT),))
        self.assertEqual(call[2]["operation_kind"].value, "publish_item")
        self.assertEqual(call[2]["shared_state"].value, "failed_retryable")
        self.assertFalse(call[2]["logical_dlq"])

        self.module.get_integration_operation_dlq()
        self.assertTrue(self.repository.calls[-1][2]["logical_dlq"])
        detail = self.module.get_integration_operation()
        self.assertEqual(detail, self.detail)
        detail_call = self.repository.calls[-1]
        self.assertEqual(detail_call[2]["operation_kind"].value, "publish_item")
        self.assertEqual(detail_call[2]["operation_id"], UUID(OPERATION))
        self.assertEqual(
            [event for event in self.events if event == "authorize"],
            ["authorize", "authorize", "authorize"],
        )

    def test_collection_diagnostic_requires_one_exact_get_and_preserves_response(self) -> None:
        trace_id = "trace-" + "a" * 32
        self.headers.update(
            {
                "X-Trace-ID": trace_id,
                self.module.INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_HEADER:
                    self.module.INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_SCOPE,
            }
        )
        self.frappe.flags.npi_route_params = {"project_id": PROJECT}
        self.frappe.local.form_dict = {
            "cmd": "npi_integration.integration_operations.api.get_integration_operations"
        }
        scopes: list[tuple[str | None, bool]] = []
        steps: list[str] = []

        @contextmanager
        def scope(value, *, active):
            scopes.append((value, active))
            yield

        @contextmanager
        def step(code):
            steps.append(code)
            yield

        with patch.object(
            self.module,
            "integration_operations_collection_diagnostics",
            side_effect=scope,
        ), patch.object(
            self.module,
            "integration_operations_collection_step",
            side_effect=step,
        ):
            result = self.module.get_integration_operations()

        self.assertEqual(result, self.collection)
        self.assertEqual(scopes, [(trace_id, True)])
        self.assertEqual(
            steps,
            [
                "P807_COLLECTION_API_DOMAIN_CALL",
                "P807_COLLECTION_API_FIELDS",
                "P807_COLLECTION_API_CONTEXT",
                "P807_COLLECTION_API_ARGUMENTS",
                "P807_COLLECTION_API_REPOSITORY",
                "P807_COLLECTION_API_OUTCOME",
                "P807_COLLECTION_API_RESPONSE",
            ],
        )

        for mutation in (
            lambda: self.headers.pop(
                self.module.INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_HEADER
            ),
            lambda: setattr(self.frappe.local.request, "method", "POST"),
            lambda: self.frappe.local.request.args.update({"limit": "1"}),
            lambda: self.frappe.flags.npi_route_params.update(
                {"operation_kind": "publish_item"}
            ),
            lambda: self.frappe.local.form_dict.update({"limit": "1"}),
        ):
            with self.subTest(mutation=mutation):
                self.headers[
                    self.module.INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_HEADER
                ] = self.module.INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_SCOPE
                self.frappe.local.request.method = "GET"
                self.frappe.local.request.args = {}
                self.frappe.flags.npi_route_params = {"project_id": PROJECT}
                self.frappe.local.form_dict = {
                    "cmd": "npi_integration.integration_operations.api.get_integration_operations"
                }
                mutation()
                self.assertFalse(
                    self.module._integration_operations_collection_diagnostic_active(
                        trace_id
                    )
                )

    def test_action_diagnostic_requires_one_exact_post_and_preserves_response(self) -> None:
        trace_id = "trace-" + "c" * 32
        command = "npi_integration.integration_operations.api.replay_publish_item"
        payload = {"expectedRawState": "failed_retryable", "expectedVersion": 3}
        self.headers.update(
            {
                "X-Trace-ID": trace_id,
                self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_HEADER:
                    self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_SCOPE,
            }
        )
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = {}
        self.frappe.flags.npi_route_params = {
            "project_id": PROJECT,
            "integration_operation_id": OPERATION,
        }
        self.frappe.local.form_dict = {"cmd": command, **payload}
        scopes: list[tuple[str | None, bool]] = []
        steps: list[str] = []

        @contextmanager
        def scope(value, *, active):
            scopes.append((value, active))
            yield

        @contextmanager
        def step(code):
            steps.append(code)
            yield

        with patch.object(
            self.module,
            "integration_operations_action_diagnostics",
            side_effect=scope,
        ), patch.object(
            self.module,
            "integration_operations_action_step",
            side_effect=step,
        ):
            result = self.module._fixed_action(
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                expectedRawState=payload["expectedRawState"],
                expectedVersion=payload["expectedVersion"],
                request_fields={"cmd": command},
            )

        self.assertEqual(result, self.action_response)
        self.assertEqual(scopes, [(trace_id, True)])
        self.assertEqual(
            steps,
            [
                "P807_ACTION_API_DOMAIN_CALL",
                "P807_ACTION_API_CSRF",
                "P807_ACTION_API_FIELDS",
                "P807_ACTION_API_CONTEXT",
                "P807_ACTION_API_REPOSITORY",
                "P807_ACTION_API_OUTCOME",
                "P807_ACTION_API_RESPONSE",
                "P807_ACTION_API_COMMIT",
                "P807_ACTION_API_HEADERS",
            ],
        )

        for mutation in (
            lambda: self.headers.pop(
                self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_HEADER
            ),
            lambda: setattr(self.frappe.local.request, "method", "GET"),
            lambda: self.frappe.local.request.args.update({"limit": "1"}),
            lambda: self.frappe.flags.npi_route_params.update(
                {"operation_kind": "publish_item"}
            ),
            lambda: self.frappe.local.form_dict.update({"extra": "withheld"}),
        ):
            with self.subTest(mutation=mutation):
                self.headers[
                    self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_HEADER
                ] = self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_SCOPE
                self.frappe.local.request.method = "POST"
                self.frappe.local.request.args = {}
                self.frappe.flags.npi_route_params = {
                    "project_id": PROJECT,
                    "integration_operation_id": OPERATION,
                }
                self.frappe.local.form_dict = {"cmd": command, **payload}
                mutation()
                self.assertFalse(
                    self.module._integration_operations_action_diagnostic_active(
                        trace_id,
                        operation_kind=self.module.IntegrationOperationKind.PUBLISH_ITEM,
                        action_kind=self.module.IntegrationActionKind.REPLAY,
                        expected_raw_state=payload["expectedRawState"],
                        expected_version=payload["expectedVersion"],
                        request_fields={"cmd": command},
                    )
                )

    def test_action_entry_diagnostic_records_first_exact_predicate_without_values(self) -> None:
        trace_id = "trace-" + "d" * 32
        command = "npi_integration.integration_operations.api.replay_publish_item"
        payload = {"expectedRawState": "failed_retryable", "expectedVersion": 3}
        self.headers.update(
            {
                "X-Trace-ID": trace_id,
                self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_HEADER:
                    self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_SCOPE,
            }
        )
        cases = (
            (
                "P807_ACTION_ENTRY_OPERATION_KIND",
                self.module.IntegrationOperationKind.PUBLISH_MBOM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "POST",
                {},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload},
            ),
            (
                "P807_ACTION_ENTRY_ACTION_KIND",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REQUEST_RECONCILIATION,
                {"cmd": command},
                "POST",
                {},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload},
            ),
            (
                "P807_ACTION_ENTRY_REQUEST_FIELDS",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command, "extra": "withheld"},
                "POST",
                {},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload},
            ),
            (
                "P807_ACTION_ENTRY_METHOD",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "GET",
                {},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload},
            ),
            (
                "P807_ACTION_ENTRY_QUERY",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "POST",
                {"limit": "1"},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload},
            ),
            (
                "P807_ACTION_ENTRY_ROUTE",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "POST",
                {},
                {"project_id": PROJECT},
                {"cmd": command, **payload},
            ),
            (
                "P807_ACTION_ENTRY_FORM",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "POST",
                {},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload, "extra": "withheld"},
            ),
            (
                "P807_ACTION_ENTRY_COMMAND",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "POST",
                {},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": "wrong", **payload},
            ),
            (
                "P807_ACTION_ENTRY_EXPECTED_RAW_STATE",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "POST",
                {},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload, "expectedRawState": "wrong"},
            ),
            (
                "P807_ACTION_ENTRY_EXPECTED_VERSION",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "POST",
                {},
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload, "expectedVersion": 4},
            ),
            (
                "P807_ACTION_ENTRY_RUNTIME_SHAPE",
                self.module.IntegrationOperationKind.PUBLISH_ITEM,
                self.module.IntegrationActionKind.REPLAY,
                {"cmd": command},
                "POST",
                object(),
                {"project_id": PROJECT, "integration_operation_id": OPERATION},
                {"cmd": command, **payload},
            ),
        )
        for expected, operation_kind, action_kind, fields, method, query, route, form in cases:
            with self.subTest(expected=expected):
                self.diagnostics.clear()
                self.frappe.local.request.method = method
                self.frappe.local.request.args = query
                self.frappe.flags.npi_route_params = route
                self.frappe.local.form_dict = form
                self.assertFalse(
                    self.module._integration_operations_action_diagnostic_active(
                        trace_id,
                        operation_kind=operation_kind,
                        action_kind=action_kind,
                        expected_raw_state=payload["expectedRawState"],
                        expected_version=payload["expectedVersion"],
                        request_fields=fields,
                    )
                )
                self.assertEqual(
                    self.diagnostics,
                    [
                        {
                            "code": expected,
                            "title": "NPI integration operation action entry predicate failed",
                            "exception_type": "RuntimeError",
                            "trace_id": trace_id,
                        }
                    ],
                )
                self.assertNotIn("withheld", repr(self.diagnostics))

        self.diagnostics.clear()
        self.headers.pop(self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_HEADER)
        self.assertFalse(
            self.module._integration_operations_action_diagnostic_active(
                trace_id,
                operation_kind=self.module.IntegrationOperationKind.PUBLISH_ITEM,
                action_kind=self.module.IntegrationActionKind.REPLAY,
                expected_raw_state=payload["expectedRawState"],
                expected_version=payload["expectedVersion"],
                request_fields={"cmd": command},
            )
        )
        self.assertEqual(self.diagnostics, [])

    def test_fixed_replay_is_csrf_actor_idempotent_and_commits_before_response(self) -> None:
        result = self.call_action()
        self.assertEqual(result, self.action_response)
        self.assertEqual(self.events, ["csrf", "authorize", "action", "commit"])
        call = self.repository.calls[-1]
        self.assertEqual(call[0], "action")
        self.assertEqual(call[1], (UUID(PROJECT),))
        self.assertEqual(call[2]["operation_kind"].value, "publish_item")
        self.assertEqual(call[2]["action_kind"].value, "replay")
        self.assertEqual(call[2]["operation_id"], UUID(OPERATION))
        self.assertEqual(call[2]["expected_raw_state"], "failed_retryable")
        self.assertEqual(call[2]["expected_version"], 3)
        self.assertEqual(call[2]["action_idempotency_key_hash"], "a" * 64)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.frappe.local.response.headers["Idempotency-Replayed"],
            "false",
        )

    def test_exact_replay_is_200_and_each_literal_action_binds_its_kind(self) -> None:
        self.replayed = True
        self.call_action()
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertEqual(
            self.frappe.local.response.headers["Idempotency-Replayed"],
            "true",
        )
        cases = {
            "replay_receive_project_submission": (
                "receive_project_submission",
                "replay",
            ),
            "request_reconciliation_receive_project_submission": (
                "receive_project_submission",
                "request_reconciliation",
            ),
            "replay_publish_item": ("publish_item", "replay"),
            "request_reconciliation_publish_item": (
                "publish_item",
                "request_reconciliation",
            ),
            "replay_publish_mbom": ("publish_mbom", "replay"),
            "request_reconciliation_publish_mbom": (
                "publish_mbom",
                "request_reconciliation",
            ),
            "replay_create_tool_asset": ("create_tool_asset", "replay"),
            "request_reconciliation_create_tool_asset": (
                "create_tool_asset",
                "request_reconciliation",
            ),
            "replay_update_tool_asset": ("update_tool_asset", "replay"),
            "request_reconciliation_update_tool_asset": (
                "update_tool_asset",
                "request_reconciliation",
            ),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.events.clear()
                self.repository.calls.clear()
                self.call_action(getattr(self.module, name))
                call = self.repository.calls[-1]
                self.assertEqual(call[2]["operation_kind"].value, expected[0])
                self.assertEqual(call[2]["action_kind"].value, expected[1])
                self.assertEqual(getattr(self.module, name).allowed_methods, ("POST",))

    def test_default_disabled_external_foreign_and_unknown_input_fail_closed(self) -> None:
        self.frappe.conf = {}
        with self.assertRaises(Exception):
            self.module.get_integration_operations()
        self.frappe.conf = {"npi_p8_07_routes_disabled": False}
        self.external = True
        with self.assertRaises(Exception):
            self.module.get_integration_operations()
        self.external = False
        self.repository.scope = False
        with self.assertRaises(Exception):
            self.module.get_integration_operations()
        self.repository.scope = True
        for values in (
            {"operationKind": "caller_selected"},
            {"sharedState": "success-ish"},
            {"limit": 0},
            {"limit": 201},
            {"cursor": " padded "},
            {"unknown": "hidden"},
        ):
            with self.subTest(values=values), self.assertRaises(Exception):
                self.frappe.local.form_dict = dict(values)
                self.module.get_integration_operations(**values)
        self.assertNotIn("commit", self.events)

    def test_foreign_or_unsafe_response_and_commit_failure_never_report_success(self) -> None:
        self.collection["projectGlobalId"] = "00000000-0000-4000-8000-00000000d799"
        with self.assertRaisesRegex(RuntimeError, "Project"):
            self.module.get_integration_operations()
        self.collection["projectGlobalId"] = PROJECT
        self.detail["operation"]["targetResponse"] = {"secret": "opaque"}
        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            self.module.get_integration_operation()
        self.detail["operation"].pop("targetResponse")
        self.action_response["token"] = "opaque"
        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            self.call_action()
        self.assertNotIn("commit", self.events)
        self.action_response.pop("token")

        def fail_commit():
            self.events.append("commit")
            raise RuntimeError("synthetic commit failure")

        self.frappe.db.commit = fail_commit
        with self.assertRaisesRegex(RuntimeError, "synthetic commit failure"):
            self.call_action()
        self.assertEqual(self.events[-2:], ["commit", "rollback"])

    def test_bff_routes_are_exact_and_no_generic_action_is_exposed(self) -> None:
        source = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        for marker in (
            "_PROJECT_INTEGRATION_OPERATIONS_ROUTE",
            "_PROJECT_INTEGRATION_OPERATION_DLQ_ROUTE",
            "_PROJECT_INTEGRATION_OPERATION_ROUTE",
            "_PROJECT_INTEGRATION_OPERATION_COMMAND_ROUTES",
            "npi_integration.integration_operations.api.get_integration_operations",
            "npi_integration.integration_operations.api.get_integration_operation_dlq",
            "npi_integration.integration_operations.api.get_integration_operation",
        ):
            self.assertIn(marker, source)
        for command in (
            "replay_receive_project_submission",
            "request_reconciliation_receive_project_submission",
            "replay_publish_item",
            "request_reconciliation_publish_item",
            "replay_publish_mbom",
            "request_reconciliation_publish_mbom",
            "replay_create_tool_asset",
            "request_reconciliation_create_tool_asset",
            "replay_update_tool_asset",
            "request_reconciliation_update_tool_asset",
        ):
            self.assertEqual(source.count(command), 1)
        api_source = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/api.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("frappe.enqueue", api_source)
        self.assertNotIn("ignore_permissions", api_source)
        self.assertNotIn("target_doctype", api_source)
        self.assertNotIn("target_method", api_source)


if __name__ == "__main__":
    unittest.main()
