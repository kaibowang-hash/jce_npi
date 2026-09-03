import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { notificationPreferenceFixture } from "../support/collaboration-fixture";
import { configurationFixture } from "../support/reporting-fixture";
import { translate } from "../translate";
import {
  effectiveViewport,
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
      "X-Trace-ID": "trace-production-activation-readiness",
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
        catalog: { language: locale, messages: {}, version: "a".repeat(64) },
        csrfToken: "production-activation-csrf-token-fixture-0001",
        deploymentEnvironment: "production",
        isSystemManager: true,
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "system.manager@example.invalid",
      });
    },
  );
  await page.route(
    /\/api\/npi\/v1\/administration\/capabilities(?:\?.*)?$/u,
    async (route) => {
      await fulfillJson(route, configurationFixture());
    },
  );
  await page.route(
    /\/api\/npi\/v1\/notifications(?:[/?].*)?$/u,
    async (route) => {
      await fulfillJson(route, {
        schemaVersion: 1,
        items: [],
        page: { limit: 25, hasMore: false, nextCursor: null },
        permissions: { serverFiltered: true },
      });
    },
  );
  await page.route(
    /\/api\/npi\/v1\/me\/preferences\/notifications(?:\?.*)?$/u,
    async (route) => {
      await fulfillJson(route, notificationPreferenceFixture());
    },
  );
}

async function openReadiness(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/administration?lang=${locale}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(
    page.getByRole("heading", {
      level: 2,
      name: translate(locale, "Production activation readiness"),
    }),
  ).toBeVisible();
}

test("shows server-observed access and ERPNext activation truth", async ({
  page,
}) => {
  await installApi(page, "en");
  await openReadiness(page, "en");
  const readiness = page
    .getByRole("heading", { name: "Production activation readiness" })
    .locator("xpath=following-sibling::div[1]");
  await expect(readiness.getByText("Production environment")).toBeVisible();
  await expect(readiness.getByText("Sign-in and MFA")).toBeVisible();
  await expect(
    readiness.getByText("LaunchFlow user provisioning"),
  ).toBeVisible();
  await expect(readiness.getByText("Implementation required")).toHaveCount(2);
  await expect(
    readiness.getByRole("link", { name: "Open Frappe administration" }),
  ).toHaveAttribute("href", "/app");
  await expectNoDocumentOverflow(page);
  const accessibility = await new AxeBuilder({ page })
    .include("#main-content")
    .analyze();
  expect(accessibility.violations).toEqual([]);
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "production-activation-readiness-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "production-activation-readiness-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "production-activation-readiness-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual production activation readiness", () => {
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
      await openReadiness(page, visual.locale);
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await page.evaluate(async () => {
        await document.fonts.ready;
      });
      await expect(page.locator(".page--reporting")).toHaveScreenshot(
        `${visual.name}.png`,
      );
    });
  }
});
