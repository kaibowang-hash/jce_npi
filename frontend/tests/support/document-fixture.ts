import type {
  ControlledDocumentPageViewModel,
  ControlledDocumentWorkspaceViewModel,
  DocumentFileCapabilityResultViewModel,
} from "../../src/api/document-data-source";

export const documentProjectId = "71000000-0000-4000-8000-000000000001";
export const controlledDocumentId = "71000000-0000-4000-8000-000000000002";
export const documentRevisionId = "71000000-0000-4000-8000-000000000003";
export const fileRevisionId = "71000000-0000-4000-8000-000000000004";
export const documentLockId = "71000000-0000-4000-8000-000000000005";
const hash = "a".repeat(64);
const policyId = "71000000-0000-4000-8000-000000000006";
const policyVersionId = "71000000-0000-4000-8000-000000000007";

const permissions = {
  view: true,
  create: true,
  revise: true,
  lock: true,
  recoverLock: true,
  preview: true,
  download: true,
  share: false,
  review: false,
  release: false,
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
    permissions,
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
  };
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
