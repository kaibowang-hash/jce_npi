from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.integration_operations.domain import (  # noqa: E402
    IntegrationActionKind,
    IntegrationActionOutcome,
    IntegrationActionReceipt,
    IntegrationFaultClass,
    IntegrationOperationKind,
    IntegrationOperationReference,
    IntegrationOperationsContractError,
    IntegrationReconciliationObservation,
    IntegrationViewState,
    ReconciliationAuthority,
    ReconciliationObservationState,
    ReconciliationObserverKind,
    ReplayEligibilityReason,
    canonical_hash,
    classify_operation_state,
    evaluate_replay_eligibility,
)


NOW = datetime(2026, 8, 28, 3, 4, 5, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{value:012d}")


def stable_uid(value: int) -> UUID:
    return UUID(f"00000000-0000-5000-8000-{value:012d}")


def operation(
    kind: IntegrationOperationKind = IntegrationOperationKind.PUBLISH_ITEM,
    raw_state: str = "failed_retryable",
) -> IntegrationOperationReference:
    classification = classify_operation_state(kind, raw_state)
    return IntegrationOperationReference(
        tenant_id="tenant-p807",
        project_global_id=stable_uid(1),
        operation_kind=kind,
        operation_global_id=uid(2),
        source_global_id=uid(3),
        operation_version=2,
        raw_state=raw_state,
        shared_state=classification.shared_state,
        source_snapshot_hash="a" * 64,
        target_idempotency_key_hash="b" * 64,
    )


def replay_receipt() -> IntegrationActionReceipt:
    response = {
        "actionGlobalId": str(uid(4)),
        "operationGlobalId": str(uid(2)),
        "outcomeState": "replay_requested",
        "outcomeReferenceGlobalId": str(uid(5)),
    }
    return IntegrationActionReceipt(
        global_id=uid(4),
        operation=operation(),
        action_kind=IntegrationActionKind.REPLAY,
        action_idempotency_key_hash="c" * 64,
        expected_raw_state="failed_retryable",
        expected_version=2,
        request_hash="d" * 64,
        outcome_state=IntegrationActionOutcome.REPLAY_REQUESTED,
        outcome_reference_global_id=uid(5),
        response_snapshot=response,
        response_hash=canonical_hash(response),
        actor_user_id="integration.operator@example.invalid",
        trace_id="trace-p807-domain-001",
        created_at=NOW,
    )


class Phase8IntegrationOperationsDomainTest(unittest.TestCase):
    def test_fixed_inventory_preserves_raw_state_and_never_promotes_synthetic_truth(self) -> None:
        expected = {
            IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: {
                "pending": "queued",
                "processing": "processing",
                "succeeded": "succeeded",
                "failed_retryable": "failed_retryable",
                "failed_final": "failed_final",
                "quarantined": "quarantined",
                "superseded": "conflict",
                "received_after_creation": "succeeded",
            },
            IntegrationOperationKind.PUBLISH_ITEM: {
                "validated_mock": "unavailable",
                "queued": "queued",
                "processing": "processing",
                "synthetic_verified": "unavailable",
                "succeeded": "succeeded",
                "failed_retryable": "failed_retryable",
                "failed_final": "failed_final",
                "uncertain_after_timeout": "uncertain",
                "mapping_conflict": "conflict",
            },
            IntegrationOperationKind.PUBLISH_MBOM: {
                "partially_succeeded": "partial",
            },
            IntegrationOperationKind.CREATE_TOOL_ASSET: {
                "partially_succeeded": "partial",
            },
            IntegrationOperationKind.UPDATE_TOOL_ASSET: {
                "partially_succeeded": "partial",
            },
            IntegrationOperationKind.RECEIVE_ENGINEERING_CHANGE_EVENT: {
                "pending": "queued",
                "processing": "processing",
                "succeeded": "succeeded",
                "failed_retryable": "failed_retryable",
                "failed_final": "failed_final",
                "quarantined": "quarantined",
                "superseded": "conflict",
            },
            IntegrationOperationKind.PUBLISH_CHANGE_IMPLEMENTATION_SUMMARY: {
                "queued": "queued",
                "processing": "processing",
                "synthetic_verified": "unavailable",
                "succeeded": "succeeded",
                "failed_retryable": "failed_retryable",
                "failed_final": "failed_final",
                "partially_succeeded": "partial",
                "uncertain_after_timeout": "uncertain",
                "identity_conflict": "conflict",
            },
        }
        for kind, states in expected.items():
            for raw_state, shared_state in states.items():
                with self.subTest(kind=kind, raw_state=raw_state):
                    value = classify_operation_state(kind, raw_state)
                    self.assertEqual(value.raw_state, raw_state)
                    self.assertEqual(value.shared_state.value, shared_state)
                    self.assertTrue(value.known_raw_state)
        unknown = classify_operation_state(
            IntegrationOperationKind.PUBLISH_ITEM,
            "future_unrecognized_state",
        )
        self.assertEqual(unknown.raw_state, "future_unrecognized_state")
        self.assertEqual(unknown.shared_state, IntegrationViewState.UNAVAILABLE)
        self.assertEqual(unknown.fault_class, IntegrationFaultClass.UNKNOWN_RAW_STATE)
        self.assertFalse(unknown.logical_dlq)

    def test_logical_dlq_is_derived_and_replay_requires_exact_safe_truth(self) -> None:
        for state, expected in (
            ("failed_retryable", True),
            ("failed_final", True),
            ("uncertain_after_timeout", True),
            ("mapping_conflict", True),
            ("succeeded", False),
            ("validated_mock", False),
        ):
            classification = classify_operation_state(
                IntegrationOperationKind.PUBLISH_ITEM,
                state,
            )
            self.assertEqual(classification.logical_dlq, expected)
        retryable = classify_operation_state(
            IntegrationOperationKind.PUBLISH_ITEM,
            "failed_retryable",
        )
        self.assertEqual(
            evaluate_replay_eligibility(
                retryable,
                uncertain_boundary=False,
                reconciliation_required=False,
                partial_result=False,
            ).reason,
            ReplayEligibilityReason.ELIGIBLE,
        )
        for kwargs, reason in (
            (
                {
                    "uncertain_boundary": True,
                    "reconciliation_required": False,
                    "partial_result": False,
                },
                ReplayEligibilityReason.UNCERTAIN_BOUNDARY,
            ),
            (
                {
                    "uncertain_boundary": False,
                    "reconciliation_required": True,
                    "partial_result": False,
                },
                ReplayEligibilityReason.RECONCILIATION_REQUIRED,
            ),
            (
                {
                    "uncertain_boundary": False,
                    "reconciliation_required": False,
                    "partial_result": True,
                },
                ReplayEligibilityReason.PARTIAL_RESULT,
            ),
        ):
            decision = evaluate_replay_eligibility(retryable, **kwargs)
            self.assertFalse(decision.eligible)
            self.assertEqual(decision.reason, reason)
        unknown = classify_operation_state(
            IntegrationOperationKind.PUBLISH_ITEM,
            "future_state",
        )
        self.assertEqual(
            evaluate_replay_eligibility(
                unknown,
                uncertain_boundary=False,
                reconciliation_required=False,
                partial_result=False,
            ).reason,
            ReplayEligibilityReason.UNKNOWN_RAW_STATE,
        )

    def test_operation_reference_rejects_state_version_identity_and_hash_drift(self) -> None:
        exact = operation()
        self.assertEqual(exact.project_global_id.version, 5)
        self.assertEqual(
            replace(exact, project_global_id=uid(1)).project_global_id.version,
            4,
        )
        self.assertEqual(
            exact.classification.shared_state,
            IntegrationViewState.FAILED_RETRYABLE,
        )
        for mutation in (
            {"shared_state": IntegrationViewState.SUCCEEDED},
            {"operation_version": 0},
            {
                "operation_global_id": UUID(
                    "00000000-0000-1000-8000-000000000002"
                )
            },
            {"source_snapshot_hash": "A" * 64},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(
                IntegrationOperationsContractError
            ):
                replace(exact, **mutation)

    def test_action_receipt_is_immutable_exact_and_redacts_transport_material(self) -> None:
        receipt = replay_receipt()
        self.assertEqual(receipt.payload()["operation"]["rawState"], "failed_retryable")
        self.assertEqual(len(receipt.receipt_hash), 64)
        for mutation in (
            {"expected_raw_state": "failed_final"},
            {"expected_version": 3},
            {"outcome_state": IntegrationActionOutcome.RECONCILIATION_REQUESTED},
            {"response_hash": "e" * 64},
            {"operation": operation(raw_state="succeeded")},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(
                IntegrationOperationsContractError
            ):
                replace(receipt, **mutation)
        unsafe = dict(receipt.response_snapshot)
        unsafe["targetResponse"] = {"body": "not allowed"}
        with self.assertRaisesRegex(
            IntegrationOperationsContractError,
            "prohibited transport",
        ):
            replace(
                receipt,
                response_snapshot=unsafe,
                response_hash=canonical_hash(unsafe),
            )
        for drift in (
            {**receipt.response_snapshot, "unexpected": "safe-but-not-contracted"},
            {**receipt.response_snapshot, "operationGlobalId": str(uid(9))},
            {**receipt.response_snapshot, "outcomeReferenceGlobalId": None},
        ):
            with self.subTest(drift=drift), self.assertRaises(
                IntegrationOperationsContractError
            ):
                replace(
                    receipt,
                    response_snapshot=drift,
                    response_hash=canonical_hash(drift),
                )

    def test_reconciliation_request_is_intent_and_observation_requires_trusted_evidence(self) -> None:
        uncertain = operation(raw_state="uncertain_after_timeout")
        response = {
            "actionGlobalId": str(uid(6)),
            "operationGlobalId": str(uid(2)),
            "outcomeState": "reconciliation_requested",
            "outcomeReferenceGlobalId": None,
        }
        request = IntegrationActionReceipt(
            global_id=uid(6),
            operation=uncertain,
            action_kind=IntegrationActionKind.REQUEST_RECONCILIATION,
            action_idempotency_key_hash="c" * 64,
            expected_raw_state=uncertain.raw_state,
            expected_version=uncertain.operation_version,
            request_hash="d" * 64,
            outcome_state=IntegrationActionOutcome.RECONCILIATION_REQUESTED,
            outcome_reference_global_id=None,
            response_snapshot=response,
            response_hash=canonical_hash(response),
            actor_user_id="integration.operator@example.invalid",
            trace_id="trace-p807-domain-002",
            created_at=NOW,
        )
        evidence = {
            "sourceSnapshotHash": uncertain.source_snapshot_hash,
            "targetIdempotencyKeyHash": uncertain.target_idempotency_key_hash,
            "resultReferenceHash": "e" * 64,
        }
        observation = IntegrationReconciliationObservation(
            global_id=uid(7),
            operation=uncertain,
            action_receipt_global_id=request.global_id,
            attempt_global_id=uid(8),
            state=ReconciliationObservationState.CONFIRMED_SUCCEEDED,
            observer_kind=ReconciliationObserverKind.TRUSTED_OPERATION_SERVICE,
            authority=ReconciliationAuthority.AUTHORITATIVE_SANDBOX,
            response_authenticated=True,
            profile_id="sandbox-profile-v1",
            profile_version=1,
            adapter_code="item-publish-sandbox-v1",
            evidence_snapshot=evidence,
            evidence_hash=canonical_hash(evidence),
            observer_id="integration.service@example.invalid",
            trace_id="trace-p807-domain-003",
            observed_at=NOW,
        )
        self.assertEqual(
            observation.payload()["reconciliationState"],
            "confirmed_succeeded",
        )
        for mutation in (
            {"authority": ReconciliationAuthority.NONE},
            {"response_authenticated": False},
            {"observer_kind": "human"},
            {"evidence_hash": "f" * 64},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(
                IntegrationOperationsContractError
            ):
                replace(observation, **mutation)
        for drift in (
            {**evidence, "extraSafeHash": "f" * 64},
            {**evidence, "sourceSnapshotHash": "f" * 64},
            {**evidence, "targetIdempotencyKeyHash": "f" * 64},
            {**evidence, "resultReferenceHash": "not-a-hash"},
        ):
            with self.subTest(drift=drift), self.assertRaises(
                IntegrationOperationsContractError
            ):
                replace(
                    observation,
                    evidence_snapshot=drift,
                    evidence_hash=canonical_hash(drift),
                )
        unavailable = replace(
            observation,
            state=ReconciliationObservationState.TARGET_UNAVAILABLE,
            authority=ReconciliationAuthority.NONE,
            response_authenticated=False,
        )
        self.assertEqual(unavailable.authority, ReconciliationAuthority.NONE)
        with self.assertRaises(IntegrationOperationsContractError):
            replace(unavailable, response_authenticated=True)


if __name__ == "__main__":
    unittest.main()
