import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { TrialQualityWorkspace } from "../../src/api/trial-data-source";
import { translate } from "../../src/i18n/runtime";
import {
  trialExecutionIds,
  trialExecutionWorkspace,
} from "../support/trial-execution-fixture";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";
import {
  trialFormalQualityLinks,
  trialFormalQualityProjection,
  trialQualityWorkspace,
} from "../support/trial-quality-fixture";
import { emptyTrialReviewWorkspace } from "../support/trial-review-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p7-03-trial-quality-browser-csrf";
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const trialEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/(?:trials|trial-plans(?:\/.*)?|trial-rounds(?:\/.*|:[^/?]+))$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

interface ObservedRequest {
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
}

interface ApiOptions {
  quality?: TrialQualityWorkspace;
  qualityFailureOnce?: boolean;
}

function requestIdentity(route: Route): string {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  return requestId;
}

async function fulfillJson(
  route: Route,
  body: unknown,
  status = 200,
  replayed?: boolean,
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(replayed === undefined
        ? {}
        : { "Idempotency-Replayed": String(replayed) }),
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p7-03-trial-quality-browser",
    },
    status,
  });
}

async function fulfillProblem(route: Route): Promise<void> {
  await route.fulfill({
    body: JSON.stringify({
      code: "TRIAL_QUALITY_UNAVAILABLE",
      retryable: true,
      status: 503,
      title: "The Trial quality workspace is temporarily unavailable.",
      traceId: "trace-p7-03-trial-quality-browser",
      type: "urn:npi:error:trial_quality_unavailable",
    }),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p7-03-trial-quality-browser",
    },
    status: 503,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "7".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "trial.engineer@example.invalid",
    });
  });
}

async function installTrialApi(
  page: Page,
  options: ApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  let qualityAttempts = 0;
  const quality = options.quality ?? trialQualityWorkspace();
  await page.route(
    /\/api\/npi\/v1\/projects\/[^/?]+\/(?:formal-quality-links|erp-projections)(?:\?.*)?$/u,
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      expect(route.request().method()).toBe("GET");
      await fulfillJson(
        route,
        path.endsWith("/erp-projections")
          ? trialFormalQualityProjection()
          : trialFormalQualityLinks(),
      );
    },
  );
  await page.route(trialEndpoint, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const payload: unknown =
      request.method() === "POST" ? request.postDataJSON() : null;
    observed.push({
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path,
      payload,
    });
    if (request.method() === "POST") {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(/^trial-quality-/u);
    }
    if (request.method() === "GET" && path.endsWith("/trials")) {
      await fulfillJson(route, trialPlanningWorkspace());
      return;
    }
    if (request.method() === "GET" && path.endsWith("/execution")) {
      await fulfillJson(route, trialExecutionWorkspace());
      return;
    }
    if (request.method() === "GET" && path.endsWith("/quality")) {
      qualityAttempts += 1;
      if (options.qualityFailureOnce && qualityAttempts === 1) {
        await fulfillProblem(route);
        return;
      }
      await fulfillJson(route, quality);
      return;
    }
    if (request.method() === "GET" && path.endsWith("/review")) {
      await fulfillJson(route, emptyTrialReviewWorkspace(quality.trialRound));
      return;
    }
    if (request.method() === "GET") {
      await fulfillJson(route, trialPlanDetail());
      return;
    }
    if (path.endsWith("/cavity-results")) {
      await fulfillJson(route, quality, 201, false);
      return;
    }
    if (path.includes("/defects")) {
      await fulfillJson(route, quality, 201, false);
      return;
    }
    throw new Error(
      `Unexpected P7-03 browser request: ${request.method()} ${path}`,
    );
  });
  return observed;
}

async function openQuality(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${trialPlanningIds.project}/trials?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator("#trial-quality-primary-action")).toBeVisible();
  await page.locator("#trial-live-quality").evaluate((element) => {
    element.scrollIntoView();
  });
  await expect(page.getByText("Rib end width", { exact: true })).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include(".trial-live")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P7-03 live Trial quality workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders exact cavity, defect, action and verification truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installTrialApi(page);
      await openQuality(page, locale);

      await expect(page.getByText("DEF-T0-001").first()).toBeVisible();
      await expect(
        page.getByRole("heading", {
          name: translate(locale, "Formal quality reference"),
        }),
      ).toBeVisible();
      await expect(
        page.getByText(trialExecutionIds.cavity).first(),
      ).toBeVisible();
      await expect(
        page.locator(".trial-live__external-effects").first(),
      ).toBeVisible();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("records one exact cavity result with evidence and immutable command context", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installTrialApi(page);
    await openQuality(page, "en");

    await page.getByRole("button", { name: "Record cavity result" }).click();
    await page.getByLabel("Characteristic key").fill("rib.width");
    await page.getByLabel("Characteristic label").fill("Rib width");
    await page.getByLabel("Lower limit").fill("2.40");
    await page.getByLabel("Nominal value").fill("2.50");
    await page.getByLabel("Upper limit").fill("2.60");
    await page.getByLabel("Measured value").fill("2.51");
    await page.getByLabel("Observed at").fill("2026-08-10T10:05");
    await page.getByRole("button", { name: "Review command" }).click();
    const review = page.getByRole("dialog", {
      name: "Review immutable Trial quality command",
    });
    await review.getByLabel("Reason").fill("Record exact T0 cavity evidence");
    await review.getByRole("button", { name: "Record cavity result" }).click();

    await expect(
      page.getByText(
        "The quality command completed with immutable audit truth.",
      ),
    ).toBeVisible();
    const command = observed.find(
      (item) => item.method === "POST" && item.path.endsWith("/cavity-results"),
    );
    expect(command).toMatchObject({
      idempotencyKey: expect.stringMatching(/^trial-quality-/u),
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-rounds/${trialPlanningIds.round}/cavity-results`,
      payload: {
        cavityGlobalId: trialExecutionIds.cavity,
        evidence: [
          {
            globalId: trialExecutionIds.evidence,
            snapshotHash: "f".repeat(64),
          },
        ],
        measurements: [
          expect.objectContaining({
            characteristicKey: "rib.width",
            lowerLimit: "2.40",
            nominalValue: "2.50",
            observedAt: "2026-08-10T10:05:00.000Z",
            state: "measured",
            upperLimit: "2.60",
            value: "2.51",
          }),
        ],
        reason: "Record exact T0 cavity evidence",
      },
    });
  });

  test("shows an explicit retryable quality failure without hiding execution truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installTrialApi(page, { qualityFailureOnce: true });
    await page.goto(`/projects/${trialPlanningIds.project}/trials?lang=en`, {
      waitUntil: "domcontentloaded",
    });

    await expect(
      page.getByText("The Trial quality workspace is temporarily unavailable."),
    ).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Actual process parameters" }),
    ).toBeVisible();
    await page
      .getByRole("heading", { name: "Trial quality workspace unavailable" })
      .locator("../..")
      .getByRole("button", { name: "Retry" })
      .click();
    await expect(
      page.getByText("Rib end width", { exact: true }),
    ).toBeVisible();
  });

  test("keeps all quality commands absent for a read-only permission snapshot", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installTrialApi(page, {
      quality: trialQualityWorkspace({
        permissions: {
          manageDefects: false,
          recordCavityResult: false,
          verifyDefects: false,
          view: true,
        },
      }),
    });
    await page.goto(`/projects/${trialPlanningIds.project}/trials?lang=en`, {
      waitUntil: "domcontentloaded",
    });

    await expect(
      page.getByText("Trial quality is read only in this session."),
    ).toBeVisible();
    await expect(page.locator("#trial-quality-primary-action")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Continue in Trial" }),
    ).toHaveCount(0);
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p7-03-trial-quality-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p7-03-trial-quality-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p7-03-trial-quality-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P7-03 Trial quality evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installTrialApi(page);
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
      await openQuality(page, visual.locale);
      const inspector = page.getByTestId("formal-quality-link-state");
      await expect(inspector).toBeVisible();
      await inspector.evaluate((element) => {
        element.scrollIntoView();
      });
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await expect(page).toHaveScreenshot(`${visual.name}.png`);
    });
  }
});
