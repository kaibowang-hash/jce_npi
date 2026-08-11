import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { TrialPermissions } from "../../src/api/trial-data-source";
import { trialExecutionWorkspace } from "../support/trial-execution-fixture";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";
import { trialQualityWorkspace } from "../support/trial-quality-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p7-01-trial-planning-browser-csrf";
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
  delayWorkspace?: boolean;
  empty?: boolean;
  permissions?: TrialPermissions;
  roundConflictOnce?: boolean;
  roundReplayed?: boolean;
  workspaceFailure?: boolean;
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
      "X-Trace-ID": "trace-p7-01-trial-planning-browser",
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
      traceId: "trace-p7-01-trial-planning-browser",
      type: `urn:npi:error:${code.toLowerCase()}`,
    }),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p7-01-trial-planning-browser",
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
  let roundAttempts = 0;
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
        /^trial-(?:plan-create|plan-revise|round-create|actions-generate)-/u,
      );
    }
    if (request.method() === "GET" && path.endsWith("/trials")) {
      if (options.delayWorkspace) {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 350);
        });
      }
      if (options.workspaceFailure) {
        await fulfillProblem(
          route,
          "TRIAL_PLANNING_UNAVAILABLE",
          503,
          true,
          "The Trial planning workspace is temporarily unavailable.",
        );
        return;
      }
      const workspace = trialPlanningWorkspace({
        ...(options.empty ? { plans: [] } : {}),
        ...(options.permissions ? { permissions: options.permissions } : {}),
      });
      await fulfillJson(route, workspace);
      return;
    }
    if (request.method() === "GET" && path.endsWith("/execution")) {
      const planned = trialPlanDetail().rounds[0];
      if (!planned)
        throw new Error("P7-01 browser fixture requires one Round.");
      await fulfillJson(
        route,
        trialExecutionWorkspace({
          actualRevisions: [],
          evidence: [],
          inputLocks: [],
          missingFacts: [
            "input_lock",
            "actual_context",
            "sample_batch",
            "evidence",
          ],
          pendingFiles: [],
          permissions: {
            canManageEvidence: false,
            canManageSamples: false,
            canPrepare: true,
            canRecordActual: false,
            canStart: false,
          },
          round: planned,
          sampleBatchRevisions: [],
        }),
      );
      return;
    }
    if (request.method() === "GET" && path.endsWith("/quality")) {
      await fulfillJson(route, trialQualityWorkspace());
      return;
    }
    if (request.method() === "GET") {
      await fulfillJson(
        route,
        trialPlanDetail({
          ...(options.permissions ? { permissions: options.permissions } : {}),
        }),
      );
      return;
    }
    if (path.endsWith("/rounds")) {
      roundAttempts += 1;
      if (options.roundConflictOnce && roundAttempts === 1) {
        await fulfillProblem(
          route,
          "TRIAL_PLAN_CONFLICT",
          409,
          true,
          "The Trial Plan was changed by another user.",
        );
        return;
      }
      await fulfillJson(
        route,
        trialPlanDetail(),
        201,
        options.roundReplayed ?? roundAttempts > 1,
      );
      return;
    }
    await fulfillJson(route, trialPlanDetail(), 201, false);
  });
  return observed;
}

async function openWorkspace(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${trialPlanningIds.project}/trials?lang=${locale}`,
    {
      waitUntil: "domcontentloaded",
    },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator(".trial-live__layout")).toBeVisible();
  await expect(page.getByText("Injection machine 550T")).toBeVisible();
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
    name: "Review immutable Trial command",
  });
  await expect(review).toContainText("Irreversible effect");
  await review.getByLabel("Reason").fill(reason);
  await review.getByRole("button", { name: commandName }).click();
}

test.describe("P7-01 live Trial planning workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders Project-first immutable Trial planning truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installTrialApi(page);
      await openWorkspace(page, locale);

      await expect(page.locator("#trial-live-plans > li")).toHaveCount(1);
      await expect(page.getByText("T0", { exact: true }).first()).toBeVisible();
      await expect(page.getByText("No booking claim")).toHaveCount(
        locale === "en" ? 1 : 0,
      );
      await expect(
        page.locator("#trial-live-later .trial-live__later-item"),
      ).toHaveCount(2);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("creates one immutable Plan from exact Tooling, member and resource references", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installTrialApi(page, { empty: true });
    await page.goto(`/projects/${trialPlanningIds.project}/trials?lang=en`, {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByText("No Trial Plan has been recorded for this Project."),
    ).toBeVisible();
    await page.getByRole("button", { name: "Create Trial Plan" }).click();
    await page
      .getByLabel("Tooling Master stable ID")
      .fill(trialPlanningIds.toolingMaster);
    await page.getByLabel("Trial objective").fill("Verify governed T0 scope");
    await page.getByLabel("Machine source object ID").fill("IM-550-02");
    await page.getByLabel("Machine label").fill("Injection machine 550T");
    await page.getByLabel("Material source object ID").fill("MAT-PA66-GF30");
    await page.getByLabel("Material label").fill("PA66-GF30 natural");
    await page.getByLabel("Material quantity").fill("80");
    await page.getByLabel("Material unit").fill("kg");
    await page
      .getByLabel("Responsible Project member stable IDs")
      .fill(trialPlanningIds.member);
    await page
      .getByLabel("Measurement-plan intent")
      .fill("Measure critical housing dimensions");
    await reviewAndConfirm(
      page,
      "Create Trial Plan",
      "Create controlled T0 plan",
    );

    await expect(
      page.getByText(
        "The Trial command was committed with immutable history and audit truth.",
      ),
    ).toBeVisible();
    const command = observed.find((item) => item.method === "POST");
    expect(command).toMatchObject({
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trials`,
      payload: {
        measurementPlan: {
          description: "Measure critical housing dimensions",
        },
        objective: "Verify governed T0 scope",
        reason: "Create controlled T0 plan",
        resources: [
          expect.objectContaining({
            kind: "machine",
            sourceObjectId: "IM-550-02",
          }),
          expect.objectContaining({
            kind: "material",
            quantity: 80,
            sourceObjectId: "MAT-PA66-GF30",
            unit: "kg",
          }),
        ],
        responsibleMemberGlobalIds: [trialPlanningIds.member],
        toolingMasterGlobalId: trialPlanningIds.toolingMaster,
      },
    });
  });

  test("submits version-locked revision, planned Round and governed action commands", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installTrialApi(page);
    await openWorkspace(page, "en");

    await page.getByRole("button", { name: "Append revision" }).click();
    await page
      .getByLabel("Trial objective")
      .fill("Verify governed revised fill balance");
    await reviewAndConfirm(
      page,
      "Append Trial Plan revision",
      "Capture revised Trial intent",
    );

    await page.getByRole("button", { name: "Create planned Round" }).click();
    await page.getByLabel("Optional Round label").fill("T1");
    await reviewAndConfirm(
      page,
      "Create planned Trial Round",
      "Schedule the next controlled Round",
    );

    await page.getByRole("button", { name: "Generate action" }).click();
    await page.getByLabel("Action key").fill("TRIAL.DIMENSION.REVIEW");
    await page.getByLabel("Action title").fill("Review T0 dimensions");
    await page
      .getByLabel("Action description")
      .fill("Review the controlled dimensional result package");
    await page.getByLabel("Related Trial Round").selectOption("T0");
    await page.getByText("Blocking action", { exact: true }).click();
    await reviewAndConfirm(
      page,
      "Generate governed action",
      "Create governed follow-up work",
    );

    const commands = observed.filter((item) => item.method === "POST");
    expect(commands).toHaveLength(3);
    expect(commands[0]).toMatchObject({
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-plans/${trialPlanningIds.plan}/revisions`,
      payload: {
        expectedPlanVersion: 1,
        expectedRevisionGlobalId: trialPlanningIds.revisionOne,
        expectedRevisionSnapshotHash: "1".repeat(64),
        objective: "Verify governed revised fill balance",
      },
    });
    expect(commands[1]).toMatchObject({
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-plans/${trialPlanningIds.plan}/rounds`,
      payload: {
        displayLabel: "T1",
        expectedPlanRevisionGlobalId: trialPlanningIds.revisionOne,
        expectedPlanRevisionSnapshotHash: "1".repeat(64),
      },
    });
    expect(commands[2]).toMatchObject({
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-plans/${trialPlanningIds.plan}/actions:generate`,
      payload: {
        actions: [
          expect.objectContaining({
            actionKey: "TRIAL.DIMENSION.REVIEW",
            blocking: true,
            responsibleMemberGlobalId: trialPlanningIds.member,
            severity: "medium",
            title: "Review T0 dimensions",
          }),
        ],
        expectedPlanRevisionGlobalId: trialPlanningIds.revisionOne,
        trialRoundGlobalId: trialPlanningIds.round,
      },
    });
  });

  test("retries one conflicted Round with the exact idempotency key and exposes replay truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installTrialApi(page, {
      roundConflictOnce: true,
      roundReplayed: true,
    });
    await openWorkspace(page, "en");
    await page.getByRole("button", { name: "Create planned Round" }).click();
    await reviewAndConfirm(
      page,
      "Create planned Trial Round",
      "Create an idempotent planned Round",
    );
    await expect(
      page.getByText("The Trial Plan was changed by another user."),
    ).toBeVisible();
    await page.getByRole("button", { name: "Retry exact command" }).click();
    await expect(
      page.getByText(
        "The exact prior Trial command response was replayed safely.",
      ),
    ).toBeVisible();

    const rounds = observed.filter((item) => item.path.endsWith("/rounds"));
    expect(rounds).toHaveLength(2);
    expect(rounds[0]?.idempotencyKey).toBe(rounds[1]?.idempotencyKey);
    expect(rounds[0]?.payload).toEqual(rounds[1]?.payload);
  });

  test("shows explicit loading, empty, read-only and retryable failure truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installTrialApi(page, { delayWorkspace: true, empty: true });
    await page.goto(`/projects/${trialPlanningIds.project}/trials?lang=en`, {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByText("Loading Trial planning workspace"),
    ).toBeVisible();
    await expect(
      page.getByText("No Trial Plan has been recorded for this Project."),
    ).toBeVisible();

    await page.unroute(trialEndpoint);
    await installTrialApi(page, {
      permissions: {
        canCreatePlan: false,
        canCreateRound: false,
        canGenerateActions: false,
        canRevisePlan: false,
      },
    });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(
      page.getByText("Trial planning is read only for this Project."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Append revision" }),
    ).toHaveCount(0);

    await page.unroute(trialEndpoint);
    await installTrialApi(page, { workspaceFailure: true });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(
      page.getByText(
        "The Trial planning workspace is temporarily unavailable.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p7-01-trial-planning-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p7-01-trial-planning-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p7-01-trial-planning-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P7-01 Trial planning evidence", () => {
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
      await openWorkspace(page, visual.locale);
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
