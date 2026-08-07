import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "../../src/app/app-shell";
import { App } from "../../src/app/app";
import type { AppRoute } from "../../src/app/router";
import { LiveMyWorkDataSource } from "../../src/api/my-work-data-source";
import type { ProjectControlsDataSource } from "../../src/api/project-controls-data-source";
import type { Locale } from "../../src/i18n/runtime";
import ExecutionPage from "../../src/pages/execution-page";
import GatePage from "../../src/pages/gate-page";
import ProjectDemoPage from "../../src/pages/project-demo-page";
import ToolingPage from "../../src/pages/tooling-page";
import TrialPage from "../../src/pages/trial-page";
import WorkPage from "../../src/pages/work-page";
import { UsabilityRecorder } from "../../src/telemetry/recorder";
import { renderWithLocale } from "../support/render";

function route(
  screen: AppRoute["screen"],
  pathname: string,
  scenario: AppRoute["scenario"] = "normal",
): AppRoute {
  const demo = pathname.startsWith("/demo/");
  const pathParts = pathname.split("/");
  const liveTooling = screen === "tooling" && pathname.startsWith("/projects/");
  const liveProjectGlobalId =
    (screen === "project" || screen === "gate" || liveTooling) && !demo
      ? (pathParts[2] ?? null)
      : null;
  const liveGateGlobalId =
    screen === "gate" && !demo ? (pathParts[4] ?? null) : null;
  return {
    gateGlobalId: liveGateGlobalId,
    gateMode: screen === "gate" ? (demo ? "demo" : "live") : null,
    pathname,
    qualityFailure: false,
    scenario,
    screen,
    projectGlobalId: liveProjectGlobalId,
    projectMode: screen === "project" ? (demo ? "demo" : "live") : null,
    toolingMasterGlobalId: liveTooling ? (pathParts[4] ?? null) : null,
    toolingMode: screen === "tooling" ? (liveTooling ? "live" : "demo") : null,
    workMode: screen === "work" ? (demo ? "demo" : "live") : null,
  };
}

function sessionBootstrap(
  language: Locale,
  csrfToken: string,
  navigationCollapsed = false,
): Readonly<Record<string, unknown>> {
  return {
    allowedLanguages: ["en", "zh", "zh-TW"],
    catalog: {
      language,
      messages: {},
      version: "a".repeat(64),
    },
    csrfToken,
    language,
    preferences: { navigationCollapsed },
    userId: "phase3@example.invalid",
  };
}

function response(body: unknown, status = 200, traceId?: string): Response {
  const init: ResponseInit = { status };
  if (traceId) init.headers = { "X-Trace-ID": traceId };
  return new Response(JSON.stringify(body), init);
}

describe("application shell behavior", () => {
  it("records a privacy-safe normalized route view from the running App", async () => {
    const record = vi
      .spyOn(UsabilityRecorder.prototype, "record")
      .mockResolvedValue(undefined);
    vi.spyOn(LiveMyWorkDataSource.prototype, "load").mockResolvedValue({
      asOf: "2026-07-25T12:00:00Z",
      timeZone: "UTC",
      projectOptions: [],
      items: [],
      nextCursor: null,
      counts: {
        all: { availability: "available", value: 0 },
        today: { availability: "available", value: 0 },
        overdue: { availability: "available", value: 0 },
        approvals: { availability: "available", value: 0 },
        blockers: { availability: "available", value: 0 },
        waiting: { availability: "available", value: 0 },
        integration: {
          availability: "unavailable",
          reason: "source_not_available",
        },
      },
    });
    renderWithLocale(<App />, "en", "/work");

    await screen.findByRole("heading", { name: "My Work" });
    expect(record).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "route_viewed",
        route: "/work",
        outcome: "viewed",
      }),
    );
    expect(JSON.stringify(record.mock.calls)).not.toContain("PJ-26018");
  });
  it("keeps one active domain entry and routes shell controls explicitly", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(
      <AppShell
        navigate={navigate}
        route={route("project", "/demo/projects/PJ-26018", "partial")}
      >
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/demo/projects/PJ-26018?scenario=partial",
    );

    expect(screen.getByRole("main")).toHaveTextContent("Workspace fixture");
    const domainNavigation = screen.getByRole("navigation", {
      name: "Domain navigation",
    });
    const currentEntries = within(domainNavigation).getAllByRole("button", {
      current: "page",
    });
    expect(currentEntries).toHaveLength(1);
    expect(currentEntries[0]).toHaveAccessibleName("Project");
    expect(
      within(domainNavigation)
        .getByText("Design and Baselines")
        .closest('[aria-disabled="true"]'),
    ).not.toBeNull();
    expect(
      screen.getByRole("searchbox", { name: "Global search" }),
    ).toHaveAttribute(
      "placeholder",
      "Search projects, tools, trials, and drawings",
    );

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Fixture state" }),
      "error",
    );
    const scenarioTarget = navigate.mock.lastCall?.[0];
    expect(scenarioTarget).toBeDefined();
    const scenarioUrl = new URL(String(scenarioTarget), "https://npi.test");
    expect(scenarioUrl.pathname).toBe("/demo/projects/PJ-26018");
    expect(scenarioUrl.searchParams.get("scenario")).toBe("error");
    expect(scenarioUrl.searchParams.get("lang")).toBe("en");

    const brandButton = screen.getByRole("button", {
      name: "Open LaunchFlow home",
    });
    expect(
      brandButton.querySelector('[data-brand-context="wordmark-dark"]'),
    ).toHaveAttribute("data-brand-asset", "LaunchFlow-logo_White.svg");
    const footer = document.querySelector("footer.status-bar");
    expect(footer).not.toBeNull();
    expect(
      within(footer as HTMLElement).getByRole("img", { name: "LaunchFlow" }),
    ).toHaveAttribute("data-brand-context", "wordmark-light");
    expect(
      within(footer as HTMLElement).getByRole("img", {
        name: "Company ownership mark",
      }),
    ).toHaveAttribute("data-brand-context", "company-footer");

    await user.click(brandButton);
    expect(navigate).toHaveBeenLastCalledWith("/work");
    await user.click(
      within(domainNavigation).getByRole("button", { name: "Tooling" }),
    );
    expect(navigate).toHaveBeenLastCalledWith("/tooling/TL-26018-01");
  });

  it("confirms an explicit compact navigation preference through the session boundary", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(response(sessionBootstrap("en", "a".repeat(32))))
      .mockResolvedValueOnce(
        response(sessionBootstrap("en", "b".repeat(32), true)),
      );
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell
        navigate={vi.fn()}
        route={route("project", "/demo/projects/PJ-26018")}
      >
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/demo/projects/PJ-26018",
    );

    expect(
      await screen.findByText("Language is managed by the Frappe session."),
    ).toBeVisible();
    const shell = document.querySelector(".app-shell");
    expect(shell).toHaveAttribute("data-navigation-collapsed", "false");
    await user.click(
      screen.getByRole("button", { name: "Collapse domain navigation" }),
    );
    await waitFor(() => {
      expect(shell).toHaveAttribute("data-navigation-collapsed", "true");
    });
    expect(fetch).toHaveBeenLastCalledWith(
      "/api/npi/v1/session/preferences/navigation",
      expect.objectContaining({
        body: JSON.stringify({ collapsed: true }),
        method: "PUT",
      }),
    );
    const project = screen.getByRole("button", {
      current: "page",
      name: "Project",
    });
    expect(project).toHaveAttribute(
      "aria-describedby",
      "navigation-project-tooltip",
    );
    await user.hover(project);
    expect(
      screen.getByRole("tooltip", {
        name: "Project",
      }),
    ).toBeVisible();
  });

  it("uses responsive compact presentation without writing the explicit preference", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({
        addEventListener: vi.fn(),
        addListener: vi.fn(),
        dispatchEvent: vi.fn(),
        matches: true,
        media: "(max-width: 720px)",
        onchange: null,
        removeEventListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    );
    const fetch = vi.fn<typeof globalThis.fetch>(() =>
      Promise.reject(new Error("No Frappe Site is active.")),
    );
    vi.stubGlobal("fetch", fetch);
    renderWithLocale(
      <AppShell navigate={vi.fn()} route={route("work", "/demo/work")}>
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/demo/work",
    );

    await waitFor(() => {
      expect(document.querySelector(".app-shell")).toHaveAttribute(
        "data-navigation-collapsed",
        "true",
      );
    });
    expect(
      screen.getByRole("button", {
        name: "Navigation is compact at this window size.",
      }),
    ).toBeDisabled();
    expect(
      fetch.mock.calls.some(
        ([target]) => target === "/api/npi/v1/session/preferences/navigation",
      ),
    ).toBe(false);
    expect(localStorage.getItem("npi-one-navigation-collapsed")).toBeNull();
  });

  it("provides keyboard-first approved commands and restores trigger focus", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(
      <AppShell
        navigate={navigate}
        route={route("project", "/demo/projects/PJ-26018")}
      >
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/demo/projects/PJ-26018",
    );

    const trigger = screen.getByRole("button", {
      name: "Open command palette",
    });
    expect(trigger).toHaveAttribute("aria-keyshortcuts", "Control+K Meta+K");
    expect(trigger).toHaveTextContent("Ctrl/⌘+K");
    trigger.focus();
    await user.keyboard("{Control>}k{/Control}");
    const dialog = screen.getByRole("dialog", { name: "Command palette" });
    const search = within(dialog).getByRole("searchbox", {
      name: "Search commands",
    });
    expect(search).toHaveFocus();
    expect(dialog).toHaveTextContent("Enter Open selected command");
    await user.type(search, "Part");
    await user.keyboard("{ArrowDown}{Enter}");
    expect(navigate).not.toHaveBeenCalled();
    expect(
      within(dialog).getByRole("button", { name: /Open Part/u }),
    ).toHaveAttribute("aria-disabled", "true");
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(trigger).toHaveFocus();
    });

    await user.keyboard("{Control>}k{/Control}");
    const reopenedSearch = screen.getByRole("searchbox", {
      name: "Search commands",
    });
    await user.type(reopenedSearch, "Tooling");
    await user.keyboard("{ArrowDown}{Enter}");
    const target = navigate.mock.lastCall?.[0];
    expect(target).toBeDefined();
    const targetUrl = new URL(String(target), "https://npi.test");
    expect(targetUrl.pathname).toBe("/tooling/TL-26018-01");
    expect(targetUrl.searchParams.get("returnTo")).toContain(
      "/demo/projects/PJ-26018",
    );
  });

  it("disables the navigation preference toggle while a failed save requires reconciliation", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(response(sessionBootstrap("en", "a".repeat(32))))
      .mockResolvedValueOnce(
        response(
          {
            code: "LOCALIZATION_UNAVAILABLE",
            retryable: true,
            status: 503,
            title: "The session preference service is unavailable.",
            traceId: "trace-navigation-preference-failure",
            type: "urn:npi:problem:localization_unavailable",
          },
          503,
          "trace-navigation-preference-failure",
        ),
      );
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell navigate={vi.fn()} route={route("work", "/work")}>
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/work",
    );

    const toggle = await screen.findByRole("button", {
      name: "Collapse domain navigation",
    });
    await waitFor(() => {
      expect(toggle).toBeEnabled();
    });
    await user.click(toggle);

    expect(
      await screen.findByText(
        "The navigation preference could not be confirmed.",
      ),
    ).toBeVisible();
    expect(toggle).toBeDisabled();
    expect(document.querySelector(".app-shell")).toHaveAttribute(
      "data-navigation-collapsed",
      "false",
    );
  });

  it("shows contextual Project learning creation only after the live capability allows it", async () => {
    const projectId = "11111111-1111-4111-8111-111111111111";
    const loadLearning = vi.fn().mockResolvedValue({
      items: [],
      permissions: { canCreate: true },
      projectId,
    });
    const dataSource = {
      loadLearning,
    } as unknown as ProjectControlsDataSource;
    vi.stubGlobal(
      "fetch",
      vi
        .fn<typeof globalThis.fetch>()
        .mockResolvedValue(response(sessionBootstrap("en", "a".repeat(32)))),
    );
    const navigate = vi.fn<(target: string) => void>();
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell
        navigate={navigate}
        projectControlsDataSource={dataSource}
        route={route("project", `/projects/${projectId}`)}
      >
        <p>Live Project workspace</p>
      </AppShell>,
      "en",
      `/projects/${projectId}`,
    );

    expect(
      await screen.findByText("Language is managed by the Frappe session."),
    ).toBeVisible();
    const quickCreate = screen.getByRole("button", { name: "Quick create" });
    await user.click(quickCreate);
    let create = await screen.findByRole("button", {
      name: "Create Project learning record",
    });
    expect(loadLearning).toHaveBeenCalledWith(
      projectId,
      { limit: 1 },
      expect.any(AbortSignal),
    );
    create.focus();
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(quickCreate).toHaveFocus();
    });
    expect(
      screen.queryByRole("dialog", { name: "Contextual quick-create" }),
    ).toBeNull();

    await user.click(quickCreate);
    create = await screen.findByRole("button", {
      name: "Create Project learning record",
    });
    create.focus();
    await user.keyboard("{Control>}k{/Control}");
    const commandDialog = screen.getByRole("dialog", {
      name: "Command palette",
    });
    expect(
      within(commandDialog).getByRole("searchbox", {
        name: "Search commands",
      }),
    ).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Open command palette" }),
      ).toHaveFocus();
    });
    expect(document.body).not.toHaveFocus();

    await user.click(quickCreate);
    create = await screen.findByRole("button", {
      name: "Create Project learning record",
    });
    expect(loadLearning).toHaveBeenCalledTimes(3);
    await user.click(create);
    const target = navigate.mock.lastCall?.[0];
    expect(target).toBeDefined();
    const targetUrl = new URL(String(target), "https://npi.test");
    expect(targetUrl.pathname).toBe(`/projects/${projectId}`);
    expect(targetUrl.searchParams.get("tab")).toBe("learning");
    expect(targetUrl.searchParams.get("quickCreate")).toBe("learning");
    expect(targetUrl.searchParams.get("returnTo")).toContain(
      `/projects/${projectId}`,
    );
  });

  it("does not expose a Project learning command when the live capability denies it", async () => {
    const projectId = "11111111-1111-4111-8111-111111111111";
    const dataSource = {
      loadLearning: vi.fn().mockResolvedValue({
        items: [],
        permissions: { canCreate: false },
        projectId,
      }),
    } as unknown as ProjectControlsDataSource;
    vi.stubGlobal(
      "fetch",
      vi
        .fn<typeof globalThis.fetch>()
        .mockResolvedValue(response(sessionBootstrap("en", "a".repeat(32)))),
    );
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell
        navigate={vi.fn()}
        projectControlsDataSource={dataSource}
        route={route("project", `/projects/${projectId}`)}
      >
        <p>Live Project workspace</p>
      </AppShell>,
      "en",
      `/projects/${projectId}`,
    );

    expect(
      await screen.findByText("Language is managed by the Frappe session."),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Quick create" }));
    expect(
      await screen.findByText(
        "Your current Project capability does not allow creating a learning record.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", {
        name: "Create Project learning record",
      }),
    ).toBeNull();
  });

  it("persists a language choice through the visible selector fallback", async () => {
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell navigate={vi.fn()} route={route("work", "/work")}>
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/work",
    );

    const language = screen.getByRole("combobox", { name: "Language" });
    expect(within(language).getAllByRole("option")).toHaveLength(3);
    await waitFor(() => {
      expect(language).toBeEnabled();
    });
    await user.selectOptions(language, "zh-TW");
    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute("lang", "zh-TW");
    });
    expect(localStorage.getItem("npi-one-prototype-locale")).toBe("zh-TW");
    expect(screen.getByRole("combobox", { name: "語言" })).toHaveValue("zh-TW");
  });

  it("labels live Project data, hides fixture controls, and dispatches a real refresh", async () => {
    const globalId = "11111111-1111-4111-8111-111111111111";
    const dispatchEvent = vi.spyOn(globalThis, "dispatchEvent");
    const navigate = vi.fn();
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell
        navigate={navigate}
        route={route("project", `/projects/${globalId}`)}
      >
        <p>Live project workspace</p>
      </AppShell>,
      "en",
      `/projects/${globalId}`,
    );

    expect(
      screen.getByText(
        "Live project data. No production ERPNext system is connected.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: "Fixture state" }),
    ).toBeNull();
    expect(
      screen.getByRole("button", { name: "Current user" }),
    ).toHaveTextContent("Signed-in user");
    const domainNavigation = screen.getByRole("navigation", {
      name: "Domain navigation",
    });
    expect(
      within(domainNavigation).getByLabelText("Project Portfolio"),
    ).toHaveAttribute("aria-disabled", "true");
    const tooling = within(domainNavigation).getByRole("button", {
      name: "Tooling",
    });
    expect(tooling).not.toHaveAttribute("aria-disabled");
    await user.click(tooling);
    expect(navigate).toHaveBeenCalledWith(`/projects/${globalId}/tooling`);

    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(dispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: "npi:refresh-project" }),
    );
    expect(
      screen.getByText("The live project request is being refreshed."),
    ).toBeVisible();

    const search = screen.getByRole("searchbox", { name: "Global search" });
    await user.type(search, "PJ-26018{Enter}");
    expect(
      screen.getByText(
        "Live global search is not available in this phase. Open this project from an authorized project link.",
      ),
    ).toBeVisible();
  });

  it("labels live My Work, hides fixture controls, and dispatches its scoped refresh", async () => {
    const dispatchEvent = vi.spyOn(globalThis, "dispatchEvent");
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell navigate={vi.fn()} route={route("work", "/work")}>
        <p>Live My Work workspace</p>
      </AppShell>,
      "en",
      "/work",
    );

    expect(
      screen.getByText(
        "Live My Work data. No production ERPNext system is connected.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: "Fixture state" }),
    ).toBeNull();
    expect(
      screen.getByRole("button", { name: "Current user" }),
    ).toHaveTextContent("Signed-in user");

    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(dispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: "npi:refresh-my-work" }),
    );
    expect(
      screen.getByText("The live My Work request is being refreshed."),
    ).toBeVisible();

    const search = screen.getByRole("searchbox", { name: "Global search" });
    await user.type(search, "PJ-26018{Enter}");
    expect(
      screen.getByText(
        "Live global search is not available in this phase. Open an authorized work item or project link.",
      ),
    ).toBeVisible();
  });

  it("keeps a live Gate in Project context and dispatches its scoped refresh", async () => {
    const projectGlobalId = "11111111-1111-4111-8111-111111111111";
    const gateGlobalId = "44444444-4444-4444-8444-444444444444";
    const path = `/projects/${projectGlobalId}/gates/${gateGlobalId}`;
    const dispatchEvent = vi.spyOn(globalThis, "dispatchEvent");
    const navigate = vi.fn<(target: string) => void>();
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell navigate={navigate} route={route("gate", path)}>
        <p>Live Gate evidence workspace</p>
      </AppShell>,
      "en",
      path,
    );

    const domainNavigation = screen.getByRole("navigation", {
      name: "Domain navigation",
    });
    expect(
      within(domainNavigation).getByRole("button", {
        current: "page",
        name: "Project",
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: "Fixture state" }),
    ).toBeNull();
    await user.click(
      within(domainNavigation).getByRole("button", { name: "Project" }),
    );
    expect(navigate).toHaveBeenCalledWith(`/projects/${projectGlobalId}`);

    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(dispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: "npi:refresh-gate-evidence" }),
    );
    expect(
      screen.getByText("The live Gate evidence request is being refreshed."),
    ).toBeVisible();
  });

  it("shows a localized bootstrap problem with its server trace and retries by keyboard", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        response(
          {
            type: "urn:npi:problem:localization_unavailable",
            title: "本地化资源不可用。",
            status: 503,
            code: "LOCALIZATION_UNAVAILABLE",
            traceId: "trace-bootstrap-failure",
            retryable: true,
          },
          503,
          "trace-bootstrap-failure",
        ),
      )
      .mockResolvedValueOnce(response(sessionBootstrap("zh", "b".repeat(32))));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell navigate={vi.fn()} route={route("work", "/work")}>
        <p>Workspace fixture</p>
      </AppShell>,
      "zh",
      "/work",
    );

    expect(await screen.findByText("无法加载会话语言和目录。")).toBeVisible();
    expect(screen.getByText("本地化资源不可用。")).toBeVisible();
    expect(screen.getByText("trace-bootstrap-failure")).toBeVisible();
    const retry = screen.getByRole("button", { name: "重试" });
    retry.focus();
    expect(retry).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(await screen.findByText("语言由 Frappe 会话管理。")).toBeVisible();
    expect(
      screen.queryByText("trace-bootstrap-failure"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "语言" })).toBeEnabled();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("keeps the active catalog after a language failure and refreshes CSRF before retry", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(response(sessionBootstrap("en", "a".repeat(32))))
      .mockResolvedValueOnce(
        response(
          {
            type: "urn:npi:problem:csrf_token_invalid",
            title: "The security token is invalid or expired.",
            status: 403,
            code: "CSRF_TOKEN_INVALID",
            traceId: "trace-language-failure",
            retryable: true,
          },
          403,
          "trace-language-failure",
        ),
      )
      .mockResolvedValueOnce(response(sessionBootstrap("en", "b".repeat(32))))
      .mockResolvedValueOnce(response(sessionBootstrap("zh", "c".repeat(32))));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell navigate={vi.fn()} route={route("work", "/work")}>
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/work",
    );
    const language = await screen.findByRole("combobox", { name: "Language" });
    await waitFor(() => {
      expect(language).toBeEnabled();
    });
    await user.selectOptions(language, "zh");

    expect(
      await screen.findByText("The language change could not be confirmed."),
    ).toBeVisible();
    expect(screen.getByText("trace-language-failure")).toBeVisible();
    expect(document.documentElement).toHaveAttribute("lang", "en");
    expect(language).toHaveValue("en");
    const retry = screen.getByRole("button", { name: "Retry" });
    retry.focus();
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute("lang", "zh");
    });
    expect(screen.getByRole("combobox", { name: "语言" })).toHaveValue("zh");
    expect(fetch).toHaveBeenCalledTimes(4);
    const initialPutHeaders = new Headers(fetch.mock.calls[1]?.[1]?.headers);
    const retryGetHeaders = new Headers(fetch.mock.calls[2]?.[1]?.headers);
    const retryPutHeaders = new Headers(fetch.mock.calls[3]?.[1]?.headers);
    expect(initialPutHeaders.get("X-Frappe-CSRF-Token")).toBe("a".repeat(32));
    expect(retryGetHeaders.get("X-Frappe-CSRF-Token")).toBeNull();
    expect(retryPutHeaders.get("X-Frappe-CSRF-Token")).toBe("b".repeat(32));
  });

  it("rejects a malformed successful language response without replacing the active catalog", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
    const malformed = {
      ...sessionBootstrap("zh", "b".repeat(32)),
      catalog: {
        language: "zh",
        messages: { "My Work": { raw: "secret malformed content" } },
        version: "b".repeat(64),
      },
    };
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(response(sessionBootstrap("en", "a".repeat(32))))
      .mockResolvedValueOnce(response(malformed, 200, "trace-malformed"));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    renderWithLocale(
      <AppShell navigate={vi.fn()} route={route("work", "/work")}>
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/work",
    );
    const language = await screen.findByRole("combobox", { name: "Language" });
    await waitFor(() => {
      expect(language).toBeEnabled();
    });
    await user.selectOptions(language, "zh");

    expect(
      await screen.findByText("The language change could not be confirmed."),
    ).toBeVisible();
    const errorDetails = screen.getByRole("alert", { name: "Error details" });
    expect(errorDetails).toHaveTextContent("Trace ID");
    expect(within(errorDetails).getByText("trace-malformed")).toBeVisible();
    expect(document.documentElement).toHaveAttribute("lang", "en");
    expect(screen.getByRole("combobox", { name: "Language" })).toHaveValue(
      "en",
    );
    expect(document.body).not.toHaveTextContent("secret malformed content");
  });

  it("searches only known fixture identities and reports unavailable utilities honestly", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(
      <AppShell navigate={navigate} route={route("work", "/demo/work")}>
        <p>Workspace fixture</p>
      </AppShell>,
      "en",
      "/demo/work",
    );
    const search = screen.getByRole("searchbox", { name: "Global search" });

    await user.type(search, "TL-99999{Enter}");
    expect(navigate).not.toHaveBeenCalled();
    expect(
      screen.getByText("No prototype search result matched this query."),
    ).toBeVisible();
    await user.clear(search);
    await user.type(search, "TL-26018-01{Enter}");
    expect(navigate).toHaveBeenLastCalledWith("/tooling/TL-26018-01");
    expect(
      screen.queryByText("No prototype search result matched this query."),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Notifications" }));
    expect(
      screen.getByText(
        "No prototype notification feed is connected. Use My Work for assigned actions.",
      ),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(
      screen.getByText(
        "Prototype refresh is unavailable because this view uses fixed in-memory data.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("main")).toHaveTextContent("Workspace fixture");
  });

  it("removes protected object identifiers from denied shell context", () => {
    renderWithLocale(
      <AppShell
        navigate={vi.fn()}
        route={route("project", "/demo/projects/PJ-26018", "no_permission")}
      >
        <p>Denied fixture</p>
      </AppShell>,
      "en",
      "/demo/projects/PJ-26018?scenario=no_permission",
    );

    expect(screen.getAllByText("Protected object")).toHaveLength(2);
    expect(
      document.querySelector(".app-header__context"),
    ).not.toHaveTextContent("PJ-26018");
    expect(document.querySelector(".breadcrumbs")).not.toHaveTextContent(
      "PJ-26018",
    );
  });

  it("does not render protected object data anywhere in a denied workspace", async () => {
    renderWithLocale(
      <App />,
      "en",
      "/demo/projects/PJ-26018/gates/G5?scenario=no_permission",
    );

    await screen.findByRole("heading", {
      name: "You do not have permission to view this object.",
    });
    expect(document.body).not.toHaveTextContent("PJ-26018");
    expect(document.body).not.toHaveTextContent("Valve cover");
    expect(document.body).not.toHaveTextContent("T1-DIM-REPORT.pdf");
    expect(document.body).not.toHaveTextContent("ACME");
    expect(screen.getAllByText("Protected object")).toHaveLength(2);
  });

  it("guards dirty internal navigation and installs a browser-leave warning", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("scrollTo", vi.fn());
    renderWithLocale(<App />, "en", "/demo/projects/PJ-26018?scenario=dirty");
    await screen.findByRole("heading", {
      name: /PJ-26018 Valve cover new tool/,
    });
    const leaveEvent = new Event("beforeunload", {
      bubbles: false,
      cancelable: true,
    });
    globalThis.dispatchEvent(leaveEvent);
    expect(leaveEvent.defaultPrevented).toBe(true);

    const commandTrigger = screen.getByRole("button", {
      name: "Open command palette",
    });
    commandTrigger.focus();
    await user.keyboard("{Control>}k{/Control}");
    const commandDialog = screen.getByRole("dialog", {
      name: "Command palette",
    });
    await user.type(
      within(commandDialog).getByRole("searchbox", {
        name: "Search commands",
      }),
      "Tooling",
    );
    await user.keyboard("{ArrowDown}{Enter}");
    const firstReview = screen.getByRole("dialog", { name: "Unsaved changes" });
    expect(firstReview).toBeVisible();
    await user.keyboard("{Control>}k{/Control}");
    expect(
      screen.queryByRole("dialog", { name: "Command palette" }),
    ).toBeNull();
    expect(firstReview).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(commandTrigger).toHaveFocus();
    });
    expect(globalThis.location.pathname).toBe("/demo/projects/PJ-26018");

    const tooling = within(
      screen.getByRole("navigation", { name: "Domain navigation" }),
    ).getByRole("button", { name: "Tooling" });
    await user.click(tooling);
    const discard = screen.getByRole("button", {
      name: "Discard changes and leave",
    });
    expect(discard).toBeDisabled();
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Discard the local draft",
    );
    expect(discard).toBeEnabled();
    await user.click(discard);
    expect(globalThis.location.pathname).toBe("/tooling/TL-26018-01");
  });
});

describe("core workspace page behavior", () => {
  it("dispatches each work-item action to its owned workspace", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(<WorkPage navigate={navigate} />);

    expect(screen.getByRole("heading", { name: "My Work" })).toBeVisible();
    const worklist = screen.getByRole("table");
    await within(worklist).findByRole("button", { name: "Open review" });
    expect(within(worklist).getAllByRole("row")).toHaveLength(7);
    const actionTargets = [
      ["Open review", "/demo/projects/PJ-26018/gates/G5"],
      ["Resolve defect", "/demo/projects/PJ-26018/gates/G5"],
      ["View context", "/tooling/TL-26018-01"],
      ["View execution", "/execution?focus=EX-260721-0048"],
      ["Start", "/tooling/TL-26018-01"],
      ["Review impact", "/demo/projects/PJ-26018/gates/G5"],
    ] as const;
    for (const [label, target] of actionTargets) {
      await user.click(within(worklist).getByRole("button", { name: label }));
      expect(navigate).toHaveBeenLastCalledWith(target);
    }
  });

  it("prepares an honest project corrective action and opens selected Gates", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(<ProjectDemoPage navigate={navigate} scenario="normal" />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "PJ-26018 Valve cover new tool",
    );
    await user.click(
      screen.getByRole("button", { name: "Create corrective action" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Prototype corrective action prepared. No action was saved.",
    );

    await user.click(
      screen.getByRole("button", { name: /G4 Trial iteration/ }),
    );
    expect(navigate).toHaveBeenLastCalledWith(
      "/demo/projects/PJ-26018/gates/G4",
    );
    await user.click(screen.getByRole("button", { name: /G6 NPI readiness/ }));
    expect(navigate).toHaveBeenLastCalledWith(
      "/demo/projects/PJ-26018/gates/G6?quality=failed",
    );
    await user.click(screen.getByRole("button", { name: "Prepare G5 review" }));
    expect(navigate).toHaveBeenLastCalledWith(
      "/demo/projects/PJ-26018/gates/G5",
    );
  });

  it("reviews, cancels, and prepares a Gate decision without claiming persistence", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(
      <GatePage navigate={navigate} qualityFailure={false} scenario="normal" />,
    );

    expect(screen.getByText("Pending in ERPNext")).toBeVisible();
    const review = screen.getByRole("button", {
      name: "Review impact and decide",
    });
    await user.click(review);
    expect(
      screen.getByRole("dialog", { name: "Gate decision impact review" }),
    ).toHaveTextContent(
      "The decision will lock five evidence versions and affect the next two Gates.",
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(review);
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Evidence reviewed",
    );
    await user.click(
      screen.getByRole("button", { name: "Prepare decision command" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Prototype command prepared. No gate decision was saved.",
    );
    await user.click(screen.getByRole("button", { name: "Return to project" }));
    expect(navigate).toHaveBeenCalledWith("/demo/projects/PJ-26018");
  });

  it("shows a formal ERPNext quality failure as a non-score blocker", () => {
    renderWithLocale(
      <GatePage navigate={vi.fn()} qualityFailure scenario="normal" />,
    );

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "G6 / PJ-26018 NPI readiness review",
    );
    expect(screen.getByText("Failed in ERPNext")).toBeVisible();
    expect(
      screen.getByText(
        "ERPNext reports a failed formal quality result. Readiness percentage cannot override this blocker.",
      ),
    ).toBeVisible();
  });

  it("prepares tooling design and acceptance commands before navigation", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(<ToolingPage navigate={navigate} scenario="normal" />);

    await user.click(screen.getByRole("button", { name: "Create T1 from T0" }));
    expect(navigate).toHaveBeenLastCalledWith("/trials/T1?inherit=T0");

    await user.click(
      screen.getByRole("button", { name: "Release design revision" }),
    );
    expect(
      screen.getByRole("dialog", {
        name: "Tooling design release impact review",
      }),
    ).toBeVisible();
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Design reviewed",
    );
    await user.click(
      screen.getByRole("button", { name: "Prepare release command" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Prototype release command prepared. Revision C remains unchanged.",
    );

    await user.click(
      screen.getByRole("button", { name: "Review tooling acceptance" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Tooling acceptance impact review" }),
    ).toHaveTextContent(
      "Acceptance will freeze the technical, quality, file, warranty, cost, and asset handover evidence.",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Acceptance reviewed",
    );
    await user.click(
      screen.getByRole("button", { name: "Prepare acceptance command" }),
    );
    expect(screen.getAllByRole("status").at(-1)).toHaveTextContent(
      "Prototype acceptance request prepared. ERPNext asset execution has not started.",
    );
    await user.click(screen.getByRole("button", { name: "View execution" }));
    expect(navigate).toHaveBeenLastCalledWith(
      "/execution?focus=EX-260721-0048",
    );
    await user.click(
      screen.getByRole("button", { name: "Open defect context" }),
    );
    expect(navigate).toHaveBeenLastCalledWith(
      "/demo/projects/PJ-26018/gates/G5",
    );
  });

  it("inherits a Trial plan, supports tab keyboarding, and prepares its conclusion", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(
      <TrialPage navigate={navigate} scenario="normal" />,
      "en",
      "/trials/T1?inherit=T0",
    );

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "T1 / TL-26018-01 Inherited trial plan",
    );
    expect(screen.getByText("Planned from T0")).toBeVisible();
    const tabPanel = screen.getByRole("tabpanel");
    expect(within(tabPanel).getByText("Melt temperature")).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "Samples and cavities" }));
    expect(within(tabPanel).getByText("Not submitted")).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Defects" }));
    expect(within(tabPanel).getByText("Major defects")).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Measurements" }));
    expect(within(tabPanel).getByText("Measurement report")).toBeVisible();

    const parameters = screen.getByRole("tab", { name: "Parameters" });
    await user.click(parameters);
    await user.keyboard("{ArrowLeft}");
    const comparison = screen.getByRole("tab", { name: "Round comparison" });
    await waitFor(() => {
      expect(comparison).toHaveFocus();
    });
    expect(within(tabPanel).getByText(/Compared with T0/)).toBeVisible();
    await user.keyboard("{ArrowRight}");
    await waitFor(() => {
      expect(parameters).toHaveFocus();
    });

    await user.click(
      screen.getByRole("button", { name: "Submit trial conclusion" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Trial conclusion impact review" }),
    ).toBeVisible();
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Trial evidence reviewed",
    );
    await user.click(
      screen.getByRole("button", { name: "Prepare conclusion command" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Prototype conclusion command prepared. The Trial snapshot was not submitted.",
    );
    await user.click(screen.getByRole("button", { name: "View blockers" }));
    expect(navigate).toHaveBeenLastCalledWith(
      "/demo/projects/PJ-26018/gates/G5",
    );
  });

  it("shows the default Trial as the next editable round", () => {
    renderWithLocale(<TrialPage navigate={vi.fn()} scenario="normal" />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "T1 / TL-26018-01 Trial round",
    );
    expect(screen.getByText("Analysis in progress")).toBeVisible();
    expect(screen.getByText("T2")).toBeVisible();
  });

  it("selects execution rows by keyboard and safely queues a failed retry", async () => {
    const user = userEvent.setup();
    renderWithLocale(<ExecutionPage scenario="normal" />);

    expect(
      screen.getByRole("heading", {
        name: "ERPNext Execution and Reconciliation",
      }),
    ).toBeVisible();
    const executionTable = screen.getByRole("table");
    const retryableRow = within(executionTable)
      .getByText("EX-260721-0048")
      .closest("tr");
    const partialRow = within(executionTable)
      .getByText("EX-260721-0046")
      .closest("tr");
    expect(retryableRow).toHaveAttribute("aria-selected", "true");
    expect(partialRow).not.toBeNull();
    if (!partialRow)
      throw new Error("The partial execution fixture is required.");
    partialRow.focus();
    fireEvent.keyDown(partialRow, { key: "Enter" });
    expect(partialRow).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("heading", { name: "EX-260721-0046" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Review impact and retry" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Failure reason")).not.toBeInTheDocument();

    expect(retryableRow).not.toBeNull();
    if (!retryableRow)
      throw new Error("The retryable execution fixture is required.");
    retryableRow.focus();
    fireEvent.keyDown(retryableRow, { key: " " });
    expect(retryableRow).toHaveAttribute("aria-selected", "true");
    await user.click(
      screen.getByRole("button", { name: "Review impact and retry" }),
    );
    expect(
      screen.getByRole("dialog", { name: "ERPNext retry impact review" }),
    ).toHaveTextContent(
      "Only the failed tool asset node will be retried. Completed ERPNext objects are unchanged.",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Retry mapping reviewed",
    );
    await user.click(screen.getByRole("button", { name: "Queue safe retry" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Prototype retry command prepared. No request was queued in LaunchFlow or ERPNext.",
    );

    await user.click(
      screen.getByRole("button", { name: "New execution request" }),
    );
    expect(
      screen.getByRole("dialog", {
        name: "New execution request impact review",
      }),
    ).toHaveTextContent(
      "The approved tooling acceptance snapshot will be locked for a new tool asset execution request.",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Execution input reviewed",
    );
    await user.click(
      screen.getByRole("button", { name: "Prepare execution request" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Prototype execution command prepared. No request was queued in LaunchFlow or ERPNext.",
    );
  });

  it("selects an exact execution request from focus and exposes governed field mapping state", async () => {
    const user = userEvent.setup();
    renderWithLocale(
      <ExecutionPage scenario="normal" />,
      "en",
      "/execution?focus=EX-260721-0046",
    );

    const executionTable = screen.getByRole("table");
    const focusedRow = within(executionTable)
      .getByText("EX-260721-0046")
      .closest("tr");
    expect(focusedRow).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("heading", { name: "EX-260721-0046" }),
    ).toBeVisible();

    const retryableRow = within(executionTable)
      .getByText("EX-260721-0048")
      .closest("tr");
    expect(retryableRow).not.toBeNull();
    if (!retryableRow)
      throw new Error("The retryable execution fixture is required.");
    await user.click(retryableRow);

    const mapping = screen.getByRole("button", { name: "Open field mapping" });
    expect(mapping).toHaveAttribute("aria-controls", "execution-field-mapping");
    expect(mapping).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByRole("region", { name: "Field mapping preview" }),
    ).not.toBeInTheDocument();

    await user.click(mapping);
    expect(
      screen.getByRole("button", { name: "Close field mapping" }),
    ).toHaveAttribute("aria-expanded", "true");
    const preview = screen.getByRole("region", {
      name: "Field mapping preview",
    });
    expect(preview).toHaveAttribute("id", "execution-field-mapping");
    expect(preview).toHaveTextContent(
      "No approved target value is available. Correct the governed mapping before preparing another request.",
    );
  });

  it("requires a reason before preparing an honest reconciliation command", async () => {
    const user = userEvent.setup();
    renderWithLocale(<ExecutionPage scenario="normal" />);

    await user.click(
      screen.getByRole("button", { name: "Run reconciliation" }),
    );
    const review = screen.getByRole("dialog", {
      name: "Reconciliation impact review",
    });
    expect(review).toHaveTextContent(
      "Reconciliation compares LaunchFlow requests with ERPNext responses. It does not overwrite either system.",
    );
    const prepare = within(review).getByRole("button", {
      name: "Prepare reconciliation",
    });
    expect(prepare).toBeDisabled();
    expect(
      within(review).getByRole("textbox", { name: "Reason" }),
    ).toBeRequired();

    await user.type(
      within(review).getByRole("textbox", { name: "Reason" }),
      "Daily comparison scope reviewed",
    );
    expect(prepare).toBeEnabled();
    await user.click(prepare);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Prototype reconciliation prepared. No ERPNext or LaunchFlow record was changed.",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "The in-memory prototype command captured a reason; no audit record was persisted.",
    );
  });
});

describe("read-only mutation boundaries", () => {
  it("disables project and Gate decision mutations", () => {
    const project = renderWithLocale(
      <ProjectDemoPage navigate={vi.fn()} scenario="read_only" />,
    );
    expect(
      screen.getByRole("button", { name: "Prepare G5 review" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Create corrective action" }),
    ).toBeDisabled();
    project.unmount();

    renderWithLocale(
      <GatePage
        navigate={vi.fn()}
        qualityFailure={false}
        scenario="read_only"
      />,
    );
    expect(
      screen.getByRole("button", { name: "Review impact and decide" }),
    ).toBeDisabled();
  });

  it("disables Tooling, Trial, and execution mutations", () => {
    const tooling = renderWithLocale(
      <ToolingPage navigate={vi.fn()} scenario="read_only" />,
    );
    for (const name of [
      "Create T1 from T0",
      "Release design revision",
      "Review tooling acceptance",
    ]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
    tooling.unmount();

    const trial = renderWithLocale(
      <TrialPage navigate={vi.fn()} scenario="read_only" />,
    );
    expect(
      screen.getByRole("button", { name: "Submit trial conclusion" }),
    ).toBeDisabled();
    expect(
      screen.queryByLabelText("Choose a local file"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("This attachment field is read only."),
    ).toBeVisible();
    expect(
      screen.getByText("The released Trial version is immutable."),
    ).toBeVisible();
    trial.unmount();

    renderWithLocale(<ExecutionPage scenario="read_only" />);
    expect(
      screen.getByRole("button", { name: "Run reconciliation" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "New execution request" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Review impact and retry" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Open field mapping" }),
    ).toBeEnabled();
  });
});
