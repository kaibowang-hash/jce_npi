import type {
  TrialConclusionPolicyVersion,
  TrialConclusionRevision,
  TrialMetricComparisonRow,
  TrialReviewReferenceRevision,
  TrialReviewWorkspace,
  TrialRoundComparisonSnapshot,
  TrialRoundSummary,
} from "../../src/api/trial-data-source";
import { trialExecutionIds } from "./trial-execution-fixture";
import { trialPlanDetail, trialPlanningIds } from "./trial-planning-fixture";
import { trialQualityIds } from "./trial-quality-fixture";

export const trialReviewIds = {
  comparison: "60000000-0000-4000-8000-000000000001",
  conclusion: "60000000-0000-4000-8000-000000000002",
  conclusionRevision: "60000000-0000-4000-8000-000000000003",
  fileRevision: "60000000-0000-4000-8000-000000000004",
  partRevision: "60000000-0000-4000-8000-000000000005",
  policy: "60000000-0000-4000-8000-000000000006",
  policyRevision: "60000000-0000-4000-8000-000000000007",
  previousRound: "60000000-0000-4000-8000-000000000008",
  reference: "60000000-0000-4000-8000-000000000009",
  referenceRevision: "60000000-0000-4000-8000-00000000000a",
  requestComparison: "60000000-0000-4000-8000-00000000000b",
  requestConclusion: "60000000-0000-4000-8000-00000000000c",
  requestPolicy: "60000000-0000-4000-8000-00000000000d",
  requestReference: "60000000-0000-4000-8000-00000000000e",
  toolingRevision: "60000000-0000-4000-8000-00000000000f",
  toolingSet: "60000000-0000-4000-8000-000000000010",
} as const;

const hash = (character: string): string => character.repeat(64);

export function trialConclusionPolicy(): TrialConclusionPolicyVersion {
  return {
    allowedConclusionCodes: [
      "pass",
      "conditional_pass",
      "tooling_change",
      "process_tuning",
    ],
    authorityBindings: [
      {
        capabilities: ["submit", "decide", "reopen"],
        member: {
          globalId: trialPlanningIds.member,
          optimisticVersion: 1,
          userId: "quality.engineer@example.invalid",
        },
      },
    ],
    blockOnOpenBlockingDefects: true,
    blockOnUnverifiedRequiredActions: true,
    globalId: trialReviewIds.policyRevision,
    outOfSpecBlockingCodes: ["pass"],
    policyGlobalId: trialReviewIds.policy,
    policyVersion: 1,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: trialPlanningIds.project,
    publishedAt: "2026-08-10T10:10:00Z",
    publishedByUserId: "quality.engineer@example.invalid",
    requestId: trialReviewIds.requestPolicy,
    requireCavityResults: true,
    requiredDimensionKeys: ["rib.end.width"],
    requiredParameterKeys: ["injection.pressure"],
    requiredReferenceKinds: ["controlled_quality_report"],
    schemaVersion: "npi.trial.v1",
    snapshotHash: hash("1"),
    tenantId: "npi-one-test",
    traceId: "trace-trial-review-policy",
    trialPlanGlobalId: trialPlanningIds.plan,
    trialPlanRevisionGlobalId: trialPlanningIds.revisionOne,
    trialPlanRevisionSnapshotHash: hash("1"),
    versionKeyHash: hash("2"),
  };
}

function metricRow(
  metricKind: TrialMetricComparisonRow["metricKind"],
  metricKey: string,
  previousValue: string,
  targetValue: string,
  unit: string,
  comparisonState: TrialMetricComparisonRow["cells"][number]["comparisonState"],
): TrialMetricComparisonRow {
  return {
    cavityGlobalId:
      metricKind === "dimension" ? trialExecutionIds.cavity : null,
    cells: [
      {
        comparisonState: "within_spec",
        deltaFromPrevious: null,
        lowerLimit: metricKind === "yield" ? "95" : null,
        sourceRevision: {
          globalId: trialExecutionIds.actualRevision,
          snapshotHash: hash("b"),
        },
        state: "measured",
        trialRoundGlobalId: trialReviewIds.previousRound,
        unit,
        upperLimit: null,
        value: previousValue,
      },
      {
        comparisonState,
        deltaFromPrevious: targetValue === previousValue ? "0" : targetValue,
        lowerLimit: metricKind === "yield" ? "95" : null,
        sourceRevision: {
          globalId:
            metricKind === "dimension"
              ? trialQualityIds.cavityResultRevision
              : trialExecutionIds.actualRevision,
          snapshotHash: metricKind === "dimension" ? hash("9") : hash("b"),
        },
        state: "measured",
        trialRoundGlobalId: trialPlanningIds.round,
        unit,
        upperLimit: null,
        value: targetValue,
      },
    ],
    metricKey,
    metricKind,
    unitState: "comparable",
  };
}

export function trialComparison(): TrialRoundComparisonSnapshot {
  const policy = trialConclusionPolicy();
  const source = {
    actualRevision: {
      globalId: trialExecutionIds.actualRevision,
      snapshotHash: hash("b"),
    },
    cavityResults: [
      {
        cavityGlobalId: trialExecutionIds.cavity,
        revision: {
          globalId: trialQualityIds.cavityResultRevision,
          snapshotHash: hash("9"),
        },
      },
    ],
    defects: [
      {
        blocking: true,
        defectGlobalId: trialQualityIds.defect,
        requiredActionsUnverified: 1,
        revision: {
          globalId: trialQualityIds.trialDefectRevision,
          snapshotHash: hash("7"),
        },
        sourceKind: "trial" as const,
        state: "ready_for_verification" as const,
      },
    ],
    inputLockRevision: {
      globalId: trialExecutionIds.inputLockRevision,
      snapshotHash: hash("a"),
    },
    sampleRevisions: [
      {
        globalId: trialExecutionIds.sampleRevision,
        snapshotHash: hash("d"),
      },
    ],
    trialPlanRevision: {
      globalId: trialPlanningIds.revisionOne,
      snapshotHash: hash("1"),
    },
  };
  return {
    createdAt: "2026-08-10T10:20:00Z",
    createdByUserId: "trial.engineer@example.invalid",
    defectTrends: [
      { defectGlobalId: trialQualityIds.defect, state: "continued" },
    ],
    formalErpQuality: "unavailable",
    globalId: trialReviewIds.comparison,
    inputRows: [
      {
        cells: [
          {
            canonicalValue: "PA66-GF30 / LOT-2026-0801",
            sourceRevision: source.inputLockRevision,
            trialRoundGlobalId: trialReviewIds.previousRound,
          },
          {
            canonicalValue: "PA66-GF30 / LOT-2026-0810",
            sourceRevision: source.inputLockRevision,
            trialRoundGlobalId: trialPlanningIds.round,
          },
        ],
        changeState: "changed",
        semanticKey: "material.lot_batch",
      },
    ],
    metricRows: [
      metricRow(
        "parameter",
        "injection.pressure",
        "88",
        "92",
        "MPa",
        "within_spec",
      ),
      metricRow(
        "dimension",
        "rib.end.width",
        "2.48",
        "2.31",
        "mm",
        "out_of_spec",
      ),
      metricRow("cycle_time", "cycle_time", "42.1", "40.8", "s", "measured"),
      metricRow("yield", "yield", "96.5", "93.2", "%", "out_of_spec"),
    ],
    policyRevision: {
      globalId: policy.globalId,
      snapshotHash: policy.snapshotHash,
    },
    projectGlobalId: trialPlanningIds.project,
    requestId: trialReviewIds.requestComparison,
    schemaVersion: "npi.trial.v1",
    snapshotHash: hash("3"),
    sources: [
      {
        ...source,
        sequence: 1,
        trialRoundGlobalId: trialReviewIds.previousRound,
        trialRoundOptimisticVersion: 4,
        trialRoundSnapshotHash: hash("4"),
      },
      {
        ...source,
        sequence: 2,
        trialRoundGlobalId: trialPlanningIds.round,
        trialRoundOptimisticVersion: 2,
        trialRoundSnapshotHash: hash("5"),
      },
    ],
    targetRoundGlobalId: trialPlanningIds.round,
    tenantId: "npi-one-test",
    traceId: "trace-trial-review-comparison",
    trialPlanGlobalId: trialPlanningIds.plan,
  };
}

export function trialReviewReference(): TrialReviewReferenceRevision {
  const comparison = trialComparison();
  return {
    approvalAuthority: "unavailable",
    comparisonSnapshot: {
      globalId: comparison.globalId,
      snapshotHash: comparison.snapshotHash,
    },
    createdAt: "2026-08-10T10:30:00Z",
    createdByUserId: "quality.engineer@example.invalid",
    effectiveFrom: "2026-08-10",
    effectiveTo: null,
    fileRevision: {
      globalId: trialReviewIds.fileRevision,
      snapshotHash: hash("6"),
    },
    globalId: trialReviewIds.referenceRevision,
    partRevision: {
      globalId: trialReviewIds.partRevision,
      snapshotHash: hash("7"),
    },
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: trialPlanningIds.project,
    reason: "Bind the controlled internal measurement report to T0 review.",
    referenceGlobalId: trialReviewIds.reference,
    referenceKind: "controlled_quality_report",
    referenceVersion: 1,
    requestId: trialReviewIds.requestReference,
    schemaVersion: "npi.trial.v1",
    snapshotHash: hash("8"),
    tenantId: "npi-one-test",
    toolingMasterGlobalId: trialPlanningIds.toolingMaster,
    toolingRevision: {
      globalId: trialReviewIds.toolingRevision,
      snapshotHash: hash("9"),
    },
    toolingSet: {
      globalId: trialReviewIds.toolingSet,
      snapshotHash: hash("a"),
    },
    traceId: "trace-trial-review-reference",
    trialRoundGlobalId: trialPlanningIds.round,
    versionKeyHash: hash("b"),
  };
}

export function trialConclusion(): TrialConclusionRevision {
  const policy = trialConclusionPolicy();
  const comparison = trialComparison();
  const reference = trialReviewReference();
  const roundReferences = comparison.sources.map((source) => ({
    globalId: source.trialRoundGlobalId,
    snapshotHash: source.trialRoundSnapshotHash,
  }));
  return {
    blockers: [
      { code: "open_blocking_defect", sourceKey: trialQualityIds.defect },
      { code: "out_of_spec_blocking", sourceKey: "rib.end.width" },
    ],
    comparisonSnapshot: {
      globalId: comparison.globalId,
      snapshotHash: comparison.snapshotHash,
    },
    conclusionCode: "conditional_pass",
    conclusionGlobalId: trialReviewIds.conclusion,
    conclusionVersion: 1,
    createdAt: "2026-08-10T10:40:00Z",
    createdByUserId: "trial.engineer@example.invalid",
    externalEffects: {
      customerSignature: "unavailable",
      formalErpQuality: "unavailable",
      gate: "unavailable",
      nextWork: "proposal_only",
      npiReadiness: "unavailable",
      toolingLifecycle: "unavailable",
    },
    globalId: trialReviewIds.conclusionRevision,
    policyRevision: {
      globalId: policy.globalId,
      snapshotHash: policy.snapshotHash,
    },
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: trialPlanningIds.project,
    proposedGateEffect:
      "Hold the gate until the blocking defect is independently verified.",
    proposedNextWork: [
      "Verify the rib-end corrective action in the next controlled Trial Round.",
    ],
    proposedNpiEffect:
      "Keep NPI readiness unchanged while the proposal is reviewed.",
    reason: "Submit the exact T0 comparison for an independent decision.",
    requestId: trialReviewIds.requestConclusion,
    reviewReferences: [
      { globalId: reference.globalId, snapshotHash: reference.snapshotHash },
    ],
    schemaVersion: "npi.trial.v1",
    snapshotHash: hash("c"),
    state: "submitted",
    summaryInput: {
      comparisonSnapshot: {
        globalId: comparison.globalId,
        snapshotHash: comparison.snapshotHash,
      },
      conclusionCode: "conditional_pass",
      conclusionState: "submitted",
      cycleTimeState: "measured",
      defectTrendCounts: { continued: 1, new: 0, reopened: 0, resolved: 0 },
      externalEffects: {
        gate: "unavailable",
        nextWork: "proposal_only",
        npiReadiness: "unavailable",
        toolingLifecycle: "unavailable",
      },
      formalErpQuality: "unavailable",
      inputChangeCounts: { added: 0, changed: 1, removed: 0, same: 0 },
      metricRowHashes: [hash("d"), hash("e"), hash("f"), hash("0")],
      reviewReferences: [
        {
          globalId: reference.globalId,
          referenceKind: reference.referenceKind,
          snapshotHash: reference.snapshotHash,
        },
      ],
      rounds: roundReferences,
      schemaVersion: "npi.trial.v1",
      targetRoundGlobalId: trialPlanningIds.round,
      yieldState: "out_of_spec",
    },
    tenantId: "npi-one-test",
    traceId: "trace-trial-review-conclusion",
    trialRoundGlobalId: trialPlanningIds.round,
    trialRoundOptimisticVersion: 2,
    trialRoundSnapshotHash: hash("5"),
    versionKeyHash: hash("e"),
  };
}

export function trialReviewWorkspace(
  overrides: Partial<TrialReviewWorkspace> = {},
): TrialReviewWorkspace {
  const sourceRound = trialPlanDetail().rounds[0];
  if (!sourceRound)
    throw new Error("The Trial review fixture requires one Round.");
  const round = {
    ...sourceRound,
    currentState: "submitted" as const,
    optimisticVersion: 2,
    snapshotHash: hash("5"),
  };
  return {
    comparisonSnapshots: [trialComparison()],
    conclusionRevisions: [trialConclusion()],
    externalEffects: {
      customerSignature: "unavailable",
      formalErpQuality: "unavailable",
      gate: "unavailable",
      nextWork: "proposal_only",
      npiReadiness: "unavailable",
      toolingLifecycle: "unavailable",
    },
    permissions: {
      beginAnalysis: false,
      createComparison: false,
      decideConclusion: true,
      manageReviewReferences: false,
      reopenConclusion: false,
      requiresExactPolicyRevision: true,
      submitConclusion: false,
      view: true,
    },
    policyVersions: [trialConclusionPolicy()],
    projectGlobalId: trialPlanningIds.project,
    reviewReferenceRevisions: [trialReviewReference()],
    trialRound: round,
    ...overrides,
  };
}

export function emptyTrialReviewWorkspace(
  trialRound: TrialRoundSummary,
): TrialReviewWorkspace {
  return trialReviewWorkspace({
    comparisonSnapshots: [],
    conclusionRevisions: [],
    permissions: {
      beginAnalysis: false,
      createComparison: false,
      decideConclusion: false,
      manageReviewReferences: false,
      reopenConclusion: false,
      requiresExactPolicyRevision: true,
      submitConclusion: false,
      view: true,
    },
    policyVersions: [],
    reviewReferenceRevisions: [],
    trialRound,
  });
}
