from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.quality_link.domain import (  # noqa: E402
    FormalQualityObservationReference, FormalQualityRecordKind,
    QualityLinkCommandIdentity, QualityLinkContractError, QualityLinkFaultKind,
    QualityLinkReconciliation, QualityLinkReconciliationReason,
    QualityLinkReconciliationState, QualityLinkRevision, QualityLinkState,
    QualitySourceKind, QualitySourceReference, canonical_payload_hash,
    quality_link_reconciliation,
)


def uid(value: int) -> UUID:
    return UUID(int=value)


def source() -> QualitySourceReference:
    return QualitySourceReference("tenant-test", uid(1), QualitySourceKind.TRIAL_ROUND, uid(2), 3, "completed", "a" * 64)


def observation() -> FormalQualityObservationReference:
    return FormalQualityObservationReference(
        "tenant-test", uid(1), "trial_round", uid(2), uid(3), uid(4), 5,
        "Quality Inspection", "QI-SYNTHETIC", "opaque-v1",
        FormalQualityRecordKind.QUALITY_INSPECTION, "RAW_STATUS", None,
        "b" * 64, "c" * 64, "d" * 64, "quality-freshness-v1",
    )


def revision() -> QualityLinkRevision:
    return QualityLinkRevision(uid(5), "e" * 64, 1, None, source(), observation(), QualityLinkState.LINKED, "user@example.invalid", "trace-quality-link", datetime(2026, 8, 26, tzinfo=UTC))


class Phase8QualityLinkDomainTest(unittest.TestCase):
    def test_command_identity_is_operation_specific_hashed_and_faults_are_closed(self) -> None:
        command = QualityLinkCommandIdentity(
            "tenant-test", uid(1), "user@example.invalid",
            "link_observed_formal_quality_reference", "1" * 64, "2" * 64, "3" * 64, "4" * 64,
        )
        self.assertEqual(len(command.receipt_key_hash), 64)
        self.assertNotIn("key", command.payload()["idempotencyKeyHash"])
        self.assertEqual(len(QualityLinkFaultKind), 5)
        with self.assertRaises(QualityLinkContractError):
            replace(command, operation="link_latest_quality")

    def test_link_preserves_raw_formal_truth_without_pass_interpretation(self) -> None:
        payload = revision().payload()
        formal = payload["formalObservation"]
        self.assertEqual(formal["projectionKind"], "formal_quality_status")
        self.assertEqual(formal["sourceSystem"], "ERPNEXT")
        self.assertEqual((formal["availability"], formal["freshness"], formal["disposition"]), ("available", "fresh", "applied_current"))
        self.assertNotIn("pass", str(payload).casefold())

    def test_source_context_record_and_state_enums_are_closed(self) -> None:
        self.assertEqual(len(QualitySourceKind), 5)
        self.assertEqual({item.value for item in FormalQualityRecordKind}, {"quality_inspection", "ncr", "capa"})
        self.assertEqual({item.value for item in QualityLinkState}, {"linked", "superseded"})
        for field, value in (("source_kind", "trial"), ("source_version", 0), ("source_snapshot_hash", "not-a-hash")):
            with self.subTest(field=field), self.assertRaises(QualityLinkContractError):
                replace(source(), **{field: value})

    def test_containment_and_exact_successor_are_fail_closed(self) -> None:
        with self.assertRaises(QualityLinkContractError):
            replace(revision(), observation=replace(observation(), project_global_id=uid(99)))
        with self.assertRaises(QualityLinkContractError):
            replace(revision(), revision_number=2)
        successor = replace(revision(), global_id=uid(6), revision_number=2, predecessor_global_id=uid(5), state=QualityLinkState.SUPERSEDED)
        self.assertEqual(successor.revision_number, 2)

    def test_hash_is_canonical_stable_and_sensitive_to_raw_truth(self) -> None:
        candidate = revision()
        self.assertEqual(candidate.payload_hash, canonical_payload_hash(candidate.payload()))
        reordered = dict(reversed(list(candidate.payload().items())))
        self.assertEqual(candidate.payload_hash, canonical_payload_hash(reordered))
        changed = replace(candidate, observation=replace(observation(), status_code="OTHER_RAW_STATUS"))
        self.assertNotEqual(candidate.payload_hash, changed.payload_hash)

    def test_reconciliation_state_reason_pairs_are_closed_and_non_interpreting(self) -> None:
        current = quality_link_reconciliation(
            QualityLinkReconciliationState.CURRENT,
            QualityLinkReconciliationState.CURRENT,
        )
        self.assertEqual(
            current.payload(),
            {"state": "current", "reasonCode": "linked_truth_current"},
        )
        cases = (
            (
                QualityLinkReconciliationState.DRIFTED,
                QualityLinkReconciliationState.CURRENT,
                "linked_source_advanced",
            ),
            (
                QualityLinkReconciliationState.CURRENT,
                QualityLinkReconciliationState.DRIFTED,
                "linked_projection_advanced",
            ),
            (
                QualityLinkReconciliationState.DRIFTED,
                QualityLinkReconciliationState.DRIFTED,
                "linked_source_and_projection_advanced",
            ),
            (
                QualityLinkReconciliationState.UNAVAILABLE,
                QualityLinkReconciliationState.CURRENT,
                "current_truth_unavailable",
            ),
        )
        for source_state, projection_state, reason in cases:
            with self.subTest(reason=reason):
                payload = quality_link_reconciliation(
                    source_state,
                    projection_state,
                ).payload()
                self.assertEqual(payload["reasonCode"], reason)
                self.assertNotIn("pass", str(payload).casefold())
        with self.assertRaises(QualityLinkContractError):
            QualityLinkReconciliation(
                QualityLinkReconciliationState.CURRENT,
                QualityLinkReconciliationReason.SOURCE_ADVANCED,
            )


if __name__ == "__main__":
    unittest.main()
