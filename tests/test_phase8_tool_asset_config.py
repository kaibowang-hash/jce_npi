from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.tool_asset_request.config import ToolAssetExecutionProfile, default_tool_asset_execution_profiles  # noqa: E402
from npi_integration.tool_asset_request.execution_domain import CREATE_TOOL_ASSET, TOOL_ASSET_EXECUTION_OPERATIONS, ToolAssetExecutionContractError, ToolAssetExecutionTargetMode  # noqa: E402


def base(mode: ToolAssetExecutionTargetMode) -> dict[str, object]:
    return {"profile_id": f"tool-asset-{mode.value}-v1", "profile_version": 1, "tenant_id": "tenant-synthetic", "project_global_id": str(UUID(int=1)), "target_mode": mode, "environment_code": mode.value, "requester_user_ids": ("engineer@example.invalid",), "service_actor_user_id": "worker@example.invalid", "projection_policy_id": "tool-asset-projection-v1", "projection_policy_version": 1, "projection_policy_hash": "a" * 64}


class Phase8ToolAssetConfigTest(unittest.TestCase):
    def test_no_default_profile_or_target_is_installed(self) -> None:
        self.assertEqual(default_tool_asset_execution_profiles(), ())

    def test_mock_profile_is_disabled_network_free_and_operation_closed(self) -> None:
        profile = ToolAssetExecutionProfile(**base(ToolAssetExecutionTargetMode.MOCK))
        self.assertEqual(profile.snapshot["allowedOperations"], [])
        self.assertFalse(profile.permits("engineer@example.invalid", CREATE_TOOL_ASSET))
        for field, value in (("allowed_operations", (CREATE_TOOL_ASSET,)), ("base_url", "https://sandbox.example.invalid"), ("secret_reference", "secrets/tool-asset")):
            with self.assertRaises(ToolAssetExecutionContractError):
                ToolAssetExecutionProfile(**{**base(ToolAssetExecutionTargetMode.MOCK), field: value})

    def test_synthetic_profile_is_disposable_and_network_free(self) -> None:
        values = {**base(ToolAssetExecutionTargetMode.SYNTHETIC), "environment_code": "disposable-test", "allowed_operations": TOOL_ASSET_EXECUTION_OPERATIONS, "adapter_resolver": "npi_integration.tool_asset_request.synthetic_adapter", "synthetic_test_only": True, "disposable_runtime_marker": True}
        profile = ToolAssetExecutionProfile(**values)
        self.assertTrue(profile.permits("ENGINEER@example.invalid", CREATE_TOOL_ASSET))
        self.assertFalse(profile.permits(None, CREATE_TOOL_ASSET))  # type: ignore[arg-type]
        self.assertTrue(replace(profile, allowed_operations=(CREATE_TOOL_ASSET,)).permits("engineer@example.invalid", CREATE_TOOL_ASSET))
        for field, value in (("base_url", "https://sandbox.example.invalid"), ("secret_reference", "secrets/tool-asset"), ("allowed_operations", (CREATE_TOOL_ASSET, CREATE_TOOL_ASSET)), ("allowed_operations", ("create_or_update_tool_asset",))):
            with self.assertRaises(ToolAssetExecutionContractError):
                ToolAssetExecutionProfile(**{**values, field: value})

    def test_sandbox_requires_nonproduction_exact_allowlist_secret_and_auth(self) -> None:
        values = {**base(ToolAssetExecutionTargetMode.SANDBOX), "environment_code": "sandbox", "allowed_operations": TOOL_ASSET_EXECUTION_OPERATIONS, "adapter_resolver": "npi_integration.tool_asset_request.sandbox_adapter", "base_url": "https://sandbox.erpnext.example.invalid", "allowed_hostnames": ("sandbox.erpnext.example.invalid",), "secret_reference": "secrets/tool-asset-sandbox", "response_authentication": "hmac-sha256-v1", "connect_timeout_seconds": 5, "read_timeout_seconds": 30, "non_production_attested": True}
        profile = ToolAssetExecutionProfile(**values)
        self.assertEqual(profile.reference.target_mode, ToolAssetExecutionTargetMode.SANDBOX)
        create_only = ToolAssetExecutionProfile(**{**values, "allowed_operations": (CREATE_TOOL_ASSET,)})
        self.assertTrue(create_only.permits("engineer@example.invalid", CREATE_TOOL_ASSET))
        self.assertFalse(create_only.permits("engineer@example.invalid", "update_tool_asset"))
        for override in ({"environment_code": "production"}, {"base_url": "http://sandbox.erpnext.example.invalid"}, {"allowed_hostnames": ("prod.erpnext.example.invalid",)}, {"secret_reference": "raw-secret"}, {"follow_redirects": True}, {"allowed_operations": ("frappe.client.insert",)}):
            with self.assertRaises(ToolAssetExecutionContractError):
                ToolAssetExecutionProfile(**{**values, **override})

    def test_profile_snapshot_never_contains_secret_reference(self) -> None:
        profile = ToolAssetExecutionProfile(**base(ToolAssetExecutionTargetMode.MOCK))
        self.assertNotIn("secret", str(profile.snapshot).casefold())
        self.assertNotEqual(profile.snapshot_hash, replace(profile, projection_policy_hash="b" * 64).snapshot_hash)


if __name__ == "__main__":
    unittest.main()
