from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextlib import ExitStack
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

ROOT = Path(__file__).resolve().parents[1]

PROJECT = "00000000-0000-4000-8000-00000000a501"
MASTER = "00000000-0000-4000-8000-00000000a502"
TOOLING_SET = "00000000-0000-4000-8000-00000000a503"
ACCEPTANCE = "00000000-0000-4000-8000-00000000a504"
REQUEST = "00000000-0000-4000-8000-00000000a505"
OUTBOX = "00000000-0000-4000-8000-00000000a506"
CREATE_COMMAND = (
    "npi_integration.tool_asset_request_api."
    "create_tool_asset_execution_request"
)


class FakeRepository:
    def __init__(self, owner: "Phase8ToolAssetApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []
        self.outcome = owner.outcome()

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.owner.events.append("authorize")
        return self.scope

    def list_execution_requests(self, *args: object, **kwargs: Any):
        self.calls.append(("list", args, kwargs))
        return {"projectGlobalId": PROJECT, "items": []}

    def execution_request_detail(self, *args: object, **kwargs: Any):
        self.calls.append(("detail", args, kwargs))
        return self.owner.response

    def create_tool_asset_execution_request(self, *args: object, **kwargs: Any):
        self.owner.events.append("create")
        self.calls.append(("create", args, kwargs))
        return self.outcome

    def update_tool_asset_execution_request(self, *args: object, **kwargs: Any):
        self.owner.events.append("update")
        self.calls.append(("update", args, kwargs))
        return self.outcome


class Phase8ToolAssetApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.foundation.errors",
        "npi_core.foundation.security",
        "npi_core.foundation.tracing",
        "npi_core.project.domain",
        "npi_core.request_security",
        "npi_core.tooling.domain",
        "npi_integration.tool_asset_request.diagnostics",
        "npi_integration.tool_asset_request.problems",
        "npi_integration.tool_asset_request.frappe_repository",
        "npi_integration.tool_asset_request_api",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[str] = []
        self.diagnostics: list[dict[str, object]] = []
        self.headers = {
            "Idempotency-Key": "p805-tool-asset-command",
            "X-Request-ID": REQUEST,
        }
        self.response = {
            "requestGlobalId": REQUEST,
            "request": {"globalId": REQUEST, "state": "queued"},
            "dispatchAllowed": True,
            "outboxEventId": OUTBOX,
            "targetIdempotencyKeyHash": "a" * 64,
            "semanticEffectHash": "b" * 64,
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace(
            npi_route_params={
                "project_id": PROJECT,
                "tooling_master_id": MASTER,
                "tooling_set_id": TOOLING_SET,
                "tool_asset_execution_request_id": REQUEST,
            }
        )
        self.frappe.session = types.SimpleNamespace(user="engineer@example.invalid")
        self.frappe.local = types.SimpleNamespace(
            response=types.SimpleNamespace(http_status_code=200),
            request=types.SimpleNamespace(method="GET"),
            form_dict={},
        )
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_hooks = lambda _name: []
        self.frappe.get_attr = lambda _path: None
        self.frappe.db = types.SimpleNamespace(
            commit=lambda: self.events.append("commit"),
            rollback=lambda: self.events.append("rollback"),
        )
        self.frappe.enqueue = lambda *_args, **kwargs: (
            self.events.append("enqueue"),
            self.events.append(str(kwargs["job_id"])),
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist
        sys.modules["frappe"] = self.frappe

        errors = types.ModuleType("npi_core.foundation.errors")

        class NpiProblem(Exception):
            def __init__(self, status: int = 500, code: str = "PROBLEM", title: str = "problem"):
                super().__init__(title)
                self.status = status
                self.code = code
                self.title = title

        class PermissionDenied(NpiProblem):
            pass

        class RequestValidationFailed(NpiProblem):
            pass

        errors.NpiProblem = NpiProblem
        errors.PermissionDenied = PermissionDenied
        errors.RequestValidationFailed = RequestValidationFailed
        sys.modules["npi_core.foundation.errors"] = errors

        api_module = types.ModuleType("npi_core.api")

        def domain_call(handle, *, success_status=200, response_headers=None, **_kwargs):
            result = handle()
            self.frappe.local.response.http_status_code = success_status
            self.frappe.local.response.headers = dict(response_headers or {})
            return result

        api_module.frappe_domain_call = domain_call
        api_module.record_safe_diagnostic = lambda **values: (
            self.events.append("diagnostic"),
            self.diagnostics.append(values),
        )
        sys.modules["npi_core.api"] = api_module

        security = types.ModuleType("npi_core.foundation.security")
        security.Principal = object
        sys.modules["npi_core.foundation.security"] = security
        tracing = types.ModuleType("npi_core.foundation.tracing")
        tracing.current_trace_id = ContextVar(
            "p805-tool-asset-api-trace",
            default="trace-p805-tool-asset-api",
        )
        sys.modules["npi_core.foundation.tracing"] = tracing
        project = types.ModuleType("npi_core.project.domain")
        project.actor_idempotency_key_hash = lambda _actor, _key: "c" * 64
        sys.modules["npi_core.project.domain"] = project

        request_security = types.ModuleType("npi_core.request_security")
        request_security.authenticated_user = lambda: self.frappe.session.user
        request_security.authenticated_principal = lambda actor: types.SimpleNamespace(
            actor=actor,
            is_external=False,
            roles=frozenset({"NPI API User"}),
        )
        request_security.require_csrf_token = lambda: self.events.append("csrf")
        request_security.require_tooling_acceptance_assets_routes_enabled = (
            lambda: self.events.append("routes")
        )
        request_security.response_request_id = lambda: REQUEST
        request_security.reject_unexpected_request_fields = self._reject
        request_security.require_request_fields = self._require
        sys.modules["npi_core.request_security"] = request_security

        tooling = types.ModuleType("npi_core.tooling.domain")
        tooling.ToolingUnavailable = type("ToolingUnavailable", (NpiProblem,), {})
        sys.modules["npi_core.tooling.domain"] = tooling

        self.api = importlib.import_module("npi_integration.tool_asset_request_api")
        self.repository = FakeRepository(self)
        self.api._repository_factory = lambda **_values: self.repository

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def _reject(
        self,
        allowed: frozenset[str],
        fields: dict[str, object],
    ) -> None:
        field_names = set(self.frappe.local.form_dict)
        field_names.update(fields)
        if field_names - set(allowed) - {"cmd"}:
            raise self.api.RequestValidationFailed()

    @staticmethod
    def _require(required: frozenset[str], fields: dict[str, object]) -> None:
        if any(fields.get(field) is None for field in required):
            raise AssertionError("missing field")

    def outcome(self, *, replayed: bool = False, enqueue: bool = True):
        return types.SimpleNamespace(
            response=self.response,
            replayed=replayed,
            should_enqueue=enqueue,
            outbox_event_id=UUID(OUTBOX) if enqueue else None,
            problem=None,
        )

    def payload(self, *, operation: str = "create_tool_asset") -> dict[str, object]:
        acknowledgement = (
            self.api._CREATE_EXECUTION_ACKNOWLEDGEMENT
            if operation == "create_tool_asset"
            else self.api._UPDATE_EXECUTION_ACKNOWLEDGEMENT
        )
        return {
            "acceptanceRevisionGlobalId": ACCEPTANCE,
            "expectedSourceHash": "a" * 64,
            "expectedApprovalHash": "b" * 64,
            "expectedMappingExpectationHash": "c" * 64,
            "expectedProfileSnapshotHash": "d" * 64,
            "acknowledgement": acknowledgement,
        }

    def test_fixed_create_commits_before_post_commit_enqueue(self) -> None:
        result = self.api.create_tool_asset_execution_request(**self.payload())
        self.assertEqual(result, self.response)
        self.assertEqual(self.events[:5], ["routes", "csrf", "authorize", "create", "commit"])
        self.assertEqual(self.events[5], "enqueue")
        call = self.repository.calls[-1]
        self.assertEqual(call[0], "create")
        self.assertEqual([str(value) for value in call[1]], [PROJECT, MASTER, TOOLING_SET])
        self.assertEqual(call[2]["idempotency_key_hash"], "c" * 64)
        self.assertEqual(call[2]["expected_approval_hash"], "b" * 64)

    def test_fixed_update_selects_only_update_operation(self) -> None:
        self.api.update_tool_asset_execution_request(
            **self.payload(operation="update_tool_asset")
        )
        self.assertEqual(self.repository.calls[-1][0], "update")
        self.assertNotIn("create", self.events)

    def test_exact_replay_is_200_and_never_enqueues(self) -> None:
        self.repository.outcome = self.outcome(replayed=True, enqueue=False)
        self.api.create_tool_asset_execution_request(**self.payload())
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertNotIn("enqueue", self.events)

    def test_mock_or_default_disabled_outcome_has_zero_enqueue(self) -> None:
        self.repository.outcome = self.outcome(enqueue=False)
        self.api.create_tool_asset_execution_request(**self.payload())
        self.assertEqual(self.events[-1], "commit")
        self.assertNotIn("enqueue", self.events)

    def test_enqueue_failure_returns_committed_truth_and_one_safe_diagnostic(self) -> None:
        secret = "target-secret-message"

        def fail(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError(secret)

        self.frappe.enqueue = fail
        result = self.api.create_tool_asset_execution_request(**self.payload())
        self.assertEqual(result, self.response)
        self.assertEqual(self.events[-2:], ["commit", "diagnostic"])
        self.assertEqual(len(self.diagnostics), 1)
        self.assertEqual(self.diagnostics[0]["exception_type"], "RuntimeError")
        self.assertNotIn(secret, repr(self.diagnostics))

    def test_commit_failure_rolls_back_and_never_enqueues(self) -> None:
        def fail_commit() -> None:
            self.events.append("commit")
            raise RuntimeError("commit failed")

        self.frappe.db.commit = fail_commit
        with self.assertRaises(RuntimeError):
            self.api.create_tool_asset_execution_request(**self.payload())
        self.assertEqual(self.events[-2:], ["commit", "rollback"])
        self.assertNotIn("enqueue", self.events)

    def test_project_authorization_precedes_secondary_route_parsing(self) -> None:
        self.repository.scope = False
        self.frappe.flags.npi_route_params["tooling_master_id"] = "invalid"
        with self.assertRaises(Exception) as caught:
            self.api.create_tool_asset_execution_request(**self.payload())
        self.assertEqual(
            getattr(caught.exception, "code", None),
            "TOOL_ASSET_EXECUTION_UNAVAILABLE",
        )
        self.assertEqual(self.events[-1], "authorize")

    def test_list_and_detail_preserve_exact_project_master_set_scope(self) -> None:
        self.api.get_tool_asset_execution_requests(
            acceptanceRevisionGlobalId=ACCEPTANCE
        )
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "list")
        self.assertEqual([str(value) for value in args], [PROJECT, MASTER, TOOLING_SET])
        self.assertEqual(str(values["acceptance_revision_id"]), ACCEPTANCE)
        self.api.get_tool_asset_execution_request()
        self.assertEqual(self.repository.calls[-1][0], "detail")
        self.assertEqual(str(self.repository.calls[-1][1][-1]), REQUEST)

    def test_collection_normalizes_only_its_named_frappe_query_field(self) -> None:
        self.assertEqual(
            self.api._EXECUTION_LIST_FIELDS,
            frozenset({"acceptanceRevisionGlobalId"}),
        )
        command = (
            "npi_integration.tool_asset_request_api."
            "get_tool_asset_execution_requests"
        )
        self.frappe.local.form_dict = {
            "cmd": command,
            "acceptanceRevisionGlobalId": ACCEPTANCE,
        }
        self.api.get_tool_asset_execution_requests(
            acceptanceRevisionGlobalId=ACCEPTANCE,
            cmd=command,
        )
        self.assertEqual(self.repository.calls[-1][0], "list")

        self.api._execution_query_context(
            {
                "cmd": command,
                "acceptanceRevisionGlobalId": ACCEPTANCE,
            },
            allowed_fields=self.api._EXECUTION_LIST_FIELDS,
        )

        for form_fields, keyword_fields in (
            (
                {
                    "cmd": command,
                    "acceptanceRevisionGlobalId": ACCEPTANCE,
                    "unexpected": "wrong",
                },
                {},
            ),
            (
                {
                    "cmd": command,
                    "acceptanceRevisionGlobalId": ACCEPTANCE,
                },
                {"unexpected": "wrong"},
            ),
            (
                {
                    "cmd": command,
                    "acceptanceRevisionGlobalID": ACCEPTANCE,
                },
                {},
            ),
        ):
            with self.subTest(
                form_fields=tuple(form_fields),
                keyword_fields=tuple(keyword_fields),
            ):
                self.frappe.local.form_dict = form_fields
                with self.assertRaises(self.api.RequestValidationFailed):
                    self.api.get_tool_asset_execution_requests(
                        acceptanceRevisionGlobalId=ACCEPTANCE,
                        **keyword_fields,
                    )

    def test_detail_keeps_query_fields_closed(self) -> None:
        self.frappe.local.form_dict = {
            "cmd": (
                "npi_integration.tool_asset_request_api."
                "get_tool_asset_execution_request"
            ),
            "acceptanceRevisionGlobalId": ACCEPTANCE,
        }
        with self.assertRaises(self.api.RequestValidationFailed):
            self.api.get_tool_asset_execution_request()

    def test_command_context_diagnostic_is_exact_scope_same_exception_and_restored(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        source_text = (
            ROOT
            / "apps/npi_integration/npi_integration/tool_asset_request_api.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            source_text.count('"P805_TOOL_ASSET_CONTEXT_QUERY_PARSE"'),
            1,
        )
        api_codes = (
            "P805_TOOL_ASSET_CONTEXT_ROUTES_ENABLED",
            "P805_TOOL_ASSET_CONTEXT_AUTHENTICATED_USER",
            "P805_TOOL_ASSET_CONTEXT_PRINCIPAL_RESOLVE",
            "P805_TOOL_ASSET_CONTEXT_PRINCIPAL_INTERNAL",
            "P805_TOOL_ASSET_CONTEXT_REQUEST_ID",
            "P805_TOOL_ASSET_CONTEXT_REPOSITORY_INIT",
            "P805_TOOL_ASSET_CONTEXT_PROJECT_ROUTE",
            "P805_TOOL_ASSET_CONTEXT_PROJECT_AUTHORIZE",
            "P805_TOOL_ASSET_CONTEXT_REQUEST_FIELDS",
            "P805_TOOL_ASSET_CONTEXT_MASTER_ROUTE",
            "P805_TOOL_ASSET_CONTEXT_SET_ROUTE",
            "P805_TOOL_ASSET_CONTEXT_REPOSITORY_LIST",
            "P805_TOOL_ASSET_CONTEXT_RESPONSE_AVAILABLE",
            "P805_TOOL_ASSET_CONTEXT_RESPONSE_SERIALIZE",
        )
        for code in api_codes:
            with self.subTest(code=code):
                self.assertEqual(source_text.count(f'"{code}"'), 1)
                self.assertIn(code, diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_CODES)
        trace_id = "trace-" + "a" * 32
        secret = "private-query-value"
        original = RuntimeError(secret)
        self.headers[diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER] = (
            diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
        )
        self.frappe.local.request.args = {
            "acceptanceRevisionGlobalId": ACCEPTANCE,
        }
        token = self.api.current_trace_id.set(trace_id)
        try:
            with patch.object(
                self.api,
                "_execution_query_context",
                return_value=(
                    REQUEST,
                    self.repository,
                    UUID(PROJECT),
                    UUID(MASTER),
                    UUID(TOOLING_SET),
                ),
            ), patch.object(self.api, "_uuid", side_effect=original):
                with self.assertRaises(RuntimeError) as caught:
                    self.api.get_tool_asset_execution_requests(
                        acceptanceRevisionGlobalId=ACCEPTANCE
                    )
            self.assertIs(caught.exception, original)
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(len(self.diagnostics), 1)
        self.assertEqual(
            {
                key: self.diagnostics[0][key]
                for key in ("code", "exception_type", "trace_id")
            },
            {
                "code": "P805_TOOL_ASSET_CONTEXT_QUERY_PARSE",
                "exception_type": "RuntimeError",
                "trace_id": trace_id,
            },
        )
        self.assertNotIn(secret, repr(self.diagnostics))
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                "npi_p805_tool_asset_context_diagnostic",
            )
        )

    def test_unstaged_command_context_boundaries_record_innermost_same_exception_without_writes(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        trace_id = "trace-" + "d" * 32
        secret = "private-command-context-boundary"
        self.headers[diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER] = (
            diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
        )
        self.frappe.local.request.method = "GET"
        self.frappe.local.request.args = {
            "acceptanceRevisionGlobalId": ACCEPTANCE,
        }

        def route_failure(target: str, error: Exception):
            values = {
                "project_id": UUID(PROJECT),
                "tooling_master_id": UUID(MASTER),
                "tooling_set_id": UUID(TOOLING_SET),
            }

            def resolve(name: str):
                if name == target:
                    raise error
                return values[name]

            return resolve

        original = RuntimeError(secret)
        cases = (
            (
                "P805_TOOL_ASSET_CONTEXT_ROUTES_ENABLED",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.api,
                        "require_tooling_acceptance_assets_routes_enabled",
                        side_effect=original,
                    )
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_AUTHENTICATED_USER",
                lambda stack: stack.enter_context(
                    patch.object(self.api, "authenticated_user", side_effect=original)
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_PRINCIPAL_RESOLVE",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.api, "authenticated_principal", side_effect=original
                    )
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_PRINCIPAL_INTERNAL",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.api,
                        "authenticated_principal",
                        return_value=types.SimpleNamespace(is_external=True),
                    )
                ),
                None,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_REQUEST_ID",
                lambda stack: stack.enter_context(
                    patch.object(self.api, "_request_id", side_effect=original)
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_REPOSITORY_INIT",
                lambda stack: stack.enter_context(
                    patch.object(self.api, "_new_repository", side_effect=original)
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_PROJECT_ROUTE",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.api,
                        "_opaque_route_uuid",
                        side_effect=route_failure("project_id", original),
                    )
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_PROJECT_AUTHORIZE",
                lambda stack: stack.enter_context(
                    patch.object(self.repository, "authorize_scope", side_effect=original)
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_REQUEST_FIELDS",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.api,
                        "reject_unexpected_request_fields",
                        side_effect=original,
                    )
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_MASTER_ROUTE",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.api,
                        "_opaque_route_uuid",
                        side_effect=route_failure("tooling_master_id", original),
                    )
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_SET_ROUTE",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.api,
                        "_opaque_route_uuid",
                        side_effect=route_failure("tooling_set_id", original),
                    )
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_REPOSITORY_LIST",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.repository,
                        "list_execution_requests",
                        side_effect=original,
                    )
                ),
                original,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_RESPONSE_AVAILABLE",
                lambda stack: stack.enter_context(
                    patch.object(
                        self.repository, "list_execution_requests", return_value=None
                    )
                ),
                None,
            ),
            (
                "P805_TOOL_ASSET_CONTEXT_RESPONSE_SERIALIZE",
                lambda stack: stack.enter_context(
                    patch.object(self.api, "_execution_response", side_effect=original)
                ),
                original,
            ),
        )
        for code, install, expected in cases:
            with self.subTest(code=code):
                self.diagnostics.clear()
                self.events.clear()
                token = self.api.current_trace_id.set(trace_id)
                try:
                    with ExitStack() as stack:
                        install(stack)
                        with self.assertRaises(Exception) as caught:
                            self.api.get_tool_asset_execution_requests(
                                acceptanceRevisionGlobalId=ACCEPTANCE
                            )
                finally:
                    self.api.current_trace_id.reset(token)
                if expected is not None:
                    self.assertIs(caught.exception, expected)
                self.assertEqual(
                    [record["code"] for record in self.diagnostics],
                    [code],
                )
                self.assertNotIn(secret, repr(self.diagnostics))
                self.assertNotIn("commit", self.events)
                self.assertNotIn("enqueue", self.events)
                self.assertNotIn("create", self.events)
                self.assertNotIn("update", self.events)
                self.assertFalse(
                    hasattr(
                        self.frappe.flags,
                        "npi_p805_tool_asset_context_diagnostic",
                    )
                )

        for name, scope, candidate_trace, method in (
            ("missing", None, trace_id, "GET"),
            ("wrong", "wrong-scope", trace_id, "GET"),
            (
                "invalid-trace",
                diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE,
                "trace-invalid",
                "GET",
            ),
            (
                "wrong-method",
                diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE,
                trace_id,
                "POST",
            ),
        ):
            with self.subTest(name=name):
                self.diagnostics.clear()
                if scope is None:
                    self.headers.pop(
                        diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER,
                        None,
                    )
                else:
                    self.headers[
                        diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER
                    ] = scope
                self.frappe.local.request.method = method
                self.frappe.local.request.args = {
                    "acceptanceRevisionGlobalId": ACCEPTANCE,
                }
                token = self.api.current_trace_id.set(candidate_trace)
                try:
                    with patch.object(
                        self.api,
                        "_execution_query_context",
                        return_value=(
                            REQUEST,
                            self.repository,
                            UUID(PROJECT),
                            UUID(MASTER),
                            UUID(TOOLING_SET),
                        ),
                    ), patch.object(self.api, "_uuid", side_effect=original):
                        with self.assertRaises(RuntimeError) as caught:
                            self.api.get_tool_asset_execution_requests(
                                acceptanceRevisionGlobalId=ACCEPTANCE
                            )
                    self.assertIs(caught.exception, original)
                finally:
                    self.api.current_trace_id.reset(token)
                self.assertEqual(self.diagnostics, [])
                self.assertFalse(
                    hasattr(
                        self.frappe.flags,
                        "npi_p805_tool_asset_context_diagnostic",
                    )
                )

        self.headers[diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER] = (
            diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
        )
        self.frappe.local.request.method = "GET"
        for query in (
            {},
            {"acceptanceRevisionGlobalId": "wrong"},
            {
                "acceptanceRevisionGlobalId": ACCEPTANCE,
                "extra": "wrong",
            },
        ):
            with self.subTest(query=query):
                self.diagnostics.clear()
                self.frappe.local.request.args = query
                token = self.api.current_trace_id.set(trace_id)
                try:
                    with patch.object(
                        self.api,
                        "_execution_query_context",
                        return_value=(
                            REQUEST,
                            self.repository,
                            UUID(PROJECT),
                            UUID(MASTER),
                            UUID(TOOLING_SET),
                        ),
                    ), patch.object(self.api, "_uuid", side_effect=original):
                        with self.assertRaises(RuntimeError) as caught:
                            self.api.get_tool_asset_execution_requests(
                                acceptanceRevisionGlobalId=ACCEPTANCE
                            )
                    self.assertIs(caught.exception, original)
                finally:
                    self.api.current_trace_id.reset(token)
                self.assertEqual(self.diagnostics, [])

        self.frappe.local.request.args = {
            "acceptanceRevisionGlobalId": ACCEPTANCE,
        }
        self.diagnostics.clear()
        token = self.api.current_trace_id.set(trace_id)
        try:
            inner = RuntimeError(secret)
            with self.assertRaises(RuntimeError) as caught:
                with diagnostics.tool_asset_context_diagnostics(
                    trace_id,
                    ACCEPTANCE,
                ), diagnostics.tool_asset_context_step(
                    "P805_TOOL_ASSET_CONTEXT_CREATE_SOURCE"
                ):
                    with diagnostics.tool_asset_context_step(
                        "P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING"
                    ):
                        raise inner
            self.assertIs(caught.exception, inner)
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(
            [record["code"] for record in self.diagnostics],
            ["P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING"],
        )
        self.assertNotIn(secret, repr(self.diagnostics))
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                "npi_p805_tool_asset_context_diagnostic",
            )
        )

    def test_command_context_diagnostic_preserves_success_response(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        without_scope = self.api.get_tool_asset_execution_requests(
            acceptanceRevisionGlobalId=ACCEPTANCE
        )
        self.headers[diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER] = (
            diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
        )
        self.frappe.local.request.args = {
            "acceptanceRevisionGlobalId": ACCEPTANCE,
        }
        token = self.api.current_trace_id.set("trace-" + "b" * 32)
        try:
            with_scope = self.api.get_tool_asset_execution_requests(
                acceptanceRevisionGlobalId=ACCEPTANCE
            )
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(with_scope, without_scope)
        self.assertEqual(self.diagnostics, [])
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                "npi_p805_tool_asset_context_diagnostic",
            )
        )

    def test_create_response_diagnostic_is_exact_same_exception_and_restored(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/tool_asset_request_api.py"
        ).read_text(encoding="utf-8")
        api_codes = (
            "P805_TOOL_ASSET_CREATE_ROUTES_ENABLED",
            "P805_TOOL_ASSET_CREATE_AUTHENTICATED_USER",
            "P805_TOOL_ASSET_CREATE_CSRF",
            "P805_TOOL_ASSET_CREATE_PRINCIPAL_RESOLVE",
            "P805_TOOL_ASSET_CREATE_PRINCIPAL_INTERNAL",
            "P805_TOOL_ASSET_CREATE_REQUEST_ID",
            "P805_TOOL_ASSET_CREATE_REPOSITORY_INIT",
            "P805_TOOL_ASSET_CREATE_PROJECT_ROUTE",
            "P805_TOOL_ASSET_CREATE_PROJECT_AUTHORIZE",
            "P805_TOOL_ASSET_CREATE_REQUEST_FIELDS",
            "P805_TOOL_ASSET_CREATE_INPUT_PARSE",
            "P805_TOOL_ASSET_CREATE_OPERATION_SELECT",
            "P805_TOOL_ASSET_CREATE_REPOSITORY_COMMAND",
            "P805_TOOL_ASSET_CREATE_OUTCOME_VALIDATE",
            "P805_TOOL_ASSET_CREATE_COMMIT",
            "P805_TOOL_ASSET_CREATE_PROBLEM_RAISE",
            "P805_TOOL_ASSET_CREATE_RESPONSE_SERIALIZE",
            "P805_TOOL_ASSET_CREATE_OUTBOX_VALIDATE",
            "P805_TOOL_ASSET_CREATE_DOMAIN_CALL",
        )
        for code in api_codes:
            with self.subTest(code=code):
                self.assertEqual(source.count(f'"{code}"'), 1)
                self.assertIn(
                    code,
                    diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES,
                )

        trace_id = "trace-" + "a" * 32
        secret = "private-create-boundary"
        original = RuntimeError(secret)
        self.headers[diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER] = (
            diagnostics.TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE
        )
        self.headers["X-Trace-ID"] = trace_id
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = {}
        self.frappe.local.form_dict = {
            **self.payload(),
            "cmd": CREATE_COMMAND,
        }
        self.frappe.flags.npi_route_params = {
            "project_id": PROJECT,
            "tooling_master_id": MASTER,
            "tooling_set_id": TOOLING_SET,
        }
        token = self.api.current_trace_id.set("trace-" + "0" * 32)
        try:
            with patch.object(
                self.api,
                "authenticated_user",
                side_effect=original,
            ):
                with self.assertRaises(RuntimeError) as caught:
                    self.api.create_tool_asset_execution_request(
                        **self.payload(),
                        cmd=CREATE_COMMAND,
                    )
            self.assertIs(caught.exception, original)
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(
            [record["code"] for record in self.diagnostics],
            ["P805_TOOL_ASSET_CREATE_AUTHENTICATED_USER"],
        )
        self.assertEqual(self.diagnostics[0]["exception_type"], "RuntimeError")
        self.assertEqual(self.diagnostics[0]["trace_id"], trace_id)
        self.assertNotIn(secret, repr(self.diagnostics))
        self.assertNotIn("commit", self.events)
        self.assertNotIn("enqueue", self.events)
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                "npi_p805_tool_asset_create_response_diagnostic",
            )
        )

    def test_create_response_scope_fail_closed_and_innermost_wins(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        trace_id = "trace-" + "b" * 32
        secret = "private-create-scope"
        original = RuntimeError(secret)
        self.frappe.local.request.args = {}
        exact_route = {
            "project_id": PROJECT,
            "tooling_master_id": MASTER,
            "tooling_set_id": TOOLING_SET,
        }
        exact_scope = diagnostics.TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE
        for name, scope, method, request_trace, route, query, command in (
            ("missing", None, "POST", trace_id, exact_route, {}, CREATE_COMMAND),
            ("old-response", diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_SCOPE, "POST", trace_id, exact_route, {}, CREATE_COMMAND),
            ("old-http", diagnostics.TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTIC_SCOPE, "POST", trace_id, exact_route, {}, CREATE_COMMAND),
            ("wrong", "wrong-scope", "POST", trace_id, exact_route, {}, CREATE_COMMAND),
            ("method", exact_scope, "GET", trace_id, exact_route, {}, CREATE_COMMAND),
            ("trace-missing", exact_scope, "POST", None, exact_route, {}, CREATE_COMMAND),
            ("trace-invalid", exact_scope, "POST", "trace-invalid", exact_route, {}, CREATE_COMMAND),
            ("route", exact_scope, "POST", trace_id, {**exact_route, "extra": "wrong"}, {}, CREATE_COMMAND),
            ("route-value", exact_scope, "POST", trace_id, {**exact_route, "tooling_set_id": "wrong"}, {}, CREATE_COMMAND),
            ("query", exact_scope, "POST", trace_id, exact_route, {"extra": "wrong"}, CREATE_COMMAND),
            ("cmd-missing", exact_scope, "POST", trace_id, exact_route, {}, None),
            ("cmd-wrong", exact_scope, "POST", trace_id, exact_route, {}, "wrong"),
        ):
            with self.subTest(name=name):
                self.diagnostics.clear()
                if scope is None:
                    self.headers.pop(
                        diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER,
                        None,
                    )
                else:
                    self.headers[
                        diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER
                    ] = scope
                self.frappe.local.request.method = method
                self.frappe.local.request.args = query
                self.frappe.flags.npi_route_params = route
                if request_trace is None:
                    self.headers.pop("X-Trace-ID", None)
                else:
                    self.headers["X-Trace-ID"] = request_trace
                self.frappe.local.form_dict = {
                    **self.payload(),
                    **({"cmd": command} if command is not None else {}),
                }
                token = self.api.current_trace_id.set("trace-" + "9" * 32)
                try:
                    with patch.object(
                        self.api,
                        "authenticated_user",
                        side_effect=original,
                    ):
                        with self.assertRaises(RuntimeError) as caught:
                            kwargs = self.payload()
                            if command is not None:
                                kwargs["cmd"] = command
                            self.api.create_tool_asset_execution_request(**kwargs)
                    self.assertIs(caught.exception, original)
                finally:
                    self.api.current_trace_id.reset(token)
                self.assertEqual(self.diagnostics, [])

        self.diagnostics.clear()
        self.headers[diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER] = (
            exact_scope
        )
        self.headers["X-Trace-ID"] = trace_id
        idempotency_key = self.headers.pop("Idempotency-Key")
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = {}
        self.frappe.flags.npi_route_params = exact_route
        self.frappe.local.form_dict = {
            **self.payload(),
            "cmd": CREATE_COMMAND,
        }
        token = self.api.current_trace_id.set(trace_id)
        try:
            with patch.object(
                self.api,
                "authenticated_user",
                side_effect=original,
            ):
                with self.assertRaises(RuntimeError) as caught:
                    self.api.create_tool_asset_execution_request(
                        **self.payload(),
                        cmd=CREATE_COMMAND,
                    )
            self.assertIs(caught.exception, original)
        finally:
            self.api.current_trace_id.reset(token)
            self.headers["Idempotency-Key"] = idempotency_key
        self.assertEqual(self.diagnostics, [])

        self.diagnostics.clear()
        self.headers[diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER] = (
            exact_scope
        )
        self.headers["X-Trace-ID"] = trace_id
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = {}
        self.frappe.flags.npi_route_params = exact_route
        self.frappe.local.form_dict = {
            **self.payload(),
            "cmd": CREATE_COMMAND,
            "unknownBusinessField": "private-extra-value",
        }
        token = self.api.current_trace_id.set(trace_id)
        try:
            with self.assertRaises(self.api.RequestValidationFailed):
                self.api.create_tool_asset_execution_request(
                    **self.payload(),
                    cmd=CREATE_COMMAND,
                    unknownBusinessField="private-extra-value",
                )
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(self.diagnostics, [])
        self.assertNotIn("private-extra-value", repr(self.diagnostics))

        self.diagnostics.clear()
        self.headers[diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER] = (
            diagnostics.TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE
        )
        self.headers["X-Trace-ID"] = trace_id
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = {}
        self.frappe.flags.npi_route_params = exact_route
        token = self.api.current_trace_id.set(trace_id)
        try:
            with patch.object(
                self.api,
                "authenticated_user",
                side_effect=original,
            ):
                with self.assertRaises(RuntimeError) as caught:
                    self.api.update_tool_asset_execution_request(
                        **self.payload(operation="update_tool_asset"),
                        cmd=CREATE_COMMAND,
                    )
            self.assertIs(caught.exception, original)
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(self.diagnostics, [])

        self.diagnostics.clear()
        self.headers[diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER] = (
            diagnostics.TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE
        )
        self.headers["X-Trace-ID"] = trace_id
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = {}
        self.frappe.flags.npi_route_params = exact_route
        with self.assertRaises(RuntimeError) as caught:
            with diagnostics.tool_asset_create_response_diagnostics(
                None,
                "create_tool_asset",
                {**self.payload(), "cmd": CREATE_COMMAND},
            ), diagnostics.tool_asset_create_response_step(
                "P805_TOOL_ASSET_CREATE_DOMAIN_CALL"
            ):
                with diagnostics.tool_asset_create_response_step(
                    "P805_TOOL_ASSET_CREATE_INPUT_PARSE"
                ):
                    raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(
            [record["code"] for record in self.diagnostics],
            ["P805_TOOL_ASSET_CREATE_INPUT_PARSE"],
        )
        self.assertNotIn(secret, repr(self.diagnostics))

    def test_create_response_diagnostic_preserves_success_and_enqueue_boundary(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        without_scope = self.api.create_tool_asset_execution_request(**self.payload())
        self.events.clear()
        self.diagnostics.clear()
        self.headers[diagnostics.TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER] = (
            diagnostics.TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE
        )
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = {}
        self.frappe.flags.npi_route_params = {
            "project_id": PROJECT,
            "tooling_master_id": MASTER,
            "tooling_set_id": TOOLING_SET,
        }
        self.frappe.local.form_dict = {
            **self.payload(),
            "cmd": CREATE_COMMAND,
        }
        self.headers["X-Trace-ID"] = "trace-" + "c" * 32
        token = self.api.current_trace_id.set("trace-" + "0" * 32)
        try:
            with_scope = self.api.create_tool_asset_execution_request(
                **self.payload(),
                cmd=CREATE_COMMAND,
            )
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(with_scope, without_scope)
        self.assertEqual(self.diagnostics, [])
        self.assertEqual(
            self.events[-2:],
            ["enqueue", f"tool-asset-execution-{OUTBOX}"],
        )

        self.events.clear()
        self.diagnostics.clear()
        self.frappe.enqueue = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("private-enqueue-message")
        )
        self.headers["X-Trace-ID"] = "trace-" + "d" * 32
        token = self.api.current_trace_id.set("trace-" + "0" * 32)
        try:
            result = self.api.create_tool_asset_execution_request(
                **self.payload(),
                cmd=CREATE_COMMAND,
            )
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(result, without_scope)
        self.assertEqual(
            [record["code"] for record in self.diagnostics],
            ["TOOL_ASSET_EXECUTION_ENQUEUE_FAILED"],
        )
        self.assertNotIn("private-enqueue-message", repr(self.diagnostics))

    def test_profile_resolver_is_default_off_and_ambiguous_hooks_fail_closed(self) -> None:
        self.assertIsNone(self.api._configured_execution_profile("tenant", UUID(PROJECT)))
        self.frappe.get_hooks = lambda _name: ["a.resolver", "b.resolver"]
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            self.api._configured_execution_profile("tenant", UUID(PROJECT))

    def test_external_principal_cannot_read_execution_collection_or_detail(self) -> None:
        self.api.authenticated_principal = lambda actor: types.SimpleNamespace(
            actor=actor,
            is_external=True,
            roles=frozenset(),
        )
        for operation in (
            self.api.get_tool_asset_execution_requests,
            self.api.get_tool_asset_execution_request,
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(Exception) as caught:
                    operation()
                self.assertIsInstance(caught.exception, self.api.PermissionDenied)
        self.assertFalse(self.repository.calls)


if __name__ == "__main__":
    unittest.main()
