from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.domain import (  # noqa: E402
    ControlledPrintRegistryVersion,
    ControlledPrintSourceReference,
    PrintCopyState,
    PrintDeliveryMode,
    PrintRegistryState,
    sha256_json,
)
from npi_core.controlled_print.service import (  # noqa: E402
    AuthorizedControlledPrintProject,
)
from npi_core.controlled_print.source_registry import (  # noqa: E402
    ControlledPrintSourceRegistry,
    ResolvedControlledPrintSource,
)


PROJECT_ID = "822ce4ac-0a90-5c0e-8c30-d791dc56e3a9"
SOURCE_ID = "0878087f-6192-4e40-862d-05e0a5927638"
REGISTRY_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
MAPPING_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
REQUEST_ID = "9321128c-675d-5b41-b1e6-9d7519fc5d81"
NOW = datetime(2026, 8, 7, 1, 0, tzinfo=UTC)


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

    def get_value(self, doctype: str, name: str, fieldname: str) -> object | None:
        if doctype == "User" and fieldname == "user_type":
            return "System User"
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class FakeAdapter:
    source_object_type = "synthetic_print_source"

    def __init__(self, owner: "Phase5ControlledPrintApiTest") -> None:
        self.owner = owner

    def resolve_exact(self, *, project_global_id: UUID, source_global_id: UUID):
        self.owner.events.append("source")
        snapshot = {"title": "Synthetic controlled source", "version": 3}
        return ResolvedControlledPrintSource(
            project_global_id=project_global_id,
            project_type_key="new_tool",
            gate_key=None,
            reference=ControlledPrintSourceReference(
                source_object_type=self.source_object_type,
                source_global_id=source_global_id,
                source_version=3,
                source_state="released",
                source_snapshot_hash=sha256_json(snapshot),
            ),
            snapshot=snapshot,
        )


class MockRepository:
    def __init__(self, owner: "Phase5ControlledPrintApiTest") -> None:
        self.owner = owner
        self.authorized = True
        self.mappings: tuple[ControlledPrintRegistryVersion, ...] = ()
        self.replayed = False
        self.error: Exception | None = None
        self.response: dict[str, Any] = {}
        self.content_response = types.SimpleNamespace(
            content=b"%PDF-1.4 synthetic",
            file_name="controlled-print-" + SOURCE_ID + ".pdf",
            mime_type="application/pdf",
            snapshot_hash="a" * 64,
            output_hash="b" * 64,
        )

    def authorize_project(self, project_global_id: UUID):
        self.owner.events.append("authorize")
        if not self.authorized:
            return None
        return AuthorizedControlledPrintProject(
            global_id=project_global_id,
            tenant_id="TENANT-A",
            project_type_key="new_tool",
        )

    def published_mapping_candidates(self, context, *, at: datetime):
        self.owner.events.append("mapping")
        return self.mappings

    def create_snapshot(self, project_global_id: UUID, **values: Any):
        self.owner.events.append("create")
        self.owner.command_values = values
        if self.error is not None:
            raise self.error
        return types.SimpleNamespace(
            response=self.response,
            replayed=self.replayed,
        )

    def snapshot_detail(self, project_global_id: UUID, snapshot_global_id: UUID):
        self.owner.events.append("detail")
        return self.response

    def content(self, project_global_id: UUID, snapshot_global_id: UUID):
        self.owner.events.append("content")
        return self.content_response


class Phase5ControlledPrintApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.controlled_print_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase5-controlled-print-api",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "Idempotency-Key": "p5-controlled-print-command-0001",
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="printer@example.invalid")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p4_05_routes_disabled=False,
            npi_p5_01_routes_disabled=False,
            npi_p5_02_routes_disabled=False,
            npi_p5_03_routes_disabled=False,
            npi_p5_04_routes_disabled=False,
            npi_p5_05_routes_disabled=False,
            npi_p5_06_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={"project_id": PROJECT_ID},
        )
        self.frappe.local = types.SimpleNamespace(
            response=AttrDict(),
            form_dict=AttrDict(),
            request=types.SimpleNamespace(path="/", method="GET"),
        )
        self.frappe.request = self.frappe.local.request
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_roles = lambda _user: ["NPI API User"]
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

        self.api = importlib.import_module("npi_core.controlled_print_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.events: list[str] = []
        self.command_values: dict[str, Any] = {}
        self.factories: list[dict[str, Any]] = []

        def repository_factory(**values: Any):
            self.factories.append(values)
            return self.repository

        self.api._repository_factory = repository_factory
        self.adapter = FakeAdapter(self)
        self.api._source_registry_factory = lambda: ControlledPrintSourceRegistry(
            (self.adapter,)
        )
        self.repository.response = self.snapshot_response()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def payload(self) -> dict[str, object]:
        return {
            "sourceKind": self.adapter.source_object_type,
            "sourceGlobalId": SOURCE_ID,
            "sourceVersion": 3,
            "language": "en",
        }

    def mapping(self, *, users: tuple[str, ...] = ("printer@example.invalid",)):
        template = "<h1>{{ doc.title }}</h1>"
        return ControlledPrintRegistryVersion(
            global_id=UUID(MAPPING_ID),
            registry_global_id=UUID(REGISTRY_ID),
            tenant_id="TENANT-A",
            mapping_key="synthetic.release.en",
            mapping_version=1,
            title="Synthetic released source",
            state=PrintRegistryState.PUBLISHED,
            source_object_type=self.adapter.source_object_type,
            project_type_key="new_tool",
            gate_key=None,
            source_state="released",
            language="en",
            delivery_mode=PrintDeliveryMode.CONTROLLED_PDF,
            copy_state=PrintCopyState.NOT_NUMBERED,
            print_format_name="Synthetic Controlled Print",
            template_content=template,
            template_sha256=__import__("hashlib").sha256(template.encode()).hexdigest(),
            watermark_source="CONTROLLED",
            printer_user_ids=users,
            effective_from=NOW,
            published_at=NOW,
        )

    @staticmethod
    def snapshot_response() -> dict[str, Any]:
        return {
            "globalId": SOURCE_ID,
            "version": 1,
            "source": {
                "sourceKind": "synthetic_print_source",
                "sourceGlobalId": SOURCE_ID,
                "sourceVersion": 3,
                "sourceState": "released",
                "sourceSnapshotHash": "c" * 64,
            },
            "registry": {
                "globalId": MAPPING_ID,
                "registryGlobalId": REGISTRY_ID,
                "version": 1,
                "snapshotHash": "d" * 64,
                "templateSha256": "e" * 64,
            },
            "language": "en",
            "deliveryMode": "controlled_pdf",
            "copyState": "not_numbered",
            "watermarkSource": "CONTROLLED",
            "actorUserId": "printer@example.invalid",
            "printedAt": "2026-08-07T01:00:00Z",
            "snapshotHash": "a" * 64,
            "verificationPayload": "urn:npi:controlled-print:synthetic",
            "output": {
                "globalId": MAPPING_ID,
                "fileName": "controlled-print-" + SOURCE_ID + ".pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 18,
                "sha256": "b" * 64,
                "recordHash": "f" * 64,
            },
        }

    def call(self, payload: dict[str, object] | None = None):
        values = payload or self.payload()
        self.frappe.local.form_dict = AttrDict(values)
        return self.api.get_controlled_print_capability(**values)

    def test_capability_authorizes_before_source_and_exact_mapping_resolution(self) -> None:
        self.repository.mappings = (self.mapping(),)
        result = self.call()
        self.assertTrue(result["available"])
        self.assertEqual(self.events, ["authorize", "source", "mapping"])
        self.assertEqual(result["registry"]["globalId"], MAPPING_ID)
        self.assertEqual(result["deliveryMode"], "controlled_pdf")
        self.assertEqual(result["copyState"], "not_numbered")
        self.assertEqual(self.factories[0]["request_id"], REQUEST_ID)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )

    def test_unauthorized_project_is_opaque_and_never_resolves_source(self) -> None:
        self.repository.authorized = False
        result = self.call()
        self.assertEqual(result["code"], "CONTROLLED_PRINT_UNAVAILABLE")
        self.assertEqual(self.events, ["authorize"])

    def test_missing_or_unapproved_mapping_returns_closed_capability(self) -> None:
        result = self.call()
        self.assertFalse(result["available"])
        self.assertIsNone(result["registry"])
        self.assertEqual(result["permissions"], {"create": False, "download": False})

        self.repository.mappings = (self.mapping(users=("other@example.invalid",)),)
        result = self.call()
        self.assertFalse(result["available"])
        self.assertIsNone(result["registry"])

    def test_request_schema_is_closed_and_canonical(self) -> None:
        query_payload = self.payload()
        query_payload["sourceVersion"] = "3"
        result = self.call(query_payload)
        self.assertFalse(result["available"])

        for field, value in (
            ("sourceGlobalId", SOURCE_ID.replace("-", "")),
            ("sourceVersion", True),
            ("language", "fr"),
            ("sourceKind", "unknown source"),
        ):
            with self.subTest(field=field):
                payload = self.payload()
                payload[field] = value
                result = self.call(payload)
                self.assertEqual(result["code"], "VALIDATION_FAILED")

        payload = self.payload()
        payload["printFormat"] = "Unsafe"
        result = self.call(payload)
        self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_route_switch_is_strict_boolean_and_independent(self) -> None:
        path = f"/api/npi/v1/projects/{PROJECT_ID}/controlled-print/capability"
        self.frappe.local.request.path = path
        self.frappe.local.request.method = "GET"
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.controlled_print_api.get_controlled_print_capability",
        )
        self.assertTrue(self.router._requires_project_request_id("GET", path))

        self.frappe.conf.npi_p5_06_routes_disabled = True
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.controlled_print_routes_disabled",
        )

        self.frappe.conf.npi_p5_06_routes_disabled = "true"
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.controlled_print_api.get_controlled_print_capability",
        )

        self.frappe.conf.npi_p5_06_routes_disabled = True
        self.frappe.local.request.path = f"/api/npi/v1/projects/{PROJECT_ID}/eboms"
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(self.frappe.local.form_dict.cmd, "npi_core.ebom_api.get_eboms")

    def test_create_is_closed_csrf_actor_bound_and_replay_correlated(self) -> None:
        result = self.call_create()
        self.assertEqual(result, self.repository.response)
        self.assertEqual(self.events, ["authorize", "create"])
        self.assertEqual(len(self.command_values["idempotency_key_hash"]), 64)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "false",
        )

        self.repository.replayed = True
        self.call_create()
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )

        self.headers["X-Frappe-CSRF-Token"] = "wrong"
        result = self.call_create()
        self.assertEqual(result["code"], "CSRF_TOKEN_INVALID")

    def test_create_failure_rolls_back_without_leaking_or_false_success(self) -> None:
        self.repository.error = RuntimeError("sensitive /private/files/output.pdf")
        result = self.call_create()
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertNotIn("sensitive", str(result))
        self.assertNotIn("/private/files", str(result))
        self.assertEqual(self.frappe.db.rollback_count, 1)

    def test_detail_and_content_use_only_opaque_route_identity(self) -> None:
        self.frappe.flags.npi_route_params = {
            "project_id": PROJECT_ID,
            "controlled_print_id": SOURCE_ID,
        }
        self.frappe.local.form_dict = AttrDict()
        result = self.api.get_controlled_print_snapshot()
        self.assertEqual(result, self.repository.response)
        self.assertEqual(self.events, ["detail"])

        captured: list[object] = []
        self.api.frappe_binary_call = lambda handler, **_values: captured.append(handler())
        self.api.download_controlled_print_output()
        payload = captured[0]
        self.assertEqual(payload.content, b"%PDF-1.4 synthetic")
        self.assertEqual(payload.mime_type, "application/pdf")
        self.assertNotIn("file_url", str(payload))

    def test_all_four_bff_routes_are_exact_and_share_the_independent_switch(self) -> None:
        base = f"/api/npi/v1/projects/{PROJECT_ID}"
        routes = (
            (
                "GET",
                f"{base}/controlled-print/capability",
                "get_controlled_print_capability",
            ),
            ("POST", f"{base}/controlled-prints", "create_controlled_print_snapshot"),
            (
                "GET",
                f"{base}/controlled-prints/{SOURCE_ID}",
                "get_controlled_print_snapshot",
            ),
            (
                "GET",
                f"{base}/controlled-prints/{SOURCE_ID}/content",
                "download_controlled_print_output",
            ),
        )
        for method, path, function_name in routes:
            with self.subTest(path=path):
                self.frappe.conf.npi_p5_06_routes_disabled = False
                self.frappe.local.request.method = method
                self.frappe.local.request.path = path
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    f"npi_core.controlled_print_api.{function_name}",
                )
                self.frappe.conf.npi_p5_06_routes_disabled = True
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    "npi_core.bff.controlled_print_routes_disabled",
                )

    def call_create(self, payload: dict[str, object] | None = None):
        values = payload or self.payload()
        self.frappe.local.form_dict = AttrDict(values)
        return self.api.create_controlled_print_snapshot(**values)


if __name__ == "__main__":
    unittest.main()
