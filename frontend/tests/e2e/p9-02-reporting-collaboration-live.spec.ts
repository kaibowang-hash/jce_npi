import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { translate } from "../../src/i18n/runtime";
import {
  meetingCollectionFixture,
  notificationFixture,
  notificationPreferenceFixture,
} from "../support/collaboration-fixture";
import { projectCockpitFixture } from "../support/project-fixture";
import {
  globalSearchFixture,
  portfolioFixture,
  reportingProjectId as projectId,
} from "../support/reporting-fixture";
import {
  effectiveViewport,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

async function fulfillJson(
  route: Route,
  body: unknown,
  status = 200,
  replayed?: "true" | "false",
): Promise<void> {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(replayed ? { "Idempotency-Replayed": replayed } : {}),
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-p9-02-reporting-collaboration",
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
        catalog: { language: locale, messages: {}, version: "9".repeat(64) },
        csrfToken: "p9-02-browser-csrf-token-fixture-0001",
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "project.admin@example.invalid",
      });
    },
  );
  await page.route(
    /\/api\/npi\/v1\/notifications(?:[/?].*)?$/u,
    async (route) => {
      observed.push(new URL(route.request().url()).pathname);
      await fulfillJson(route, {
        schemaVersion: 1,
        items: [notificationFixture()],
        page: { limit: 25, hasMore: false, nextCursor: null },
        permissions: { serverFiltered: true },
      });
    },
  );
  await page.route(
    /\/api\/npi\/v1\/me\/preferences\/notifications(?:\?.*)?$/u,
    async (route) => {
      observed.push(new URL(route.request().url()).pathname);
      await fulfillJson(route, notificationPreferenceFixture());
    },
  );
  await page.route(
    /\/api\/npi\/v1\/portfolio\/projects(?:\?.*)?$/u,
    async (route) => {
      observed.push(new URL(route.request().url()).pathname);
      await fulfillJson(route, portfolioFixture());
    },
  );
  await page.route(/\/api\/npi\/v1\/search(?:\?.*)?$/u, async (route) => {
    observed.push(new URL(route.request().url()).pathname);
    const query =
      new URL(route.request().url()).searchParams.get("query") ?? "";
    await fulfillJson(route, globalSearchFixture(query));
  });
  await page.route(
    /\/api\/npi\/v1\/projects\/[^/?]+\/cockpit(?:\?.*)?$/u,
    async (route) => {
      const cockpit = projectCockpitFixture();
      await fulfillJson(route, {
        ...cockpit,
        permissions: { ...cockpit.permissions, canAdminister: true },
      });
    },
  );
  await page.route(
    /\/api\/npi\/v1\/projects\/[^/?]+\/meetings(?:\?.*)?$/u,
    async (route) => {
      observed.push(new URL(route.request().url()).pathname);
      if (route.request().method() === "GET") {
        await fulfillJson(route, meetingCollectionFixture());
        return;
      }
      expect(route.request().headers()["x-frappe-csrf-token"]).toBe(
        "p9-02-browser-csrf-token-fixture-0001",
      );
      expect(route.request().headers()["idempotency-key"]).toMatch(
        /^meeting-minute-/u,
      );
      const body = route.request().postDataJSON() as Record<string, unknown>;
      await fulfillJson(
        route,
        {
          schemaVersion: 1,
          globalId: "55555555-5555-4555-8555-555555555555",
          projectId,
          projectVersion: 4,
          templateRef: body.templateRef,
          title: body.title,
          occurredAt: body.occurredAt,
          attendeeUserIds: body.attendeeUserIds,
          sections: body.sections,
          linkedItems: [],
          contentHash: "a".repeat(64),
          createdBy: "project.admin@example.invalid",
          createdAt: "2026-09-01T08:00:00Z",
          version: 1,
        },
        201,
        "false",
      );
    },
  );
  return observed;
}

async function openPortfolio(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/portfolio?lang=${locale}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: translate(locale, "Project Portfolio"),
    }),
  ).toBeVisible();
  await expect(page.locator(".reporting-table tbody tr")).toHaveCount(1);
}

test.describe("P9-02 reporting and collaboration", () => {
  test("uses permission-filtered reporting, global search, and recipient notifications", async ({
    page,
  }) => {
    const observed = await installApi(page, "en");
    await openPortfolio(page, "en");
    await page.getByRole("searchbox", { name: "Global search" }).fill("SYN");
    await page.getByRole("searchbox", { name: "Global search" }).press("Enter");
    await expect(
      page
        .getByRole("dialog", { name: "Global search results" })
        .getByText("Synthetic project cockpit"),
    ).toBeVisible();
    await page.getByRole("button", { name: "Notifications" }).click();
    await expect(page.getByText("Work item due soon")).toBeVisible();
    expect(observed).toContain("/api/npi/v1/portfolio/projects");
    expect(observed).toContain("/api/npi/v1/search");
    expect(observed).toContain("/api/npi/v1/notifications");
  });

  test("creates an immutable meeting minute only through the Project command", async ({
    page,
  }) => {
    const observed = await installApi(page, "en");
    await page.goto(`/projects/${projectId}?tab=meetings&lang=en`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.locator(".route-loading")).toHaveCount(0);
    await expect(
      page.getByText("No meeting minutes have been recorded for this Project."),
    ).toBeVisible();
    await page.getByLabel("Meeting title").fill("Synthetic review");
    await page
      .getByLabel("Attendee emails")
      .fill("project.admin@example.invalid");
    await page.getByLabel("Agenda").fill("Review release readiness");
    await page.getByLabel("Discussion").fill("Evidence reviewed");
    await page.getByLabel("Decisions").fill("Proceed with controls");
    await page.getByRole("button", { name: "Review and create" }).click();
    await page.getByRole("button", { name: "Create meeting minute" }).click();
    await expect(
      page.getByText(
        "The immutable meeting minute and 0 linked work items were created.",
      ),
    ).toBeVisible();
    expect(observed.some((path) => path.endsWith("/meetings"))).toBe(true);
  });

  test("keeps the reporting workspace accessible and industrial", async ({
    page,
  }) => {
    await installApi(page, "en");
    await openPortfolio(page, "en");
    await expectNoDocumentOverflow(page);
    await expect(page.locator("html")).toHaveAttribute(
      "data-ix-theme",
      "classic",
    );
    await expect(page.locator("html")).toHaveAttribute(
      "data-ix-color-schema",
      "light",
    );
    expect(
      await page
        .locator(".page--reporting .panel")
        .first()
        .evaluate((element) => {
          const style = getComputedStyle(element);
          return { radius: style.borderRadius, shadow: style.boxShadow };
        }),
    ).toEqual({ radius: "0px", shadow: "none" });
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
    name: "p9-02-portfolio-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p9-02-portfolio-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p9-02-portfolio-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P9-02 portfolio", () => {
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
      await openPortfolio(page, visual.locale);
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
