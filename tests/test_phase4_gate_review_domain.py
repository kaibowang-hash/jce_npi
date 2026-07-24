from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed, VersionConflict
from npi_core.gate_review.domain import (
    ActivationKind,
    AuthorityBinding,
    DecisionOutcome,
    PolicyState,
    ReviewCycle,
    ReviewDenied,
    ReviewOutcome,
    ReviewPolicyVersion,
    ReviewStep,
    downstream_decision_is_current,
)

POLICY_ID = UUID("2e61347c-313a-4443-b531-b605e90d5f45")
GATE_TEMPLATE_ID = UUID("27a34964-9987-4e3c-b010-2e5165782c62")
GATE_ID = UUID("2bf63d3d-12db-47c7-b623-4dd42e76a7cb")
PROJECT_ID = UUID("47444697-ce5c-4ea4-8df1-1e1cf809dc2f")
NOW = datetime(2026, 7, 24, tzinfo=timezone.utc)
INPUT_HASH = "a" * 64


def policy() -> ReviewPolicyVersion:
    return ReviewPolicyVersion.create_draft(
        policy_global_id=POLICY_ID,
        policy_code="SYNTHETIC-P4-04",
        gate_template_global_id=GATE_TEMPLATE_ID,
        gate_template_version=1,
        gate_template_hash="b" * 64,
        steps=(
            ReviewStep("engineering", 1, "engineering_reviewer"),
            ReviewStep("tooling", 1, "tooling_reviewer"),
            ReviewStep(
                "quality",
                2,
                "quality_reviewer",
                ActivationKind.REQUIREMENT_PRIORITY_PRESENT,
                "P0",
            ),
        ),
        decision_authority_slot="gate_decider",
        reopen_authority_slot="gate_reopener",
    ).publish(1)


def bindings() -> tuple[AuthorityBinding, ...]:
    return tuple(
        AuthorityBinding(slot, UUID(int=index), user, name)
        for index, (slot, user, name) in enumerate(
            (
                ("engineering_reviewer", "eng@example.test", "Engineering Reviewer"),
                ("tooling_reviewer", "tool@example.test", "Tooling Reviewer"),
                ("quality_reviewer", "quality@example.test", "Quality Reviewer"),
                ("gate_decider", "decider@example.test", "Gate Decider"),
                ("gate_reopener", "reopen@example.test", "Gate Reopener"),
            ),
            1,
        )
    )


def cycle() -> ReviewCycle:
    return ReviewCycle.start(
        gate_global_id=GATE_ID,
        project_global_id=PROJECT_ID,
        tenant_id="tenant-test",
        cycle_number=1,
        policy=policy(),
        bindings=bindings(),
        requirement_priorities=frozenset({"P0"}),
        input_hash=INPUT_HASH,
    )


class GateReviewPolicyTest(unittest.TestCase):
    def test_policy_is_versioned_canonical_and_immutable(self) -> None:
        value = policy()
        self.assertEqual(value.state, PolicyState.PUBLISHED)
        self.assertEqual(len(value.snapshot_hash), 64)
        with self.assertRaises(FrozenInstanceError):
            value.policy_code = "changed"  # type: ignore[misc]
        with self.assertRaises(ReviewDenied):
            value.publish(value.version)

    def test_policy_separates_assignment_and_decision_authority(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ReviewPolicyVersion.create_draft(
                policy_global_id=POLICY_ID,
                policy_code="BAD",
                gate_template_global_id=GATE_TEMPLATE_ID,
                gate_template_version=1,
                gate_template_hash="b" * 64,
                steps=(ReviewStep("review", 1, "same"),),
                decision_authority_slot="same",
                reopen_authority_slot="reopen",
            )

    def test_policy_rejects_unknown_condition_and_incomplete_bindings(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ReviewStep("review", 1, "reviewer", "script")  # type: ignore[arg-type]
        with self.assertRaises(RequestValidationFailed):
            ReviewCycle.start(
                gate_global_id=GATE_ID,
                project_global_id=PROJECT_ID,
                tenant_id="tenant-test",
                cycle_number=1,
                policy=policy(),
                bindings=bindings()[:-1],
                requirement_priorities=frozenset({"P0"}),
                input_hash=INPUT_HASH,
            )


class GateReviewCycleTest(unittest.TestCase):
    def test_parallel_reviews_then_conditional_sequential_review(self) -> None:
        value = cycle()
        with self.assertRaises(ReviewDenied) as blocked:
            value.submit_review(
                step_key="quality",
                actor_user_id="quality@example.test",
                outcome=ReviewOutcome.APPROVED,
                opinion="Approved.",
                occurred_at=NOW,
                expected_version=1,
                expected_input_hash=INPUT_HASH,
            )
        self.assertEqual(blocked.exception.code, "REVIEW_SEQUENCE_BLOCKED")
        value = value.submit_review(
            step_key="tooling",
            actor_user_id="tool@example.test",
            outcome=ReviewOutcome.APPROVED,
            opinion="Tooling evidence accepted.",
            occurred_at=NOW,
            expected_version=1,
            expected_input_hash=INPUT_HASH,
        )
        value = value.submit_review(
            step_key="engineering",
            actor_user_id="eng@example.test",
            outcome=ReviewOutcome.APPROVED,
            opinion="Engineering evidence accepted.",
            occurred_at=NOW,
            expected_version=2,
            expected_input_hash=INPUT_HASH,
        )
        value = value.submit_review(
            step_key="quality",
            actor_user_id="quality@example.test",
            outcome=ReviewOutcome.APPROVED,
            opinion="Quality evidence accepted.",
            occurred_at=NOW,
            expected_version=3,
            expected_input_hash=INPUT_HASH,
        )
        self.assertEqual(
            [record.step_key for record in value.reviews],
            ["tooling", "engineering", "quality"],
        )

    def test_review_assignment_does_not_grant_decision_authority(self) -> None:
        with self.assertRaises(ReviewDenied) as denied:
            cycle().decide(
                actor_user_id="eng@example.test",
                outcome=DecisionOutcome.REJECT,
                occurred_at=NOW,
                expected_version=1,
                expected_input_hash=INPUT_HASH,
                required_evidence_complete=False,
                file_evidence_safe=False,
                blocking_items=2,
            )
        self.assertEqual(denied.exception.code, "DECISION_AUTHORITY_REQUIRED")

    def test_pass_fails_closed_for_reviews_evidence_files_and_blockers(self) -> None:
        value = cycle()
        for code, kwargs in (("REVIEWS_INCOMPLETE", {}),):
            with self.assertRaises(ReviewDenied) as denied:
                value.decide(
                    actor_user_id="decider@example.test",
                    outcome=DecisionOutcome.PASS,
                    occurred_at=NOW,
                    expected_version=value.version,
                    expected_input_hash=INPUT_HASH,
                    required_evidence_complete=True,
                    file_evidence_safe=True,
                    blocking_items=0,
                    **kwargs,
                )
            self.assertEqual(denied.exception.code, code)
        for key, user in (
            ("engineering", "eng@example.test"),
            ("tooling", "tool@example.test"),
            ("quality", "quality@example.test"),
        ):
            value = value.submit_review(
                step_key=key,
                actor_user_id=user,
                outcome=ReviewOutcome.APPROVED,
                opinion="Approved with exact evidence.",
                occurred_at=NOW,
                expected_version=value.version,
                expected_input_hash=INPUT_HASH,
            )
        cases = (
            (False, True, 0, "REQUIRED_EVIDENCE_MISSING"),
            (True, False, 0, "FILE_EVIDENCE_UNSAFE"),
            (True, True, 1, "GATE_BLOCKED"),
        )
        for complete, safe, blockers, code in cases:
            with self.assertRaises(ReviewDenied) as denied:
                value.decide(
                    actor_user_id="decider@example.test",
                    outcome=DecisionOutcome.PASS,
                    occurred_at=NOW,
                    expected_version=value.version,
                    expected_input_hash=INPUT_HASH,
                    required_evidence_complete=complete,
                    file_evidence_safe=safe,
                    blocking_items=blockers,
                )
            self.assertEqual(denied.exception.code, code)

    def test_decision_snapshot_is_server_built_and_reopen_preserves_it(self) -> None:
        value = cycle()
        for key, user in (
            ("engineering", "eng@example.test"),
            ("tooling", "tool@example.test"),
            ("quality", "quality@example.test"),
        ):
            value = value.submit_review(
                step_key=key,
                actor_user_id=user,
                outcome=ReviewOutcome.APPROVED,
                opinion="Approved with exact evidence.",
                occurred_at=NOW,
                expected_version=value.version,
                expected_input_hash=INPUT_HASH,
            )
        decided = value.decide(
            actor_user_id="decider@example.test",
            outcome=DecisionOutcome.PASS,
            occurred_at=NOW,
            expected_version=value.version,
            expected_input_hash=INPUT_HASH,
            required_evidence_complete=True,
            file_evidence_safe=True,
            blocking_items=0,
        )
        self.assertTrue(downstream_decision_is_current(decided, INPUT_HASH))
        self.assertFalse(downstream_decision_is_current(decided, "c" * 64))
        reopened = decided.reopen(
            actor_user_id="reopen@example.test",
            reason="Controlled input changed.",
            occurred_at=NOW,
            current_input_hash="c" * 64,
        )
        self.assertEqual(reopened.cycle_number, 2)
        self.assertEqual(reopened.prior_decision_hash, decided.decision.snapshot_hash)  # type: ignore[union-attr]
        self.assertEqual(reopened.reviews, ())
        self.assertIsNone(reopened.decision)

    def test_stale_version_or_input_is_rejected(self) -> None:
        with self.assertRaises(VersionConflict):
            cycle().submit_review(
                step_key="engineering",
                actor_user_id="eng@example.test",
                outcome=ReviewOutcome.APPROVED,
                opinion="Approved.",
                occurred_at=NOW,
                expected_version=2,
                expected_input_hash=INPUT_HASH,
            )
        with self.assertRaises(VersionConflict):
            cycle().submit_review(
                step_key="engineering",
                actor_user_id="eng@example.test",
                outcome=ReviewOutcome.APPROVED,
                opinion="Approved.",
                occurred_at=NOW,
                expected_version=1,
                expected_input_hash="c" * 64,
            )


if __name__ == "__main__":
    unittest.main()
