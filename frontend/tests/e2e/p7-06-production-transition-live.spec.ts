import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";

import type { ProductionTransitionWorkspace } from "../../src/api/production-transition-data-source";
import { translate } from "../translate";
import {
  productionTransitionAcknowledgedWorkspace,
  productionTransitionAcknowledgementResult,
  productionTransitionEmptyWorkspace,
  productionTransitionIds,
  productionTransitionUsers,
  productionTransitionWorkspace,
} from "../support/production-transition-fixture";
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

const csrfToken = "p7-06-production-transition-browser-csrf-exact";
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const projectEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/.+/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

type ProblemStatus = 403 | 409 | 422 | 503;

interface ObservedRequest {
  csrfToken: string | undefined;
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
  search: string;
}

interface ApiOptions {
  acknowledgeDelay?: boolean;
  acknowledgeProblems?: readonly ProblemStatus[];
  loadDelay?: boolean;
  loadProblem?: ProblemStatus;
  malformedWorkspace?: boolean;
  refreshProblemOnce?: ProblemStatus;
  replayed?: boolean;
  workspace?: ProductionTransitionWorkspace;
  workspaceAfterAcknowledgement?: ProductionTransitionWorkspace;
}

interface UnavailableSessionObservation {
  requests: number;
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
      "X-Trace-ID": "trace-p7-06-production-transition-browser",
    },
    status,
  });
}

function problemFor(status: ProblemStatus): {
  code: string;
  retryable: boolean;
  title: string;
} {
  if (status === 403) {
    return {
      code: "PRODUCTION_TRANSITION_FORBIDDEN",
      retryable: false,
      title: "You do not have permission to view Production Transition.",
    };
  }
  if (status === 409) {
    return {
      code: "PRODUCTION_TRANSITION_CONFLICT",
      retryable: false,
      title: "The retained production handover package changed.",
    };
  }
  if (status === 422) {
    return {
      code: "PRODUCTION_TRANSITION_VALIDATION_FAILED",
      retryable: false,
      title: "The exact acknowledgement command is not valid.",
    };
  }
  return {
    code: "PRODUCTION_TRANSITION_UNAVAILABLE",
    retryable: true,
    title: "The Production Transition workspace is temporarily unavailable.",
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
      retryable: problem.retryable,
      status,
      title: problem.title,
      traceId: "trace-p7-06-production-transition-browser",
      type: `urn:npi:problem:${problem.code.toLowerCase()}`,
    }),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p7-06-production-transition-browser",
    },
    status,
  });
}

async function installSession(
  page: Page,
  locale: TestLocale,
  userId: string = productionTransitionUsers.receiver,
): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "6".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId,
    });
  });
}

async function installUnavailableSession(
  page: Page,
): Promise<UnavailableSessionObservation> {
  const observation = { requests: 0 };
  await page.route(sessionEndpoint, async (route) => {
    observation.requests += 1;
    await fulfillProblem(route, 503);
  });
  return observation;
}

async function installProductionTransitionApi(
  page: Page,
  options: ApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const workspace =
    options.workspace ?? (await productionTransitionWorkspace());
  const workspaceAfterAcknowledgement =
    options.workspaceAfterAcknowledgement ??
    (await productionTransitionAcknowledgedWorkspace());
  const acknowledgementResult = await productionTransitionAcknowledgementResult(
    options.replayed ?? false,
  );
  let acknowledgementAttempt = 0;
  let acknowledgementAccepted = false;
  let refreshProblemPending = options.refreshProblemOnce ?? null;

  await page.route(projectEndpoint, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const payload: unknown = request.postData()
      ? (JSON.parse(request.postData() ?? "null") as unknown)
      : null;
    observed.push({
      csrfToken: request.headers()["x-frappe-csrf-token"],
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path: url.pathname,
      payload,
      search: url.search,
    });
    expect(request.headers().accept).toBe(
      "application/json, application/problem+json",
    );

    if (request.method() === "GET" && url.pathname.endsWith("/cockpit")) {
      await fulfillJson(route, projectWorkCockpitFixture());
      return;
    }
    if (request.method() === "GET" && url.pathname.endsWith("/work-context")) {
      await fulfillJson(route, projectWorkContextFixture());
      return;
    }
    if (
      request.method() === "GET" &&
      url.pathname.endsWith("/production-transition")
    ) {
      if (options.loadDelay) {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 450);
        });
      }
      if (acknowledgementAccepted && refreshProblemPending !== null) {
        const status = refreshProblemPending;
        refreshProblemPending = null;
        await fulfillProblem(route, status);
        return;
      }
      if (options.loadProblem) {
        await fulfillProblem(route, options.loadProblem);
        return;
      }
      const current = acknowledgementAccepted
        ? workspaceAfterAcknowledgement
        : workspace;
      await fulfillJson(
        route,
        options.malformedWorkspace
          ? { ...current, callerSuppliedTenantId: "tenant-b" }
          : current,
      );
      return;
    }
    if (
      request.method() === "POST" &&
      url.pathname ===
        `/api/npi/v1/projects/${productionTransitionIds.project}/production-handover/${productionTransitionIds.handover}/revisions/2/acknowledgements`
    ) {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(
        /^production-handover-ack-[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u,
      );
      acknowledgementAttempt += 1;
      if (options.acknowledgeDelay) {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 1_200);
        });
      }
      const problem = options.acknowledgeProblems?.[acknowledgementAttempt - 1];
      if (problem) {
        await fulfillProblem(route, problem);
        return;
      }
      acknowledgementAccepted = true;
      await fulfillJson(
        route,
        {
          acknowledgement: acknowledgementResult.acknowledgement,
          handoverPackage: acknowledgementResult.handoverPackage,
          projectGlobalId: acknowledgementResult.projectGlobalId,
        },
        201,
        options.replayed ?? false,
      );
      return;
    }
    throw new Error(
      `Unexpected P7-06 browser request: ${request.method()} ${url.pathname}`,
    );
  });
  return observed;
}

async function openProductionTransition(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await page.goto(
    `/projects/${productionTransitionIds.project}?lang=${locale}&tab=production-transition`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByTestId("production-transition-workspace"),
  ).toBeVisible();
  await expect(
    page.getByTestId("production-transition-handover-tab"),
  ).toHaveAttribute("aria-selected", "true");
}

async function reviewAcknowledgementByKeyboard(page: Page): Promise<void> {
  const action = page.getByRole("button", {
    exact: true,
    name: "Acknowledge exact slot",
  });
  await action.focus();
  await expect(action).toBeFocused();
  await page.keyboard.press("Enter");
  const review = page.getByRole("dialog", {
    name: "Review exact acknowledgement",
  });
  await expect(review).toBeVisible();
  const confirm = review.getByRole("button", {
    name: "Acknowledge exact slot",
  });
  await confirm.focus();
  await expect(confirm).toBeFocused();
  await page.keyboard.press("Enter");
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include('[data-testid="production-transition-workspace"]')
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function expectDefinitionValue(
  scope: Locator,
  label: string,
  value: string,
): Promise<void> {
  const term = scope.locator("dt").filter({ hasText: label });
  await expect(term).toHaveCount(1);
  await expect(term).toHaveText(label);
  await expect(term.locator("xpath=following-sibling::dd[1]")).toHaveText(
    value,
  );
}

async function expectReceiverInspectorBinding(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  const inspector = page.getByTestId("production-transition-inspector");
  await expectDefinitionValue(
    inspector,
    translate(locale, "Eligible slot"),
    "receiver",
  );
  const selectedFact = inspector.locator(
    ".production-transition-workspace__inspector-detail",
  );
  await expect(
    selectedFact.getByRole("heading", {
      name: translate(locale, "Selected exact fact"),
    }),
  ).toBeVisible();
  await expectDefinitionValue(
    selectedFact,
    translate(locale, "Slot key"),
    "receiver",
  );
  await expectDefinitionValue(
    selectedFact,
    translate(locale, "Member"),
    productionTransitionUsers.receiver,
  );
}

function productionWorkspaceRequests(
  observed: readonly ObservedRequest[],
): ObservedRequest[] {
  return observed.filter((request) =>
    request.path.endsWith("/production-transition"),
  );
}

function acknowledgementRequests(
  observed: readonly ObservedRequest[],
): ObservedRequest[] {
  return observed.filter(
    (request) =>
      request.method === "POST" && request.path.endsWith("/acknowledgements"),
  );
}

test.describe("P7-06 live Production Transition workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders complete immutable handover and observation GET truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      const observed = await installProductionTransitionApi(page);
      await openProductionTransition(page, locale);
      await expectReceiverInspectorBinding(page, locale);

      await expect(page.getByTestId("handover-history-2")).toHaveAttribute(
        "aria-current",
        "page",
      );
      await expect(page.getByTestId("handover-history-1")).toBeVisible();
      await expect(page.getByTestId("handover-slot-sender")).toBeVisible();
      await expect(page.getByTestId("handover-slot-receiver")).toBeVisible();
      await expect(
        page.getByTestId(
          "manifest-readiness_snapshot-readiness_instance_revision",
        ),
      ).toBeVisible();
      await expect(
        page.getByTestId("manifest-released_trial_summary-released_document"),
      ).toBeVisible();
      await expect(
        page.getByText(productionTransitionIds.unresolvedAction, {
          exact: true,
        }),
      ).toBeVisible();
      await expect(
        page.getByText(productionTransitionIds.unresolvedRisk, { exact: true }),
      ).toBeVisible();
      await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(1);

      const observationTab = page.getByTestId(
        "production-transition-observation-tab",
      );
      await observationTab.focus();
      await expect(observationTab).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(observationTab).toHaveAttribute("aria-selected", "true");
      await expect(page.getByTestId("observation-history-2")).toHaveAttribute(
        "aria-current",
        "page",
      );
      const providerTable = page.getByTestId("production-transition-providers");
      await expect(providerTable.locator("tbody tr")).toHaveCount(5);
      await expect(page.getByTestId("provider-actual_sop")).toBeVisible();
      await expect(
        page.getByTestId("provider-tooling_stability"),
      ).toBeVisible();

      await page.getByTestId("production-transition-handover-tab").click();
      const historical = page.getByTestId("handover-history-1");
      await historical.focus();
      await expect(historical).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(historical).toHaveAttribute("aria-current", "page");
      await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);
      await expect(
        page.getByTestId("acknowledgement-unavailable"),
      ).toBeVisible();

      const workspaceGets = productionWorkspaceRequests(observed);
      expect(workspaceGets.length).toBeGreaterThanOrEqual(1);
      expect(
        workspaceGets.every(
          (request) =>
            request.method === "GET" &&
            request.payload === null &&
            request.search === "",
        ),
      ).toBe(true);
      expect(acknowledgementRequests(observed)).toHaveLength(0);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("shows loading, empty, read-only, retryable failure and denied states without stale protected truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installProductionTransitionApi(page, { loadDelay: true });
    await page.goto(
      `/projects/${productionTransitionIds.project}?lang=en&tab=production-transition`,
      { waitUntil: "domcontentloaded" },
    );
    await expect(
      page.getByTestId("production-transition-loading"),
    ).toBeVisible();
    await expect(
      page.getByTestId("production-transition-workspace"),
    ).toBeVisible();

    await page.unroute(projectEndpoint);
    await installProductionTransitionApi(page, {
      workspace: productionTransitionEmptyWorkspace(),
    });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("production-transition-empty")).toBeVisible();
    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);

    const readOnlyBase = await productionTransitionWorkspace();
    const readOnlyWorkspace: ProductionTransitionWorkspace = {
      ...readOnlyBase,
      permissions: {
        canAcknowledgeSlots: [],
        canCreateHandover: false,
        canCreateObservation: false,
        canManagePolicies: false,
        canReviseHandover: false,
        canReviseObservation: false,
      },
    };
    await page.unroute(projectEndpoint);
    await installProductionTransitionApi(page, {
      workspace: readOnlyWorkspace,
    });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("acknowledgement-unavailable")).toBeVisible();
    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);

    await page.unroute(projectEndpoint);
    await installProductionTransitionApi(page, { loadProblem: 503 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("production-transition-error")).toBeVisible();
    await expect(
      page.getByTestId("production-transition-workspace"),
    ).toHaveCount(0);
    await page.unroute(projectEndpoint);
    await installProductionTransitionApi(page);
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(
      page.getByTestId("production-transition-workspace"),
    ).toBeVisible();

    await page.unroute(projectEndpoint);
    await installProductionTransitionApi(page, { loadProblem: 403 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("production-transition-error")).toContainText(
      "Production transition access is not available",
    );
    await expect(
      page.getByText(productionTransitionUsers.receiver, { exact: true }),
    ).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
  });

  test("keeps acknowledgement unavailable when session verification fails or the actor does not own the eligible slot", async ({
    page,
  }) => {
    const unavailableSession = await installUnavailableSession(page);
    await installProductionTransitionApi(page);
    await openProductionTransition(page, "en");

    expect(unavailableSession.requests).toBeGreaterThanOrEqual(1);
    await expect(page.getByTestId("acknowledgement-unavailable")).toContainText(
      "Session verification is required before an acknowledgement can be prepared.",
    );
    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);

    await page.unroute(sessionEndpoint);
    await page.unroute(projectEndpoint);
    await installSession(page, "en", productionTransitionUsers.sender);
    await installProductionTransitionApi(page);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("acknowledgement-unavailable")).toContainText(
      "The acknowledgement permission does not match the current actor and frozen slot.",
    );
    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);
  });

  test("acknowledges only the authenticated actor's exact eligible current slot by keyboard and reloads GET truth", async ({
    page,
  }) => {
    const initial = await productionTransitionWorkspace();
    await installSession(page, "en");
    const observed = await installProductionTransitionApi(page, {
      acknowledgeDelay: true,
      workspace: initial,
    });
    await openProductionTransition(page, "en");
    await expectReceiverInspectorBinding(page, "en");
    const initialGetCount = productionWorkspaceRequests(observed).length;

    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(1);
    await reviewAcknowledgementByKeyboard(page);
    await expect(page.getByTestId("acknowledgement-processing")).toBeVisible();
    await expect(
      page.getByRole("button", {
        exact: true,
        name: "Acknowledge exact slot",
      }),
    ).toBeDisabled();
    await expect(page.getByTestId("handover-history-1")).toBeDisabled();
    expect(acknowledgementRequests(observed)).toHaveLength(1);
    await page.getByTestId("production-transition-observation-tab").click();
    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);
    await page.getByTestId("production-transition-handover-tab").click();
    await expect(page.getByTestId("acknowledgement-processing")).toBeVisible();
    expect(acknowledgementRequests(observed)).toHaveLength(1);
    await expect(page.getByTestId("acknowledgement-succeeded")).toBeVisible();
    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);

    const commands = acknowledgementRequests(observed);
    expect(commands).toHaveLength(1);
    expect(commands[0]).toMatchObject({
      csrfToken,
      idempotencyKey: expect.stringMatching(/^production-handover-ack-/u),
      method: "POST",
      path: `/api/npi/v1/projects/${productionTransitionIds.project}/production-handover/${productionTransitionIds.handover}/revisions/2/acknowledgements`,
      payload: {
        expectedRevisionGlobalId:
          productionTransitionIds.currentHandoverRevision,
        expectedSnapshotHash: initial.currentHandover?.revision.snapshotHash,
        intent: "acknowledge",
        slotKey: "receiver",
      },
      search: "",
    });
    expect(commands[0]?.payload).not.toHaveProperty("actorUserId");
    expect(commands[0]?.payload).not.toHaveProperty("memberGlobalId");
    expect(commands[0]?.payload).not.toHaveProperty("roleGlobalId");
    expect(commands[0]?.payload).not.toHaveProperty("tenantId");
    expect(productionWorkspaceRequests(observed).length).toBeGreaterThan(
      initialGetCount,
    );
  });

  test("uses one sealed idempotency key for an explicit retry and exposes replay truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installProductionTransitionApi(page, {
      acknowledgeProblems: [503],
      replayed: true,
    });
    await openProductionTransition(page, "en");
    await reviewAcknowledgementByKeyboard(page);

    await expect(page.getByTestId("acknowledgement-failed")).toBeVisible();
    expect(acknowledgementRequests(observed)).toHaveLength(1);
    await page
      .getByRole("button", { name: "Retry exact acknowledgement" })
      .click();
    await expect(page.getByTestId("acknowledgement-succeeded")).toContainText(
      "The original acknowledgement result was replayed safely.",
    );
    const commands = acknowledgementRequests(observed);
    expect(commands).toHaveLength(2);
    expect(commands[0]?.idempotencyKey).toBe(commands[1]?.idempotencyKey);
    expect(commands[0]?.payload).toEqual(commands[1]?.payload);
  });

  test("does not blindly retry a conflict and requires an explicit current-package reload", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installProductionTransitionApi(page, {
      acknowledgeProblems: [409],
    });
    await openProductionTransition(page, "en");
    const initialGetCount = productionWorkspaceRequests(observed).length;
    await reviewAcknowledgementByKeyboard(page);

    await expect(page.getByTestId("acknowledgement-failed")).toContainText(
      "Conflict",
    );
    expect(acknowledgementRequests(observed)).toHaveLength(1);
    await expect(
      page.getByRole("button", { name: "Retry exact acknowledgement" }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Reload current package" }).click();
    await expect(page.getByTestId("acknowledge-exact-slot")).toBeVisible();
    expect(acknowledgementRequests(observed)).toHaveLength(1);
    expect(productionWorkspaceRequests(observed).length).toBeGreaterThan(
      initialGetCount,
    );
  });

  test("holds accepted command truth until a failed refresh is explicitly reloaded", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installProductionTransitionApi(page, {
      refreshProblemOnce: 503,
    });
    await openProductionTransition(page, "en");
    await reviewAcknowledgementByKeyboard(page);

    await expect(
      page.getByTestId("acknowledgement-refresh-failed"),
    ).toContainText("Reload before making another decision");
    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);
    await page.getByRole("button", { name: "Reload current data" }).click();
    await expect(
      page.getByTestId("acknowledgement-refresh-failed"),
    ).toHaveCount(0);
    await expect(page.getByTestId("acknowledge-exact-slot")).toHaveCount(0);
    expect(productionWorkspaceRequests(observed).length).toBeGreaterThanOrEqual(
      3,
    );
  });

  test("surfaces a final validation failure and requires an explicit data reload", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installProductionTransitionApi(page, {
      acknowledgeProblems: [422],
    });
    await openProductionTransition(page, "en");
    const initialGetCount = productionWorkspaceRequests(observed).length;
    await reviewAcknowledgementByKeyboard(page);

    await expect(page.getByTestId("acknowledgement-failed")).toContainText(
      "Validation error",
    );
    expect(acknowledgementRequests(observed)).toHaveLength(1);
    await expect(
      page.getByRole("button", { name: "Retry exact acknowledgement" }),
    ).toHaveCount(0);
    await expect(page.getByTestId("handover-history-1")).toBeDisabled();
    await page.getByRole("button", { name: "Reload current data" }).click();
    await expect(page.getByTestId("acknowledge-exact-slot")).toBeVisible();
    expect(acknowledgementRequests(observed)).toHaveLength(1);
    expect(productionWorkspaceRequests(observed).length).toBeGreaterThan(
      initialGetCount,
    );
  });

  test("fails closed when the GET response contains a caller-supplied tenant projection", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installProductionTransitionApi(page, { malformedWorkspace: true });
    await page.goto(
      `/projects/${productionTransitionIds.project}?lang=en&tab=production-transition`,
      { waitUntil: "domcontentloaded" },
    );

    await expect(page.getByTestId("production-transition-error")).toBeVisible();
    await expect(
      page.getByTestId("production-transition-workspace"),
    ).toHaveCount(0);
    await expect(
      page.getByText(productionTransitionUsers.receiver, { exact: true }),
    ).toHaveCount(0);
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p7-06-production-transition-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p7-06-production-transition-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p7-06-production-transition-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P7-06 Production Transition evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installProductionTransitionApi(page);
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
      await openProductionTransition(page, visual.locale);
      await expectReceiverInspectorBinding(page, visual.locale);
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
