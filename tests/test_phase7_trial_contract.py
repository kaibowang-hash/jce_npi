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
        self.assertNotIn("trial_api.", BFF)

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
        self.assertIn("domainWorkItemGlobalId:", link)
        self.assertIn("trialPlanRevisionSnapshotHash:", link)
        for duplicate in ("status:", "state:", "owner:", "completedAt:"):
            self.assertNotIn(duplicate, link)
        self.assertIn("actions:", generate)
        self.assertNotIn("workItemState:", generate)

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


if __name__ == "__main__":
    unittest.main()
