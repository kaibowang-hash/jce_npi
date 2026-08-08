from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.acceptance_domain import (
    ErpAssetMovementObservation,
    ErpAssetRepairObservation,
    ErpAssetSpareInventoryObservation,
    ToolingAcceptanceCategory,
    ToolingAcceptanceChecklistItem,
    ToolingAcceptanceEvidenceRevision,
    ToolingAcceptanceEvidenceRole,
    ToolingAcceptanceFileEvidence,
    ToolingAssetActionEvidence,
    ToolingAssetActionKind,
    ToolingAssetProjectionAvailable,
    ToolingAssetProjectionUnavailable,
    ToolingEvidenceDisposition,
    ToolingRepairEvidence,
    ToolingSpareKind,
    ToolingSpareRecommendation,
    acceptance_revision_from_snapshot,
    validate_acceptance_successor,
)
from npi_core.tooling.domain import ToolingRequirementKind
from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility


NOW = datetime(2026, 8, 8, 22, 30, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def uid(value: int) -> UUID:
    return UUID(int=value)


def member() -> ProjectMemberResponsibility:
    return ProjectMemberResponsibility(global_id=uid(10), user_id="owner@example.test", optimistic_version=3)


def evidence(value: int, role: ToolingAcceptanceEvidenceRole = ToolingAcceptanceEvidenceRole.CHECKLIST) -> ToolingAcceptanceFileEvidence:
    return ToolingAcceptanceFileEvidence(
        global_id=uid(100 + value),
        role=role,
        file_revision_global_id=uid(200 + value),
        file_optimistic_version=2,
        frappe_content_hash="d" * 40,
        file_name=f"synthetic-{value}.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256=HASH_A,
    )


def checklist() -> tuple[ToolingAcceptanceChecklistItem, ...]:
    return tuple(
        ToolingAcceptanceChecklistItem(
            global_id=uid(1_000 + index),
            category=category,
            requirement_key=f"synthetic-{category.value}",
            requirement_statement=f"Synthetic {category.value} evidence requirement",
            disposition=ToolingEvidenceDisposition.EVIDENCE_RECORDED,
            responsible_member=member(),
            evidence=(evidence(index),),
        )
        for index, category in enumerate(ToolingAcceptanceCategory, start=1)
    )


def acceptance(*, version: int = 1, predecessor=None, predecessor_hash=None, requirement_kind=ToolingRequirementKind.COPY_OR_ADDITIONAL_SET, repairs=()) -> ToolingAcceptanceEvidenceRevision:
    return ToolingAcceptanceEvidenceRevision(
        global_id=uid(400 + version),
        acceptance_global_id=uid(400),
        tenant_id="tenant-synthetic",
        project_global_id=uid(1),
        tooling_master_global_id=uid(2),
        tooling_master_snapshot_hash=HASH_A,
        tooling_set_global_id=uid(3),
        tooling_set_snapshot_hash=HASH_B,
        tooling_requirement_kind=requirement_kind,
        set_revision_binding_global_id=uid(4),
        set_revision_binding_snapshot_hash=HASH_C,
        tooling_revision_global_id=uid(5),
        tooling_revision_number=4,
        tooling_revision_snapshot_hash=HASH_A,
        acceptance_version=version,
        predecessor_global_id=predecessor,
        predecessor_snapshot_hash=predecessor_hash,
        checklist=checklist(),
        asset_actions=(),
        spare_recommendations=(),
        repairs=repairs,
        reason="Synthetic evidence revision",
        created_by_user_id="owner@example.test",
        created_at=NOW,
        request_id=uid(900 + version),
        trace_id=f"trace-{version}",
    )


class ToolingAcceptanceDomainTest(unittest.TestCase):
    def test_complete_evidence_round_trips_without_claiming_approval(self) -> None:
        value = acceptance()
        restored = acceptance_revision_from_snapshot(value.snapshot_payload())
        self.assertEqual(restored.snapshot_hash, value.snapshot_hash)
        public = value.public_dict()
        self.assertEqual(public["businessApproval"]["state"], "unavailable")
        self.assertEqual(len(public["categoryCoverage"]), 9)
        self.assertTrue(all(item["recordedCount"] == 1 for item in public["categoryCoverage"]))
        self.assertNotIn("accepted", json.dumps(public).lower())

    def test_every_frozen_category_is_required(self) -> None:
        value = acceptance()
        with self.assertRaises(RequestValidationFailed):
            replace(value, checklist=value.checklist[:-1])

    def test_disposition_rules_preserve_missing_and_not_applicable_truth(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(
                checklist()[0],
                disposition=ToolingEvidenceDisposition.EVIDENCE_MISSING,
            )
        item = replace(
            checklist()[0],
            disposition=ToolingEvidenceDisposition.NOT_APPLICABLE_ASSERTED,
            evidence=(),
            note="Not applicable to this synthetic Set",
        )
        self.assertEqual(item.snapshot_payload()["disposition"], "not_applicable_asserted")

    def test_customer_owned_repair_requires_customer_authorization_evidence(self) -> None:
        repair = ToolingRepairEvidence(
            global_id=uid(700),
            authorization_reference="CUSTOMER-AUTH-SYNTHETIC",
            quote_reference="QUOTE-SYNTHETIC",
            quote_currency="CNY",
            quote_amount="1000.00",
            responsible_member=member(),
            downtime_impact_hours="8",
            detail="Synthetic repair evidence",
            customer_authorization_evidence=(),
            verification_evidence=(),
        )
        with self.assertRaises(RequestValidationFailed):
            acceptance(
                requirement_kind=ToolingRequirementKind.CUSTOMER_OWNED_INTAKE,
                repairs=(repair,),
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                repair,
                customer_authorization_evidence=(evidence(90),),
            )
        authorized = replace(
            repair,
            customer_authorization_evidence=(
                evidence(90, ToolingAcceptanceEvidenceRole.CUSTOMER_AUTHORIZATION),
            ),
        )
        value = acceptance(
            requirement_kind=ToolingRequirementKind.CUSTOMER_OWNED_INTAKE,
            repairs=(authorized,),
        )
        self.assertEqual(len(value.repairs), 1)

    def test_asset_action_and_spare_are_npi_evidence_with_erp_truth_unavailable(self) -> None:
        action = ToolingAssetActionEvidence(
            global_id=uid(800),
            action_kind=ToolingAssetActionKind.LOAN,
            reason="Synthetic loan evidence",
            approval_reference="APPROVAL-EVIDENCE-SYNTHETIC",
            proposed_effective_date=date(2026, 9, 1),
            evidence=(evidence(95, ToolingAcceptanceEvidenceRole.APPROVAL_REFERENCE),),
        )
        spare = ToolingSpareRecommendation(
            global_id=uid(801),
            recommendation_key="wear-pin",
            kind=ToolingSpareKind.WEAR_PART,
            description="Synthetic wear pin",
            recommended_minimum_quantity="2.0",
            unit="EA",
        )
        self.assertEqual(action.snapshot_payload()["erpExecution"]["state"], "unavailable")
        self.assertEqual(spare.snapshot_payload()["formalItemAndInventory"]["state"], "unavailable")

    def test_successor_requires_exact_current_revision(self) -> None:
        current = acceptance()
        successor = acceptance(
            version=2,
            predecessor=current.global_id,
            predecessor_hash=current.snapshot_hash,
        )
        validate_acceptance_successor(current, successor)
        with self.assertRaises(RequestValidationFailed):
            validate_acceptance_successor(current, replace(successor, predecessor_snapshot_hash=HASH_B))
        with self.assertRaises(RequestValidationFailed):
            validate_acceptance_successor(
                current,
                replace(successor, tooling_revision_global_id=uid(50)),
            )

    def test_unavailable_and_future_available_erp_projection_are_read_only(self) -> None:
        unavailable = ToolingAssetProjectionUnavailable().public_dict()
        self.assertEqual(unavailable["sourceSystem"], "ERPNEXT")
        self.assertEqual(unavailable["editableIn"], "ERPNEXT")
        self.assertEqual(unavailable["state"], "unavailable")
        self.assertNotIn("shotCount", unavailable)

        projection = ToolingAssetProjectionAvailable(
            tooling_set_global_id=uid(3),
            mapping_version=1,
            formal_asset_id="ASSET-SYNTHETIC-001",
            target_version="v1",
            asset_state="active",
            current_location="Synthetic Warehouse",
            shot_count=12,
            expected_life_shots=100000,
            maintenance_due=date(2026, 12, 1),
            movements=(
                ErpAssetMovementObservation(
                    global_id=uid(901),
                    action_kind=ToolingAssetActionKind.MOVE,
                    from_location="A",
                    to_location="B",
                    occurred_at=NOW,
                    source_object_id="MOVE-SYNTHETIC-1",
                ),
            ),
            repairs=(
                ErpAssetRepairObservation(
                    global_id=uid(902),
                    summary="Synthetic repair",
                    downtime_hours="4",
                    completed_at=NOW,
                    source_object_id="REPAIR-SYNTHETIC-1",
                ),
            ),
            spares=(
                ErpAssetSpareInventoryObservation(
                    formal_item_id="ITEM-SYNTHETIC-1",
                    description="Synthetic spare",
                    stock_on_hand="2",
                    minimum_stock="1",
                    unit="EA",
                    supplier_id=None,
                ),
            ),
            observation_global_id=uid(903),
            observation_hash=HASH_C,
            observed_at=NOW,
        ).public_dict()
        self.assertEqual(projection["state"], "available")
        self.assertEqual(projection["formalAssetId"], "ASSET-SYNTHETIC-001")
        self.assertEqual(projection["mappingCardinality"], "zero_or_one_per_physical_set")


if __name__ == "__main__":
    unittest.main()
