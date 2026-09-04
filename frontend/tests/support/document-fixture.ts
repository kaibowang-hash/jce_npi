import type {
  ControlledDocumentPageViewModel,
  ControlledDocumentWorkspaceViewModel,
  DocumentBaselineCommandViewModel,
  DocumentBaselineWorkspaceViewModel,
  DocumentFileCapabilityResultViewModel,
  DocumentReleaseTransitionViewModel,
} from "../../src/api/document-data-source";

export const documentProjectId = "71000000-0000-4000-8000-000000000001";
export const controlledDocumentId = "71000000-0000-4000-8000-000000000002";
export const documentRevisionId = "71000000-0000-4000-8000-000000000003";
export const fileRevisionId = "71000000-0000-4000-8000-000000000004";
export const documentLockId = "71000000-0000-4000-8000-000000000005";
const hash = "a".repeat(64);
const policyId = "71000000-0000-4000-8000-000000000006";
const policyVersionId = "71000000-0000-4000-8000-000000000007";
export const releasePolicyId = "71000000-0000-4000-8000-000000000012";
export const baselinePolicyId = "71000000-0000-4000-8000-000000000023";
export const documentBaselineId = "71000000-0000-4000-8000-000000000024";

const permissions = {
  view: true,
  create: true,
  revise: true,
  lock: true,
  recoverLock: true,
  preview: true,
  download: true,
  share: false,
  submitReview: false,
  resubmitReview: false,
  review: false,
  approve: false,
  release: false,
  supersede: false,
  obsolete: false,
} as const;

const project = {
  globalId: documentProjectId,
  businessCode: "NPI-2026-071",
  title: "Synthetic Project",
  lifecycleState: "active",
  optimisticVersion: 4,
} as const;

const policy = {
  globalId: policyId,
  versionId: policyVersionId,
  version: 1,
  snapshotHash: hash,
  key: "synthetic.document.policy",
  title: "Synthetic document policy",
  documentTypes: [
    {
      key: "drawing",
      prefix: "DRW",
      titleSource: "Drawing",
    },
  ],
  confidentialityKeys: ["internal"],
  allowedMimeTypes: ["application/pdf"],
  previewMimeTypes: ["application/pdf"],
  maximumFileBytes: 1_048_576,
  lockLeaseMinutes: 30,
} as const;

const capabilities = {
  integrity: {
    state: "available",
    reasonCode: "integrity_verified",
  },
  preview: {
    state: "available",
    reasonCode: "native_preview_available",
    mode: "native_pdf",
  },
  download: {
    state: "available",
    reasonCode: "download_available",
  },
  externalRetrieval: {
    state: "unavailable",
    reasonCode: "external_access_policy_unavailable",
  },
  connector: {
    state: "unavailable",
    reasonCode: "connector_not_configured",
  },
} as const;

const document = {
  globalId: controlledDocumentId,
  documentNumber: "DRW-000071",
  documentTypeKey: "drawing",
  title: "Synthetic cavity drawing",
  confidentialityKey: "internal",
  documentPolicyRef: {
    globalId: policyId,
    version: 1,
    snapshotHash: hash,
  },
  currentRevision: {
    globalId: documentRevisionId,
    major: 0,
    minor: 1,
    snapshotHash: hash,
  },
  currentLock: {
    globalId: documentLockId,
    version: 1,
    holderUserId: "administrator@example.invalid",
    expiresAt: "2026-07-30T15:00:00Z",
  },
  source: {
    sourceSystem: "NPI_ONE",
    editableIn: "NPI_ONE",
    syncState: "local",
  },
  optimisticVersion: 3,
} as const;

export function controlledDocumentPageFixture(): ControlledDocumentPageViewModel {
  return {
    project,
    permissions,
    policies: [policy],
    items: [document],
    nextCursor: null,
  };
}

export function controlledDocumentWorkspaceFixture(): ControlledDocumentWorkspaceViewModel {
  return {
    project,
    permissions: {
      ...permissions,
      submitReview: true,
    },
    document,
    revisions: [
      {
        globalId: documentRevisionId,
        major: 0,
        minor: 1,
        state: "draft",
        reason: "Initial synthetic revision",
        effectiveDate: "2026-07-30",
        predecessorRevisionId: null,
        snapshotHash: hash,
        optimisticVersion: 1,
        createdByUserId: "administrator@example.invalid",
        createdAt: "2026-07-30T14:30:00Z",
        files: [
          {
            associationId: "71000000-0000-4000-8000-000000000008",
            role: "primary",
            provenance: "manual_upload",
            connector: {
              state: "unavailable",
              reasonCode: "connector_not_configured",
            },
            globalId: fileRevisionId,
            fileDocumentId: "71000000-0000-4000-8000-000000000009",
            revision: 1,
            optimisticVersion: 1,
            fileName: "synthetic-drawing.pdf",
            mimeType: "application/pdf",
            sizeBytes: 4,
            sha256: hash,
            scanState: "clean",
            scanObservedAt: "2026-07-30T14:31:00Z",
            private: true,
            released: false,
            capabilities,
          },
        ],
      },
    ],
    relationships: [
      {
        globalId: "71000000-0000-4000-8000-000000000010",
        kind: "project",
        projectReferenceType: null,
        targetSourceSystem: null,
        targetReferenceGlobalId: null,
        targetIdentity: documentProjectId,
        targetVersion: 4,
        snapshotHash: hash,
      },
    ],
    lockHistory: [
      {
        globalId: "71000000-0000-4000-8000-000000000011",
        lockId: documentLockId,
        version: 1,
        eventType: "acquired",
        holderUserId: "administrator@example.invalid",
        actorUserId: "administrator@example.invalid",
        acquiredAt: "2026-07-30T14:30:00Z",
        expiresAt: "2026-07-30T15:00:00Z",
        occurredAt: "2026-07-30T14:30:00Z",
        reason: null,
        snapshotHash: hash,
      },
    ],
    externalRetrieval: {
      state: "unavailable",
      reasonCode: "external_access_policy_unavailable",
    },
    releaseWorkspace: {
      available: true,
      commandsEnabled: true,
      reasonCode: "available",
      policies: [
        {
          globalId: releasePolicyId,
          version: 1,
          snapshotHash: hash,
          key: "synthetic.document.release",
          title: "Synthetic document release policy",
          requiredApprovalCount: 1,
          confirmationMethod: "authenticated_session_confirmation",
        },
      ],
      revisions: [
        {
          revisionId: documentRevisionId,
          lifecycle: {
            state: "draft",
            version: 0,
            activeCycleId: null,
            approvedCycleId: null,
            approvedEventId: null,
            releaseEventId: null,
            releaseSnapshotHash: null,
            replacementRevisionId: null,
            replacementEffectiveDate: null,
            terminalEventId: null,
          },
          capabilities: {
            submitReview: true,
            resubmitReview: false,
            review: false,
            approve: false,
            release: false,
            supersede: false,
            obsolete: false,
          },
          cycles: [],
          confirmations: [],
          events: [],
        },
      ],
    },
  };
}

export function controlledDocumentInReviewWorkspaceFixture(): ControlledDocumentWorkspaceViewModel {
  const workspace = controlledDocumentWorkspaceFixture();
  const cycleId = "71000000-0000-4000-8000-000000000013";
  return {
    ...workspace,
    permissions: {
      ...workspace.permissions,
      submitReview: false,
      review: true,
      approve: true,
    },
    releaseWorkspace: {
      ...workspace.releaseWorkspace,
      revisions: [
        {
          revisionId: documentRevisionId,
          lifecycle: {
            state: "in_review",
            version: 1,
            activeCycleId: cycleId,
            approvedCycleId: null,
            approvedEventId: null,
            releaseEventId: null,
            releaseSnapshotHash: null,
            replacementRevisionId: null,
            replacementEffectiveDate: null,
            terminalEventId: null,
          },
          capabilities: {
            submitReview: false,
            resubmitReview: false,
            review: true,
            approve: true,
            release: false,
            supersede: false,
            obsolete: false,
          },
          cycles: [
            {
              globalId: cycleId,
              cycleNumber: 1,
              state: "active",
              policy: {
                globalId: releasePolicyId,
                version: 1,
                snapshotHash: hash,
              },
              evidenceSnapshotHash: hash,
              fileEvidence: [
                {
                  fileRevisionId,
                  associationId: "71000000-0000-4000-8000-000000000008",
                  mimeType: "application/pdf",
                  sizeBytes: 4,
                  sha256: hash,
                  scanState: "clean",
                  scanObservedAt: "2026-07-30T14:31:00Z",
                  uploadedByUserId: "administrator@example.invalid",
                  uploadedAt: "2026-07-30T14:30:00Z",
                },
              ],
              reviewerAssignments: [
                {
                  slotKey: "engineering_reviewer",
                  userId: "reviewer@example.invalid",
                  state: "pending",
                  confirmationId: null,
                },
              ],
              requiredApprovalCount: 1,
              priorRejectedCycleId: null,
              submittedByUserId: "administrator@example.invalid",
              submittedAt: "2026-07-30T14:32:00Z",
              requestId: "71000000-0000-4000-8000-000000000020",
              traceId: "trace-p5-02-submit-review",
              snapshotHash: hash,
            },
          ],
          confirmations: [],
          events: [
            {
              globalId: "71000000-0000-4000-8000-000000000014",
              type: "submitted",
              fromState: "draft",
              toState: "in_review",
              fromVersion: 0,
              toVersion: 1,
              cycleId,
              confirmationHashes: [],
              replacementRevisionId: null,
              replacementEffectiveDate: null,
              actorUserId: "administrator@example.invalid",
              occurredAt: "2026-07-30T14:32:00Z",
              requestId: "71000000-0000-4000-8000-000000000020",
              traceId: "trace-p5-02-submit-review",
              eventHash: hash,
            },
          ],
        },
      ],
    },
  };
}

export function controlledDocumentReleasedWorkspaceFixture(): ControlledDocumentWorkspaceViewModel {
  const workspace = controlledDocumentInReviewWorkspaceFixture();
  const history = workspace.releaseWorkspace.revisions[0];
  const revision = workspace.revisions[0];
  if (!history || !revision)
    throw new Error("The released document fixture requires one revision.");
  const cycle = history.cycles[0];
  if (!cycle)
    throw new Error("The released document fixture requires one review cycle.");
  const cycleId = cycle.globalId;
  const approvalId = "71000000-0000-4000-8000-000000000015";
  const approvalEventId = "71000000-0000-4000-8000-000000000016";
  const releaseConfirmationId = "71000000-0000-4000-8000-000000000017";
  const releaseEventId = "71000000-0000-4000-8000-000000000018";
  return {
    ...workspace,
    permissions: {
      ...workspace.permissions,
      review: false,
      approve: false,
      supersede: true,
      obsolete: true,
    },
    revisions: [
      {
        ...revision,
        files: revision.files.map((file) => ({
          ...file,
          optimisticVersion: 2,
          released: true,
        })),
      },
    ],
    releaseWorkspace: {
      ...workspace.releaseWorkspace,
      revisions: [
        {
          ...history,
          lifecycle: {
            state: "released",
            version: 3,
            activeCycleId: null,
            approvedCycleId: cycleId,
            approvedEventId: approvalEventId,
            releaseEventId,
            releaseSnapshotHash: hash,
            replacementRevisionId: null,
            replacementEffectiveDate: null,
            terminalEventId: null,
          },
          capabilities: {
            submitReview: false,
            resubmitReview: false,
            review: false,
            approve: false,
            release: false,
            supersede: true,
            obsolete: true,
          },
          cycles: [
            {
              ...cycle,
              state: "approved",
              reviewerAssignments: [
                {
                  slotKey: "engineering_reviewer",
                  userId: "reviewer@example.invalid",
                  state: "approved",
                  confirmationId: approvalId,
                },
              ],
            },
          ],
          confirmations: [
            {
              globalId: approvalId,
              cycleId,
              type: "review_approve",
              actorUserId: "reviewer@example.invalid",
              authoritySlot: "engineering_reviewer",
              confirmationMethod: "authenticated_session_confirmation",
              confirmationIntent: "review_decision",
              reason: null,
              confirmedAt: "2026-07-30T14:34:00Z",
              requestId: "71000000-0000-4000-8000-000000000021",
              traceId: "trace-p5-02-approve-review",
              evidenceHash: hash,
            },
            {
              globalId: releaseConfirmationId,
              cycleId,
              type: "release",
              actorUserId: "administrator@example.invalid",
              authoritySlot: "final_release_authority",
              confirmationMethod: "authenticated_session_confirmation",
              confirmationIntent: "release_revision",
              reason: null,
              confirmedAt: "2026-07-30T14:36:00Z",
              requestId: "71000000-0000-4000-8000-000000000022",
              traceId: "trace-p5-02-release-revision",
              evidenceHash: "b".repeat(64),
            },
          ],
          events: [
            ...history.events,
            {
              globalId: approvalEventId,
              type: "approved",
              fromState: "in_review",
              toState: "approved",
              fromVersion: 1,
              toVersion: 2,
              cycleId,
              confirmationHashes: [hash],
              replacementRevisionId: null,
              replacementEffectiveDate: null,
              actorUserId: "reviewer@example.invalid",
              occurredAt: "2026-07-30T14:34:00Z",
              requestId: "71000000-0000-4000-8000-000000000021",
              traceId: "trace-p5-02-approve-review",
              eventHash: "b".repeat(64),
            },
            {
              globalId: releaseEventId,
              type: "released",
              fromState: "approved",
              toState: "released",
              fromVersion: 2,
              toVersion: 3,
              cycleId,
              confirmationHashes: [hash, "b".repeat(64)],
              replacementRevisionId: null,
              replacementEffectiveDate: null,
              actorUserId: "administrator@example.invalid",
              occurredAt: "2026-07-30T14:36:00Z",
              requestId: "71000000-0000-4000-8000-000000000022",
              traceId: "trace-p5-02-release-revision",
              eventHash: "c".repeat(64),
            },
          ],
        },
      ],
    },
  };
}

export function documentBaselineWorkspaceFixture(): DocumentBaselineWorkspaceViewModel {
  const baseline = {
    globalId: documentBaselineId,
    label: "G2 synthetic release package",
    version: 1 as const,
    snapshotHash: "d".repeat(64),
    policy: {
      globalId: baselinePolicyId,
      version: 1,
      snapshotHash: "e".repeat(64),
    },
    createdByUserId: "administrator@example.invalid",
    createdAt: "2026-07-30T15:00:00Z",
    members: [
      {
        globalId: "71000000-0000-4000-8000-000000000025",
        sequence: 1,
        documentGlobalId: controlledDocumentId,
        revisionGlobalId: documentRevisionId,
        major: 0,
        minor: 1,
        revisionSnapshotHash: hash,
        lifecycleVersion: 3,
        releaseEventGlobalId: "71000000-0000-4000-8000-000000000018",
        releaseSnapshotHash: hash,
        memberHash: "f".repeat(64),
        files: [
          {
            fileRevisionGlobalId: fileRevisionId,
            fileDocumentGlobalId: "71000000-0000-4000-8000-000000000009",
            fileName: "synthetic-drawing.pdf",
            mimeType: "application/pdf",
            sizeBytes: 4,
            sha256: hash,
            scanState: "clean" as const,
          },
        ],
      },
    ],
  };
  return {
    project: {
      globalId: documentProjectId,
      projectCode: project.businessCode,
      projectName: project.title,
    },
    permissions: { view: true, create: true },
    policies: [
      {
        globalId: baselinePolicyId,
        version: 1,
        snapshotHash: "e".repeat(64),
        key: "synthetic.baseline.policy",
        title: "Synthetic baseline policy",
      },
    ],
    items: [baseline],
    impacts: [
      {
        globalId: "71000000-0000-4000-8000-000000000026",
        eventType: "invalidated",
        dependencyGlobalId: "71000000-0000-4000-8000-000000000027",
        baselineGlobalId: documentBaselineId,
        baselineSnapshotHash: baseline.snapshotHash,
        oldRevisionGlobalId: documentRevisionId,
        oldRevisionSnapshotHash: hash,
        newRevisionGlobalId: "71000000-0000-4000-8000-000000000028",
        newRevisionSnapshotHash: "1".repeat(64),
        gateGlobalId: "71000000-0000-4000-8000-000000000029",
        requirementGlobalId: "71000000-0000-4000-8000-000000000030",
        evidenceReferenceGlobalId: "71000000-0000-4000-8000-000000000031",
        initiatedByUserId: "administrator@example.invalid",
        occurredAt: "2026-07-30T16:00:00Z",
        eventHash: "2".repeat(64),
      },
    ],
  };
}

export function documentBaselineCommandFixture(): DocumentBaselineCommandViewModel {
  const workspace = documentBaselineWorkspaceFixture();
  const baseline = workspace.items[0];
  if (!baseline)
    throw new Error("The Document baseline fixture requires one baseline.");
  return { projectId: documentProjectId, baseline };
}

export function documentFileCapabilityFixture(): DocumentFileCapabilityResultViewModel {
  const workspace = controlledDocumentWorkspaceFixture();
  const file = workspace.revisions[0]?.files[0];
  if (!file) throw new Error("The document file fixture is unavailable.");
  return {
    projectId: documentProjectId,
    documentId: controlledDocumentId,
    revisionId: documentRevisionId,
    fileRevisionId,
    file: {
      globalId: file.globalId,
      fileDocumentId: file.fileDocumentId,
      revision: file.revision,
      optimisticVersion: file.optimisticVersion,
      fileName: file.fileName,
      mimeType: file.mimeType,
      sizeBytes: file.sizeBytes,
      sha256: file.sha256,
      scanState: file.scanState,
      scanObservedAt: file.scanObservedAt,
      private: file.private,
      released: file.released,
    },
    capabilities: file.capabilities,
  };
}

export function documentReleaseTransitionFixture(
  overrides: Partial<DocumentReleaseTransitionViewModel> = {},
): DocumentReleaseTransitionViewModel {
  return {
    projectId: documentProjectId,
    documentId: controlledDocumentId,
    documentOptimisticVersion: 3,
    revisionId: documentRevisionId,
    state: "in_review",
    lifecycleVersion: 1,
    reviewCycleId: "71000000-0000-4000-8000-000000000013",
    releasePolicy: {
      globalId: releasePolicyId,
      version: 1,
      snapshotHash: hash,
    },
    event: {
      globalId: "71000000-0000-4000-8000-000000000014",
      type: "submitted",
      snapshotHash: hash,
    },
    confirmation: null,
    releaseSnapshotHash: null,
    ...overrides,
  };
}
