import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  EngineeringBomDetailViewModel,
  EngineeringBomListViewModel,
} from "../../src/api/ebom-data-source";
import type {
  EngineeringBomPublishRequestListViewModel,
  EngineeringBomPublishRequestViewModel,
} from "../../src/api/publish-request-data-source";
import {
  isMbomRequestList,
  type MbomRequestListViewModel,
} from "../../src/api/mbom-publish-data-source";
import { translate } from "../translate";
import {
  ebomId,
  ebomRevisionOneId,
  engineeringBomDetailFixture,
  engineeringBomListFixture,
} from "../support/ebom-fixture";
import {
  publishRequestFixture,
  publishRequestId,
  publishRequestListFixture,
} from "../support/publish-request-fixture";
import { mbomPublishListFixture } from "../support/mbom-publish-fixture";
import { projectWorkCockpitFixture } from "../support/project-work-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  expectSinglePrimaryAction,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const csrfToken = "p5-05-publish-browser-csrf-token-exact";
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
}

function listFixture(): EngineeringBomListViewModel {
  const fixture = engineeringBomListFixture();
  return { ...fixture, project: { ...fixture.project, globalId: projectId } };
}

function detailFixture(): EngineeringBomDetailViewModel {
  const fixture = engineeringBomDetailFixture();
  return { ...fixture, project: { ...fixture.project, globalId: projectId } };
}

function requestFixture(
  request = publishRequestFixture(),
): EngineeringBomPublishRequestViewModel {
  return {
    ...request,
    releasedEbom: { ...request.releasedEbom, projectGlobalId: projectId },
  };
}

function publishListFixture(
  request = requestFixture(),
): EngineeringBomPublishRequestListViewModel {
  const fixture = publishRequestListFixture(request);
  return { ...fixture, project: { ...fixture.project, globalId: projectId } };
}

function disabledMbomListFixture(): MbomRequestListViewModel {
  const fixture = mbomPublishListFixture(null, {
    profileUnavailable: true,
    canView: true,
    canExecute: false,
  });
  const exactFixture = {
    ...fixture,
    projectGlobalId: projectId,
    phase5PublishRequestGlobalId: publishRequestId,
  };
  expect(isMbomRequestList(exactFixture)).toBe(true);
  expect(exactFixture.executionProfile).toBeNull();
  expect(exactFixture.createContext).toBeNull();
  expect(exactFixture.items).toEqual([]);
  expect(JSON.stringify(exactFixture)).not.toContain("formalBomId");
  return exactFixture;
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
      "X-Trace-ID": "trace-p5-05-publish-browser",
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
        version: "8".repeat(64),
      },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "publisher@example.invalid",
    });
  });
}

async function installApi(
  page: Page,
  request = requestFixture(),
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const list = listFixture();
  const detail = detailFixture();
  const publishList = publishListFixture(request);
  const mbomList = disabledMbomListFixture();
  await page.route(projectApiEndpoint, async (route) => {
    const apiRequest = route.request();
    const url = new URL(apiRequest.url());
    const headers = apiRequest.headers();
    observed.push({
      csrfToken: headers["x-frappe-csrf-token"],
      idempotencyKey: headers["idempotency-key"],
      method: apiRequest.method(),
      path: url.pathname,
      payload:
        apiRequest.method() === "POST" ? apiRequest.postDataJSON() : null,
    });
    if (url.pathname.endsWith("/cockpit")) {
      await fulfillJson(route, projectWorkCockpitFixture());
      return;
    }
    if (url.pathname.endsWith("/eboms") && apiRequest.method() === "GET") {
      await fulfillJson(route, list);
      return;
    }
    if (url.pathname.endsWith(`/eboms/${ebomId}`)) {
      await fulfillJson(route, detail);
      return;
    }
    const publishBase = `/eboms/${ebomId}/revisions/${ebomRevisionOneId}/publish-requests`;
    if (url.pathname.endsWith(`${publishBase}/${publishRequestId}`)) {
      await fulfillJson(route, request);
      return;
    }
    if (url.pathname.endsWith(publishBase) && apiRequest.method() === "GET") {
      await fulfillJson(route, publishList);
      return;
    }
    if (url.pathname.endsWith(publishBase) && apiRequest.method() === "POST") {
      expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(headers["idempotency-key"]).toMatch(/^ebom-publish-/u);
      expect(apiRequest.postDataJSON()).toEqual({
        expectedEbomVersion: 2,
        expectedRevisionSnapshotHash: "b".repeat(64),
        expectedLifecycleVersion: 4,
        publishPolicyGlobalId: "75000000-0000-4000-8000-000000000020",
        publishPolicyVersion: 1,
        publishPolicySnapshotHash: "d".repeat(64),
        targetMode: "mock",
        confirmed: true,
        confirmationIntent:
          "validate_exact_released_ebom_for_item_mbom_publish",
        reason: "Validate exact released structure",
      });
      await fulfillJson(route, request, 201);
      return;
    }
    const mbomBase = `/api/npi/v1/projects/${projectId}/mbom-publish-requests`;
    if (url.pathname === mbomBase) {
      expect(apiRequest.method()).toBe("GET");
      expect([...url.searchParams.entries()]).toEqual([
        ["phase5PublishRequestGlobalId", publishRequestId],
      ]);
      await fulfillJson(route, mbomList);
      return;
    }
    throw new Error(
      `Unhandled P5-05 browser request: ${apiRequest.method()} ${url.pathname}`,
    );
  });
  return observed;
}

async function openPublishWorkspace(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await page.goto(`/projects/${projectId}?lang=${locale}&tab=ebom`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: translate(locale, "Immutable revisions"),
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "R1", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: translate(locale, "Formal publish requests"),
    }),
  ).toBeVisible();
  await expect(
    page.getByText(translate(locale, "Mock validation only")),
  ).toBeVisible();
  await expect(page.getByText("ENG-SYN-001").last()).toBeVisible();
  const mbomInspector = page.getByRole("region", {
    name: translate(locale, "MBOM execution inspector"),
  });
  await expect(
    mbomInspector.getByText(
      translate(
        locale,
        "You can inspect MBOM execution but cannot request it.",
      ),
    ),
  ).toBeVisible();
  await expect(
    mbomInspector.getByRole("button", {
      name: translate(locale, "Review MBOM request"),
    }),
  ).toBeDisabled();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P5-05 live EBOM publish-request workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders exact Mock and node truth in ${locale}`, async ({ page }) => {
      await installSession(page, locale);
      const observed = await installApi(page);
      await openPublishWorkspace(page, locale);

      await expect(
        page.getByText(translate(locale, "Validated in Mock")).first(),
      ).toBeVisible();
      await expect(
        page.getByText(translate(locale, "Not assigned")).first(),
      ).toBeVisible();
      await expect(
        page.getByText(
          translate(locale, "Create Item intent") +
            "; " +
            translate(locale, "Create or update MBOM intent"),
        ),
      ).toBeVisible();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectSinglePrimaryAction(page);
      await expectAxeClean(page);

      const publishReads = observed.filter((item) =>
        item.path.includes("/publish-requests"),
      );
      expect(publishReads).toHaveLength(2);
      expect(publishReads.every((item) => item.method === "GET")).toBe(true);
      expect(publishReads.every((item) => item.csrfToken === undefined)).toBe(
        true,
      );
    });
  }

  test("creates one confirmed Mock request without browser-owned ERP fields", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page);
    await openPublishWorkspace(page, "en");

    await page.getByRole("button", { name: "Prepare publish request" }).click();
    await page
      .getByRole("textbox", { name: "Reason" })
      .fill("Validate exact released structure");
    await page
      .getByRole("checkbox", {
        name: "I confirm validation of this exact released EBOM in Mock mode. No Item or MBOM will be created in ERPNext.",
      })
      .check();
    await page
      .getByRole("button", { name: "Validate exact released EBOM" })
      .click();
    await expect(
      page.getByText(
        "The immutable request was recorded locally. ERPNext was not contacted.",
      ),
    ).toBeVisible();

    const command = observed.find(
      (item) =>
        item.method === "POST" && item.path.endsWith("/publish-requests"),
    );
    expect(command?.csrfToken).toBe(csrfToken);
    expect(command?.idempotencyKey).toMatch(/^ebom-publish-/u);
    expect(command?.payload).not.toHaveProperty("actorUserId");
    expect(command?.payload).not.toHaveProperty("formalItemCode");
    expect(command?.payload).not.toHaveProperty("formalMbomId");
    expect(command?.payload).not.toHaveProperty("operation");
  });

  test("renders target-unavailable manual intervention without a Phase 5 retry action", async ({
    page,
  }) => {
    const request = requestFixture(
      publishRequestFixture({
        requestState: "manual_intervention",
        nodeState: "target_unavailable",
      }),
    );
    await installSession(page, "en");
    await installApi(page, request);
    await openPublishWorkspace(page, "en");

    await expect(page.getByText("Manual intervention").first()).toBeVisible();
    await expect(page.getByText("Target unavailable").first()).toBeVisible();
    await expect(page.getByText("Reconcile before retry")).toBeVisible();
    await expect(page.getByText("Reconciliation required")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Retry failed nodes only" }),
    ).toHaveCount(0);
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p5-05-publish-request-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p5-05-publish-request-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p5-05-publish-request-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P5-05 publish-request evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installApi(page);
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
      await openPublishWorkspace(page, visual.locale);
      const heading = page.getByRole("heading", {
        name: translate(visual.locale, "Formal publish requests"),
      });
      await heading.scrollIntoViewIfNeeded();
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await heading.evaluate((element) => {
        element.scrollIntoView({ block: "start", inline: "nearest" });
      });
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
