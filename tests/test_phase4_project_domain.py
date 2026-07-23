from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from uuid import UUID, uuid4

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed, VersionConflict
from npi_core.project.domain import (
    BusinessCodeConflict,
    CreateProjectCommand,
    GateDefinition,
    GateShellState,
    IdempotencyConflict,
    InMemoryProjectStore,
    ProjectInstantiationService,
    ProjectLifecycleState,
    ProjectReferenceType,
    ProjectSourceSystem,
    ProjectTemplateVersion,
    ProjectType,
    PublishedTemplateImmutable,
    ReferenceSourceSystem,
    TemplateNotPublished,
    TemplateReferenceRule,
    TypedReference,
    actor_idempotency_key_hash,
    business_code_reservation_hash,
)


TEMPLATE_ID = UUID("2f4d63bf-4d51-4a17-aeb1-08116cb129fa")


def make_draft(*, gates: tuple[GateDefinition, ...] | None = None) -> ProjectTemplateVersion:
    return ProjectTemplateVersion.create_draft(
        template_global_id=TEMPLATE_ID,
        template_code="SYNTHETIC-P4-TEST",
        template_version=1,
        title="Synthetic P4 Test Template",
        applicable_project_types=(
            ProjectType.NEW_TOOL,
            ProjectType.CUSTOMER_OWNED_TOOL,
        ),
        reference_rules=(
            TemplateReferenceRule(ProjectReferenceType.CUSTOMER, required=True),
            TemplateReferenceRule(ProjectReferenceType.PRODUCT),
            TemplateReferenceRule(ProjectReferenceType.ORDER),
        ),
        gates=(
            GateDefinition("G1", "Project Authorization", 2),
            GateDefinition("G0", "Feasibility", 1),
        )
        if gates is None
        else gates,
    )


def make_published_template() -> ProjectTemplateVersion:
    return make_draft().publish(expected_version=1)


def make_reference() -> TypedReference:
    return TypedReference(
        ProjectReferenceType.CUSTOMER,
        ReferenceSourceSystem.NPI_ONE,
        "CUSTOMER-SYNTHETIC",
        UUID("9b333a43-bd44-4196-817e-3efad6d3a47c"),
    )


def make_command(
    template: ProjectTemplateVersion,
    *,
    header_key: str = "phase4-create-project-0001",
    tenant_id: str = "TENANT-A",
    business_code: str = "P4-SYNTHETIC-001",
) -> CreateProjectCommand:
    return CreateProjectCommand(
        idempotency_key=actor_idempotency_key_hash("Administrator", header_key),
        tenant_id=tenant_id,
        business_code=business_code,
        title="Synthetic New Tool Project",
        project_type=ProjectType.NEW_TOOL,
        owner_user_id="owner@example.invalid",
        target_sop=date(2027, 6, 30),
        template_global_id=template.template_global_id,
        template_version=template.template_version,
        expected_version=template.version,
        references=(make_reference(),),
    )


class ProjectTemplateDomainTest(unittest.TestCase):
    def test_published_template_is_immutable_at_value_and_store_boundaries(self) -> None:
        published = make_published_template()
        with self.assertRaises(FrozenInstanceError):
            published.title = "Changed"  # type: ignore[misc]
        with self.assertRaises(PublishedTemplateImmutable):
            published.edit_draft(expected_version=published.version, title="Changed")

        store = InMemoryProjectStore()
        store.add_template_version(published)
        with self.assertRaises(PublishedTemplateImmutable):
            store.add_template_version(replace(published, title="Changed"))

    def test_unpublished_and_invalid_templates_fail_closed(self) -> None:
        draft = make_draft()
        store = InMemoryProjectStore()
        store.add_template_version(draft)
        with self.assertRaises(TemplateNotPublished):
            ProjectInstantiationService(store).instantiate(make_command(draft))
        self.assertEqual(store.projects, ())

        invalid_draft = make_draft(gates=())
        with self.assertRaises(RequestValidationFailed):
            invalid_draft.publish(expected_version=1)

    def test_template_definition_types_and_uniqueness_are_validated(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ProjectTemplateVersion.create_draft(
                template_global_id=TEMPLATE_ID,
                template_code="SYNTHETIC-P4-TEST",
                template_version=1,
                title="Synthetic",
                applicable_project_types=("new_tool",),  # type: ignore[arg-type]
            )
        with self.assertRaises(RequestValidationFailed):
            make_draft(
                gates=(
                    GateDefinition("G0", "First", 1),
                    GateDefinition("g0", "Duplicate", 2),
                )
            )

    def test_revision_has_new_identity_and_preserves_published_history(self) -> None:
        published = make_published_template()
        revision = published.next_draft()
        self.assertEqual(revision.template_global_id, published.template_global_id)
        self.assertEqual(revision.template_version, 2)
        self.assertNotEqual(revision.global_id, published.global_id)
        self.assertEqual(published.template_version, 1)
        self.assertEqual(tuple(gate.key for gate in published.gates), ("G0", "G1"))


class ProjectInstantiationDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.template = make_published_template()
        self.store = InMemoryProjectStore()
        self.store.add_template_version(self.template)
        self.service = ProjectInstantiationService(self.store)

    def test_atomic_instantiation_is_ordered_stable_and_explicit(self) -> None:
        command = make_command(self.template)
        result = self.service.instantiate(command)

        self.assertEqual(result.project.state, ProjectLifecycleState.DRAFT)
        self.assertEqual(result.project.source_system, ProjectSourceSystem.NPI_ONE)
        self.assertEqual(result.project.version, 1)
        self.assertEqual(result.project.project_type, ProjectType.NEW_TOOL)
        self.assertEqual(result.project.owner_user_id, "owner@example.invalid")
        self.assertEqual(result.project.target_sop, date(2027, 6, 30))
        self.assertEqual(tuple(gate.key for gate in result.gates), ("G0", "G1"))
        self.assertEqual(tuple(gate.sequence for gate in result.gates), (1, 2))
        self.assertTrue(
            all(gate.state is GateShellState.NOT_STARTED for gate in result.gates)
        )
        self.assertTrue(
            all(gate.project_global_id == result.project.global_id for gate in result.gates)
        )
        self.assertEqual(result.project.template_snapshot.template_version, 1)
        self.assertEqual(
            result.project.template_snapshot.snapshot_hash,
            self.template.snapshot_hash,
        )

    def test_duplicate_idempotency_replays_and_payload_change_conflicts(self) -> None:
        command = make_command(self.template)
        created = self.service.instantiate(command)
        replayed = self.service.instantiate(command)

        self.assertFalse(created.replayed)
        self.assertTrue(replayed.replayed)
        self.assertEqual(replayed.project, created.project)
        self.assertEqual(replayed.gates, created.gates)
        self.assertEqual(len(self.store.projects), 1)
        self.assertEqual(len(self.store.gates), 2)
        self.assertEqual(len(self.store.idempotency_records), 1)

        with self.assertRaises(IdempotencyConflict):
            self.service.instantiate(replace(command, title="Different payload"))
        self.assertEqual(len(self.store.projects), 1)

    def test_expected_version_conflict_has_no_mutation(self) -> None:
        command = replace(make_command(self.template), expected_version=1)
        with self.assertRaises(VersionConflict):
            self.service.instantiate(command)
        self.assertEqual(self.store.projects, ())
        self.assertEqual(self.store.gates, ())
        self.assertEqual(self.store.idempotency_records, ())

    def test_business_code_uniqueness_is_tenant_scoped_and_case_insensitive(self) -> None:
        self.service.instantiate(make_command(self.template))
        with self.assertRaises(BusinessCodeConflict):
            self.service.instantiate(
                make_command(
                    self.template,
                    header_key="phase4-create-project-0002",
                    business_code="p4-synthetic-001",
                )
            )

        other_tenant = self.service.instantiate(
            make_command(
                self.template,
                header_key="phase4-create-project-0003",
                tenant_id="TENANT-B",
                business_code="p4-synthetic-001",
            )
        )
        self.assertEqual(other_tenant.project.tenant_id, "TENANT-B")
        self.assertEqual(len(self.store.projects), 2)

    def test_reference_types_sources_requirements_and_project_type_fail_closed(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            TypedReference(
                "customer",  # type: ignore[arg-type]
                ReferenceSourceSystem.NPI_ONE,
                "CUSTOMER-1",
            )
        with self.assertRaises(RequestValidationFailed):
            TypedReference(
                ProjectReferenceType.CUSTOMER,
                "NPI_ONE",  # type: ignore[arg-type]
                "CUSTOMER-1",
            )
        with self.assertRaises(RequestValidationFailed):
            replace(make_command(self.template), references=("invalid",))  # type: ignore[arg-type]
        with self.assertRaises(RequestValidationFailed):
            self.service.instantiate(replace(make_command(self.template), references=()))
        with self.assertRaises(RequestValidationFailed):
            self.service.instantiate(
                replace(
                    make_command(self.template),
                    project_type=ProjectType.TOOL_CHANGE,
                )
            )
        with self.assertRaises(RequestValidationFailed):
            self.service.instantiate(
                replace(
                    make_command(self.template),
                    references=(
                        make_reference(),
                        TypedReference(
                            ProjectReferenceType.TOOLING,
                            ReferenceSourceSystem.NPI_ONE,
                            "TOOL-1",
                        ),
                    ),
                )
            )
        self.assertEqual(self.store.projects, ())

    def test_owner_and_date_inputs_are_typed(self) -> None:
        command = make_command(self.template)
        with self.assertRaises(RequestValidationFailed):
            replace(command, owner_user_id="not-an-email")
        with self.assertRaises(RequestValidationFailed):
            replace(command, target_sop="2027-06-30")  # type: ignore[arg-type]
        with self.assertRaises(RequestValidationFailed):
            replace(command, target_sop=datetime(2027, 6, 30, 9, 0))

    def test_template_history_isolated_from_later_revision(self) -> None:
        first = self.service.instantiate(make_command(self.template))
        revision = self.template.next_draft().edit_draft(
            expected_version=1,
            title="Synthetic Revised Template",
            gates=(
                GateDefinition("G0", "Revised Feasibility", 1),
                GateDefinition("G2", "Design Freeze", 2),
            ),
        )
        published_revision = revision.publish(expected_version=revision.version)
        self.store.add_template_version(published_revision)
        second = self.service.instantiate(
            replace(
                make_command(
                    published_revision,
                    header_key="phase4-create-project-0004",
                    business_code="P4-SYNTHETIC-002",
                ),
                template_version=2,
                expected_version=published_revision.version,
            )
        )

        self.assertEqual(first.project.template_snapshot.template_version, 1)
        self.assertEqual(tuple(gate.key for gate in first.gates), ("G0", "G1"))
        self.assertEqual(second.project.template_snapshot.template_version, 2)
        self.assertEqual(tuple(gate.key for gate in second.gates), ("G0", "G2"))
        self.assertEqual(tuple(gate.key for gate in first.gates), ("G0", "G1"))

    def test_unit_of_work_failure_leaves_no_partial_records(self) -> None:
        def fail_after_first_gate(point: str) -> None:
            if point == "after_gate":
                raise RuntimeError("synthetic transaction failure")

        store = InMemoryProjectStore(failure_hook=fail_after_first_gate)
        store.add_template_version(self.template)
        with self.assertRaises(RuntimeError):
            ProjectInstantiationService(store).instantiate(make_command(self.template))
        self.assertEqual(store.projects, ())
        self.assertEqual(store.gates, ())
        self.assertEqual(store.idempotency_records, ())

    def test_identity_is_deterministic_across_clean_atomic_retries(self) -> None:
        command = make_command(self.template)
        first = self.service.instantiate(command)
        second_store = InMemoryProjectStore()
        second_store.add_template_version(self.template)
        second = ProjectInstantiationService(second_store).instantiate(command)
        self.assertEqual(first.project.global_id, second.project.global_id)
        self.assertEqual(
            tuple(gate.global_id for gate in first.gates),
            tuple(gate.global_id for gate in second.gates),
        )


class ProjectPersistenceKeyTest(unittest.TestCase):
    def test_actor_idempotency_hash_accepts_administrator_and_validates_header(self) -> None:
        key = "phase4-create-project-0001"
        self.assertEqual(
            actor_idempotency_key_hash("Administrator", key),
            actor_idempotency_key_hash("administrator", key),
        )
        self.assertEqual(len(actor_idempotency_key_hash("Administrator", key)), 64)
        with self.assertRaises(RequestValidationFailed):
            actor_idempotency_key_hash("Administrator", "too-short")
        with self.assertRaises(RequestValidationFailed):
            actor_idempotency_key_hash("Administrator", "contains a space key")
        with self.assertRaises(RequestValidationFailed):
            actor_idempotency_key_hash("Administrator", "x" * 256)

    def test_business_code_reservation_hash_is_tenant_scoped_and_casefolded(self) -> None:
        first = business_code_reservation_hash("TENANT-A", "Project-001")
        self.assertEqual(
            first,
            business_code_reservation_hash("tenant-a", "project-001"),
        )
        self.assertNotEqual(
            first,
            business_code_reservation_hash("TENANT-B", "project-001"),
        )
        self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
