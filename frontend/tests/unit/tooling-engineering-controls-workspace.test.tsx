import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ToolingCockpitViewModel,
  ToolingDataSource,
  ToolingEngineeringControlsViewModel,
  ToolingRevisionCollectionViewModel,
  ToolingSetCollectionViewModel,
} from "../../src/api/tooling-data-source";
import { NpiApiError, NpiTransportError } from "../../src/api/http";
import type { ReportWorkspaceDirty } from "../../src/app/workspace-navigation";
import ToolingEngineeringControlsWorkspace from "../../src/pages/tooling-engineering-controls-workspace";
import { renderWithLocale } from "../support/render";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const revisionId = "33333333-3333-4333-8333-333333333333";
const cavityId = "44444444-4444-4444-8444-444444444444";
const defectId = "55555555-5555-4555-8555-555555555555";
const defectRevisionId = "66666666-6666-4666-8666-666666666666";
const memberId = "77777777-7777-4777-8777-777777777777";
const actionId = "88888888-8888-4888-8888-888888888888";
const profileId = "99999999-9999-4999-8999-999999999999";
const profileRevisionId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const metricId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const scenarioId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const scenarioRevisionId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const lineId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const partRevisionId = "ffffffff-ffff-4fff-8fff-ffffffffffff";
const applicabilityId = "12345678-1234-4234-8234-123456789abc";
const setId = "13572468-1357-4357-8357-246813572468";
const hash = (value: string) => value.repeat(64);

function controls(
  overrides: Partial<ToolingEngineeringControlsViewModel> = {},
): ToolingEngineeringControlsViewModel {
  return {
    capacityScenarioRevisions: [
      {
        createdAt: "2026-08-08T12:10:00Z",
        createdByUserId: "tooling.engineer@example.invalid",
        effectiveFrom: "2026-08-08",
        formulaVersion: "capacity.v1",
        globalId: scenarioRevisionId,
        lines: [
          {
            applicabilityGlobalId: applicabilityId,
            applicabilitySnapshotHash: hash("b"),
            availableHoursPerDay: "20",
            cavityCount: 1,
            cavityProvenance: {
              globalId: revisionId,
              kind: "tooling_revision",
              snapshotHash: hash("a"),
            },
            cycleProvenance: {
              globalId: profileRevisionId,
              kind: "customer_standard",
              snapshotHash: hash("c"),
            },
            cycleSeconds: "35",
            effectiveSetCount: 1,
            globalId: lineId,
            oeeRatio: "0.8",
            partRevisionGlobalId: partRevisionId,
            partRevisionSnapshotHash: hash("d"),
            selectedToolingSetGlobalIds: [setId],
            setProvenance: {
              globalId: setId,
              kind: "tooling_set_selection",
              snapshotHash: hash("e"),
            },
            usagePerAssembly: "1",
            usageProvenance: {
              globalId: applicabilityId,
              kind: "tooling_applicability",
              snapshotHash: hash("b"),
            },
            workingDaysPerMonth: 26,
            yieldRatio: "0.95",
          },
        ],
        predecessorGlobalId: null,
        predecessorSnapshotHash: null,
        projectGlobalId: projectId,
        reason: "Initial scenario",
        requestId: defectRevisionId,
        result: {
          bottleneckLineGlobalIds: [lineId],
          formulaVersion: "capacity.v1",
          gap: "100.000000",
          lineResults: [
            {
              assemblyUnitsPerDay: "1954.285714",
              assemblyUnitsPerMonth: "50811.428571",
              globalId: lineId,
              partsPerDay: "1954.285714",
              partsPerMonth: "50811.428571",
            },
          ],
          roundingRule: "decimal-6-half-even",
          scenarioAssemblyUnitsPerMonth: "50811.428571",
        },
        roundingRule: "decimal-6-half-even",
        scenarioGlobalId: scenarioId,
        scenarioVersion: 1,
        schemaVersion: 1,
        snapshotHash: hash("f"),
        targetMonthlyAssemblyUnits: "50911.428571",
        tenantId: "tenant.test",
        title: "Nominal monthly capacity",
        toolingMasterGlobalId: masterId,
        traceId: "trace-workspace-test",
        versionKeyHash: hash("1"),
      },
    ],
    defectRevisions: [
      {
        actions: [
          {
            actionType: "corrective",
            detail: "Correct ejector alignment",
            dueDate: "2026-08-20",
            evidence: [],
            globalId: actionId,
            responsibleMember: {
              globalId: memberId,
              optimisticVersion: 2,
              userId: "tooling.engineer@example.invalid",
            },
            state: "completed",
          },
        ],
        blocking: true,
        businessCode: "DEF-001",
        categoryKey: "fit_and_function",
        cavityGlobalId: cavityId,
        cavityIdentifier: "C01",
        createdAt: "2026-08-08T12:00:00Z",
        createdByUserId: "tooling.engineer@example.invalid",
        defectGlobalId: defectId,
        defectVersion: 1,
        description: "Ejector alignment is outside specification.",
        detectionContext: {
          globalId: revisionId,
          kind: "tooling_revision",
          snapshotHash: hash("a"),
        },
        evidence: [],
        globalId: defectRevisionId,
        predecessorGlobalId: null,
        predecessorSnapshotHash: null,
        projectGlobalId: projectId,
        reason: "Initial finding",
        requestId: defectRevisionId,
        responsibleMember: {
          globalId: memberId,
          optimisticVersion: 2,
          userId: "tooling.engineer@example.invalid",
        },
        rootCause: "Machining alignment drift",
        rootCauseState: "recorded",
        schemaVersion: 1,
        severity: "high",
        snapshotHash: hash("2"),
        state: "ready_for_verification",
        targetRoundLabel: "T1 intention",
        tenantId: "tenant.test",
        title: "Ejector alignment",
        toolingMasterGlobalId: masterId,
        toolingRevisionGlobalId: revisionId,
        toolingRevisionSnapshotHash: hash("a"),
        traceId: "trace-workspace-test",
        trialReference: {
          reasonCode: "trial_context_unavailable",
          state: "unavailable",
        },
        versionKeyHash: hash("3"),
      },
    ],
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
          ruleGlobalId: null,
          ruleSnapshotHash: null,
          ruleVersion: null,
          state: "not_measured",
          unit: "s",
          visualSemantics: {
            reasonCode: "variance_exception_color_policy_unavailable",
            state: "unavailable",
          },
        },
      ],
      customerStandardRevisions: [
        {
          context: {
            approvalEventGlobalId: null,
            approvalEventHash: null,
            globalId: revisionId,
            kind: "tooling_revision_specification",
            releasedDocument: null,
            snapshotHash: hash("a"),
          },
          createdAt: "2026-08-08T12:05:00Z",
          createdByUserId: "tooling.engineer@example.invalid",
          effectiveFrom: "2026-08-08",
          globalId: profileRevisionId,
          layer: "customer_standard",
          metrics: [
            {
              code: "cycle_time",
              comparisonRule: null,
              globalId: metricId,
              numericValue: "35",
              textValue: null,
              unit: "s",
              valueKind: "numeric",
            },
          ],
          predecessorGlobalId: null,
          predecessorSnapshotHash: null,
          profileGlobalId: profileId,
          profileVersion: 1,
          projectGlobalId: projectId,
          reason: "Customer cycle requirement",
          requestId: defectRevisionId,
          schemaVersion: 1,
          snapshotHash: hash("c"),
          tenantId: "tenant.test",
          toolingMasterGlobalId: masterId,
          toolingRevisionGlobalId: revisionId,
          toolingRevisionSnapshotHash: hash("a"),
          traceId: "trace-workspace-test",
          versionKeyHash: hash("4"),
        },
      ],
      trialActual: {
        reasonCode: "trial_context_unavailable",
        state: "not_measured",
      },
    },
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
    ...overrides,
  };
}

function capacityScenario() {
  const value = controls().capacityScenarioRevisions[0];
  if (!value) throw new Error("The capacity scenario fixture is required.");
  return value;
}

function defectRevision() {
  const value = controls().defectRevisions[0];
  if (!value) throw new Error("The defect Revision fixture is required.");
  return value;
}

function processProfile() {
  const value = controls().process.customerStandardRevisions[0];
  if (!value) throw new Error("The process profile fixture is required.");
  return value;
}

function revisions(): ToolingRevisionCollectionViewModel {
  return {
    combinedTrial: {
      reasonCode: "combined_trial_not_delivered",
      state: "unavailable",
    },
    erpLocationAndAsset: {
      reasonCode: "erp_projection_unavailable",
      state: "unavailable",
    },
    items: [
      {
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
        globalId: revisionId,
        inserts: [],
        predecessorGlobalId: null,
        reason: "Controlled Revision",
        revisionLabel: "R1",
        revisionNumber: 1,
        snapshotHash: hash("a"),
        specification: {
          cavityCount: 1,
          targetCycle: { source: "Engineering", unit: "s", value: "35" },
        },
        toolingMasterGlobalId: masterId,
      },
    ],
    lifecycle: {
      reasonCode: "lifecycle_policy_unavailable",
      state: "unavailable",
    },
    permissions: {
      bindSetSource: false,
      createPartSpecification: false,
      createProcessChain: false,
      createRevision: false,
      transitionLifecycle: false,
      view: true,
    },
    projectGlobalId: projectId,
    supplier: {
      reasonCode: "formal_supplier_unavailable",
      state: "unavailable",
    },
    toolingMasterGlobalId: masterId,
  } as unknown as ToolingRevisionCollectionViewModel;
}

function cockpit(): ToolingCockpitViewModel {
  return {
    applicability: [
      {
        globalId: applicabilityId,
        part: {
          globalId: partRevisionId,
          partGlobalId: defectId,
          revisionLabel: "A",
          revisionNumber: 1,
          snapshotHash: hash("d"),
        },
        projectGlobalId: projectId,
        snapshotHash: hash("b"),
        toolingMasterGlobalId: masterId,
      },
    ],
    parts: [
      {
        currentRevision: { globalId: partRevisionId },
        title: "Housing",
      },
    ],
  } as unknown as ToolingCockpitViewModel;
}

function sets(): ToolingSetCollectionViewModel {
  return {
    items: [{ globalId: setId, snapshotHash: hash("e") }],
    permissions: {
      attachEvidence: false,
      createIntake: false,
      createSet: false,
      transitionLifecycle: false,
      view: true,
    },
    toolingMasterGlobalId: masterId,
  } as unknown as ToolingSetCollectionViewModel;
}

function dataSource(
  overrides: Partial<ToolingDataSource> = {},
): ToolingDataSource {
  return {
    createToolingCapacityScenarioRevision: vi.fn(() =>
      Promise.resolve({ scenario: capacityScenario() }),
    ),
    createToolingDefectRevision: vi.fn(() =>
      Promise.resolve({ defect: defectRevision() }),
    ),
    createToolingProcessProfileRevision: vi.fn(() =>
      Promise.resolve({
        profile: processProfile(),
      }),
    ),
    loadEngineeringControls: vi.fn(() => Promise.resolve(controls())),
    loadMaster: vi.fn(() => Promise.resolve(cockpit())),
    loadSets: vi.fn(() => Promise.resolve(sets())),
    loadToolingRevisions: vi.fn(() => Promise.resolve(revisions())),
    ...overrides,
  } as unknown as ToolingDataSource;
}

function enableCommandSession(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: { language: "en", messages: {}, version: hash("a") },
            csrfToken: "engineering-controls-workspace-csrf-token",
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "tooling.engineer@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

function renderWorkspace(
  source: ToolingDataSource,
  reportWorkspaceDirty?: ReportWorkspaceDirty,
): void {
  renderWithLocale(
    <ToolingEngineeringControlsWorkspace
      dataSource={source}
      masterId={masterId}
      projectId={projectId}
      reportWorkspaceDirty={reportWorkspaceDirty}
    />,
    "en",
    `/projects/${projectId}/tooling/${masterId}`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Tooling engineering-controls workspace", () => {
  it("keeps loading and the server-controlled empty read-only state explicit", async () => {
    let resolveControls:
      | ((value: ToolingEngineeringControlsViewModel) => void)
      | undefined;
    const pending = new Promise<ToolingEngineeringControlsViewModel>(
      (resolve) => {
        resolveControls = resolve;
      },
    );
    renderWorkspace(dataSource({ loadEngineeringControls: () => pending }));
    expect(
      await screen.findByText("Loading engineering controls workspace"),
    ).toBeInTheDocument();

    act(() => {
      resolveControls?.(
        controls({ capacityScenarioRevisions: [], defectRevisions: [] }),
      );
    });
    expect(
      await screen.findByText("No Tooling defect has been recorded."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No Capacity Scenario has been recorded."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Engineering controls are read only in this session."),
    ).toBeInTheDocument();
  });

  it("renders separated defect, process, capacity and unavailable health truth", async () => {
    renderWorkspace(dataSource());
    expect(await screen.findByText("DEF-001")).toBeInTheDocument();
    expect(screen.getByText("Explicitly blocking")).toBeInTheDocument();
    expect(screen.getByText("Correct ejector alignment")).toBeInTheDocument();
    expect(screen.getByText("Trial Actual")).toBeInTheDocument();
    expect(screen.getAllByText("Not measured").length).toBeGreaterThan(0);
    expect(screen.getByText("Approved Process Baseline")).toBeInTheDocument();
    expect(screen.getByText("Nominal monthly capacity")).toBeInTheDocument();
    expect(screen.getAllByText("50811.428571").length).toBeGreaterThan(0);
    expect(screen.getByText("erp_shot_count_unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Trial approved")).not.toBeInTheDocument();
  });

  it("retries an evidence-backed workspace transport failure", async () => {
    const loadEngineeringControls = vi
      .fn<ToolingDataSource["loadEngineeringControls"]>()
      .mockRejectedValueOnce(
        new NpiTransportError(
          "network",
          "trace-engineering-controls-network",
          "trace",
        ),
      )
      .mockResolvedValueOnce(controls());
    const user = userEvent.setup();
    renderWorkspace(dataSource({ loadEngineeringControls }));

    await user.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByText("DEF-001")).toBeInTheDocument();
    expect(loadEngineeringControls).toHaveBeenCalledTimes(2);
  });

  it("appends a defect without sending a Gate or Trial mutation", async () => {
    enableCommandSession();
    const create = vi.fn<ToolingDataSource["createToolingDefectRevision"]>(() =>
      Promise.resolve({ defect: defectRevision() }),
    );
    renderWorkspace(dataSource({ createToolingDefectRevision: create }));
    await screen.findByText("DEF-001");
    fireEvent.click(
      screen.getByRole("button", { name: "Append defect Revision" }),
    );
    fireEvent.change(screen.getByLabelText("Tooling Defect Revision Reason"), {
      target: { value: "Verification preparation" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Append immutable defect Revision" }),
    );

    await waitFor(() => {
      expect(create).toHaveBeenCalledTimes(1);
    });
    const payload = create.mock.calls[0]?.[2];
    expect(payload).toMatchObject({
      defectGlobalId: defectId,
      expectedVersion: 1,
      reason: "Verification preparation",
      toolingRevisionGlobalId: revisionId,
    });
    expect(payload).not.toHaveProperty("transitionGate");
    expect(payload).not.toHaveProperty("trialActual");
  });

  it("preserves exact defect inputs and reports dirty workspace ownership", async () => {
    enableCommandSession();
    const create = vi.fn<ToolingDataSource["createToolingDefectRevision"]>(() =>
      Promise.resolve({ defect: defectRevision() }),
    );
    const reportWorkspaceDirty = vi.fn<ReportWorkspaceDirty>();
    renderWorkspace(
      dataSource({ createToolingDefectRevision: create }),
      reportWorkspaceDirty,
    );
    await screen.findByText("DEF-001");
    fireEvent.click(
      screen.getByRole("button", { name: "Append defect Revision" }),
    );
    await waitFor(() => {
      expect(reportWorkspaceDirty).toHaveBeenCalledWith(
        expect.objectContaining({
          objectIdentity: `${masterId}:engineering-controls:defect`,
        }),
      );
    });

    fireEvent.change(screen.getByLabelText("Tooling Revision"), {
      target: { value: revisionId },
    });
    fireEvent.change(screen.getByLabelText("Cavity"), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByLabelText("Tooling Defect Code"), {
      target: { value: "DEF-002" },
    });
    fireEvent.change(screen.getByLabelText("Tooling Defect Title"), {
      target: { value: "Controlled verification defect" },
    });
    fireEvent.change(screen.getByLabelText("Tooling Defect Severity"), {
      target: { value: "critical" },
    });
    fireEvent.change(screen.getByLabelText("Tooling Defect State"), {
      target: { value: "in_progress" },
    });
    fireEvent.change(screen.getByLabelText("Tooling Defect Category Key"), {
      target: { value: "verification" },
    });
    fireEvent.click(screen.getByLabelText("Explicit blocking intent"));
    fireEvent.change(screen.getByLabelText("Responsible member Global ID"), {
      target: { value: memberId },
    });
    fireEvent.change(screen.getByLabelText("Responsible user ID"), {
      target: { value: "verification.owner@example.invalid" },
    });
    fireEvent.change(screen.getByLabelText("Responsible member version"), {
      target: { value: "4" },
    });
    fireEvent.change(screen.getByLabelText("Target-round intention"), {
      target: { value: "T2 intention" },
    });
    fireEvent.change(screen.getByLabelText("Corrective action"), {
      target: { value: "Verify the corrected alignment" },
    });
    fireEvent.change(screen.getByLabelText("Action due date"), {
      target: { value: "2026-08-25" },
    });
    fireEvent.change(screen.getByLabelText("File Revision Global ID"), {
      target: { value: scenarioRevisionId },
    });
    fireEvent.change(screen.getByLabelText("File optimistic version"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("Frappe content hash"), {
      target: { value: hash("d") },
    });
    fireEvent.change(screen.getByLabelText("SHA-256"), {
      target: { value: hash("e") },
    });
    fireEvent.change(screen.getByLabelText("Tooling Defect Description"), {
      target: { value: "Controlled evidence requires verification." },
    });
    fireEvent.change(screen.getByLabelText("Root cause"), {
      target: { value: "Verified machining drift" },
    });
    fireEvent.change(screen.getByLabelText("Tooling Defect Revision Reason"), {
      target: { value: "Preserve exact verification inputs" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Append immutable defect Revision" }),
    );

    await waitFor(() => {
      expect(create).toHaveBeenCalledTimes(1);
    });
    expect(create.mock.calls[0]?.[2]).toMatchObject({
      blocking: false,
      businessCode: "DEF-002",
      cavityGlobalId: null,
      evidence: [
        {
          fileOptimisticVersion: 2,
          fileRevisionGlobalId: scenarioRevisionId,
          frappeContentHash: hash("d"),
          sha256: hash("e"),
        },
      ],
      severity: "critical",
      state: "in_progress",
    });
  });

  it("keeps invalid defect, process and Capacity commands explicit", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    renderWorkspace(dataSource());
    await screen.findByText("DEF-001");

    await user.click(
      screen.getByRole("button", { name: "Append defect Revision" }),
    );
    await user.clear(screen.getByLabelText("Tooling Defect Title"));
    await user.type(
      screen.getByLabelText("Tooling Defect Revision Reason"),
      "Invalid exact defect",
    );
    await user.click(
      screen.getByRole("button", { name: "Append immutable defect Revision" }),
    );
    expect(
      screen.getByText(
        "Complete the required exact defect and evidence fields.",
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await user.click(
      screen.getByRole("button", { name: "Append Customer Standard Revision" }),
    );
    await user.clear(screen.getByLabelText("Customer Standard value"));
    await user.click(
      screen.getByRole("button", { name: "Append Customer Standard Revision" }),
    );
    expect(
      screen.getByText(
        "Complete the Customer Standard value, source and reason.",
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await user.click(
      screen.getByRole("button", { name: "Append Capacity Scenario Revision" }),
    );
    await user.clear(screen.getByLabelText("Target monthly assembly units"));
    await user.click(
      screen.getByRole("button", { name: "Append Capacity Scenario Revision" }),
    );
    expect(
      screen.getByText("Complete every explicit capacity input and reason."),
    ).toBeInTheDocument();
  });

  it("appends only Customer Standard and server-derived Capacity inputs", async () => {
    enableCommandSession();
    const createProcess = vi.fn<
      ToolingDataSource["createToolingProcessProfileRevision"]
    >(() =>
      Promise.resolve({
        profile: processProfile(),
      }),
    );
    const createCapacity = vi.fn<
      ToolingDataSource["createToolingCapacityScenarioRevision"]
    >(() => Promise.resolve({ scenario: capacityScenario() }));
    renderWorkspace(
      dataSource({
        createToolingCapacityScenarioRevision: createCapacity,
        createToolingProcessProfileRevision: createProcess,
      }),
    );
    await screen.findByText("DEF-001");

    fireEvent.click(
      screen.getByRole("button", { name: "Append Customer Standard Revision" }),
    );
    fireEvent.change(screen.getByLabelText("Process Profile Revision Reason"), {
      target: { value: "Controlled standard refresh" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Append Customer Standard Revision" }),
    );
    await waitFor(() => {
      expect(createProcess).toHaveBeenCalledTimes(1);
    });
    expect(createProcess.mock.calls[0]?.[2]).not.toHaveProperty("trialActual");
    expect(createProcess.mock.calls[0]?.[2]).not.toHaveProperty(
      "approvedBaseline",
    );

    const appendCapacity = await screen.findByRole("button", {
      name: "Append Capacity Scenario Revision",
    });
    fireEvent.click(appendCapacity);
    fireEvent.change(
      screen.getByLabelText("Capacity Scenario Revision Reason"),
      {
        target: { value: "Explicit demand adjustment" },
      },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Append Capacity Scenario Revision" }),
    );
    await waitFor(() => {
      expect(createCapacity).toHaveBeenCalledTimes(1);
    });
    expect(createCapacity.mock.calls[0]?.[2]).not.toHaveProperty("result");
    expect(createCapacity.mock.calls[0]?.[2]).toMatchObject({
      expectedVersion: 1,
      reason: "Explicit demand adjustment",
      scenarioGlobalId: scenarioId,
    });
  });

  it("retries a conflicting engineering command with one idempotency key", async () => {
    enableCommandSession();
    const create = vi
      .fn<ToolingDataSource["createToolingDefectRevision"]>()
      .mockRejectedValueOnce(
        new NpiApiError({
          code: "TOOLING_DEFECT_REVISION_CONFLICT",
          retryable: true,
          status: 409,
          title: "The defect conflicts with exact Tooling truth",
          traceId: "trace-tooling-defect-conflict",
          type: "urn:npi:problem:tooling-defect-revision-conflict",
        }),
      )
      .mockResolvedValueOnce({ defect: defectRevision() });
    const user = userEvent.setup();
    renderWorkspace(dataSource({ createToolingDefectRevision: create }));

    await user.click(
      await screen.findByRole("button", { name: "Append defect Revision" }),
    );
    await user.type(
      screen.getByLabelText("Tooling Defect Revision Reason"),
      "Retry controlled conflict",
    );
    await user.click(
      screen.getByRole("button", { name: "Append immutable defect Revision" }),
    );
    expect(
      await screen.findByText("The defect conflicts with exact Tooling truth"),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Retry exact command" }),
    );

    await waitFor(() => {
      expect(create).toHaveBeenCalledTimes(2);
    });
    expect(create.mock.calls[0]?.[3].idempotencyKey).toBe(
      create.mock.calls[1]?.[3].idempotencyKey,
    );
  });
});
