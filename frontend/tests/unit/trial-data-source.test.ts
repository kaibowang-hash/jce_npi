import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isTrialExecutionWorkspace,
  isTrialPlanDetail,
  isTrialPlanningWorkspace,
  LiveTrialDataSource,
  type CreateTrialPlanCommand,
} from "../../src/api/trial-data-source";
import { NpiTransportError } from "../../src/api/http";
import {
  trialActualRevision,
  trialExecutionWorkspace,
  trialInputLock,
  trialSampleRevision,
} from "../support/trial-execution-fixture";
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
  it("accepts only exact Project-contained execution snapshots", () => {
    const workspace = trialExecutionWorkspace();

    expect(isTrialExecutionWorkspace(workspace)).toBe(true);
    expect(
      isTrialExecutionWorkspace({ ...workspace, machineImported: true }),
    ).toBe(false);
    expect(
      isTrialExecutionWorkspace({
        ...workspace,
        pendingFiles: workspace.pendingFiles.map((file) => ({
          fileName: file.fileName,
          globalId: file.globalId,
          mimeType: file.mimeType,
          privacy: file.privacy,
          scanState: file.scanState,
          sha256: file.sha256,
          sizeBytes: file.sizeBytes,
        })),
      }),
    ).toBe(false);
    expect(
      isTrialExecutionWorkspace({
        ...workspace,
        actualRevisions: workspace.actualRevisions.map((revision) => ({
          ...revision,
          projectGlobalId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        })),
      }),
    ).toBe(false);
  });

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

  it("loads and writes the exact Round execution command surface", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>((_request, init) =>
      Promise.resolve(
        response(
          trialExecutionWorkspace({
            pendingFiles: [
              {
                fileName: "curve.csv",
                globalId: "10000000-0000-4000-8000-000000000007",
                mimeType: "text/csv",
                optimisticVersion: 2,
                privacy: "private",
                scanState: "clean",
                sha256: "9".repeat(64),
                sizeBytes: 1024,
              },
            ],
          }),
          init,
          init?.method === "POST" ? false : undefined,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();
    const lock = trialInputLock();
    const actual = trialActualRevision();
    const sample = trialSampleRevision();

    await source.loadRoundExecution(
      trialPlanningIds.project,
      trialPlanningIds.round,
      new AbortController().signal,
    );
    await source.prepareRound(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        expectedRoundOptimisticVersion: 1,
        material: {
          additive: lock.material.additive,
          color: lock.material.color,
          label: lock.material.label,
          lotBatchCode: lock.material.lotBatchCode,
          observedAt: lock.material.observedAt,
          sourceObjectId: lock.material.sourceObjectId,
          sourceSystem: lock.material.sourceSystem,
        },
        parameterDefinitions: lock.parameterDefinitions,
        reason: "Freeze exact Trial inputs",
        references: lock.references.map((reference) => ({
          expectedOptimisticVersion: reference.optimisticVersion,
          globalId: reference.globalId,
          kind: reference.kind,
        })),
      },
      context("prepare"),
    );
    await source.startRound(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        environment: actual.environment,
        executionStartedAt: actual.executionStartedAt,
        expectedInputLockRevisionGlobalId: lock.globalId,
        expectedInputLockVersion: lock.lockVersion,
        expectedRoundOptimisticVersion: 2,
        material: {
          additive: actual.material.additive,
          color: actual.material.color,
          label: actual.material.label,
          lotBatchCode: actual.material.lotBatchCode,
          observedAt: actual.material.observedAt,
          sourceObjectId: actual.material.sourceObjectId,
          sourceSystem: actual.material.sourceSystem,
        },
        operatorUserId: actual.operatorUserId,
        parameters: actual.parameters,
        reason: "Start exact manual Trial context",
        resources: actual.resources.map((resource) => ({
          kind: resource.kind,
          label: resource.label,
          sourceObjectId: resource.sourceObjectId,
          sourceSystem: resource.sourceSystem,
        })),
      },
      context("start"),
    );
    await source.appendActualRevision(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        environment: actual.environment,
        executionStartedAt: actual.executionStartedAt,
        expectedActualRevisionGlobalId: actual.globalId,
        expectedActualVersion: actual.actualVersion,
        expectedRoundOptimisticVersion: 3,
        material: {
          additive: actual.material.additive,
          color: actual.material.color,
          label: actual.material.label,
          lotBatchCode: actual.material.lotBatchCode,
          observedAt: actual.material.observedAt,
          sourceObjectId: actual.material.sourceObjectId,
          sourceSystem: actual.material.sourceSystem,
        },
        operatorUserId: actual.operatorUserId,
        parameters: actual.parameters,
        reason: "Append exact manual Trial context",
        resources: actual.resources.map((resource) => ({
          kind: resource.kind,
          label: resource.label,
          sourceObjectId: resource.sourceObjectId,
          sourceSystem: resource.sourceSystem,
        })),
      },
      context("actual-revision"),
    );
    await source.createSampleBatch(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        expectedInputLockRevisionGlobalId: lock.globalId,
        expectedRoundOptimisticVersion: 3,
        reason: "Register exact Sample Batch",
        sample: {
          cavityGlobalIds: sample.cavityGlobalIds,
          destination: sample.destination,
          feedbackObservedAt: sample.feedbackObservedAt,
          feedbackSource: sample.feedbackSource,
          feedbackText: sample.feedbackText,
          label: sample.label,
          packaging: sample.packaging,
          quantity: sample.quantity,
          unit: sample.unit,
        },
      },
      context("sample"),
    );
    await source.appendSampleBatchRevision(
      trialPlanningIds.project,
      trialPlanningIds.round,
      sample.sampleBatchGlobalId,
      {
        expectedRevisionGlobalId: sample.globalId,
        expectedRoundOptimisticVersion: 3,
        expectedSampleVersion: sample.sampleVersion,
        reason: "Append exact Sample Batch feedback",
        sample: {
          cavityGlobalIds: sample.cavityGlobalIds,
          destination: "Customer quality laboratory",
          feedbackObservedAt: "2026-08-10T10:30:00Z",
          feedbackSource: "Customer quality",
          feedbackText: "Dimensional review accepted",
          label: sample.label,
          packaging: sample.packaging,
          quantity: sample.quantity,
          unit: sample.unit,
        },
      },
      context("sample-revision"),
    );
    await source.uploadEvidenceFile(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        expectedRoundOptimisticVersion: 3,
        file: new File(["curve"], "curve.csv", { type: "text/csv" }),
      },
      context("upload"),
    );
    await source.bindEvidence(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        expectedFileOptimisticVersion: 2,
        expectedRoundOptimisticVersion: 3,
        fileRevisionGlobalId: "10000000-0000-4000-8000-000000000007",
        role: "parameter_curve",
        sampleBatchRevisionGlobalId: sample.globalId,
        expectedSampleVersion: sample.sampleVersion,
      },
      context("bind"),
    );

    expect(fetch).toHaveBeenCalledTimes(8);
    expect(requestUrl(fetch.mock.calls[0]?.[0])).toContain(
      `/trial-rounds/${trialPlanningIds.round}/execution`,
    );
    expect(requestUrl(fetch.mock.calls[1]?.[0])).toContain(
      `/trial-rounds/${trialPlanningIds.round}:prepare`,
    );
    expect(requestUrl(fetch.mock.calls[2]?.[0])).toContain(
      `/trial-rounds/${trialPlanningIds.round}:start`,
    );
    expect(requestUrl(fetch.mock.calls[3]?.[0])).toContain("/actual-revisions");
    expect(requestUrl(fetch.mock.calls[4]?.[0])).toContain("/sample-batches");
    expect(requestUrl(fetch.mock.calls[5]?.[0])).toContain(
      `/sample-batches/${sample.sampleBatchGlobalId}/revisions`,
    );
    expect(fetch.mock.calls[6]?.[1]?.body).toBeInstanceOf(FormData);
    expect(
      (fetch.mock.calls[6]?.[1]?.body as FormData).get(
        "expectedRoundOptimisticVersion",
      ),
    ).toBe("3");
    expect(bodyValue(fetch.mock.calls[7]?.[1]?.body)).toMatchObject({
      expectedFileOptimisticVersion: 2,
      role: "parameter_curve",
    });
  });

  it("downloads only exact clean private evidence with hardened response headers and hash", async () => {
    const sourceEvidence = trialExecutionWorkspace().evidence[0];
    if (!sourceEvidence)
      throw new Error("The Trial download test requires one evidence record.");
    const evidence = {
      ...sourceEvidence,
      fileMimeType: "image/png",
      fileSha256:
        "736b88fa9eefc18bd6598e09ca6ac60111d8797e3a7e9ad5ba06bd3697577689",
      fileSizeBytes: 14,
    };
    const responseBytes = new TextEncoder().encode("clean evidence");
    const responseBody = {
      arrayBuffer: () => Promise.resolve(responseBytes.slice().buffer),
      size: responseBytes.byteLength,
      type: "image/png",
      [Symbol.toStringTag]: "Blob",
    } as unknown as Blob;
    const fetch = vi.fn<typeof globalThis.fetch>((_request, init) => {
      const requestId = new Headers(init?.headers).get("X-Request-ID") ?? "";
      const binaryResponse = new Response(null, {
        headers: {
          "Cache-Control": "private, no-store",
          "Content-Disposition": "attachment; filename*=UTF-8''t0-photo.png",
          "Content-Security-Policy": "sandbox; default-src 'none'",
          "Content-Type": "image/png",
          "Referrer-Policy": "no-referrer",
          "X-Content-Type-Options": "nosniff",
          "X-Request-ID": requestId,
          "X-Trace-ID": "trace-trial-evidence-download",
        },
        status: 200,
      });
      vi.spyOn(binaryResponse, "blob").mockResolvedValue(responseBody);
      return Promise.resolve(binaryResponse);
    });
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();

    const result = await source.downloadEvidence(
      trialPlanningIds.project,
      trialPlanningIds.round,
      evidence,
      {
        csrfToken: "c".repeat(32),
        signal: new AbortController().signal,
      },
    );

    expect(result.fileName).toBe("t0-photo.png");
    expect(result.blob.size).toBe(14);
    expect(requestUrl(fetch.mock.calls[0]?.[0])).toContain(
      `/trial-rounds/${trialPlanningIds.round}/evidence/${evidence.globalId}:content`,
    );
    expect(fetch.mock.calls[0]?.[1]?.method).toBe("POST");
    expect(new Headers(fetch.mock.calls[0]?.[1]?.headers).get("Accept")).toBe(
      "image/png",
    );

    await expect(
      source.downloadEvidence(
        trialPlanningIds.project,
        trialPlanningIds.round,
        { ...evidence, fileSha256: "0".repeat(64) },
        {
          csrfToken: "c".repeat(32),
          signal: new AbortController().signal,
        },
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
