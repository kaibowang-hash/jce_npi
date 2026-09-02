from __future__ import annotations

import importlib
import sys
import types
import unittest
from typing import Any

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import PermissionDenied, ReportingRoutesDisabled, RequestValidationFailed
from npi_core.foundation.security import Principal


class Row(dict):
    def __getattr__(self, name: str) -> Any:
        return self[name]

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class Repository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def portfolio(self, **values):
        self.calls.append(("portfolio", values))
        return {"schemaVersion": 1, "items": []}

    def global_search(self, **values):
        self.calls.append(("search", values))
        return {"schemaVersion": 1, "items": []}

    def kpi_trends(self, **values):
        self.calls.append(("kpis", values))
        return {"schemaVersion": 1, "series": []}

    def configuration_catalog(self):
        self.calls.append(("configuration", {}))
        return {"schemaVersion": 1, "items": []}


class Phase9ReportingApiTest(unittest.TestCase):
    MODULES = ("frappe", "npi_core.reporting_api")

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.conf = Row(npi_p9_02_routes_disabled=False)
        frappe.local = types.SimpleNamespace(response=Row(), form_dict=Row())
        frappe.get_request_header = lambda name: (
            "00000000-0000-4000-8000-000000000001" if name == "X-Request-ID" else None
        )
        frappe.whitelist = lambda *, allow_guest=False, methods=None: (lambda function: function)
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.api = importlib.import_module("npi_core.reporting_api")
        self.repository = Repository()
        self.principal = Principal(
            user_id="pm@example.invalid",
            roles=frozenset({"NPI API User"}),
            tenant_id="TENANT-A",
        )
        self.api._repository_factory = lambda **_values: self.repository
        self.api.authenticated_user = lambda: self.principal.user_id
        self.api.authenticated_principal = lambda _actor: self.principal
        self.api.frappe_domain_call = lambda handle, **_values: handle()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def test_portfolio_parses_all_required_filters_and_page_bound(self) -> None:
        result = self.api.get_project_portfolio(
            customerReferenceKey="CUST-01",
            ownerUserId="PM@Example.invalid",
            projectType="new_tool",
            factoryReferenceKey="WH-JC-01",
            sopMonth="2026-09",
            lifecycleState="active",
            limit="50",
        )
        self.assertEqual(result["schemaVersion"], 1)
        name, values = self.repository.calls[-1]
        self.assertEqual(name, "portfolio")
        self.assertEqual(values["limit"], 50)
        self.assertEqual(values["filters"].owner_user_id, "pm@example.invalid")
        self.assertEqual(values["filters"].factory_reference_key, "WH-JC-01")

    def test_search_is_closed_bounded_and_typed(self) -> None:
        self.api.search(query=" mold  trial ", kinds="project,tooling", limit="10")
        name, values = self.repository.calls[-1]
        self.assertEqual(name, "search")
        self.assertEqual(values["query"], "mold trial")
        self.assertEqual(tuple(kind.value for kind in values["kinds"]), ("project", "tooling"))
        with self.assertRaises(RequestValidationFailed):
            self.api.search(query="x", kinds="project")
        with self.assertRaises(RequestValidationFailed):
            self.api.search(query="mold", kinds="unknown")

    def test_kpi_range_is_at_most_twenty_four_months(self) -> None:
        self.api.get_kpi_trends(fromMonth="2025-10", toMonth="2026-09")
        self.assertEqual(self.repository.calls[-1][0], "kpis")
        with self.assertRaises(RequestValidationFailed):
            self.api.get_kpi_trends(fromMonth="2024-09", toMonth="2026-09")

    def test_external_user_and_disabled_route_fail_closed(self) -> None:
        self.principal = Principal(
            user_id="external@example.invalid",
            is_external=True,
            tenant_id="TENANT-A",
        )
        with self.assertRaises(PermissionDenied):
            self.api.get_project_portfolio()
        self.principal = Principal(user_id="pm@example.invalid", tenant_id="TENANT-A")
        self.frappe.conf.npi_p9_02_routes_disabled = True
        with self.assertRaises(ReportingRoutesDisabled):
            self.api.get_project_portfolio()

    def test_unknown_fields_are_rejected_and_admin_catalog_stays_repository_guarded(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            self.api.search(query="mold", arbitrary="value")
        self.api.get_configuration_catalog()
        self.assertEqual(self.repository.calls[-1][0], "configuration")


if __name__ == "__main__":
    unittest.main()
