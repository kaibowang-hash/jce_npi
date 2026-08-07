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
    ToolingMaster,
    ToolingRequirement,
    ToolingRequirementKind,
    ensure_no_effectivity_overlap,
    validate_applicability_successor,
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


if __name__ == "__main__":
    unittest.main()
