import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { translate } from "../../src/i18n/runtime";
import {
  projectDomainWorkItemsFixture,
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

const projectId = "11111111-1111-4111-8111-111111111111";
const cockpitEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/cockpit(?:\?.*)?$/u;
const contextEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/work-context(?:\?.*)?$/u;
const workItemsEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/domain-work-items(?:\?.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

interface ObservedWorkspaceRequest {
  method: string;
  path: string;
  query: string;
  requestId: string;
}

interface WorkspaceApiOptions {
  contextVersion?: number;
  pageSize?: number;
  workItemsVersion?: number;
}

async function fulfill(
  route: Route,
  requestId: string,
  body: unknown,
  traceId: string,
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
      "X-Trace-ID": traceId,
    },
    status: 200,
  });
}

async function installWorkspaceApi(
  page: Page,
  options: WorkspaceApiOptions = {},
): Promise<ObservedWorkspaceRequest[]> {
  const observed: ObservedWorkspaceRequest[] = [];
  const install = async (
    pattern: RegExp,
    responseFor: (url: URL) => unknown,
    traceId: string,
  ): Promise<void> => {
    await page.route(pattern, async (route) => {
      const request = route.request();
      const requestId = request.headers()["x-request-id"] ?? "";
      const url = new URL(request.url());
      expect(requestId).toMatch(requestIdPattern);
      expect(request.headers().accept).toBe(
        "application/json, application/problem+json",
      );
      observed.push({
        method: request.method(),
        path: url.pathname,
        query: url.search,
        requestId,
      });
      await fulfill(route, requestId, responseFor(url), traceId);
    });
  };
  await install(
    cockpitEndpoint,
    () => projectWorkCockpitFixture(),
    "trace-project-workspace-cockpit",
  );
  await install(
    contextEndpoint,
    () => ({
      ...projectWorkContextFixture(),
      projectVersion: options.contextVersion ?? 4,
    }),
    "trace-project-workspace-context",
  );
  await install(
    workItemsEndpoint,
    (url) => {
      const fixture = projectDomainWorkItemsFixture();
      const stageId = url.searchParams.get("stageId");
      const ownerUserId = url.searchParams.get("ownerUserId");
      const overdue = url.searchParams.get("overdue");
      const kind = url.searchParams.get("kind");
      const requestedLimit = Number.parseInt(
        url.searchParams.get("limit") ?? "50",
        10,
      );
      const limit = Number.isInteger(requestedLimit)
        ? Math.min(Math.max(requestedLimit, 1), 100)
        : 50;
      const cursor = url.searchParams.get("cursor");
      const offset =
        cursor === null
          ? 0
          : Number.parseInt(cursor.replace(/^cursor-/u, ""), 10);
      const pageSize = options.pageSize
        ? Math.min(options.pageSize, limit)
        : limit;
      const items = fixture.items.filter(
        (item) =>
          (stageId === null || item.context.stageId === stageId) &&
          (ownerUserId === null ||
            item.ownerUserId.toLowerCase() === ownerUserId.toLowerCase()) &&
          (overdue === null || item.overdue === (overdue === "true")) &&
          (kind === null || item.kind === kind),
      );
      return {
        ...fixture,
        projectVersion: options.workItemsVersion ?? 4,
        items: items.slice(offset, offset + pageSize),
        nextCursor:
          offset + pageSize < items.length
            ? `cursor-${String(offset + pageSize)}`
            : null,
      };
    },
    "trace-project-workspace-items",
  );
  return observed;
}

async function openWorkspace(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/projects/${projectId}?lang=${locale}`, {
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

async function openWorkspaceTab(
  page: Page,
  locale: TestLocale,
  tab: "team" | "plan" | "work-items",
): Promise<void> {
  const source = {
    team: "Team and responsibilities",
    plan: "Plan",
    "work-items": "Work items",
  }[tab];
  await page.getByRole("tab", { name: translate(locale, source) }).click();
  await expect(
    page.getByRole("tab", { name: translate(locale, source) }),
  ).toHaveAttribute("aria-selected", "true");
  if (tab === "team") {
    await expect(
      page.getByText("engineering.lead@example.invalid").first(),
    ).toBeVisible();
  } else if (tab === "plan") {
    await expect(
      page
        .getByLabel(translate(locale, "Project plan"))
        .getByText("Synthetic tooling launch", { exact: true }),
    ).toBeVisible();
  } else {
    await expect(
      page.getByText("Synthetic interface dimension issue"),
    ).toBeVisible();
  }
}

test.describe("live Project work-management tabs", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`loads separate work resources and preserves language purity in ${locale}`, async ({
      page,
    }) => {
      const observed = await installWorkspaceApi(page);
      await openWorkspace(page, locale);

      await expect(
        page.getByRole("tab", { name: translate(locale, "Overview") }),
      ).toHaveAttribute("aria-selected", "true");
      expect(
        observed.filter((request) => request.path.endsWith("/work-context")),
      ).toHaveLength(0);
      expect(
        observed.filter((request) =>
          request.path.endsWith("/domain-work-items"),
        ),
      ).toHaveLength(0);

      await openWorkspaceTab(page, locale, "team");
      await openWorkspaceTab(page, locale, "plan");
      expect(
        observed.filter((request) => request.path.endsWith("/work-context")),
      ).toHaveLength(1);

      await openWorkspaceTab(page, locale, "work-items");
      const workItemRequests = observed.filter((request) =>
        request.path.endsWith("/domain-work-items"),
      );
      expect(workItemRequests).toHaveLength(1);
      expect(workItemRequests[0]?.query).toBe("?limit=100");
      expect(observed.every((request) => request.method === "GET")).toBe(true);
      expect(new Set(observed.map((request) => request.requestId)).size).toBe(
        observed.length,
      );
      await expect(
        page.locator('[data-visual-primary="true"]:visible'),
      ).toHaveCount(0);
      await expectNoMixedLanguage(page, locale);
    });
  }

  test("sends bounded WorkItem filters and keeps the table keyboard-accessible", async ({
    page,
  }) => {
    const observed = await installWorkspaceApi(page);
    await openWorkspace(page, "en");
    await openWorkspaceTab(page, "en", "work-items");

    await expect(
      page
        .getByRole("combobox", { name: "Kind" })
        .getByRole("option", { name: "Action item" }),
    ).toHaveAttribute("value", "action");
    await page.getByRole("combobox", { name: "Kind" }).selectOption("issue");
    await expect
      .poll(
        () =>
          observed.filter((request) =>
            request.path.endsWith("/domain-work-items"),
          ).length,
      )
      .toBe(2);
    expect(observed.at(-1)?.query).toBe("?kind=issue&limit=100");
    const firstRow = page
      .locator(".project-work-items-layout tbody tr")
      .first();
    await firstRow.focus();
    await expect(firstRow).toBeFocused();
    await firstRow.press("Enter");
    await expect(firstRow).toHaveAttribute("aria-selected", "true");

    await page
      .getByRole("textbox", { name: "Owner email" })
      .fill("QUALITY.LEAD@EXAMPLE.INVALID");
    await page.getByRole("button", { name: "Apply owner filter" }).click();
    await expect
      .poll(
        () =>
          observed.filter((request) =>
            request.path.endsWith("/domain-work-items"),
          ).length,
      )
      .toBe(3);
    expect(observed.at(-1)?.query).toBe(
      "?kind=issue&limit=100&ownerUserId=quality.lead%40example.invalid",
    );
    await expect(
      page.getByRole("textbox", { name: "Owner email" }),
    ).toHaveValue("quality.lead@example.invalid");
    await expect(
      page.getByText("Synthetic interface dimension issue"),
    ).toBeVisible();
  });

  test("shows complete dated substitution details to the holder and substitute", async ({
    page,
  }) => {
    await installWorkspaceApi(page);
    await openWorkspace(page, "en");
    await openWorkspaceTab(page, "en", "team");

    const team = page.getByLabel("Team members");
    await team.getByText("quality.lead@example.invalid").click();
    const inspector = page.getByRole("complementary", {
      name: "Team member details",
    });
    await expect(inspector.getByText("Substitution assignments")).toBeVisible();
    await expect(inspector.getByText("Original member")).toBeVisible();
    await expect(inspector.getByText("Substitute member")).toBeVisible();
    await expect(
      inspector.getByText("quality.lead@example.invalid").first(),
    ).toBeVisible();
    await expect(
      inspector.getByText("tooling.lead@example.invalid").first(),
    ).toBeVisible();
    await expect(inspector.getByText("Aug 1, 2026")).toBeVisible();
    await expect(inspector.getByText("Aug 15, 2026")).toBeVisible();

    await team.getByText("tooling.lead@example.invalid").click();
    await expect(inspector.getByText("Original member")).toBeVisible();
    await expect(
      inspector.getByText("quality.lead@example.invalid").first(),
    ).toBeVisible();
  });

  test("navigates all bounded WorkItem pages with next and previous controls", async ({
    page,
  }) => {
    const observed = await installWorkspaceApi(page, { pageSize: 2 });
    await openWorkspace(page, "en");
    await openWorkspaceTab(page, "en", "work-items");

    await expect(page.getByText("Page 1")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
    await page.getByRole("button", { name: "Next page" }).click();
    await expect(page.getByText("Synthetic drawing correction")).toBeVisible();
    await expect(page.getByText("Page 2")).toBeVisible();
    expect(
      observed
        .filter((request) => request.path.endsWith("/domain-work-items"))
        .at(-1)?.query,
    ).toBe("?cursor=cursor-2&limit=100");
    await expect(
      page.getByRole("button", { name: "Next page" }),
    ).toBeDisabled();

    await page.getByRole("button", { name: "Previous page" }).click();
    await expect(
      page.getByText("Synthetic resin availability risk"),
    ).toBeVisible();
    await expect(page.getByText("Page 1")).toBeVisible();
    expect(
      observed
        .filter((request) => request.path.endsWith("/domain-work-items"))
        .at(-1)?.query,
    ).toBe("?limit=100");
  });

  test("fails closed when work resources do not match the cockpit version", async ({
    page,
  }) => {
    await installWorkspaceApi(page, {
      contextVersion: 5,
      workItemsVersion: 5,
    });
    await openWorkspace(page, "en");

    await page.getByRole("tab", { name: "Team and responsibilities" }).click();
    await expect(
      page.getByRole("heading", {
        name: "The project work context response could not be used safely",
      }),
    ).toBeVisible();
    await expect(
      page.getByText("engineering.lead@example.invalid"),
    ).toHaveCount(0);

    await page.getByRole("tab", { name: "Work items" }).click();
    await expect(
      page.getByRole("heading", {
        name: "The domain work item response could not be used safely",
      }),
    ).toBeVisible();
    await expect(
      page.getByText("Synthetic interface dimension issue"),
    ).toHaveCount(0);
  });

  test("meets accessibility, industrial geometry, and local overflow contracts", async ({
    page,
  }) => {
    await installWorkspaceApi(page);
    await openWorkspace(page, "en");
    await openWorkspaceTab(page, "en", "work-items");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
    await expectIndustrialComputedStyles(page);
    await expectNoDocumentOverflow(page);
    await expect(page.getByLabel("Domain work items")).toHaveAttribute(
      "tabindex",
      "0",
    );
  });
});

interface WorkspaceVisualCase {
  height: number;
  locale: TestLocale;
  name: string;
  tab: "team" | "plan" | "work-items";
  width: number;
  zoom: 1 | 1.25 | 1.5;
}

const workspaceVisualCases: readonly WorkspaceVisualCase[] = [
  {
    height: 768,
    locale: "en",
    name: "live-project-team-en-1366x768-100",
    tab: "team",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "live-project-team-zh-TW-1920x1080-150",
    tab: "team",
    width: 1920,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "zh",
    name: "live-project-plan-zh-1920x1080-125",
    tab: "plan",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "en",
    name: "live-project-plan-en-1366x768-150",
    tab: "plan",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "live-project-work-items-zh-TW-1920x1080-100",
    tab: "work-items",
    width: 1920,
    zoom: 1,
  },
  {
    height: 768,
    locale: "zh",
    name: "live-project-work-items-zh-1366x768-150",
    tab: "work-items",
    width: 1366,
    zoom: 1.5,
  },
];

test.describe("@visual live Project work-management evidence", () => {
  for (const fixture of workspaceVisualCases) {
    test(fixture.name, async ({ page }) => {
      await installWorkspaceApi(page);
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
      await openWorkspace(page, fixture.locale);
      await openWorkspaceTab(page, fixture.locale, fixture.tab);
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
      });
    });
  }
});
