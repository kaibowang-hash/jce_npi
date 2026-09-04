import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { translate } from "../translate";
import {
  readinessFormalQualityLinks,
  readinessFormalQualityProjection,
  readinessIds,
  readinessWorkspace,
} from "../support/readiness-fixture";
import {
  projectWorkCockpitFixture,
  projectWorkContextFixture,
} from "../support/project-work-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-p8-06-quality-link-browser",
    },
    status: 200,
  });
}

async function installApi(page: Page, locale: TestLocale): Promise<void> {
  await page.route(
    /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u,
    async (route) => {
      await fulfillJson(route, {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: { language: locale, messages: {}, version: "8".repeat(64) },
        csrfToken: "p8-06-formal-quality-link-browser-csrf",
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "quality.lead@example.invalid",
      });
    },
  );
  await page.route(/\/api\/npi\/v1\/projects\/[^/?]+\/.+/u, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    expect(request.method()).toBe("GET");
    if (path.endsWith("/cockpit"))
      return fulfillJson(route, projectWorkCockpitFixture());
    if (path.endsWith("/work-context"))
      return fulfillJson(route, projectWorkContextFixture());
    if (path.endsWith("/npi-readiness"))
      return fulfillJson(route, readinessWorkspace());
    if (path.endsWith("/formal-quality-links"))
      return fulfillJson(route, readinessFormalQualityLinks());
    if (path.endsWith("/erp-projections"))
      return fulfillJson(route, readinessFormalQualityProjection());
    throw new Error(
      `Unexpected P8-06 browser request: ${request.method()} ${path}`,
    );
  });
}

async function openInspector(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${readinessIds.project}?lang=${locale}&tab=readiness`,
    {
      waitUntil: "domcontentloaded",
    },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  const heading = page.getByRole("heading", {
    name: translate(locale, "Formal quality reference"),
  });
  await expect(heading).toBeVisible();
  await heading.evaluate((element) => {
    element.scrollIntoView();
  });
  await expect(page.getByTestId("formal-quality-link-state")).toBeVisible();
}

test.describe("P8-06 formal quality link inspector", () => {
  test("gates the sole link action through Impact Review and performs no browser target call", async ({
    page,
  }) => {
    const requests: string[] = [];
    page.on("request", (request) => requests.push(request.url()));
    await installApi(page, "en");
    await openInspector(page, "en");
    await page
      .getByRole("button", { name: "Link formal quality reference" })
      .click();
    const review = page.getByRole("dialog", {
      name: "Review formal quality link",
    });
    await expect(review).toBeVisible();
    await expect(review).toContainText("Open");
    await expect(review).toContainText("ncr");
    await review.getByRole("button", { name: "Cancel" }).click();
    expect(
      requests.every((url) => {
        const host = new URL(url).hostname;
        return host === "127.0.0.1" || host === "localhost";
      }),
    ).toBe(true);
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p8-06-formal-quality-link-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p8-06-formal-quality-link-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p8-06-formal-quality-link-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P8-06 formal quality link inspector", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installApi(page, visual.locale);
      await page.setViewportSize(
        effectiveViewport(
          { height: visual.height, width: visual.width },
          visual.zoom,
        ),
      );
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      await openInspector(page, visual.locale);
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      const results = await new AxeBuilder({ page })
        .include(".formal-quality-link")
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(results.violations).toEqual([]);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
