from __future__ import annotations

import copy
import importlib
import json
import sys
import types
import unittest
from typing import Any


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = "8b000000-0000-4000-8000-000000000001"
PACKAGE_ID = "8b000000-0000-4000-8000-000000000002"
MASTER_ID = "8b000000-0000-4000-8000-000000000003"
REQUEST_ID = "8b000000-0000-4000-8000-000000000004"
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
    def __init__(self) -> None:
        self.rollback_count = 0

    @staticmethod
    def get_value(doctype: str, name: str, fieldname: str):
        if doctype == "User" and fieldname == "user_type":
            return "Website User" if name == "external@example.invalid" else "System User"
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockRepository:
    def __init__(self, owner: "Phase6ToolingExportApiTests") -> None:
        self.owner = owner
        self.scope = True
        self.replayed = False
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def tooling_list(self, *args: object, **kwargs: Any):
        self.calls.append(("list", args, kwargs))
        return copy.deepcopy(self.owner.list_response) if self.scope else None

    def tooling_list_preference(self, *args: object, **kwargs: Any):
        self.calls.append(("preference", args, kwargs))
        return copy.deepcopy(self.owner.preference_response) if self.scope else None

    def save_tooling_list_preference(self, *args: object, **kwargs: Any):
        self.calls.append(("save_preference", args, kwargs))
        return copy.deepcopy(self.owner.preference_response) if self.scope else None

    def create_tooling_export_package(self, *args: object, **kwargs: Any):
        self.calls.append(("create", args, kwargs))
        if not self.scope:
            return None
        return types.SimpleNamespace(
            response=copy.deepcopy(self.owner.export_response),
            replayed=self.replayed,
        )

    def tooling_export_package_content(self, *args: object, **kwargs: Any):
        self.calls.append(("download", args, kwargs))
        if not self.scope:
            return None
        return types.SimpleNamespace(
            content=b"PK\x03\x04synthetic-tooling-package",
            file_name="tooling-objects-NPI-800.zip",
            mime_type="application/zip",
            replayed=self.replayed,
        )


class Phase6ToolingExportApiTests(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.tooling.export_repository",
        "npi_core.tooling_export_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p6-tooling-export-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase6-tooling-export-api",
        }
        self.roles = {
            "admin@example.invalid": ["System Manager"],
            "member@example.invalid": ["NPI API User"],
            "external@example.invalid": ["System Manager"],
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="admin@example.invalid")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p6_01_routes_disabled=False,
            npi_p6_02_routes_disabled=False,
            npi_p6_03_routes_disabled=False,
            npi_p6_04_routes_disabled=False,
            npi_p6_05_routes_disabled=False,
            npi_p6_06_routes_disabled=False,
            npi_p6_07_routes_disabled=False,
            npi_p6_08_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "view_id": "shared_parts",
                "package_id": PACKAGE_ID,
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
        self.frappe.parse_json = lambda value: (
            json.loads(value) if isinstance(value, str) else value
        )
        self.frappe.db = StubDatabase()
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
        repository_module = types.ModuleType("npi_core.tooling.export_repository")
        repository_module.FrappeToolingExportRepository = object
        sys.modules["npi_core.tooling.export_repository"] = repository_module

        self.api = importlib.import_module("npi_core.tooling_export_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.api._repository_factory = lambda **_values: self.repository
        self.list_response = {
            "projectGlobalId": PROJECT_ID,
            "filter": self.filter_payload(),
            "querySnapshotHash": HASH,
            "totalCount": 0,
            "pageSize": 50,
            "nextCursor": None,
            "items": [],
            "permissions": {
                "view": True,
                "canExport": True,
                "exportUnavailableReason": None,
            },
        }
        self.preference_response = {
            "stored": False,
            "globalId": None,
            "optimisticVersion": 0,
            "snapshotHash": None,
            "preference": self.preference_payload(),
        }
        self.export_response = {
            "package": {
                "globalId": PACKAGE_ID,
                "snapshotHash": HASH,
            }
        }

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    @staticmethod
    def filter_payload() -> dict[str, object]:
        return {
            "viewId": "shared_parts",
            "search": "tool",
            "sortKey": "title",
            "sortDirection": "asc",
            "groupKey": "none",
        }

    @classmethod
    def preference_payload(cls) -> dict[str, object]:
        return {
            "gridId": "tooling-list",
            "tableSchemaVersion": "tooling-list-grid-v1",
            "viewId": "shared_parts",
            "filter": cls.filter_payload(),
            "columnOrder": [
                "selection",
                "tooling",
                "applicability",
                "part_revisions",
                "physical_sets",
                "design_revisions",
                "origin",
                "source",
                "action",
            ],
            "hiddenColumns": ["origin"],
            "columnWidths": [{"columnId": "tooling", "width": 260}],
        }

    def test_independent_route_switch_is_default_closed_before_authentication(self) -> None:
        self.frappe.conf.pop("npi_p6_08_routes_disabled")
        result = self.call(self.api.get_tooling_list)
        self.assertEqual(result["code"], "TOOLING_EXPORT_ROUTES_DISABLED")
        self.assertEqual(self.frappe.local.response.http_status_code, 503)
        self.assertFalse(self.repository.calls)

    def test_list_authorizes_project_before_parsing_and_uses_closed_stable_query(self) -> None:
        result = self.call(
            self.api.get_tooling_list,
            {
                "viewId": "shared_parts",
                "search": "tool",
                "sortKey": "title",
                "sortDirection": "asc",
                "groupKey": "none",
                "pageSize": 25,
                "cursor": "opaque-cursor",
            },
        )
        self.assertEqual(result, self.list_response)
        self.assertEqual([call[0] for call in self.repository.calls], ["authorize", "list"])
        query = self.repository.calls[1][2]
        self.assertEqual(query["filter_spec"].snapshot_payload(), self.filter_payload())
        self.assertEqual(query["page_size"], 25)
        self.assertEqual(query["cursor"], "opaque-cursor")

        self.repository.calls.clear()
        self.repository.scope = False
        result = self.call(self.api.get_tooling_list, {"doctype": "File"})
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual([call[0] for call in self.repository.calls], ["authorize"])

    def test_guest_and_invalid_route_identity_never_reach_secondary_data(self) -> None:
        self.frappe.session.user = "Guest"
        result = self.call(self.api.get_tooling_list)
        self.assertEqual(result["code"], "AUTHENTICATION_REQUIRED")
        self.assertFalse(self.repository.calls)

        self.frappe.session.user = "admin@example.invalid"
        self.frappe.flags.npi_route_params["project_id"] = "not-a-project"
        result = self.call(self.api.get_tooling_list)
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertFalse(self.repository.calls)

    def test_preference_is_exact_view_scoped_optimistic_and_strict(self) -> None:
        result = self.call(self.api.get_tooling_list_preference)
        self.assertEqual(result, self.preference_response)
        self.assertEqual(self.repository.calls[-1][0], "preference")
        self.assertEqual(self.repository.calls[-1][1][1].value, "shared_parts")

        self.repository.calls.clear()
        payload = {
            "expectedVersion": 0,
            "expectedSnapshotHash": None,
            "preference": self.preference_payload(),
        }
        result = self.call(self.api.set_tooling_list_preference, payload)
        self.assertEqual(result, self.preference_response)
        command = self.repository.calls[-1]
        self.assertEqual(command[0], "save_preference")
        self.assertEqual(command[2]["expected_version"], 0)
        self.assertIsNone(command[2]["expected_snapshot_hash"])
        self.assertEqual(command[2]["preference"].snapshot_payload(), self.preference_payload())

        invalid = copy.deepcopy(payload)
        invalid["preference"]["filter"]["viewId"] = "all"  # type: ignore[index]
        result = self.call(self.api.set_tooling_list_preference, invalid)
        self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_commands_require_csrf_internal_manager_and_administer_scope(self) -> None:
        payload = {
            "mode": "selection",
            "selection": [{"toolingMasterGlobalId": MASTER_ID, "snapshotHash": HASH}],
        }
        self.headers.pop("X-Frappe-CSRF-Token")
        result = self.call(self.api.create_tooling_export_package, payload)
        self.assertEqual(result["code"], "CSRF_TOKEN_INVALID")
        self.assertFalse(self.repository.calls)

        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + "a" * 48
        for actor in ("member@example.invalid", "external@example.invalid"):
            with self.subTest(actor=actor):
                self.frappe.session.user = actor
                result = self.call(self.api.create_tooling_export_package, payload)
                self.assertEqual(result["code"], "PERMISSION_DENIED")
                self.assertFalse(self.repository.calls)

        self.frappe.session.user = "admin@example.invalid"
        self.repository.scope = False
        result = self.call(self.api.create_tooling_export_package, {"doctype": "File"})
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual(self.repository.calls[0][2], {"administer": True})

    def test_selection_and_filtered_commands_are_mutually_exclusive_and_actor_bound(self) -> None:
        selection = {
            "mode": "selection",
            "selection": [{"toolingMasterGlobalId": MASTER_ID, "snapshotHash": HASH}],
        }
        result = self.call(self.api.create_tooling_export_package, selection)
        self.assertEqual(result, self.export_response)
        command = self.repository.calls[-1]
        self.assertEqual(command[0], "create")
        self.assertEqual(command[2]["mode"].value, "selection")
        self.assertEqual(str(command[2]["selection"][0].tooling_master_global_id), MASTER_ID)
        self.assertEqual(len(command[2]["idempotency_key_hash"]), 64)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)

        self.repository.calls.clear()
        filtered = {
            "mode": "filtered",
            "filter": self.filter_payload(),
            "querySnapshotHash": HASH,
        }
        self.call(self.api.create_tooling_export_package, filtered)
        command = self.repository.calls[-1]
        self.assertIsNone(command[2]["selection"])
        self.assertEqual(command[2]["filter_spec"].snapshot_payload(), self.filter_payload())
        self.assertEqual(command[2]["query_snapshot_hash"], HASH)

        for payload in (
            {**selection, "filter": self.filter_payload()},
            {**filtered, "selection": selection["selection"]},
            {**selection, "fields": ["*" ]},
        ):
            with self.subTest(payload=payload):
                result = self.call(self.api.create_tooling_export_package, payload)
                self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_download_is_creator_reauthorized_post_with_exact_hash_and_safe_headers(self) -> None:
        captured: dict[str, object] = {}

        def capture_binary(handler, *, response_headers):
            captured["payload"] = handler()
            captured["headers"] = dict(response_headers)

        self.api.frappe_binary_call = capture_binary
        result = self.call(
            self.api.download_tooling_export_package,
            {"expectedSnapshotHash": HASH},
        )
        self.assertIsNone(result)
        self.assertEqual([call[0] for call in self.repository.calls], ["authorize", "download"])
        command = self.repository.calls[-1]
        self.assertEqual(str(command[1][0]), PROJECT_ID)
        self.assertEqual(str(command[1][1]), PACKAGE_ID)
        self.assertEqual(command[2]["expected_snapshot_hash"], HASH)
        self.assertEqual(len(command[2]["idempotency_key_hash"]), 64)
        payload = captured["payload"]
        self.assertEqual(payload.mime_type, "application/zip")
        self.assertEqual(payload.disposition, "attachment")
        self.assertEqual(payload.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(payload.headers["Content-Security-Policy"], "sandbox; default-src 'none'")
        self.assertNotIn("file_url", repr(payload))

    def test_bff_maps_exact_routes_and_p6_08_switch_is_independent(self) -> None:
        cases = (
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-list", "get_tooling_list"),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling-list/preferences/shared_parts",
                "get_tooling_list_preference",
            ),
            (
                "PUT",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling-list/preferences/shared_parts",
                "set_tooling_list_preference",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling-exports",
                "create_tooling_export_package",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling-exports/{PACKAGE_ID}:content",
                "download_tooling_export_package",
            ),
        )
        for method, path, suffix in cases:
            with self.subTest(path=path):
                self.frappe.local.form_dict = AttrDict()
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.router.route_request()
                self.assertTrue(self.frappe.local.form_dict.cmd.endswith(suffix))

        self.frappe.conf.npi_p6_08_routes_disabled = True
        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(path=cases[0][1], method="GET")
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.tooling_export_routes_disabled",
        )
        self.assertFalse(self.frappe.flags.npi_route_params)


if __name__ == "__main__":
    unittest.main()
