import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";

import { translate } from "../../src/i18n/runtime";
import {
  projectControlIds,
  projectLearningFixture,
} from "../support/project-controls-fixture";
import { projectCockpitFixture } from "../support/project-fixture";
import {
  effectiveViewport,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = projectControlIds.project;
const csrfToken = "c".repeat(32);
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const sessionBootstrapEndpoint =
  /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const navigationPreferenceEndpoint =
  /\/api\/npi\/v1\/session\/preferences\/navigation(?:\?.*)?$/u;
const cockpitEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/cockpit(?:\?.*)?$/u;
const learningEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/learning(?:\?.*)?$/u;

interface NavigationPreferenceRequest {
  body: { collapsed: boolean };
  csrf: string | undefined;
  method: string;
}

interface SessionHarness {
  preferenceRequests: NavigationPreferenceRequest[];
}

interface ProjectHarness {
  learningRequests: URL[];
}

function sessionBootstrap(
  locale: TestLocale,
  navigationCollapsed: boolean,
): Readonly<Record<string, unknown>> {
  return {
    allowedLanguages: ["en", "zh", "zh-TW"],
    catalog: {
      language: locale,
      messages: {},
      version: "f".repeat(64),
    },
    csrfToken,
    language: locale,
    preferences: { navigationCollapsed },
    userId: "manager@example.invalid",
  };
}

function requestId(route: Route): string {
  const value = route.request().headers()["x-request-id"] ?? "";
  expect(value).toMatch(requestIdPattern);
  return value;
}

async function fulfillApi(
  route: Route,
  body: unknown,
  traceId: string,
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      "X-Request-ID": requestId(route),
      "X-Trace-ID": traceId,
    },
    status: 200,
  });
}

function expectSafeGet(route: Route): void {
  const headers = route.request().headers();
  expect(route.request().method()).toBe("GET");
  expect(headers.accept).toBe("application/json, application/problem+json");
  expect(headers["x-frappe-csrf-token"]).toBeUndefined();
  expect(headers["idempotency-key"]).toBeUndefined();
}

async function installSession(
  page: Page,
  locale: TestLocale,
  initialCollapsed = false,
): Promise<SessionHarness> {
  let confirmedCollapsed = initialCollapsed;
  const preferenceRequests: NavigationPreferenceRequest[] = [];

  await page.route(sessionBootstrapEndpoint, async (route) => {
    expectSafeGet(route);
    await fulfillApi(
      route,
      sessionBootstrap(locale, confirmedCollapsed),
      "trace-r1-03-session-bootstrap",
    );
  });
  await page.route(navigationPreferenceEndpoint, async (route) => {
    const request = route.request();
    const headers = request.headers();
    expect(request.method()).toBe("PUT");
    expect(headers.accept).toBe("application/json, application/problem+json");
    expect(headers["content-type"]).toBe("application/json");
    expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
    expect(headers["idempotency-key"]).toBeUndefined();

    const candidate: unknown = request.postDataJSON();
    expect(candidate).not.toBeNull();
    expect(typeof candidate).toBe("object");
    expect(Array.isArray(candidate)).toBe(false);
    const record = candidate as Record<string, unknown>;
    expect(Object.keys(record)).toEqual(["collapsed"]);
    expect(typeof record.collapsed).toBe("boolean");
    confirmedCollapsed = record.collapsed as boolean;
    const observed = {
      body: { collapsed: confirmedCollapsed },
      csrf: headers["x-frappe-csrf-token"],
      method: request.method(),
    };
    preferenceRequests.push(observed);

    await fulfillApi(
      route,
      sessionBootstrap(locale, confirmedCollapsed),
      "trace-r1-03-navigation-preference",
    );
  });

  return { preferenceRequests };
}

async function installProjectApis(
  page: Page,
  canCreate = true,
): Promise<ProjectHarness> {
  const learningRequests: URL[] = [];
  await page.route(cockpitEndpoint, async (route) => {
    expectSafeGet(route);
    await fulfillApi(
      route,
      projectCockpitFixture(),
      "trace-r1-03-project-cockpit",
    );
  });
  await page.route(learningEndpoint, async (route) => {
    expectSafeGet(route);
    learningRequests.push(new URL(route.request().url()));
    await fulfillApi(
      route,
      {
        ...projectLearningFixture(),
        permissions: { canCreate },
      },
      "trace-r1-03-project-learning",
    );
  });
  return { learningRequests };
}

async function openLiveProject(
  page: Page,
  locale: TestLocale,
  search = "",
): Promise<void> {
  await page.goto(`/projects/${projectId}?lang=${locale}${search}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: /SYN-PROJECT-001 Synthetic project cockpit/u,
    }),
  ).toBeVisible();
  await expect(
    page.getByText(
      translate(locale, "Language is managed by the Frappe session."),
      { exact: true },
    ),
  ).toBeVisible();
}

function domainNavigation(page: Page, locale: TestLocale): Locator {
  return page.getByRole("navigation", {
    name: translate(locale, "Domain navigation"),
  });
}

function activeProjectNavigation(page: Page, locale: TestLocale): Locator {
  return domainNavigation(page, locale).getByRole("button", {
    exact: true,
    name: translate(locale, "Project"),
  });
}

function commandButton(dialog: Locator, label: string): Locator {
  return dialog.getByRole("button").filter({ hasText: label });
}

async function expectCollapsedProjectTooltip(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  const project = activeProjectNavigation(page, locale);
  const tooltipId = await project.getAttribute("aria-describedby");
  expect(tooltipId).toBe("navigation-project-tooltip");
  const tooltip = page.locator(`#${tooltipId ?? ""}`);
  await project.hover();
  await expect(tooltip).toBeVisible();
  await expect(tooltip.locator("strong")).toHaveText(
    translate(locale, "Project"),
  );
  await page.locator(".app-header__context").hover();
  await expect(tooltip).toBeHidden();
  await project.focus();
  await expect(tooltip).toBeVisible();
  await expect(tooltip.locator("strong")).toHaveText(
    translate(locale, "Project"),
  );
}

test.describe("R1-03 application Shell behavior", () => {
  test("persists full-to-collapsed navigation through the exact session preference boundary", async ({
    page,
  }) => {
    const session = await installSession(page, "en");
    await installProjectApis(page);
    await openLiveProject(page, "en");

    const shell = page.locator(".app-shell");
    await expect(shell).toHaveAttribute("data-navigation-collapsed", "false");
    await expect(shell).toHaveAttribute("data-navigation-preference", "full");
    await expect(shell).toHaveAttribute("data-navigation-responsive", "false");
    await expect(activeProjectNavigation(page, "en")).toHaveAttribute(
      "aria-current",
      "page",
    );

    await page
      .getByRole("button", {
        name: translate("en", "Collapse domain navigation"),
      })
      .click();

    await expect(shell).toHaveAttribute("data-navigation-collapsed", "true");
    await expect(shell).toHaveAttribute(
      "data-navigation-preference",
      "collapsed",
    );
    expect(session.preferenceRequests).toEqual([
      {
        body: { collapsed: true },
        csrf: csrfToken,
        method: "PUT",
      },
    ]);
    await expectCollapsedProjectTooltip(page, "en");
  });

  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`loads the explicit collapsed preference with a translated hover and focus tooltip in ${locale}`, async ({
      page,
    }) => {
      const session = await installSession(page, locale, true);
      await installProjectApis(page);
      await openLiveProject(page, locale);

      const shell = page.locator(".app-shell");
      await expect(shell).toHaveAttribute("data-navigation-collapsed", "true");
      await expect(shell).toHaveAttribute(
        "data-navigation-preference",
        "collapsed",
      );
      await expect(activeProjectNavigation(page, locale)).toHaveAttribute(
        "aria-current",
        "page",
      );
      await expectCollapsedProjectTooltip(page, locale);
      expect(session.preferenceRequests).toEqual([]);
    });
  }

  test("uses responsive compact navigation without issuing a preference PUT", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    const session = await installSession(page, "en");
    await installProjectApis(page);
    await openLiveProject(page, "en");

    const shell = page.locator(".app-shell");
    await expect(shell).toHaveAttribute("data-navigation-collapsed", "false");
    await page.setViewportSize({ height: 768, width: 700 });
    await expect(shell).toHaveAttribute("data-navigation-collapsed", "true");
    await expect(shell).toHaveAttribute("data-navigation-preference", "full");
    await expect(shell).toHaveAttribute("data-navigation-responsive", "true");
    await expect(
      page.getByRole("button", {
        name: translate("en", "Navigation is compact at this window size."),
      }),
    ).toBeDisabled();
    expect(session.preferenceRequests).toEqual([]);

    await page.setViewportSize({ height: 768, width: 1366 });
    await expect(shell).toHaveAttribute("data-navigation-collapsed", "false");
    await expect(shell).toHaveAttribute("data-navigation-responsive", "false");
    expect(session.preferenceRequests).toEqual([]);
  });

  test("keeps every domain command keyboard-accessible in collapsed navigation at 150 percent", async ({
    page,
  }) => {
    await page.setViewportSize(
      effectiveViewport({ height: 768, width: 1366 }, 1.5),
    );
    const session = await installSession(page, "en", true);
    await installProjectApis(page);
    await openLiveProject(page, "en");

    const navigation = domainNavigation(page, "en");
    const administration = navigation.locator(
      `[aria-label="${translate("en", "Administration")}"]`,
    );
    await administration.focus();
    await expect(administration).toBeFocused();
    await expect(administration).toBeInViewport();
    await expect
      .poll(() => navigation.evaluate((element) => element.scrollTop))
      .toBeGreaterThan(0);
    await expect(
      page.getByRole("button", {
        name: translate("en", "Expand domain navigation"),
      }),
    ).toBeVisible();
    await expect(
      page
        .locator(".environment-marker")
        .getByText(translate("en", "Test environment"), { exact: true }),
    ).toBeVisible();

    const tooltip = page.getByRole("tooltip", {
      name: new RegExp(translate("en", "Administration"), "u"),
    });
    await expect(tooltip).toBeVisible();
    const [tooltipBounds, viewport] = await Promise.all([
      tooltip.boundingBox(),
      Promise.resolve(page.viewportSize()),
    ]);
    expect(tooltipBounds).not.toBeNull();
    expect(viewport).not.toBeNull();
    if (!tooltipBounds || !viewport) {
      throw new Error("Collapsed navigation geometry was unavailable.");
    }
    expect(tooltipBounds.x).toBeGreaterThanOrEqual(0);
    expect(tooltipBounds.y).toBeGreaterThanOrEqual(0);
    expect(tooltipBounds.x + tooltipBounds.width).toBeLessThanOrEqual(
      viewport.width,
    );
    expect(tooltipBounds.y + tooltipBounds.height).toBeLessThanOrEqual(
      viewport.height,
    );
    expect(session.preferenceRequests).toEqual([]);
    await expectNoDocumentOverflow(page);
  });

  test("supports Ctrl and Meta command shortcuts, complete list navigation, unavailable live commands, and focus restore", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installProjectApis(page);
    await openLiveProject(page, "en");

    const trigger = page.getByRole("button", {
      name: translate("en", "Open command palette"),
    });
    await expect(trigger).toHaveAttribute(
      "aria-keyshortcuts",
      "Control+K Meta+K",
    );
    await expect(page.locator("#command-palette-trigger")).toContainText(
      "Ctrl/⌘+K",
    );
    await trigger.focus();
    await page.keyboard.press("Control+K");

    let dialog = page.getByRole("dialog", {
      name: translate("en", "Command palette"),
    });
    let search = dialog.getByRole("searchbox", {
      name: translate("en", "Search commands"),
    });
    await expect(search).toBeFocused();
    await expect(dialog).toContainText(
      `Enter ${translate("en", "Open selected command")}`,
    );
    await search.fill(translate("en", "Part"));
    const part = commandButton(dialog, translate("en", "Open Part"));
    await expect(part).toHaveAttribute("aria-disabled", "true");
    await search.press("ArrowDown");
    await expect(part).toBeFocused();
    await part.press("Enter");
    await expect(dialog).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}`));
    await part.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();

    await page.keyboard.press("Meta+K");
    dialog = page.getByRole("dialog", {
      name: translate("en", "Command palette"),
    });
    search = dialog.getByRole("searchbox", {
      name: translate("en", "Search commands"),
    });
    await expect(search).toBeFocused();
    await expect(
      commandButton(dialog, translate("en", "Open Part")),
    ).toHaveAttribute("aria-disabled", "true");
    await expect(
      commandButton(dialog, translate("en", "Open Project Tooling")),
    ).toHaveAttribute("aria-disabled", "false");
    await expect(
      commandButton(dialog, translate("en", "Open Project Trial planning")),
    ).toHaveAttribute("aria-disabled", "false");

    const commandButtons = dialog.getByRole("button");
    await expect(commandButtons).toHaveCount(9);
    await search.press("ArrowDown");
    await expect(commandButtons.first()).toBeFocused();
    await commandButtons.first().press("ArrowUp");
    await expect(commandButtons.last()).toBeFocused();
    await commandButtons.last().press("Home");
    await expect(commandButtons.first()).toBeFocused();
    await commandButtons.first().press("End");
    await expect(commandButtons.last()).toBeFocused();
    await commandButtons.last().press("Home");
    for (let index = 0; index < 4; index += 1) {
      await page.keyboard.press("ArrowDown");
    }
    await expect(commandButtons.nth(4)).toBeFocused();
    await commandButtons.nth(4).press("Enter");
    await expect(dialog).toHaveCount(0);
    await expect
      .poll(() => new URL(page.url()).pathname)
      .toBe(`/projects/${projectId}`);
    const commandTarget = new URL(page.url());
    expect(commandTarget.searchParams.get("returnTo")).toBe(
      `/projects/${projectId}?lang=en`,
    );
  });

  test("checks the existing learning GET before exposing live Project quick-create and keeps returnTo internal", async ({
    page,
  }) => {
    await installSession(page, "en");
    const project = await installProjectApis(page);
    const forgedReturnTarget = encodeURIComponent(
      "https://outside.example.invalid/projects/escape",
    );
    await openLiveProject(page, "en", `&returnTo=${forgedReturnTarget}`);

    const quickCreate = page.getByRole("button", {
      name: translate("en", "Quick create"),
    });
    await quickCreate.click();
    let create = page.getByRole("button", {
      name: translate("en", "Create Project learning record"),
    });
    await expect(create).toBeVisible();
    expect(project.learningRequests).toHaveLength(1);
    expect(project.learningRequests[0]?.pathname).toBe(
      `/api/npi/v1/projects/${projectId}/learning`,
    );
    expect([
      ...new URLSearchParams(project.learningRequests[0]?.search),
    ]).toEqual([["limit", "1"]]);

    await create.focus();
    await create.press("Escape");
    await expect(
      page.getByRole("dialog", {
        name: translate("en", "Contextual quick-create"),
      }),
    ).toHaveCount(0);
    await expect(quickCreate).toBeFocused();

    await quickCreate.click();
    create = page.getByRole("button", {
      name: translate("en", "Create Project learning record"),
    });
    await expect(create).toBeVisible();
    await create.focus();
    await page.keyboard.press("Control+K");
    const commandDialog = page.getByRole("dialog", {
      name: translate("en", "Command palette"),
    });
    await expect(
      commandDialog.getByRole("searchbox", {
        name: translate("en", "Search commands"),
      }),
    ).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(commandDialog).toHaveCount(0);
    await expect(
      page.getByRole("button", {
        name: translate("en", "Open command palette"),
      }),
    ).toBeFocused();
    await expect(page.locator("body")).not.toBeFocused();

    await quickCreate.click();
    create = page.getByRole("button", {
      name: translate("en", "Create Project learning record"),
    });
    await expect(create).toBeVisible();
    expect(project.learningRequests).toHaveLength(3);
    await create.click();
    await expect
      .poll(() => new URL(page.url()).searchParams.get("tab"))
      .toBe("learning");
    const target = new URL(page.url());
    expect(target.pathname).toBe(`/projects/${projectId}`);
    expect(target.searchParams.get("quickCreate")).toBe("learning");
    expect(target.searchParams.get("returnTo")).toBe(
      `/projects/${projectId}?lang=en`,
    );
    expect(target.search).not.toContain("outside.example.invalid");
    await expect(
      page.getByRole("textbox", {
        exact: true,
        name: translate("en", "Title"),
      }),
    ).toBeFocused();
  });

  test("does not expose live Project quick-create when the learning capability is false", async ({
    page,
  }) => {
    await installSession(page, "en");
    const project = await installProjectApis(page, false);
    await openLiveProject(page, "en");

    await page
      .getByRole("button", { name: translate("en", "Quick create") })
      .click();
    await expect(
      page.getByText(
        translate(
          "en",
          "Your current Project capability does not allow creating a learning record.",
        ),
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: translate("en", "Create Project learning record"),
      }),
    ).toHaveCount(0);
    expect(project.learningRequests).toHaveLength(1);
    expect([
      ...new URLSearchParams(project.learningRequests[0]?.search),
    ]).toEqual([["limit", "1"]]);
  });

  test("has no basic WCAG A or AA axe violations with the command palette closed or open", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installProjectApis(page);
    await openLiveProject(page, "en");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);

    await page.keyboard.press("Control+K");
    await expect(
      page.getByRole("dialog", {
        name: translate("en", "Command palette"),
      }),
    ).toBeVisible();
    const commandResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(commandResults.violations).toEqual([]);
  });
});

async function settleVisual(page: Page, locale: TestLocale): Promise<void> {
  await expectNoMixedLanguage(page, locale);
  await expectNoDocumentOverflow(page);
  await page.addStyleTag({
    content:
      "*, *::before, *::after { animation: none !important; caret-color: transparent !important; transition: none !important; }",
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

test.describe("@visual R1-03 application Shell", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`captures full, collapsed, and command Shell states in ${locale} at 1366x768`, async ({
      page,
    }) => {
      await page.setViewportSize({ height: 768, width: 1366 });
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      const session = await installSession(page, locale);
      await installProjectApis(page);
      await openLiveProject(page, locale);
      await settleVisual(page, locale);

      await expect(page).toHaveScreenshot(
        `r1-03-shell-full-${locale}-1366x768-100.png`,
        { fullPage: false },
      );

      await page
        .getByRole("button", {
          name: translate(locale, "Collapse domain navigation"),
        })
        .click();
      await expect(page.locator(".app-shell")).toHaveAttribute(
        "data-navigation-preference",
        "collapsed",
      );
      expect(session.preferenceRequests).toHaveLength(1);
      await settleVisual(page, locale);
      await expect(page).toHaveScreenshot(
        `r1-03-shell-collapsed-${locale}-1366x768-100.png`,
        { fullPage: false },
      );

      await page.keyboard.press("Control+K");
      await expect(
        page.getByRole("dialog", {
          name: translate(locale, "Command palette"),
        }),
      ).toBeVisible();
      await settleVisual(page, locale);
      await expect(page).toHaveScreenshot(
        `r1-03-shell-command-${locale}-1366x768-100.png`,
        { fullPage: false },
      );
    });
  }

  test("captures command Shell at 1920x1080 and 125 percent", async ({
    page,
  }) => {
    const locale = "zh";
    await page.setViewportSize(
      effectiveViewport({ height: 1080, width: 1920 }, 1.25),
    );
    await page.emulateMedia({
      colorScheme: "light",
      reducedMotion: "reduce",
    });
    await installSession(page, locale);
    await installProjectApis(page);
    await openLiveProject(page, locale);
    await page.keyboard.press("Control+K");
    await expect(
      page.getByRole("dialog", {
        name: translate(locale, "Command palette"),
      }),
    ).toBeVisible();
    await settleVisual(page, locale);
    await expect(page).toHaveScreenshot(
      "r1-03-shell-command-zh-1920x1080-125.png",
      { fullPage: false },
    );
  });

  test("captures collapsed focus and tooltip at 1366x768 and 150 percent", async ({
    page,
  }) => {
    const locale = "zh-TW";
    await page.setViewportSize(
      effectiveViewport({ height: 768, width: 1366 }, 1.5),
    );
    await page.emulateMedia({
      colorScheme: "light",
      reducedMotion: "reduce",
    });
    await installSession(page, locale, true);
    await installProjectApis(page);
    await openLiveProject(page, locale);
    const navigation = domainNavigation(page, locale);
    await navigation
      .locator(`[aria-label="${translate(locale, "Administration")}"]`)
      .focus();
    await expect(
      page.getByRole("tooltip", {
        name: new RegExp(translate(locale, "Administration"), "u"),
      }),
    ).toBeVisible();
    await settleVisual(page, locale);
    await expect(page).toHaveScreenshot(
      "r1-03-shell-collapsed-focus-zh-TW-1366x768-150.png",
      { fullPage: false },
    );
  });

  test("captures responsive compact Shell at 1024x768 and 150 percent", async ({
    page,
  }) => {
    const locale = "en";
    await page.setViewportSize(
      effectiveViewport({ height: 768, width: 1024 }, 1.5),
    );
    await page.emulateMedia({
      colorScheme: "light",
      reducedMotion: "reduce",
    });
    const session = await installSession(page, locale);
    await installProjectApis(page);
    await openLiveProject(page, locale);
    await expect(page.locator(".app-shell")).toHaveAttribute(
      "data-navigation-responsive",
      "true",
    );
    expect(session.preferenceRequests).toEqual([]);
    await settleVisual(page, locale);
    await expect(page).toHaveScreenshot(
      "r1-03-shell-responsive-en-1024x768-150.png",
      { fullPage: false },
    );
  });
});
