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


class Phase7TrialContractTest(unittest.TestCase):
    def test_project_first_routes_replace_legacy_collapsed_placeholders(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        for path in (
            "/projects/{projectId}/trials:",
            "/projects/{projectId}/trial-plans/{trialPlanId}:",
            "/projects/{projectId}/trial-plans/{trialPlanId}/revisions:",
            "/projects/{projectId}/trial-plans/{trialPlanId}/rounds:",
            "/projects/{projectId}/trial-plans/{trialPlanId}/actions:generate:",
        ):
            self.assertIn(path, paths)
        for legacy in (
            "/tooling/{toolingId}/trials:",
            "/trials/{trialId}/workspace:",
            "/trials/{trialId}:submit:",
            "submitTrialRound",
            "    TrialWorkspace:\n",
            "    CommandResult:\n",
        ):
            self.assertNotIn(legacy, OPENAPI)
        for marker in (
            "x-audit-operation: trial_plan.create",
            "x-audit-operation: trial_plan.revise",
            "x-audit-operation: trial_round.create",
            "x-audit-operation: trial_plan.generate_actions",
        ):
            self.assertIn(marker, paths)
        for command in (
            "npi_core.trial_api.get_trial_planning_workspace",
            "npi_core.trial_api.get_trial_plan",
            "npi_core.trial_api.create_trial_plan",
            "npi_core.trial_api.create_trial_plan_revision",
            "npi_core.trial_api.create_planned_trial_round",
            "npi_core.trial_api.generate_trial_plan_actions",
        ):
            self.assertIn(command, BFF)
        create_path = paths.split("/projects/{projectId}/trial-plans/{trialPlanId}:", 1)[0]
        self.assertIn(
            '"201": { $ref: "#/components/responses/TrialPlanDetailCommandResult" }',
            create_path,
        )
        self.assertNotIn("TrialCommandResult:", OPENAPI)

    def test_trial_schemas_are_closed_and_plan_round_remain_distinct(self) -> None:
        schema_names = (
            "TrialResourceProposalInput",
            "TrialResourceProposal",
            "TrialProjectMemberReference",
            "TrialMeasurementPlanInput",
            "TrialMeasurementPlanIntent",
            "TrialPlanRevision",
            "TrialRoundSummary",
            "TrialPlanWorkLink",
            "TrialPlanSummary",
            "TrialUnavailableCapability",
            "TrialPermissions",
            "TrialPlanningWorkspace",
            "TrialPlanDetail",
            "CreateTrialPlan",
            "CreateTrialPlanRevision",
            "CreatePlannedTrialRound",
            "TrialPlanActionInput",
            "GenerateTrialPlanActions",
        )
        for name in schema_names:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", _schema(name))
        plan = _schema("TrialPlanRevision")
        round_summary = _schema("TrialRoundSummary")
        self.assertIn("planVersion:", plan)
        self.assertIn("measurementPlan:", plan)
        self.assertNotIn("currentState:", plan)
        self.assertIn("trialPlanRevisionGlobalId:", round_summary)
        self.assertIn("currentState:", round_summary)
        self.assertNotIn("measurementPlan:", round_summary)

    def test_requests_cannot_supply_server_owned_or_later_trial_truth(self) -> None:
        requests = "\n".join(
            _schema(name)
            for name in (
                "CreateTrialPlan",
                "CreateTrialPlanRevision",
                "CreatePlannedTrialRound",
                "TrialPlanActionInput",
                "GenerateTrialPlanActions",
            )
        )
        for forbidden in (
            "tenantId:",
            "projectGlobalId:",
            "planGlobalId:",
            "bookingState:",
            "currentState:",
            "roundSequence:",
            "actorUserId:",
            "createdByUserId:",
            "createdAt:",
            "requestId:",
            "traceId:",
            "reservationId:",
            "qualityResult:",
            "conclusion:",
            "workItemState:",
        ):
            self.assertNotIn(forbidden, requests)

    def test_resource_capability_is_fail_closed_and_never_a_booking_claim(self) -> None:
        proposal = _schema("TrialResourceProposal")
        capability = _schema("TrialUnavailableCapability")
        measurement = _schema("TrialMeasurementPlanIntent")
        self.assertIn("bookingState: { type: string, const: unavailable }", proposal)
        self.assertIn("availability: { type: string, const: unavailable }", capability)
        self.assertIn("approved_resource_reader_not_configured", capability)
        self.assertIn("approved_booking_policy_not_configured", capability)
        self.assertIn("lockState: { type: string, const: planning_intent_only }", measurement)
        combined = "\n".join((proposal, capability, measurement)).casefold()
        for forbidden in ("reserved", "confirmed", "available_at", "reservationid"):
            self.assertNotIn(forbidden, combined)

    def test_generated_actions_reference_domain_work_without_copying_task_state(self) -> None:
        link = _schema("TrialPlanWorkLink")
        generate = _schema("GenerateTrialPlanActions")
        action = _schema("TrialPlanActionInput")
        self.assertIn("domainWorkItemGlobalId:", link)
        self.assertIn("trialPlanRevisionSnapshotHash:", link)
        for duplicate in ("status:", "state:", "owner:", "completedAt:"):
            self.assertNotIn(duplicate, link)
        self.assertIn("actions:", generate)
        self.assertNotIn("workItemState:", generate)
        self.assertIn("dueAt: { type: string, format: date-time }", action)
        self.assertIn("severity: { type: string, enum: [low, medium, high, critical] }", action)
        self.assertIn("blocking: { type: boolean }", action)
        self.assertNotIn("priority:", action)
        create_round = _schema("CreatePlannedTrialRound")
        required = create_round.split("properties:", 1)[0]
        self.assertNotIn("displayLabel", required)
        self.assertIn('type: [string, "null"]', create_round)

    def test_exact_ownership_rows_preserve_trial_erp_and_work_boundaries(self) -> None:
        for object_name in (
            "TrialPlanRevision",
            "TrialRound",
            "TrialRoundLifecycleEvent",
            "TrialPlanWorkLink",
            "TrialCommandIdempotency",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        self.assertIn("conflict: PLANNING_PROPOSAL_ONLY", OWNERSHIP)
        self.assertIn(
            "resource_availability_and_reservation: {owner: FUTURE_APPROVED_RESOURCE_READER_AND_BOOKING_POLICY",
            OWNERSHIP,
        )
        self.assertIn("conflict: UNAVAILABLE", OWNERSHIP)
        self.assertIn("conflict: DOMAIN_WORK_ITEM_OWNER_WINS", OWNERSHIP)
        self.assertIn("raw_idempotency_key:", OWNERSHIP)
        self.assertIn("conflict: NEVER_PERSIST", OWNERSHIP)

    def test_p702_execution_paths_are_project_first_and_live_behind_switch(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        for path in (
            "/projects/{projectId}/trial-rounds/{trialRoundId}/execution:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}:prepare:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}:start:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/actual-revisions:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/sample-batches:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/sample-batches/{sampleBatchId}/revisions:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/files:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/evidence:",
            "/projects/{projectId}/trial-rounds/{trialRoundId}/evidence/{evidenceId}:content:",
        ):
            self.assertIn(path, paths)
        for audit in (
            "trial_round.prepare",
            "trial_round.start",
            "trial_actual.append",
            "trial_sample.create",
            "trial_sample.revise",
            "trial_file.upload",
            "trial_evidence.bind",
            "trial_evidence.content.read",
        ):
            self.assertIn(f"x-audit-operation: {audit}", paths)
        for active_command in (
            "get_trial_round_execution",
            "prepare_trial_round",
            "start_trial_round",
            "append_trial_actual_revision",
            "create_trial_sample_batch",
            "append_trial_sample_batch_revision",
            "upload_trial_evidence_file",
            "bind_trial_evidence",
            "read_trial_evidence_content",
        ):
            self.assertIn(active_command, BFF)
        self.assertIn("npi_p7_02_routes_disabled", BFF)
        self.assertIn("trial_execution_routes_disabled", BFF)

    def test_p702_execution_schemas_are_closed_and_keep_layers_disjoint(self) -> None:
        names = (
            "TrialLockedReferenceInput",
            "TrialLockedReference",
            "TrialMaterialObservationInput",
            "TrialMaterialObservation",
            "TrialParameterDefinitionInput",
            "TrialParameterDefinition",
            "TrialRoundInputLockRevision",
            "TrialActualResourceInput",
            "TrialActualResource",
            "TrialEnvironmentObservationInput",
            "TrialEnvironmentObservation",
            "TrialParameterObservationInput",
            "TrialParameterObservation",
            "TrialRoundActualRevision",
            "TrialSampleBatchRevision",
            "TrialEvidenceReference",
            "TrialPendingFileRevision",
            "TrialExecutionCapabilities",
            "TrialExecutionPermissions",
            "TrialExecutionWorkspace",
            "PrepareTrialRound",
            "StartTrialRound",
            "AppendTrialActualRevision",
            "TrialSampleBatchInput",
            "CreateTrialSampleBatch",
            "AppendTrialSampleBatchRevision",
            "UploadTrialEvidenceFile",
            "BindTrialEvidence",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", _schema(name))
        actual = _schema("TrialRoundActualRevision")
        self.assertIn("acquisitionMode: { type: string, const: manual }", actual)
        self.assertIn("machineImport: { type: string, const: unavailable }", actual)
        self.assertNotIn("customerStandard", actual)
        self.assertNotIn("approvedBaselineValue", actual)
        evidence = _schema("TrialEvidenceReference")
        self.assertIn("scanState: { type: string, const: clean }", evidence)
        self.assertIn("privacy: { type: string, const: private }", evidence)
        self.assertNotIn("url:", evidence.casefold())

    def test_p702_requests_cannot_claim_server_external_or_approval_truth(self) -> None:
        requests = "\n".join(
            _schema(name)
            for name in (
                "PrepareTrialRound",
                "StartTrialRound",
                "AppendTrialActualRevision",
                "CreateTrialSampleBatch",
                "AppendTrialSampleBatchRevision",
                "UploadTrialEvidenceFile",
                "BindTrialEvidence",
            )
        )
        for forbidden in (
            "tenantId:",
            "projectGlobalId:",
            "snapshotHash:",
            "createdByUserId:",
            "confirmedByUserId:",
            "requestId:",
            "traceId:",
            "scanState:",
            "privacy:",
            "fileUrl:",
            "machineImport:",
            "erpVerification:",
            "qualityResult:",
            "conclusion:",
            "gateEffect:",
            "approvedBaseline:",
        ):
            self.assertNotIn(forbidden, requests)

    def test_p702_ownership_has_one_npi_actual_owner_and_external_holds(self) -> None:
        for object_name in (
            "TrialRoundInputLockRevision",
            "TrialRoundActualRevision",
            "TrialSampleBatchRevision",
            "TrialEvidenceReference",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        self.assertIn("conflict: NEVER_COPY_TO_TRIAL_ACTUAL", OWNERSHIP)
        self.assertIn("conflict: EXPLICIT_NO_IMPUTATION", OWNERSHIP)
        self.assertIn("conflict: UNAVAILABLE_IN_P7_02", OWNERSHIP)
        self.assertIn("conflict: NEVER_PERSIST_OR_RETURN", OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
