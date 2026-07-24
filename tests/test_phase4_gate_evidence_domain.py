from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from datetime import date
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.gate_evidence.domain import (  # noqa: E402
    build_frozen_requirement_snapshot,
    evidence_reference_key,
    requirement_global_id,
    wbs_source_snapshot,
)
from npi_core.foundation.errors import RequestValidationFailed  # noqa: E402


GATE_ID = UUID("62d6ac02-b85f-4ae0-a522-953c4ebc2de4")
TEMPLATE_ID = UUID("77932078-9512-428e-b9d7-863303661059")
OWNER_ID = UUID("4b5e2ed1-0e5a-41b6-a217-6f84a809ba36")
REVIEWER_ID = UUID("44f7b429-a527-4304-865d-d61e6a42320b")
SOURCE_ID = UUID("590b332e-1ec4-44d8-8778-8b84eaf079bc")


@dataclass(frozen=True)
class Requirement:
    key: str
    title: str
    classification: str
    priority: str
    allowed_evidence_kinds: tuple[str, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "classification": self.classification,
            "priority": self.priority,
            "allowedEvidenceKinds": list(self.allowed_evidence_kinds),
        }


@dataclass(frozen=True)
class TemplateSnapshot:
    gate_template_global_id: UUID
    gate_template_version: int
    snapshot_hash: str
    requirements: tuple[Requirement, ...]


class Phase4GateEvidenceDomainTest(unittest.TestCase):
    def template(self) -> TemplateSnapshot:
        return TemplateSnapshot(
            gate_template_global_id=TEMPLATE_ID,
            gate_template_version=3,
            snapshot_hash="a" * 64,
            requirements=(
                Requirement(
                    "drawing",
                    "Released drawing",
                    "required",
                    "P0",
                    ("file_revision",),
                ),
                Requirement(
                    "review_task",
                    "Review task",
                    "optional",
                    "P1",
                    ("wbs_item",),
                ),
            ),
        )

    def assignments(self) -> tuple[dict[str, object], ...]:
        return (
            {
                "key": "review_task",
                "owner_member_id": OWNER_ID,
                "reviewer_member_ids": (REVIEWER_ID,),
                "due_date": date(2026, 8, 30),
            },
            {
                "key": "drawing",
                "owner_member_id": OWNER_ID,
                "reviewer_member_ids": (REVIEWER_ID,),
                "due_date": date(2026, 8, 28),
            },
        )

    def test_snapshot_follows_template_order_and_has_deterministic_hash(self) -> None:
        snapshot, snapshot_hash = build_frozen_requirement_snapshot(
            gate_global_id=GATE_ID,
            gate_template_snapshot=self.template(),
            gate_due_date=date(2026, 8, 31),
            assignments=self.assignments(),
        )
        repeated, repeated_hash = build_frozen_requirement_snapshot(
            gate_global_id=GATE_ID,
            gate_template_snapshot=self.template(),
            gate_due_date=date(2026, 8, 31),
            assignments=tuple(reversed(self.assignments())),
        )
        self.assertEqual(snapshot, repeated)
        self.assertEqual(snapshot_hash, repeated_hash)
        self.assertEqual(len(snapshot_hash), 64)
        requirements = snapshot["requirements"]
        self.assertEqual(
            [item["key"] for item in requirements],  # type: ignore[index]
            ["drawing", "review_task"],
        )
        self.assertEqual(
            requirements[0]["globalId"],  # type: ignore[index]
            str(requirement_global_id(GATE_ID, "drawing")),
        )
        self.assertEqual(
            snapshot["gateTemplateRef"],
            {
                "globalId": str(TEMPLATE_ID),
                "version": 3,
                "snapshotHash": "a" * 64,
            },
        )

    def test_snapshot_requires_exactly_one_assignment_for_every_definition(
        self,
    ) -> None:
        cases = (
            self.assignments()[:1],
            (*self.assignments(), self.assignments()[0]),
            (
                *self.assignments(),
                {
                    "key": "unexpected",
                    "owner_member_id": OWNER_ID,
                    "reviewer_member_ids": (REVIEWER_ID,),
                    "due_date": date(2026, 8, 31),
                },
            ),
        )
        for assignments in cases:
            with self.subTest(assignments=assignments):
                with self.assertRaises(RequestValidationFailed):
                    build_frozen_requirement_snapshot(
                        gate_global_id=GATE_ID,
                        gate_template_snapshot=self.template(),
                        gate_due_date=date(2026, 8, 31),
                        assignments=assignments,
                    )

    def test_snapshot_requires_real_unique_reviewer_member_ids(self) -> None:
        assignments = list(self.assignments())
        assignments[0] = {
            **assignments[0],
            "reviewer_member_ids": (REVIEWER_ID, REVIEWER_ID),
        }
        with self.assertRaises(RequestValidationFailed):
            build_frozen_requirement_snapshot(
                gate_global_id=GATE_ID,
                gate_template_snapshot=self.template(),
                gate_due_date=date(2026, 8, 31),
                assignments=assignments,
            )

    def test_wbs_snapshot_is_exact_safe_and_hash_sensitive(self) -> None:
        document = {
            "global_id": str(SOURCE_ID),
            "tenant_id": "TENANT-A",
            "project_global_id": "2e96f421-5872-4c96-a0dd-718d5c970a21",
            "work_policy_global_id": str(TEMPLATE_ID),
            "work_policy_version": 1,
            "work_policy_snapshot_hash": "b" * 64,
            "wbs_code": "1.2",
            "title": "Release drawing",
            "parent_global_id": None,
            "owner_role_assignment_global_id": None,
            "planned_start": date(2026, 8, 1),
            "planned_end": date(2026, 8, 5),
            "actual_start": None,
            "actual_end": None,
            "milestone": 1,
            "status_key": "planned",
            "status_label_source": "Not started",
            "progress_percent": 0,
            "critical_task": 1,
            "plan_revision": 2,
            "optimistic_version": 3,
        }
        snapshot, snapshot_hash = wbs_source_snapshot(document)
        self.assertEqual(snapshot["optimisticVersion"], 3)
        self.assertEqual(snapshot["criticalTask"], True)
        self.assertNotIn("fileUrl", snapshot)
        changed = {**document, "progress_percent": 10}
        _changed_snapshot, changed_hash = wbs_source_snapshot(changed)
        self.assertNotEqual(snapshot_hash, changed_hash)

    def test_reference_key_covers_gate_requirement_kind_version_and_hash(self) -> None:
        key = evidence_reference_key(
            tenant_id="TENANT-A",
            project_global_id="2e96f421-5872-4c96-a0dd-718d5c970a21",
            gate_global_id=str(GATE_ID),
            requirement_global_id=str(requirement_global_id(GATE_ID, "drawing")),
            requirement_key="drawing",
            evidence_kind="file_revision",
            source_object_type="file_revision",
            source_global_id=str(SOURCE_ID),
            source_version=2,
            source_hash="c" * 64,
        )
        changed = evidence_reference_key(
            tenant_id="TENANT-A",
            project_global_id="2e96f421-5872-4c96-a0dd-718d5c970a21",
            gate_global_id=str(GATE_ID),
            requirement_global_id=str(requirement_global_id(GATE_ID, "drawing")),
            requirement_key="drawing",
            evidence_kind="file_revision",
            source_object_type="file_revision",
            source_global_id=str(SOURCE_ID),
            source_version=3,
            source_hash="c" * 64,
        )
        self.assertEqual(len(key), 64)
        self.assertNotEqual(key, changed)


if __name__ == "__main__":
    unittest.main()
