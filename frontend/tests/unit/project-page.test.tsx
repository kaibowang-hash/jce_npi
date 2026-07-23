import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ProjectCockpitDataSource } from "../../src/api/project-data-source";
import {
  NpiApiError,
  NpiTransportError,
  type ProblemDetails,
} from "../../src/api/http";
import type { ProjectCockpitViewModel } from "../../src/domain/view-models";
import { I18nProvider } from "../../src/i18n/runtime";
import ProjectPage from "../../src/pages/project-page";
import { projectCockpitFixture } from "../support/project-fixture";
import { renderWithLocale } from "../support/render";

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

function resolvedDataSource(
  cockpit: ProjectCockpitViewModel,
): ProjectCockpitDataSource {
  return {
    load: vi.fn(() => Promise.resolve(cockpit)),
  };
}

function rejectedDataSource(error: Error): ProjectCockpitDataSource {
  return {
    load: vi.fn(() => Promise.reject(error)),
  };
}

describe("live Project cockpit states", () => {
  it("renders only validated live Project facts without fixture health, cost, or commands", async () => {
    const fixture = projectCockpitFixture();
    const dataSource = resolvedDataSource(fixture);
    renderWithLocale(
      <ProjectPage
        dataSource={dataSource}
        globalId={fixture.project.globalId}
        navigate={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("status", { name: "Loading project cockpit" }),
    ).toHaveAttribute("aria-busy", "true");
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /SYN-PROJECT-001 Synthetic project cockpit/,
      }),
    ).toBeVisible();
    expect(dataSource.load).toHaveBeenCalledOnce();
    expect(screen.getByText("SYNTHETIC-PROJECT-TEMPLATE")).toBeVisible();
    expect(screen.getByText("Synthetic feasibility shell")).toBeVisible();
    expect(screen.getByText("SYN-CUSTOMER-001")).toBeVisible();
    for (const label of ["Gate shells", "Governed references"]) {
      expect(screen.getByLabelText(label)).toHaveAttribute("tabindex", "0");
    }
    expect(document.body).not.toHaveTextContent("Project health");
    expect(document.body).not.toHaveTextContent("Budget");
    expect(document.body).not.toHaveTextContent("Gate decision");
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(0);
  });

  it("renders an honest read-only banner from the permission projection", async () => {
    const fixture = projectCockpitFixture();
    const readOnlyFixture = {
      ...fixture,
      permissions: { ...fixture.permissions, canContribute: false },
    } satisfies ProjectCockpitViewModel;
    renderWithLocale(
      <ProjectPage
        dataSource={resolvedDataSource(readOnlyFixture)}
        globalId={fixture.project.globalId}
        navigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(
        "You have view-only access. Project commands are not available in this cockpit.",
      ),
    ).toBeVisible();
    expect(screen.getByText("View only")).toBeVisible();
  });

  it("renders business data as text without creating executable markup", async () => {
    const fixture = projectCockpitFixture({
      title: '<img src=x onerror="globalThis.compromised=true">',
    });
    renderWithLocale(
      <ProjectPage
        dataSource={resolvedDataSource(fixture)}
        globalId={fixture.project.globalId}
        navigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(
        '<img src=x onerror="globalThis.compromised=true">',
      ),
    ).toBeVisible();
    expect(document.querySelector(".object-header img")).toBeNull();
    expect(
      (globalThis as typeof globalThis & { compromised?: boolean }).compromised,
    ).toBeUndefined();
  });

  it("renders the loaded empty state without pretending Gates or references exist", async () => {
    const fixture = projectCockpitFixture();
    const emptyFixture = {
      ...fixture,
      references: [],
    } satisfies ProjectCockpitViewModel;
    renderWithLocale(
      <ProjectPage
        dataSource={resolvedDataSource(emptyFixture)}
        globalId={fixture.project.globalId}
        navigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(
        "This project has no governed object references.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Synthetic feasibility shell")).toBeVisible();
    expect(
      screen.getByText("No governed references are attached to this project."),
    ).toBeVisible();
  });

  it.each([
    [404, "PROJECT_NOT_FOUND", "Project unavailable"],
    [403, "PROJECT_ACCESS_DENIED", "Project access is not available"],
    [422, "REQUEST_VALIDATION_FAILED", "The project address is invalid"],
  ] as const)(
    "maps HTTP %s to a protected terminal state",
    async (status, code, heading) => {
      const fixture = projectCockpitFixture();
      renderWithLocale(
        <ProjectPage
          dataSource={rejectedDataSource(problem(status, code))}
          globalId={fixture.project.globalId}
          navigate={vi.fn()}
        />,
      );

      expect(
        await screen.findByRole("heading", { level: 1, name: heading }),
      ).toBeVisible();
      const error = screen.getByRole("alert", { name: "Error details" });
      expect(error).toHaveTextContent(`trace-${code.toLowerCase()}`);
      expect(document.body).not.toHaveTextContent(fixture.project.title);
      expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    },
  );

  it("treats an invalid client route as validation without issuing a blind retry", async () => {
    renderWithLocale(
      <ProjectPage
        dataSource={rejectedDataSource(
          new NpiTransportError(
            "request_not_ready",
            "client-project-address",
            "client",
          ),
        )}
        globalId="not-a-uuid"
        navigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "The project address is invalid",
      }),
    ).toBeVisible();
    expect(screen.getByText("client-project-address")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("reloads after a trace-aware conflict and replaces the failure with live data", async () => {
    const fixture = projectCockpitFixture();
    const load = vi
      .fn<ProjectCockpitDataSource["load"]>()
      .mockRejectedValueOnce(problem(409, "VERSION_CONFLICT"))
      .mockResolvedValueOnce(fixture);
    const user = userEvent.setup();
    renderWithLocale(
      <ProjectPage
        dataSource={{ load }}
        globalId={fixture.project.globalId}
        navigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "The project view is out of date",
      }),
    ).toBeVisible();
    expect(screen.getByText("trace-version_conflict")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Reload project" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /SYN-PROJECT-001 Synthetic project cockpit/,
      }),
    ).toBeVisible();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("performs an actual retry for a retryable failure and keeps the trace visible", async () => {
    const fixture = projectCockpitFixture();
    const load = vi
      .fn<ProjectCockpitDataSource["load"]>()
      .mockRejectedValueOnce(problem(503, "PROJECT_UNAVAILABLE", true))
      .mockResolvedValueOnce(fixture);
    const user = userEvent.setup();
    renderWithLocale(
      <ProjectPage
        dataSource={{ load }}
        globalId={fixture.project.globalId}
        navigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "The project could not be loaded",
      }),
    ).toBeVisible();
    expect(screen.getByText("trace-project_unavailable")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /SYN-PROJECT-001 Synthetic project cockpit/,
      }),
    ).toBeVisible();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("fails closed on an invalid response and offers only safe navigation", async () => {
    const fixture = projectCockpitFixture();
    const navigate = vi.fn<(target: string) => void>();
    const user = userEvent.setup();
    renderWithLocale(
      <ProjectPage
        dataSource={rejectedDataSource(
          new NpiTransportError(
            "invalid_response",
            "trace-invalid-project",
            "trace",
          ),
        )}
        globalId={fixture.project.globalId}
        navigate={navigate}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "The project response could not be used safely",
      }),
    ).toBeVisible();
    expect(screen.getByText("trace-invalid-project")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Return to My Work" }));
    expect(navigate).toHaveBeenCalledWith("/work");
  });
});

describe("Project request lifetime safety", () => {
  it("aborts the active request when the page unmounts", () => {
    const fixture = projectCockpitFixture();
    let requestSignal: AbortSignal | undefined;
    const dataSource: ProjectCockpitDataSource = {
      load: (_globalId, signal) => {
        requestSignal = signal;
        return new Promise<ProjectCockpitViewModel>(() => undefined);
      },
    };
    const rendered = renderWithLocale(
      <ProjectPage
        dataSource={dataSource}
        globalId={fixture.project.globalId}
        navigate={vi.fn()}
      />,
    );

    expect(requestSignal?.aborted).toBe(false);
    rendered.unmount();
    expect(requestSignal?.aborted).toBe(true);
  });

  it("does not let a stale response replace a newer Project", async () => {
    const first = projectCockpitFixture();
    const second = projectCockpitFixture({
      globalId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      businessCode: "SYN-PROJECT-002",
      title: "Second synthetic project",
    });
    const pending = new Map<
      string,
      (cockpit: ProjectCockpitViewModel) => void
    >();
    const dataSource: ProjectCockpitDataSource = {
      load: (globalId) =>
        new Promise((resolve) => {
          pending.set(globalId, resolve);
        }),
    };
    const rendered = renderWithLocale(
      <ProjectPage
        dataSource={dataSource}
        globalId={first.project.globalId}
        navigate={vi.fn()}
      />,
    );
    rendered.rerender(
      <I18nProvider>
        <ProjectPage
          dataSource={dataSource}
          globalId={second.project.globalId}
          navigate={vi.fn()}
        />
      </I18nProvider>,
    );

    pending.get(second.project.globalId)?.(second);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /SYN-PROJECT-002 Second synthetic project/,
      }),
    ).toBeVisible();
    pending.get(first.project.globalId)?.(first);
    await waitFor(() => {
      expect(document.body).not.toHaveTextContent("SYN-PROJECT-001");
    });
    expect(screen.queryByText("Synthetic project cockpit")).toBeNull();
  });
});
