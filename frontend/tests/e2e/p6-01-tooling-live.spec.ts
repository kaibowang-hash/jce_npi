import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ToolingCockpitViewModel } from "../../src/api/tooling-data-source";
import {
  toolingListPage,
  toolingListPreference,
} from "../support/tooling-list-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const partId = "33333333-3333-4333-8333-333333333333";
const revisionId = "44444444-4444-4444-8444-444444444444";
const csrfToken = "p6-01-tooling-browser-csrf-token";
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const toolingEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/(?:tooling(?:\/[^/?]+)?|parts(?:\/[^/?]+\/revisions)?|tooling-requirements|tooling-masters|tooling-applicabilities)$/u;
const toolingSetEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/tooling\/[^/?]+\/sets$/u;
const toolingListEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/tooling-list(?:\/preferences\/[^/?]+)?(?:\?.*)?$/u;

type FixtureState = "normal" | "empty" | "read_only";

interface ObservedRequest {
  csrfToken: string | undefined;
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
}

function cockpit(state: FixtureState = "normal"): ToolingCockpitViewModel {
  const source = {
    editableIn: "NPI_ONE" as const,
    sourceSystem: "NPI_ONE" as const,
    syncState: "local" as const,
  };
  const empty = state === "empty";
  return {
    applicability: empty
      ? []
      : [
          {
            effectiveFrom: "2026-08-07",
            effectiveTo: null,
            globalId: "66666666-6666-4666-8666-666666666666",
            model: {
              sourceObjectId: "MODEL-SYN-01",
              sourceSystem: "NPI_ONE",
            },
            part: {
              globalId: revisionId,
              partGlobalId: partId,
              revisionLabel: "A",
              revisionNumber: 1,
              snapshotHash: "c".repeat(64),
            },
            predecessorGlobalId: null,
            product: {
              sourceObjectId: "PRODUCT-SYN-01",
              sourceSystem: "NPI_ONE",
            },
            projectGlobalId: projectId,
            relationshipGlobalId: "77777777-7777-4777-8777-777777777777",
            relationshipKeyHash: "d".repeat(64),
            snapshotHash: "e".repeat(64),
            toolingMasterGlobalId: masterId,
            version: 1,
          },
        ],
    downstream: {
      erp: { reasonCode: "erp_projection_unavailable", state: "unavailable" },
      lifecycle: {
        reasonCode: "lifecycle_policy_unavailable",
        state: "unavailable",
      },
      physicalSet: {
        reasonCode: "physical_set_not_delivered",
        state: "unavailable",
      },
      revision: {
        reasonCode: "tooling_revision_not_delivered",
        state: "unavailable",
      },
      trial: { reasonCode: "trial_not_delivered", state: "unavailable" },
    },
    masters: empty
      ? []
      : [
          {
            globalId: masterId,
            originatingProjectGlobalId: projectId,
            snapshotHash: "b".repeat(64),
            source,
            title: "Synthetic logical injection tool",
          },
        ],
    parts: empty
      ? []
      : [
          {
            currentRevision: {
              globalId: revisionId,
              partGlobalId: partId,
              revisionLabel: "A",
              revisionNumber: 1,
              snapshotHash: "c".repeat(64),
            },
            globalId: partId,
            source,
            title: "Synthetic valve cover",
            version: 1,
          },
        ],
    permissions: {
      createApplicability: state !== "read_only",
      createMaster: state !== "read_only",
      createPart: state !== "read_only",
      createRequirement: state !== "read_only",
      transitionLifecycle: false,
      view: true,
    },
    project: {
      businessCode: "SYN-PROJECT-001",
      globalId: projectId,
      title: "Synthetic Tooling Project",
    },
    requirements: empty
      ? []
      : [
          {
            globalId: "55555555-5555-4555-8555-555555555555",
            kind: "new_tool",
            projectGlobalId: projectId,
            reason: "A dedicated injection tool is required.",
            snapshotHash: "f".repeat(64),
            targetDate: "2026-09-30",
            targetPartRevisionGlobalId: revisionId,
            title: "Production injection tool requirement",
          },
        ],
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
      "X-Trace-ID": "trace-p6-01-tooling-browser",
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
  fieldErrors?: readonly { path: string; message: string }[],
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify({
      code,
      ...(fieldErrors ? { fieldErrors } : {}),
      retryable,
      status,
      title,
      traceId: "trace-p6-01-tooling-browser",
      type: `urn:npi:error:${code.toLowerCase()}`,
    }),
    headers: {
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p6-01-tooling-browser",
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "a".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "tooling.engineer@example.invalid",
    });
  });
}

async function installToolingApi(
  page: Page,
  options: {
    state?: FixtureState;
    initialProblem?: {
      code: string;
      retryable: boolean;
      status: number;
      title: string;
    };
    commandProblem?: {
      code: string;
      retryable: boolean;
      status: number;
      title: string;
      fieldErrors?: readonly { path: string; message: string }[];
    };
    delayCommand?: boolean;
  } = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(toolingSetEndpoint, async (route) => {
    await fulfillJson(route, {
      items: [],
      permissions: {
        attachEvidence: options.state !== "read_only",
        createIntake: options.state !== "read_only",
        createSet: options.state !== "read_only",
        transitionLifecycle: false,
        view: true,
      },
      toolingMasterGlobalId: masterId,
    });
  });
  await page.route(toolingListEndpoint, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes("/preferences/")) {
      await fulfillJson(route, toolingListPreference());
      return;
    }
    await fulfillJson(
      route,
      toolingListPage(
        options.state === "empty"
          ? { items: [], totalCount: 0 }
          : options.state === "read_only"
            ? {
                permissions: {
                  canExport: false,
                  exportUnavailableReason: "separate_export_authority_required",
                  view: true,
                },
              }
            : {},
      ),
    );
  });
  await page.route(toolingEndpoint, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    observed.push({
      csrfToken: request.headers()["x-frappe-csrf-token"],
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path: url.pathname,
      payload: request.method() === "POST" ? request.postDataJSON() : null,
    });
    if (request.method() === "GET") {
      if (options.initialProblem) {
        await fulfillProblem(
          route,
          options.initialProblem.code,
          options.initialProblem.status,
          options.initialProblem.retryable,
          options.initialProblem.title,
        );
        return;
      }
      await fulfillJson(route, cockpit(options.state));
      return;
    }
    expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
    expect(request.headers()["idempotency-key"]).toMatch(/^tooling-/u);
    if (options.delayCommand) {
      await new Promise<void>((resolve) => {
        globalThis.setTimeout(resolve, 300);
      });
    }
    if (options.commandProblem) {
      await fulfillProblem(
        route,
        options.commandProblem.code,
        options.commandProblem.status,
        options.commandProblem.retryable,
        options.commandProblem.title,
        options.commandProblem.fieldErrors,
      );
      return;
    }
    await fulfillJson(route, cockpit(options.state), 201);
  });
  return observed;
}

async function openTooling(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/projects/${projectId}/tooling?lang=${locale}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: /SYN-PROJECT-001/u,
    }),
  ).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P6-01 live Tooling cockpit", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders distinct live identity and unavailable truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      const observed = await installToolingApi(page);
      await openTooling(page, locale);

      await expect(
        page.getByText("Synthetic logical injection tool").first(),
      ).toBeVisible();
      await expect(
        page.getByText("Synthetic valve cover").first(),
      ).toBeVisible();
      await expect(
        page.getByText("PRODUCT-SYN-01 · MODEL-SYN-01"),
      ).toBeVisible();
      await expect(
        page.locator(".tooling-live__downstream .semantic-status"),
      ).toHaveCount(4);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      const collectionRequests = observed.filter(
        (request) =>
          request.path === `/api/npi/v1/projects/${projectId}/tooling`,
      );
      const selectedMasterRequests = observed.filter(
        (request) =>
          request.path ===
          `/api/npi/v1/projects/${projectId}/tooling/${masterId}`,
      );
      expect(collectionRequests.length).toBeGreaterThanOrEqual(1);
      expect(collectionRequests.length).toBeLessThanOrEqual(2);
      expect(selectedMasterRequests.length).toBeGreaterThanOrEqual(1);
      expect(selectedMasterRequests.length).toBeLessThanOrEqual(2);
      expect(
        observed.every(
          (request) =>
            request.csrfToken === undefined &&
            request.idempotencyKey === undefined &&
            request.method === "GET" &&
            (request.path === `/api/npi/v1/projects/${projectId}/tooling` ||
              request.path ===
                `/api/npi/v1/projects/${projectId}/tooling/${masterId}`),
        ),
      ).toBe(true);
    });
  }

  test("navigates to one exact authorized Master without leaving Project context", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installToolingApi(page);
    await openTooling(page, "en");
    await page.getByText("Synthetic logical injection tool").first().click();
    await expect(page).toHaveURL(
      new RegExp(`/projects/${projectId}/tooling/${masterId}`),
    );
    await expect
      .poll(() => observed.at(-1)?.path)
      .toBe(`/api/npi/v1/projects/${projectId}/tooling/${masterId}`);
  });

  test("submits one capability-driven Master command with session binding", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installToolingApi(page);
    await openTooling(page, "en");
    await page.getByRole("button", { name: "Add Tooling record" }).click();
    await page
      .getByRole("combobox", { name: "Command" })
      .selectOption("master");
    await page
      .getByRole("textbox", { name: "Title" })
      .fill("Second logical tool");
    await page
      .getByRole("button", { name: "Create logical Tooling Master" })
      .click();
    await expect
      .poll(
        () => observed.filter((request) => request.method === "POST").length,
      )
      .toBe(1);
    const command = observed.find((request) => request.method === "POST");
    expect(command).toMatchObject({
      csrfToken,
      method: "POST",
      path: `/api/npi/v1/projects/${projectId}/tooling-masters`,
      payload: { title: "Second logical tool" },
    });
    expect(command?.idempotencyKey).toMatch(/^tooling-master-/u);
  });

  test("keeps processing, conflict and validation states explicit", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installToolingApi(page, {
      commandProblem: {
        code: "TOOLING_VERSION_CONFLICT",
        retryable: false,
        status: 409,
        title: "The Tooling version changed.",
      },
      delayCommand: true,
    });
    await openTooling(page, "en");
    await page.getByRole("button", { name: "Add Tooling record" }).click();
    await page.getByLabel("Revision label").fill("B");
    await page.getByRole("textbox", { name: "Title" }).fill("Second part");
    await page.getByLabel("Reason").fill("Exact revision conflict proof");
    await page
      .getByRole("button", { name: "Create Part and initial Revision" })
      .click();
    await expect(
      page.getByText("The command is processing. Keep this workspace open."),
    ).toBeVisible();
    await expect(page.getByText("The Tooling version changed.")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Retry exact command" }),
    ).toBeVisible();
  });

  test("shows an indistinguishable unavailable surface before protected identities", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installToolingApi(page, {
      initialProblem: {
        code: "TOOLING_UNAVAILABLE",
        retryable: false,
        status: 404,
        title: "The Tooling workspace is unavailable.",
      },
    });
    await page.goto(`/projects/${projectId}/tooling?lang=en`);
    await expect(
      page.getByRole("heading", { name: "Tooling workspace unavailable" }),
    ).toBeVisible();
    await expect(
      page.getByText("The Tooling workspace is unavailable."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Return to project" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
  });

  test("shows closed field validation without offering an unsafe retry", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installToolingApi(page, {
      commandProblem: {
        code: "VALIDATION_FAILED",
        fieldErrors: [{ message: "Use an approved title.", path: "title" }],
        retryable: false,
        status: 422,
        title: "The Tooling command is invalid.",
      },
    });
    await openTooling(page, "en");
    await page.getByRole("button", { name: "Add Tooling record" }).click();
    await page.getByLabel("Revision label").fill("A2");
    await page.getByRole("textbox", { name: "Title" }).fill("Rejected part");
    await page.getByLabel("Reason").fill("Validation proof");
    await page
      .getByRole("button", { name: "Create Part and initial Revision" })
      .click();
    await expect(
      page.getByText("The Tooling command is invalid."),
    ).toBeVisible();
    await expect(page.getByText("Use an approved title.")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Retry exact command" }),
    ).toHaveCount(0);
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p6-01-tooling-live-en-1366x768-100",
    state: "normal",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p6-01-tooling-live-zh-1440x900-125",
    state: "normal",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p6-01-tooling-live-zh-TW-1920x1080-150",
    state: "normal",
    width: 1920,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "en",
    name: "p6-01-tooling-empty-en-1366x768-100",
    state: "empty",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p6-01-tooling-read-only-zh-1440x900-125",
    state: "read_only",
    width: 1440,
    zoom: 1.25,
  },
] as const;

test.describe("@visual P6-01 live Tooling cockpit evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installToolingApi(page, { state: visual.state });
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
      await openTooling(page, visual.locale);
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
