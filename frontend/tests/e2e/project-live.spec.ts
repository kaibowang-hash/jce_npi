import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ProblemDetails } from "../../src/api/http";
import type { ProjectCockpitViewModel } from "../../src/domain/view-models";
import { translate } from "../translate";
import { projectCockpitFixture } from "../support/project-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectGlobalId = "11111111-1111-4111-8111-111111111111";
const projectEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/cockpit(?:\?.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

interface ObservedProjectRequest {
  accept: string | undefined;
  method: string;
  requestId: string;
  traceId: string | undefined;
  url: string;
}

interface ProblemDefinition {
  code: string;
  retryable?: boolean;
  status: number;
  title: string;
  traceId: string;
}

function problem(
  locale: TestLocale,
  definition: ProblemDefinition,
): ProblemDetails {
  return {
    type: `urn:npi:problem:${definition.code.toLowerCase()}`,
    title: translate(locale, definition.title),
    status: definition.status,
    code: definition.code,
    traceId: definition.traceId,
    retryable: definition.retryable ?? false,
  };
}

async function fulfillJson(
  route: Route,
  requestId: string,
  body: unknown,
  options: { status?: number; traceId?: string } = {},
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type":
        (options.status ?? 200) >= 400
          ? "application/problem+json"
          : "application/json",
      "X-Request-ID": requestId,
      "X-Trace-ID": options.traceId ?? "trace-project-live-success",
    },
    status: options.status ?? 200,
  });
}

async function installProjectApi(
  page: Page,
  respond: (route: Route, requestId: string, attempt: number) => Promise<void>,
): Promise<ObservedProjectRequest[]> {
  const observed: ObservedProjectRequest[] = [];
  await page.route(projectEndpoint, async (route) => {
    const headers = route.request().headers();
    const requestId = headers["x-request-id"] ?? "";
    expect(requestId).toMatch(requestIdPattern);
    observed.push({
      accept: headers.accept,
      method: route.request().method(),
      requestId,
      traceId: headers["x-trace-id"],
      url: route.request().url(),
    });
    await respond(route, requestId, observed.length);
  });
  return observed;
}

async function installSuccess(
  page: Page,
  cockpit: ProjectCockpitViewModel = projectCockpitFixture(),
): Promise<ObservedProjectRequest[]> {
  return installProjectApi(page, async (route, requestId) => {
    await fulfillJson(route, requestId, cockpit);
  });
}

async function installProblem(
  page: Page,
  locale: TestLocale,
  definition: ProblemDefinition,
): Promise<ObservedProjectRequest[]> {
  return installProjectApi(page, async (route, requestId) => {
    await fulfillJson(route, requestId, problem(locale, definition), {
      status: definition.status,
      traceId: definition.traceId,
    });
  });
}

async function openLiveProject(
  page: Page,
  locale: TestLocale = "en",
  globalId = projectGlobalId,
): Promise<void> {
  await page.goto(`/projects/${globalId}?lang=${locale}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
}

async function expectLoadedProject(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: /SYN-PROJECT-001 Synthetic project cockpit/u,
    }),
  ).toBeVisible();
}

type LiveNonNormalState =
  | "loading"
  | "empty"
  | "read_only"
  | "not_found"
  | "no_permission"
  | "validation"
  | "conflict"
  | "retryable"
  | "final";

const nonNormalStates = [
  "loading",
  "empty",
  "read_only",
  "not_found",
  "no_permission",
  "validation",
  "conflict",
  "retryable",
  "final",
] as const satisfies readonly LiveNonNormalState[];

const stateProblemDefinitions = {
  not_found: {
    code: "PROJECT_UNAVAILABLE",
    status: 404,
    title: "The requested project is unavailable.",
    traceId: "trace-project-unavailable",
  },
  no_permission: {
    code: "PERMISSION_DENIED",
    status: 403,
    title: "You do not have permission to perform this action.",
    traceId: "trace-project-permission",
  },
  conflict: {
    code: "VERSION_CONFLICT",
    status: 409,
    title: "The object was changed by another user.",
    traceId: "trace-project-conflict",
  },
  retryable: {
    code: "PROJECT_QUERY_UNAVAILABLE",
    retryable: true,
    status: 503,
    title: "The request could not be completed.",
    traceId: "trace-project-retryable",
  },
} as const satisfies Record<
  "not_found" | "no_permission" | "conflict" | "retryable",
  ProblemDefinition
>;

const stateHeadingSources = {
  not_found: "Project unavailable",
  no_permission: "Project access is not available",
  validation: "The project address is invalid",
  conflict: "The project view is out of date",
  retryable: "The project could not be loaded",
  final: "The project response could not be used safely",
} as const satisfies Record<
  Exclude<LiveNonNormalState, "loading" | "empty" | "read_only">,
  string
>;

async function prepareNonNormalState(
  page: Page,
  locale: TestLocale,
  state: LiveNonNormalState,
): Promise<() => Promise<void>> {
  let globalId = projectGlobalId;
  let finish = (): Promise<void> => Promise.resolve();
  if (state === "loading") {
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await installProjectApi(page, async (route, requestId) => {
      await responseMayComplete;
      await fulfillJson(route, requestId, projectCockpitFixture());
    });
    finish = async () => {
      releaseResponse?.();
      await expectLoadedProject(page);
    };
  } else if (state === "empty") {
    const cockpit = projectCockpitFixture();
    await installSuccess(page, { ...cockpit, references: [] });
  } else if (state === "read_only") {
    const cockpit = projectCockpitFixture();
    await installSuccess(page, {
      ...cockpit,
      permissions: { ...cockpit.permissions, canContribute: false },
    });
  } else if (state === "validation") {
    globalId = "not-a-uuid";
  } else if (state === "final") {
    await installProjectApi(page, async (route, requestId) => {
      await fulfillJson(
        route,
        requestId,
        { ...projectCockpitFixture(), untrustedDebugField: true },
        { traceId: "trace-project-invalid-response" },
      );
    });
  } else {
    await installProblem(page, locale, stateProblemDefinitions[state]);
  }
  await openLiveProject(page, locale, globalId);
  return finish;
}

test.describe("live Project cockpit BFF path", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders validated live Project data in ${locale}`, async ({
      page,
    }) => {
      const requests = await installSuccess(page);
      await openLiveProject(page, locale);
      await expectLoadedProject(page);

      await expect(page.locator(".prototype-banner")).toContainText(
        translate(
          locale,
          "Live project data. No production ERPNext system is connected.",
        ),
      );
      await expect(page.getByText("SYNTHETIC-PROJECT-TEMPLATE")).toBeVisible();
      await expect(page.getByText("Synthetic feasibility shell")).toBeVisible();
      await expect(page.getByText("SYN-CUSTOMER-001")).toBeVisible();
      await expectNoMixedLanguage(page, locale);

      expect(requests.length).toBeGreaterThanOrEqual(1);
      for (const request of requests) {
        expect(request).toMatchObject({
          accept: "application/json, application/problem+json",
          method: "GET",
          url: `http://127.0.0.1:4173/api/npi/v1/projects/${projectGlobalId}/cockpit`,
        });
        expect(request.traceId).toMatch(/^trace-/u);
      }
    });
  }

  test("keeps the live loading state honest until the BFF responds", async ({
    page,
  }) => {
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await installProjectApi(page, async (route, requestId) => {
      await responseMayComplete;
      await fulfillJson(route, requestId, projectCockpitFixture());
    });

    await openLiveProject(page);
    const loading = page.getByRole("status", {
      name: "Loading project cockpit",
    });
    await expect(loading).toBeVisible();
    await expect(loading).toHaveAttribute("aria-busy", "true");
    releaseResponse?.();
    await expectLoadedProject(page);
  });

  test("renders loaded empty references without inventing governed objects", async ({
    page,
  }) => {
    const fixture = projectCockpitFixture();
    await installSuccess(page, { ...fixture, references: [] });
    await openLiveProject(page);

    await expect(
      page.getByText("This project has no governed object references."),
    ).toBeVisible();
    await expect(
      page.getByText("No governed references are attached to this project."),
    ).toBeVisible();
    await expect(page.getByText("Synthetic feasibility shell")).toBeVisible();
  });

  test("renders the server permission projection as an explicit read-only cockpit", async ({
    page,
  }) => {
    const fixture = projectCockpitFixture();
    await installSuccess(page, {
      ...fixture,
      permissions: { ...fixture.permissions, canContribute: false },
    });
    await openLiveProject(page);

    await expect(page.locator(".scenario-banner--read_only")).toContainText(
      "You have view-only access. Project commands are not available in this cockpit.",
    );
    await expect(page.getByText("View only")).toBeVisible();
    await expect(page.locator('[data-visual-primary="true"]')).toHaveCount(0);
  });

  for (const denied of [
    {
      code: "PROJECT_UNAVAILABLE",
      status: 404,
      title: "The requested project is unavailable.",
      traceId: "trace-project-unavailable",
      expectedHeading: "Project unavailable",
    },
    {
      code: "PERMISSION_DENIED",
      status: 403,
      title: "You do not have permission to perform this action.",
      traceId: "trace-project-permission",
      expectedHeading: "Project access is not available",
    },
  ] as const) {
    test(`${String(denied.status)} hides protected Project data and exposes a trace`, async ({
      page,
    }) => {
      await installProblem(page, "en", denied);
      await openLiveProject(page);

      await expect(
        page.getByRole("heading", {
          level: 1,
          name: denied.expectedHeading,
        }),
      ).toBeVisible();
      await expect(page.getByText(denied.traceId)).toBeVisible();
      await expect(page.getByText("Synthetic project cockpit")).toHaveCount(0);
      await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
    });
  }

  test("rejects an invalid live Project address before an API request", async ({
    page,
  }) => {
    const requests = await installSuccess(page);
    await openLiveProject(page, "en", "not-a-uuid");

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The project address is invalid",
      }),
    ).toBeVisible();
    await expect(page.locator(".trace-reference code")).toContainText(
      /^client-/u,
    );
    expect(requests).toHaveLength(0);
  });

  test("reloads current data after a traceable version conflict", async ({
    page,
  }) => {
    let allowSuccess = false;
    const conflict = {
      code: "VERSION_CONFLICT",
      status: 409,
      title: "The object was changed by another user.",
      traceId: "trace-project-conflict",
    } as const;
    const requests = await installProjectApi(page, async (route, requestId) => {
      if (!allowSuccess) {
        await fulfillJson(route, requestId, problem("en", conflict), {
          status: conflict.status,
          traceId: conflict.traceId,
        });
        return;
      }
      await fulfillJson(route, requestId, projectCockpitFixture());
    });
    await openLiveProject(page);

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The project view is out of date",
      }),
    ).toBeVisible();
    await expect(page.getByText(conflict.traceId)).toBeVisible();
    const failedRequestCount = requests.length;
    allowSuccess = true;
    await page.getByRole("button", { name: "Reload project" }).click();
    await expectLoadedProject(page);
    expect(requests.length).toBeGreaterThan(failedRequestCount);
    expect(new Set(requests.map((request) => request.requestId)).size).toBe(
      requests.length,
    );
  });

  test("retries a retryable server failure without hiding its first trace", async ({
    page,
  }) => {
    let allowSuccess = false;
    const unavailable = {
      code: "PROJECT_QUERY_UNAVAILABLE",
      retryable: true,
      status: 503,
      title: "The request could not be completed.",
      traceId: "trace-project-retryable",
    } as const;
    const requests = await installProjectApi(page, async (route, requestId) => {
      if (!allowSuccess) {
        await fulfillJson(route, requestId, problem("en", unavailable), {
          status: unavailable.status,
          traceId: unavailable.traceId,
        });
        return;
      }
      await fulfillJson(route, requestId, projectCockpitFixture());
    });
    await openLiveProject(page);

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The project could not be loaded",
      }),
    ).toBeVisible();
    await expect(page.getByText(unavailable.traceId)).toBeVisible();
    const failedRequestCount = requests.length;
    allowSuccess = true;
    await page.getByRole("button", { name: "Retry" }).click();
    await expectLoadedProject(page);
    expect(requests.length).toBeGreaterThan(failedRequestCount);
  });

  test("fails closed on a structurally invalid success response", async ({
    page,
  }) => {
    const requests = await installProjectApi(page, async (route, requestId) => {
      await fulfillJson(
        route,
        requestId,
        { ...projectCockpitFixture(), untrustedDebugField: true },
        { traceId: "trace-project-invalid-response" },
      );
    });
    await openLiveProject(page);

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The project response could not be used safely",
      }),
    ).toBeVisible();
    await expect(
      page.getByText("trace-project-invalid-response"),
    ).toBeVisible();
    await expect(page.getByText("Synthetic project cockpit")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
    expect(requests.length).toBeGreaterThanOrEqual(1);
  });

  test("meets the live cockpit accessibility and industrial style contracts", async ({
    page,
  }) => {
    await installSuccess(page);
    await openLiveProject(page);
    await expectLoadedProject(page);

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
    await expectIndustrialComputedStyles(page);
    await expectNoDocumentOverflow(page);
  });
});

test.describe("trilingual live Project non-normal state purity", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    for (const state of nonNormalStates) {
      test(`${state} renders its controlled ${locale} surface`, async ({
        page,
      }) => {
        const finish = await prepareNonNormalState(page, locale, state);
        try {
          if (state === "loading") {
            await expect(
              page.locator(".state-surface--loading"),
            ).toHaveAttribute("aria-busy", "true");
          } else if (state === "empty") {
            await expect(page.locator(".scenario-banner--empty")).toContainText(
              translate(
                locale,
                "This project has no governed object references.",
              ),
            );
            await expectLoadedProject(page);
          } else if (state === "read_only") {
            await expect(
              page.locator(".scenario-banner--read_only"),
            ).toContainText(
              translate(
                locale,
                "You have view-only access. Project commands are not available in this cockpit.",
              ),
            );
            await expectLoadedProject(page);
          } else {
            await expect(
              page.getByRole("heading", {
                level: 1,
                name: translate(locale, stateHeadingSources[state]),
              }),
            ).toBeVisible();
            await expect(page.locator(".problem-details")).toBeVisible();
            await expect(
              page.getByText("Synthetic project cockpit"),
            ).toHaveCount(0);
          }
          await expectNoMixedLanguage(page, locale);
        } finally {
          await finish();
        }
      });
    }
  }
});

type LiveVisualState =
  | "normal"
  | "loading"
  | "empty"
  | "read_only"
  | "not_found"
  | "no_permission"
  | "validation"
  | "conflict"
  | "retryable"
  | "final";

interface LiveVisualCase {
  height: number;
  locale: TestLocale;
  name: string;
  state: LiveVisualState;
  width: number;
  zoom: 1 | 1.25 | 1.5;
}

const liveVisualCases: readonly LiveVisualCase[] = [
  {
    height: 768,
    locale: "en",
    name: "live-project-normal-en-1366x768-100",
    state: "normal",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh",
    name: "live-project-normal-zh-1920x1080-125",
    state: "normal",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "live-project-normal-zh-TW-1366x768-150",
    state: "normal",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "en",
    name: "live-project-loading-en-1920x1080-150",
    state: "loading",
    width: 1920,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "zh",
    name: "live-project-empty-zh-1366x768-125",
    state: "empty",
    width: 1366,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "live-project-read-only-zh-TW-1920x1080-100",
    state: "read_only",
    width: 1920,
    zoom: 1,
  },
  {
    height: 768,
    locale: "en",
    name: "live-project-not-found-en-1366x768-150",
    state: "not_found",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "zh",
    name: "live-project-no-permission-zh-1920x1080-125",
    state: "no_permission",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "live-project-validation-zh-TW-1366x768-100",
    state: "validation",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "en",
    name: "live-project-conflict-en-1920x1080-150",
    state: "conflict",
    width: 1920,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "zh",
    name: "live-project-retryable-zh-1366x768-100",
    state: "retryable",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "live-project-final-zh-TW-1920x1080-125",
    state: "final",
    width: 1920,
    zoom: 1.25,
  },
];

async function prepareLiveVisualCase(
  page: Page,
  fixture: LiveVisualCase,
): Promise<() => Promise<void>> {
  let globalId = projectGlobalId;
  let finish = (): Promise<void> => Promise.resolve();
  if (fixture.state === "normal") {
    await installSuccess(page);
  } else if (fixture.state === "empty") {
    const cockpit = projectCockpitFixture();
    await installSuccess(page, { ...cockpit, references: [] });
  } else if (fixture.state === "read_only") {
    const cockpit = projectCockpitFixture();
    await installSuccess(page, {
      ...cockpit,
      permissions: { ...cockpit.permissions, canContribute: false },
    });
  } else if (fixture.state === "loading") {
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await installProjectApi(page, async (route, requestId) => {
      await responseMayComplete;
      await fulfillJson(route, requestId, projectCockpitFixture());
    });
    finish = async () => {
      releaseResponse?.();
      await expectLoadedProject(page);
    };
  } else if (fixture.state === "validation") {
    globalId = "not-a-uuid";
  } else if (fixture.state === "final") {
    await installProjectApi(page, async (route, requestId) => {
      await fulfillJson(
        route,
        requestId,
        { ...projectCockpitFixture(), untrustedDebugField: true },
        { traceId: "trace-project-invalid-response" },
      );
    });
  } else {
    const definitions: Record<
      Exclude<
        LiveVisualState,
        "normal" | "loading" | "empty" | "read_only" | "validation" | "final"
      >,
      ProblemDefinition
    > = {
      not_found: {
        code: "PROJECT_UNAVAILABLE",
        status: 404,
        title: "The requested project is unavailable.",
        traceId: "trace-project-unavailable",
      },
      no_permission: {
        code: "PERMISSION_DENIED",
        status: 403,
        title: "You do not have permission to perform this action.",
        traceId: "trace-project-permission",
      },
      conflict: {
        code: "VERSION_CONFLICT",
        status: 409,
        title: "The object was changed by another user.",
        traceId: "trace-project-conflict",
      },
      retryable: {
        code: "PROJECT_QUERY_UNAVAILABLE",
        retryable: true,
        status: 503,
        title: "The request could not be completed.",
        traceId: "trace-project-retryable",
      },
    };
    await installProblem(page, fixture.locale, definitions[fixture.state]);
  }

  await page.setViewportSize(
    effectiveViewport(
      { height: fixture.height, width: fixture.width },
      fixture.zoom,
    ),
  );
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await openLiveProject(page, fixture.locale, globalId);
  if (fixture.state === "normal") await expectLoadedProject(page);
  else if (fixture.state === "loading") {
    await expect(page.locator(".state-surface--loading")).toBeVisible();
  } else if (fixture.state === "empty") {
    await expect(page.locator(".scenario-banner--empty")).toBeVisible();
  } else if (fixture.state === "read_only") {
    await expect(page.locator(".scenario-banner--read_only")).toBeVisible();
  } else {
    await expect(page.locator(".state-surface")).toBeVisible();
  }
  await expectNoMixedLanguage(page, fixture.locale);
  await expectNoDocumentOverflow(page);
  await page.addStyleTag({
    content:
      "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
  });
  await page.evaluate(async () => document.fonts.ready);
  await page.evaluate(() => {
    globalThis.scrollTo(0, 0);
  });
  return finish;
}

test.describe("@visual live Project cockpit evidence", () => {
  for (const fixture of liveVisualCases) {
    test(fixture.name, async ({ page }) => {
      const finish = await prepareLiveVisualCase(page, fixture);
      try {
        await expect(page).toHaveScreenshot(`${fixture.name}.png`, {
          fullPage: false,
          mask:
            fixture.state === "validation"
              ? [page.locator(".trace-reference code")]
              : [],
        });
      } finally {
        await finish();
      }
    });
  }
});
