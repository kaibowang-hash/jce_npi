import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ErpProjectionCollectionViewModel } from "../../src/api/erp-projections-data-source";
import { translate } from "../../src/i18n/runtime";
import {
  erpProjectionCollectionFixture,
  projectControlIds,
  projectControlsFixture,
} from "../support/project-controls-fixture";
import { projectCockpitFixture } from "../support/project-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = projectControlIds.project;
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const cockpitEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/cockpit(?:\?.*)?$/u;
const controlsEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/controls(?:\?.*)?$/u;
const projectionsEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/erp-projections(?:\?.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

function required<T>(value: T | undefined, message: string): T {
  if (value === undefined) throw new Error(message);
  return value;
}

interface ProjectionApiOptions {
  malformed?: boolean;
  problemStatus?: 403 | 503;
  responseMayComplete?: Promise<void>;
  value?: ErpProjectionCollectionViewModel;
}

function requestIdentity(route: Route): string {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  expect(route.request().headers().accept).toBe(
    "application/json, application/problem+json",
  );
  return requestId;
}

async function fulfillJson(
  route: Route,
  body: unknown,
  traceId: string,
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": traceId,
    },
    status: 200,
  });
}

async function fulfillProblem(
  route: Route,
  locale: TestLocale,
  status: 403 | 503,
): Promise<void> {
  const denied = status === 403;
  const title = denied
    ? "You do not have permission to perform this action."
    : "ERP projection access is temporarily unavailable.";
  await route.fulfill({
    body: JSON.stringify({
      code: denied ? "PERMISSION_DENIED" : "ERP_PROJECTION_UNAVAILABLE",
      retryable: !denied,
      status,
      title: translate(locale, title),
      traceId: `trace-p8-01-projection-${String(status)}`,
      type: denied
        ? "urn:npi:problem:permission-denied"
        : "urn:npi:problem:erp-projection-unavailable",
    }),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": `trace-p8-01-projection-${String(status)}`,
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(
      route,
      {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: { language: locale, messages: {}, version: "8".repeat(64) },
        csrfToken: "p8-01-projection-browser-csrf-token",
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "project.manager@example.invalid",
      },
      "trace-p8-01-session",
    );
  });
}

async function installProjectApi(
  page: Page,
  locale: TestLocale,
  options: ProjectionApiOptions = {},
): Promise<string[]> {
  const observed: string[] = [];
  await page.route(cockpitEndpoint, async (route) => {
    expect(route.request().method()).toBe("GET");
    observed.push(new URL(route.request().url()).pathname);
    await fulfillJson(route, projectCockpitFixture(), "trace-p8-01-cockpit");
  });
  await page.route(controlsEndpoint, async (route) => {
    expect(route.request().method()).toBe("GET");
    observed.push(new URL(route.request().url()).pathname);
    await fulfillJson(route, projectControlsFixture(), "trace-p8-01-controls");
  });
  await page.route(projectionsEndpoint, async (route) => {
    expect(route.request().method()).toBe("GET");
    expect(new URL(route.request().url()).search).toBe("");
    observed.push(new URL(route.request().url()).pathname);
    if (options.responseMayComplete) {
      await options.responseMayComplete;
    }
    if (options.problemStatus) {
      await fulfillProblem(route, locale, options.problemStatus);
      return;
    }
    const value = options.value ?? erpProjectionCollectionFixture();
    await fulfillJson(
      route,
      options.malformed
        ? { ...value, sourceUrl: "https://erp.example.invalid/private" }
        : value,
      "trace-p8-01-projections",
    );
  });
  return observed;
}

async function openControls(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/projects/${projectId}?lang=${locale}&tab=controls`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: translate(locale, "ERPNext governed projections"),
    }),
  ).toBeVisible();
}

async function settleVisual(page: Page): Promise<void> {
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await page.locator(".route-loading").waitFor({ state: "detached" });
  await page.waitForTimeout(100);
}

test.describe("P8-01 live ERP projection read path", () => {
  test("loads all projection kinds, supports keyboard inspection and exposes no write path", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 900, width: 1440 });
    await installSession(page, "en");
    const observed = await installProjectApi(page, "en");
    await openControls(page, "en");

    const panel = page
      .getByRole("heading", { name: "ERPNext governed projections" })
      .locator("xpath=../..");
    await expect(panel.getByRole("radio")).toHaveCount(7);
    await expect(panel.getByText("Mobility Customer")).toBeVisible();
    const asset = panel.getByRole("radio", {
      name: "Inspect Tool Asset status",
    });
    await asset.focus();
    await expect(asset).toBeFocused();
    await asset.press("Space");
    await expect(asset).toBeChecked();
    await expect(panel.getByText("ASSET-00042")).toBeVisible();
    await expect(panel.getByText("No, read only")).toBeVisible();
    await expect(
      panel.getByRole("button", { name: /edit|refresh/iu }),
    ).toHaveCount(0);
    expect(observed).toContain(
      `/api/npi/v1/projects/${projectId}/erp-projections`,
    );

    await expectNoMixedLanguage(page, "en");
    await expectNoDocumentOverflow(page);
    await expectIndustrialComputedStyles(page);
    const accessibility = await new AxeBuilder({ page })
      .include("#main-content")
      .analyze();
    expect(accessibility.violations).toEqual([]);
  });

  test("withholds stale, unavailable, synthetic and conflicted observations", async ({
    page,
  }) => {
    const value = erpProjectionCollectionFixture();
    required(value.items[0], "The stale projection is required.").freshness =
      "stale";
    const unavailable = required(
      value.items[1],
      "The unavailable projection is required.",
    );
    unavailable.availability = "unavailable";
    unavailable.freshness = "unknown";
    unavailable.disposition = "unavailable_current";
    unavailable.sourceVersion = null;
    unavailable.sourceModifiedAt = null;
    unavailable.unavailableReasonCode = "not_observed";
    unavailable.values = null;
    unavailable.currentTruth = null;
    const synthetic = required(
      value.items[2],
      "The synthetic projection is required.",
    );
    synthetic.availability = "synthetic";
    synthetic.freshness = "unknown";
    synthetic.disposition = "synthetic_retained";
    required(
      value.items[3],
      "The conflicted projection is required.",
    ).disposition = "conflicted";
    await installSession(page, "en");
    await installProjectApi(page, "en", { value });
    await openControls(page, "en");

    const panel = page
      .getByRole("heading", { name: "ERPNext governed projections" })
      .locator("xpath=../..");
    await expect(panel.getByText("Formal value withheld")).toBeVisible();
    await expect(panel.getByText("Mobility Customer")).toHaveCount(0);
    await expect(panel.getByText("Unavailable observation")).toBeVisible();
    await expect(panel.getByText("Synthetic observation")).toBeVisible();
    await expect(panel.getByText("Conflicted observation")).toBeVisible();
  });

  test("keeps loading, redacted, denied, retryable and invalid responses explicit", async ({
    page,
  }) => {
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await installSession(page, "en");
    await installProjectApi(page, "en", { responseMayComplete });
    const navigation = page.goto(
      `/projects/${projectId}?lang=en&tab=controls`,
      { waitUntil: "domcontentloaded" },
    );
    try {
      await expect(page.getByLabel("Loading ERP projections")).toBeVisible();
    } finally {
      releaseResponse?.();
    }
    await navigation;
    await expect(
      page.getByRole("heading", { name: "ERPNext governed projections" }),
    ).toBeVisible();
    await expect(page.getByText("Mobility Customer")).toBeVisible();

    await page.unrouteAll({ behavior: "wait" });
    await installSession(page, "en");
    await installProjectApi(page, "en", {
      value: {
        projectGlobalId: projectId,
        accessState: "redacted",
        reasonCode: "projection_access_redacted",
        permissions: { view: false, edit: false, refresh: false },
        items: [],
      },
    });
    await openControls(page, "en");
    await expect(
      page.getByText("No protected ERP projection values were displayed."),
    ).toBeVisible();

    await page.unrouteAll({ behavior: "wait" });
    await installSession(page, "en");
    await installProjectApi(page, "en", { problemStatus: 403 });
    await openControls(page, "en");
    await expect(
      page.getByText("ERP projection access is not available"),
    ).toBeVisible();
    await expect(page.getByText("trace-p8-01-projection-403")).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);

    await page.unrouteAll({ behavior: "wait" });
    await installSession(page, "en");
    await installProjectApi(page, "en", { problemStatus: 503 });
    await openControls(page, "en");
    await expect(
      page.getByText("ERP projection data could not be used safely"),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();

    await page.unrouteAll({ behavior: "wait" });
    await installSession(page, "en");
    await installProjectApi(page, "en", { malformed: true });
    await openControls(page, "en");
    await expect(
      page.getByText("ERP projection data could not be used safely"),
    ).toBeVisible();
    await expect(page.getByText("Mobility Customer")).toHaveCount(0);
  });

  for (const locale of ["zh", "zh-TW"] as const) {
    test(`renders the governed projection surface entirely from the ${locale} catalog`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installProjectApi(page, locale);
      await openControls(page, locale);
      await expectNoMixedLanguage(page, locale);
      await expect(page.getByText("ERPNext governed projections")).toHaveCount(
        0,
      );
    });
  }
});

test.describe("@visual P8-01 governed ERP projection evidence", () => {
  const profiles = [
    { locale: "en", scale: 1, viewport: { height: 768, width: 1366 } },
    { locale: "zh", scale: 1.25, viewport: { height: 900, width: 1440 } },
    {
      locale: "zh-TW",
      scale: 1.5,
      viewport: { height: 1080, width: 1920 },
    },
  ] as const;

  for (const profile of profiles) {
    const scaleLabel = String(profile.scale * 100);
    const viewportLabel = `${String(profile.viewport.width)}x${String(
      profile.viewport.height,
    )}`;
    test(`p8-01-erp-projections-${profile.locale}-${viewportLabel}-${scaleLabel}`, async ({
      page,
    }) => {
      await page.setViewportSize(
        effectiveViewport(profile.viewport, profile.scale),
      );
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      await installSession(page, profile.locale);
      await installProjectApi(page, profile.locale);
      await openControls(page, profile.locale);
      const panel = page
        .getByRole("heading", {
          name: translate(profile.locale, "ERPNext governed projections"),
        })
        .locator("xpath=../..");
      const surface = panel.locator(".erp-projections__layout");
      await surface.evaluate((element) => {
        if (element instanceof HTMLElement) {
          element.style.gridTemplateColumns = "minmax(0, 1fr) 18rem";
        }
        const table = element.querySelector<HTMLElement>(
          ".erp-projections__table",
        );
        const inspector =
          element.querySelector<HTMLElement>(".docked-inspector");
        if (table) {
          table.style.blockSize = "24rem";
          table.style.maxBlockSize = "24rem";
        }
        if (inspector) {
          inspector.style.blockSize = "24rem";
          inspector.style.maxBlockSize = "24rem";
          inspector.style.position = "static";
        }
      });
      await surface.scrollIntoViewIfNeeded();
      await settleVisual(page);
      await expectNoMixedLanguage(page, profile.locale);

      await expect(surface).toHaveScreenshot(
        `p8-01-erp-projections-${profile.locale}-${viewportLabel}-${scaleLabel}.png`,
      );
    });
  }
});
