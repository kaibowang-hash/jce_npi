from __future__ import annotations

import hashlib
import json
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4


sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed, VersionConflict
from npi_core.project_work.domain import (
    DomainWorkItemKind,
    KindLifecycle,
    LifecycleDefinition,
    LifecycleState,
    PolicyPublicationState,
    ProjectMember,
    ProjectRaciAssignment,
    ProjectRoleAssignment,
    ProjectSubstitution,
    ProjectTeam,
    ProjectWorkPolicyVersion,
    PublishedWorkPolicyImmutable,
    RaciContextType,
    RaciResponsibility,
    Severity,
    WbsDependency,
    WbsItem,
    WbsPlan,
    capture_wbs_baseline,
    compare_wbs_baseline,
    create_domain_work_item,
)


POLICY_ID = UUID("3efde079-6179-48e6-a529-63929ea3f231")
PROJECT_ID = UUID("a7d4d6f6-2511-482e-824a-83a01743ce46")
OTHER_PROJECT_ID = UUID("5b294915-7e5f-4883-b3af-6f9ee3fa3b30")
TENANT_ID = "TENANT-A"
MEMBER_ID = UUID("9ddf3941-ffb3-4d04-8d9e-2611a0da757f")
SUBSTITUTE_ID = UUID("09655fb2-c3a0-4544-aa72-2a94d08f752b")
ROLE_ID = UUID("c71ade8a-98f2-42af-bf62-08ba698a74d6")
WBS_ROOT_ID = UUID("926980bc-e560-42f1-aab7-f87a62b72929")
WBS_CHILD_ID = UUID("a2daff59-3b08-4810-a50f-685793ad6ca8")
STAGE_ID = UUID("51f0a038-91f7-4a1a-9b9f-4fdbf585c709")


def lifecycle(
    initial_key: str,
    label: str,
    *,
    terminal_key: str | None = None,
) -> LifecycleDefinition:
    states = [LifecycleState(initial_key, label)]
    if terminal_key is not None:
        states.append(LifecycleState(terminal_key, "Draft", terminal=True))
    return LifecycleDefinition(initial_key, tuple(states))


def make_draft(
    *,
    include_all_kinds: bool = True,
) -> ProjectWorkPolicyVersion:
    lifecycles = (
        KindLifecycle(
            DomainWorkItemKind.RISK,
            lifecycle("identified", "Identified", terminal_key="retired"),
        ),
        KindLifecycle(
            DomainWorkItemKind.ISSUE,
            lifecycle("open", "Open", terminal_key="closed"),
        ),
        KindLifecycle(
            DomainWorkItemKind.ACTION,
            lifecycle("assigned", "Draft", terminal_key="closed"),
        ),
        KindLifecycle(
            DomainWorkItemKind.DECISION_REQUEST,
            lifecycle("requested", "Requested", terminal_key="decided"),
        ),
    )
    if not include_all_kinds:
        lifecycles = lifecycles[:-1]
    return ProjectWorkPolicyVersion.create_draft(
        policy_global_id=POLICY_ID,
        policy_key="synthetic_p4_work",
        policy_version=1,
        title="Synthetic P4 Work Policy",
        role_keys=("project_manager", "quality_engineer"),
        wbs_lifecycle=lifecycle(
            "not_started",
            "Not started",
            terminal_key="completed",
        ),
        work_item_lifecycles=lifecycles,
    )


def make_policy():
    return make_draft().publish(expected_version=1).snapshot()


def make_members() -> tuple[ProjectMember, ProjectMember]:
    return (
        ProjectMember(
            MEMBER_ID,
            TENANT_ID,
            PROJECT_ID,
            "owner@example.invalid",
            date(2026, 7, 1),
            date(2027, 12, 31),
        ),
        ProjectMember(
            SUBSTITUTE_ID,
            TENANT_ID,
            PROJECT_ID,
            "substitute@example.invalid",
            date(2026, 7, 1),
            date(2027, 12, 31),
        ),
    )


def make_role() -> ProjectRoleAssignment:
    return ProjectRoleAssignment(
        ROLE_ID,
        TENANT_ID,
        PROJECT_ID,
        MEMBER_ID,
        "project_manager",
        date(2026, 7, 1),
        date(2027, 12, 31),
    )


def make_team(
    *,
    raci_context_type: RaciContextType = RaciContextType.PROJECT,
    raci_context_id: UUID = PROJECT_ID,
) -> ProjectTeam:
    members = make_members()
    role = make_role()
    return ProjectTeam(
        tenant_id=TENANT_ID,
        project_global_id=PROJECT_ID,
        policy=make_policy(),
        members=members,
        role_assignments=(role,),
        substitutions=(
            ProjectSubstitution(
                uuid4(),
                TENANT_ID,
                PROJECT_ID,
                ROLE_ID,
                SUBSTITUTE_ID,
                date(2026, 8, 1),
                date(2026, 8, 31),
            ),
        ),
        raci_assignments=(
            ProjectRaciAssignment(
                uuid4(),
                TENANT_ID,
                PROJECT_ID,
                raci_context_type,
                raci_context_id,
                "project_delivery",
                ROLE_ID,
                RaciResponsibility.ACCOUNTABLE,
            ),
        ),
    )


def make_wbs_item(
    global_id: UUID,
    code: str,
    *,
    parent_id: UUID | None = None,
    project_id: UUID = PROJECT_ID,
    planned_start: date = date(2026, 8, 1),
    planned_finish: date = date(2026, 8, 5),
    status_key: str = "not_started",
    critical: bool = False,
) -> WbsItem:
    policy = make_policy()
    return WbsItem(
        global_id=global_id,
        tenant_id=TENANT_ID,
        project_global_id=project_id,
        work_policy_global_id=policy.policy_global_id,
        work_policy_version=policy.policy_version,
        work_policy_snapshot_hash=policy.snapshot_hash,
        code=code,
        title=f"Synthetic {code}",
        parent_global_id=parent_id,
        owner_role_assignment_global_id=ROLE_ID,
        planned_start=planned_start,
        planned_finish=planned_finish,
        actual_start=None,
        actual_finish=None,
        milestone=False,
        status_key=status_key,
        progress_percent=0,
        critical=critical,
        plan_revision=1,
    )


def make_plan(
    *,
    items: tuple[WbsItem, ...] | None = None,
    dependencies: tuple[WbsDependency, ...] = (),
    project_version: int = 4,
) -> WbsPlan:
    return WbsPlan(
        tenant_id=TENANT_ID,
        project_global_id=PROJECT_ID,
        project_version=project_version,
        policy=make_policy(),
        items=items
        or (
            make_wbs_item(WBS_ROOT_ID, "1"),
            make_wbs_item(WBS_CHILD_ID, "1.1", parent_id=WBS_ROOT_ID),
        ),
        dependencies=dependencies,
        role_assignments=(make_role(),),
    )


def make_bounded_wbs_items(
    count: int,
    *,
    parent_chain: bool,
) -> tuple[tuple[UUID, ...], tuple[WbsItem, ...]]:
    item_ids = tuple(UUID(int=100_000 + index) for index in range(count))
    template = make_wbs_item(item_ids[0], "WBS-0")
    items = tuple(
        replace(
            template,
            global_id=item_id,
            code=f"WBS-{index}",
            title=f"Synthetic bounded WBS item {index}",
            parent_global_id=(
                item_ids[index + 1]
                if parent_chain and index + 1 < count
                else None
            ),
        )
        for index, item_id in enumerate(item_ids)
    )
    return item_ids, items


def make_bounded_dependencies(
    item_ids: tuple[UUID, ...],
    *,
    count: int,
    terminal_cycle: bool,
) -> tuple[WbsDependency, ...]:
    acyclic_count = count - int(terminal_cycle)
    pairs = [
        (item_ids[index], item_ids[index + 1])
        for index in range(len(item_ids) - 1)
    ]
    distance = 2
    while len(pairs) < acyclic_count:
        for index in range(len(item_ids) - distance):
            pairs.append((item_ids[index], item_ids[index + distance]))
            if len(pairs) == acyclic_count:
                break
        distance += 1
    if terminal_cycle:
        pairs.append((item_ids[-1], item_ids[0]))
    return tuple(
        WbsDependency(
            UUID(int=1_000_000 + index),
            TENANT_ID,
            PROJECT_ID,
            predecessor_id,
            successor_id,
            1,
        )
        for index, (predecessor_id, successor_id) in enumerate(pairs)
    )


class ProjectWorkPolicyTest(unittest.TestCase):
    def test_published_policy_is_exact_immutable_and_versioned(self) -> None:
        draft = make_draft()
        published = draft.publish(expected_version=1)
        snapshot = published.snapshot()

        self.assertEqual(published.publication_state, PolicyPublicationState.PUBLISHED)
        self.assertEqual(published.version, 2)
        self.assertRegex(snapshot.snapshot_hash, r"^[a-f0-9]{64}$")
        self.assertEqual(snapshot.role_keys, ("project_manager", "quality_engineer"))
        self.assertEqual(
            snapshot.lifecycle_for(DomainWorkItemKind.RISK).initial_state_key,
            "identified",
        )
        self.assertEqual(
            snapshot.lifecycle_for(DomainWorkItemKind.DECISION_REQUEST).initial_state_key,
            "requested",
        )
        with self.assertRaises(PublishedWorkPolicyImmutable):
            published.edit_draft(expected_version=2, title="Changed")
        with self.assertRaises(PublishedWorkPolicyImmutable):
            published.publish(expected_version=2)
        with self.assertRaises(FrozenInstanceError):
            published.title = "Changed"  # type: ignore[misc]

        next_draft = published.next_draft()
        self.assertEqual(next_draft.policy_version, 2)
        self.assertNotEqual(next_draft.global_id, published.global_id)
        self.assertEqual(next_draft.publication_state, PolicyPublicationState.DRAFT)

    def test_policy_publish_requires_roles_and_four_distinct_kind_lifecycles(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            make_draft(include_all_kinds=False).publish(expected_version=1)
        with self.assertRaises(RequestValidationFailed):
            replace(make_draft(), role_keys=()).publish(expected_version=1)
        with self.assertRaises(RequestValidationFailed):
            replace(
                make_draft(),
                work_item_lifecycles=(
                    KindLifecycle(
                        DomainWorkItemKind.RISK,
                        lifecycle("identified", "Identified"),
                    ),
                    KindLifecycle(
                        DomainWorkItemKind.RISK,
                        lifecycle("other", "Other"),
                    ),
                ),
            )

    def test_policy_uses_optimistic_concurrency(self) -> None:
        with self.assertRaises(VersionConflict):
            make_draft().edit_draft(expected_version=2, title="Conflict")


class ProjectTeamTest(unittest.TestCase):
    def test_team_dates_roles_substitution_and_raci_are_explicit(self) -> None:
        team = make_team()
        team.validate_contexts()

        self.assertEqual(team.role_assignments[0].role_key, "project_manager")
        self.assertEqual(
            team.raci_assignments[0].responsibility,
            RaciResponsibility.ACCOUNTABLE,
        )
        self.assertNotIn(
            "approve",
            {responsibility.value for responsibility in RaciResponsibility},
        )

    def test_team_rejects_unknown_roles_cross_project_and_bad_effectivity(self) -> None:
        role = replace(make_role(), role_key="not_in_policy")
        with self.assertRaises(RequestValidationFailed):
            replace(make_team(), role_assignments=(role,))

        cross_project_member = replace(
            make_members()[0],
            project_global_id=OTHER_PROJECT_ID,
        )
        with self.assertRaises(RequestValidationFailed):
            replace(make_team(), members=(cross_project_member, make_members()[1]))

        outside_role = replace(
            make_role(),
            effective_from=date(2026, 6, 30),
        )
        with self.assertRaises(RequestValidationFailed):
            replace(make_team(), role_assignments=(outside_role,))

    def test_team_rejects_self_overlapping_or_out_of_range_substitution(self) -> None:
        self_substitution = replace(
            make_team().substitutions[0],
            substitute_member_global_id=MEMBER_ID,
        )
        with self.assertRaises(RequestValidationFailed):
            replace(make_team(), substitutions=(self_substitution,))

        first = make_team().substitutions[0]
        overlapping = replace(
            first,
            global_id=uuid4(),
            effective_from=date(2026, 8, 15),
            effective_to=date(2026, 9, 15),
        )
        with self.assertRaises(RequestValidationFailed):
            replace(make_team(), substitutions=(first, overlapping))

        outside = replace(
            first,
            effective_to=date(2028, 1, 1),
        )
        with self.assertRaises(RequestValidationFailed):
            replace(make_team(), substitutions=(outside,))

    def test_raci_context_is_fail_closed_against_known_project_objects(self) -> None:
        team = make_team(
            raci_context_type=RaciContextType.WBS_ITEM,
            raci_context_id=WBS_CHILD_ID,
        )
        team.validate_contexts(wbs_item_ids=frozenset({WBS_CHILD_ID}))
        with self.assertRaises(RequestValidationFailed):
            team.validate_contexts(wbs_item_ids=frozenset())


class WbsDomainTest(unittest.TestCase):
    def test_valid_plan_preserves_parent_dependency_owner_and_manual_criticality(self) -> None:
        dependency = WbsDependency(
            uuid4(),
            TENANT_ID,
            PROJECT_ID,
            WBS_ROOT_ID,
            WBS_CHILD_ID,
            1,
        )
        plan = make_plan(
            items=(
                make_wbs_item(WBS_ROOT_ID, "1", critical=True),
                make_wbs_item(WBS_CHILD_ID, "1.1", parent_id=WBS_ROOT_ID),
            ),
            dependencies=(dependency,),
        )
        self.assertTrue(plan.items[0].critical)
        self.assertEqual(plan.items[1].parent_global_id, WBS_ROOT_ID)
        self.assertEqual(plan.dependencies[0].predecessor_global_id, WBS_ROOT_ID)

    def test_parent_and_dependency_cycles_are_rejected_independently(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            make_plan(
                items=(
                    make_wbs_item(WBS_ROOT_ID, "1", parent_id=WBS_CHILD_ID),
                    make_wbs_item(WBS_CHILD_ID, "1.1", parent_id=WBS_ROOT_ID),
                )
            )

        first = WbsDependency(
            uuid4(),
            TENANT_ID,
            PROJECT_ID,
            WBS_ROOT_ID,
            WBS_CHILD_ID,
            1,
        )
        second = WbsDependency(
            uuid4(),
            TENANT_ID,
            PROJECT_ID,
            WBS_CHILD_ID,
            WBS_ROOT_ID,
            1,
        )
        with self.assertRaises(RequestValidationFailed):
            make_plan(dependencies=(first, second))

    def test_iterative_parent_validation_accepts_2000_item_chain(self) -> None:
        _item_ids, items = make_bounded_wbs_items(
            2_000,
            parent_chain=True,
        )

        plan = make_plan(items=items)

        self.assertEqual(len(plan.items), 2_000)

    def test_iterative_parent_validation_rejects_terminal_cycle_at_2000_items(
        self,
    ) -> None:
        item_ids, items = make_bounded_wbs_items(
            2_000,
            parent_chain=True,
        )
        terminal_cycle = items[:-1] + (
            replace(items[-1], parent_global_id=item_ids[-2]),
        )

        with self.assertRaises(RequestValidationFailed) as caught:
            make_plan(items=terminal_cycle)

        self.assertEqual(
            caught.exception.field_errors,
            [
                {
                    "path": "items.parentId",
                    "message": "The WBS graph cannot contain a cycle.",
                }
            ],
        )

    def test_iterative_dependency_validation_rejects_terminal_cycle_at_5000_edges(
        self,
    ) -> None:
        item_ids, items = make_bounded_wbs_items(
            2_000,
            parent_chain=False,
        )
        dependencies = make_bounded_dependencies(
            item_ids,
            count=5_000,
            terminal_cycle=True,
        )

        with self.assertRaises(RequestValidationFailed) as caught:
            make_plan(items=items, dependencies=dependencies)

        self.assertEqual(
            caught.exception.field_errors,
            [
                {
                    "path": "dependencies",
                    "message": "The WBS graph cannot contain a cycle.",
                }
            ],
        )

    def test_cross_project_missing_owner_and_unknown_policy_status_fail(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            make_plan(
                items=(
                    make_wbs_item(
                        WBS_ROOT_ID,
                        "1",
                        project_id=OTHER_PROJECT_ID,
                    ),
                )
            )
        with self.assertRaises(RequestValidationFailed):
            make_plan(
                items=(
                    replace(
                        make_wbs_item(WBS_ROOT_ID, "1"),
                        owner_role_assignment_global_id=uuid4(),
                    ),
                )
            )
        with self.assertRaises(RequestValidationFailed):
            make_plan(
                items=(
                    make_wbs_item(WBS_ROOT_ID, "1", status_key="invented"),
                )
            )

    def test_dates_milestone_progress_and_duplicates_are_strict(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            make_wbs_item(
                WBS_ROOT_ID,
                "1",
                planned_start=date(2026, 8, 5),
                planned_finish=date(2026, 8, 1),
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                make_wbs_item(WBS_ROOT_ID, "1"),
                milestone=True,
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                make_wbs_item(WBS_ROOT_ID, "1"),
                progress_percent=101,
            )
        with self.assertRaises(RequestValidationFailed):
            make_plan(
                items=(
                    make_wbs_item(WBS_ROOT_ID, "WBS-1"),
                    make_wbs_item(WBS_CHILD_ID, "wbs-1"),
                )
            )

    def test_immutable_baseline_hash_and_variance_are_exact(self) -> None:
        plan = make_plan()
        baseline = capture_wbs_baseline(
            plan,
            global_id=uuid4(),
            label="Synthetic plan baseline",
            captured_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
            captured_by="Administrator",
        )
        self.assertEqual(baseline.captured_by, "Administrator")
        for invalid_actor in (
            "",
            "Admin User",
            "Administrator\n",
            "a" * 255,
        ):
            with self.subTest(invalid_actor=repr(invalid_actor)):
                with self.assertRaises(RequestValidationFailed):
                    replace(baseline, captured_by=invalid_actor)
        shifted = make_plan(
            project_version=5,
            items=(
                make_wbs_item(
                    WBS_ROOT_ID,
                    "1",
                    planned_start=date(2026, 8, 3),
                    planned_finish=date(2026, 8, 9),
                ),
                make_wbs_item(
                    WBS_CHILD_ID,
                    "1.1",
                    parent_id=WBS_ROOT_ID,
                    planned_start=date(2026, 8, 2),
                    planned_finish=date(2026, 8, 6),
                    critical=True,
                ),
            ),
        )
        comparison = compare_wbs_baseline(baseline, shifted)
        root_comparison = next(
            item
            for item in comparison.items
            if item.wbs_item_global_id == WBS_ROOT_ID
        )
        self.assertEqual(root_comparison.start_variance_days, 2)
        self.assertEqual(root_comparison.finish_variance_days, 4)
        self.assertEqual(comparison.baseline_project_version, 4)
        self.assertEqual(comparison.current_project_version, 5)
        self.assertRegex(baseline.snapshot_hash, r"^[a-f0-9]{64}$")
        self.assertEqual(
            baseline.snapshot_hash,
            hashlib.sha256(
                json.dumps(
                    baseline.snapshot_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest(),
        )
        with self.assertRaises(FrozenInstanceError):
            baseline.label = "Changed"  # type: ignore[misc]
        with self.assertRaises(RequestValidationFailed):
            replace(baseline, snapshot_hash="0" * 64)


class DomainWorkItemTest(unittest.TestCase):
    def create_item(
        self,
        kind: DomainWorkItemKind,
        *,
        global_id: UUID | None = None,
        related_ids: tuple[UUID, ...] = (),
        related_items=(),
    ):
        return create_domain_work_item(
            global_id=global_id or uuid4(),
            tenant_id=TENANT_ID,
            project_global_id=PROJECT_ID,
            policy=make_policy(),
            kind=kind,
            title=f"Synthetic {kind.value}",
            detail="Synthetic detail",
            stage_global_id=STAGE_ID,
            wbs_item_global_id=WBS_CHILD_ID,
            known_stage_ids=frozenset({STAGE_ID}),
            known_wbs_item_ids=frozenset({WBS_CHILD_ID}),
            owner_user_id="owner@example.invalid",
            due_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
            severity=Severity.HIGH,
            blocking=True,
            related_work_item_ids=related_ids,
            related_items=related_items,
        )

    def test_each_kind_dispatches_to_its_own_policy_initial_state(self) -> None:
        expected = {
            DomainWorkItemKind.RISK: "identified",
            DomainWorkItemKind.ISSUE: "open",
            DomainWorkItemKind.ACTION: "assigned",
            DomainWorkItemKind.DECISION_REQUEST: "requested",
        }
        for kind, state_key in expected.items():
            with self.subTest(kind=kind):
                item = self.create_item(kind)
                self.assertEqual(item.state_key, state_key)
                self.assertFalse(item.state_terminal)
                self.assertEqual(item.kind, kind)
                self.assertEqual(item.work_policy_snapshot_hash, make_policy().snapshot_hash)

    def test_shared_context_owner_due_severity_blocking_and_relations_are_validated(self) -> None:
        issue = self.create_item(DomainWorkItemKind.ISSUE)
        action = self.create_item(
            DomainWorkItemKind.ACTION,
            related_ids=(issue.global_id,),
            related_items=(issue,),
        )
        self.assertEqual(action.related_work_item_ids, (issue.global_id,))
        self.assertEqual(action.stage_global_id, STAGE_ID)
        self.assertEqual(action.wbs_item_global_id, WBS_CHILD_ID)
        self.assertEqual(action.owner_user_id, "owner@example.invalid")
        self.assertEqual(action.severity, Severity.HIGH)
        self.assertTrue(action.blocking)

        foreign = replace(issue, project_global_id=OTHER_PROJECT_ID)
        with self.assertRaises(RequestValidationFailed):
            self.create_item(
                DomainWorkItemKind.ACTION,
                related_ids=(foreign.global_id,),
                related_items=(foreign,),
            )
        with self.assertRaises(RequestValidationFailed):
            create_domain_work_item(
                global_id=uuid4(),
                tenant_id=TENANT_ID,
                project_global_id=PROJECT_ID,
                policy=make_policy(),
                kind=DomainWorkItemKind.RISK,
                title="Invalid context",
                stage_global_id=uuid4(),
                known_stage_ids=frozenset({STAGE_ID}),
                owner_user_id="owner@example.invalid",
                due_at=datetime.now(UTC),
                severity=Severity.LOW,
                blocking=False,
            )

    def test_overdue_uses_exact_policy_terminal_state_and_aware_server_time(self) -> None:
        item = self.create_item(DomainWorkItemKind.RISK)
        self.assertTrue(
            item.is_overdue(
                as_of=item.due_at + timedelta(seconds=1),
            )
        )
        terminal = replace(item, state_key="retired", state_terminal=True)
        self.assertFalse(
            terminal.is_overdue(
                as_of=item.due_at + timedelta(days=1),
            )
        )
        with self.assertRaises(RequestValidationFailed):
            item.is_overdue(as_of=datetime(2026, 8, 2, 12, 0))

    def test_state_is_not_caller_supplied_and_p4_03_evidence_is_fail_closed(self) -> None:
        item = self.create_item(DomainWorkItemKind.DECISION_REQUEST)
        self.assertEqual(item.state_key, "requested")
        with self.assertRaises(RequestValidationFailed):
            replace(item, evidence_references=(uuid4(),))
        self.assertFalse(hasattr(item, "transition"))


if __name__ == "__main__":
    unittest.main()
