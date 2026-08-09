from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.export_domain import (
    MAX_TOOLING_EXPORT_OBJECTS,
    TOOLING_LIST_COLUMN_IDS,
    TOOLING_OBJECT_PACKAGE_VALIDITY,
    ToolingExportLanguage,
    ToolingExportMode,
    ToolingExportPackageIdentity,
    ToolingExportReference,
    ToolingExportSelection,
    ToolingListFilter,
    ToolingListGroupKey,
    ToolingListPreferenceSnapshot,
    ToolingListRow,
    ToolingListSortDirection,
    ToolingListSortKey,
    ToolingListViewId,
    ToolingSource,
    filtered_query_snapshot_hash,
    resolve_exact_selection,
    select_filtered_rows,
    tooling_list_preference_key_hash,
    tooling_export_receipt_key_hash,
)


PROJECT_ID = UUID("98000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 10, 2, 0, tzinfo=UTC)


def _row(
    index: int,
    *,
    title: str | None = None,
    applicability_count: int = 1,
    part_count: int = 1,
    set_count: int = 1,
    design_count: int = 1,
    latest_revision: int | None = 1,
    customer_owned: bool = False,
) -> ToolingListRow:
    return ToolingListRow(
        tooling_master_global_id=UUID(f"98000000-0000-4000-8000-{index:012d}"),
        tooling_master_snapshot_hash=f"{index:064x}",
        title=title or f"Tool {index:03d}",
        project_global_id=PROJECT_ID,
        project_code="NPI-980",
        originating_project_global_id=PROJECT_ID,
        applicability_count=applicability_count,
        distinct_part_revision_count=part_count,
        physical_set_count=set_count,
        design_revision_count=design_count,
        latest_revision_number=latest_revision,
        customer_owned_set=customer_owned,
        source=ToolingSource.MANUAL,
    )


class Phase6ToolingExportDomainTests(unittest.TestCase):
    def test_exact_ten_views_have_closed_membership_rules(self) -> None:
        self.assertEqual(
            tuple(item.value for item in ToolingListViewId),
            (
                "all",
                "missing_applicability",
                "single_part",
                "shared_parts",
                "missing_physical_set",
                "single_physical_set",
                "multiple_physical_sets",
                "missing_design_revision",
                "has_design_revision",
                "customer_owned_set",
            ),
        )
        row = _row(
            2,
            applicability_count=0,
            part_count=2,
            set_count=0,
            design_count=0,
            latest_revision=None,
            customer_owned=True,
        )
        matches = {view.value for view in ToolingListViewId if row.matches_view(view)}
        self.assertEqual(
            matches,
            {
                "all",
                "missing_applicability",
                "shared_parts",
                "missing_physical_set",
                "missing_design_revision",
                "customer_owned_set",
            },
        )

    def test_filtered_result_is_complete_stable_and_bound_to_exact_hashes(self) -> None:
        rows = (_row(3, title="Beta"), _row(1, title="Alpha"), _row(2, title="Alpha"))
        filter_spec = ToolingListFilter(
            search=" alpha ",
            sort_key=ToolingListSortKey.TITLE,
            sort_direction=ToolingListSortDirection.ASCENDING,
            group_key=ToolingListGroupKey.NONE,
        )
        selected = select_filtered_rows(rows, filter_spec)
        self.assertEqual(
            [row.tooling_master_global_id for row in selected],
            [_row(1).tooling_master_global_id, _row(2).tooling_master_global_id],
        )
        first_hash = filtered_query_snapshot_hash(filter_spec, rows)
        self.assertEqual(first_hash, filtered_query_snapshot_hash(filter_spec, reversed(rows)))
        self.assertNotEqual(
            first_hash,
            filtered_query_snapshot_hash(
                filter_spec,
                (rows[0], replace(rows[1], tooling_master_snapshot_hash="f" * 64), rows[2]),
            ),
        )

    def test_filtered_export_rejects_truncation_beyond_one_hundred(self) -> None:
        rows = tuple(_row(index) for index in range(1, MAX_TOOLING_EXPORT_OBJECTS + 2))
        with self.assertRaises(RequestValidationFailed):
            select_filtered_rows(rows, ToolingListFilter())

    def test_selection_is_exact_ordered_unique_and_stale_safe(self) -> None:
        rows = (_row(1), _row(2))
        selection = ToolingExportSelection((rows[1].reference(), rows[0].reference()))
        self.assertEqual(resolve_exact_selection(rows, selection), (rows[1], rows[0]))
        self.assertEqual(selection.snapshot_hash, ToolingExportSelection(selection.references).snapshot_hash)
        with self.assertRaises(RequestValidationFailed):
            ToolingExportSelection((rows[0].reference(), rows[0].reference()))
        stale = ToolingExportSelection(
            (ToolingExportReference(rows[0].tooling_master_global_id, "f" * 64),)
        )
        with self.assertRaises(RequestValidationFailed):
            resolve_exact_selection(rows, stale)

    def test_preference_is_scoped_to_project_actor_view_and_table_schema(self) -> None:
        filter_spec = ToolingListFilter(view_id=ToolingListViewId.SHARED_PARTS)
        preference = ToolingListPreferenceSnapshot(
            view_id=ToolingListViewId.SHARED_PARTS,
            filter_spec=filter_spec,
            column_order=tuple(reversed(TOOLING_LIST_COLUMN_IDS)),
            hidden_columns=("source",),
            column_widths=(("tooling", 260), ("source", 120)),
        )
        self.assertEqual(preference.snapshot_payload()["viewId"], "shared_parts")
        self.assertEqual(preference.snapshot_hash, preference.snapshot_hash)
        first_key = tooling_list_preference_key_hash(
            tenant_id="tenant-980",
            project_global_id=PROJECT_ID,
            actor_user_id="engineer@example.invalid",
            view_id=ToolingListViewId.SHARED_PARTS,
        )
        second_key = tooling_list_preference_key_hash(
            tenant_id="tenant-980",
            project_global_id=PROJECT_ID,
            actor_user_id="engineer@example.invalid",
            view_id=ToolingListViewId.ALL,
        )
        self.assertNotEqual(first_key, second_key)
        with self.assertRaises(RequestValidationFailed):
            replace(preference, hidden_columns=("selection",))

    def test_package_identity_has_exact_one_hour_validity_and_mode_rules(self) -> None:
        row = _row(1)
        identity = ToolingExportPackageIdentity(
            global_id=UUID("98000000-0000-4000-8000-000000000100"),
            tenant_id="tenant-980",
            project_global_id=PROJECT_ID,
            actor_user_id="engineer@example.invalid",
            mode=ToolingExportMode.SELECTION,
            language=ToolingExportLanguage.ENGLISH,
            query_snapshot_hash=None,
            references=(row.reference(),),
            generated_at=NOW,
            expires_at=NOW + TOOLING_OBJECT_PACKAGE_VALIDITY,
            request_id=UUID("98000000-0000-4000-8000-000000000101"),
            trace_id="trace-p6-08-domain",
        )
        self.assertEqual(identity.snapshot_payload()["confidentialityClass"], "internal_project")
        self.assertEqual(len(identity.snapshot_hash), 64)
        with self.assertRaises(RequestValidationFailed):
            replace(identity, expires_at=NOW + timedelta(minutes=59))
        with self.assertRaises(RequestValidationFailed):
            replace(identity, query_snapshot_hash="f" * 64)

    def test_receipt_key_is_actor_project_operation_and_idempotency_bound(self) -> None:
        from npi_core.tooling.export_domain import ToolingExportOperation

        values = {
            "tenant_id": "tenant-980",
            "project_global_id": PROJECT_ID,
            "actor_user_id": "engineer@example.invalid",
            "operation": ToolingExportOperation.CREATE,
            "idempotency_key_hash": "a" * 64,
        }
        first = tooling_export_receipt_key_hash(**values)
        self.assertEqual(first, tooling_export_receipt_key_hash(**values))
        self.assertNotEqual(
            first,
            tooling_export_receipt_key_hash(
                **{**values, "actor_user_id": "other@example.invalid"}
            ),
        )


if __name__ == "__main__":
    unittest.main()
