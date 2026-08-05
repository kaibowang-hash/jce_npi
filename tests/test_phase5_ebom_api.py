from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from typing import Any


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
EBOM_ID = "0878087f-6192-4e40-862d-05e0a5927638"
REVISION_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
REVISION_TWO_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
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
    def __init__(self, owner: "Phase5EngineeringBomApiTest") -> None:
        self.owner = owner
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []
        self.scope = True
        self.replayed = False
        self.unavailable = False

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def list_eboms(self, *args: object, **kwargs: Any):
        return self._query("list", args, kwargs)

    def ebom_detail(self, *args: object, **kwargs: Any):
        return self._query("detail", args, kwargs)

    def compare(self, *args: object, **kwargs: Any):
        return self._query("compare", args, kwargs)

    def create_ebom(self, *args: object, **kwargs: Any):
        return self._command("create", args, kwargs)

    def create_revision(self, *args: object, **kwargs: Any):
        return self._command("revise", args, kwargs)

    def submit_review(self, *args: object, **kwargs: Any):
        return self._command("submit", args, kwargs)

    def review(self, *args: object, **kwargs: Any):
        return self._command("review", args, kwargs)

    def release(self, *args: object, **kwargs: Any):
        return self._command("release", args, kwargs)

    def _query(self, name: str, args: tuple[object, ...], kwargs: dict[str, Any]):
        self.calls.append((name, args, kwargs))
        return None if self.unavailable else copy.deepcopy(self.owner.response)

    def _command(self, name: str, args: tuple[object, ...], kwargs: dict[str, Any]):
        response = self._query(name, args, kwargs)
        return None if response is None else types.SimpleNamespace(
            response=response,
            replayed=self.replayed,
        )


class Phase5EngineeringBomApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.ebom_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p5-ebom-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase5-ebom-api",
        }
        self.roles = {
            "member@example.invalid": ["NPI API User"],
            "viewer@example.invalid": [],
            "external@example.invalid": ["NPI API User"],
        }
        self.user_types = {
            "member@example.invalid": "System User",
            "viewer@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="member@example.invalid")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p5_01_routes_disabled=False,
            npi_p5_02_routes_disabled=False,
            npi_p5_03_routes_disabled=False,
            npi_p5_04_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "ebom_id": EBOM_ID,
                "revision_id": REVISION_ID,
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
        self.frappe.db = StubDatabase(self.user_types)
        self.frappe.log_error = lambda **_values: None
        self.frappe.logger = lambda _name: types.SimpleNamespace(error=lambda *_args, **_kwargs: None)

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

        self.api = importlib.import_module("npi_core.ebom_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.factories: list[dict[str, Any]] = []

        def factory(**values: Any):
            self.factories.append(values)
            return self.repository

        self.api._repository_factory = factory
        self.response = {
            "ebom": {"globalId": EBOM_ID},
            "revision": {"globalId": REVISION_ID},
        }

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def create_payload() -> dict[str, object]:
        return {
            "policyGlobalId": POLICY_ID,
            "policyVersion": 1,
            "policySnapshotHash": HASH,
            "engineeringBomKey": "synthetic_ebom-main",
            "title": "Synthetic EBOM",
            "reason": "Initial structure",
            "lines": [
                {
                    "lineKey": "10",
                    "engineeringItemId": "eng:assembly-a",
                    "description": "Assembly A",
                    "quantity": "1.000",
                    "engineeringUom": "EA",
                    "effectivityStart": "2026-08-05",
                    "attributes": {"material": "ABS"},
                }
            ],
        }

    @staticmethod
    def transition_payload() -> dict[str, object]:
        return {
            "expectedEbomVersion": 2,
            "expectedRevisionSnapshotHash": HASH,
            "expectedLifecycleVersion": 3,
            "policyGlobalId": POLICY_ID,
            "policyVersion": 1,
            "policySnapshotHash": HASH,
        }

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def test_query_authorizes_project_then_ebom_before_fields(self) -> None:
        result = self.call(self.api.get_ebom)
        self.assertEqual(result, self.response)
        authorizations = [
            call[1] for call in self.repository.calls if call[0] == "authorize"
        ]
        self.assertEqual(len(authorizations[0]), 1)
        self.assertEqual(str(authorizations[0][0]), PROJECT_ID)
        self.assertEqual(len(authorizations[1]), 2)
        self.assertEqual(str(authorizations[1][1]), EBOM_ID)
        self.repository.calls.clear()
        result = self.call(
            self.api.compare_ebom_revisions,
            {"fromRevisionId": REVISION_ID, "toRevisionId": REVISION_TWO_ID},
        )
        self.assertEqual(result, self.response)
        compare = self.repository.calls[-1]
        self.assertEqual(compare[0], "compare")
        self.assertEqual(str(compare[2]["from_revision_id"]), REVISION_ID)
        self.assertEqual(str(compare[2]["to_revision_id"]), REVISION_TWO_ID)

    def test_create_is_closed_csrf_role_bound_and_actor_replay_correlated(self) -> None:
        payload = self.create_payload()
        result = self.call(self.api.create_ebom, payload)
        self.assertEqual(result, self.response)
        call = self.repository.calls[-1]
        self.assertEqual(call[0], "create")
        self.assertEqual(len(call[2]["idempotency_key_hash"]), 64)
        self.assertEqual(call[2]["lines"][0]["effectivityStart"], "2026-08-05")
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(self.frappe.flags.npi_response_headers["Idempotency-Replayed"], "false")

        self.repository.replayed = True
        self.call(self.api.create_ebom, payload)
        self.assertEqual(self.frappe.flags.npi_response_headers["Idempotency-Replayed"], "true")

        invalid = dict(payload)
        invalid["itemCode"] = "ERP-100"
        result = self.call(self.api.create_ebom, invalid)
        self.assertEqual(result["code"], "VALIDATION_FAILED")
        self.assertEqual(self.frappe.db.rollback_count, 1)

    def test_command_authorization_precedes_body_validation(self) -> None:
        self.repository.scope = False
        result = self.call(self.api.create_ebom, {"itemCode": "protected"})
        self.assertEqual(result["code"], "EBOM_UNAVAILABLE")
        self.assertEqual(result["status"], 404)
        self.assertEqual(self.repository.calls[0][0], "authorize")

        self.repository.scope = True
        self.frappe.session.user = "viewer@example.invalid"
        result = self.call(self.api.create_ebom, self.create_payload())
        self.assertEqual(result["code"], "PERMISSION_DENIED")

    def test_review_and_release_are_exact_and_separately_confirmed(self) -> None:
        review = self.transition_payload()
        review["decision"] = "approve"
        self.call(self.api.review_ebom_revision, review)
        self.assertEqual(self.repository.calls[-1][0], "review")
        self.assertEqual(self.repository.calls[-1][2]["decision"].value, "approve")

        release = self.transition_payload()
        release.update(
            {
                "confirmed": True,
                "confirmationIntent": "release_exact_ebom_revision",
            }
        )
        self.call(self.api.release_ebom_revision, release)
        self.assertEqual(self.repository.calls[-1][0], "release")
        self.assertIs(self.repository.calls[-1][2]["confirmed"], True)

        release["confirmationIntent"] = "release_latest"
        result = self.call(self.api.release_ebom_revision, release)
        self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_routes_are_exact_request_correlated_and_independently_disabled(self) -> None:
        routes = (
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/eboms", "get_eboms"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/eboms", "create_ebom"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/eboms/{EBOM_ID}", "get_ebom"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/eboms/{EBOM_ID}/revisions", "create_ebom_revision"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/eboms/{EBOM_ID}/compare", "compare_ebom_revisions"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/eboms/{EBOM_ID}/revisions/{REVISION_ID}:submit-review", "submit_ebom_review"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/eboms/{EBOM_ID}/revisions/{REVISION_ID}:review", "review_ebom_revision"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/eboms/{EBOM_ID}/revisions/{REVISION_ID}:release", "release_ebom_revision"),
        )
        for method, path, function_name in routes:
            with self.subTest(path=path):
                self.frappe.local.request.method = method
                self.frappe.local.request.path = path
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    f"npi_core.ebom_api.{function_name}",
                )
                self.assertTrue(self.router._requires_project_request_id(method, path))

        self.frappe.conf.npi_p5_04_routes_disabled = True
        self.frappe.local.request.method = "GET"
        self.frappe.local.request.path = routes[0][1]
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.engineering_bom_routes_disabled",
        )
        self.frappe.conf.npi_p5_04_routes_disabled = False
        self.frappe.conf.npi_p5_01_routes_disabled = True
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(self.frappe.local.form_dict.cmd, "npi_core.ebom_api.get_eboms")


if __name__ == "__main__":
    unittest.main()
