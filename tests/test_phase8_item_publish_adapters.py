from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.item_publish.adapters import (
    ItemAdapterCommand,
    ItemAdapterRegistration,
    ItemAdapterRegistry,
    ItemAdapterResponse,
    classify_item_adapter_response,
    uncertain_item_adapter_result,
)
from npi_integration.item_publish.config import ItemExecutionProfile
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_OPERATION,
    ItemFaultKind,
    ItemPublishIntent,
    ItemPublishResultState,
    ItemResultAuthority,
    ItemTargetMode,
    canonical_hash,
)


NOW = datetime(2026, 8, 16, 15, 30, tzinfo=UTC)
REQUEST_ID = UUID("00000000-0000-4000-8000-000000008351")
ATTEMPT_ID = UUID("00000000-0000-4000-8000-000000008352")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000008353")


def profile(mode: ItemTargetMode) -> ItemExecutionProfile:
    common = {
        "profile_id": f"item-{mode.value}-v1",
        "profile_version": 1,
        "tenant_id": "TENANT-A",
        "project_global_id": str(PROJECT_ID),
        "target_mode": mode,
        "requester_user_ids": ("publisher@example.invalid",),
        "service_actor_user_id": "item-worker@example.invalid",
    }
    if mode is ItemTargetMode.SYNTHETIC:
        return ItemExecutionProfile(
            environment_code="disposable-test",
            allowed_operations=(ITEM_PUBLISH_OPERATION,),
            adapter_resolver=(
                "npi_integration.item_publish.runtime_fixture.synthetic_adapter"
            ),
            synthetic_test_only=True,
            disposable_runtime_marker=True,
            **common,
        )
    if mode is ItemTargetMode.SANDBOX:
        return ItemExecutionProfile(
            environment_code="sandbox",
            allowed_operations=(ITEM_PUBLISH_OPERATION,),
            adapter_resolver="npi_integration.item_publish.sandbox_adapter.resolve",
            base_url="https://erpnext.sandbox.example.invalid",
            allowed_hostnames=("erpnext.sandbox.example.invalid",),
            secret_reference="secrets/item-sandbox-v1",
            response_authentication="hmac-sha256-v1",
            connect_timeout_seconds=10,
            read_timeout_seconds=30,
            non_production_attested=True,
            **common,
        )
    return ItemExecutionProfile(environment_code="mock", **common)


def command() -> ItemAdapterCommand:
    source_payload = {
        "tenantId": "TENANT-A",
        "projectGlobalId": str(PROJECT_ID),
        "engineeringItemId": "ENG-ITEM-001",
        "selectedPublishNodeGlobalId": str(UUID(int=8354)),
        "itemMaster": {
            "description": "Synthetic released item",
            "engineeringUom": "Nos",
            "attributes": {"material": "PA66"},
        },
        "occurrences": [],
    }
    source_hash = canonical_hash(source_payload)
    source = {
        **source_payload,
        "streamKeyHash": "a" * 64,
        "sourceHash": source_hash,
    }
    return ItemAdapterCommand(
        request_global_id=REQUEST_ID,
        attempt_global_id=ATTEMPT_ID,
        attempt_number=1,
        target_idempotency_key_hash="b" * 64,
        source_hash=source_hash,
        source_snapshot=source,
        intent=ItemPublishIntent.CREATE_ITEM,
        expected_mapping_version=0,
        expected_target_version=None,
    )


def response(**changes: object) -> ItemAdapterResponse:
    value = command()
    fields: dict[str, object] = {
        "request_global_id": value.request_global_id,
        "attempt_global_id": value.attempt_global_id,
        "attempt_number": value.attempt_number,
        "target_idempotency_key_hash": value.target_idempotency_key_hash,
        "source_hash": value.source_hash,
        "response_hash": "c" * 64,
    }
    fields.update(changes)
    return ItemAdapterResponse(**fields)  # type: ignore[arg-type]


class Phase8ItemPublishAdapterTest(unittest.TestCase):
    def test_registry_is_empty_by_default_and_resolves_only_exact_closed_tuple(self) -> None:
        synthetic = profile(ItemTargetMode.SYNTHETIC)
        adapter = lambda value: response()
        self.assertIsNone(ItemAdapterRegistry().resolve(synthetic))
        registry = ItemAdapterRegistry(
            (
                ItemAdapterRegistration(
                    resolver_path=str(synthetic.adapter_resolver),
                    target_mode=ItemTargetMode.SYNTHETIC,
                    operation=ITEM_PUBLISH_OPERATION,
                    adapter=adapter,
                ),
            )
        )
        self.assertIs(registry.resolve(synthetic), adapter)
        self.assertIsNone(registry.resolve(profile(ItemTargetMode.SANDBOX)))
        self.assertIsNone(registry.resolve(profile(ItemTargetMode.MOCK)))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            ItemAdapterRegistry(
                (
                    ItemAdapterRegistration(
                        str(synthetic.adapter_resolver),
                        ItemTargetMode.SYNTHETIC,
                        ITEM_PUBLISH_OPERATION,
                        adapter,
                    ),
                    ItemAdapterRegistration(
                        str(synthetic.adapter_resolver),
                        ItemTargetMode.SYNTHETIC,
                        ITEM_PUBLISH_OPERATION,
                        adapter,
                    ),
                )
            )

    def test_synthetic_success_is_non_authoritative_without_formal_identity(self) -> None:
        value = classify_item_adapter_response(
            profile=profile(ItemTargetMode.SYNTHETIC),
            command=command(),
            response=response(),
            observed_at=NOW,
        )
        self.assertEqual(
            value.observation.state,
            ItemPublishResultState.SYNTHETIC_VERIFIED,
        )
        self.assertEqual(value.observation.authority, ItemResultAuthority.SYNTHETIC)
        self.assertIsNone(value.observation.formal_item_code)
        self.assertIsNone(value.observation.target_version)
        self.assertFalse(value.reconciliation_required)

    def test_authoritative_sandbox_success_requires_exact_authenticated_binding(self) -> None:
        sandbox = profile(ItemTargetMode.SANDBOX)
        success = classify_item_adapter_response(
            profile=sandbox,
            command=command(),
            response=response(
                http_status=200,
                response_authenticated=True,
                formal_item_code="ITEM-SANDBOX-001",
                target_version="7",
            ),
            observed_at=NOW,
        )
        self.assertTrue(success.observation.is_authoritative_success)
        self.assertEqual(success.observation.formal_item_code, "ITEM-SANDBOX-001")

        mismatch = classify_item_adapter_response(
            profile=sandbox,
            command=command(),
            response=response(
                attempt_global_id=UUID(int=999),
                http_status=200,
                response_authenticated=True,
                formal_item_code="ITEM-SANDBOX-001",
                target_version="7",
            ),
            observed_at=NOW,
        )
        self.assertEqual(mismatch.observation.state, ItemPublishResultState.FAILED_FINAL)
        self.assertEqual(
            mismatch.observation.fault_kind,
            ItemFaultKind.RESPONSE_CONTRACT_INVALID,
        )
        self.assertIsNone(mismatch.observation.formal_item_code)
        self.assertTrue(mismatch.reconciliation_required)

    def test_closed_fault_matrix_retains_safe_classification_only(self) -> None:
        sandbox = profile(ItemTargetMode.SANDBOX)
        cases = (
            (
                {"http_status": 429, "response_authenticated": True},
                ItemPublishResultState.FAILED_RETRYABLE,
                ItemFaultKind.RATE_LIMITED,
            ),
            (
                {"http_status": 503, "response_authenticated": True},
                ItemPublishResultState.FAILED_RETRYABLE,
                ItemFaultKind.TARGET_SERVER_ERROR,
            ),
            (
                {
                    "http_status": 422,
                    "response_authenticated": True,
                    "business_validation_failed": True,
                },
                ItemPublishResultState.FAILED_FINAL,
                ItemFaultKind.BUSINESS_VALIDATION,
            ),
            (
                {"http_status": 200, "response_authenticated": False},
                ItemPublishResultState.FAILED_FINAL,
                ItemFaultKind.RESPONSE_AUTHENTICATION_INVALID,
            ),
        )
        for changes, state, fault in cases:
            with self.subTest(fault=fault):
                value = classify_item_adapter_response(
                    profile=sandbox,
                    command=command(),
                    response=response(**changes),
                    observed_at=NOW,
                )
                self.assertEqual(value.observation.state, state)
                self.assertEqual(value.observation.fault_kind, fault)
                self.assertIsNone(value.observation.formal_item_code)

    def test_timeout_after_boundary_is_uncertain_and_never_redispatch_truth(self) -> None:
        value = uncertain_item_adapter_result(
            command=command(),
            observed_at=NOW,
            safe_error_code="ITEM_PUBLISH_ADAPTER_TIMEOUT",
        )
        self.assertEqual(
            value.observation.state,
            ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT,
        )
        self.assertEqual(
            value.observation.fault_kind,
            ItemFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
        )
        self.assertTrue(value.reconciliation_required)
        self.assertNotIn("private", repr(value))

    def test_command_rejects_source_hash_drift(self) -> None:
        value = command()
        with self.assertRaisesRegex(ValueError, "source hash"):
            replace(value, source_hash="d" * 64)


if __name__ == "__main__":
    unittest.main()
