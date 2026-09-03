import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DataExchangeDataSource } from "../../src/api/data-exchange-data-source";
import DataExchangeRoute from "../../src/app/data-exchange-route";
import DataExchangeWorkspace from "../../src/pages/data-exchange-workspace";
import { renderWithLocale } from "../support/render";
import { workspace } from "./data-exchange-data-source.test";

function source(): DataExchangeDataSource {
  return {
    load: () =>
      Promise.resolve({
        ...workspace,
        capabilities: [
          {
            id: "project_portfolio.v1",
            mode: "report_export_profile",
            exportableHere: true,
            route: "/portfolio/projects",
          },
          {
            id: "controlled_print.v1",
            mode: "specialized_existing",
            exportableHere: false,
            route: "/projects/{projectId}/documents",
          },
        ],
      }),
    publishProfile: () => Promise.reject(new Error("not used")),
    createExport: () => Promise.reject(new Error("not used")),
    downloadExport: () => Promise.reject(new Error("not used")),
    publishPolicy: () => Promise.reject(new Error("not used")),
    createArchive: () => Promise.reject(new Error("not used")),
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
            catalog: {
              language: "en",
              messages: {},
              version: "4".repeat(64),
            },
            csrfToken: `csrf-${"a".repeat(48)}`,
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "manager@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  globalThis.localStorage.clear();
});

describe("Data Exchange workspace", () => {
  it("wires the administration route to the governed live workspace", () => {
    expect(DataExchangeRoute().type).toBe(DataExchangeWorkspace);
  });

  it("shows fixed catalog immutable export and explicit retention truth", async () => {
    renderWithLocale(
      <DataExchangeWorkspace dataSource={source()} />,
      "en",
      "/administration/data-exchange",
    );
    expect(
      await screen.findByRole("heading", { name: /Data Exchange/u }),
    ).toBeVisible();
    expect(screen.getByText("Routes enabled")).toBeVisible();
    expect(screen.getAllByText("project_portfolio.v1")[0]).toBeVisible();
    expect(screen.getByText("controlled_print.v1")).toBeVisible();
    expect(screen.getByText("data-exchange.zip")).toBeVisible();
    expect(
      screen.getByText(/No default policy or precedence is inferred/u),
    ).toBeVisible();
    expect(screen.getByText(/Retain until/u)).toBeVisible();
    expect(screen.queryByText(/production endpoint/iu)).not.toBeInTheDocument();
  });

  it.each([
    ["zh", "数据交换", "路由已启用"],
    ["zh-TW", "資料交換", "路由已啟用"],
  ] as const)(
    "renders direct %s translations",
    async (locale, title, status) => {
      renderWithLocale(
        <DataExchangeWorkspace dataSource={source()} />,
        locale,
        "/administration/data-exchange",
      );
      expect(
        await screen.findByRole("heading", { name: new RegExp(title, "u") }),
      ).toBeVisible();
      expect(screen.getByText(status)).toBeVisible();
    },
  );

  it("shows empty and fault truth without a fake success", async () => {
    const empty: DataExchangeDataSource = {
      ...source(),
      load: () =>
        Promise.resolve({
          ...workspace,
          capabilities: [],
          profiles: [],
          exports: [],
          retentionPolicies: [],
          archiveRecords: [],
        }),
    };
    const { unmount } = renderWithLocale(
      <DataExchangeWorkspace dataSource={empty} />,
      "en",
      "/administration/data-exchange",
    );
    expect(
      await screen.findByText("No export profiles are published."),
    ).toBeVisible();
    expect(
      screen.getByText("No report packages have been created."),
    ).toBeVisible();
    unmount();
    renderWithLocale(
      <DataExchangeWorkspace
        dataSource={{
          ...source(),
          load: () => Promise.reject(new Error("offline")),
        }}
      />,
      "en",
      "/administration/data-exchange",
    );
    expect(
      await screen.findByRole("heading", {
        name: "Data Exchange workspace unavailable",
      }),
    ).toBeVisible();
  });

  it("executes only the fixed profile, package, policy and archive commands", async () => {
    enableCommandSession();
    const publishProfile = vi.fn(() => Promise.resolve(workspace.profiles[0]!));
    const createExport = vi.fn(() => Promise.resolve(workspace.exports[0]!));
    const downloadExport = vi.fn(() => Promise.resolve(new Blob(["zip"])));
    const publishPolicy = vi.fn(() =>
      Promise.resolve(workspace.retentionPolicies[0]!),
    );
    const createArchive = vi.fn(() =>
      Promise.resolve(workspace.archiveRecords[0]!),
    );
    const load = vi.fn(() => Promise.resolve(workspace));
    const user = userEvent.setup();

    renderWithLocale(
      <DataExchangeWorkspace
        dataSource={{
          load,
          publishProfile,
          createExport,
          downloadExport,
          publishPolicy,
          createArchive,
        }}
      />,
      "en",
      "/administration/data-exchange",
    );
    Object.defineProperties(globalThis.URL, {
      createObjectURL: {
        configurable: true,
        value: vi.fn(() => "blob:data-exchange"),
      },
      revokeObjectURL: { configurable: true, value: vi.fn() },
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const publishProfileButton = await screen.findByRole("button", {
      name: "Publish profile",
    });
    await waitFor(() => {
      expect(publishProfileButton).toBeEnabled();
    });
    await user.selectOptions(screen.getByLabelText("Dataset"), "kpi_trends.v1");
    await user.clear(screen.getByLabelText("Maximum rows"));
    await user.type(screen.getByLabelText("Maximum rows"), "250");
    await user.clear(screen.getByLabelText("From month"));
    await user.type(screen.getByLabelText("From month"), "2026-02");
    await user.click(publishProfileButton);
    await waitFor(() => {
      expect(publishProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          datasetId: "kpi_trends.v1",
          maxRows: 250,
          query: { fromMonth: "2026-02", toMonth: "2026-12" },
        }),
        expect.objectContaining({ csrfToken: `csrf-${"a".repeat(48)}` }),
      );
    });

    await user.click(screen.getByRole("button", { name: "Create package" }));
    await waitFor(() => {
      expect(createExport).toHaveBeenCalledWith(
        workspace.profiles[0],
        expect.objectContaining({ csrfToken: `csrf-${"a".repeat(48)}` }),
      );
    });
    await user.click(screen.getByRole("button", { name: "Download" }));
    await waitFor(() => {
      expect(downloadExport).toHaveBeenCalledWith(
        workspace.exports[0],
        expect.objectContaining({ csrfToken: `csrf-${"a".repeat(48)}` }),
      );
    });

    await user.selectOptions(
      screen.getByLabelText("Scope"),
      "customer_reference",
    );
    await user.type(
      await screen.findByLabelText("Scope reference"),
      "customer-reference-01",
    );
    await user.click(screen.getByRole("button", { name: "Publish policy" }));
    await waitFor(() => {
      expect(publishPolicy).toHaveBeenCalledWith(
        expect.objectContaining({
          scope: "customer_reference",
          scopeReference: "customer-reference-01",
        }),
        expect.objectContaining({ csrfToken: `csrf-${"a".repeat(48)}` }),
      );
    });

    await user.selectOptions(
      screen.getByLabelText("Source kind"),
      "file_revision",
    );
    await user.type(
      screen.getByLabelText("Source ID"),
      "66666666-6666-4666-8666-666666666666",
    );
    await user.type(screen.getByLabelText("Source hash"), "2".repeat(64));
    await user.click(
      screen.getByRole("button", { name: "Create archive record" }),
    );
    await waitFor(() => {
      expect(createArchive).toHaveBeenCalledWith(
        expect.objectContaining({
          sourceKind: "file_revision",
          sourceId: "66666666-6666-4666-8666-666666666666",
          sourceHash: "2".repeat(64),
          policyId: workspace.retentionPolicies[0]?.globalId,
        }),
        expect.objectContaining({ csrfToken: `csrf-${"a".repeat(48)}` }),
      );
    });
    expect(load.mock.calls.length).toBeGreaterThanOrEqual(5);
  });
});
