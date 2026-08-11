import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { TrialReviewWorkspace } from "../../src/api/trial-data-source";
import { trialExecutionWorkspace } from "../support/trial-execution-fixture";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";
import { trialQualityWorkspace } from "../support/trial-quality-fixture";
import {
  trialConclusion,
  trialConclusionPolicy,
  trialReviewIds,
  trialReviewWorkspace,
} from "../support/trial-review-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p7-04-trial-review-browser-csrf-x";
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
  review?: TrialReviewWorkspace;
  reviewFailureOnce?: boolean;
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
      "X-Trace-ID": "trace-p7-04-trial-review-browser",
    },
    status,
  });
}

async function fulfillProblem(route: Route): Promise<void> {
  await route.fulfill({
    body: JSON.stringify({
      code: "TRIAL_REVIEW_UNAVAILABLE",
      retryable: true,
      status: 503,
      title: "The Trial review workspace is temporarily unavailable.",
      traceId: "trace-p7-04-trial-review-browser",
      type: "urn:npi:error:trial_review_unavailable",
    }),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p7-04-trial-review-browser",
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
      userId: "quality.engineer@example.invalid",
    });
  });
}

async function installTrialApi(
  page: Page,
  options: ApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  let reviewAttempts = 0;
  const review = options.review ?? trialReviewWorkspace();
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
      expect(request.headers()["idempotency-key"]).toMatch(/^trial-review-/u);
    }
    if (request.method() === "GET" && path.endsWith("/trials")) {
      await fulfillJson(route, trialPlanningWorkspace());
      return;
    }
    if (request.method() === "GET" && path.endsWith("/execution")) {
      await fulfillJson(
        route,
        trialExecutionWorkspace({ round: review.trialRound }),
      );
      return;
    }
    if (request.method() === "GET" && path.endsWith("/quality")) {
      await fulfillJson(
        route,
        trialQualityWorkspace({ trialRound: review.trialRound }),
      );
      return;
    }
    if (request.method() === "GET" && path.endsWith("/review")) {
      reviewAttempts += 1;
      if (options.reviewFailureOnce && reviewAttempts === 1) {
        await fulfillProblem(route);
        return;
      }
      await fulfillJson(route, review);
      return;
    }
    if (request.method() === "GET") {
      await fulfillJson(route, trialPlanDetail());
      return;
    }
    if (path.endsWith(":decide")) {
      await fulfillJson(route, review, 201, false);
      return;
    }
    throw new Error(
      `Unexpected P7-04 browser request: ${request.method()} ${path}`,
    );
  });
  return observed;
}

async function openReview(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${trialPlanningIds.project}/trials?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: /Trial review and conclusion|试模审查与结论|試模審查與結論/u,
    }),
  ).toBeVisible();
  await page.locator("#trial-live-review").evaluate((element) => {
    element.scrollIntoView();
  });
  await expect(
    page.getByText("material.lot_batch", { exact: true }),
  ).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include(".trial-live")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P7-04 live Trial review and conclusion workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders exact comparison, policy blockers and proposal boundary in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installTrialApi(page);
      await openReview(page, locale);

      await expect(
        page.getByText("rib.end.width", { exact: true }).first(),
      ).toBeVisible();
      await expect(
        page.getByText(trialReviewIds.referenceRevision, { exact: true }),
      ).toHaveCount(0);
      await expect(page.locator(".trial-live__summary-grid")).toBeVisible();
      await expect(
        page.locator(".trial-live__external-effects").last(),
      ).toBeVisible();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("records one independent decision against exact policy and conclusion snapshots by keyboard", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installTrialApi(page);
    const conclusion = trialConclusion();
    const policy = trialConclusionPolicy();
    await openReview(page, "en");

    const primary = page.getByRole("button", {
      name: "Record conclusion decision",
    });
    await primary.focus();
    await expect(primary).toBeFocused();
    await page.keyboard.press("Enter");
    const review = page.getByRole("dialog", {
      name: "Review immutable Trial conclusion command",
    });
    await expect(review).toBeVisible();
    await review
      .getByLabel("Reason")
      .fill("Approve the exact submitted proposal after independent review");
    await review
      .getByRole("button", { name: "Record conclusion decision" })
      .click();

    await expect(
      page.getByText("The review command appended immutable audit history."),
    ).toBeVisible();
    const command = observed.find(
      (item) => item.method === "POST" && item.path.endsWith(":decide"),
    );
    expect(command).toMatchObject({
      idempotencyKey: expect.stringMatching(
        /^trial-review-decide_conclusion-/u,
      ),
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-rounds/${trialPlanningIds.round}/conclusions/${trialReviewIds.conclusion}:decide`,
      payload: {
        decision: "approved",
        expectedConclusionRevisionGlobalId: conclusion.globalId,
        expectedConclusionRevisionSnapshotHash: conclusion.snapshotHash,
        expectedConclusionVersion: conclusion.conclusionVersion,
        expectedPolicyRevisionSnapshotHash: policy.snapshotHash,
        expectedRoundOptimisticVersion: 2,
        expectedRoundSnapshotHash: "5".repeat(64),
        policyRevisionGlobalId: policy.globalId,
        reason: "Approve the exact submitted proposal after independent review",
      },
    });
  });

  test("shows a retryable review failure while preserving quality truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installTrialApi(page, { reviewFailureOnce: true });
    await page.goto(`/projects/${trialPlanningIds.project}/trials?lang=en`, {
      waitUntil: "domcontentloaded",
    });

    await expect(
      page.getByText("The Trial review workspace is temporarily unavailable."),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Trial quality workspace" }),
    ).toBeVisible();
    await page
      .getByRole("heading", { name: "Trial review workspace unavailable" })
      .locator("../..")
      .getByRole("button", { name: "Retry" })
      .click();
    await expect(
      page.getByText("material.lot_batch", { exact: true }),
    ).toBeVisible();
  });

  test("fails closed when comparison permission has fewer than two exact Rounds", async ({
    page,
  }) => {
    const base = trialReviewWorkspace();
    await installSession(page, "en");
    await installTrialApi(page, {
      review: trialReviewWorkspace({
        comparisonSnapshots: [],
        conclusionRevisions: [],
        permissions: {
          beginAnalysis: false,
          createComparison: true,
          decideConclusion: false,
          manageReviewReferences: false,
          reopenConclusion: false,
          requiresExactPolicyRevision: true,
          submitConclusion: false,
          view: true,
        },
        reviewReferenceRevisions: [],
        trialRound: { ...base.trialRound, currentState: "analysis" },
      }),
    });
    await page.goto(`/projects/${trialPlanningIds.project}/trials?lang=en`, {
      waitUntil: "domcontentloaded",
    });

    await page.getByRole("button", { name: "Create exact comparison" }).click();
    await expect(
      page.getByText(
        "At least two exact Trial Round snapshots are required for comparison.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("keeps every review command absent for a read-only permission snapshot", async ({
    page,
  }) => {
    const review = trialReviewWorkspace();
    await installSession(page, "en");
    await installTrialApi(page, {
      review: trialReviewWorkspace({
        permissions: {
          beginAnalysis: false,
          createComparison: false,
          decideConclusion: false,
          manageReviewReferences: false,
          reopenConclusion: false,
          requiresExactPolicyRevision: true,
          submitConclusion: false,
          view: true,
        },
        trialRound: review.trialRound,
      }),
    });
    await page.goto(`/projects/${trialPlanningIds.project}/trials?lang=en`, {
      waitUntil: "domcontentloaded",
    });

    await expect(page.locator("#trial-review-primary-action")).toHaveCount(0);
    await expect(page.getByText("Conditional pass").first()).toBeVisible();
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p7-04-trial-review-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p7-04-trial-review-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p7-04-trial-review-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P7-04 Trial review evidence", () => {
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
      await openReview(page, visual.locale);
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
