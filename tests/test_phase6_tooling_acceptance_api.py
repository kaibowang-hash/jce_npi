from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from typing import Any
from unittest.mock import patch


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
MASTER_ID = "0878087f-6192-4e40-862d-05e0a5927638"
SET_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
ACCEPTANCE_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
ASSET_REQUEST_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
REQUEST_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"
HASH = "a" * 64
ACKNOWLEDGEMENT = (
    "I confirm this only validates a local Mock draft. It does not approve "
    "Tooling, contact ERPNext or create an Asset."
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
    def __init__(self, user_types: dict[str, str]) -> None:
        self.user_types = user_types
        self.rollback_count = 0

    def get_value(self, doctype: str, name: str, fieldname: str):
        if doctype == "User" and fieldname == "user_type":
            return self.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockRepository:
    def __init__(self, owner: "Phase6ToolingAcceptanceApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.replayed = False
        self.error: Exception | None = None
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def acceptance_asset_context(self, *args: object, **kwargs: Any):
        return self._query("context", args, kwargs, self.owner.context_response)

    def list_asset_requests(self, *args: object, **kwargs: Any):
        return self._query("list", args, kwargs, self.owner.list_response)

    def asset_request_detail(self, *args: object, **kwargs: Any):
        return self._query("detail", args, kwargs, self.owner.request_response)

    def create_asset_request(self, *args: object, **kwargs: Any):
        self.calls.append(("create", args, kwargs))
        if self.error is not None:
            raise self.error
        return types.SimpleNamespace(
            response=copy.deepcopy(self.owner.request_response),
            replayed=self.replayed,
        )

    def _query(self, name: str, args, kwargs, response):
        self.calls.append((name, args, kwargs))
        return copy.deepcopy(response) if self.scope else None


class Phase6ToolingAcceptanceApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_integration.tool_asset_request.diagnostics",
        "npi_integration.tool_asset_request_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p6-tool-asset-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase6-tool-asset-api",
        }
        self.roles = {
            "admin@example.invalid": ["System Manager"],
            "member@example.invalid": ["NPI API User"],
            "external@example.invalid": ["System Manager"],
        }
        user_types = {
            "admin@example.invalid": "System User",
            "member@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="admin@example.invalid")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p4_05_routes_disabled=False,
            npi_p5_01_routes_disabled=False,
            npi_p5_02_routes_disabled=False,
            npi_p5_03_routes_disabled=False,
            npi_p5_04_routes_disabled=False,
            npi_p5_05_routes_disabled=False,
            npi_p5_06_routes_disabled=False,
            npi_p6_01_routes_disabled=False,
            npi_p6_02_routes_disabled=False,
            npi_p6_03_routes_disabled=False,
            npi_p6_04_routes_disabled=False,
            npi_p6_05_routes_disabled=False,
            npi_p6_06_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "tooling_master_id": MASTER_ID,
                "tooling_set_id": SET_ID,
                "asset_request_id": ASSET_REQUEST_ID,
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
        self.frappe.db = StubDatabase(user_types)
        self.frappe.log_error = lambda **_values: None
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda *_args, **_kwargs: None
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

        self.api = importlib.import_module("npi_integration.tool_asset_request_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.api._repository_factory = lambda **_values: self.repository
        self.request_response = {
            "globalId": ASSET_REQUEST_ID,
            "payloadHash": HASH,
            "targetMode": "mock",
            "requestState": "draft",
            "dispatchState": "prohibited",
            "targetResultState": "not_requested",
        }
        self.list_response = {
            "projectGlobalId": PROJECT_ID,
            "toolingMasterGlobalId": MASTER_ID,
            "items": [],
        }
        self.context_response = {
            "projectGlobalId": PROJECT_ID,
            "toolingMasterGlobalId": MASTER_ID,
            "acceptanceRevisions": [],
            "assetRequests": [],
        }

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def payload() -> dict[str, object]:
        return {
            "targetMode": "mock",
            "acceptanceRevisionGlobalId": ACCEPTANCE_ID,
            "acceptanceVersion": 1,
            "acceptanceSnapshotHash": HASH,
            "expectedToolingMasterSnapshotHash": HASH,
            "expectedToolingSetSnapshotHash": HASH,
            "expectedBindingSnapshotHash": HASH,
            "expectedToolingRevisionNumber": 1,
            "expectedToolingRevisionSnapshotHash": HASH,
            "acknowledgement": ACKNOWLEDGEMENT,
        }

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def test_queries_authorize_project_and_master_before_exact_resolution(self) -> None:
        for function, expected in (
            (self.api.get_tooling_acceptance_assets, "context"),
            (self.api.get_tool_asset_requests, "list"),
            (self.api.get_tool_asset_request, "detail"),
        ):
            with self.subTest(expected=expected):
                self.repository.calls.clear()
                self.call(function)
                self.assertEqual(self.repository.calls[0][0], "authorize")
                self.assertEqual(
                    [str(value) for value in self.repository.calls[0][1]],
                    [PROJECT_ID, MASTER_ID],
                )
                self.assertEqual(self.repository.calls[1][0], expected)

        self.repository.calls.clear()
        self.repository.scope = False
        result = self.call(self.api.get_tool_asset_request)
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual([call[0] for call in self.repository.calls], ["authorize"])

    def test_create_is_mock_only_closed_actor_bound_and_replay_correlated(self) -> None:
        result = self.call(self.api.create_tool_asset_request, self.payload())
        self.assertEqual(result, self.request_response)
        authorize, create = self.repository.calls
        self.assertEqual(authorize[0], "authorize")
        self.assertEqual(authorize[2], {"administer": True})
        self.assertEqual(create[0], "create")
        self.assertEqual(
            [str(value) for value in create[1]],
            [PROJECT_ID, MASTER_ID, SET_ID],
        )
        self.assertEqual(len(create[2]["idempotency_key_hash"]), 64)
        self.assertNotIn("acknowledgement", create[2])
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "false",
        )

        self.repository.calls.clear()
        self.repository.replayed = True
        self.call(self.api.create_tool_asset_request, self.payload())
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )

        for field, value in (
            ("targetMode", "sandbox"),
            ("acknowledgement", "contact ERPNext"),
            ("operation", "arbitrary"),
        ):
            with self.subTest(field=field):
                payload = self.payload()
                payload[field] = value
                result = self.call(self.api.create_tool_asset_request, payload)
                self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_command_authorization_precedes_body_validation_and_is_internal_only(self) -> None:
        self.repository.scope = False
        result = self.call(
            self.api.create_tool_asset_request,
            {"operation": "protected"},
        )
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual([call[0] for call in self.repository.calls], ["authorize"])

        self.repository.scope = True
        self.repository.calls.clear()
        self.frappe.session.user = "member@example.invalid"
        result = self.call(self.api.create_tool_asset_request, self.payload())
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        self.assertFalse(self.repository.calls)

        self.frappe.session.user = "external@example.invalid"
        result = self.call(self.api.create_tool_asset_request, self.payload())
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        self.assertFalse(self.repository.calls)

    def test_unexpected_write_failure_rolls_back_and_never_reports_success(self) -> None:
        self.repository.error = RuntimeError("synthetic persistence failure")
        result = self.call(self.api.create_tool_asset_request, self.payload())
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(self.frappe.local.response.http_status_code, 500)
        self.assertEqual(self.frappe.db.rollback_count, 1)
        self.assertNotEqual(result, self.request_response)

    def test_asset_create_diagnostic_is_exact_scoped_response_neutral_and_restored(self) -> None:
        diagnostic = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        trace_id = "trace-" + "a" * 32
        self.headers["X-Trace-ID"] = trace_id
        self.repository.create_asset_request = lambda *_args, **_kwargs: (
            types.SimpleNamespace(
                response=copy.deepcopy(self.request_response),
                replayed="private business value",
            )
        )
        self.headers[diagnostic.P606_ASSET_CREATE_DIAGNOSTIC_HEADER] = (
            diagnostic.P606_ASSET_CREATE_DIAGNOSTIC_SCOPE
        )
        token = self.api.current_trace_id.set(trace_id)
        records: list[dict[str, object]] = []
        try:
            with patch(
                "npi_core.api.record_safe_diagnostic",
                side_effect=lambda **values: records.append(values),
            ):
                result = self.call(self.api.create_tool_asset_request, self.payload())
        finally:
            self.api.current_trace_id.reset(token)
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        stage_records = [
            record
            for record in records
            if str(record.get("code", "")).startswith("P805_P606_ASSET_")
        ]
        self.assertEqual(
            stage_records,
            [
                {
                    "code": "P805_P606_ASSET_OUTCOME_VALIDATE",
                    "title": "NPI predecessor Tool Asset create stage failed",
                    "exception_type": "RuntimeError",
                    "trace_id": trace_id,
                }
            ],
        )
        self.assertNotIn("private business value", repr(records))
        self.assertFalse(
            hasattr(self.frappe.flags, "npi_p805_p606_asset_create_diagnostic")
        )

        for scope, candidate_trace in (
            (None, trace_id),
            ("wrong-scope", trace_id),
            (diagnostic.P606_ASSET_CREATE_DIAGNOSTIC_SCOPE, "invalid-trace"),
        ):
            with self.subTest(scope=scope, trace=candidate_trace):
                if scope is None:
                    self.headers.pop(
                        diagnostic.P606_ASSET_CREATE_DIAGNOSTIC_HEADER, None
                    )
                else:
                    self.headers[
                        diagnostic.P606_ASSET_CREATE_DIAGNOSTIC_HEADER
                    ] = scope
                self.headers["X-Trace-ID"] = candidate_trace
                records.clear()
                token = self.api.current_trace_id.set(candidate_trace)
                try:
                    with patch(
                        "npi_core.api.record_safe_diagnostic",
                        side_effect=lambda **values: records.append(values),
                    ):
                        retry = self.call(
                            self.api.create_tool_asset_request, self.payload()
                        )
                finally:
                    self.api.current_trace_id.reset(token)
                self.assertEqual(
                    {key: value for key, value in retry.items() if key != "traceId"},
                    {key: value for key, value in result.items() if key != "traceId"},
                )
                self.assertFalse(
                    any(
                        str(record.get("code", "")).startswith(
                            "P805_P606_ASSET_"
                        )
                        for record in records
                    )
                )

    def test_asset_create_diagnostic_records_innermost_once_and_rethrows_same_object(self) -> None:
        diagnostic = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        trace_id = "trace-" + "b" * 32
        self.headers[diagnostic.P606_ASSET_CREATE_DIAGNOSTIC_HEADER] = (
            diagnostic.P606_ASSET_CREATE_DIAGNOSTIC_SCOPE
        )
        records: list[dict[str, object]] = []
        original = ValueError("private request identity")
        with patch(
            "npi_core.api.record_safe_diagnostic",
            side_effect=lambda **values: records.append(values),
        ):
            with self.assertRaises(ValueError) as raised:
                with diagnostic.p606_asset_create_diagnostics(trace_id):
                    with diagnostic.p606_asset_create_step(
                        "P805_P606_ASSET_TRANSACTION_SCOPE"
                    ):
                        with diagnostic.p606_asset_create_step(
                            "P805_P606_ASSET_REQUEST_INSERT"
                        ):
                            raise original
        self.assertIs(raised.exception, original)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["code"], "P805_P606_ASSET_REQUEST_INSERT")
        self.assertEqual(records[0]["trace_id"], trace_id)
        self.assertNotIn("private request identity", repr(records))
        self.assertFalse(
            hasattr(self.frappe.flags, "npi_p805_p606_asset_create_diagnostic")
        )

    def test_bff_maps_only_exact_methods_and_independent_switch_fails_closed(self) -> None:
        cases = (
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/acceptance-assets", "get_tooling_acceptance_assets"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/acceptance-revisions", "create_tooling_acceptance_evidence_revision"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/asset-requests", "get_tool_asset_requests"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/asset-requests", "create_tool_asset_request"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/asset-requests/{ASSET_REQUEST_ID}", "get_tool_asset_request"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/asset-execution-requests", "get_tool_asset_execution_requests"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/asset-execution-requests/{ASSET_REQUEST_ID}", "get_tool_asset_execution_request"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/asset-execution-requests:create", "create_tool_asset_execution_request"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/asset-execution-requests:update", "update_tool_asset_execution_request"),
        )
        for method, path, suffix in cases:
            with self.subTest(path=path):
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.router.route_request()
                self.assertTrue(self.frappe.local.form_dict.cmd.endswith(suffix))
                if "asset-execution-requests" in path:
                    route_params = self.frappe.flags.npi_route_params
                    self.assertEqual(route_params["project_id"], PROJECT_ID)
                    self.assertEqual(
                        route_params["tooling_master_id"],
                        MASTER_ID,
                    )
                    self.assertEqual(route_params["tooling_set_id"], SET_ID)
                    if path.endswith(f"/{ASSET_REQUEST_ID}"):
                        self.assertEqual(
                            route_params["tool_asset_execution_request_id"],
                            ASSET_REQUEST_ID,
                        )

        execution_base = f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/asset-execution-requests"
        for method, path in (
            ("POST", execution_base),
            ("PUT", execution_base),
            ("PATCH", execution_base),
            ("DELETE", execution_base),
            ("POST", f"{execution_base}/{ASSET_REQUEST_ID}"),
            ("POST", f"{execution_base}:retry"),
            ("POST", f"{execution_base}:reconcile"),
            ("POST", f"{execution_base}:create/extra"),
        ):
            with self.subTest(method=method, path=path):
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    "npi_core.bff.route_not_found",
                )

        self.frappe.conf.npi_p6_06_routes_disabled = True
        self.frappe.local.request = types.SimpleNamespace(path=cases[0][1], method="GET")
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.tooling_acceptance_assets_routes_disabled",
        )
        self.assertFalse(self.frappe.flags.npi_route_params)


if __name__ == "__main__":
    unittest.main()
