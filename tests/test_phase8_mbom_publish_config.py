from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.mbom_publish.config import MbomExecutionProfile  # noqa: E402
from npi_integration.mbom_publish.domain import (  # noqa: E402
    MBOM_PUBLISH_OPERATION,
    MbomPublishContractError,
    MbomTargetMode,
)


PROJECT = str(UUID(int=1))


def base(mode: MbomTargetMode) -> dict[str, object]:
    return {
        "profile_id": f"mbom-{mode.value}-v1",
        "profile_version": 1,
        "tenant_id": "tenant-synthetic",
        "project_global_id": PROJECT,
        "target_mode": mode,
        "environment_code": mode.value,
        "requester_user_ids": ("engineer@example.invalid",),
        "service_actor_user_id": "worker@example.invalid",
        "projection_policy_id": "mbom-projection-v1",
        "projection_policy_version": 1,
        "projection_policy_hash": "a" * 64,
    }


class Phase8MbomPublishConfigTest(unittest.TestCase):
    def test_mock_profile_is_separate_disabled_and_network_free(self) -> None:
        profile = MbomExecutionProfile(**base(MbomTargetMode.MOCK))
        self.assertEqual(profile.snapshot["allowedOperations"], [])
        self.assertIsNone(profile.snapshot["baseUrl"])
        self.assertTrue(profile.permits("ENGINEER@example.invalid"))
        for field, value in (
            ("allowed_operations", (MBOM_PUBLISH_OPERATION,)),
            ("adapter_resolver", "npi_integration.mbom.adapter"),
            ("base_url", "https://erpnext-sandbox.example.invalid"),
            ("secret_reference", "secret/mbom"),
        ):
            with self.subTest(field=field), self.assertRaises(MbomPublishContractError):
                MbomExecutionProfile(**{**base(MbomTargetMode.MOCK), field: value})

    def test_synthetic_profile_requires_disposable_network_free_markers(self) -> None:
        values = {
            **base(MbomTargetMode.SYNTHETIC),
            "environment_code": "disposable-test",
            "allowed_operations": (MBOM_PUBLISH_OPERATION,),
            "adapter_resolver": "npi_integration.mbom_publish.synthetic_adapter",
            "synthetic_test_only": True,
            "disposable_runtime_marker": True,
        }
        profile = MbomExecutionProfile(**values)
        self.assertEqual(profile.reference.target_mode, MbomTargetMode.SYNTHETIC)
        for field, value in (
            ("synthetic_test_only", False),
            ("disposable_runtime_marker", False),
            ("base_url", "https://sandbox.example.invalid"),
            ("secret_reference", "secret/mbom"),
            ("allowed_operations", ("publish_released_item",)),
        ):
            with self.subTest(field=field), self.assertRaises(MbomPublishContractError):
                MbomExecutionProfile(**{**values, field: value})

    def test_sandbox_profile_requires_exact_nonproduction_origin_secret_and_authentication(self) -> None:
        values = {
            **base(MbomTargetMode.SANDBOX),
            "environment_code": "sandbox",
            "allowed_operations": (MBOM_PUBLISH_OPERATION,),
            "adapter_resolver": "npi_integration.mbom_publish.sandbox_adapter",
            "base_url": "https://sandbox.erpnext.example.invalid",
            "allowed_hostnames": ("sandbox.erpnext.example.invalid",),
            "secret_reference": "secrets/mbom-sandbox",
            "response_authentication": "hmac-sha256-v1",
            "connect_timeout_seconds": 5,
            "read_timeout_seconds": 30,
            "non_production_attested": True,
        }
        profile = MbomExecutionProfile(**values)
        self.assertEqual(profile.reference.projection_policy_hash, "a" * 64)
        for field, value in (
            ("environment_code", "production"),
            ("base_url", "http://sandbox.erpnext.example.invalid"),
            ("base_url", "https://user:pass@sandbox.erpnext.example.invalid"),
            ("allowed_hostnames", ("sandbox.other.example.invalid",)),
            ("secret_reference", "raw-password"),
            ("response_authentication", "none"),
            ("follow_redirects", True),
            ("non_production_attested", False),
        ):
            with self.subTest(field=field), self.assertRaises(MbomPublishContractError):
                MbomExecutionProfile(**{**values, field: value})

    def test_production_labels_ip_literals_and_generic_operation_are_closed(self) -> None:
        values = {
            **base(MbomTargetMode.SANDBOX),
            "environment_code": "sandbox",
            "allowed_operations": (MBOM_PUBLISH_OPERATION,),
            "adapter_resolver": "npi_integration.mbom_publish.sandbox_adapter",
            "base_url": "https://sandbox.erpnext.example.invalid",
            "allowed_hostnames": ("sandbox.erpnext.example.invalid",),
            "secret_reference": "secrets/mbom-sandbox",
            "response_authentication": "hmac-sha256-v1",
            "connect_timeout_seconds": 5,
            "read_timeout_seconds": 30,
            "non_production_attested": True,
        }
        for override in (
            {"base_url": "https://127.0.0.1", "allowed_hostnames": ("127.0.0.1",)},
            {"base_url": "https://prod.erpnext.example.invalid", "allowed_hostnames": ("prod.erpnext.example.invalid",)},
            {"allowed_operations": ("frappe.client.insert",)},
        ):
            with self.assertRaises(MbomPublishContractError):
                MbomExecutionProfile(**{**values, **override})

    def test_profile_hash_changes_for_projection_policy_and_never_contains_credentials(self) -> None:
        profile = MbomExecutionProfile(**base(MbomTargetMode.MOCK))
        changed = replace(profile, projection_policy_hash="b" * 64)
        self.assertNotEqual(profile.snapshot_hash, changed.snapshot_hash)
        serialized = str(profile.snapshot).casefold()
        self.assertNotIn("password", serialized)
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("credential", serialized)


if __name__ == "__main__":
    unittest.main()
