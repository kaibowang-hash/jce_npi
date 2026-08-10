import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TrialDataSource } from "../../src/api/trial-data-source";
import { NpiTransportError } from "../../src/api/http";
import LiveTrialPage from "../../src/pages/live-trial-page";
import { renderWithLocale } from "../support/render";
import {
  trialExecutionWorkspace,
  trialInputLock,
} from "../support/trial-execution-fixture";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";

const sessionCsrfToken = "c".repeat(64);

function dataSource(overrides: Partial<TrialDataSource> = {}): TrialDataSource {
  const round = trialPlanDetail().rounds[0];
  if (!round) throw new Error("The Trial page test requires one Round.");
  return {
    appendActualRevision: () => Promise.reject(new Error("not used")),
    appendSampleBatchRevision: () => Promise.reject(new Error("not used")),
    bindEvidence: () => Promise.reject(new Error("not used")),
    createPlan: () => Promise.reject(new Error("not used")),
    createRound: () => Promise.reject(new Error("not used")),
    createSampleBatch: () => Promise.reject(new Error("not used")),
    downloadEvidence: () => Promise.reject(new Error("not used")),
    generateActions: () => Promise.reject(new Error("not used")),
    loadPlan: () => Promise.resolve(trialPlanDetail()),
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
    revisePlan: () => Promise.reject(new Error("not used")),
    startRound: () => Promise.reject(new Error("not used")),
    uploadEvidenceFile: () => Promise.reject(new Error("not used")),
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
    await user.click(screen.getByRole("button", { name: "Review command" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Review immutable Trial execution command",
    });
    await user.type(
      within(dialog).getByLabelText("Reason"),
      "Begin controlled T0 execution",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Start Trial Round" }),
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
});
