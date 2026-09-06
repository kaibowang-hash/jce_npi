from __future__ import annotations

import hashlib
import json
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.gate_template.domain import (
    EvidenceKind,
    GateRequirementClassification,
    GateRequirementDefinition,
    GateRequirementPriority,
    GateTemplateVersion,
    PublishedGateTemplateImmutable,
)
from npi_core.project.domain import (
    CreateProjectCommand,
    GateDefinition,
    InMemoryProjectStore,
    ProjectInstantiationService,
    ProjectTemplateVersion,
    ProjectType,
)


GATE_TEMPLATE_ID = UUID("27a34964-9987-4e3c-b010-2e5165782c62")
PROJECT_TEMPLATE_ID = UUID("2f4d63bf-4d51-4a17-aeb1-08116cb129fa")
SNAPSHOT_HASH = "a" * 64


def requirement(
    key: str = "technical_input",
    *,
    title: str = "Technical input",
) -> GateRequirementDefinition:
    return GateRequirementDefinition(
        key=key,
        title=title,
        classification=GateRequirementClassification.REQUIRED,
        priority=GateRequirementPriority.P0,
        allowed_evidence_kinds=(
            EvidenceKind.FILE_REVISION,
            EvidenceKind.WBS_ITEM,
        ),
    )


def gate_template_draft(
    *,
    requirements: tuple[GateRequirementDefinition, ...] | None = None,
) -> GateTemplateVersion:
    return GateTemplateVersion.create_draft(
        gate_template_global_id=GATE_TEMPLATE_ID,
        gate_template_code="SYNTHETIC-G0",
        gate_template_version=1,
        title="Synthetic feasibility Gate",
        applicable_project_types=(
            ProjectType.NEW_TOOL,
            ProjectType.CUSTOMER_OWNED_TOOL,
        ),
        requirements=(
            (
                requirement(),
                requirement("review_record", title="Review record"),
            )
            if requirements is None
            else requirements
        ),
    )


def project_template(gate: GateDefinition) -> ProjectTemplateVersion:
    return ProjectTemplateVersion.create_draft(
        template_global_id=PROJECT_TEMPLATE_ID,
        template_code="SYNTHETIC-P4-TEST",
        template_version=1,
        title="Synthetic Project Template",
        applicable_project_types=(ProjectType.NEW_TOOL,),
        gates=(gate,),
    )


class GateTemplateDomainTest(unittest.TestCase):
    def test_publish_freezes_ordered_canonical_requirements_and_exact_hash(
        self,
    ) -> None:
        published = gate_template_draft().publish(expected_version=1)
        snapshot = published.snapshot()

        self.assertEqual(
            [value.key for value in snapshot.requirements],
            ["technical_input", "review_record"],
        )
        self.assertEqual(
            snapshot.requirements[0].canonical_dict(),
            {
                "key": "technical_input",
                "title": "Technical input",
                "classification": "required",
                "priority": "P0",
                "allowedEvidenceKinds": [
                    "file_revision",
                    "wbs_item",
                ],
            },
        )
        encoded = json.dumps(
            snapshot.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.assertEqual(
            snapshot.snapshot_hash,
            hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        )

    def test_published_version_is_immutable_and_revision_preserves_history(
        self,
    ) -> None:
        published = gate_template_draft().publish(expected_version=1)
        with self.assertRaises(FrozenInstanceError):
            published.title = "Changed"  # type: ignore[misc]
        with self.assertRaises(PublishedGateTemplateImmutable):
            published.edit_draft(
                expected_version=published.version,
                title="Changed",
            )

        revision = published.next_draft()
        self.assertEqual(revision.gate_template_global_id, GATE_TEMPLATE_ID)
        self.assertEqual(revision.gate_template_version, 2)
        self.assertNotEqual(revision.global_id, published.global_id)
        self.assertEqual(revision.requirements, published.requirements)

    def test_publication_rejects_missing_or_ambiguous_requirements(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            gate_template_draft(requirements=()).publish(expected_version=1)
        with self.assertRaises(RequestValidationFailed):
            gate_template_draft(
                requirements=(
                    requirement("Input"),
                    requirement("input"),
                )
            )
        with self.assertRaises(RequestValidationFailed):
            GateRequirementDefinition(
                key="input",
                title="Input",
                classification=GateRequirementClassification.REQUIRED,
                priority=GateRequirementPriority.P0,
                allowed_evidence_kinds=(),
            )
        with self.assertRaises(RequestValidationFailed):
            GateRequirementDefinition(
                key="input",
                title="Input",
                classification=GateRequirementClassification.REQUIRED,
                priority=GateRequirementPriority.P0,
                allowed_evidence_kinds=(
                    EvidenceKind.WBS_ITEM,
                    EvidenceKind.WBS_ITEM,
                ),
            )

    def test_template_rejects_unfreezable_requirement_count_and_evidence_kind(
        self,
    ) -> None:
        with self.assertRaises(RequestValidationFailed):
            gate_template_draft(
                requirements=tuple(
                    requirement(f"requirement_{index}") for index in range(501)
                )
            )
        with self.assertRaises(RequestValidationFailed):
            gate_template_draft(
                requirements=(
                    GateRequirementDefinition(
                        key="document",
                        title="Document",
                        classification=GateRequirementClassification.REQUIRED,
                        priority=GateRequirementPriority.P0,
                        allowed_evidence_kinds=(EvidenceKind.DOCUMENT_REVISION,),
                    ),
                )
            ).publish(expected_version=1)

        baseline_template = gate_template_draft(
            requirements=(
                GateRequirementDefinition(
                    key="release_package",
                    title="Release package",
                    classification=GateRequirementClassification.REQUIRED,
                    priority=GateRequirementPriority.P0,
                    allowed_evidence_kinds=(EvidenceKind.RELEASE_BASELINE,),
                ),
            )
        ).publish(expected_version=1)
        self.assertEqual(
            baseline_template.snapshot().requirements[0].canonical_dict()[
                "allowedEvidenceKinds"
            ],
            ["release_baseline"],
        )

    def test_legacy_project_template_hash_and_payload_remain_byte_compatible(
        self,
    ) -> None:
        legacy = project_template(GateDefinition("G0", "Feasibility", 1))
        legacy_payload = {
            "templateGlobalId": str(PROJECT_TEMPLATE_ID),
            "templateCode": "SYNTHETIC-P4-TEST",
            "templateVersion": 1,
            "applicableProjectTypes": ["new_tool"],
            "referenceRules": [],
            "gates": [
                {
                    "key": "G0",
                    "title": "Feasibility",
                    "sequence": 1,
                }
            ],
        }
        encoded = json.dumps(
            legacy_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.assertEqual(
            legacy.snapshot_hash,
            hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            legacy.gates[0].canonical_dict(),
            legacy_payload["gates"][0],
        )

    def test_configured_project_gate_uses_exact_ref_without_legacy_empty_fields(
        self,
    ) -> None:
        configured = GateDefinition(
            "G0",
            "Feasibility",
            1,
            gate_template_global_id=GATE_TEMPLATE_ID,
            gate_template_version=1,
            gate_template_snapshot_hash=SNAPSHOT_HASH,
        )
        self.assertEqual(
            configured.canonical_dict(),
            {
                "key": "G0",
                "title": "Feasibility",
                "sequence": 1,
                "gateTemplateRef": {
                    "globalId": str(GATE_TEMPLATE_ID),
                    "version": 1,
                    "snapshotHash": SNAPSHOT_HASH,
                },
            },
        )
        with self.assertRaises(RequestValidationFailed):
            GateDefinition(
                "G0",
                "Feasibility",
                1,
                gate_template_global_id=GATE_TEMPLATE_ID,
            )
        with self.assertRaises(RequestValidationFailed):
            GateDefinition(
                "G0",
                "Feasibility",
                1,
                gate_template_global_id=GATE_TEMPLATE_ID,
                gate_template_version=1,
                gate_template_snapshot_hash="A" * 64,
            )

    def test_project_instantiation_freezes_exact_gate_template_ref(self) -> None:
        gate = GateDefinition(
            "G0",
            "Feasibility",
            1,
            gate_template_global_id=GATE_TEMPLATE_ID,
            gate_template_version=1,
            gate_template_snapshot_hash=SNAPSHOT_HASH,
        )
        template = project_template(gate).publish(expected_version=1)
        store = InMemoryProjectStore()
        store.add_template_version(template)

        result = ProjectInstantiationService(store).instantiate(
            CreateProjectCommand(
                idempotency_key="p403-gate-template-ref",
                tenant_id="TENANT-A",
                business_code="P403-REF-001",
                title="Configured Gate Template Project",
                project_type=ProjectType.NEW_TOOL,
                owner_user_id="owner@example.invalid",
                target_sop=date(2027, 6, 30),
                template_global_id=template.template_global_id,
                template_version=template.template_version,
                expected_version=template.version,
                references=(),
            )
        )

        shell = result.gates[0]
        self.assertEqual(shell.gate_template_global_id, GATE_TEMPLATE_ID)
        self.assertEqual(shell.gate_template_version, 1)
        self.assertEqual(shell.gate_template_snapshot_hash, SNAPSHOT_HASH)
        self.assertEqual(
            shell.template_gate_definition.canonical_dict(), gate.canonical_dict()
        )

    def test_legacy_project_instantiation_keeps_gate_template_ref_empty(self) -> None:
        template = project_template(GateDefinition("G0", "Feasibility", 1)).publish(
            expected_version=1
        )
        store = InMemoryProjectStore()
        store.add_template_version(template)

        result = ProjectInstantiationService(store).instantiate(
            CreateProjectCommand(
                idempotency_key="p403-legacy-gate-ref",
                tenant_id="TENANT-A",
                business_code="P403-LEGACY-001",
                title="Legacy Gate Template Project",
                project_type=ProjectType.NEW_TOOL,
                owner_user_id="owner@example.invalid",
                target_sop=date(2027, 6, 30),
                template_global_id=template.template_global_id,
                template_version=template.template_version,
                expected_version=template.version,
                references=(),
            )
        )

        shell = result.gates[0]
        self.assertIsNone(shell.gate_template_global_id)
        self.assertEqual(
            shell.template_gate_definition.canonical_dict(),
            {"key": "G0", "title": "Feasibility", "sequence": 1},
        )


if __name__ == "__main__":
    unittest.main()
