from __future__ import annotations

import ast
import importlib
import sys
import types
import unittest
from contextvars import ContextVar
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from tests.test_phase8_projection_domain import uid


PROJECT_ID = uid(1)
REQUEST_ID = str(uid(90))
API_PATH = ROOT / "apps/npi_integration/npi_integration/projection_api.py"
BFF_PATH = ROOT / "apps/npi_core/npi_core/bff.py"


class Problem(Exception):
    def __init__(self, *values: object) -> None:
        super().__init__(*values)
        self.values = values


class FakeRepository:
    owner: "Phase8ProjectionApiTest"

    def __init__(self, **_values: object) -> None:
        self.owner.events.append("repository")

    def authorize_project(self, project_id):
        self.owner.events.append("authorize_project")
        return None if self.owner.project_absent else {"project": str(project_id)}

    def project_collection(self, access, *, kind):
        self.owner.events.append("project_collection")
        return {
            "projectGlobalId": str(PROJECT_ID),
            "accessState": "available",
            "reasonCode": None,
            "permissions": {"view": True, "edit": False, "refresh": False},
            "items": [],
        }


class Phase8ProjectionApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.foundation.errors",
        "npi_core.foundation.tracing",
        "npi_core.project_api",
        "npi_core.request_security",
        "npi_integration.projection_api",
        "npi_integration.projections.frappe_repository",
        "npi_integration.projections.response",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[str] = []
        self.project_absent = False
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace(
            npi_route_params={"project_id": str(PROJECT_ID)}
        )
        self.frappe.conf = {"npi_p8_01_routes_disabled": False}
        self.frappe.get_request_header = lambda _name: REQUEST_ID
        self.frappe.whitelist = lambda **_values: lambda function: function
        sys.modules["frappe"] = self.frappe

        api_module = types.ModuleType("npi_core.api")
        api_module.frappe_domain_call = self.frappe_domain_call
        sys.modules["npi_core.api"] = api_module

        errors_module = types.ModuleType("npi_core.foundation.errors")
        errors_module.NpiProblem = Problem
        errors_module.RequestValidationFailed = Problem
        sys.modules["npi_core.foundation.errors"] = errors_module

        tracing_module = types.ModuleType("npi_core.foundation.tracing")
        tracing_module.current_trace_id = ContextVar("test_trace", default="trace-p8-api")
        sys.modules["npi_core.foundation.tracing"] = tracing_module

        project_module = types.ModuleType("npi_core.project_api")
        project_module.ProjectUnavailable = type("ProjectUnavailable", (Problem,), {})
        sys.modules["npi_core.project_api"] = project_module

        security_module = types.ModuleType("npi_core.request_security")
        security_module.authenticated_user = self.authenticated_user
        security_module.authenticated_principal = self.authenticated_principal
        security_module.reject_unexpected_request_fields = self.reject_fields
        security_module.response_request_id = lambda: REQUEST_ID
        sys.modules["npi_core.request_security"] = security_module

        repository_module = types.ModuleType(
            "npi_integration.projections.frappe_repository"
        )
        FakeRepository.owner = self
        repository_module.FrappeProjectionRepository = FakeRepository
        sys.modules[
            "npi_integration.projections.frappe_repository"
        ] = repository_module
        self.module = importlib.import_module("npi_integration.projection_api")
        self.response_module = importlib.import_module(
            "npi_integration.projections.response"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved_modules[name] is not None:
                sys.modules[name] = self.saved_modules[name]

    def frappe_domain_call(self, handle, **_values: object):
        return handle()

    def authenticated_user(self):
        self.events.append("authenticated_user")
        return "user@example.invalid"

    def authenticated_principal(self, _actor: str):
        self.events.append("authenticated_principal")
        return object()

    def reject_fields(self, allowed: frozenset[str], supplied: dict[str, Any]):
        self.events.append("reject_fields")
        if set(supplied) - set(allowed):
            raise Problem("unexpected field")

    def test_auth_and_project_authorization_precede_filter_parsing(self) -> None:
        with self.assertRaises(Problem):
            self.module.get_erp_projections(kind="not-a-kind")
        self.assertLess(self.events.index("authenticated_user"), self.events.index("repository"))
        self.assertLess(self.events.index("repository"), self.events.index("authorize_project"))
        self.assertLess(self.events.index("authorize_project"), self.events.index("reject_fields"))
        self.events.clear()
        with self.assertRaises(Problem):
            self.module.get_erp_projections(sourceObjectId="ERP-SECRET-ID")
        self.assertEqual(
            self.events[:5],
            [
                "authenticated_user",
                "authenticated_principal",
                "repository",
                "authorize_project",
                "reject_fields",
            ],
        )

    def test_absent_project_is_indistinguishable_before_optional_filter(self) -> None:
        self.project_absent = True
        with self.assertRaises(Problem):
            self.module.get_erp_projections(kind="not-a-kind", sourceObjectId="hidden")
        self.assertEqual(
            self.events,
            [
                "authenticated_user",
                "authenticated_principal",
                "repository",
                "authorize_project",
            ],
        )

    def test_route_switch_defaults_disabled_and_enabled_route_is_read_only(self) -> None:
        self.frappe.conf = {}
        with self.assertRaises(self.module.ProjectionRoutesDisabled):
            self.module.get_erp_projections()
        self.assertNotIn("project_collection", self.events)
        self.events.clear()
        self.frappe.conf = {"npi_p8_01_routes_disabled": False}
        response = self.module.get_erp_projections(kind="customer_master")
        self.assertEqual(response["accessState"], "available")
        self.assertIn("project_collection", self.events)

    def test_bff_registers_only_one_get_route_and_requires_request_id(self) -> None:
        api_source = API_PATH.read_text(encoding="utf-8")
        bff_source = BFF_PATH.read_text(encoding="utf-8")
        ast.parse(api_source)
        ast.parse(bff_source)
        self.assertIn('@frappe.whitelist(allow_guest=True, methods=["GET"])', api_source)
        self.assertNotIn('methods=["POST"]', api_source)
        self.assertIn("_PROJECT_ERP_PROJECTIONS_ROUTE", bff_source)
        self.assertIn(
            'command = "npi_integration.projection_api.get_erp_projections"',
            bff_source,
        )
        request_boundary = bff_source[bff_source.index("def _requires_project_request_id") :]
        self.assertIn("_PROJECT_ERP_PROJECTIONS_ROUTE.fullmatch(path)", request_boundary)

    def test_response_is_closed_typed_bounded_sorted_and_read_only(self) -> None:
        item = {
            "observationGlobalId": str(uid(10)),
            "projectionKind": "customer_master",
            "scopeKind": "project",
            "scopeGlobalId": str(PROJECT_ID),
            "availability": "available",
            "freshness": "fresh",
            "disposition": "applied_current",
            "sourceSystem": "ERPNEXT",
            "sourceObjectType": "Customer",
            "sourceObjectId": "CUSTOMER-SANDBOX-001",
            "sourceVersion": "opaque-v1",
            "sourceModifiedAt": "2026-08-16T08:00:00Z",
            "receivedAt": "2026-08-16T08:01:00Z",
            "payloadHash": "a" * 64,
            "unavailableReasonCode": None,
            "values": {
                "code": "CUSTOMER-SANDBOX-001",
                "displayName": "Sandbox Customer",
                "enabled": True,
                "statusCode": "enabled",
            },
            "currentTruth": {
                "observationGlobalId": str(uid(10)),
                "sourceVersion": "opaque-v1",
                "sourceModifiedAt": "2026-08-16T08:00:00Z",
                "receivedAt": "2026-08-16T08:01:00Z",
                "payloadHash": "a" * 64,
                "values": {
                    "code": "CUSTOMER-SANDBOX-001",
                    "displayName": "Sandbox Customer",
                    "enabled": True,
                    "statusCode": "enabled",
                },
            },
            "editable": False,
        }
        collection = {
            "projectGlobalId": str(PROJECT_ID),
            "accessState": "available",
            "reasonCode": None,
            "permissions": {"view": True, "edit": False, "refresh": False},
            "items": [item],
        }
        normalized = self.response_module.validate_project_projection_collection(
            collection,
            expected_project_global_id=PROJECT_ID,
        )
        self.assertEqual(normalized, collection)
        for invalid in (
            {**collection, "secret": "must-not-escape"},
            {**collection, "permissions": {"view": True, "edit": True, "refresh": False}},
            {**collection, "items": [{**item, "editable": True}]},
            {**collection, "items": [{**item, "sourceObjectType": "Supplier"}]},
            {**collection, "items": [{**item, "values": {**item["values"], "secret": "x"}}]},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.response_module.validate_project_projection_collection(
                    invalid,
                    expected_project_global_id=PROJECT_ID,
                )


if __name__ == "__main__":
    unittest.main()
