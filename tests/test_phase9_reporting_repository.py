from __future__ import annotations

import base64
import importlib
import inspect
import sys
import types
import unittest
from datetime import UTC, date, datetime
from typing import Any

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.security import Principal
from npi_core.reporting.domain import PortfolioFilters, SearchKind


NOW = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)


class Row(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


def project(number: int, *, owner: str, references=()) -> Row:
    identity = f"00000000-0000-4000-8000-{number:012d}"
    return Row(
        global_id=identity,
        tenant_id="TENANT-A",
        business_code=f"NPI-{number:03d}",
        title=f"Mold program {number}",
        project_type="new_tool",
        owner_user_id=owner,
        target_sop=date(2026, 9, number),
        lifecycle_state="active",
        optimistic_version=number,
        current_health_status="yellow",
        current_health_at=NOW,
        modified=NOW,
        references=[Row(value) for value in references],
    )


class Phase9ReportingRepositoryTest(unittest.TestCase):
    MODULES = ("frappe", "npi_core.reporting.frappe_repository")

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.projects = {
            item.global_id: item
            for item in (
                project(
                    1,
                    owner="owner@example.invalid",
                    references=(
                        {"reference_type": "customer", "source_object_id": "CUST-01"},
                        {"reference_type": "factory", "source_object_id": "WH-JC-01"},
                    ),
                ),
                project(2, owner="other@example.invalid"),
                project(3, owner="hidden@example.invalid"),
            )
        }
        self.query_calls: list[tuple[str, dict[str, Any]]] = []
        self.get_doc_calls = 0
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.local = types.SimpleNamespace(
            conf={"encryption_key": base64.urlsafe_b64encode(b"s" * 32).decode()}
        )
        frappe.conf = frappe.local.conf
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.get_all = self.get_all
        frappe.get_doc = self.get_doc
        sys.modules["frappe"] = frappe
        self.module = importlib.import_module("npi_core.reporting.frappe_repository")

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def repository(self, *, user="owner@example.invalid", roles=frozenset()):
        return self.module.FrappeReportingRepository(
            principal=Principal(
                user_id=user,
                roles=roles,
                tenant_id="TENANT-A",
                is_external=False,
            ),
            clock=lambda: NOW,
        )

    def get_doc(self, doctype: str, name: str):
        self.get_doc_calls += 1
        if doctype == "NPI Engineering Project" and name in self.projects:
            return self.projects[name]
        raise sys.modules["frappe"].DoesNotExistError()

    def get_all(self, doctype: str, **kwargs):
        self.query_calls.append((doctype, kwargs))
        if doctype == "NPI Engineering Project":
            return list(self.projects.values())
        if doctype == "NPI Project Member":
            if kwargs["filters"]["user_id"] == "member@example.invalid":
                return [
                    Row(
                        project_global_id=list(self.projects)[1],
                        effective_from=date(2026, 1, 1),
                        effective_to=None,
                    )
                ]
            return []
        if doctype == "NPI Project Reference":
            visible = set(kwargs["filters"]["parent"][1])
            reference_type = kwargs["filters"].get("reference_type")
            like_filter = kwargs["filters"].get("source_object_id")
            needle = "" if like_filter is None else str(like_filter[1]).strip("%").casefold()
            return [
                Row(
                    parent=project_id,
                    reference_type=reference["reference_type"],
                    source_object_id=reference["source_object_id"],
                )
                for project_id, item in self.projects.items()
                if project_id in visible
                for reference in item.references
                if (reference_type is None or reference["reference_type"] == reference_type)
                and needle in reference["source_object_id"].casefold()
            ]
        if doctype == "NPI Domain Work Item":
            visible = set(kwargs["filters"]["project_global_id"][1])
            if list(self.projects)[0] in visible:
                return [
                    Row(project_global_id=list(self.projects)[0], kind="action", due_at=datetime(2026, 9, 1, tzinfo=UTC), blocking=1, state_terminal=0),
                    Row(project_global_id=list(self.projects)[0], kind="decision_request", due_at=datetime(2026, 9, 5, tzinfo=UTC), blocking=0, state_terminal=0),
                ]
            return []
        if doctype == "NPI Gate Shell":
            visible = set(kwargs["filters"]["project_global_id"][1])
            return [
                Row(
                    project_global_id=project_id,
                    global_id="10000000-0000-4000-8000-000000000001",
                    gate_key="G2",
                    title="Design release",
                    sequence=2,
                    gate_due_date=date(2026, 9, 4),
                    review_state="in_review",
                    latest_decision_outcome="",
                )
                for project_id in visible
            ]
        if doctype == "NPI ERP Projection Head":
            return []
        if doctype == "NPI Tooling Master":
            visible = set(kwargs["filters"]["originating_project_global_id"][1])
            return [
                Row(
                    global_id="20000000-0000-4000-8000-000000000001",
                    originating_project_global_id=list(self.projects)[0],
                    title="Mold Alpha",
                    optimistic_version=1,
                )
            ] if list(self.projects)[0] in visible and "mold" in kwargs["or_filters"][0][2].casefold() else []
        return []

    def test_portfolio_filters_to_owned_or_active_member_projects_server_side(self) -> None:
        owner = self.repository().portfolio(filters=PortfolioFilters(), cursor=None, limit=25)
        self.assertEqual([item["businessCode"] for item in owner["items"]], ["NPI-001"])
        member = self.repository(user="member@example.invalid").portfolio(
            filters=PortfolioFilters(), cursor=None, limit=25
        )
        self.assertEqual([item["businessCode"] for item in member["items"]], ["NPI-002"])
        admin = self.repository(roles=frozenset({"System Manager"})).portfolio(
            filters=PortfolioFilters(), cursor=None, limit=25
        )
        self.assertEqual(len(admin["items"]), 3)
        self.assertTrue(owner["permissions"]["serverFiltered"])

    def test_portfolio_preserves_facets_work_and_unavailable_erp_truth(self) -> None:
        response = self.repository().portfolio(
            filters=PortfolioFilters(
                customer_reference_key="CUST-01",
                factory_reference_key="WH-JC-01",
                sop_month="2026-09",
            ),
            cursor=None,
            limit=25,
        )
        item = response["items"][0]
        self.assertEqual(item["customerReferenceKeys"], ["CUST-01"])
        self.assertEqual(item["factoryReferenceKeys"], ["WH-JC-01"])
        self.assertEqual(item["work"]["overdueCount"], 1)
        self.assertEqual(item["work"]["blockerCount"], 1)
        self.assertEqual(item["work"]["decisionCount"], 1)
        self.assertEqual(item["erp"]["availability"], "unavailable")
        self.assertEqual(item["erp"]["reasonCode"], "erp_projection_not_observed")
        self.assertNotIn("cost", item)

    def test_search_filters_every_object_through_visible_projects(self) -> None:
        response = self.repository().global_search(
            query="mold",
            kinds=(SearchKind.PROJECT, SearchKind.CUSTOMER, SearchKind.TOOLING),
            cursor=None,
            limit=25,
        )
        self.assertEqual({item["projectGlobalId"] for item in response["items"]}, {list(self.projects)[0]})
        self.assertEqual({item["kind"] for item in response["items"]}, {"project", "tooling"})
        customer = self.repository().global_search(
            query="cust",
            kinds=(SearchKind.CUSTOMER,),
            cursor=None,
            limit=25,
        )["items"][0]
        self.assertEqual(customer["sourceSystem"], "ERPNEXT")
        self.assertEqual(customer["availability"], "partial")
        self.assertEqual(customer["reasonCode"], "customer_reference_only")

    def test_signed_cursor_is_deterministic_and_tamper_evident(self) -> None:
        first = self.repository(roles=frozenset({"System Manager"})).portfolio(
            filters=PortfolioFilters(), cursor=None, limit=1
        )
        self.assertTrue(first["page"]["hasMore"])
        second = self.repository(roles=frozenset({"System Manager"})).portfolio(
            filters=PortfolioFilters(), cursor=first["page"]["nextCursor"], limit=1
        )
        self.assertNotEqual(first["items"][0]["globalId"], second["items"][0]["globalId"])
        with self.assertRaises(Exception):
            self.repository(roles=frozenset({"System Manager"})).portfolio(
                filters=PortfolioFilters(), cursor=first["page"]["nextCursor"] + "x", limit=1
            )

    def test_kpis_keep_missing_controlled_sources_unavailable(self) -> None:
        response = self.repository().kpi_trends(
            from_month="2026-01",
            to_month="2026-09",
            filters=PortfolioFilters(),
        )
        self.assertEqual(response["visibleProjectCount"], 1)
        self.assertEqual(len(response["series"]), 4)
        self.assertTrue(all(item["availability"] == "unavailable" for item in response["series"]))
        self.assertTrue(all(item["points"] == [] for item in response["series"]))

    def test_configuration_catalog_is_internal_admin_only_and_has_no_writer(self) -> None:
        with self.assertRaises(Exception):
            self.repository().configuration_catalog()
        result = self.repository(roles=frozenset({"System Manager"})).configuration_catalog()
        self.assertFalse(result["genericWriterAvailable"])
        self.assertEqual(result["mode"], "read_only_catalog")

    def test_repository_has_no_write_sql_external_or_permission_bypass(self) -> None:
        source = inspect.getsource(self.module)
        for forbidden in (
            ".insert(",
            ".save(",
            "frappe.db." + "sql",
            "frappe.db." + "commit",
            "ignore_permissions",
            "requests.",
            "httpx.",
            "enqueue(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("serverFiltered", source)
        self.assertIn("customer_reference_only", source)

    def test_portfolio_uses_a_fixed_number_of_batched_reads(self) -> None:
        self.query_calls.clear()
        self.repository(roles=frozenset({"System Manager"})).portfolio(
            filters=PortfolioFilters(), cursor=None, limit=25
        )
        doctypes = [doctype for doctype, _ in self.query_calls]
        self.assertEqual(
            doctypes,
            [
                "NPI Engineering Project",
                "NPI Project Reference",
                "NPI Domain Work Item",
                "NPI Gate Shell",
                "NPI ERP Projection Head",
            ],
        )
        by_doctype = {doctype: arguments for doctype, arguments in self.query_calls}
        self.assertEqual(
            by_doctype["NPI Domain Work Item"]["limit_page_length"],
            3_001,
        )
        self.assertEqual(
            by_doctype["NPI Gate Shell"]["limit_page_length"],
            301,
        )
        self.assertEqual(
            by_doctype["NPI ERP Projection Head"]["limit_page_length"],
            3_001,
        )
        self.assertEqual(self.get_doc_calls, 0)


if __name__ == "__main__":
    unittest.main()
