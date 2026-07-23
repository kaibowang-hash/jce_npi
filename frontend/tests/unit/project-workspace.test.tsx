import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ProjectCockpitDataSource } from "../../src/api/project-data-source";
import {
  NpiApiError,
  NpiTransportError,
  type ProblemDetails,
} from "../../src/api/http";
import type {
  ProjectDomainWorkItemsDataSource,
  ProjectWorkContextDataSource,
} from "../../src/api/project-work-data-source";
import { ProjectWorkRequestCancelledError } from "../../src/api/project-work-data-source";
import type {
  ProjectCockpitViewModel,
  ProjectWorkContextViewModel,
} from "../../src/domain/view-models";
import ProjectPage from "../../src/pages/project-page";
import { projectCockpitFixture } from "../support/project-fixture";
import {
  projectDomainWorkItemsFixture,
  projectWorkCockpitFixture,
  projectWorkContextFixture,
} from "../support/project-work-fixture";
import { renderWithLocale } from "../support/render";

function renderWorkspace({
  cockpit = projectWorkCockpitFixture(),
  contextDataSource,
  domainWorkItemsDataSource,
}: {
  cockpit?: ProjectCockpitViewModel;
  contextDataSource?: ProjectWorkContextDataSource;
  domainWorkItemsDataSource?: ProjectDomainWorkItemsDataSource;
} = {}): void {
  const dataSource: ProjectCockpitDataSource = {
    load: vi.fn(() => Promise.resolve(cockpit)),
  };
  renderWithLocale(
    <ProjectPage
      contextDataSource={contextDataSource}
      dataSource={dataSource}
      domainWorkItemsDataSource={domainWorkItemsDataSource}
      globalId={cockpit.project.globalId}
      navigate={vi.fn()}
    />,
  );
}

function problem(status: number, code: string, retryable = false): NpiApiError {
  const value: ProblemDetails = {
    type: `urn:npi:problem:${code.toLowerCase()}`,
    title: `Controlled ${code} response`,
    status,
    code,
    traceId: `trace-${code.toLowerCase()}`,
    retryable,
  };
  return new NpiApiError(value);
}

describe("live Project workspace tabs", () => {
  it("preserves Overview as the default and does not prefetch protected tab resources", async () => {
    const contextLoad = vi.fn<ProjectWorkContextDataSource["load"]>(() =>
      Promise.resolve(projectWorkContextFixture()),
    );
    const workItemsLoad = vi.fn<ProjectDomainWorkItemsDataSource["load"]>(() =>
      Promise.resolve(projectDomainWorkItemsFixture()),
    );
    renderWorkspace({
      contextDataSource: { load: contextLoad },
      domainWorkItemsDataSource: { load: workItemsLoad },
    });

    expect(
      await screen.findByRole("tab", { name: "Overview" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("tablist", { name: "Project workspace sections" }),
    ).toBeVisible();
    expect(screen.getByText("Synthetic feasibility shell")).toBeVisible();
    expect(contextLoad).not.toHaveBeenCalled();
    expect(workItemsLoad).not.toHaveBeenCalled();
  });

  it("lazy-loads one work context for the Team and Plan tabs and exposes no write command", async () => {
    const user = userEvent.setup();
    const contextLoad = vi.fn<ProjectWorkContextDataSource["load"]>(() =>
      Promise.resolve(projectWorkContextFixture()),
    );
    renderWorkspace({ contextDataSource: { load: contextLoad } });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    expect(
      (await screen.findAllByText("engineering.lead@example.invalid"))[0],
    ).toBeVisible();
    expect(
      screen.getByText("Project roles do not grant Gate approval authority."),
    ).toBeVisible();
    expect(screen.getByText("project.delivery")).toBeVisible();
    const responsibilityTable = screen
      .getByText("Responsibility key")
      .closest("table");
    expect(responsibilityTable).not.toBeNull();
    if (!responsibilityTable) {
      throw new Error("The responsibility table was not rendered.");
    }
    expect(
      within(responsibilityTable)
        .getAllByRole("columnheader")
        .map((header) => header.textContent),
    ).toEqual([
      "Scope",
      "Responsibility key",
      "Role key",
      "User",
      "Responsibility",
    ]);
    for (const row of responsibilityTable.querySelectorAll("tbody tr")) {
      expect(row.querySelectorAll("td")).toHaveLength(5);
    }
    expect(contextLoad).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("tab", { name: "Plan" }));
    expect(await screen.findByText("Synthetic tooling launch")).toBeVisible();
    expect(screen.getAllByText("2 days late")[0]).toBeVisible();
    expect(screen.getByText("Critical task")).toBeVisible();
    expect(
      screen.getByText(
        "Critical task is a recorded plan indicator, not a computed critical path.",
      ),
    ).toBeVisible();
    expect(contextLoad).toHaveBeenCalledOnce();
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(0);
  });

  it("loads the separate Project Domain WorkItem endpoint and sends filter changes as bounded queries", async () => {
    const user = userEvent.setup();
    const workItemsLoad = vi.fn<ProjectDomainWorkItemsDataSource["load"]>(() =>
      Promise.resolve(projectDomainWorkItemsFixture()),
    );
    renderWorkspace({
      domainWorkItemsDataSource: { load: workItemsLoad },
    });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(screen.getByRole("tab", { name: "Work items" }));
    expect(
      await screen.findByText("Synthetic interface dimension issue"),
    ).toBeVisible();
    expect(screen.getAllByText("Decision request")[0]).toBeVisible();
    expect(screen.getByText("Blocking")).toBeVisible();
    const inspector = screen.getByRole("complementary", {
      name: "Domain work item details",
    });
    expect(
      [...inspector.querySelectorAll("dt")].filter(
        (label) => label.textContent === "Owner",
      ),
    ).toHaveLength(1);
    expect(workItemsLoad).toHaveBeenCalledWith(
      projectWorkCockpitFixture().project.globalId,
      4,
      { limit: 100 },
      expect.any(AbortSignal),
    );

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Kind" }),
      "issue",
    );
    await screen.findByText("Synthetic interface dimension issue");
    expect(workItemsLoad).toHaveBeenLastCalledWith(
      projectWorkCockpitFixture().project.globalId,
      4,
      { kind: "issue", limit: 100 },
      expect.any(AbortSignal),
    );
    expect(
      within(screen.getByRole("combobox", { name: "Kind" })).getByRole(
        "option",
        { name: "Action item" },
      ),
    ).toHaveValue("action");

    await user.type(
      screen.getByRole("textbox", { name: "Owner email" }),
      "external.owner@example.invalid",
    );
    await user.click(
      screen.getByRole("button", { name: "Apply owner filter" }),
    );
    await waitFor(() => {
      expect(workItemsLoad).toHaveBeenLastCalledWith(
        projectWorkCockpitFixture().project.globalId,
        4,
        {
          kind: "issue",
          limit: 100,
          ownerUserId: "external.owner@example.invalid",
        },
        expect.any(AbortSignal),
      );
    });
  });

  it("shows complete substitutions from both the original holder and substitute perspectives", async () => {
    const user = userEvent.setup();
    renderWorkspace({
      contextDataSource: {
        load: vi.fn(() => Promise.resolve(projectWorkContextFixture())),
      },
    });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    const team = await screen.findByLabelText("Team members");
    await user.click(
      within(team)
        .getByText("quality.lead@example.invalid")
        .closest("tr") as HTMLElement,
    );
    let inspector = screen.getByRole("complementary", {
      name: "Team member details",
    });
    expect(within(inspector).getByText("Original member")).toBeVisible();
    expect(
      within(inspector).getAllByText("quality.lead@example.invalid")[0],
    ).toBeVisible();
    expect(within(inspector).getByText("Substitute member")).toBeVisible();
    expect(
      within(inspector).getAllByText("tooling.lead@example.invalid")[0],
    ).toBeVisible();
    expect(within(inspector).getAllByText("quality.lead")[0]).toBeVisible();
    expect(within(inspector).getByText("Aug 1, 2026")).toBeVisible();
    expect(within(inspector).getByText("Aug 15, 2026")).toBeVisible();

    await user.click(
      within(team)
        .getByText("tooling.lead@example.invalid")
        .closest("tr") as HTMLElement,
    );
    inspector = screen.getByRole("complementary", {
      name: "Team member details",
    });
    expect(within(inspector).getByText("quality.lead")).toBeVisible();
    expect(
      within(inspector).getAllByText("quality.lead@example.invalid")[0],
    ).toBeVisible();
    expect(
      within(inspector).getAllByText("tooling.lead@example.invalid")[0],
    ).toBeVisible();
  });

  it("fails closed when Project work resources do not match the cockpit version", async () => {
    const user = userEvent.setup();
    const context = projectWorkContextFixture();
    const workItems = projectDomainWorkItemsFixture();
    renderWorkspace({
      contextDataSource: {
        load: vi.fn(() => Promise.resolve({ ...context, projectVersion: 5 })),
      },
      domainWorkItemsDataSource: {
        load: vi.fn(() => Promise.resolve({ ...workItems, projectVersion: 5 })),
      },
    });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "The project work context response could not be used safely",
      }),
    ).toBeVisible();
    expect(screen.queryByText("engineering.lead@example.invalid")).toBeNull();

    await user.click(screen.getByRole("tab", { name: "Work items" }));
    expect(
      await screen.findByRole("heading", {
        name: "The domain work item response could not be used safely",
      }),
    ).toBeVisible();
    expect(
      screen.queryByText("Synthetic interface dimension issue"),
    ).toBeNull();
  });

  it("uses bounded next and previous cursor requests without mixing pages", async () => {
    const user = userEvent.setup();
    const fixture = projectDomainWorkItemsFixture();
    const firstPage = {
      ...fixture,
      items: fixture.items.slice(0, 2),
      nextCursor: "cursor-page-2",
    };
    const secondPage = {
      ...fixture,
      items: fixture.items.slice(2),
      nextCursor: null,
    };
    const workItemsLoad = vi.fn<ProjectDomainWorkItemsDataSource["load"]>(
      (_projectId, _expectedProjectVersion, query) =>
        Promise.resolve(query.cursor ? secondPage : firstPage),
    );
    renderWorkspace({
      domainWorkItemsDataSource: { load: workItemsLoad },
    });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(screen.getByRole("tab", { name: "Work items" }));
    expect(
      await screen.findByText("Synthetic resin availability risk"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("navigation", { name: "Domain work item pages" }),
    ).toBeVisible();
    expect(screen.getByText("Page 1")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(
      await screen.findByText("Synthetic drawing correction"),
    ).toBeVisible();
    expect(screen.queryByText("Synthetic resin availability risk")).toBeNull();
    expect(screen.getByText("Page 2")).toBeVisible();
    expect(workItemsLoad).toHaveBeenLastCalledWith(
      projectWorkCockpitFixture().project.globalId,
      4,
      { cursor: "cursor-page-2", limit: 100 },
      expect.any(AbortSignal),
    );
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Previous page" }));
    expect(
      await screen.findByText("Synthetic resin availability risk"),
    ).toBeVisible();
    expect(workItemsLoad).toHaveBeenLastCalledWith(
      projectWorkCockpitFixture().project.globalId,
      4,
      { limit: 100 },
      expect.any(AbortSignal),
    );
    expect(screen.getByText("Page 1")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Synthetic drawing correction");
    await user.type(
      screen.getByRole("textbox", { name: "Owner email" }),
      "quality.lead@example.invalid",
    );
    await user.click(
      screen.getByRole("button", { name: "Apply owner filter" }),
    );
    await screen.findByText("Synthetic resin availability risk");
    expect(workItemsLoad).toHaveBeenLastCalledWith(
      projectWorkCockpitFixture().project.globalId,
      4,
      {
        limit: 100,
        ownerUserId: "quality.lead@example.invalid",
      },
      expect.any(AbortSignal),
    );
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
    expect(screen.getByText("Page 1")).toBeVisible();
  });

  it("fails closed on a repeated or cyclic next cursor", async () => {
    const user = userEvent.setup();
    const fixture = projectDomainWorkItemsFixture();
    const workItemsLoad = vi.fn<ProjectDomainWorkItemsDataSource["load"]>(
      (_projectId, _expectedProjectVersion, query) =>
        Promise.resolve({
          ...fixture,
          items: query.cursor
            ? fixture.items.slice(2)
            : fixture.items.slice(0, 2),
          nextCursor: "cursor-page-2",
        }),
    );
    renderWorkspace({
      domainWorkItemsDataSource: { load: workItemsLoad },
    });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(screen.getByRole("tab", { name: "Work items" }));
    await screen.findByText("Synthetic resin availability risk");
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(
      await screen.findByRole("heading", {
        name: "The domain work item response could not be used safely",
      }),
    ).toBeVisible();
    expect(screen.queryByText("Synthetic drawing correction")).toBeNull();
  });

  it("aborts an in-flight cursor request when the cockpit refreshes", async () => {
    const user = userEvent.setup();
    const cockpit = projectWorkCockpitFixture();
    const dataSource: ProjectCockpitDataSource = {
      load: vi.fn(() => Promise.resolve(cockpit)),
    };
    const fixture = projectDomainWorkItemsFixture();
    let cursorSignal: AbortSignal | undefined;
    const workItemsLoad = vi.fn<ProjectDomainWorkItemsDataSource["load"]>(
      (_projectId, _expectedProjectVersion, query, signal) => {
        if (!query.cursor) {
          return Promise.resolve({
            ...fixture,
            items: fixture.items.slice(0, 2),
            nextCursor: "cursor-page-2",
          });
        }
        cursorSignal = signal;
        return new Promise((_resolve, reject) => {
          signal.addEventListener(
            "abort",
            () => {
              reject(new ProjectWorkRequestCancelledError());
            },
            { once: true },
          );
        });
      },
    );
    renderWithLocale(
      <ProjectPage
        dataSource={dataSource}
        domainWorkItemsDataSource={{ load: workItemsLoad }}
        globalId={cockpit.project.globalId}
        navigate={vi.fn()}
      />,
    );

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(screen.getByRole("tab", { name: "Work items" }));
    await screen.findByText("Synthetic resin availability risk");
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => {
      expect(cursorSignal).toBeDefined();
    });
    globalThis.dispatchEvent(new Event("npi:refresh-project"));
    await waitFor(() => {
      expect(cursorSignal?.aborted).toBe(true);
    });
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    });
  });

  it("remounts the cockpit on a refreshed Project version and reloads matching resources", async () => {
    const user = userEvent.setup();
    const cockpitVersion4 = projectWorkCockpitFixture();
    const cockpitVersion5 = projectCockpitFixture({ version: 5 });
    let cockpitIndex = 0;
    const dataSource: ProjectCockpitDataSource = {
      load: vi.fn(() =>
        Promise.resolve(
          cockpitIndex++ === 0 ? cockpitVersion4 : cockpitVersion5,
        ),
      ),
    };
    let contextIndex = 0;
    const contextDataSource: ProjectWorkContextDataSource = {
      load: vi.fn(() => {
        const context = projectWorkContextFixture();
        const projectVersion = contextIndex++ === 0 ? 4 : 5;
        return Promise.resolve({ ...context, projectVersion });
      }),
    };
    renderWithLocale(
      <ProjectPage
        contextDataSource={contextDataSource}
        dataSource={dataSource}
        globalId={cockpitVersion4.project.globalId}
        navigate={vi.fn()}
      />,
    );

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    await screen.findAllByText("engineering.lead@example.invalid");

    globalThis.dispatchEvent(new Event("npi:refresh-project"));
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    });
    expect(screen.queryByText("engineering.lead@example.invalid")).toBeNull();

    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    await screen.findAllByText("engineering.lead@example.invalid");
    expect(contextDataSource.load).toHaveBeenCalledTimes(2);
    expect(contextDataSource.load).toHaveBeenNthCalledWith(
      1,
      cockpitVersion4.project.globalId,
      4,
      expect.any(AbortSignal),
    );
    expect(contextDataSource.load).toHaveBeenNthCalledWith(
      2,
      cockpitVersion5.project.globalId,
      5,
      expect.any(AbortSignal),
    );
  });

  it("announces loading and then renders the validated work context", async () => {
    const user = userEvent.setup();
    let resolveContext:
      | ((context: ProjectWorkContextViewModel) => void)
      | undefined;
    const contextDataSource: ProjectWorkContextDataSource = {
      load: vi.fn(
        () =>
          new Promise<ProjectWorkContextViewModel>((resolve) => {
            resolveContext = resolve;
          }),
      ),
    };
    renderWorkspace({ contextDataSource });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    expect(
      screen.getByRole("status", { name: "Loading project work context" }),
    ).toHaveAttribute("aria-busy", "true");

    await act(async () => {
      resolveContext?.(projectWorkContextFixture());
      await Promise.resolve();
    });
    expect(
      (await screen.findAllByText("engineering.lead@example.invalid"))[0],
    ).toBeVisible();
  });

  it("renders the honest uninitialized empty state", async () => {
    const user = userEvent.setup();
    const fixture = projectWorkContextFixture();
    const emptyContext: ProjectWorkContextViewModel = {
      ...fixture,
      initialized: false,
      workPolicyRef: null,
      members: [],
      roleAssignments: [],
      substitutions: [],
      raciAssignments: [],
      wbsItems: [],
      dependencies: [],
      baselines: [],
      baselineComparison: null,
    };
    renderWorkspace({
      contextDataSource: {
        load: vi.fn(() => Promise.resolve(emptyContext)),
      },
    });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    expect(
      await screen.findByText(
        "Team, responsibility, and plan data have not been initialized.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText("No team members are assigned to this project."),
    ).toBeVisible();
    expect(
      screen.getByText(
        "No responsibility assignments are configured for this project.",
      ),
    ).toBeVisible();
  });

  it("keeps protected data hidden for a non-retryable 403 response", async () => {
    const user = userEvent.setup();
    renderWorkspace({
      contextDataSource: {
        load: vi.fn(() =>
          Promise.reject(problem(403, "PROJECT_ACCESS_DENIED")),
        ),
      },
    });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Project work context is unavailable",
      }),
    ).toBeVisible();
    expect(screen.getByText("trace-project_access_denied")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.queryByText("engineering.lead@example.invalid")).toBeNull();
  });

  it("offers retry for a 409 response and recovers without mixing stale data", async () => {
    const user = userEvent.setup();
    const contextLoad = vi
      .fn<ProjectWorkContextDataSource["load"]>()
      .mockRejectedValueOnce(problem(409, "VERSION_CONFLICT"))
      .mockResolvedValueOnce(projectWorkContextFixture());
    renderWorkspace({ contextDataSource: { load: contextLoad } });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Project work context is unavailable",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      (await screen.findAllByText("engineering.lead@example.invalid"))[0],
    ).toBeVisible();
    expect(contextLoad).toHaveBeenCalledTimes(2);
  });

  it("keeps the Project workspace read-only when contribution is denied", async () => {
    const cockpit = projectWorkCockpitFixture();
    renderWorkspace({
      cockpit: {
        ...cockpit,
        permissions: {
          ...cockpit.permissions,
          canContribute: false,
        },
      },
    });

    expect(
      await screen.findByText(
        "You have view-only access. Project commands are not available in this cockpit.",
      ),
    ).toBeVisible();
    expect(screen.getByText("View only")).toBeVisible();
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(0);
  });

  it("supports arrow, Home, and End movement with a single tab stop", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    const overview = await screen.findByRole("tab", { name: "Overview" });
    overview.focus();
    await user.keyboard("{ArrowRight}");
    expect(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    ).toHaveFocus();
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Work items" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(overview).toHaveFocus();
    expect(
      screen.getAllByRole("tab").filter((tab) => tab.tabIndex === 0),
    ).toHaveLength(1);
  });

  it("fails closed when the work-context response cannot be trusted", async () => {
    const user = userEvent.setup();
    const contextDataSource: ProjectWorkContextDataSource = {
      load: vi.fn(() =>
        Promise.reject(
          new NpiTransportError(
            "invalid_response",
            "trace-project-work-invalid",
            "trace",
          ),
        ),
      ),
    };
    renderWorkspace({ contextDataSource });

    await screen.findByRole("tab", { name: "Overview" });
    await user.click(
      screen.getByRole("tab", { name: "Team and responsibilities" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "The project work context response could not be used safely",
      }),
    ).toBeVisible();
    expect(screen.getByText("trace-project-work-invalid")).toBeVisible();
    expect(screen.queryByText("engineering.lead@example.invalid")).toBeNull();
  });
});
