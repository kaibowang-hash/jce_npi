from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed, VersionConflict
from npi_core.gate_review.domain import (
    ActivationKind,
    AuthorityBinding,
    ClosureActionReference,
    CycleState,
    CycleTrigger,
    DecisionOutcome,
    DependencyEvaluator,
    ExceptionOutcome,
    ExceptionRule,
    ExceptionState,
    GateBlockerInput,
    GateDependencyInput,
    GateEvidenceInput,
    GateInputSnapshot,
    GateRequirementInput,
    PolicyState,
    ReviewCycle,
    ReviewDenied,
    ReviewEventKind,
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
REQUIREMENT_P0_ID = UUID("847e666c-5371-4220-94c7-5e2c7e05a1bf")
REQUIREMENT_P1_ID = UUID("8e1f05c9-21bf-45a6-8551-f6dbabacbe73")
EVIDENCE_ID = UUID("786b239a-fcbf-4ddd-bd55-59719a8a28ac")
SOURCE_ID = UUID("d73df0ec-ef0e-444a-a8bc-a5e9a08c0014")
DEPENDENCY_ID = UUID("4abcc093-5366-4a58-a6d2-7efcdf824840")
EXCEPTION_ID = UUID("44f290f7-43a7-4453-a13a-2207131fb3c7")
ACTION_ID = UUID("a05978ee-1e35-4340-a693-6e211bc0880c")
ACTION_REF = ClosureActionReference(ACTION_ID, 3, "a" * 64)
REQUESTER_MEMBER_ID = UUID("7be3a1c2-552f-4b38-af14-8b457c64409b")


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
        exception_rules=(
            ExceptionRule(
                "p1_evidence_timing",
                ("supplier_timing",),
                "exception_approver",
                14,
                "action",
            ),
        ),
        dependency_evaluators=(DependencyEvaluator.GATE_INPUT_SNAPSHOT,),
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
                (
                    "exception_approver",
                    "exception@example.test",
                    "Exception Approver",
                ),
            ),
            1,
        )
    )


def input_snapshot(
    *,
    p0_complete: bool = True,
    p1_complete: bool = True,
    file_safe: bool = True,
    blocker: bool = False,
    dependency_hash: str = "e" * 64,
    gate_version: int = 1,
) -> GateInputSnapshot:
    return GateInputSnapshot(
        gate_global_id=GATE_ID,
        project_global_id=PROJECT_ID,
        tenant_id="tenant-test",
        gate_version=gate_version,
        requirements=(
            GateRequirementInput(
                REQUIREMENT_P0_ID,
                "design_release",
                "P0",
                3,
                "a" * 64,
                p0_complete,
            ),
            GateRequirementInput(
                REQUIREMENT_P1_ID,
                "supplier_timing",
                "P1",
                2,
                "b" * 64,
                p1_complete,
            ),
        ),
        evidence=(
            GateEvidenceInput(
                EVIDENCE_ID,
                REQUIREMENT_P0_ID,
                "file_revision",
                SOURCE_ID,
                4,
                "c" * 64,
                True,
                file_safe,
            ),
        ),
        blockers=(
            GateBlockerInput(
                UUID("bc8d129b-3afe-4d06-a729-7231cc30e541"),
                2,
                "open",
                blocker,
                False,
            ),
        ),
        dependencies=(
            GateDependencyInput(
                DependencyEvaluator.GATE_INPUT_SNAPSHOT,
                DEPENDENCY_ID,
                5,
                dependency_hash,
            ),
        ),
    )


INPUT_HASH = input_snapshot().snapshot_hash


def cycle(snapshot: GateInputSnapshot | None = None) -> ReviewCycle:
    frozen_input = snapshot or input_snapshot()
    return ReviewCycle.start(
        gate_global_id=GATE_ID,
        project_global_id=PROJECT_ID,
        tenant_id="tenant-test",
        cycle_number=1,
        trigger=CycleTrigger.MANUAL_START,
        policy=policy(),
        bindings=bindings(),
        input_snapshot=frozen_input,
    )


def approve_all(value: ReviewCycle) -> ReviewCycle:
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
            expected_input_hash=value.input_hash,
        )
    return value


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
                exception_rules=(),
                dependency_evaluators=(DependencyEvaluator.GATE_INPUT_SNAPSHOT,),
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
                trigger=CycleTrigger.MANUAL_START,
                policy=policy(),
                bindings=bindings()[:-1],
                input_snapshot=input_snapshot(),
            )
        conditional_only = ReviewPolicyVersion.create_draft(
            policy_global_id=POLICY_ID,
            policy_code="CONDITIONAL-ONLY",
            gate_template_global_id=GATE_TEMPLATE_ID,
            gate_template_version=1,
            gate_template_hash="b" * 64,
            steps=(
                ReviewStep(
                    "quality",
                    1,
                    "quality_reviewer",
                    ActivationKind.REQUIREMENT_PRIORITY_PRESENT,
                    "P2",
                ),
            ),
            decision_authority_slot="gate_decider",
            reopen_authority_slot="gate_reopener",
            exception_rules=(),
            dependency_evaluators=(DependencyEvaluator.GATE_INPUT_SNAPSHOT,),
        ).publish(1)
        with self.assertRaises(RequestValidationFailed):
            ReviewCycle.start(
                gate_global_id=GATE_ID,
                project_global_id=PROJECT_ID,
                tenant_id="tenant-test",
                cycle_number=1,
                trigger=CycleTrigger.MANUAL_START,
                policy=conditional_only,
                bindings=tuple(
                    binding
                    for binding in bindings()
                    if binding.slot
                    in {"quality_reviewer", "gate_decider", "gate_reopener"}
                ),
                input_snapshot=input_snapshot(),
            )

    def test_policy_next_draft_version_is_contiguous_and_canonical(self) -> None:
        published = policy()
        next_draft = published.next_draft(
            expected_version=published.version,
            gate_template_global_id=GATE_TEMPLATE_ID,
            gate_template_version=2,
            gate_template_hash="f" * 64,
            steps=published.steps,
            decision_authority_slot=published.decision_authority_slot,
            reopen_authority_slot=published.reopen_authority_slot,
            exception_rules=published.exception_rules,
            dependency_evaluators=published.dependency_evaluators,
        )
        self.assertEqual(next_draft.policy_version, published.policy_version + 1)
        self.assertEqual(next_draft.state, PolicyState.DRAFT)
        self.assertIn("exceptionRules", next_draft.canonical_dict())
        self.assertEqual(
            next_draft.canonical_dict()["dependencyEvaluators"],
            ["gate_input_snapshot"],
        )
        with self.assertRaises(VersionConflict):
            published.next_draft(
                expected_version=published.version + 1,
                gate_template_global_id=GATE_TEMPLATE_ID,
                gate_template_version=2,
                gate_template_hash="f" * 64,
                steps=published.steps,
                decision_authority_slot=published.decision_authority_slot,
                reopen_authority_slot=published.reopen_authority_slot,
                exception_rules=published.exception_rules,
                dependency_evaluators=published.dependency_evaluators,
            )

    def test_step_sequences_need_only_be_positive_and_roles_are_not_over_split(
        self,
    ) -> None:
        value = ReviewPolicyVersion.create_draft(
            policy_global_id=POLICY_ID,
            policy_code="NON-CONTIGUOUS",
            gate_template_global_id=GATE_TEMPLATE_ID,
            gate_template_version=1,
            gate_template_hash="b" * 64,
            steps=(
                ReviewStep("first", 2, "first_reviewer"),
                ReviewStep("later", 9, "later_reviewer"),
            ),
            decision_authority_slot="gate_authority",
            reopen_authority_slot="gate_authority",
            exception_rules=(
                ExceptionRule(
                    "controlled",
                    ("supplier_timing",),
                    "first_reviewer",
                    1,
                    "action",
                ),
            ),
            dependency_evaluators=(DependencyEvaluator.GATE_INPUT_SNAPSHOT,),
        ).publish(1)
        self.assertEqual([step.sequence for step in value.steps], [2, 9])
        self.assertEqual(
            value.decision_authority_slot,
            value.reopen_authority_slot,
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
                current_input=input_snapshot(),
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
                    current_input=input_snapshot(),
                    **kwargs,
                )
            self.assertEqual(denied.exception.code, code)
        cases = (
            (
                input_snapshot(p1_complete=False),
                "REQUIRED_EVIDENCE_MISSING",
            ),
            (input_snapshot(file_safe=False), "FILE_EVIDENCE_UNSAFE"),
            (input_snapshot(blocker=True), "GATE_BLOCKED"),
            (
                input_snapshot(p0_complete=False),
                "REQUIRED_P0_EVIDENCE_MISSING",
            ),
        )
        for snapshot, code in cases:
            value = approve_all(cycle(snapshot))
            with self.assertRaises(ReviewDenied) as denied:
                value.decide(
                    actor_user_id="decider@example.test",
                    outcome=DecisionOutcome.PASS,
                    occurred_at=NOW,
                    expected_version=value.version,
                    expected_input_hash=value.input_hash,
                    current_input=snapshot,
                )
            self.assertEqual(denied.exception.code, code)

    def test_decision_snapshot_is_server_built_and_reopen_preserves_it(self) -> None:
        snapshot = input_snapshot()
        value = approve_all(cycle(snapshot))
        current = replace(
            snapshot,
            requirements=tuple(reversed(snapshot.requirements)),
        )
        decided = value.decide(
            actor_user_id="decider@example.test",
            outcome=DecisionOutcome.PASS,
            occurred_at=NOW,
            expected_version=value.version,
            expected_input_hash=INPUT_HASH,
            current_input=current,
        )
        self.assertEqual(
            decided.decision.input_snapshot.canonical_dict(),  # type: ignore[union-attr]
            snapshot.canonical_dict(),
        )
        self.assertEqual(
            decided.decision.global_id,  # type: ignore[union-attr]
            uuid5(decided.global_id, "decision-snapshot"),
        )
        self.assertTrue(
            downstream_decision_is_current(
                decided,
                gate_current_cycle_global_id=decided.global_id,
                current_input=snapshot,
                at=NOW,
            )
        )
        changed = input_snapshot(dependency_hash="d" * 64, gate_version=2)
        transition = decided.reopen(
            actor_user_id="reopen@example.test",
            reason="Controlled input changed.",
            occurred_at=NOW,
            current_input=changed,
            current_bindings=bindings(),
            gate_current_cycle_global_id=decided.global_id,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
        )
        self.assertEqual(transition.prior_cycle.state, CycleState.INVALIDATED)
        self.assertIs(transition.prior_cycle.decision, decided.decision)
        self.assertEqual(transition.current_cycle.cycle_number, 2)
        self.assertEqual(transition.event.kind, ReviewEventKind.REOPENED)
        self.assertEqual(
            transition.current_cycle.prior_decision_hash,
            decided.decision.snapshot_hash,  # type: ignore[union-attr]
        )
        self.assertEqual(transition.current_cycle.reviews, ())
        self.assertFalse(
            downstream_decision_is_current(
                decided,
                gate_current_cycle_global_id=transition.current_cycle.global_id,
                current_input=changed,
                at=NOW,
            )
        )

    def test_conditional_pass_requires_controlled_exception_lifecycle(self) -> None:
        snapshot = input_snapshot(p1_complete=False)
        value = approve_all(cycle(snapshot))
        with self.assertRaises(ReviewDenied) as separated:
            value.request_exception(
                exception_global_id=EXCEPTION_ID,
                requester_member_global_id=REQUESTER_MEMBER_ID,
                actor_user_id="exception@example.test",
                kind="p1_evidence_timing",
                requirement_key="supplier_timing",
                reason="Supplier certificate will arrive after the Gate.",
                risk="Timing risk is bounded by the closure action.",
                closure_action_ref=ACTION_REF,
                closure_action_kind="action",
                requested_at=NOW,
                expires_at=NOW + timedelta(days=7),
                expected_version=value.version,
                expected_input_hash=value.input_hash,
            )
        self.assertEqual(
            separated.exception.code, "EXCEPTION_REQUESTER_APPROVER_CONFLICT"
        )
        approver_member_id = next(
            item.member_global_id
            for item in value.bindings
            if item.slot == "exception_approver"
        )
        with self.assertRaises(ReviewDenied) as member_separated:
            value.request_exception(
                exception_global_id=EXCEPTION_ID,
                requester_member_global_id=approver_member_id,
                actor_user_id="requester@example.test",
                kind="p1_evidence_timing",
                requirement_key="supplier_timing",
                reason="Same member cannot request and approve.",
                risk="Segregation risk.",
                closure_action_ref=ACTION_REF,
                closure_action_kind="action",
                requested_at=NOW,
                expires_at=NOW + timedelta(days=7),
                expected_version=value.version,
                expected_input_hash=value.input_hash,
            )
        self.assertEqual(
            member_separated.exception.code,
            "EXCEPTION_REQUESTER_APPROVER_CONFLICT",
        )
        value = value.request_exception(
            exception_global_id=EXCEPTION_ID,
            requester_member_global_id=REQUESTER_MEMBER_ID,
            actor_user_id="requester@example.test",
            kind="p1_evidence_timing",
            requirement_key="supplier_timing",
            reason="Supplier certificate will arrive after the Gate.",
            risk="Timing risk is bounded by the closure action.",
            closure_action_ref=ACTION_REF,
            closure_action_kind="action",
            requested_at=NOW,
            expires_at=NOW + timedelta(days=7),
            expected_version=value.version,
            expected_input_hash=value.input_hash,
        )
        self.assertEqual(value.exceptions[0].state, ExceptionState.PENDING)
        with self.assertRaises(ReviewDenied) as missing:
            value.decide(
                actor_user_id="decider@example.test",
                outcome=DecisionOutcome.CONDITIONAL_PASS,
                occurred_at=NOW + timedelta(minutes=30),
                expected_version=value.version,
                expected_input_hash=value.input_hash,
                current_input=snapshot,
                current_closure_action_refs={EXCEPTION_ID: ACTION_REF},
            )
        self.assertEqual(missing.exception.code, "APPROVED_EXCEPTION_REQUIRED")
        value = value.decide_exception(
            exception_global_id=EXCEPTION_ID,
            actor_user_id="exception@example.test",
            outcome=ExceptionOutcome.APPROVED,
            opinion="Approved with a dated closure action.",
            occurred_at=NOW + timedelta(hours=1),
            expected_version=value.version,
            expected_input_hash=value.input_hash,
            expected_exception_version=1,
        )
        self.assertEqual(value.exceptions[0].state, ExceptionState.APPROVED)
        with self.assertRaises(ReviewDenied) as one_way:
            value.decide_exception(
                exception_global_id=EXCEPTION_ID,
                actor_user_id="exception@example.test",
                outcome=ExceptionOutcome.REJECTED,
                opinion="Attempted replacement.",
                occurred_at=NOW + timedelta(hours=2),
                expected_version=value.version,
                expected_input_hash=value.input_hash,
                expected_exception_version=2,
            )
        self.assertEqual(one_way.exception.code, "EXCEPTION_ALREADY_DECIDED")
        changed_action_ref = replace(
            ACTION_REF,
            version=ACTION_REF.version + 1,
        )
        with self.assertRaises(ReviewDenied) as changed_action:
            value.decide(
                actor_user_id="decider@example.test",
                outcome=DecisionOutcome.CONDITIONAL_PASS,
                occurred_at=NOW + timedelta(hours=2),
                expected_version=value.version,
                expected_input_hash=value.input_hash,
                current_input=snapshot,
                current_closure_action_refs={
                    EXCEPTION_ID: changed_action_ref,
                },
            )
        self.assertEqual(
            changed_action.exception.code,
            "APPROVED_EXCEPTION_REQUIRED",
        )
        decided = value.decide(
            actor_user_id="decider@example.test",
            outcome=DecisionOutcome.CONDITIONAL_PASS,
            occurred_at=NOW + timedelta(hours=2),
            expected_version=value.version,
            expected_input_hash=value.input_hash,
            current_input=snapshot,
            current_closure_action_refs={EXCEPTION_ID: ACTION_REF},
        )
        self.assertEqual(
            decided.decision.outcome,  # type: ignore[union-attr]
            DecisionOutcome.CONDITIONAL_PASS,
        )
        self.assertEqual(len(decided.decision.exception_hashes), 1)  # type: ignore[union-attr]
        self.assertTrue(
            downstream_decision_is_current(
                decided,
                gate_current_cycle_global_id=decided.global_id,
                current_input=snapshot,
                at=NOW + timedelta(days=6),
                current_closure_action_refs={EXCEPTION_ID: ACTION_REF},
            )
        )
        self.assertFalse(
            downstream_decision_is_current(
                decided,
                gate_current_cycle_global_id=decided.global_id,
                current_input=snapshot,
                current_closure_action_refs={
                    EXCEPTION_ID: changed_action_ref,
                },
                at=NOW + timedelta(days=6),
            )
        )
        self.assertFalse(
            downstream_decision_is_current(
                decided,
                gate_current_cycle_global_id=decided.global_id,
                current_input=snapshot,
                at=NOW + timedelta(days=7),
            )
        )

    def test_p0_unsafe_file_expiry_and_closure_action_fail_closed(self) -> None:
        cases = (
            (
                input_snapshot(p0_complete=False),
                "design_release",
                "EXCEPTION_NOT_ELIGIBLE",
                "action",
            ),
            (
                input_snapshot(p1_complete=False, file_safe=False),
                "supplier_timing",
                "FILE_EVIDENCE_UNSAFE",
                "action",
            ),
            (
                input_snapshot(p1_complete=False),
                "supplier_timing",
                "CLOSURE_ACTION_REQUIRED",
                "task",
            ),
        )
        for snapshot, requirement_key, code, action_kind in cases:
            value = approve_all(cycle(snapshot))
            with self.assertRaises(ReviewDenied) as denied:
                value.request_exception(
                    exception_global_id=EXCEPTION_ID,
                    requester_member_global_id=REQUESTER_MEMBER_ID,
                    actor_user_id="requester@example.test",
                    kind="p1_evidence_timing",
                    requirement_key=requirement_key,
                    reason="Controlled exception request.",
                    risk="Controlled residual risk.",
                    closure_action_ref=ACTION_REF,
                    closure_action_kind=action_kind,
                    requested_at=NOW,
                    expires_at=NOW + timedelta(days=7),
                    expected_version=value.version,
                    expected_input_hash=value.input_hash,
                )
            self.assertEqual(denied.exception.code, code)

        snapshot = input_snapshot(p1_complete=False)
        value = approve_all(cycle(snapshot)).request_exception(
            exception_global_id=EXCEPTION_ID,
            requester_member_global_id=REQUESTER_MEMBER_ID,
            actor_user_id="requester@example.test",
            kind="p1_evidence_timing",
            requirement_key="supplier_timing",
            reason="Short-lived controlled exception.",
            risk="Expires before the delayed approval.",
            closure_action_ref=ACTION_REF,
            closure_action_kind="action",
            requested_at=NOW,
            expires_at=NOW + timedelta(hours=1),
            expected_version=4,
            expected_input_hash=snapshot.snapshot_hash,
        )
        with self.assertRaises(ReviewDenied) as expired:
            value.decide_exception(
                exception_global_id=EXCEPTION_ID,
                actor_user_id="exception@example.test",
                outcome=ExceptionOutcome.APPROVED,
                opinion="Too late.",
                occurred_at=NOW + timedelta(hours=1),
                expected_version=value.version,
                expected_input_hash=value.input_hash,
                expected_exception_version=1,
            )
        self.assertEqual(expired.exception.code, "EXCEPTION_EXPIRED")

    def test_legacy_exception_history_is_readable_but_never_current(self) -> None:
        snapshot = input_snapshot(p1_complete=False)
        value = approve_all(cycle(snapshot)).request_exception(
            exception_global_id=EXCEPTION_ID,
            requester_member_global_id=REQUESTER_MEMBER_ID,
            actor_user_id="requester@example.test",
            kind="p1_evidence_timing",
            requirement_key="supplier_timing",
            reason="Legacy controlled exception request.",
            risk="Legacy controlled residual risk.",
            closure_action_ref=ACTION_REF,
            closure_action_kind="action",
            requested_at=NOW,
            expires_at=NOW + timedelta(days=7),
            expected_version=4,
            expected_input_hash=snapshot.snapshot_hash,
        )
        value = value.decide_exception(
            exception_global_id=EXCEPTION_ID,
            actor_user_id="exception@example.test",
            outcome=ExceptionOutcome.APPROVED,
            opinion="Legacy approval retained for history.",
            occurred_at=NOW + timedelta(hours=1),
            expected_version=value.version,
            expected_input_hash=value.input_hash,
            expected_exception_version=1,
        )
        legacy = replace(
            value.exceptions[0],
            closure_action_ref=ClosureActionReference(ACTION_ID, None, None),
        )
        historical = replace(value, exceptions=(legacy,))
        requirement = snapshot.missing_requirements[0]

        self.assertIn("closureActionGlobalId", legacy.canonical_dict())
        self.assertNotIn("closureActionRef", legacy.canonical_dict())
        self.assertTrue(
            legacy.supports_recorded_decision(
                requirement,
                policy=historical.policy,
                input_hash=historical.input_hash,
                at=NOW + timedelta(hours=2),
            )
        )
        self.assertFalse(
            legacy.supports(
                requirement,
                policy=historical.policy,
                input_hash=historical.input_hash,
                at=NOW + timedelta(hours=2),
                current_closure_action_ref=ACTION_REF,
            )
        )
        with self.assertRaises(ReviewDenied) as denied:
            historical.decide(
                actor_user_id="decider@example.test",
                outcome=DecisionOutcome.CONDITIONAL_PASS,
                occurred_at=NOW + timedelta(hours=2),
                expected_version=historical.version,
                expected_input_hash=historical.input_hash,
                current_input=snapshot,
                current_closure_action_refs={EXCEPTION_ID: ACTION_REF},
            )
        self.assertEqual(denied.exception.code, "APPROVED_EXCEPTION_REQUIRED")

    def test_dependency_invalidation_uses_new_snapshot_bindings_and_guard(self) -> None:
        original = input_snapshot()
        decided = approve_all(cycle(original)).decide(
            actor_user_id="decider@example.test",
            outcome=DecisionOutcome.PASS,
            occurred_at=NOW,
            expected_version=4,
            expected_input_hash=original.snapshot_hash,
            current_input=original,
        )
        changed = replace(
            original,
            gate_version=2,
            requirements=(
                replace(original.requirements[0], priority="P2"),
                original.requirements[1],
            ),
            dependencies=(replace(original.dependencies[0], snapshot_hash="d" * 64),),
        )
        fresh_bindings = bindings()
        transition = decided.invalidate_for_dependency_change(
            actor_user_id="dependency-worker@example.test",
            reason="The exact Gate input dependency changed.",
            occurred_at=NOW + timedelta(hours=1),
            current_input=changed,
            current_bindings=fresh_bindings,
            gate_current_cycle_global_id=decided.global_id,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
        )
        self.assertEqual(transition.event.kind, ReviewEventKind.INVALIDATED)
        self.assertEqual(
            transition.event.prior_decision_snapshot_global_id,
            decided.decision.global_id,  # type: ignore[union-attr]
        )
        self.assertEqual(transition.event.old_input_hash, original.snapshot_hash)
        self.assertEqual(transition.event.new_input_hash, changed.snapshot_hash)
        self.assertNotIn(
            "quality", {step.key for step in transition.current_cycle.selected_steps}
        )
        self.assertIn(
            "quality_reviewer",
            {binding.slot for binding in transition.current_cycle.bindings},
        )
        self.assertEqual(transition.current_cycle.bindings, fresh_bindings)
        self.assertIs(transition.prior_cycle.decision, decided.decision)
        with self.assertRaises(VersionConflict):
            decided.invalidate_for_dependency_change(
                actor_user_id="dependency-worker@example.test",
                reason="Stale current-cycle pointer.",
                occurred_at=NOW + timedelta(hours=1),
                current_input=changed,
                current_bindings=fresh_bindings,
                gate_current_cycle_global_id=transition.current_cycle.global_id,
                expected_version=decided.version,
                expected_input_hash=decided.input_hash,
            )

    def test_active_dependency_refresh_preserves_history_and_lineage(self) -> None:
        original = input_snapshot()
        active = cycle(original).submit_review(
            step_key="engineering",
            actor_user_id="eng@example.test",
            outcome=ReviewOutcome.APPROVED,
            opinion="This review remains frozen on the superseded cycle.",
            occurred_at=NOW,
            expected_version=1,
            expected_input_hash=original.snapshot_hash,
        )
        changed = input_snapshot(
            dependency_hash="d" * 64,
            gate_version=2,
        )
        initial_refresh = active.invalidate_for_dependency_change(
            actor_user_id="npi-gate-review-dependency-system",
            initiated_by_user_id="disabled-initiator@example.test",
            reason="The active Gate input changed.",
            occurred_at=NOW + timedelta(minutes=5),
            current_input=changed,
            current_bindings=bindings(),
            gate_current_cycle_global_id=active.global_id,
            expected_version=active.version,
            expected_input_hash=active.input_hash,
        )
        self.assertEqual(
            initial_refresh.prior_cycle.state,
            CycleState.SUPERSEDED,
        )
        self.assertEqual(initial_refresh.prior_cycle.reviews, active.reviews)
        self.assertIsNone(initial_refresh.prior_cycle.decision)
        self.assertEqual(initial_refresh.event.kind, ReviewEventKind.REFRESHED)
        self.assertIsNone(initial_refresh.event.prior_decision_snapshot_global_id)
        self.assertIsNone(initial_refresh.event.prior_decision_hash)
        self.assertEqual(
            initial_refresh.event.initiated_by_user_id,
            "disabled-initiator@example.test",
        )
        self.assertIsNone(
            initial_refresh.current_cycle.prior_decision_snapshot_global_id
        )
        self.assertIsNone(initial_refresh.current_cycle.prior_decision_hash)

        decided = approve_all(cycle(original)).decide(
            actor_user_id="decider@example.test",
            outcome=DecisionOutcome.PASS,
            occurred_at=NOW,
            expected_version=4,
            expected_input_hash=original.snapshot_hash,
            current_input=original,
        )
        invalidated = decided.invalidate_for_dependency_change(
            actor_user_id="npi-gate-review-dependency-system",
            reason="The decided Gate input changed.",
            occurred_at=NOW + timedelta(minutes=10),
            current_input=changed,
            current_bindings=bindings(),
            gate_current_cycle_global_id=decided.global_id,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
        )
        changed_again = input_snapshot(
            dependency_hash="c" * 64,
            gate_version=3,
        )
        inherited_refresh = invalidated.current_cycle.invalidate_for_dependency_change(
            actor_user_id="npi-gate-review-dependency-system",
            reason="The replacement Gate input changed again.",
            occurred_at=NOW + timedelta(minutes=15),
            current_input=changed_again,
            current_bindings=bindings(),
            gate_current_cycle_global_id=(invalidated.current_cycle.global_id),
            expected_version=invalidated.current_cycle.version,
            expected_input_hash=invalidated.current_cycle.input_hash,
        )
        assert decided.decision is not None
        self.assertEqual(
            inherited_refresh.prior_cycle.state,
            CycleState.SUPERSEDED,
        )
        self.assertEqual(
            inherited_refresh.current_cycle.prior_decision_snapshot_global_id,
            decided.decision.global_id,
        )
        self.assertEqual(
            inherited_refresh.current_cycle.prior_decision_hash,
            decided.decision.snapshot_hash,
        )
        self.assertEqual(
            inherited_refresh.event.prior_decision_snapshot_global_id,
            decided.decision.global_id,
        )
        self.assertEqual(
            inherited_refresh.event.prior_decision_hash,
            decided.decision.snapshot_hash,
        )

    def test_hydration_rejects_forged_review_decision_exception_and_event(
        self,
    ) -> None:
        snapshot = input_snapshot()
        reviewed = approve_all(cycle(snapshot))
        with self.assertRaises(RequestValidationFailed):
            replace(
                reviewed,
                reviews=(
                    replace(
                        reviewed.reviews[0],
                        actor_user_id="other@example.test",
                    ),
                    *reviewed.reviews[1:],
                ),
            )

        decided = reviewed.decide(
            actor_user_id="decider@example.test",
            outcome=DecisionOutcome.PASS,
            occurred_at=NOW,
            expected_version=reviewed.version,
            expected_input_hash=reviewed.input_hash,
            current_input=snapshot,
        )
        decision = decided.decision
        self.assertIsNotNone(decision)
        with self.assertRaises(RequestValidationFailed):
            replace(decision, global_id=UUID(int=99))  # type: ignore[arg-type]
        wrong_policy_decision = type(decision).build(
            tenant_id=decision.tenant_id,  # type: ignore[union-attr]
            project_global_id=decision.project_global_id,  # type: ignore[union-attr]
            gate_global_id=decision.gate_global_id,  # type: ignore[union-attr]
            cycle_global_id=decision.cycle_global_id,  # type: ignore[union-attr]
            cycle_number=decision.cycle_number,  # type: ignore[union-attr]
            outcome=decision.outcome,  # type: ignore[union-attr]
            actor_user_id=decision.actor_user_id,  # type: ignore[union-attr]
            occurred_at=decision.occurred_at,  # type: ignore[union-attr]
            policy_global_id=UUID(int=98),
            policy_version=decision.policy_version,  # type: ignore[union-attr]
            policy_hash=decision.policy_hash,  # type: ignore[union-attr]
            input_snapshot=decision.input_snapshot,  # type: ignore[union-attr]
            review_hashes=decision.review_hashes,  # type: ignore[union-attr]
            exception_hashes=decision.exception_hashes,  # type: ignore[union-attr]
            cycle_version=decision.cycle_version,  # type: ignore[union-attr]
        )
        with self.assertRaises(RequestValidationFailed):
            replace(decided, decision=wrong_policy_decision)

        exception_snapshot = input_snapshot(p1_complete=False)
        exception_cycle = approve_all(cycle(exception_snapshot)).request_exception(
            exception_global_id=EXCEPTION_ID,
            requester_member_global_id=REQUESTER_MEMBER_ID,
            actor_user_id="requester@example.test",
            kind="p1_evidence_timing",
            requirement_key="supplier_timing",
            reason="Controlled exception request.",
            risk="Controlled residual risk.",
            closure_action_ref=ACTION_REF,
            closure_action_kind="action",
            requested_at=NOW,
            expires_at=NOW + timedelta(days=1),
            expected_version=4,
            expected_input_hash=exception_snapshot.snapshot_hash,
        )
        with self.assertRaises(RequestValidationFailed):
            replace(
                exception_cycle,
                exceptions=(replace(exception_cycle.exceptions[0], kind="unknown"),),
            )

        changed = input_snapshot(dependency_hash="d" * 64, gate_version=2)
        transition = decided.reopen(
            actor_user_id="reopen@example.test",
            reason="Controlled review restart.",
            occurred_at=NOW + timedelta(hours=1),
            current_input=changed,
            current_bindings=bindings(),
            gate_current_cycle_global_id=decided.global_id,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
        )
        mismatched_event = type(transition.event).build(
            kind=ReviewEventKind.INVALIDATED,
            gate_global_id=transition.event.gate_global_id,
            project_global_id=transition.event.project_global_id,
            old_cycle_global_id=transition.event.old_cycle_global_id,
            new_cycle_global_id=transition.event.new_cycle_global_id,
            old_input_hash=transition.event.old_input_hash,
            new_input_hash=transition.event.new_input_hash,
            prior_decision_snapshot_global_id=(
                transition.event.prior_decision_snapshot_global_id
            ),
            prior_decision_hash=transition.event.prior_decision_hash,
            actor_user_id=transition.event.actor_user_id,
            initiated_by_user_id=transition.event.initiated_by_user_id,
            reason=transition.event.reason,
            occurred_at=transition.event.occurred_at,
        )
        with self.assertRaises(RequestValidationFailed):
            replace(transition, event=mismatched_event)

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


class GateReviewValidationTest(unittest.TestCase):
    def test_input_snapshot_is_canonical_and_identity_complete(self) -> None:
        value = input_snapshot()
        reordered = replace(
            value,
            requirements=tuple(reversed(value.requirements)),
            dependencies=tuple(reversed(value.dependencies)),
        )
        self.assertEqual(value.snapshot_hash, reordered.snapshot_hash)
        changed = replace(
            value,
            dependencies=(replace(value.dependencies[0], version=6),),
        )
        self.assertNotEqual(value.snapshot_hash, changed.snapshot_hash)
        canonical = value.canonical_dict()
        self.assertEqual(canonical["gateVersion"], 1)
        self.assertEqual(
            canonical["requirements"][0]["globalId"],
            str(REQUIREMENT_P0_ID),
        )
        self.assertEqual(
            canonical["dependencies"][0]["snapshotHash"],
            "e" * 64,
        )

    def test_invalid_enum_bool_int_uuid_hash_datetime_and_state_are_rejected(
        self,
    ) -> None:
        with self.assertRaises(RequestValidationFailed):
            ReviewStep("review", True, "reviewer")
        with self.assertRaises(RequestValidationFailed):
            ReviewStep("review", 1, "reviewer", "always")  # type: ignore[arg-type]
        with self.assertRaises(RequestValidationFailed):
            replace(input_snapshot().requirements[0], evidence_complete=1)
        with self.assertRaises(RequestValidationFailed):
            AuthorityBinding(
                "reviewer",
                UUID(int=0),
                "reviewer@example.test",
                "Reviewer",
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                input_snapshot().dependencies[0],
                snapshot_hash="not-a-hash",
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                input_snapshot().dependencies[0],
                kind="gate_input_snapshot",  # type: ignore[arg-type]
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                input_snapshot(),
                requirements=input_snapshot().requirements * 129,
            )
        with self.assertRaises(RequestValidationFailed):
            replace(cycle(), state="decided")  # type: ignore[arg-type]
        with self.assertRaises(RequestValidationFailed):
            cycle().submit_review(
                step_key="engineering",
                actor_user_id="eng@example.test",
                outcome=ReviewOutcome.APPROVED,
                opinion="Naive time is not accepted.",
                occurred_at=datetime(2026, 7, 24),  # noqa: DTZ001
                expected_version=1,
                expected_input_hash=INPUT_HASH,
            )
        with self.assertRaises(RequestValidationFailed):
            ExceptionRule(
                "too_long",
                ("supplier_timing",),
                "exception_approver",
                3651,
                "action",
            )
        with self.assertRaises(RequestValidationFailed):
            ExceptionRule(
                "unknown_action",
                ("supplier_timing",),
                "exception_approver",
                14,
                "task",
            )


if __name__ == "__main__":
    unittest.main()
