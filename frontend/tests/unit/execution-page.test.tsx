import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NpiApiError } from "../../src/api/http";
import type {
  IntegrationOperationActionResult,
  IntegrationOperationsDataSource,
} from "../../src/api/integration-operations-data-source";
import ExecutionPage from "../../src/pages/execution-page";
import {
  integrationOperationCollection,
  integrationOperationDetail,
  integrationOperationItem,
  integrationOperationItems,
  integrationOperationsProjectId as projectId,
} from "../support/integration-operations-fixture";
import { renderWithLocale } from "../support/render";

function source(
  overrides: Partial<IntegrationOperationsDataSource> = {},
): IntegrationOperationsDataSource {
  return {
    loadOperations: vi.fn(() =>
      Promise.resolve(integrationOperationCollection()),
    ),
    loadOperation: vi.fn((_project, _kind, operationId) => {
      const item =
        integrationOperationItems().find(
          (candidate) => candidate.operationGlobalId === operationId,
        ) ?? integrationOperationItem("failed_retryable", 4);
      return Promise.resolve(integrationOperationDetail(item));
    }),
    requestAction: vi.fn<IntegrationOperationsDataSource["requestAction"]>(() =>
      Promise.resolve({
        actionGlobalId: "90000000-0000-4000-8000-000000000001",
        operationGlobalId: integrationOperationItem("failed_retryable", 4)
          .operationGlobalId,
        outcomeState: "replay_requested",
        outcomeReferenceGlobalId: null,
      }),
    ),
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
            csrfToken: "integration-operations-csrf-token",
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "integration.operator@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

function renderPage(dataSource: IntegrationOperationsDataSource): void {
  renderWithLocale(
    <ExecutionPage dataSource={dataSource} projectId={projectId} />,
    "en",
    `/projects/${projectId}/integration-operations`,
  );
}

function operationRow(operationId: string): HTMLTableRowElement {
  const row = screen.getByText(operationId).closest("tr");
  if (!(row instanceof HTMLTableRowElement)) {
    throw new Error(`Operation row was not rendered for ${operationId}`);
  }
  return row;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("live integration operations workspace", () => {
  it("renders all closed states and opens operation detail with keyboard selection", async () => {
    const loadOperation = vi.fn<
      IntegrationOperationsDataSource["loadOperation"]
    >((_project, _kind, operationId) => {
      const item =
        integrationOperationItems().find(
          (candidate) => candidate.operationGlobalId === operationId,
        ) ?? integrationOperationItem("failed_retryable", 4);
      return Promise.resolve(integrationOperationDetail(item));
    });
    const dataSource = source({ loadOperation });
    renderPage(dataSource);

    expect(
      screen.getByLabelText("Loading integration operations"),
    ).toBeVisible();
    expect(
      await screen.findByRole("heading", {
        name: "Project operation worklist",
      }),
    ).toBeVisible();
    for (const label of [
      "Queued",
      "Processing",
      "Succeeded",
      "Failed, replay available",
      "Final failure",
      "Outcome uncertain",
      "Partial result",
      "Identity or version conflict",
      "Quarantined",
      "Evidence unavailable",
    ]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("Showing 10 operations")).toBeVisible();

    const processing = integrationOperationItem("processing", 2);
    const row = operationRow(processing.operationGlobalId);
    row.focus();
    await userEvent.setup().keyboard("{Enter}");
    await waitFor(() => {
      expect(loadOperation).toHaveBeenLastCalledWith(
        projectId,
        processing.operationKind,
        processing.operationGlobalId,
        expect.any(AbortSignal),
      );
    });
    expect(
      await screen.findByRole("heading", {
        name: processing.operationGlobalId,
      }),
    ).toBeVisible();
    expect(screen.getByText("Attempts")).toBeVisible();
    expect(screen.getByText("Results")).toBeVisible();
    expect(screen.getByText("Action history")).toBeVisible();
  });

  it("renders the empty state and requests the logical DLQ projection", async () => {
    const loadOperations = vi
      .fn<IntegrationOperationsDataSource["loadOperations"]>()
      .mockResolvedValue(integrationOperationCollection({ items: [] }));
    renderPage(source({ loadOperations }));
    const user = userEvent.setup();

    expect(
      await screen.findByRole("heading", { name: "No integration operations" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Show logical DLQ" }));
    await waitFor(() => {
      expect(loadOperations).toHaveBeenLastCalledWith(
        projectId,
        expect.objectContaining({ logicalDlq: true }),
        expect.any(AbortSignal),
      );
    });
    expect(
      screen.getByText(
        "No operation currently belongs to the Project logical DLQ classification.",
      ),
    ).toBeVisible();
    globalThis.dispatchEvent(
      new CustomEvent("npi:refresh-integration-operations"),
    );
    await waitFor(() => {
      expect(loadOperations).toHaveBeenCalledTimes(3);
    });
  });

  it("keeps the only eligible action visible but disabled without authority", async () => {
    const replayable = integrationOperationItem("failed_retryable", 4);
    renderPage(
      source({
        loadOperations: vi.fn(() =>
          Promise.resolve(
            integrationOperationCollection({ act: false, items: [replayable] }),
          ),
        ),
        loadOperation: vi.fn(() =>
          Promise.resolve(integrationOperationDetail(replayable)),
        ),
      }),
    );

    expect(await screen.findByText("Read-only integration view")).toBeVisible();
    expect(
      screen.getByText(
        "You may inspect Project-contained operation truth, but no operator action is authorized.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Review and request replay" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("button", {
        name: "Review and request reconciliation",
      }),
    ).toBeNull();
  });

  it("does not render operation identities when view permission is denied", async () => {
    const hidden = integrationOperationItem("failed_retryable", 4);
    const loadOperation =
      vi.fn<IntegrationOperationsDataSource["loadOperation"]>();
    const dataSource = source({
      loadOperations: vi.fn(() =>
        Promise.resolve(
          integrationOperationCollection({
            act: false,
            items: [hidden],
            view: false,
          }),
        ),
      ),
      loadOperation,
    });
    renderPage(dataSource);

    expect(
      await screen.findByRole("heading", {
        name: "Integration operations unavailable",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "You do not have permission to view integration operations for this Project.",
      ),
    ).toBeVisible();
    expect(screen.queryByText(hidden.operationGlobalId)).toBeNull();
    expect(loadOperation).not.toHaveBeenCalled();
  });

  it("keeps a permission-safe API failure and trace visible", async () => {
    renderPage(
      source({
        loadOperations: vi.fn(() =>
          Promise.reject(
            new NpiApiError({
              type: "urn:npi:problem:not-found",
              title: "The requested Project was not found or is not available.",
              status: 404,
              code: "PROJECT_NOT_FOUND",
              traceId: "trace-project-permission-safe",
              retryable: false,
            }),
          ),
        ),
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Integration operations unavailable",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "The requested Project was not found or is not available.",
      ),
    ).toBeVisible();
    expect(screen.getByText("trace-project-permission-safe")).toBeVisible();
  });

  it("reviews and records one replay request without claiming ERPNext completion", async () => {
    enableCommandSession();
    const replayable = integrationOperationItem("failed_retryable", 4);
    let resolveCommand!: (value: IntegrationOperationActionResult) => void;
    const requestAction = vi.fn<
      IntegrationOperationsDataSource["requestAction"]
    >(
      () =>
        new Promise((resolve) => {
          resolveCommand = resolve;
        }),
    );
    renderPage(
      source({
        loadOperations: vi.fn(() =>
          Promise.resolve(
            integrationOperationCollection({ items: [replayable] }),
          ),
        ),
        loadOperation: vi.fn(() =>
          Promise.resolve(integrationOperationDetail(replayable)),
        ),
        requestAction,
      }),
    );
    const user = userEvent.setup();

    const action = await screen.findByRole("button", {
      name: "Review and request replay",
    });
    await waitFor(() => {
      expect(action).toBeEnabled();
    });
    await user.click(action);
    const review = screen.getByRole("dialog", { name: "Replay impact review" });
    const confirm = within(review).getByRole("button", {
      name: "Request exact replay",
    });
    expect(confirm).toBeDisabled();
    await user.type(
      within(review).getByRole("textbox", { name: "Reason" }),
      "Reviewed exact immutable source",
    );
    await user.click(confirm);

    await waitFor(() => {
      expect(requestAction).toHaveBeenCalledOnce();
    });
    const request = requestAction.mock.calls[0];
    if (!request) throw new Error("Replay request was not recorded");
    expect(request[0]).toBe(projectId);
    expect(request[1]).toBe(replayable);
    expect(request[2]).toBe("replay");
    expect(request[3].csrfToken).toBe("integration-operations-csrf-token");
    expect(request[3].idempotencyKey).toMatch(/^p807-replay-/u);
    expect(request[3].signal).toBeInstanceOf(AbortSignal);
    expect(screen.getByText("Command in progress")).toBeVisible();
    resolveCommand({
      actionGlobalId: "90000000-0000-4000-8000-000000000001",
      operationGlobalId: replayable.operationGlobalId,
      outcomeState: "replay_requested",
      outcomeReferenceGlobalId: replayable.operationGlobalId,
    });
    expect(await screen.findByText("Replay request recorded")).toBeVisible();
    expect(
      screen.getByText(
        "The append-only operator action is recorded. This does not confirm ERPNext completion.",
      ),
    ).toBeVisible();
  });

  it("shows reconciliation only for uncertain truth and no mutation for final failure", async () => {
    const uncertain = integrationOperationItem("uncertain", 6);
    const final = integrationOperationItem("failed_final", 5);
    renderPage(
      source({
        loadOperations: vi.fn(() =>
          Promise.resolve(
            integrationOperationCollection({ items: [uncertain, final] }),
          ),
        ),
        loadOperation: vi.fn((_project, _kind, operationId) =>
          Promise.resolve(
            integrationOperationDetail(
              operationId === uncertain.operationGlobalId ? uncertain : final,
            ),
          ),
        ),
      }),
    );
    const user = userEvent.setup();

    expect(
      await screen.findByRole("button", {
        name: "Review and request reconciliation",
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Review and request replay" }),
    ).toBeNull();
    await user.click(operationRow(final.operationGlobalId));
    expect(
      await screen.findByText(
        "This operation is observe-only. Correction or new owning commands remain outside this workspace.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", {
        name: "Review and request reconciliation",
      }),
    ).toBeNull();
  });

  it("keeps a 409 command conflict visible and requires a fresh review", async () => {
    enableCommandSession();
    const replayable = integrationOperationItem("failed_retryable", 4);
    const requestAction = vi.fn<
      IntegrationOperationsDataSource["requestAction"]
    >(() =>
      Promise.reject(
        new NpiApiError({
          type: "urn:npi:problem:integration-operation-conflict",
          title: "The integration operation changed.",
          status: 409,
          code: "INTEGRATION_OPERATION_CONFLICT",
          traceId: "trace-integration-conflict",
          retryable: false,
        }),
      ),
    );
    renderPage(
      source({
        loadOperations: vi.fn(() =>
          Promise.resolve(
            integrationOperationCollection({ items: [replayable] }),
          ),
        ),
        loadOperation: vi.fn(() =>
          Promise.resolve(integrationOperationDetail(replayable)),
        ),
        requestAction,
      }),
    );
    const user = userEvent.setup();

    const action = await screen.findByRole("button", {
      name: "Review and request replay",
    });
    await waitFor(() => {
      expect(action).toBeEnabled();
    });
    await user.click(action);
    const review = screen.getByRole("dialog", { name: "Replay impact review" });
    await user.type(
      within(review).getByRole("textbox", { name: "Reason" }),
      "Review conflict handling",
    );
    await user.click(
      within(review).getByRole("button", { name: "Request exact replay" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Command conflict" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "The operation changed before this command committed. Refresh and review the current state before trying again.",
      ),
    ).toBeVisible();
    expect(screen.getByText("trace-integration-conflict")).toBeVisible();
  });

  it("fails closed before loading when Project context is absent", () => {
    const loadOperations =
      vi.fn<IntegrationOperationsDataSource["loadOperations"]>();
    const loadOperation =
      vi.fn<IntegrationOperationsDataSource["loadOperation"]>();
    const dataSource = source({ loadOperation, loadOperations });
    renderWithLocale(
      <ExecutionPage dataSource={dataSource} projectId="not-a-project" />,
      "en",
      "/execution",
    );

    expect(
      screen.getByRole("heading", { name: "Project context required" }),
    ).toBeVisible();
    expect(loadOperations).not.toHaveBeenCalled();
    expect(loadOperation).not.toHaveBeenCalled();
  });
});
