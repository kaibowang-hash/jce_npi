from __future__ import annotations

import unittest
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.ebom.domain import (
    EngineeringBomAuthorityUnavailable,
    EngineeringBomChangeType,
    EngineeringBomLifecycleState,
    EngineeringBomLifecycleEvent,
    EngineeringBomEventType,
    EngineeringBomLine,
    EngineeringBomPolicyState,
    EngineeringBomPolicyUnavailable,
    EngineeringBomPolicyVersion,
    EngineeringBomReviewDecision,
    EngineeringBomRevision,
    EngineeringBomRevisionLifecycle,
    EngineeringBomStateConflict,
    compare_engineering_bom_revisions,
    create_engineering_bom_revision,
    transition_engineering_bom,
)
from npi_core.foundation.errors import RequestValidationFailed


TENANT_ID = "tenant-a"
PROJECT_ID = UUID("ee7193f7-a704-4ed3-9ac0-85c2b1b45184")
POLICY_ID = UUID("eb233de2-5d4d-4556-ad16-9476d8f0776f")
POLICY_VERSION_ID = UUID("2ff69aca-ac9e-4f48-b56d-cf969b23d875")
EBOM_ID = UUID("0878087f-6192-4e40-862d-05e0a5927638")
REVISION_ONE_ID = UUID("29e933a3-3954-4a96-9400-2be1987ae370")
REVISION_TWO_ID = UUID("89953948-4178-46dc-b7ca-8b94f2ac4e36")
ROOT_LINE_ID = UUID("5729ff5a-50a0-4ac8-a98b-0a2e52dca148")
CHILD_LINE_ID = UUID("787801a4-7298-42fd-ac16-1ea7f7d3103a")
ALTERNATE_LINE_ID = UUID("62594bc2-020f-4416-8848-fb2ab580a2fd")
ADDED_LINE_ID = UUID("5040a9c2-3c21-430c-8843-c94beef08e21")
EVENT_ID = UUID("ca699225-0384-45c2-99bb-1ed087765643")
NOW = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)


def policy(
    *,
    state: EngineeringBomPolicyState = EngineeringBomPolicyState.PUBLISHED,
    **changes: object,
) -> EngineeringBomPolicyVersion:
    values: dict[str, object] = {
        "global_id": POLICY_VERSION_ID,
        "policy_global_id": POLICY_ID,
        "tenant_id": TENANT_ID,
        "project_global_id": PROJECT_ID,
        "policy_key": "synthetic_ebom_policy",
        "policy_version": 1,
        "title": "Synthetic EBOM policy",
        "state": state,
        "synthetic_namespace": "synthetic_ebom",
        "quantity_scale": 3,
        "maximum_nodes": 20,
        "engineering_uoms": ("EA", "KG"),
        "attribute_keys": ("material", "finish"),
        "creator_user_ids": ("creator@example.invalid",),
        "review_submitter_user_ids": ("submitter@example.invalid",),
        "reviewer_user_ids": ("reviewer@example.invalid",),
        "release_authority_user_ids": ("releaser@example.invalid",),
    }
    values.update(changes)
    return EngineeringBomPolicyVersion(**values)  # type: ignore[arg-type]


def root_line(**changes: object) -> EngineeringBomLine:
    values: dict[str, object] = {
        "global_id": ROOT_LINE_ID,
        "line_key": "10",
        "parent_line_key": None,
        "engineering_item_id": "eng:assembly-a",
        "description": "Assembly A",
        "quantity": Decimal("1"),
        "engineering_uom": "EA",
        "alternate_group_key": "group-a",
        "attributes": (("material", "ABS"),),
    }
    values.update(changes)
    return EngineeringBomLine(**values)  # type: ignore[arg-type]


def child_line(**changes: object) -> EngineeringBomLine:
    values: dict[str, object] = {
        "global_id": CHILD_LINE_ID,
        "line_key": "20",
        "parent_line_key": "10",
        "engineering_item_id": "eng:component-b",
        "description": "Component B",
        "quantity": Decimal("2.500"),
        "engineering_uom": "EA",
        "effectivity_start": date(2026, 8, 1),
        "attributes": (("finish", "matte"),),
    }
    values.update(changes)
    return EngineeringBomLine(**values)  # type: ignore[arg-type]


def revision(
    *,
    revision_id: UUID = REVISION_ONE_ID,
    revision_number: int = 1,
    predecessor: EngineeringBomRevision | None = None,
    lines: tuple[EngineeringBomLine, ...] | None = None,
    selected_policy: EngineeringBomPolicyVersion | None = None,
    actor: str = "creator@example.invalid",
) -> EngineeringBomRevision:
    return create_engineering_bom_revision(
        global_id=revision_id,
        ebom_global_id=EBOM_ID,
        tenant_id=TENANT_ID,
        project_global_id=PROJECT_ID,
        engineering_bom_key="synthetic_ebom-main",
        revision_number=revision_number,
        predecessor=predecessor,
        reason="Initial structure" if revision_number == 1 else "Design update",
        effectivity_note=None,
        policy=selected_policy or policy(),
        lines=lines or (root_line(), child_line()),
        actor=actor,
        now=NOW,
        request_id=f"request-{revision_number}",
        trace_id=f"trace-{revision_number}",
    )


class Phase5EngineeringBomDomainTest(unittest.TestCase):
    def test_policy_is_canonical_hashed_and_authorities_are_independent(self) -> None:
        value = policy(engineering_uoms=("KG", "EA"))
        self.assertEqual(value.engineering_uoms, ("EA", "KG"))
        self.assertEqual(value.snapshot_hash, value.reference.snapshot_hash)
        self.assertTrue(value.permits("create", "CREATOR@example.invalid"))
        self.assertFalse(value.permits("release", "creator@example.invalid"))
        self.assertEqual(
            value.snapshot_payload()["lineIdentityMode"],
            "caller_supplied_stable_key",
        )

    def test_policy_rejects_non_synthetic_or_weakened_rules(self) -> None:
        for changes in (
            {"synthetic_namespace": "production"},
            {"line_identity_mode": "position"},
            {"require_acyclic_graph": False},
            {"quantity_scale": 7},
            {"engineering_uoms": ()},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                RequestValidationFailed
            ):
                policy(**changes)

    def test_initial_revision_canonicalizes_lines_and_exact_quantity_scale(self) -> None:
        value = revision(lines=(child_line(), root_line()))
        self.assertEqual([line.line_key for line in value.lines], ["10", "20"])
        snapshot = value.snapshot_payload()
        self.assertEqual(snapshot["lines"][0]["quantity"], "1.000")  # type: ignore[index]
        self.assertEqual(snapshot["lines"][1]["quantity"], "2.500")  # type: ignore[index]
        self.assertEqual(len(value.snapshot_hash), 64)

    def test_creation_requires_published_matching_policy_and_creator(self) -> None:
        with self.assertRaises(EngineeringBomPolicyUnavailable):
            revision(selected_policy=policy(state=EngineeringBomPolicyState.DRAFT))
        with self.assertRaises(EngineeringBomAuthorityUnavailable):
            revision(actor="reviewer@example.invalid")
        with self.assertRaises(RequestValidationFailed):
            create_engineering_bom_revision(
                global_id=REVISION_ONE_ID,
                ebom_global_id=EBOM_ID,
                tenant_id=TENANT_ID,
                project_global_id=PROJECT_ID,
                engineering_bom_key="PROD-100",
                revision_number=1,
                predecessor=None,
                reason="Initial",
                effectivity_note=None,
                policy=policy(),
                lines=(root_line(),),
                actor="creator@example.invalid",
                now=NOW,
                request_id="request",
                trace_id="trace",
            )

    def test_graph_rejects_missing_parent_and_cycles(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            revision(lines=(root_line(), child_line(parent_line_key="missing")))
        with self.assertRaises(RequestValidationFailed):
            revision(
                lines=(
                    root_line(parent_line_key="20"),
                    child_line(parent_line_key="10"),
                )
            )

    def test_policy_rejects_quantity_uom_and_attribute_drift(self) -> None:
        for line in (
            child_line(quantity=Decimal("1.0001")),
            child_line(engineering_uom="BOX"),
            child_line(attributes=(("unapproved", "value"),)),
        ):
            with self.subTest(line=line), self.assertRaises(RequestValidationFailed):
                revision(lines=(root_line(), line))

    def test_effectivity_and_alternate_references_are_closed(self) -> None:
        alternate = EngineeringBomLine(
            global_id=ALTERNATE_LINE_ID,
            line_key="11",
            parent_line_key=None,
            engineering_item_id="eng:assembly-alternate",
            description="Assembly alternate",
            quantity=Decimal("1"),
            engineering_uom="EA",
            alternate_for_line_key="10",
            alternate_group_key="group-a",
        )
        value = revision(lines=(root_line(), alternate, child_line()))
        self.assertEqual(len(value.lines), 3)
        with self.assertRaises(RequestValidationFailed):
            revision(
                lines=(
                    root_line(),
                    EngineeringBomLine(
                        global_id=ALTERNATE_LINE_ID,
                        line_key="11",
                        parent_line_key="10",
                        engineering_item_id="eng:bad-alternate",
                        description="Bad alternate",
                        quantity=Decimal("1"),
                        engineering_uom="EA",
                        alternate_for_line_key="10",
                        alternate_group_key="group-a",
                    ),
                )
            )
        with self.assertRaises(RequestValidationFailed):
            child_line(
                effectivity_start=date(2026, 8, 2),
                effectivity_end=date(2026, 8, 1),
            )

    def test_successor_requires_exact_same_current_revision(self) -> None:
        first = revision()
        second = revision(
            revision_id=REVISION_TWO_ID,
            revision_number=2,
            predecessor=first,
        )
        self.assertEqual(second.predecessor_global_id, first.global_id)
        self.assertEqual(second.predecessor_snapshot_hash, first.snapshot_hash)
        with self.assertRaises(RequestValidationFailed):
            revision(
                revision_id=REVISION_TWO_ID,
                revision_number=3,
                predecessor=first,
            )

    def test_comparison_is_deterministic_and_covers_all_required_types(self) -> None:
        first = revision()
        second = revision(
            revision_id=REVISION_TWO_ID,
            revision_number=2,
            predecessor=first,
            lines=(
                root_line(
                    engineering_item_id="eng:assembly-c",
                    description="Assembly C",
                ),
                EngineeringBomLine(
                    global_id=ADDED_LINE_ID,
                    line_key="30",
                    parent_line_key="10",
                    engineering_item_id="eng:component-d",
                    description="Component D",
                    quantity=Decimal("3"),
                    engineering_uom="EA",
                ),
            ),
        )
        differences = compare_engineering_bom_revisions(first, second)
        self.assertEqual(
            [(item.line_key, item.change_type) for item in differences],
            [
                ("10", EngineeringBomChangeType.SUBSTITUTION),
                ("10", EngineeringBomChangeType.ATTRIBUTE),
                ("20", EngineeringBomChangeType.REMOVED),
                ("30", EngineeringBomChangeType.ADDED),
            ],
        )
        self.assertEqual(compare_engineering_bom_revisions(first, first), ())

    def test_comparison_reports_quantity_separately(self) -> None:
        first = revision()
        second = revision(
            revision_id=REVISION_TWO_ID,
            revision_number=2,
            predecessor=first,
            lines=(root_line(), child_line(quantity=Decimal("3"))),
        )
        differences = compare_engineering_bom_revisions(first, second)
        self.assertEqual(len(differences), 1)
        self.assertEqual(differences[0].change_type, EngineeringBomChangeType.QUANTITY)

    def test_lifecycle_uses_independent_authorities_and_exact_versions(self) -> None:
        content = revision()
        lifecycle = EngineeringBomRevisionLifecycle(
            revision_global_id=content.global_id,
            revision_snapshot_hash=content.snapshot_hash,
            current_state=EngineeringBomLifecycleState.DRAFT,
            lifecycle_version=1,
        )
        submitted = transition_engineering_bom(
            lifecycle=lifecycle,
            policy=policy(),
            actor="submitter@example.invalid",
            event_global_id=EVENT_ID,
            now=NOW,
            request_id="request-submit",
            trace_id="trace-submit",
            expected_version=1,
            action="submit_review",
        )
        self.assertEqual(
            submitted.lifecycle.current_state,
            EngineeringBomLifecycleState.IN_REVIEW,
        )
        with self.assertRaises(EngineeringBomAuthorityUnavailable):
            transition_engineering_bom(
                lifecycle=submitted.lifecycle,
                policy=policy(),
                actor="releaser@example.invalid",
                event_global_id=EVENT_ID,
                now=NOW,
                request_id="request-review",
                trace_id="trace-review",
                expected_version=2,
                action="review",
                decision=EngineeringBomReviewDecision.APPROVE,
            )
        with self.assertRaises(EngineeringBomStateConflict):
            transition_engineering_bom(
                lifecycle=submitted.lifecycle,
                policy=policy(),
                actor="reviewer@example.invalid",
                event_global_id=EVENT_ID,
                now=NOW,
                request_id="request-review",
                trace_id="trace-review",
                expected_version=1,
                action="review",
                decision=EngineeringBomReviewDecision.APPROVE,
            )

    def test_reject_retains_event_and_release_requires_exact_confirmation(self) -> None:
        content = revision()
        in_review = EngineeringBomRevisionLifecycle(
            revision_global_id=content.global_id,
            revision_snapshot_hash=content.snapshot_hash,
            current_state=EngineeringBomLifecycleState.IN_REVIEW,
            lifecycle_version=2,
        )
        rejected = transition_engineering_bom(
            lifecycle=in_review,
            policy=policy(),
            actor="reviewer@example.invalid",
            event_global_id=EVENT_ID,
            now=NOW,
            request_id="request-reject",
            trace_id="trace-reject",
            expected_version=2,
            action="review",
            decision=EngineeringBomReviewDecision.REJECT,
            reason="Correct the structure",
        )
        self.assertEqual(rejected.lifecycle.current_state, EngineeringBomLifecycleState.DRAFT)
        self.assertEqual(rejected.event.reason, "Correct the structure")

        approved = EngineeringBomRevisionLifecycle(
            revision_global_id=content.global_id,
            revision_snapshot_hash=content.snapshot_hash,
            current_state=EngineeringBomLifecycleState.APPROVED,
            lifecycle_version=3,
        )
        with self.assertRaises(RequestValidationFailed):
            transition_engineering_bom(
                lifecycle=approved,
                policy=policy(),
                actor="releaser@example.invalid",
                event_global_id=EVENT_ID,
                now=NOW,
                request_id="request-release",
                trace_id="trace-release",
                expected_version=3,
                action="release",
                confirmed=True,
                confirmation_intent="wrong_intent",
            )
        released = transition_engineering_bom(
            lifecycle=approved,
            policy=policy(),
            actor="releaser@example.invalid",
            event_global_id=EVENT_ID,
            now=NOW,
            request_id="request-release",
            trace_id="trace-release",
            expected_version=3,
            action="release",
            confirmed=True,
            confirmation_intent="release_exact_ebom_revision",
        )
        self.assertEqual(released.lifecycle.current_state, EngineeringBomLifecycleState.RELEASED)
        with self.assertRaises(EngineeringBomStateConflict):
            transition_engineering_bom(
                lifecycle=released.lifecycle,
                policy=policy(),
                actor="submitter@example.invalid",
                event_global_id=EVENT_ID,
                now=NOW,
                request_id="request-terminal",
                trace_id="trace-terminal",
                expected_version=4,
                action="submit_review",
            )

    def test_event_snapshot_rejects_a_forged_type_or_release_intent(self) -> None:
        content = revision()
        with self.assertRaises(RequestValidationFailed):
            EngineeringBomLifecycleEvent(
                global_id=EVENT_ID,
                revision_global_id=content.global_id,
                revision_snapshot_hash=content.snapshot_hash,
                policy_ref=policy().reference,
                event_type=EngineeringBomEventType.RELEASED,
                from_state=EngineeringBomLifecycleState.DRAFT,
                to_state=EngineeringBomLifecycleState.RELEASED,
                from_version=1,
                to_version=2,
                actor_user_id="releaser@example.invalid",
                authority_action="release",
                decision=None,
                reason=None,
                confirmation_intent="release_exact_ebom_revision",
                occurred_at=NOW,
                request_id="request-forged",
                trace_id="trace-forged",
            )
        with self.assertRaises(RequestValidationFailed):
            EngineeringBomLifecycleEvent(
                global_id=EVENT_ID,
                revision_global_id=content.global_id,
                revision_snapshot_hash=content.snapshot_hash,
                policy_ref=policy().reference,
                event_type=EngineeringBomEventType.RELEASED,
                from_state=EngineeringBomLifecycleState.APPROVED,
                to_state=EngineeringBomLifecycleState.RELEASED,
                from_version=3,
                to_version=4,
                actor_user_id="releaser@example.invalid",
                authority_action="release",
                decision=None,
                reason=None,
                confirmation_intent="wrong_intent",
                occurred_at=NOW,
                request_id="request-forged",
                trace_id="trace-forged",
            )


if __name__ == "__main__":
    unittest.main()
