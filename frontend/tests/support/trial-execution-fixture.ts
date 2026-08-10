import type {
  TrialExecutionWorkspace,
  TrialLockedReferenceKind,
  TrialRoundActualRevision,
  TrialRoundInputLockRevision,
  TrialSampleBatchRevision,
} from "../../src/api/trial-data-source";
import { trialPlanDetail, trialPlanningIds } from "./trial-planning-fixture";

export const trialExecutionIds = {
  actual: "10000000-0000-4000-8000-000000000001",
  actualRevision: "10000000-0000-4000-8000-000000000002",
  evidence: "10000000-0000-4000-8000-000000000003",
  fileRevision: "10000000-0000-4000-8000-000000000004",
  inputLock: "10000000-0000-4000-8000-000000000005",
  inputLockRevision: "10000000-0000-4000-8000-000000000006",
  pendingFile: "10000000-0000-4000-8000-000000000007",
  requestActual: "10000000-0000-4000-8000-000000000008",
  requestEvidence: "10000000-0000-4000-8000-000000000009",
  requestLock: "10000000-0000-4000-8000-00000000000a",
  requestSample: "10000000-0000-4000-8000-00000000000b",
  sampleBatch: "10000000-0000-4000-8000-00000000000c",
  sampleRevision: "10000000-0000-4000-8000-00000000000d",
} as const;

const referenceKinds: readonly TrialLockedReferenceKind[] = [
  "design_baseline",
  "part_revision",
  "tooling_revision",
  "tooling_set",
  "tooling_set_binding",
  "cavity",
  "process_chain",
  "inspection_document",
];

const referenceIds = referenceKinds.map(
  (_kind, index) =>
    `20000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
);

export function trialInputLock(): TrialRoundInputLockRevision {
  return {
    createdAt: "2026-08-10T08:30:00Z",
    createdByUserId: "trial.engineer@example.invalid",
    globalId: trialExecutionIds.inputLockRevision,
    inputLockGlobalId: trialExecutionIds.inputLock,
    lockVersion: 1,
    material: {
      additive: "GF30",
      color: "Natural",
      confirmedByUserId: "trial.engineer@example.invalid",
      erpVerification: "unavailable",
      label: "PA66-GF30 natural",
      lotBatchCode: "LOT-2026-0810",
      observedAt: "2026-08-10T08:25:00Z",
      sourceObjectId: "MAT-PA66-GF30",
      sourceSystem: "ERPNEXT",
    },
    parameterDefinitions: [
      {
        category: "Injection",
        key: "injection.pressure",
        lowerLimit: "80",
        required: true,
        targetValue: "90",
        unit: "MPa",
        upperLimit: "100",
        valueKind: "decimal",
      },
      {
        category: "Cooling",
        key: "cooling.time",
        lowerLimit: "18",
        required: true,
        targetValue: "20",
        unit: "s",
        upperLimit: "22",
        valueKind: "decimal",
      },
    ],
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: trialPlanningIds.project,
    reason: "Freeze exact released inputs before Trial execution",
    references: referenceKinds.map((kind, index) => ({
      globalId: referenceIds[index] ?? "",
      kind,
      optimisticVersion: 1,
      snapshotHash: String(index + 1)
        .repeat(64)
        .slice(0, 64),
    })),
    requestId: trialExecutionIds.requestLock,
    schemaVersion: 1,
    snapshotHash: "a".repeat(64),
    tenantId: "npi-one-test",
    traceId: "trace-trial-input-lock",
    trialPlanRevisionGlobalId: trialPlanningIds.revisionOne,
    trialPlanRevisionSnapshotHash: "1".repeat(64),
    trialRoundGlobalId: trialPlanningIds.round,
  };
}

export function trialActualRevision(): TrialRoundActualRevision {
  const lock = trialInputLock();
  return {
    acquisitionMode: "manual",
    actualGlobalId: trialExecutionIds.actual,
    actualVersion: 1,
    confirmedByUserId: "trial.engineer@example.invalid",
    createdAt: "2026-08-10T08:45:00Z",
    environment: [
      {
        key: "ambient.temperature",
        observedAt: "2026-08-10T08:40:00Z",
        unit: "°C",
        value: "24",
      },
    ],
    executionStartedAt: "2026-08-10T08:35:00Z",
    globalId: trialExecutionIds.actualRevision,
    inputLockRevisionGlobalId: lock.globalId,
    inputLockRevisionSnapshotHash: lock.snapshotHash,
    machineImport: "unavailable",
    material: lock.material,
    operatorUserId: "trial.engineer@example.invalid",
    parameters: [
      {
        definitionKey: "injection.pressure",
        observedAt: "2026-08-10T08:42:00Z",
        source: "manual",
        state: "measured",
        unit: "MPa",
        value: "91",
      },
      {
        definitionKey: "cooling.time",
        observedAt: "2026-08-10T08:42:00Z",
        source: "manual",
        state: "measured",
        unit: "s",
        value: "20",
      },
    ],
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: trialPlanningIds.project,
    reason: "Start T0 with manually confirmed actual context",
    requestId: trialExecutionIds.requestActual,
    resources: [
      {
        erpVerification: "unavailable",
        kind: "machine",
        label: "Injection machine 550T",
        sourceObjectId: "IM-550-02",
        sourceSystem: "ERPNEXT",
      },
    ],
    schemaVersion: 1,
    snapshotHash: "b".repeat(64),
    tenantId: "npi-one-test",
    traceId: "trace-trial-actual",
    trialRoundGlobalId: trialPlanningIds.round,
  };
}

export function trialSampleRevision(): TrialSampleBatchRevision {
  const lock = trialInputLock();
  return {
    cavityGlobalIds: [referenceIds[5] ?? ""],
    createdAt: "2026-08-10T09:00:00Z",
    createdByUserId: "trial.engineer@example.invalid",
    destination: "Metrology laboratory",
    feedbackObservedAt: null,
    feedbackSource: null,
    feedbackText: null,
    globalId: trialExecutionIds.sampleRevision,
    inputLockRevisionGlobalId: lock.globalId,
    inputLockRevisionSnapshotHash: lock.snapshotHash,
    label: "T0-SAMPLE-01",
    materialSnapshotHash: lock.material.sourceObjectId
      ? "c".repeat(64)
      : "d".repeat(64),
    packaging: "Sealed cavity-labelled tray",
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: trialPlanningIds.project,
    quantity: 20,
    reason: "Register traceable T0 sample batch",
    requestId: trialExecutionIds.requestSample,
    sampleBatchGlobalId: trialExecutionIds.sampleBatch,
    sampleVersion: 1,
    schemaVersion: 1,
    snapshotHash: "d".repeat(64),
    tenantId: "npi-one-test",
    traceId: "trace-trial-sample",
    trialRoundGlobalId: trialPlanningIds.round,
    unit: "pcs",
  };
}

export function trialExecutionWorkspace(
  overrides: Partial<TrialExecutionWorkspace> = {},
): TrialExecutionWorkspace {
  const detail = trialPlanDetail();
  const sourceRound = detail.rounds[0];
  if (!sourceRound)
    throw new Error("The Trial execution fixture requires one Round.");
  const round = { ...sourceRound, currentState: "running" as const };
  const lock = trialInputLock();
  const actual = trialActualRevision();
  const sample = trialSampleRevision();
  return {
    actualRevisions: [actual],
    capabilities: {
      approvedBaseline: "unavailable",
      conclusion: "unavailable",
      erpQuality: "unavailable",
      gateEffect: "unavailable",
      machineImport: "unavailable",
    },
    evidence: [
      {
        createdAt: "2026-08-10T09:10:00Z",
        createdByUserId: "trial.engineer@example.invalid",
        fileMimeType: "image/png",
        fileRevisionGlobalId: trialExecutionIds.fileRevision,
        fileSha256: "e".repeat(64),
        fileSizeBytes: 4096,
        globalId: trialExecutionIds.evidence,
        privacy: "private",
        projectGlobalId: trialPlanningIds.project,
        requestId: trialExecutionIds.requestEvidence,
        role: "photo",
        sampleBatchRevisionGlobalId: sample.globalId,
        sampleBatchRevisionSnapshotHash: sample.snapshotHash,
        scanState: "clean",
        schemaVersion: 1,
        snapshotHash: "f".repeat(64),
        tenantId: "npi-one-test",
        traceId: "trace-trial-evidence",
        trialRoundGlobalId: trialPlanningIds.round,
      },
    ],
    inputLocks: [lock],
    missingFacts: [],
    pendingFiles: [
      {
        fileName: "parameter-curve.csv",
        globalId: trialExecutionIds.pendingFile,
        mimeType: "text/csv",
        optimisticVersion: 1,
        privacy: "private",
        scanState: "pending",
        sha256: "9".repeat(64),
        sizeBytes: 1024,
      },
    ],
    permissions: {
      canManageEvidence: true,
      canManageSamples: true,
      canPrepare: false,
      canRecordActual: true,
      canStart: false,
    },
    projectGlobalId: trialPlanningIds.project,
    round,
    sampleBatchRevisions: [sample],
    ...overrides,
  };
}
