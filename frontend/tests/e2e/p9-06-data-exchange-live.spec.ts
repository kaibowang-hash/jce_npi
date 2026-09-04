import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { translate } from "../translate";
import {
  notificationFixture,
  notificationPreferenceFixture,
} from "../support/collaboration-fixture";
import {
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u,
  );
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-p9-06-browser",
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
        csrfToken: "p9-06-browser-csrf-token-fixture-0001",
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "exchange.manager@example.invalid",
      });
    },
  );
  await page.route(
    /\/api\/npi\/v1\/notifications(?:[/?].*)?$/u,
    async (route) => {
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
      await fulfillJson(route, notificationPreferenceFixture());
    },
  );
  await page.route(
    /\/api\/npi\/v1\/administration\/data-exchange(?:\?.*)?$/u,
    async (route) => {
      await fulfillJson(route, {
        schemaVersion: "data-exchange.v1",
        mode: "closed_operation_specific",
        routesEnabled: false,
        productionContact: false,
        genericWriterAvailable: false,
        automaticDispositionAvailable: false,
        capabilities: [
          {
            id: "tooling_xlsx_import.v1",
            mode: "specialized_existing",
            exportableHere: false,
            route: "/projects/{projectId}/tooling/imports",
          },
          {
            id: "controlled_print.v1",
            mode: "specialized_existing",
            exportableHere: false,
            route: "/projects/{projectId}/documents",
          },
          {
            id: "project_portfolio.v1",
            mode: "report_export_profile",
            exportableHere: true,
            route: "/portfolio/projects",
          },
          {
            id: "kpi_trends.v1",
            mode: "report_export_profile",
            exportableHere: true,
            route: "/reports/kpis",
          },
        ],
        profiles: [],
        exports: [],
        retentionPolicies: [],
        archiveRecords: [],
      });
    },
  );
}

for (const locale of ["en", "zh", "zh-TW"] as const) {
  test(`P9-06 Data Exchange remains closed, accessible and language-pure in ${locale}`, async ({
    page,
  }) => {
    await installApi(page, locale);
    await page.goto(`/administration/data-exchange?lang=${locale}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.locator(".route-loading")).toHaveCount(0);
    await expect(page.locator("html")).toHaveAttribute("lang", locale);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: new RegExp(translate(locale, "Data Exchange"), "u"),
      }),
    ).toBeVisible();
    await expect(
      page.getByText(translate(locale, "Routes disabled")),
    ).toBeVisible();
    await expect(page.getByText("tooling_xlsx_import.v1")).toBeVisible();
    await expect(page.getByText("project_portfolio.v1")).toBeVisible();
    await expect(
      page.getByText(translate(locale, "No export profiles are published.")),
    ).toBeVisible();
    await expect(
      page.getByText(translate(locale, "No retention policies are published.")),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: translate(locale, "Create archive record"),
      }),
    ).toBeDisabled();
    await expectNoMixedLanguage(page, locale);
    await expectNoDocumentOverflow(page);
    await expect(page.locator("html")).toHaveAttribute(
      "data-ix-theme",
      "classic",
    );
    const accessibility = await new AxeBuilder({ page })
      .include("#main-content")
      .analyze();
    expect(accessibility.violations).toEqual([]);
  });
}
