import { describe, expect, it, vi } from "vitest";

import {
  isCreateToolingCapacityScenarioRevisionCommand,
  isCreateToolingDefectRevisionCommand,
  isCreateToolingProcessProfileRevisionCommand,
  isToolingEngineeringControls,
  LiveToolingDataSource,
  type CreateToolingCapacityScenarioRevisionCommand,
  type CreateToolingDefectRevisionCommand,
  type CreateToolingProcessProfileRevisionCommand,
  type ToolingCapacityScenarioRevisionViewModel,
  type ToolingDefectRevisionViewModel,
  type ToolingEngineeringControlsViewModel,
  type ToolingProcessProfileRevisionViewModel,
} from "../../src/api/tooling-data-source";

const ids = {
  action: "11111111-1111-4111-8111-111111111111",
  applicability: "22222222-2222-4222-8222-222222222222",
  cavity: "33333333-3333-4333-8333-333333333333",
  defect: "44444444-4444-4444-8444-444444444444",
  defectRevision: "55555555-5555-4555-8555-555555555555",
  evidence: "66666666-6666-4666-8666-666666666666",
  file: "77777777-7777-4777-8777-777777777777",
  line: "88888888-8888-4888-8888-888888888888",
  master: "99999999-9999-4999-8999-999999999999",
  member: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  metric: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  partRevision: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  profile: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  profileRevision: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
  project: "ffffffff-ffff-4fff-8fff-ffffffffffff",
  request: "12345678-1234-4234-8234-123456789abc",
  revision: "13572468-1357-4357-8357-246813572468",
  rule: "24681357-2468-4468-8468-135724681357",
  scenario: "35792468-3579-4579-8579-246813579246",
  scenarioRevision: "46813579-4681-4681-8681-357924683579",
  set: "57924681-5792-4792-8792-468135794681",
};
const hash = (value: string) => value.repeat(64);

function defect(): ToolingDefectRevisionViewModel {
  return {
    actions: [
      {
        actionType: "corrective",
        detail: "Correct ejector alignment",
        dueDate: "2026-08-20",
        evidence: [],
        globalId: ids.action,
        responsibleMember: {
          globalId: ids.member,
          optimisticVersion: 2,
          userId: "tooling.engineer@example.invalid",
        },
        state: "completed",
      },
    ],
    blocking: true,
    businessCode: "DEF-001",
    categoryKey: "fit_and_function",
    cavityGlobalId: ids.cavity,
    cavityIdentifier: "C01",
    createdAt: "2026-08-08T12:00:00Z",
    createdByUserId: "tooling.engineer@example.invalid",
    defectGlobalId: ids.defect,
    defectVersion: 1,
    description: "The ejector alignment is outside the released specification.",
    detectionContext: {
      globalId: ids.revision,
      kind: "tooling_revision",
      snapshotHash: hash("a"),
    },
    evidence: [
      {
        fileName: "verification.pdf",
        fileOptimisticVersion: 3,
        fileRevisionGlobalId: ids.file,
        frappeContentHash: hash("b"),
        globalId: ids.evidence,
        mimeType: "application/pdf",
        role: "verification",
        sha256: hash("c"),
        sizeBytes: 4096,
      },
    ],
    globalId: ids.defectRevision,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: ids.project,
    reason: "Initial controlled finding",
    requestId: ids.request,
    responsibleMember: {
      globalId: ids.member,
      optimisticVersion: 2,
      userId: "tooling.engineer@example.invalid",
    },
    rootCause: "Ejector plate alignment drifted during machining.",
    rootCauseState: "recorded",
    schemaVersion: 1,
    severity: "high",
    snapshotHash: hash("d"),
    state: "ready_for_verification",
    targetRoundLabel: "T1 intention",
    tenantId: "tenant.test",
    title: "Ejector alignment",
    toolingMasterGlobalId: ids.master,
    toolingRevisionGlobalId: ids.revision,
    toolingRevisionSnapshotHash: hash("a"),
    traceId: "trace-engineering-controls",
    trialReference: {
      reasonCode: "trial_context_unavailable",
      state: "unavailable",
    },
    versionKeyHash: hash("e"),
  };
}

function profile(): ToolingProcessProfileRevisionViewModel {
  return {
    context: {
      approvalEventGlobalId: null,
      approvalEventHash: null,
      globalId: ids.revision,
      kind: "tooling_revision_specification",
      releasedDocument: null,
      snapshotHash: hash("a"),
    },
    createdAt: "2026-08-08T12:05:00Z",
    createdByUserId: "tooling.engineer@example.invalid",
    effectiveFrom: "2026-08-08",
    globalId: ids.profileRevision,
    layer: "customer_standard",
    metrics: [
      {
        code: "cycle_time",
        comparisonRule: {
          globalId: ids.rule,
          maximum: "37",
          minimum: "33",
          ruleVersion: 1,
          snapshotHash: hash("f"),
          unit: "s",
        },
        globalId: ids.metric,
        numericValue: "35",
        textValue: null,
        unit: "s",
        valueKind: "numeric",
      },
    ],
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    profileGlobalId: ids.profile,
    profileVersion: 1,
    projectGlobalId: ids.project,
    reason: "Released customer cycle requirement",
    requestId: ids.request,
    schemaVersion: 1,
    snapshotHash: hash("1"),
    tenantId: "tenant.test",
    toolingMasterGlobalId: ids.master,
    toolingRevisionGlobalId: ids.revision,
    toolingRevisionSnapshotHash: hash("a"),
    traceId: "trace-engineering-controls",
    versionKeyHash: hash("2"),
  };
}

function scenario(): ToolingCapacityScenarioRevisionViewModel {
  return {
    createdAt: "2026-08-08T12:10:00Z",
    createdByUserId: "tooling.engineer@example.invalid",
    effectiveFrom: "2026-08-08",
    formulaVersion: "capacity.v1",
    globalId: ids.scenarioRevision,
    lines: [
      {
        applicabilityGlobalId: ids.applicability,
        applicabilitySnapshotHash: hash("3"),
        availableHoursPerDay: "20",
        cavityCount: 1,
        cavityProvenance: {
          globalId: ids.revision,
          kind: "tooling_revision",
          snapshotHash: hash("a"),
        },
        cycleProvenance: {
          globalId: ids.profileRevision,
          kind: "customer_standard",
          snapshotHash: hash("1"),
        },
        cycleSeconds: "35",
        effectiveSetCount: 1,
        globalId: ids.line,
        oeeRatio: "0.8",
        partRevisionGlobalId: ids.partRevision,
        partRevisionSnapshotHash: hash("4"),
        selectedToolingSetGlobalIds: [ids.set],
        setProvenance: {
          globalId: ids.set,
          kind: "tooling_set_selection",
          snapshotHash: hash("5"),
        },
        usagePerAssembly: "1",
        usageProvenance: {
          globalId: ids.applicability,
          kind: "tooling_applicability",
          snapshotHash: hash("3"),
        },
        workingDaysPerMonth: 26,
        yieldRatio: "0.95",
      },
    ],
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: ids.project,
    reason: "Initial explicit capacity assumptions",
    requestId: ids.request,
    result: {
      bottleneckLineGlobalIds: [ids.line],
      formulaVersion: "capacity.v1",
      gap: "100.000000",
      lineResults: [
        {
          assemblyUnitsPerDay: "1954.285714",
          assemblyUnitsPerMonth: "50811.428571",
          globalId: ids.line,
          partsPerDay: "1954.285714",
          partsPerMonth: "50811.428571",
        },
      ],
      roundingRule: "decimal-6-half-even",
      scenarioAssemblyUnitsPerMonth: "50811.428571",
    },
    roundingRule: "decimal-6-half-even",
    scenarioGlobalId: ids.scenario,
    scenarioVersion: 1,
    schemaVersion: 1,
    snapshotHash: hash("6"),
    targetMonthlyAssemblyUnits: "50911.428571",
    tenantId: "tenant.test",
    title: "Nominal monthly capacity",
    toolingMasterGlobalId: ids.master,
    traceId: "trace-engineering-controls",
    versionKeyHash: hash("7"),
  };
}

function controls(): ToolingEngineeringControlsViewModel {
  return {
    capacityScenarioRevisions: [scenario()],
    defectRevisions: [defect()],
    health: {
      calibration: {
        reasonCode: "shot_count_calibration_policy_unavailable",
        state: "unavailable",
      },
      editableIn: "ERPNEXT",
      healthScore: {
        reasonCode: "tooling_health_policy_unavailable",
        state: "unavailable",
      },
      maintenance: {
        reasonCode: "erp_maintenance_projection_unavailable",
        state: "unavailable",
      },
      shotCount: {
        reasonCode: "erp_shot_count_unavailable",
        state: "unavailable",
      },
      sourceSystem: "ERPNEXT",
      state: "unavailable",
    },
    permissions: {
      approveProcessBaseline: false,
      createCapacityScenario: true,
      createCustomerStandard: true,
      createTrialActual: false,
      editHealth: false,
      reviseDefect: true,
      transitionGate: false,
      transitionToolingLifecycle: false,
      view: true,
    },
    process: {
      approvedBaseline: {
        reasonCode: "approved_trial_evidence_unavailable",
        state: "unavailable",
      },
      comparisons: [
        {
          actualValue: null,
          delta: null,
          metricCode: "cycle_time",
          percentDelta: null,
          referenceLayer: "customer_standard",
          referenceValue: "35",
          ruleGlobalId: ids.rule,
          ruleSnapshotHash: hash("f"),
          ruleVersion: 1,
          state: "not_measured",
          unit: "s",
          visualSemantics: {
            reasonCode: "variance_exception_color_policy_unavailable",
            state: "unavailable",
          },
        },
      ],
      customerStandardRevisions: [profile()],
      trialActual: {
        reasonCode: "trial_context_unavailable",
        state: "not_measured",
      },
    },
    projectGlobalId: ids.project,
    toolingMasterGlobalId: ids.master,
  };
}

function defectCommand(): CreateToolingDefectRevisionCommand {
  const value = defect();
  return {
    actions: value.actions.map((item) => ({
      actionType: item.actionType,
      detail: item.detail,
      dueDate: item.dueDate,
      evidence: [],
      globalId: item.globalId,
      responsibleMember: item.responsibleMember,
      state: item.state,
    })),
    blocking: value.blocking,
    businessCode: value.businessCode,
    categoryKey: value.categoryKey,
    cavityGlobalId: value.cavityGlobalId,
    description: value.description,
    detectionContext: value.detectionContext,
    evidence: value.evidence.map((item) => ({
      fileOptimisticVersion: item.fileOptimisticVersion,
      fileRevisionGlobalId: item.fileRevisionGlobalId,
      frappeContentHash: item.frappeContentHash,
      role: item.role,
      sha256: item.sha256,
    })),
    reason: value.reason,
    responsibleMember: value.responsibleMember,
    rootCause: value.rootCause,
    rootCauseState: value.rootCauseState,
    severity: value.severity,
    state: value.state,
    targetRoundLabel: value.targetRoundLabel,
    title: value.title,
    toolingRevisionGlobalId: value.toolingRevisionGlobalId,
    toolingRevisionSnapshotHash: value.toolingRevisionSnapshotHash,
  };
}

function profileCommand(): CreateToolingProcessProfileRevisionCommand {
  const value = profile();
  return {
    context: {
      globalId: value.context.globalId,
      kind: "tooling_revision_specification",
      snapshotHash: value.context.snapshotHash,
    },
    effectiveFrom: value.effectiveFrom,
    metrics: value.metrics.map((item) => ({
      code: item.code,
      comparisonRule: item.comparisonRule
        ? {
            maximum: item.comparisonRule.maximum,
            minimum: item.comparisonRule.minimum,
            unit: item.comparisonRule.unit,
          }
        : null,
      numericValue: item.numericValue,
      textValue: item.textValue,
      unit: item.unit,
      valueKind: item.valueKind,
    })),
    reason: value.reason,
    toolingRevisionGlobalId: value.toolingRevisionGlobalId,
    toolingRevisionSnapshotHash: value.toolingRevisionSnapshotHash,
  };
}

function capacityCommand(): CreateToolingCapacityScenarioRevisionCommand {
  const value = scenario();
  return {
    effectiveFrom: value.effectiveFrom,
    lines: value.lines.map(({ globalId, ...line }) => {
      void globalId;
      return line;
    }),
    reason: value.reason,
    targetMonthlyAssemblyUnits: value.targetMonthlyAssemblyUnits,
    title: value.title,
  };
}

function governedResponse(value: unknown, init?: RequestInit): Response {
  const headers = new Headers(init?.headers);
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Idempotency-Replayed": "false",
      "X-Request-ID": headers.get("X-Request-ID") ?? "",
      "X-Trace-ID": "trace-engineering-controls-source",
    },
    status: init?.method === "POST" ? 201 : 200,
  });
}

describe("Tooling engineering-controls live data source", () => {
  it("accepts only closed separated process, capacity and unavailable health truth", () => {
    expect(isToolingEngineeringControls(controls())).toBe(true);
    expect(
      isToolingEngineeringControls({ ...controls(), unexpected: true }),
    ).toBe(false);
    expect(
      isToolingEngineeringControls({
        ...controls(),
        process: {
          ...controls().process,
          trialActual: { state: "available", value: "35" },
        },
      }),
    ).toBe(false);
    expect(
      isToolingEngineeringControls({
        ...controls(),
        capacityScenarioRevisions: [
          { ...scenario(), result: { ...scenario().result, gap: "0" } },
        ],
      }),
    ).toBe(false);
  });

  it("rejects caller actual, approval, status and capacity result fields", () => {
    expect(isCreateToolingDefectRevisionCommand(defectCommand())).toBe(true);
    expect(isCreateToolingProcessProfileRevisionCommand(profileCommand())).toBe(
      true,
    );
    expect(
      isCreateToolingCapacityScenarioRevisionCommand(capacityCommand()),
    ).toBe(true);
    expect(
      isCreateToolingDefectRevisionCommand({
        ...defectCommand(),
        transitionGate: true,
      }),
    ).toBe(false);
    expect(
      isCreateToolingProcessProfileRevisionCommand({
        ...profileCommand(),
        trialActual: "35",
      }),
    ).toBe(false);
    expect(
      isCreateToolingCapacityScenarioRevisionCommand({
        ...capacityCommand(),
        result: scenario().result,
      }),
    ).toBe(false);
  });

  it("uses exactly one read and three governed append routes", async () => {
    const fetch = vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof request === "string"
          ? request
          : request instanceof URL
            ? request.href
            : request.url;
      const value =
        init?.method !== "POST"
          ? controls()
          : url.endsWith("/defect-revisions")
            ? { defect: defect() }
            : url.endsWith("/process-profile-revisions")
              ? { profile: profile() }
              : { scenario: scenario() };
      return Promise.resolve(governedResponse(value, init));
    });
    vi.stubGlobal("fetch", fetch);
    const source = new LiveToolingDataSource();
    const signal = new AbortController().signal;
    const context = (suffix: string) => ({
      csrfToken: "c".repeat(32),
      idempotencyKey: `tooling-engineering-${suffix}-12345678`,
      signal,
    });

    await source.loadEngineeringControls(ids.project, ids.master, signal);
    await source.createToolingDefectRevision(
      ids.project,
      ids.master,
      defectCommand(),
      context("defect"),
    );
    await source.createToolingProcessProfileRevision(
      ids.project,
      ids.master,
      profileCommand(),
      context("process"),
    );
    await source.createToolingCapacityScenarioRevision(
      ids.project,
      ids.master,
      capacityCommand(),
      context("capacity"),
    );

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/engineering-controls`,
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/defect-revisions`,
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/process-profile-revisions`,
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/capacity-scenario-revisions`,
    ]);
    expect(
      fetch.mock.calls
        .filter(([, init]) => init?.method === "POST")
        .every(([, init]) => {
          const headers = new Headers(init?.headers);
          return (
            headers.get("X-Frappe-CSRF-Token") === "c".repeat(32) &&
            headers.get("Idempotency-Key")?.startsWith("tooling-engineering-")
          );
        }),
    ).toBe(true);
  });

  it("fails closed when an exact response escapes Project containment", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_request: RequestInfo | URL, init?: RequestInit) =>
        Promise.resolve(
          governedResponse(
            { ...controls(), projectGlobalId: ids.defectRevision },
            init,
          ),
        ),
      ),
    );
    await expect(
      new LiveToolingDataSource().loadEngineeringControls(
        ids.project,
        ids.master,
        new AbortController().signal,
      ),
    ).rejects.toThrow();
  });
});
