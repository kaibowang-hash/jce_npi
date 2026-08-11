import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isTrialExecutionWorkspace,
  isTrialPlanDetail,
  isTrialPlanningWorkspace,
  isTrialQualityWorkspace,
  isTrialReviewWorkspace,
  LiveTrialDataSource,
  type CreateTrialCavityResultCommand,
  type CreateTrialDefectCommand,
  type CreateTrialPlanCommand,
} from "../../src/api/trial-data-source";
import { NpiTransportError } from "../../src/api/http";
import {
  trialActualRevision,
  trialExecutionIds,
  trialExecutionWorkspace,
  trialInputLock,
  trialSampleRevision,
} from "../support/trial-execution-fixture";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";
import {
  trialQualityDefect,
  trialQualityIds,
  trialQualityVerification,
  trialQualityWorkspace,
} from "../support/trial-quality-fixture";
import {
  trialComparison,
  trialConclusion,
  trialConclusionPolicy,
  trialReviewIds,
  trialReviewReference,
  trialReviewWorkspace,
} from "../support/trial-review-fixture";

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

  it("accepts only exact contained Trial quality snapshots", () => {
    const workspace = trialQualityWorkspace();

    expect(isTrialQualityWorkspace(workspace)).toBe(true);
    expect(isTrialQualityWorkspace({ ...workspace, ncrCreated: true })).toBe(
      false,
    );
    expect(
      isTrialQualityWorkspace({
        ...workspace,
        externalEffects: { ...workspace.externalEffects, gate: "available" },
      }),
    ).toBe(false);
    expect(
      isTrialQualityWorkspace({
        ...workspace,
        cavityResultRevisions: workspace.cavityResultRevisions.map(
          (revision) => ({
            ...revision,
            projectGlobalId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          }),
        ),
      }),
    ).toBe(false);
    expect(
      isTrialQualityWorkspace({
        ...workspace,
        defectRevisions: workspace.defectRevisions.map((entry) =>
          entry.source === "trial"
            ? {
                ...entry,
                revision: {
                  ...entry.revision,
                  actions: entry.revision.actions.map((action) => ({
                    ...action,
                    targetRoundSnapshotHash: "not-a-hash",
                  })),
                },
              }
            : entry,
        ),
      }),
    ).toBe(false);
    expect(
      isTrialQualityWorkspace({
        ...workspace,
        defectRevisions: workspace.defectRevisions.map((entry) =>
          entry.source === "tooling"
            ? {
                ...entry,
                revision: {
                  ...entry.revision,
                  evidence: [{ globalId: trialQualityIds.verification }],
                },
              }
            : entry,
        ),
      }),
    ).toBe(false);
  });

  it("loads and writes the exact Trial quality command surface", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>((_request, init) =>
      Promise.resolve(
        response(
          trialQualityWorkspace(),
          init,
          init?.method === "POST" ? false : undefined,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();
    const workspace = trialQualityWorkspace();
    const execution = trialExecutionWorkspace();
    const lock = trialInputLock();
    const sample = trialSampleRevision();
    const cavity = workspace.cavityResultRevisions[0];
    const defect = trialQualityDefect();
    const verification = trialQualityVerification();
    if (!cavity) throw new Error("The quality test requires a cavity result.");
    const measurement = cavity.measurements.map((value) => ({
      characteristicKey: value.characteristicKey,
      label: value.label,
      lowerLimit: value.lowerLimit,
      nominalValue: value.nominalValue,
      observedAt: value.observedAt,
      required: value.required,
      source: value.source,
      state: value.state,
      unit: value.unit,
      upperLimit: value.upperLimit,
      value: value.value,
    }));
    const evidence = cavity.evidence;
    const cavityCommand: CreateTrialCavityResultCommand = {
      cavityGlobalId: cavity.cavityGlobalId,
      evidence,
      expectedInputLockRevisionGlobalId: lock.globalId,
      expectedInputLockRevisionSnapshotHash: lock.snapshotHash,
      expectedRoundOptimisticVersion: execution.round.optimisticVersion,
      expectedRoundSnapshotHash: execution.round.snapshotHash,
      expectedSampleBatchRevisionSnapshotHash: sample.snapshotHash,
      measurements: measurement,
      reason: "Record exact cavity result",
      sampleBatchRevisionGlobalId: sample.globalId,
    };
    const defectFields = {
      actions: defect.actions.map((action) => ({
        actionType: action.actionType,
        detail: action.detail,
        dueDate: action.dueDate,
        globalId: action.globalId,
        responsibleMember: {
          globalId: action.responsibleMember.globalId,
          optimisticVersion: action.responsibleMember.optimisticVersion,
        },
        state: action.state,
        targetRoundGlobalId: action.targetRoundGlobalId,
        targetRoundOptimisticVersion: action.targetRoundOptimisticVersion,
        targetRoundSnapshotHash: action.targetRoundSnapshotHash,
        verificationRevisionGlobalId: action.verificationRevisionGlobalId,
        verificationRevisionSnapshotHash:
          action.verificationRevisionSnapshotHash,
      })),
      blocking: defect.blocking,
      businessCode: defect.businessCode,
      categoryKey: defect.categoryKey,
      cavityGlobalId: defect.cavityGlobalId,
      description: defect.description,
      evidence: defect.evidence,
      expectedInputLockRevisionGlobalId: lock.globalId,
      expectedInputLockRevisionSnapshotHash: lock.snapshotHash,
      expectedRoundOptimisticVersion: execution.round.optimisticVersion,
      expectedRoundSnapshotHash: execution.round.snapshotHash,
      expectedSampleBatchRevisionSnapshotHash: sample.snapshotHash,
      location: defect.location,
      occurrenceCount: defect.occurrenceCount,
      reason: "Append exact Trial defect truth",
      responsibleMember: defect.responsibleMember
        ? {
            globalId: defect.responsibleMember.globalId,
            optimisticVersion: defect.responsibleMember.optimisticVersion,
          }
        : undefined,
      rootCause: defect.rootCause ?? undefined,
      rootCauseState: defect.rootCauseState,
      sampleBatchRevisionGlobalId: sample.globalId,
      severity: defect.severity,
      state: defect.state,
      title: defect.title,
    } as const;
    const createDefect: CreateTrialDefectCommand = {
      ...defectFields,
      defectGlobalId: defect.defectGlobalId,
      expectedDefectVersion: 1,
      expectedPredecessorGlobalId: trialQualityIds.toolingDefectRevision,
      expectedPredecessorKind: "tooling_defect_revision",
      expectedPredecessorSnapshotHash: "5".repeat(64),
    };

    await source.loadRoundQuality(
      trialPlanningIds.project,
      trialPlanningIds.round,
      new AbortController().signal,
    );
    await source.createCavityResult(
      trialPlanningIds.project,
      trialPlanningIds.round,
      cavityCommand,
      context("quality-cavity-create"),
    );
    await source.reviseCavityResult(
      trialPlanningIds.project,
      trialPlanningIds.round,
      cavity.cavityResultGlobalId,
      {
        expectedInputLockRevisionGlobalId: lock.globalId,
        expectedInputLockRevisionSnapshotHash: lock.snapshotHash,
        expectedResultVersion: cavity.resultVersion,
        expectedRevisionGlobalId: cavity.globalId,
        expectedRevisionSnapshotHash: cavity.snapshotHash,
        expectedRoundOptimisticVersion: execution.round.optimisticVersion,
        expectedRoundSnapshotHash: execution.round.snapshotHash,
        measurements: measurement,
        reason: "Append exact cavity result revision",
      },
      context("quality-cavity-revise"),
    );
    await source.createDefect(
      trialPlanningIds.project,
      trialPlanningIds.round,
      createDefect,
      context("quality-defect-create"),
    );
    await source.reviseDefect(
      trialPlanningIds.project,
      trialPlanningIds.round,
      defect.defectGlobalId,
      {
        ...defectFields,
        expectedDefectVersion: defect.defectVersion,
        expectedPredecessorGlobalId: defect.globalId,
        expectedPredecessorKind: "trial_defect_revision",
        expectedPredecessorSnapshotHash: defect.snapshotHash,
      },
      context("quality-defect-revise"),
    );
    await source.verifyDefect(
      trialPlanningIds.project,
      trialPlanningIds.round,
      defect.defectGlobalId,
      {
        actionGlobalId: verification.actionGlobalId,
        cavityResultRevisionGlobalId: verification.cavityResultRevisionGlobalId,
        evidence: verification.evidence,
        expectedAttemptSequence: verification.attemptSequence,
        expectedCavityResultRevisionSnapshotHash:
          verification.cavityResultRevisionSnapshotHash,
        expectedDefectRevisionGlobalId: verification.defectRevisionGlobalId,
        expectedDefectRevisionSnapshotHash:
          verification.defectRevisionSnapshotHash,
        expectedTargetRoundOptimisticVersion:
          verification.targetRoundOptimisticVersion,
        expectedTargetRoundSnapshotHash: verification.targetRoundSnapshotHash,
        finding: "Independent retry confirms the exact target Round result.",
        observedAt: verification.observedAt,
        result: "pass",
        targetRoundGlobalId: verification.targetRoundGlobalId,
        verificationGlobalId: verification.verificationGlobalId,
        verifierMember: {
          globalId: verification.verifierMember.globalId,
          optimisticVersion: verification.verifierMember.optimisticVersion,
        },
      },
      context("quality-verify"),
    );

    expect(fetch).toHaveBeenCalledTimes(6);
    expect(requestUrl(fetch.mock.calls[0]?.[0])).toContain(
      `/trial-rounds/${trialPlanningIds.round}/quality`,
    );
    expect(requestUrl(fetch.mock.calls[1]?.[0])).toContain("/cavity-results");
    expect(requestUrl(fetch.mock.calls[2]?.[0])).toContain(
      `/cavity-results/${cavity.cavityResultGlobalId}/revisions`,
    );
    expect(requestUrl(fetch.mock.calls[3]?.[0])).toContain("/defects");
    expect(requestUrl(fetch.mock.calls[4]?.[0])).toContain(
      `/defects/${defect.defectGlobalId}/revisions`,
    );
    expect(requestUrl(fetch.mock.calls[5]?.[0])).toContain(
      `/defects/${defect.defectGlobalId}/verifications`,
    );
    for (const call of fetch.mock.calls.slice(1)) {
      expect(call[1]?.method).toBe("POST");
      expect(new Headers(call[1]?.headers).get("X-Frappe-CSRF-Token")).toBe(
        "c".repeat(32),
      );
      expect(new Headers(call[1]?.headers).get("Idempotency-Key")).toMatch(
        /^trial-/u,
      );
    }
  });

  it("fails closed before transport for incomplete Trial quality evidence", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>();
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();
    const execution = trialExecutionWorkspace();
    const lock = trialInputLock();
    const sample = trialSampleRevision();

    await expect(
      source.createCavityResult(
        trialPlanningIds.project,
        trialPlanningIds.round,
        {
          cavityGlobalId: trialExecutionIds.cavity,
          evidence: [],
          expectedInputLockRevisionGlobalId: lock.globalId,
          expectedInputLockRevisionSnapshotHash: lock.snapshotHash,
          expectedRoundOptimisticVersion: execution.round.optimisticVersion,
          expectedRoundSnapshotHash: execution.round.snapshotHash,
          expectedSampleBatchRevisionSnapshotHash: sample.snapshotHash,
          measurements: [],
          reason: "Invalid empty evidence and measurement arrays",
          sampleBatchRevisionGlobalId: sample.globalId,
        },
        context("quality-invalid"),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("accepts only exact and fully contained Trial review snapshots", () => {
    const workspace = trialReviewWorkspace();

    expect(isTrialReviewWorkspace(workspace)).toBe(true);
    expect(
      isTrialReviewWorkspace({ ...workspace, gateDecisionCreated: true }),
    ).toBe(false);
    expect(
      isTrialReviewWorkspace({
        ...workspace,
        comparisonSnapshots: workspace.comparisonSnapshots.map((snapshot) => ({
          ...snapshot,
          sources: [...snapshot.sources].reverse(),
        })),
      }),
    ).toBe(false);
    expect(
      isTrialReviewWorkspace({
        ...workspace,
        conclusionRevisions: workspace.conclusionRevisions.map((revision) => ({
          ...revision,
          externalEffects: {
            ...revision.externalEffects,
            gate: "approved",
          },
        })),
      }),
    ).toBe(false);
  });

  it("sends exact policy-bound Trial review commands and preserves replay evidence", async () => {
    const workspace = trialReviewWorkspace();
    const policy = trialConclusionPolicy();
    const comparison = trialComparison();
    const reference = trialReviewReference();
    const conclusion = trialConclusion();
    const fetch = vi.fn<typeof globalThis.fetch>((_request, init) =>
      Promise.resolve(
        response(workspace, init, init?.method === "POST" ? true : undefined),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();
    const policyContext = {
      expectedPolicyRevisionSnapshotHash: policy.snapshotHash,
      expectedRoundOptimisticVersion: workspace.trialRound.optimisticVersion,
      expectedRoundSnapshotHash: workspace.trialRound.snapshotHash,
      policyRevisionGlobalId: policy.globalId,
    } as const;

    await source.loadRoundReview(
      trialPlanningIds.project,
      trialPlanningIds.round,
      new AbortController().signal,
    );
    await source.beginAnalysis(
      trialPlanningIds.project,
      trialPlanningIds.round,
      { ...policyContext, reason: "Begin policy-bound analysis" },
      context("review-begin"),
    );
    await source.createComparison(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        ...policyContext,
        reason: "Compare exact Round snapshots",
        rounds: comparison.sources.map((item) => ({
          expectedOptimisticVersion: item.trialRoundOptimisticVersion,
          expectedSnapshotHash: item.trialRoundSnapshotHash,
          trialRoundGlobalId: item.trialRoundGlobalId,
        })),
      },
      context("review-compare"),
    );
    await source.createReviewReference(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        ...policyContext,
        comparisonSnapshotGlobalId: comparison.globalId,
        expectedComparisonSnapshotHash: comparison.snapshotHash,
        expectedFileRevisionSnapshotHash: reference.fileRevision.snapshotHash,
        expectedPartRevisionSnapshotHash: reference.partRevision.snapshotHash,
        expectedToolingRevisionSnapshotHash:
          reference.toolingRevision.snapshotHash,
        expectedToolingSetSnapshotHash: reference.toolingSet.snapshotHash,
        fileRevisionGlobalId: reference.fileRevision.globalId,
        partRevisionGlobalId: reference.partRevision.globalId,
        reason: "Bind exact review evidence",
        referenceKind: reference.referenceKind,
        toolingMasterGlobalId: reference.toolingMasterGlobalId,
        toolingRevisionGlobalId: reference.toolingRevision.globalId,
        toolingSetGlobalId: reference.toolingSet.globalId,
      },
      context("review-reference"),
    );
    await source.submitConclusion(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        ...policyContext,
        comparisonSnapshotGlobalId: comparison.globalId,
        conclusionCode: conclusion.conclusionCode,
        expectedComparisonSnapshotHash: comparison.snapshotHash,
        proposedGateEffect: conclusion.proposedGateEffect,
        proposedNextWork: conclusion.proposedNextWork,
        proposedNpiEffect: conclusion.proposedNpiEffect,
        reason: "Submit the immutable conclusion proposal",
        reviewReferences: conclusion.reviewReferences,
      },
      context("review-submit"),
    );
    await source.decideConclusion(
      trialPlanningIds.project,
      trialPlanningIds.round,
      conclusion.conclusionGlobalId,
      {
        ...policyContext,
        decision: "approved",
        expectedConclusionRevisionGlobalId: conclusion.globalId,
        expectedConclusionRevisionSnapshotHash: conclusion.snapshotHash,
        expectedConclusionVersion: conclusion.conclusionVersion,
        reason: "Approve the exact submitted revision",
      },
      context("review-decide"),
    );
    await source.reopenConclusion(
      trialPlanningIds.project,
      trialPlanningIds.round,
      {
        ...policyContext,
        conclusionGlobalId: conclusion.conclusionGlobalId,
        expectedConclusionRevisionGlobalId: conclusion.globalId,
        expectedConclusionRevisionSnapshotHash: conclusion.snapshotHash,
        expectedConclusionVersion: conclusion.conclusionVersion,
        reason: "Reopen the exact decided revision",
      },
      context("review-reopen"),
    );

    expect(fetch).toHaveBeenCalledTimes(7);
    expect(requestUrl(fetch.mock.calls[0]?.[0])).toContain(
      `/trial-rounds/${trialPlanningIds.round}/review`,
    );
    expect(requestUrl(fetch.mock.calls[1]?.[0])).toContain(":begin-analysis");
    expect(requestUrl(fetch.mock.calls[2]?.[0])).toContain("/comparisons");
    expect(requestUrl(fetch.mock.calls[3]?.[0])).toContain(
      "/review-references",
    );
    expect(requestUrl(fetch.mock.calls[4]?.[0])).toContain("/conclusions");
    expect(requestUrl(fetch.mock.calls[5]?.[0])).toContain(
      `/conclusions/${trialReviewIds.conclusion}:decide`,
    );
    expect(requestUrl(fetch.mock.calls[6]?.[0])).toContain(":reopen");
    for (const call of fetch.mock.calls.slice(1)) {
      expect(call[1]?.method).toBe("POST");
      expect(new Headers(call[1]?.headers).get("Idempotency-Key")).toMatch(
        /^trial-review-/u,
      );
    }
    expect(bodyValue(fetch.mock.calls[5]?.[1]?.body)).toMatchObject({
      decision: "approved",
      expectedConclusionRevisionGlobalId: conclusion.globalId,
      expectedPolicyRevisionSnapshotHash: policy.snapshotHash,
    });
  });

  it("fails closed before transport for an incomplete review reference tuple", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>();
    vi.stubGlobal("fetch", fetch);
    const source = new LiveTrialDataSource();
    const workspace = trialReviewWorkspace();
    const policy = trialConclusionPolicy();
    const comparison = trialComparison();
    const reference = trialReviewReference();

    await expect(
      source.createReviewReference(
        trialPlanningIds.project,
        trialPlanningIds.round,
        {
          comparisonSnapshotGlobalId: comparison.globalId,
          expectedComparisonSnapshotHash: comparison.snapshotHash,
          expectedFileRevisionSnapshotHash: reference.fileRevision.snapshotHash,
          expectedPartRevisionSnapshotHash: reference.partRevision.snapshotHash,
          expectedPolicyRevisionSnapshotHash: policy.snapshotHash,
          expectedReferenceVersion: 1,
          expectedRoundOptimisticVersion:
            workspace.trialRound.optimisticVersion,
          expectedRoundSnapshotHash: workspace.trialRound.snapshotHash,
          expectedToolingRevisionSnapshotHash:
            reference.toolingRevision.snapshotHash,
          expectedToolingSetSnapshotHash: reference.toolingSet.snapshotHash,
          fileRevisionGlobalId: reference.fileRevision.globalId,
          partRevisionGlobalId: reference.partRevision.globalId,
          policyRevisionGlobalId: policy.globalId,
          reason: "The predecessor tuple is intentionally incomplete",
          referenceKind: reference.referenceKind,
          toolingMasterGlobalId: reference.toolingMasterGlobalId,
          toolingRevisionGlobalId: reference.toolingRevision.globalId,
          toolingSetGlobalId: reference.toolingSet.globalId,
        },
        context("review-invalid"),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(fetch).not.toHaveBeenCalled();
  });
});
