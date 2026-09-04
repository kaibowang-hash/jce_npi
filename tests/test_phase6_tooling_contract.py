from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
BFF = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")


def _schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


class Phase6ToolingContractTest(unittest.TestCase):
    def test_schemas_are_closed_and_exact_routes_are_active(self) -> None:
        schema_names = (
            "ToolingExternalReference",
            "EngineeringPartRevisionReference",
            "EngineeringPartSummary",
            "ToolingRequirementSummary",
            "ToolingMasterSummary",
            "ToolingApplicabilitySummary",
            "ToolingPermissions",
            "ToolingDownstreamCapability",
            "ToolingProjectCockpit",
            "CreateEngineeringPart",
            "CreateEngineeringPartRevision",
            "CreateToolingRequirement",
            "CreateToolingMaster",
            "CreateToolingApplicability",
            "ToolingSetUnavailableField",
            "ToolingSetPermissions",
            "ToolingSetSummary",
            "ToolingIntakeAccessory",
            "ToolingIntakeInspection",
            "ToolingIntakeDifference",
            "ToolingIntakeSummary",
            "ToolingIntakeEvidenceReference",
            "ToolingSetCollection",
            "ToolingSetDetail",
            "CreateToolingSet",
            "CreateToolingIntake",
            "CreateToolingIntakeEvidenceReference",
            "ToolingMeasurement",
            "ToolingSpecification",
            "ToolingCavityMapping",
            "CreateToolingCavityMapping",
            "ToolingInsertApplicability",
            "CreateToolingInsertApplicability",
            "ToolingExternalIdentity",
            "CreateToolingExternalIdentity",
            "ToolingDocumentRevisionReference",
            "ToolingRevision",
            "PartControlledSpecificationItem",
            "CreatePartControlledSpecificationItem",
            "PartControlledSpecification",
            "ToolingProcessStep",
            "CreateToolingProcessStep",
            "ToolingProcessChainRevision",
            "ToolingSetRevisionBinding",
            "CreateToolingRevision",
            "CreatePartControlledSpecification",
            "CreateToolingProcessChainRevision",
            "CreateToolingSetRevisionBinding",
            "ToolingRevisionAvailableCapability",
            "ToolingRevisionNotDeliveredCapability",
            "ToolingRevisionUnavailableField",
            "ToolingRevisionPermissions",
            "ToolingRevisionCollection",
            "ToolingRevisionDetail",
            "PartControlledSpecificationContext",
            "ToolingProcessChainCollection",
        )
        for name in schema_names:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", _schema(name))
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        for path in (
            "/projects/{projectId}/tooling:",
            "/projects/{projectId}/tooling/{toolingMasterId}:",
            "/projects/{projectId}/parts:",
            "/projects/{projectId}/parts/{partId}/revisions:",
            "/projects/{projectId}/tooling-requirements:",
            "/projects/{projectId}/tooling-masters:",
            "/projects/{projectId}/tooling-applicabilities:",
            "/projects/{projectId}/tooling/{toolingMasterId}/sets:",
            "/projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}:",
            "/projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}/intakes:",
            "/projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}/intakes/{intakeId}/evidence:",
            "/projects/{projectId}/tooling/{toolingMasterId}/revisions:",
            "/projects/{projectId}/tooling/{toolingMasterId}/revisions/{toolingRevisionId}:",
            "/projects/{projectId}/parts/{partId}/revisions/{partRevisionId}/controlled-specification:",
            "/projects/{projectId}/tooling-process-chains:",
            "/projects/{projectId}/tooling-process-chains/{processChainRevisionId}:",
            "/projects/{projectId}/tooling/{toolingMasterId}/sets/{toolingSetId}/revision-binding:",
        ):
            self.assertIn(path, paths)
        for command in (
            "tooling_api.get_tooling_cockpit",
            "tooling_api.get_tooling_master",
            "tooling_api.create_engineering_part",
            "tooling_api.create_engineering_part_revision",
            "tooling_api.create_tooling_requirement",
            "tooling_api.create_tooling_master",
            "tooling_api.create_tooling_applicability",
            "tooling_api.get_tooling_sets",
            "tooling_api.get_tooling_set",
            "tooling_api.create_tooling_set",
            "tooling_api.create_tooling_intake",
            "tooling_api.create_tooling_intake_evidence_reference",
            "tooling_api.get_tooling_revisions",
            "tooling_api.get_tooling_revision",
            "tooling_api.create_tooling_revision",
            "tooling_api.get_part_controlled_specification",
            "tooling_api.create_part_controlled_specification",
            "tooling_api.get_tooling_process_chains",
            "tooling_api.get_tooling_process_chain",
            "tooling_api.create_tooling_process_chain_revision",
            "tooling_api.create_tooling_set_revision_binding",
        ):
            self.assertIn(command, BFF)
        self.assertIn("_p6_01_routes_disabled", BFF)
        self.assertIn("_p6_02_routes_disabled", BFF)
        self.assertIn("_p6_03_routes_disabled", BFF)

    def test_browser_requests_cannot_supply_server_owned_truth(self) -> None:
        requests = "\n".join(
            _schema(name)
            for name in (
                "CreateEngineeringPart",
                "CreateEngineeringPartRevision",
                "CreateToolingRequirement",
                "CreateToolingMaster",
                "CreateToolingApplicability",
                "CreateToolingSet",
                "CreateToolingIntake",
                "CreateToolingIntakeEvidenceReference",
                "CreateToolingRevision",
                "CreatePartControlledSpecification",
                "CreateToolingProcessChainRevision",
                "CreateToolingSetRevisionBinding",
            )
        )
        for forbidden in (
            "tenantId:", "actorUserId:", "snapshotHash:",
            "relationshipKeyHash:", "sourceSystem:", "assetId:",
            "lifecycleState:", "setCount:", "doctype:", "fileUrl:",
        ):
            self.assertNotIn(forbidden, requests)

    def test_shared_master_applicability_is_versioned_and_exact(self) -> None:
        applicability = _schema("ToolingApplicabilitySummary")
        cockpit = _schema("ToolingProjectCockpit")
        for marker in (
            "relationshipGlobalId:", "relationshipKeyHash:",
            "toolingMasterGlobalId:", "part:", "version:",
            "predecessorGlobalId:", "effectiveFrom:", "effectiveTo:",
            "snapshotHash:",
        ):
            self.assertIn(marker, applicability)
        self.assertNotIn("setCount:", applicability)
        self.assertNotIn("lifecycleState:", applicability)
        self.assertIn("masters:", cockpit)
        self.assertNotIn("\n        master:", cockpit)

    def test_later_capabilities_are_explicitly_unavailable(self) -> None:
        capability = _schema("ToolingDownstreamCapability")
        revision_capability = _schema("ToolingRevisionNotDeliveredCapability")
        permissions = _schema("ToolingPermissions")
        self.assertIn("const: unavailable", capability)
        self.assertIn("lifecycle_policy_unavailable", capability)
        self.assertIn("const: unavailable", revision_capability)
        self.assertIn(
            "const: tooling_revision_not_delivered",
            revision_capability,
        )
        self.assertIn("transitionLifecycle: { type: boolean, const: false }", permissions)

    def test_tooling_revision_insert_response_preserves_frozen_model_provenance(
        self,
    ) -> None:
        insert = _schema("ToolingInsertApplicability")
        self.assertIn("modelSourceSystem:", insert)
        self.assertIn("modelSourceObjectId:", insert)
        self.assertNotIn("\n        model:", insert)

    def test_physical_set_intake_contract_is_distinct_url_free_and_active(self) -> None:
        tooling_set = _schema("ToolingSetSummary")
        intake = _schema("ToolingIntakeSummary")
        inspection = _schema("ToolingIntakeInspection")
        evidence = _schema("ToolingIntakeEvidenceReference")
        create_set = _schema("CreateToolingSet")
        for marker in (
            "globalId:", "toolingMasterGlobalId:",
            "toolingRequirementGlobalId:", "physicalSerial:",
            "custodyResponsibility:", "repairAuthorizationReference:",
            "returnConditions:", "sourceRevision:", "supplier:",
            "lifecycle:", "erpLocationAndAsset:",
        ):
            self.assertIn(marker, tooling_set)
        self.assertNotIn("setCount:", tooling_set)
        self.assertNotIn("status:", tooling_set)
        for category in (
            "appearance", "water_circuit", "hot_runner", "electrical", "safety",
        ):
            self.assertIn(category, inspection)
        self.assertIn("inspections:", intake)
        for marker in (
            "fileRevisionGlobalId:", "fileOptimisticVersion:",
            "fileContentHash:", "sha256:", "differenceGlobalIds:",
        ):
            self.assertIn(marker, evidence)
        self.assertNotIn("fileUrl:", evidence)
        self.assertNotIn("assetId:", create_set)
        self.assertNotIn("sourceRevisionGlobalId:", create_set)
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        self.assertIn("x-audit-operation: tooling_set.create", paths)
        self.assertIn("x-audit-operation: tooling_intake.create", paths)
        self.assertIn("x-audit-operation: tooling_intake_evidence.create", paths)

    def test_exact_ownership_rows_preserve_npi_erp_boundary(self) -> None:
        for object_name in (
            "EngineeringPart", "EngineeringPartRevision", "ToolingRequirement",
            "ToolingMaster", "ToolingApplicability", "ToolingCommandIdempotency",
            "ToolingSet", "ToolingIntake", "ToolingIntakeEvidenceReference",
            "ToolingRevision", "PartControlledSpecification",
            "ToolingProcessChainRevision", "ToolingSetRevisionBinding",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        self.assertIn("formal_item_mapping: {owner: ERPNEXT", OWNERSHIP)
        self.assertIn("formal_asset_id_state_location_shot_count_and_maintenance: {owner: ERPNEXT", OWNERSHIP)
        self.assertIn("lifecycle_state_and_authority: {owner: FUTURE_APPROVED_TOOLING_POLICY", OWNERSHIP)
        self.assertIn("raw_idempotency_key:", OWNERSHIP)
        self.assertIn("conflict: NEVER_PERSIST", OWNERSHIP)
        self.assertIn("exact_source_tooling_revision: {owner: NPI_ONE_TOOLING_REVISION_COMMAND", OWNERSHIP)
        self.assertIn("conflict: INITIAL_BINDING_ONLY", OWNERSHIP)
        self.assertIn("formal_supplier: {owner: ERPNEXT", OWNERSHIP)
        self.assertIn("raw_private_url_and_file_content: {owner: NPI_ONE_FILE_SERVICE", OWNERSHIP)
        self.assertIn("conflict: NEVER_EXPOSE_OR_MUTATE", OWNERSHIP)

    def test_p6_03_components_and_exact_routes_are_active_fail_closed(self) -> None:
        revision = _schema("ToolingRevision")
        part_specification = _schema("PartControlledSpecification")
        chain = _schema("ToolingProcessChainRevision")
        binding = _schema("ToolingSetRevisionBinding")
        self.assertIn("specification:", revision)
        self.assertIn("cavities:", revision)
        self.assertIn("designDocumentRevisions:", revision)
        self.assertIn("partRevisionSnapshotHash:", part_specification)
        self.assertIn("processChainGlobalId:", chain)
        self.assertIn("toolingSetSnapshotHash:", binding)
        combined = "\n".join((revision, part_specification, chain, binding)).casefold()
        for forbidden in ("lifecycle", "approved", "released", "assetid", "supplierid"):
            self.assertNotIn(forbidden, combined)
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        for marker in (
            "x-audit-operation: tooling_revision.create",
            "x-audit-operation: part_controlled_specification.create",
            "x-audit-operation: tooling_process_chain_revision.create",
            "x-audit-operation: tooling_set_revision_binding.create",
        ):
            self.assertIn(marker, paths)
        for command in (
            "tooling_api.create_tooling_revision",
            "tooling_api.create_part_controlled_specification",
            "tooling_api.create_tooling_process_chain_revision",
            "tooling_api.create_tooling_set_revision_binding",
        ):
            self.assertIn(command, BFF)
        self.assertIn("tooling_revision_routes_are_disabled", BFF)


if __name__ == "__main__":
    unittest.main()
