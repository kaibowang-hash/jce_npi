from __future__ import annotations

import copy
import importlib
import json
import sys
import types
import unittest
from typing import Any


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
EBOM_ID = "0878087f-6192-4e40-862d-05e0a5927638"
REVISION_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
PUBLISH_REQUEST_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
POLICY_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
REQUEST_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"
HASH = "a" * 64


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

    def get_value(self, doctype: str, name: str, fieldname: str) -> object | None:
        if doctype == "User" and fieldname == "user_type":
            return self.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockRepository:
    def __init__(self, owner: "Phase5PublishRequestApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.replayed = False
        self.error: Exception | None = None
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def list_requests(self, *args: object, **kwargs: Any):
        self.calls.append(("list", args, kwargs))
        return copy.deepcopy(self.owner.list_response)

    def request_detail(self, *args: object, **kwargs: Any):
        self.calls.append(("detail", args, kwargs))
        return copy.deepcopy(self.owner.request_response)

    def create_request(self, *args: object, **kwargs: Any):
        self.calls.append(("create", args, kwargs))
        if self.error is not None:
            raise self.error
        return types.SimpleNamespace(
            response=copy.deepcopy(self.owner.request_response),
            replayed=self.replayed,
        )


class Phase5PublishRequestApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_integration.publish_request.diagnostics",
        "npi_integration.publish_request_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p5-publish-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase5-publish-api",
        }
        self.roles = {
            "publisher@example.invalid": ["NPI API User"],
            "viewer@example.invalid": [],
            "external@example.invalid": ["NPI API User"],
        }
        user_types = {
            "publisher@example.invalid": "System User",
            "viewer@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="publisher@example.invalid")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p4_05_routes_disabled=False,
            npi_p5_01_routes_disabled=False,
            npi_p5_02_routes_disabled=False,
            npi_p5_03_routes_disabled=False,
            npi_p5_04_routes_disabled=False,
            npi_p5_05_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "ebom_id": EBOM_ID,
                "revision_id": REVISION_ID,
                "publish_request_id": PUBLISH_REQUEST_ID,
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
        self.safe_logs: list[str] = []
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda message, *_args, **_kwargs: self.safe_logs.append(message)
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

        self.api = importlib.import_module("npi_integration.publish_request_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.factories: list[dict[str, Any]] = []

        def factory(**values: Any):
            self.factories.append(values)
            return self.repository

        self.api._repository_factory = factory
        self.request_response = {
            "globalId": PUBLISH_REQUEST_ID,
            "payloadHash": HASH,
            "targetMode": "mock",
            "state": "validated",
            "dispatchAllowed": False,
        }
        self.list_response = {
            "project": {"globalId": PROJECT_ID},
            "ebom": {"globalId": EBOM_ID},
            "revision": {"globalId": REVISION_ID},
            "permissions": {"view": True, "create": True},
            "policies": [],
            "items": [],
        }

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def payload() -> dict[str, object]:
        return {
            "expectedEbomVersion": 4,
            "expectedRevisionSnapshotHash": HASH,
            "expectedLifecycleVersion": 4,
            "publishPolicyGlobalId": POLICY_ID,
            "publishPolicyVersion": 1,
            "publishPolicySnapshotHash": HASH,
            "targetMode": "mock",
            "confirmed": True,
            "confirmationIntent": (
                "validate_exact_released_ebom_for_item_mbom_publish"
            ),
            "reason": "Validate the exact released EBOM for formal publishing.",
        }

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def test_queries_authorize_project_before_repository_resolution(self) -> None:
        result = self.call(self.api.get_publish_requests)
        self.assertEqual(result, self.list_response)
        self.assertEqual(self.repository.calls[0][0], "authorize")
        self.assertEqual(len(self.repository.calls[0][1]), 1)
        self.assertEqual(self.repository.calls[1][0], "list")

        self.repository.calls.clear()
        result = self.call(self.api.get_publish_request)
        self.assertEqual(result, self.request_response)
        self.assertEqual(self.repository.calls[0][0], "authorize")
        self.assertEqual(self.repository.calls[1][0], "detail")
        self.assertEqual(
            [str(value) for value in self.repository.calls[1][1][1:]],
            [EBOM_ID, REVISION_ID, PUBLISH_REQUEST_ID],
        )

    def test_create_is_closed_csrf_role_bound_and_replay_correlated(self) -> None:
        result = self.call(self.api.create_publish_request, self.payload())
        self.assertEqual(result, self.request_response)
        call = self.repository.calls[-1]
        self.assertEqual(call[0], "create")
        self.assertEqual([str(value) for value in call[1][1:]], [EBOM_ID, REVISION_ID])
        self.assertEqual(len(call[2]["idempotency_key_hash"]), 64)
        self.assertEqual(call[2]["reason"], self.payload()["reason"])
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "false",
        )

        self.repository.replayed = True
        self.call(self.api.create_publish_request, self.payload())
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )

        invalid = self.payload()
        invalid["operation"] = "arbitrary"
        result = self.call(self.api.create_publish_request, invalid)
        self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_authorization_precedes_body_validation(self) -> None:
        self.repository.scope = False
        result = self.call(
            self.api.create_publish_request,
            {"operation": "protected"},
        )
        self.assertEqual(result["code"], "EBOM_PUBLISH_REQUEST_UNAVAILABLE")
        self.assertEqual(self.repository.calls[0][0], "authorize")

        self.repository.scope = True
        self.repository.calls.clear()
        self.frappe.session.user = "viewer@example.invalid"
        result = self.call(self.api.create_publish_request, self.payload())
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        self.assertFalse(self.repository.calls)

    def test_exact_confirmation_and_mock_mode_are_required(self) -> None:
        for field, value in (
            ("confirmed", False),
            ("targetMode", "sandbox"),
            ("confirmationIntent", "publish_latest"),
        ):
            with self.subTest(field=field):
                payload = self.payload()
                payload[field] = value
                result = self.call(self.api.create_publish_request, payload)
                self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_repository_failure_rolls_back_without_false_success(self) -> None:
        self.repository.error = RuntimeError("sensitive target detail")
        result = self.call(self.api.create_publish_request, self.payload())
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(result["status"], 500)
        self.assertTrue(result["retryable"])
        self.assertNotIn("sensitive", str(result).casefold())
        self.assertEqual(self.frappe.db.rollback_count, 1)

    def test_create_diagnostic_is_header_gated_response_neutral_and_sanitized(
        self,
    ) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.publish_request.diagnostics"
        )
        trace_id = "trace-" + ("f" * 32)
        self.repository.error = ValueError("sensitive database /tmp/private")

        result_without_header = self.call(
            self.api.create_publish_request,
            self.payload(),
        )
        self.assertEqual(result_without_header["code"], "INTERNAL_SERVER_ERROR")
        self.assertFalse(any("P505_CREATE" in value for value in self.safe_logs))
        self.safe_logs.clear()

        self.headers[diagnostics.PUBLISH_CREATE_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.PUBLISH_CREATE_SERVER_DIAGNOSTIC_SCOPE
        )
        self.headers["X-Trace-ID"] = trace_id
        result = self.call(self.api.create_publish_request, self.payload())

        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("P505_CREATE", serialized)
        self.assertNotIn("sensitive", serialized)
        self.assertNotIn("/tmp", serialized)
        records = []
        for message in self.safe_logs:
            try:
                record = json.loads(message)
            except (TypeError, ValueError):
                continue
            if record.get("code") == "P505_CREATE_API_RESPONSE":
                records.append(record)
        self.assertEqual(
            records,
            [
                {
                    "code": "P505_CREATE_API_RESPONSE",
                    "exceptionType": "ValueError",
                    "traceId": trace_id,
                }
            ],
        )
        self.assertFalse(
            hasattr(self.frappe.flags, "npi_p505_publish_create_diagnostic")
        )

    def test_routes_are_exact_and_p5_05_switch_is_independent(self) -> None:
        base = (
            f"/api/npi/v1/projects/{PROJECT_ID}/eboms/{EBOM_ID}/revisions/"
            f"{REVISION_ID}/publish-requests"
        )
        routes = (
            ("GET", base, "get_publish_requests"),
            ("POST", base, "create_publish_request"),
            (
                "GET",
                f"{base}/{PUBLISH_REQUEST_ID}",
                "get_publish_request",
            ),
        )
        for method, path, function_name in routes:
            with self.subTest(path=path):
                self.frappe.local.request.method = method
                self.frappe.local.request.path = path
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    f"npi_integration.publish_request_api.{function_name}",
                )
                self.assertTrue(
                    self.router._requires_project_request_id(method, path)
                )

        self.frappe.conf.npi_p5_05_routes_disabled = True
        self.frappe.local.request.method = "GET"
        self.frappe.local.request.path = base
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.publish_request_routes_disabled",
        )

        self.frappe.conf.npi_p5_05_routes_disabled = "true"
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_integration.publish_request_api.get_publish_requests",
        )

        self.frappe.conf.npi_p5_05_routes_disabled = True
        self.frappe.local.request.path = (
            f"/api/npi/v1/projects/{PROJECT_ID}/eboms/{EBOM_ID}"
        )
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.ebom_api.get_ebom",
        )


if __name__ == "__main__":
    unittest.main()
