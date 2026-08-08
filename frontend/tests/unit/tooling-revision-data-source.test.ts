import { describe, expect, it, vi } from "vitest";

import {
  isCreatePartControlledSpecificationCommand,
  isCreateToolingProcessChainRevisionCommand,
  isCreateToolingRevisionCommand,
  isPartControlledSpecificationContext,
  isToolingProcessChainCollection,
  isToolingRevisionCollection,
  isToolingRevisionDetail,
  LiveToolingDataSource,
  type CreatePartControlledSpecificationCommand,
  type CreateToolingProcessChainRevisionCommand,
  type CreateToolingRevisionCommand,
  type PartControlledSpecificationContextViewModel,
  type ToolingMeasurementViewModel,
  type ToolingProcessChainCollectionViewModel,
  type ToolingProcessChainRevisionViewModel,
  type ToolingRevisionCollectionViewModel,
  type ToolingRevisionDetailViewModel,
  type ToolingRevisionViewModel,
} from "../../src/api/tooling-data-source";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const toolingRevisionId = "33333333-3333-4333-8333-333333333333";
const applicabilityId = "44444444-4444-4444-8444-444444444444";
const cavityId = "55555555-5555-4555-8555-555555555555";
const partId = "66666666-6666-4666-8666-666666666666";
const partRevisionId = "77777777-7777-4777-8777-777777777777";
const controlledSpecificationId = "88888888-8888-4888-8888-888888888888";
const specificationItemId = "99999999-9999-4999-8999-999999999999";
const processChainId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const processChainRevisionId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const firstStepId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const secondStepId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

const unavailable = {
  combinedTrial: {
    reasonCode: "combined_trial_not_delivered" as const,
    state: "unavailable" as const,
  },
  erpLocationAndAsset: {
    reasonCode: "erp_projection_unavailable" as const,
    state: "unavailable" as const,
  },
  lifecycle: {
    reasonCode: "lifecycle_policy_unavailable" as const,
    state: "unavailable" as const,
  },
  supplier: {
    reasonCode: "formal_supplier_unavailable" as const,
    state: "unavailable" as const,
  },
};

const permissions = {
  bindSetSource: true,
  createPartSpecification: true,
  createProcessChain: true,
  createRevision: true,
  transitionLifecycle: false as const,
  view: true,
};

function measurement(value: string, unit: string): ToolingMeasurementViewModel {
  return { source: "Engineering", unit, value };
}

function revision(): ToolingRevisionViewModel {
  return {
    cavities: [
      {
        cavityIdentifier: "C01",
        globalId: cavityId,
        partRevisionGlobalId: partRevisionId,
        structuralState: "enabled",
        toolingApplicabilityGlobalId: applicabilityId,
      },
    ],
    designDocumentRevisions: [],
    externalIdentities: [],
    globalId: toolingRevisionId,
    inserts: [],
    predecessorGlobalId: null,
    reason: "Initial controlled Revision",
    revisionLabel: "R1",
    revisionNumber: 1,
    snapshotHash: "a".repeat(64),
    specification: {
      cavityCount: 1,
      clampTonnage: measurement("180", "t"),
      coreMaterial: "H13",
      customerStandard: "STD-001",
      deliveryDocuments: ["Inspection report"],
      hardness: measurement("48", "HRC"),
      height: measurement("320", "mm"),
      hotRunner: "Valve gate",
      injectionCapacity: measurement("450", "g"),
      interfaceRequirement: "EUROMAP",
      length: measurement("600", "mm"),
      machineType: "Injection molding",
      moldBaseMaterial: "P20",
      spareParts: ["Seal kit"],
      surfaceTreatment: "Nitrided",
      targetCycle: measurement("35", "s"),
      targetLife: measurement("500000", "cycles"),
      tieBarSpacingX: measurement("700", "mm"),
      tieBarSpacingY: measurement("650", "mm"),
      toolingType: "Two-plate mold",
      warranty: "12 months",
      weight: measurement("820", "kg"),
      width: measurement("520", "mm"),
    },
    toolingMasterGlobalId: masterId,
  };
}

function revisionCollection(): ToolingRevisionCollectionViewModel {
  return {
    ...unavailable,
    items: [revision()],
    permissions,
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function revisionDetail(): ToolingRevisionDetailViewModel {
  return {
    ...unavailable,
    permissions,
    projectGlobalId: projectId,
    revision: revision(),
  };
}

function partContext(): PartControlledSpecificationContextViewModel {
  return {
    automaticImpact: {
      reasonCode: "automatic_impact_not_delivered",
      state: "unavailable",
    },
    controlledSpecification: {
      externalIdentities: [],
      globalId: controlledSpecificationId,
      items: [
        {
          effectiveFrom: "2026-08-08",
          effectiveTo: null,
          globalId: specificationItemId,
          kind: "material_family",
          normalizedValue: "PA66",
          rawValue: "PA66",
          sourceObjectId: "PART-SPEC-001",
          sourceSystem: "NPI_ONE",
          unit: null,
        },
      ],
      partGlobalId: partId,
      partRevisionGlobalId: partRevisionId,
      partRevisionSnapshotHash: "b".repeat(64),
      snapshotHash: "c".repeat(64),
    },
    partGlobalId: partId,
    partRevision: {
      globalId: partRevisionId,
      partGlobalId: partId,
      revisionLabel: "A",
      revisionNumber: 1,
      snapshotHash: "b".repeat(64),
    },
    permissions,
    projectGlobalId: projectId,
  };
}

function processChain(): ToolingProcessChainRevisionViewModel {
  return {
    chainVersion: 1,
    globalId: processChainRevisionId,
    predecessorGlobalId: null,
    processChainGlobalId: processChainId,
    reason: "Initial ordered route",
    snapshotHash: "d".repeat(64),
    steps: [
      {
        clampTonnage: measurement("180", "t"),
        globalId: firstStepId,
        inputPartRevisionGlobalIds: [partRevisionId],
        machineType: "Injection molding",
        outputPartRevisionGlobalId: partRevisionId,
        parentStepGlobalId: null,
        processKind: "primary_molding",
        stepOrder: 1,
        toolingRevisionGlobalId: toolingRevisionId,
        toolingRevisionSnapshotHash: "a".repeat(64),
      },
      {
        clampTonnage: measurement("120", "t"),
        globalId: secondStepId,
        inputPartRevisionGlobalIds: [partRevisionId],
        machineType: "Overmolding",
        outputPartRevisionGlobalId: partRevisionId,
        parentStepGlobalId: firstStepId,
        processKind: "overmold",
        stepOrder: 2,
        toolingRevisionGlobalId: toolingRevisionId,
        toolingRevisionSnapshotHash: "a".repeat(64),
      },
    ],
  };
}

function chainCollection(): ToolingProcessChainCollectionViewModel {
  return {
    combinedTrial: unavailable.combinedTrial,
    items: [processChain()],
    permissions,
    projectGlobalId: projectId,
  };
}

function revisionCommand(): CreateToolingRevisionCommand {
  const value = revision();
  return {
    cavities: value.cavities.map((item) => ({
      cavityIdentifier: item.cavityIdentifier,
      partRevisionGlobalId: item.partRevisionGlobalId,
      structuralState: item.structuralState,
      toolingApplicabilityGlobalId: item.toolingApplicabilityGlobalId,
    })),
    designDocumentRevisions: [],
    externalIdentities: [],
    inserts: [],
    reason: value.reason,
    revisionLabel: value.revisionLabel,
    specification: value.specification,
  };
}

function partCommand(): CreatePartControlledSpecificationCommand {
  return {
    externalIdentities: [],
    items: [
      {
        effectiveFrom: "2026-08-08",
        kind: "material_family",
        normalizedValue: "PA66",
        rawValue: "PA66",
        sourceObjectId: "PART-SPEC-001",
        sourceSystem: "NPI_ONE",
      },
    ],
  };
}

function chainCommand(): CreateToolingProcessChainRevisionCommand {
  return {
    reason: "Initial ordered route",
    steps: [
      {
        clampTonnage: measurement("180", "t"),
        inputPartRevisionGlobalIds: [partRevisionId],
        machineType: "Injection molding",
        outputPartRevisionGlobalId: partRevisionId,
        processKind: "primary_molding",
        stepOrder: 1,
        toolingRevisionGlobalId: toolingRevisionId,
      },
      {
        clampTonnage: measurement("120", "t"),
        inputPartRevisionGlobalIds: [partRevisionId],
        machineType: "Overmolding",
        outputPartRevisionGlobalId: partRevisionId,
        parentStepOrder: 1,
        processKind: "overmold",
        stepOrder: 2,
        toolingRevisionGlobalId: toolingRevisionId,
      },
    ],
  };
}

function governedResponse(value: unknown, init?: RequestInit): Response {
  const headers = new Headers(init?.headers);
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Idempotency-Replayed": "false",
      "X-Request-ID": headers.get("X-Request-ID") ?? "",
      "X-Trace-ID": "trace-tooling-revision-test",
    },
    status: init?.method === "POST" ? 201 : 200,
  });
}

describe("Tooling Revision live data source", () => {
  it("accepts only closed, coherent Revision, Part specification and process-chain graphs", () => {
    expect(isToolingRevisionCollection(revisionCollection())).toBe(true);
    expect(isToolingRevisionDetail(revisionDetail())).toBe(true);
    expect(isPartControlledSpecificationContext(partContext())).toBe(true);
    expect(
      isPartControlledSpecificationContext({
        ...partContext(),
        controlledSpecification: {
          reasonCode: "controlled_part_specification_not_recorded",
          state: "unavailable",
        },
      }),
    ).toBe(true);
    expect(isToolingProcessChainCollection(chainCollection())).toBe(true);
    expect(
      isToolingRevisionCollection({
        ...revisionCollection(),
        unexpected: true,
      }),
    ).toBe(false);
    expect(
      isPartControlledSpecificationContext({
        ...partContext(),
        partGlobalId: masterId,
      }),
    ).toBe(false);
  });

  it("rejects open or semantically incomplete commands before transport", () => {
    expect(isCreateToolingRevisionCommand(revisionCommand())).toBe(true);
    expect(
      isCreateToolingRevisionCommand({
        ...revisionCommand(),
        unexpected: true,
      }),
    ).toBe(false);
    expect(isCreatePartControlledSpecificationCommand(partCommand())).toBe(
      true,
    );
    expect(isCreateToolingProcessChainRevisionCommand(chainCommand())).toBe(
      true,
    );
    expect(
      isCreateToolingProcessChainRevisionCommand({
        ...chainCommand(),
        steps: chainCommand().steps.map((step) => ({
          ...step,
          parentStepOrder: 9,
        })),
      }),
    ).toBe(false);
  });

  it("uses only the frozen query and command paths with governed headers", async () => {
    const fetch = vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof request === "string"
          ? request
          : request instanceof URL
            ? request.href
            : request.url;
      const value = url.includes("controlled-specification")
        ? partContext()
        : url.includes("tooling-process-chains")
          ? url.endsWith("tooling-process-chains") && init?.method !== "POST"
            ? chainCollection()
            : processChain()
          : url.endsWith("revisions") && init?.method !== "POST"
            ? revisionCollection()
            : revisionDetail();
      return Promise.resolve(governedResponse(value, init));
    });
    vi.stubGlobal("fetch", fetch);
    const dataSource = new LiveToolingDataSource();
    const signal = new AbortController().signal;
    const context = (suffix: string) => ({
      csrfToken: "c".repeat(32),
      idempotencyKey: `tooling-revision-${suffix}-12345678`,
      signal,
    });

    await dataSource.loadToolingRevisions(projectId, masterId, signal);
    await dataSource.loadToolingRevision(
      projectId,
      masterId,
      toolingRevisionId,
      signal,
    );
    await dataSource.createToolingRevision(
      projectId,
      masterId,
      revisionCommand(),
      context("create"),
    );
    await dataSource.loadPartControlledSpecification(
      projectId,
      partId,
      partRevisionId,
      signal,
    );
    await dataSource.createPartControlledSpecification(
      projectId,
      partId,
      partRevisionId,
      partCommand(),
      context("part"),
    );
    await dataSource.loadToolingProcessChains(projectId, signal);
    await dataSource.loadToolingProcessChain(
      projectId,
      processChainRevisionId,
      signal,
    );
    await dataSource.createToolingProcessChainRevision(
      projectId,
      chainCommand(),
      context("chain"),
    );

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/revisions`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/revisions/${toolingRevisionId}`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/revisions`,
      `/api/npi/v1/projects/${projectId}/parts/${partId}/revisions/${partRevisionId}/controlled-specification`,
      `/api/npi/v1/projects/${projectId}/parts/${partId}/revisions/${partRevisionId}/controlled-specification`,
      `/api/npi/v1/projects/${projectId}/tooling-process-chains`,
      `/api/npi/v1/projects/${projectId}/tooling-process-chains/${processChainRevisionId}`,
      `/api/npi/v1/projects/${projectId}/tooling-process-chains`,
    ]);
    expect(
      fetch.mock.calls
        .filter(([, init]) => init?.method === "POST")
        .every(([, init]) => {
          const headers = new Headers(init?.headers);
          return (
            headers.get("X-Frappe-CSRF-Token") === "c".repeat(32) &&
            headers.get("Idempotency-Key")?.startsWith("tooling-revision-")
          );
        }),
    ).toBe(true);
  });
});
