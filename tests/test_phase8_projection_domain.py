from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.projections.config import (
    ProjectionAdapterConfiguration,
    ProjectionConfigurationState,
)
from npi_integration.projections.domain import (
    PROJECTION_DEFINITIONS,
    AdapterMode,
    ApplicationDisposition,
    CurrentProjectionIdentity,
    ProjectionAvailability,
    ProjectionContext,
    ProjectionContractError,
    ProjectionFreshness,
    ProjectionKind,
    ProjectionReaderResult,
    ProjectionScopeKind,
    canonical_payload_hash,
    classify_observation,
    projection_freshness,
)


NOW = datetime(2026, 8, 16, 2, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def values(kind: ProjectionKind) -> dict[str, object]:
    master_id = str(uid(20))
    if kind in {ProjectionKind.CUSTOMER_MASTER, ProjectionKind.SUPPLIER_MASTER}:
        return {
            "code": "MASTER-SYNTHETIC-001",
            "displayName": "Synthetic Master",
            "enabled": True,
            "statusCode": "enabled",
        }
    if kind is ProjectionKind.FORMAL_ITEM_MASTER:
        return {
            "itemCode": "ITEM-SYNTHETIC-001",
            "stockUom": "PCS",
            "enabled": True,
            "statusCode": "enabled",
        }
    if kind is ProjectionKind.TOOLING_PROCUREMENT_COST:
        return {
            "toolingMasterGlobalId": master_id,
            "supplier": {
                "sourceObjectId": "SUP-SYNTHETIC-001",
                "targetVersion": "opaque-supplier-version",
                "supplierCode": "SUP-SYNTHETIC-001",
                "supplierName": "Synthetic Supplier",
            },
            "rows": [
                {
                    "toolingMasterGlobalId": master_id,
                    "sourceRowId": "ROW-SYNTHETIC-001",
                    "sourceRowVersion": "opaque-row-version",
                    "supplierSourceObjectId": "SUP-SYNTHETIC-001",
                    "purchaseOrderSourceId": "PO-SYNTHETIC-001",
                    "purchaseReceiptSourceId": "PR-SYNTHETIC-001",
                    "purchaseInvoiceSourceId": "PI-SYNTHETIC-001",
                    "actualCostSourceId": "COST-SYNTHETIC-001",
                    "costTypeCode": "tool_build",
                    "postingDate": "2026-08-15",
                    "currency": "CNY",
                    "amount": "1200.50",
                }
            ],
        }
    if kind is ProjectionKind.PROJECT_COST:
        return {
            "rows": [
                {
                    "rowKind": "actual_cost",
                    "sourceRowId": "COST-SYNTHETIC-001",
                    "sourceRowVersion": "opaque-cost-version",
                    "postingDate": "2026-08-15",
                    "currency": "CNY",
                    "amount": "88.25",
                    "hours": None,
                },
                {
                    "rowKind": "labor_hours",
                    "sourceRowId": "LABOR-SYNTHETIC-001",
                    "sourceRowVersion": "opaque-labor-version",
                    "postingDate": "2026-08-15",
                    "currency": None,
                    "amount": None,
                    "hours": "7.5",
                },
            ]
        }
    if kind is ProjectionKind.FORMAL_QUALITY_STATUS:
        return {
            "recordKind": "quality_inspection",
            "statusCode": "submitted",
            "resultCode": "accepted",
            "observedAt": "2026-08-15T18:00:00Z",
        }
    if kind is ProjectionKind.TOOL_ASSET_STATUS:
        return {
            "toolingSetGlobalId": str(uid(30)),
            "mappingVersion": 1,
            "formalAssetId": "ASSET-SYNTHETIC-001",
            "targetVersion": "opaque-asset-version",
            "assetState": "active",
            "currentLocation": "Synthetic Tool Room",
            "shotCount": 100,
            "expectedLifeShots": 100000,
            "maintenanceDue": "2026-12-31",
            "movements": [],
            "repairs": [],
            "spares": [],
        }
    raise AssertionError(kind)


def scope(kind: ProjectionKind) -> ProjectionScopeKind:
    return next(iter(PROJECTION_DEFINITIONS[kind].scopes))


def available(
    kind: ProjectionKind = ProjectionKind.CUSTOMER_MASTER,
    *,
    modified_at: datetime = NOW,
    version: str = "opaque-version-a",
) -> ProjectionReaderResult:
    return ProjectionReaderResult(
        kind=kind,
        adapter_mode=AdapterMode.SANDBOX,
        source_environment="sandbox",
        source_object_id="SOURCE-SYNTHETIC-001",
        source_version=version,
        source_modified_at=modified_at,
        availability=ProjectionAvailability.AVAILABLE,
        values=values(kind),
    )


class Phase8ProjectionDomainTest(unittest.TestCase):
    def test_catalog_is_exact_and_every_kind_normalizes_a_closed_payload(self) -> None:
        self.assertEqual(
            set(PROJECTION_DEFINITIONS),
            {
                ProjectionKind.CUSTOMER_MASTER,
                ProjectionKind.SUPPLIER_MASTER,
                ProjectionKind.FORMAL_ITEM_MASTER,
                ProjectionKind.TOOLING_PROCUREMENT_COST,
                ProjectionKind.PROJECT_COST,
                ProjectionKind.FORMAL_QUALITY_STATUS,
                ProjectionKind.TOOL_ASSET_STATUS,
            },
        )
        for index, kind in enumerate(ProjectionKind, start=1):
            with self.subTest(kind=kind):
                result = available(kind)
                context = ProjectionContext(
                    tenant_id="tenant-synthetic",
                    project_global_id=uid(1),
                    scope_kind=scope(kind),
                    scope_global_id=(uid(1) if scope(kind) is ProjectionScopeKind.PROJECT else uid(100 + index)),
                )
                payload = result.event_payload(context=context, received_at=NOW)
                self.assertEqual(payload["projection_kind"], kind.value)
                self.assertEqual(payload["availability"], "available")
                self.assertIsInstance(payload["values"], dict)
        tenant_context = ProjectionContext(
            tenant_id="tenant@synthetic",
            project_global_id=uid(1),
            scope_kind=ProjectionScopeKind.PROJECT,
            scope_global_id=uid(1),
        )
        self.assertEqual(tenant_context.tenant_id, "tenant@synthetic")

    def test_payloads_reject_extra_missing_wrong_type_and_oversize_input(self) -> None:
        baseline = values(ProjectionKind.CUSTOMER_MASTER)
        for invalid in (
            {**baseline, "secret": "must-not-land"},
            {key: value for key, value in baseline.items() if key != "enabled"},
            {**baseline, "enabled": 1},
            {**baseline, "displayName": "x" * 201},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ProjectionContractError):
                    replace(available(), values=invalid)
        duplicated = values(ProjectionKind.PROJECT_COST)
        duplicated["rows"] = [duplicated["rows"][0], duplicated["rows"][0]]
        with self.assertRaises(ProjectionContractError):
            available(ProjectionKind.PROJECT_COST, version="v2").__class__(
                kind=ProjectionKind.PROJECT_COST,
                adapter_mode=AdapterMode.SANDBOX,
                source_environment="sandbox",
                source_object_id="SOURCE-SYNTHETIC-001",
                source_version="v2",
                source_modified_at=NOW,
                availability=ProjectionAvailability.AVAILABLE,
                values=duplicated,
            )
        asset = values(ProjectionKind.TOOL_ASSET_STATUS)
        asset["movements"] = [
            {
                "globalId": str(uid(70)),
                "actionKind": "delete",
                "fromLocation": None,
                "toLocation": "Synthetic Tool Room",
                "occurredAt": "2026-08-15T18:00:00Z",
                "sourceObjectId": "MOVE-SYNTHETIC-001",
            }
        ]
        with self.assertRaises(ProjectionContractError):
            replace(available(ProjectionKind.TOOL_ASSET_STATUS), values=asset)
        asset = values(ProjectionKind.TOOL_ASSET_STATUS)
        asset["spares"] = [
            {
                "formalItemId": "ITEM-SYNTHETIC-001",
                "description": "Synthetic spare",
                "stockOnHand": "1",
                "minimumStock": "1",
                "unit": "U" * 33,
                "supplierId": None,
            }
        ]
        with self.assertRaises(ProjectionContractError):
            replace(available(ProjectionKind.TOOL_ASSET_STATUS), values=asset)

    def test_hash_is_canonical_and_rejects_non_object_input(self) -> None:
        first = canonical_payload_hash({"b": 2, "a": 1})
        second = canonical_payload_hash({"a": 1, "b": 2})
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        with self.assertRaises(ProjectionContractError):
            canonical_payload_hash([])  # type: ignore[arg-type]

    def test_ordering_uses_modified_time_and_never_lexically_orders_opaque_versions(self) -> None:
        current = CurrentProjectionIdentity(
            event_id=uid(10),
            source_object_id="SOURCE-SYNTHETIC-001",
            source_version="z-opaque",
            source_modified_at=NOW,
            payload_hash="a" * 64,
        )
        cases = (
            (available(modified_at=NOW + timedelta(seconds=1), version="a-opaque"), uid(11), "b" * 64, ApplicationDisposition.APPLIED_CURRENT),
            (available(modified_at=NOW - timedelta(seconds=1), version="zzzz"), uid(12), "b" * 64, ApplicationDisposition.SUPERSEDED),
            (available(modified_at=NOW, version="z-opaque"), uid(13), "a" * 64, ApplicationDisposition.DUPLICATE_EXACT),
            (available(modified_at=NOW, version="a-opaque"), uid(14), "b" * 64, ApplicationDisposition.CONFLICTED),
            (available(modified_at=NOW + timedelta(seconds=1)), uid(10), "a" * 64, ApplicationDisposition.DUPLICATE_EXACT),
            (available(modified_at=NOW + timedelta(seconds=1)), uid(10), "b" * 64, ApplicationDisposition.CONFLICTED),
        )
        for result, event_id, payload_hash, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    classify_observation(
                        current,
                        event_id=event_id,
                        result=result,
                        payload_hash=payload_hash,
                    ),
                    expected,
                )

    def test_availability_is_separate_from_freshness_and_no_policy_means_unknown(self) -> None:
        self.assertEqual(
            projection_freshness(observed_at=NOW, now=NOW + timedelta(days=90), maximum_age_seconds=None),
            ProjectionFreshness.UNKNOWN,
        )
        self.assertEqual(
            projection_freshness(observed_at=NOW, now=NOW + timedelta(seconds=60), maximum_age_seconds=60),
            ProjectionFreshness.FRESH,
        )
        self.assertEqual(
            projection_freshness(observed_at=NOW, now=NOW + timedelta(seconds=61), maximum_age_seconds=60),
            ProjectionFreshness.STALE,
        )

    def test_mock_is_network_free_unavailable_and_synthetic_never_becomes_formal_truth(self) -> None:
        config = ProjectionAdapterConfiguration()
        self.assertEqual(config.state, ProjectionConfigurationState.DISABLED)
        unavailable = ProjectionReaderResult(
            kind=ProjectionKind.CUSTOMER_MASTER,
            adapter_mode=AdapterMode.MOCK,
            source_environment="mock",
            source_object_id="SOURCE-SYNTHETIC-001",
            source_version=None,
            source_modified_at=None,
            availability=ProjectionAvailability.UNAVAILABLE,
            values=None,
            unavailable_reason_code="provider_unavailable",
        )
        self.assertEqual(
            classify_observation(None, event_id=uid(50), result=unavailable, payload_hash="c" * 64),
            ApplicationDisposition.UNAVAILABLE_CURRENT,
        )
        current = CurrentProjectionIdentity(
            event_id=uid(50),
            source_object_id="SOURCE-SYNTHETIC-001",
            source_version="opaque-version",
            source_modified_at=NOW,
            payload_hash="c" * 64,
        )
        self.assertEqual(
            classify_observation(current, event_id=uid(50), result=unavailable, payload_hash="e" * 64),
            ApplicationDisposition.CONFLICTED,
        )
        with self.assertRaises(ProjectionContractError):
            replace(unavailable, availability=ProjectionAvailability.AVAILABLE, values=values(ProjectionKind.CUSTOMER_MASTER))
        synthetic = replace(
            available(),
            adapter_mode=AdapterMode.SYNTHETIC,
            availability=ProjectionAvailability.SYNTHETIC,
            source_environment="disposable-test",
        )
        self.assertEqual(
            classify_observation(None, event_id=uid(51), result=synthetic, payload_hash="d" * 64),
            ApplicationDisposition.SYNTHETIC_RETAINED,
        )

    def test_sandbox_configuration_is_explicit_allowlisted_and_fail_closed(self) -> None:
        valid = ProjectionAdapterConfiguration(
            mode=AdapterMode.SANDBOX,
            enabled=True,
            base_url="https://erp.sandbox.example.test",
            allowed_hostnames=("erp.sandbox.example.test",),
            allowed_operations=(ProjectionKind.CUSTOMER_MASTER,),
            secret_reference="secrets/erp-sandbox-read",
            environment_code="sandbox",
            non_production_attested=True,
        )
        self.assertEqual(valid.state, ProjectionConfigurationState.ENABLED_NON_PRODUCTION)
        invalid_changes = (
            {"base_url": "http://erp.sandbox.example.test"},
            {"base_url": "https://user:secret@erp.sandbox.example.test"},
            {"base_url": "https://127.0.0.1"},
            {"base_url": "https://[::"},
            {"base_url": "https://erp.sandbox.example.test:invalid"},
            {"base_url": "https://bad_host.sandbox.example.test", "allowed_hostnames": ("bad_host.sandbox.example.test",)},
            {"base_url": "https://erp.prod.example.test", "allowed_hostnames": ("erp.prod.example.test",)},
            {"allowed_hostnames": ("other.sandbox.example.test",)},
            {"allowed_hostnames": ("erp.sandbox.example.test", "erp.prod.example.test")},
            {"allowed_hostnames": ["erp.sandbox.example.test"]},
            {"allowed_operations": ()},
            {"allowed_operations": [ProjectionKind.CUSTOMER_MASTER]},
            {"secret_reference": None},
            {"secret_reference": "inline-password"},
            {"secret_reference": "secrets/erp/../production"},
            {"environment_code": None},
            {"follow_redirects": True},
            {"non_production_attested": False},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes), self.assertRaises(ProjectionContractError):
                replace(valid, **changes)


if __name__ == "__main__":
    unittest.main()
