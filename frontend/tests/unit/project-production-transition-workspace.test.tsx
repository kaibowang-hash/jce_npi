import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ProductionTransitionAcknowledgementCommandResult,
  ProductionTransitionDataSource,
  ProductionTransitionWorkspace,
} from "../../src/api/production-transition-data-source";
import {
  NpiApiError,
  NpiTransportError,
  type ProblemDetails,
} from "../../src/api/http";
import { ProjectProductionTransitionWorkspace } from "../../src/pages/project-production-transition-workspace";
import {
  productionTransitionAcknowledgedWorkspace,
  productionTransitionAcknowledgementResult,
  productionTransitionEmptyWorkspace,
  productionTransitionIds,
  productionTransitionUsers,
  productionTransitionWorkspace,
} from "../support/production-transition-fixture";
import { renderWithLocale } from "../support/render";

const csrfToken = "production-transition-csrf-token-fixture-0001";

async function fixtureWorkspace(): Promise<ProductionTransitionWorkspace> {
  return Promise.resolve(productionTransitionWorkspace());
}

async function acknowledgedWorkspace(): Promise<ProductionTransitionWorkspace> {
  return Promise.resolve(productionTransitionAcknowledgedWorkspace());
}

async function emptyWorkspace(): Promise<ProductionTransitionWorkspace> {
  return Promise.resolve(productionTransitionEmptyWorkspace());
}

async function sharedActorMultiSlotWorkspace(): Promise<ProductionTransitionWorkspace> {
  const value = await fixtureWorkspace();
  const current = value.currentHandover;
  if (!current) throw new Error("The fixture requires a current handover.");
  const sharedActorCurrent = {
    ...current,
    acknowledgements: [],
    fullyAcknowledged: false,
    revision: {
      ...current.revision,
      slots: current.revision.slots.map((slot) => ({
        ...slot,
        member: {
          ...slot.member,
          userId: productionTransitionUsers.receiver,
        },
      })),
    },
  };
  return {
    ...value,
    currentHandover: sharedActorCurrent,
    handoverHistory: value.handoverHistory.map((entry) =>
      entry.revision.globalId === current.revision.globalId
        ? sharedActorCurrent
        : entry,
    ),
    permissions: {
      ...value.permissions,
      canAcknowledgeSlots: ["sender", "receiver"],
    },
  };
}

async function acknowledgementResult(
  replayed = false,
): Promise<ProductionTransitionAcknowledgementCommandResult> {
  return Promise.resolve(productionTransitionAcknowledgementResult(replayed));
}

async function createDataSource(
  overrides: Partial<ProductionTransitionDataSource> = {},
  workspaceValue?: ProductionTransitionWorkspace,
): Promise<ProductionTransitionDataSource> {
  const value = workspaceValue ?? (await fixtureWorkspace());
  return {
    acknowledgeSlot: () => acknowledgementResult(),
    loadWorkspace: () => Promise.resolve(value),
    ...overrides,
  };
}

function enableCommandSession(
  userId: string = productionTransitionUsers.receiver,
): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: {
              language: "en",
              messages: {},
              version: "4".repeat(64),
            },
            csrfToken,
            language: "en",
            preferences: { navigationCollapsed: false },
            userId,
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

function problem(
  status: number,
  code: string,
  options: { retryable?: boolean } = {},
): NpiApiError {
  const value: ProblemDetails = {
    code,
    retryable: options.retryable ?? false,
    status,
    title: `Controlled ${code} response`,
    traceId: `trace-${code.toLowerCase()}`,
    type: `/problems/${code.toLowerCase()}`,
  };
  return new NpiApiError(value);
}

function renderWorkspace(dataSource: ProductionTransitionDataSource): void {
  renderWithLocale(
    <ProjectProductionTransitionWorkspace
      dataSource={dataSource}
      projectId={productionTransitionIds.project}
    />,
    "en",
    `/projects/${productionTransitionIds.project}?tab=production-transition`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  globalThis.localStorage.clear();
});

describe("Project production transition workspace", () => {
  it("keeps protected transition facts hidden while the workspace is loading", () => {
    renderWorkspace({
      acknowledgeSlot: () => acknowledgementResult(),
      loadWorkspace: () =>
        new Promise<ProductionTransitionWorkspace>(() => undefined),
    });

    expect(screen.getByTestId("production-transition-loading")).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(screen.queryByText("receiver")).not.toBeInTheDocument();
  });

  it("renders immutable handover history, frozen groups, manifest, and unresolved truth", async () => {
    const user = userEvent.setup();
    renderWorkspace(await createDataSource());

    expect(
      await screen.findByRole("heading", { name: "Handover history" }),
    ).toBeVisible();
    expect(screen.getByTestId("handover-history-2")).toHaveTextContent(
      "Current package",
    );
    expect(screen.getByTestId("handover-history-1")).toHaveTextContent(
      "Superseded package",
    );
    expect(screen.getByTestId("handover-slot-receiver")).toBeVisible();
    expect(
      screen.getByTestId(
        "manifest-readiness_snapshot-readiness_instance_revision",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "Unresolved actions at package freeze",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(productionTransitionIds.unresolvedRisk),
    ).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: "Frozen receiving groups and acknowledgement slots",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Frozen handover manifest" }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: "Unresolved actions at package freeze",
      }),
    ).toBeVisible();
    expect(
      document.querySelector(
        ".production-transition-workspace__summary > .panel__body",
      ),
    ).toHaveAttribute("tabindex", "0");
    await user.click(
      screen.getByRole("button", {
        name: productionTransitionIds.unresolvedAction,
      }),
    );
    const inspector = within(
      screen.getByTestId("production-transition-inspector"),
    );
    expect(inspector.getByText("Retained state key")).toBeVisible();
    expect(inspector.getByText("Open")).toBeVisible();
    expect(inspector.getByText("open")).toHaveAttribute(
      "data-language-exempt",
      "identifier",
    );
    expect(screen.getAllByText(/does not close G7/u).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/It is not a signature, approval/u).length,
    ).toBeGreaterThan(0);
  });

  it("switches to the independent observation view with exactly five unavailable providers", async () => {
    const user = userEvent.setup();
    renderWorkspace(await createDataSource());

    await user.click(
      await screen.findByTestId("production-transition-observation-tab"),
    );

    expect(screen.getByText("Observation history")).toBeVisible();
    expect(screen.getAllByText("Not evaluable").length).toBeGreaterThan(0);
    const providers = screen.getByTestId("production-transition-providers");
    expect(within(providers).getAllByText("Unavailable")).toHaveLength(5);
    expect(screen.getByTestId("provider-actual_sop")).toHaveTextContent(
      "Actual SOP",
    );
    expect(screen.getByTestId("provider-tooling_stability")).toHaveTextContent(
      "Tooling stability",
    );
    expect(screen.getByText("Review context")).toBeVisible();
    expect(screen.getByText("Retrospective evidence")).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Mandatory external providers" }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Exact observation references" }),
    ).toBeVisible();
    expect(screen.getByText(/No observed window, zero value/u)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /create|revise/iu }),
    ).toBeNull();
  });

  it("implements one keyboard-operated tab stop with exact tabpanel labelling", async () => {
    const user = userEvent.setup();
    renderWorkspace(await createDataSource());

    const handoverTab = await screen.findByTestId(
      "production-transition-handover-tab",
    );
    const observationTab = screen.getByTestId(
      "production-transition-observation-tab",
    );
    expect(handoverTab).toHaveAttribute(
      "id",
      "production-transition-handover-tab",
    );
    expect(handoverTab).toHaveAttribute("tabindex", "0");
    expect(observationTab).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "production-transition-handover-tab",
    );

    handoverTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(observationTab).toHaveAttribute("aria-selected", "true");
    expect(observationTab).toHaveAttribute("tabindex", "0");
    expect(observationTab).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "production-transition-observation-tab",
    );

    await user.keyboard("{Home}");
    expect(handoverTab).toHaveAttribute("aria-selected", "true");
    expect(handoverTab).toHaveFocus();
  });

  it("renders the honest empty state without exposing create or revise transport", async () => {
    const user = userEvent.setup();
    const value = await emptyWorkspace();
    renderWorkspace(await createDataSource({}, value));

    expect(
      await screen.findByTestId("production-transition-empty"),
    ).toHaveTextContent("No production transition history");
    expect(
      screen.queryByRole("button", { name: /create|revise/iu }),
    ).toBeNull();
    await user.click(
      screen.getByTestId("production-transition-observation-tab"),
    );
    expect(screen.getByTestId("production-transition-providers")).toBeVisible();
  });

  it("fails closed when protected workspace access is denied", async () => {
    renderWorkspace(
      await createDataSource({
        loadWorkspace: () =>
          Promise.reject(problem(403, "PRODUCTION_TRANSITION_FORBIDDEN")),
      }),
    );

    expect(await screen.findByText("No permission")).toBeVisible();
    expect(
      screen.getByText(
        "No protected production transition data was displayed.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("quality.receiver@example.invalid")).toBeNull();
  });

  it("keeps the acknowledgement read only until the authenticated session is verified", async () => {
    renderWorkspace(await createDataSource());

    expect(
      await screen.findByText(
        "Session verification is required before an acknowledgement can be prepared.",
      ),
    ).toBeVisible();
    expect(screen.queryByTestId("acknowledge-exact-slot")).toBeNull();
  });

  it("offers the only primary action for one exact current actor slot and appends it after review", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const initial = await fixtureWorkspace();
    const updated = await acknowledgedWorkspace();
    const acknowledgeSlot = vi.fn<
      ProductionTransitionDataSource["acknowledgeSlot"]
    >(() => acknowledgementResult());
    let loadCount = 0;
    const loadWorkspace = vi.fn<
      ProductionTransitionDataSource["loadWorkspace"]
    >(() => Promise.resolve(loadCount++ === 0 ? initial : updated));
    renderWorkspace(
      await createDataSource({ acknowledgeSlot, loadWorkspace }, initial),
    );

    const action = await screen.findByTestId("acknowledge-exact-slot");
    expect(action).toHaveTextContent("Acknowledge exact slot");
    expect(
      screen.getByTestId("handover-slot-receiver").closest("tr"),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByTestId("handover-slot-sender").closest("tr"),
    ).toHaveAttribute("aria-selected", "false");
    const selectedExactFact = screen
      .getByRole("heading", { name: "Selected exact fact" })
      .closest("section");
    if (!selectedExactFact)
      throw new Error("The selected exact fact inspector is missing.");
    expect(within(selectedExactFact).getByText("receiver")).toBeVisible();
    expect(
      screen.getAllByText(productionTransitionUsers.receiver).length,
    ).toBeGreaterThan(0);
    await user.click(action);

    expect(
      screen.getByRole("heading", { name: "Review exact acknowledgement" }),
    ).toBeVisible();
    expect(screen.getByText(/cannot be overwritten or copied/u)).toBeVisible();
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Acknowledge exact slot",
      }),
    );

    await waitFor(() => {
      expect(acknowledgeSlot).toHaveBeenCalledTimes(1);
    });
    const acknowledgementCall = acknowledgeSlot.mock.calls[0];
    expect(acknowledgementCall?.slice(0, 4)).toEqual([
      productionTransitionIds.project,
      productionTransitionIds.handover,
      2,
      {
        expectedRevisionGlobalId:
          productionTransitionIds.currentHandoverRevision,
        expectedSnapshotHash: initial.currentHandover?.revision.snapshotHash,
        intent: "acknowledge",
        slotKey: "receiver",
      },
    ]);
    expect(acknowledgementCall?.[4].csrfToken).toBe(csrfToken);
    expect(acknowledgementCall?.[4].idempotencyKey).toMatch(
      /^production-handover-ack-/u,
    );
    expect(
      await screen.findByTestId("acknowledgement-succeeded"),
    ).toHaveTextContent("Acknowledgement retained");
    expect(screen.getAllByText("Fully acknowledged").length).toBeGreaterThan(0);
  });

  it("shows processing truth and prevents duplicate submission while the append is pending", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    let resolveAcknowledgement:
      | ((value: ProductionTransitionAcknowledgementCommandResult) => void)
      | undefined;
    const pending =
      new Promise<ProductionTransitionAcknowledgementCommandResult>(
        (resolve) => {
          resolveAcknowledgement = resolve;
        },
      );
    const dataSource = await createDataSource({
      acknowledgeSlot: () => pending,
    });
    renderWorkspace(dataSource);

    await user.click(await screen.findByTestId("acknowledge-exact-slot"));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Acknowledge exact slot",
      }),
    );

    expect(
      await screen.findByTestId("acknowledgement-processing"),
    ).toHaveTextContent("Do not submit it again");
    expect(screen.getByTestId("acknowledge-exact-slot")).toBeDisabled();
    expect(screen.getByTestId("handover-history-1")).toBeDisabled();
    expect(screen.getByTestId("handover-history-2")).toBeDisabled();
    await user.click(screen.getByTestId("handover-history-1"));
    expect(screen.getByTestId("handover-history-2")).toHaveAttribute(
      "aria-current",
      "page",
    );
    resolveAcknowledgement?.(await acknowledgementResult());
    await screen.findByTestId("acknowledgement-succeeded");
  });

  it("uses a same-key retry for a retryable acknowledgement failure", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const initial = await fixtureWorkspace();
    const updated = await acknowledgedWorkspace();
    const acknowledgeSlot = vi
      .fn<ProductionTransitionDataSource["acknowledgeSlot"]>()
      .mockRejectedValueOnce(
        new NpiTransportError(
          "network",
          "request-production-transition-1",
          "request",
        ),
      )
      .mockResolvedValueOnce(await acknowledgementResult(true));
    let loadCount = 0;
    const loadWorkspace = vi.fn<
      ProductionTransitionDataSource["loadWorkspace"]
    >(() => Promise.resolve(loadCount++ === 0 ? initial : updated));
    renderWorkspace(
      await createDataSource({ acknowledgeSlot, loadWorkspace }, initial),
    );

    await user.click(await screen.findByTestId("acknowledge-exact-slot"));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Acknowledge exact slot",
      }),
    );
    await screen.findByTestId("acknowledgement-failed");
    expect(screen.getByTestId("handover-history-1")).toBeDisabled();
    const firstContext = acknowledgeSlot.mock.calls[0]?.[4];

    await user.click(
      screen.getByRole("button", { name: "Retry exact acknowledgement" }),
    );
    expect(
      await screen.findByTestId("acknowledgement-succeeded"),
    ).toHaveTextContent("replayed safely");
    expect(acknowledgeSlot.mock.calls[1]?.[4].idempotencyKey).toBe(
      firstContext?.idempotencyKey,
    );
  });

  it("requires reload instead of same-command retry after a version conflict", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const acknowledgeSlot = vi.fn<
      ProductionTransitionDataSource["acknowledgeSlot"]
    >(() => Promise.reject(problem(409, "PRODUCTION_TRANSITION_CONFLICT")));
    renderWorkspace(await createDataSource({ acknowledgeSlot }));

    await user.click(await screen.findByTestId("acknowledge-exact-slot"));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Acknowledge exact slot",
      }),
    );

    expect(
      await screen.findByTestId("acknowledgement-failed"),
    ).toHaveTextContent("Conflict");
    expect(
      screen.getByRole("button", { name: "Reload current package" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry exact acknowledgement" }),
    ).toBeNull();
    expect(screen.getByTestId("handover-history-1")).toBeDisabled();
    expect(screen.queryByTestId("acknowledge-exact-slot")).toBeNull();
  });

  it("does not claim confirmed current state when refresh fails after an accepted response", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const initial = await fixtureWorkspace();
    const loadWorkspace = vi
      .fn<ProductionTransitionDataSource["loadWorkspace"]>()
      .mockResolvedValueOnce(initial)
      .mockRejectedValueOnce(
        new NpiTransportError(
          "network",
          "request-production-transition-refresh",
          "request",
        ),
      );
    renderWorkspace(
      await createDataSource(
        {
          acknowledgeSlot: () => acknowledgementResult(),
          loadWorkspace,
        },
        initial,
      ),
    );

    await user.click(await screen.findByTestId("acknowledge-exact-slot"));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Acknowledge exact slot",
      }),
    );

    expect(
      await screen.findByTestId("acknowledgement-refresh-failed"),
    ).toHaveTextContent("Reload before making another decision");
    expect(
      screen.getByRole("button", { name: "Reload current data" }),
    ).toBeVisible();
    expect(screen.getByTestId("handover-history-1")).toBeDisabled();
    expect(screen.queryByTestId("acknowledge-exact-slot")).toBeNull();
  });

  it("fails closed when a permission slot does not bind to the current actor", async () => {
    enableCommandSession();
    const value = await fixtureWorkspace();
    const inconsistent: ProductionTransitionWorkspace = {
      ...value,
      permissions: {
        ...value.permissions,
        canAcknowledgeSlots: ["sender", "receiver"],
      },
    };
    renderWorkspace(await createDataSource({}, inconsistent));

    expect(
      await screen.findByText(
        "The acknowledgement permission does not match the current actor and frozen slot.",
      ),
    ).toBeVisible();
    expect(screen.queryByTestId("acknowledgement-slot-selector")).toBeNull();
    expect(screen.queryByTestId("acknowledge-exact-slot")).toBeNull();
  });

  it("requires an exact multi-slot choice and locks that choice to the command", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const value = await sharedActorMultiSlotWorkspace();
    let resolveAcknowledgement:
      | ((value: ProductionTransitionAcknowledgementCommandResult) => void)
      | undefined;
    const pending =
      new Promise<ProductionTransitionAcknowledgementCommandResult>(
        (resolve) => {
          resolveAcknowledgement = resolve;
        },
      );
    const acknowledgeSlot = vi.fn<
      ProductionTransitionDataSource["acknowledgeSlot"]
    >(() => pending);
    renderWorkspace(await createDataSource({ acknowledgeSlot }, value));

    const selector = await screen.findByTestId("acknowledgement-slot-selector");
    expect(selector).toHaveValue("");
    expect(selector).not.toBeDisabled();
    expect(screen.queryByTestId("acknowledge-exact-slot")).toBeNull();
    expect(
      screen.getByText("Select one exact eligible slot before acknowledging."),
    ).toBeVisible();

    selector.focus();
    expect(selector).toHaveFocus();
    await user.selectOptions(selector, "sender");
    expect(selector).toHaveValue("sender");
    expect(
      screen.getByTestId("handover-slot-sender").closest("tr"),
    ).toHaveAttribute("aria-selected", "true");
    const selectedExactFact = screen
      .getByRole("heading", { name: "Selected exact fact" })
      .closest("section");
    if (!selectedExactFact)
      throw new Error("The selected exact fact inspector is missing.");
    expect(within(selectedExactFact).getByText("sender")).toBeVisible();

    await user.click(screen.getByTestId("acknowledge-exact-slot"));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Acknowledge exact slot",
      }),
    );
    await waitFor(() => {
      expect(acknowledgeSlot).toHaveBeenCalledTimes(1);
    });
    expect(acknowledgeSlot.mock.calls[0]?.slice(0, 4)).toEqual([
      productionTransitionIds.project,
      productionTransitionIds.handover,
      2,
      {
        expectedRevisionGlobalId:
          productionTransitionIds.currentHandoverRevision,
        expectedSnapshotHash: value.currentHandover?.revision.snapshotHash,
        intent: "acknowledge",
        slotKey: "sender",
      },
    ]);
    expect(selector).toBeDisabled();
    expect(screen.getByTestId("handover-history-1")).toBeDisabled();
    expect(screen.getByTestId("handover-slot-receiver")).toBeDisabled();

    resolveAcknowledgement?.(await acknowledgementResult());
    await screen.findByTestId("acknowledgement-succeeded");
  });

  it("keeps a superseded package read only and does not inherit current eligibility", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    renderWorkspace(await createDataSource());

    await user.click(await screen.findByTestId("handover-history-1"));

    expect(screen.getAllByText("Superseded package").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("acknowledge-exact-slot")).toBeNull();
  });

  it("paginates the bounded unresolved action table on the client", async () => {
    const value = await fixtureWorkspace();
    const current = value.currentHandover;
    if (!current) throw new Error("The fixture requires a current handover.");
    const seed = current.revision.unresolvedActions[0];
    if (!seed) throw new Error("The fixture requires one unresolved action.");
    const unresolvedActions = Array.from({ length: 26 }, (_, index) => ({
      ...seed,
      globalId: `88000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
      snapshotHash: `${(index % 10).toString()}${"a".repeat(63)}`,
      sourceVersion: index + 1,
    }));
    const revisedCurrent = {
      ...current,
      revision: { ...current.revision, unresolvedActions },
    };
    const historical = value.handoverHistory[0];
    if (!historical) throw new Error("The fixture requires handover history.");
    const paginated: ProductionTransitionWorkspace = {
      ...value,
      currentHandover: revisedCurrent,
      handoverHistory: [historical, revisedCurrent],
    };
    const finalUnresolved = unresolvedActions.at(-1);
    if (!finalUnresolved) throw new Error("The pagination fixture is empty.");
    const user = userEvent.setup();
    renderWorkspace(await createDataSource({}, paginated));

    expect(await screen.findByText("Page 1 of 2")).toBeVisible();
    expect(screen.queryByText(finalUnresolved.globalId)).toBeNull();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByText("Page 2 of 2")).toBeVisible();
    expect(screen.getByText(finalUnresolved.globalId)).toBeVisible();
  });
});
