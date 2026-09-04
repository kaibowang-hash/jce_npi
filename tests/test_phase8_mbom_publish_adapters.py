from __future__ import annotations

import unittest
import sys
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.mbom_publish.adapters import (
    MbomAdapterCommand,
    MbomAdapterNodeCommand,
    MbomAdapterNodeResponse,
    MbomAdapterRegistration,
    MbomAdapterRegistry,
    MbomAdapterResponse,
    classify_mbom_adapter_response,
    failed_before_mbom_adapter_boundary_result,
    uncertain_mbom_adapter_result,
)
from npi_integration.mbom_publish.config import MbomExecutionProfile
from npi_integration.mbom_publish.domain import (
    MBOM_PUBLISH_OPERATION,
    MbomNodeResultState,
    MbomPublishContractError,
    MbomPublishIntent,
    MbomPublishRequestState,
    MbomTargetMode,
    MbomTargetSubmissionState,
    canonical_hash,
)


NOW = datetime(2026, 8, 21, 16, 0, tzinfo=UTC)


def profile(mode: MbomTargetMode) -> MbomExecutionProfile:
    common = dict(
        profile_id=f"mbom-{mode.value}-v1",
        profile_version=1,
        tenant_id="tenant-a",
        project_global_id=str(UUID(int=1)),
        target_mode=mode,
        environment_code="disposable-test" if mode is MbomTargetMode.SYNTHETIC else "sandbox",
        requester_user_ids=("publisher@example.invalid",),
        service_actor_user_id="worker@example.invalid",
        projection_policy_id="projection-v1",
        projection_policy_version=1,
        projection_policy_hash="7" * 64,
        allowed_operations=(MBOM_PUBLISH_OPERATION,),
        adapter_resolver=f"npi.adapters.{mode.value}",
        non_production_attested=(mode is MbomTargetMode.SANDBOX),
    )
    if mode is MbomTargetMode.SYNTHETIC:
        common.update(synthetic_test_only=True, disposable_runtime_marker=True)
    else:
        common.update(
            base_url="https://erpnext.sandbox.example.invalid",
            allowed_hostnames=("erpnext.sandbox.example.invalid",),
            secret_reference="secrets/mbom-sandbox-v1",
            response_authentication="hmac-sha256-v1",
            connect_timeout_seconds=10,
            read_timeout_seconds=30,
        )
    return MbomExecutionProfile(**common)


def command() -> MbomAdapterCommand:
    request_id = UUID(int=10)
    snapshots = (
        {"line": {"stableLineKey": "ROOT"}, "itemReadiness": {}, "mbomExpectation": {}},
        {"line": {"stableLineKey": "SUB"}, "itemReadiness": {}, "mbomExpectation": {}},
    )
    nodes = tuple(
        MbomAdapterNodeCommand(
            node_global_id=UUID(int=20 + index),
            stable_line_key=key,
            assembly_source_key=str(index + 1) * 64,
            intent=MbomPublishIntent.CREATE_DRAFT,
            expected_mapping_version=0,
            expected_formal_bom_id=None,
            expected_target_version=None,
            node_snapshot=snapshots[index],
            node_snapshot_hash=canonical_hash(snapshots[index]),
        )
        for index, key in enumerate(("ROOT", "SUB"))
    )
    manifest_hash = canonical_hash(
        {
            "requestGlobalId": str(request_id),
            "nodes": [
                {
                    "globalId": str(node.node_global_id),
                    "stableLineKey": node.stable_line_key,
                    "nodeSnapshotHash": node.node_snapshot_hash,
                }
                for node in nodes
            ],
        }
    )
    request = {
        "globalId": str(request_id),
        "sourceHash": "3" * 64,
        "topologyHash": "4" * 64,
        "itemMappingSetHash": "5" * 64,
        "mbomMappingSetHash": "6" * 64,
        "targetIdempotencyKeyHash": "7" * 64,
    }
    return MbomAdapterCommand(
        request_id,
        UUID(int=11),
        1,
        "7" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        "6" * 64,
        manifest_hash,
        request,
        nodes,
    )


def response(
    value: MbomAdapterCommand,
    *,
    nodes: tuple[MbomAdapterNodeResponse, ...] | None = None,
    **changes: object,
) -> MbomAdapterResponse:
    values = dict(
        request_global_id=value.request_global_id,
        attempt_global_id=value.attempt_global_id,
        attempt_number=value.attempt_number,
        target_idempotency_key_hash=value.target_idempotency_key_hash,
        source_hash=value.source_hash,
        topology_hash=value.topology_hash,
        node_manifest_hash=value.node_manifest_hash,
        response_hash="8" * 64,
        nodes=nodes
        or tuple(
            MbomAdapterNodeResponse(node.stable_line_key, node.assembly_source_key, "9" * 64)
            for node in value.nodes
        ),
    )
    values.update(changes)
    return MbomAdapterResponse(**values)


class Phase8MbomPublishAdaptersTest(unittest.TestCase):
    def test_closed_registry_resolves_only_exact_non_mock_operation(self) -> None:
        synthetic = profile(MbomTargetMode.SYNTHETIC)
        adapter = lambda _command: None
        registry = MbomAdapterRegistry(
            (
                MbomAdapterRegistration(
                    synthetic.adapter_resolver,
                    MbomTargetMode.SYNTHETIC,
                    MBOM_PUBLISH_OPERATION,
                    adapter,
                ),
            )
        )
        self.assertIs(registry.resolve(synthetic), adapter)
        self.assertIsNone(MbomAdapterRegistry().resolve(synthetic))
        with self.assertRaises(MbomPublishContractError):
            MbomAdapterRegistry(
                (
                    MbomAdapterRegistration(
                        synthetic.adapter_resolver,
                        MbomTargetMode.SYNTHETIC,
                        MBOM_PUBLISH_OPERATION,
                        adapter,
                    ),
                )
                * 2
            )

    def test_command_rejects_manifest_or_request_binding_drift(self) -> None:
        value = command()
        with self.assertRaisesRegex(MbomPublishContractError, "manifest hash"):
            replace(value, node_manifest_hash="0" * 64)
        with self.assertRaisesRegex(MbomPublishContractError, "request binding"):
            replace(value, source_hash="a" * 64)

    def test_synthetic_batch_has_no_formal_ids_and_exact_node_coverage(self) -> None:
        value = command()
        result = classify_mbom_adapter_response(
            profile=profile(MbomTargetMode.SYNTHETIC),
            command=value,
            response=response(value),
            observed_at=NOW,
        )
        self.assertEqual(result.state, MbomPublishRequestState.SYNTHETIC_VERIFIED)
        self.assertTrue(
            all(node.state is MbomNodeResultState.SYNTHETIC_VERIFIED for node in result.observations)
        )
        self.assertTrue(all(node.formal_bom_id is None for node in result.observations))

    def test_partial_success_is_not_aggregate_success(self) -> None:
        value = command()
        nodes = (
            MbomAdapterNodeResponse(
                "ROOT",
                value.nodes[0].assembly_source_key,
                "a" * 64,
                http_status=201,
                response_authenticated=True,
                formal_bom_id="BOM-SBX-1",
                target_version="1",
                target_submission_state=MbomTargetSubmissionState.EDITABLE_DRAFT,
            ),
            MbomAdapterNodeResponse(
                "SUB",
                value.nodes[1].assembly_source_key,
                "b" * 64,
                http_status=429,
                response_authenticated=True,
            ),
        )
        result = classify_mbom_adapter_response(
            profile=profile(MbomTargetMode.SANDBOX),
            command=value,
            response=response(value, nodes=nodes),
            observed_at=NOW,
        )
        self.assertEqual(result.state, MbomPublishRequestState.PARTIALLY_SUCCEEDED)
        self.assertEqual(
            tuple(node.state for node in result.observations),
            (
                MbomNodeResultState.SUCCEEDED_AUTHORITATIVE,
                MbomNodeResultState.FAILED_RETRYABLE,
            ),
        )

    def test_missing_mismatch_timeout_business_and_submitted_fail_closed(self) -> None:
        value = command()
        cases = (
            (
                response(value, nodes=(response(value).nodes[0],)),
                MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
            ),
            (
                response(value, source_hash="a" * 64),
                MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
            ),
            (
                response(
                    value,
                    nodes=tuple(
                        replace(node, timed_out=True) for node in response(value).nodes
                    ),
                ),
                MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
            ),
            (
                response(
                    value,
                    nodes=tuple(
                        replace(
                            node,
                            http_status=422,
                            response_authenticated=True,
                            business_validation_failed=True,
                        )
                        for node in response(value).nodes
                    ),
                ),
                MbomPublishRequestState.FAILED_FINAL,
            ),
            (
                response(
                    value,
                    nodes=tuple(
                        replace(
                            node,
                            http_status=200,
                            response_authenticated=True,
                            formal_bom_id=f"BOM-{index}",
                            target_version="2",
                            target_submission_state=MbomTargetSubmissionState.SUBMITTED_IMMUTABLE,
                        )
                        for index, node in enumerate(response(value).nodes)
                    ),
                ),
                MbomPublishRequestState.MAPPING_CONFLICT,
            ),
        )
        for response_value, expected in cases:
            with self.subTest(expected=expected):
                result = classify_mbom_adapter_response(
                    profile=profile(MbomTargetMode.SANDBOX),
                    command=value,
                    response=response_value,
                    observed_at=NOW,
                )
                self.assertEqual(result.state, expected)

    def test_uncertain_and_preboundary_helpers_never_claim_target_truth(self) -> None:
        value = command()
        uncertain = uncertain_mbom_adapter_result(
            command=value, safe_error_code="MBOM_PUBLISH_TIMEOUT"
        )
        failed = failed_before_mbom_adapter_boundary_result(
            command=value, safe_error_code="MBOM_PUBLISH_ADAPTER_UNAVAILABLE"
        )
        self.assertTrue(uncertain.reconciliation_required)
        self.assertFalse(failed.reconciliation_required)
        for result in (uncertain, failed):
            self.assertTrue(all(node.formal_bom_id is None for node in result.observations))


if __name__ == "__main__":
    unittest.main()
