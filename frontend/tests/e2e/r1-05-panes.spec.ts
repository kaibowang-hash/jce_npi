import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import {
  defaultMyWorkGridPreferences,
  type MyWorkGridPreferences,
} from "../../src/api/grid-preferences-data-source";
import {
  defaultMyWorkInspectorPreference,
  isSaveMyWorkInspectorPreference,
  myWorkInspectorDefaultWidthPx,
  myWorkInspectorSchemaVersion,
  type MyWorkInspectorPreference,
  type SaveMyWorkInspectorPreference,
} from "../../src/api/my-work-inspector-preferences-data-source";
import { isMyWorkPageResponse } from "../../src/api/my-work-data-source";
import type { MyWorkPageViewModel } from "../../src/domain/view-models";
import { translate } from "../../src/i18n/runtime";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const workItemId = "22222222-2222-4222-8222-222222222222";
const gateId = "33333333-3333-4333-8333-333333333333";
const csrfToken = "c".repeat(32);
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const myWorkEndpoint = /\/api\/npi\/v1\/me\/work(?:\?.*)?$/u;
const gridPreferenceEndpoint =
  /\/api\/npi\/v1\/me\/preferences\/my-work-grid(?:\?.*)?$/u;
const inspectorPreferenceEndpoint =
  /\/api\/npi\/v1\/me\/preferences\/my-work-inspector(?:\?.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

interface ObservedInspectorPut {
  readonly body: SaveMyWorkInspectorPreference;
  readonly csrf: string | undefined;
  readonly requestId: string;
}

interface InspectorHarness {
  readonly confirmed: () => MyWorkInspectorPreference;
  readonly getCount: () => number;
  readonly puts: readonly ObservedInspectorPut[];
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

function myWorkPageFixture(): MyWorkPageViewModel {
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
          businessCode: "NPI-26018",
          globalId: projectId,
          title: "Battery housing",
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
        target: { gateId, kind: "gate_review", projectId },
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
    ],
    timeZone: "America/Los_Angeles",
  };
}

function filteredMyWorkPage(url: URL): MyWorkPageViewModel {
  const fixture = myWorkPageFixture();
  const search = url.searchParams.get("search")?.toLocaleLowerCase();
  if (!search) return fixture;
  return {
    ...fixture,
    items: fixture.items.filter((item) =>
      [item.title, item.context.code, item.context.title].some((value) =>
        value.toLocaleLowerCase().includes(search),
      ),
    ),
  };
}

async function installLiveMyWorkRoutes(
  page: Page,
  locale: TestLocale,
  options: {
    failFirstInspectorPut?: boolean;
    initialCollapsed?: boolean;
    recoveryReason?: MyWorkInspectorPreference["recoveryReason"];
  } = {},
): Promise<InspectorHarness> {
  let confirmed: MyWorkInspectorPreference = {
    ...defaultMyWorkInspectorPreference(),
    collapsed: options.initialCollapsed ?? false,
    recoveryReason: options.recoveryReason ?? null,
  };
  let inspectorGetCount = 0;
  const puts: ObservedInspectorPut[] = [];
  const gridPreference: MyWorkGridPreferences = defaultMyWorkGridPreferences();

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
      { traceId: "trace-r1-05-session" },
    );
  });

  await page.route(myWorkEndpoint, async (route) => {
    expectSafeGet(route);
    const response = filteredMyWorkPage(new URL(route.request().url()));
    expect(isMyWorkPageResponse(response)).toBe(true);
    await fulfillApi(route, response, {
      traceId: "trace-r1-05-my-work",
    });
  });

  await page.route(gridPreferenceEndpoint, async (route) => {
    expectSafeGet(route);
    await fulfillApi(route, gridPreference, {
      traceId: "trace-r1-05-grid-preference",
    });
  });

  await page.route(inspectorPreferenceEndpoint, async (route) => {
    const request = route.request();
    const headers = request.headers();
    if (request.method() === "GET") {
      expectSafeGet(route);
      inspectorGetCount += 1;
      await fulfillApi(route, confirmed, {
        traceId: "trace-r1-05-inspector-get",
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
    expect(isSaveMyWorkInspectorPreference(candidate)).toBe(true);
    const record = candidate as Record<string, unknown>;
    expect(Object.keys(record)).toEqual([
      "schemaVersion",
      "collapsed",
      "widthPx",
    ]);
    expect(record).not.toHaveProperty("userId");
    expect(record).not.toHaveProperty("paneId");
    expect(record).not.toHaveProperty("preferenceKey");
    const body = candidate as SaveMyWorkInspectorPreference;
    puts.push({
      body: structuredClone(body),
      csrf: headers["x-frappe-csrf-token"],
      requestId: observedRequestId,
    });

    if (options.failFirstInspectorPut && puts.length === 1) {
      await fulfillApi(
        route,
        {
          code: "INSPECTOR_PREFERENCE_SAVE_UNAVAILABLE",
          retryable: true,
          status: 503,
          title: "Pane layout could not be saved.",
          traceId: "trace-r1-05-inspector-save-failure",
          type: "urn:npi:problem:inspector-preference-save-unavailable",
        },
        {
          status: 503,
          traceId: "trace-r1-05-inspector-save-failure",
        },
      );
      return;
    }

    confirmed = {
      ...confirmed,
      collapsed: body.collapsed,
      recoveryReason: null,
      widthPx: body.widthPx,
    };
    await fulfillApi(route, confirmed, {
      traceId: "trace-r1-05-inspector-put",
    });
  });

  return {
    confirmed: () => structuredClone(confirmed),
    getCount: () => inspectorGetCount,
    puts,
  };
}

async function openLiveMyWork(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/work?lang=${locale}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("table", { name: translate(locale, "My Work grid") }),
  ).toBeVisible();
  await expect(page.locator('.worklist-panel [aria-busy="true"]')).toHaveCount(
    0,
  );
}

function inspectorSeparator(page: Page, locale: TestLocale) {
  return page.getByRole("separator", {
    name: translate(locale, "Resize inspector"),
  });
}

test.describe("R1-05 live My Work inspector layout", () => {
  test("persists bounded pointer, 20px keyboard, reset, collapse, and expansion through the exact actor boundary", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    const harness = await installLiveMyWorkRoutes(page, "en");
    await openLiveMyWork(page, "en");
    await expect.poll(harness.getCount).toBeGreaterThan(0);

    const separator = inspectorSeparator(page, "en");
    await expect(separator).toBeVisible();
    await expect(separator).toHaveAttribute("aria-valuenow", "340");
    const separatorBox = await separator.boundingBox();
    expect(separatorBox).not.toBeNull();
    if (!separatorBox) {
      throw new Error("The inspector separator must have pointer geometry.");
    }
    const startX = separatorBox.x + separatorBox.width / 2;
    const startY = separatorBox.y + Math.min(24, separatorBox.height / 2);
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX - 40, startY);
    await expect(page.locator(".worklist-layout")).toHaveCSS(
      "--npi-inspector-width",
      "380px",
    );
    expect(harness.puts).toHaveLength(0);
    await page.mouse.up();
    await expect.poll(() => harness.puts.length).toBe(1);
    await expect(separator).toHaveAttribute("aria-valuenow", "380");

    await separator.press("ArrowLeft");
    await expect.poll(() => harness.puts.length).toBe(2);
    expect(harness.puts[1]?.body.widthPx).toBe(400);
    await separator.press("ArrowRight");
    await expect.poll(() => harness.puts.length).toBe(3);
    expect(harness.puts[2]?.body.widthPx).toBe(380);
    await separator.dblclick();
    await expect.poll(() => harness.puts.length).toBe(4);
    expect(harness.puts[3]?.body.widthPx).toBe(myWorkInspectorDefaultWidthPx);

    await page
      .getByRole("searchbox", { name: translate("en", "Filter") })
      .fill("e");
    const gateRow = page
      .getByRole("row")
      .filter({ hasText: "Review Gate G3 evidence" });
    await expect(gateRow).toBeVisible();
    await gateRow.click();
    await expect(gateRow).toHaveAttribute("aria-selected", "true");
    const gridViewport = page.locator(".worklist-panel .dense-grid__viewport");
    await gridViewport.evaluate((element) => {
      element.scrollLeft = 96;
      element.dispatchEvent(new Event("scroll", { bubbles: true }));
    });

    const collapse = page.getByRole("button", {
      name: translate("en", "Collapse inspector"),
    });
    const collapseAction = page.locator(".inspector-controls .npi-icon-action");
    await expect(collapseAction.locator("ix-button")).toHaveAttribute(
      "title",
      translate("en", "Collapse inspector"),
    );
    await expect(collapseAction).toHaveAttribute("data-icon-action", "true");
    await collapse.focus();
    await expect(
      collapseAction.getByRole("tooltip", {
        name: translate("en", "Collapse inspector"),
      }),
    ).toBeVisible();
    await collapse.press("Enter");
    await expect.poll(() => harness.puts.length).toBe(5);
    const expand = page.getByRole("button", {
      name: translate("en", "Expand inspector"),
    });
    await expect(expand).toBeVisible();
    await expect(collapseAction.locator("ix-button")).toHaveAttribute(
      "title",
      translate("en", "Expand inspector"),
    );
    await expect(expand).toBeFocused();
    await expect(
      page.getByRole("searchbox", { name: translate("en", "Filter") }),
    ).toHaveValue("e");
    await expect(gateRow).toHaveAttribute("aria-selected", "true");
    expect(await gridViewport.evaluate((element) => element.scrollLeft)).toBe(
      96,
    );
    await expand.click();
    await expect.poll(() => harness.puts.length).toBe(6);
    await expect(
      page.getByRole("button", {
        name: translate("en", "Collapse inspector"),
      }),
    ).toBeFocused();

    for (const observed of harness.puts) {
      expect(observed.csrf).toBe(csrfToken);
      expect(observed.requestId).toMatch(requestIdPattern);
      expect(observed.body.schemaVersion).toBe(myWorkInspectorSchemaVersion);
      expect(Object.keys(observed.body)).toEqual([
        "schemaVersion",
        "collapsed",
        "widthPx",
      ]);
    }
    expect(harness.confirmed()).toMatchObject({
      collapsed: false,
      recoveryReason: null,
      widthPx: 340,
    });
  });

  test("shows invalid-storage recovery without a repair GET and clears it only after explicit PUT", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    const harness = await installLiveMyWorkRoutes(page, "en", {
      recoveryReason: "stored_preference_invalid",
    });
    await openLiveMyWork(page, "en");

    await expect(
      page.getByText(translate("en", "Defaults active"), { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(
        translate(
          "en",
          "Stored pane layout was invalid. The default layout is active.",
        ),
        { exact: true },
      ),
    ).toBeVisible();
    await expect.poll(harness.getCount).toBeGreaterThan(0);
    const initialGetCount = harness.getCount();
    expect(harness.puts).toHaveLength(0);

    await inspectorSeparator(page, "en").press("ArrowLeft");
    await expect.poll(() => harness.puts.length).toBe(1);
    await expect(
      page.getByText(translate("en", "Confirmed"), { exact: true }),
    ).toBeVisible();
    expect(harness.getCount()).toBe(initialGetCount);
    expect(harness.confirmed().recoveryReason).toBeNull();
  });

  test("rolls back a failed collapse, exposes traceable failure, and reloads without replaying the PUT", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    const harness = await installLiveMyWorkRoutes(page, "en", {
      failFirstInspectorPut: true,
    });
    await openLiveMyWork(page, "en");
    await expect.poll(harness.getCount).toBeGreaterThan(0);
    const initialGetCount = harness.getCount();
    await page
      .getByRole("button", {
        name: translate("en", "Collapse inspector"),
      })
      .click();

    await expect(
      page.getByText(translate("en", "Not saved"), { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Pane layout could not be saved.", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("trace-r1-05-inspector-save-failure", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: translate("en", "Collapse inspector"),
      }),
    ).toBeVisible();
    expect(harness.puts).toHaveLength(1);

    await page
      .getByRole("button", {
        name: translate("en", "Reload pane layout"),
      })
      .click();
    await expect.poll(harness.getCount).toBeGreaterThan(initialGetCount);
    await expect(
      page.getByText(translate("en", "Confirmed"), { exact: true }),
    ).toBeVisible();
    expect(harness.puts).toHaveLength(1);
  });

  test("keeps a failed expansion traceable and moves recovery focus off the disabled expand control", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    const harness = await installLiveMyWorkRoutes(page, "en", {
      failFirstInspectorPut: true,
      initialCollapsed: true,
    });
    await openLiveMyWork(page, "en");
    await expect.poll(harness.getCount).toBeGreaterThan(0);

    await page
      .getByRole("button", {
        name: translate("en", "Expand inspector"),
      })
      .click();

    await expect(
      page.getByText(translate("en", "Not saved"), { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Pane layout could not be saved.", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("trace-r1-05-inspector-save-failure", { exact: true }),
    ).toBeVisible();
    const disabledExpand = page.getByRole("button", {
      name: translate("en", "Expand inspector"),
    });
    await expect(disabledExpand).toBeDisabled();
    await expect(
      page.locator(".inspector-controls .npi-icon-action ix-button"),
    ).toHaveAttribute("title", translate("en", "Expand inspector"));
    await expect(
      page.locator(".inspector-controls .npi-icon-action"),
    ).toHaveAttribute("data-icon-action", "true");
    await expect(
      page.getByRole("button", {
        name: translate("en", "Reload pane layout"),
      }),
    ).toBeFocused();
    await expect(page.locator(".worklist-layout")).toHaveCSS(
      "--npi-inspector-width",
      "340px",
    );
    expect(harness.puts).toHaveLength(1);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  });

  test("treats the stacked breakpoint as presentation only and never writes a preference", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    const harness = await installLiveMyWorkRoutes(page, "en");
    await openLiveMyWork(page, "en");
    const separator = inspectorSeparator(page, "en");
    await expect(separator).toBeVisible();

    await page.setViewportSize({ height: 768, width: 1180 });
    await expect(separator).toBeHidden();
    await page.waitForTimeout(100);
    expect(harness.puts).toHaveLength(0);
    expect(harness.confirmed().widthPx).toBe(340);
    expect(
      await page.evaluate(() => ({
        collapsed: localStorage.getItem("npi-one-inspector-collapsed"),
        width: localStorage.getItem("npi-one-inspector-width"),
      })),
    ).toEqual({ collapsed: null, width: null });
  });
});

test.describe("@visual R1-05 live My Work inspector evidence", () => {
  const profiles = [
    {
      locale: "en",
      nominal: { height: 768, width: 1366 },
      zoom: 1,
    },
    {
      locale: "zh",
      nominal: { height: 900, width: 1440 },
      zoom: 1.25,
    },
    {
      locale: "zh-TW",
      nominal: { height: 1080, width: 1920 },
      zoom: 1.5,
    },
  ] as const;

  for (const profile of profiles) {
    test(`inspector ${profile.locale} ${String(profile.nominal.width)}x${String(profile.nominal.height)} ${String(profile.zoom * 100)}% @visual`, async ({
      page,
    }) => {
      await page.setViewportSize(
        effectiveViewport(profile.nominal, profile.zoom),
      );
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      const harness = await installLiveMyWorkRoutes(page, profile.locale);
      await openLiveMyWork(page, profile.locale);
      await expect.poll(harness.getCount).toBeGreaterThan(0);
      const collapse = page.getByRole("button", {
        name: translate(profile.locale, "Collapse inspector"),
      });
      const collapseAction = page.locator(
        ".inspector-controls .npi-icon-action",
      );
      await collapse.focus();
      await expect(
        collapseAction.getByRole("tooltip", {
          name: translate(profile.locale, "Collapse inspector"),
        }),
      ).toBeVisible();
      await expectNoMixedLanguage(page, profile.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(results.violations).toEqual([]);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await expect(page.locator(".page--work")).toHaveScreenshot(
        `r1-05-inspector-${profile.locale}-${String(profile.nominal.width)}x${String(profile.nominal.height)}-${String(profile.zoom * 100)}.png`,
        { animations: "disabled" },
      );
    });
  }
});
