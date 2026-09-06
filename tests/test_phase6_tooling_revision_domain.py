from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.revision_domain import (
    CavityMapping,
    CavityStructuralState,
    DocumentRevisionReference,
    ExternalIdentity,
    ExternalIdentityType,
    InsertApplicability,
    InsertValidationState,
    PartControlledSpecification,
    PartSpecificationItem,
    PartSpecificationKind,
    ToolingMeasurement,
    ToolingProcessChainRevision,
    ToolingProcessKind,
    ToolingProcessStep,
    ToolingRevision,
    ToolingSetRevisionBinding,
    ToolingSpecification,
    part_controlled_specification_from_snapshot,
    process_chain_revision_from_snapshot,
    set_revision_binding_from_snapshot,
    tooling_revision_from_snapshot,
    validate_process_chain_successor,
    validate_tooling_revision_successor,
)


TENANT = "tenant-a"
PROJECT = UUID("d60e1aef-9b53-486e-95b1-4136ef72fdc5")
MASTER = UUID("8b93b720-2455-44ac-900d-56841f17ad28")
REVISION_R1 = UUID("83c7ab50-7709-4550-bf8f-9bfe50bd8f50")
REVISION_R2 = UUID("6ca374ef-096b-4e38-bd7d-7b24e9be8794")
APPLICABILITY = UUID("72d34534-d806-4abd-b8d9-79a737bd1dc5")
PART = UUID("352f4488-4049-4e6b-94f7-15db16aa7959")
PART_R1 = UUID("b1de6219-09b8-460b-a578-a3edc3e719ff")
PART_R2 = UUID("4740d641-0a13-47a9-b026-6814245d698f")
NOW = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
REQUEST = UUID("c2f67034-f9e9-4e53-82f6-008bdf256a54")
HASH_A = "a" * 64
HASH_B = "b" * 64


def measurement(value: str = "12.50", unit: str = "mm") -> ToolingMeasurement:
    return ToolingMeasurement(value=value, unit=unit, source="Engineering specification")


def specification(*, cavity_count: int = 1) -> ToolingSpecification:
    return ToolingSpecification(
        tooling_type="Injection mold",
        mold_base_material="P20 steel",
        core_material="H13 steel",
        hardness=measurement("52", "HRC"),
        surface_treatment="Nitrided",
        cavity_count=cavity_count,
        hot_runner="Valve gate",
        length=measurement("600"),
        width=measurement("450"),
        height=measurement("520"),
        weight=measurement("950", "kg"),
        clamp_tonnage=measurement("450", "t"),
        tie_bar_spacing_x=measurement("700"),
        tie_bar_spacing_y=measurement("650"),
        injection_capacity=measurement("1800", "g"),
        machine_type="Hydraulic injection molding machine",
        target_cycle=measurement("38", "s"),
        target_life=measurement("500000", "cycles"),
        warranty="Twelve months from controlled acceptance.",
        customer_standard="Customer mold standard STD-001.",
        interface_requirement="EUROMAP-compatible connections.",
        spare_parts=("Ejector pin",),
        delivery_documents=("Material certificate", "Inspection report"),
    )


def cavity(
    *,
    global_id: UUID = UUID("51fed18b-34cb-46bf-a8c3-926bf33706c0"),
    identifier: str = "C01",
) -> CavityMapping:
    return CavityMapping(
        global_id=global_id,
        cavity_identifier=identifier,
        tooling_applicability_global_id=APPLICABILITY,
        part_revision_global_id=PART_R1,
        structural_state=CavityStructuralState.ENABLED,
    )


def insert(*, validated: bool = False) -> InsertApplicability:
    return InsertApplicability(
        global_id=UUID("bb4a328e-62b4-49ed-b90c-fb7ebd231a31"),
        insert_code="INS-A",
        insert_version=1,
        tooling_applicability_global_id=APPLICABILITY,
        part_revision_global_id=PART_R1,
        model_source_system="NPI_ONE",
        model_source_object_id="model-revision-1",
        changeover_duration=measurement("20", "min"),
        validation_state=(
            InsertValidationState.VALIDATED
            if validated
            else InsertValidationState.NOT_VALIDATED
        ),
        validated_by_user_id=("tooling.owner@example.invalid" if validated else None),
        validated_at=(NOW if validated else None),
        validation_reason=("Exact insert fit was verified." if validated else None),
    )


def external_identity() -> ExternalIdentity:
    return ExternalIdentity(
        global_id=UUID("e79e0fb8-9f49-4233-bf97-05fa7ce8cf96"),
        identity_type=ExternalIdentityType.CUSTOMER,
        value="CUSTOMER-MOLD-001",
        raw_value=" CUSTOMER-MOLD-001 ",
        source_system="ERPNEXT",
        source_object_id="ITEM-SYNTHETIC-001",
        effective_from=date(2026, 8, 7),
        effective_to=None,
    )


def tooling_revision(
    *,
    global_id: UUID = REVISION_R1,
    revision_number: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
    revision_cavities: tuple[CavityMapping, ...] | None = None,
) -> ToolingRevision:
    return ToolingRevision(
        global_id=global_id,
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        revision_number=revision_number,
        revision_label=f"R{revision_number}",
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        specification=specification(),
        cavities=revision_cavities or (cavity(),),
        inserts=(insert(validated=True),),
        external_identities=(external_identity(),),
        design_document_revisions=(
            DocumentRevisionReference(
                global_id=UUID("c0c321ad-038b-40bf-a8cb-8e81e839c066"),
                snapshot_hash=HASH_A,
            ),
        ),
        reason="Create exact controlled engineering revision.",
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p603-revision",
    )


def part_specification() -> PartControlledSpecification:
    return PartControlledSpecification(
        global_id=UUID("9f21ec33-e590-45b2-a158-a46d48bd15da"),
        tenant_id=TENANT,
        project_global_id=PROJECT,
        part_global_id=PART,
        part_revision_global_id=PART_R1,
        part_revision_snapshot_hash=HASH_A,
        items=(
            PartSpecificationItem(
                global_id=UUID("cd71bfc5-49d8-4ba1-bec8-a5f276107944"),
                kind=PartSpecificationKind.MATERIAL_FAMILY,
                normalized_value="PA66-GF30",
                raw_value="PA66 GF30",
                source_system="ERPNEXT",
                source_object_id="ITEM-SYNTHETIC-001",
                effective_from=date(2026, 8, 7),
                effective_to=None,
                unit=None,
            ),
        ),
        external_identities=(external_identity(),),
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p603-part-specification",
    )


def process_chain(
    *,
    global_id: UUID = UUID("3b5e358b-c245-4094-8acb-b0331e1b00d2"),
    chain_version: int = 1,
    predecessor_global_id: UUID | None = None,
    predecessor_snapshot_hash: str | None = None,
    steps: tuple[ToolingProcessStep, ...] | None = None,
) -> ToolingProcessChainRevision:
    primary = ToolingProcessStep(
        global_id=UUID("72c976e9-1f6d-47b0-b932-240aed6e36cf"),
        step_order=1,
        process_kind=ToolingProcessKind.PRIMARY_MOLDING,
        tooling_revision_global_id=REVISION_R1,
        tooling_revision_snapshot_hash=HASH_A,
        input_part_revision_global_ids=(PART_R1,),
        output_part_revision_global_id=PART_R2,
        parent_step_global_id=None,
        machine_type="Hydraulic injection molding machine",
        clamp_tonnage=measurement("450", "t"),
    )
    secondary = ToolingProcessStep(
        global_id=UUID("42e48970-ea3a-437c-aef4-9585f5da2c62"),
        step_order=2,
        process_kind=ToolingProcessKind.OVERMOLD,
        tooling_revision_global_id=REVISION_R1,
        tooling_revision_snapshot_hash=HASH_A,
        input_part_revision_global_ids=(PART_R2,),
        output_part_revision_global_id=UUID("ed8cb5b3-46cc-4e09-900e-caf1aa393424"),
        parent_step_global_id=primary.global_id,
        machine_type="Vertical overmolding machine",
        clamp_tonnage=measurement("250", "t"),
    )
    return ToolingProcessChainRevision(
        global_id=global_id,
        process_chain_global_id=UUID("d207f04b-aa0e-407b-b9ae-bcf2fe757e92"),
        tenant_id=TENANT,
        project_global_id=PROJECT,
        chain_version=chain_version,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        steps=steps or (primary, secondary),
        reason="Record the exact parent and overmold sequence.",
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p603-process-chain",
    )


def set_binding() -> ToolingSetRevisionBinding:
    return ToolingSetRevisionBinding(
        global_id=UUID("40a5bea3-85f1-4933-871b-4101996f8468"),
        tenant_id=TENANT,
        project_global_id=PROJECT,
        tooling_master_global_id=MASTER,
        tooling_set_global_id=UUID("37fe1c21-586d-468c-869c-ec5c2a8b2af3"),
        tooling_set_snapshot_hash=HASH_A,
        tooling_revision_global_id=REVISION_R1,
        tooling_revision_snapshot_hash=HASH_B,
        reason="Bind the unmodified physical Set to its exact source revision.",
        created_by_user_id="tooling.owner@example.invalid",
        created_at=NOW,
        request_id=REQUEST,
        trace_id="trace-p603-set-binding",
    )


class Phase6ToolingRevisionDomainTest(unittest.TestCase):
    def test_tooling_revision_is_closed_hash_bound_and_lifecycle_free(self) -> None:
        revision = tooling_revision()
        payload = revision.snapshot_payload()
        self.assertEqual(tooling_revision_from_snapshot(payload), revision)
        self.assertEqual(len(revision.revision_key_hash), 64)
        self.assertEqual(len(revision.snapshot_hash), 64)
        serialized = json.dumps(payload, sort_keys=True).casefold()
        for forbidden in ("status", "lifecycle", "approved", "released"):
            self.assertNotIn(forbidden, serialized)
        with self.assertRaises(RequestValidationFailed):
            replace(revision, revision_label="R1 changed")
        with self.assertRaises(RequestValidationFailed):
            tooling_revision_from_snapshot({**payload, "status": "released"})

    def test_tooling_revision_requires_exact_cavity_structure(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            tooling_revision(revision_cavities=(cavity(), cavity()))
        duplicate = cavity(
            global_id=UUID("0c34f66d-0e3d-4fcc-898e-8afc8b225f6c")
        )
        with self.assertRaises(RequestValidationFailed):
            replace(
                tooling_revision(),
                specification=specification(cavity_count=2),
                cavities=(cavity(), duplicate),
                snapshot_hash="",
            )

    def test_tooling_revision_successor_requires_exact_tip(self) -> None:
        first = tooling_revision()
        second = tooling_revision(
            global_id=REVISION_R2,
            revision_number=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        validate_tooling_revision_successor(first, second)
        with self.assertRaises(RequestValidationFailed):
            validate_tooling_revision_successor(second, first)

    def test_insert_validation_evidence_is_state_bound(self) -> None:
        self.assertEqual(insert(validated=True).validation_state.value, "validated")
        with self.assertRaises(RequestValidationFailed):
            replace(insert(), validation_reason="Evidence without validation state.")
        with self.assertRaises(RequestValidationFailed):
            replace(insert(validated=True), validated_at=None)

    def test_external_identity_preserves_source_raw_value_and_effectivity(self) -> None:
        identity = external_identity()
        payload = identity.snapshot_payload()
        self.assertEqual(payload["rawValue"], "CUSTOMER-MOLD-001")
        self.assertEqual(payload["sourceSystem"], "ERPNEXT")
        with self.assertRaises(RequestValidationFailed):
            replace(identity, effective_from=datetime(2026, 8, 7, tzinfo=UTC))

    def test_measurements_are_canonical_bounded_and_unit_bearing(self) -> None:
        self.assertEqual(measurement("12.500").value, "12.5")
        for invalid in ("0", "NaN", "1E+999999"):
            with self.subTest(invalid=invalid), self.assertRaises(
                RequestValidationFailed
            ):
                measurement(invalid)

    def test_part_specification_is_exact_closed_and_hash_bound(self) -> None:
        controlled = part_specification()
        payload = controlled.snapshot_payload()
        self.assertEqual(
            part_controlled_specification_from_snapshot(payload),
            controlled,
        )
        self.assertEqual(payload["partRevisionGlobalId"], str(PART_R1))
        with self.assertRaises(RequestValidationFailed):
            replace(controlled, items=())
        with self.assertRaises(RequestValidationFailed):
            part_controlled_specification_from_snapshot(
                {**payload, "arbitrarySpecification": "not allowed"}
            )

    def test_process_chain_is_ordered_parent_bound_and_closed(self) -> None:
        chain = process_chain()
        self.assertEqual(process_chain_revision_from_snapshot(chain.snapshot_payload()), chain)
        secondary = chain.steps[1]
        with self.assertRaises(RequestValidationFailed):
            process_chain(steps=(chain.steps[0], replace(secondary, step_order=3)))
        with self.assertRaises(RequestValidationFailed):
            process_chain(
                steps=(
                    chain.steps[0],
                    replace(
                        secondary,
                        parent_step_global_id=UUID(
                            "fcb442ad-5af3-4d64-9e6f-71f22dde965d"
                        ),
                    ),
                )
            )
        with self.assertRaises(RequestValidationFailed):
            process_chain(
                steps=(
                    chain.steps[0],
                    replace(
                        secondary,
                        input_part_revision_global_ids=(PART_R1,),
                    ),
                )
            )

    def test_only_the_first_process_step_can_be_primary_molding(self) -> None:
        chain = process_chain()
        with self.assertRaises(RequestValidationFailed):
            process_chain(
                steps=(
                    chain.steps[0],
                    replace(
                        chain.steps[1],
                        process_kind=ToolingProcessKind.PRIMARY_MOLDING,
                        parent_step_global_id=None,
                    ),
                )
            )

    def test_process_chain_successor_requires_exact_tip(self) -> None:
        first = process_chain()
        second = process_chain(
            global_id=UUID("e211b746-8e52-47cb-9932-57623639120c"),
            chain_version=2,
            predecessor_global_id=first.global_id,
            predecessor_snapshot_hash=first.snapshot_hash,
        )
        validate_process_chain_successor(first, second)
        with self.assertRaises(RequestValidationFailed):
            validate_process_chain_successor(second, first)

    def test_set_binding_is_initial_exact_provenance_without_lifecycle(self) -> None:
        binding = set_binding()
        payload = binding.snapshot_payload()
        self.assertEqual(set_revision_binding_from_snapshot(payload), binding)
        self.assertEqual(
            payload["toolingRevisionSnapshotHash"],
            binding.tooling_revision_snapshot_hash,
        )
        serialized = json.dumps(payload, sort_keys=True).casefold()
        for forbidden in ("status", "supplier", "asset", "released", "approved"):
            self.assertNotIn(forbidden, serialized)
        with self.assertRaises(RequestValidationFailed):
            set_revision_binding_from_snapshot({**payload, "assetId": "not allowed"})


if __name__ == "__main__":
    unittest.main()
