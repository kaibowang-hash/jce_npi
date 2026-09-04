from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "apps/npi_core")

from npi_core.reporting.domain import (
    CONFIGURATION_CAPABILITIES,
    KPI_DEFINITIONS,
    Availability,
    PageCursor,
    PortfolioFilters,
    SearchKind,
    decode_cursor,
    encode_cursor,
    page_size,
    query_fingerprint,
    search_kinds,
    search_term,
    source_availability,
)
from npi_core.foundation.errors import RequestValidationFailed


class Phase9ReportingDomainTest(unittest.TestCase):
    def test_filters_are_closed_normalized_and_cover_required_facets(self) -> None:
        filters = PortfolioFilters(
            customer_reference_key="CUST-001",
            owner_user_id="PM@Example.invalid",
            project_type="new_tool",
            factory_reference_key="WH-JC-01",
            sop_month="2026-09",
            lifecycle_state="active",
        )
        self.assertEqual(
            filters.canonical_dict(),
            {
                "customerReferenceKey": "CUST-001",
                "factoryReferenceKey": "WH-JC-01",
                "lifecycleState": "active",
                "ownerUserId": "pm@example.invalid",
                "projectType": "new_tool",
                "sopMonth": "2026-09",
            },
        )
        for invalid in (
            {"sop_month": "2026-13"},
            {"project_type": "other"},
            {"lifecycle_state": "done"},
            {"customer_reference_key": "bad value"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(RequestValidationFailed):
                PortfolioFilters(**invalid)

    def test_search_and_page_inputs_are_bounded(self) -> None:
        self.assertEqual(search_term("  mold   trial "), "mold trial")
        self.assertEqual(
            search_kinds(["tooling", "project"]),
            (SearchKind.PROJECT, SearchKind.TOOLING),
        )
        self.assertEqual(page_size(None), 25)
        self.assertEqual(page_size(100), 100)
        for invalid in ("x", " " * 3, "x" * 101):
            with self.subTest(invalid=invalid), self.assertRaises(RequestValidationFailed):
                search_term(invalid)
        for invalid in (0, 101, True, "25"):
            with self.subTest(invalid=invalid), self.assertRaises(RequestValidationFailed):
                page_size(invalid)

    def test_cursor_is_signed_and_bound_to_exact_query(self) -> None:
        signing_key = b"k" * 32
        fingerprint = query_fingerprint("portfolio", {"owner": "pm@example.invalid"})
        cursor = PageCursor(fingerprint, "2026-09-03T00:00:00Z", "project-1")
        encoded = encode_cursor(cursor, signing_key)
        self.assertEqual(decode_cursor(encoded, signing_key, fingerprint), cursor)
        with self.assertRaises(RequestValidationFailed):
            decode_cursor(encoded + "x", signing_key, fingerprint)
        with self.assertRaises(RequestValidationFailed):
            decode_cursor(
                encoded,
                signing_key,
                query_fingerprint("portfolio", {"owner": "other@example.invalid"}),
            )

    def test_kpi_definitions_freeze_calculation_sources_before_values(self) -> None:
        self.assertEqual(
            [definition.key for definition in KPI_DEFINITIONS],
            [
                "project_sop_on_time_rate",
                "project_cycle_time_days",
                "trial_first_pass_rate",
                "project_cost_variance_rate",
            ],
        )
        for definition in KPI_DEFINITIONS:
            value = definition.public_dict()
            self.assertEqual(value["schemaVersion"], 1)
            self.assertTrue(value["numeratorSource"])
            self.assertTrue(value["denominatorSource"])
            self.assertEqual(value["timeZone"], "site")

    def test_unavailable_and_partial_sources_never_collapse_to_available(self) -> None:
        self.assertEqual(source_availability(()), Availability.UNAVAILABLE)
        self.assertEqual(
            source_availability((Availability.UNAVAILABLE, Availability.UNAVAILABLE)),
            Availability.UNAVAILABLE,
        )
        self.assertEqual(
            source_availability((Availability.AVAILABLE, Availability.STALE)),
            Availability.STALE,
        )
        self.assertEqual(
            source_availability((Availability.AVAILABLE, Availability.UNAVAILABLE)),
            Availability.PARTIAL,
        )

    def test_configuration_catalog_has_only_explicit_read_only_links(self) -> None:
        self.assertGreaterEqual(len(CONFIGURATION_CAPABILITIES), 6)
        self.assertEqual(
            {item["mode"] for item in CONFIGURATION_CAPABILITIES},
            {"versioned_commands", "operation_specific"},
        )
        self.assertTrue(all(item["route"].startswith("/administration/") for item in CONFIGURATION_CAPABILITIES))
        self.assertFalse(any("doctype" in item["route"].casefold() for item in CONFIGURATION_CAPABILITIES))


if __name__ == "__main__":
    unittest.main()
