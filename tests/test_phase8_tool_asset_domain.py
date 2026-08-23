from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.tool_asset_request.execution_domain import (  # noqa: E402
    CREATE_TOOL_ASSET,
    UPDATE_TOOL_ASSET,
    ToolAssetApprovalState,
    ToolAssetBusinessApprovalReference,
    ToolAssetExecutionContractError,
    ToolAssetExecutionProfileReference,
    ToolAssetExecutionOperation,
    ToolAssetExecutionRequest,
    ToolAssetExecutionRequestState,
    ToolAssetExecutionTargetMode,
    ToolAssetFaultKind,
    ToolAssetFieldResult,
    ToolAssetFieldResultState,
    ToolAssetMappingDisposition,
    ToolAssetMappingExpectation,
    ToolAssetResultAuthority,
    ToolAssetSourceSnapshot,
    aggregate_field_results,
    canonical_hash,
    classify_adapter_fault,
    classify_mapping_result,
    tool_asset_execution_request_from_mapping,
    tool_asset_source_from_mapping,
)


NOW = datetime(2026, 8, 24, 2, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def source(*, tooling_set: UUID = uid(3)) -> ToolAssetSourceSnapshot:
    return ToolAssetSourceSnapshot(
        tenant_id="tenant-synthetic",
        project_global_id=uid(1),
        tooling_master_global_id=uid(2),
        tooling_master_title="Synthetic Tooling Master",
        tooling_master_snapshot_hash="1" * 64,
        tooling_set_global_id=tooling_set,
        tooling_set_physical_serial="SET-SYNTHETIC-001",
        tooling_set_snapshot_hash="2" * 64,
        tooling_requirement_kind="new_tool",
        set_revision_binding_global_id=uid(4),
        set_revision_binding_snapshot_hash="3" * 64,
        tooling_revision_global_id=uid(5),
        tooling_revision_number=2,
        tooling_revision_label="R2",
        tooling_revision_snapshot_hash="4" * 64,
        acceptance_revision_global_id=uid(6),
        acceptance_global_id=uid(7),
        acceptance_version=1,
        acceptance_predecessor_global_id=None,
        acceptance_predecessor_snapshot_hash=None,
        acceptance_snapshot_hash="5" * 64,
        accepted_at=NOW,
    )


def profile(mode: ToolAssetExecutionTargetMode) -> ToolAssetExecutionProfileReference:
    return ToolAssetExecutionProfileReference(
        profile_id=f"tool-asset-{mode.value}-v1",
        profile_version=1,
        target_mode=mode,
        environment_code="disposable-test" if mode is ToolAssetExecutionTargetMode.SYNTHETIC else mode.value,
        projection_policy_id="tool-asset-projection-v1",
        projection_policy_version=1,
        projection_policy_hash="6" * 64,
        snapshot_hash="7" * 64,
    )


class Phase8ToolAssetDomainTest(unittest.TestCase):
    def test_physical_set_source_is_deterministic_and_cardinality_scoped(self) -> None:
        first = source()
        self.assertEqual(first.source_hash, source().source_hash)
        self.assertEqual(
            first.source_stream_key_hash,
            canonical_hash({"schemaVersion": 2, "tenantId": first.tenant_id, "projectGlobalId": str(first.project_global_id), "toolingSetGlobalId": str(first.tooling_set_global_id)}),
        )
        self.assertNotEqual(first.source_stream_key_hash, source(tooling_set=uid(30)).source_stream_key_hash)
        self.assertEqual(len(first.canonical_mapping()["ownedFieldsManifest"]), 5)
        self.assertEqual(tool_asset_source_from_mapping(first.canonical_mapping()), first)
        with self.assertRaisesRegex(ToolAssetExecutionContractError, "stream key"):
            replace(first, source_stream_key_hash="0" * 64)
        with self.assertRaisesRegex(ToolAssetExecutionContractError, "successor"):
            replace(first, acceptance_version=2, source_hash="")
        successor = replace(
            first,
            acceptance_version=2,
            acceptance_predecessor_global_id=uid(8),
            acceptance_predecessor_snapshot_hash="6" * 64,
            source_hash="",
        )
        self.assertNotEqual(successor.source_hash, first.source_hash)

    def test_create_is_exactly_unmapped_and_update_requires_current_mapping(self) -> None:
        value = source()
        create = ToolAssetMappingExpectation(ToolAssetExecutionOperation.CREATE, value.source_stream_key_hash, 0)
        self.assertIsNone(create.formal_asset_id)
        update = ToolAssetMappingExpectation(ToolAssetExecutionOperation.UPDATE, value.source_stream_key_hash, 2, "ASSET-SANDBOX-1", "2", "8" * 64)
        self.assertEqual(update.mapping_version, 2)
        for invalid in (
            lambda: ToolAssetMappingExpectation(ToolAssetExecutionOperation.CREATE, value.source_stream_key_hash, 1),
            lambda: ToolAssetMappingExpectation(ToolAssetExecutionOperation.UPDATE, value.source_stream_key_hash, 0),
            lambda: ToolAssetMappingExpectation(ToolAssetExecutionOperation.UPDATE, value.source_stream_key_hash, 1, "ASSET-1", None, "8" * 64),
        ):
            with self.assertRaises(ToolAssetExecutionContractError):
                invalid()

    def test_acceptance_evidence_does_not_infer_business_approval(self) -> None:
        unavailable = ToolAssetBusinessApprovalReference(ToolAssetApprovalState.UNAVAILABLE)
        self.assertEqual(unavailable.canonical_mapping()["state"], "unavailable")
        with self.assertRaisesRegex(ToolAssetExecutionContractError, "inferred"):
            ToolAssetBusinessApprovalReference(ToolAssetApprovalState.UNAVAILABLE, evidence_reference="ACCEPTANCE-1")
        verified = ToolAssetBusinessApprovalReference(ToolAssetApprovalState.VERIFIED, "approval-policy-v1", 1, "8" * 64, "approval-evidence-1", "9" * 64)
        self.assertNotEqual(verified.evidence_hash, source().acceptance_snapshot_hash)

    def test_mock_and_sandbox_request_safety_are_separate(self) -> None:
        value = source()
        create = ToolAssetMappingExpectation(ToolAssetExecutionOperation.CREATE, value.source_stream_key_hash, 0)
        mock = ToolAssetExecutionRequest(uid(20), value, ToolAssetBusinessApprovalReference(ToolAssetApprovalState.UNAVAILABLE), create, profile(ToolAssetExecutionTargetMode.MOCK), ToolAssetExecutionRequestState.VALIDATED_MOCK, "engineer@example.invalid", uid(21), "trace-tool-asset-001", "a" * 64, NOW)
        self.assertEqual(mock.operation.value, CREATE_TOOL_ASSET)
        self.assertEqual(mock.canonical_mapping()["approval"]["state"], "unavailable")
        self.assertEqual(tool_asset_execution_request_from_mapping(mock.canonical_mapping()), mock)
        corrupted = deepcopy(mock.canonical_mapping())
        corrupted["source"]["acceptancePredecessorGlobalId"] = str(uid(30))
        with self.assertRaises(ToolAssetExecutionContractError):
            tool_asset_execution_request_from_mapping(corrupted)
        with self.assertRaisesRegex(ToolAssetExecutionContractError, "verified business approval"):
            replace(mock, profile=profile(ToolAssetExecutionTargetMode.SANDBOX), state=ToolAssetExecutionRequestState.QUEUED)
        with self.assertRaisesRegex(ToolAssetExecutionContractError, "authoritative target truth"):
            replace(mock, profile=profile(ToolAssetExecutionTargetMode.SYNTHETIC), state=ToolAssetExecutionRequestState.SUCCEEDED)

    def test_mapping_only_advances_for_authenticated_complete_authoritative_truth(self) -> None:
        value = source()
        create = ToolAssetMappingExpectation(ToolAssetExecutionOperation.CREATE, value.source_stream_key_hash, 0)
        self.assertEqual(classify_mapping_result(create, result_state=ToolAssetExecutionRequestState.SUCCEEDED, authority=ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX, response_authenticated=True, observed_formal_asset_id="ASSET-1", observed_previous_mapping_version=0), ToolAssetMappingDisposition.ADVANCE)
        for state, authority, authenticated, version, expected in (
            (ToolAssetExecutionRequestState.PARTIALLY_SUCCEEDED, ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX, True, 0, ToolAssetMappingDisposition.RESULT_NOT_COMPLETE),
            (ToolAssetExecutionRequestState.SUCCEEDED, ToolAssetResultAuthority.SYNTHETIC, False, 0, ToolAssetMappingDisposition.NON_AUTHORITATIVE),
            (ToolAssetExecutionRequestState.SUCCEEDED, ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX, True, 1, ToolAssetMappingDisposition.EXPECTATION_CONFLICT),
        ):
            self.assertEqual(classify_mapping_result(create, result_state=state, authority=authority, response_authenticated=authenticated, observed_formal_asset_id="ASSET-1", observed_previous_mapping_version=version), expected)

    def test_field_aggregation_preserves_partial_and_uncertain_truth(self) -> None:
        success = ToolAssetFieldResult("asset_identity", ToolAssetFieldResultState.SUCCEEDED_AUTHORITATIVE, ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX, True, "b" * 64, ToolAssetFaultKind.NONE)
        failure = ToolAssetFieldResult("maintenance_profile", ToolAssetFieldResultState.FAILED_FINAL, ToolAssetResultAuthority.NONE, False, "c" * 64, ToolAssetFaultKind.BUSINESS_VALIDATION)
        uncertain = ToolAssetFieldResult("location", ToolAssetFieldResultState.UNCERTAIN_AFTER_TIMEOUT, ToolAssetResultAuthority.NONE, False, "d" * 64, ToolAssetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT)
        self.assertEqual(aggregate_field_results((success,)), ToolAssetExecutionRequestState.SUCCEEDED)
        self.assertEqual(aggregate_field_results((success, failure)), ToolAssetExecutionRequestState.PARTIALLY_SUCCEEDED)
        self.assertEqual(aggregate_field_results((success, uncertain)), ToolAssetExecutionRequestState.UNCERTAIN_AFTER_TIMEOUT)
        with self.assertRaisesRegex(ToolAssetExecutionContractError, "unique"):
            aggregate_field_results((success, success))
        synthetic = ToolAssetFieldResult("asset_identity", ToolAssetFieldResultState.SYNTHETIC_VERIFIED, ToolAssetResultAuthority.SYNTHETIC, False, "e" * 64, ToolAssetFaultKind.NONE)
        self.assertEqual(aggregate_field_results((synthetic,)), ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED)
        with self.assertRaisesRegex(ToolAssetExecutionContractError, "synthetic"):
            replace(synthetic, authority=ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX, response_authenticated=True)

    def test_fault_classification_keeps_post_boundary_timeout_uncertain(self) -> None:
        self.assertEqual(classify_adapter_fault(adapter_boundary_crossed=True, timeout=True), ToolAssetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT)
        self.assertEqual(classify_adapter_fault(adapter_boundary_crossed=False, timeout=True), ToolAssetFaultKind.TARGET_UNAVAILABLE)
        self.assertEqual(classify_adapter_fault(adapter_boundary_crossed=True, status_code=429), ToolAssetFaultKind.RATE_LIMITED)
        self.assertEqual(classify_adapter_fault(adapter_boundary_crossed=True, response_authenticated=False), ToolAssetFaultKind.RESPONSE_AUTHENTICATION_INVALID)


if __name__ == "__main__":
    unittest.main()
