import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ProblemDetails } from "../../src/api/http";
import type {
  MyWorkPageViewModel,
  ProjectActivityItemViewModel,
  ProjectActivityPageViewModel,
  ProjectControlsViewModel,
  ProjectLearningPageViewModel,
} from "../../src/domain/view-models";
import { translate } from "../../src/i18n/runtime";
import {
  projectActivityFixture,
  projectControlIds,
  projectControlsFixture,
  projectLearningFixture,
} from "../support/project-controls-fixture";
import { projectCockpitFixture } from "../support/project-fixture";
import { projectDomainWorkItemsFixture } from "../support/project-work-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  expectSinglePrimaryAction,
  type TestLocale,
} from "./support";

const projectId = projectControlIds.project;
const laterProjectId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const csrfToken = "c".repeat(32);
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const idempotencyKeyPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const myWorkEndpoint = /\/api\/npi\/v1\/me\/work(?:\?.*)?$/u;
const cockpitEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/cockpit(?:\?.*)?$/u;
const controlsEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/controls(?:\?.*)?$/u;
const activityEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/activity(?:\?.*)?$/u;
const commentsEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/comments(?:\?.*)?$/u;
const learningEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/learning(?:\?.*)?$/u;
const workItemsEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/domain-work-items(?:\?.*)?$/u;

interface ObservedRequest {
  accept: string | undefined;
  csrf: string | undefined;
  idempotencyKey: string | undefined;
  method: string;
  requestId: string;
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
    code: definition.code,
    retryable: definition.retryable ?? false,
    status: definition.status,
    title: translate(locale, definition.title),
    traceId: definition.traceId,
    type: `urn:npi:problem:${definition.code.toLowerCase()}`,
  };
}

function observe(route: Route): ObservedRequest {
  const headers = route.request().headers();
  const requestId = headers["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  return {
    accept: headers.accept,
    csrf: headers["x-frappe-csrf-token"],
    idempotencyKey: headers["idempotency-key"],
    method: route.request().method(),
    requestId,
    url: route.request().url(),
  };
}

async function fulfillApi(
  route: Route,
  body: unknown,
  options: {
    idempotencyReplayed?: boolean;
    status?: number;
    traceId?: string;
  } = {},
): Promise<void> {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  const status = options.status ?? 200;
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type":
        status >= 400 ? "application/problem+json" : "application/json",
      ...(options.idempotencyReplayed === undefined
        ? {}
        : {
            "Idempotency-Replayed": String(options.idempotencyReplayed),
          }),
      "X-Request-ID": requestId,
      "X-Trace-ID": options.traceId ?? "trace-p4-05-live-success",
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(
    /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u,
    async (route) => {
      const request = observe(route);
      expect(request).toMatchObject({
        accept: "application/json, application/problem+json",
        csrf: undefined,
        idempotencyKey: undefined,
        method: "GET",
      });
      await fulfillApi(route, {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: {
          language: locale,
          messages: {},
          version: "f".repeat(64),
        },
        csrfToken,
        language: locale,
        userId: "manager@example.invalid",
      });
    },
  );
}

function activeCockpit() {
  const controls = projectControlsFixture();
  return projectCockpitFixture({
    businessCode: controls.project.businessCode,
    state: controls.project.state,
    tenantId: controls.project.tenantId,
    title: controls.project.title,
    version: controls.project.version,
  });
}

function terminalControlsFixture(): ProjectControlsViewModel {
  const controls = projectControlsFixture();
  return {
    ...controls,
    bindingOptions: null,
    lifecycleActions: controls.lifecycleActions.map((action) => ({
      ...action,
      available: false,
      reasonCode: "project_terminal",
    })),
    permissions: {
      canAssessHealth: false,
      canBindPolicy: false,
      canTransition: false,
    },
    project: {
      ...controls.project,
      state: "cancelled",
      version: 8,
    },
  };
}

function terminalCockpit() {
  const controls = terminalControlsFixture();
  return projectCockpitFixture({
    businessCode: controls.project.businessCode,
    state: controls.project.state,
    tenantId: controls.project.tenantId,
    title: controls.project.title,
    version: controls.project.version,
  });
}

function restrictedControlsFixture(): ProjectControlsViewModel {
  const controls = projectControlsFixture();
  return {
    ...controls,
    bindingOptions: null,
    lifecycleActions: controls.lifecycleActions.map((action) => ({
      ...action,
      available: false,
      reasonCode: "command_access_required",
    })),
    permissions: {
      canAssessHealth: false,
      canBindPolicy: false,
      canTransition: false,
    },
  };
}

function restrictedActivityFixture(): ProjectActivityPageViewModel {
  return {
    ...projectActivityFixture(),
    commentOptions: {
      attachments: [],
      mentions: [],
      objectLinks: [],
      truncated: false,
    },
    following: false,
    items: [],
    permissions: {
      canComment: false,
      canFollow: false,
    },
  };
}

function restrictedLearningFixture(): ProjectLearningPageViewModel {
  return {
    ...projectLearningFixture(),
    permissions: { canCreate: false },
  };
}

function proposedLearningFixture(): ProjectLearningPageViewModel {
  const learning = projectLearningFixture();
  const item = learning.items[0];
  if (!item) {
    throw new Error("The Project learning fixture requires one item.");
  }
  return {
    ...learning,
    items: [{ ...item, kind: "template_improvement" }],
  };
}

async function installCockpit(
  page: Page,
  cockpit = activeCockpit(),
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(cockpitEndpoint, async (route) => {
    const request = observe(route);
    observed.push(request);
    expect(request).toMatchObject({
      accept: "application/json, application/problem+json",
      csrf: undefined,
      idempotencyKey: undefined,
      method: "GET",
    });
    await fulfillApi(route, cockpit, {
      traceId: "trace-p4-05-project-cockpit",
    });
  });
  return observed;
}

interface GovernanceResponses {
  activity?: ProjectActivityPageViewModel;
  controls?: ProjectControlsViewModel;
  learning?: ProjectLearningPageViewModel;
}

async function installGovernanceReads(
  page: Page,
  responses: GovernanceResponses = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const install = async (
    endpoint: RegExp,
    body: unknown,
    traceId: string,
  ): Promise<void> => {
    await page.route(endpoint, async (route) => {
      const request = observe(route);
      observed.push(request);
      expect(request).toMatchObject({
        accept: "application/json, application/problem+json",
        csrf: undefined,
        idempotencyKey: undefined,
        method: "GET",
      });
      await fulfillApi(route, body, { traceId });
    });
  };
  await install(
    controlsEndpoint,
    responses.controls ?? projectControlsFixture(),
    "trace-p4-05-controls",
  );
  await install(
    activityEndpoint,
    responses.activity ?? projectActivityFixture(),
    "trace-p4-05-activity",
  );
  await install(
    learningEndpoint,
    responses.learning ?? proposedLearningFixture(),
    "trace-p4-05-learning",
  );
  return observed;
}

async function openProjectTab(
  page: Page,
  locale: TestLocale,
  tab: "controls" | "activity" | "learning",
): Promise<void> {
  await page.goto(`/projects/${projectId}?lang=${locale}&tab=${tab}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: /NPI-26018 Battery housing/u,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", {
      name: translate(
        locale,
        {
          activity: "Activity",
          controls: "Controls",
          learning: "Learning",
        }[tab],
      ),
    }),
  ).toHaveAttribute("aria-selected", "true");
}

const myWorkIds = {
  domainWorkItem: "22222222-2222-4222-8222-222222222222",
  gate: "33333333-3333-4333-8333-333333333333",
  invalidatedGate: "44444444-4444-4444-8444-444444444444",
} as const;

function myWorkPageFixture(): MyWorkPageViewModel {
  return {
    asOf: "2026-07-25T12:00:00Z",
    counts: {
      all: { availability: "available", value: 3 },
      approvals: { availability: "available", value: 1 },
      blockers: { availability: "available", value: 2 },
      integration: {
        availability: "unavailable",
        reason: "source_not_available",
      },
      overdue: { availability: "available", value: 2 },
      today: { availability: "available", value: 0 },
      waiting: { availability: "available", value: 1 },
    },
    items: [
      {
        action: "view_work_item",
        blocking: true,
        category: "risk",
        context: {
          code: "RISK-014",
          globalId: myWorkIds.domainWorkItem,
          title: "Hot runner delivery risk",
          type: "domain_work_item",
        },
        dueAt: "2026-07-25T01:00:00Z",
        dueState: "overdue",
        id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        priority: {
          scheme: "domain_severity",
          value: "high",
        },
        project: {
          businessCode: "NPI-26018",
          globalId: projectId,
          title: "Battery housing",
        },
        source: {
          globalId: myWorkIds.domainWorkItem,
          type: "domain_work_item",
          version: 4,
        },
        sourceStatus: {
          editableIn: "NPI_ONE",
          sourceSystem: "NPI_ONE",
          syncState: "local",
        },
        status: "ready",
        target: {
          kind: "my_work_item",
          workItemId: myWorkIds.domainWorkItem,
        },
        title: "Hot runner delivery risk",
        why: "domain_work_item_owner",
      },
      {
        action: "open_gate_review",
        blocking: false,
        category: "approval",
        context: {
          code: "G3",
          globalId: myWorkIds.gate,
          title: "Tooling release",
          type: "gate",
        },
        dueAt: "2026-07-25T02:00:00Z",
        dueState: "overdue",
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        priority: {
          scheme: "gate_requirement_priority",
          value: "P0",
        },
        project: {
          businessCode: "NPI-26018",
          globalId: projectId,
          title: "Battery housing",
        },
        source: {
          globalId: myWorkIds.gate,
          type: "gate_review_assignment",
          version: 7,
        },
        sourceStatus: {
          editableIn: "NPI_ONE",
          sourceSystem: "NPI_ONE",
          syncState: "local",
        },
        status: "waiting",
        target: {
          gateId: myWorkIds.gate,
          kind: "gate_review",
          projectId,
        },
        title: "Review Gate G3 evidence",
        why: "gate_review_step",
      },
      {
        action: "open_gate_review",
        blocking: true,
        category: "blocker",
        context: {
          code: "G4",
          globalId: myWorkIds.invalidatedGate,
          title: "Trial approval",
          type: "gate",
        },
        dueAt: null,
        dueState: "unscheduled",
        id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        priority: null,
        project: {
          businessCode: "NPI-26099",
          globalId: laterProjectId,
          title: "Later-page project",
        },
        source: {
          globalId: myWorkIds.invalidatedGate,
          type: "gate_review_invalidation",
          version: 3,
        },
        sourceStatus: {
          editableIn: "NPI_ONE",
          sourceSystem: "NPI_ONE",
          syncState: "local",
        },
        status: "blocked",
        target: {
          gateId: myWorkIds.invalidatedGate,
          kind: "gate_review",
          projectId: laterProjectId,
        },
        title: "Re-review invalidated Gate G4",
        why: "gate_dependency_change",
      },
    ],
    nextCursor: null,
    projectOptions: [
      {
        businessCode: "NPI-26018",
        globalId: projectId,
        title: "Battery housing",
      },
      {
        businessCode: "NPI-26099",
        globalId: laterProjectId,
        title: "Later-page project",
      },
    ],
    timeZone: "America/Los_Angeles",
  };
}

function filteredMyWorkPage(url: URL): MyWorkPageViewModel {
  const fixture = myWorkPageFixture();
  let items = [...fixture.items];
  const view = url.searchParams.get("view") ?? "all";
  if (view === "today" || view === "overdue") {
    items = items.filter((item) => item.dueAt !== null);
  } else if (view === "approvals") {
    items = items.filter((item) => item.category === "approval");
  } else if (view === "blockers") {
    items = items.filter((item) => item.blocking);
  } else if (view === "waiting") {
    items = items.filter((item) => item.status === "waiting");
  } else if (view === "integration") {
    items = [];
  }
  const requestedProject = url.searchParams.get("projectId");
  if (requestedProject) {
    items = items.filter((item) => item.project.globalId === requestedProject);
  }
  const priorityScheme = url.searchParams.get("priorityScheme");
  const priorityValue = url.searchParams.get("priorityValue");
  if (priorityScheme && priorityValue) {
    items = items.filter(
      (item) =>
        item.priority?.scheme === priorityScheme &&
        item.priority.value === priorityValue,
    );
  }
  const search = url.searchParams.get("search")?.toLocaleLowerCase();
  if (search) {
    items = items.filter((item) =>
      [item.title, item.context.code, item.context.title].some((value) =>
        value.toLocaleLowerCase().includes(search),
      ),
    );
  }
  const offset = url.searchParams.get("cursor") === "my-work.cursor.2" ? 2 : 0;
  const pageItems = items.slice(offset, offset + 2);
  return {
    ...fixture,
    items: pageItems,
    nextCursor:
      offset === 0 && items.length > pageItems.length
        ? "my-work.cursor.2"
        : null,
  };
}

async function installMyWorkApi(
  page: Page,
  respond: (
    route: Route,
    request: ObservedRequest,
    attempt: number,
  ) => Promise<void>,
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(myWorkEndpoint, async (route) => {
    const request = observe(route);
    observed.push(request);
    expect(request).toMatchObject({
      accept: "application/json, application/problem+json",
      csrf: undefined,
      idempotencyKey: undefined,
      method: "GET",
    });
    await respond(route, request, observed.length);
  });
  return observed;
}

async function installMyWorkSuccess(page: Page): Promise<ObservedRequest[]> {
  return installMyWorkApi(page, async (route, request) => {
    await fulfillApi(route, filteredMyWorkPage(new URL(request.url)), {
      traceId: "trace-p4-05-my-work",
    });
  });
}

async function openMyWork(
  page: Page,
  locale: TestLocale = "en",
): Promise<void> {
  await page.goto(`/work?lang=${locale}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: translate(locale, "My Work"),
    }),
  ).toBeVisible();
}

async function expectMyWorkLoaded(page: Page): Promise<void> {
  await expect(
    page.getByText("Hot runner delivery risk").first(),
  ).toBeVisible();
  await expect(page.locator('.worklist-panel [aria-busy="true"]')).toHaveCount(
    0,
  );
}

test.describe("P4-05 live My Work BFF path", () => {
  test("loads validated work, supports keyboard selection, and derives a safe local target", async ({
    page,
  }) => {
    await installSession(page, "en");
    const requests = await installMyWorkSuccess(page);
    await installCockpit(page);
    const exactTargetRequests: ObservedRequest[] = [];
    await page.route(workItemsEndpoint, async (route) => {
      const request = observe(route);
      exactTargetRequests.push(request);
      const url = new URL(request.url);
      expect(Object.fromEntries(url.searchParams)).toEqual({
        limit: "1",
        workItemId: myWorkIds.domainWorkItem,
      });
      const fixture = projectDomainWorkItemsFixture();
      const source = fixture.items[0];
      if (!source) {
        throw new Error("The exact WorkItem fixture requires one source item.");
      }
      await fulfillApi(
        route,
        {
          ...fixture,
          items: [
            {
              ...source,
              context: { ...source.context, projectId },
              globalId: myWorkIds.domainWorkItem,
              projectId,
              title: "Hot runner delivery risk",
            },
          ],
          nextCursor: null,
          projectId,
          projectVersion: activeCockpit().project.version,
        },
        { traceId: "trace-p4-05-exact-work-item" },
      );
    });
    await openMyWork(page);
    await expectMyWorkLoaded(page);
    await expect(
      page
        .getByRole("combobox", { name: "Project" })
        .getByRole("option", { name: "NPI-26099 · Later-page project" }),
    ).toHaveCount(1);
    await expect(
      page.getByText("Jul 24, 2026, 6:00 PM", { exact: true }).first(),
    ).toBeVisible();
    await expect(page.getByText("America/Los_Angeles")).toBeVisible();
    await expect(page.getByText("Due time zone")).toBeVisible();
    await expect(page.getByText("System time zone")).toBeVisible();
    await expect(page.getByText("Overdue").first()).toBeVisible();

    const rows = page.locator(".worklist-panel tbody tr");
    await expect(rows).toHaveCount(2);
    await rows.nth(1).focus();
    await expect(rows.nth(1)).toBeFocused();
    await rows.nth(1).press("Enter");
    await expect(rows.nth(1)).toHaveAttribute("aria-selected", "true");
    await expect(
      page
        .getByRole("complementary", { name: "Work item details" })
        .getByText("Gate review assignment"),
    ).toBeVisible();

    await rows.nth(0).press("Enter");
    const workItemAction = page
      .getByRole("button", { name: "View work item" })
      .first();
    await workItemAction.focus();
    await workItemAction.press("Enter");
    await expect(page).toHaveURL(
      `/projects/${projectId}?tab=work-items&workItem=${myWorkIds.domainWorkItem}`,
    );
    await expect(page.getByRole("tab", { name: "Work items" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(
      page.locator(".project-work-items-layout tbody tr"),
    ).toHaveCount(1);
    await expect(
      page
        .getByRole("complementary", { name: "Domain work item details" })
        .getByText(myWorkIds.domainWorkItem),
    ).toBeVisible();
    await expect(
      page.getByText("Synthetic interface dimension issue"),
    ).toHaveCount(0);
    expect(exactTargetRequests.length).toBeGreaterThanOrEqual(1);
    expect(
      new Set(
        exactTargetRequests.map((request) => new URL(request.url).search),
      ),
    ).toEqual(new Set([`?limit=1&workItemId=${myWorkIds.domainWorkItem}`]));
    expect(
      new Set(exactTargetRequests.map((request) => request.requestId)).size,
    ).toBe(exactTargetRequests.length);

    expect(requests.length).toBeGreaterThanOrEqual(1);
    const url = new URL(requests[0]?.url ?? "");
    expect(url.pathname).toBe("/api/npi/v1/me/work");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      limit: "20",
      view: "all",
    });
  });

  test("keeps pagination and Project, priority, and saved-view filters server-owned", async ({
    page,
  }) => {
    await installSession(page, "en");
    const requests = await installMyWorkSuccess(page);
    await openMyWork(page);
    await expectMyWorkLoaded(page);

    await expect(page.getByText("Page 1")).toBeVisible();
    await page.getByRole("button", { name: "Next page" }).click();
    await expect(
      page.getByText("Re-review invalidated Gate G4").first(),
    ).toBeVisible();
    await expect(page.getByText("Page 2")).toBeVisible();
    expect(new URL(requests.at(-1)?.url ?? "").searchParams.get("cursor")).toBe(
      "my-work.cursor.2",
    );

    await page.getByRole("button", { name: "Previous page" }).click();
    await expectMyWorkLoaded(page);

    let count = requests.length;
    await page
      .getByRole("combobox", { name: "Project" })
      .selectOption(projectId);
    await expect.poll(() => requests.length).toBeGreaterThan(count);
    expect(
      new URL(requests.at(-1)?.url ?? "").searchParams.get("projectId"),
    ).toBe(projectId);

    count = requests.length;
    await page
      .getByRole("combobox", { name: "Priority" })
      .selectOption("domain_severity:high");
    await expect.poll(() => requests.length).toBeGreaterThan(count);
    let parameters = new URL(requests.at(-1)?.url ?? "").searchParams;
    expect(parameters.get("priorityScheme")).toBe("domain_severity");
    expect(parameters.get("priorityValue")).toBe("high");
    await expect(page.getByText("Review Gate G3 evidence")).toHaveCount(0);

    count = requests.length;
    await page
      .getByRole("combobox", { name: "Saved view" })
      .selectOption("overdue");
    await expect.poll(() => requests.length).toBeGreaterThan(count);
    parameters = new URL(requests.at(-1)?.url ?? "").searchParams;
    expect(parameters.get("view")).toBe("overdue");
    expect(parameters.get("projectId")).toBe(projectId);
    expect(parameters.get("priorityValue")).toBe("high");
    await expect(
      page.getByText("Hot runner delivery risk").first(),
    ).toBeVisible();
  });

  test("renders an honest empty work queue without inventing assignments", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installMyWorkApi(page, async (route) => {
      const fixture = myWorkPageFixture();
      await fulfillApi(route, {
        ...fixture,
        counts: {
          ...fixture.counts,
          all: { availability: "available", value: 0 },
          approvals: { availability: "available", value: 0 },
          blockers: { availability: "available", value: 0 },
          overdue: { availability: "available", value: 0 },
          today: { availability: "available", value: 0 },
          waiting: { availability: "available", value: 0 },
        },
        items: [],
      });
    });
    await openMyWork(page);

    await expect(
      page.getByText("No assigned work is available in this view."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Next page" }),
    ).toBeDisabled();
  });

  test("hides protected work on a 403 response", async ({ page }) => {
    await installSession(page, "en");
    await installMyWorkApi(page, async (route) => {
      const denied = {
        code: "PERMISSION_DENIED",
        status: 403,
        title: "You do not have permission to perform this action.",
        traceId: "trace-p4-05-my-work-denied",
      } as const;
      await fulfillApi(route, problem("en", denied), {
        status: denied.status,
        traceId: denied.traceId,
      });
    });
    await openMyWork(page);

    await expect(
      page.getByText("My Work access is not available"),
    ).toBeVisible();
    await expect(page.getByText("trace-p4-05-my-work-denied")).toBeVisible();
    await expect(page.getByText("Hot runner delivery risk")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
  });

  test("fails closed on an invalid success response", async ({ page }) => {
    await installSession(page, "en");
    await installMyWorkApi(page, async (route) => {
      await fulfillApi(
        route,
        {
          ...myWorkPageFixture(),
          untrustedTargetPath: "https://example.invalid/escape",
        },
        {
          traceId: "trace-p4-05-my-work-invalid",
        },
      );
    });
    await openMyWork(page);

    await expect(
      page.getByText("The My Work response could not be used safely"),
    ).toBeVisible();
    await expect(page.getByText("trace-p4-05-my-work-invalid")).toBeVisible();
    await expect(page.getByText("Hot runner delivery risk")).toHaveCount(0);
  });

  test("retries a traceable retryable failure and then renders current work", async ({
    page,
  }) => {
    await installSession(page, "en");
    let allowSuccess = false;
    const requests = await installMyWorkApi(page, async (route, request) => {
      if (!allowSuccess) {
        const unavailable = {
          code: "MY_WORK_QUERY_UNAVAILABLE",
          retryable: true,
          status: 503,
          title: "The request could not be completed.",
          traceId: "trace-p4-05-my-work-retryable",
        } as const;
        await fulfillApi(route, problem("en", unavailable), {
          status: unavailable.status,
          traceId: unavailable.traceId,
        });
        return;
      }
      await fulfillApi(route, filteredMyWorkPage(new URL(request.url)));
    });
    await openMyWork(page);

    await expect(page.getByText("My Work could not be loaded")).toBeVisible();
    await expect(page.getByText("trace-p4-05-my-work-retryable")).toBeVisible();
    allowSuccess = true;
    await page.getByRole("button", { name: "Retry" }).click();
    await expectMyWorkLoaded(page);
    expect(requests.length).toBeGreaterThanOrEqual(2);
    expect(new Set(requests.map((request) => request.requestId)).size).toBe(
      requests.length,
    );
  });

  test("reloads a conflicted later page from the current first page", async ({
    page,
  }) => {
    await installSession(page, "en");
    const requests = await installMyWorkApi(page, async (route, request) => {
      const url = new URL(request.url);
      if (url.searchParams.has("cursor")) {
        const conflict = {
          code: "MY_WORK_CONFLICT",
          status: 409,
          title: "The object was changed by another user.",
          traceId: "trace-p4-05-my-work-conflict",
        } as const;
        await fulfillApi(route, problem("en", conflict), {
          status: conflict.status,
          traceId: conflict.traceId,
        });
        return;
      }
      await fulfillApi(route, filteredMyWorkPage(url));
    });
    await openMyWork(page);
    await expectMyWorkLoaded(page);

    await page.getByRole("button", { name: "Next page" }).click();
    await expect(page.getByText("My Work changed")).toBeVisible();
    await expect(page.getByText("Conflict", { exact: true })).toBeVisible();
    await expect(page.getByText("trace-p4-05-my-work-conflict")).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);

    await page.getByRole("button", { name: "Reload latest data" }).click();
    await expectMyWorkLoaded(page);
    await expect(page.getByText("Page 1")).toBeVisible();
    expect(new URL(requests.at(-1)?.url ?? "").searchParams.has("cursor")).toBe(
      false,
    );
  });

  test("meets the dense industrial, accessibility, and one-primary-action contracts", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installMyWorkSuccess(page);
    await openMyWork(page);
    await expectMyWorkLoaded(page);

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
    await expectIndustrialComputedStyles(page);
    await expectNoDocumentOverflow(page);
    await expectSinglePrimaryAction(page);
  });
});

test.describe("P4-05 live Project governance tabs", () => {
  for (const fixture of [
    {
      expected: "Control policy and authority",
      locale: "en",
      tab: "controls",
    },
    {
      expected: "Project activity",
      locale: "zh",
      tab: "activity",
    },
    {
      expected: "Project learning",
      locale: "zh-TW",
      tab: "learning",
    },
  ] as const) {
    test(`loads the ${fixture.tab} resource through the ${fixture.locale} catalog`, async ({
      page,
    }) => {
      await installSession(page, fixture.locale);
      await installCockpit(page);
      const requests = await installGovernanceReads(page);
      await openProjectTab(page, fixture.locale, fixture.tab);

      await expect(
        page.getByRole("heading", {
          name: translate(fixture.locale, fixture.expected),
        }),
      ).toBeVisible();
      if (fixture.tab === "controls") {
        await expect(
          page.getByText("Standard project control policy", { exact: true }),
        ).toBeVisible();
        await expect(page.getByText("Source unavailable")).toBeVisible();
      } else if (fixture.tab === "activity") {
        await expect(
          page.getByText("Review the controlled Gate evidence."),
        ).toBeVisible();
      } else {
        await expect(
          page.getByText("Hot runner sourcing retrospective").first(),
        ).toBeVisible();
      }
      await expectNoMixedLanguage(page, fixture.locale);
      const resourceRequests = requests.filter((request) =>
        new URL(request.url).pathname.endsWith(`/${fixture.tab}`),
      );
      expect(resourceRequests.length).toBeGreaterThanOrEqual(1);
      expect(
        resourceRequests.every((request) => request.method === "GET"),
      ).toBe(true);
    });
  }

  test("enforces server permission metadata across Controls, Activity, and Learning", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installCockpit(page);
    await installGovernanceReads(page, {
      activity: restrictedActivityFixture(),
      controls: restrictedControlsFixture(),
      learning: restrictedLearningFixture(),
    });
    await openProjectTab(page, "en", "controls");

    await expect(
      page.getByRole("heading", { name: "Control policy and authority" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Assess project health" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("radio", { name: "Pause project" }),
    ).toBeDisabled();

    await page.getByRole("tab", { name: "Activity" }).click();
    await expect(
      page.getByText(
        "You can view activity but cannot add project collaboration records.",
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Add project comment" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Follow project" }),
    ).toBeDisabled();

    await page.getByRole("tab", { name: "Learning" }).click();
    await expect(
      page.getByText("You can view learning records but cannot create them."),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Create learning record" }),
    ).toHaveCount(0);
  });

  test("reviews exact lifecycle authority and prerequisites in an isolated modal", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installCockpit(page);
    await installGovernanceReads(page);
    await openProjectTab(page, "en", "controls");

    await expect(
      page.getByRole("combobox", {
        name: "New manual health status Quality",
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("combobox", {
        name: "New manual health status Risk",
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("textbox", {
        name: "New numeric health value Progress",
      }),
    ).toBeVisible();

    await page.getByRole("radio", { name: "Pause project" }).check();
    await page.getByRole("button", { name: "Review lifecycle action" }).click();

    const dialog = page.getByRole("dialog", {
      name: "Review project lifecycle transition",
    });
    await expect(dialog).toBeVisible();
    await expect
      .poll(() =>
        page.locator("#root").evaluate((element) => {
          if (!(element instanceof HTMLElement)) {
            throw new Error("The application root must be an HTMLElement.");
          }
          return element.inert;
        }),
      )
      .toBe(true);
    await expect(
      dialog.getByText("Battery housing", { exact: true }),
    ).toBeVisible();
    await expect(dialog.getByText("Active", { exact: true })).toBeVisible();
    await expect(dialog.getByText("On hold", { exact: true })).toBeVisible();
    await expect(
      dialog.getByText(`PCP-STD / 3 / ${"a".repeat(64)}`, { exact: true }),
    ).toBeVisible();
    await expect(
      dialog.getByText("project_manager", { exact: true }),
    ).toBeVisible();
    await expect(
      dialog.getByText("Project Manager", { exact: true }),
    ).toBeVisible();
    await expect(
      dialog.getByText("manager@example.invalid", { exact: true }),
    ).toBeVisible();
    await expect(
      dialog.getByText(projectControlIds.managerMember, { exact: true }),
    ).toBeVisible();
    await expect(dialog.getByText("2", { exact: true })).toBeVisible();
    await expect(dialog.getByText("None", { exact: true })).toBeVisible();

    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toHaveCount(0);
    await expect
      .poll(() =>
        page.locator("#root").evaluate((element) => {
          if (!(element instanceof HTMLElement)) {
            throw new Error("The application root must be an HTMLElement.");
          }
          return element.inert;
        }),
      )
      .toBe(false);
  });

  test("keeps governed English business data explicitly exempt in a Chinese UI", async ({
    page,
  }) => {
    const controls = projectControlsFixture();
    const assessment = controls.health.assessment;
    const binding = controls.binding;
    const policy = controls.policy;
    const lifecycleAuthority = binding?.authorities[0];
    if (!assessment || !binding || !policy || !lifecycleAuthority) {
      throw new Error("The business-data fixture requires bound controls.");
    }
    const reason = "Supplier recovery approved after controlled review.";
    const recoveryPlan = "Track delivery evidence at the next Gate review.";
    const lifecycleReason = "Customer acceptance recorded in the source file.";
    const activity = projectActivityFixture();
    const lifecycleActivity: ProjectActivityPageViewModel = {
      ...activity,
      items: [
        {
          actorUserId: "manager@example.invalid",
          detail: {
            action: "pause",
            approvedBy: lifecycleAuthority,
            bindingGlobalId: binding.globalId,
            fromState: "active",
            policyRef: {
              globalId: policy.globalId,
              snapshotHash: policy.snapshotHash,
              version: policy.version,
            },
            prerequisites: [],
            projectVersion: controls.project.version,
            reason: lifecycleReason,
            toState: "on_hold",
          },
          eventType: "lifecycle_transition",
          globalId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          occurredAt: "2026-07-25T12:00:00Z",
        },
      ],
    };
    await installSession(page, "zh");
    await installCockpit(page);
    await installGovernanceReads(page, {
      activity: lifecycleActivity,
      controls: {
        ...controls,
        health: {
          ...controls.health,
          assessment: { ...assessment, reason, recoveryPlan },
        },
      },
    });
    await openProjectTab(page, "zh", "controls");

    for (const value of [reason, recoveryPlan]) {
      await expect(page.getByText(value, { exact: true })).toHaveAttribute(
        "data-language-exempt",
        "business-data",
      );
    }
    await expectNoMixedLanguage(page, "zh");

    await page.getByRole("tab", { name: translate("zh", "Activity") }).click();
    await expect(
      page.getByText(lifecycleReason, { exact: true }),
    ).toHaveAttribute("data-language-exempt", "business-data");
    await expectNoMixedLanguage(page, "zh");
  });

  test("locks mutable terminal controls while keeping authorized append-only context", async ({
    page,
  }) => {
    const controls = terminalControlsFixture();
    await installSession(page, "en");
    await installCockpit(page, terminalCockpit());
    await installGovernanceReads(page, { controls });
    await openProjectTab(page, "en", "controls");

    await expect(page.getByText("Terminal project")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Review lifecycle action" }),
    ).toBeDisabled();
    await expect(
      page.locator(".governance-lifecycle-table input:enabled"),
    ).toHaveCount(0);

    await page.getByRole("tab", { name: "Activity" }).click();
    await expect(page.getByText("Append-only collaboration")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Add project comment" }),
    ).toBeVisible();

    await page.getByRole("tab", { name: "Learning" }).click();
    await expect(page.getByText("Append-only learning")).toBeVisible();
    await expect(
      page.getByText(
        "This feedback is proposed only. It does not change or publish a Project Template.",
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Create learning record" }),
    ).toBeVisible();
  });

  for (const tab of ["controls", "activity", "learning"] as const) {
    test(`${tab} exposes a traceable retryable resource error without protected data`, async ({
      page,
    }) => {
      await installSession(page, "en");
      await installCockpit(page);
      const endpoint = {
        activity: activityEndpoint,
        controls: controlsEndpoint,
        learning: learningEndpoint,
      }[tab];
      await page.route(endpoint, async (route) => {
        const request = observe(route);
        expect(request).toMatchObject({
          accept: "application/json, application/problem+json",
          csrf: undefined,
          idempotencyKey: undefined,
          method: "GET",
        });
        const unavailable = {
          code: "PROJECT_COLLABORATION_UNAVAILABLE",
          retryable: true,
          status: 503,
          title: "The request could not be completed.",
          traceId: `trace-p4-05-${tab}-retryable`,
        } as const;
        await fulfillApi(route, problem("en", unavailable), {
          status: unavailable.status,
          traceId: unavailable.traceId,
        });
      });
      await openProjectTab(page, "en", tab);

      await expect(
        page.getByText("Project collaboration data is unavailable"),
      ).toBeVisible();
      await expect(
        page.getByText(`trace-p4-05-${tab}-retryable`),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
      await expect(
        page.getByText("Standard project control policy"),
      ).toHaveCount(0);
    });
  }

  test("loads an older Activity page once, preserves strict order, and sends the opaque cursor", async ({
    page,
  }) => {
    const first = {
      ...projectActivityFixture(),
      nextCursor: "activity.cursor.1",
    };
    const older: ProjectActivityItemViewModel = {
      actorUserId: "quality@example.invalid",
      detail: { active: true },
      eventType: "followed",
      globalId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      occurredAt: "2026-07-25T10:00:00Z",
    };
    const continuation = {
      ...projectActivityFixture(),
      items: [older],
      nextCursor: null,
    };
    const requests: ObservedRequest[] = [];
    await installSession(page, "en");
    await installCockpit(page);
    await page.route(activityEndpoint, async (route) => {
      const request = observe(route);
      requests.push(request);
      expect(request).toMatchObject({
        accept: "application/json, application/problem+json",
        csrf: undefined,
        idempotencyKey: undefined,
        method: "GET",
      });
      const cursor = new URL(request.url).searchParams.get("cursor");
      await fulfillApi(route, cursor ? continuation : first, {
        traceId: cursor
          ? "trace-p4-05-activity-continuation"
          : "trace-p4-05-activity-first",
      });
    });
    await openProjectTab(page, "en", "activity");

    await page.getByRole("button", { name: "Load more activity" }).click();
    await expect(
      page.locator(".governance-activity-table tbody tr"),
    ).toHaveCount(2);
    await expect(page.getByText("Project followed").first()).toBeVisible();
    const continuationRequests = requests.filter((request) =>
      new URL(request.url).searchParams.has("cursor"),
    );
    expect(continuationRequests).toHaveLength(1);
    const continuationUrl = new URL(continuationRequests[0]?.url ?? "");
    expect(continuationUrl.searchParams.get("cursor")).toBe(
      "activity.cursor.1",
    );
    expect(continuationUrl.searchParams.get("limit")).toBe("50");
    await expect(
      page.getByRole("button", { name: "Load more activity" }),
    ).toHaveCount(0);
  });

  test("does not claim a comment succeeded while the server rejects the command", async ({
    page,
  }) => {
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    const commands: (ObservedRequest & { body: unknown })[] = [];
    await installSession(page, "en");
    await installCockpit(page);
    await page.route(activityEndpoint, async (route) => {
      await fulfillApi(route, projectActivityFixture(), {
        traceId: "trace-p4-05-activity-command-base",
      });
    });
    await page.route(commentsEndpoint, async (route) => {
      const request = observe(route);
      commands.push({
        ...request,
        body: route.request().postDataJSON(),
      });
      await responseMayComplete;
      const conflict = {
        code: "PROJECT_VERSION_CONFLICT",
        retryable: true,
        status: 409,
        title: "The object was changed by another user.",
        traceId: "trace-p4-05-comment-conflict",
      } as const;
      await fulfillApi(route, problem("en", conflict), {
        status: conflict.status,
        traceId: conflict.traceId,
      });
    });
    await openProjectTab(page, "en", "activity");

    await page
      .getByRole("textbox", { name: "Comment" })
      .fill("Reload before another controlled comment.");
    await page.getByRole("button", { name: "Add comment" }).click();
    await expect.poll(() => commands.length).toBe(1);
    await expect(
      page.getByText("The server is validating the exact project version."),
    ).toBeVisible();
    await expect(
      page.locator(".governance-activity-table tbody tr"),
    ).toHaveCount(1);
    await expect(
      page.getByText("Append-only project comment recorded."),
    ).toHaveCount(0);

    const command = commands[0];
    expect(command).toMatchObject({
      accept: "application/json, application/problem+json",
      csrf: csrfToken,
      method: "POST",
    });
    expect(command?.idempotencyKey).toMatch(idempotencyKeyPattern);
    expect(command?.body).toEqual({
      attachments: [],
      body: "Reload before another controlled comment.",
      mentions: [],
      objectLinks: [],
    });

    releaseResponse?.();
    await expect(page.getByText("trace-p4-05-comment-conflict")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Reload latest data" }),
    ).toBeVisible();
    await expect(
      page.locator(".governance-activity-table tbody tr"),
    ).toHaveCount(1);
    await expect(
      page.getByText("Append-only project comment recorded."),
    ).toHaveCount(0);
  });

  test("keeps the Activity workspace keyboard-accessible and industrial", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installCockpit(page);
    await installGovernanceReads(page);
    await openProjectTab(page, "en", "activity");

    const row = page.locator(".governance-activity-table tbody tr").first();
    await row.focus();
    await expect(row).toBeFocused();
    await row.press("Enter");
    await expect(row).toHaveAttribute("aria-selected", "true");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
    await expectIndustrialComputedStyles(page);
    await expectNoDocumentOverflow(page);
    await expectSinglePrimaryAction(page);
  });

  for (const tab of ["controls", "learning"] as const) {
    test(`${tab} meets the accessibility and one-primary-action contracts`, async ({
      page,
    }) => {
      await installSession(page, "en");
      await installCockpit(page);
      await installGovernanceReads(page);
      await openProjectTab(page, "en", tab);

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(results.violations).toEqual([]);
      await expectNoDocumentOverflow(page);
      await expectSinglePrimaryAction(page);
    });
  }
});

async function settleVisual(page: Page, locale: TestLocale): Promise<void> {
  await expectNoMixedLanguage(page, locale);
  await expectNoDocumentOverflow(page);
  await page.addStyleTag({
    content:
      "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
  });
  await page.evaluate(async () => document.fonts.ready);
  await page.evaluate(() => {
    globalThis.scrollTo(0, 0);
  });
}

test.describe("@visual P4-05 live work and governance evidence", () => {
  const profiles = [
    {
      locale: "en",
      scale: 1,
      viewport: { height: 768, width: 1366 },
    },
    {
      locale: "zh",
      scale: 1.25,
      viewport: { height: 1080, width: 1920 },
    },
    {
      locale: "zh-TW",
      scale: 1.5,
      viewport: { height: 768, width: 1366 },
    },
  ] as const;
  const governanceSurfaces = [
    {
      heading: "Control policy and authority",
      section: "controls",
      surface: "controls",
    },
    {
      heading: "Project activity",
      section: "activity",
      surface: "activity",
    },
    {
      heading: "Project learning",
      section: "learning",
      surface: "learning",
    },
  ] as const;

  for (const profile of profiles) {
    const scaleLabel = String(profile.scale * 100);
    const viewportLabel = `${String(profile.viewport.width)}x${String(
      profile.viewport.height,
    )}`;
    test(`p4-05-my-work-${profile.locale}-${viewportLabel}-${scaleLabel}`, async ({
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
      await installMyWorkSuccess(page);
      await openMyWork(page, profile.locale);
      await expectMyWorkLoaded(page);
      await settleVisual(page, profile.locale);

      await expect(page).toHaveScreenshot(
        `p4-05-my-work-${profile.locale}-${viewportLabel}-${scaleLabel}.png`,
        { fullPage: false },
      );
      await page.setViewportSize({ height: 1000, width: 1600 });
      await settleVisual(page, profile.locale);
      await page.locator(".app-header, .status-bar").evaluateAll((elements) => {
        for (const element of elements) {
          if (element instanceof HTMLElement) {
            element.style.visibility = "hidden";
          }
        }
      });
      await expect(
        page.getByRole("complementary", {
          name: translate(profile.locale, "Work item details"),
        }),
      ).toHaveScreenshot(
        `p4-05-my-work-details-${profile.locale}-1600x1000-100.png`,
      );
    });

    for (const surface of governanceSurfaces) {
      test(`p4-05-${surface.surface}-${profile.locale}-${viewportLabel}-${scaleLabel}`, async ({
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
        await installCockpit(page);
        await installGovernanceReads(page);
        await openProjectTab(page, profile.locale, surface.section);
        await expect(
          page.getByRole("heading", {
            name: translate(profile.locale, surface.heading),
          }),
        ).toBeVisible();
        await settleVisual(page, profile.locale);

        await expect(page).toHaveScreenshot(
          `p4-05-${surface.surface}-${profile.locale}-${viewportLabel}-${scaleLabel}.png`,
          { fullPage: false },
        );
        if (surface.surface === "learning") {
          await page.setViewportSize({ height: 1000, width: 1600 });
          await settleVisual(page, profile.locale);
          await page
            .locator(".app-header, .status-bar")
            .evaluateAll((elements) => {
              for (const element of elements) {
                if (element instanceof HTMLElement) {
                  element.style.visibility = "hidden";
                }
              }
            });
          await expect(
            page.getByRole("complementary", {
              name: translate(profile.locale, "Template improvement"),
            }),
          ).toHaveScreenshot(
            `p4-05-learning-proposal-${profile.locale}-1600x1000-100.png`,
          );
        }
      });
    }

    test(`p4-05-controls-health-lifecycle-${profile.locale}-1600x1000-100`, async ({
      page,
    }) => {
      await page.setViewportSize({ height: 1000, width: 1600 });
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      await installSession(page, profile.locale);
      await installCockpit(page);
      await installGovernanceReads(page);
      await openProjectTab(page, profile.locale, "controls");
      const healthPanel = page
        .getByRole("heading", {
          name: translate(profile.locale, "Project health"),
        })
        .locator("xpath=../..");
      const lifecyclePanel = page
        .getByRole("heading", {
          name: translate(profile.locale, "Lifecycle actions"),
        })
        .locator("xpath=../..");
      await expect(healthPanel).toBeVisible();
      await expect(lifecyclePanel).toBeVisible();
      await settleVisual(page, profile.locale);
      await page.locator(".app-header, .status-bar").evaluateAll((elements) => {
        for (const element of elements) {
          if (element instanceof HTMLElement) {
            element.style.visibility = "hidden";
          }
        }
      });

      await expect(healthPanel).toHaveScreenshot(
        `p4-05-controls-health-${profile.locale}-1600x1000-100.png`,
      );
      await expect(lifecyclePanel).toHaveScreenshot(
        `p4-05-controls-lifecycle-${profile.locale}-1600x1000-100.png`,
      );
    });

    test(`p4-05-lifecycle-dialog-${profile.locale}-${viewportLabel}-${scaleLabel}`, async ({
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
      await installCockpit(page);
      await installGovernanceReads(page);
      await openProjectTab(page, profile.locale, "controls");
      await page
        .getByRole("radio", {
          name: translate(profile.locale, "Pause project"),
        })
        .check();
      await page
        .getByRole("button", {
          name: translate(profile.locale, "Review lifecycle action"),
        })
        .click();
      const dialog = page.getByRole("dialog", {
        name: translate(profile.locale, "Review project lifecycle transition"),
      });
      await expect(dialog).toBeVisible();
      await expect(
        dialog.getByRole("heading", {
          name: translate(
            profile.locale,
            "Review project lifecycle transition",
          ),
        }),
      ).toBeFocused();
      await settleVisual(page, profile.locale);

      await expect(page).toHaveScreenshot(
        `p4-05-lifecycle-dialog-${profile.locale}-${viewportLabel}-${scaleLabel}.png`,
        { fullPage: false },
      );
      await page.setViewportSize({ height: 1000, width: 1600 });
      await settleVisual(page, profile.locale);
      await expect(dialog).toHaveScreenshot(
        `p4-05-lifecycle-dialog-detail-${profile.locale}-1600x1000-100.png`,
      );
    });
  }
});
