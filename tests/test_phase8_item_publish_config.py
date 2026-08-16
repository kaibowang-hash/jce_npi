from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.item_publish.config import ItemExecutionProfile
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_OPERATION,
    ItemPublishContractError,
    ItemTargetMode,
)


def base(mode: ItemTargetMode) -> ItemExecutionProfile:
    common = {
        "profile_id": f"item-{mode.value}-v1",
        "profile_version": 1,
        "tenant_id": "tenant-synthetic",
        "project_global_id": str(UUID(int=1)),
        "target_mode": mode,
        "requester_user_ids": ("engineer@example.invalid",),
        "service_actor_user_id": "item-worker@example.invalid",
    }
    if mode is ItemTargetMode.MOCK:
        return ItemExecutionProfile(environment_code="mock", **common)
    if mode is ItemTargetMode.SYNTHETIC:
        return ItemExecutionProfile(
            environment_code="disposable-test",
            allowed_operations=(ITEM_PUBLISH_OPERATION,),
            adapter_resolver="npi_integration.item_publish.runtime_fixture.synthetic_adapter",
            synthetic_test_only=True,
            disposable_runtime_marker=True,
            **common,
        )
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


class Phase8ItemPublishConfigurationTest(unittest.TestCase):
    def test_all_three_modes_are_explicit_and_snapshot_hash_is_stable(self) -> None:
        for mode in ItemTargetMode:
            with self.subTest(mode=mode):
                profile = base(mode)
                self.assertEqual(profile.reference.target_mode, mode)
                self.assertEqual(profile.snapshot_hash, replace(profile).snapshot_hash)
                self.assertTrue(profile.permits("ENGINEER@example.invalid"))
                self.assertFalse(profile.permits("other@example.invalid"))

    def test_mock_rejects_every_dispatch_or_network_field(self) -> None:
        candidate = base(ItemTargetMode.MOCK)
        mutations = (
            {"allowed_operations": (ITEM_PUBLISH_OPERATION,)},
            {"adapter_resolver": "npi_integration.item_publish.adapter.resolve"},
            {"base_url": "https://erpnext.sandbox.example.invalid"},
            {"secret_reference": "secrets/item-sandbox-v1"},
            {"non_production_attested": True},
            {"synthetic_test_only": True},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ItemPublishContractError, "Mock Item"):
                    replace(candidate, **mutation)

    def test_synthetic_requires_disposable_marker_and_has_no_network_or_secret(self) -> None:
        candidate = base(ItemTargetMode.SYNTHETIC)
        for mutation in (
            {"disposable_runtime_marker": False},
            {"synthetic_test_only": False},
            {"base_url": "https://erpnext.test.example.invalid"},
            {"secret_reference": "secrets/item-test-v1"},
            {"allowed_operations": ("generic_crud",)},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ItemPublishContractError, "Synthetic Item"):
                    replace(candidate, **mutation)

    def test_sandbox_requires_exact_nonproduction_origin_operation_secret_and_auth(self) -> None:
        candidate = base(ItemTargetMode.SANDBOX)
        mutations = (
            {"base_url": "http://erpnext.sandbox.example.invalid"},
            {"base_url": "https://user@erpnext.sandbox.example.invalid"},
            {"base_url": "https://erpnext.production.example.invalid"},
            {"allowed_hostnames": ("other.sandbox.example.invalid",)},
            {"allowed_operations": ("generic_crud",)},
            {"secret_reference": "raw-password"},
            {"response_authentication": "none"},
            {"environment_code": "production"},
            {"follow_redirects": True},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ItemPublishContractError):
                    replace(candidate, **mutation)

    def test_profile_rejects_builtin_or_ambiguous_actor_authority(self) -> None:
        candidate = base(ItemTargetMode.MOCK)
        for mutation in (
            {"service_actor_user_id": "Administrator"},
            {"requester_user_ids": ("Guest",)},
            {"requester_user_ids": ("same@example.invalid", "SAME@example.invalid")},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(ItemPublishContractError):
                    replace(candidate, **mutation)

    def test_profile_rejects_noncanonical_project_or_invalid_tenant_scope(self) -> None:
        candidate = base(ItemTargetMode.MOCK)
        with self.assertRaisesRegex(ItemPublishContractError, "canonical UUID"):
            replace(candidate, project_global_id=str(UUID(int=0xABC)).upper())
        with self.assertRaisesRegex(ItemPublishContractError, "tenant identity"):
            replace(candidate, tenant_id=" tenant-synthetic")
        with self.assertRaises(ItemPublishContractError):
            replace(candidate, environment_code=7)  # type: ignore[arg-type]
        with self.assertRaises(ItemPublishContractError):
            replace(candidate, requester_user_ids=(object(),))  # type: ignore[arg-type]
        self.assertFalse(candidate.permits(object()))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
