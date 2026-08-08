import { describe, expect, it, vi } from "vitest";

import {
  isCreateToolingManufacturingObservationCommand,
  isCreateToolingManufacturingPlanCommand,
  isToolingManufacturingPlanCollection,
  isToolingManufacturingPlanDetail,
  LiveToolingDataSource,
  type CreateToolingManufacturingObservationCommand,
  type CreateToolingManufacturingPlanCommand,
  type ToolingManufacturingMilestoneObservationViewModel,
  type ToolingManufacturingPlanCollectionViewModel,
  type ToolingManufacturingPlanRevisionViewModel,
  type ToolingReleasedDocumentEvidenceViewModel,
} from "../../src/api/tooling-data-source";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const revisionId = "33333333-3333-4333-8333-333333333333";
const planId = "44444444-4444-4444-8444-444444444444";
const planRevisionId = "55555555-5555-4555-8555-555555555555";
const memberId = "66666666-6666-4666-8666-666666666666";
const milestoneId = "77777777-7777-4777-8777-777777777777";
const observationId = "88888888-8888-4888-8888-888888888888";
const documentRevisionId = "99999999-9999-4999-8999-999999999999";
const lifecycleId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const releaseEventId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const hash = (value: string) => value.repeat(64);

function released(): ToolingReleasedDocumentEvidenceViewModel {
  return {
    lifecycleGlobalId: lifecycleId,
    lifecycleVersion: 2,
    releaseEventGlobalId: releaseEventId,
    releaseEventHash: hash("b"),
    releaseSnapshotHash: hash("c"),
    revisionGlobalId: documentRevisionId,
    revisionSnapshotHash: hash("a"),
  };
}

function plan(): ToolingManufacturingPlanRevisionViewModel {
  return {
    budget: { amount: "125000.00", currency: "CNY" },
    designReleaseEvidence: [released()],
    engineeringEstimate: { amount: "120000", currency: "CNY" },
    evidence: [{ document: released(), role: "dfm" }],
    globalId: planRevisionId,
    milestones: [
      {
        category: "machining",
        globalId: milestoneId,
        plannedFinish: "2026-09-20",
        plannedStart: "2026-09-01",
        predecessorGlobalIds: [],
        responsibleMember: {
          globalId: memberId,
          optimisticVersion: 3,
          userId: "tooling.engineer@example.invalid",
        },
        responsibilityKind: "internal",
        sequence: 1,
        snapshotHash: hash("d"),
      },
    ],
    planGlobalId: planId,
    planVersion: 1,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    reason: "Initial controlled manufacturing plan",
    responsibleMember: {
      globalId: memberId,
      optimisticVersion: 3,
      userId: "tooling.engineer@example.invalid",
    },
    snapshotHash: hash("e"),
    sourcingStrategy: "hybrid",
    toolingMasterGlobalId: masterId,
    toolingRevisionGlobalId: revisionId,
    toolingRevisionSnapshotHash: hash("f"),
  };
}

function observation(): ToolingManufacturingMilestoneObservationViewModel {
  return {
    actualFinish: null,
    actualStart: "2026-09-02",
    evidence: [],
    globalId: observationId,
    milestoneGlobalId: milestoneId,
    milestoneSnapshotHash: hash("d"),
    note: "Machining fixture completed",
    observationVersion: 1,
    planRevisionGlobalId: planRevisionId,
    planRevisionSnapshotHash: hash("e"),
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    progressPercentage: 40,
    reportedByMember: {
      globalId: memberId,
      optimisticVersion: 3,
      userId: "tooling.engineer@example.invalid",
    },
    risk: "Cooling insert lead time",
    snapshotHash: hash("1"),
  };
}

function collection(): ToolingManufacturingPlanCollectionViewModel {
  return {
    erpProjection: {
      editableIn: "ERPNEXT",
      reasonCode: "erp_projection_unavailable",
      sourceSystem: "ERPNEXT",
      state: "unavailable",
    },
    items: [
      {
        designReleaseEvidence: {
          items: [released()],
          reasonCode: null,
          state: "satisfied",
        },
        observations: [observation()],
        plan: plan(),
      },
    ],
    manufacturingAuthorization: {
      reasonCode: "tooling_lifecycle_policy_unavailable",
      state: "unavailable",
    },
    permissions: {
      createPlan: true,
      editErpProjection: false,
      observeMilestone: true,
      transitionLifecycle: false,
      view: true,
    },
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function detail() {
  const value = collection();
  const item = value.items[0];
  if (!item) throw new Error("The manufacturing fixture is required.");
  return {
    erpProjection: value.erpProjection,
    item,
    manufacturingAuthorization: value.manufacturingAuthorization,
    permissions: value.permissions,
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function planCommand(): CreateToolingManufacturingPlanCommand {
  const value = plan();
  return {
    budget: value.budget ?? undefined,
    designReleaseEvidence: value.designReleaseEvidence,
    engineeringEstimate: value.engineeringEstimate ?? undefined,
    evidence: value.evidence,
    milestones: value.milestones.map((item) => ({
      category: item.category,
      globalId: item.globalId,
      plannedFinish: item.plannedFinish,
      plannedStart: item.plannedStart,
      predecessorGlobalIds: item.predecessorGlobalIds,
      responsibleMember: item.responsibleMember,
      responsibilityKind: item.responsibilityKind,
      sequence: item.sequence,
    })),
    reason: value.reason,
    responsibleMember: value.responsibleMember,
    sourcingStrategy: value.sourcingStrategy,
    toolingRevisionGlobalId: value.toolingRevisionGlobalId,
    toolingRevisionSnapshotHash: value.toolingRevisionSnapshotHash,
  };
}

function observationCommand(): CreateToolingManufacturingObservationCommand {
  return {
    actualStart: "2026-09-02",
    evidence: [],
    milestoneSnapshotHash: hash("d"),
    note: "Machining fixture completed",
    planRevisionSnapshotHash: hash("e"),
    progressPercentage: 40,
    risk: "Cooling insert lead time",
  };
}

function governedResponse(value: unknown, init?: RequestInit): Response {
  const headers = new Headers(init?.headers);
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Idempotency-Replayed": "false",
      "X-Request-ID": headers.get("X-Request-ID") ?? "",
      "X-Trace-ID": "trace-manufacturing-source-test",
    },
    status: init?.method === "POST" ? 201 : 200,
  });
}

describe("Tooling manufacturing live data source", () => {
  it("accepts only closed and coherent plan, milestone, release and ERP truth", () => {
    expect(isToolingManufacturingPlanCollection(collection())).toBe(true);
    expect(isToolingManufacturingPlanDetail(detail())).toBe(true);
    expect(
      isToolingManufacturingPlanCollection({
        ...collection(),
        unexpected: true,
      }),
    ).toBe(false);
    expect(
      isToolingManufacturingPlanCollection({
        ...collection(),
        toolingMasterGlobalId: projectId,
      }),
    ).toBe(false);
    expect(
      isToolingManufacturingPlanCollection({
        ...collection(),
        items: [
          {
            ...collection().items[0],
            designReleaseEvidence: {
              items: [],
              reasonCode: null,
              state: "satisfied",
            },
          },
        ],
      }),
    ).toBe(false);
  });

  it("validates an available ERP projection without adding a write capability", () => {
    const value = collection();
    expect(
      isToolingManufacturingPlanCollection({
        ...value,
        erpProjection: {
          editableIn: "ERPNEXT",
          observedAt: "2026-08-08T12:00:00Z",
          rows: [
            {
              actualCostSourceId: "ACT-001",
              amount: "100.50",
              costTypeCode: "MATERIAL",
              currency: "CNY",
              postingDate: "2026-08-08",
              purchaseInvoiceSourceId: "PINV-001",
              purchaseOrderSourceId: "PO-001",
              purchaseReceiptSourceId: "PREC-001",
              sourceRowId: "ROW-001",
              sourceRowVersion: "1",
              supplierSourceObjectId: "SUP-001",
              toolingMasterGlobalId: masterId,
            },
            {
              actualCostSourceId: "ACT-002",
              amount: "9.5",
              costTypeCode: "MATERIAL",
              currency: "CNY",
              postingDate: "2026-08-09",
              purchaseInvoiceSourceId: "PINV-002",
              purchaseOrderSourceId: "PO-002",
              purchaseReceiptSourceId: "PREC-002",
              sourceRowId: "ROW-002",
              sourceRowVersion: "1",
              supplierSourceObjectId: "SUP-001",
              toolingMasterGlobalId: masterId,
            },
          ],
          sourceSystem: "ERPNEXT",
          state: "available",
          summaries: [
            {
              amount: "110.00",
              costTypeCode: "MATERIAL",
              currency: "CNY",
              supplierSourceObjectId: "SUP-001",
              toolingMasterGlobalId: masterId,
            },
          ],
          supplier: {
            sourceObjectId: "SUP-001",
            supplierCode: "SUP-001",
            supplierName: "Synthetic supplier",
            targetVersion: "5",
          },
          targetVersion: "42",
          toolingMasterGlobalId: masterId,
        },
      }),
    ).toBe(true);
    expect(
      isToolingManufacturingPlanCollection({
        ...value,
        erpProjection: {
          ...value.erpProjection,
          writeUrl: "https://erp.invalid/write",
        },
      }),
    ).toBe(false);
  });

  it("rejects open or incomplete commands before transport", () => {
    expect(isCreateToolingManufacturingPlanCommand(planCommand())).toBe(true);
    expect(
      isCreateToolingManufacturingPlanCommand({
        ...planCommand(),
        manufacturingApproved: true,
      }),
    ).toBe(false);
    expect(
      isCreateToolingManufacturingPlanCommand({
        ...planCommand(),
        milestones: [
          {
            ...planCommand().milestones[0],
            predecessorGlobalIds: [milestoneId],
          },
        ],
      }),
    ).toBe(false);
    expect(
      isCreateToolingManufacturingObservationCommand(observationCommand()),
    ).toBe(true);
    expect(
      isCreateToolingManufacturingObservationCommand({
        ...observationCommand(),
        actualStart: undefined,
        actualFinish: "2026-09-03",
      }),
    ).toBe(false);
  });

  it("uses only the four frozen paths with governed command headers", async () => {
    const fetch = vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof request === "string"
          ? request
          : request instanceof URL
            ? request.href
            : request.url;
      const value =
        init?.method === "POST"
          ? url.endsWith("/observations")
            ? { observation: observation() }
            : {
                designReleaseEvidence:
                  collection().items[0]?.designReleaseEvidence,
                plan: plan(),
              }
          : url.endsWith(planRevisionId)
            ? detail()
            : collection();
      return Promise.resolve(governedResponse(value, init));
    });
    vi.stubGlobal("fetch", fetch);
    const source = new LiveToolingDataSource();
    const signal = new AbortController().signal;
    const context = (suffix: string) => ({
      csrfToken: "c".repeat(32),
      idempotencyKey: `tooling-manufacturing-${suffix}-12345678`,
      signal,
    });

    await source.loadManufacturingPlans(projectId, masterId, signal);
    await source.loadManufacturingPlan(
      projectId,
      masterId,
      planRevisionId,
      signal,
    );
    await source.createManufacturingPlan(
      projectId,
      masterId,
      planCommand(),
      context("plan"),
    );
    await source.createManufacturingObservation(
      projectId,
      masterId,
      planRevisionId,
      milestoneId,
      observationCommand(),
      context("observation"),
    );

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/manufacturing-plans`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/manufacturing-plans/${planRevisionId}`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/manufacturing-plans`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/manufacturing-plans/${planRevisionId}/milestones/${milestoneId}/observations`,
    ]);
    expect(
      fetch.mock.calls
        .filter(([, init]) => init?.method === "POST")
        .every(([, init]) => {
          const headers = new Headers(init?.headers);
          return (
            headers.get("X-Frappe-CSRF-Token") === "c".repeat(32) &&
            headers.get("Idempotency-Key")?.startsWith("tooling-manufacturing-")
          );
        }),
    ).toBe(true);
  });
});
