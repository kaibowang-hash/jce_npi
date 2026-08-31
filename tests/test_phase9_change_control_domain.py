from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.change_control.domain import (
    FORMAL_CHANGE_DOCTYPE,
    AffectedObjectKind,
    AffectedObjectVersion,
    ClosureEvidence,
    CostSummary,
    DispositionDecision,
    DispositionKind,
    DispositionScope,
    EffectivityKind,
    EffectivityRule,
    EngineeringChangeEvent,
    EngineeringChangeEventType,
    EngineeringChangeRevision,
    EngineeringChangeState,
    FormalChangeObservation,
    ImpactAssessment,
    ImpactCategory,
    ImpactConclusion,
    ImplementationTaskKind,
    ImplementationTaskLink,
    RevalidationKind,
    RevalidationRequirement,
    RevalidationState,
    sha256_json,
)
from npi_core.foundation.errors import RequestValidationFailed


def uid(value: int) -> UUID:
    return UUID(int=value)


NOW = datetime(2026, 8, 31, 8, 30, tzinfo=UTC)


def impacts(*, affected: ImpactCategory = ImpactCategory.PRODUCT) -> tuple[ImpactAssessment, ...]:
    return tuple(
        ImpactAssessment(
            category=category,
            conclusion=(
                ImpactConclusion.AFFECTED
                if category is affected
                else ImpactConclusion.NOT_AFFECTED
            ),
            responsible_user_id=f"{category.value}@example.invalid",
            rationale=f"Assessed {category.value}",
            evidence_reference_global_ids=(uid(100 + index),),
        )
        for index, category in enumerate(ImpactCategory)
    )


def formal() -> FormalChangeObservation:
    return FormalChangeObservation(
        document_name="ECR-2026-00001",
        raw_status="Effective",
        source_version="2026-08-31T08:00:00Z",
        source_modified_at=NOW,
        source_hash="a" * 64,
        observed_at=NOW,
    )


def revision(
    *,
    state: EngineeringChangeState = EngineeringChangeState.ACTIVE,
    closeable: bool = False,
) -> EngineeringChangeRevision:
    evidence = ClosureEvidence(
        new_versions_released=closeable,
        erp_update_observed=closeable,
        old_versions_withdrawn=closeable,
        effectivity_validated=closeable,
        dispositions_executed=closeable,
        evidence_reference_global_ids=(uid(501),),
    )
    revalidation = RevalidationRequirement(
        kind=RevalidationKind.FAI,
        state=(RevalidationState.SATISFIED if closeable else RevalidationState.IN_PROGRESS),
        responsible_user_id="quality@example.invalid",
        work_item_global_id=uid(401),
        evidence_reference_global_ids=((uid(402),) if closeable else ()),
    )
    return EngineeringChangeRevision(
        global_id=uid(1),
        change_global_id=uid(2),
        tenant_id="tenant-a",
        project_global_id=uid(3),
        revision=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        state=state,
        title="Customer drawing change",
        reason="Initial impact assessment",
        formal_change=formal(),
        impact_assessments=impacts(),
        affected_objects=(
            AffectedObjectVersion(
                category=ImpactCategory.PRODUCT,
                kind=AffectedObjectKind.ENGINEERING_PART_REVISION,
                object_global_id=uid(201),
                prior_version_global_id=uid(202),
                prior_snapshot_hash="b" * 64,
                successor_version_global_id=uid(203),
                successor_snapshot_hash="c" * 64,
            ),
        ),
        implementation_tasks=(
            ImplementationTaskLink(
                kind=ImplementationTaskKind.DESIGN,
                work_item_global_id=uid(301),
                purpose="Release the successor drawing",
            ),
        ),
        effectivity_rules=(
            EffectivityRule(
                kind=EffectivityKind.DATE,
                effective_date=date(2026, 9, 15),
                validation_evidence_global_id=(uid(302) if closeable else None),
            ),
        ),
        dispositions=(
            DispositionDecision(
                scope=DispositionScope.OLD_INVENTORY,
                decision=DispositionKind.REWORK,
                approved_by_user_id="approver@example.invalid",
                approval_evidence_global_id=uid(303),
                execution_evidence_global_id=(uid(304) if closeable else None),
            ),
        ),
        revalidation_requirements=(revalidation,),
        cost_summary=CostSummary(
            currency="CNY",
            engineering_cost=Decimal("1200.00"),
            tooling_cost=Decimal("300"),
            scrap_cost=Decimal("50"),
            logistics_cost=Decimal("25"),
            downtime_minutes=45,
            delivery_impact_days=2,
        ),
        closure_evidence=evidence,
        created_by_user_id="owner@example.invalid",
        created_at=NOW,
        request_id=uid(4),
        trace_id="trace-p9-change-1",
    )


class Phase9ChangeControlDomainTest(unittest.TestCase):
    def test_revision_is_canonical_and_preserves_exact_ownership_boundaries(self) -> None:
        value = revision()
        payload = value.revision_payload()
        self.assertEqual(payload["formalChange"]["doctype"], FORMAL_CHANGE_DOCTYPE)
        self.assertEqual(payload["formalChange"]["rawStatus"], "Effective")
        self.assertEqual(len(payload["impactAssessments"]), 12)
        self.assertEqual(payload["affectedObjects"][0]["priorSnapshotHash"], "b" * 64)
        self.assertEqual(payload["implementationTasks"][0]["workItemGlobalId"], str(uid(301)))
        self.assertEqual(value.snapshot_hash, sha256_json(payload))
        self.assertEqual(
            value.version_key_hash,
            sha256_json(
                {
                    "changeGlobalId": str(value.change_global_id),
                    "revision": 1,
                    "tenantId": value.tenant_id,
                }
            ),
        )
        self.assertFalse(value.ready_to_close)

    def test_every_required_impact_category_is_present_once_with_responsibility(self) -> None:
        value = revision()
        self.assertEqual(
            {item.category for item in value.impact_assessments},
            set(ImpactCategory),
        )
        with self.assertRaises(RequestValidationFailed):
            replace(value, impact_assessments=value.impact_assessments[:-1])
        with self.assertRaises(RequestValidationFailed):
            replace(
                value,
                impact_assessments=value.impact_assessments[:-1]
                + (value.impact_assessments[0],),
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                value.impact_assessments[0],
                responsible_user_id="not-an-actor",
            )

    def test_affected_objects_require_exact_old_or_new_versions_and_affected_category(self) -> None:
        current = revision().affected_objects[0]
        with self.assertRaises(RequestValidationFailed):
            replace(
                current,
                prior_version_global_id=None,
                prior_snapshot_hash=None,
                successor_version_global_id=None,
                successor_snapshot_hash=None,
            )
        with self.assertRaises(RequestValidationFailed):
            replace(current, prior_snapshot_hash=None)
        with self.assertRaises(RequestValidationFailed):
            replace(
                revision(),
                impact_assessments=impacts(affected=ImpactCategory.DRAWING),
            )

    def test_addition_and_withdrawal_are_explicit_version_shapes(self) -> None:
        addition = replace(
            revision().affected_objects[0],
            prior_version_global_id=None,
            prior_snapshot_hash=None,
        )
        withdrawal = replace(
            revision().affected_objects[0],
            successor_version_global_id=None,
            successor_snapshot_hash=None,
        )
        self.assertIsNone(addition.payload()["priorVersionGlobalId"])
        self.assertIsNone(withdrawal.payload()["successorVersionGlobalId"])

    def test_effectivity_kinds_are_closed_and_shape_specific(self) -> None:
        date_rule = revision().effectivity_rules[0]
        self.assertEqual(date_rule.payload()["effectiveDate"], "2026-09-15")
        order_rule = EffectivityRule(
            kind=EffectivityKind.ORDER,
            selector_reference="SO-2026-0001",
        )
        self.assertEqual(order_rule.payload()["selectorReference"], "SO-2026-0001")
        with self.assertRaises(RequestValidationFailed):
            EffectivityRule(kind=EffectivityKind.DATE, selector_reference="wrong")
        with self.assertRaises(RequestValidationFailed):
            EffectivityRule(
                kind=EffectivityKind.BATCH,
                effective_date=date(2026, 9, 1),
            )

    def test_disposition_requires_approval_and_keeps_execution_separate(self) -> None:
        value = revision().dispositions[0]
        self.assertIsNone(value.execution_evidence_global_id)
        self.assertEqual(value.payload()["decision"], "rework")
        with self.assertRaises(RequestValidationFailed):
            replace(value, approved_by_user_id="")

    def test_revalidation_satisfied_and_waived_states_fail_closed_without_evidence(self) -> None:
        current = revision().revalidation_requirements[0]
        with self.assertRaises(RequestValidationFailed):
            replace(current, state=RevalidationState.SATISFIED)
        with self.assertRaises(RequestValidationFailed):
            replace(current, state=RevalidationState.WAIVED)
        waived = replace(
            current,
            state=RevalidationState.WAIVED,
            evidence_reference_global_ids=(uid(405),),
            waiver_approval_global_id=uid(406),
        )
        self.assertTrue(waived.complete)
        self.assertEqual(waived.payload()["waiverApprovalGlobalId"], str(uid(406)))

    def test_cost_summary_is_nonnegative_and_canonical(self) -> None:
        value = revision().cost_summary
        self.assertEqual(value.payload()["engineeringCost"], "1200")
        with self.assertRaises(RequestValidationFailed):
            replace(value, scrap_cost=Decimal("-0.01"))
        with self.assertRaises(RequestValidationFailed):
            replace(value, currency="CNYX")

    def test_ready_to_close_requires_all_explicit_checks(self) -> None:
        ready = revision(state=EngineeringChangeState.READY_TO_CLOSE, closeable=True)
        self.assertTrue(ready.ready_to_close)
        closed = replace(ready, state=EngineeringChangeState.CLOSED)
        self.assertTrue(closed.ready_to_close)
        with self.assertRaises(RequestValidationFailed):
            revision(state=EngineeringChangeState.CLOSED, closeable=False)
        with self.assertRaises(RequestValidationFailed):
            replace(
                ready,
                closure_evidence=replace(
                    ready.closure_evidence,
                    old_versions_withdrawn=False,
                ),
            )

    def test_successor_binds_exact_predecessor_and_increments_revision(self) -> None:
        first = revision()
        second = first.successor(
            global_id=uid(9),
            reason="Add validated effectivity evidence",
            created_by_user_id="owner@example.invalid",
            created_at=NOW,
            request_id=uid(10),
            trace_id="trace-p9-change-2",
        )
        self.assertEqual(second.revision, 2)
        self.assertEqual(second.predecessor_global_id, first.global_id)
        self.assertEqual(second.predecessor_snapshot_hash, first.snapshot_hash)
        self.assertNotEqual(second.snapshot_hash, first.snapshot_hash)

    def test_first_and_successor_predecessor_contracts_are_fail_closed(self) -> None:
        first = revision()
        with self.assertRaises(RequestValidationFailed):
            replace(first, predecessor_global_id=uid(80))
        with self.assertRaises(RequestValidationFailed):
            replace(first, revision=2)

    def test_formal_change_is_exactly_ecr_and_raw_status_is_not_interpreted(self) -> None:
        observation = formal()
        self.assertEqual(observation.doctype, FORMAL_CHANGE_DOCTYPE)
        self.assertEqual(observation.raw_status, "Effective")
        with self.assertRaises(RequestValidationFailed):
            replace(observation, doctype="Engineering Change Order")

    def test_event_is_append_only_canonical_evidence_shape(self) -> None:
        current = revision()
        event = EngineeringChangeEvent(
            global_id=uid(700),
            change_global_id=current.change_global_id,
            tenant_id=current.tenant_id,
            project_global_id=current.project_global_id,
            revision_global_id=current.global_id,
            revision=current.revision,
            revision_snapshot_hash=current.snapshot_hash,
            event_type=EngineeringChangeEventType.REVISED,
            actor_user_id="owner@example.invalid",
            occurred_at=NOW,
            request_id=uid(701),
            trace_id="trace-p9-event-1",
        )
        self.assertEqual(event.event_hash, sha256_json(event.event_payload()))
        self.assertEqual(event.event_payload()["eventType"], "revised")

    def test_boolean_decimal_hash_uuid_and_trace_validation_reject_ambiguous_values(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ClosureEvidence(1, True, True, True, True, (uid(1),))
        with self.assertRaises(RequestValidationFailed):
            replace(formal(), source_hash="A" * 64)
        with self.assertRaises(RequestValidationFailed):
            replace(revision(), global_id=UUID(int=0))
        with self.assertRaises(RequestValidationFailed):
            replace(revision(), trace_id="Trace With Spaces")

    def test_input_sequences_are_frozen_as_tuples_and_duplicates_are_rejected(self) -> None:
        value = revision()
        copied = copy.deepcopy(value.revision_payload())
        copied["impactAssessments"][0]["rationale"] = "mutated"
        self.assertNotEqual(sha256_json(copied), value.snapshot_hash)
        with self.assertRaises(RequestValidationFailed):
            replace(
                value,
                implementation_tasks=value.implementation_tasks * 2,
            )


if __name__ == "__main__":
    unittest.main()
