import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isTrialPlanDetail,
  isTrialPlanningWorkspace,
  LiveTrialDataSource,
  type CreateTrialPlanCommand,
} from "../../src/api/trial-data-source";
import { NpiTransportError } from "../../src/api/http";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";

function requestUrl(request: RequestInfo | URL | undefined): string {
  if (typeof request === "string") return request;
  if (request instanceof URL) return request.href;
  return request?.url ?? "";
}

function bodyValue(body: BodyInit | null | undefined): unknown {
  if (typeof body !== "string")
    throw new Error("An exact JSON request body is required.");
  return JSON.parse(body) as unknown;
}

function response(
  value: unknown,
  init?: RequestInit,
  replayed?: boolean,
): Response {
  const requestId = new Headers(init?.headers).get("X-Request-ID") ?? "";
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(replayed === undefined
        ? {}
        : { "Idempotency-Replayed": String(replayed) }),
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-trial-data-source-test",
    },
    status: replayed === undefined ? 200 : 201,
  });
}

function context(suffix: string) {
  return {
    csrfToken: "c".repeat(32),
    idempotencyKey: `trial-${suffix}-12345678`,
    signal: new AbortController().signal,
  };
}

function createPlanCommand(): CreateTrialPlanCommand {
  return {
    measurementPlan: { description: "Measure critical dimensions" },
    objective: "Confirm first-shot fill balance",
    plannedEndAt: "2026-08-20T12:00:00.000Z",
    plannedStartAt: "2026-08-20T08:00:00.000Z",
    purpose: "first_trial",
    reason: "Create the controlled Trial Plan",
    resources: [
      {
        kind: "machine",
        label: "Injection machine 550T",
        quantity: null,
        sourceObjectId: "IM-550-02",
        sourceSystem: "ERPNEXT",
        unit: null,
      },
      {
        kind: "material",
        label: "PA66-GF30 natural",
        quantity: 80,
        sourceObjectId: "MAT-PA66-GF30",
        sourceSystem: "ERPNEXT",
        unit: "kg",
      },
    ],
    responsibleMemberGlobalIds: [trialPlanningIds.member],
    sampleQuantity: 80,
    toolingMasterGlobalId: trialPlanningIds.toolingMaster,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Trial planning data source", () => {
  it("accepts only exact contained workspace and Plan snapshots", () => {
    const workspace = trialPlanningWorkspace();
    const detail = trialPlanDetail();

    expect(isTrialPlanningWorkspace(workspace)).toBe(true);
    expect(isTrialPlanDetail(detail)).toBe(true);
    expect(
      isTrialPlanningWorkspace({ ...workspace, reservationConfirmed: true }),
    ).toBe(false);
    expect(
      isTrialPlanningWorkspace({
        ...workspace,
        capabilities: workspace.capabilities.map((capability) => ({
          ...capability,
          availability: "available",
        })),
      }),
    ).toBe(false);
    expect(
      isTrialPlanDetail({
        ...detail,
        rounds: [
          {
            ...detail.rounds[0],
            projectGlobalId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          },
        ],
      }),
    ).toBe(false);
  });

  it("loads the Project-first workspace and exact Plan detail", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>((request, init) =>
      Promise.resolve(
        response(
          requestUrl(request).endsWith(`/trial-plans/${trialPlanningIds.plan}`)
            ? trialPlanDetail()
            : trialPlanningWorkspace(),
          init,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();

    await source.loadWorkspace(
      trialPlanningIds.project,
      new AbortController().signal,
    );
    await source.loadPlan(
      trialPlanningIds.project,
      trialPlanningIds.plan,
      new AbortController().signal,
    );

    expect(requestUrl(fetch.mock.calls[0]?.[0])).toBe(
      `/api/npi/v1/projects/${trialPlanningIds.project}/trials`,
    );
    expect(requestUrl(fetch.mock.calls[1]?.[0])).toBe(
      `/api/npi/v1/projects/${trialPlanningIds.project}/trial-plans/${trialPlanningIds.plan}`,
    );
  });

  it("sends exact actor-bound Plan, revision, Round and action commands", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>((_request, init) =>
      Promise.resolve(response(trialPlanDetail(), init, true)),
    );
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();
    const detail = trialPlanDetail();
    const revision = detail.latestRevision;
    const initial = createPlanCommand();

    const created = await source.createPlan(
      trialPlanningIds.project,
      initial,
      context("create"),
    );
    const revised = await source.revisePlan(
      trialPlanningIds.project,
      trialPlanningIds.plan,
      {
        expectedPlanVersion: revision.planVersion,
        expectedRevisionGlobalId: revision.globalId,
        expectedRevisionSnapshotHash: revision.snapshotHash,
        measurementPlan: initial.measurementPlan,
        objective: initial.objective,
        plannedEndAt: initial.plannedEndAt,
        plannedStartAt: initial.plannedStartAt,
        purpose: initial.purpose,
        reason: "Append one exact successor",
        resources: initial.resources,
        responsibleMemberGlobalIds: initial.responsibleMemberGlobalIds,
        sampleQuantity: initial.sampleQuantity,
      },
      context("revise"),
    );
    const round = await source.createRound(
      trialPlanningIds.project,
      trialPlanningIds.plan,
      {
        displayLabel: "T1",
        expectedPlanRevisionGlobalId: revision.globalId,
        expectedPlanRevisionSnapshotHash: revision.snapshotHash,
        reason: "Create the next planned Round",
      },
      context("round"),
    );
    const actions = await source.generateActions(
      trialPlanningIds.project,
      trialPlanningIds.plan,
      {
        actions: [
          {
            actionKey: "trial.prepare.measurement",
            blocking: true,
            description: "Confirm the measurement intent before preparation",
            dueAt: "2026-08-19T08:00:00.000Z",
            responsibleMemberGlobalId: trialPlanningIds.member,
            severity: "high",
            title: "Confirm Trial measurement intent",
          },
        ],
        expectedPlanRevisionGlobalId: revision.globalId,
        expectedPlanRevisionSnapshotHash: revision.snapshotHash,
        reason: "Generate one governed action",
        trialRoundGlobalId: trialPlanningIds.round,
      },
      context("actions"),
    );

    expect(created.replayed).toBe(true);
    expect(revised.replayed).toBe(true);
    expect(round.replayed).toBe(true);
    expect(actions.replayed).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(4);
    expect(
      requestUrl(fetch.mock.calls[0]?.[0]).endsWith(
        `/projects/${trialPlanningIds.project}/trials`,
      ),
    ).toBe(true);
    expect(
      requestUrl(fetch.mock.calls[1]?.[0]).endsWith(
        `/trial-plans/${trialPlanningIds.plan}/revisions`,
      ),
    ).toBe(true);
    expect(
      requestUrl(fetch.mock.calls[2]?.[0]).endsWith(
        `/trial-plans/${trialPlanningIds.plan}/rounds`,
      ),
    ).toBe(true);
    expect(
      requestUrl(fetch.mock.calls[3]?.[0]).endsWith(
        `/trial-plans/${trialPlanningIds.plan}/actions:generate`,
      ),
    ).toBe(true);
    for (const call of fetch.mock.calls) {
      const init = call[1];
      expect(init?.method).toBe("POST");
      expect(new Headers(init?.headers).get("X-Frappe-CSRF-Token")).toBe(
        "c".repeat(32),
      );
      expect(new Headers(init?.headers).get("Idempotency-Key")).toMatch(
        /^trial-/u,
      );
    }
    expect(bodyValue(fetch.mock.calls[2]?.[1]?.body)).toEqual({
      displayLabel: "T1",
      expectedPlanRevisionGlobalId: revision.globalId,
      expectedPlanRevisionSnapshotHash: revision.snapshotHash,
      reason: "Create the next planned Round",
    });
  });

  it("fails closed before transport for invalid identity, resource and action claims", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>();
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();
    const command = createPlanCommand();

    await expect(
      source.loadWorkspace("not-a-uuid", new AbortController().signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.createPlan(
        trialPlanningIds.project,
        {
          ...command,
          resources: command.resources.map((resource) => ({
            ...resource,
            bookingState: "reserved",
          })),
        },
        context("invalid-resource"),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.generateActions(
        trialPlanningIds.project,
        trialPlanningIds.plan,
        {
          actions: [],
          expectedPlanRevisionGlobalId: trialPlanningIds.revisionOne,
          expectedPlanRevisionSnapshotHash: "1".repeat(64),
          reason: "Invalid empty action batch",
        },
        context("invalid-actions"),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(fetch).not.toHaveBeenCalled();
  });
});
