from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import (  # noqa: E402
    RequestValidationFailed,
    VersionConflict,
)
from npi_core.project_controls.domain import (  # noqa: E402
    ControlPolicyPublicationState,
    FrozenProjectControlAuthority,
    HealthAggregationMode,
    HealthAggregationRule,
    HealthDimension,
    HealthDimensionRule,
    HealthMeasurement,
    HealthRuleMode,
    HealthStatus,
    PrerequisiteStatus,
    PriorPolicyVersionReference,
    ProjectControlAction,
    ProjectControlAuthorityRequired,
    ProjectControlBinding,
    ProjectControlPolicyMismatch,
    ProjectControlPolicyVersion,
    ProjectLifecycleState,
    ProjectPrerequisiteKey,
    ProjectTransitionBlocked,
    ProjectTransitionPrerequisiteUnavailable,
    ProjectTransitionRule,
    ProjectTransitionUnavailable,
    PublishedProjectControlPolicyImmutable,
    PublishedProjectControlPolicyRequired,
    evaluate_project_health,
    evaluate_project_transition,
)
from npi_core.project_controls.terminal_guard import (  # noqa: E402
    ProjectHistoryLocked,
    require_mutable_project,
)


POLICY_GLOBAL_ID = UUID("11111111-1111-4111-8111-111111111111")
PROJECT_GLOBAL_ID = UUID("22222222-2222-4222-8222-222222222222")
BINDING_GLOBAL_ID = UUID("33333333-3333-4333-8333-333333333333")
CONTROLLER_MEMBER_ID = UUID("44444444-4444-4444-8444-444444444444")
SPONSOR_MEMBER_ID = UUID("55555555-5555-4555-8555-555555555555")
OTHER_MEMBER_ID = UUID("66666666-6666-4666-8666-666666666666")

CONTROLLER_SLOT = "project_controller"
SPONSOR_SLOT = "project_sponsor"
CONTROLLER_USER = "controller@example.com"
SPONSOR_USER = "sponsor@example.com"

COMPLETE_PREREQUISITES = (
    ProjectPrerequisiteKey.OPEN_BLOCKERS,
    ProjectPrerequisiteKey.CONTROLLED_FILES,
    ProjectPrerequisiteKey.HANDOVER,
    ProjectPrerequisiteKey.COST,
)


class ProjectControlsDomainTest(unittest.TestCase):
    def test_terminal_project_history_rejects_every_legacy_mutation_guard(
        self,
    ) -> None:
        for state in ("cancelled", "completed"):
            with self.subTest(state=state), self.assertRaises(ProjectHistoryLocked):
                require_mutable_project(SimpleNamespace(lifecycle_state=state))
        for state in ("draft", "proposed", "active", "on_hold"):
            with self.subTest(state=state):
                require_mutable_project(SimpleNamespace(lifecycle_state=state))

    def health_rules(self) -> tuple[HealthDimensionRule, ...]:
        return (
            HealthDimensionRule(
                HealthDimension.PROGRESS,
                HealthRuleMode.HIGHER_IS_BETTER,
                green_threshold="80",
                yellow_threshold="60",
            ),
            HealthDimensionRule(
                HealthDimension.COST,
                HealthRuleMode.LOWER_IS_BETTER,
                green_threshold="100",
                yellow_threshold="120",
            ),
            HealthDimensionRule(
                HealthDimension.QUALITY,
                HealthRuleMode.MANUAL,
            ),
            HealthDimensionRule(
                HealthDimension.RISK,
                HealthRuleMode.UNAVAILABLE,
            ),
        )

    def transitions(self) -> tuple[ProjectTransitionRule, ...]:
        return (
            ProjectTransitionRule(
                ProjectLifecycleState.ACTIVE,
                ProjectControlAction.PAUSE,
                ProjectLifecycleState.ON_HOLD,
                CONTROLLER_SLOT,
                (),
            ),
            ProjectTransitionRule(
                ProjectLifecycleState.ACTIVE,
                ProjectControlAction.CANCEL,
                ProjectLifecycleState.CANCELLED,
                SPONSOR_SLOT,
                (ProjectPrerequisiteKey.OPEN_BLOCKERS,),
            ),
            ProjectTransitionRule(
                ProjectLifecycleState.ON_HOLD,
                ProjectControlAction.RESUME,
                ProjectLifecycleState.ACTIVE,
                CONTROLLER_SLOT,
                (),
            ),
            ProjectTransitionRule(
                ProjectLifecycleState.ACTIVE,
                ProjectControlAction.COMPLETE,
                ProjectLifecycleState.COMPLETED,
                CONTROLLER_SLOT,
                COMPLETE_PREREQUISITES,
            ),
        )

    def draft(
        self,
        *,
        policy_global_id: UUID = POLICY_GLOBAL_ID,
        policy_version: int = 1,
        authority_slots: tuple[str, ...] | None = None,
        health_assessment_slot: str = CONTROLLER_SLOT,
        health_rules: tuple[HealthDimensionRule, ...] | None = None,
        aggregation: HealthAggregationRule | None = None,
        transitions: tuple[ProjectTransitionRule, ...] | None = None,
        previous_version: ProjectControlPolicyVersion | None = None,
    ) -> ProjectControlPolicyVersion:
        return ProjectControlPolicyVersion.create_draft(
            policy_global_id=policy_global_id,
            policy_code="PROJECT-CONTROL",
            policy_version=policy_version,
            title="Synthetic Project control policy",
            authority_slots=(
                (CONTROLLER_SLOT, SPONSOR_SLOT)
                if authority_slots is None
                else authority_slots
            ),
            health_assessment_slot=health_assessment_slot,
            health_rules=(
                self.health_rules() if health_rules is None else health_rules
            ),
            aggregation=(
                HealthAggregationRule(
                    HealthAggregationMode.WORST_STATUS,
                    require_all=True,
                )
                if aggregation is None
                else aggregation
            ),
            transitions=(self.transitions() if transitions is None else transitions),
            previous_version=previous_version,
        )

    def snapshot(self, **changes):
        return self.draft(**changes).publish(expected_version=1).snapshot()

    def authorities(self) -> tuple[FrozenProjectControlAuthority, ...]:
        return (
            FrozenProjectControlAuthority(
                CONTROLLER_SLOT,
                CONTROLLER_MEMBER_ID,
                CONTROLLER_USER,
            ),
            FrozenProjectControlAuthority(
                SPONSOR_SLOT,
                SPONSOR_MEMBER_ID,
                SPONSOR_USER,
            ),
        )

    def binding(
        self,
        snapshot,
        *,
        authorities: tuple[FrozenProjectControlAuthority, ...] | None = None,
    ) -> ProjectControlBinding:
        return ProjectControlBinding.freeze(
            global_id=BINDING_GLOBAL_ID,
            tenant_id="tenant-a",
            project_global_id=PROJECT_GLOBAL_ID,
            policy=snapshot,
            authorities=(self.authorities() if authorities is None else authorities),
        )

    def green_measurements(self) -> tuple[HealthMeasurement, ...]:
        return (
            HealthMeasurement(
                HealthDimension.PROGRESS,
                numeric_value="80",
            ),
            HealthMeasurement(
                HealthDimension.COST,
                numeric_value="100",
            ),
            HealthMeasurement(
                HealthDimension.QUALITY,
                manual_status=HealthStatus.GREEN,
            ),
        )

    def complete_prerequisites(
        self,
        status: PrerequisiteStatus = PrerequisiteStatus.SATISFIED,
    ) -> dict[ProjectPrerequisiteKey, PrerequisiteStatus]:
        return {key: status for key in COMPLETE_PREREQUISITES}

    def test_published_policy_is_canonical_and_immutable(self) -> None:
        draft = self.draft()
        self.assertEqual(
            draft.publication_state,
            ControlPolicyPublicationState.DRAFT,
        )
        self.assertEqual(draft.policy_version, 1)
        self.assertEqual(draft.version, 1)

        published = draft.publish(expected_version=1)
        snapshot = published.snapshot()

        self.assertEqual(
            published.publication_state,
            ControlPolicyPublicationState.PUBLISHED,
        )
        self.assertEqual(published.version, 2)
        self.assertEqual(snapshot.snapshot_hash, published.snapshot_hash)
        self.assertEqual(len(snapshot.snapshot_hash), 64)
        self.assertEqual(
            snapshot.canonical_dict()["authoritySlots"],
            [CONTROLLER_SLOT, SPONSOR_SLOT],
        )
        self.assertEqual(
            [rule["dimension"] for rule in snapshot.canonical_dict()["healthRules"]],
            ["cost", "progress", "quality", "risk"],
        )

        with self.assertRaises(FrozenInstanceError):
            published.title = "Changed"  # type: ignore[misc]
        with self.assertRaises(PublishedProjectControlPolicyImmutable):
            published.edit_draft(expected_version=2, title="Changed")
        with self.assertRaises(PublishedProjectControlPolicyImmutable):
            published.publish(expected_version=2)
        with self.assertRaises(PublishedProjectControlPolicyRequired):
            draft.snapshot()
        with self.assertRaises(RequestValidationFailed):
            replace(snapshot, snapshot_hash="0" * 64)

    def test_canonical_hash_is_stable_across_input_order(self) -> None:
        first = self.snapshot()
        second = self.snapshot(
            authority_slots=(SPONSOR_SLOT, CONTROLLER_SLOT),
            health_rules=tuple(reversed(self.health_rules())),
            transitions=tuple(reversed(self.transitions())),
        )

        self.assertEqual(first.canonical_dict(), second.canonical_dict())
        self.assertEqual(first.snapshot_hash, second.snapshot_hash)

    def test_draft_edit_uses_optimistic_versioning(self) -> None:
        draft = self.draft()
        edited = draft.edit_draft(
            expected_version=1,
            title="Edited synthetic policy",
        )
        self.assertEqual(edited.version, 2)
        self.assertEqual(edited.title, "Edited synthetic policy")
        with self.assertRaises(VersionConflict):
            draft.edit_draft(expected_version=2, title="Stale")

    def test_policy_versions_are_contiguous_and_hash_chained(self) -> None:
        version_one = self.draft().publish(expected_version=1)
        version_two = version_one.next_draft(
            title="Synthetic Project control policy v2",
            authority_slots=(CONTROLLER_SLOT, SPONSOR_SLOT),
            health_assessment_slot=CONTROLLER_SLOT,
            health_rules=self.health_rules(),
            aggregation=HealthAggregationRule(
                HealthAggregationMode.WORST_STATUS,
                require_all=True,
            ),
            transitions=self.transitions(),
        )

        self.assertEqual(version_two.policy_version, 2)
        self.assertNotEqual(version_two.global_id, version_one.global_id)
        self.assertIsNotNone(version_two.prior_version_ref)
        assert version_two.prior_version_ref is not None
        self.assertEqual(
            version_two.prior_version_ref.global_id,
            version_one.global_id,
        )
        self.assertEqual(
            version_two.prior_version_ref.snapshot_hash,
            version_one.snapshot_hash,
        )

        with self.assertRaises(RequestValidationFailed):
            self.draft(policy_version=2)
        with self.assertRaises(RequestValidationFailed):
            self.draft(
                policy_version=3,
                previous_version=version_one,
            )
        with self.assertRaises(PublishedProjectControlPolicyRequired):
            self.draft(
                policy_version=2,
                previous_version=self.draft(),
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                version_two,
                prior_version_ref=PriorPolicyVersionReference(
                    OTHER_MEMBER_ID,
                    1,
                    "a" * 64,
                ),
            )

    def test_publish_requires_closed_dimensions_actions_and_slots(self) -> None:
        invalid_drafts = (
            self.draft(health_rules=self.health_rules()[:-1]),
            self.draft(transitions=self.transitions()[:-1]),
            self.draft(
                authority_slots=(),
                health_assessment_slot=CONTROLLER_SLOT,
            ),
            self.draft(health_assessment_slot="undeclared_slot"),
        )
        for draft in invalid_drafts:
            with self.subTest(draft=draft):
                with self.assertRaises(RequestValidationFailed):
                    draft.publish(expected_version=1)

    def test_complete_publication_requires_all_readiness_keys(self) -> None:
        incomplete = ProjectTransitionRule(
            ProjectLifecycleState.ACTIVE,
            ProjectControlAction.COMPLETE,
            ProjectLifecycleState.COMPLETED,
            CONTROLLER_SLOT,
            COMPLETE_PREREQUISITES[:-1],
        )
        transitions = tuple(
            incomplete if rule.action is ProjectControlAction.COMPLETE else rule
            for rule in self.transitions()
        )

        with self.assertRaises(RequestValidationFailed):
            self.draft(transitions=transitions).publish(expected_version=1)

    def test_transition_rule_rejects_invalid_action_shape(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ProjectTransitionRule(
                ProjectLifecycleState.ACTIVE,
                ProjectControlAction.PAUSE,
                ProjectLifecycleState.CANCELLED,
                CONTROLLER_SLOT,
                (),
            )
        with self.assertRaises(RequestValidationFailed):
            ProjectTransitionRule(
                ProjectLifecycleState.ACTIVE,
                ProjectControlAction.RESUME,
                ProjectLifecycleState.ACTIVE,
                CONTROLLER_SLOT,
                (),
            )
        with self.assertRaises(RequestValidationFailed):
            ProjectTransitionRule(
                ProjectLifecycleState.COMPLETED,
                ProjectControlAction.CANCEL,
                ProjectLifecycleState.CANCELLED,
                CONTROLLER_SLOT,
                (),
            )

    def test_binding_freezes_every_slot_exactly_once(self) -> None:
        snapshot = self.snapshot()
        binding = self.binding(snapshot)

        self.assertEqual(
            tuple(item.slot for item in binding.authorities),
            (CONTROLLER_SLOT, SPONSOR_SLOT),
        )
        self.assertEqual(binding.policy_snapshot_hash, snapshot.snapshot_hash)
        self.assertEqual(len(binding.snapshot_hash), 64)

        with self.assertRaises(RequestValidationFailed):
            self.binding(snapshot, authorities=self.authorities()[:-1])
        with self.assertRaises(RequestValidationFailed):
            self.binding(
                snapshot,
                authorities=(
                    self.authorities()[0],
                    self.authorities()[0],
                ),
            )
        malformed_binding = ProjectControlBinding(
            global_id=BINDING_GLOBAL_ID,
            tenant_id="tenant-a",
            project_global_id=PROJECT_GLOBAL_ID,
            policy_global_id=snapshot.policy_global_id,
            policy_version=snapshot.policy_version,
            policy_snapshot_hash=snapshot.snapshot_hash,
            authorities=self.authorities()[:-1],
        )
        with self.assertRaises(ProjectControlPolicyMismatch):
            malformed_binding.require_policy(snapshot)

    def test_binding_requires_exact_member_and_user_identity(self) -> None:
        snapshot = self.snapshot()
        binding = self.binding(snapshot)

        selected = binding.require_actor(
            CONTROLLER_SLOT,
            actor_member_global_id=CONTROLLER_MEMBER_ID,
            actor_user_id=CONTROLLER_USER.upper(),
        )
        self.assertEqual(selected.member_global_id, CONTROLLER_MEMBER_ID)

        with self.assertRaises(ProjectControlAuthorityRequired):
            binding.require_actor(
                CONTROLLER_SLOT,
                actor_member_global_id=OTHER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
            )
        with self.assertRaises(ProjectControlAuthorityRequired):
            binding.require_actor(
                CONTROLLER_SLOT,
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id="other@example.com",
            )

    def test_health_threshold_boundaries_and_threshold_validation(self) -> None:
        higher = self.health_rules()[0]
        lower = self.health_rules()[1]

        self.assertEqual(
            higher.evaluate(
                HealthMeasurement(HealthDimension.PROGRESS, numeric_value=80)
            ).status,
            HealthStatus.GREEN,
        )
        self.assertEqual(
            higher.evaluate(
                HealthMeasurement(HealthDimension.PROGRESS, numeric_value=60)
            ).status,
            HealthStatus.YELLOW,
        )
        self.assertEqual(
            higher.evaluate(
                HealthMeasurement(HealthDimension.PROGRESS, numeric_value=59)
            ).status,
            HealthStatus.RED,
        )
        self.assertEqual(
            lower.evaluate(
                HealthMeasurement(HealthDimension.COST, numeric_value=100)
            ).status,
            HealthStatus.GREEN,
        )
        self.assertEqual(
            lower.evaluate(
                HealthMeasurement(HealthDimension.COST, numeric_value=120)
            ).status,
            HealthStatus.YELLOW,
        )
        self.assertEqual(
            lower.evaluate(
                HealthMeasurement(HealthDimension.COST, numeric_value=121)
            ).status,
            HealthStatus.RED,
        )

        with self.assertRaises(RequestValidationFailed):
            HealthDimensionRule(
                HealthDimension.PROGRESS,
                HealthRuleMode.HIGHER_IS_BETTER,
                green_threshold=60,
                yellow_threshold=60,
            )
        with self.assertRaises(RequestValidationFailed):
            HealthDimensionRule(
                HealthDimension.COST,
                HealthRuleMode.LOWER_IS_BETTER,
                green_threshold=120,
                yellow_threshold=100,
            )
        with self.assertRaises(RequestValidationFailed):
            HealthDimensionRule(
                HealthDimension.RISK,
                HealthRuleMode.UNAVAILABLE,
                green_threshold=1,
            )

    def test_health_decimals_are_bounded_fixed_point_values(self) -> None:
        largest = HealthMeasurement(
            HealthDimension.PROGRESS,
            numeric_value=Decimal("1E+37"),
        )
        self.assertEqual(
            largest.canonical_dict()["numericValue"],
            "1" + ("0" * 37),
        )
        fractional = HealthMeasurement(
            HealthDimension.PROGRESS,
            numeric_value=Decimal("-0.0012300"),
        )
        self.assertEqual(
            fractional.canonical_dict()["numericValue"],
            "-0.00123",
        )

        invalid_values = (
            "1e3",
            "1e1000000",
            "+1",
            " 1",
            "1 ",
            "1" * 39,
            "0." + ("1" * 19),
            "9" * 10000,
            float("inf"),
            1e39,
        )
        for value in invalid_values:
            with self.subTest(value=str(value)[:80]):
                with self.assertRaises(RequestValidationFailed):
                    HealthMeasurement(
                        HealthDimension.PROGRESS,
                        numeric_value=value,
                    )

        with self.assertRaises(RequestValidationFailed):
            HealthDimensionRule(
                HealthDimension.PROGRESS,
                HealthRuleMode.HIGHER_IS_BETTER,
                green_threshold="1e3",
                yellow_threshold="900",
            )

    def test_require_all_keeps_unavailable_dimension_honest(self) -> None:
        snapshot = self.snapshot()
        result = evaluate_project_health(
            policy=snapshot,
            binding=self.binding(snapshot),
            actor_member_global_id=CONTROLLER_MEMBER_ID,
            actor_user_id=CONTROLLER_USER,
            measurements=self.green_measurements(),
        )

        self.assertEqual(result.overall_status, HealthStatus.UNAVAILABLE)
        self.assertEqual(
            {item.dimension: item.status for item in result.dimension_results}[
                HealthDimension.RISK
            ],
            HealthStatus.UNAVAILABLE,
        )

        with self.assertRaises(RequestValidationFailed):
            evaluate_project_health(
                policy=snapshot,
                binding=self.binding(snapshot),
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                measurements=(
                    *self.green_measurements(),
                    HealthMeasurement(
                        HealthDimension.RISK,
                        manual_status=HealthStatus.GREEN,
                    ),
                ),
            )

    def test_non_required_inputs_aggregate_worst_assessed_status(self) -> None:
        snapshot = self.snapshot(
            aggregation=HealthAggregationRule(
                HealthAggregationMode.WORST_STATUS,
                require_all=False,
            )
        )
        result = evaluate_project_health(
            policy=snapshot,
            binding=self.binding(snapshot),
            actor_member_global_id=CONTROLLER_MEMBER_ID,
            actor_user_id=CONTROLLER_USER,
            measurements=(
                HealthMeasurement(
                    HealthDimension.PROGRESS,
                    numeric_value=80,
                ),
                HealthMeasurement(
                    HealthDimension.COST,
                    numeric_value=100,
                ),
                HealthMeasurement(
                    HealthDimension.QUALITY,
                    manual_status=HealthStatus.YELLOW,
                ),
            ),
        )

        self.assertEqual(result.overall_status, HealthStatus.YELLOW)

    def test_any_red_dimension_requires_reason_and_recovery_plan(self) -> None:
        snapshot = self.snapshot()
        measurements = (
            *self.green_measurements()[:-1],
            HealthMeasurement(
                HealthDimension.QUALITY,
                manual_status=HealthStatus.RED,
            ),
        )

        with self.assertRaises(RequestValidationFailed) as caught:
            evaluate_project_health(
                policy=snapshot,
                binding=self.binding(snapshot),
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                measurements=measurements,
            )
        self.assertEqual(
            {item["path"] for item in caught.exception.field_errors},
            {"reason", "recoveryPlan"},
        )

        result = evaluate_project_health(
            policy=snapshot,
            binding=self.binding(snapshot),
            actor_member_global_id=CONTROLLER_MEMBER_ID,
            actor_user_id=CONTROLLER_USER,
            measurements=measurements,
            reason="Quality evidence failed.",
            recovery_plan="Repeat inspection before release.",
        )
        self.assertEqual(result.overall_status, HealthStatus.UNAVAILABLE)
        self.assertEqual(result.reason, "Quality evidence failed.")

    def test_health_evaluation_checks_policy_and_authority(self) -> None:
        version_one = self.draft().publish(expected_version=1)
        snapshot_one = version_one.snapshot()
        binding = self.binding(snapshot_one)

        with self.assertRaises(ProjectControlAuthorityRequired):
            evaluate_project_health(
                policy=snapshot_one,
                binding=binding,
                actor_member_global_id=OTHER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                measurements=self.green_measurements(),
            )

        version_two = version_one.next_draft(
            title="Synthetic Project control policy v2",
            authority_slots=(CONTROLLER_SLOT, SPONSOR_SLOT),
            health_assessment_slot=CONTROLLER_SLOT,
            health_rules=self.health_rules(),
            aggregation=HealthAggregationRule(
                HealthAggregationMode.WORST_STATUS,
                require_all=True,
            ),
            transitions=self.transitions(),
        ).publish(expected_version=1)
        with self.assertRaises(ProjectControlPolicyMismatch):
            evaluate_project_health(
                policy=version_two.snapshot(),
                binding=binding,
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                measurements=self.green_measurements(),
            )

    def test_policy_authorized_pause_and_resume_are_exact(self) -> None:
        snapshot = self.snapshot()
        binding = self.binding(snapshot)
        paused = evaluate_project_transition(
            policy=snapshot,
            binding=binding,
            current_state=ProjectLifecycleState.ACTIVE,
            action=ProjectControlAction.PAUSE,
            actor_member_global_id=CONTROLLER_MEMBER_ID,
            actor_user_id=CONTROLLER_USER,
            prerequisite_states={},
            reason="Waiting for the customer decision.",
            current_project_version=8,
            expected_project_version=8,
        )
        self.assertEqual(paused.target_state, ProjectLifecycleState.ON_HOLD)
        self.assertEqual(paused.project_version_after, 9)

        resumed = evaluate_project_transition(
            policy=snapshot,
            binding=binding,
            current_state=ProjectLifecycleState.ON_HOLD,
            action=ProjectControlAction.RESUME,
            actor_member_global_id=CONTROLLER_MEMBER_ID,
            actor_user_id=CONTROLLER_USER,
            prerequisite_states={},
            reason="The customer decision is available.",
            current_project_version=9,
            expected_project_version=9,
        )
        self.assertEqual(resumed.target_state, ProjectLifecycleState.ACTIVE)

    def test_transition_rejects_wrong_state_authority_and_version(self) -> None:
        snapshot = self.snapshot()
        binding = self.binding(snapshot)

        with self.assertRaises(ProjectTransitionUnavailable):
            evaluate_project_transition(
                policy=snapshot,
                binding=binding,
                current_state=ProjectLifecycleState.PROPOSED,
                action=ProjectControlAction.PAUSE,
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                prerequisite_states={},
                reason="Not available from this state.",
                current_project_version=1,
                expected_project_version=1,
            )
        with self.assertRaises(ProjectControlAuthorityRequired):
            evaluate_project_transition(
                policy=snapshot,
                binding=binding,
                current_state=ProjectLifecycleState.ACTIVE,
                action=ProjectControlAction.PAUSE,
                actor_member_global_id=OTHER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                prerequisite_states={},
                reason="Wrong authority.",
                current_project_version=1,
                expected_project_version=1,
            )
        with self.assertRaises(VersionConflict):
            evaluate_project_transition(
                policy=snapshot,
                binding=binding,
                current_state=ProjectLifecycleState.ACTIVE,
                action=ProjectControlAction.PAUSE,
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                prerequisite_states={},
                reason="Stale request.",
                current_project_version=2,
                expected_project_version=1,
            )
        with self.assertRaises(RequestValidationFailed):
            evaluate_project_transition(
                policy=snapshot,
                binding=binding,
                current_state=ProjectLifecycleState.ACTIVE,
                action=ProjectControlAction.PAUSE,
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                prerequisite_states={},
                reason=" ",
                current_project_version=1,
                expected_project_version=1,
            )

    def test_transition_requires_exact_server_prerequisite_set(self) -> None:
        snapshot = self.snapshot()
        binding = self.binding(snapshot)
        missing_cost = self.complete_prerequisites()
        del missing_cost[ProjectPrerequisiteKey.COST]

        with self.assertRaises(RequestValidationFailed):
            evaluate_project_transition(
                policy=snapshot,
                binding=binding,
                current_state=ProjectLifecycleState.ACTIVE,
                action=ProjectControlAction.COMPLETE,
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                prerequisite_states=missing_cost,
                reason="Attempt completion.",
                current_project_version=3,
                expected_project_version=3,
            )

    def test_complete_fails_closed_for_unavailable_or_blocked_input(self) -> None:
        snapshot = self.snapshot()
        binding = self.binding(snapshot)
        unavailable = self.complete_prerequisites()
        unavailable[ProjectPrerequisiteKey.HANDOVER] = PrerequisiteStatus.UNAVAILABLE
        blocked = self.complete_prerequisites()
        blocked[ProjectPrerequisiteKey.OPEN_BLOCKERS] = PrerequisiteStatus.BLOCKED

        with self.assertRaises(ProjectTransitionPrerequisiteUnavailable):
            evaluate_project_transition(
                policy=snapshot,
                binding=binding,
                current_state=ProjectLifecycleState.ACTIVE,
                action=ProjectControlAction.COMPLETE,
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                prerequisite_states=unavailable,
                reason="Attempt completion.",
                current_project_version=3,
                expected_project_version=3,
            )
        with self.assertRaises(ProjectTransitionBlocked):
            evaluate_project_transition(
                policy=snapshot,
                binding=binding,
                current_state=ProjectLifecycleState.ACTIVE,
                action=ProjectControlAction.COMPLETE,
                actor_member_global_id=CONTROLLER_MEMBER_ID,
                actor_user_id=CONTROLLER_USER,
                prerequisite_states=blocked,
                reason="Attempt completion.",
                current_project_version=3,
                expected_project_version=3,
            )

    def test_complete_succeeds_only_when_every_input_is_satisfied(self) -> None:
        snapshot = self.snapshot()
        decision = evaluate_project_transition(
            policy=snapshot,
            binding=self.binding(snapshot),
            current_state=ProjectLifecycleState.ACTIVE,
            action=ProjectControlAction.COMPLETE,
            actor_member_global_id=CONTROLLER_MEMBER_ID,
            actor_user_id=CONTROLLER_USER,
            prerequisite_states=self.complete_prerequisites(),
            reason="All controlled completion evidence is ready.",
            current_project_version=12,
            expected_project_version=12,
        )

        self.assertEqual(
            decision.target_state,
            ProjectLifecycleState.COMPLETED,
        )
        self.assertEqual(decision.project_version_after, 13)
        self.assertEqual(len(decision.decision_hash), 64)


if __name__ == "__main__":
    unittest.main()
