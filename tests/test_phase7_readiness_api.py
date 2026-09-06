from __future__ import annotations

import copy
import hashlib
import importlib
import json
import sys
import types
import unittest
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
TEMPLATE_ID = "0878087f-6192-4e40-862d-05e0a5927638"
TEMPLATE_REVISION_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
INSTANCE_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
REVISION_ID = "6dd227c4-2c74-4f2f-a3ce-347497758118"
MEMBER_ID = "99d03125-7947-4a72-a94f-47930cfcb7bb"
SOURCE_ID = "a8ab6f87-227f-42f9-a7cb-d695e8d34bca"
REQUEST_ID = "5dc0ef7b-8563-46ad-9f40-76dd474566ea"
SHA256_A = "a" * 64


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self, owner: "Phase7ReadinessApiTest") -> None:
        self.owner = owner
        self.rollback_count = 0

    def get_value(self, doctype: str, name: str, fieldname: str):
        if doctype == "User" and fieldname == "user_type":
            return self.owner.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockRepository:
    def __init__(self, owner: "Phase7ReadinessApiTest") -> None:
        self.owner = owner
        self.available = True
        self.replayed: object = False
        self.command_response: object | None = None
        self.query_response: object | None = None
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def template_catalog(self, *args: object, **kwargs: Any):
        return self._query("template_catalog", args, kwargs)

    def create_template(self, *args: object, **kwargs: Any):
        return self._command("create_template", args, kwargs)

    def edit_template(self, *args: object, **kwargs: Any):
        return self._command("edit_template", args, kwargs)

    def publish_template(self, *args: object, **kwargs: Any):
        return self._command("publish_template", args, kwargs)

    def readiness_workspace(self, *args: object, **kwargs: Any):
        return self._query("readiness_workspace", args, kwargs)

    def initialize_readiness(self, *args: object, **kwargs: Any):
        return self._command("initialize_readiness", args, kwargs)

    def revise_readiness(self, *args: object, **kwargs: Any):
        return self._command("revise_readiness", args, kwargs)

    def _query(
        self,
        name: str,
        args: tuple[object, ...],
        kwargs: dict[str, Any],
    ):
        self.calls.append((name, args, kwargs))
        if not self.available:
            return None
        response = (
            self.owner.template_catalog_response
            if name == "template_catalog"
            else self.owner.response
        )
        if self.query_response is not None:
            response = self.query_response
        return copy.deepcopy(response)

    def _command(
        self,
        name: str,
        args: tuple[object, ...],
        kwargs: dict[str, Any],
    ):
        self.calls.append((name, args, kwargs))
        if not self.available:
            return None
        if name == "publish_template":
            response = self.owner.published_template_response
        elif name in {"create_template", "edit_template"}:
            response = self.owner.template_response
        elif name == "initialize_readiness":
            response = self.owner.initialize_response
        elif name == "revise_readiness":
            response = self.owner.revise_response
        else:
            response = self.owner.response
        if self.command_response is not None:
            response = self.command_response
        return types.SimpleNamespace(
            response=copy.deepcopy(response),
            replayed=self.replayed,
        )


class Phase7ReadinessApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.readiness_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.headers = {
            "Idempotency-Key": "p7-readiness-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-" + "a" * 32,
        }
        self.roles = {
            "admin@example.invalid": ["System Manager"],
            "other-admin@example.invalid": ["System Manager"],
            "reader@example.invalid": ["NPI API User"],
            "ordinary@example.invalid": [],
            "external@example.invalid": ["NPI API User", "System Manager"],
        }
        self.user_types = {
            "admin@example.invalid": "System User",
            "other-admin@example.invalid": "System User",
            "reader@example.invalid": "System User",
            "ordinary@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="admin@example.invalid")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p7_01_routes_disabled=False,
            npi_p7_02_routes_disabled=False,
            npi_p7_03_routes_disabled=False,
            npi_p7_04_routes_disabled=False,
            npi_p7_05_routes_disabled=False,
        )
        self.frappe.flags = AttrDict(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "template_id": TEMPLATE_ID,
                "template_version": "1",
                "instance_id": INSTANCE_ID,
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

        self.api = importlib.import_module("npi_core.readiness_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.factory_calls: list[dict[str, Any]] = []

        def repository_factory(**values: Any):
            self.factory_calls.append(values)
            return self.repository

        self.api._repository_factory = repository_factory
        from npi_core.project.domain import ProjectType
        from npi_core.readiness.domain import (
            ReadinessApplicabilitySelector,
            ReadinessBlockingLevel,
            ReadinessCategoryDefinition,
            ReadinessCompletionRule,
            ReadinessGateReference,
            ReadinessItemDefinition,
            ReadinessItemState,
            ReadinessMemberReference,
            ReadinessProjectSnapshot,
            ReadinessTemplateVersion,
            initialize_readiness_instance,
            revise_readiness_item,
        )
        from npi_core.readiness.source_resolver import (
            EXTERNAL_SOURCE_KINDS,
            EXTERNAL_UNAVAILABLE_REASON_CODES,
        )

        applicability = ReadinessApplicabilitySelector(
            project_types=(ProjectType.NEW_TOOL,),
            industry_keys=("automotive",),
        )
        template = ReadinessTemplateVersion.create_draft(
            template_global_id=UUID(TEMPLATE_ID),
            template_code="NPI-AUTO",
            template_version=1,
            title="Automotive NPI readiness",
            applicability=applicability,
            categories=(ReadinessCategoryDefinition("launch", "Launch readiness"),),
            items=(
                ReadinessItemDefinition(
                    key="handover",
                    title="Handover",
                    category_key="launch",
                    weight=10,
                    required=True,
                    blocking_level=ReadinessBlockingLevel.P0,
                    gate_key="G6",
                    completion_rule=ReadinessCompletionRule.CONFIRMATION,
                    applicability=applicability,
                ),
            ),
            changed_by_user_id="admin@example.invalid",
            changed_at=datetime(2026, 8, 11, 13, 0, tzinfo=UTC),
            request_id=UUID(REQUEST_ID),
            trace_id=self.headers["X-Trace-ID"],
        )
        published = template.publish(
            expected_version=1,
            changed_by_user_id="admin@example.invalid",
            changed_at=datetime(2026, 8, 11, 13, 1, tzinfo=UTC),
            request_id=UUID(REQUEST_ID),
            trace_id=self.headers["X-Trace-ID"],
        )
        self.template_response = {
            **template.snapshot_payload(),
            "snapshotHash": template.snapshot_hash,
        }
        self.published_template_response = {
            **published.snapshot_payload(),
            "snapshotHash": published.snapshot_hash,
        }
        self.template_catalog_response = {
            "projectGlobalId": PROJECT_ID,
            "templates": [self.published_template_response],
        }
        self.response = {
            "projectGlobalId": PROJECT_ID,
            "currentRevision": None,
            "revisions": [],
            "sourceOptions": [],
            "unavailableProjections": [
                {
                    "kind": kind.value,
                    "state": "unavailable",
                    "reasonCode": EXTERNAL_UNAVAILABLE_REASON_CODES[kind],
                }
                for kind in sorted(EXTERNAL_SOURCE_KINDS, key=lambda item: item.value)
            ],
            "permissions": {
                "canManageTemplates": True,
                "canInitialize": True,
                "canRevise": True,
            },
        }
        member = ReadinessMemberReference(
            UUID(MEMBER_ID),
            "admin@example.invalid",
            1,
        )
        project = ReadinessProjectSnapshot(
            UUID(PROJECT_ID),
            1,
            "1" * 64,
            ProjectType.NEW_TOOL,
            (),
            "automotive",
        )
        gate = ReadinessGateReference(UUID(int=81), "G6", 1, "2" * 64)
        initialized = initialize_readiness_instance(
            global_id=UUID(REVISION_ID),
            instance_global_id=UUID(INSTANCE_ID),
            tenant_id="TENANT-A",
            project=project,
            template=published,
            gates={"G6": gate},
            assignments={"handover": (member, date(2026, 9, 1))},
            created_by_user_id="admin@example.invalid",
            created_at=datetime(2026, 8, 11, 13, 2, tzinfo=UTC),
            request_id=UUID(REQUEST_ID),
            trace_id=self.headers["X-Trace-ID"],
        )
        revised = revise_readiness_item(
            initialized,
            global_id=UUID(int=82),
            expected_instance_version=1,
            item_key="handover",
            owner=member,
            due_date=date(2026, 9, 2),
            state=ReadinessItemState.IN_PROGRESS,
            confirmation_value=None,
            sources=(),
            created_by_user_id="admin@example.invalid",
            created_at=datetime(2026, 8, 11, 13, 3, tzinfo=UTC),
            request_id=UUID(REQUEST_ID),
            trace_id=self.headers["X-Trace-ID"],
        )

        def workspace(*revisions) -> dict[str, object]:
            values = [
                {
                    **revision.snapshot_payload(),
                    "snapshotHash": revision.snapshot_hash,
                }
                for revision in revisions
            ]
            return {
                **copy.deepcopy(self.response),
                "currentRevision": values[-1],
                "revisions": values,
            }

        self.initialize_response = workspace(initialized)
        self.revise_response = workspace(initialized, revised)

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def route(self, method: str, path: str) -> tuple[str, dict[str, str]]:
        self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
        self.frappe.local.form_dict = AttrDict()
        self.frappe.flags.npi_route_params = {}
        self.router.route_request()
        return (
            self.frappe.local.form_dict.cmd,
            dict(self.frappe.flags.npi_route_params),
        )

    def assert_problem(
        self,
        response: object,
        status: int,
        code: str,
    ) -> dict[str, Any]:
        self.assertIsInstance(response, dict)
        problem = response
        assert isinstance(problem, dict)
        self.assertEqual(problem["status"], status)
        self.assertEqual(problem["code"], code)
        self.assertEqual(self.frappe.local.response.http_status_code, status)
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(headers["X-Trace-ID"], problem["traceId"])
        self.assertIn("X-Request-ID", headers)
        return problem

    @staticmethod
    def template_payload() -> dict[str, object]:
        return {
            "templateCode": "NPI-CUSTOMER-NEW-TOOL",
            "title": "Customer New Tool Readiness",
            "applicability": {
                "projectTypes": ["new_tool"],
                "customerReferenceKeys": [],
                "industryKeys": ["automotive"],
            },
            "categories": [{"key": "quality", "title": "Quality"}],
            "items": [
                {
                    "key": "quality_report",
                    "title": "Controlled quality report",
                    "categoryKey": "quality",
                    "weight": 10,
                    "required": True,
                    "blockingLevel": "P0",
                    "gateKey": "G6",
                    "completionRule": "exact_evidence",
                    "applicability": {
                        "projectTypes": ["new_tool"],
                        "customerReferenceKeys": [],
                        "industryKeys": ["automotive"],
                    },
                    "evidenceRequirements": [
                        {
                            "key": "quality_result",
                            "acceptedSourceKinds": [
                                "controlled_quality_result",
                                "erp_quality_result",
                            ],
                            "minimumCount": 1,
                            "unavailableBlocks": True,
                        }
                    ],
                }
            ],
        }

    @classmethod
    def edit_template_payload(cls) -> dict[str, object]:
        payload = cls.template_payload()
        payload.pop("templateCode")
        return {"expectedOptimisticVersion": 3, **payload}

    @staticmethod
    def initialize_payload() -> dict[str, object]:
        return {
            "templateRevisionGlobalId": TEMPLATE_REVISION_ID,
            "templateVersion": 2,
            "templateSnapshotHash": SHA256_A,
            "industryKey": "automotive",
            "assignments": [
                {
                    "itemKey": "quality_report",
                    "ownerMemberGlobalId": MEMBER_ID,
                    "dueDate": "2026-08-20",
                }
            ],
        }

    @staticmethod
    def revise_payload() -> dict[str, object]:
        return {
            "expectedInstanceVersion": 1,
            "expectedRevisionGlobalId": REVISION_ID,
            "expectedRevisionSnapshotHash": SHA256_A,
            "itemKey": "quality_report",
            "ownerMemberGlobalId": MEMBER_ID,
            "dueDate": "2026-08-20",
            "state": "complete",
            "confirmationValue": None,
            "sources": [
                {
                    "requirementKey": "quality_result",
                    "kind": "controlled_quality_result",
                    "globalId": SOURCE_ID,
                    "sourceVersion": 4,
                    "snapshotHash": SHA256_A,
                }
            ],
        }

    def test_bff_maps_exactly_the_seven_frozen_method_routes(self) -> None:
        cases = (
            (
                "GET",
                "/api/npi/v1/npi-readiness/templates",
                "get_readiness_templates",
                {},
            ),
            (
                "POST",
                "/api/npi/v1/npi-readiness/templates",
                "create_readiness_template",
                {},
            ),
            (
                "PUT",
                f"/api/npi/v1/npi-readiness/templates/{TEMPLATE_ID}/versions/2",
                "edit_readiness_template",
                {"template_id": TEMPLATE_ID, "template_version": "2"},
            ),
            (
                "POST",
                f"/api/npi/v1/npi-readiness/templates/{TEMPLATE_ID}/versions/2:publish",
                "publish_readiness_template",
                {"template_id": TEMPLATE_ID, "template_version": "2"},
            ),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/npi-readiness",
                "get_project_readiness",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/npi-readiness",
                "initialize_project_readiness",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/npi-readiness/{INSTANCE_ID}/revisions",
                "revise_project_readiness",
                {"project_id": PROJECT_ID, "instance_id": INSTANCE_ID},
            ),
        )
        for method, path, handler, route_params in cases:
            with self.subTest(method=method, path=path):
                command, actual_params = self.route(method, path)
                self.assertEqual(command, f"npi_core.readiness_api.{handler}")
                self.assertEqual(actual_params, route_params)

    def test_whitelisted_handlers_allow_only_the_frozen_methods(self) -> None:
        expected = {
            "get_readiness_templates": ("GET",),
            "create_readiness_template": ("POST",),
            "edit_readiness_template": ("PUT",),
            "publish_readiness_template": ("POST",),
            "get_project_readiness": ("GET",),
            "initialize_project_readiness": ("POST",),
            "revise_project_readiness": ("POST",),
        }
        for name, methods in expected.items():
            with self.subTest(name=name):
                function = getattr(self.api, name)
                self.assertEqual(function.allowed_methods, methods)
                self.assertIs(function.allow_guest, True)

    def test_p705_switch_is_default_closed_for_every_route_and_independent(self) -> None:
        self.frappe.conf.pop("npi_p7_05_routes_disabled")
        cases = (
            ("GET", "/api/npi/v1/npi-readiness/templates"),
            ("POST", "/api/npi/v1/npi-readiness/templates"),
            ("PUT", f"/api/npi/v1/npi-readiness/templates/{TEMPLATE_ID}/versions/2"),
            ("POST", f"/api/npi/v1/npi-readiness/templates/{TEMPLATE_ID}/versions/2:publish"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/npi-readiness"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/npi-readiness"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/npi-readiness/{INSTANCE_ID}/revisions"),
        )
        for method, path in cases:
            with self.subTest(method=method, path=path):
                command, route_params = self.route(method, path)
                self.assertEqual(
                    command,
                    "npi_core.readiness_api.readiness_routes_disabled",
                )
                self.assertEqual(route_params, {})

        self.frappe.conf.npi_p7_05_routes_disabled = False
        self.frappe.conf.npi_p7_01_routes_disabled = True
        self.frappe.conf.npi_p7_02_routes_disabled = True
        self.frappe.conf.npi_p7_03_routes_disabled = True
        self.frappe.conf.npi_p7_04_routes_disabled = True
        command, _params = self.route(
            "GET", f"/api/npi/v1/projects/{PROJECT_ID}/npi-readiness"
        )
        self.assertEqual(command, "npi_core.readiness_api.get_project_readiness")

    def test_direct_switch_closes_before_authentication_or_body_parsing(self) -> None:
        self.frappe.conf.pop("npi_p7_05_routes_disabled")
        self.frappe.session.user = "Guest"
        response = self.call(
            self.api.create_readiness_template,
            {"score": 10_000, "ready": True},
        )
        self.assert_problem(response, 503, "READINESS_ROUTES_DISABLED")
        self.assertEqual(self.factory_calls, [])
        self.assertEqual(self.repository.calls, [])

    def test_authentication_csrf_and_role_precede_body_validation(self) -> None:
        malformed = {"score": 10_000, "ready": True}
        self.frappe.session.user = "Guest"
        response = self.call(self.api.create_readiness_template, malformed)
        self.assert_problem(response, 401, "AUTHENTICATION_REQUIRED")

        self.frappe.session.user = "admin@example.invalid"
        self.headers.pop("X-Frappe-CSRF-Token")
        response = self.call(self.api.create_readiness_template, malformed)
        self.assert_problem(response, 403, "CSRF_TOKEN_INVALID")

        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + "a" * 48
        self.frappe.session.user = "reader@example.invalid"
        response = self.call(self.api.create_readiness_template, malformed)
        self.assert_problem(response, 403, "PERMISSION_DENIED")
        self.assertEqual(self.factory_calls, [])
        self.assertEqual(self.repository.calls, [])

    def test_read_requires_internal_npi_api_user_and_mutation_requires_manager(self) -> None:
        self.frappe.session.user = "reader@example.invalid"
        response = self.call(
            self.api.get_readiness_templates,
            {"projectId": PROJECT_ID},
        )
        self.assertEqual(response, self.template_catalog_response)
        self.assertEqual(self.repository.calls[-1][0], "template_catalog")

        self.frappe.session.user = "ordinary@example.invalid"
        denied = self.call(
            self.api.get_readiness_templates,
            {"projectId": PROJECT_ID},
        )
        self.assert_problem(denied, 403, "PERMISSION_DENIED")

        self.frappe.session.user = "admin@example.invalid"
        created = self.call(self.api.create_readiness_template, self.template_payload())
        self.assertEqual(created, self.template_response)
        self.assertEqual(self.repository.calls[-1][0], "create_template")

        self.frappe.session.user = "reader@example.invalid"
        denied = self.call(self.api.create_readiness_template, self.template_payload())
        self.assert_problem(denied, 403, "PERMISSION_DENIED")

        self.frappe.session.user = "external@example.invalid"
        denied = self.call(
            self.api.get_readiness_templates,
            {"projectId": PROJECT_ID},
        )
        self.assert_problem(denied, 403, "PERMISSION_DENIED")
        denied = self.call(self.api.create_readiness_template, self.template_payload())
        self.assert_problem(denied, 403, "PERMISSION_DENIED")

    def test_query_and_commands_parse_opaque_project_and_secondary_ids(self) -> None:
        self.frappe.session.user = "reader@example.invalid"
        self.call(self.api.get_readiness_templates, {"projectId": PROJECT_ID})
        name, args, _kwargs = self.repository.calls[-1]
        self.assertEqual(name, "template_catalog")
        self.assertEqual(args, (UUID(PROJECT_ID),))

        self.call(self.api.get_project_readiness)
        name, args, _kwargs = self.repository.calls[-1]
        self.assertEqual(name, "readiness_workspace")
        self.assertEqual(args, (UUID(PROJECT_ID),))

        self.frappe.session.user = "admin@example.invalid"
        self.call(self.api.edit_readiness_template, self.edit_template_payload())
        name, args, _kwargs = self.repository.calls[-1]
        self.assertEqual(name, "edit_template")
        self.assertEqual(args, (UUID(TEMPLATE_ID), 1))

        self.call(self.api.revise_project_readiness, self.revise_payload())
        name, args, _kwargs = self.repository.calls[-1]
        self.assertEqual(name, "revise_readiness")
        self.assertEqual(args, (UUID(PROJECT_ID), UUID(INSTANCE_ID)))

    def test_malformed_route_ids_are_opaque_404_and_query_id_is_422(self) -> None:
        self.frappe.session.user = "reader@example.invalid"
        response = self.call(
            self.api.get_readiness_templates,
            {"projectId": "not-a-uuid"},
        )
        self.assert_problem(response, 422, "VALIDATION_FAILED")

        self.frappe.flags.npi_route_params["project_id"] = "not-a-uuid"
        response = self.call(self.api.get_project_readiness)
        self.assert_problem(response, 404, "READINESS_UNAVAILABLE")

        self.frappe.session.user = "admin@example.invalid"
        self.frappe.flags.npi_route_params["template_id"] = "not-a-uuid"
        response = self.call(
            self.api.publish_readiness_template,
            {"expectedOptimisticVersion": 3},
        )
        self.assert_problem(response, 404, "READINESS_TEMPLATE_UNAVAILABLE")

        self.frappe.flags.npi_route_params.update(
            project_id=PROJECT_ID,
            instance_id="not-a-uuid",
        )
        response = self.call(self.api.revise_project_readiness, self.revise_payload())
        self.assert_problem(response, 404, "READINESS_UNAVAILABLE")
        self.assertEqual(self.repository.calls, [])

    def test_template_nested_payload_is_strictly_closed(self) -> None:
        cases = (
            ("applicability", "score", "applicability.score"),
            ("category", "state", "categories[0].state"),
            ("item", "ready", "items[0].ready"),
            (
                "requirement",
                "sourceState",
                "items[0].evidenceRequirements[0].sourceState",
            ),
        )
        for location, field, expected_path in cases:
            payload = self.template_payload()
            if location == "applicability":
                payload["applicability"][field] = True
            elif location == "category":
                payload["categories"][0][field] = "complete"
            elif location == "item":
                payload["items"][0][field] = True
            else:
                payload["items"][0]["evidenceRequirements"][0][field] = "satisfied"
            with self.subTest(location=location):
                response = self.call(self.api.create_readiness_template, payload)
                problem = self.assert_problem(response, 422, "VALIDATION_FAILED")
                self.assertEqual(problem["fieldErrors"][0]["path"], expected_path)
                self.assertEqual(self.repository.calls, [])

    def test_initialize_assignments_are_closed_and_server_truth_is_rejected(self) -> None:
        payload = self.initialize_payload()
        payload["score"] = 10_000
        response = self.call(self.api.initialize_project_readiness, payload)
        problem = self.assert_problem(response, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "score")

        payload = self.initialize_payload()
        payload["assignments"][0]["ownerUserId"] = "forged@example.invalid"
        response = self.call(self.api.initialize_project_readiness, payload)
        problem = self.assert_problem(response, 422, "VALIDATION_FAILED")
        self.assertEqual(
            problem["fieldErrors"][0]["path"],
            "assignments[0].ownerUserId",
        )
        self.assertEqual(self.repository.calls, [])

    def test_source_state_and_other_caller_derived_truth_are_rejected(self) -> None:
        for field, value in (
            ("state", "satisfied"),
            ("reasonCode", "passed"),
            ("blocker", False),
            ("score", 10_000),
            ("ready", True),
        ):
            payload = self.revise_payload()
            payload["sources"][0][field] = value
            with self.subTest(field=field):
                response = self.call(self.api.revise_project_readiness, payload)
                problem = self.assert_problem(response, 422, "VALIDATION_FAILED")
                self.assertEqual(
                    problem["fieldErrors"][0]["path"],
                    f"sources[0].{field}",
                )
                self.assertEqual(self.repository.calls, [])

    def test_external_source_is_identity_free_and_resolved_server_side(self) -> None:
        payload = self.revise_payload()
        payload["sources"] = [
            {"requirementKey": "quality_result", "kind": "erp_quality_result"}
        ]
        response = self.call(self.api.revise_project_readiness, payload)
        self.assertEqual(response, self.revise_response)
        source = self.repository.calls[-1][2]["source_requests"][0]
        self.assertEqual(source.kind.value, "erp_quality_result")
        self.assertIsNone(source.global_id)
        self.assertIsNone(source.source_version)
        self.assertIsNone(source.snapshot_hash)

        payload = self.revise_payload()
        payload["sources"] = [
            {
                "requirementKey": "quality_result",
                "kind": "erp_quality_result",
                "globalId": SOURCE_ID,
                "sourceVersion": 1,
                "snapshotHash": SHA256_A,
            }
        ]
        rejected = self.call(self.api.revise_project_readiness, payload)
        problem = self.assert_problem(rejected, 422, "VALIDATION_FAILED")
        self.assertEqual(
            {item["path"] for item in problem["fieldErrors"]},
            {
                "sources[0].globalId",
                "sources[0].sourceVersion",
                "sources[0].snapshotHash",
            },
        )

    def test_success_status_headers_and_repository_factory_context(self) -> None:
        cases = (
            (
                self.api.get_readiness_templates,
                {"projectId": PROJECT_ID},
                "reader@example.invalid",
                200,
                False,
                self.template_catalog_response,
            ),
            (
                self.api.create_readiness_template,
                self.template_payload(),
                "admin@example.invalid",
                201,
                True,
                self.template_response,
            ),
            (
                self.api.edit_readiness_template,
                self.edit_template_payload(),
                "admin@example.invalid",
                200,
                True,
                self.template_response,
            ),
            (
                self.api.publish_readiness_template,
                {"expectedOptimisticVersion": 3},
                "admin@example.invalid",
                200,
                True,
                self.published_template_response,
            ),
            (
                self.api.get_project_readiness,
                {},
                "reader@example.invalid",
                200,
                False,
                self.response,
            ),
            (
                self.api.initialize_project_readiness,
                self.initialize_payload(),
                "admin@example.invalid",
                201,
                True,
                self.initialize_response,
            ),
            (
                self.api.revise_project_readiness,
                self.revise_payload(),
                "admin@example.invalid",
                201,
                True,
                self.revise_response,
            ),
        )
        for function, payload, user, status, command, expected_response in cases:
            with self.subTest(function=function.__name__):
                self.frappe.session.user = user
                response = self.call(function, payload)
                self.assertEqual(response, expected_response)
                self.assertEqual(self.frappe.local.response.http_status_code, status)
                headers = self.frappe.flags.npi_response_headers
                self.assertEqual(headers["X-Request-ID"], REQUEST_ID)
                self.assertEqual(headers["X-Trace-ID"], self.headers["X-Trace-ID"])
                self.assertEqual(headers["Cache-Control"], "private, no-store")
                self.assertEqual(headers["Content-Type"], "application/json")
                if command:
                    self.assertEqual(headers["Idempotency-Replayed"], "false")
                else:
                    self.assertNotIn("Idempotency-Replayed", headers)
                factory = self.factory_calls[-1]
                self.assertEqual(factory["principal"].user_id, user)
                self.assertEqual(factory["principal"].tenant_id, "TENANT-A")
                self.assertEqual(factory["request_id"], REQUEST_ID)
                self.assertEqual(factory["trace_id"], self.headers["X-Trace-ID"])

    def test_replay_header_and_actor_bound_idempotency_hash(self) -> None:
        payload = self.template_payload()
        self.repository.replayed = True
        self.call(self.api.create_readiness_template, payload)
        first_hash = self.repository.calls[-1][2]["idempotency_key_hash"]
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )
        self.assertEqual(len(first_hash), 64)
        self.assertNotEqual(first_hash, self.headers["Idempotency-Key"])

        self.repository.replayed = False
        self.call(self.api.create_readiness_template, payload)
        self.assertEqual(
            self.repository.calls[-1][2]["idempotency_key_hash"], first_hash
        )

        self.frappe.session.user = "other-admin@example.invalid"
        self.call(self.api.create_readiness_template, payload)
        other_hash = self.repository.calls[-1][2]["idempotency_key_hash"]
        self.assertNotEqual(other_hash, first_hash)
        expected = hashlib.sha256(
            (
                "other-admin@example.invalid\x1f"
                + self.headers["Idempotency-Key"]
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(other_hash, expected)

    def test_unavailable_resources_return_closed_404_without_false_success(self) -> None:
        self.repository.available = False
        self.frappe.session.user = "reader@example.invalid"
        response = self.call(
            self.api.get_readiness_templates,
            {"projectId": PROJECT_ID},
        )
        self.assert_problem(response, 404, "READINESS_UNAVAILABLE")

        response = self.call(self.api.get_project_readiness)
        self.assert_problem(response, 404, "READINESS_UNAVAILABLE")

        self.frappe.session.user = "admin@example.invalid"
        response = self.call(self.api.create_readiness_template, self.template_payload())
        self.assert_problem(response, 404, "READINESS_TEMPLATE_UNAVAILABLE")
        self.assertEqual(self.frappe.db.rollback_count, 3)

    def test_invalid_request_id_returns_422_without_echoing_bad_header(self) -> None:
        self.headers["X-Request-ID"] = "not-a-request-id"
        self.frappe.session.user = "reader@example.invalid"
        response = self.call(
            self.api.get_readiness_templates,
            {"projectId": PROJECT_ID},
        )
        problem = self.assert_problem(response, 422, "VALIDATION_FAILED")
        response_id = self.frappe.flags.npi_response_headers["X-Request-ID"]
        self.assertNotEqual(response_id, "not-a-request-id")
        self.assertEqual(str(UUID(response_id)), response_id)
        self.assertEqual(problem["fieldErrors"][0]["path"], "requestId")

    def test_factory_failure_is_safe_500_with_no_exception_leak(self) -> None:
        def explode_factory(**_values: Any):
            raise RuntimeError("secret repository factory detail")

        self.api._repository_factory = explode_factory
        self.frappe.session.user = "reader@example.invalid"
        response = self.call(
            self.api.get_readiness_templates,
            {"projectId": PROJECT_ID},
        )
        problem = self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertNotIn("secret", str(problem).casefold())
        self.assertEqual(self.repository.calls, [])
        self.assertEqual(self.frappe.db.rollback_count, 1)

    def test_closed_response_boundary_rejects_invalid_or_tampered_values(self) -> None:
        secret = "database-password-must-not-escape"

        self.frappe.session.user = "reader@example.invalid"
        catalog = copy.deepcopy(self.template_catalog_response)
        catalog["databasePassword"] = secret
        self.repository.query_response = catalog
        response = self.call(
            self.api.get_readiness_templates,
            {"projectId": PROJECT_ID},
        )
        problem = self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertNotIn(secret, str(problem))

        self.repository.query_response = None
        self.frappe.session.user = "admin@example.invalid"
        template = copy.deepcopy(self.template_response)
        template.pop("snapshotHash")
        self.repository.command_response = template
        response = self.call(self.api.create_readiness_template, self.template_payload())
        problem = self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertNotIn("snapshotHash", str(problem))

        self.repository.command_response = None
        self.frappe.session.user = "reader@example.invalid"
        workspace = copy.deepcopy(self.response)
        workspace["permissions"]["canRevise"] = "true"
        self.repository.query_response = workspace
        response = self.call(self.api.get_project_readiness)
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")

        self.repository.query_response = None
        self.repository.command_response = {
            **copy.deepcopy(self.template_response),
            "databasePassword": secret,
        }
        self.repository.replayed = True
        self.frappe.session.user = "admin@example.invalid"
        response = self.call(self.api.create_readiness_template, self.template_payload())
        problem = self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertNotIn(secret, str(problem))
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "false",
        )
        self.assertEqual(self.frappe.db.rollback_count, 4)

    def test_response_boundary_enforces_openapi_minimums_and_project_scope(
        self,
    ) -> None:
        empty_draft = copy.deepcopy(self.template_response)
        empty_draft["categories"] = []
        empty_draft["items"] = []
        empty_snapshot = {
            key: value
            for key, value in empty_draft.items()
            if key != "snapshotHash"
        }
        empty_draft["snapshotHash"] = hashlib.sha256(
            json.dumps(
                empty_snapshot,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.repository.command_response = empty_draft
        response = self.call(
            self.api.create_readiness_template,
            self.template_payload(),
        )
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")

        self.repository.command_response = None
        self.repository.query_response = {
            **copy.deepcopy(self.response),
            "projectGlobalId": "6493572f-0e17-49cb-a17f-428f12bbdc9a",
        }
        self.frappe.session.user = "reader@example.invalid"
        response = self.call(self.api.get_project_readiness)
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertEqual(self.frappe.db.rollback_count, 2)

    def test_replay_response_is_bound_to_operation_and_route_identity(self) -> None:
        self.repository.replayed = True
        self.repository.command_response = copy.deepcopy(
            self.published_template_response
        )
        response = self.call(
            self.api.create_readiness_template,
            self.template_payload(),
        )
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "false",
        )

        self.repository.command_response = copy.deepcopy(self.initialize_response)
        response = self.call(
            self.api.revise_project_readiness,
            self.revise_payload(),
        )
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")

        self.repository.command_response = copy.deepcopy(self.template_response)
        self.frappe.flags.npi_route_params["template_id"] = (
            "6493572f-0e17-49cb-a17f-428f12bbdc9a"
        )
        response = self.call(
            self.api.edit_readiness_template,
            self.edit_template_payload(),
        )
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertEqual(self.frappe.db.rollback_count, 3)

    def test_invalid_command_response_and_replay_flag_fail_safely(self) -> None:
        self.repository.command_response = []
        response = self.call(self.api.create_readiness_template, self.template_payload())
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")

        self.repository.command_response = self.template_response
        self.repository.replayed = "true"
        response = self.call(self.api.create_readiness_template, self.template_payload())
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertEqual(self.frappe.db.rollback_count, 2)

    def test_invalid_query_response_fails_safely_instead_of_leaking_shape(self) -> None:
        self.repository.query_response = ["not", "a", "closed", "mapping"]
        self.frappe.session.user = "reader@example.invalid"
        response = self.call(
            self.api.get_readiness_templates,
            {"projectId": PROJECT_ID},
        )
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertEqual(self.frappe.db.rollback_count, 1)


if __name__ == "__main__":
    unittest.main()
