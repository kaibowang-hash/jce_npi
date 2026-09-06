import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EngineeringBomDataSource } from "../../src/api/ebom-data-source";
import { NpiApiError } from "../../src/api/http";
import { ProjectEngineeringBomWorkspace } from "../../src/pages/project-ebom-workspace";
import {
  ebomId,
  ebomProjectId,
  ebomRevisionOneId,
  ebomRevisionTwoId,
  engineeringBomCommandFixture,
  engineeringBomComparisonFixture,
  engineeringBomDetailFixture,
  engineeringBomListFixture,
} from "../support/ebom-fixture";
import { renderWithLocale } from "../support/render";

const csrfToken = "ebom-workspace-csrf-token-fixture";
const expectedEngineeringBomBusinessId = "synthetic.ebom.002";

function enableCommandSession(): void {
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
              version: "c".repeat(64),
            },
            csrfToken,
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "engineer@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

function createDataSource(
  overrides: Partial<EngineeringBomDataSource> = {},
): EngineeringBomDataSource {
  return {
    compare: () => Promise.resolve(engineeringBomComparisonFixture()),
    createEbom: () => Promise.resolve(engineeringBomCommandFixture()),
    createRevision: () => Promise.resolve(engineeringBomCommandFixture()),
    loadEbom: () => Promise.resolve(engineeringBomDetailFixture()),
    loadEboms: () => Promise.resolve(engineeringBomListFixture()),
    release: () => Promise.resolve(engineeringBomCommandFixture()),
    review: () => Promise.resolve(engineeringBomCommandFixture()),
    submitReview: () => Promise.resolve(engineeringBomCommandFixture()),
    ...overrides,
  };
}

function renderWorkspace(
  dataSource: EngineeringBomDataSource | undefined,
): void {
  renderWithLocale(
    <ProjectEngineeringBomWorkspace
      dataSource={dataSource}
      projectId={ebomProjectId}
    />,
    "en",
    `/projects/${ebomProjectId}?tab=ebom`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Project EBOM workspace", () => {
  it("renders dense immutable revision, line, lifecycle and ownership truth", async () => {
    renderWorkspace(createDataSource());

    expect(
      await screen.findByRole("heading", { name: "EBOM working revisions" }),
    ).toBeVisible();
    expect(screen.getAllByText("synthetic.ebom.001")[0]).toBeVisible();
    expect(screen.getByText("Synthetic assembly EBOM")).toBeVisible();
    expect(
      await screen.findByRole("heading", { name: "Immutable revisions" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Exact revision lines" }),
    ).toBeVisible();
    const exactLine = screen.getAllByText("ENG-SYN-001")[0]?.closest("tr");
    expect(exactLine).toHaveTextContent("2.000 EA");
    expect(screen.getAllByText("Synthetic EBOM policy")[0]).toBeVisible();
    expect(
      screen.getByText(
        "This workspace does not create formal ERPNext Items, MBOMs, routings or production execution.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Submit for review" }),
    ).toBeDisabled();
  });

  it("compares two explicit revisions and renders typed deterministic differences", async () => {
    const user = userEvent.setup();
    const compare = vi.fn<EngineeringBomDataSource["compare"]>(() =>
      Promise.resolve(engineeringBomComparisonFixture()),
    );
    renderWorkspace(createDataSource({ compare }));

    await screen.findByRole("heading", { name: "Immutable revisions" });
    await user.click(screen.getByRole("button", { name: "Compare revisions" }));
    const comparisonPanel = screen
      .getByRole("heading", { name: "Compare exact EBOM revisions" })
      .closest("section");
    if (!comparisonPanel)
      throw new Error("The comparison panel is unavailable.");
    await user.click(
      within(comparisonPanel).getByRole("button", {
        name: "Compare revisions",
      }),
    );

    expect(await screen.findByText("Differences found")).toBeVisible();
    expect(screen.getAllByText("Quantity changed").length).toBeGreaterThan(0);
    expect(screen.getByText("ENG-SYN-001 · 1.000 EA")).toBeVisible();
    expect(screen.getByText("ENG-SYN-001 · 2.000 EA")).toBeVisible();
    expect(compare).toHaveBeenCalledWith(
      ebomProjectId,
      ebomId,
      ebomRevisionOneId,
      ebomRevisionTwoId,
      expect.any(AbortSignal),
    );
  });

  it("creates the first policy-bound working structure with exact line input and command identity", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const createEbom = vi.fn<EngineeringBomDataSource["createEbom"]>(() =>
      Promise.resolve(engineeringBomCommandFixture()),
    );
    renderWorkspace(createDataSource({ createEbom }));

    const createButton = await screen.findByRole("button", {
      name: "Create EBOM",
    });
    await waitFor(() => {
      expect(createButton).toBeEnabled();
    });
    await user.click(createButton);

    const panel = screen
      .getByRole("heading", { name: "Create EBOM working structure" })
      .closest("section");
    if (!panel) throw new Error("The EBOM create panel is unavailable.");
    const policy = within(panel).getByRole("combobox", {
      name: "Exact EBOM policy",
    });
    await waitFor(() => {
      expect(policy).toHaveFocus();
    });
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);
    await user.type(
      within(panel).getByRole("textbox", { name: "EBOM key" }),
      "synthetic.ebom.002",
    );
    await user.type(
      within(panel).getByRole("textbox", { name: "Title" }),
      "Second synthetic EBOM",
    );
    await user.type(
      within(panel).getByRole("textbox", { name: "Revision reason" }),
      "Initial exact structure",
    );
    await user.type(
      within(panel).getByRole("textbox", { name: "Line 1 key" }),
      "root",
    );
    await user.type(
      within(panel).getByRole("textbox", {
        name: "Line 1 engineering item",
      }),
      "ENG-SYN-002",
    );
    await user.type(
      within(panel).getByRole("textbox", { name: "Line 1 description" }),
      "Synthetic exact assembly",
    );
    await user.selectOptions(
      within(panel).getByRole("combobox", {
        name: "Line 1 engineering UOM",
      }),
      "EA",
    );
    await user.click(
      within(panel).getByRole("button", { name: "Create EBOM" }),
    );

    await waitFor(() => {
      expect(createEbom).toHaveBeenCalledOnce();
    });
    expect(createEbom.mock.calls[0]?.[0]).toBe(ebomProjectId);
    expect(createEbom.mock.calls[0]?.[1]).toMatchObject({
      engineeringBomKey: expectedEngineeringBomBusinessId,
      title: "Second synthetic EBOM",
      reason: "Initial exact structure",
      policyGlobalId: "75000000-0000-4000-8000-000000000005",
      policyVersion: 1,
      lines: [
        expect.objectContaining({
          engineeringItemId: "ENG-SYN-002",
          engineeringUom: "EA",
          lineKey: "root",
          quantity: "1",
        }),
      ],
    });
    expect(createEbom.mock.calls[0]?.[2].csrfToken).toBe(csrfToken);
    expect(createEbom.mock.calls[0]?.[2].idempotencyKey).toMatch(
      /^ebom-create-/u,
    );
  });

  it("submits the exact selected revision with capability, concurrency and session truth", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const submitReview = vi.fn<EngineeringBomDataSource["submitReview"]>(() =>
      Promise.resolve(engineeringBomCommandFixture()),
    );
    renderWorkspace(createDataSource({ submitReview }));

    const submitButton = await screen.findByRole("button", {
      name: "Submit for review",
    });
    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });
    await user.click(submitButton);
    await user.type(screen.getByRole("textbox", { name: "Reason" }), "Ready");
    const panel = screen
      .getByRole("heading", { name: "EBOM lifecycle review" })
      .closest("section");
    if (!panel) throw new Error("The lifecycle panel is unavailable.");
    await user.click(
      within(panel).getByRole("button", { name: "Submit for review" }),
    );

    await waitFor(() => {
      expect(submitReview).toHaveBeenCalledOnce();
    });
    const call = submitReview.mock.calls[0];
    expect(call?.[0]).toBe(ebomProjectId);
    expect(call?.[1]).toBe(ebomId);
    expect(call?.[2]).toBe(ebomRevisionTwoId);
    expect(call?.[3]).toMatchObject({
      expectedEbomVersion: 2,
      expectedLifecycleVersion: 1,
      expectedRevisionSnapshotHash: "c".repeat(64),
      reason: "Ready",
    });
    expect(call?.[4].csrfToken).toBe(csrfToken);
    expect(call?.[4].idempotencyKey).toMatch(/^ebom-submit-/u);
  });

  it("reuses one actor-bound idempotency key when a retryable command is retried", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const failure = new NpiApiError({
      type: "https://example.invalid/problems/temporarily-unavailable",
      title: "Temporarily unavailable",
      status: 503,
      code: "EBOM_COMMAND_TEMPORARILY_UNAVAILABLE",
      traceId: "trace-ebom-command-retry",
      retryable: true,
    });
    const submitReview = vi
      .fn<EngineeringBomDataSource["submitReview"]>()
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(engineeringBomCommandFixture());
    renderWorkspace(createDataSource({ submitReview }));

    const submitButton = await screen.findByRole("button", {
      name: "Submit for review",
    });
    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });
    await user.click(submitButton);
    const lifecyclePanel = screen
      .getByRole("heading", { name: "EBOM lifecycle review" })
      .closest("section");
    if (!lifecyclePanel) throw new Error("The lifecycle panel is unavailable.");
    await user.click(
      within(lifecyclePanel).getByRole("button", {
        name: "Submit for review",
      }),
    );

    expect(await screen.findByText("Temporarily unavailable")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(submitReview).toHaveBeenCalledTimes(2);
    });
    expect(submitReview.mock.calls[0]?.[4].idempotencyKey).toBe(
      submitReview.mock.calls[1]?.[4].idempotencyKey,
    );
  });

  it("requires explicit release confirmation and preserves the no-ERP boundary", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const detail = engineeringBomDetailFixture();
    const approved = detail.revisions[0];
    if (!approved)
      throw new Error("The approved revision fixture is unavailable.");
    const release = vi.fn<EngineeringBomDataSource["release"]>(() =>
      Promise.resolve(engineeringBomCommandFixture()),
    );
    const approvedDetail = {
      ...detail,
      revisions: [
        {
          ...approved,
          lifecycle: {
            state: "approved" as const,
            version: 1,
            lastEventId: null,
          },
          capabilities: {
            ...approved.capabilities,
            revise: false,
            submitReview: false,
            review: false,
            release: true,
          },
        },
        ...detail.revisions.slice(1),
      ],
    };
    renderWorkspace(
      createDataSource({
        loadEbom: () => Promise.resolve(approvedDetail),
        release,
      }),
    );

    const releaseButton = await screen.findByRole("button", {
      name: "Release revision",
    });
    await waitFor(() => {
      expect(releaseButton).toBeEnabled();
    });
    await user.click(releaseButton);
    const confirm = screen.getByRole("checkbox", {
      name: "I confirm release of this exact immutable EBOM revision. No ERPNext execution will occur.",
    });
    const lifecyclePanel = screen
      .getByRole("heading", { name: "EBOM lifecycle review" })
      .closest("section");
    if (!lifecyclePanel) throw new Error("The release panel is unavailable.");
    await user.click(
      within(lifecyclePanel).getByRole("button", {
        name: "Release exact revision",
      }),
    );
    expect(
      await screen.findByText(
        "Confirm the exact EBOM revision before release.",
      ),
    ).toBeVisible();
    expect(release).not.toHaveBeenCalled();
    await user.click(confirm);
    await user.click(
      within(lifecyclePanel).getByRole("button", {
        name: "Release exact revision",
      }),
    );
    await waitFor(() => {
      expect(release).toHaveBeenCalledOnce();
    });
    expect(release.mock.calls[0]?.[3]).toMatchObject({
      confirmed: true,
      confirmationIntent: "release_exact_ebom_revision",
    });
  });

  it("renders empty, read-only, unavailable-policy and protected failure states", async () => {
    const empty = engineeringBomListFixture();
    const { unmount } = renderWithLocale(
      <ProjectEngineeringBomWorkspace
        dataSource={createDataSource({
          loadEboms: () =>
            Promise.resolve({
              ...empty,
              permissions: { view: true, create: false },
              policies: [],
              items: [],
            }),
        })}
        projectId={ebomProjectId}
      />,
      "en",
      `/projects/${ebomProjectId}?tab=ebom`,
    );
    expect(await screen.findByText("No EBOM working structure")).toBeVisible();
    expect(screen.getByText("Read only")).toBeVisible();
    expect(
      screen.getByText(
        "EBOM creation is unavailable because no accepted synthetic EBOM policy is published.",
      ),
    ).toBeVisible();
    expect(
      screen
        .getAllByRole("button", { name: "Create EBOM" })
        .every((button) => button.hasAttribute("disabled")),
    ).toBe(true);
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(0);
    unmount();

    const failure = new NpiApiError({
      type: "https://example.invalid/problems/not-found",
      title: "Not found",
      status: 404,
      code: "ENGINEERING_BOM_UNAVAILABLE",
      traceId: "trace-ebom-protected",
      retryable: false,
    });
    renderWorkspace(
      createDataSource({ loadEboms: () => Promise.reject(failure) }),
    );
    expect(await screen.findByText("Not found")).toBeVisible();
    expect(screen.getByText("trace-ebom-protected")).toBeVisible();
  });

  it("fails closed when the live EBOM adapter is absent", () => {
    renderWorkspace(undefined);
    expect(
      screen.getByText("The live EBOM data source is not configured."),
    ).toBeVisible();
  });
});
