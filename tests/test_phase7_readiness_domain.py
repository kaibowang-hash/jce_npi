from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID, uuid5

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.project.domain import ProjectType
from npi_core.readiness.domain import (
    ReadinessApplicabilitySelector,
    ReadinessBlockingLevel,
    ReadinessCategoryDefinition,
    ReadinessCompletionRule,
    ReadinessEvidenceRequirement,
    ReadinessExactReference,
    ReadinessGateReference,
    ReadinessItemDefinition,
    ReadinessItemSnapshot,
    ReadinessItemState,
    ReadinessMemberReference,
    ReadinessProjectSnapshot,
    ReadinessPublicationState,
    ReadinessSourceKind,
    ReadinessSourceReference,
    ReadinessSourceState,
    ReadinessTemplateImmutable,
    ReadinessTemplateVersion,
    ReadinessVersionConflict,
    initialize_readiness_instance,
    instance_from_snapshot,
    revise_readiness_item,
    template_from_snapshot,
    validate_readiness_successor,
)


def uid(value: int) -> UUID:
    return UUID(int=value)


NOW = datetime(2026, 8, 11, 13, 0, tzinfo=UTC)
TEMPLATE_ID = uid(1)
PROJECT_ID = uid(2)
INSTANCE_ID = uid(3)
MEMBER = ReadinessMemberReference(uid(4), "owner@example.invalid", 2)
GATE_G6 = ReadinessGateReference(uid(5), "G6", 3, "6" * 64)
GATE_G7 = ReadinessGateReference(uid(6), "G7", 4, "7" * 64)
PROJECT = ReadinessProjectSnapshot(
    PROJECT_ID,
    5,
    "1" * 64,
    ProjectType.NEW_TOOL,
    ("ERPNEXT:CUST-001",),
    "automotive",
)


def applicability(*, industries: tuple[str, ...] = ()) -> ReadinessApplicabilitySelector:
    return ReadinessApplicabilitySelector(
        project_types=(ProjectType.NEW_TOOL,),
        customer_reference_keys=("ERPNEXT:CUST-001",),
        industry_keys=industries,
    )


def requirement(
    key: str,
    kind: ReadinessSourceKind,
    *,
    unavailable_blocks: bool = False,
) -> ReadinessEvidenceRequirement:
    return ReadinessEvidenceRequirement(
        key,
        (kind,),
        unavailable_blocks=unavailable_blocks,
    )


def item(
    key: str,
    weight: int,
    *,
    blocking: ReadinessBlockingLevel,
    gate: str,
    rule: ReadinessCompletionRule = ReadinessCompletionRule.CONFIRMATION,
    requirements: tuple[ReadinessEvidenceRequirement, ...] = (),
    industries: tuple[str, ...] = (),
) -> ReadinessItemDefinition:
    return ReadinessItemDefinition(
        key=key,
        title=key.replace("_", " ").title(),
        category_key="launch",
        weight=weight,
        required=True,
        blocking_level=blocking,
        gate_key=gate,
        completion_rule=rule,
        applicability=applicability(industries=industries),
        evidence_requirements=requirements,
    )


def draft() -> ReadinessTemplateVersion:
    return ReadinessTemplateVersion.create_draft(
        template_global_id=TEMPLATE_ID,
        template_code="NPI-AUTO",
        template_version=1,
        title="Automotive NPI readiness",
        applicability=applicability(),
        categories=(ReadinessCategoryDefinition("launch", "Launch readiness"),),
        items=(
            item(
                "released_documents",
                99,
                blocking=ReadinessBlockingLevel.P1,
                gate="G6",
                rule=ReadinessCompletionRule.EXACT_EVIDENCE,
                requirements=(requirement("release", ReadinessSourceKind.RELEASED_DOCUMENT),),
            ),
            item(
                "formal_quality",
                1,
                blocking=ReadinessBlockingLevel.P0,
                gate="G6",
                rule=ReadinessCompletionRule.EXACT_SOURCE_RESULT,
                requirements=(
                    ReadinessEvidenceRequirement(
                        "quality",
                        (ReadinessSourceKind.ERP_QUALITY_RESULT,),
                        unavailable_blocks=True,
                    ),
                ),
            ),
            item(
                "ppap",
                10,
                blocking=ReadinessBlockingLevel.P1,
                gate="G7",
                industries=("automotive",),
            ),
        ),
        changed_by_user_id="admin@example.invalid",
        changed_at=NOW,
        request_id=uid(7),
        trace_id="trace-p705-template",
    )


def published() -> ReadinessTemplateVersion:
    return draft().publish(
        expected_version=1,
        changed_by_user_id="admin@example.invalid",
        changed_at=NOW,
        request_id=uid(8),
        trace_id="trace-p705-publish",
    )


def instance():
    return initialize_readiness_instance(
        global_id=uid(9),
        instance_global_id=INSTANCE_ID,
        tenant_id="tenant-a",
        project=PROJECT,
        template=published(),
        gates={"G6": GATE_G6, "G7": GATE_G7},
        assignments={
            "released_documents": (MEMBER, date(2026, 9, 1)),
            "formal_quality": (MEMBER, date(2026, 9, 2)),
            "ppap": (MEMBER, date(2026, 9, 3)),
        },
        created_by_user_id="admin@example.invalid",
        created_at=NOW,
        request_id=uid(10),
        trace_id="trace-p705-instance",
    )


def exact_source(
    requirement_key: str,
    kind: ReadinessSourceKind,
    source_id: int,
    *,
    state: ReadinessSourceState = ReadinessSourceState.SATISFIED,
) -> ReadinessSourceReference:
    return ReadinessSourceReference(
        requirement_key=requirement_key,
        kind=kind,
        state=state,
        global_id=uid(source_id),
        source_version=2,
        snapshot_hash=str(source_id % 10) * 64,
    )


class Phase7ReadinessDomainTest(unittest.TestCase):
    def test_published_template_round_trip_is_exact_and_immutable(self) -> None:
        value = published()
        self.assertEqual(template_from_snapshot(value.snapshot_payload()), value)
        self.assertEqual(value.publication_state, ReadinessPublicationState.PUBLISHED)
        self.assertEqual(value.global_id, uuid5(TEMPLATE_ID, "npi-readiness-template-version:1"))
        with self.assertRaises(ReadinessTemplateImmutable):
            value.edit_draft(expected_version=2, title="Changed")

    def test_draft_edit_requires_exact_optimistic_version(self) -> None:
        value = draft().edit_draft(
            expected_version=1,
            title="Revised title",
            changed_by_user_id="admin@example.invalid",
            changed_at=NOW,
            request_id=uid(11),
            trace_id="trace-edit",
        )
        self.assertEqual(value.optimistic_version, 2)
        with self.assertRaises(ReadinessVersionConflict):
            value.edit_draft(expected_version=1, title="Stale")

    def test_industry_deliverable_is_configured_and_derived(self) -> None:
        value = published()
        ppap = next(row for row in value.items if row.key == "ppap")
        self.assertTrue(ppap.applicability.applies_to(PROJECT))
        other = replace(PROJECT, industry_key="medical")
        self.assertFalse(ppap.applicability.applies_to(other))

    def test_instance_freezes_exact_template_project_gate_and_item_ids(self) -> None:
        value = instance()
        self.assertEqual(value.template_revision, ReadinessExactReference(published().global_id, 1, published().snapshot_hash))
        self.assertEqual(
            value.items[0].global_id,
            uuid5(INSTANCE_ID, "npi-readiness-item:released_documents"),
        )
        self.assertEqual(instance_from_snapshot(value.snapshot_payload()), value)

    def test_instance_accepts_the_configured_site_tenant_vocabulary(self) -> None:
        value = replace(instance(), tenant_id="tenant/site@example.invalid")
        self.assertEqual(value.tenant_id, "tenant/site@example.invalid")

    def test_high_percentage_never_hides_incomplete_p0_blocker(self) -> None:
        current = instance()
        successor = revise_readiness_item(
            current,
            global_id=uid(12),
            expected_instance_version=1,
            item_key="released_documents",
            owner=MEMBER,
            due_date=date(2026, 9, 1),
            state=ReadinessItemState.COMPLETE,
            confirmation_value=None,
            sources=(exact_source("release", ReadinessSourceKind.RELEASED_DOCUMENT, 21),),
            created_by_user_id="owner@example.invalid",
            created_at=NOW,
            request_id=uid(13),
            trace_id="trace-complete-docs",
        )
        evaluation = successor.evaluation
        self.assertEqual(evaluation.total_score.basis_points, 9000)
        self.assertFalse(evaluation.ready)
        self.assertIn("incomplete_p0", {row.code.value for row in evaluation.blockers})

    def test_unavailable_formal_source_is_identity_free_and_dominant(self) -> None:
        unavailable = ReadinessSourceReference(
            requirement_key="quality",
            kind=ReadinessSourceKind.ERP_QUALITY_RESULT,
            state=ReadinessSourceState.UNAVAILABLE,
            global_id=None,
            source_version=None,
            snapshot_hash=None,
            reason_code="erp_quality_provider_unavailable",
        )
        successor = revise_readiness_item(
            instance(),
            global_id=uid(14),
            expected_instance_version=1,
            item_key="formal_quality",
            owner=MEMBER,
            due_date=date(2026, 9, 2),
            state=ReadinessItemState.IN_PROGRESS,
            confirmation_value=None,
            sources=(unavailable,),
            created_by_user_id="owner@example.invalid",
            created_at=NOW,
            request_id=uid(15),
            trace_id="trace-unavailable-quality",
        )
        codes = {row.code.value for row in successor.evaluation.blockers}
        self.assertEqual(codes, {"incomplete_p0", "required_source_unavailable"})
        self.assertIsNone(unavailable.global_id)

    def test_failed_quality_blocks_even_when_configured_below_p0(self) -> None:
        current = instance()
        selected = current.items[1]
        for index, kind in enumerate(
            (
                ReadinessSourceKind.TRIAL_CAVITY_RESULT,
                ReadinessSourceKind.TRIAL_DEFECT,
                ReadinessSourceKind.TRIAL_DEFECT_VERIFICATION,
            ),
            start=22,
        ):
            with self.subTest(kind=kind):
                quality_requirement = replace(
                    selected.definition.evidence_requirements[0],
                    accepted_source_kinds=(kind,),
                )
                definition = replace(
                    selected.definition,
                    blocking_level=ReadinessBlockingLevel.P1,
                    evidence_requirements=(quality_requirement,),
                )
                failed = replace(
                    selected,
                    definition=definition,
                    state=ReadinessItemState.FAILED,
                    sources=(
                        exact_source(
                            "quality",
                            kind,
                            index,
                            state=ReadinessSourceState.FAILED,
                        ),
                    ),
                )
                manual = replace(
                    current,
                    items=(current.items[0], failed, current.items[2]),
                )
                self.assertIn(
                    "failed_mandatory_quality",
                    {row.code.value for row in manual.evaluation.blockers},
                )

    def test_complete_state_requires_exact_evidence(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            revise_readiness_item(
                instance(),
                global_id=uid(16),
                expected_instance_version=1,
                item_key="formal_quality",
                owner=MEMBER,
                due_date=date(2026, 9, 2),
                state=ReadinessItemState.COMPLETE,
                confirmation_value=None,
                sources=(),
                created_by_user_id="owner@example.invalid",
                created_at=NOW,
                request_id=uid(17),
                trace_id="trace-unsafe-complete",
            )

    def test_disallowed_source_kind_cannot_suppress_an_unavailable_blocker(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            revise_readiness_item(
                instance(),
                global_id=uid(23),
                expected_instance_version=1,
                item_key="formal_quality",
                owner=MEMBER,
                due_date=date(2026, 9, 2),
                state=ReadinessItemState.IN_PROGRESS,
                confirmation_value=None,
                sources=(
                    exact_source(
                        "quality",
                        ReadinessSourceKind.RELEASED_DOCUMENT,
                        24,
                    ),
                ),
                created_by_user_id="owner@example.invalid",
                created_at=NOW,
                request_id=uid(25),
                trace_id="trace-disallowed-source-kind",
            )

    def test_evidence_existence_cannot_be_configured_as_source_result_approval(self) -> None:
        for kind in (
            ReadinessSourceKind.RELEASED_DOCUMENT,
            ReadinessSourceKind.CONTROLLED_QUALITY_RESULT,
        ):
            with self.subTest(kind=kind), self.assertRaises(RequestValidationFailed):
                item(
                    "unsafe_report_approval",
                    10,
                    blocking=ReadinessBlockingLevel.P0,
                    gate="G6",
                    rule=ReadinessCompletionRule.EXACT_SOURCE_RESULT,
                    requirements=(requirement("report", kind),),
                )

        evidence = item(
            "controlled_report_evidence",
            10,
            blocking=ReadinessBlockingLevel.P1,
            gate="G6",
            rule=ReadinessCompletionRule.EXACT_EVIDENCE,
            requirements=(
                requirement(
                    "report", ReadinessSourceKind.CONTROLLED_QUALITY_RESULT
                ),
            ),
        )
        self.assertIs(evidence.completion_rule, ReadinessCompletionRule.EXACT_EVIDENCE)

    def test_successor_changes_exactly_one_item_and_preserves_policy(self) -> None:
        current = instance()
        successor = revise_readiness_item(
            current,
            global_id=uid(18),
            expected_instance_version=1,
            item_key="ppap",
            owner=MEMBER,
            due_date=date(2026, 9, 3),
            state=ReadinessItemState.COMPLETE,
            confirmation_value="PPAP applicability confirmed",
            sources=(),
            created_by_user_id="owner@example.invalid",
            created_at=NOW,
            request_id=uid(19),
            trace_id="trace-ppap",
        )
        validate_readiness_successor(current, successor)
        self.assertEqual(successor.predecessor_snapshot_hash, current.snapshot_hash)
        self.assertEqual(successor.items[2].item_version, 2)

    def test_tampered_derived_score_is_rejected_on_replay(self) -> None:
        payload = copy.deepcopy(instance().snapshot_payload())
        payload["evaluation"]["totalScore"]["basisPoints"] = 10_000
        with self.assertRaises(RequestValidationFailed):
            instance_from_snapshot(payload)

    def test_external_unavailable_cannot_claim_fake_identity(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ReadinessSourceReference(
                requirement_key="quality",
                kind=ReadinessSourceKind.ERP_QUALITY_RESULT,
                state=ReadinessSourceState.UNAVAILABLE,
                global_id=uid(20),
                source_version=1,
                snapshot_hash="a" * 64,
                reason_code="provider_unavailable",
            )

    def test_non_applicable_item_cannot_be_used_to_suppress_a_blocker(self) -> None:
        selected = instance().items[1]
        with self.assertRaises(RequestValidationFailed):
            ReadinessItemSnapshot(
                global_id=selected.global_id,
                item_version=selected.item_version,
                definition=selected.definition,
                applicable=True,
                gate=selected.gate,
                owner=selected.owner,
                due_date=selected.due_date,
                state=ReadinessItemState.NOT_APPLICABLE,
                confirmation_value=None,
                sources=(),
            )


if __name__ == "__main__":
    unittest.main()
