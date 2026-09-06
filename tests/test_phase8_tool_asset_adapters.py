from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.tool_asset_request.adapters import (  # noqa: E402
    ToolAssetAdapterCommand, ToolAssetAdapterFieldResponse,
    ToolAssetAdapterRegistration, ToolAssetAdapterRegistry, ToolAssetAdapterResponse,
    classify_tool_asset_adapter_response, uncertain_tool_asset_adapter_result,
)
from npi_integration.tool_asset_request.config import ToolAssetExecutionProfile  # noqa: E402
from npi_integration.tool_asset_request.execution_domain import (  # noqa: E402
    TOOL_ASSET_OWNED_FIELDS, ToolAssetExecutionOperation, ToolAssetExecutionRequestState,
    ToolAssetExecutionTargetMode, ToolAssetMappingExpectation, ToolAssetResultAuthority,
    canonical_hash,
)
from tests.test_phase8_tool_asset_domain import source  # noqa: E402

NOW = datetime(2026, 8, 24, 8, tzinfo=UTC)


def execution_profile(mode):
    values = dict(profile_id=f"tool-asset-{mode.value}-v1", profile_version=1, tenant_id="tenant-synthetic", project_global_id=str(UUID(int=1)), target_mode=mode, environment_code="testing" if mode is ToolAssetExecutionTargetMode.SYNTHETIC else "sandbox", requester_user_ids=("engineer@example.invalid",), service_actor_user_id="worker@example.invalid", projection_policy_id="projection-v1", projection_policy_version=1, projection_policy_hash="7"*64, allowed_operations=("create_tool_asset", "update_tool_asset"), adapter_resolver=f"npi.tool_asset.{mode.value}")
    if mode is ToolAssetExecutionTargetMode.SYNTHETIC:
        values.update(synthetic_test_only=True, disposable_runtime_marker=True)
    else:
        values.update(base_url="https://erpnext.sandbox.example.invalid", allowed_hostnames=("erpnext.sandbox.example.invalid",), secret_reference="secrets/tool-asset", response_authentication="hmac-sha256-v1", connect_timeout_seconds=5, read_timeout_seconds=30, non_production_attested=True)
    return ToolAssetExecutionProfile(**values)


def command(operation=ToolAssetExecutionOperation.CREATE):
    expectation = ToolAssetMappingExpectation(operation, source().source_stream_key_hash, 0) if operation is ToolAssetExecutionOperation.CREATE else ToolAssetMappingExpectation(operation, source().source_stream_key_hash, 1, "ASSET-1", "1", "8"*64)
    return ToolAssetAdapterCommand(UUID(int=20), UUID(int=21), 1, operation, "9"*64, source().source_hash, expectation, {"request":"frozen"})


def response(cmd, *, mode=ToolAssetExecutionTargetMode.SYNTHETIC, partial=False):
    fields = []
    for index, code in enumerate(TOOL_ASSET_OWNED_FIELDS):
        fields.append(ToolAssetAdapterFieldResponse(code, canonical_hash({"code":code}), http_status=(500 if partial and index == 0 else (200 if mode is ToolAssetExecutionTargetMode.SANDBOX else None)), response_authenticated=(mode is ToolAssetExecutionTargetMode.SANDBOX), response_contract_valid=True))
    return ToolAssetAdapterResponse(cmd.request_global_id, cmd.attempt_global_id, cmd.attempt_number, cmd.operation, cmd.target_idempotency_key_hash, cmd.source_hash, "a"*64, tuple(fields), "ASSET-1" if mode is ToolAssetExecutionTargetMode.SANDBOX else None, "2" if mode is ToolAssetExecutionTargetMode.SANDBOX else None)


class Phase8ToolAssetAdaptersTest(unittest.TestCase):
    def test_registry_is_operation_specific_and_default_closed(self):
        profile = execution_profile(ToolAssetExecutionTargetMode.SYNTHETIC)
        self.assertIsNone(ToolAssetAdapterRegistry().resolve(profile, ToolAssetExecutionOperation.CREATE))
        adapter = lambda value: response(value)
        registry = ToolAssetAdapterRegistry((ToolAssetAdapterRegistration(profile.adapter_resolver, profile.target_mode, ToolAssetExecutionOperation.CREATE, adapter),))
        self.assertIs(registry.resolve(profile, ToolAssetExecutionOperation.CREATE), adapter)
        self.assertIsNone(registry.resolve(profile, ToolAssetExecutionOperation.UPDATE))

    def test_synthetic_is_complete_network_free_truth_without_formal_identity(self):
        cmd = command()
        result = classify_tool_asset_adapter_response(profile=execution_profile(ToolAssetExecutionTargetMode.SYNTHETIC), command=cmd, response=response(cmd), observed_at=NOW)
        self.assertEqual(result.state, ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED)
        self.assertEqual(result.authority, ToolAssetResultAuthority.SYNTHETIC)
        self.assertIsNone(result.formal_asset_id)

    def test_sandbox_partial_and_binding_mismatch_never_advance(self):
        cmd = command()
        profile = execution_profile(ToolAssetExecutionTargetMode.SANDBOX)
        partial = classify_tool_asset_adapter_response(profile=profile, command=cmd, response=response(cmd, mode=profile.target_mode, partial=True), observed_at=NOW)
        self.assertEqual(partial.state, ToolAssetExecutionRequestState.PARTIALLY_SUCCEEDED)
        mismatch = classify_tool_asset_adapter_response(profile=profile, command=cmd, response=replace(response(cmd, mode=profile.target_mode), source_hash="b"*64), observed_at=NOW)
        self.assertEqual(mismatch.state, ToolAssetExecutionRequestState.UNCERTAIN_AFTER_TIMEOUT)
        self.assertIsNone(mismatch.formal_asset_id)

    def test_post_boundary_unknown_is_uncertain_for_every_field(self):
        result = uncertain_tool_asset_adapter_result(command=command(), safe_error_code="TOOL_ASSET_UNKNOWN")
        self.assertEqual(result.state, ToolAssetExecutionRequestState.UNCERTAIN_AFTER_TIMEOUT)
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(len(result.fields), len(TOOL_ASSET_OWNED_FIELDS))


if __name__ == "__main__":
    unittest.main()
