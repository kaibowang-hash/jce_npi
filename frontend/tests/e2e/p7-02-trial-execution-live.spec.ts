import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  TrialExecutionWorkspace,
  TrialPermissions,
} from "../../src/api/trial-data-source";
import {
  trialExecutionIds,
  trialExecutionWorkspace,
} from "../support/trial-execution-fixture";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";
import { trialQualityWorkspace } from "../support/trial-quality-fixture";
import { emptyTrialReviewWorkspace } from "../support/trial-review-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p7-02-trial-execution-browser-csrf";
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
  execution?: TrialExecutionWorkspace;
  executionFailureOnce?: boolean;
  planningPermissions?: TrialPermissions;
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
      "X-Trace-ID": "trace-p7-02-trial-execution-browser",
    },
    status,
  });
}

async function fulfillProblem(
  route: Route,
  code: string,
  status: number,
  retryable: boolean,
  title: string,
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify({
      code,
      retryable,
      status,
      title,
      traceId: "trace-p7-02-trial-execution-browser",
      type: `urn:npi:error:${code.toLowerCase()}`,
    }),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p7-02-trial-execution-browser",
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
      userId: "trial.engineer@example.invalid",
    });
  });
}

async function installTrialApi(
  page: Page,
  options: ApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  let executionAttempts = 0;
  const execution = options.execution ?? trialExecutionWorkspace();
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
      expect(request.headers()["idempotency-key"]).toMatch(
        /^trial-(?:round-start|evidence-bind)-/u,
      );
    }
    if (request.method() === "GET" && path.endsWith("/trials")) {
      await fulfillJson(
        route,
        trialPlanningWorkspace({
          ...(options.planningPermissions
            ? { permissions: options.planningPermissions }
            : {}),
        }),
      );
      return;
    }
    if (request.method() === "GET" && path.endsWith("/execution")) {
      executionAttempts += 1;
      if (options.executionFailureOnce && executionAttempts === 1) {
        await fulfillProblem(
          route,
          "TRIAL_EXECUTION_UNAVAILABLE",
          503,
          true,
          "The Trial execution workspace is temporarily unavailable.",
        );
        return;
      }
      await fulfillJson(route, execution);
      return;
    }
    if (request.method() === "GET" && path.endsWith("/quality")) {
      await fulfillJson(route, trialQualityWorkspace());
      return;
    }
    if (request.method() === "GET" && path.endsWith("/review")) {
      await fulfillJson(route, emptyTrialReviewWorkspace(execution.round));
      return;
    }
    if (request.method() === "GET") {
      await fulfillJson(route, trialPlanDetail());
      return;
    }
    if (path.endsWith(":start")) {
      await fulfillJson(route, trialExecutionWorkspace(), 200, false);
      return;
    }
    if (path.endsWith("/evidence")) {
      await fulfillJson(
        route,
        trialExecutionWorkspace({ pendingFiles: [] }),
        201,
        false,
      );
      return;
    }
    throw new Error(
      `Unexpected P7-02 browser request: ${request.method()} ${path}`,
    );
  });
  return observed;
}

async function openExecution(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${trialPlanningIds.project}/trials?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator("#trial-execution-primary-action")).toBeVisible();
  await expect(page.getByText("Injection machine 550T")).toBeVisible();
  await page.locator("#trial-live-execution").evaluate((element) => {
    element.scrollIntoView();
  });
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include(".trial-live")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function reviewAndConfirm(
  page: Page,
  commandName: string,
  reason: string,
): Promise<void> {
  await page.getByRole("button", { name: "Review command" }).click();
  const review = page.getByRole("dialog", {
    name: "Review immutable Trial execution command",
  });
  await expect(review).toContainText("Irreversible effect");
  await review.getByLabel("Reason").fill(reason);
  await review.getByRole("button", { name: commandName }).click();
}

function preparedExecution(): TrialExecutionWorkspace {
  const plannedRound = trialPlanDetail().rounds[0];
  if (!plannedRound) throw new Error("Prepared execution requires one Round.");
  return trialExecutionWorkspace({
    actualRevisions: [],
    evidence: [],
    missingFacts: ["actual_context", "sample_batch", "evidence"],
    pendingFiles: [],
    permissions: {
      canManageEvidence: false,
      canManageSamples: false,
      canPrepare: false,
      canRecordActual: false,
      canStart: true,
    },
    round: { ...plannedRound, currentState: "prepared", optimisticVersion: 2 },
    sampleBatchRevisions: [],
  });
}

function cleanAndPendingExecution(): TrialExecutionWorkspace {
  const workspace = trialExecutionWorkspace();
  return {
    ...workspace,
    pendingFiles: [
      workspace.pendingFiles[0] ?? {
        fileName: "parameter-curve.csv",
        globalId: trialExecutionIds.pendingFile,
        mimeType: "text/csv",
        optimisticVersion: 1,
        privacy: "private",
        scanState: "pending",
        sha256: "9".repeat(64),
        sizeBytes: 1024,
      },
      {
        fileName: "t0-photo.png",
        globalId: trialExecutionIds.fileRevision,
        mimeType: "image/png",
        optimisticVersion: 3,
        privacy: "private",
        scanState: "clean",
        sha256: "8".repeat(64),
        sizeBytes: 2048,
      },
    ],
  };
}

test.describe("P7-02 live Trial execution workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders exact locked, actual, sample and evidence truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installTrialApi(page);
      await openExecution(page, locale);

      await expect(
        page.getByText("injection.pressure", { exact: true }),
      ).toBeVisible();
      await expect(page.getByText("T0-SAMPLE-01")).toBeVisible();
      await expect(page.getByText("Machine import unavailable")).toHaveCount(
        locale === "en" ? 1 : 0,
      );
      await expect(page.locator("#trial-execution-primary-action")).toHaveCount(
        1,
      );
      const pendingRow = page.getByRole("row", {
        name: /parameter-curve\.csv/u,
      });
      await expect(pendingRow.getByRole("button")).toBeDisabled();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("starts one prepared Round with exact manual observations and locked material", async ({
    page,
  }) => {
    await installSession(page, "en");
    const execution = preparedExecution();
    const observed = await installTrialApi(page, { execution });
    await openExecution(page, "en");

    await page.getByRole("button", { name: "Start Trial Round" }).click();
    await page.getByLabel("Machine source system").selectOption("ERPNEXT");
    await page.getByLabel("Actual machine source object ID").fill("IM-550-02");
    await page
      .getByLabel("Actual machine label")
      .fill("Injection machine 550T");
    await page
      .getByLabel("Execution started at (UTC)")
      .fill("2026-08-10T08:35");
    await page.getByLabel("Environment key").fill("ambient.temperature");
    await page.getByLabel("Environment value").fill("24");
    await page.getByLabel("Environment unit").fill("°C");
    await page
      .getByLabel("injection.pressure measurement state")
      .selectOption("measured");
    await page.getByLabel("injection.pressure observed value").fill("91");
    await page
      .getByLabel("cooling.time measurement state")
      .selectOption("measured");
    await page.getByLabel("cooling.time observed value").fill("20");
    await reviewAndConfirm(
      page,
      "Start Trial Round",
      "Start exact manually observed T0 execution",
    );

    await expect(
      page.getByText(
        "The execution command completed with immutable audit truth.",
      ),
    ).toBeVisible();
    const command = observed.find(
      (item) => item.method === "POST" && item.path.endsWith(":start"),
    );
    expect(command).toMatchObject({
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-rounds/${trialPlanningIds.round}:start`,
      payload: {
        environment: [
          {
            key: "ambient.temperature",
            observedAt: "2026-08-10T08:35:00.000Z",
            unit: "°C",
            value: "24",
          },
        ],
        executionStartedAt: "2026-08-10T08:35:00.000Z",
        expectedInputLockRevisionGlobalId: trialExecutionIds.inputLockRevision,
        expectedInputLockVersion: 1,
        expectedRoundOptimisticVersion: 2,
        material: {
          additive: "GF30",
          color: "Natural",
          label: "PA66-GF30 natural",
          lotBatchCode: "LOT-2026-0810",
          observedAt: "2026-08-10T08:25:00Z",
          sourceObjectId: "MAT-PA66-GF30",
          sourceSystem: "ERPNEXT",
        },
        operatorUserId: "trial.engineer@example.invalid",
        parameters: [
          expect.objectContaining({
            definitionKey: "injection.pressure",
            source: "manual",
            state: "measured",
            value: "91",
          }),
          expect.objectContaining({
            definitionKey: "cooling.time",
            source: "manual",
            state: "measured",
            value: "20",
          }),
        ],
        reason: "Start exact manually observed T0 execution",
        resources: [
          {
            kind: "machine",
            label: "Injection machine 550T",
            sourceObjectId: "IM-550-02",
            sourceSystem: "ERPNEXT",
          },
        ],
      },
    });
  });

  test("keeps pending files unbindable and binds only the exact clean File Revision", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installTrialApi(page, {
      execution: cleanAndPendingExecution(),
    });
    await openExecution(page, "en");

    const pendingRow = page.getByRole("row", { name: /parameter-curve\.csv/u });
    await expect(
      pendingRow.getByRole("button", { name: "Bind as evidence" }),
    ).toBeDisabled();
    const cleanRow = page.getByRole("row", { name: /t0-photo\.png/u });
    await cleanRow.getByRole("button", { name: "Bind as evidence" }).click();
    await page.getByLabel("Evidence role").selectOption("photo");
    await page
      .getByLabel("Related Sample Batch revision")
      .selectOption(trialExecutionIds.sampleRevision);
    await page.getByRole("button", { name: "Bind clean evidence" }).click();

    await expect(
      page.getByText(
        "The execution command completed with immutable audit truth.",
      ),
    ).toBeVisible();
    const command = observed.find(
      (item) => item.method === "POST" && item.path.endsWith("/evidence"),
    );
    expect(command).toMatchObject({
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-rounds/${trialPlanningIds.round}/evidence`,
      payload: {
        expectedFileOptimisticVersion: 3,
        expectedRoundOptimisticVersion: 1,
        expectedSampleVersion: 1,
        fileRevisionGlobalId: trialExecutionIds.fileRevision,
        role: "photo",
        sampleBatchRevisionGlobalId: trialExecutionIds.sampleRevision,
      },
    });
  });

  test("shows a retryable execution failure without replacing planning truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installTrialApi(page, { executionFailureOnce: true });
    await page.goto(`/projects/${trialPlanningIds.project}/trials?lang=en`, {
      waitUntil: "domcontentloaded",
    });

    await expect(
      page.getByText(
        "The Trial execution workspace is temporarily unavailable.",
      ),
    ).toBeVisible();
    await expect(page.getByText("Injection machine 550T")).toBeVisible();
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await expect(
      page.getByRole("table", { name: "Actual process parameters" }),
    ).toBeVisible();
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p7-02-trial-execution-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p7-02-trial-execution-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p7-02-trial-execution-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P7-02 Trial execution evidence", () => {
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
      await openExecution(page, visual.locale);
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
