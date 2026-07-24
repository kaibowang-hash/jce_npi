import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ProblemDetails } from "../../src/api/http";
import type { GateEvidenceViewModel } from "../../src/domain/view-models";
import { translate } from "../../src/i18n/runtime";
import { gateEvidenceFixture } from "../support/gate-evidence-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectGlobalId = "11111111-1111-4111-8111-111111111111";
const gateGlobalId = "44444444-4444-4444-8444-444444444444";
const gateEvidenceEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/gates\/[^/?]+\/evidence(?:\?.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

interface ObservedGateRequest {
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

type LiveGateState =
  | "normal"
  | "loading"
  | "empty"
  | "read_only"
  | "partial"
  | "not_found"
  | "no_permission"
  | "validation"
  | "conflict"
  | "retryable"
  | "final";

const problemDefinitions = {
  not_found: {
    code: "GATE_UNAVAILABLE",
    status: 404,
    title: "The requested Gate is unavailable.",
    traceId: "trace-gate-unavailable",
  },
  no_permission: {
    code: "PERMISSION_DENIED",
    status: 403,
    title: "You do not have permission to perform this action.",
    traceId: "trace-gate-permission",
  },
  conflict: {
    code: "VERSION_CONFLICT",
    status: 409,
    title: "The object was changed by another user.",
    traceId: "trace-gate-conflict",
  },
  retryable: {
    code: "GATE_EVIDENCE_UNAVAILABLE",
    retryable: true,
    status: 503,
    title: "The request could not be completed.",
    traceId: "trace-gate-retryable",
  },
} as const satisfies Record<
  "not_found" | "no_permission" | "conflict" | "retryable",
  ProblemDefinition
>;

const stateHeadingSources = {
  not_found: "Gate evidence is unavailable",
  no_permission: "Gate evidence access is not available",
  validation: "The Gate evidence address is invalid",
  conflict: "The Gate evidence view is out of date",
  retryable: "Gate evidence could not be loaded",
  final: "The Gate evidence response could not be used safely",
} as const satisfies Record<
  Exclude<
    LiveGateState,
    "normal" | "loading" | "empty" | "read_only" | "partial"
  >,
  string
>;

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

function normalGateEvidence(): GateEvidenceViewModel {
  const fixture = structuredClone(gateEvidenceFixture());
  const requirement = fixture.requirements[1];
  const reference = requirement?.evidence[0];
  if (!requirement || !reference?.file) {
    throw new Error("The Gate evidence fixture must contain file evidence.");
  }
  reference.file.scanState = "clean";
  requirement.evidenceState = "scan_clean";
  return {
    ...fixture,
    summary: { ...fixture.summary, unsafeScanCount: 0 },
    permissions: { ...fixture.permissions, canAttachEvidence: true },
  };
}

function emptyGateEvidence(): GateEvidenceViewModel {
  const fixture = normalGateEvidence();
  const requirements = fixture.requirements.map((requirement) => ({
    ...requirement,
    evidenceState: "missing" as const,
    evidence: [],
  }));
  return {
    ...fixture,
    requirements,
    summary: {
      requiredCount: 2,
      missingRequiredCount: 2,
      unsafeScanCount: 0,
      evidenceCount: 0,
    },
  };
}

function readOnlyGateEvidence(): GateEvidenceViewModel {
  const fixture = normalGateEvidence();
  return {
    ...fixture,
    permissions: { ...fixture.permissions, canAttachEvidence: false },
  };
}

function partialGateEvidence(): GateEvidenceViewModel {
  const fixture = gateEvidenceFixture();
  return {
    ...fixture,
    permissions: { ...fixture.permissions, canAttachEvidence: true },
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
      "X-Trace-ID": options.traceId ?? "trace-gate-evidence-success",
    },
    status: options.status ?? 200,
  });
}

async function installGateApi(
  page: Page,
  respond: (route: Route, requestId: string, attempt: number) => Promise<void>,
): Promise<ObservedGateRequest[]> {
  const observed: ObservedGateRequest[] = [];
  await page.route(gateEvidenceEndpoint, async (route) => {
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
  view: GateEvidenceViewModel = normalGateEvidence(),
): Promise<ObservedGateRequest[]> {
  return installGateApi(page, async (route, requestId) => {
    await fulfillJson(route, requestId, view);
  });
}

async function installProblem(
  page: Page,
  locale: TestLocale,
  definition: ProblemDefinition,
): Promise<ObservedGateRequest[]> {
  return installGateApi(page, async (route, requestId) => {
    await fulfillJson(route, requestId, problem(locale, definition), {
      status: definition.status,
      traceId: definition.traceId,
    });
  });
}

async function openLiveGate(
  page: Page,
  locale: TestLocale = "en",
  projectId = projectGlobalId,
  gateId = gateGlobalId,
): Promise<void> {
  await page.goto(`/projects/${projectId}/gates/${gateId}?lang=${locale}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
}

async function expectLoadedGate(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: /G1 \/ SYN-PROJECT-001 Synthetic initiation evidence/u,
    }),
  ).toBeVisible();
}

async function prepareState(
  page: Page,
  locale: TestLocale,
  state: LiveGateState,
): Promise<() => Promise<void>> {
  let projectId = projectGlobalId;
  let finish = (): Promise<void> => Promise.resolve();
  if (state === "normal") {
    await installSuccess(page);
  } else if (state === "loading") {
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await installGateApi(page, async (route, requestId) => {
      await responseMayComplete;
      await fulfillJson(route, requestId, normalGateEvidence());
    });
    finish = async () => {
      releaseResponse?.();
      await expectLoadedGate(page);
    };
  } else if (state === "empty") {
    await installSuccess(page, emptyGateEvidence());
  } else if (state === "read_only") {
    await installSuccess(page, readOnlyGateEvidence());
  } else if (state === "partial") {
    await installSuccess(page, partialGateEvidence());
  } else if (state === "validation") {
    projectId = "not-a-uuid";
  } else if (state === "final") {
    await installGateApi(page, async (route, requestId) => {
      await fulfillJson(
        route,
        requestId,
        { ...normalGateEvidence(), untrustedDebugField: true },
        { traceId: "trace-gate-invalid-response" },
      );
    });
  } else {
    await installProblem(page, locale, problemDefinitions[state]);
  }
  await openLiveGate(page, locale, projectId);
  return finish;
}

test.describe("live Gate evidence BFF path", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders validated exact Gate evidence in ${locale}`, async ({
      page,
    }) => {
      const requests = await installSuccess(page);
      await openLiveGate(page, locale);
      await expectLoadedGate(page);

      await expect(page.getByText("3".repeat(64))).toBeVisible();
      await expect(page.getByText("4".repeat(64))).toHaveCount(0);
      await page
        .getByRole("button", {
          name: /DIMENSIONAL_REPORT Synthetic dimensional report/u,
        })
        .click();
      await expect(page.getByText("SYN-DIMENSIONAL-REPORT.pdf")).toBeVisible();
      await expect(page.getByText("4".repeat(64))).toBeVisible();
      await expect(page.getByText("/private/files/")).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: /decide|waiver|reopen/iu }),
      ).toHaveCount(0);
      await expect(page.locator('[data-visual-primary="true"]')).toHaveCount(0);
      await expectNoMixedLanguage(page, locale);

      expect(requests.length).toBeGreaterThanOrEqual(1);
      for (const request of requests) {
        expect(request).toMatchObject({
          accept: "application/json, application/problem+json",
          method: "GET",
          url: `http://127.0.0.1:4173/api/npi/v1/projects/${projectGlobalId}/gates/${gateGlobalId}/evidence`,
        });
        expect(request.traceId).toMatch(/^trace-/u);
      }
    });
  }

  test("keeps loading truthful until the Gate evidence response arrives", async ({
    page,
  }) => {
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await installGateApi(page, async (route, requestId) => {
      await responseMayComplete;
      await fulfillJson(route, requestId, normalGateEvidence());
    });
    await openLiveGate(page);

    const loading = page.getByRole("status", {
      name: "Loading Gate evidence workspace",
    });
    await expect(loading).toBeVisible();
    await expect(loading).toHaveAttribute("aria-busy", "true");
    releaseResponse?.();
    await expectLoadedGate(page);
  });

  test("keeps missing evidence and unsafe scan states explicit", async ({
    page,
  }) => {
    await installSuccess(page, partialGateEvidence());
    await openLiveGate(page);
    await expectLoadedGate(page);

    await expect(page.locator(".scenario-banner--partial")).toContainText(
      "Pending, failed, or infected file scans are not represented as clean evidence.",
    );
    await page
      .getByRole("button", {
        name: /DIMENSIONAL_REPORT Synthetic dimensional report/u,
      })
      .click();
    await expect(
      page
        .getByRole("table", { name: "Controlled evidence" })
        .getByText("Scan pending", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", {
        name: /CUSTOMER_CONFIRMATION Synthetic customer confirmation/u,
      })
      .click();
    await expect(
      page.getByText("No controlled evidence is attached."),
    ).toBeVisible();
  });

  for (const denied of [
    {
      ...problemDefinitions.not_found,
      expectedHeading: "Gate evidence is unavailable",
    },
    {
      ...problemDefinitions.no_permission,
      expectedHeading: "Gate evidence access is not available",
    },
  ] as const) {
    test(`${String(denied.status)} hides protected Gate evidence and exposes only a trace`, async ({
      page,
    }) => {
      await installProblem(page, "en", denied);
      await openLiveGate(page);

      await expect(
        page.getByRole("heading", {
          level: 1,
          name: denied.expectedHeading,
        }),
      ).toBeVisible();
      await expect(page.getByText(denied.traceId)).toBeVisible();
      await expect(page.getByText("Synthetic initiation evidence")).toHaveCount(
        0,
      );
      await expect(page.getByText("SYN-DIMENSIONAL-REPORT.pdf")).toHaveCount(0);
      await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
    });
  }

  test("rejects invalid route identities before requesting protected data", async ({
    page,
  }) => {
    const requests = await installSuccess(page);
    await openLiveGate(page, "en", "not-a-uuid");

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The Gate evidence address is invalid",
      }),
    ).toBeVisible();
    await expect(page.locator(".trace-reference code")).toContainText(
      /^client-/u,
    );
    expect(requests).toHaveLength(0);
  });

  test("reloads exact evidence after a traceable conflict", async ({
    page,
  }) => {
    let allowSuccess = false;
    const requests = await installGateApi(page, async (route, requestId) => {
      if (!allowSuccess) {
        await fulfillJson(
          route,
          requestId,
          problem("en", problemDefinitions.conflict),
          {
            status: problemDefinitions.conflict.status,
            traceId: problemDefinitions.conflict.traceId,
          },
        );
        return;
      }
      await fulfillJson(route, requestId, normalGateEvidence());
    });
    await openLiveGate(page);

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The Gate evidence view is out of date",
      }),
    ).toBeVisible();
    await expect(
      page.getByText(problemDefinitions.conflict.traceId),
    ).toBeVisible();
    const failedRequestCount = requests.length;
    allowSuccess = true;
    await page.getByRole("button", { name: "Reload Gate evidence" }).click();
    await expectLoadedGate(page);
    expect(requests.length).toBeGreaterThan(failedRequestCount);
    expect(new Set(requests.map((request) => request.requestId)).size).toBe(
      requests.length,
    );
  });

  test("fails closed on structurally invalid or executable business data", async ({
    page,
  }) => {
    const unsafe = '<img src=x onerror="globalThis.compromised=true">';
    const fixture = normalGateEvidence();
    await installSuccess(page, {
      ...fixture,
      gate: { ...fixture.gate, title: unsafe },
      requirements: fixture.requirements.map((requirement, index) =>
        index === 0 ? { ...requirement, title: unsafe } : requirement,
      ),
    });
    await openLiveGate(page);

    await expect(page.getByText(unsafe).first()).toBeVisible();
    await expect(page.locator(".object-header img")).toHaveCount(0);
    expect(
      await page.evaluate(
        () =>
          (globalThis as typeof globalThis & { compromised?: boolean })
            .compromised,
      ),
    ).toBeUndefined();
  });

  test("fails closed when the success response contains an unknown field", async ({
    page,
  }) => {
    const requests = await installGateApi(page, async (route, requestId) => {
      await fulfillJson(
        route,
        requestId,
        { ...normalGateEvidence(), rawPrivateUrl: "/private/files/unsafe.pdf" },
        { traceId: "trace-gate-invalid-response" },
      );
    });
    await openLiveGate(page);

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The Gate evidence response could not be used safely",
      }),
    ).toBeVisible();
    await expect(page.getByText("trace-gate-invalid-response")).toBeVisible();
    await expect(page.getByText("/private/files/unsafe.pdf")).toHaveCount(0);
    await expect(page.getByText("Synthetic initiation evidence")).toHaveCount(
      0,
    );
    expect(requests.length).toBeGreaterThanOrEqual(1);
  });

  test("supports keyboard selection, accessibility, and industrial layout", async ({
    page,
  }) => {
    await installSuccess(page);
    await openLiveGate(page);
    await expectLoadedGate(page);

    const dimensional = page.getByRole("button", {
      name: /DIMENSIONAL_REPORT Synthetic dimensional report/u,
    });
    await dimensional.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByText("SYN-DIMENSIONAL-REPORT.pdf")).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
    await expectIndustrialComputedStyles(page);
    await expectNoDocumentOverflow(page);
  });
});

test.describe("trilingual live Gate evidence state purity", () => {
  const nonNormalStates = [
    "loading",
    "empty",
    "read_only",
    "partial",
    "not_found",
    "no_permission",
    "validation",
    "conflict",
    "retryable",
    "final",
  ] as const satisfies readonly Exclude<LiveGateState, "normal">[];

  for (const locale of ["en", "zh", "zh-TW"] as const) {
    for (const state of nonNormalStates) {
      test(`${state} renders its controlled ${locale} surface`, async ({
        page,
      }) => {
        const finish = await prepareState(page, locale, state);
        try {
          if (state === "loading") {
            await expect(
              page.locator(".state-surface--loading"),
            ).toHaveAttribute("aria-busy", "true");
          } else if (state === "empty") {
            await expect(page.locator(".scenario-banner--empty")).toContainText(
              translate(
                locale,
                "This Gate has frozen requirements but no controlled evidence references.",
              ),
            );
            await expectLoadedGate(page);
          } else if (state === "read_only") {
            await expect(
              page.locator(".scenario-banner--read_only"),
            ).toContainText(
              translate(
                locale,
                "You have view-only access. Evidence attachment is not available in this workspace.",
              ),
            );
            await expectLoadedGate(page);
          } else if (state === "partial") {
            await expect(
              page.locator(".scenario-banner--partial"),
            ).toContainText(
              translate(
                locale,
                "Pending, failed, or infected file scans are not represented as clean evidence.",
              ),
            );
            await expectLoadedGate(page);
          } else {
            await expect(
              page.getByRole("heading", {
                level: 1,
                name: translate(locale, stateHeadingSources[state]),
              }),
            ).toBeVisible();
            await expect(page.locator(".problem-details")).toBeVisible();
            await expect(
              page.getByText("Synthetic initiation evidence"),
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

interface LiveGateVisualCase {
  height: number;
  locale: TestLocale;
  name: string;
  state: LiveGateState;
  width: number;
  zoom: 1 | 1.25 | 1.5;
}

const liveGateVisualCases: readonly LiveGateVisualCase[] = [
  {
    height: 768,
    locale: "en",
    name: "live-gate-evidence-normal-en-1366x768-100",
    state: "normal",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh",
    name: "live-gate-evidence-normal-zh-1920x1080-125",
    state: "normal",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "live-gate-evidence-normal-zh-TW-1366x768-150",
    state: "normal",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "en",
    name: "live-gate-evidence-loading-en-1920x1080-150",
    state: "loading",
    width: 1920,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "zh",
    name: "live-gate-evidence-empty-zh-1366x768-125",
    state: "empty",
    width: 1366,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "live-gate-evidence-read-only-zh-TW-1920x1080-100",
    state: "read_only",
    width: 1920,
    zoom: 1,
  },
  {
    height: 768,
    locale: "en",
    name: "live-gate-evidence-partial-en-1366x768-150",
    state: "partial",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "zh",
    name: "live-gate-evidence-no-permission-zh-1920x1080-125",
    state: "no_permission",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "live-gate-evidence-validation-zh-TW-1366x768-100",
    state: "validation",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "en",
    name: "live-gate-evidence-conflict-en-1920x1080-150",
    state: "conflict",
    width: 1920,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "zh",
    name: "live-gate-evidence-retryable-zh-1366x768-100",
    state: "retryable",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "live-gate-evidence-final-zh-TW-1920x1080-125",
    state: "final",
    width: 1920,
    zoom: 1.25,
  },
];

test.describe("@visual live Gate evidence", () => {
  for (const fixture of liveGateVisualCases) {
    test(fixture.name, async ({ page }) => {
      await page.setViewportSize(
        effectiveViewport(
          { height: fixture.height, width: fixture.width },
          fixture.zoom,
        ),
      );
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      const finish = await prepareState(page, fixture.locale, fixture.state);
      try {
        if (fixture.state === "normal") await expectLoadedGate(page);
        else if (fixture.state === "loading") {
          await expect(page.locator(".state-surface--loading")).toBeVisible();
        } else if (
          fixture.state === "empty" ||
          fixture.state === "read_only" ||
          fixture.state === "partial"
        ) {
          await expect(
            page.locator(`.scenario-banner--${fixture.state}`),
          ).toBeVisible();
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
