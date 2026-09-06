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
    transition_trial_round,
    trial_event_from_snapshot,
    trial_plan_from_snapshot,
    trial_round_from_snapshot,
    trial_work_link_from_snapshot,
    validate_trial_plan_successor,
)
from npi_core.trial.execution_domain import (
    TrialAcquisitionMode,
    TrialActualResourceKind,
    TrialActualResourceObservation,
    TrialEnvironmentObservation,
    TrialEvidenceReference,
    TrialEvidenceRole,
    TrialLockedReference,
    TrialLockedReferenceKind,
    TrialMaterialObservation,
    TrialMeasurementState,
    TrialParameterDefinition,
    TrialParameterObservation,
    TrialParameterValueKind,
    TrialRoundActualRevision,
    TrialRoundInputLockRevision,
    TrialSampleBatchRevision,
    actual_revision_from_snapshot,
    evidence_reference_from_snapshot,
    input_lock_from_snapshot,
    sample_batch_from_snapshot,
    validate_input_lock_successor,
    validate_sample_batch_successor,
    validate_trial_actual_against_lock,
    validate_trial_actual_successor,
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
LOCK = UUID("f2eca061-10e6-43fa-bb75-3fab5814012b")
LOCK_R1 = UUID("d60b971c-a1b8-4813-80a9-c83ad13b942c")
LOCK_R2 = UUID("6be650f5-c5ef-4236-a947-b9f7138a50cb")
ACTUAL = UUID("e8e669c1-e01c-45d8-869a-0f34b1f2ea19")
ACTUAL_R1 = UUID("8a98fedd-01f8-4d35-b11d-503a41740472")
ACTUAL_R2 = UUID("543b6279-6649-4750-bc63-22fda6181615")
SAMPLE = UUID("8eea50d4-cc10-4858-837c-07751e136744")
SAMPLE_R1 = UUID("5b41ad11-ed16-4325-819f-f717100f0aac")
SAMPLE_R2 = UUID("77992bb2-0da0-4d2c-b188-e57823387133")
CAVITY = UUID("8266f55a-7fbd-4798-b26f-411d594f0573")


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


def material_observation() -> TrialMaterialObservation:
    return TrialMaterialObservation(
        source_system="ERPNEXT",
        source_object_id="MATERIAL-SYNTHETIC-01",
        lot_batch_code="LOT-SYNTHETIC-01",
        label="Synthetic manual material observation",
        color="Black",
        additive="Synthetic additive A",
        observed_at=NOW,
        confirmed_by_user_id="trial.owner@example.invalid",
    )


def input_lock_revision(
    *,
    global_id: UUID = LOCK_R1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
) -> TrialRoundInputLockRevision:
    references = tuple(
        TrialLockedReference(
            global_id=UUID(int=index + 100),
            kind=kind,
            optimistic_version=1,
            snapshot_hash=f"{index + 1:064x}",
        )
        for index, kind in enumerate(TrialLockedReferenceKind)
    )
    return TrialRoundInputLockRevision(
        global_id=global_id,
        input_lock_global_id=LOCK,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        trial_round_global_id=ROUND,
        trial_plan_revision_global_id=PLAN_R1,
        trial_plan_revision_snapshot_hash="a" * 64,
        lock_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        references=references,
        material=material_observation(),
        parameter_definitions=(
            TrialParameterDefinition(
                key="melt_temperature",
                category="temperature",
                value_kind=TrialParameterValueKind.DECIMAL,
                required=True,
                unit="degC",
                target_value="230.0",
                lower_limit="225",
                upper_limit="235",
            ),
            TrialParameterDefinition(
                key="operator_note",
                category="observation",
                value_kind=TrialParameterValueKind.TEXT,
                required=False,
            ),
        ),
        reason="Freeze exact Trial Round inputs.",
        created_by_user_id="trial.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p702-input-lock",
    )


def actual_revision(
    input_lock: TrialRoundInputLockRevision,
    *,
    global_id: UUID = ACTUAL_R1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
) -> TrialRoundActualRevision:
    return TrialRoundActualRevision(
        global_id=global_id,
        actual_global_id=ACTUAL,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        trial_round_global_id=ROUND,
        input_lock_revision_global_id=input_lock.global_id,
        input_lock_revision_snapshot_hash=input_lock.snapshot_hash,
        actual_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        acquisition_mode=TrialAcquisitionMode.MANUAL,
        resources=(
            TrialActualResourceObservation(
                kind=TrialActualResourceKind.MACHINE,
                source_system="ERPNEXT",
                source_object_id="MACHINE-SYNTHETIC-01",
                label="Synthetic observed machine",
            ),
        ),
        material=material_observation(),
        environment=(
            TrialEnvironmentObservation(
                key="ambient_temperature",
                value="24.0",
                unit="degC",
                observed_at=NOW,
            ),
        ),
        parameters=(
            TrialParameterObservation(
                definition_key="melt_temperature",
                state=TrialMeasurementState.MEASURED,
                value="231.0",
                unit="degC",
                source=TrialAcquisitionMode.MANUAL,
                observed_at=NOW,
            ),
            TrialParameterObservation(
                definition_key="operator_note",
                state=TrialMeasurementState.NOT_MEASURED,
            ),
        ),
        operator_user_id="trial.operator@example.invalid",
        confirmed_by_user_id="trial.owner@example.invalid",
        execution_started_at=NOW,
        reason="Record exact manual Trial Actuals.",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p702-actual",
    )


def sample_revision(
    input_lock: TrialRoundInputLockRevision,
    *,
    global_id: UUID = SAMPLE_R1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
) -> TrialSampleBatchRevision:
    return TrialSampleBatchRevision(
        global_id=global_id,
        sample_batch_global_id=SAMPLE,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        trial_round_global_id=ROUND,
        input_lock_revision_global_id=input_lock.global_id,
        input_lock_revision_snapshot_hash=input_lock.snapshot_hash,
        sample_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        label="SAMPLE-BATCH-01",
        cavity_global_ids=(CAVITY,),
        material_snapshot_hash="b" * 64,
        quantity=20,
        unit="pcs",
        packaging="One sealed synthetic tray.",
        destination="Synthetic metrology laboratory.",
        feedback_text=None,
        feedback_source=None,
        feedback_observed_at=None,
        reason="Create the immutable Sample Batch revision.",
        created_by_user_id="trial.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p702-sample",
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

    def test_trial_round_allows_only_explicit_sequential_lifecycle_transitions(self) -> None:
        trial_round, _created = create_planned_trial_round(
            global_id=ROUND,
            event_global_id=EVENT,
            plan=plan_revision(),
            round_sequence=0,
            display_label="T0",
            reason="Create the planned Trial Round.",
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p702-round",
        )
        prepared, prepared_event = transition_trial_round(
            trial_round,
            event_global_id=UUID(int=901),
            to_state=TrialRoundState.PREPARED,
            reason="Freeze the exact execution input lock.",
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p702-prepare",
        )
        self.assertEqual(prepared.current_state, TrialRoundState.PREPARED)
        self.assertEqual(prepared_event.event_type, TrialLifecycleEventType.PREPARED)
        running, started_event = transition_trial_round(
            prepared,
            event_global_id=UUID(int=902),
            to_state=TrialRoundState.RUNNING,
            reason="Freeze the first exact manual execution context.",
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p702-start",
        )
        self.assertEqual(running.current_state, TrialRoundState.RUNNING)
        self.assertEqual(started_event.event_type, TrialLifecycleEventType.STARTED)
        self.assertEqual(running.optimistic_version, 3)
        analysis, analysis_event = transition_trial_round(
            running,
            event_global_id=UUID(int=903),
            to_state=TrialRoundState.ANALYSIS,
            reason="Begin exact policy-bound Trial analysis.",
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p704-analysis",
        )
        self.assertEqual(analysis.current_state, TrialRoundState.ANALYSIS)
        self.assertEqual(
            analysis_event.event_type,
            TrialLifecycleEventType.ANALYSIS_BEGUN,
        )
        with self.assertRaises(RequestValidationFailed):
            transition_trial_round(
                analysis,
                event_global_id=UUID(int=904),
                to_state=TrialRoundState.APPROVED,
                reason="Do not skip immutable conclusion submission.",
                created_by_user_id="trial.owner@example.invalid",
                created_at=NOW,
                request_id=REQUEST,
                trace_id="trace-p704-held",
            )

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

    def test_input_lock_is_exact_versioned_and_never_resolves_latest(self) -> None:
        first = input_lock_revision()
        second = input_lock_revision(
            global_id=LOCK_R2,
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        validate_input_lock_successor(first, second)
        self.assertEqual(
            input_lock_from_snapshot(first.snapshot_payload()).snapshot_hash,
            first.snapshot_hash,
        )
        with self.assertRaises(RequestValidationFailed):
            validate_input_lock_successor(
                first,
                replace(second, predecessor_snapshot_hash="0" * 64),
            )
        kinds = {item.kind for item in first.references}
        self.assertEqual(kinds, set(TrialLockedReferenceKind))

    def test_input_lock_requires_every_exact_reference_and_unique_parameters(self) -> None:
        first = input_lock_revision()
        with self.assertRaises(RequestValidationFailed):
            replace(first, references=first.references[:-1])
        with self.assertRaises(RequestValidationFailed):
            replace(
                first,
                parameter_definitions=(
                    first.parameter_definitions[0],
                    first.parameter_definitions[0],
                ),
            )

    def test_actual_is_manual_disjoint_and_explicit_about_not_measured(self) -> None:
        input_lock = input_lock_revision()
        actual = actual_revision(input_lock)
        validate_trial_actual_against_lock(input_lock, actual)
        payload = actual.snapshot_payload()
        self.assertEqual(payload["acquisitionMode"], "manual")
        self.assertEqual(payload["machineImport"], "unavailable")
        self.assertNotIn("customerStandard", payload)
        self.assertNotIn("approvedBaseline", payload)
        not_measured = next(
            item for item in payload["parameters"] if item["state"] == "not_measured"
        )
        self.assertIsNone(not_measured["value"])
        with self.assertRaises(RequestValidationFailed):
            TrialParameterObservation(
                definition_key="operator_note",
                state=TrialMeasurementState.NOT_MEASURED,
                value="Copied standard text",
            )

    def test_actual_must_match_every_locked_definition_and_unit(self) -> None:
        input_lock = input_lock_revision()
        actual = actual_revision(input_lock)
        with self.assertRaises(RequestValidationFailed):
            validate_trial_actual_against_lock(
                input_lock,
                replace(actual, parameters=actual.parameters[:-1]),
            )
        changed = replace(actual.parameters[0], unit="kelvin")
        with self.assertRaises(RequestValidationFailed):
            validate_trial_actual_against_lock(
                input_lock,
                replace(actual, parameters=(changed, actual.parameters[1])),
            )

    def test_actual_successor_and_closed_snapshot_are_exact(self) -> None:
        input_lock = input_lock_revision()
        first = actual_revision(input_lock)
        second = actual_revision(
            input_lock,
            global_id=ACTUAL_R2,
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        validate_trial_actual_successor(first, second)
        self.assertEqual(
            actual_revision_from_snapshot(first.snapshot_payload()).snapshot_hash,
            first.snapshot_hash,
        )
        payload = first.snapshot_payload()
        payload["machineImport"] = "available"
        with self.assertRaises(RequestValidationFailed):
            actual_revision_from_snapshot(payload)

    def test_sample_batch_has_stable_identity_and_append_only_revisions(self) -> None:
        input_lock = input_lock_revision()
        first = sample_revision(input_lock)
        second = sample_revision(
            input_lock,
            global_id=SAMPLE_R2,
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        validate_sample_batch_successor(first, second)
        self.assertEqual(first.sample_batch_global_id, second.sample_batch_global_id)
        self.assertEqual(
            sample_batch_from_snapshot(first.snapshot_payload()).snapshot_hash,
            first.snapshot_hash,
        )
        with self.assertRaises(RequestValidationFailed):
            replace(first, cavity_global_ids=())
        for fieldname, value in (
            ("label", "SAMPLE-BATCH-02"),
            ("cavity_global_ids", (UUID(int=999),)),
            ("material_snapshot_hash", "c" * 64),
            ("quantity", 21),
            ("unit", "box"),
        ):
            with self.subTest(field=fieldname):
                with self.assertRaises(RequestValidationFailed):
                    validate_sample_batch_successor(
                        first,
                        replace(second, **{fieldname: value}),
                    )

    def test_evidence_binds_only_exact_clean_private_file_without_raw_url(self) -> None:
        sample = sample_revision(input_lock_revision())
        evidence = TrialEvidenceReference(
            global_id=UUID("12809b12-011d-41a2-af6b-f73c8276275d"),
            tenant_id=TENANT,
            project_global_id=PROJECT,
            trial_round_global_id=ROUND,
            role=TrialEvidenceRole.MEASUREMENT_REPORT,
            sample_batch_revision_global_id=sample.global_id,
            sample_batch_revision_snapshot_hash=sample.snapshot_hash,
            file_revision_global_id=UUID(
                "7e2fa1a2-e488-49ec-a864-24bdcd0c48b2"
            ),
            file_sha256="f" * 64,
            file_size_bytes=128,
            file_mime_type="application/pdf",
            created_by_user_id="trial.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p702-evidence",
        )
        payload = evidence.snapshot_payload()
        self.assertEqual(payload["scanState"], "clean")
        self.assertEqual(payload["privacy"], "private")
        self.assertFalse(any("url" in key.casefold() for key in payload))
        self.assertEqual(
            evidence_reference_from_snapshot(payload).snapshot_hash,
            evidence.snapshot_hash,
        )
        payload["scanState"] = "pending"
        with self.assertRaises(RequestValidationFailed):
            evidence_reference_from_snapshot(payload)

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
