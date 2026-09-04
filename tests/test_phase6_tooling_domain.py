from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import (
    EngineeringPart,
    EngineeringPartRevision,
    ToolingApplicability,
    ToolingAccessoryLine,
    ToolingDifferenceSourceKind,
    ToolingInspectionCategory,
    ToolingInspectionObservation,
    ToolingIntake,
    ToolingIntakeDifference,
    ToolingIntakeEvidenceReference,
    ToolingIntakeEvidenceRole,
    ToolingMaster,
    ToolingRequirement,
    ToolingRequirementKind,
    ToolingSet,
    ensure_no_effectivity_overlap,
    validate_applicability_successor,
    validate_intake_successor,
)


TENANT = "tenant-a"
PROJECT = UUID("d60e1aef-9b53-486e-95b1-4136ef72fdc5")
PART = UUID("352f4488-4049-4e6b-94f7-15db16aa7959")
PART_R1 = UUID("b1de6219-09b8-460b-a578-a3edc3e719ff")
PART_R2 = UUID("4740d641-0a13-47a9-b026-6814245d698f")
MASTER = UUID("8b93b720-2455-44ac-900d-56841f17ad28")
RELATIONSHIP = UUID("ca5af429-afc7-4680-87c0-12c5be56c3f8")
APPLICABILITY_R1 = UUID("72d34534-d806-4abd-b8d9-79a737bd1dc5")
NOW = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
REQUEST = UUID("c2f67034-f9e9-4e53-82f6-008bdf256a54")
REQUIREMENT = UUID("f9517f60-a42e-4b21-99e1-80c4d8ae5260")
TOOLING_SET = UUID("37fe1c21-586d-468c-869c-ec5c2a8b2af3")
INTAKE_R1 = UUID("18c91429-cfef-492a-a6dd-772d88b53f31")
ACCESSORY = UUID("4669becf-4ff2-43a4-b1a0-eeae9d6c1b43")
INSPECTION_IDS = (
    UUID("b777b1c6-bae1-4054-b65a-ea7f2a79d370"),
    UUID("2b3101b2-6f42-4550-a930-65cc87b5d87b"),
    UUID("4760e4d3-ee72-4129-9a22-6287ba49a27b"),
    UUID("e9e7c74b-cf44-4145-a142-a00b47424b0a"),
    UUID("45298cdf-a498-458f-a756-001690190e79"),
)
DIFFERENCE = UUID("1f34161f-cfa8-4242-926c-0cf4ab320102")


def part_revision(
    *,
    global_id: UUID = PART_R1,
    revision_number: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
) -> EngineeringPartRevision:
    return EngineeringPartRevision(
        global_id=global_id,
        part_global_id=PART,
        tenant_id=TENANT,
        originating_project_global_id=PROJECT,
        revision_number=revision_number,
        revision_label=f"R{revision_number}",
        title="Synthetic housing",
        reason="Create exact engineering Part revision.",
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p601-part",
    )


def applicability(
    *,
    global_id: UUID = APPLICABILITY_R1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
    effective_from: date = date(2026, 8, 7),
    effective_to: date | None = None,
    project: UUID = PROJECT,
) -> ToolingApplicability:
    return ToolingApplicability(
        global_id=global_id,
        relationship_global_id=RELATIONSHIP,
        tenant_id=TENANT,
        project_global_id=project,
        tooling_master_global_id=MASTER,
        part_global_id=PART,
        part_revision_global_id=PART_R1,
        product_source_system="ERPNEXT",
        product_source_object_id="ITEM-SYNTHETIC-001",
        model_source_system=None,
        model_source_object_id=None,
        applicability_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        effective_from=effective_from,
        effective_to=effective_to,
        reason="Bind the shared Tooling Master to an exact Part revision.",
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p601-applicability",
    )


def tooling_set(
    *,
    global_id: UUID = TOOLING_SET,
    kind: ToolingRequirementKind = ToolingRequirementKind.CUSTOMER_OWNED_INTAKE,
    serial: str = "CUSTOMER-MOLD-001",
) -> ToolingSet:
    return ToolingSet(
        global_id=global_id,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        tooling_requirement_global_id=REQUIREMENT,
        requirement_kind=kind,
        physical_serial=serial,
        customer_source_system="ERPNEXT",
        customer_source_object_id="CUSTOMER-SYNTHETIC-001",
        custody_responsibility="NPI Engineering safeguards the customer-owned tool.",
        repair_authorization_reference="Customer authorization is required before repair.",
        return_conditions="Return with the exact intake evidence package.",
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p602-tooling-set",
    )


def intake(
    *,
    global_id: UUID = INTAKE_R1,
    version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
    difference_observed: bool = True,
) -> ToolingIntake:
    inspections = tuple(
        ToolingInspectionObservation(
            global_id=global_id,
            category=category,
            observation=(
                "Connector mismatch observed."
                if category is ToolingInspectionCategory.ELECTRICAL
                and difference_observed
                else "No visible discrepancy observed."
            ),
            difference_observed=(
                category is ToolingInspectionCategory.ELECTRICAL
                and difference_observed
            ),
        )
        for global_id, category in zip(
            INSPECTION_IDS,
            ToolingInspectionCategory,
            strict=True,
        )
    )
    differences = (
        (
            ToolingIntakeDifference(
                global_id=DIFFERENCE,
                source_kind=ToolingDifferenceSourceKind.INSPECTION,
                source_global_id=INSPECTION_IDS[3],
                description="Electrical connector differs from the supplied list.",
                customer_confirmation_required=True,
            ),
        )
        if difference_observed
        else ()
    )
    return ToolingIntake(
        global_id=global_id,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        tooling_set_global_id=TOOLING_SET,
        intake_version=version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        transport_provider="Synthetic carrier",
        transport_reference="SHIPMENT-SYNTHETIC-001",
        arrived_at=NOW,
        custody_handover="Received by NPI Engineering under customer custody terms.",
        accessories=(
            ToolingAccessoryLine(
                global_id=ACCESSORY,
                description="Hot-runner controller cable",
                declared_quantity=1,
                received_quantity=1,
                unit="piece",
            ),
        ),
        inspections=inspections,
        differences=differences,
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p602-intake",
    )


class Phase6ToolingDomainTest(unittest.TestCase):
    def test_part_revision_is_immutable_hash_bound_truth(self) -> None:
        revision = part_revision()
        self.assertEqual(revision.snapshot_payload()["partGlobalId"], str(PART))
        self.assertEqual(len(revision.snapshot_hash), 64)
        with self.assertRaises(RequestValidationFailed):
            part_revision(predecessor_global_id=PART_R2)

    def test_part_advances_only_the_exact_current_revision(self) -> None:
        first = part_revision()
        root = EngineeringPart(
            global_id=PART,
            tenant_id=TENANT,
            originating_project_global_id=PROJECT,
            title=first.title,
            current_revision_global_id=first.global_id,
            current_revision_number=first.revision_number,
            current_revision_snapshot_hash=first.snapshot_hash,
        )
        second = part_revision(
            global_id=PART_R2,
            revision_number=2,
            predecessor_global_id=PART_R1,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        advanced = root.advance(second)
        self.assertEqual(advanced.current_revision_global_id, PART_R2)
        self.assertEqual(advanced.optimistic_version, 2)
        with self.assertRaises(RequestValidationFailed):
            advanced.advance(second)

    def test_requirement_is_not_a_master_or_physical_set(self) -> None:
        requirement = ToolingRequirement(
            global_id=UUID("e337a36a-a2d8-43f3-a29b-9ca61cdf4618"),
            tenant_id=TENANT,
            project_global_id=PROJECT,
            kind=ToolingRequirementKind.COPY_OR_ADDITIONAL_SET,
            title="Synthetic capacity need",
            reason="Record why Tooling is required without creating a Set.",
            target_part_revision_global_id=PART_R1,
            target_date=date(2026, 12, 1),
            created_by_user_id="tooling.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p601-requirement",
        )
        payload = requirement.snapshot_payload()
        self.assertEqual(payload["kind"], "copy_or_additional_set")
        self.assertNotIn("toolingMasterGlobalId", payload)
        self.assertNotIn("setCount", payload)
        self.assertNotIn("lifecycleState", payload)

    def test_master_has_no_project_lifecycle_set_or_asset_projection(self) -> None:
        master = ToolingMaster(
            global_id=MASTER,
            tenant_id=TENANT,
            originating_project_global_id=PROJECT,
            title="Synthetic shared logical tool",
            created_by_user_id="tooling.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p601-master",
        )
        payload = master.snapshot_payload()
        self.assertEqual(payload["originatingProjectGlobalId"], str(PROJECT))
        for forbidden in ("lifecycleState", "revision", "setCount", "assetId"):
            self.assertNotIn(forbidden, payload)

    def test_applicability_has_stable_exact_relationship_key(self) -> None:
        first = applicability()
        replay = applicability()
        self.assertEqual(first.relationship_key_hash, replay.relationship_key_hash)
        self.assertEqual(first.snapshot_hash, replay.snapshot_hash)
        other_project = applicability(
            project=UUID("a14d2d7d-1792-4e77-b643-96b36ab5ad62")
        )
        self.assertNotEqual(first.relationship_key_hash, other_project.relationship_key_hash)

    def test_applicability_reference_pairs_fail_closed(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(applicability(), product_source_system=None)

    def test_applicability_version_requires_exact_predecessor(self) -> None:
        first = applicability(effective_to=date(2026, 9, 1))
        second = applicability(
            global_id=UUID("5af79e85-c2aa-4e7d-bf84-f1631ea6f42d"),
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
            effective_from=date(2026, 9, 1),
        )
        validate_applicability_successor(first, second)
        self.assertTrue(second.is_effective(date(2026, 9, 1)))
        with self.assertRaises(RequestValidationFailed):
            validate_applicability_successor(second, first)

    def test_effectivity_is_half_open_and_cannot_overlap(self) -> None:
        first = applicability(effective_to=date(2026, 9, 1))
        successor = applicability(
            global_id=UUID("5af79e85-c2aa-4e7d-bf84-f1631ea6f42d"),
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
            effective_from=date(2026, 9, 1),
        )
        ensure_no_effectivity_overlap(successor, (first,))
        overlapping = applicability(effective_from=date(2026, 8, 31))
        with self.assertRaises(RequestValidationFailed):
            ensure_no_effectivity_overlap(overlapping, (first,))

    def test_invalid_hash_and_time_are_rejected(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(part_revision(), snapshot_hash="f" * 64)
        with self.assertRaises(RequestValidationFailed):
            applicability(
                effective_from=date(2026, 9, 1),
                effective_to=date(2026, 9, 1),
            )

    def test_each_physical_set_has_independent_identity_without_quantity(self) -> None:
        first = tooling_set()
        second = tooling_set(
            global_id=UUID("52017506-0d12-4a93-a73a-f3fa2c34d538"),
            kind=ToolingRequirementKind.COPY_OR_ADDITIONAL_SET,
            serial="CUSTOMER-MOLD-001",
        )
        self.assertNotEqual(first.global_id, second.global_id)
        self.assertEqual(first.physical_serial, second.physical_serial)
        for payload in (first.snapshot_payload(), second.snapshot_payload()):
            self.assertNotIn("quantity", payload)
            self.assertNotIn("setCount", payload)
            self.assertNotIn("lifecycleState", payload)
            self.assertNotIn("assetId", payload)

    def test_customer_owned_set_requires_exact_customer_and_boundary_statements(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(
                tooling_set(),
                customer_source_system=None,
                customer_source_object_id=None,
            )
        with self.assertRaises(RequestValidationFailed):
            replace(tooling_set(), return_conditions=" ")
        with self.assertRaises(RequestValidationFailed):
            replace(
                tooling_set(),
                requirement_kind=ToolingRequirementKind.REPAIR,
            )

    def test_intake_requires_all_five_inspections_and_exact_differences(self) -> None:
        value = intake()
        self.assertEqual(
            {item.category for item in value.inspections},
            set(ToolingInspectionCategory),
        )
        self.assertEqual(value.differences[0].global_id, DIFFERENCE)
        with self.assertRaises(RequestValidationFailed):
            replace(value, inspections=value.inspections[:-1])
        with self.assertRaises(RequestValidationFailed):
            replace(value, differences=())

    def test_intake_successor_is_append_only_and_exact(self) -> None:
        first = intake()
        second = intake(
            global_id=UUID("63cafec8-7976-4e06-a11b-9425dd91b64a"),
            version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
            difference_observed=False,
        )
        validate_intake_successor(first, second)
        with self.assertRaises(RequestValidationFailed):
            validate_intake_successor(second, first)

    def test_exact_private_file_evidence_is_url_free_and_role_scoped(self) -> None:
        value = ToolingIntakeEvidenceReference(
            global_id=UUID("4ab64c87-11c6-4fe9-88c9-f2fb0e48f937"),
            tenant_id=TENANT,
            project_global_id=PROJECT,
            tooling_master_global_id=MASTER,
            tooling_set_global_id=TOOLING_SET,
            tooling_intake_global_id=INTAKE_R1,
            intake_snapshot_hash=intake().snapshot_hash,
            evidence_role=ToolingIntakeEvidenceRole.CUSTOMER_CONFIRMATION,
            difference_global_ids=(DIFFERENCE,),
            file_revision_global_id=UUID("dc885f80-bd0e-487d-ac39-526c11dfc80a"),
            file_optimistic_version=2,
            frappe_content_hash="a" * 32,
            file_name="customer-confirmation.pdf",
            mime_type="application/pdf",
            size_bytes=128,
            sha256="b" * 64,
            created_by_user_id="tooling.owner@example.invalid",
            created_at=NOW,
            request_id=REQUEST,
            trace_id="trace-p602-evidence",
        )
        payload = value.snapshot_payload()
        self.assertNotIn("fileUrl", payload)
        self.assertEqual(payload["differenceGlobalIds"], [str(DIFFERENCE)])
        with self.assertRaises(RequestValidationFailed):
            replace(value, difference_global_ids=())
        with self.assertRaises(RequestValidationFailed):
            replace(
                value,
                evidence_role=ToolingIntakeEvidenceRole.ARRIVAL_PHOTO,
                difference_global_ids=(),
            )


if __name__ == "__main__":
    unittest.main()
