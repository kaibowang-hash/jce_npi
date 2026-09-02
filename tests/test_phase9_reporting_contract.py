from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")


def path_block(path: str) -> str:
    start = OPENAPI.index(f"  {path}:\n", OPENAPI.index("paths:\n"))
    match = re.search(r"\n  /[^\n]+:\n|\ncomponents:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


def schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase9ReportingContractTest(unittest.TestCase):
    def test_four_read_only_routes_are_explicit_and_have_no_write_method(self) -> None:
        expected = {
            "/search": "searchNpiObjects",
            "/portfolio/projects": "getProjectPortfolio",
            "/reports/kpis": "getKpiTrends",
            "/administration/capabilities": "getConfigurationCapabilityCatalog",
        }
        for path, operation in expected.items():
            with self.subTest(path=path):
                block = path_block(path)
                self.assertEqual(re.findall(r"^    (get|post|put|patch|delete):$", block, re.MULTILINE), ["get"])
                self.assertIn(f"operationId: {operation}", block)
                self.assertIn("#/components/parameters/RequestId", block)
        self.assertIn("x-direction: NPI_ONE_TO_READ_ONLY_BI", path_block("/reports/kpis"))
        self.assertIn("x-reverse-write: prohibited", path_block("/reports/kpis"))

    def test_search_and_portfolio_contracts_are_closed_permission_filtered_and_paged(self) -> None:
        search = schema("GlobalSearchResponse")
        item = schema("GlobalSearchItem")
        portfolio = schema("ProjectPortfolioResponse")
        row = schema("ProjectPortfolioItem")
        for block in (search, item, portfolio, row):
            self.assertIn("additionalProperties: false", block)
        self.assertIn("serverFiltered", schema("ReportingPermissions"))
        self.assertIn("nextCursor", schema("ReportingPage"))
        self.assertIn("sourceSystem", item)
        self.assertIn("availability", item)
        self.assertIn("customerReferenceKeys", row)
        self.assertIn("factoryReferenceKeys", row)
        self.assertIn("currentGate", row)
        self.assertIn("work", row)
        self.assertIn("erp", row)

    def test_kpis_freeze_four_calculations_and_allow_no_fake_point(self) -> None:
        definition = schema("KpiDefinition")
        for key in (
            "project_sop_on_time_rate",
            "project_cycle_time_days",
            "trial_first_pass_rate",
            "project_cost_variance_rate",
        ):
            self.assertIn(key, definition)
        for field in ("numeratorSource", "denominatorSource", "sourceSystem", "timeZone"):
            self.assertIn(field, definition)
        series = schema("KpiSeries")
        self.assertIn("unavailable", schema("ReportingAvailability"))
        self.assertNotIn("minItems:", series.split("points:", 1)[1])

    def test_configuration_is_catalog_only_and_factory_is_an_additive_typed_reference(self) -> None:
        catalog = schema("ConfigurationCapabilityCatalog")
        self.assertIn("const: read_only_catalog", catalog)
        self.assertIn("const: false", catalog)
        self.assertIn("enum: [customer, factory, product, part, tooling, order]", OPENAPI)
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
        self.assertIn("factory_reference: {owner: NPI_ONE_PROJECT_COMMAND", ownership)
        self.assertIn("PortfolioAndReportingProjection:", ownership)
        self.assertIn("direction: NPI_ONE_TO_READ_ONLY_BI", ownership)
        self.assertIn("FIXED_DEFINITION_NO_FAKE_VALUE", ownership)
        self.assertIn("reverse_write_or_generic_configuration_mutation", ownership)
        self.assertNotIn("generic_doctype_writer", catalog.casefold())

    def test_bff_has_exact_routes_and_independent_fail_closed_switch(self) -> None:
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        security = (ROOT / "apps/npi_core/npi_core/request_security.py").read_text(encoding="utf-8")
        for path in (
            "/api/npi/v1/search",
            "/api/npi/v1/portfolio/projects",
            "/api/npi/v1/reports/kpis",
            "/api/npi/v1/administration/capabilities",
        ):
            self.assertIn(path, bff)
        self.assertIn("_p9_02_routes_disabled(command)", bff)
        self.assertIn("npi_p9_02_routes_disabled", security)
        self.assertIn("return value is not False", security)

    def test_collaboration_routes_are_exact_versioned_and_closed(self) -> None:
        expected = {
            "/projects/{projectId}/meetings": {"getProjectMeetings", "createProjectMeeting"},
            "/notifications": {"getInternalNotifications"},
            "/notifications/{notificationId}:mark-read": {"markInternalNotificationRead"},
            "/me/preferences/notifications": {"getNotificationPreference", "setNotificationPreference"},
        }
        for path, operations in expected.items():
            with self.subTest(path=path):
                block = path_block(path)
                self.assertEqual(
                    set(re.findall(r"^      operationId: ([A-Za-z0-9]+)$", block, re.MULTILINE)),
                    operations,
                )
                self.assertIn("tags: [Collaboration]", block)
        meeting = schema("MeetingMinute")
        for field in ("templateRef", "linkedItems", "contentHash", "createdBy", "version"):
            self.assertIn(field, meeting)
        self.assertIn("const: 1", meeting)
        notification = schema("InternalNotification")
        for field in ("source", "criticalAudit", "emailDeliveryState", "failureCode", "readAt"):
            self.assertIn(field, notification)
        self.assertNotIn("sent", notification)

    def test_collaboration_ownership_has_no_erp_or_dual_master_write(self) -> None:
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
        for object_name in ("MeetingMinute:", "InternalNotification:", "NotificationPreference:"):
            self.assertIn(object_name, ownership)
        self.assertIn("IMMUTABLE_SNAPSHOT", ownership)
        self.assertIn("IDEMPOTENT_RECIPIENT_PROJECTION", ownership)
        self.assertIn("QUEUED_FAILED_UNAVAILABLE_OR_NOT_REQUESTED_NO_FAKE_DELIVERY", ownership)
        self.assertIn("MANDATORY_NOT_USER_MUTABLE", ownership)


if __name__ == "__main__":
    unittest.main()
