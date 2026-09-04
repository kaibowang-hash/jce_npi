import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { translate } from "../translate";
import {
  changeControlIds,
  engineeringChangeDetail,
  engineeringChangeList,
  engineeringChangeSummaryReceipt,
} from "../support/change-control-fixture";
import { projectCockpitFixture } from "../support/project-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

function requestId(route: Route): string {
  const value = route.request().headers()["x-request-id"] ?? "";
  expect(value).toMatch(requestIdPattern);
  return value;
}

async function fulfillJson(
  route: Route,
  body: unknown,
  status = 200,
  replayed?: "true" | "false",
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(replayed ? { "Idempotency-Replayed": replayed } : {}),
      "X-Request-ID": requestId(route),
      "X-Trace-ID": "trace-p9-01-change-browser",
    },
    status,
  });
}

async function installApi(page: Page, locale: TestLocale): Promise<string[]> {
  const observed: string[] = [];
  await page.route(
    /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u,
    async (route) => {
      await fulfillJson(route, {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: { language: locale, messages: {}, version: "8".repeat(64) },
        csrfToken: "p9-01-change-control-browser-csrf-token",
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "engineer@example.invalid",
      });
    },
  );
  await page.route(
    /\/api\/npi\/v1\/projects\/[^/?]+\/cockpit(?:\?.*)?$/u,
    async (route) => {
      observed.push(new URL(route.request().url()).pathname);
      await fulfillJson(route, projectCockpitFixture());
    },
  );
  await page.route(
    /\/api\/npi\/v1\/projects\/[^/?]+\/engineering-changes(?:[/?].*)?$/u,
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      observed.push(path);
      if (request.method() === "POST") {
        expect(request.headers()["x-frappe-csrf-token"]).toBe(
          "p9-01-change-control-browser-csrf-token",
        );
        expect(request.headers()["idempotency-key"]).toMatch(
          /^engineering-change-summary-/u,
        );
        expect(request.postDataJSON()).toEqual({
          expectedRevision: 1,
          expectedRevisionGlobalId: changeControlIds.revision,
          expectedRevisionSnapshotHash: "4".repeat(64),
        });
        await fulfillJson(
          route,
          engineeringChangeSummaryReceipt(),
          202,
          "false",
        );
        return;
      }
      expect(request.method()).toBe("GET");
      await fulfillJson(
        route,
        path.endsWith(changeControlIds.change)
          ? engineeringChangeDetail()
          : engineeringChangeList(),
      );
    },
  );
  return observed;
}

async function openChangeControl(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await page.goto(
    `/projects/${changeControlIds.project}?tab=change-control&lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(
    page.getByRole("heading", { name: translate(locale, "Change control") }),
  ).toBeVisible();
  await expect(page.locator(".change-control-impact-grid")).toHaveCount(0);
  await expect(page.locator(".engineering-table tbody tr")).toHaveCount(12);
}

test.describe("P9-01 live Change Control workspace", () => {
  test("uses only Project-first BFF reads and queues the exact summary command", async ({
    page,
  }) => {
    const browserRequests: string[] = [];
    page.on("request", (request) => browserRequests.push(request.url()));
    const observed = await installApi(page, "en");
    await openChangeControl(page, "en");

    await expect(page.getByText("ECR-0001")).toBeVisible();
    await expect(page.getByText("Approved", { exact: true })).toBeVisible();
    await page
      .getByRole("button", { name: "Request implementation summary" })
      .click();
    const review = page.getByRole("dialog", {
      name: "Review engineering change command",
    });
    await review
      .getByRole("button", { name: "Request implementation summary" })
      .click();
    await expect(page.getByText("queued")).toBeVisible();
    expect(observed).toContain(
      `/api/npi/v1/projects/${changeControlIds.project}/engineering-changes/${changeControlIds.change}:request-implementation-summary`,
    );
    expect(
      browserRequests.every((value) => {
        const url = new URL(value);
        return url.hostname === "127.0.0.1" || url.hostname === "localhost";
      }),
    ).toBe(true);
  });

  test("supports keyboard navigation, exact read-only truth and accessibility", async ({
    page,
  }) => {
    await installApi(page, "en");
    await openChangeControl(page, "en");
    const tab = page.getByRole("tab", { name: "Change control" });
    await tab.focus();
    await expect(tab).toBeFocused();
    await expect(page.getByText("Engineering Change Request")).toBeVisible();
    await expect(page.getByText("Raw ERP status")).toBeVisible();
    await expect(page.getByRole("button", { name: /edit erp/iu })).toHaveCount(
      0,
    );
    await expectNoDocumentOverflow(page);
    await expectIndustrialComputedStyles(page);
    const accessibility = await new AxeBuilder({ page })
      .include("#main-content")
      .analyze();
    expect(accessibility.violations).toEqual([]);
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p9-01-change-control-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p9-01-change-control-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p9-01-change-control-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

for (const visual of visualCases) {
  test(`renders the governed Change Control workspace in ${visual.locale} @visual`, async ({
    page,
  }) => {
    await page.setViewportSize(
      effectiveViewport(
        { height: visual.height, width: visual.width },
        visual.zoom,
      ),
    );
    await installApi(page, visual.locale);
    await openChangeControl(page, visual.locale);
    await expectNoMixedLanguage(page, visual.locale);
    await expectNoDocumentOverflow(page);
    await expectIndustrialComputedStyles(page);
    await page.evaluate(async () => {
      await document.fonts.ready;
    });
    await expect(page).toHaveScreenshot(`${visual.name}.png`, {
      fullPage: true,
    });
  });
}
