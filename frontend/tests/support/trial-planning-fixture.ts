import type {
  TrialPlanDetail,
  TrialPlanRevision,
  TrialPlanningWorkspace,
} from "../../src/api/trial-data-source";

export const trialPlanningIds = {
  actionLink: "88888888-8888-4888-8888-888888888888",
  document: "99999999-9999-4999-8999-999999999999",
  member: "55555555-5555-4555-8555-555555555555",
  plan: "33333333-3333-4333-8333-333333333333",
  project: "11111111-1111-4111-8111-111111111111",
  resourceMachine: "66666666-6666-4666-8666-666666666666",
  resourceMaterial: "77777777-7777-4777-8777-777777777777",
  revisionOne: "44444444-4444-4444-8444-444444444444",
  revisionTwo: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  round: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  toolingMaster: "22222222-2222-4222-8222-222222222222",
  workItem: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
} as const;

export function trialPlanRevision(
  overrides: Partial<TrialPlanRevision> = {},
): TrialPlanRevision {
  return {
    createdAt: "2026-08-10T08:00:00Z",
    createdByUserId: "trial.engineer@example.invalid",
    globalId: trialPlanningIds.revisionOne,
    measurementPlan: {
      description: "Measure critical housing dimensions",
      documentOptimisticVersion: null,
      documentRevisionGlobalId: null,
      documentRevisionSnapshotHash: null,
      lockState: "planning_intent_only",
    },
    objective: "Verify first-shot fill balance and dimensional intent",
    planGlobalId: trialPlanningIds.plan,
    planVersion: 1,
    plannedEndAt: "2026-08-20T12:00:00Z",
    plannedStartAt: "2026-08-20T08:00:00Z",
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: trialPlanningIds.project,
    purpose: "first_trial",
    reason: "Initial controlled Trial planning scope",
    resources: [
      {
        bookingState: "unavailable",
        globalId: trialPlanningIds.resourceMachine,
        kind: "machine",
        label: "Injection machine 550T",
        quantity: null,
        sourceObjectId: "IM-550-02",
        sourceSystem: "ERPNEXT",
        unit: null,
      },
      {
        bookingState: "unavailable",
        globalId: trialPlanningIds.resourceMaterial,
        kind: "material",
        label: "PA66-GF30 natural",
        quantity: 80,
        sourceObjectId: "MAT-PA66-GF30",
        sourceSystem: "ERPNEXT",
        unit: "kg",
      },
    ],
    responsibleMembers: [
      {
        globalId: trialPlanningIds.member,
        optimisticVersion: 1,
        userId: "trial.engineer@example.invalid",
      },
    ],
    sampleQuantity: 80,
    snapshotHash: "1".repeat(64),
    toolingMasterGlobalId: trialPlanningIds.toolingMaster,
    ...overrides,
  };
}

export function trialPlanDetail(
  overrides: Partial<TrialPlanDetail> = {},
): TrialPlanDetail {
  const revision = trialPlanRevision();
  return {
    actionLinks: [
      {
        createdAt: "2026-08-10T08:20:00Z",
        createdByUserId: "trial.engineer@example.invalid",
        domainWorkItemGlobalId: trialPlanningIds.workItem,
        globalId: trialPlanningIds.actionLink,
        projectGlobalId: trialPlanningIds.project,
        snapshotHash: "2".repeat(64),
        trialPlanGlobalId: trialPlanningIds.plan,
        trialPlanRevisionGlobalId: revision.globalId,
        trialPlanRevisionSnapshotHash: revision.snapshotHash,
        trialRoundGlobalId: trialPlanningIds.round,
      },
    ],
    capabilities: [
      {
        availability: "unavailable",
        key: "resource_availability",
        reasonCode: "approved_resource_reader_not_configured",
      },
      {
        availability: "unavailable",
        key: "resource_reservation",
        reasonCode: "approved_booking_policy_not_configured",
      },
    ],
    latestRevision: revision,
    permissions: {
      canCreatePlan: true,
      canCreateRound: true,
      canGenerateActions: true,
      canRevisePlan: true,
    },
    planGlobalId: trialPlanningIds.plan,
    projectGlobalId: trialPlanningIds.project,
    revisions: [revision],
    rounds: [
      {
        createdAt: "2026-08-10T08:10:00Z",
        createdByUserId: "trial.engineer@example.invalid",
        currentState: "planned",
        displayLabel: "T0",
        globalId: trialPlanningIds.round,
        optimisticVersion: 1,
        plannedEndAt: revision.plannedEndAt,
        plannedStartAt: revision.plannedStartAt,
        projectGlobalId: trialPlanningIds.project,
        purpose: revision.purpose,
        roundSequence: 0,
        snapshotHash: "3".repeat(64),
        toolingMasterGlobalId: trialPlanningIds.toolingMaster,
        trialPlanGlobalId: trialPlanningIds.plan,
        trialPlanRevisionGlobalId: revision.globalId,
        trialPlanRevisionSnapshotHash: revision.snapshotHash,
      },
    ],
    ...overrides,
  };
}

export function trialPlanningWorkspace(
  overrides: Partial<TrialPlanningWorkspace> = {},
): TrialPlanningWorkspace {
  const detail = trialPlanDetail();
  return {
    capabilities: detail.capabilities,
    permissions: detail.permissions,
    plans: [
      {
        actionCount: detail.actionLinks.length,
        latestRevision: detail.latestRevision,
        planGlobalId: detail.planGlobalId,
        roundCount: detail.rounds.length,
      },
    ],
    projectGlobalId: trialPlanningIds.project,
    ...overrides,
  };
}
