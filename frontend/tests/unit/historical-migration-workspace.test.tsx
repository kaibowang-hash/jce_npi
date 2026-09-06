import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  HistoricalMigrationDataSource,
  HistoricalMigrationJob,
  HistoricalMigrationPreview,
  HistoricalMigrationWorkspace as Workspace,
} from "../../src/api/historical-migration-data-source";
import HistoricalMigrationRoute from "../../src/app/historical-migration-route";
import HistoricalMigrationWorkspace from "../../src/pages/historical-migration-workspace";
import { renderWithLocale } from "../support/render";

const workspace: Workspace = {
  schemaVersion: "historical-migration-rehearsal.v1",
  mode: "non_production_rehearsal",
  executionEnabled: false,
  productionContact: false,
  previews: [
    {
      schemaVersion: "historical-migration-preview.v1",
      globalId: "11111111-1111-4111-8111-111111111111",
      bundleId: "22222222-2222-4222-8222-222222222222",
      manifestHash: "a".repeat(64),
      sourceSha256: "b".repeat(64),
      sourceFileRevisionGlobalId: "33333333-3333-4333-8333-333333333333",
      sourceFileOptimisticVersion: 1,
      tenantId: "tenant-a",
      version: 1,
      summary: { create: 1, link: 1, skip: 0, blocked: 1 },
      rows: [
        {
          family: "project",
          ordinal: 2,
          sourceKey: "project-01",
          sourceHash: "c".repeat(64),
          action: "blocked",
          targetGlobalId: null,
          targetVersion: null,
          targetSnapshotHash: null,
          differences: [
            { field: "title", sourceValue: "old", targetValue: "new" },
          ],
          findings: [
            {
              code: "target_difference",
              field: "project",
              message:
                "The existing Project differs from the historical source.",
            },
          ],
        },
      ],
      createdByUserId: "manager@example.invalid",
      createdAt: "2026-09-03T08:00:00Z",
      requestId: "44444444-4444-4444-8444-444444444444",
      traceId: "trace-preview",
      snapshotHash: "d".repeat(64),
    },
  ],
  jobs: [],
};

function dataSource(): HistoricalMigrationDataSource {
  const [preview] = workspace.previews;
  return {
    load: () => Promise.resolve(workspace),
    createPreview: () =>
      preview
        ? Promise.resolve(preview)
        : Promise.reject(new Error("fixture missing preview")),
    execute: () => Promise.reject(new Error("disabled")),
    loadJob: () => Promise.reject(new Error("not used")),
    createCorrection: () => Promise.reject(new Error("not used")),
    downloadCorrection: () => Promise.reject(new Error("not used")),
    reconcile: () => Promise.reject(new Error("not used")),
    rollback: () => Promise.reject(new Error("not used")),
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
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  globalThis.localStorage.clear();
});

describe("historical migration workspace", () => {
  it("wires the administration route to the governed live workspace", () => {
    expect(HistoricalMigrationRoute().type).toBe(HistoricalMigrationWorkspace);
  });

  it("shows immutable preview and explicit non-production blocked truth without raw differences", async () => {
    renderWithLocale(
      <HistoricalMigrationWorkspace dataSource={dataSource()} />,
      "en",
      "/administration/migration-rehearsal",
    );
    expect(
      await screen.findByRole("heading", {
        name: /Historical migration rehearsal/u,
      }),
    ).toBeVisible();
    expect(screen.getByText("Preview only")).toBeVisible();
    expect(screen.getByText("Non-production rehearsal")).toBeVisible();
    expect(
      screen.getByText(
        "The existing Project differs from the historical source.",
      ),
    ).toBeVisible();
    expect(screen.getByText("title")).toBeVisible();
    expect(screen.queryByText("old")).not.toBeInTheDocument();
    expect(screen.queryByText("new")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Execute rehearsal" }),
    ).toBeDisabled();
  });

  it("renders direct Chinese translations for the governed workspace", async () => {
    renderWithLocale(
      <HistoricalMigrationWorkspace dataSource={dataSource()} />,
      "zh",
      "/administration/migration-rehearsal",
    );
    expect(
      await screen.findByRole("heading", { name: /历史迁移演练/u }),
    ).toBeVisible();
    expect(screen.getByText("仅预览")).toBeVisible();
    expect(screen.getByText("非生产演练")).toBeVisible();
  });

  it("runs the enabled preview, reconciliation, correction, and logical rollback controls", async () => {
    const [blockedPreview] = workspace.previews;
    if (!blockedPreview) throw new Error("fixture missing preview");
    const [baseRow] = blockedPreview.rows;
    if (!baseRow) throw new Error("fixture missing preview row");
    const readyPreview: HistoricalMigrationPreview = {
      ...blockedPreview,
      summary: { create: 1, link: 1, skip: 1, blocked: 0 },
      rows: [
        { ...baseRow, action: "create" as const },
        {
          ...baseRow,
          family: "tooling_mapping" as const,
          sourceKey: "tooling-01",
          action: "link" as const,
        },
        {
          ...baseRow,
          family: "file_index" as const,
          sourceKey: "file-01",
          action: "skip" as const,
        },
      ],
    };
    const completedJob: HistoricalMigrationJob = {
      schemaVersion: "historical-migration-job.v1",
      globalId: "55555555-5555-4555-8555-555555555555",
      batchGlobalId: readyPreview.bundleId,
      previewGlobalId: readyPreview.globalId,
      previewSnapshotHash: readyPreview.snapshotHash,
      state: "succeeded",
      optimisticVersion: 3,
      results: [
        {
          family: "project",
          sourceKey: "project-01",
          state: "created",
          targetGlobalId: "77777777-7777-4777-8777-777777777777",
        },
        {
          family: "tooling_mapping",
          sourceKey: "tooling-01",
          state: "linked",
        },
        { family: "file_index", sourceKey: "file-01", state: "skipped" },
        {
          family: "npi_reference",
          sourceKey: "reference-01",
          state: "failed_retryable",
          findingCodes: ["target_stale"],
        },
        {
          family: "job",
          sourceKey: "job-final",
          state: "failed_final",
        },
        { family: "job", sourceKey: "job-rollback", state: "rolled_back" },
        {
          family: "job",
          sourceKey: "job-denied",
          state: "rollback_denied",
        },
      ],
      queuedAt: "2026-09-03T08:01:00Z",
      updatedAt: "2026-09-03T08:02:00Z",
      actorUserId: "manager@example.invalid",
      requestId: "66666666-6666-4666-8666-666666666666",
      traceId: "trace-job",
      productionContact: false,
      correction: {
        schemaVersion: "historical-migration-correction.v1",
        jobGlobalId: "55555555-5555-4555-8555-555555555555",
        fileName: "historical-migration-correction.csv",
        sizeBytes: 16,
        sha256: "f".repeat(64),
        failedRowCount: 2,
        private: true,
      },
      snapshotHash: "e".repeat(64),
    };
    const enabledWorkspace: Workspace = {
      ...workspace,
      executionEnabled: true,
      previews: [readyPreview],
      jobs: [completedJob],
    };
    const execute = vi.fn(() => Promise.resolve(completedJob));
    const createCorrection = vi.fn(() => {
      const correction = completedJob.correction;
      return correction
        ? Promise.resolve(correction)
        : Promise.reject(new Error("fixture missing correction"));
    });
    const downloadCorrection = vi.fn(() =>
      Promise.resolve({
        blob: new Blob(["family,source_key"]),
        fileName: "historical-migration-correction.csv",
      }),
    );
    const reconcile = vi.fn(() => Promise.resolve(completedJob));
    const rollback = vi.fn(() => Promise.resolve(completedJob));
    const controlledSource: HistoricalMigrationDataSource = {
      load: vi.fn(() => Promise.resolve(enabledWorkspace)),
      createPreview: vi.fn(() => Promise.resolve(readyPreview)),
      execute,
      loadJob: vi.fn(() => Promise.resolve(completedJob)),
      createCorrection,
      downloadCorrection,
      reconcile,
      rollback,
    };
    enableCommandSession();
    const anchorClick = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const createObjectUrl = vi.fn(() => "blob:historical-migration");
    const revokeObjectUrl = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectUrl,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectUrl,
    });
    const user = userEvent.setup();
    renderWithLocale(
      <HistoricalMigrationWorkspace dataSource={controlledSource} />,
      "en",
      "/administration/migration-rehearsal",
    );

    const executeButton = await screen.findByRole("button", {
      name: "Execute rehearsal",
    });
    await waitFor(() => {
      expect(executeButton).toBeEnabled();
    });
    await user.click(executeButton);
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Rehearsal",
    );
    await user.click(
      screen.getByRole("button", { name: "Queue exact preview" }),
    );
    await waitFor(() => {
      expect(execute).toHaveBeenCalledOnce();
    });

    await user.click(screen.getByRole("button", { name: "Reconcile" }));
    await waitFor(() => {
      expect(reconcile).toHaveBeenCalledOnce();
    });
    await user.click(
      screen.getByRole("button", { name: "Create correction artifact" }),
    );
    await waitFor(() => {
      expect(createCorrection).toHaveBeenCalledOnce();
    });
    await user.click(
      screen.getByRole("button", { name: "Download correction artifact" }),
    );
    await waitFor(() => {
      expect(downloadCorrection).toHaveBeenCalledOnce();
    });
    expect(anchorClick).toHaveBeenCalledOnce();
    expect(createObjectUrl).toHaveBeenCalledOnce();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:historical-migration");

    await user.click(
      screen.getByRole("button", { name: "Evaluate logical rollback" }),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Check rollback",
    );
    await user.click(
      screen.getByRole("button", { name: "Record rollback decision" }),
    );
    await waitFor(() => {
      expect(rollback).toHaveBeenCalledOnce();
    });
  });
});
