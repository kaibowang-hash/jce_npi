from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_API_VERSION,
    ITEM_PUBLISH_OPERATION,
    CurrentItemMapping,
    ItemAdapterObservation,
    ItemExecutionProfileReference,
    ItemFaultKind,
    ItemMappingDisposition,
    ItemMappingExpectation,
    ItemOccurrence,
    ItemPublishContractError,
    ItemPublishRequestState,
    ItemPublishResultState,
    ItemResultAuthority,
    ItemRetryDirective,
    ItemTargetMode,
    ReleasedItemSourceEvidence,
    canonical_hash,
    classify_adapter_fault,
    classify_mapping_observation,
    create_item_publish_request,
    group_item_source,
    issue_item_claim,
)


NOW = datetime(2026, 8, 16, 13, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def occurrence(
    value: int,
    *,
    engineering_item_id: str = "ENG-ITEM-001",
    description: str = "Synthetic engineering item",
    uom: str = "Nos",
    attributes: tuple[tuple[str, str], ...] = (("material", "PA66"),),
) -> ItemOccurrence:
    return ItemOccurrence(
        publish_node_global_id=uid(value),
        line_global_id=uid(100 + value),
        engineering_item_id=engineering_item_id,
        description=description,
        engineering_uom=uom,
        attributes=attributes,
        line_hash=f"{value:064x}",
        node_input_hash=f"{value + 1000:064x}",
    )


def evidence() -> ReleasedItemSourceEvidence:
    return ReleasedItemSourceEvidence(
        publish_request_global_id=uid(20),
        publish_request_payload_hash="a" * 64,
        publish_policy_global_id=uid(21),
        publish_policy_version=2,
        publish_policy_snapshot_hash="b" * 64,
        ebom_global_id=uid(22),
        ebom_version=3,
        revision_global_id=uid(23),
        revision_number=3,
        revision_snapshot_hash="c" * 64,
        lifecycle_version=4,
        release_event_global_id=uid(24),
        release_event_hash="d" * 64,
        approval_evidence_ids=(uid(24), uid(25)),
        released_at=NOW,
    )


def profile(mode: ItemTargetMode) -> ItemExecutionProfileReference:
    return ItemExecutionProfileReference(
        profile_id=f"item-{mode.value}-v1",
        profile_version=1,
        target_mode=mode,
        environment_code=("disposable-test" if mode is ItemTargetMode.SYNTHETIC else mode.value),
        snapshot_hash="e" * 64,
    )


class Phase8ItemPublishDomainTest(unittest.TestCase):
    def test_grouping_uses_project_scoped_engineering_identity_and_all_occurrences(self) -> None:
        source = group_item_source(
            tenant_id="tenant-synthetic",
            project_global_id=uid(1),
            selected_publish_node_global_id=uid(2),
            occurrences=(
                occurrence(2),
                occurrence(3),
                occurrence(4, engineering_item_id="ENG-ITEM-002"),
            ),
        )
        self.assertEqual(source.engineering_item_id, "ENG-ITEM-001")
        self.assertEqual(len(source.occurrences), 2)
        self.assertEqual(
            source.stream_key_hash,
            canonical_hash(
                {
                    "schemaVersion": 1,
                    "tenantId": "tenant-synthetic",
                    "projectGlobalId": str(uid(1)),
                    "engineeringItemId": "ENG-ITEM-001",
                }
            ),
        )
        self.assertNotIn("quantity", str(source.canonical_mapping()).casefold())
        self.assertNotIn("parent", str(source.canonical_mapping()).casefold())
        self.assertEqual(source.source_hash, replace(source).source_hash)

    def test_grouping_rejects_missing_ambiguous_and_divergent_occurrences(self) -> None:
        with self.assertRaisesRegex(ItemPublishContractError, "unavailable or ambiguous"):
            group_item_source(
                tenant_id="tenant-synthetic",
                project_global_id=uid(1),
                selected_publish_node_global_id=uid(9),
                occurrences=(occurrence(2),),
            )
        duplicate = replace(occurrence(2), line_global_id=uid(199))
        with self.assertRaisesRegex(ItemPublishContractError, "unavailable or ambiguous"):
            group_item_source(
                tenant_id="tenant-synthetic",
                project_global_id=uid(1),
                selected_publish_node_global_id=uid(2),
                occurrences=(occurrence(2), duplicate),
            )
        with self.assertRaisesRegex(ItemPublishContractError, "conflicting Item-master"):
            group_item_source(
                tenant_id="tenant-synthetic",
                project_global_id=uid(1),
                selected_publish_node_global_id=uid(2),
                occurrences=(occurrence(2), occurrence(3, description="Different")),
            )
        with self.assertRaisesRegex(ItemPublishContractError, "occurrences are invalid"):
            group_item_source(
                tenant_id="tenant-synthetic",
                project_global_id=uid(1),
                selected_publish_node_global_id=uid(2),
                occurrences=(object(),),  # type: ignore[arg-type]
            )

    def test_malformed_attribute_pairs_raise_closed_contract_errors(self) -> None:
        with self.assertRaisesRegex(ItemPublishContractError, "key/value pairs"):
            replace(occurrence(2), attributes=(("finish",),))  # type: ignore[arg-type]

    def test_mapping_expectation_derives_create_or_update_without_caller_target_choice(self) -> None:
        create = ItemMappingExpectation(0)
        self.assertEqual(create.intent.value, "create_item")
        update = ItemMappingExpectation(2, "ITEM-0001", "7", "f" * 64)
        self.assertEqual(update.intent.value, "update_item_engineering_fields")
        for invalid in (
            ItemMappingExpectation,
        ):
            self.assertTrue(callable(invalid))
        with self.assertRaises(ItemPublishContractError):
            ItemMappingExpectation(0, "ITEM-0001", None, None)
        with self.assertRaises(ItemPublishContractError):
            ItemMappingExpectation(1, "ITEM-0001", None, "f" * 64)

    def test_request_freezes_exact_source_profile_mapping_and_mock_never_emits_event(self) -> None:
        source = group_item_source(
            tenant_id="tenant-synthetic",
            project_global_id=uid(1),
            selected_publish_node_global_id=uid(2),
            occurrences=(occurrence(2), occurrence(3)),
        )
        request = create_item_publish_request(
            source=source,
            released_evidence=evidence(),
            profile=profile(ItemTargetMode.MOCK),
            mapping_expectation=ItemMappingExpectation(0),
            actor_user_id="engineer@example.invalid",
            request_id=uid(30),
            trace_id="trace-item-0001",
            idempotency_key_hash="1" * 64,
            global_id=uid(31),
            created_at=NOW,
        )
        self.assertEqual(request.state, ItemPublishRequestState.VALIDATED_MOCK)
        self.assertFalse(request.dispatch_allowed)
        self.assertEqual(request.payload()["apiVersion"], ITEM_PUBLISH_API_VERSION)
        self.assertEqual(request.payload()["operation"], ITEM_PUBLISH_OPERATION)
        with self.assertRaisesRegex(ItemPublishContractError, "Mock requests"):
            request.event_payload()
        synthetic = replace(
            request,
            profile=profile(ItemTargetMode.SYNTHETIC),
            state=ItemPublishRequestState.QUEUED,
            payload_hash="",
        )
        event_payload = synthetic.event_payload()
        self.assertEqual(event_payload["target_mode"], "synthetic")
        self.assertNotIn("formal_item_code", event_payload)
        self.assertNotIn("endpoint", event_payload)

    def test_only_authenticated_authoritative_sandbox_success_can_advance_mapping(self) -> None:
        expectation = ItemMappingExpectation(0)
        synthetic = ItemAdapterObservation(
            request_global_id=uid(31),
            attempt_global_id=uid(32),
            attempt_number=1,
            idempotency_key_hash="1" * 64,
            source_hash="2" * 64,
            expected_target_version=None,
            state=ItemPublishResultState.SYNTHETIC_VERIFIED,
            authority=ItemResultAuthority.SYNTHETIC,
            response_authenticated=False,
            response_hash="3" * 64,
            observed_at=NOW,
        )
        self.assertEqual(
            classify_mapping_observation(expectation=expectation, current=None, observation=synthetic),
            ItemMappingDisposition.NON_AUTHORITATIVE,
        )
        authoritative = replace(
            synthetic,
            state=ItemPublishResultState.SUCCEEDED,
            authority=ItemResultAuthority.AUTHORITATIVE_SANDBOX,
            response_authenticated=True,
            formal_item_code="ITEM-SANDBOX-0001",
            target_version="1",
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=expectation,
                current=None,
                observation=authoritative,
            ),
            ItemMappingDisposition.ADVANCE,
        )
        with self.assertRaisesRegex(ItemPublishContractError, "cannot contain formal"):
            replace(
                synthetic,
                formal_item_code="ITEM-FAKE",
                target_version="1",
            )
        with self.assertRaisesRegex(ItemPublishContractError, "authenticated authoritative"):
            replace(
                synthetic,
                state=ItemPublishResultState.SUCCEEDED,
                authority=ItemResultAuthority.NONE,
            )
        with self.assertRaisesRegex(ItemPublishContractError, "exact fault"):
            replace(
                synthetic,
                state=ItemPublishResultState.FAILED_FINAL,
                authority=ItemResultAuthority.NONE,
            )

    def test_mapping_compare_and_set_rejects_stale_head_and_item_code_change(self) -> None:
        current = CurrentItemMapping(2, "ITEM-0001", "7", "a" * 64)
        observation = ItemAdapterObservation(
            request_global_id=uid(31),
            attempt_global_id=uid(32),
            attempt_number=1,
            idempotency_key_hash="1" * 64,
            source_hash="2" * 64,
            expected_target_version="7",
            state=ItemPublishResultState.SUCCEEDED,
            authority=ItemResultAuthority.AUTHORITATIVE_SANDBOX,
            response_authenticated=True,
            response_hash="3" * 64,
            observed_at=NOW,
            formal_item_code="ITEM-0001",
            target_version="8",
        )
        expected = ItemMappingExpectation(2, "ITEM-0001", "7", "a" * 64)
        self.assertEqual(
            classify_mapping_observation(expectation=expected, current=current, observation=observation),
            ItemMappingDisposition.ADVANCE,
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=replace(expected, mapping_version=3),
                current=current,
                observation=observation,
            ),
            ItemMappingDisposition.EXPECTATION_CONFLICT,
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=expected,
                current=current,
                observation=replace(observation, formal_item_code="ITEM-OTHER"),
            ),
            ItemMappingDisposition.TARGET_IDENTITY_CONFLICT,
        )

    def test_fault_matrix_never_authorizes_redispatch_and_timeout_after_boundary_is_uncertain(self) -> None:
        uncertain = classify_adapter_fault(adapter_boundary_crossed=True, timed_out=True)
        self.assertEqual(uncertain.request_state, ItemPublishRequestState.UNCERTAIN_AFTER_TIMEOUT)
        self.assertEqual(uncertain.fault_kind, ItemFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT)
        self.assertEqual(uncertain.retry_directive, ItemRetryDirective.RECONCILE_BEFORE_RETRY)
        self.assertTrue(uncertain.reconciliation_required)
        self.assertFalse(uncertain.redispatch_allowed)
        before = classify_adapter_fault(adapter_boundary_crossed=False, timed_out=True)
        self.assertEqual(before.request_state, ItemPublishRequestState.FAILED_RETRYABLE)
        rate = classify_adapter_fault(adapter_boundary_crossed=True, http_status=429)
        self.assertEqual(rate.retry_directive, ItemRetryDirective.RETRY_AFTER)
        invalid = classify_adapter_fault(
            adapter_boundary_crossed=True,
            http_status=200,
            response_contract_valid=False,
        )
        self.assertEqual(invalid.fault_kind, ItemFaultKind.RESPONSE_CONTRACT_INVALID)
        self.assertTrue(invalid.reconciliation_required)
        redirect = classify_adapter_fault(
            adapter_boundary_crossed=True,
            http_status=302,
        )
        self.assertEqual(redirect.fault_kind, ItemFaultKind.RESPONSE_CONTRACT_INVALID)
        self.assertEqual(redirect.request_state, ItemPublishRequestState.FAILED_FINAL)
        self.assertFalse(redirect.redispatch_allowed)

    def test_claim_lease_is_bounded_and_expiry_is_inclusive(self) -> None:
        lease = issue_item_claim(
            now=NOW,
            lease_seconds=60,
            previous_attempt_count=2,
            token=uid(40),
        )
        self.assertEqual(lease.attempt_count, 3)
        self.assertTrue(lease.is_live(NOW + timedelta(seconds=59)))
        self.assertFalse(lease.is_live(NOW + timedelta(seconds=60)))
        with self.assertRaises(ItemPublishContractError):
            issue_item_claim(now=NOW, lease_seconds=0, previous_attempt_count=0)


if __name__ == "__main__":
    unittest.main()
