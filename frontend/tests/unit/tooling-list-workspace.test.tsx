import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ToolingListDataSource } from "../../src/api/tooling-list-data-source";
import { NpiApiError, NpiTransportError } from "../../src/api/http";
import { ToolingListWorkspace } from "../../src/components/tooling-list-workspace";
import { renderWithLocale } from "../support/render";
import {
  toolingExportPackage,
  toolingListIds,
  toolingListPage,
  toolingListPreference,
} from "../support/tooling-list-fixture";

function dataSource(
  overrides: Partial<ToolingListDataSource> = {},
): ToolingListDataSource {
  return {
    createExport: () =>
      Promise.resolve({
        package: toolingExportPackage({
          expiresAt: "2099-08-10T10:00:00Z",
          generatedAt: "2099-08-10T09:00:00Z",
        }),
        replayed: false,
      }),
    downloadExport: (_project, packageValue) =>
      Promise.resolve({
        blob: new Blob(["exact package"], { type: "application/zip" }),
        fileName: packageValue.fileName,
        replayed: false,
      }),
    loadList: () => Promise.resolve(toolingListPage()),
    loadPreference: () => Promise.resolve(toolingListPreference()),
    savePreference: () => Promise.resolve(toolingListPreference()),
    ...overrides,
  };
}

function enableCommandSession(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: {
              language: "en",
              messages: {},
              version: "a".repeat(64),
            },
            csrfToken: "tooling-list-workspace-csrf-token",
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
  source: ToolingListDataSource,
  navigate = vi.fn<(target: string) => void>(),
): void {
  renderWithLocale(
    <ToolingListWorkspace
      dataSource={source}
      navigate={navigate}
      projectId={toolingListIds.project}
      selectedMasterId={toolingListIds.masterOne}
    />,
    "en",
    `/projects/${toolingListIds.project}/tooling`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  Reflect.deleteProperty(globalThis.URL, "createObjectURL");
  Reflect.deleteProperty(globalThis.URL, "revokeObjectURL");
});

describe("Tooling List workspace", () => {
  it("renders ten governed views, dense selected-object navigation and shared-origin truth", async () => {
    const navigate = vi.fn<(target: string) => void>();
    renderWorkspace(dataSource(), navigate);
    const user = userEvent.setup();

    await screen.findByText("Front housing mould");
    const grid = screen.getByRole("grid", {
      name: "Project Tooling List",
    });
    expect(within(grid).getAllByRole("row")).toHaveLength(3);
    expect(within(grid).getAllByRole("columnheader")).toHaveLength(9);
    expect(
      screen.getByRole("option", { name: "All Tooling Masters" }),
    ).toBeVisible();
    expect(screen.getAllByRole("option")).toHaveLength(10 + 4 + 2 + 4 + 2);
    expect(screen.getByText("Shared Master")).toBeVisible();
    expect(screen.getByText("Controlled XLSX import")).toBeVisible();
    const selectedRow = within(grid)
      .getByText("Front housing mould")
      .closest("tr");
    expect(selectedRow).toHaveAttribute("aria-selected", "true");

    await user.click(within(grid).getByText("Connector insert mould"));
    expect(navigate).toHaveBeenCalledWith(
      `/projects/${toolingListIds.project}/tooling/${toolingListIds.masterTwo}`,
    );
    expect(grid).not.toHaveTextContent("private/files");
  });

  it("applies closed search, sort and grouping controls as one stable first-page request", async () => {
    const loadList = vi.fn<ToolingListDataSource["loadList"]>(() =>
      Promise.resolve(toolingListPage()),
    );
    renderWorkspace(dataSource({ loadList }));
    const user = userEvent.setup();

    await screen.findByRole("grid", { name: "Project Tooling List" });
    await user.type(screen.getByLabelText("Search Tooling"), "insert");
    await user.selectOptions(
      screen.getByLabelText("Sort by"),
      "physical_set_count",
    );
    await user.selectOptions(screen.getByLabelText("Direction"), "desc");
    await user.selectOptions(
      screen.getByLabelText("Group by"),
      "physical_set_presence",
    );
    await user.click(screen.getByRole("button", { name: "Apply view" }));

    await waitFor(() => {
      expect(loadList).toHaveBeenCalledTimes(2);
    });
    expect(loadList.mock.calls[1]?.slice(0, 4)).toEqual([
      toolingListIds.project,
      {
        groupKey: "physical_set_presence",
        search: "insert",
        sortDirection: "desc",
        sortKey: "physical_set_count",
        viewId: "all",
      },
      50,
      null,
    ]);
  });

  it("reviews an exact selection before package creation and private download", async () => {
    enableCommandSession();
    const createExport = vi.fn<ToolingListDataSource["createExport"]>(() =>
      Promise.resolve({
        package: toolingExportPackage({
          expiresAt: "2099-08-10T10:00:00Z",
          generatedAt: "2099-08-10T09:00:00Z",
          objectCount: 1,
          objectRefs: [
            toolingExportPackage().objectRefs[0] ?? {
              snapshotHash: "a".repeat(64),
              toolingMasterGlobalId: toolingListIds.masterOne,
            },
          ],
        }),
        replayed: false,
      }),
    );
    const downloadExport = vi.fn<ToolingListDataSource["downloadExport"]>(
      (_project, packageValue) =>
        Promise.resolve({
          blob: new Blob(["exact package"], { type: "application/zip" }),
          fileName: packageValue.fileName,
          replayed: true,
        }),
    );
    const createObjectUrl = vi.fn(() => "blob:exact-package");
    const revokeObjectUrl = vi.fn();
    Object.defineProperty(globalThis.URL, "createObjectURL", {
      configurable: true,
      value: createObjectUrl,
    });
    Object.defineProperty(globalThis.URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectUrl,
    });
    vi.spyOn(
      globalThis.HTMLAnchorElement.prototype,
      "click",
    ).mockImplementation(() => undefined);
    renderWorkspace(dataSource({ createExport, downloadExport }));
    const user = userEvent.setup();

    const select = await screen.findByRole("checkbox", {
      name: "Select Front housing mould",
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Export object package" }),
      ).toBeDisabled();
    });
    await user.click(select);
    await user.click(
      screen.getByRole("button", { name: "Export object package" }),
    );
    const review = screen.getByRole("dialog", {
      name: "Review Tooling object package export",
    });
    expect(review).toHaveTextContent("1");
    expect(review).toHaveTextContent("One hour");
    expect(review).toHaveTextContent(
      "Confidential and external execution fields are omitted.",
    );
    await user.click(
      within(review).getByRole("button", { name: "Create object package" }),
    );

    expect(await screen.findByText("Package created")).toBeVisible();
    expect(createExport).toHaveBeenCalledOnce();
    expect(createExport.mock.calls[0]?.[1]).toEqual({
      mode: "selection",
      selection: [
        {
          snapshotHash: "a".repeat(64),
          toolingMasterGlobalId: toolingListIds.masterOne,
        },
      ],
    });
    await user.click(
      screen.getByRole("button", { name: "Download object package" }),
    );
    expect(
      await screen.findByText(
        "The exact package download was replayed safely.",
      ),
    ).toBeVisible();
    expect(downloadExport).toHaveBeenCalledOnce();
    expect(createObjectUrl).toHaveBeenCalledOnce();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:exact-package");
  });

  it("reuses the same idempotency key for a retryable exact export", async () => {
    enableCommandSession();
    const createExport = vi
      .fn<ToolingListDataSource["createExport"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "request-export", "request"),
      )
      .mockResolvedValueOnce({
        package: toolingExportPackage({
          expiresAt: "2099-08-10T10:00:00Z",
          generatedAt: "2099-08-10T09:00:00Z",
          objectCount: 1,
          objectRefs: [
            {
              snapshotHash: "a".repeat(64),
              toolingMasterGlobalId: toolingListIds.masterOne,
            },
          ],
        }),
        replayed: true,
      });
    renderWorkspace(dataSource({ createExport }));
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("checkbox", {
        name: "Select Front housing mould",
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Export object package" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Create object package" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Retry exact export" }),
    );

    expect(await screen.findByText("Replayed exact package")).toBeVisible();
    expect(createExport).toHaveBeenCalledTimes(2);
    expect(createExport.mock.calls[0]?.[2].idempotencyKey).toBe(
      createExport.mock.calls[1]?.[2].idempotencyKey,
    );
  });

  it("surfaces saved-view conflicts and reloads authoritative preferences", async () => {
    enableCommandSession();
    const loadPreference = vi.fn<ToolingListDataSource["loadPreference"]>(() =>
      Promise.resolve(toolingListPreference()),
    );
    const savePreference = vi.fn<ToolingListDataSource["savePreference"]>(() =>
      Promise.reject(
        new NpiApiError({
          code: "TOOLING_LIST_PREFERENCE_CONFLICT",
          retryable: true,
          status: 409,
          title: "Saved view conflict",
          traceId: "trace-view-conflict",
          type: "https://npi.invalid/problems/tooling-list-preference-conflict",
        }),
      ),
    );
    renderWorkspace(dataSource({ loadPreference, savePreference }));
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Search Tooling"), "housing");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled();
    });
    await user.click(screen.getByRole("button", { name: "Save view" }));
    expect(
      await screen.findByText(
        "The saved view changed in another session. Reload it before saving again.",
      ),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Reload saved view" }));
    await waitFor(() => {
      expect(loadPreference).toHaveBeenCalledTimes(2);
    });
  });

  it("persists a successful personal view with optional column visibility", async () => {
    enableCommandSession();
    const savePreference = vi.fn<ToolingListDataSource["savePreference"]>(
      (_projectId, _viewId, request) =>
        Promise.resolve({
          ...toolingListPreference(),
          optimisticVersion: 2,
          preference: request.preference,
          snapshotHash: "e".repeat(64),
        }),
    );
    renderWorkspace(dataSource({ savePreference }));
    const user = userEvent.setup();

    await screen.findByRole("grid", { name: "Project Tooling List" });
    await user.click(screen.getByText("Columns"));
    await user.click(screen.getByRole("checkbox", { name: "Source" }));
    await user.type(screen.getByLabelText("Search Tooling"), " housing ");
    await user.click(screen.getByRole("button", { name: "Save view" }));

    expect(
      await screen.findByText("Personal Tooling List view saved."),
    ).toBeVisible();
    expect(savePreference).toHaveBeenCalledOnce();
    expect(savePreference.mock.calls[0]?.[2].preference).toMatchObject({
      filter: { search: "housing" },
      hiddenColumns: ["source"],
    });
  });

  it("keeps selection across stable cursor pages and renders governed grouping", async () => {
    const rows = toolingListPage().items;
    const loadList = vi.fn<ToolingListDataSource["loadList"]>(
      (_projectId, filter, _pageSize, cursor) =>
        Promise.resolve(
          toolingListPage({
            filter,
            items: cursor ? rows.slice(1) : rows.slice(0, 1),
            nextCursor: cursor ? null : "cursor-page-2",
          }),
        ),
    );
    renderWorkspace(dataSource({ loadList }));
    const user = userEvent.setup();

    await screen.findByText("Front housing mould");
    await user.selectOptions(
      screen.getByLabelText("Group by"),
      "applicability_scope",
    );
    await user.click(screen.getByRole("button", { name: "Apply view" }));
    expect(await screen.findByText("Shared Part Revision scope")).toBeVisible();

    await user.click(
      screen.getByRole("checkbox", {
        name: "Select all objects on this page",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Connector insert mould")).toBeVisible();
    expect(screen.getByText("Single Part Revision scope")).toBeVisible();
    await user.click(
      screen.getByRole("checkbox", {
        name: "Select all objects on this page",
      }),
    );
    expect(screen.getByText("Selected objects: 2")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Previous page" }));
    expect(await screen.findByText("Front housing mould")).toBeVisible();
    expect(
      screen.getByRole("checkbox", {
        name: "Select Front housing mould",
      }),
    ).toBeChecked();
  });

  it("creates a complete filtered result package from the reviewed snapshot", async () => {
    enableCommandSession();
    const createExport = vi.fn<ToolingListDataSource["createExport"]>(() =>
      Promise.resolve({
        package: toolingExportPackage({
          expiresAt: "2099-08-10T10:00:00Z",
          generatedAt: "2099-08-10T09:00:00Z",
          mode: "filtered",
          objectRefs: [],
          querySnapshotHash: "c".repeat(64),
        }),
        replayed: false,
      }),
    );
    renderWorkspace(dataSource({ createExport }));
    const user = userEvent.setup();

    await screen.findByRole("grid", { name: "Project Tooling List" });
    await user.selectOptions(screen.getByLabelText("Export mode"), "filtered");
    await user.click(
      screen.getByRole("button", { name: "Export object package" }),
    );
    const review = screen.getByRole("dialog", {
      name: "Review Tooling object package export",
    });
    expect(review).toHaveTextContent("Complete filtered result");
    expect(review).toHaveTextContent("Exact filtered query snapshot");
    await user.click(
      within(review).getByRole("button", { name: "Create object package" }),
    );

    expect(await screen.findByText("Package created")).toBeVisible();
    expect(createExport.mock.calls[0]?.[1]).toEqual({
      filter: toolingListPage().filter,
      mode: "filtered",
      querySnapshotHash: "c".repeat(64),
    });
    await user.click(
      screen.getByRole("button", { name: "Dismiss package result" }),
    );
    expect(screen.queryByText("Package SHA-256")).not.toBeInTheDocument();
  });

  it("keeps export closed for read-only, unauthorized and empty results", async () => {
    renderWorkspace(
      dataSource({
        loadList: () =>
          Promise.resolve(
            toolingListPage({
              items: [],
              permissions: {
                canExport: false,
                exportUnavailableReason: "separate_export_authority_required",
                view: true,
              },
              totalCount: 0,
            }),
          ),
      }),
    );

    expect(
      await screen.findByText("No Tooling Masters match this view."),
    ).toBeVisible();
    expect(
      screen.getByText("Tooling List commands are read only in this session."),
    ).toBeVisible();
    expect(
      screen.getByText("Tooling List export is unavailable."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Export object package" }),
    ).toBeDisabled();
  });
});
