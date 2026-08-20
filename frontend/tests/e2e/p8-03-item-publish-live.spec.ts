import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  EngineeringBomDetailViewModel,
  EngineeringBomListViewModel,
} from "../../src/api/ebom-data-source";
import type {
  ItemPublishRequestDetailViewModel,
  ItemPublishRequestListViewModel,
} from "../../src/api/item-publish-data-source";
import type {
  EngineeringBomPublishRequestListViewModel,
  EngineeringBomPublishRequestViewModel,
} from "../../src/api/publish-request-data-source";
import { translate } from "../../src/i18n/runtime";
import {
  ebomId,
  ebomRevisionOneId,
  engineeringBomDetailFixture,
  engineeringBomListFixture,
} from "../support/ebom-fixture";
import {
  itemPublishDetailFixture,
  itemPublishListFixture,
  itemPublishRequestId,
} from "../support/item-publish-fixture";
import {
  publishNodeId,
  publishRequestFixture,
  publishRequestId,
  publishRequestListFixture,
} from "../support/publish-request-fixture";
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
const csrfToken = "p8-03-item-publish-browser-csrf-token";
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
  return { ...fixture, project: { ...fixture.project, globalId: projectId } };
}

function detailFixture(): EngineeringBomDetailViewModel {
  const fixture = engineeringBomDetailFixture();
  return { ...fixture, project: { ...fixture.project, globalId: projectId } };
}

function phase5Request(): EngineeringBomPublishRequestViewModel {
  const fixture = publishRequestFixture();
  return {
    ...fixture,
    releasedEbom: { ...fixture.releasedEbom, projectGlobalId: projectId },
  };
}

function phase5List(
  request = phase5Request(),
): EngineeringBomPublishRequestListViewModel {
  const fixture = publishRequestListFixture(request);
  return { ...fixture, project: { ...fixture.project, globalId: projectId } };
}

function exactItemDetail(
  detail: ItemPublishRequestDetailViewModel,
): ItemPublishRequestDetailViewModel {
  return {
    ...detail,
    request: {
      ...detail.request,
      source: { ...detail.request.source, projectGlobalId: projectId },
    },
  };
}

function exactItemList(
  detail: ItemPublishRequestDetailViewModel | null,
  options: Parameters<typeof itemPublishListFixture>[1] = {},
): ItemPublishRequestListViewModel {
  const exactDetail = detail ? exactItemDetail(detail) : null;
  const fixture = itemPublishListFixture(exactDetail, options);
  return { ...fixture, projectGlobalId: projectId };
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
      "X-Trace-ID": "trace-p8-03-item-publish-browser",
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
  options: {
    detail?: ItemPublishRequestDetailViewModel | null;
    list?: ItemPublishRequestListViewModel;
    commandResponse?: ItemPublishRequestDetailViewModel;
  } = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const engineeringList = listFixture();
  const engineeringDetail = detailFixture();
  const publishRequest = phase5Request();
  const publishList = phase5List(publishRequest);
  const itemDetail =
    options.detail === undefined
      ? exactItemDetail(itemPublishDetailFixture())
      : options.detail
        ? exactItemDetail(options.detail)
        : null;
  const itemList =
    options.list ?? exactItemList(itemDetail, { profileMode: "synthetic" });
  const defaultCommandResponse = itemPublishDetailFixture({
    state: "queued",
    targetMode: "synthetic",
  });
  const commandResponse = exactItemDetail(
    options.commandResponse ?? {
      ...defaultCommandResponse,
      request: {
        ...defaultCommandResponse.request,
        mappingExpectation:
          itemList.mappingExpectation ??
          defaultCommandResponse.request.mappingExpectation,
      },
    },
  );

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
      await fulfillJson(route, engineeringList);
      return;
    }
    if (url.pathname.endsWith(`/eboms/${ebomId}`)) {
      await fulfillJson(route, engineeringDetail);
      return;
    }
    const publishBase = `/eboms/${ebomId}/revisions/${ebomRevisionOneId}/publish-requests`;
    if (url.pathname.endsWith(`${publishBase}/${publishRequestId}`)) {
      await fulfillJson(route, publishRequest);
      return;
    }
    if (url.pathname.endsWith(publishBase) && request.method() === "GET") {
      await fulfillJson(route, publishList);
      return;
    }
    const itemBase = `/projects/${projectId}/item-publish-requests`;
    if (url.pathname.endsWith(itemBase) && request.method() === "GET") {
      expect(url.searchParams.get("publishRequestGlobalId")).toBe(
        publishRequestId,
      );
      expect(url.searchParams.get("selectedPublishNodeGlobalId")).toBe(
        publishNodeId,
      );
      await fulfillJson(route, itemList);
      return;
    }
    if (
      url.pathname.endsWith(`${itemBase}/${itemPublishRequestId}`) &&
      request.method() === "GET" &&
      itemDetail
    ) {
      await fulfillJson(route, itemDetail);
      return;
    }
    if (url.pathname.endsWith(itemBase) && request.method() === "POST") {
      expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(headers["idempotency-key"]).toMatch(/^item-publish-/u);
      expect(request.postDataJSON()).toEqual({
        acknowledgement:
          "I confirm this request uses the exact released Item source and current execution profile.",
        expectedMappingVersion: 3,
        publishRequestGlobalId: publishRequestId,
        selectedPublishNodeGlobalId: publishNodeId,
      });
      await fulfillJson(route, commandResponse, 201);
      return;
    }
    throw new Error(
      `Unhandled P8-03 browser request: ${request.method()} ${url.pathname}${url.search}`,
    );
  });
  return observed;
}

async function openItemInspector(
  page: Page,
  locale: TestLocale,
  options: { expectAttemptHistory?: boolean } = {},
): Promise<void> {
  await page.goto(`/projects/${projectId}?lang=${locale}&tab=ebom`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await page.getByRole("button", { name: "R1", exact: true }).click();
  await page.locator('[data-item-inspector-trigger="true"]').first().click();
  const inspector = page.getByRole("region", {
    name: translate(locale, "Item execution inspector"),
  });
  await expect(inspector).toBeVisible();
  await inspector.getByRole("button", { name: "ENG-SYN-001" }).click();
  await expect(
    inspector.getByText(
      translate(locale, "Exact source and execution expectation"),
    ),
  ).toBeVisible();
  await expect(inspector.locator(".item-publish__status-strip")).toBeVisible();
  if (options.expectAttemptHistory ?? true) {
    await expect(inspector.locator(".item-publish__attempts")).toBeVisible();
  }
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P8-03 live Item execution inspector", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders non-authoritative synthetic truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      const observed = await installApi(page);
      await openItemInspector(page, locale);

      await expect(
        page.getByText(
          translate(locale, "Synthetic verification; not authoritative"),
        ),
      ).toBeVisible();
      await expect(
        page.getByText(translate(locale, "No authoritative mapping")),
      ).toBeVisible();
      await expect(page.getByText("ITEM-SANDBOX-0001")).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: /retry|reconcile/iu }),
      ).toHaveCount(0);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectSinglePrimaryAction(page);
      await expectAxeClean(page);

      const itemReads = observed.filter((item) =>
        item.path.includes("/item-publish-requests"),
      );
      expect(itemReads).toHaveLength(2);
      expect(itemReads.every((item) => item.method === "GET")).toBe(true);
      expect(itemReads.every((item) => item.csrfToken === undefined)).toBe(
        true,
      );
    });
  }

  test("creates one exact local request without browser-owned target fields", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page, {
      detail: null,
      list: exactItemList(null, {
        mappingExpectation: {
          mappingVersion: 3,
          formalItemCode: "ITEM-SANDBOX-0001",
          targetVersion: "7",
          observationHash: "c".repeat(64),
        },
        profileMode: "synthetic",
      }),
    });
    await openItemInspector(page, "en", { expectAttemptHistory: false });

    await page
      .getByRole("checkbox", {
        name: "I confirm this request uses the exact released Item source and current execution profile.",
      })
      .check();
    await page.getByRole("button", { name: "Request Item execution" }).click();
    await expect(
      page.getByText(
        "The immutable request was committed locally. This is not target success.",
      ),
    ).toBeVisible();
    await expect(
      page
        .getByRole("region", { name: "Item execution inspector" })
        .locator(".item-publish__attempts"),
    ).toBeVisible();

    const command = observed.find(
      (item) =>
        item.method === "POST" && item.path.endsWith("/item-publish-requests"),
    );
    expect(command?.csrfToken).toBe(csrfToken);
    expect(command?.idempotencyKey).toMatch(/^item-publish-/u);
    expect(command?.payload).not.toHaveProperty("actorUserId");
    expect(command?.payload).not.toHaveProperty("targetMode");
    expect(command?.payload).not.toHaveProperty("formalItemCode");
    expect(command?.payload).not.toHaveProperty("targetVersion");
    expect(command?.payload).not.toHaveProperty("operation");
  });

  test("blocks uncertain execution and shows an authoritative mapping only when supplied", async ({
    page,
  }) => {
    const uncertain = itemPublishDetailFixture({
      state: "uncertain_after_timeout",
      targetMode: "sandbox",
    });
    await installSession(page, "en");
    await installApi(page, { detail: uncertain });
    await openItemInspector(page, "en");
    await expect(
      page.getByText("Uncertain after timeout; reconciliation required"),
    ).toBeVisible();
    await expect(
      page.getByText(
        "The outcome is uncertain. Reconciliation is required before any new request.",
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Request Item execution" }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: /retry|reconcile/iu }),
    ).toHaveCount(0);
  });

  test("keeps mapping conflict request and result states distinct", async ({
    page,
  }) => {
    const conflict = itemPublishDetailFixture({ state: "mapping_conflict" });
    expect(conflict.request.state).toBe("mapping_conflict");
    expect(conflict.result?.state).toBe("succeeded");
    expect(conflict.result?.authority).toBe("authoritative_sandbox");
    expect(conflict.result?.responseAuthenticated).toBe(true);
    await installSession(page, "en");
    await installApi(page, { detail: conflict });
    await openItemInspector(page, "en");
    await expect(
      page.getByText("Mapping conflict; no mapping changed"),
    ).toBeVisible();
    await expect(
      page
        .locator(".item-publish__evidence")
        .filter({ hasText: "Profile and mapping authority" })
        .locator("dl > div")
        .filter({ hasText: "Mapping version" })
        .locator("dd"),
    ).toHaveText("1");
    await expect(page.getByText("ITEM-SANDBOX-0001")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Request Item execution" }),
    ).toBeDisabled();
  });
});

const visualCases = [
  {
    detail: itemPublishDetailFixture(),
    height: 768,
    locale: "en",
    name: "p8-03-item-synthetic-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    detail: itemPublishDetailFixture({
      state: "uncertain_after_timeout",
      targetMode: "sandbox",
    }),
    height: 900,
    locale: "zh",
    name: "p8-03-item-uncertain-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    detail: itemPublishDetailFixture({
      authoritativeMapping: true,
      state: "succeeded",
      targetMode: "sandbox",
    }),
    height: 1080,
    locale: "zh-TW",
    name: "p8-03-item-authoritative-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P8-03 Item execution truth", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installApi(page, { detail: visual.detail });
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
      await openItemInspector(page, visual.locale);
      const heading = page.getByRole("heading", {
        name: translate(visual.locale, "Item execution inspector"),
      });
      await heading.scrollIntoViewIfNeeded();
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectSinglePrimaryAction(page);
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
