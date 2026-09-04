import {
  act,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  defaultMyWorkGridPreferences,
  type MyWorkGridPreferencesDataSource,
} from "../../src/api/grid-preferences-data-source";
import {
  NpiApiError,
  NpiTransportError,
  type ProblemDetails,
} from "../../src/api/http";
import {
  defaultMyWorkInspectorPreference,
  type MyWorkInspectorPreferencesDataSource,
} from "../../src/api/my-work-inspector-preferences-data-source";
import type {
  MyWorkDataSource,
  MyWorkQuery,
} from "../../src/api/my-work-data-source";
import { myWorkTargetPath } from "../../src/app/my-work-navigation";
import { LiveMyWorklist } from "../../src/components/live-my-worklist";
import type {
  MyWorkItemViewModel,
  MyWorkPageViewModel,
} from "../../src/domain/view-models";
import { supportedLocales } from "../../src/i18n/runtime";
import { renderWithLocale } from "../support/render";

const projectId = "11111111-1111-4111-8111-111111111111";
const workItemId = "22222222-2222-4222-8222-222222222222";
const gateId = "33333333-3333-4333-8333-333333333333";
const laterProjectId = "99999999-9999-4999-8999-999999999999";

function itemFixture(
  overrides: Partial<MyWorkItemViewModel> = {},
): MyWorkItemViewModel {
  return {
    action: "view_work_item",
    blocking: true,
    category: "risk",
    context: {
      code: "RISK-014",
      globalId: workItemId,
      title: "Hot runner delivery risk",
      type: "domain_work_item",
    },
    dueAt: "2026-07-25T01:00:00Z",
    dueState: "overdue",
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    priority: { scheme: "domain_severity", value: "high" },
    project: {
      businessCode: "NPI-26018",
      globalId: projectId,
      title: "Battery housing",
    },
    source: {
      globalId: workItemId,
      type: "domain_work_item",
      version: 4,
    },
    sourceStatus: {
      editableIn: "NPI_ONE",
      sourceSystem: "NPI_ONE",
      syncState: "local",
    },
    status: "ready",
    target: { kind: "my_work_item", workItemId },
    title: "Hot runner delivery risk",
    why: "domain_work_item_owner",
    ...overrides,
  };
}

function gateItemFixture(): MyWorkItemViewModel {
  return itemFixture({
    action: "open_gate_review",
    blocking: false,
    category: "approval",
    context: {
      code: "G3",
      globalId: gateId,
      title: "Tooling release",
      type: "gate",
    },
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    priority: { scheme: "gate_requirement_priority", value: "P0" },
    source: {
      globalId: gateId,
      type: "gate_review_assignment",
      version: 7,
    },
    status: "waiting",
    target: { gateId, kind: "gate_review", projectId },
    title: "Review Gate G3 evidence",
    why: "gate_review_step",
  });
}

function pageFixture(
  overrides: Partial<MyWorkPageViewModel> = {},
): MyWorkPageViewModel {
  return {
    asOf: "2026-07-25T12:00:00Z",
    counts: {
      all: { availability: "available", value: 2 },
      approvals: { availability: "available", value: 1 },
      blockers: { availability: "available", value: 1 },
      integration: {
        availability: "unavailable",
        reason: "source_not_available",
      },
      overdue: { availability: "available", value: 2 },
      today: { availability: "available", value: 0 },
      waiting: { availability: "available", value: 1 },
    },
    items: [itemFixture(), gateItemFixture()],
    nextCursor: null,
    projectOptions: [
      itemFixture().project,
      {
        businessCode: "NPI-26099",
        globalId: laterProjectId,
        title: "Later-page project",
      },
    ],
    timeZone: "America/Los_Angeles",
    ...overrides,
  };
}

function dataSource(load: MyWorkDataSource["load"]): MyWorkDataSource & {
  load: ReturnType<typeof vi.fn<MyWorkDataSource["load"]>>;
} {
  return { load: vi.fn(load) };
}

function resolvedDataSource(
  page: MyWorkPageViewModel = pageFixture(),
): ReturnType<typeof dataSource> {
  return dataSource(() => Promise.resolve(page));
}

function problem(status: number, code: string, retryable = false): NpiApiError {
  const details: ProblemDetails = {
    code,
    retryable,
    status,
    title: `Controlled ${code} response`,
    traceId: `trace-${code.toLowerCase()}`,
    type: `urn:npi:problem:${code.toLowerCase()}`,
  };
  return new NpiApiError(details);
}

function deferred<T>(): {
  promise: Promise<T>;
  reject: (reason: unknown) => void;
  resolve: (value: T) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

describe("live My Work worklist", () => {
  it("announces personal-grid persistence changes through one polite status region", async () => {
    const user = userEvent.setup();
    renderWithLocale(
      <LiveMyWorklist dataSource={resolvedDataSource()} navigate={vi.fn()} />,
    );
    await within(screen.getByRole("table")).findByRole("button", {
      name: "View work item",
    });

    await user.click(screen.getByRole("button", { name: "Grid settings" }));

    const persistenceStatus = screen.getByRole("status");
    expect(persistenceStatus).toHaveAttribute("aria-live", "polite");
    expect(persistenceStatus).toHaveAttribute("aria-atomic", "true");
    expect(persistenceStatus).toHaveTextContent(
      "Session verification is required before personal grid settings can be saved.",
    );
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });

  it("renders validated assignments, honest counts, keyboard selection, and typed target navigation", async () => {
    const navigate = vi.fn<(target: string) => void>();
    const user = userEvent.setup();
    renderWithLocale(
      <LiveMyWorklist dataSource={resolvedDataSource()} navigate={navigate} />,
    );

    expect(screen.getByText("Loading My Work")).toBeVisible();
    const table = screen.getByRole("table");
    await within(table).findByRole("button", { name: "View work item" });
    expect(within(table).getAllByRole("columnheader")).toHaveLength(8);
    const integrationMetric = screen
      .getByText("Integration")
      .closest(".metric-strip__item");
    expect(integrationMetric).toBeInstanceOf(HTMLElement);
    if (!(integrationMetric instanceof HTMLElement)) {
      throw new Error("The Integration metric is required.");
    }
    expect(within(integrationMetric).getByText("Unavailable")).toBeVisible();
    expect(
      within(integrationMetric).queryByText("0", { exact: true }),
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByText("You own this domain work item.").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Domain severity: High").length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByText("Jul 24, 2026, 6:00 PM").length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByText("Overdue").length).toBeGreaterThan(1);
    expect(screen.getByText("America/Los_Angeles")).toBeVisible();
    expect(screen.getByText("Due time zone")).toBeVisible();

    const gateRow = within(table)
      .getByText("Review Gate G3 evidence")
      .closest("tr");
    expect(gateRow).not.toBeNull();
    if (!gateRow) throw new Error("The Gate assignment row is required.");
    gateRow.focus();
    await user.keyboard("{Enter}");
    expect(gateRow).toHaveAttribute("aria-selected", "true");

    const gateAction = within(gateRow).getByRole("button", {
      name: "Open Gate review",
    });
    gateAction.focus();
    await user.keyboard("{Enter}");
    expect(navigate).toHaveBeenLastCalledWith(
      `/projects/${projectId}/gates/${gateId}`,
    );

    const domainRow = within(table)
      .getByRole("button", { name: "View work item" })
      .closest("tr");
    expect(domainRow).not.toBeNull();
    if (!domainRow) throw new Error("The domain work item row is required.");
    await user.click(
      within(domainRow).getByRole("button", { name: "View work item" }),
    );
    expect(navigate).toHaveBeenLastCalledWith(
      `/projects/${projectId}?tab=work-items&workItem=${workItemId}`,
    );
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);
  });

  it("uses the injected authenticated pane preference and preserves work context across collapse", async () => {
    const bootstrap = {
      allowedLanguages: supportedLocales,
      catalog: {
        language: "en" as const,
        messages: {},
        version: "a".repeat(64),
      },
      csrfToken: "authenticated-my-work-pane-csrf-token",
      language: "en" as const,
      preferences: { navigationCollapsed: false },
      userId: "pane-engineer@example.invalid",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(bootstrap), { status: 200 }),
        ),
      ),
    );
    const gridPreferencesDataSource: MyWorkGridPreferencesDataSource = {
      load: vi.fn(() => Promise.resolve(defaultMyWorkGridPreferences())),
      save: vi.fn(() => Promise.resolve(defaultMyWorkGridPreferences())),
    };
    const paneLoad = vi.fn<MyWorkInspectorPreferencesDataSource["load"]>(() =>
      Promise.resolve(defaultMyWorkInspectorPreference()),
    );
    const paneSave = vi.fn<MyWorkInspectorPreferencesDataSource["save"]>(
      (command) =>
        Promise.resolve({
          ...defaultMyWorkInspectorPreference(),
          collapsed: command.collapsed,
          widthPx: command.widthPx,
        }),
    );
    const source = resolvedDataSource();
    const user = userEvent.setup();
    const { container } = renderWithLocale(
      <LiveMyWorklist
        dataSource={source}
        gridPreferencesDataSource={gridPreferencesDataSource}
        navigate={vi.fn()}
        panePreferencesDataSource={{ load: paneLoad, save: paneSave }}
      />,
    );
    await waitFor(() => {
      expect(paneLoad).toHaveBeenCalledOnce();
    });
    const collapse = screen.getByRole("button", {
      name: "Collapse inspector",
    });
    await waitFor(() => {
      expect(collapse).toBeEnabled();
    });

    fireEvent.change(screen.getByRole("searchbox", { name: "Filter" }), {
      target: { value: "runner" },
    });
    await waitFor(() => {
      expect(source.load).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "runner" }),
        expect.any(AbortSignal),
      );
    });
    const table = screen.getByRole("table");
    const gateRow = within(table)
      .getByText("Review Gate G3 evidence")
      .closest("tr");
    expect(gateRow).not.toBeNull();
    if (!gateRow) throw new Error("The Gate assignment row is required.");
    await user.click(gateRow);
    expect(gateRow).toHaveAttribute("aria-selected", "true");

    const viewport = container.querySelector<HTMLElement>(
      ".dense-grid__viewport",
    );
    expect(viewport).not.toBeNull();
    if (!viewport) throw new Error("The grid viewport is required.");
    viewport.scrollLeft = 120;
    fireEvent.scroll(viewport);

    await user.click(
      screen.getByRole("button", { name: "Collapse inspector" }),
    );

    expect(screen.getByRole("searchbox", { name: "Filter" })).toHaveValue(
      "runner",
    );
    expect(gateRow).toHaveAttribute("aria-selected", "true");
    expect(viewport.scrollLeft).toBe(120);
    expect(
      screen.getByRole("button", { name: "Expand inspector" }),
    ).toBeVisible();
    await waitFor(() => {
      expect(paneSave).toHaveBeenCalledWith(
        {
          collapsed: true,
          schemaVersion: "my-work-inspector-v1",
          widthPx: 340,
        },
        {
          csrfToken: bootstrap.csrfToken,
          userId: bootstrap.userId,
        },
        expect.any(AbortSignal),
      );
    });
  });

  it("uses only closed filters and cursor pagination, then returns to the prior cursor", async () => {
    const firstPage = pageFixture({ nextCursor: "cursor-page-2" });
    const secondPage = pageFixture({
      items: [gateItemFixture()],
      nextCursor: null,
    });
    const source = dataSource((query) =>
      Promise.resolve(query.cursor ? secondPage : firstPage),
    );
    const user = userEvent.setup();
    renderWithLocale(<LiveMyWorklist dataSource={source} navigate={vi.fn()} />);
    await within(screen.getByRole("table")).findByRole("button", {
      name: "View work item",
    });
    expect(
      within(screen.getByRole("combobox", { name: "Project" })).getByRole(
        "option",
        { name: "NPI-26099 · Later-page project" },
      ),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Saved view" }), {
      target: { value: "overdue" },
    });
    await waitFor(() => {
      expect(source.load).toHaveBeenLastCalledWith(
        expect.objectContaining({ view: "overdue" }),
        expect.any(AbortSignal),
      );
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Project" }), {
      target: { value: projectId },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Priority" }), {
      target: { value: "domain_severity:high" },
    });
    fireEvent.change(screen.getByRole("searchbox", { name: "Filter" }), {
      target: { value: "runner" },
    });
    await waitFor(() => {
      const lastQuery = source.load.mock.calls.at(-1)?.[0];
      expect(lastQuery).toEqual({
        limit: 20,
        priority: { scheme: "domain_severity", value: "high" },
        projectId,
        search: "runner",
        view: "overdue",
      });
    });

    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => {
      expect(source.load).toHaveBeenLastCalledWith(
        expect.objectContaining({ cursor: "cursor-page-2" }),
        expect.any(AbortSignal),
      );
    });
    expect(screen.getByText("Page 2")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Previous page" }));
    await waitFor(() => {
      const lastQuery = source.load.mock.calls.at(-1)?.[0];
      expect(lastQuery).not.toHaveProperty("cursor");
    });
    expect(screen.getByText("Page 1")).toBeVisible();
  });

  it("shows loading and an honest empty state without inventing a count", async () => {
    const pending = deferred<MyWorkPageViewModel>();
    const source = dataSource(() => pending.promise);
    renderWithLocale(<LiveMyWorklist dataSource={source} navigate={vi.fn()} />);

    expect(screen.getByText("Loading My Work")).toBeVisible();
    await act(async () => {
      pending.resolve(
        pageFixture({
          counts: {
            all: { availability: "available", value: 0 },
            approvals: { availability: "available", value: 0 },
            blockers: { availability: "available", value: 0 },
            integration: {
              availability: "unavailable",
              reason: "source_not_available",
            },
            overdue: { availability: "available", value: 0 },
            today: { availability: "available", value: 0 },
            waiting: { availability: "available", value: 0 },
          },
          items: [],
        }),
      );
      await pending.promise;
    });
    expect(
      await screen.findByText("No assigned work is available in this view."),
    ).toBeVisible();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Clear filters" })).toBeNull();
  });

  it.each([
    [
      "no permission",
      problem(403, "MY_WORK_FORBIDDEN"),
      "My Work access is not available",
    ],
    [
      "invalid response",
      new NpiTransportError(
        "invalid_response",
        "trace-invalid-response",
        "trace",
      ),
      "The My Work response could not be used safely",
    ],
    [
      "final service failure",
      problem(500, "MY_WORK_FINAL"),
      "My Work is unavailable",
    ],
  ])(
    "fails closed for %s without offering a false retry",
    async (_name, error, title) => {
      const source = dataSource(() => Promise.reject(error));
      renderWithLocale(
        <LiveMyWorklist dataSource={source} navigate={vi.fn()} />,
      );

      expect(await screen.findByText(title)).toBeVisible();
      expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
      expect(screen.queryByText("Hot runner delivery risk")).toBeNull();
    },
  );

  it("retries only a retryable failure and replaces it with current data", async () => {
    const source = dataSource(
      vi
        .fn<MyWorkDataSource["load"]>()
        .mockRejectedValueOnce(problem(503, "MY_WORK_RETRYABLE", true))
        .mockResolvedValueOnce(pageFixture()),
    );
    const user = userEvent.setup();
    renderWithLocale(<LiveMyWorklist dataSource={source} navigate={vi.fn()} />);

    expect(
      await screen.findByText("My Work could not be loaded"),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await within(screen.getByRole("table")).findByRole("button", {
        name: "View work item",
      }),
    ).toBeVisible();
    expect(source.load).toHaveBeenCalledTimes(2);
  });

  it("reloads a conflicted later page from the first current page", async () => {
    const source = dataSource(
      vi
        .fn<MyWorkDataSource["load"]>()
        .mockResolvedValueOnce(pageFixture({ nextCursor: "cursor-page-2" }))
        .mockRejectedValueOnce(problem(409, "MY_WORK_CONFLICT"))
        .mockResolvedValueOnce(pageFixture()),
    );
    const user = userEvent.setup();
    renderWithLocale(<LiveMyWorklist dataSource={source} navigate={vi.fn()} />);

    await within(screen.getByRole("table")).findByRole("button", {
      name: "View work item",
    });
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("My Work changed")).toBeVisible();
    expect(screen.getByText("Conflict")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();

    await user.click(
      screen.getByRole("button", { name: "Reload latest data" }),
    );
    await within(screen.getByRole("table")).findByRole("button", {
      name: "View work item",
    });
    expect(source.load).toHaveBeenCalledTimes(3);
    expect(source.load.mock.calls[2]?.[0]).toEqual({
      limit: 20,
      view: "all",
    });
    expect(screen.getByText("Page 1")).toBeVisible();
  });

  it("rejects a repeated cursor instead of looping", async () => {
    const source = dataSource((query: MyWorkQuery) =>
      Promise.resolve(
        pageFixture({
          nextCursor: query.cursor ?? "cursor-page-2",
        }),
      ),
    );
    const user = userEvent.setup();
    renderWithLocale(<LiveMyWorklist dataSource={source} navigate={vi.fn()} />);

    await within(screen.getByRole("table")).findByRole("button", {
      name: "View work item",
    });
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(
      await screen.findByText("The My Work response could not be used safely"),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("aborts superseded and unmounted requests and ignores their stale results", async () => {
    const first = deferred<MyWorkPageViewModel>();
    const second = deferred<MyWorkPageViewModel>();
    const refresh = deferred<MyWorkPageViewModel>();
    const source = dataSource(
      vi
        .fn<MyWorkDataSource["load"]>()
        .mockReturnValueOnce(first.promise)
        .mockReturnValueOnce(second.promise)
        .mockReturnValueOnce(refresh.promise),
    );
    const rendered = renderWithLocale(
      <LiveMyWorklist dataSource={source} navigate={vi.fn()} />,
    );
    await waitFor(() => {
      expect(source.load).toHaveBeenCalledTimes(1);
    });
    const firstSignal = source.load.mock.calls[0]?.[1];

    fireEvent.change(screen.getByRole("combobox", { name: "Saved view" }), {
      target: { value: "overdue" },
    });
    await waitFor(() => {
      expect(source.load).toHaveBeenCalledTimes(2);
    });
    expect(firstSignal?.aborted).toBe(true);
    const secondSignal = source.load.mock.calls[1]?.[1];
    await act(async () => {
      second.resolve(
        pageFixture({
          items: [itemFixture({ title: "Current assigned item" })],
        }),
      );
      await second.promise;
    });
    expect(
      await within(screen.getByRole("table")).findByText(
        "Current assigned item",
      ),
    ).toBeVisible();
    await act(async () => {
      first.resolve(
        pageFixture({
          items: [itemFixture({ title: "Stale protected item" })],
        }),
      );
      await first.promise;
    });
    expect(screen.queryByText("Stale protected item")).toBeNull();

    act(() => {
      globalThis.dispatchEvent(new CustomEvent("npi:refresh-my-work"));
    });
    await waitFor(() => {
      expect(source.load).toHaveBeenCalledTimes(3);
    });
    expect(secondSignal?.aborted).toBe(true);
    const refreshSignal = source.load.mock.calls[2]?.[1];
    rendered.unmount();
    expect(refreshSignal?.aborted).toBe(true);
  });

  it("encodes typed target identifiers without accepting a server path", () => {
    const item = itemFixture({
      project: {
        ...itemFixture().project,
        globalId: "project/../unsafe",
      },
      target: {
        kind: "my_work_item",
        workItemId: "item/../unsafe?path=/admin",
      },
    });
    expect(myWorkTargetPath(item)).toBe(
      "/projects/project%2F..%2Funsafe?tab=work-items&workItem=item%2F..%2Funsafe%3Fpath%3D%2Fadmin",
    );
  });
});
