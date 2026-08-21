import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  EngineeringBomDetailViewModel,
  EngineeringBomListViewModel,
} from "../../src/api/ebom-data-source";
import type {
  MbomRequestDetailViewModel,
  MbomRequestListViewModel,
} from "../../src/api/mbom-publish-data-source";
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
  mbomPublishDetailFixture,
  mbomPublishListFixture,
  mbomRequestId,
} from "../support/mbom-publish-fixture";
import {
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
const csrfToken = "p8-04-mbom-publish-browser-csrf-token";
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
  const value = engineeringBomListFixture();
  return { ...value, project: { ...value.project, globalId: projectId } };
}
function detailFixture(): EngineeringBomDetailViewModel {
  const value = engineeringBomDetailFixture();
  return { ...value, project: { ...value.project, globalId: projectId } };
}
function phase5Request(): EngineeringBomPublishRequestViewModel {
  const value = publishRequestFixture();
  return {
    ...value,
    releasedEbom: { ...value.releasedEbom, projectGlobalId: projectId },
  };
}
function phase5List(
  request = phase5Request(),
): EngineeringBomPublishRequestListViewModel {
  const value = publishRequestListFixture(request);
  return { ...value, project: { ...value.project, globalId: projectId } };
}
function exactMbomDetail(
  value: MbomRequestDetailViewModel,
): MbomRequestDetailViewModel {
  return {
    ...value,
    request: {
      ...value.request,
      source: { ...value.request.source, projectGlobalId: projectId },
    },
  };
}
function exactMbomList(
  detail: MbomRequestDetailViewModel | null,
  empty = false,
): MbomRequestListViewModel {
  const exact = detail ? exactMbomDetail(detail) : null;
  const value = mbomPublishListFixture(exact);
  return {
    ...value,
    projectGlobalId: projectId,
    createContext: value.createContext
      ? {
          ...value.createContext,
          source: { ...value.createContext.source, projectGlobalId: projectId },
        }
      : null,
    items: empty ? [] : value.items,
  };
}

function requestIdentity(route: Route): string {
  const value = route.request().headers()["x-request-id"] ?? "";
  expect(value).toMatch(requestIdPattern);
  return value;
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
      "X-Trace-ID": "trace-p8-04-mbom-browser",
    },
    status,
  });
}
async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, (route) =>
    fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "8".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "publisher@example.invalid",
    }),
  );
}

async function installApi(
  page: Page,
  options: {
    detail?: MbomRequestDetailViewModel;
    empty?: boolean;
    list?: MbomRequestListViewModel;
    commandFailure?: number;
  } = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const detail = exactMbomDetail(options.detail ?? mbomPublishDetailFixture());
  const list = options.list ?? exactMbomList(detail, options.empty);
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
    if (url.pathname.endsWith("/cockpit"))
      return fulfillJson(route, projectWorkCockpitFixture());
    if (url.pathname.endsWith("/eboms") && request.method() === "GET")
      return fulfillJson(route, listFixture());
    if (url.pathname.endsWith(`/eboms/${ebomId}`))
      return fulfillJson(route, detailFixture());
    const phase5Base = `/eboms/${ebomId}/revisions/${ebomRevisionOneId}/publish-requests`;
    if (url.pathname.endsWith(`${phase5Base}/${publishRequestId}`))
      return fulfillJson(route, phase5Request());
    if (url.pathname.endsWith(phase5Base) && request.method() === "GET")
      return fulfillJson(route, phase5List());
    const mbomBase = `/projects/${projectId}/mbom-publish-requests`;
    if (url.pathname.endsWith(mbomBase) && request.method() === "GET") {
      expect(url.searchParams.get("phase5PublishRequestGlobalId")).toBe(
        publishRequestId,
      );
      return fulfillJson(route, list);
    }
    if (
      url.pathname.endsWith(`${mbomBase}/${mbomRequestId}`) &&
      request.method() === "GET"
    )
      return fulfillJson(route, detail);
    if (url.pathname.endsWith(mbomBase) && request.method() === "POST") {
      expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(headers["idempotency-key"]).toMatch(/^mbom-publish-/u);
      const context = list.createContext;
      if (!context)
        throw new Error("The command fixture requires a create context.");
      expect(request.postDataJSON()).toEqual({
        acknowledgement:
          "I confirm this request uses the exact released EBOM topology, current Item readiness, MBOM expectations, and execution profile.",
        expectedItemMappingSetHash: context.itemMappingSetHash,
        expectedMbomMappingSetHash: context.mbomMappingSetHash,
        expectedSourceHash: context.source.sourceHash,
        expectedTopologyHash: context.source.topologyHash,
        phase5PublishRequestGlobalId: publishRequestId,
      });
      if (options.commandFailure)
        return fulfillJson(
          route,
          {
            type: "https://example.invalid/problems/mbom-command",
            title: "MBOM command failed",
            status: options.commandFailure,
            code: "MBOM_PUBLISH_COMMAND_FAILED",
            traceId: "trace-mbom-command-failed",
            retryable: false,
          },
          options.commandFailure,
        );
      const summary = exactMbomList(detail).items[0];
      if (!summary) throw new Error("The command summary is unavailable.");
      return fulfillJson(route, summary, 201);
    }
    throw new Error(
      `Unhandled P8-04 browser request: ${request.method()} ${url.pathname}${url.search}`,
    );
  });
  return observed;
}

async function openMbomInspector(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await page.goto(`/projects/${projectId}?lang=${locale}&tab=ebom`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await page.getByRole("button", { name: "R1", exact: true }).click();
  await expect(
    page.getByRole("region", {
      name: translate(locale, "MBOM execution inspector"),
    }),
  ).toBeVisible();
}
async function expectAxeClean(page: Page): Promise<void> {
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
}

test.describe("P8-04 live MBOM execution inspector", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders synthetic non-authoritative truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      const observed = await installApi(page);
      await openMbomInspector(page, locale);
      const inspector = page.getByRole("region", {
        name: translate(locale, "MBOM execution inspector"),
      });
      await expect(
        inspector.getByText(
          translate(locale, "Synthetic MBOM verification; not authoritative"),
        ),
      ).toBeVisible();
      await expect(
        inspector.getByText(
          translate(locale, "Synthetic evidence; no formal identity"),
        ),
      ).toHaveCount(2);
      await expect(page.getByText("BOM-SANDBOX-0001")).toHaveCount(0);
      await expect(
        inspector.getByRole("button", { name: /retry|reconcile|submit/iu }),
      ).toHaveCount(0);
      expect(
        observed
          .filter((item) => item.path.includes("/mbom-publish-requests"))
          .every(
            (item) =>
              !item.path.includes("erpnext") && !item.path.includes("target"),
          ),
      ).toBe(true);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectSinglePrimaryAction(page);
      await expectAxeClean(page);
    });
  }

  test("shows partial, failed, uncertain, conflict and authoritative truth without fake aggregate success", async ({
    page,
  }) => {
    for (const [state, label] of [
      ["partially_succeeded", "Partial MBOM result; inspect every assembly"],
      ["failed_final", "Final MBOM failure; no success recorded"],
      [
        "uncertain_after_timeout",
        "Uncertain MBOM outcome; reconciliation required",
      ],
      ["mapping_conflict", "MBOM mapping conflict; no mapping changed"],
      ["succeeded", "Authoritative Sandbox MBOM result observed"],
    ] as const) {
      await installSession(page, "en");
      await installApi(page, { detail: mbomPublishDetailFixture({ state }) });
      await openMbomInspector(page, "en");
      await expect(page.getByText(label)).toBeVisible();
      if (state === "succeeded" || state === "partially_succeeded")
        await expect(page.getByText("BOM-SANDBOX-0001")).toBeVisible();
      else await expect(page.getByText("BOM-SANDBOX-0001")).toHaveCount(0);
      await page.unrouteAll({ behavior: "wait" });
    }
  });

  test("creates one exact local request through keyboard-accessible Impact Review", async ({
    page,
  }) => {
    await installSession(page, "en");
    const detail = mbomPublishDetailFixture({
      state: "queued",
      targetMode: "synthetic",
    });
    const observed = await installApi(page, { detail, empty: true });
    await openMbomInspector(page, "en");
    const action = page.getByRole("button", { name: "Review MBOM request" });
    await action.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", {
      name: "Review exact MBOM request",
    });
    await expect(dialog).toBeVisible();
    await expect(
      dialog.getByText(
        "I confirm this request uses the exact released EBOM topology, current Item readiness, MBOM expectations, and execution profile.",
      ),
    ).toBeVisible();
    await dialog
      .getByRole("button", { name: "Request MBOM execution" })
      .click();
    await expect(
      page.getByText(
        "The immutable MBOM request was committed. Target completion is not claimed.",
      ),
    ).toBeVisible();
    const commands = observed.filter(
      (item) =>
        item.method === "POST" && item.path.endsWith("/mbom-publish-requests"),
    );
    expect(commands).toHaveLength(1);
    expect(commands[0]?.csrfToken).toBe(csrfToken);
    expect(commands[0]?.idempotencyKey).toMatch(/^mbom-publish-/u);
    expect(Object.keys(commands[0]?.payload as object)).not.toContain("target");
  });

  test("keeps submitted MBOM expectations read-only", async ({ page }) => {
    await installSession(page, "en");
    await installApi(page, {
      detail: mbomPublishDetailFixture({
        state: "queued",
        targetMode: "sandbox",
        submittedExpectation: true,
      }),
      empty: true,
    });
    await openMbomInspector(page, "en");
    await expect(
      page.getByText(
        "A submitted MBOM is immutable and cannot be overwritten.",
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Review MBOM request" }),
    ).toBeDisabled();
  });
});

const visualCases = [
  {
    detail: mbomPublishDetailFixture(),
    height: 768,
    locale: "en",
    name: "p8-04-mbom-synthetic-en-1366x768-125",
    width: 1366,
    zoom: 1.25,
  },
  {
    detail: mbomPublishDetailFixture({
      state: "partially_succeeded",
      targetMode: "sandbox",
    }),
    height: 1080,
    locale: "zh",
    name: "p8-04-mbom-partial-zh-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
  {
    detail: mbomPublishDetailFixture({
      state: "succeeded",
      targetMode: "sandbox",
    }),
    height: 1080,
    locale: "zh-TW",
    name: "p8-04-mbom-authoritative-zh-TW-1920x1080-125",
    width: 1920,
    zoom: 1.25,
  },
] as const;

test.describe("@visual P8-04 MBOM execution truth", () => {
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
      await openMbomInspector(page, visual.locale);
      const visualAnchor =
        visual.detail.request.state === "synthetic_verified"
          ? page.getByRole("heading", {
              name: translate(visual.locale, "MBOM execution inspector"),
            })
          : page.getByLabel(
              translate(visual.locale, "MBOM assembly execution truth"),
            );
      await visualAnchor.evaluate((element) => {
        element.scrollIntoView({ block: "start" });
      });
      if (visual.detail.request.state === "partially_succeeded") {
        const nodeTruth = page.getByLabel(
          translate(visual.locale, "MBOM assembly execution truth"),
        );
        await nodeTruth.evaluate((element) => {
          element.scrollLeft = element.scrollWidth;
        });
        await expect(
          nodeTruth.getByText(translate(visual.locale, "Retryable failure"), {
            exact: true,
          }),
        ).toBeVisible();
        const action = page.locator('[data-mbom-request-action="true"]');
        await expect(action).toHaveText(
          translate(visual.locale, "Review MBOM request"),
        );
        expect(
          await action.evaluate((element) => {
            const actionBox = element.getBoundingClientRect();
            const containerBox = element.parentElement?.getBoundingClientRect();
            const copyBox =
              element.previousElementSibling?.getBoundingClientRect();
            return Boolean(
              containerBox &&
              copyBox &&
              actionBox.top >= copyBox.bottom &&
              actionBox.right <= containerBox.right &&
              element.scrollWidth <= element.clientWidth,
            );
          }),
        ).toBe(true);
      }
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
      await visualAnchor.evaluate((element) => {
        element.scrollIntoView({ block: "start", inline: "nearest" });
      });
      if (visual.detail.request.state === "partially_succeeded") {
        await page
          .getByLabel(translate(visual.locale, "MBOM assembly execution truth"))
          .evaluate((element) => {
            element.scrollLeft = element.scrollWidth;
          });
      }
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
