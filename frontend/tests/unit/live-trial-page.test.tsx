import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TrialDataSource } from "../../src/api/trial-data-source";
import { NpiApiError, NpiTransportError } from "../../src/api/http";
import LiveTrialPage from "../../src/pages/live-trial-page";
import { renderWithLocale } from "../support/render";
import {
  trialExecutionIds,
  trialExecutionWorkspace,
  trialInputLock,
} from "../support/trial-execution-fixture";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";
import {
  trialQualityIds,
  trialQualityWorkspace,
} from "../support/trial-quality-fixture";
import {
  trialConclusion,
  trialReviewIds,
  trialReviewWorkspace,
} from "../support/trial-review-fixture";

const sessionCsrfToken = "c".repeat(64);

function dataSource(overrides: Partial<TrialDataSource> = {}): TrialDataSource {
  const round = trialPlanDetail().rounds[0];
  if (!round) throw new Error("The Trial page test requires one Round.");
  return {
    appendActualRevision: () => Promise.reject(new Error("not used")),
    appendSampleBatchRevision: () => Promise.reject(new Error("not used")),
    bindEvidence: () => Promise.reject(new Error("not used")),
    beginAnalysis: () => Promise.reject(new Error("not used")),
    createComparison: () => Promise.reject(new Error("not used")),
    createPlan: () => Promise.reject(new Error("not used")),
    createCavityResult: () => Promise.reject(new Error("not used")),
    createDefect: () => Promise.reject(new Error("not used")),
    createRound: () => Promise.reject(new Error("not used")),
    createReviewReference: () => Promise.reject(new Error("not used")),
    createSampleBatch: () => Promise.reject(new Error("not used")),
    downloadEvidence: () => Promise.reject(new Error("not used")),
    generateActions: () => Promise.reject(new Error("not used")),
    loadPlan: () => Promise.resolve(trialPlanDetail()),
    loadRoundQuality: () => Promise.resolve(trialQualityWorkspace()),
    loadRoundReview: () => Promise.resolve(trialReviewWorkspace()),
    loadRoundExecution: () =>
      Promise.resolve(
        trialExecutionWorkspace({
          actualRevisions: [],
          evidence: [],
          inputLocks: [],
          missingFacts: [
            "input_lock",
            "actual_context",
            "sample_batch",
            "evidence",
          ],
          pendingFiles: [],
          permissions: {
            canManageEvidence: false,
            canManageSamples: false,
            canPrepare: true,
            canRecordActual: false,
            canStart: false,
          },
          round,
          sampleBatchRevisions: [],
        }),
      ),
    loadWorkspace: () => Promise.resolve(trialPlanningWorkspace()),
    prepareRound: () => Promise.reject(new Error("not used")),
    reviseCavityResult: () => Promise.reject(new Error("not used")),
    reviseDefect: () => Promise.reject(new Error("not used")),
    revisePlan: () => Promise.reject(new Error("not used")),
    decideConclusion: () => Promise.reject(new Error("not used")),
    reopenConclusion: () => Promise.reject(new Error("not used")),
    startRound: () => Promise.reject(new Error("not used")),
    submitConclusion: () => Promise.reject(new Error("not used")),
    uploadEvidenceFile: () => Promise.reject(new Error("not used")),
    verifyDefect: () => Promise.reject(new Error("not used")),
    ...overrides,
  };
}

function installAuthenticatedSession(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: {
              language: "en",
              messages: {},
              version: "7".repeat(64),
            },
            csrfToken: sessionCsrfToken,
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "trial.engineer@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

async function confirmCommand(
  user: ReturnType<typeof userEvent.setup>,
  commandName: string,
  reason: string,
): Promise<void> {
  await user.click(screen.getByRole("button", { name: "Review command" }));
  const dialog = await screen.findByRole("dialog", {
    name: "Review immutable Trial command",
  });
  await user.type(within(dialog).getByLabelText("Reason"), reason);
  await user.click(within(dialog).getByRole("button", { name: commandName }));
}

async function confirmExecutionCommand(
  user: ReturnType<typeof userEvent.setup>,
  commandName: string,
  reason: string,
): Promise<void> {
  await user.click(screen.getByRole("button", { name: "Review command" }));
  const dialog = await screen.findByRole("dialog", {
    name: "Review immutable Trial execution command",
  });
  fireEvent.change(within(dialog).getByLabelText("Reason"), {
    target: { value: reason },
  });
  await user.click(within(dialog).getByRole("button", { name: commandName }));
}

async function completeCavityEditor(
  user: ReturnType<typeof userEvent.setup>,
): Promise<void> {
  await user.type(screen.getByLabelText("Characteristic key"), "rib.width");
  await user.type(screen.getByLabelText("Characteristic label"), "Rib width");
  await user.type(screen.getByLabelText("Lower limit"), "2.40");
  await user.type(screen.getByLabelText("Nominal value"), "2.50");
  await user.type(screen.getByLabelText("Upper limit"), "2.60");
  await user.type(screen.getByLabelText("Measured value"), "2.51");
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("live Trial planning page", () => {
  it("renders distinct Plan, Round, resource and governed-action truth", async () => {
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource()}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    expect(
      await screen.findByRole("heading", { name: /Trial planning workspace/u }),
    ).toBeVisible();
    expect(await screen.findByText("Injection machine 550T")).toBeVisible();
    await waitFor(() => {
      expect(
        screen.getAllByText(
          "Verify first-shot fill balance and dimensional intent",
        ),
      ).toHaveLength(2);
    });
    expect(screen.getByText("PA66-GF30 natural")).toBeVisible();
    expect(screen.getAllByText("T0").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(trialPlanningIds.workItem)).toBeVisible();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("No booking claim")).toBeVisible();
    expect(screen.getByText("Execution boundary active")).toBeVisible();
  });

  it("shows an honest empty planning state without inventing a Round", async () => {
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          loadWorkspace: () =>
            Promise.resolve(trialPlanningWorkspace({ plans: [] })),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    expect(
      await screen.findByText(
        "No Trial Plan has been recorded for this Project.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("T0")).not.toBeInTheDocument();
  });

  it("creates a controlled Plan with exact resource and member references", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const createPlan = vi
      .fn<TrialDataSource["createPlan"]>()
      .mockResolvedValue({ detail: trialPlanDetail(), replayed: false });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          createPlan,
          loadWorkspace: () =>
            Promise.resolve(trialPlanningWorkspace({ plans: [] })),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const create = await screen.findByRole("button", {
      name: "Create Trial Plan",
    });
    await waitFor(() => {
      expect(create).toBeEnabled();
    });
    await user.click(create);
    await user.type(
      screen.getByLabelText("Tooling Master stable ID"),
      trialPlanningIds.toolingMaster,
    );
    await user.type(
      screen.getByLabelText("Trial objective"),
      "Verify controlled T0 scope",
    );
    await user.type(
      screen.getByLabelText("Machine source object ID"),
      "IM-550-02",
    );
    await user.type(
      screen.getByLabelText("Machine label"),
      "Injection machine 550T",
    );
    await user.type(
      screen.getByLabelText("Material source object ID"),
      "MAT-PA66-GF30",
    );
    await user.type(
      screen.getByLabelText("Material label"),
      "PA66-GF30 natural",
    );
    await user.type(
      screen.getByLabelText("Responsible Project member stable IDs"),
      trialPlanningIds.member,
    );
    await user.type(
      screen.getByLabelText("Measurement-plan intent"),
      "Measure the critical housing dimensions",
    );
    await confirmCommand(user, "Create Trial Plan", "Create controlled plan");

    await waitFor(() => {
      expect(createPlan).toHaveBeenCalledTimes(1);
    });
    const createCall = createPlan.mock.calls[0];
    expect(createCall?.[0]).toBe(trialPlanningIds.project);
    expect(createCall?.[1]).toMatchObject({
      objective: "Verify controlled T0 scope",
      responsibleMemberGlobalIds: [trialPlanningIds.member],
      toolingMasterGlobalId: trialPlanningIds.toolingMaster,
    });
    expect(createCall?.[2].csrfToken).toBe(sessionCsrfToken);
    expect(createCall?.[2].idempotencyKey).toMatch(/^trial-plan-create-/u);
  });

  it("appends a version-locked Plan revision and reports replay truth", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const revisePlan = vi
      .fn<TrialDataSource["revisePlan"]>()
      .mockResolvedValue({ detail: trialPlanDetail(), replayed: true });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({ revisePlan })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const append = await screen.findByRole("button", {
      name: "Append revision",
    });
    await waitFor(() => {
      expect(append).toBeEnabled();
    });
    await user.click(append);
    await user.clear(screen.getByLabelText("Trial objective"));
    await user.type(
      screen.getByLabelText("Trial objective"),
      "Verify revised controlled scope",
    );
    await confirmCommand(
      user,
      "Append Trial Plan revision",
      "Capture revised intent",
    );

    await waitFor(() => {
      expect(revisePlan).toHaveBeenCalledTimes(1);
    });
    const reviseCall = revisePlan.mock.calls[0];
    expect(reviseCall?.[0]).toBe(trialPlanningIds.project);
    expect(reviseCall?.[1]).toBe(trialPlanningIds.plan);
    expect(reviseCall?.[2]).toMatchObject({
      expectedPlanVersion: 1,
      expectedRevisionGlobalId: trialPlanningIds.revisionOne,
      expectedRevisionSnapshotHash: "1".repeat(64),
    });
    expect(reviseCall?.[3].idempotencyKey).toMatch(/^trial-plan-revise-/u);
    expect(
      await screen.findByText(
        "The exact prior Trial command response was replayed safely.",
      ),
    ).toBeVisible();
  });

  it("retries an exact planned-Round command with one idempotency key", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const createRound = vi
      .fn<TrialDataSource["createRound"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "request-round-test", "request"),
      )
      .mockResolvedValueOnce({ detail: trialPlanDetail(), replayed: true });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({ createRound })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const create = await screen.findByRole("button", {
      name: "Create planned Round",
    });
    await waitFor(() => {
      expect(create).toBeEnabled();
    });
    await user.click(create);
    await user.type(screen.getByLabelText("Optional Round label"), "T1");
    await confirmCommand(
      user,
      "Create planned Trial Round",
      "Schedule an exact Round",
    );
    await user.click(
      await screen.findByRole("button", { name: "Retry exact command" }),
    );

    await waitFor(() => {
      expect(createRound).toHaveBeenCalledTimes(2);
    });
    const firstContext = createRound.mock.calls[0]?.[3];
    const retryContext = createRound.mock.calls[1]?.[3];
    expect(firstContext?.idempotencyKey).toBe(retryContext?.idempotencyKey);
    expect(createRound.mock.calls[0]?.[2]).toEqual(
      createRound.mock.calls[1]?.[2],
    );
  });

  it("generates one governed Project Work action from the locked Plan", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const generateActions = vi
      .fn<TrialDataSource["generateActions"]>()
      .mockResolvedValue({ detail: trialPlanDetail(), replayed: false });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({ generateActions })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const generate = await screen.findByRole("button", {
      name: "Generate action",
    });
    await waitFor(() => {
      expect(generate).toBeEnabled();
    });
    await user.click(generate);
    await user.type(screen.getByLabelText("Action key"), "TRIAL.REVIEW");
    await user.type(
      screen.getByLabelText("Action title"),
      "Review Trial dimensions",
    );
    await user.click(screen.getByText("Blocking action", { exact: true }));
    await confirmCommand(
      user,
      "Generate governed action",
      "Create governed follow-up",
    );

    await waitFor(() => {
      expect(generateActions).toHaveBeenCalledTimes(1);
    });
    const generateCall = generateActions.mock.calls[0];
    expect(generateCall?.[0]).toBe(trialPlanningIds.project);
    expect(generateCall?.[1]).toBe(trialPlanningIds.plan);
    expect(generateCall?.[2]).toMatchObject({
      actions: [
        {
          actionKey: "TRIAL.REVIEW",
          blocking: true,
          description: null,
          dueAt: "2026-08-20T12:00:00.000Z",
          responsibleMemberGlobalId: trialPlanningIds.member,
          severity: "medium",
          title: "Review Trial dimensions",
        },
      ],
      expectedPlanRevisionGlobalId: trialPlanningIds.revisionOne,
      expectedPlanRevisionSnapshotHash: "1".repeat(64),
      reason: "Create governed follow-up",
      trialRoundGlobalId: trialPlanningIds.round,
    });
    expect(generateCall?.[3].idempotencyKey).toMatch(
      /^trial-actions-generate-/u,
    );
  });

  it("keeps server-denied capabilities read only", async () => {
    const workspace = trialPlanningWorkspace({
      permissions: {
        canCreatePlan: false,
        canCreateRound: false,
        canGenerateActions: false,
        canRevisePlan: false,
      },
    });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          loadPlan: () =>
            Promise.resolve(
              trialPlanDetail({ permissions: workspace.permissions }),
            ),
          loadWorkspace: () => Promise.resolve(workspace),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    expect(
      await screen.findByText("Trial planning is read only for this Project."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Create Trial Plan" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Append revision" }),
    ).not.toBeInTheDocument();
  });

  it("renders a referenced failure and retries a retryable workspace load", async () => {
    const user = userEvent.setup();
    const loadWorkspace = vi
      .fn<TrialDataSource["loadWorkspace"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "request-trial-test", "request"),
      )
      .mockResolvedValueOnce(trialPlanningWorkspace());
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({ loadWorkspace })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Trial planning workspace unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByText("request-trial-test")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(loadWorkspace).toHaveBeenCalledTimes(2);
    });
    expect(
      await screen.findByRole("heading", { name: /Trial planning workspace/u }),
    ).toBeVisible();
  });

  it("renders dense running actual, Sample and private-evidence truth", async () => {
    const running = trialExecutionWorkspace();
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          loadRoundExecution: () => Promise.resolve(running),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    expect(
      await screen.findByRole("heading", { name: "Actual process parameters" }),
    ).toBeVisible();
    expect(screen.getByText("91 MPa")).toBeVisible();
    expect(screen.getByText("T0-SAMPLE-01")).toBeVisible();
    expect(screen.getByText("Clean and private")).toBeVisible();
    expect(screen.getByText("Machine import unavailable")).toBeVisible();
    expect(screen.getByText("Pending scan")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Bind as evidence" }),
    ).toBeDisabled();
  });

  it("starts only the exact prepared Round with manual observations", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const prepared = trialExecutionWorkspace({
      actualRevisions: [],
      evidence: [],
      missingFacts: ["actual_context", "sample_batch", "evidence"],
      pendingFiles: [],
      permissions: {
        canManageEvidence: false,
        canManageSamples: false,
        canPrepare: false,
        canRecordActual: false,
        canStart: true,
      },
      round: {
        ...trialExecutionWorkspace().round,
        currentState: "prepared",
        optimisticVersion: 2,
      },
      sampleBatchRevisions: [],
    });
    const startRound = vi
      .fn<TrialDataSource["startRound"]>()
      .mockResolvedValue({
        replayed: false,
        workspace: trialExecutionWorkspace(),
      });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          loadRoundExecution: () => Promise.resolve(prepared),
          startRound,
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const start = await screen.findByRole("button", {
      name: "Start Trial Round",
    });
    await waitFor(() => {
      expect(start).toBeEnabled();
    });
    await user.click(start);
    await user.selectOptions(
      screen.getByLabelText("injection.pressure measurement state"),
      "measured",
    );
    await user.type(
      screen.getByLabelText("injection.pressure observed value"),
      "91",
    );
    await user.selectOptions(
      screen.getByLabelText("cooling.time measurement state"),
      "measured",
    );
    await user.type(screen.getByLabelText("cooling.time observed value"), "20");
    await confirmExecutionCommand(
      user,
      "Start Trial Round",
      "Begin controlled T0 execution",
    );

    await waitFor(() => {
      expect(startRound).toHaveBeenCalledOnce();
    });
    expect(startRound.mock.calls[0]?.[2]).toMatchObject({
      expectedInputLockRevisionGlobalId: trialInputLock().globalId,
      expectedInputLockVersion: 1,
      expectedRoundOptimisticVersion: 2,
      operatorUserId: "trial.engineer@example.invalid",
      parameters: [
        { definitionKey: "injection.pressure", state: "measured", value: "91" },
        { definitionKey: "cooling.time", state: "measured", value: "20" },
      ],
    });
  });

  it("prepares one planned Round from exact released references and observed material", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const lock = trialInputLock();
    const prepared = trialExecutionWorkspace({
      actualRevisions: [],
      evidence: [],
      inputLocks: [lock],
      pendingFiles: [],
      permissions: {
        canManageEvidence: false,
        canManageSamples: false,
        canPrepare: false,
        canRecordActual: false,
        canStart: true,
      },
      round: {
        ...trialExecutionWorkspace().round,
        currentState: "prepared",
        optimisticVersion: 2,
      },
      sampleBatchRevisions: [],
    });
    const prepareRound = vi
      .fn<TrialDataSource["prepareRound"]>()
      .mockResolvedValue({ replayed: false, workspace: prepared });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({ prepareRound })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const prepare = await screen.findByRole("button", {
      name: "Prepare Trial Round",
    });
    await waitFor(() => {
      expect(prepare).toBeEnabled();
    });
    await user.click(prepare);
    const referenceLabels = [
      "Design baseline",
      "Part revision",
      "Tooling revision",
      "Tooling Set",
      "Tooling Set binding",
      "Cavity",
      "Process chain",
      "Inspection document",
    ] as const;
    for (const [index, reference] of lock.references.entries()) {
      const referenceLabel = referenceLabels[index];
      if (!referenceLabel) throw new Error("A reference label is required.");
      fireEvent.change(screen.getByLabelText(`${referenceLabel} stable ID`), {
        target: { value: reference.globalId },
      });
    }
    fireEvent.change(screen.getByLabelText("Lot or batch code"), {
      target: { value: "LOT-T0-01" },
    });
    fireEvent.change(screen.getByLabelText("Parameter 1 key"), {
      target: { value: "hold.time" },
    });
    fireEvent.change(screen.getByLabelText("Parameter 1 category"), {
      target: { value: "Holding" },
    });
    fireEvent.change(screen.getByLabelText("Parameter 1 unit"), {
      target: { value: "s" },
    });
    await confirmExecutionCommand(
      user,
      "Prepare Trial Round",
      "Freeze exact released inputs",
    );

    await waitFor(() => {
      expect(prepareRound).toHaveBeenCalledOnce();
    });
    expect(prepareRound.mock.calls[0]?.[2]).toMatchObject({
      expectedRoundOptimisticVersion: 1,
      material: {
        label: "PA66-GF30 natural",
        lotBatchCode: "LOT-T0-01",
        sourceObjectId: "MAT-PA66-GF30",
      },
      parameterDefinitions: [
        expect.objectContaining({
          category: "Holding",
          key: "hold.time",
          required: true,
          unit: "s",
        }),
      ],
      references: lock.references.map((reference) => ({
        expectedOptimisticVersion: 1,
        globalId: reference.globalId,
        kind: reference.kind,
      })),
    });
  });

  it("appends exact actual and Sample Batch successor revisions", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const running = trialExecutionWorkspace();
    const appendActualRevision = vi
      .fn<TrialDataSource["appendActualRevision"]>()
      .mockResolvedValue({ replayed: false, workspace: running });
    const appendSampleBatchRevision = vi
      .fn<TrialDataSource["appendSampleBatchRevision"]>()
      .mockResolvedValue({ replayed: true, workspace: running });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          appendActualRevision,
          appendSampleBatchRevision,
          loadRoundExecution: () => Promise.resolve(running),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const appendActual = await screen.findByRole("button", {
      name: "Append actual revision",
    });
    await waitFor(() => {
      expect(appendActual).toBeEnabled();
    });
    await user.click(appendActual);
    fireEvent.change(screen.getByLabelText("Environment value"), {
      target: { value: "25" },
    });
    await confirmExecutionCommand(
      user,
      "Append actual revision",
      "Record the controlled follow-up observation",
    );
    await waitFor(() => {
      expect(appendActualRevision).toHaveBeenCalledOnce();
    });
    expect(appendActualRevision.mock.calls[0]?.[2]).toMatchObject({
      expectedActualRevisionGlobalId: trialExecutionIds.actualRevision,
      expectedActualVersion: 1,
      expectedRoundOptimisticVersion: running.round.optimisticVersion,
      environment: [expect.objectContaining({ value: "25" })],
    });

    const sampleRow = screen.getByRole("row", { name: /T0-SAMPLE-01/u });
    await user.click(
      within(sampleRow).getByRole("button", { name: "Append revision" }),
    );
    fireEvent.change(screen.getByLabelText("Destination"), {
      target: { value: "Customer lab" },
    });
    fireEvent.change(screen.getByLabelText("Feedback source"), {
      target: { value: "Customer quality" },
    });
    fireEvent.change(screen.getByLabelText("Feedback observation"), {
      target: { value: "Dimensional review accepted" },
    });
    fireEvent.change(screen.getByLabelText("Feedback observed at (UTC)"), {
      target: { value: "2026-08-10T10:30" },
    });
    await confirmExecutionCommand(
      user,
      "Append Sample Batch revision",
      "Record controlled sample feedback",
    );
    await waitFor(() => {
      expect(appendSampleBatchRevision).toHaveBeenCalledOnce();
    });
    expect(appendSampleBatchRevision.mock.calls[0]?.[2]).toBe(
      trialExecutionIds.sampleBatch,
    );
    expect(appendSampleBatchRevision.mock.calls[0]?.[3]).toMatchObject({
      expectedRevisionGlobalId: trialExecutionIds.sampleRevision,
      expectedSampleVersion: 1,
      sample: {
        destination: "Customer lab",
        feedbackSource: "Customer quality",
        feedbackText: "Dimensional review accepted",
        label: "T0-SAMPLE-01",
      },
    });
    expect(
      await screen.findByText(
        "The exact prior execution command response was replayed safely.",
      ),
    ).toBeVisible();
  });

  it("uploads a private pending file and downloads clean evidence as audited bytes", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const running = trialExecutionWorkspace();
    const uploadEvidenceFile = vi
      .fn<TrialDataSource["uploadEvidenceFile"]>()
      .mockResolvedValue({ replayed: false, workspace: running });
    const downloadEvidence = vi
      .fn<TrialDataSource["downloadEvidence"]>()
      .mockResolvedValue({
        blob: new Blob(["clean evidence"], { type: "image/png" }),
        fileName: "t0-photo.png",
      });
    const createObjectURL = vi.fn(() => "blob:npi-trial-evidence");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal(
      "URL",
      class extends URL {
        static createObjectURL = createObjectURL;
        static revokeObjectURL = revokeObjectURL;
      },
    );
    const anchorClick = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          downloadEvidence,
          loadRoundExecution: () => Promise.resolve(running),
          uploadEvidenceFile,
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const upload = await screen.findByRole("button", {
      name: "Upload private evidence file",
    });
    await waitFor(() => {
      expect(upload).toBeEnabled();
    });
    await user.click(upload);
    const file = new File(["curve"], "curve.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Evidence file"), file);
    await user.click(
      screen.getByRole("button", { name: "Upload pending file" }),
    );
    await waitFor(() => {
      expect(uploadEvidenceFile).toHaveBeenCalledOnce();
    });
    expect(uploadEvidenceFile.mock.calls[0]?.[2]).toMatchObject({
      expectedRoundOptimisticVersion: running.round.optimisticVersion,
      file,
    });

    await user.click(
      screen.getByRole("button", { name: "Download audited bytes" }),
    );
    await waitFor(() => {
      expect(downloadEvidence).toHaveBeenCalledOnce();
      expect(anchorClick).toHaveBeenCalledOnce();
    });
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:npi-trial-evidence");
    expect(
      await screen.findByText("Private Trial evidence downloaded"),
    ).toBeVisible();
  });

  it("binds only a clean pending File Revision with its exact version", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const running = trialExecutionWorkspace({
      evidence: [],
      missingFacts: ["evidence"],
      pendingFiles: [
        {
          fileName: "trial-photo.png",
          globalId: "10000000-0000-4000-8000-000000000007",
          mimeType: "image/png",
          optimisticVersion: 3,
          privacy: "private",
          scanState: "clean",
          sha256: "9".repeat(64),
          sizeBytes: 2048,
        },
      ],
    });
    const bindEvidence = vi
      .fn<TrialDataSource["bindEvidence"]>()
      .mockResolvedValue({
        replayed: false,
        workspace: trialExecutionWorkspace(),
      });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          bindEvidence,
          loadRoundExecution: () => Promise.resolve(running),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const bind = await screen.findByRole("button", {
      name: "Bind as evidence",
    });
    await waitFor(() => {
      expect(bind).toBeEnabled();
    });
    await user.click(bind);
    await user.selectOptions(
      screen.getByLabelText("Evidence role"),
      "measurement_report",
    );
    await user.selectOptions(
      screen.getByLabelText("Related Sample Batch revision"),
      running.sampleBatchRevisions[0]?.globalId ?? "",
    );
    await user.click(
      screen.getByRole("button", { name: "Bind clean evidence" }),
    );

    await waitFor(() => {
      expect(bindEvidence).toHaveBeenCalledOnce();
    });
    expect(bindEvidence.mock.calls[0]?.[2]).toMatchObject({
      expectedFileOptimisticVersion: 3,
      expectedRoundOptimisticVersion: running.round.optimisticVersion,
      role: "measurement_report",
      sampleBatchRevisionGlobalId: running.sampleBatchRevisions[0]?.globalId,
      expectedSampleVersion: 1,
    });
  });

  it("retries a referenced execution-workspace load failure", async () => {
    const user = userEvent.setup();
    const loadRoundExecution = vi
      .fn<TrialDataSource["loadRoundExecution"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "request-execution-test", "request"),
      )
      .mockResolvedValueOnce(trialExecutionWorkspace());
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({ loadRoundExecution })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Trial execution workspace unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByText("request-execution-test")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(loadRoundExecution).toHaveBeenCalledTimes(2);
    });
    expect(
      await screen.findByRole("heading", { name: "Actual process parameters" }),
    ).toBeVisible();
  });

  it("renders dense cavity, defect, action, verification and unavailable external quality truth", async () => {
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource()}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    expect(
      await screen.findByRole("heading", { name: "Trial quality workspace" }),
    ).toBeVisible();
    expect(screen.getByText("Rib end width")).toBeVisible();
    expect(screen.getAllByText("DEF-T0-001")).toHaveLength(3);
    expect(screen.getByText("Corrective")).toBeVisible();
    expect(
      screen.getByText(
        "The first verification still shows an undersized rib end.",
      ),
    ).toBeVisible();
    expect(screen.getByText("NCR creation")).toBeVisible();
    expect(screen.getAllByText("Unavailable in this checkpoint")).toHaveLength(
      6,
    );
  });

  it("renders exact Round comparison, policy blockers and proposal-only conclusion truth", async () => {
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource()}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Trial review and conclusion",
      }),
    ).toBeVisible();
    expect(screen.getByText("material.lot_batch")).toBeVisible();
    expect(screen.getAllByText("rib.end.width")).toHaveLength(2);
    expect(screen.getByText("Controlled quality report")).toBeVisible();
    expect(screen.getAllByText("Conditional pass")).toHaveLength(2);
    expect(screen.getByText("A blocking defect remains open")).toBeVisible();
    expect(screen.getByText("Proposal only")).toBeVisible();
    expect(
      screen.getByText(
        "This review records an NPI One proposal only. It does not create ERP quality, customer signature, Gate, readiness or Tooling lifecycle truth.",
      ),
    ).toBeVisible();
  });

  it("records an independent decision against the exact submitted conclusion", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const decideConclusion = vi
      .fn<TrialDataSource["decideConclusion"]>()
      .mockResolvedValue({
        replayed: false,
        workspace: trialReviewWorkspace(),
      });
    const conclusion = trialConclusion();
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({ decideConclusion })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Record conclusion decision",
      }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Review immutable Trial conclusion command",
    });
    await user.type(
      within(dialog).getByLabelText("Reason"),
      "Approve the exact submitted proposal after independent review",
    );
    await user.click(
      within(dialog).getByRole("button", {
        name: "Record conclusion decision",
      }),
    );

    await waitFor(() => {
      expect(decideConclusion).toHaveBeenCalledOnce();
    });
    expect(decideConclusion.mock.calls[0]?.[2]).toBe(trialReviewIds.conclusion);
    expect(decideConclusion.mock.calls[0]?.[3]).toMatchObject({
      decision: "approved",
      expectedConclusionRevisionGlobalId: conclusion.globalId,
      expectedConclusionRevisionSnapshotHash: conclusion.snapshotHash,
      expectedConclusionVersion: conclusion.conclusionVersion,
      expectedPolicyRevisionSnapshotHash: "1".repeat(64),
      expectedRoundOptimisticVersion: 2,
      expectedRoundSnapshotHash: "5".repeat(64),
      reason: "Approve the exact submitted proposal after independent review",
    });
  });

  it("records one exact cavity result through review and immutable command context", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const createCavityResult = vi
      .fn<TrialDataSource["createCavityResult"]>()
      .mockResolvedValue({
        replayed: false,
        workspace: trialQualityWorkspace(),
      });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          createCavityResult,
          loadRoundExecution: () => Promise.resolve(trialExecutionWorkspace()),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const record = await screen.findByRole("button", {
      name: "Record cavity result",
    });
    await waitFor(() => {
      expect(record).toBeEnabled();
    });
    await user.click(record);
    await user.type(screen.getByLabelText("Characteristic key"), "rib.width");
    await user.type(screen.getByLabelText("Characteristic label"), "Rib width");
    await user.type(screen.getByLabelText("Lower limit"), "2.40");
    await user.type(screen.getByLabelText("Nominal value"), "2.50");
    await user.type(screen.getByLabelText("Upper limit"), "2.60");
    await user.type(screen.getByLabelText("Measured value"), "2.51");
    await user.click(screen.getByRole("button", { name: "Review command" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Review immutable Trial quality command",
    });
    await user.type(
      within(dialog).getByLabelText("Reason"),
      "Record exact T0 cavity evidence",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Record cavity result" }),
    );

    await waitFor(() => {
      expect(createCavityResult).toHaveBeenCalledOnce();
    });
    expect(createCavityResult.mock.calls[0]?.[2]).toMatchObject({
      cavityGlobalId: trialExecutionIds.cavity,
      evidence: [
        {
          globalId: trialExecutionIds.evidence,
          snapshotHash: "f".repeat(64),
        },
      ],
      measurements: [
        {
          characteristicKey: "rib.width",
          lowerLimit: "2.40",
          nominalValue: "2.50",
          state: "measured",
          upperLimit: "2.60",
          value: "2.51",
        },
      ],
      reason: "Record exact T0 cavity evidence",
    });
    expect(createCavityResult.mock.calls[0]?.[3].csrfToken).toBe(
      sessionCsrfToken,
    );
  });

  it("renders empty quality truth and blocks review until every exact field is valid", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          loadRoundExecution: () => Promise.resolve(trialExecutionWorkspace()),
          loadRoundQuality: () =>
            Promise.resolve(
              trialQualityWorkspace({
                cavityFilters: [],
                cavityResultRevisions: [],
                defectRevisions: [],
                pareto: [],
                verificationRevisions: [],
              }),
            ),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const record = await screen.findByRole("button", {
      name: "Record cavity result",
    });
    await waitFor(() => {
      expect(record).toBeEnabled();
    });
    expect(
      screen.getByText("No cavity result has been recorded."),
    ).toBeVisible();
    expect(
      screen.getByText("No governed defect action is recorded."),
    ).toBeVisible();
    expect(
      screen.getByText("No independent verification has been recorded."),
    ).toBeVisible();

    await user.click(record);
    await user.click(screen.getByRole("button", { name: "Review command" }));
    expect(
      screen.getByText(
        "Complete every required quality field and exact evidence reference before review.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("dialog", {
        name: "Review immutable Trial quality command",
      }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("heading", { name: "Record cavity result" }),
    ).not.toBeInTheDocument();
  });

  it("retries one conflicted quality command with the original idempotency key", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const createCavityResult = vi
      .fn<TrialDataSource["createCavityResult"]>()
      .mockRejectedValueOnce(
        new NpiApiError({
          code: "TRIAL_QUALITY_CONFLICT",
          retryable: true,
          status: 409,
          title: "The Trial quality workspace changed.",
          traceId: "trace-quality-conflict",
          type: "urn:npi:error:trial_quality_conflict",
        }),
      )
      .mockResolvedValueOnce({
        replayed: true,
        workspace: trialQualityWorkspace(),
      });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          createCavityResult,
          loadRoundExecution: () => Promise.resolve(trialExecutionWorkspace()),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const record = await screen.findByRole("button", {
      name: "Record cavity result",
    });
    await waitFor(() => {
      expect(record).toBeEnabled();
    });
    await user.click(record);
    await completeCavityEditor(user);
    await user.click(screen.getByRole("button", { name: "Review command" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Review immutable Trial quality command",
    });
    await user.type(
      within(dialog).getByLabelText("Reason"),
      "Record an exact conflict retry",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Record cavity result" }),
    );

    expect(
      await screen.findByText("The Trial quality workspace changed."),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Retry exact command" }),
    );

    await waitFor(() => {
      expect(createCavityResult).toHaveBeenCalledTimes(2);
    });
    expect(createCavityResult.mock.calls[0]?.[3].idempotencyKey).toBe(
      createCavityResult.mock.calls[1]?.[3].idempotencyKey,
    );
    expect(
      await screen.findByText(
        "The exact prior quality command response was replayed safely.",
      ),
    ).toBeVisible();
  });

  it("reloads the quality workspace after a retryable load failure", async () => {
    const loadRoundQuality = vi
      .fn<TrialDataSource["loadRoundQuality"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "request-quality-load", "request"),
      )
      .mockResolvedValueOnce(trialQualityWorkspace());
    const user = userEvent.setup();
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({ loadRoundQuality })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const unavailable = await screen.findByRole("heading", {
      name: "Trial quality workspace unavailable",
    });
    const panel = unavailable.closest("section");
    if (!panel) throw new Error("The quality failure panel is required.");
    await user.click(within(panel).getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { name: "Trial quality workspace" }),
    ).toBeVisible();
    expect(loadRoundQuality).toHaveBeenCalledTimes(2);
  });

  it("records an independent verification against exact defect, action, Round and cavity truth", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const verifyDefect = vi
      .fn<TrialDataSource["verifyDefect"]>()
      .mockResolvedValue({
        replayed: false,
        workspace: trialQualityWorkspace(),
      });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          loadRoundExecution: () => Promise.resolve(trialExecutionWorkspace()),
          verifyDefect,
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    await user.click(await screen.findByRole("button", { name: "Verify" }));
    await user.type(
      screen.getByLabelText("Verification finding"),
      "The second exact attempt confirms the corrective action.",
    );
    await user.click(screen.getByRole("button", { name: "Review command" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Review immutable Trial quality command",
    });
    await user.type(
      within(dialog).getByLabelText("Reason"),
      "Verify the exact completed action",
    );
    await user.click(
      within(dialog).getByRole("button", {
        name: "Record independent verification",
      }),
    );

    await waitFor(() => {
      expect(verifyDefect).toHaveBeenCalledOnce();
    });
    expect(verifyDefect.mock.calls[0]?.[2]).toBe(trialQualityIds.defect);
    expect(verifyDefect.mock.calls[0]?.[3]).toMatchObject({
      actionGlobalId: trialQualityIds.action,
      cavityResultRevisionGlobalId: trialQualityIds.cavityResultRevision,
      expectedAttemptSequence: 1,
      expectedDefectRevisionGlobalId: trialQualityIds.trialDefectRevision,
      expectedTargetRoundOptimisticVersion: 1,
      finding: "The second exact attempt confirms the corrective action.",
      result: "pass",
      targetRoundGlobalId: trialPlanningIds.round,
      verificationGlobalId: trialQualityIds.verification,
    });
  });

  it("appends a cavity result revision against its exact predecessor", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const reviseCavityResult = vi
      .fn<TrialDataSource["reviseCavityResult"]>()
      .mockResolvedValue({
        replayed: false,
        workspace: trialQualityWorkspace(),
      });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          loadRoundExecution: () => Promise.resolve(trialExecutionWorkspace()),
          reviseCavityResult,
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    const cavityTable = await screen.findByRole("table", {
      name: "Cavity measurements",
    });
    await user.click(
      within(cavityTable).getByRole("button", { name: "Revise" }),
    );
    await user.clear(screen.getByLabelText("Measured value"));
    await user.type(screen.getByLabelText("Measured value"), "2.52");
    await user.click(screen.getByRole("button", { name: "Review command" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Review immutable Trial quality command",
    });
    await user.type(
      within(dialog).getByLabelText("Reason"),
      "Append the corrected exact measurement",
    );
    await user.click(
      within(dialog).getByRole("button", {
        name: "Append cavity result revision",
      }),
    );

    await waitFor(() => {
      expect(reviseCavityResult).toHaveBeenCalledOnce();
    });
    expect(reviseCavityResult.mock.calls[0]?.[2]).toBe(
      trialQualityIds.cavityResult,
    );
    expect(reviseCavityResult.mock.calls[0]?.[3]).toMatchObject({
      expectedResultVersion: 1,
      expectedRevisionGlobalId: trialQualityIds.cavityResultRevision,
      expectedRevisionSnapshotHash: "9".repeat(64),
      measurements: [{ value: "2.52" }],
      reason: "Append the corrected exact measurement",
    });
  });

  it("continues one Tooling defect with a governed action and exact predecessor", async () => {
    installAuthenticatedSession();
    const user = userEvent.setup();
    const createDefect = vi
      .fn<TrialDataSource["createDefect"]>()
      .mockResolvedValue({
        replayed: false,
        workspace: trialQualityWorkspace(),
      });
    renderWithLocale(
      <LiveTrialPage
        dataSource={dataSource({
          createDefect,
          loadRoundExecution: () => Promise.resolve(trialExecutionWorkspace()),
        })}
        navigate={vi.fn()}
        projectId={trialPlanningIds.project}
      />,
      "en",
      `/projects/${trialPlanningIds.project}/trials`,
    );

    await user.click(
      await screen.findByRole("button", { name: "Continue in Trial" }),
    );
    await user.type(screen.getByLabelText("Location"), "Rib end");
    await user.type(
      screen.getByLabelText("Action detail"),
      "Increase fill pressure and inspect the exact cavity.",
    );
    await user.type(
      screen.getByLabelText("Action responsible member stable ID"),
      trialPlanningIds.member,
    );
    await user.type(
      screen.getByLabelText("Action responsible member version"),
      "1",
    );
    await user.clear(screen.getByLabelText("Due date"));
    await user.type(screen.getByLabelText("Due date"), "2026-08-13");
    await user.click(screen.getByRole("button", { name: "Review command" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Review immutable Trial quality command",
    });
    await user.type(
      within(dialog).getByLabelText("Reason"),
      "Continue the stable Tooling defect into T0",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Record Trial defect" }),
    );

    await waitFor(() => {
      expect(createDefect).toHaveBeenCalledOnce();
    });
    expect(createDefect.mock.calls[0]?.[2]).toMatchObject({
      actions: [
        {
          actionType: "corrective",
          detail: "Increase fill pressure and inspect the exact cavity.",
          dueDate: "2026-08-13",
          globalId: null,
          responsibleMember: {
            globalId: trialPlanningIds.member,
            optimisticVersion: 1,
          },
          state: "planned",
          targetRoundGlobalId: trialPlanningIds.round,
        },
      ],
      defectGlobalId: trialQualityIds.defect,
      expectedDefectVersion: 1,
      expectedPredecessorGlobalId: trialQualityIds.toolingDefectRevision,
      expectedPredecessorKind: "tooling_defect_revision",
      expectedPredecessorSnapshotHash: "5".repeat(64),
      location: "Rib end",
      reason: "Continue the stable Tooling defect into T0",
    });
  });
});
