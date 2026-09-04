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

const previewId = "11111111-1111-4111-8111-111111111111";

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
      "X-Trace-ID": "trace-p9-05-browser-rehearsal",
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
        catalog: { language: locale, messages: {}, version: "9".repeat(64) },
        csrfToken: "p9-05-browser-csrf-token-fixture-0001",
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "migration.manager@example.invalid",
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
    /\/api\/npi\/v1\/administration\/historical-migration-rehearsals(?:\?.*)?$/u,
    async (route) => {
      await fulfillJson(route, {
        schemaVersion: "historical-migration-rehearsal.v1",
        mode: "non_production_rehearsal",
        executionEnabled: false,
        productionContact: false,
        previews: [
          {
            schemaVersion: "historical-migration-preview.v1",
            globalId: previewId,
            bundleId: "22222222-2222-4222-8222-222222222222",
            manifestHash: "a".repeat(64),
            sourceSha256: "b".repeat(64),
            sourceFileRevisionGlobalId: "33333333-3333-4333-8333-333333333333",
            sourceFileOptimisticVersion: 2,
            tenantId: "runtime-tenant",
            version: 1,
            summary: { create: 0, link: 0, skip: 0, blocked: 1 },
            rows: [
              {
                family: "project",
                ordinal: 2,
                sourceKey: "synthetic-project",
                sourceHash: "c".repeat(64),
                action: "blocked",
                targetGlobalId: null,
                targetVersion: null,
                targetSnapshotHash: null,
                differences: [
                  {
                    field: "title",
                    sourceValue: "hidden-source-value",
                    targetValue: "hidden-target-value",
                  },
                ],
                findings: [
                  {
                    code: "target_difference",
                    field: "project",
                    message: translate(
                      locale,
                      "The existing Project differs from the historical source.",
                    ),
                  },
                ],
              },
            ],
            createdByUserId: "migration.manager@example.invalid",
            createdAt: "2026-09-03T08:00:00Z",
            requestId: "44444444-4444-4444-8444-444444444444",
            traceId: "trace-p9-05-preview",
            snapshotHash: "d".repeat(64),
          },
        ],
        jobs: [],
      });
    },
  );
}

for (const locale of ["en", "zh", "zh-TW"] as const) {
  test(`P9-05 historical migration stays non-production, accessible, and language-pure in ${locale}`, async ({
    page,
  }) => {
    await installApi(page, locale);
    await page.goto(`/administration/migration-rehearsal?lang=${locale}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.locator(".route-loading")).toHaveCount(0);
    await expect(page.locator("html")).toHaveAttribute("lang", locale);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: new RegExp(
          translate(locale, "Historical migration rehearsal"),
          "u",
        ),
      }),
    ).toBeVisible();
    await expect(
      page.getByText(translate(locale, "Non-production rehearsal")),
    ).toBeVisible();
    await expect(
      page.getByText(
        translate(
          locale,
          "The existing Project differs from the historical source.",
        ),
      ),
    ).toBeVisible();
    await expect(page.getByText("hidden-source-value")).toHaveCount(0);
    await expect(page.getByText("hidden-target-value")).toHaveCount(0);
    await expect(
      page.getByRole("button", {
        name: translate(locale, "Execute rehearsal"),
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
