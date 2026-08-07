import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ToolingCockpitViewModel,
  ToolingDataSource,
} from "../../src/api/tooling-data-source";
import { NpiTransportError } from "../../src/api/http";
import LiveToolingPage from "../../src/pages/live-tooling-page";
import { renderWithLocale } from "../support/render";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const partId = "33333333-3333-4333-8333-333333333333";
const revisionId = "44444444-4444-4444-8444-444444444444";

function cockpit(
  overrides: Partial<ToolingCockpitViewModel> = {},
): ToolingCockpitViewModel {
  return {
    applicability: [
      {
        effectiveFrom: "2026-08-07",
        effectiveTo: null,
        globalId: "66666666-6666-4666-8666-666666666666",
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
        relationshipGlobalId: "77777777-7777-4777-8777-777777777777",
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
        source: {
          editableIn: "NPI_ONE",
          sourceSystem: "NPI_ONE",
          syncState: "local",
        },
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
        source: {
          editableIn: "NPI_ONE",
          sourceSystem: "NPI_ONE",
          syncState: "local",
        },
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
    requirements: [],
    ...overrides,
  };
}

function dataSource(
  overrides: Partial<ToolingDataSource> = {},
): ToolingDataSource {
  const value = cockpit();
  return {
    attachIntakeEvidence: () => Promise.reject(new Error("not used")),
    createApplicability: () => Promise.resolve(value),
    createIntake: () => Promise.reject(new Error("not used")),
    createMaster: () => Promise.resolve(value),
    createPart: () => Promise.resolve(value),
    createPartRevision: () => Promise.resolve(value),
    createRequirement: () => Promise.resolve(value),
    createSet: () => Promise.reject(new Error("not used")),
    loadCockpit: () => Promise.resolve(value),
    loadMaster: () => Promise.resolve(value),
    loadSet: () => Promise.reject(new Error("not used")),
    loadSets: () =>
      Promise.resolve({
        items: [],
        permissions: {
          attachEvidence: false,
          createIntake: false,
          createSet: false,
          transitionLifecycle: false,
          view: true,
        },
        toolingMasterGlobalId: masterId,
      }),
    ...overrides,
  };
}

function enableCommandSession(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: { language: "en", messages: {}, version: "a".repeat(64) },
            csrfToken: "tooling-workspace-csrf-token-value",
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

function renderPage(
  source: ToolingDataSource,
  reportWorkspaceDirty = vi.fn(),
): void {
  renderWithLocale(
    <LiveToolingPage
      dataSource={source}
      masterId={null}
      navigate={vi.fn()}
      projectId={projectId}
      reportWorkspaceDirty={reportWorkspaceDirty}
    />,
    "en",
    `/projects/${projectId}/tooling`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("live Tooling cockpit", () => {
  it("renders dense distinct identity, applicability and unavailable downstream truth", async () => {
    renderPage(dataSource());

    expect(
      await screen.findByRole("heading", {
        name: /SYN-PROJECT-001 Synthetic Project/u,
      }),
    ).toBeVisible();
    expect(screen.getAllByText("Synthetic logical tool")[0]).toBeVisible();
    expect(screen.getAllByText("Synthetic engineering part")[0]).toBeVisible();
    expect(
      screen.getByText("Project and exact Part Revision only"),
    ).toBeVisible();
    expect(screen.getAllByText("Unavailable")).toHaveLength(4);
    expect(
      screen.getByText(
        "No lifecycle, Tooling Revision, Trial or ERPNext success is inferred by this workspace.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Add Tooling record" }),
    ).toBeDisabled();
  });

  it("uses capability-driven operations and submits an exact Master command", async () => {
    enableCommandSession();
    const createMaster = vi.fn<ToolingDataSource["createMaster"]>(() =>
      Promise.resolve(cockpit()),
    );
    const reportWorkspaceDirty = vi.fn();
    renderPage(dataSource({ createMaster }), reportWorkspaceDirty);
    const user = userEvent.setup();

    const add = await screen.findByRole("button", {
      name: "Add Tooling record",
    });
    await waitFor(() => {
      expect(add).toBeEnabled();
    });
    await user.click(add);
    await user.selectOptions(screen.getByLabelText("Command"), "master");
    await user.type(screen.getByLabelText("Title"), "New logical tool");
    expect(reportWorkspaceDirty).toHaveBeenLastCalledWith(
      expect.objectContaining({ version: "unsaved-tooling-context" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Create logical Tooling Master" }),
    );

    await waitFor(() => {
      expect(createMaster).toHaveBeenCalledOnce();
    });
    expect(createMaster.mock.calls[0]?.[0]).toBe(projectId);
    expect(createMaster.mock.calls[0]?.[1]).toEqual({
      title: "New logical tool",
    });
    expect(createMaster.mock.calls[0]?.[2].csrfToken).toBe(
      "tooling-workspace-csrf-token-value",
    );
    expect(createMaster.mock.calls[0]?.[2].idempotencyKey).toMatch(
      /^tooling-master-/u,
    );
  });

  it("retries the exact command with one idempotency key and a fresh signal", async () => {
    enableCommandSession();
    const createMaster = vi
      .fn<ToolingDataSource["createMaster"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "trace-tooling-network", "trace"),
      )
      .mockResolvedValueOnce(cockpit());
    renderPage(dataSource({ createMaster }));
    const user = userEvent.setup();

    const add = await screen.findByRole("button", {
      name: "Add Tooling record",
    });
    await waitFor(() => {
      expect(add).toBeEnabled();
    });
    await user.click(add);
    await user.selectOptions(screen.getByLabelText("Command"), "master");
    await user.type(screen.getByLabelText("Title"), "Retry logical tool");
    await user.click(
      screen.getByRole("button", { name: "Create logical Tooling Master" }),
    );

    const retry = await screen.findByRole("button", {
      name: "Retry exact command",
    });
    const firstContext = createMaster.mock.calls[0]?.[2];
    expect(firstContext).toBeDefined();
    await user.click(retry);
    await waitFor(() => {
      expect(createMaster).toHaveBeenCalledTimes(2);
    });
    const secondContext = createMaster.mock.calls[1]?.[2];
    expect(secondContext?.idempotencyKey).toBe(firstContext?.idempotencyKey);
    expect(secondContext?.csrfToken).toBe(firstContext?.csrfToken);
    expect(secondContext?.signal).not.toBe(firstContext?.signal);
  });

  it("renders an explicit empty state without creating downstream success", async () => {
    const empty = cockpit({
      applicability: [],
      masters: [],
      parts: [],
      requirements: [],
    });
    renderPage(dataSource({ loadCockpit: () => Promise.resolve(empty) }));

    expect(
      await screen.findByText(
        "No Tooling identity has been recorded for this Project.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Add Tooling record" }),
    ).toBeDisabled();
    expect(screen.getAllByText("Unavailable")).toHaveLength(4);
  });
});
