from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from typing import Any


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
MASTER_ID = "0878087f-6192-4e40-862d-05e0a5927638"
PART_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
REVISION_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
RELATIONSHIP_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
REQUEST_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self, owner: "Phase6ToolingApiTest") -> None:
        self.owner = owner
        self.rollback_count = 0

    def get_value(self, doctype: str, name: str, fieldname: str):
        if doctype == "User" and fieldname == "user_type":
            return self.owner.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockRepository:
    def __init__(self, owner: "Phase6ToolingApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.replayed = False
        self.failure: Exception | None = None
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def cockpit(self, *args: object, **kwargs: Any):
        return self._query("cockpit", args, kwargs)

    def master_detail(self, *args: object, **kwargs: Any):
        return self._query("detail", args, kwargs)

    def create_part(self, *args: object, **kwargs: Any):
        return self._command("part", args, kwargs)

    def create_part_revision(self, *args: object, **kwargs: Any):
        return self._command("revision", args, kwargs)

    def create_requirement(self, *args: object, **kwargs: Any):
        return self._command("requirement", args, kwargs)

    def create_master(self, *args: object, **kwargs: Any):
        return self._command("master", args, kwargs)

    def create_applicability(self, *args: object, **kwargs: Any):
        return self._command("applicability", args, kwargs)

    def _query(self, name: str, args: tuple[object, ...], kwargs: dict[str, Any]):
        self.calls.append((name, args, kwargs))
        if self.failure is not None:
            raise self.failure
        return copy.deepcopy(self.owner.response) if self.scope else None

    def _command(self, name: str, args: tuple[object, ...], kwargs: dict[str, Any]):
        response = self._query(name, args, kwargs)
        return types.SimpleNamespace(response=response, replayed=self.replayed)


class Phase6ToolingApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.tooling_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p6-tooling-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase6-tooling-api",
        }
        self.roles = {
            "admin@example.invalid": ["System Manager"],
            "member@example.invalid": ["NPI API User"],
            "external@example.invalid": ["System Manager"],
        }
        self.user_types = {
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
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "tooling_master_id": MASTER_ID,
                "part_id": PART_ID,
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
        self.frappe.db = StubDatabase(self)
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

        self.api = importlib.import_module("npi_core.tooling_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.api._repository_factory = lambda **_values: self.repository
        self.response = {
            "project": {"globalId": PROJECT_ID},
            "masters": [],
            "requirements": [],
            "parts": [],
            "applicability": [],
        }

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def test_queries_authorize_project_before_protected_master(self) -> None:
        self.assertEqual(self.call(self.api.get_tooling_cockpit), self.response)
        self.assertEqual(self.repository.calls[0][0], "authorize")
        self.assertEqual(len(self.repository.calls[0][1]), 1)
        self.repository.calls.clear()
        self.assertEqual(self.call(self.api.get_tooling_master), self.response)
        self.assertEqual([value[0] for value in self.repository.calls[:2]], ["authorize", "authorize"])
        self.assertEqual(str(self.repository.calls[1][1][1]), MASTER_ID)

    def test_part_command_is_closed_admin_actor_bound_and_replay_visible(self) -> None:
        payload = {
            "title": "Front housing",
            "revisionLabel": "A",
            "reason": "Initial engineering release",
        }
        self.assertEqual(self.call(self.api.create_engineering_part, payload), self.response)
        name, _args, values = self.repository.calls[-1]
        self.assertEqual(name, "part")
        self.assertEqual(len(values["idempotency_key_hash"]), 64)
        self.assertEqual(values["revision_label"], "A")
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.repository.replayed = True
        self.call(self.api.create_engineering_part, payload)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )

    def test_project_authorization_and_admin_role_precede_body_validation(self) -> None:
        self.repository.scope = False
        result = self.call(self.api.create_engineering_part, {"doctype": "Secret"})
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual(self.repository.calls[0][0], "authorize")
        self.repository.scope = True
        self.frappe.session.user = "member@example.invalid"
        result = self.call(
            self.api.create_engineering_part,
            {"title": "Part", "revisionLabel": "A", "reason": "Initial"},
        )
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        self.frappe.session.user = "external@example.invalid"
        result = self.call(
            self.api.create_engineering_part,
            {"title": "Part", "revisionLabel": "A", "reason": "Initial"},
        )
        self.assertEqual(result["code"], "PERMISSION_DENIED")

    def test_applicability_parses_only_exact_reference_and_successor_fields(self) -> None:
        payload = {
            "toolingMasterGlobalId": MASTER_ID,
            "partRevisionGlobalId": REVISION_ID,
            "product": {"sourceSystem": "ERPNEXT", "sourceObjectId": "ITEM-001"},
            "relationshipGlobalId": RELATIONSHIP_ID,
            "expectedVersion": 1,
            "effectiveFrom": "2026-08-07",
            "effectiveTo": "2026-09-01",
            "reason": "Exact successor effectivity",
        }
        self.call(self.api.create_tooling_applicability, payload)
        name, _args, values = self.repository.calls[-1]
        self.assertEqual(name, "applicability")
        self.assertEqual(values["product"]["sourceObjectId"], "ITEM-001")
        self.assertEqual(str(values["relationship_id"]), RELATIONSHIP_ID)
        self.assertEqual(values["effective_from"].isoformat(), "2026-08-07")
        invalid = dict(payload)
        invalid.pop("expectedVersion")
        result = self.call(self.api.create_tooling_applicability, invalid)
        self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_router_maps_all_seven_paths_and_switch_is_fail_closed(self) -> None:
        cases = {
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling"): "get_tooling_cockpit",
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}"): "get_tooling_master",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/parts"): "create_engineering_part",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/parts/{PART_ID}/revisions"): "create_engineering_part_revision",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-requirements"): "create_tooling_requirement",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-masters"): "create_tooling_master",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-applicabilities"): "create_tooling_applicability",
        }
        for (method, path), suffix in cases.items():
            with self.subTest(path=path):
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.router.route_request()
                self.assertTrue(self.frappe.local.form_dict.cmd.endswith(suffix))
        del self.frappe.conf["npi_p6_01_routes_disabled"]
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/tooling",
            method="GET",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.tooling_routes_disabled",
        )

    def test_direct_route_switch_and_command_failure_roll_back_fail_closed(self) -> None:
        self.frappe.conf.npi_p6_01_routes_disabled = True
        result = self.call(self.api.get_tooling_cockpit)
        self.assertEqual(result["code"], "TOOLING_ROUTES_DISABLED")
        self.assertEqual(self.frappe.local.response.http_status_code, 503)
        self.assertEqual(self.frappe.db.rollback_count, 1)

        self.frappe.conf.npi_p6_01_routes_disabled = False
        self.repository.failure = RuntimeError("synthetic protected failure")
        result = self.call(
            self.api.create_tooling_master,
            {"title": "Front housing tool"},
        )
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(self.frappe.local.response.http_status_code, 500)
        self.assertEqual(self.frappe.db.rollback_count, 2)


if __name__ == "__main__":
    unittest.main()
