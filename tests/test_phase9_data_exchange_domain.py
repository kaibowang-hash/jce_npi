from __future__ import annotations

import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_core.data_exchange.domain import (
    ArchiveSourceKind,
    DatasetId,
    ExportLanguage,
    ExportProfileVersion,
    RedactionProfile,
    RetentionCategory,
    RetentionPolicyVersion,
    RetentionScope,
    archive_record_payload,
    calculate_retain_until,
    sha256_json,
)
from npi_core.foundation.errors import RequestValidationFailed


PROFILE_ID = UUID("00000000-0000-4000-8000-000000000061")
POLICY_ID = UUID("00000000-0000-4000-8000-000000000062")
NOW = datetime(2026, 9, 3, 8, 30, tzinfo=UTC)


def profile(**overrides) -> ExportProfileVersion:
    values = {
        "global_id": PROFILE_ID,
        "version": 1,
        "dataset_id": DatasetId.PROJECT_PORTFOLIO,
        "columns": ("projectCode", "title", "ownerUserId"),
        "language": ExportLanguage.ENGLISH,
        "redaction_profile": RedactionProfile.INTERNAL_REPORT,
        "query": (("lifecycleState", "active"),),
        "max_rows": 500,
        "max_bytes": 1_000_000,
        "published_by_user_id": "manager@example.invalid",
        "published_at": NOW,
    }
    values.update(overrides)
    return ExportProfileVersion(**values)


def policy(**overrides) -> RetentionPolicyVersion:
    values = {
        "global_id": POLICY_ID,
        "version": 2,
        "scope": RetentionScope.TENANT,
        "scope_reference": None,
        "effective_from": date(2026, 1, 1),
        "effective_until": None,
        "retention_years": tuple((category, 7) for category in RetentionCategory),
        "published_by_user_id": "manager@example.invalid",
        "published_at": NOW,
    }
    values.update(overrides)
    return RetentionPolicyVersion(**values)


class Phase9DataExchangeDomainTest(unittest.TestCase):
    def test_profile_is_closed_versioned_hash_bound_and_redacted_before_render(self) -> None:
        value = profile()
        self.assertEqual(value.response()["schemaVersion"], "data-exchange-export-profile.v1")
        self.assertEqual(value.definition_hash, sha256_json(value.definition_payload()))
        self.assertEqual(value.response()["outputs"], ["csv", "xlsx", "pdf", "readme"])
        with self.assertRaises(RequestValidationFailed):
            profile(columns=("projectCode", "password"))
        with self.assertRaises(RequestValidationFailed):
            profile(
                columns=("projectCode", "ownerUserId"),
                redaction_profile=RedactionProfile.MINIMUM_DISCLOSURE,
            )

    def test_kpi_profile_requires_exact_month_range_and_fixed_columns(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            profile(dataset_id=DatasetId.KPI_TRENDS, columns=("metricKey",), query=())
        value = profile(
            dataset_id=DatasetId.KPI_TRENDS,
            columns=("metricKey", "availability", "month", "value"),
            query=(("fromMonth", "2026-01"), ("toMonth", "2026-12")),
        )
        self.assertEqual(value.dataset_id, DatasetId.KPI_TRENDS)

    def test_policy_requires_all_categories_explicit_scope_and_effectivity(self) -> None:
        value = policy()
        self.assertTrue(value.applies(on_date=date(2026, 9, 3), scope=RetentionScope.TENANT, reference=None))
        self.assertEqual(value.years_for(RetentionCategory.FILE), 7)
        with self.assertRaises(RequestValidationFailed):
            policy(retention_years=((RetentionCategory.PROJECT, 7),))
        with self.assertRaises(RequestValidationFailed):
            policy(scope=RetentionScope.CUSTOMER, scope_reference=None)
        with self.assertRaises(RequestValidationFailed):
            policy(effective_until=date(2025, 12, 31))

    def test_retain_until_handles_leap_day_and_archive_binds_exact_truth(self) -> None:
        self.assertEqual(calculate_retain_until(date(2024, 2, 29), 1), date(2025, 2, 28))
        selected = policy()
        payload = archive_record_payload(
            global_id=UUID("00000000-0000-4000-8000-000000000063"),
            tenant_id="tenant-a",
            source_kind=ArchiveSourceKind.FILE_REVISION,
            source_id=UUID("00000000-0000-4000-8000-000000000064"),
            source_version=3,
            source_hash="a" * 64,
            source_date=date(2026, 3, 1),
            source_snapshot={"sha256": "a" * 64, "privateFileBound": True},
            policy=selected,
            retain_until=date(2033, 3, 1),
            actor="manager@example.invalid",
            created_at=NOW,
            request_id=UUID("00000000-0000-4000-8000-000000000065"),
            trace_id="trace-data-exchange-0001",
        )
        self.assertEqual(payload["category"], "file")
        self.assertEqual(payload["policyHash"], selected.definition_hash)
        self.assertNotIn("fileUrl", str(payload))


if __name__ == "__main__":
    unittest.main()
