import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TrialDataSource } from "../../src/api/trial-data-source";
import { NpiTransportError } from "../../src/api/http";
import LiveTrialPage from "../../src/pages/live-trial-page";
import { renderWithLocale } from "../support/render";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";

const sessionCsrfToken = "c".repeat(64);

function dataSource(overrides: Partial<TrialDataSource> = {}): TrialDataSource {
  return {
    createPlan: () => Promise.reject(new Error("not used")),
    createRound: () => Promise.reject(new Error("not used")),
    generateActions: () => Promise.reject(new Error("not used")),
    loadPlan: () => Promise.resolve(trialPlanDetail()),
    loadWorkspace: () => Promise.resolve(trialPlanningWorkspace()),
    revisePlan: () => Promise.reject(new Error("not used")),
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
    expect(screen.getByText("T0")).toBeVisible();
    expect(screen.getByText(trialPlanningIds.workItem)).toBeVisible();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("No booking claim")).toBeVisible();
    expect(screen.getByText("Planned state only")).toBeVisible();
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
});
