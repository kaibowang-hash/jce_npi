from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from typing import Any


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
BATCH_ID = "0878087f-6192-4e40-862d-05e0a5927638"
PREVIEW_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
INSPECTION_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
MAPPING_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
FILE_REVISION_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"
TARGET_ID = "1e1f1939-adcf-4c04-8b70-a776f6681523"
REQUEST_ID = "5b82874f-cdf0-48eb-a393-458186511edb"
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

    def get_value(self, doctype: str, name: str, fieldname: str):
        if doctype == "User" and fieldname == "user_type":
            return self.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockRepository:
    def __init__(self, owner: "Phase6ToolingImportApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.replayed = False
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def tooling_import_batches(self, *args: object, **kwargs: Any):
        return self._query("list", args, kwargs)

    def tooling_import_batch_detail(self, *args: object, **kwargs: Any):
        return self._query("detail", args, kwargs)

    def create_tooling_import_batch(self, *args: object, **kwargs: Any):
        return self._command("batch", args, kwargs)

    def create_tooling_import_inspection(self, *args: object, **kwargs: Any):
        return self._command("inspection", args, kwargs)

    def create_tooling_import_mapping_proposal(
        self, *args: object, **kwargs: Any
    ):
        return self._command("mapping", args, kwargs)

    def create_tooling_import_preview(self, *args: object, **kwargs: Any):
        return self._command("preview", args, kwargs)

    def create_tooling_import_confirmation(self, *args: object, **kwargs: Any):
        return self._command("confirmation", args, kwargs)

    def _query(self, name: str, args, kwargs):
        self.calls.append((name, args, kwargs))
        if not self.scope:
            return None
        return copy.deepcopy(self.owner.query_response)

    def _command(self, name: str, args, kwargs):
        self.calls.append((name, args, kwargs))
        return types.SimpleNamespace(
            response=copy.deepcopy(self.owner.command_response),
            replayed=self.replayed,
        )


class Phase6ToolingImportApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.tooling.import_repository",
        "npi_core.tooling_import_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p6-tooling-import-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase6-tooling-import-api",
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
            npi_p6_01_routes_disabled=False,
            npi_p6_02_routes_disabled=False,
            npi_p6_03_routes_disabled=False,
            npi_p6_04_routes_disabled=False,
            npi_p6_05_routes_disabled=False,
            npi_p6_06_routes_disabled=False,
            npi_p6_07_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "batch_id": BATCH_ID,
                "preview_id": PREVIEW_ID,
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
        repository_module = types.ModuleType("npi_core.tooling.import_repository")
        repository_module.FrappeToolingImportRepository = object
        sys.modules["npi_core.tooling.import_repository"] = repository_module

        self.api = importlib.import_module("npi_core.tooling_import_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.api._repository_factory = lambda **_values: self.repository
        self.query_response = {
            "projectGlobalId": PROJECT_ID,
            "mappingAuthority": {"state": "unavailable"},
            "batches": [],
        }
        self.command_response = {
            "mappingAuthority": {"state": "unavailable"},
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
    def batch_payload() -> dict[str, object]:
        return {
            "customerScopeId": "CUSTOMER-001",
            "fileRevisionGlobalId": FILE_REVISION_ID,
            "fileOptimisticVersion": 3,
            "frappeContentHash": "b" * 32,
            "sha256": HASH,
        }

    @staticmethod
    def mapping_payload() -> dict[str, object]:
        return {
            "inspectionGlobalId": INSPECTION_ID,
            "inspectionSnapshotHash": HASH,
            "templateKey": "customer.reviewed.v1",
            "reason": "Reviewed proposal for preview only.",
        }

    @staticmethod
    def preview_payload() -> dict[str, object]:
        return {
            "inspectionGlobalId": INSPECTION_ID,
            "inspectionSnapshotHash": HASH,
            "mappingGlobalId": MAPPING_ID,
            "mappingSnapshotHash": HASH,
        }

    @staticmethod
    def confirmation_payload() -> dict[str, object]:
        return {
            "expectedVersion": 1,
            "expectedSnapshotHash": HASH,
            "confirmations": [
                {
                    "kind": "image_anchor",
                    "worksheetName": "Tooling List",
                    "sourceRow": 7,
                    "anchorKey": "tooling-list.image-0001",
                    "selectedTargetObject": "tooling_master",
                    "selectedTargetGlobalId": TARGET_ID,
                    "selectedTargetSnapshotHash": HASH,
                    "reason": "Confirmed against the exact controlled target.",
                }
            ],
        }

    def test_routes_default_closed_before_authentication_or_repository_access(self) -> None:
        self.frappe.conf.pop("npi_p6_07_routes_disabled")
        result = self.call(self.api.get_tooling_import_batches)
        self.assertEqual(result["code"], "TOOLING_IMPORT_ROUTES_DISABLED")
        self.assertEqual(self.frappe.local.response.http_status_code, 503)
        self.assertFalse(self.repository.calls)

    def test_queries_authorize_project_before_resolving_batch(self) -> None:
        for function, expected in (
            (self.api.get_tooling_import_batches, "list"),
            (self.api.get_tooling_import_batch, "detail"),
        ):
            with self.subTest(expected=expected):
                self.repository.calls.clear()
                result = self.call(function)
                self.assertEqual(result, self.query_response)
                self.assertEqual(self.repository.calls[0][0], "authorize")
                self.assertEqual(str(self.repository.calls[0][1][0]), PROJECT_ID)
                self.assertEqual(self.repository.calls[1][0], expected)

        self.repository.calls.clear()
        self.repository.scope = False
        result = self.call(self.api.get_tooling_import_batch)
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual([call[0] for call in self.repository.calls], ["authorize"])

    def test_query_requires_authenticated_tenant_principal(self) -> None:
        self.frappe.session.user = "Guest"
        result = self.call(self.api.get_tooling_import_batches)
        self.assertEqual(result["code"], "AUTHENTICATION_REQUIRED")
        self.assertFalse(self.repository.calls)

    def test_commands_require_csrf_internal_manager_and_administer_scope(self) -> None:
        self.headers.pop("X-Frappe-CSRF-Token")
        result = self.call(self.api.create_tooling_import_batch, self.batch_payload())
        self.assertEqual(result["code"], "CSRF_TOKEN_INVALID")
        self.assertFalse(self.repository.calls)

        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + "a" * 48
        for actor in ("member@example.invalid", "external@example.invalid"):
            with self.subTest(actor=actor):
                self.frappe.session.user = actor
                result = self.call(
                    self.api.create_tooling_import_batch, self.batch_payload()
                )
                self.assertEqual(result["code"], "PERMISSION_DENIED")
                self.assertFalse(self.repository.calls)

        self.frappe.session.user = "admin@example.invalid"
        self.repository.scope = False
        result = self.call(
            self.api.create_tooling_import_batch,
            {"unexpected": "must not be parsed before scope"},
        )
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual(self.repository.calls[0][0], "authorize")
        self.assertEqual(self.repository.calls[0][2], {"administer": True})

    def test_source_registration_is_strict_actor_bound_and_replay_correlated(self) -> None:
        result = self.call(self.api.create_tooling_import_batch, self.batch_payload())
        self.assertEqual(result, self.command_response)
        authorize, command = self.repository.calls
        self.assertEqual(authorize[0], "authorize")
        self.assertEqual(authorize[2], {"administer": True})
        self.assertEqual(command[0], "batch")
        self.assertEqual(str(command[1][0]), PROJECT_ID)
        self.assertEqual(command[2]["customer_scope_id"], "CUSTOMER-001")
        self.assertEqual(str(command[2]["file_revision_id"]), FILE_REVISION_ID)
        self.assertEqual(command[2]["file_optimistic_version"], 3)
        self.assertEqual(command[2]["frappe_content_hash"], "b" * 32)
        self.assertEqual(command[2]["sha256"], HASH)
        self.assertEqual(len(command[2]["idempotency_key_hash"]), 64)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"], "false"
        )

        self.repository.calls.clear()
        self.repository.replayed = True
        self.call(self.api.create_tooling_import_batch, self.batch_payload())
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"], "true"
        )

        for payload in (
            {**self.batch_payload(), "approval": True},
            {key: value for key, value in self.batch_payload().items() if key != "sha256"},
            {**self.batch_payload(), "sha256": "A" * 64},
        ):
            with self.subTest(payload=payload):
                result = self.call(self.api.create_tooling_import_batch, payload)
                self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_checkpoint_2_commands_expose_proposal_preview_and_confirmation_only(self) -> None:
        cases = (
            (self.api.create_tooling_import_inspection, {}, "inspection"),
            (
                self.api.create_tooling_import_mapping_proposal,
                self.mapping_payload(),
                "mapping",
            ),
            (self.api.create_tooling_import_preview, self.preview_payload(), "preview"),
            (
                self.api.create_tooling_import_confirmation,
                self.confirmation_payload(),
                "confirmation",
            ),
        )
        for function, payload, expected in cases:
            with self.subTest(expected=expected):
                self.repository.calls.clear()
                self.call(function, payload)
                command = self.repository.calls[-1]
                self.assertEqual(command[0], expected)
                self.assertNotIn("approval", command[2])
                self.assertNotIn("state", command[2])
                self.assertNotIn("execute", command[2])
                self.assertEqual(str(command[1][0]), PROJECT_ID)
                if expected != "batch":
                    self.assertEqual(str(command[1][1]), BATCH_ID)
                if expected == "confirmation":
                    self.assertEqual(str(command[1][2]), PREVIEW_ID)
                    confirmation = command[2]["confirmations"][0]
                    self.assertEqual(confirmation["anchorKey"], "tooling-list.image-0001")
                    self.assertEqual(confirmation["selectedTargetSnapshotHash"], HASH)

    def test_confirmation_rejects_ambiguous_anchor_or_target(self) -> None:
        for mutation in (
            {"kind": "image_anchor", "anchorKey": None},
            {"kind": "relationship", "anchorKey": "unexpected.anchor"},
            {"selectedTargetObject": "erpnext_item"},
        ):
            with self.subTest(mutation=mutation):
                payload = self.confirmation_payload()
                payload["confirmations"][0].update(mutation)  # type: ignore[index,union-attr]
                result = self.call(self.api.create_tooling_import_confirmation, payload)
                self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_bff_maps_exact_routes_and_p6_07_switch_is_independent(self) -> None:
        cases = (
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-imports", "get_tooling_import_batches"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-imports", "create_tooling_import_batch"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-imports/{BATCH_ID}", "get_tooling_import_batch"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-imports/{BATCH_ID}/inspections", "create_tooling_import_inspection"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-imports/{BATCH_ID}/mapping-proposals", "create_tooling_import_mapping_proposal"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-imports/{BATCH_ID}/previews", "create_tooling_import_preview"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-imports/{BATCH_ID}/previews/{PREVIEW_ID}/confirmations", "create_tooling_import_confirmation"),
        )
        for method, path, suffix in cases:
            with self.subTest(path=path):
                self.frappe.local.form_dict = AttrDict()
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.router.route_request()
                self.assertTrue(self.frappe.local.form_dict.cmd.endswith(suffix))

        self.frappe.conf.npi_p6_07_routes_disabled = True
        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(path=cases[0][1], method="GET")
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.tooling_import_routes_disabled",
        )
        self.assertFalse(self.frappe.flags.npi_route_params)


if __name__ == "__main__":
    unittest.main()
