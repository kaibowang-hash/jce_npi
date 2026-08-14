from __future__ import annotations

import copy
import inspect
import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid5

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.production_transition import domain as production_transition_domain
from npi_core.production_transition.domain import (
    AcknowledgementDirection,
    AcknowledgementSlotDefinition,
    ExactVersionReference,
    FrozenAcknowledgementSlot,
    HandoverObjectRequirement,
    HandoverSourceKind,
    HandoverSourceReference,
    MANDATORY_OBSERVATION_PROVIDER_KINDS,
    MetricComparator,
    ObservationProviderKind,
    ObservationReferenceUsage,
    ObservationSourceReference,
    ObservationSourceRule,
    PolicyPublicationState,
    ProductionTransitionApplicability,
    ProductionTransitionPolicyImmutable,
    ProductionTransitionPolicyPublishedRequired,
    ProductionTransitionPolicyVersion,
    ProductionTransitionVersionConflict,
    ProjectMemberSnapshot,
    ProjectRoleSnapshot,
    ProjectTransitionSnapshot,
    ReceivingGroupDefinition,
    TechnicalDisposition,
    UnresolvedActionSnapshot,
    WorkItemKind,
    acknowledgement_from_snapshot,
    create_handover_acknowledgement,
    create_handover_package_revision,
    create_handover_package_successor,
    create_observation_period_revision,
    create_observation_period_successor,
    derive_fully_acknowledged,
    handover_package_from_snapshot,
    observation_from_snapshot,
    policy_from_snapshot,
    unavailable_observation_providers,
    validate_handover_successor,
    validate_observation_successor,
    validate_policy_persistence_transition,
)
from npi_core.project.domain import ProjectType


def uid(value: int) -> UUID:
    return UUID(int=value)


NOW = datetime(2026, 8, 14, 8, 30, tzinfo=UTC)
TENANT = "tenant-a"
PROJECT_ID = uid(10)


def exact(value: int, version: int = 1, digit: str = "a") -> ExactVersionReference:
    return ExactVersionReference(uid(value), version, digit * 64)


def project() -> ProjectTransitionSnapshot:
    return ProjectTransitionSnapshot(
        global_id=PROJECT_ID,
        tenant_id=TENANT,
        optimistic_version=7,
        business_code="NPI-2026-001",
        title="Synthetic production transition",
        project_type=ProjectType.NEW_TOOL,
        owner_user_id="owner@example.invalid",
        target_sop_date=date(2026, 9, 1),
        lifecycle_state="active",
        template_ref=exact(11, 3, "b"),
        work_policy_ref=exact(12, 2, "c"),
        customer_reference_keys=("ERPNEXT:CUST-001",),
    )


def source_rules() -> tuple[ObservationSourceRule, ...]:
    rules = []
    for kind in MANDATORY_OBSERVATION_PROVIDER_KINDS:
        if kind is ObservationProviderKind.ACTUAL_SOP:
            rules.append(
                ObservationSourceRule(
                    provider_kind=kind,
                    allowed_dispositions=(TechnicalDisposition.NOT_EVALUABLE,),
                )
            )
        else:
            rules.append(
                ObservationSourceRule(
                    provider_kind=kind,
                    unit="percent" if kind is ObservationProviderKind.FIRST_BATCH_YIELD else "count",
                    comparator=MetricComparator.LESS_THAN_OR_EQUAL,
                    threshold=Decimal("1.5"),
                    allowed_dispositions=(
                        TechnicalDisposition.NOT_EVALUABLE,
                        TechnicalDisposition.WITHIN_RULE,
                        TechnicalDisposition.OUTSIDE_RULE,
                    ),
                )
            )
    return tuple(rules)


def draft_policy() -> ProductionTransitionPolicyVersion:
    return ProductionTransitionPolicyVersion.create_draft(
        policy_global_id=uid(20),
        tenant_id=TENANT,
        policy_code="PROD-TRANSITION",
        title="Synthetic production transition policy",
        applicability=ProductionTransitionApplicability((ProjectType.NEW_TOOL,)),
        receiving_groups=(
            ReceivingGroupDefinition("npi_sender", "NPI sender group"),
            ReceivingGroupDefinition("production_receiver", "Production receiving group"),
        ),
        acknowledgement_slots=(
            AcknowledgementSlotDefinition(
                "sender",
                "npi_sender",
                AcknowledgementDirection.SENDER,
                ("npi_owner",),
            ),
            AcknowledgementSlotDefinition(
                "receiver",
                "production_receiver",
                AcknowledgementDirection.RECEIVER,
                ("production_receiver",),
            ),
        ),
        handover_requirements=(
            HandoverObjectRequirement(
                "open_work",
                (HandoverSourceKind.DOMAIN_WORK_ITEM,),
                "unresolved_action",
            ),
        ),
        observation_source_rules=source_rules(),
        observation_window_days=30,
        changed_by_user_id="admin@example.invalid",
        changed_at=NOW,
        request_id=uid(21),
        trace_id="trace-p706-policy-draft",
    )


def policy() -> ProductionTransitionPolicyVersion:
    return draft_policy().publish(
        expected_version=1,
        changed_by_user_id="publisher@example.invalid",
        changed_at=NOW,
        request_id=uid(22),
        trace_id="trace-p706-policy-publish",
    )


def member(value: int, user_id: str) -> ProjectMemberSnapshot:
    return ProjectMemberSnapshot(
        global_id=uid(value),
        tenant_id=TENANT,
        project_global_id=PROJECT_ID,
        user_id=user_id,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        optimistic_version=2,
    )


def role(value: int, member_value: ProjectMemberSnapshot, key: str) -> ProjectRoleSnapshot:
    return ProjectRoleSnapshot(
        global_id=uid(value),
        tenant_id=TENANT,
        project_global_id=PROJECT_ID,
        member_global_id=member_value.global_id,
        role_key=key,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        optimistic_version=3,
    )


SENDER_MEMBER = member(30, "sender@example.invalid")
RECEIVER_MEMBER = member(31, "receiver@example.invalid")
SENDER_ROLE = role(32, SENDER_MEMBER, "npi_owner")
RECEIVER_ROLE = role(33, RECEIVER_MEMBER, "production_receiver")


def slots() -> tuple[FrozenAcknowledgementSlot, ...]:
    return (
        FrozenAcknowledgementSlot(
            "sender",
            "npi_sender",
            AcknowledgementDirection.SENDER,
            SENDER_MEMBER,
            SENDER_ROLE,
        ),
        FrozenAcknowledgementSlot(
            "receiver",
            "production_receiver",
            AcknowledgementDirection.RECEIVER,
            RECEIVER_MEMBER,
            RECEIVER_ROLE,
        ),
    )


SOURCE = HandoverSourceReference(
    requirement_key="open_work",
    kind=HandoverSourceKind.DOMAIN_WORK_ITEM,
    global_id=uid(40),
    source_version=4,
    snapshot_hash="d" * 64,
    role="unresolved_action",
)


CONTEXT_SOURCE = ObservationSourceReference(
    kind=HandoverSourceKind.DOMAIN_WORK_ITEM,
    global_id=SOURCE.global_id,
    source_version=SOURCE.source_version,
    snapshot_hash=SOURCE.snapshot_hash,
    usage=ObservationReferenceUsage.CONTEXT,
)


RETROSPECTIVE_SOURCE = ObservationSourceReference(
    kind=HandoverSourceKind.DOMAIN_WORK_ITEM,
    global_id=SOURCE.global_id,
    source_version=SOURCE.source_version,
    snapshot_hash=SOURCE.snapshot_hash,
    usage=ObservationReferenceUsage.RETROSPECTIVE,
)


ACTION = UnresolvedActionSnapshot(
    global_id=uid(40),
    source_version=4,
    snapshot_hash="d" * 64,
    kind=WorkItemKind.ACTION,
    state="open",
    owner_user_id="owner@example.invalid",
    due_date=date(2026, 9, 10),
)


def package():
    return create_handover_package_revision(
        handover_global_id=uid(50),
        tenant_id=TENANT,
        project=project(),
        policy=policy(),
        readiness_ref=None,
        slots=slots(),
        manifest=(SOURCE,),
        server_unresolved_actions=(ACTION,),
        enabled_user_ids=frozenset({SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}),
        reason="Freeze the exact technical handover package.",
        created_by_user_id="admin@example.invalid",
        created_at=NOW,
        request_id=uid(51),
        trace_id="trace-p706-package",
    )


class Phase7ProductionTransitionDomainTest(unittest.TestCase):
    def test_domain_keeps_the_standard_independent_test_translation_fallback(self) -> None:
        source = inspect.getsource(production_transition_domain)
        self.assertIn("from frappe import _", source)
        self.assertIn("except ImportError", source)

    def test_policy_draft_publish_next_version_and_round_trip(self) -> None:
        draft = draft_policy()
        self.assertEqual(draft.tenant_id, TENANT)
        self.assertEqual(draft.snapshot_payload()["tenantId"], TENANT)
        edited = draft.edit_draft(
            expected_version=1,
            title="Edited title",
            changed_by_user_id="editor@example.invalid",
            changed_at=NOW,
            request_id=uid(23),
            trace_id="trace-p706-policy-edit",
        )
        self.assertEqual(edited.optimistic_version, 2)
        self.assertEqual(edited.changed_by_user_id, "editor@example.invalid")
        with self.assertRaises(ProductionTransitionVersionConflict):
            edited.edit_draft(
                expected_version=1,
                title="Stale",
                changed_by_user_id="editor@example.invalid",
                changed_at=NOW,
                request_id=uid(24),
                trace_id="trace-p706-policy-stale",
            )
        published = edited.publish(
            expected_version=2,
            changed_by_user_id="publisher@example.invalid",
            changed_at=NOW,
            request_id=uid(25),
            trace_id="trace-p706-policy-publish-edited",
        )
        self.assertEqual(published.publication_state, PolicyPublicationState.PUBLISHED)
        self.assertEqual(policy_from_snapshot(published.snapshot_payload()), published)
        with self.assertRaises(ProductionTransitionPolicyImmutable):
            published.edit_draft(
                expected_version=3,
                title="Changed",
                changed_by_user_id="editor@example.invalid",
                changed_at=NOW,
                request_id=uid(26),
                trace_id="trace-p706-policy-immutable",
            )
        successor = published.next_draft(
            changed_by_user_id="editor@example.invalid",
            changed_at=NOW,
            request_id=uid(27),
            trace_id="trace-p706-policy-next",
        )
        self.assertEqual(successor.policy_version, 2)
        self.assertEqual(successor.tenant_id, TENANT)
        self.assertEqual(successor.prior_version_ref.snapshot_hash, published.snapshot_hash)
        with self.assertRaises(ProductionTransitionPolicyPublishedRequired):
            successor.next_draft(
                changed_by_user_id="editor@example.invalid",
                changed_at=NOW,
                request_id=uid(28),
                trace_id="trace-p706-policy-invalid-next",
            )

    def test_policy_tenant_is_canonical_and_cannot_cross_project_boundary(self) -> None:
        published = policy()
        tampered = copy.deepcopy(published.snapshot_payload())
        tampered["tenantId"] = "tenant-b"
        with self.assertRaises(RequestValidationFailed):
            policy_from_snapshot(tampered)

        other_tenant_policy = replace(published, tenant_id="tenant-b")
        self.assertNotEqual(other_tenant_policy.snapshot_hash, published.snapshot_hash)
        self.assertNotEqual(
            other_tenant_policy.version_key_hash,
            published.version_key_hash,
        )
        with self.assertRaises(RequestValidationFailed):
            create_handover_package_revision(
                handover_global_id=uid(229),
                tenant_id=TENANT,
                project=project(),
                policy=other_tenant_policy,
                readiness_ref=None,
                slots=slots(),
                manifest=(SOURCE,),
                server_unresolved_actions=(ACTION,),
                enabled_user_ids=frozenset(
                    {SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}
                ),
                reason="Reject a cross-tenant policy.",
                created_by_user_id="admin@example.invalid",
                created_at=NOW,
                request_id=uid(230),
                trace_id="trace-p706-policy-tenant-boundary",
            )
        with self.assertRaises(RequestValidationFailed):
            create_observation_period_revision(
                observation_global_id=uid(231),
                tenant_id=TENANT,
                project=project(),
                policy=other_tenant_policy,
                handover_package_ref=None,
                context_references=(),
                retrospective_references=(),
                retrospective_note=None,
                reason="Reject a cross-tenant policy.",
                created_by_user_id="admin@example.invalid",
                created_at=NOW,
                request_id=uid(232),
                trace_id="trace-p706-observation-policy-tenant-boundary",
            )

    def test_policy_persistence_transition_is_exact_and_optimistic(self) -> None:
        draft = draft_policy()
        validate_policy_persistence_transition(None, draft)
        with self.assertRaises(RequestValidationFailed):
            validate_policy_persistence_transition(
                None,
                replace(draft, optimistic_version=2),
            )

        edited = draft.edit_draft(
            expected_version=1,
            title="Edited through the exact draft transition",
            changed_by_user_id="editor@example.invalid",
            changed_at=NOW,
            request_id=uid(97),
            trace_id="trace-p706-policy-exact-edit",
        )
        validate_policy_persistence_transition(draft, edited)
        for optimistic_version in (1, 3):
            with self.subTest(optimistic_version=optimistic_version):
                with self.assertRaises(RequestValidationFailed):
                    validate_policy_persistence_transition(
                        draft,
                        replace(edited, optimistic_version=optimistic_version),
                    )

        published = draft.publish(
            expected_version=1,
            changed_by_user_id="publisher@example.invalid",
            changed_at=NOW,
            request_id=uid(98),
            trace_id="trace-p706-policy-exact-publish",
        )
        validate_policy_persistence_transition(draft, published)
        with self.assertRaises(RequestValidationFailed):
            validate_policy_persistence_transition(
                draft,
                replace(published, title="Changed while publishing"),
            )
        with self.assertRaises(ProductionTransitionPolicyImmutable):
            validate_policy_persistence_transition(published, published)

    def test_policy_requires_sender_receiver_and_all_five_providers(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(
                draft_policy(),
                acknowledgement_slots=(draft_policy().acknowledgement_slots[0],),
            ).publish(
                expected_version=1,
                changed_by_user_id="publisher@example.invalid",
                changed_at=NOW,
                request_id=uid(29),
                trace_id="trace-p706-policy-invalid-publish",
            )
        with self.assertRaises(RequestValidationFailed):
            replace(draft_policy(), observation_source_rules=source_rules()[:-1])

    def test_policy_publish_bounds_the_total_required_manifest_count(self) -> None:
        at_limit_requirements = (
            HandoverObjectRequirement(
                "open_work",
                (HandoverSourceKind.DOMAIN_WORK_ITEM,),
                "unresolved_action",
                500,
            ),
            HandoverObjectRequirement(
                "decision_record",
                (HandoverSourceKind.DOMAIN_WORK_ITEM,),
                "decision_evidence",
                500,
            ),
        )
        at_limit = replace(
            draft_policy(),
            handover_requirements=at_limit_requirements,
        ).publish(
            expected_version=1,
            changed_by_user_id="publisher@example.invalid",
            changed_at=NOW,
            request_id=uid(95),
            trace_id="trace-p706-manifest-limit",
        )
        self.assertEqual(
            sum(value.minimum_count for value in at_limit.handover_requirements),
            production_transition_domain.MAX_MANIFEST_SOURCES,
        )

        with self.assertRaises(RequestValidationFailed):
            replace(
                draft_policy(),
                handover_requirements=(
                    at_limit_requirements[0],
                    replace(at_limit_requirements[1], minimum_count=501),
                ),
            ).publish(
                expected_version=1,
                changed_by_user_id="publisher@example.invalid",
                changed_at=NOW,
                request_id=uid(96),
                trace_id="trace-p706-manifest-over-limit",
            )

    def test_policy_applicability_rejects_more_than_one_thousand_projects(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ProductionTransitionApplicability(
                (ProjectType.NEW_TOOL,),
                project_global_ids=tuple(uid(value) for value in range(1, 1_002)),
            )

    def test_bounded_reference_collections_accept_lists_and_freeze_sorted_tuples(self) -> None:
        applicability = ProductionTransitionApplicability(
            [ProjectType.NEW_TOOL],
            project_global_ids=[uid(102), uid(101)],
            customer_reference_keys=["ERPNEXT:CUST-002", "ERPNEXT:CUST-001"],
        )
        self.assertEqual(applicability.project_global_ids, (uid(101), uid(102)))
        self.assertEqual(
            applicability.customer_reference_keys,
            ("ERPNEXT:CUST-001", "ERPNEXT:CUST-002"),
        )
        slot = AcknowledgementSlotDefinition(
            "sender",
            "npi_sender",
            AcknowledgementDirection.SENDER,
            ["role_b", "role_a"],
        )
        self.assertEqual(slot.allowed_project_role_keys, ("role_a", "role_b"))
        project_value = replace(
            project(),
            customer_reference_keys=["ERPNEXT:CUST-002", "ERPNEXT:CUST-001"],
        )
        self.assertEqual(
            project_value.customer_reference_keys,
            ("ERPNEXT:CUST-001", "ERPNEXT:CUST-002"),
        )

    def test_policy_applicability_rejects_more_than_one_thousand_customers(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ProductionTransitionApplicability(
                (ProjectType.NEW_TOOL,),
                customer_reference_keys=tuple(
                    f"ERPNEXT:CUST-{value:04d}" for value in range(1_001)
                ),
            )

    def test_acknowledgement_slot_rejects_more_than_one_hundred_roles(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            AcknowledgementSlotDefinition(
                "sender",
                "npi_sender",
                AcknowledgementDirection.SENDER,
                tuple(f"npi_role_{value:03d}" for value in range(101)),
            )

    def test_project_snapshot_rejects_more_than_one_thousand_customers(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(
                project(),
                customer_reference_keys=tuple(
                    f"ERPNEXT:CUST-{value:04d}" for value in range(1_001)
                ),
            )

    def test_closed_source_kind_and_canonical_project_hash_are_enforced(self) -> None:
        self.assertEqual({value.value for value in HandoverSourceKind}, {
            "readiness_instance_revision",
            "domain_work_item",
            "released_document",
            "release_baseline",
            "file_revision",
            "tooling_capacity_scenario",
            "trial_defect_revision",
            "trial_review_reference",
            "trial_conclusion",
        })
        payload = package().snapshot_payload()
        payload["projectSnapshotHash"] = "0" * 64
        with self.assertRaises(RequestValidationFailed):
            handover_package_from_snapshot(payload)

    def test_package_freezes_exact_slots_manifest_and_server_actions(self) -> None:
        value = package()
        self.assertEqual(handover_package_from_snapshot(value.snapshot_payload()), value)
        self.assertNotIn("fullyAcknowledged", value.snapshot_payload())
        self.assertEqual(value.snapshot_payload()["unresolvedActionSelector"], {
            "mode": "all_non_terminal",
            "kinds": ["action", "decision_request", "issue", "risk"],
        })
        with self.assertRaises(RequestValidationFailed):
            create_handover_package_revision(
                handover_global_id=uid(52),
                tenant_id=TENANT,
                project=project(),
                policy=policy(),
                readiness_ref=None,
                slots=slots(),
                manifest=(),
                server_unresolved_actions=(),
                enabled_user_ids=frozenset({SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}),
                reason="Missing required object.",
                created_by_user_id="admin@example.invalid",
                created_at=NOW,
                request_id=uid(53),
                trace_id="trace-p706-missing",
            )

    def test_manifest_requirement_keys_allow_overlapping_kinds_but_freeze_policy_roles(self) -> None:
        overlapping_policy = replace(
            draft_policy(),
            handover_requirements=(
                HandoverObjectRequirement(
                    "open_work",
                    (HandoverSourceKind.DOMAIN_WORK_ITEM,),
                    "unresolved_action",
                ),
                HandoverObjectRequirement(
                    "decision_record",
                    (HandoverSourceKind.DOMAIN_WORK_ITEM,),
                    "decision_evidence",
                ),
            ),
        ).publish(
            expected_version=1,
            changed_by_user_id="publisher@example.invalid",
            changed_at=NOW,
            request_id=uid(91),
            trace_id="trace-p706-overlapping-policy",
        )
        decision_source = HandoverSourceReference(
            requirement_key="decision_record",
            kind=HandoverSourceKind.DOMAIN_WORK_ITEM,
            global_id=uid(41),
            source_version=2,
            snapshot_hash="e" * 64,
            role="decision_evidence",
        )
        value = create_handover_package_revision(
            handover_global_id=uid(92),
            tenant_id=TENANT,
            project=project(),
            policy=overlapping_policy,
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE, decision_source),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset({SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}),
            reason="Freeze overlapping source kinds by explicit requirement key.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(93),
            trace_id="trace-p706-overlapping-manifest",
        )
        self.assertEqual(value.manifest, (SOURCE, decision_source))
        self.assertEqual(
            overlapping_policy.snapshot_payload()["handoverRequirements"][0]["manifestRole"],
            "unresolved_action",
        )

        with self.assertRaises(RequestValidationFailed):
            create_handover_package_revision(
                handover_global_id=uid(94),
                tenant_id=TENANT,
                project=project(),
                policy=overlapping_policy,
                readiness_ref=None,
                slots=slots(),
                manifest=(SOURCE, replace(decision_source, role="wrong_role")),
                server_unresolved_actions=(ACTION,),
                enabled_user_ids=frozenset({SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}),
                reason="Reject a caller-selected manifest role.",
                created_by_user_id="admin@example.invalid",
                created_at=NOW,
                request_id=uid(95),
                trace_id="trace-p706-wrong-manifest-role",
            )

        with self.assertRaises(RequestValidationFailed):
            create_handover_package_revision(
                handover_global_id=uid(96),
                tenant_id=TENANT,
                project=project(),
                policy=overlapping_policy,
                readiness_ref=None,
                slots=slots(),
                manifest=(
                    SOURCE,
                    replace(
                        SOURCE,
                        requirement_key="decision_record",
                        role="decision_evidence",
                    ),
                ),
                server_unresolved_actions=(ACTION,),
                enabled_user_ids=frozenset({SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}),
                reason="Reject one exact source counted for two requirements.",
                created_by_user_id="admin@example.invalid",
                created_at=NOW,
                request_id=uid(97),
                trace_id="trace-p706-duplicate-manifest-source",
            )

    def test_package_successor_is_exact_and_does_not_contain_acknowledgements(self) -> None:
        current = package()
        successor = create_handover_package_successor(
            current,
            project=project(),
            policy=policy(),
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE,),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset({SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}),
            reason="Create a corrected immutable successor.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(54),
            trace_id="trace-p706-successor",
        )
        validate_handover_successor(current, successor)
        self.assertEqual(successor.predecessor_snapshot_hash, current.snapshot_hash)
        self.assertNotIn("acknowledgements", successor.snapshot_payload())
        with self.assertRaises(RequestValidationFailed):
            validate_handover_successor(current, replace(successor, predecessor_snapshot_hash="0" * 64))

    def test_acknowledgements_are_independent_actor_bound_facts_and_query_derived(self) -> None:
        value = package()
        original_hash = value.snapshot_hash
        sender = create_handover_acknowledgement(
            value,
            slot_key="sender",
            acknowledgement_intent=True,
            actor_user_id=SENDER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=SENDER_MEMBER,
            current_role=SENDER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(60),
            trace_id="trace-p706-sender",
        )
        self.assertEqual(acknowledgement_from_snapshot(sender.snapshot_payload()), sender)
        self.assertFalse(derive_fully_acknowledged(value, (sender,)))
        receiver = create_handover_acknowledgement(
            value,
            slot_key="receiver",
            acknowledgement_intent=True,
            actor_user_id=RECEIVER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=RECEIVER_MEMBER,
            current_role=RECEIVER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(61),
            trace_id="trace-p706-receiver",
        )
        self.assertTrue(derive_fully_acknowledged(value, (sender, receiver)))
        self.assertEqual(value.snapshot_hash, original_hash)
        with self.assertRaises(RequestValidationFailed):
            create_handover_acknowledgement(
                value,
                slot_key="sender",
                acknowledgement_intent=True,
                actor_user_id="proxy@example.invalid",
                actor_user_enabled=True,
                current_member=SENDER_MEMBER,
                current_role=SENDER_ROLE,
                acknowledged_at=NOW,
                request_id=uid(62),
                trace_id="trace-p706-proxy",
            )

    def test_acknowledgement_rejects_member_or_role_drift(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            create_handover_acknowledgement(
                package(),
                slot_key="sender",
                acknowledgement_intent=True,
                actor_user_id=SENDER_MEMBER.user_id,
                actor_user_enabled=True,
                current_member=replace(SENDER_MEMBER, optimistic_version=3),
                current_role=SENDER_ROLE,
                acknowledged_at=NOW,
                request_id=uid(63),
                trace_id="trace-p706-drift",
            )

    def test_observation_is_independent_with_five_identity_free_unavailable_providers(self) -> None:
        handover = package()
        value = create_observation_period_revision(
            observation_global_id=uid(70),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=ExactVersionReference(
                handover.global_id,
                handover.handover_version,
                handover.snapshot_hash,
            ),
            context_references=(CONTEXT_SOURCE,),
            retrospective_references=(),
            retrospective_note="Review context only; not a production result.",
            reason="Create an independent technical observation revision.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(71),
            trace_id="trace-p706-observation",
        )
        self.assertEqual(observation_from_snapshot(value.snapshot_payload()), value)
        self.assertEqual(value.technical_disposition, TechnicalDisposition.NOT_EVALUABLE)
        self.assertEqual(value.providers, unavailable_observation_providers())
        for provider in value.snapshot_payload()["providers"]:
            self.assertIsNone(provider["sourceIdentity"])
            self.assertIsNone(provider["observedAt"])
            self.assertIsNone(provider["value"])

    def test_observation_successor_requires_exact_tip_and_remains_not_evaluable(self) -> None:
        current = create_observation_period_revision(
            observation_global_id=uid(72),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Create observation stream.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(73),
            trace_id="trace-p706-observation-one",
        )
        successor = create_observation_period_successor(
            current,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(CONTEXT_SOURCE,),
            retrospective_references=(RETROSPECTIVE_SOURCE,),
            retrospective_note="Retrospective context is not an external actual.",
            reason="Append review context.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(74),
            trace_id="trace-p706-observation-two",
        )
        validate_observation_successor(current, successor)
        self.assertEqual(successor.technical_disposition, TechnicalDisposition.NOT_EVALUABLE)
        with self.assertRaises(RequestValidationFailed):
            validate_observation_successor(
                current,
                replace(successor, predecessor_global_id=uid(999)),
            )

    def test_observation_references_have_fixed_usage_and_cross_list_exactness(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            create_observation_period_revision(
                observation_global_id=uid(98),
                tenant_id=TENANT,
                project=project(),
                policy=policy(),
                handover_package_ref=None,
                context_references=(replace(CONTEXT_SOURCE, usage=ObservationReferenceUsage.RETROSPECTIVE),),
                retrospective_references=(),
                retrospective_note=None,
                reason="Reject a mismatched observation-reference usage.",
                created_by_user_id="admin@example.invalid",
                created_at=NOW,
                request_id=uid(99),
                trace_id="trace-p706-observation-usage",
            )

        with self.assertRaises(RequestValidationFailed):
            create_observation_period_revision(
                observation_global_id=uid(100),
                tenant_id=TENANT,
                project=project(),
                policy=policy(),
                handover_package_ref=None,
                context_references=(CONTEXT_SOURCE,),
                retrospective_references=(
                    replace(RETROSPECTIVE_SOURCE, source_version=SOURCE.source_version + 1),
                ),
                retrospective_note=None,
                reason="Reject cross-list exact-source drift.",
                created_by_user_id="admin@example.invalid",
                created_at=NOW,
                request_id=uid(101),
                trace_id="trace-p706-observation-drift",
            )

        value = create_observation_period_revision(
            observation_global_id=uid(102),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(CONTEXT_SOURCE,),
            retrospective_references=(RETROSPECTIVE_SOURCE,),
            retrospective_note="The same exact source may serve both fixed usages.",
            reason="Freeze exact observation references independently from handover roles.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(103),
            trace_id="trace-p706-observation-exact",
        )
        self.assertEqual(observation_from_snapshot(value.snapshot_payload()), value)
        self.assertEqual(
            set(value.snapshot_payload()["contextReferences"][0]),
            {"kind", "globalId", "sourceVersion", "snapshotHash", "usage"},
        )

    def test_snapshot_parsers_reject_caller_production_truth(self) -> None:
        observation = create_observation_period_revision(
            observation_global_id=uid(80),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Retain unavailable provider truth.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(81),
            trace_id="trace-p706-unavailable",
        )
        payload = copy.deepcopy(observation.snapshot_payload())
        payload["providers"][0]["value"] = "2026-08-14"
        with self.assertRaises(RequestValidationFailed):
            observation_from_snapshot(payload)
        payload = copy.deepcopy(observation.snapshot_payload())
        payload["technicalDisposition"] = "within_rule"
        with self.assertRaises(RequestValidationFailed):
            observation_from_snapshot(payload)

    def test_lineage_identities_are_canonical_within_each_stream(self) -> None:
        policy_successor = policy().next_draft(
            changed_by_user_id="editor@example.invalid",
            changed_at=NOW,
            request_id=uid(82),
            trace_id="trace-p706-lineage-policy",
        )
        policy_payload = copy.deepcopy(policy_successor.snapshot_payload())
        policy_payload["priorVersionRef"]["globalId"] = str(uid(900))
        with self.assertRaises(RequestValidationFailed):
            policy_from_snapshot(policy_payload)

        current_package = package()
        package_successor = create_handover_package_successor(
            current_package,
            project=project(),
            policy=policy(),
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE,),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset({SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}),
            reason="Test canonical handover lineage.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(83),
            trace_id="trace-p706-lineage-handover",
        )
        package_payload = copy.deepcopy(package_successor.snapshot_payload())
        package_payload["predecessorGlobalId"] = str(uid(901))
        with self.assertRaises(RequestValidationFailed):
            handover_package_from_snapshot(package_payload)

        current_observation = create_observation_period_revision(
            observation_global_id=uid(84),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Create canonical observation lineage.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(85),
            trace_id="trace-p706-lineage-observation-one",
        )
        observation_successor = create_observation_period_successor(
            current_observation,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Append canonical observation lineage.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(86),
            trace_id="trace-p706-lineage-observation-two",
        )
        observation_payload = copy.deepcopy(observation_successor.snapshot_payload())
        observation_payload["predecessorGlobalId"] = str(uid(902))
        with self.assertRaises(RequestValidationFailed):
            observation_from_snapshot(observation_payload)

        acknowledgement = create_handover_acknowledgement(
            current_package,
            slot_key="sender",
            acknowledgement_intent=True,
            actor_user_id=SENDER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=SENDER_MEMBER,
            current_role=SENDER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(87),
            trace_id="trace-p706-lineage-ack",
        )
        acknowledgement_payload = copy.deepcopy(acknowledgement.snapshot_payload())
        acknowledgement_payload["packageRevisionGlobalId"] = str(uid(903))
        acknowledgement_payload["globalId"] = str(
            uuid5(uid(903), "npi-handover-acknowledgement:sender")
        )
        with self.assertRaises(RequestValidationFailed):
            acknowledgement_from_snapshot(acknowledgement_payload)

    def test_version_key_hashes_and_closed_snapshot_keys_reject_tampering(self) -> None:
        policy_value = policy()
        policy_payload = copy.deepcopy(policy_value.snapshot_payload())
        policy_payload["versionKeyHash"] = "0" * 64
        with self.assertRaises(RequestValidationFailed):
            policy_from_snapshot(policy_payload)

        package_value = package()
        package_payload = copy.deepcopy(package_value.snapshot_payload())
        package_payload["versionKeyHash"] = "0" * 64
        with self.assertRaises(RequestValidationFailed):
            handover_package_from_snapshot(package_payload)

        observation_value = create_observation_period_revision(
            observation_global_id=uid(88),
            tenant_id=TENANT,
            project=project(),
            policy=policy_value,
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Test canonical observation version key.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(89),
            trace_id="trace-p706-version-key",
        )
        observation_payload = copy.deepcopy(observation_value.snapshot_payload())
        observation_payload["versionKeyHash"] = "0" * 64
        with self.assertRaises(RequestValidationFailed):
            observation_from_snapshot(observation_payload)

        acknowledgement_value = create_handover_acknowledgement(
            package_value,
            slot_key="sender",
            acknowledgement_intent=True,
            actor_user_id=SENDER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=SENDER_MEMBER,
            current_role=SENDER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(90),
            trace_id="trace-p706-extra-key",
        )
        closed_cases = (
            (policy_from_snapshot, policy_value.snapshot_payload(), "privateToken"),
            (handover_package_from_snapshot, package_value.snapshot_payload(), "privateToken"),
            (acknowledgement_from_snapshot, acknowledgement_value.snapshot_payload(), "privateToken"),
            (observation_from_snapshot, observation_value.snapshot_payload(), "privateToken"),
        )
        for parser, source_payload, extra_key in closed_cases:
            with self.subTest(parser=parser.__name__):
                tampered = copy.deepcopy(source_payload)
                tampered[extra_key] = "must-not-survive"
                with self.assertRaises(RequestValidationFailed):
                    parser(tampered)


if __name__ == "__main__":
    unittest.main()
