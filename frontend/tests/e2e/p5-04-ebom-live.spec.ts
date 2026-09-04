import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  EngineeringBomCommandViewModel,
  EngineeringBomDetailViewModel,
  EngineeringBomListViewModel,
} from "../../src/api/ebom-data-source";
import { translate } from "../translate";
import {
  ebomId,
  ebomRevisionOneId,
  ebomRevisionTwoId,
  engineeringBomComparisonFixture,
  engineeringBomDetailFixture,
  engineeringBomListFixture,
} from "../support/ebom-fixture";
import { projectWorkCockpitFixture } from "../support/project-work-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const csrfToken = "p5-04-ebom-browser-csrf-token-exact";
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

function listFixture(): EngineeringBomListViewModel {
  const fixture = engineeringBomListFixture();
  return {
    ...fixture,
    project: { ...fixture.project, globalId: projectId },
  };
}

function detailFixture(): EngineeringBomDetailViewModel {
  const fixture = engineeringBomDetailFixture();
  return {
    ...fixture,
    project: { ...fixture.project, globalId: projectId },
  };
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
      "Content-Type": "application/json",
      ...(route.request().headers()["idempotency-key"]
        ? { "Idempotency-Replayed": "false" }
        : {}),
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p5-04-ebom-browser",
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: {
        language: locale,
        messages: {},
        version: "f".repeat(64),
      },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "engineer@example.invalid",
    });
  });
}

function submittedDetail(
  detail: EngineeringBomDetailViewModel,
): EngineeringBomDetailViewModel {
  const latest = detail.revisions[0];
  if (!latest)
    throw new Error("The EBOM browser fixture has no latest revision.");
  const event = {
    globalId: "75000000-0000-4000-8000-000000000011",
    eventType: "review_submitted" as const,
    fromState: "draft" as const,
    toState: "in_review" as const,
    fromVersion: 1,
    toVersion: 2,
    actorUserId: "engineer@example.invalid",
    decision: null,
    reason: "Ready for exact review",
    confirmationIntent: null,
    occurredAt: "2026-08-05T10:00:00Z",
    eventHash: "d".repeat(64),
  };
  return {
    ...detail,
    revisions: [
      {
        ...latest,
        lifecycle: {
          state: "in_review",
          version: 2,
          lastEventId: event.globalId,
        },
        events: [event],
        capabilities: {
          ...latest.capabilities,
          revise: false,
          submitReview: false,
          review: true,
        },
      },
      ...detail.revisions.slice(1),
    ],
  };
}

async function installEbomApi(page: Page): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const list = listFixture();
  let detail = detailFixture();
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
    if (url.pathname.endsWith("/eboms") && request.method() === "GET") {
      await fulfillJson(route, list);
      return;
    }
    if (url.pathname.endsWith(`/eboms/${ebomId}`)) {
      await fulfillJson(route, detail);
      return;
    }
    if (url.pathname.endsWith(`/eboms/${ebomId}/compare`)) {
      const comparison = engineeringBomComparisonFixture();
      await fulfillJson(route, comparison);
      return;
    }
    if (url.pathname.endsWith(":submit-review")) {
      expect(request.method()).toBe("POST");
      expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(headers["idempotency-key"]).toMatch(/^ebom-submit-/u);
      const payload = request.postDataJSON() as Record<string, unknown>;
      expect(payload).toEqual({
        expectedEbomVersion: 2,
        expectedRevisionSnapshotHash: "c".repeat(64),
        expectedLifecycleVersion: 1,
        policyGlobalId: "75000000-0000-4000-8000-000000000005",
        policyVersion: 1,
        policySnapshotHash: "a".repeat(64),
        reason: "Ready for exact review",
      });
      expect(payload).not.toHaveProperty("actorUserId");
      expect(payload).not.toHaveProperty("formalItemCode");
      expect(payload).not.toHaveProperty("mbomId");
      detail = submittedDetail(detail);
      const latest = detail.revisions[0];
      if (!latest)
        throw new Error("The submitted EBOM revision is unavailable.");
      const response: EngineeringBomCommandViewModel = {
        ebom: detail.ebom,
        revision: latest,
      };
      await fulfillJson(route, response, 201);
      return;
    }
    throw new Error(
      `Unhandled P5-04 browser request: ${request.method()} ${url.pathname}${url.search}`,
    );
  });
  return observed;
}

async function openEbom(page: Page, locale: TestLocale): Promise<void> {
  const cockpitResponse = page.waitForResponse((response) => {
    const request = response.request();
    const url = new URL(response.url());
    return (
      request.method() === "GET" &&
      url.pathname === `/api/npi/v1/projects/${projectId}/cockpit` &&
      url.search === ""
    );
  });
  await page.goto(`/projects/${projectId}?lang=${locale}&tab=ebom`, {
    waitUntil: "domcontentloaded",
  });
  expect((await cockpitResponse).status()).toBe(200);
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("tab", { name: translate(locale, "EBOM"), exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("heading", {
      name: translate(locale, "Immutable revisions"),
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: translate(locale, "Create EBOM"),
      exact: true,
    }),
  ).toBeEnabled();
  await expect(page.getByText("ENG-SYN-001").first()).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P5-04 live EBOM workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders exact immutable EBOM truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      const observed = await installEbomApi(page);
      await openEbom(page, locale);

      await expect(
        page.getByText(
          translate(
            locale,
            "This workspace does not create formal ERPNext Items, MBOMs, routings or production execution.",
          ),
        ),
      ).toBeVisible();
      await expect(
        page.getByRole("heading", {
          name: translate(locale, "Exact revision lines"),
        }),
      ).toBeVisible();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);

      const ebomRequests = observed.filter((request) =>
        request.path.includes("/eboms"),
      );
      expect(ebomRequests.length).toBeGreaterThanOrEqual(2);
      expect(
        ebomRequests.filter((request) =>
          request.path.endsWith(`/eboms/${ebomId}`),
        ),
      ).toHaveLength(1);
      expect(
        ebomRequests.every(
          (request) =>
            request.method === "GET" &&
            request.csrfToken === undefined &&
            request.idempotencyKey === undefined,
        ),
      ).toBe(true);
    });
  }

  test("compares only two explicit immutable revisions", async ({ page }) => {
    await installSession(page, "en");
    const observed = await installEbomApi(page);
    await openEbom(page, "en");

    await page.getByRole("button", { name: "Compare revisions" }).click();
    const comparisonPanel = page
      .getByRole("heading", { name: "Compare exact EBOM revisions" })
      .locator("xpath=ancestor::section[1]");
    await comparisonPanel
      .getByRole("button", { name: "Compare revisions" })
      .click();
    await expect(page.getByText("Differences found")).toBeVisible();
    await expect(page.getByText("ENG-SYN-001 · 1.000 EA")).toBeVisible();
    await expect(page.getByText("ENG-SYN-001 · 2.000 EA")).toBeVisible();

    const comparison = observed.find((request) =>
      request.path.endsWith("/compare"),
    );
    expect(comparison).toMatchObject({
      method: "GET",
      path: `/api/npi/v1/projects/${projectId}/eboms/${ebomId}/compare`,
    });
    expect(new URLSearchParams(comparison?.query).get("fromRevisionId")).toBe(
      ebomRevisionOneId,
    );
    expect(new URLSearchParams(comparison?.query).get("toRevisionId")).toBe(
      ebomRevisionTwoId,
    );
  });

  test("submits one exact revision with CSRF and actor-bound idempotency", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installEbomApi(page);
    await openEbom(page, "en");

    await page.getByRole("button", { name: "Submit for review" }).click();
    await page
      .getByRole("textbox", { name: "Reason" })
      .fill("Ready for exact review");
    const lifecyclePanel = page
      .getByRole("heading", { name: "EBOM lifecycle review" })
      .locator("xpath=ancestor::section[1]");
    await lifecyclePanel
      .getByRole("button", { name: "Submit for review" })
      .click();
    await expect(
      page.getByText("In review", { exact: true }).first(),
    ).toBeVisible();

    const command = observed.find((request) =>
      request.path.endsWith(":submit-review"),
    );
    expect(command).toMatchObject({
      csrfToken,
      method: "POST",
    });
    expect(command?.idempotencyKey).toMatch(/^ebom-submit-/u);
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p5-04-ebom-workspace-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p5-04-ebom-workspace-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p5-04-ebom-workspace-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P5-04 EBOM revision and comparison evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installEbomApi(page);
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
      await openEbom(page, visual.locale);
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
