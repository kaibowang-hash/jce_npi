import type {
  ToolingImportBatchCollection,
  ToolingImportBatchDetail,
  ToolingImportJobSnapshot,
  ToolingImportMappingAuthority,
  ToolingImportPermissions,
  ToolingImportReconciliationRevision,
} from "../../src/api/tooling-import-contract";

export const toolingImportIds = {
  project: "11111111-1111-4111-8111-111111111111",
  batch: "22222222-2222-4222-8222-222222222222",
  fileRevision: "33333333-3333-4333-8333-333333333333",
  inspection: "44444444-4444-4444-8444-444444444444",
  mappingRevision: "55555555-5555-4555-8555-555555555555",
  mapping: "66666666-6666-4666-8666-666666666666",
  activation: "77777777-7777-4777-8777-777777777777",
  previewRevision: "88888888-8888-4888-8888-888888888888",
  preview: "99999999-9999-4999-8999-999999999999",
  job: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  rowResult: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  target: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  request: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  correction: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
  reconciliation: "ffffffff-ffff-4fff-8fff-ffffffffffff",
} as const;

const hash = (character: string): string => character.repeat(64);

export const toolingImportPermissions: ToolingImportPermissions = {
  activateProductionMapping: false,
  confirmPreview: true,
  createCorrectionArtifact: true,
  createMappingProposal: true,
  createPreview: true,
  downloadCorrectionArtifact: true,
  evaluateRollback: true,
  execute: true,
  inspect: true,
  reconcile: true,
  registerSource: true,
  retry: true,
  rollback: true,
  view: true,
};

export const toolingImportMappingAuthority: ToolingImportMappingAuthority = {
  activationGlobalId: toolingImportIds.activation,
  activationSnapshotHash: hash("1"),
  mappingRevisionGlobalId: toolingImportIds.mappingRevision,
  mappingSnapshotHash: hash("2"),
  reasonCode: "synthetic_fixture_scope_only",
  state: "approved_fixture",
};

export function toolingImportJob(
  state: ToolingImportJobSnapshot["state"] = "partially_succeeded",
): ToolingImportJobSnapshot {
  const retryable =
    state === "partially_succeeded" || state === "failed_retryable";
  return {
    attempt: 1,
    batchGlobalId: toolingImportIds.batch,
    correctionArtifactGlobalId: null,
    correctionArtifactSnapshotHash: null,
    correctionArtifacts: [],
    counts: {
      confirmation_required: 0,
      created: retryable ? 0 : 1,
      failed_final: state === "failed_final" ? 1 : 0,
      failed_retryable: retryable ? 1 : 0,
      skipped: 0,
      updated: 0,
    },
    failure: retryable
      ? {
          code: "unexpected_retryable_failure",
          message: "Synthetic retryable worker failure",
          traceId: "trace-worker-retryable",
        }
      : null,
    globalId: toolingImportIds.job,
    optimisticVersion: 1,
    previewGlobalId: toolingImportIds.preview,
    previewSnapshotHash: hash("9"),
    queuedAt: "2026-08-09T08:00:00Z",
    reconciliations: [],
    rowResults: [
      {
        attempt: 1,
        fieldResults: [
          {
            message: retryable
              ? "Synthetic retryable worker failure"
              : "The field was imported.",
            resultCode: retryable ? "unexpected_retryable_failure" : "created",
            sourceHeader: "Tooling No.",
            sourceOrdinal: 1,
            targetField: retryable ? null : "tooling_number",
          },
        ],
        globalId: toolingImportIds.rowResult,
        sourceRow: 3,
        state: retryable ? "failed_retryable" : "created",
        targetGlobalId: retryable ? null : toolingImportIds.target,
        targetObjectType: retryable ? null : "tooling_master",
        targetSnapshotHash: retryable ? null : hash("c"),
        traceId: "trace-worker-row",
        worksheetName: "Tooling List",
      },
    ],
    schemaVersion: "tooling-import.v1",
    snapshotHash: hash("a"),
    state,
    updatedAt: "2026-08-09T08:01:00Z",
  };
}

export function toolingImportReconciliation(
  itemState: ToolingImportReconciliationRevision["items"][number]["state"] = "matched",
): ToolingImportReconciliationRevision {
  return {
    createdAt: "2026-08-09T08:02:00Z",
    createdByUserId: "tooling.engineer@example.invalid",
    globalId: toolingImportIds.reconciliation,
    items: [
      {
        downstreamReferenceCount: itemState === "downstream_used" ? 1 : 0,
        expectedSnapshotHash: hash("c"),
        observedSnapshotHash: hash("c"),
        rowResultGlobalId: toolingImportIds.rowResult,
        state: itemState,
        targetGlobalId: toolingImportIds.target,
        targetObjectType: "tooling_master",
      },
    ],
    jobGlobalId: toolingImportIds.job,
    jobSnapshotHash: hash("a"),
    kind: "reconciliation",
    requestId: toolingImportIds.request,
    schemaVersion: "tooling-import-reconciliation.v1",
    snapshotHash: hash("f"),
    traceId: "trace-reconciliation",
  };
}

export function toolingImportCollection(
  overrides: Partial<ToolingImportBatchCollection> = {},
): ToolingImportBatchCollection {
  const batch = {
    batchGlobalId: toolingImportIds.batch,
    createdAt: "2026-08-09T07:00:00Z",
    createdByUserId: "tooling.engineer@example.invalid",
    customerScopeId: "SYNTHETIC-CUSTOMER",
    fileName: "synthetic-tooling-list.xlsx",
    fileOptimisticVersion: 1,
    fileRevisionGlobalId: toolingImportIds.fileRevision,
    frappeContentHash: "d".repeat(32),
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" as const,
    projectGlobalId: toolingImportIds.project,
    requestId: toolingImportIds.request,
    schemaVersion: "tooling-import.v1" as const,
    sha256: hash("3"),
    sizeBytes: 4096,
    snapshotHash: hash("4"),
    tenantId: "synthetic-tenant",
    traceId: "trace-source",
  };
  return {
    batches: [batch],
    mappingAuthority: toolingImportMappingAuthority,
    permissions: toolingImportPermissions,
    projectGlobalId: toolingImportIds.project,
    ...overrides,
  };
}

export function toolingImportDetail(
  jobState: ToolingImportJobSnapshot["state"] | null = "partially_succeeded",
): ToolingImportBatchDetail {
  const batch = toolingImportCollection().batches[0];
  if (!batch) throw new Error("The synthetic import batch is required.");
  return {
    batch,
    inspections: [
      {
        batchGlobalId: toolingImportIds.batch,
        columns: [
          { headerCell: "A2", ordinal: 1, sourceHeader: "Tooling No." },
          { headerCell: "B2", ordinal: 2, sourceHeader: "Clamp tonnage" },
        ],
        createdAt: "2026-08-09T07:05:00Z",
        detectionPolicyVersion: "tooling-list-detection.v1",
        formulaErrors: [],
        globalId: toolingImportIds.inspection,
        headerRow: 2,
        imageAnchors: [],
        inspectionPolicyVersion: "tooling-xlsx-inspection.v1",
        inspectionVersion: 1,
        passiveReportHash: hash("5"),
        regions: [
          {
            evidence: "Header detected from exact source cells",
            firstRow: 2,
            kind: "header",
            lastRow: 2,
            requiresConfirmation: false,
          },
          {
            evidence: "One synthetic source data row",
            firstRow: 3,
            kind: "data",
            lastRow: 3,
            requiresConfirmation: false,
          },
        ],
        schemaVersion: "tooling-import.v1",
        snapshotHash: hash("6"),
        sourceSignature: hash("7"),
        sourceSnapshotHash: hash("4"),
        worksheetName: "Tooling List",
      },
    ],
    jobs: jobState ? [toolingImportJob(jobState)] : [],
    mappingAuthority: toolingImportMappingAuthority,
    mappingProposals: [
      {
        batchGlobalId: toolingImportIds.batch,
        createdAt: "2026-08-09T07:10:00Z",
        createdByUserId: "tooling.engineer@example.invalid",
        customerScopeId: "SYNTHETIC-CUSTOMER",
        entries: [
          {
            disposition: "candidate",
            semanticClassification: "identity",
            sourceHeader: "Tooling No.",
            sourceOrdinal: 1,
            targetFieldCandidate: "tooling_number",
            targetObjectCandidate: "tooling_master",
            transformationKey: "preserve_identifier",
            validationRuleKeys: ["required_value"],
          },
          {
            disposition: "candidate",
            semanticClassification: "descriptive",
            sourceHeader: "Clamp tonnage",
            sourceOrdinal: 2,
            targetFieldCandidate: "clamp_tonnage",
            targetObjectCandidate: "tooling_master",
            transformationKey: "normalize_unit",
            validationRuleKeys: ["supported_unit"],
          },
        ],
        globalId: toolingImportIds.mappingRevision,
        inspectionGlobalId: toolingImportIds.inspection,
        inspectionSnapshotHash: hash("6"),
        mappingGlobalId: toolingImportIds.mapping,
        mappingVersion: 1,
        reason: "Approved synthetic fixture proposal",
        schemaVersion: "tooling-import.v1",
        snapshotHash: hash("8"),
        sourceSignature: hash("7"),
        sourceSnapshotHash: hash("4"),
        state: "approved_fixture",
        templateKey: "synthetic-tooling-list.v1",
      },
    ],
    permissions: toolingImportPermissions,
    previews: [
      {
        batchGlobalId: toolingImportIds.batch,
        confirmations: [],
        createdAt: "2026-08-09T07:15:00Z",
        executionEligible: true,
        globalId: toolingImportIds.previewRevision,
        inspectionGlobalId: toolingImportIds.inspection,
        inspectionSnapshotHash: hash("6"),
        mappingGlobalId: toolingImportIds.mappingRevision,
        mappingSnapshotHash: hash("8"),
        mappingState: "approved_fixture",
        predecessorGlobalId: null,
        predecessorSnapshotHash: null,
        previewGlobalId: toolingImportIds.preview,
        previewVersion: 1,
        rows: [
          {
            action: "create",
            fields: [
              {
                findings: [],
                normalizedCandidates: ["TL-SYN-001"],
                rawValue: "TL-SYN-001",
                rawValueHash: hash("b"),
                sourceHeader: "Tooling No.",
                sourceOrdinal: 1,
                stateCandidate: null,
                transformationKey: "preserve_identifier",
              },
            ],
            reasonCodes: [],
            requiresConfirmation: false,
            sourceRow: 3,
            worksheetName: "Tooling List",
          },
        ],
        schemaVersion: "tooling-import.v1",
        snapshotHash: hash("9"),
        sourceSnapshotHash: hash("4"),
        transformationPolicyVersion: "tooling-list-transform.v1",
      },
    ],
    projectGlobalId: toolingImportIds.project,
  };
}
