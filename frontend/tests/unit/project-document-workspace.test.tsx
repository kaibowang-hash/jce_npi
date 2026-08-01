import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ControlledDocumentPageViewModel,
  ControlledDocumentWorkspaceViewModel,
  DocumentDataSource,
} from "../../src/api/document-data-source";
import type {
  ReportWorkspaceDirty,
  RequestWorkspaceTransition,
} from "../../src/app/workspace-navigation";
import { ProjectDocumentWorkspace } from "../../src/pages/project-document-workspace";
import {
  baselinePolicyId,
  controlledDocumentPageFixture,
  controlledDocumentReleasedWorkspaceFixture,
  controlledDocumentWorkspaceFixture,
  documentBaselineCommandFixture,
  documentBaselineWorkspaceFixture,
  documentFileCapabilityFixture,
  documentProjectId,
  documentReleaseTransitionFixture,
} from "../support/document-fixture";
import { renderWithLocale } from "../support/render";

const csrfToken = "document-workspace-csrf-token-fixture-0001";

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
            userId: "administrator@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

function createDataSource(
  overrides: Partial<DocumentDataSource> = {},
): DocumentDataSource {
  const workspace = controlledDocumentWorkspaceFixture();
  return {
    checkIn: () => Promise.resolve(workspace),
    checkOut: () => Promise.resolve(workspace),
    createBaseline: () => Promise.resolve(documentBaselineCommandFixture()),
    createDocument: () => Promise.resolve(workspace),
    createRevision: () => Promise.resolve(workspace),
    loadCapabilities: () => Promise.resolve(documentFileCapabilityFixture()),
    loadContent: () =>
      Promise.resolve(new Blob(["%PDF"], { type: "application/pdf" })),
    loadBaselines: () => Promise.resolve(documentBaselineWorkspaceFixture()),
    loadDocument: () => Promise.resolve(workspace),
    loadDocuments: () => Promise.resolve(controlledDocumentPageFixture()),
    obsoleteRevision: () => Promise.reject(new Error("not configured")),
    confirmReview: () => Promise.reject(new Error("not configured")),
    releaseRevision: () => Promise.reject(new Error("not configured")),
    recoverLock: () => Promise.resolve(workspace),
    resubmitReview: () => Promise.reject(new Error("not configured")),
    submitReview: () => Promise.reject(new Error("not configured")),
    supersedeRevision: () => Promise.reject(new Error("not configured")),
    ...overrides,
  };
}

function renderWorkspace(
  dataSource: DocumentDataSource | undefined,
  options: {
    reportWorkspaceDirty?: ReportWorkspaceDirty;
    requestWorkspaceTransition?: RequestWorkspaceTransition;
  } = {},
): void {
  renderWithLocale(
    <ProjectDocumentWorkspace
      dataSource={dataSource}
      projectId={documentProjectId}
      reportWorkspaceDirty={options.reportWorkspaceDirty}
      requestWorkspaceTransition={options.requestWorkspaceTransition}
    />,
    "en",
    `/projects/${documentProjectId}?tab=documents`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Project controlled document workspace", () => {
  it("renders dense identity, revision, file, lock, and provider truth", async () => {
    renderWorkspace(createDataSource());

    expect(
      await screen.findByRole("heading", { name: "Design and documents" }),
    ).toBeVisible();
    expect(screen.getAllByText("DRW-000071")[0]).toBeVisible();
    expect(screen.getAllByText("Synthetic cavity drawing")[0]).toBeVisible();
    expect(
      await screen.findByRole("heading", {
        name: "Immutable revision history",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Exact private files" }),
    ).toBeVisible();
    expect(screen.getByText("synthetic-drawing.pdf")).toBeVisible();
    expect(
      within(
        screen
          .getByRole("heading", { name: "Exact private files" })
          .closest("section") ?? document.body,
      ).getByText(/^SHA-256 a{64}$/u),
    ).toBeVisible();
    expect(screen.getAllByText("Clean")[0]).toBeVisible();
    expect(
      within(
        screen
          .getByRole("heading", { name: "Provider boundaries" })
          .closest("section") ?? document.body,
      ).getAllByText("Unavailable").length,
    ).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("No outbound request was made")).toBeVisible();
    expect(
      screen.queryByText("/private/files/synthetic-drawing.pdf"),
    ).not.toBeInTheDocument();
  });

  it("reports real form dirty state and guards document selection without losing input", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const basePage = controlledDocumentPageFixture();
    const firstDocument = basePage.items[0];
    if (!firstDocument)
      throw new Error("The document page fixture requires one document.");
    const secondId = "73000000-0000-4000-8000-000000000001";
    const second = {
      ...firstDocument,
      globalId: secondId,
      documentNumber: "DRW-000072",
      title: "Second synthetic drawing",
    };
    const page: ControlledDocumentPageViewModel = {
      ...basePage,
      items: [...basePage.items, second],
    };
    const baseWorkspace = controlledDocumentWorkspaceFixture();
    const secondWorkspace: ControlledDocumentWorkspaceViewModel = {
      ...baseWorkspace,
      document: {
        ...baseWorkspace.document,
        globalId: secondId,
        documentNumber: second.documentNumber,
        title: second.title,
      },
    };
    const loadDocument = vi.fn<DocumentDataSource["loadDocument"]>(
      (_projectId, documentId) =>
        Promise.resolve(
          documentId === secondId ? secondWorkspace : baseWorkspace,
        ),
    );
    const reportWorkspaceDirty = vi.fn<ReportWorkspaceDirty>();
    let pendingPerform = (): void => {
      throw new Error("The guarded document transition was not captured.");
    };
    const requestWorkspaceTransition = vi.fn<RequestWorkspaceTransition>(
      (perform) => {
        pendingPerform = perform;
      },
    );
    renderWorkspace(
      createDataSource({
        loadDocument,
        loadDocuments: () => Promise.resolve(page),
      }),
      { reportWorkspaceDirty, requestWorkspaceTransition },
    );

    const create = await screen.findByRole("button", {
      name: "Create document",
    });
    await waitFor(() => {
      expect(create).toBeEnabled();
    });
    await user.click(create);
    const title = screen.getByRole("textbox", { name: "Title" });
    await user.type(title, "Unsubmitted controlled drawing");
    await waitFor(() => {
      expect(reportWorkspaceDirty).toHaveBeenLastCalledWith(
        expect.objectContaining({
          objectIdentity: `${documentProjectId}:new-document`,
          version: "unsaved-document",
        }),
      );
    });

    await user.click(
      screen.getByRole("button", {
        name: second.documentNumber,
      }),
    );
    expect(requestWorkspaceTransition).toHaveBeenCalledOnce();
    expect(loadDocument).toHaveBeenCalledTimes(1);
    expect(title).toHaveValue("Unsubmitted controlled drawing");

    act(() => {
      pendingPerform();
    });
    await waitFor(() => {
      expect(loadDocument).toHaveBeenCalledTimes(2);
    });
    expect((await screen.findAllByText(second.title))[0]).toBeVisible();
    expect(
      screen.queryByDisplayValue("Unsubmitted controlled drawing"),
    ).toBeNull();
  });

  it("submits an actor-bound check-in command and refreshes lock truth", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const base = controlledDocumentWorkspaceFixture();
    const updated: ControlledDocumentWorkspaceViewModel = {
      ...base,
      document: {
        ...base.document,
        currentLock: null,
        optimisticVersion: base.document.optimisticVersion + 1,
      },
    };
    const checkIn = vi.fn<DocumentDataSource["checkIn"]>(() =>
      Promise.resolve(updated),
    );
    renderWorkspace(createDataSource({ checkIn }));

    const button = await screen.findByRole("button", { name: "Check in" });
    await waitFor(() => {
      expect(button).toBeEnabled();
    });
    await user.click(button);

    await waitFor(() => {
      expect(checkIn).toHaveBeenCalledOnce();
    });
    const call = checkIn.mock.calls[0];
    if (!call) throw new Error("The check-in command was not captured.");
    expect(call.slice(0, 4)).toEqual([
      documentProjectId,
      base.document.globalId,
      base.document.optimisticVersion,
      base.document.currentLock?.version,
    ]);
    expect(call[4].csrfToken).toBe(csrfToken);
    expect(call[4].idempotencyKey).toMatch(/^check-in-/u);
    expect(
      await screen.findByRole("button", { name: "Check out" }),
    ).toBeEnabled();
  });

  it("requires explicit authenticated confirmation before submitting review", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const workspace = controlledDocumentWorkspaceFixture();
    const submitReview = vi.fn<DocumentDataSource["submitReview"]>(() =>
      Promise.resolve(documentReleaseTransitionFixture()),
    );
    const loadDocument = vi.fn<DocumentDataSource["loadDocument"]>(() =>
      Promise.resolve(workspace),
    );
    renderWorkspace(createDataSource({ loadDocument, submitReview }));

    const start = await screen.findByRole("button", {
      name: "Submit for review",
    });
    await waitFor(() => {
      expect(start).toBeEnabled();
    });
    await user.click(start);

    expect(
      screen.getByText(
        "I confirm this exact action using my authenticated session.",
      ),
    ).toBeVisible();
    const submit = screen.getByRole("button", { name: "Submit for review" });
    expect(submit).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: "I confirm this exact action using my authenticated session.",
      }),
    );
    expect(submit).toBeEnabled();
    await user.click(submit);

    await waitFor(() => {
      expect(submitReview).toHaveBeenCalledOnce();
      expect(loadDocument).toHaveBeenCalledTimes(2);
    });
    const call = submitReview.mock.calls[0];
    if (!call) throw new Error("The review submission was not captured.");
    expect(call.slice(0, 3)).toEqual([
      documentProjectId,
      workspace.document.globalId,
      workspace.revisions[0]?.globalId,
    ]);
    expect(call[3]).toEqual({
      expectedDocumentVersion: workspace.document.optimisticVersion,
      expectedLifecycleVersion: 0,
      policyGlobalId: workspace.releaseWorkspace.policies[0]?.globalId,
      policyVersion: workspace.releaseWorkspace.policies[0]?.version,
      policySnapshotHash: workspace.releaseWorkspace.policies[0]?.snapshotHash,
      confirmationIntent: "submit_review",
      confirmed: true,
    });
    expect(call[4].csrfToken).toBe(csrfToken);
    expect(call[4].idempotencyKey).toMatch(/^document-release-/u);
  });

  it("creates an immutable baseline from an explicitly selected released revision", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const released = controlledDocumentReleasedWorkspaceFixture();
    const baselineCommand = documentBaselineCommandFixture();
    const createBaseline = vi.fn<DocumentDataSource["createBaseline"]>(() =>
      Promise.resolve(baselineCommand),
    );
    renderWorkspace(
      createDataSource({
        createBaseline,
        loadDocument: () => Promise.resolve(released),
      }),
    );

    const start = await screen.findByRole("button", {
      name: "Create release baseline",
    });
    await waitFor(() => {
      expect(start).toBeEnabled();
    });
    await user.click(start);
    await user.type(
      screen.getByRole("textbox", { name: "Baseline label" }),
      "G2 controlled release",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Add selected released revision",
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Create immutable baseline" }),
    );

    await waitFor(() => {
      expect(createBaseline).toHaveBeenCalledOnce();
    });
    const call = createBaseline.mock.calls[0];
    if (!call) throw new Error("The baseline command was not captured.");
    const history = released.releaseWorkspace.revisions[0];
    const revision = released.revisions[0];
    expect(call[0]).toBe(documentProjectId);
    expect(call[1]).toEqual({
      policyGlobalId: baselinePolicyId,
      policyVersion: 1,
      policySnapshotHash: "e".repeat(64),
      label: "G2 controlled release",
      members: [
        {
          revisionId: revision?.globalId,
          expectedRevisionSnapshotHash: revision?.snapshotHash,
          expectedLifecycleVersion: history?.lifecycle.version,
          expectedReleaseSnapshotHash: history?.lifecycle.releaseSnapshotHash,
        },
      ],
    });
    expect(call[2].csrfToken).toBe(csrfToken);
    expect(call[2].idempotencyKey).toMatch(/^document-baseline-/u);
  });

  it("shows an honest empty state and disables creation without a policy", async () => {
    const page = controlledDocumentPageFixture();
    renderWorkspace(
      createDataSource({
        loadDocuments: () =>
          Promise.resolve({
            ...page,
            items: [],
            policies: [],
            permissions: { ...page.permissions, create: false },
          }),
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "No controlled documents" }),
    ).toBeVisible();
    expect(
      screen.getAllByText(
        "Document creation is unavailable because no accepted document policy is configured.",
      ),
    ).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "Create document" }),
    ).toBeDisabled();
  });

  it("keeps protected content absent when the data source is unavailable", () => {
    renderWorkspace(undefined);
    expect(
      screen.getByText(
        "The live controlled document data source is not configured.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("DRW-000071")).not.toBeInTheDocument();
  });
});
