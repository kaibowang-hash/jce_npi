import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  ControlledPrintCapabilityViewModel,
  ControlledPrintSnapshotViewModel,
} from "../../src/api/controlled-print-data-source";
import type { ProblemDetails } from "../../src/api/http";
import { translate } from "../translate";
import {
  controlledPrintCapabilityFixture,
  controlledPrintProjectId,
  controlledPrintSnapshotFixture,
} from "../support/controlled-print-fixture";
import { projectWorkCockpitFixture } from "../support/project-work-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p5-06-controlled-print-browser-csrf";
const projectVersion = projectWorkCockpitFixture().project.version;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const projectApiEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/.+/u;

interface ObservedRequest {
  csrfToken: string | undefined;
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
  query: string;
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
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type":
        status >= 400 ? "application/problem+json" : "application/json",
      ...(route.request().headers()["idempotency-key"]
        ? { "Idempotency-Replayed": "false" }
        : {}),
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p5-06-controlled-print",
    },
    status,
  });
}

function problem(status: number, code: string): ProblemDetails {
  return {
    code,
    retryable: false,
    status,
    title: "The controlled print request could not be completed.",
    traceId: "trace-p5-06-controlled-print",
    type: `urn:npi:problem:${code.toLowerCase()}`,
  };
}

function capability(locale: TestLocale): ControlledPrintCapabilityViewModel {
  return {
    ...controlledPrintCapabilityFixture(),
    language: locale,
    sourceVersion: projectVersion,
  };
}

function snapshot(locale: TestLocale): ControlledPrintSnapshotViewModel {
  const fixture = controlledPrintSnapshotFixture();
  return {
    ...fixture,
    language: locale,
    source: { ...fixture.source, sourceVersion: projectVersion },
  };
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: {
        language: locale,
        messages: {},
        version: "8".repeat(64),
      },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "printer@example.invalid",
    });
  });
}

async function installApi(
  page: Page,
  locale: TestLocale,
  options: { capability?: "available" | "unavailable" | "denied" } = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const exactCapability = capability(locale);
  const exactSnapshot = snapshot(locale);
  await page.route(projectApiEndpoint, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = request.headers();
    observed.push({
      csrfToken: headers["x-frappe-csrf-token"],
      idempotencyKey: headers["idempotency-key"],
      method: request.method(),
      path: url.pathname,
      payload: request.method() === "POST" ? request.postDataJSON() : null,
      query: url.search,
    });
    if (url.pathname.endsWith("/cockpit")) {
      await fulfillJson(route, projectWorkCockpitFixture());
      return;
    }
    if (url.pathname.endsWith("/controlled-print/capability")) {
      expect(url.searchParams.get("sourceKind")).toBe("npi.project");
      expect(url.searchParams.get("sourceGlobalId")).toBe(
        controlledPrintProjectId,
      );
      expect(url.searchParams.get("sourceVersion")).toBe(
        String(projectVersion),
      );
      expect(url.searchParams.get("language")).toBe(locale);
      if (options.capability === "denied") {
        await fulfillJson(route, problem(403, "CONTROLLED_PRINT_DENIED"), 403);
        return;
      }
      await fulfillJson(
        route,
        options.capability === "unavailable"
          ? {
              ...exactCapability,
              available: false,
              copyState: null,
              deliveryMode: null,
              permissions: { create: false, download: false },
              registry: null,
            }
          : exactCapability,
      );
      return;
    }
    if (
      url.pathname.endsWith("/controlled-prints") &&
      request.method() === "POST"
    ) {
      expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(headers["idempotency-key"]).toMatch(/^controlled-print-/u);
      expect(request.postDataJSON()).toEqual({
        language: locale,
        sourceGlobalId: controlledPrintProjectId,
        sourceKind: "npi.project",
        sourceVersion: projectVersion,
      });
      await fulfillJson(route, exactSnapshot, 201);
      return;
    }
    if (
      url.pathname.endsWith(
        `/controlled-prints/${exactSnapshot.globalId}/content`,
      )
    ) {
      expect(request.method()).toBe("GET");
      expect(headers.accept).toBe("application/pdf");
      await route.fulfill({
        body: "%PDF",
        headers: {
          "Cache-Control": "private, no-store",
          "Content-Disposition": `attachment; filename="${exactSnapshot.output.fileName}"`,
          "Content-Type": "application/pdf",
          "X-NPI-Output-Hash": exactSnapshot.output.sha256,
          "X-NPI-Snapshot-Hash": exactSnapshot.snapshotHash,
          "X-Request-ID": requestIdentity(route),
          "X-Trace-ID": "trace-p5-06-controlled-print",
        },
        status: 200,
      });
      return;
    }
    throw new Error(
      `Unhandled P5-06 browser request: ${request.method()} ${url.pathname}`,
    );
  });
  return observed;
}

async function openProject(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/projects/${controlledPrintProjectId}?lang=${locale}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: /SYN-PROJECT-001 Synthetic project cockpit/u,
    }),
  ).toBeVisible();
}

async function retainControlledPrint(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await page
    .getByRole("button", {
      name: translate(locale, "Check controlled print availability"),
    })
    .click();
  await page
    .getByRole("button", { name: translate(locale, "Create controlled PDF") })
    .click();
  await expect(
    page.getByRole("dialog", {
      name: translate(locale, "Create immutable controlled PDF"),
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: translate(locale, "Create retained PDF") })
    .click();
  await expect(
    page.getByText(translate(locale, "Controlled PDF retained")),
  ).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P5-06 live controlled-print affordance", () => {
  test("creates and downloads only one exact retained output", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page, "en");
    await openProject(page, "en");
    await retainControlledPrint(page, "en");

    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download retained PDF" }).click();
    expect((await download).suggestedFilename()).toBe(
      "controlled-project-001.pdf",
    );
    await expect(page.getByText("Retained PDF downloaded")).toBeVisible();

    const create = observed.find(
      (item) =>
        item.method === "POST" && item.path.endsWith("/controlled-prints"),
    );
    expect(create?.csrfToken).toBe(csrfToken);
    expect(create?.idempotencyKey).toMatch(/^controlled-print-/u);
    expect(create?.payload).not.toHaveProperty("actorUserId");
    expect(create?.payload).not.toHaveProperty("template");
    expect(create?.payload).not.toHaveProperty("watermarkSource");
    expect(create?.payload).not.toHaveProperty("fileUrl");
  });

  test("keeps absent mapping and permission denial closed", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installApi(page, "en", { capability: "unavailable" });
    await openProject(page, "en");
    await page
      .getByRole("button", { name: "Check controlled print availability" })
      .click();
    await expect(
      page.getByText("Controlled print is unavailable"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Create controlled PDF" }),
    ).toHaveCount(0);

    await page.unroute(projectApiEndpoint);
    await installApi(page, "en", { capability: "denied" });
    await page.getByRole("button", { name: "Check again" }).click();
    await expect(
      page.getByText("Controlled print permission unavailable"),
    ).toBeVisible();
    await expect(page.getByText("trace-p5-06-controlled-print")).toBeVisible();
    expect(
      await page
        .locator("[data-language-exempt='identifier']")
        .allTextContents(),
    ).not.toContain("/private/files/");
  });

  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`passes language, industrial and accessibility checks in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installApi(page, locale);
      await openProject(page, locale);
      await retainControlledPrint(page, locale);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      expect(await page.locator('[data-visual-primary="true"]').count()).toBe(
        0,
      );
    });
  }
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p5-06-controlled-print-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p5-06-controlled-print-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p5-06-controlled-print-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P5-06 controlled-print evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installApi(page, visual.locale);
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
      await openProject(page, visual.locale);
      await retainControlledPrint(page, visual.locale);
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
