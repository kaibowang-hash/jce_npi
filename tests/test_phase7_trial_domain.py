from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.trial.domain import (
    TrialLifecycleEventType,
    TrialMeasurementPlanIntent,
    TrialPlanRevision,
    TrialPlanWorkLink,
    TrialProjectMemberReference,
    TrialPurpose,
    TrialResourceKind,
    TrialResourceProposal,
    TrialResourceSource,
    TrialRoundLifecycleEvent,
    TrialRoundState,
    create_planned_trial_round,
    trial_event_from_snapshot,
    trial_plan_from_snapshot,
    trial_round_from_snapshot,
    trial_work_link_from_snapshot,
    validate_trial_plan_successor,
)


TENANT = "tenant-a"
PROJECT = UUID("7c195533-f20e-45a3-9932-41535b94381c")
MASTER = UUID("6cc3f53d-9679-42e4-b944-580d67765828")
PLAN = UUID("b14fcb3c-5551-4d89-9d14-c40c5f87784a")
PLAN_R1 = UUID("652db38a-ab59-4fd3-8f09-5522190078bd")
PLAN_R2 = UUID("da05c78a-ab8c-4f6b-b521-e01a641ccf3a")
ROUND = UUID("6b90f0db-a7f1-4ab4-997b-6c1115051eb8")
EVENT = UUID("658cd2ba-7dd5-4894-92ee-e42497ad91b2")
MEMBER = UUID("75929200-f0b4-418e-b84d-96b69ae0c8f7")
RESOURCE = UUID("d91409dc-31ca-4818-8cb8-f2b49f90c4f8")
MATERIAL = UUID("2241cf4d-31e9-471d-8f51-e07bbe7688b9")
REQUEST = UUID("08964ef3-0378-4be2-9cbb-dcf088994f76")
NOW = datetime(2026, 8, 10, 6, 0, tzinfo=UTC)


def plan_revision(
    *,
    global_id: UUID = PLAN_R1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
) -> TrialPlanRevision:
    return TrialPlanRevision(
        global_id=global_id,
        plan_global_id=PLAN,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        plan_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        purpose=TrialPurpose.FIRST_TRIAL,
        objective="Verify the first bounded synthetic Trial plan.",
        planned_start_at=NOW,
        planned_end_at=NOW + timedelta(hours=6),
        resources=(
            TrialResourceProposal(
                global_id=RESOURCE,
                kind=TrialResourceKind.MACHINE,
                source_system=TrialResourceSource.ERPNEXT,
                source_object_id="MACHINE-SYNTHETIC-01",
                label="Synthetic machine proposal",
            ),
            TrialResourceProposal(
                global_id=MATERIAL,
                kind=TrialResourceKind.MATERIAL,
                source_system=TrialResourceSource.ERPNEXT,
                source_object_id="MATERIAL-SYNTHETIC-01",
                label="Synthetic material proposal",
                quantity=20,
                unit="kg",
            ),
        ),
        responsible_members=(
            TrialProjectMemberReference(
                global_id=MEMBER,
                user_id="trial.owner@example.invalid",
                optimistic_version=2,
            ),
        ),
        sample_quantity=20,
        measurement_plan=TrialMeasurementPlanIntent(
            description="Measure the bounded synthetic characteristics."
        ),
        reason="Create the first immutable Trial Plan revision.",
        created_by_user_id="trial.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p701-plan",
    )


class Phase7TrialDomainTest(unittest.TestCase):
    def test_plan_revision_is_immutable_hash_bound_and_resource_truth_is_honest(
        self,
    ) -> None:
        revision = plan_revision()
        payload = revision.snapshot_payload()
        self.assertEqual(payload["planGlobalId"], str(PLAN))
        self.assertTrue(
            all(item["bookingState"] == "unavailable" for item in payload["resources"])
        )
        self.assertEqual(
            payload["measurementPlan"]["lockState"],
            "planning_intent_only",
        )
        self.assertEqual(len(revision.snapshot_hash), 64)
        self.assertEqual(len(revision.version_key_hash), 64)

    def test_plan_and_round_are_distinct_identities(self) -> None:
        revision = plan_revision()
        trial_round, event = create_planned_trial_round(
            global_id=ROUND,
            event_global_id=EVENT,
            plan=revision,
            round_sequence=0,
            display_label="T0",
            reason="Create the first planned Trial Round.",
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p701-round",
        )
        self.assertNotEqual(revision.plan_global_id, trial_round.global_id)
        self.assertNotEqual(revision.global_id, trial_round.global_id)
        self.assertEqual(trial_round.trial_plan_revision_global_id, revision.global_id)
        self.assertEqual(trial_round.current_event_global_id, event.global_id)
        self.assertEqual(trial_round.current_state, TrialRoundState.PLANNED)
        self.assertEqual(event.event_type, TrialLifecycleEventType.CREATED)

    def test_successor_requires_the_exact_current_plan_revision(self) -> None:
        first = plan_revision()
        second = plan_revision(
            global_id=PLAN_R2,
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        validate_trial_plan_successor(first, second)
        with self.assertRaises(RequestValidationFailed):
            validate_trial_plan_successor(
                first,
                replace(second, predecessor_snapshot_hash="0" * 64),
            )

    def test_first_revision_cannot_claim_a_predecessor(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            plan_revision(
                predecessor_global_id=PLAN_R2,
                predecessor_snapshot_hash="0" * 64,
            )

    def test_successor_cannot_change_plan_project_or_tooling_identity(self) -> None:
        first = plan_revision()
        second = plan_revision(
            global_id=PLAN_R2,
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        with self.assertRaises(RequestValidationFailed):
            validate_trial_plan_successor(
                first,
                replace(
                    second,
                    tooling_master_global_id=UUID(
                        "28b02e4b-124f-4341-9e7c-70fd434111b7"
                    ),
                ),
            )

    def test_resources_cannot_claim_booking_state(self) -> None:
        resource = TrialResourceProposal(
            global_id=RESOURCE,
            kind=TrialResourceKind.MATERIAL,
            source_system=TrialResourceSource.ERPNEXT,
            source_object_id="MATERIAL-SYNTHETIC-01",
            label="Synthetic material proposal",
            quantity=20,
            unit="kg",
        )
        self.assertEqual(resource.snapshot_payload()["bookingState"], "unavailable")
        self.assertFalse(hasattr(resource, "reserved"))
        self.assertFalse(hasattr(resource, "available"))

    def test_resource_quantity_and_unit_are_atomic(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            TrialResourceProposal(
                global_id=RESOURCE,
                kind=TrialResourceKind.MATERIAL,
                source_system=TrialResourceSource.ERPNEXT,
                source_object_id="MATERIAL-SYNTHETIC-01",
                label="Synthetic material proposal",
                quantity=20,
            )

    def test_plan_requires_machine_and_material_proposals(self) -> None:
        revision = plan_revision()
        machine_only = tuple(
            item for item in revision.resources if item.kind is TrialResourceKind.MACHINE
        )
        with self.assertRaises(RequestValidationFailed):
            replace(revision, resources=machine_only)

    def test_measurement_plan_requires_complete_document_provenance(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            TrialMeasurementPlanIntent(
                document_revision_global_id=UUID(
                    "c81a558b-b21e-44dc-9277-e2f8039bc84a"
                )
            )
        with self.assertRaises(RequestValidationFailed):
            TrialMeasurementPlanIntent()

    def test_plan_interval_and_members_are_validated(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(
                plan_revision(),
                planned_end_at=NOW,
            )
        member = TrialProjectMemberReference(
            global_id=MEMBER,
            user_id="TRIAL.OWNER@EXAMPLE.INVALID",
            optimistic_version=1,
        )
        self.assertEqual(member.user_id, "trial.owner@example.invalid")

    def test_round_label_is_controlled_and_sequence_is_nonnegative(self) -> None:
        revision = plan_revision()
        for label, sequence in (("T-1", 0), ("T1", -1), ("R1", 1)):
            with self.subTest(label=label, sequence=sequence):
                with self.assertRaises(RequestValidationFailed):
                    create_planned_trial_round(
                        global_id=ROUND,
                        event_global_id=EVENT,
                        plan=revision,
                        round_sequence=sequence,
                        display_label=label,
                        reason="Create a planned Trial Round.",
                        created_by_user_id="trial.owner@example.invalid",
                        created_at=NOW,
                        request_id=REQUEST,
                        trace_id="trace-p701-round",
                    )

    def test_later_lifecycle_transition_cannot_be_smuggled_as_creation(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            TrialRoundLifecycleEvent(
                global_id=EVENT,
                tenant_id=TENANT,
                project_global_id=PROJECT,
                trial_round_global_id=ROUND,
                event_version=1,
                event_type=TrialLifecycleEventType.CREATED,
                from_state=None,
                to_state=TrialRoundState.PREPARED,
                reason="Do not activate later lifecycle truth.",
                created_by_user_id="trial.owner@example.invalid",
                created_at=NOW,
                request_id=REQUEST,
                trace_id="trace-p701-invalid",
            )

    def test_only_planned_cancellation_is_available_in_bounded_event_domain(self) -> None:
        event = TrialRoundLifecycleEvent(
            global_id=EVENT,
            tenant_id=TENANT,
            project_global_id=PROJECT,
            trial_round_global_id=ROUND,
            event_version=2,
            event_type=TrialLifecycleEventType.CANCELLED,
            from_state=TrialRoundState.PLANNED,
            to_state=TrialRoundState.CANCELLED,
            reason="Cancel the planned Round without deleting it.",
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p701-cancel",
        )
        self.assertEqual(event.to_state, TrialRoundState.CANCELLED)
        with self.assertRaises(RequestValidationFailed):
            replace(event, from_state=TrialRoundState.RUNNING)

    def test_work_link_retains_existing_work_item_as_the_task_truth(self) -> None:
        revision = plan_revision()
        link = TrialPlanWorkLink(
            global_id=UUID("e1efdb56-fee6-4011-9427-9bd7cfaf321c"),
            tenant_id=TENANT,
            project_global_id=PROJECT,
            trial_plan_global_id=PLAN,
            trial_plan_revision_global_id=revision.global_id,
            trial_plan_revision_snapshot_hash=revision.snapshot_hash,
            trial_round_global_id=ROUND,
            domain_work_item_global_id=UUID(
                "33bdaeff-04f6-40d3-9d2d-d1e0894c6ad8"
            ),
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p701-work-link",
        )
        payload = link.snapshot_payload()
        self.assertIn("domainWorkItemGlobalId", payload)
        self.assertNotIn("taskState", payload)
        self.assertNotIn("taskTitle", payload)

    def test_snapshot_reconstruction_is_exact_for_every_history_object(self) -> None:
        revision = plan_revision()
        trial_round, event = create_planned_trial_round(
            global_id=ROUND,
            event_global_id=EVENT,
            plan=revision,
            round_sequence=0,
            display_label="t0",
            reason="Create the first planned Trial Round.",
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p701-round",
        )
        link = TrialPlanWorkLink(
            global_id=UUID("e1efdb56-fee6-4011-9427-9bd7cfaf321c"),
            tenant_id=TENANT,
            project_global_id=PROJECT,
            trial_plan_global_id=PLAN,
            trial_plan_revision_global_id=revision.global_id,
            trial_plan_revision_snapshot_hash=revision.snapshot_hash,
            trial_round_global_id=ROUND,
            domain_work_item_global_id=UUID(
                "33bdaeff-04f6-40d3-9d2d-d1e0894c6ad8"
            ),
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p701-work-link",
        )
        self.assertEqual(
            trial_plan_from_snapshot(revision.snapshot_payload()).snapshot_hash,
            revision.snapshot_hash,
        )
        self.assertEqual(
            trial_round_from_snapshot(trial_round.snapshot_payload()).snapshot_hash,
            trial_round.snapshot_hash,
        )
        self.assertEqual(
            trial_event_from_snapshot(event.snapshot_payload()).snapshot_hash,
            event.snapshot_hash,
        )
        self.assertEqual(
            trial_work_link_from_snapshot(link.snapshot_payload()).snapshot_hash,
            link.snapshot_hash,
        )

    def test_snapshot_tamper_is_rejected(self) -> None:
        revision = plan_revision()
        payload = revision.snapshot_payload()
        payload["sampleQuantity"] = 21
        rebuilt = trial_plan_from_snapshot(payload)
        self.assertNotEqual(rebuilt.snapshot_hash, revision.snapshot_hash)
        with self.assertRaises(RequestValidationFailed):
            replace(revision, snapshot_hash=rebuilt.snapshot_hash)

    def test_snapshot_reconstruction_rejects_open_or_claiming_objects(self) -> None:
        payload = plan_revision().snapshot_payload()
        payload["unexpected"] = True
        with self.assertRaises(RequestValidationFailed):
            trial_plan_from_snapshot(payload)

        payload = plan_revision().snapshot_payload()
        payload["resources"][0]["bookingState"] = "reserved"
        with self.assertRaises(RequestValidationFailed):
            trial_plan_from_snapshot(payload)

        payload = plan_revision().snapshot_payload()
        payload["measurementPlan"]["lockState"] = "locked"
        with self.assertRaises(RequestValidationFailed):
            trial_plan_from_snapshot(payload)


if __name__ == "__main__":
    unittest.main()
