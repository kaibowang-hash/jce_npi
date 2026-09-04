import type {
  ControlledPrintCapabilityViewModel,
  ControlledPrintSnapshotViewModel,
  ControlledPrintSourceIdentity,
} from "../../src/api/controlled-print-data-source";

export const controlledPrintProjectId = "11111111-1111-4111-8111-111111111111";
export const controlledPrintSnapshotId = "81000000-0000-4000-8000-000000000001";
export const controlledPrintOutputId = "81000000-0000-4000-8000-000000000002";
export const controlledPrintMappingId = "81000000-0000-4000-8000-000000000003";
export const controlledPrintRegistryId = "81000000-0000-4000-8000-000000000004";

const hashA = "a".repeat(64);
const hashB = "b".repeat(64);
const hashC = "c".repeat(64);
const hashD = "d".repeat(64);
const hashE = "e".repeat(64);

export function controlledPrintSourceFixture(): ControlledPrintSourceIdentity {
  return {
    sourceGlobalId: controlledPrintProjectId,
    sourceKind: "npi.project",
    sourceVersion: 3,
  };
}

export function controlledPrintCapabilityFixture(
  available = true,
): ControlledPrintCapabilityViewModel {
  return {
    ...controlledPrintSourceFixture(),
    available,
    copyState: available ? "not_numbered" : null,
    deliveryMode: available ? "controlled_pdf" : null,
    language: "en",
    permissions: { create: available, download: available },
    registry: available
      ? {
          globalId: controlledPrintMappingId,
          registryGlobalId: controlledPrintRegistryId,
          snapshotHash: hashA,
          templateSha256: hashB,
          version: 2,
        }
      : null,
  };
}

export function controlledPrintSnapshotFixture(): ControlledPrintSnapshotViewModel {
  return {
    actorUserId: "printer@example.invalid",
    copyState: "not_numbered",
    deliveryMode: "controlled_pdf",
    globalId: controlledPrintSnapshotId,
    language: "en",
    output: {
      fileName: "controlled-project-001.pdf",
      globalId: controlledPrintOutputId,
      mimeType: "application/pdf",
      recordHash: hashE,
      sha256: hashD,
      sizeBytes: 4,
    },
    printedAt: "2026-08-07T03:30:00Z",
    registry: {
      globalId: controlledPrintMappingId,
      registryGlobalId: controlledPrintRegistryId,
      snapshotHash: hashA,
      templateSha256: hashB,
      version: 2,
    },
    snapshotHash: hashC,
    source: {
      ...controlledPrintSourceFixture(),
      sourceSnapshotHash: hashB,
      sourceState: "active",
    },
    verificationPayload: `urn:npi:controlled-print:${controlledPrintSnapshotId}:${hashC}`,
    version: 1,
    watermarkSource: "Controlled output",
  };
}
