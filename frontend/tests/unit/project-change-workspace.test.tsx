import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChangeControlDataSource } from "../../src/api/change-control-data-source";
import { NpiApiError } from "../../src/api/http";
import type { ReportWorkspaceDirty } from "../../src/app/workspace-navigation";
import { ProjectChangeWorkspace } from "../../src/pages/project-change-workspace";
import {
  changeControlIds,
  engineeringChangeCommandResult,
  engineeringChangeDetail,
  engineeringChangeList,
  engineeringChangeSummaryReceipt,
} from "../support/change-control-fixture";
import { renderWithLocale } from "../support/render";

function source(
  overrides: Partial<ChangeControlDataSource> = {},
): ChangeControlDataSource {
  return {
    loadChanges: () => Promise.resolve(engineeringChangeList()),
    loadChange: () => Promise.resolve(engineeringChangeDetail()),
    createChange: () =>
      Promise.resolve(
        engineeringChangeCommandResult("engineering_change.create"),
      ),
    reviseChange: () =>
      Promise.resolve(
        engineeringChangeCommandResult("engineering_change.revise"),
      ),
    closeChange: () =>
      Promise.resolve(
        engineeringChangeCommandResult("engineering_change.close"),
      ),
    requestImplementationSummary: () =>
      Promise.resolve(engineeringChangeSummaryReceipt()),
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
            catalog: {
              language: "en",
              messages: {},
              version: "4".repeat(64),
            },
            csrfToken: "change-control-csrf-token-fixture-0001",
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

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Project Change Control workspace", () => {
  it("renders one Project-contained change, exact impact matrix and read-only ERP truth", async () => {
    renderWithLocale(
      <ProjectChangeWorkspace
        dataSource={source()}
        projectId={changeControlIds.project}
      />,
    );

    expect(
      (await screen.findAllByText("Gate-safe material substitution"))[0],
    ).toBeVisible();
    const matrix = await screen.findByRole("table");
    expect(within(matrix).getAllByRole("row")).toHaveLength(13);
    expect(screen.getByText("ERP formal observation")).toBeVisible();
    expect(screen.getByText("Engineering Change Request")).toBeVisible();
    expect(screen.getByText("ECR-0001")).toBeVisible();
    expect(screen.getByText("Approved")).toBeVisible();
    expect(screen.getByText("2 affected areas")).toBeVisible();
  });

  it("keeps an empty or unauthorized collection bounded", async () => {
    const rendered = renderWithLocale(
      <ProjectChangeWorkspace
        dataSource={source({
          loadChanges: () =>
            Promise.resolve(engineeringChangeList({ items: [] })),
        })}
        projectId={changeControlIds.project}
      />,
    );
    expect(
      await screen.findByText(
        "No engineering changes have been recorded for this Project.",
      ),
    ).toBeVisible();

    rendered.unmount();
    renderWithLocale(
      <ProjectChangeWorkspace
        dataSource={source({
          loadChanges: () =>
            Promise.resolve(
              engineeringChangeList({
                items: [],
                permissions: {
                  canView: false,
                  canCreate: false,
                  canRevise: false,
                  canLinkFormalObservation: false,
                  canClose: false,
                },
              }),
            ),
        })}
        projectId={changeControlIds.project}
      />,
    );
    expect(
      await screen.findByText(
        "Project membership and backend permission are required.",
      ),
    ).toBeVisible();
  });

  it("registers an unsaved create editor and exposes all fixed impact categories", async () => {
    enableCommandSession();
    const reportWorkspaceDirty = vi.fn<ReportWorkspaceDirty>();
    const user = userEvent.setup();
    renderWithLocale(
      <ProjectChangeWorkspace
        dataSource={source()}
        projectId={changeControlIds.project}
        reportWorkspaceDirty={reportWorkspaceDirty}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "New engineering change" }),
    );
    expect(
      screen.getByRole("heading", { name: "New engineering change" }),
    ).toBeVisible();
    expect(screen.getAllByRole("group")).toHaveLength(12);
    await waitFor(() => {
      expect(reportWorkspaceDirty).toHaveBeenCalledWith(
        expect.objectContaining({
          objectIdentity: `${changeControlIds.project}:engineering-change`,
        }),
      );
    });
  });

  it("reviews and queues the exact implementation summary with session authority", async () => {
    enableCommandSession();
    const baseline = source();
    const requestImplementationSummary = vi.fn(
      (...args: Parameters<typeof baseline.requestImplementationSummary>) =>
        baseline.requestImplementationSummary(...args),
    );
    const user = userEvent.setup();
    renderWithLocale(
      <ProjectChangeWorkspace
        dataSource={source({ requestImplementationSummary })}
        projectId={changeControlIds.project}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Request implementation summary",
      }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Review engineering change command",
    });
    await user.click(
      within(dialog).getByRole("button", {
        name: "Request implementation summary",
      }),
    );
    await waitFor(() => {
      expect(requestImplementationSummary).toHaveBeenCalledTimes(1);
    });
    expect(requestImplementationSummary.mock.calls[0]?.[0]).toBe(
      changeControlIds.project,
    );
    expect(requestImplementationSummary.mock.calls[0]?.[1].snapshotHash).toBe(
      "4".repeat(64),
    );
    expect(await screen.findByText("queued")).toBeVisible();
  });

  it("classifies an exact conflict without displaying unverified data", async () => {
    renderWithLocale(
      <ProjectChangeWorkspace
        dataSource={source({
          loadChanges: () =>
            Promise.reject(
              new NpiApiError({
                code: "ENGINEERING_CHANGE_CONFLICT",
                retryable: false,
                status: 409,
                title: "Controlled conflict",
                traceId: "trace-change-conflict",
                type: "urn:npi:problem:engineering-change-conflict",
              }),
            ),
        })}
        projectId={changeControlIds.project}
      />,
    );
    expect(
      await screen.findByText(
        "The engineering change changed before this action completed",
      ),
    ).toBeVisible();
    expect(screen.queryByText("Gate-safe material substitution")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Reload latest data" }),
    ).toBeVisible();
  });

  it("renders controlled Chinese translations without mixed ordinary English", async () => {
    renderWithLocale(
      <ProjectChangeWorkspace
        dataSource={source()}
        projectId={changeControlIds.project}
      />,
      "zh",
    );
    expect(await screen.findByText("变更控制")).toBeVisible();
    expect(screen.getByText("影响评估矩阵")).toBeVisible();
    expect(screen.queryByText("Change control")).toBeNull();
  });
});
