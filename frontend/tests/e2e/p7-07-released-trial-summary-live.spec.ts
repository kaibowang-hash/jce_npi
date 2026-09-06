import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ReleasedTrialSummaryWorkspace } from "../../src/api/trial-data-source";
import { translate } from "../translate";
import { controlledPrintCapabilityFixture } from "../support/controlled-print-fixture";
import { trialExecutionWorkspace } from "../support/trial-execution-fixture";
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
import {
  emptyReleasedTrialSummaryWorkspace,
  releasedTrialSummaryIds,
  releasedTrialSummaryWorkspace,
  successorReleasedTrialSummaryWorkspace,
} from "../support/released-trial-summary-fixture";
import { trialReviewWorkspace } from "../support/trial-review-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p7-07-released-summary-browser-csrf-exact";
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const trialEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/(?:trials|trial-plans(?:\/.*)?|trial-rounds(?:\/.*|:[^/?]+))$/u;
const formalQualityEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/(?:formal-quality-links|erp-projections)(?:\?.*)?$/u;
const controlledPrintEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/controlled-print\/capability(?:\?.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

type ProblemStatus = 409 | 422 | 503;

interface ObservedRequest {
  csrfToken: string | undefined;
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
}

interface ApiOptions {
  afterCommand?: ReleasedTrialSummaryWorkspace;
  commandDelayMs?: number;
  commandProblem?: ProblemStatus;
  refreshProblemOnce?: boolean;
  replayed?: boolean;
  workspace?: ReleasedTrialSummaryWorkspace;
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
      "X-Trace-ID": "trace-p7-07-released-summary-browser",
    },
    status,
  });
}

function problemFor(status: ProblemStatus): {
  code: string;
  retryable: boolean;
  title: string;
} {
  if (status === 409) {
    return {
      code: "RELEASED_TRIAL_SUMMARY_CONFLICT",
      retryable: false,
      title: "The current Released Summary source changed.",
    };
  }
  if (status === 422) {
    return {
      code: "RELEASED_TRIAL_SUMMARY_OVERFLOW",
      retryable: false,
      title: "The complete Released Summary source graph is too large.",
    };
  }
  return {
    code: "RELEASED_TRIAL_SUMMARY_UNAVAILABLE",
    retryable: true,
    title: "The Released Trial Summary workspace is temporarily unavailable.",
  };
}

async function fulfillProblem(
  route: Route,
  status: ProblemStatus,
): Promise<void> {
  const problem = problemFor(status);
  await route.fulfill({
    body: JSON.stringify({
      code: problem.code,
      retryable: problem.retryable,
      status,
      title: problem.title,
      traceId: "trace-p7-07-released-summary-browser",
      type: `urn:npi:problem:${problem.code.toLowerCase()}`,
    }),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p7-07-released-summary-browser",
    },
    status,
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

async function installControlledPrintUnavailable(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await page.route(controlledPrintEndpoint, async (route) => {
    const url = new URL(route.request().url());
    expect(route.request().method()).toBe("GET");
    expect(url.searchParams.get("sourceKind")).toBe("released_trial_summary");
    const sourceGlobalId = url.searchParams.get("sourceGlobalId") ?? "";
    const sourceVersion = Number(url.searchParams.get("sourceVersion"));
    await fulfillJson(route, {
      ...controlledPrintCapabilityFixture(false),
      language: locale,
      sourceGlobalId,
      sourceKind: "released_trial_summary",
      sourceVersion,
    });
  });
}

async function installTrialApi(
  page: Page,
  options: ApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const workspace = options.workspace ?? releasedTrialSummaryWorkspace();
  const afterCommand = options.afterCommand ?? releasedTrialSummaryWorkspace();
  let commandAccepted = false;
  let refreshProblemPending = options.refreshProblemOnce ?? false;

  await page.route(formalQualityEndpoint, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    expect(request.method()).toBe("GET");
    expect([...url.searchParams.entries()]).toEqual(
      url.pathname.endsWith("/erp-projections")
        ? [["kind", "formal_quality_status"]]
        : [],
    );
    await fulfillJson(
      route,
      url.pathname.endsWith("/erp-projections")
        ? trialFormalQualityProjection()
        : trialFormalQualityLinks(),
    );
  });
  await page.route(trialEndpoint, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const payload: unknown = request.postData()
      ? (request.postDataJSON() as unknown)
      : null;
    observed.push({
      csrfToken: request.headers()["x-frappe-csrf-token"],
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path,
      payload,
    });
    expect(request.headers().accept).toBe(
      "application/json, application/problem+json",
    );

    const isSummaryCollection = path.endsWith("/released-trial-summaries");
    const isSummaryRevision = path.endsWith(":revise");
    if (
      request.method() === "GET" &&
      (isSummaryCollection || isSummaryRevision)
    ) {
      if (commandAccepted && refreshProblemPending) {
        refreshProblemPending = false;
        await fulfillProblem(route, 503);
        return;
      }
      await fulfillJson(route, commandAccepted ? afterCommand : workspace);
      return;
    }
    if (
      request.method() === "POST" &&
      (isSummaryCollection || isSummaryRevision)
    ) {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(
        /^released-summary-(?:retain|revise)-/u,
      );
      if (options.commandDelayMs) {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, options.commandDelayMs);
        });
      }
      if (options.commandProblem) {
        await fulfillProblem(route, options.commandProblem);
        return;
      }
      commandAccepted = true;
      await fulfillJson(route, afterCommand, 201, options.replayed ?? false);
      return;
    }
    if (request.method() === "GET" && path.endsWith("/trials")) {
      await fulfillJson(route, trialPlanningWorkspace());
      return;
    }
    if (request.method() === "GET" && path.endsWith("/execution")) {
      await fulfillJson(
        route,
        trialExecutionWorkspace({ round: workspace.trialRound }),
      );
      return;
    }
    if (request.method() === "GET" && path.endsWith("/quality")) {
      await fulfillJson(
        route,
        trialQualityWorkspace({ trialRound: workspace.trialRound }),
      );
      return;
    }
    if (request.method() === "GET" && path.endsWith("/review")) {
      await fulfillJson(
        route,
        trialReviewWorkspace({ trialRound: workspace.trialRound }),
      );
      return;
    }
    if (request.method() === "GET") {
      await fulfillJson(route, trialPlanDetail());
      return;
    }
    throw new Error(
      `Unexpected P7-07 browser request: ${request.method()} ${path}`,
    );
  });
  return observed;
}

async function openSummary(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${trialPlanningIds.project}/trials?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  const workspace = page.getByRole("region", {
    name: translate(locale, "Released Trial Summary"),
  });
  await expect(workspace).toBeVisible();
  await expect(page.getByTestId("formal-quality-link-state")).toBeVisible();
  await workspace.evaluate((element) => {
    element.scrollIntoView();
  });
  await expect(workspace).toBeInViewport();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include(".released-summary-workspace")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function submitRetain(page: Page, reason: string): Promise<void> {
  const primary = page.getByRole("button", {
    name: "Retain technical summary",
  });
  await primary.focus();
  await expect(primary).toBeFocused();
  await page.keyboard.press("Enter");
  const review = page.getByRole("dialog", {
    name: "Review immutable technical summary command",
  });
  await expect(review).toBeVisible();
  await review.getByLabel("Reason").fill(reason);
  await review
    .getByRole("button", { name: "Retain technical summary" })
    .click();
}

test.describe("P7-07 live Released Trial Summary workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders exact safe history, source and redaction truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installControlledPrintUnavailable(page, locale);
      await installTrialApi(page, {
        workspace: successorReleasedTrialSummaryWorkspace(),
      });
      await openSummary(page, locale);

      const workspace = page.getByRole("region", {
        name: translate(locale, "Released Trial Summary"),
      });
      await expect(
        workspace.getByText("material.lot_batch", { exact: true }),
      ).toBeVisible();
      await expect(
        workspace.getByText(translate(locale, "Controlled output mapping"), {
          exact: true,
        }),
      ).toBeVisible();
      await expect(
        workspace.getByText(
          translate(
            locale,
            "Structural redaction excludes private locators, file content, credentials, provider payloads and unapproved external projection.",
          ),
        ),
      ).toBeVisible();
      await workspace
        .getByRole("button", {
          name: translate(locale, "Check controlled print availability"),
        })
        .click();
      await expect(
        workspace.getByText(
          translate(locale, "Controlled print is unavailable"),
        ),
      ).toBeVisible();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("inspects an immutable predecessor without replacing the current tip", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installControlledPrintUnavailable(page, "en");
    await installTrialApi(page, {
      workspace: successorReleasedTrialSummaryWorkspace(),
    });
    await openSummary(page, "en");

    const workspace = page.getByRole("region", {
      name: "Released Trial Summary",
    });
    const content = workspace.locator(".released-summary-workspace__content");
    await content.evaluate((element) => {
      element.scrollIntoView();
    });
    await expect(
      content.getByText(releasedTrialSummaryIds.successorRevision, {
        exact: true,
      }),
    ).toBeVisible();
    await workspace
      .locator(".released-summary-workspace__history-select")
      .filter({ hasText: "Version 1" })
      .click();
    await expect(
      content.getByText(releasedTrialSummaryIds.revision, { exact: true }),
    ).toBeVisible();
    await expect(
      workspace
        .locator(".released-summary-workspace__history-select")
        .filter({ hasText: "Version 1" }),
    ).toHaveAttribute("aria-current", "page");
  });

  test("retains one exact decided conclusion by keyboard and exposes processing honestly", async ({
    page,
  }) => {
    const empty = emptyReleasedTrialSummaryWorkspace();
    const retained = releasedTrialSummaryWorkspace();
    await installSession(page, "en");
    await installControlledPrintUnavailable(page, "en");
    const observed = await installTrialApi(page, {
      afterCommand: retained,
      commandDelayMs: 350,
      workspace: empty,
    });
    await openSummary(page, "en");
    await expect(
      page.getByText("No technical summary has been retained."),
    ).toBeVisible();

    const reason =
      "Retain the exact decided conclusion and complete source graph";
    await submitRetain(page, reason);
    await expect(
      page.getByText(
        "The exact Round, decided conclusion, predecessor and source graph are being verified atomically.",
      ),
    ).toBeVisible();
    await expect(
      page.getByText(
        "The technical summary and audit history were retained immutably.",
      ),
    ).toBeVisible();

    const command = observed.find(
      (item) =>
        item.method === "POST" &&
        item.path.endsWith("/released-trial-summaries"),
    );
    expect(command).toMatchObject({
      csrfToken,
      idempotencyKey: expect.stringMatching(/^released-summary-retain-/u),
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-rounds/${trialPlanningIds.round}/released-trial-summaries`,
      payload: {
        conclusionRevisionGlobalId: empty.currentDecidedConclusion?.globalId,
        expectedConclusionSnapshotHash:
          empty.currentDecidedConclusion?.snapshotHash,
        expectedConclusionVersion:
          empty.currentDecidedConclusion?.conclusionVersion,
        expectedRoundOptimisticVersion: empty.trialRound.optimisticVersion,
        expectedRoundSnapshotHash: empty.trialRound.snapshotHash,
        reason,
      },
    });
    expect(command?.payload).not.toHaveProperty("actorUserId");
    expect(observed.filter((item) => item.method === "POST")).toHaveLength(1);
  });

  test("preserves an accepted command when the mandatory history refresh fails", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installControlledPrintUnavailable(page, "en");
    const observed = await installTrialApi(page, {
      afterCommand: releasedTrialSummaryWorkspace(),
      refreshProblemOnce: true,
      workspace: emptyReleasedTrialSummaryWorkspace(),
    });
    await openSummary(page, "en");
    await submitRetain(page, "Retain once and refresh from server truth");

    await expect(
      page.getByRole("heading", {
        name: "Summary retained; current history could not be refreshed",
      }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "The server accepted the command. Do not submit it again.",
      ),
    ).toBeVisible();
    await page.getByRole("button", { name: "Reload summary history" }).click();
    await expect(
      page
        .getByRole("region", { name: "Released Trial Summary" })
        .locator(".released-summary-workspace__history-select")
        .filter({ hasText: "Version 1" }),
    ).toBeVisible();
    expect(observed.filter((item) => item.method === "POST")).toHaveLength(1);
  });

  test("shows sealed replay truth without a second retain", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installControlledPrintUnavailable(page, "en");
    const observed = await installTrialApi(page, {
      afterCommand: releasedTrialSummaryWorkspace(),
      replayed: true,
      workspace: emptyReleasedTrialSummaryWorkspace(),
    });
    await openSummary(page, "en");
    await submitRetain(page, "Replay the exact sealed response safely");

    await expect(
      page.getByText(
        "The exact prior summary command response was replayed safely.",
      ),
    ).toBeVisible();
    expect(observed.filter((item) => item.method === "POST")).toHaveLength(1);
  });

  for (const scenario of [
    {
      expectedHeading: "Reload current summary",
      status: 409 as const,
    },
    {
      expectedHeading:
        "Summary source graph exceeds the safe retention boundary",
      status: 422 as const,
    },
  ]) {
    test(`fails closed for summary command status ${String(scenario.status)}`, async ({
      page,
    }) => {
      await installSession(page, "en");
      await installControlledPrintUnavailable(page, "en");
      const observed = await installTrialApi(page, {
        commandProblem: scenario.status,
        workspace: emptyReleasedTrialSummaryWorkspace(),
      });
      await openSummary(page, "en");
      await submitRetain(page, "Exercise an exact closed failure boundary");

      if (scenario.status === 409) {
        await expect(
          page.getByRole("button", { name: scenario.expectedHeading }),
        ).toBeVisible();
      } else {
        await expect(
          page.getByRole("heading", { name: scenario.expectedHeading }),
        ).toBeVisible();
      }
      expect(observed.filter((item) => item.method === "POST")).toHaveLength(1);
    });
  }
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p7-07-released-trial-summary-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p7-07-released-trial-summary-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p7-07-released-trial-summary-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P7-07 Released Trial Summary evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installControlledPrintUnavailable(page, visual.locale);
      await installTrialApi(page, {
        workspace: successorReleasedTrialSummaryWorkspace(),
      });
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
      await openSummary(page, visual.locale);
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
