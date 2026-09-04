import type {
  TrialDefectRevision,
  TrialDefectVerificationRevision,
  TrialQualityWorkspace,
} from "../../src/api/trial-data-source";
import type { ToolingDefectRevisionViewModel } from "../../src/api/tooling-engineering-controls-contract";
import type { ErpProjectionCollectionViewModel } from "../../src/api/erp-projections-data-source";
import {
  trialExecutionIds,
  trialExecutionWorkspace,
  trialInputLock,
  trialSampleRevision,
} from "./trial-execution-fixture";
import { trialPlanningIds } from "./trial-planning-fixture";

export const trialQualityIds = {
  action: "30000000-0000-4000-8000-000000000001",
  cavityResult: "30000000-0000-4000-8000-000000000002",
  cavityResultRevision: "30000000-0000-4000-8000-000000000003",
  defect: "30000000-0000-4000-8000-000000000004",
  toolingDefectRevision: "30000000-0000-4000-8000-000000000005",
  trialDefectRevision: "30000000-0000-4000-8000-000000000006",
  verification: "30000000-0000-4000-8000-000000000007",
  verificationRevision: "30000000-0000-4000-8000-000000000008",
  requestCavityResult: "30000000-0000-4000-8000-000000000009",
  requestDefect: "30000000-0000-4000-8000-00000000000a",
  requestVerification: "30000000-0000-4000-8000-00000000000b",
} as const;

const member = {
  globalId: trialPlanningIds.member,
  optimisticVersion: 1,
  userId: "trial.engineer@example.invalid",
} as const;

export function trialToolingDefect(): ToolingDefectRevisionViewModel {
  return {
    actions: [],
    blocking: true,
    businessCode: "DEF-T0-001",
    categoryKey: "short_shot",
    cavityGlobalId: trialExecutionIds.cavity,
    cavityIdentifier: "CAV-01",
    createdAt: "2026-08-10T09:14:00Z",
    createdByUserId: "tooling.engineer@example.invalid",
    defectGlobalId: trialQualityIds.defect,
    defectVersion: 1,
    description: "Short shot detected at the rib end during tooling review.",
    detectionContext: {
      globalId: "40000000-0000-4000-8000-000000000001",
      kind: "tooling_revision",
      snapshotHash: "4".repeat(64),
    },
    evidence: [],
    globalId: trialQualityIds.toolingDefectRevision,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: trialPlanningIds.project,
    reason: "Record the first stable Tooling defect identity.",
    requestId: "40000000-0000-4000-8000-000000000002",
    responsibleMember: member,
    rootCause: null,
    rootCauseState: "pending",
    schemaVersion: 1,
    severity: "high",
    snapshotHash: "5".repeat(64),
    state: "in_progress",
    targetRoundLabel: "T0",
    tenantId: "npi-one-test",
    title: "Short shot at rib end",
    toolingMasterGlobalId: trialPlanningIds.toolingMaster,
    toolingRevisionGlobalId: "20000000-0000-4000-8000-000000000003",
    toolingRevisionSnapshotHash: "3".repeat(64),
    traceId: "trace-trial-tooling-defect",
    trialReference: {
      reasonCode: "trial_context_unavailable",
      state: "unavailable",
    },
    versionKeyHash: "6".repeat(64),
  };
}

export function trialQualityDefect(): TrialDefectRevision {
  const execution = trialExecutionWorkspace();
  const lock = trialInputLock();
  const sample = trialSampleRevision();
  const round = execution.round;
  return {
    actions: [
      {
        actionType: "corrective",
        detail: "Increase fill pressure and verify the rib-end dimension.",
        dueDate: "2026-08-13",
        globalId: trialQualityIds.action,
        responsibleMember: member,
        state: "completed",
        targetRoundGlobalId: round.globalId,
        targetRoundOptimisticVersion: round.optimisticVersion,
        targetRoundSnapshotHash: round.snapshotHash,
        verificationRevisionGlobalId: null,
        verificationRevisionSnapshotHash: null,
      },
    ],
    blocking: true,
    businessCode: "DEF-T0-001",
    cavityGlobalId: trialExecutionIds.cavity,
    categoryKey: "short_shot",
    createdAt: "2026-08-10T09:20:00Z",
    createdByUserId: "trial.engineer@example.invalid",
    defectGlobalId: trialQualityIds.defect,
    defectVersion: 2,
    description: "Short shot reproduced in T0 at the exact physical cavity.",
    evidence: [
      {
        globalId: trialExecutionIds.evidence,
        snapshotHash: "f".repeat(64),
      },
    ],
    externalEffects: {
      gate: "unavailable",
      ncr: "unavailable",
      qualityInspection: "unavailable",
      toolingLifecycle: "unavailable",
    },
    globalId: trialQualityIds.trialDefectRevision,
    inputLockRevisionGlobalId: lock.globalId,
    inputLockRevisionSnapshotHash: lock.snapshotHash,
    location: "Rib end",
    occurrenceCount: 3,
    predecessorGlobalId: trialQualityIds.toolingDefectRevision,
    predecessorKind: "tooling_defect_revision",
    predecessorSnapshotHash: "5".repeat(64),
    projectGlobalId: trialPlanningIds.project,
    reason: "Continue the stable Tooling defect into exact Trial evidence.",
    requestId: trialQualityIds.requestDefect,
    responsibleMember: member,
    rootCause: "Fill pressure decays before the rib end is packed.",
    rootCauseState: "recorded",
    sampleBatchRevisionGlobalId: sample.globalId,
    sampleBatchRevisionSnapshotHash: sample.snapshotHash,
    schemaVersion: 1,
    severity: "high",
    snapshotHash: "7".repeat(64),
    state: "ready_for_verification",
    tenantId: "npi-one-test",
    title: "Short shot at rib end",
    toolingMasterGlobalId: trialPlanningIds.toolingMaster,
    toolingRevisionGlobalId: "20000000-0000-4000-8000-000000000003",
    toolingRevisionSnapshotHash: "3".repeat(64),
    toolingSetGlobalId: "20000000-0000-4000-8000-000000000004",
    toolingSetSnapshotHash: "4".repeat(64),
    traceId: "trace-trial-defect",
    trialRoundGlobalId: round.globalId,
    trialRoundOptimisticVersion: round.optimisticVersion,
    trialRoundSnapshotHash: round.snapshotHash,
    versionKeyHash: "8".repeat(64),
  };
}

export function trialQualityVerification(): TrialDefectVerificationRevision {
  const defect = trialQualityDefect();
  const execution = trialExecutionWorkspace();
  return {
    actionGlobalId: trialQualityIds.action,
    attemptSequence: 1,
    cavityResultRevisionGlobalId: trialQualityIds.cavityResultRevision,
    cavityResultRevisionSnapshotHash: "9".repeat(64),
    createdAt: "2026-08-10T10:00:00Z",
    createdByUserId: "quality.engineer@example.invalid",
    defectGlobalId: defect.defectGlobalId,
    defectRevisionGlobalId: defect.globalId,
    defectRevisionSnapshotHash: defect.snapshotHash,
    evidence: [
      {
        globalId: trialExecutionIds.evidence,
        snapshotHash: "f".repeat(64),
      },
    ],
    finding: "The first verification still shows an undersized rib end.",
    globalId: trialQualityIds.verificationRevision,
    observedAt: "2026-08-10T09:58:00Z",
    projectGlobalId: trialPlanningIds.project,
    requestId: trialQualityIds.requestVerification,
    result: "fail",
    schemaVersion: 1,
    snapshotHash: "a".repeat(64),
    targetRoundGlobalId: execution.round.globalId,
    targetRoundOptimisticVersion: execution.round.optimisticVersion,
    targetRoundSnapshotHash: execution.round.snapshotHash,
    tenantId: "npi-one-test",
    traceId: "trace-trial-verification",
    verificationGlobalId: trialQualityIds.verification,
    verificationRoundGlobalId: execution.round.globalId,
    verificationRoundOptimisticVersion: execution.round.optimisticVersion,
    verificationRoundSnapshotHash: execution.round.snapshotHash,
    verifierMember: {
      globalId: "50000000-0000-4000-8000-000000000001",
      optimisticVersion: 1,
      userId: "quality.engineer@example.invalid",
    },
    versionKeyHash: "b".repeat(64),
  };
}

export function trialQualityWorkspace(
  overrides: Partial<TrialQualityWorkspace> = {},
): TrialQualityWorkspace {
  const execution = trialExecutionWorkspace();
  const lock = trialInputLock();
  const sample = trialSampleRevision();
  const defect = trialQualityDefect();
  return {
    cavityFilters: [{ globalId: trialExecutionIds.cavity }],
    cavityResultRevisions: [
      {
        cavityGlobalId: trialExecutionIds.cavity,
        cavityResultGlobalId: trialQualityIds.cavityResult,
        createdAt: "2026-08-10T09:30:00Z",
        createdByUserId: "trial.engineer@example.invalid",
        evidence: [
          {
            globalId: trialExecutionIds.evidence,
            snapshotHash: "f".repeat(64),
          },
        ],
        globalId: trialQualityIds.cavityResultRevision,
        inputLockRevisionGlobalId: lock.globalId,
        inputLockRevisionSnapshotHash: lock.snapshotHash,
        measurements: [
          {
            characteristicKey: "rib.end.width",
            comparisonState: "out_of_spec",
            label: "Rib end width",
            lowerLimit: "2.40",
            nominalValue: "2.50",
            observedAt: "2026-08-10T09:25:00Z",
            observedByUserId: "trial.engineer@example.invalid",
            required: true,
            source: "manual",
            state: "measured",
            unit: "mm",
            upperLimit: "2.60",
            value: "2.31",
          },
        ],
        predecessorGlobalId: null,
        predecessorSnapshotHash: null,
        projectGlobalId: trialPlanningIds.project,
        reason: "Record the exact T0 cavity measurement.",
        requestId: trialQualityIds.requestCavityResult,
        resultVersion: 1,
        sampleBatchRevisionGlobalId: sample.globalId,
        sampleBatchRevisionSnapshotHash: sample.snapshotHash,
        schemaVersion: 1,
        snapshotHash: "9".repeat(64),
        tenantId: "npi-one-test",
        toolingRevisionGlobalId: "20000000-0000-4000-8000-000000000003",
        toolingRevisionSnapshotHash: "3".repeat(64),
        toolingSetGlobalId: "20000000-0000-4000-8000-000000000004",
        toolingSetSnapshotHash: "4".repeat(64),
        traceId: "trace-trial-cavity-result",
        trialRoundGlobalId: execution.round.globalId,
        versionKeyHash: "c".repeat(64),
      },
    ],
    defectRevisions: [
      { revision: trialToolingDefect(), source: "tooling" },
      { revision: defect, source: "trial" },
    ],
    externalEffects: {
      gate: "unavailable",
      ncr: "unavailable",
      qualityInspection: "unavailable",
      toolingLifecycle: "unavailable",
    },
    pareto: [
      {
        categoryKey: "short_shot",
        cavityGlobalId: trialExecutionIds.cavity,
        count: 3,
        severity: "high",
      },
    ],
    permissions: {
      manageDefects: true,
      recordCavityResult: true,
      verifyDefects: true,
      view: true,
    },
    projectGlobalId: trialPlanningIds.project,
    trialRound: execution.round,
    verificationRevisions: [trialQualityVerification()],
    ...overrides,
  };
}

export function trialFormalQualityProjection(): ErpProjectionCollectionViewModel {
  const workspace = trialQualityWorkspace();
  const defect = workspace.defectRevisions.find(
    (entry) => entry.source === "trial",
  )?.revision;
  if (!defect)
    throw new Error("Trial formal quality fixture requires one Trial defect.");
  const observationGlobalId = "30000000-0000-4000-8000-00000000000d";
  const headGlobalId = "30000000-0000-4000-8000-00000000000e";
  const values = {
    observedAt: "2026-08-10T10:00:00Z",
    recordKind: "quality_inspection" as const,
    resultCode: "Accepted",
    statusCode: "Completed",
  };
  return {
    accessState: "available",
    items: [
      {
        availability: "available",
        currentTruth: {
          headGlobalId,
          headHash: "e".repeat(64),
          headOptimisticVersion: 2,
          observationGlobalId,
          payloadHash: "d".repeat(64),
          receivedAt: "2026-08-10T10:01:00Z",
          sourceModifiedAt: "2026-08-10T10:00:00Z",
          sourceVersion: "quality-v2",
          values,
        },
        disposition: "applied_current",
        editable: false,
        freshness: "fresh",
        observationGlobalId,
        payloadHash: "d".repeat(64),
        projectionKind: "formal_quality_status",
        receivedAt: "2026-08-10T10:01:00Z",
        scopeGlobalId: workspace.trialRound.globalId,
        scopeKind: "trial_round",
        sourceModifiedAt: "2026-08-10T10:00:00Z",
        sourceObjectId: "QI-SANDBOX-T0",
        sourceObjectType: "FormalQualityStatus",
        sourceSystem: "ERPNEXT",
        sourceVersion: "quality-v2",
        unavailableReasonCode: null,
        values,
      },
    ],
    permissions: { edit: false, refresh: false, view: true },
    projectGlobalId: trialPlanningIds.project,
    reasonCode: null,
  };
}

export function trialFormalQualityLinks() {
  return {
    items: [],
    permissions: { link: true, view: true as const },
    projectGlobalId: trialPlanningIds.project,
  };
}
