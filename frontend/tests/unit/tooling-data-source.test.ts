import { describe, expect, it, vi } from "vitest";

import {
  isToolingSetCollectionResponse,
  isToolingSetDetailResponse,
  isToolingCockpitResponse,
  LiveToolingDataSource,
  ToolingRequestCancelledError,
  type ToolingCockpitViewModel,
  type ToolingSetCollectionViewModel,
  type ToolingSetDetailViewModel,
} from "../../src/api/tooling-data-source";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const partId = "33333333-3333-4333-8333-333333333333";
const revisionId = "44444444-4444-4444-8444-444444444444";
const requirementId = "55555555-5555-4555-8555-555555555555";
const applicabilityId = "66666666-6666-4666-8666-666666666666";
const relationshipId = "77777777-7777-4777-8777-777777777777";
const setId = "88888888-8888-4888-8888-888888888888";
const intakeId = "99999999-9999-4999-8999-999999999999";
const inspectionIds = [
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5",
] as const;
const differenceId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const evidenceId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const fileRevisionId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const source = {
  editableIn: "NPI_ONE" as const,
  sourceSystem: "NPI_ONE" as const,
  syncState: "local" as const,
};

function fixture(): ToolingCockpitViewModel {
  return {
    applicability: [
      {
        effectiveFrom: "2026-08-07",
        effectiveTo: null,
        globalId: applicabilityId,
        model: null,
        part: {
          globalId: revisionId,
          partGlobalId: partId,
          revisionLabel: "A",
          revisionNumber: 1,
          snapshotHash: "c".repeat(64),
        },
        predecessorGlobalId: null,
        product: null,
        projectGlobalId: projectId,
        relationshipGlobalId: relationshipId,
        relationshipKeyHash: "d".repeat(64),
        snapshotHash: "e".repeat(64),
        toolingMasterGlobalId: masterId,
        version: 1,
      },
    ],
    downstream: {
      erp: { reasonCode: "erp_projection_unavailable", state: "unavailable" },
      lifecycle: {
        reasonCode: "lifecycle_policy_unavailable",
        state: "unavailable",
      },
      physicalSet: {
        reasonCode: "physical_set_not_delivered",
        state: "unavailable",
      },
      revision: {
        reasonCode: "tooling_revision_not_delivered",
        state: "unavailable",
      },
      trial: { reasonCode: "trial_not_delivered", state: "unavailable" },
    },
    masters: [
      {
        globalId: masterId,
        originatingProjectGlobalId: projectId,
        snapshotHash: "b".repeat(64),
        source,
        title: "Synthetic logical tool",
      },
    ],
    parts: [
      {
        currentRevision: {
          globalId: revisionId,
          partGlobalId: partId,
          revisionLabel: "A",
          revisionNumber: 1,
          snapshotHash: "c".repeat(64),
        },
        globalId: partId,
        source,
        title: "Synthetic engineering part",
        version: 1,
      },
    ],
    permissions: {
      createApplicability: true,
      createMaster: true,
      createPart: true,
      createRequirement: true,
      transitionLifecycle: false,
      view: true,
    },
    project: {
      businessCode: "SYN-PROJECT-001",
      globalId: projectId,
      title: "Synthetic Project",
    },
    requirements: [
      {
        globalId: requirementId,
        kind: "new_tool",
        projectGlobalId: projectId,
        reason: "Synthetic need",
        snapshotHash: "f".repeat(64),
        targetDate: null,
        targetPartRevisionGlobalId: revisionId,
        title: "Synthetic Tooling need",
      },
    ],
  };
}

function setCollection(): ToolingSetCollectionViewModel {
  return {
    items: [
      {
        custodyResponsibility: "Customer-owned custody",
        customer: { sourceObjectId: "CUST-001", sourceSystem: "ERPNEXT" },
        erpLocationAndAsset: {
          reasonCode: "erp_projection_unavailable",
          state: "unavailable",
        },
        globalId: setId,
        lifecycle: {
          reasonCode: "lifecycle_policy_unavailable",
          state: "unavailable",
        },
        physicalSerial: "SET-001",
        projectGlobalId: projectId,
        repairAuthorizationReference: "AUTH-001",
        requirementKind: "customer_owned_intake",
        returnConditions: "Return on request",
        snapshotHash: "1".repeat(64),
        sourceRevision: {
          reasonCode: "tooling_revision_not_delivered",
          state: "unavailable",
        },
        supplier: {
          reasonCode: "formal_supplier_unavailable",
          state: "unavailable",
        },
        toolingMasterGlobalId: masterId,
        toolingRequirementGlobalId: requirementId,
      },
    ],
    permissions: {
      attachEvidence: true,
      createIntake: true,
      createSet: true,
      transitionLifecycle: false,
      view: true,
    },
    toolingMasterGlobalId: masterId,
  };
}

function setDetail(): ToolingSetDetailViewModel {
  const toolingSet = setCollection().items[0];
  if (!toolingSet) throw new Error("The Set fixture is required.");
  const inspections = (
    [
      "appearance",
      "water_circuit",
      "hot_runner",
      "electrical",
      "safety",
    ] as const
  ).map((category, index) => ({
    category,
    differenceObserved: index === 0,
    globalId: inspectionIds[index] ?? inspectionIds[0],
    observation: index === 0 ? "Scratch observed" : "No difference",
  }));
  return {
    evidence: [
      {
        differenceGlobalIds: [differenceId],
        evidenceRole: "arrival_photo",
        fileContentHash: "2".repeat(64),
        fileName: "arrival.jpg",
        fileOptimisticVersion: 1,
        fileRevisionGlobalId: fileRevisionId,
        globalId: evidenceId,
        intakeSnapshotHash: "3".repeat(64),
        mimeType: "image/jpeg",
        sha256: "4".repeat(64),
        sizeBytes: 128,
        snapshotHash: "5".repeat(64),
        toolingIntakeGlobalId: intakeId,
      },
    ],
    intakes: [
      {
        accessories: [],
        arrivedAt: "2026-08-07T08:00:00Z",
        custodyHandover: "Accepted at receiving dock",
        differences: [
          {
            customerConfirmationRequired: true,
            description: "Scratch observed",
            globalId: differenceId,
            sourceGlobalId: inspectionIds[0],
            sourceKind: "inspection",
          },
        ],
        globalId: intakeId,
        inspections,
        predecessorGlobalId: null,
        snapshotHash: "3".repeat(64),
        toolingSetGlobalId: setId,
        transportProvider: "Synthetic carrier",
        transportReference: "SHIP-001",
        version: 1,
      },
    ],
    permissions: setCollection().permissions,
    toolingSet,
  };
}

function governedResponse(value: unknown, init?: RequestInit): Response {
  const headers = new Headers(init?.headers);
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Idempotency-Replayed": "false",
      "X-Request-ID": headers.get("X-Request-ID") ?? "",
      "X-Trace-ID": "trace-tooling-set-test",
    },
    status: init?.method === "POST" ? 201 : 200,
  });
}

function responseFor(request: RequestInfo | URL, init?: RequestInit): Response {
  const headers = new Headers(init?.headers);
  const requestUrl =
    typeof request === "string"
      ? request
      : request instanceof URL
        ? request.href
        : request.url;
  return new Response(JSON.stringify(fixture()), {
    headers: {
      "Cache-Control": "private, no-store",
      "Idempotency-Replayed": "false",
      "X-Request-ID": headers.get("X-Request-ID") ?? "",
      "X-Trace-ID": "trace-tooling-test",
    },
    status:
      requestUrl.includes("/parts") && init?.method === "POST" ? 201 : 200,
  });
}

describe("live Tooling data source", () => {
  it("accepts only the exact bounded cockpit graph", () => {
    const value = fixture();
    expect(isToolingCockpitResponse(value)).toBe(true);
    expect(isToolingCockpitResponse({ ...value, unexpected: true })).toBe(
      false,
    );
    expect(
      isToolingCockpitResponse({
        ...value,
        applicability: [
          { ...value.applicability[0], toolingMasterGlobalId: projectId },
        ],
      }),
    ).toBe(false);
    expect(
      isToolingCockpitResponse({
        ...value,
        downstream: {
          ...value.downstream,
          erp: value.downstream.trial,
        },
      }),
    ).toBe(false);
  });

  it("loads the Project-first cockpit and exact Master using only closed paths", async () => {
    const fetch = vi.fn(responseFor);
    vi.stubGlobal("fetch", fetch);
    const dataSource = new LiveToolingDataSource();

    await expect(
      dataSource.loadCockpit(projectId, new AbortController().signal),
    ).resolves.toEqual(fixture());
    await expect(
      dataSource.loadMaster(projectId, masterId, new AbortController().signal),
    ).resolves.toEqual(fixture());

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      `/api/npi/v1/projects/${projectId}/tooling`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}`,
    ]);
    expect(
      fetch.mock.calls.every(([, init]) => init?.credentials === "same-origin"),
    ).toBe(true);
  });

  it("submits an actor-session command with CSRF and idempotency headers", async () => {
    const fetch = vi.fn(responseFor);
    vi.stubGlobal("fetch", fetch);
    const dataSource = new LiveToolingDataSource();
    const controller = new AbortController();

    await expect(
      dataSource.createPart(
        projectId,
        { reason: "Initial", revisionLabel: "A", title: "Part" },
        {
          csrfToken: "c".repeat(32),
          idempotencyKey: "tooling-part-12345678",
          signal: controller.signal,
        },
      ),
    ).resolves.toEqual(fixture());

    const [url, init] = fetch.mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(url).toBe(`/api/npi/v1/projects/${projectId}/parts`);
    expect(init?.method).toBe("POST");
    expect(headers.get("X-Frappe-CSRF-Token")).toBe("c".repeat(32));
    expect(headers.get("Idempotency-Key")).toBe("tooling-part-12345678");
    expect(typeof init?.body).toBe("string");
    const body = typeof init?.body === "string" ? init.body : "";
    expect(JSON.parse(body)).toEqual({
      reason: "Initial",
      revisionLabel: "A",
      title: "Part",
    });
  });

  it("uses the four remaining frozen command paths without generic CRUD", async () => {
    const fetch = vi.fn(responseFor);
    vi.stubGlobal("fetch", fetch);
    const dataSource = new LiveToolingDataSource();
    const commandContext = (suffix: string) => ({
      csrfToken: "c".repeat(32),
      idempotencyKey: `tooling-command-${suffix}`,
      signal: new AbortController().signal,
    });

    await dataSource.createPartRevision(
      projectId,
      partId,
      {
        expectedVersion: 1,
        reason: "Successor",
        revisionLabel: "B",
        title: "Part B",
      },
      commandContext("revision"),
    );
    await dataSource.createRequirement(
      projectId,
      { kind: "new_tool", reason: "Need", title: "Requirement" },
      commandContext("requirement"),
    );
    await dataSource.createMaster(
      projectId,
      { title: "Master" },
      commandContext("master"),
    );
    await dataSource.createApplicability(
      projectId,
      {
        effectiveFrom: "2026-08-07",
        partRevisionGlobalId: revisionId,
        reason: "Initial applicability",
        toolingMasterGlobalId: masterId,
      },
      commandContext("applicability"),
    );

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      `/api/npi/v1/projects/${projectId}/parts/${partId}/revisions`,
      `/api/npi/v1/projects/${projectId}/tooling-requirements`,
      `/api/npi/v1/projects/${projectId}/tooling-masters`,
      `/api/npi/v1/projects/${projectId}/tooling-applicabilities`,
    ]);
    expect(fetch.mock.calls.every(([, init]) => init?.method === "POST")).toBe(
      true,
    );
  });

  it("fails locally for invalid identities, command context and cancellation", async () => {
    const fetch = vi.fn(responseFor);
    vi.stubGlobal("fetch", fetch);
    const dataSource = new LiveToolingDataSource();
    await expect(
      dataSource.loadCockpit("not-a-uuid", new AbortController().signal),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    await expect(
      dataSource.createMaster(
        projectId,
        { title: "Master" },
        {
          csrfToken: "short",
          idempotencyKey: "tooling-master-12345678",
          signal: new AbortController().signal,
        },
      ),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    const cancelled = new AbortController();
    cancelled.abort();
    await expect(
      dataSource.loadCockpit(projectId, cancelled.signal),
    ).rejects.toBeInstanceOf(ToolingRequestCancelledError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("accepts only coherent bounded Set, intake and exact evidence graphs", () => {
    expect(isToolingSetCollectionResponse(setCollection())).toBe(true);
    expect(isToolingSetDetailResponse(setDetail())).toBe(true);
    expect(
      isToolingSetCollectionResponse({
        ...setCollection(),
        unexpected: true,
      }),
    ).toBe(false);
    const detail = setDetail();
    const firstIntake = detail.intakes[0];
    if (!firstIntake) throw new Error("The intake fixture is required.");
    expect(
      isToolingSetDetailResponse({
        ...detail,
        evidence: [
          {
            ...detail.evidence[0],
            intakeSnapshotHash: "f".repeat(64),
          },
        ],
      }),
    ).toBe(false);
    expect(
      isToolingSetDetailResponse({
        ...detail,
        intakes: [
          {
            ...firstIntake,
            inspections: firstIntake.inspections.slice(0, 4),
          },
        ],
      }),
    ).toBe(false);
  });

  it("uses only the closed Set, intake and evidence routes", async () => {
    const fetch = vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof request === "string"
          ? request
          : request instanceof URL
            ? request.href
            : request.url;
      return Promise.resolve(
        governedResponse(
          url.endsWith("/sets") ? setCollection() : setDetail(),
          init,
        ),
      );
    });
    vi.stubGlobal("fetch", fetch);
    const dataSource = new LiveToolingDataSource();
    const intake = setDetail().intakes[0];
    if (!intake) throw new Error("The intake fixture is required.");
    const context = (suffix: string) => ({
      csrfToken: "c".repeat(32),
      idempotencyKey: `tooling-set-${suffix}-12345678`,
      signal: new AbortController().signal,
    });

    await dataSource.loadSets(
      projectId,
      masterId,
      new AbortController().signal,
    );
    await dataSource.loadSet(
      projectId,
      masterId,
      setId,
      new AbortController().signal,
    );
    await dataSource.createSet(
      projectId,
      masterId,
      {
        custodyResponsibility: "Customer custody",
        physicalSerial: "SET-001",
        repairAuthorizationReference: "AUTH-001",
        returnConditions: "Return on request",
        toolingRequirementGlobalId: requirementId,
      },
      context("create"),
    );
    await dataSource.createIntake(
      projectId,
      masterId,
      setId,
      {
        accessories: [],
        arrivedAt: "2026-08-07T08:00:00Z",
        custodyHandover: "Accepted",
        differences: intake.differences,
        inspections: intake.inspections,
        transportProvider: "Carrier",
        transportReference: "SHIP-001",
      },
      context("intake"),
    );
    await dataSource.attachIntakeEvidence(
      projectId,
      masterId,
      setId,
      intakeId,
      {
        differenceGlobalIds: [differenceId],
        evidenceRole: "arrival_photo",
        fileRevisionGlobalId: fileRevisionId,
      },
      context("evidence"),
    );

    expect(
      fetch.mock.calls.map(([url]) =>
        typeof url === "string" ? url : url instanceof URL ? url.href : url.url,
      ),
    ).toEqual([
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/sets`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/sets/${setId}`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/sets`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/sets/${setId}/intakes`,
      `/api/npi/v1/projects/${projectId}/tooling/${masterId}/sets/${setId}/intakes/${intakeId}/evidence`,
    ]);
    expect(
      fetch.mock.calls.slice(2).every(([, init]) => init?.method === "POST"),
    ).toBe(true);
  });

  it("rejects malformed Set commands before transport", async () => {
    const fetch = vi.fn(responseFor);
    vi.stubGlobal("fetch", fetch);
    const dataSource = new LiveToolingDataSource();
    await expect(
      dataSource.createSet(
        projectId,
        masterId,
        {
          custodyResponsibility: "",
          physicalSerial: "SET-001",
          repairAuthorizationReference: "AUTH-001",
          returnConditions: "Return",
          toolingRequirementGlobalId: requirementId,
        },
        {
          csrfToken: "c".repeat(32),
          idempotencyKey: "tooling-set-invalid-12345678",
          signal: new AbortController().signal,
        },
      ),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    expect(fetch).not.toHaveBeenCalled();
  });
});
