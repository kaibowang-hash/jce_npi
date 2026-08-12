import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  ReadinessTemplateCatalog,
  ReadinessWorkspace,
} from "../../src/api/readiness-data-source";
import { translate } from "../../src/i18n/runtime";
import {
  readinessEmptyWorkspace,
  readinessIds,
  readinessPublishedTemplate,
  readinessRevisedWorkspace,
  readinessWorkspace,
} from "../support/readiness-fixture";
import {
  projectWorkCockpitFixture,
  projectWorkContextFixture,
} from "../support/project-work-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p7-05-readiness-browser-csrf-exact";
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const projectEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/.+/u;
const templateCatalogEndpoint =
  /\/api\/npi\/v1\/npi-readiness\/templates(?:\?.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

type ProblemStatus = 403 | 409 | 422 | 503;

interface ObservedRequest {
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
}

interface ApiOptions {
  commandWorkspace?: ReadinessWorkspace;
  loadDelay?: boolean;
  loadProblem?: ProblemStatus;
  malformedWorkspace?: boolean;
  replayed?: boolean;
  reviseDelay?: boolean;
  reviseProblems?: readonly ProblemStatus[];
  templateCatalog?: ReadinessTemplateCatalog;
  workspace?: ReadinessWorkspace;
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
      "X-Trace-ID": "trace-p7-05-readiness-browser",
    },
    status,
  });
}

function problemFor(status: ProblemStatus): {
  code: string;
  fieldErrors?: readonly { message: string; path: string }[];
  retryable: boolean;
  title: string;
} {
  if (status === 403) {
    return {
      code: "PERMISSION_DENIED",
      retryable: false,
      title: "You do not have permission to perform this action.",
    };
  }
  if (status === 409) {
    return {
      code: "READINESS_VERSION_CONFLICT",
      retryable: false,
      title: "The NPI readiness record was changed by another user.",
    };
  }
  if (status === 422) {
    return {
      code: "VALIDATION_FAILED",
      fieldErrors: [
        {
          message: "Select a supported readiness item state.",
          path: "state",
        },
      ],
      retryable: false,
      title: "Correct the highlighted fields and submit again.",
    };
  }
  return {
    code: "READINESS_ROUTES_DISABLED",
    retryable: true,
    title: "The NPI Readiness workspace is temporarily unavailable.",
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
      ...(problem.fieldErrors ? { fieldErrors: problem.fieldErrors } : {}),
      retryable: problem.retryable,
      status,
      title: problem.title,
      traceId: "trace-p7-05-readiness-browser",
      type: `urn:npi:problem:${problem.code.toLowerCase()}`,
    }),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p7-05-readiness-browser",
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "5".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "quality.lead@example.invalid",
    });
  });
}

async function installReadinessApi(
  page: Page,
  options: ApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const workspace = options.workspace ?? readinessWorkspace();
  const commandWorkspace =
    options.commandWorkspace ?? readinessRevisedWorkspace();
  let reviseAttempt = 0;
  if (options.templateCatalog) {
    await page.route(templateCatalogEndpoint, async (route) => {
      expect(route.request().method()).toBe("GET");
      expect(new URL(route.request().url()).searchParams.get("projectId")).toBe(
        readinessIds.project,
      );
      await fulfillJson(route, options.templateCatalog);
    });
  }
  await page.route(projectEndpoint, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const payload: unknown =
      request.method() === "POST" || request.method() === "PUT"
        ? (JSON.parse(request.postData() ?? "null") as unknown)
        : null;
    observed.push({
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path,
      payload,
    });
    expect(request.headers().accept).toBe(
      "application/json, application/problem+json",
    );
    if (path.endsWith("/cockpit")) {
      await fulfillJson(route, projectWorkCockpitFixture());
      return;
    }
    if (path.endsWith("/work-context")) {
      await fulfillJson(route, projectWorkContextFixture());
      return;
    }
    if (request.method() === "GET" && path.endsWith("/npi-readiness")) {
      if (options.loadDelay) {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 450);
        });
      }
      if (options.loadProblem) {
        await fulfillProblem(route, options.loadProblem);
        return;
      }
      await fulfillJson(
        route,
        options.malformedWorkspace
          ? { ...workspace, callerSuppliedReady: true }
          : workspace,
      );
      return;
    }
    if (
      request.method() === "POST" &&
      path.endsWith(`/npi-readiness/${readinessIds.instance}/revisions`)
    ) {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(
        /^readiness-revise-[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u,
      );
      reviseAttempt += 1;
      if (options.reviseDelay) {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 450);
        });
      }
      const problem = options.reviseProblems?.[reviseAttempt - 1];
      if (problem) {
        await fulfillProblem(route, problem);
        return;
      }
      await fulfillJson(
        route,
        commandWorkspace,
        201,
        options.replayed ?? false,
      );
      return;
    }
    throw new Error(
      `Unexpected P7-05 browser request: ${request.method()} ${path}`,
    );
  });
  return observed;
}

async function openReadiness(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${readinessIds.project}?lang=${locale}&tab=readiness`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("tab", {
      exact: true,
      name: translate(locale, "NPI readiness"),
    }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("readiness-workspace")).toBeVisible();
}

async function openSupplierInspector(page: Page): Promise<void> {
  const item = page.getByTestId("readiness-item-supplier_execution");
  await item.focus();
  await expect(item).toBeFocused();
  await item.press("Enter");
  await expect(page.getByTestId("readiness-item-inspector")).toBeVisible();
}

async function submitSupplierRevision(page: Page): Promise<void> {
  await openSupplierInspector(page);
  await page.getByLabel("Item state").selectOption("in_progress");
  await page.getByRole("button", { name: "Review readiness revision" }).click();
  const review = page.getByRole("dialog", {
    name: "Review readiness revision",
  });
  await expect(review).toBeVisible();
  await review
    .getByRole("button", { name: "Append readiness revision" })
    .click();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include('[data-testid="readiness-workspace"]')
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P7-05 live Project readiness workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`keeps P0 blockers dominant over a high score in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      const observed = await installReadinessApi(page);
      await openReadiness(page, locale);

      await expect(page.getByTestId("readiness-summary")).toBeVisible();
      await expect(page.getByTestId("readiness-score-summary")).toContainText(
        "99",
      );
      await expect(page.getByTestId("readiness-blocker-summary")).toContainText(
        "2",
      );
      await expect(
        page.getByTestId("readiness-category-engineering"),
      ).toBeVisible();
      await expect(
        page.getByTestId("readiness-category-industrialization"),
      ).toBeVisible();
      await openSupplierInspector(page);
      await expect(
        page.getByTestId(
          "readiness-source-formal_supplier_execution-erp_supplier_execution",
        ),
      ).toBeVisible();
      await expect(
        page.getByTestId("readiness-unavailable-projections"),
      ).toBeVisible();
      await expect(page.getByTestId("readiness-history")).toBeVisible();
      expect(
        observed.filter((request) => request.path.endsWith("/npi-readiness"))
          .length,
      ).toBeGreaterThanOrEqual(1);
      expect(observed.every((request) => request.method === "GET")).toBe(true);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  for (const locale of ["zh", "zh-TW"] as const) {
    test(`scopes a configured English template title in the ${locale} initialization catalog`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installReadinessApi(page, {
        templateCatalog: {
          projectGlobalId: readinessIds.project,
          templates: [readinessPublishedTemplate()],
        },
        workspace: readinessEmptyWorkspace({
          canInitialize: true,
          canManageTemplates: false,
          canRevise: false,
        }),
      });
      await page.goto(
        `/projects/${readinessIds.project}?lang=${locale}&tab=readiness`,
        { waitUntil: "domcontentloaded" },
      );

      const option = page.getByRole("option", {
        name: "Automotive readiness",
      });
      await expect(option).toBeAttached();
      await expect(option).toHaveAttribute(
        "data-language-exempt-tokens",
        JSON.stringify(["Automotive readiness"]),
      );
      await expectNoMixedLanguage(page, locale);
    });
  }

  test("exposes loading, empty, permission and fail-closed BFF states without stale readiness truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installReadinessApi(page, { loadDelay: true });
    await page.goto(`/projects/${readinessIds.project}?lang=en&tab=readiness`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("readiness-loading")).toBeVisible();
    await expect(page.getByTestId("readiness-summary")).toBeVisible();

    await page.unroute(projectEndpoint);
    await installReadinessApi(page, { workspace: readinessEmptyWorkspace() });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("readiness-empty")).toContainText(
      "NPI readiness has not been initialized",
    );
    await expect(page.getByTestId("readiness-revise")).toHaveCount(0);

    await page.unroute(projectEndpoint);
    await installReadinessApi(page, { loadProblem: 403 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("readiness-error")).toContainText(
      "NPI readiness access is not available",
    );
    await expect(page.getByTestId("readiness-summary")).toHaveCount(0);

    await page.unroute(projectEndpoint);
    await installReadinessApi(page, { malformedWorkspace: true });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("readiness-error")).toContainText(
      "NPI readiness data is unavailable",
    );
    await expect(page.getByTestId("readiness-summary")).toHaveCount(0);
    await expect(page.getByTestId("readiness-revise")).toHaveCount(0);
  });

  test("keeps current read-only and historical revisions non-editable", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installReadinessApi(page, {
      workspace: readinessWorkspace({
        permissions: {
          canInitialize: false,
          canManageTemplates: false,
          canRevise: false,
        },
      }),
    });
    await openReadiness(page, "en");

    await expect(page.getByText("Read-only workspace").first()).toBeVisible();
    await openSupplierInspector(page);
    await expect(
      page.getByRole("button", { name: "Review readiness revision" }),
    ).toHaveCount(0);
    await page.getByTestId("readiness-revision-1").click();
    await expect(page.getByText("Historical revision")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Review readiness revision" }),
    ).toHaveCount(0);
  });

  test("fails closed on 409 drift and 422 validation without submitting caller score or Gate truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installReadinessApi(page, {
      reviseProblems: [409],
    });
    await openReadiness(page, "en");
    await submitSupplierRevision(page);

    await expect(page.getByText("Input drift", { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        "The retained readiness revision changed. Reload before editing again.",
      ),
    ).toBeVisible();
    const conflict = observed.find((request) => request.method === "POST");
    expect(conflict?.payload).toEqual({
      confirmationValue: null,
      dueDate: "2026-08-22",
      expectedInstanceVersion: 2,
      expectedRevisionGlobalId: readinessIds.revisionTwo,
      expectedRevisionSnapshotHash:
        "0780e831695a9ee52b688438079bb6a233a23a391b51d7c4f03ca284905299a6",
      itemKey: "supplier_execution",
      ownerMemberGlobalId: readinessIds.qualityMember,
      sources: [
        {
          kind: "erp_supplier_execution",
          requirementKey: "formal_supplier_execution",
        },
      ],
      state: "in_progress",
    });
    expect(conflict?.payload).not.toHaveProperty("evaluation");
    expect(conflict?.payload).not.toHaveProperty("ready");
    expect(conflict?.payload).not.toHaveProperty("gate");

    await page.unroute(projectEndpoint);
    await installReadinessApi(page, { reviseProblems: [422] });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("readiness-summary")).toBeVisible();
    await submitSupplierRevision(page);
    await expect(
      page.getByText("Validation failed", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Retry same command" }),
    ).toHaveCount(0);
  });

  test("shows processing and retries a 503 with the same idempotency key before exposing replay truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installReadinessApi(page, {
      replayed: true,
      reviseDelay: true,
      reviseProblems: [503],
    });
    await openReadiness(page, "en");
    await submitSupplierRevision(page);

    await expect(page.getByTestId("readiness-processing")).toContainText(
      "Saving exact readiness revision",
    );
    await expect(
      page.getByText("Command failed", { exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Retry same command" }).click();
    await expect(page.getByTestId("readiness-replay-receipt")).toContainText(
      "The server replayed the sealed readiness response.",
    );
    const commands = observed.filter((request) => request.method === "POST");
    expect(commands).toHaveLength(2);
    expect(commands[0]?.idempotencyKey).toBe(commands[1]?.idempotencyKey);
  });

  test("retries a retryable workspace load while preserving unavailable formal-source truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installReadinessApi(page, { loadProblem: 503 });
    await page.goto(`/projects/${readinessIds.project}?lang=en&tab=readiness`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("readiness-error")).toContainText(
      "NPI readiness data is unavailable",
    );

    await page.unroute(projectEndpoint);
    await installReadinessApi(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(page.getByTestId("readiness-summary")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Unavailable formal sources" }),
    ).toBeVisible();
    await expect(
      page.getByTestId("readiness-unavailable-projections"),
    ).toBeVisible();
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p7-05-readiness-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p7-05-readiness-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p7-05-readiness-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P7-05 Project readiness evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installReadinessApi(page);
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
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await page.evaluate(() => {
        globalThis.scrollTo(0, 0);
      });
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
