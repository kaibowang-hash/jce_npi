import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  ToolingImportCorrectionArtifact,
  ToolingImportPermissions,
} from "../../src/api/tooling-import-contract";
import {
  toolingImportCollection,
  toolingImportDetail,
  toolingImportIds,
  toolingImportJob,
  toolingImportReconciliation,
} from "../support/tooling-import-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p6-07-tooling-import-browser-csrf";
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const importEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/tooling-imports(?:\/.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

interface ObservedRequest {
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
}

const correctionArtifact: ToolingImportCorrectionArtifact = {
  batchGlobalId: toolingImportIds.batch,
  createdAt: "2026-08-09T08:02:00Z",
  createdByUserId: "tooling.engineer@example.invalid",
  entryCount: 1,
  fileName: "tooling-import-correction.csv",
  frappeFileId: "private/files/tooling-import-correction.csv",
  globalId: toolingImportIds.correction,
  jobGlobalId: toolingImportIds.job,
  jobSnapshotHash: "a".repeat(64),
  mimeType: "text/csv",
  requestId: toolingImportIds.request,
  schemaVersion: "tooling-import-correction.v1",
  sha256: "e".repeat(64),
  sizeBytes: 16,
  snapshotHash: "d".repeat(64),
  traceId: "trace-correction",
};

function requestIdentity(route: Route): string {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  return requestId;
}

async function fulfillJson(
  route: Route,
  body: unknown,
  status = 200,
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(route.request().headers()["idempotency-key"]
        ? { "Idempotency-Replayed": "false" }
        : {}),
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p6-07-tooling-import-browser",
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
      userId: "tooling.engineer@example.invalid",
    });
  });
}

async function installImportApi(
  page: Page,
  options: {
    invalidCollection?: boolean;
    permissions?: ToolingImportPermissions;
    rollbackDenied?: boolean;
  } = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(importEndpoint, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    observed.push({
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path,
      payload: request.method() === "POST" ? request.postDataJSON() : null,
    });
    if (request.method() === "POST") {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(/^tooling-import-/u);
    }
    if (path.endsWith(":retry")) {
      await fulfillJson(route, { job: toolingImportJob("queued") }, 201);
      return;
    }
    if (path.endsWith("/correction-artifacts")) {
      await fulfillJson(route, { correctionArtifact }, 201);
      return;
    }
    if (path.endsWith(":evaluate-rollback")) {
      await fulfillJson(
        route,
        {
          rollbackEligibility: {
            ...toolingImportReconciliation(
              options.rollbackDenied ? "downstream_used" : "matched",
            ),
            kind: "rollback_eligibility",
          },
        },
        201,
      );
      return;
    }
    if (path.endsWith(`/tooling-imports/${toolingImportIds.batch}`)) {
      const detail = toolingImportDetail();
      await fulfillJson(
        route,
        options.permissions
          ? { ...detail, permissions: options.permissions }
          : detail,
      );
      return;
    }
    if (path.endsWith("/tooling-imports")) {
      if (options.invalidCollection) {
        await fulfillJson(route, { projectGlobalId: toolingImportIds.project });
        return;
      }
      const collection = toolingImportCollection();
      await fulfillJson(
        route,
        options.permissions
          ? { ...collection, permissions: options.permissions }
          : collection,
      );
      return;
    }
    await route.abort();
  });
  return observed;
}

async function openWorkspace(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${toolingImportIds.project}/tooling?workspace=import&lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator(".tooling-import__layout")).toBeVisible();
  await expect(
    page.getByText("synthetic-tooling-list.xlsx").first(),
  ).toBeVisible();
}

async function selectStep(page: Page, index: number): Promise<void> {
  await page.locator(".tooling-import__step").nth(index).click();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P6-07 live Tooling List import workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders exact partial worker truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installImportApi(page);
      await openWorkspace(page, locale);
      await selectStep(page, 6);

      await expect(page.locator(".tooling-import__result-strip")).toBeVisible();
      await expect(page.getByText("trace-worker-row")).toBeVisible();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("creates a bounded correction artifact and retries exact failed rows", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installImportApi(page);
    await openWorkspace(page, "en");
    await selectStep(page, 6);

    await page.getByLabel("Worksheet").fill("Tooling List");
    await page.getByLabel("Source row").fill("3");
    await page.getByLabel("Source column").fill("Tooling No.");
    await page.getByLabel("Corrected value").fill("TL-SYN-002");
    await page
      .getByRole("button", { name: "Create controlled correction file" })
      .click();
    await expect(page.getByText("tooling-import-correction.csv")).toBeVisible();
    await page.getByRole("button", { name: "Retry exact failed rows" }).click();

    await expect
      .poll(() => observed.filter((item) => item.method === "POST").length)
      .toBe(2);
    expect(observed.filter((item) => item.method === "POST")).toEqual([
      expect.objectContaining({
        path: `/api/npi/v1/projects/${toolingImportIds.project}/tooling-imports/${toolingImportIds.batch}/jobs/${toolingImportIds.job}/correction-artifacts`,
        payload: expect.objectContaining({
          corrections: [
            {
              correctedValue: "TL-SYN-002",
              sourceHeader: "Tooling No.",
              sourceRow: 3,
              worksheetName: "Tooling List",
            },
          ],
        }),
      }),
      expect.objectContaining({
        path: `/api/npi/v1/projects/${toolingImportIds.project}/tooling-imports/${toolingImportIds.batch}/jobs/${toolingImportIds.job}:retry`,
        payload: expect.objectContaining({
          correctionArtifactGlobalId: toolingImportIds.correction,
        }),
      }),
    ]);
  });

  test("renders server rollback denial without exposing a destructive action", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installImportApi(page, { rollbackDenied: true });
    await openWorkspace(page, "en");
    await selectStep(page, 7);
    await page
      .getByRole("button", { name: "Evaluate rollback eligibility" })
      .click();

    await expect(
      page.getByText("Rollback is denied by current target usage or changes."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Rollback imported unused objects" }),
    ).toHaveCount(0);
  });

  test("shows no-permission truth and rejects an invalid collection response", async ({
    page,
  }) => {
    await installSession(page, "en");
    const noPermission: ToolingImportPermissions = {
      activateProductionMapping: false,
      confirmPreview: false,
      createCorrectionArtifact: false,
      createMappingProposal: false,
      createPreview: false,
      downloadCorrectionArtifact: false,
      evaluateRollback: false,
      execute: false,
      inspect: false,
      reconcile: false,
      registerSource: false,
      retry: false,
      rollback: false,
      view: true,
    };
    await installImportApi(page, { permissions: noPermission });
    await openWorkspace(page, "en");
    await expect(
      page.getByRole("button", { name: "Register controlled workbook" }),
    ).toBeDisabled();

    await page.unroute(importEndpoint);
    await installImportApi(page, { invalidCollection: true });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(
      page.getByText("The service returned an invalid response."),
    ).toBeVisible();
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p6-07-tooling-import-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p6-07-tooling-import-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p6-07-tooling-import-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P6-07 Tooling List import evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installImportApi(page);
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
      await selectStep(page, 6);
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
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
