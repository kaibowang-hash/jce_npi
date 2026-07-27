import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import {
  defaultMyWorkGridLayout,
  defaultMyWorkGridPreferences,
  isMyWorkGridFilter,
  isMyWorkGridLayout,
  myWorkGridColumnWidthSpecs,
  myWorkGridViewIds,
  myWorkTableSchemaVersion,
  type MyWorkGridPreferences,
  type SaveMyWorkGridPreference,
} from "../../src/api/grid-preferences-data-source";
import type { ProblemDetails } from "../../src/api/http";
import {
  defaultMyWorkInspectorPreference,
  isSaveMyWorkInspectorPreference,
} from "../../src/api/my-work-inspector-preferences-data-source";
import { isMyWorkPageResponse } from "../../src/api/my-work-data-source";
import type {
  MyWorkItemViewModel,
  MyWorkPageViewModel,
} from "../../src/domain/view-models";
import { translate } from "../../src/i18n/runtime";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const laterProjectId = "99999999-9999-4999-8999-999999999999";
const workItemId = "22222222-2222-4222-8222-222222222222";
const gateId = "33333333-3333-4333-8333-333333333333";
const csrfToken = "c".repeat(32);
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const myWorkEndpoint = /\/api\/npi\/v1\/me\/work(?:\?.*)?$/u;
const gridPreferenceEndpoint =
  /\/api\/npi\/v1\/me\/preferences\/my-work-grid(?:\?.*)?$/u;
const inspectorPreferenceEndpoint =
  /\/api\/npi\/v1\/me\/preferences\/my-work-inspector(?:\?.*)?$/u;
const preferencePath = "/api/npi/v1/me/preferences/my-work-grid";

interface ObservedPreferencePut {
  body: SaveMyWorkGridPreference;
  csrf: string | undefined;
  requestId: string;
}

interface GridPreferenceHarness {
  confirmed: () => MyWorkGridPreferences;
  getCount: () => number;
  puts: ObservedPreferencePut[];
}

function requestId(route: Route): string {
  const value = route.request().headers()["x-request-id"] ?? "";
  expect(value).toMatch(requestIdPattern);
  return value;
}

function expectSafeGet(route: Route): void {
  const request = route.request();
  const headers = request.headers();
  expect(request.method()).toBe("GET");
  expect(headers.accept).toBe("application/json, application/problem+json");
  expect(headers["x-frappe-csrf-token"]).toBeUndefined();
  expect(headers["idempotency-key"]).toBeUndefined();
  requestId(route);
}

async function fulfillApi(
  route: Route,
  body: unknown,
  options: { status?: number; traceId: string },
): Promise<void> {
  const status = options.status ?? 200;
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type":
        status >= 400 ? "application/problem+json" : "application/json",
      "X-Request-ID": requestId(route),
      "X-Trace-ID": options.traceId,
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    expectSafeGet(route);
    await fulfillApi(
      route,
      {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: {
          language: locale,
          messages: {},
          version: "f".repeat(64),
        },
        csrfToken,
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "engineer@example.invalid",
      },
      { traceId: "trace-r1-04-session" },
    );
  });
}

function myWorkPageFixture(itemCount = 2): MyWorkPageViewModel {
  const page: MyWorkPageViewModel = {
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
    items: [
      {
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
      },
      {
        action: "open_gate_review",
        blocking: false,
        category: "approval",
        context: {
          code: "G3",
          globalId: gateId,
          title: "Tooling release",
          type: "gate",
        },
        dueAt: "2026-07-25T02:00:00Z",
        dueState: "overdue",
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        priority: { scheme: "gate_requirement_priority", value: "P0" },
        project: {
          businessCode: "NPI-26099",
          globalId: laterProjectId,
          title: "Later-page project",
        },
        source: {
          globalId: gateId,
          type: "gate_review_assignment",
          version: 7,
        },
        sourceStatus: {
          editableIn: "NPI_ONE",
          sourceSystem: "NPI_ONE",
          syncState: "local",
        },
        status: "waiting",
        target: {
          gateId,
          kind: "gate_review",
          projectId: laterProjectId,
        },
        title: "Review Gate G3 evidence",
        why: "gate_review_step",
      },
    ],
    nextCursor: null,
    projectOptions: [
      {
        businessCode: "NPI-26018",
        globalId: projectId,
        title: "Battery housing",
      },
      {
        businessCode: "NPI-26099",
        globalId: laterProjectId,
        title: "Later-page project",
      },
    ],
    timeZone: "America/Los_Angeles",
  };
  if (itemCount <= page.items.length) return page;
  const template = page.items[0];
  if (template?.target.kind !== "my_work_item") return page;
  const additionalItems: MyWorkItemViewModel[] = Array.from(
    { length: itemCount - page.items.length },
    (_, offset): MyWorkItemViewModel => {
      const itemNumber = offset + page.items.length + 1;
      const suffix = String(itemNumber).padStart(12, "0");
      const itemGlobalId = `44444444-4444-4444-8444-${suffix}`;
      return {
        ...template,
        context: {
          ...template.context,
          code: `RISK-${String(itemNumber).padStart(3, "0")}`,
          globalId: itemGlobalId,
          title: `Hot runner delivery risk ${String(itemNumber)}`,
        },
        dueAt: `2026-07-25T03:${String(offset).padStart(2, "0")}:00Z`,
        id: `55555555-5555-4555-8555-${suffix}`,
        source: {
          ...template.source,
          globalId: itemGlobalId,
          version: itemNumber,
        },
        target: {
          kind: "my_work_item",
          workItemId: itemGlobalId,
        },
        title: `Hot runner delivery risk ${String(itemNumber)}`,
      };
    },
  );
  return {
    ...page,
    counts: {
      ...page.counts,
      all: { availability: "available", value: itemCount },
      blockers: { availability: "available", value: itemCount - 1 },
      overdue: { availability: "available", value: itemCount },
    },
    items: [...page.items, ...additionalItems],
  };
}

function filteredMyWorkPage(url: URL, itemCount = 2): MyWorkPageViewModel {
  const page = myWorkPageFixture(itemCount);
  let items = [...page.items];
  const view = url.searchParams.get("view") ?? "all";
  if (view === "today" || view === "integration") {
    items = [];
  } else if (view === "overdue") {
    items = items.filter((item) => item.dueState === "overdue");
  } else if (view === "approvals") {
    items = items.filter((item) => item.category === "approval");
  } else if (view === "blockers") {
    items = items.filter((item) => item.blocking);
  } else if (view === "waiting") {
    items = items.filter((item) => item.status === "waiting");
  }
  const requestedProject = url.searchParams.get("projectId");
  if (requestedProject) {
    items = items.filter((item) => item.project.globalId === requestedProject);
  }
  const priorityScheme = url.searchParams.get("priorityScheme");
  const priorityValue = url.searchParams.get("priorityValue");
  if (priorityScheme && priorityValue) {
    items = items.filter(
      (item) =>
        item.priority?.scheme === priorityScheme &&
        item.priority.value === priorityValue,
    );
  }
  const search = url.searchParams.get("search")?.toLocaleLowerCase();
  if (search) {
    items = items.filter((item) =>
      [item.title, item.context.code, item.context.title].some((value) =>
        value.toLocaleLowerCase().includes(search),
      ),
    );
  }
  return { ...page, items };
}

async function installMyWorkApi(
  page: Page,
  options: { itemCount?: number } = {},
): Promise<URL[]> {
  const requests: URL[] = [];
  await page.route(myWorkEndpoint, async (route) => {
    expectSafeGet(route);
    const url = new URL(route.request().url());
    requests.push(url);
    const response = filteredMyWorkPage(url, options.itemCount);
    expect(isMyWorkPageResponse(response)).toBe(true);
    await fulfillApi(route, response, {
      traceId: "trace-r1-04-my-work",
    });
  });
  return requests;
}

function applyPreferencePut(
  current: MyWorkGridPreferences,
  command: SaveMyWorkGridPreference,
): MyWorkGridPreferences {
  return {
    ...current,
    defaultProjectId: command.defaultProjectId,
    favoriteViewIds: [...command.favoriteViewIds],
    recentViewIds: [...command.recentViewIds],
    version: current.version + 1,
    viewLayouts: current.viewLayouts.map((candidate) =>
      candidate.viewId === command.viewId
        ? {
            filter: command.saveFilter
              ? structuredClone(command.filter)
              : candidate.filter,
            hasSavedFilter: command.saveFilter
              ? true
              : candidate.hasSavedFilter,
            layout: structuredClone(command.layout),
            viewId: candidate.viewId,
          }
        : candidate,
    ),
  };
}

function conflictPreference(
  current: MyWorkGridPreferences,
): MyWorkGridPreferences {
  return {
    ...current,
    favoriteViewIds: ["today"],
    version: current.version + 3,
    viewLayouts: current.viewLayouts.map((candidate) =>
      candidate.viewId === "all"
        ? {
            ...candidate,
            layout: {
              ...candidate.layout,
              widths: { ...candidate.layout.widths, type: 176 },
            },
          }
        : candidate,
    ),
  };
}

function preferenceConflict(): ProblemDetails {
  return {
    code: "PREFERENCE_VERSION_CONFLICT",
    retryable: true,
    status: 409,
    title: "The personal grid preference changed on another client.",
    traceId: "trace-r1-04-grid-conflict",
    type: "urn:npi:problem:preference-version-conflict",
  };
}

function preferenceSaveUnavailable(): ProblemDetails {
  return {
    code: "GRID_PREFERENCE_SAVE_UNAVAILABLE",
    retryable: true,
    status: 503,
    title: "Personal grid settings could not be saved.",
    traceId: "trace-r1-04-grid-save-unavailable",
    type: "urn:npi:problem:grid-preference-save-unavailable",
  };
}

async function installGridPreferenceApi(
  page: Page,
  options: {
    conflictOnPut?: number;
    failureOnPut?: number;
    recoveryReason?: MyWorkGridPreferences["recoveryReason"];
  } = {},
): Promise<GridPreferenceHarness> {
  let confirmed: MyWorkGridPreferences = {
    ...structuredClone(defaultMyWorkGridPreferences()),
    recoveryReason: options.recoveryReason ?? null,
    version: 4,
  };
  let getCount = 0;
  const puts: ObservedPreferencePut[] = [];
  let inspectorPreference = defaultMyWorkInspectorPreference();

  await page.route(inspectorPreferenceEndpoint, async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      expectSafeGet(route);
      await fulfillApi(route, inspectorPreference, {
        traceId: "trace-r1-04-inspector-get",
      });
      return;
    }
    expect(request.method()).toBe("PUT");
    const candidate: unknown = request.postDataJSON();
    expect(isSaveMyWorkInspectorPreference(candidate)).toBe(true);
    if (!isSaveMyWorkInspectorPreference(candidate)) {
      throw new Error("The inspector preference command must be valid.");
    }
    inspectorPreference = {
      ...inspectorPreference,
      collapsed: candidate.collapsed,
      recoveryReason: null,
      widthPx: candidate.widthPx,
    };
    await fulfillApi(route, inspectorPreference, {
      traceId: "trace-r1-04-inspector-put",
    });
  });

  await page.route(gridPreferenceEndpoint, async (route) => {
    const request = route.request();
    const headers = request.headers();
    if (request.method() === "GET") {
      expectSafeGet(route);
      getCount += 1;
      await fulfillApi(route, confirmed, {
        traceId: "trace-r1-04-grid-get",
      });
      return;
    }

    expect(request.method()).toBe("PUT");
    expect(headers.accept).toBe("application/json, application/problem+json");
    expect(headers["content-type"]).toBe("application/json");
    expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
    expect(headers["idempotency-key"]).toBeUndefined();
    const observedRequestId = requestId(route);
    const candidate: unknown = request.postDataJSON();
    expect(candidate).not.toBeNull();
    expect(typeof candidate).toBe("object");
    expect(Array.isArray(candidate)).toBe(false);
    const record = candidate as Record<string, unknown>;
    expect(Object.keys(record)).toEqual([
      "defaultProjectId",
      "expectedVersion",
      "favoriteViewIds",
      "filter",
      "layout",
      "recentViewIds",
      "saveFilter",
      "tableSchemaVersion",
      "viewId",
    ]);
    expect(record.tableSchemaVersion).toBe(myWorkTableSchemaVersion);
    expect(myWorkGridViewIds).toContain(record.viewId);
    expect(isMyWorkGridFilter(record.filter)).toBe(true);
    expect(isMyWorkGridLayout(record.layout)).toBe(true);
    expect(typeof record.saveFilter).toBe("boolean");
    expect(record.expectedVersion).toBe(confirmed.version);
    expect(record).not.toHaveProperty("userId");
    expect(record).not.toHaveProperty("gridId");
    expect(record).not.toHaveProperty("preferenceKey");
    const body = candidate as SaveMyWorkGridPreference;
    puts.push({
      body: structuredClone(body),
      csrf: headers["x-frappe-csrf-token"],
      requestId: observedRequestId,
    });

    if (puts.length === options.conflictOnPut) {
      confirmed = conflictPreference(confirmed);
      await fulfillApi(route, preferenceConflict(), {
        status: 409,
        traceId: "trace-r1-04-grid-conflict",
      });
      return;
    }

    if (puts.length === options.failureOnPut) {
      await fulfillApi(route, preferenceSaveUnavailable(), {
        status: 503,
        traceId: "trace-r1-04-grid-save-unavailable",
      });
      return;
    }

    confirmed = applyPreferencePut(confirmed, body);
    await fulfillApi(route, confirmed, {
      traceId: "trace-r1-04-grid-put",
    });
  });

  return {
    confirmed: () => structuredClone(confirmed),
    getCount: () => getCount,
    puts,
  };
}

async function waitForLiveGrid(page: Page, locale: TestLocale): Promise<void> {
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: translate(locale, "My Work"),
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: translate(locale, "My Work grid") }),
  ).toBeVisible();
  await expect(page.locator('.worklist-panel [aria-busy="true"]')).toHaveCount(
    0,
  );
}

async function openLiveGrid(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/work?lang=${locale}`, { waitUntil: "domcontentloaded" });
  await waitForLiveGrid(page, locale);
}

async function waitForDarkWordmark(page: Page): Promise<void> {
  const wordmark = page.locator('img[data-brand-context="wordmark-dark"]');
  await expect(wordmark).toBeVisible();
  await expect
    .poll(() =>
      wordmark.evaluate(
        (image) =>
          (image as HTMLImageElement).complete &&
          (image as HTMLImageElement).naturalWidth > 0,
      ),
    )
    .toBe(true);
}

function typeSeparator(page: Page, locale: TestLocale) {
  return page.getByRole("separator", {
    name: translate(locale, "Resize {{column}} column", {
      column: translate(locale, "Type"),
    }),
  });
}

async function runPreferenceAction(
  page: Page,
  action: () => Promise<unknown>,
): Promise<void> {
  const response = page.waitForResponse(
    (candidate) =>
      new URL(candidate.url()).pathname === preferencePath &&
      candidate.request().method() === "PUT",
  );
  await action();
  await response;
}

async function settleBrowserUpdates(page: Page): Promise<void> {
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            resolve();
          });
        });
      }),
  );
}

async function resetScreenshotScrollPosition(page: Page): Promise<void> {
  await page.evaluate(() => {
    globalThis.scrollTo(0, 0);
    const mainContent = document.querySelector<HTMLElement>("#main-content");
    if (!mainContent) {
      throw new Error("Expected #main-content before visual capture.");
    }
    mainContent.scrollTo(0, 0);
  });
  await expect
    .poll(() =>
      page.evaluate(() => {
        const mainContent =
          document.querySelector<HTMLElement>("#main-content");
        return {
          mainContentLeft: mainContent?.scrollLeft ?? -1,
          mainContentTop: mainContent?.scrollTop ?? -1,
          windowLeft: globalThis.scrollX,
          windowTop: globalThis.scrollY,
        };
      }),
    )
    .toEqual({
      mainContentLeft: 0,
      mainContentTop: 0,
      windowLeft: 0,
      windowTop: 0,
    });
}

async function openGridSettings(page: Page, locale: TestLocale) {
  await page
    .getByRole("button", { name: translate(locale, "Grid settings") })
    .click();
  const settings = page.getByRole("region", {
    name: translate(locale, "Personal grid settings"),
  });
  await expect(settings).toBeVisible();
  await expect(
    settings.getByText(
      translate(locale, "Personal grid settings are confirmed by the server."),
      { exact: true },
    ),
  ).toBeVisible();
  return settings;
}

async function setInspectorWidth(
  page: Page,
  locale: TestLocale,
  width: number,
): Promise<void> {
  expect(width).toBe(340);
  const separator = page.getByRole("separator", {
    name: translate(locale, "Resize inspector"),
  });
  if (await separator.isVisible()) {
    await separator.dblclick();
    await expect(separator).toHaveAttribute("aria-valuenow", String(width));
  } else {
    await expect(separator).toBeHidden();
  }
}

async function expectMainContentVerticalGeometry(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  const main = page.locator("#main-content");
  const context = page.locator(".page-heading");
  const worklist = page.locator(".worklist-panel");
  const inspector = page.getByRole("complementary", {
    name: translate(locale, "Work item details"),
  });
  const action = inspector.getByRole("button", {
    name: translate(locale, "View work item"),
  });
  await expect(context).toBeVisible();
  await expect(worklist).toBeVisible();
  await expect(inspector).toBeVisible();
  await expect(action).toBeVisible();

  const [mainBox, contextBox, actionBox, worklistBox, inspectorBox] =
    await Promise.all([
      main.boundingBox(),
      context.boundingBox(),
      action.boundingBox(),
      worklist.boundingBox(),
      inspector.boundingBox(),
    ]);
  if (!mainBox || !contextBox || !actionBox || !worklistBox || !inspectorBox) {
    throw new Error("The 1440×900 My Work geometry must be measurable.");
  }
  const mainBottom = mainBox.y + mainBox.height;
  for (const [label, box] of [
    ["context", contextBox],
    ["primary action", actionBox],
    ["worklist", worklistBox],
    ["inspector", inspectorBox],
  ] as const) {
    expect(
      box.y,
      `${label} must start inside main content`,
    ).toBeGreaterThanOrEqual(mainBox.y - 1);
    expect(
      box.y + box.height,
      `${label} must end inside main content`,
    ).toBeLessThanOrEqual(mainBottom + 1);
  }
  expect(Math.abs(inspectorBox.width - 340)).toBeLessThanOrEqual(1);
  const verticalDimensions = await main.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(verticalDimensions.scrollHeight).toBeLessThanOrEqual(
    verticalDimensions.clientHeight + 1,
  );
  const gridDimensions = await page
    .locator(".worklist-panel .dense-grid__viewport")
    .evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }));
  expect(gridDimensions.scrollHeight).toBeGreaterThan(
    gridDimensions.clientHeight,
  );
}

test.describe("R1-04 live My Work grid personalization", () => {
  test("persists sizing, layout, personal view metadata, and filters through the exact current-actor boundary", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1180 });
    await installSession(page, "en");
    const workRequests = await installMyWorkApi(page);
    const grid = await installGridPreferenceApi(page);
    await openLiveGrid(page, "en");
    await expect.poll(grid.getCount).toBeGreaterThan(0);
    await settleBrowserUpdates(page);

    const separator = typeSeparator(page, "en");
    await expect(separator).toHaveAttribute("aria-valuenow", "112");
    await runPreferenceAction(page, () => separator.press("ArrowRight"));
    await expect.poll(() => grid.puts.length).toBe(1);
    expect(grid.puts[0]).toEqual({
      body: {
        defaultProjectId: null,
        expectedVersion: 4,
        favoriteViewIds: [],
        filter: { priority: null, projectId: null, search: "" },
        layout: {
          ...defaultMyWorkGridLayout(),
          widths: { ...defaultMyWorkGridLayout().widths, type: 120 },
        },
        recentViewIds: [],
        saveFilter: false,
        tableSchemaVersion: myWorkTableSchemaVersion,
        viewId: "all",
      },
      csrf: csrfToken,
      requestId: expect.stringMatching(requestIdPattern),
    });
    await expect(separator).toHaveAttribute("aria-valuenow", "120");

    const separatorBox = await separator.boundingBox();
    expect(separatorBox).not.toBeNull();
    if (!separatorBox) {
      throw new Error("The Type resize separator must have layout geometry.");
    }
    const startX = separatorBox.x + separatorBox.width / 2;
    const pointerResponse = page.waitForResponse(
      (candidate) =>
        new URL(candidate.url()).pathname === preferencePath &&
        candidate.request().method() === "PUT",
    );
    await page.mouse.move(startX, separatorBox.y + separatorBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(
      startX + 24,
      separatorBox.y + separatorBox.height / 2,
    );
    await page.mouse.up();
    await pointerResponse;
    await expect.poll(() => grid.puts.length).toBe(2);
    expect(grid.puts[1]?.body.expectedVersion).toBe(5);
    expect(grid.puts[1]?.body.saveFilter).toBe(false);
    expect(grid.puts[1]?.body.layout.widths.type).toBe(144);
    await expect(separator).toHaveAttribute("aria-valuenow", "144");

    await runPreferenceAction(page, () => separator.dblclick());
    await expect.poll(() => grid.puts.length).toBe(3);
    expect(grid.puts[2]?.body.expectedVersion).toBe(6);
    expect(grid.puts[2]?.body.saveFilter).toBe(false);
    const autoFitWidth = grid.puts[2]?.body.layout.widths.type;
    expect(autoFitWidth).toEqual(expect.any(Number));
    expect(autoFitWidth).toBeGreaterThanOrEqual(88);
    expect(autoFitWidth).toBeLessThanOrEqual(180);
    await expect(separator).toHaveAttribute(
      "aria-valuenow",
      String(autoFitWidth),
    );
    await settleBrowserUpdates(page);
    expect(grid.puts).toHaveLength(3);

    const settings = await openGridSettings(page, "en");
    await runPreferenceAction(page, () =>
      settings.getByRole("checkbox", { name: "Why assigned" }).click(),
    );
    await expect.poll(() => grid.puts.length).toBe(4);
    expect(grid.puts[3]?.body.layout.hiddenColumnIds).toEqual(["assignment"]);
    await expect(
      page.getByRole("columnheader", { name: "Why assigned" }),
    ).toHaveCount(0);

    await runPreferenceAction(page, () =>
      settings
        .getByRole("combobox", { name: "Fixed columns" })
        .selectOption("1"),
    );
    await expect.poll(() => grid.puts.length).toBe(5);
    expect(grid.puts[4]?.body.layout.fixedColumnCount).toBe(1);
    await expect(
      page.locator('.dense-grid thead [data-fixed-column="start"]'),
    ).toHaveCount(1);

    await runPreferenceAction(page, () =>
      settings.getByRole("checkbox", { name: "Favorite this view" }).click(),
    );
    await expect.poll(() => grid.puts.length).toBe(6);
    expect(grid.puts[5]?.body.favoriteViewIds).toEqual(["all"]);

    await runPreferenceAction(page, () =>
      settings
        .getByRole("combobox", { name: "Default Project" })
        .selectOption(projectId),
    );
    await expect.poll(() => grid.puts.length).toBe(7);
    expect(grid.puts[6]?.body.defaultProjectId).toBe(projectId);
    expect(grid.puts.slice(0, 7).every(({ body }) => !body.saveFilter)).toBe(
      true,
    );

    const search = page.getByRole("searchbox", { name: "Filter" });
    const priority = page.getByRole("combobox", { name: "Priority" });
    const putCountBeforeTyping = grid.puts.length;
    await search.fill("runner");
    await expect
      .poll(() =>
        workRequests.some(
          (request) => request.searchParams.get("search") === "runner",
        ),
      )
      .toBe(true);
    await settleBrowserUpdates(page);
    expect(grid.puts).toHaveLength(putCountBeforeTyping);

    await priority.selectOption("domain_severity:high");
    await expect
      .poll(() =>
        workRequests.some(
          (request) =>
            request.searchParams.get("priorityScheme") === "domain_severity" &&
            request.searchParams.get("priorityValue") === "high" &&
            request.searchParams.get("search") === "runner",
        ),
      )
      .toBe(true);
    expect(grid.puts).toHaveLength(putCountBeforeTyping);

    await runPreferenceAction(page, () =>
      settings.getByRole("button", { name: "Save current filters" }).click(),
    );
    await expect.poll(() => grid.puts.length).toBe(8);
    expect(grid.puts[7]?.body.saveFilter).toBe(true);
    expect(grid.puts[7]?.body.filter).toEqual({
      priority: { scheme: "domain_severity", value: "high" },
      projectId: null,
      search: "runner",
    });
    expect(
      grid.confirmed().viewLayouts.find(({ viewId }) => viewId === "all")
        ?.hasSavedFilter,
    ).toBe(true);

    const confirmedBeforeReload = grid.confirmed();
    const putCountBeforeReload = grid.puts.length;
    const getCountBeforeReload = grid.getCount();
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForLiveGrid(page, "en");
    await expect.poll(grid.getCount).toBeGreaterThan(getCountBeforeReload);
    await expect(typeSeparator(page, "en")).toHaveAttribute(
      "aria-valuenow",
      String(
        confirmedBeforeReload.viewLayouts[0]?.layout.widths.type ??
          defaultMyWorkGridLayout().widths.type,
      ),
    );
    await expect(
      page.getByRole("columnheader", { name: "Why assigned" }),
    ).toHaveCount(0);
    await expect(page.getByRole("searchbox", { name: "Filter" })).toHaveValue(
      "runner",
    );
    await expect(page.getByRole("combobox", { name: "Priority" })).toHaveValue(
      "domain_severity:high",
    );
    await expect(page.getByRole("combobox", { name: "Project" })).toHaveValue(
      "",
    );
    expect(grid.puts).toHaveLength(putCountBeforeReload);

    const reloadedSettings = await openGridSettings(page, "en");
    await expect(
      reloadedSettings.getByRole("checkbox", { name: "Favorite this view" }),
    ).toBeChecked();
    await expect(
      reloadedSettings.getByRole("combobox", { name: "Fixed columns" }),
    ).toHaveValue("1");
    await expect(
      reloadedSettings.getByRole("combobox", { name: "Default Project" }),
    ).toHaveValue(projectId);
    await expect(
      reloadedSettings.getByRole("checkbox", { name: "Why assigned" }),
    ).not.toBeChecked();

    const viewport = page.locator(".worklist-panel .dense-grid__viewport");
    const dimensions = await viewport.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth);
    const fixedHeader = page
      .locator('.dense-grid thead [data-fixed-column="start"]')
      .first();
    const fixedBefore = await fixedHeader.boundingBox();
    await viewport.evaluate((element) => {
      element.scrollLeft = 240;
    });
    await expect
      .poll(() => viewport.evaluate((element) => element.scrollLeft))
      .toBeGreaterThan(0);
    const fixedAfter = await fixedHeader.boundingBox();
    expect(fixedBefore).not.toBeNull();
    expect(fixedAfter).not.toBeNull();
    expect(Math.abs((fixedAfter?.x ?? 0) - (fixedBefore?.x ?? 0))).toBeLessThan(
      2,
    );
    await expectNoDocumentOverflow(page);
  });

  test("supports keyboard bounds and persists individual and full resets across remount", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 900, width: 1440 });
    await installSession(page, "en");
    await installMyWorkApi(page);
    const grid = await installGridPreferenceApi(page);
    await openLiveGrid(page, "en");
    await expect.poll(grid.getCount).toBeGreaterThan(0);
    await settleBrowserUpdates(page);

    const separator = typeSeparator(page, "en");
    await runPreferenceAction(page, () => separator.press("End"));
    await expect.poll(() => grid.puts.length).toBe(1);
    expect(grid.puts[0]?.body.layout.widths.type).toBe(180);
    await expect(separator).toHaveAttribute("aria-valuenow", "180");

    await runPreferenceAction(page, () => separator.dblclick());
    await expect.poll(() => grid.puts.length).toBe(2);
    const fittedWidth = grid.puts[1]?.body.layout.widths.type;
    expect(fittedWidth).toEqual(expect.any(Number));
    expect(fittedWidth).toBeLessThan(180);
    await expect(separator).toHaveAttribute(
      "aria-valuenow",
      String(fittedWidth),
    );
    const fittedVersion = grid.confirmed().version;
    await separator.dblclick();
    await settleBrowserUpdates(page);
    expect(grid.puts).toHaveLength(2);
    expect(grid.confirmed().version).toBe(fittedVersion);

    await runPreferenceAction(page, () => separator.press("Home"));
    await expect.poll(() => grid.puts.length).toBe(3);
    expect(grid.puts[2]?.body.layout.widths.type).toBe(88);
    await expect(separator).toHaveAttribute("aria-valuenow", "88");

    const settings = await openGridSettings(page, "en");
    await runPreferenceAction(page, () =>
      settings.getByRole("button", { name: "Reset Type width" }).click(),
    );
    await expect.poll(() => grid.puts.length).toBe(4);
    expect(grid.puts[3]?.body.layout.widths.type).toBe(112);
    await expect(separator).toHaveAttribute("aria-valuenow", "112");

    await runPreferenceAction(page, () =>
      settings
        .getByRole("combobox", { name: "Fixed columns" })
        .selectOption("1"),
    );
    await runPreferenceAction(page, () =>
      settings.getByRole("checkbox", { name: "Why assigned" }).click(),
    );
    await expect.poll(() => grid.puts.length).toBe(6);
    expect(grid.puts[5]?.body.layout).toMatchObject({
      fixedColumnCount: 1,
      hiddenColumnIds: ["assignment"],
    });

    await runPreferenceAction(page, () =>
      settings.getByRole("button", { name: "Reset grid layout" }).click(),
    );
    await expect.poll(() => grid.puts.length).toBe(7);
    expect(grid.puts[6]?.body.layout).toEqual(defaultMyWorkGridLayout());
    expect(grid.puts.every(({ body }) => !body.saveFilter)).toBe(true);
    await expect(separator).toHaveAttribute("aria-valuenow", "112");
    await expect(
      page.getByRole("columnheader", { name: "Why assigned" }),
    ).toBeVisible();
    await expect(
      page.locator('.dense-grid thead [data-fixed-column="start"]'),
    ).toHaveCount(2);

    const putCountBeforeRemount = grid.puts.length;
    const getCountBeforeRemount = grid.getCount();
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForLiveGrid(page, "en");
    await expect.poll(grid.getCount).toBeGreaterThan(getCountBeforeRemount);
    await expect(typeSeparator(page, "en")).toHaveAttribute(
      "aria-valuenow",
      "112",
    );
    await expect(
      page.getByRole("columnheader", { name: "Why assigned" }),
    ).toBeVisible();
    await expect(
      page.locator('.dense-grid thead [data-fixed-column="start"]'),
    ).toHaveCount(2);
    expect(grid.puts).toHaveLength(putCountBeforeRemount);
  });

  test("adopts the latest server revision after one 409 save conflict", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installMyWorkApi(page);
    const grid = await installGridPreferenceApi(page, { conflictOnPut: 1 });
    await openLiveGrid(page, "en");
    await expect.poll(grid.getCount).toBeGreaterThan(0);
    await settleBrowserUpdates(page);
    const getCountBeforeConflict = grid.getCount();

    const separator = typeSeparator(page, "en");
    await runPreferenceAction(page, () => separator.press("ArrowRight"));
    await expect.poll(() => grid.puts.length).toBe(1);
    expect(grid.puts[0]?.body.expectedVersion).toBe(4);
    expect(grid.puts[0]?.body.saveFilter).toBe(false);
    expect(grid.puts[0]?.body.layout.widths.type).toBe(120);
    await expect.poll(grid.getCount).toBe(getCountBeforeConflict + 1);
    expect(grid.confirmed().version).toBe(7);
    await expect(separator).toHaveAttribute("aria-valuenow", "176");

    const settings = page.getByRole("region", {
      name: "Personal grid settings",
    });
    await expect(settings).toBeVisible();
    await expect(
      settings.getByText("Not saved", { exact: true }),
    ).toBeVisible();
    await expect(
      settings.getByRole("button", { name: "Due today" }),
    ).toBeVisible();
    await expect(
      settings.getByRole("button", { name: "Reload personal settings" }),
    ).toBeVisible();
  });

  test("restores the confirmed visual and ARIA width after a save failure", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installMyWorkApi(page);
    const grid = await installGridPreferenceApi(page, { failureOnPut: 1 });
    await openLiveGrid(page, "en");
    await expect.poll(grid.getCount).toBeGreaterThan(0);
    const getCountBeforeFailure = grid.getCount();

    const separator = typeSeparator(page, "en");
    const typeColumn = page.locator('col[data-grid-column="type"]');
    await expect(separator).toHaveAttribute("aria-valuenow", "112");
    await expect
      .poll(() =>
        typeColumn.evaluate(
          (column) => (column as HTMLTableColElement).style.width,
        ),
      )
      .toBe("112px");

    await runPreferenceAction(page, () => separator.press("ArrowRight"));
    await expect.poll(() => grid.puts.length).toBe(1);
    expect(grid.puts[0]?.body.layout.widths.type).toBe(120);
    expect(grid.confirmed().viewLayouts[0]?.layout.widths.type).toBe(112);
    expect(grid.getCount()).toBe(getCountBeforeFailure);

    await expect(separator).toHaveAttribute("aria-valuenow", "112");
    await expect
      .poll(() =>
        typeColumn.evaluate(
          (column) => (column as HTMLTableColElement).style.width,
        ),
      )
      .toBe("112px");
    const settings = page.getByRole("region", {
      name: "Personal grid settings",
    });
    await expect(settings).toBeVisible();
    await expect(
      settings.getByText(
        "Personal grid settings were not saved. The last confirmed settings remain active.",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      settings.getByText("Not saved", { exact: true }),
    ).toBeVisible();
  });

  test("opens the settings warning when invalid stored preferences fall back to defaults", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installMyWorkApi(page);
    const grid = await installGridPreferenceApi(page, {
      recoveryReason: "stored_preference_invalid",
    });
    await openLiveGrid(page, "en");
    await expect.poll(grid.getCount).toBeGreaterThan(0);

    const settingsToggle = page.getByRole("button", {
      name: "Grid settings",
    });
    await expect(settingsToggle).toHaveAttribute("aria-expanded", "true");
    const settings = page.getByRole("region", {
      name: "Personal grid settings",
    });
    await expect(settings).toBeVisible();
    await expect(
      settings.getByText("Defaults active", { exact: true }),
    ).toBeVisible();
    await expect(
      settings.getByText(
        "Stored grid settings were invalid. Code-owned defaults are active.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(grid.puts).toHaveLength(0);
  });

  test("keeps persisted widths exact when only required columns remain", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 900, width: 1920 });
    await installSession(page, "en");
    await installMyWorkApi(page);
    const grid = await installGridPreferenceApi(page);
    await openLiveGrid(page, "en");
    await expect.poll(grid.getCount).toBeGreaterThan(0);

    const settings = await openGridSettings(page, "en");
    const optionalColumns = [
      "Type",
      "Project or object",
      "Why assigned",
      "Priority",
      "Due",
      "Status",
    ] as const;
    for (const column of optionalColumns) {
      await runPreferenceAction(page, () =>
        settings.getByRole("checkbox", { exact: true, name: column }).click(),
      );
    }
    await expect.poll(() => grid.puts.length).toBe(optionalColumns.length);
    expect(grid.puts.at(-1)?.body.layout.hiddenColumnIds).toEqual([
      "type",
      "context",
      "assignment",
      "priority",
      "due",
      "status",
    ]);
    expect(grid.puts.every(({ body }) => !body.saveFilter)).toBe(true);

    await expect(
      settings.getByRole("checkbox", { exact: true, name: "Item" }),
    ).toBeDisabled();
    await expect(
      settings.getByRole("checkbox", { exact: true, name: "Next action" }),
    ).toBeDisabled();
    await expect(page.getByRole("columnheader")).toHaveCount(2);

    const table = page.getByRole("table", { name: "My Work grid" });
    const viewport = page.locator(".worklist-panel .dense-grid__viewport");
    const itemHeader = page.locator('.dense-grid th[data-grid-column="item"]');
    const actionHeader = page.locator(
      '.dense-grid th[data-grid-column="action"]',
    );
    const itemSeparator = page.getByRole("separator", {
      name: "Resize Item column",
    });
    const actionSeparator = page.getByRole("separator", {
      name: "Resize Next action column",
    });
    const [tableBox, itemBox, actionBox, tableInlineStyle, viewportDimensions] =
      await Promise.all([
        table.boundingBox(),
        itemHeader.boundingBox(),
        actionHeader.boundingBox(),
        table.evaluate((element) => ({
          minWidth: (element as HTMLTableElement).style.minWidth,
          width: (element as HTMLTableElement).style.width,
        })),
        viewport.evaluate((element) => ({
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
        })),
      ]);
    if (!tableBox || !itemBox || !actionBox) {
      throw new Error("The required grid columns must expose layout geometry.");
    }
    const expectedItemWidth = myWorkGridColumnWidthSpecs.item.default;
    const expectedActionWidth = myWorkGridColumnWidthSpecs.action.default;
    const expectedTableWidth = expectedItemWidth + expectedActionWidth;
    expect(tableInlineStyle).toEqual({
      minWidth: `${String(expectedTableWidth)}px`,
      width: `${String(expectedTableWidth)}px`,
    });
    expect(Math.abs(tableBox.width - expectedTableWidth)).toBeLessThanOrEqual(
      1,
    );
    expect(Math.abs(itemBox.width - expectedItemWidth)).toBeLessThanOrEqual(1);
    expect(Math.abs(actionBox.width - expectedActionWidth)).toBeLessThanOrEqual(
      1,
    );
    expect(itemBox.width).toBeLessThanOrEqual(
      myWorkGridColumnWidthSpecs.item.maximum,
    );
    expect(actionBox.width).toBeLessThanOrEqual(
      myWorkGridColumnWidthSpecs.action.maximum,
    );
    await expect(itemSeparator).toHaveAttribute(
      "aria-valuenow",
      String(expectedItemWidth),
    );
    await expect(actionSeparator).toHaveAttribute(
      "aria-valuenow",
      String(expectedActionWidth),
    );
    expect(viewportDimensions.clientWidth).toBeGreaterThan(tableBox.width);
    expect(viewportDimensions.scrollWidth).toBe(viewportDimensions.clientWidth);
    await expectNoDocumentOverflow(page);
    await expectNoMixedLanguage(page, "en");
  });

  test("keeps horizontal overflow inside the accessible grid viewport", async ({
    page,
  }) => {
    await page.setViewportSize(
      effectiveViewport({ height: 768, width: 1366 }, 1.5),
    );
    await installSession(page, "en");
    await installMyWorkApi(page);
    await installGridPreferenceApi(page);
    await openLiveGrid(page, "en");

    const viewport = page.locator(".worklist-panel .dense-grid__viewport");
    await expect(viewport).toHaveAttribute("tabindex", "0");
    const dimensions = await viewport.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth);
    await expectNoDocumentOverflow(page);
    await expectNoMixedLanguage(page, "en");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  });
});

test.describe("@visual R1-04 grid personalization evidence", () => {
  const profiles = [
    {
      locale: "en",
      nominal: { height: 900, width: 1440 },
      zoom: 1,
    },
    {
      locale: "zh",
      nominal: { height: 900, width: 1440 },
      zoom: 1,
    },
    {
      locale: "zh-TW",
      nominal: { height: 900, width: 1440 },
      zoom: 1,
    },
    {
      locale: "en",
      nominal: { height: 768, width: 1366 },
      zoom: 1,
    },
    {
      locale: "zh",
      nominal: { height: 1080, width: 1920 },
      zoom: 1.25,
    },
    {
      locale: "zh-TW",
      nominal: { height: 768, width: 1366 },
      zoom: 1.5,
    },
  ] as const;

  for (const profile of profiles) {
    test(`grid settings ${profile.locale} ${String(profile.nominal.width)}x${String(profile.nominal.height)} ${String(profile.zoom * 100)}% @visual`, async ({
      page,
    }) => {
      await page.setViewportSize(
        effectiveViewport(profile.nominal, profile.zoom),
      );
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      await installSession(page, profile.locale);
      await installMyWorkApi(page, { itemCount: 20 });
      await installGridPreferenceApi(page);
      await openLiveGrid(page, profile.locale);
      await waitForDarkWordmark(page);
      await setInspectorWidth(page, profile.locale, 340);
      await openGridSettings(page, profile.locale);
      await expect(
        page.locator(".worklist-panel .dense-grid tbody tr"),
      ).toHaveCount(20);

      await expectNoMixedLanguage(page, profile.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      if (profile.zoom > 1) {
        const dimensions = await page
          .locator(".worklist-panel .dense-grid__viewport")
          .evaluate((element) => ({
            clientWidth: element.clientWidth,
            scrollWidth: element.scrollWidth,
          }));
        expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth);
      }
      if (profile.nominal.width === 1440) {
        await expectMainContentVerticalGeometry(page, profile.locale);
      }
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(results.violations).toEqual([]);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await resetScreenshotScrollPosition(page);
      const capturesHeaderBrand =
        profile.nominal.width === 1440 && profile.zoom === 1;
      if (capturesHeaderBrand) {
        const wordmark = page.locator(
          'img[data-brand-context="wordmark-dark"]',
        );
        const wordmarkState = await wordmark.evaluate((element) => {
          const image = element as HTMLImageElement;
          const bounds = image.getBoundingClientRect();
          const style = globalThis.getComputedStyle(image);
          return {
            complete: image.complete,
            display: style.display,
            height: bounds.height,
            naturalHeight: image.naturalHeight,
            naturalWidth: image.naturalWidth,
            opacity: style.opacity,
            source: new URL(image.currentSrc).pathname,
            visibility: style.visibility,
            width: bounds.width,
          };
        });
        expect(wordmarkState).toMatchObject({
          complete: true,
          display: "block",
          opacity: "1",
          visibility: "visible",
        });
        expect(wordmarkState.source).toContain("LaunchFlow-logo_White");
        expect(wordmarkState.naturalHeight).toBeGreaterThan(0);
        expect(wordmarkState.naturalWidth).toBeGreaterThan(0);
        expect(wordmarkState.height).toBeGreaterThan(0);
        expect(wordmarkState.width).toBeGreaterThan(0);
      }

      await expect(page).toHaveScreenshot(
        `r1-04-grid-${profile.locale}-${String(profile.nominal.width)}x${String(profile.nominal.height)}-${String(profile.zoom * 100)}.png`,
        { fullPage: false },
      );
      if (capturesHeaderBrand) {
        await expect(page.locator(".app-header__brand")).toHaveScreenshot(
          `r1-04-header-brand-${profile.locale}-1440x900-100.png`,
          { animations: "disabled" },
        );
      }
    });
  }
});
