import { describe, expect, it, vi } from "vitest";

import {
  isToolingCockpitResponse,
  LiveToolingDataSource,
  ToolingRequestCancelledError,
  type ToolingCockpitViewModel,
} from "../../src/api/tooling-data-source";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const partId = "33333333-3333-4333-8333-333333333333";
const revisionId = "44444444-4444-4444-8444-444444444444";
const requirementId = "55555555-5555-4555-8555-555555555555";
const applicabilityId = "66666666-6666-4666-8666-666666666666";
const relationshipId = "77777777-7777-4777-8777-777777777777";
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
});
