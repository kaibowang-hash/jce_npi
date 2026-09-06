import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ToolingListPage } from "../../src/api/tooling-list-data-source";
import {
  toolingExportPackage,
  toolingListCockpit,
  toolingListIds,
  toolingListPage,
  toolingListPreference,
  toolingListRows,
} from "../support/tooling-list-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p6-08-tooling-list-browser-csrf-1";
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const projectEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/.+/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const packageBytes = new TextEncoder().encode("exact tooling object package");

interface ObservedRequest {
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
  query: string;
}

interface ApiOptions {
  canExport?: boolean;
  delayExport?: boolean;
  delayList?: boolean;
  delayPreference?: boolean;
  downloadFailureOnce?: boolean;
  downloadReplayed?: boolean;
  empty?: boolean;
  exportFailure?: 409 | 422;
  exportFailureOnce?: boolean;
  exportReplayed?: boolean;
  packageExpired?: boolean;
  paginated?: boolean;
  preferenceConflict?: boolean;
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
      "X-Trace-ID": "trace-p6-08-tooling-list-browser",
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
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify({
      code,
      retryable,
      status,
      title,
      traceId: "trace-p6-08-tooling-list-browser",
      type: `urn:npi:error:${code.toLowerCase()}`,
    }),
    headers: {
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p6-08-tooling-list-browser",
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "8".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "tooling.engineer@example.invalid",
    });
  });
}

async function packageSha256(): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    packageBytes.slice().buffer,
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

async function installApi(
  page: Page,
  locale: TestLocale,
  options: ApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  let exportAttempt = 0;
  let downloadAttempt = 0;
  await page.route(projectEndpoint, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const payload: unknown =
      request.method() === "POST" || request.method() === "PUT"
        ? (JSON.parse(request.postData() ?? "null") as unknown)
        : null;
    observed.push({
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path,
      payload,
      query: url.search,
    });
    if (request.method() === "POST" || request.method() === "PUT") {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
    }
    if (path.includes("/tooling-list/preferences/")) {
      if (options.delayPreference && request.method() === "GET") {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 300);
        });
      }
      if (request.method() === "PUT" && options.preferenceConflict) {
        await fulfillProblem(
          route,
          "TOOLING_LIST_PREFERENCE_CONFLICT",
          409,
          true,
          "The saved view changed.",
        );
        return;
      }
      if (request.method() === "PUT") {
        const body = payload as {
          preference: ReturnType<typeof toolingListPreference>["preference"];
        };
        await fulfillJson(
          route,
          {
            ...toolingListPreference(),
            optimisticVersion: 2,
            preference: body.preference,
            snapshotHash: "9".repeat(64),
          },
          200,
        );
        return;
      }
      await fulfillJson(route, toolingListPreference());
      return;
    }
    if (path.endsWith("/tooling-list")) {
      if (options.delayList) {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 300);
        });
      }
      const rows = toolingListRows();
      let pageValue: ToolingListPage;
      if (options.empty) {
        pageValue = toolingListPage({ items: [], totalCount: 0 });
      } else if (options.paginated && url.searchParams.has("cursor")) {
        pageValue = toolingListPage({
          items: rows.slice(1),
          nextCursor: null,
          totalCount: 2,
        });
      } else if (options.paginated) {
        pageValue = toolingListPage({
          items: rows.slice(0, 1),
          nextCursor: "cursor-page-2",
          totalCount: 2,
        });
      } else {
        pageValue = toolingListPage();
      }
      if (options.canExport === false) {
        pageValue = {
          ...pageValue,
          permissions: {
            canExport: false,
            exportUnavailableReason: "separate_export_authority_required",
            view: true,
          },
        };
      }
      await fulfillJson(route, pageValue);
      return;
    }
    if (path.endsWith("/tooling-exports")) {
      exportAttempt += 1;
      if (options.delayExport) {
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 350);
        });
      }
      const shouldFail =
        options.exportFailure !== undefined &&
        (!options.exportFailureOnce || exportAttempt === 1);
      if (shouldFail) {
        const status = options.exportFailure ?? 409;
        await fulfillProblem(
          route,
          status === 409 ? "TOOLING_EXPORT_STALE" : "VALIDATION_FAILED",
          status,
          status === 409,
          status === 409
            ? "The Tooling List export is stale."
            : "The Tooling List export is invalid.",
        );
        return;
      }
      const body = payload as
        | {
            mode: "selection";
            selection: readonly {
              snapshotHash: string;
              toolingMasterGlobalId: string;
            }[];
          }
        | {
            filter: ToolingListPage["filter"];
            mode: "filtered";
            querySnapshotHash: string;
          };
      const refs =
        body.mode === "selection"
          ? body.selection
          : toolingListRows().map((row) => ({
              snapshotHash: row.toolingMasterSnapshotHash,
              toolingMasterGlobalId: row.toolingMasterGlobalId,
            }));
      await fulfillJson(
        route,
        {
          package: toolingExportPackage({
            expiresAt: options.packageExpired
              ? "2026-08-01T10:00:00Z"
              : "2099-08-10T10:00:00Z",
            generatedAt: options.packageExpired
              ? "2026-08-01T09:00:00Z"
              : "2099-08-10T09:00:00Z",
            language: locale,
            mode: body.mode,
            objectCount: refs.length,
            objectRefs: refs,
            querySnapshotHash:
              body.mode === "filtered" ? body.querySnapshotHash : null,
            sha256: await packageSha256(),
            sizeBytes: packageBytes.length,
          }),
        },
        201,
        options.exportReplayed ?? exportAttempt > 1,
      );
      return;
    }
    if (path.endsWith(":content")) {
      downloadAttempt += 1;
      if (options.downloadFailureOnce && downloadAttempt === 1) {
        await fulfillProblem(
          route,
          "TOOLING_EXPORT_DOWNLOAD_UNAVAILABLE",
          503,
          true,
          "The Tooling object package download is unavailable.",
        );
        return;
      }
      await route.fulfill({
        body: "exact tooling object package",
        headers: {
          "Cache-Control": "private, no-store",
          "Content-Disposition":
            'attachment; filename="tooling-object-package.zip"',
          "Content-Security-Policy": "sandbox; default-src 'none'",
          "Content-Type": "application/zip",
          "Idempotency-Replayed": String(
            options.downloadReplayed ?? downloadAttempt > 1,
          ),
          "Referrer-Policy": "no-referrer",
          "X-Content-Type-Options": "nosniff",
          "X-Request-ID": requestIdentity(route),
          "X-Trace-ID": "trace-p6-08-tooling-list-browser",
        },
        status: 200,
      });
      return;
    }
    if (/\/tooling(?:\/[^/]+)?$/u.test(path)) {
      await fulfillJson(route, toolingListCockpit());
      return;
    }
    await route.abort();
  });
  return observed;
}

async function openWorkspace(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${toolingListIds.project}/tooling?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator("#tooling-list-workspace")).toBeVisible();
  await expect(page.getByText("Front housing mould").first()).toBeVisible();
}

async function selectFirstObject(page: Page): Promise<void> {
  await page.getByRole("checkbox", { name: /Front housing mould/u }).check();
}

async function createReviewedPackage(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Export object package" }).click();
  const review = page.getByRole("dialog", {
    name: "Review Tooling object package export",
  });
  await expect(review).toBeVisible();
  await expect(review).toContainText("One hour");
  await review.getByRole("button", { name: "Create object package" }).click();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include("#tooling-list-workspace")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P6-08 live Tooling List workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders ten governed views and exact shared-object truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installApi(page, locale);
      await openWorkspace(page, locale);

      await expect(
        page
          .locator("#tooling-list-workspace select")
          .first()
          .locator("option"),
      ).toHaveCount(10);
      await expect(
        page.locator("#tooling-list-workspace tbody tr"),
      ).toHaveCount(2);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("keeps stable server pages and selection across accessible pagination", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page, "en", { paginated: true });
    await openWorkspace(page, "en");

    await selectFirstObject(page);
    await expect(page.getByText("Selected objects: 1")).toBeVisible();
    await page.getByRole("button", { name: "Next page" }).click();
    await expect(
      page
        .locator("#tooling-list-workspace")
        .getByText("Connector insert mould"),
    ).toBeVisible();
    await page
      .getByRole("checkbox", { name: /Connector insert mould/u })
      .check();
    await expect(page.getByText("Selected objects: 2")).toBeVisible();
    await page.getByRole("button", { name: "Previous page" }).click();
    await expect(
      page.getByRole("checkbox", { name: /Front housing mould/u }),
    ).toBeChecked();
    expect(
      observed.filter(
        (request) =>
          request.method === "GET" && request.path.endsWith("/tooling-list"),
      ),
    ).toEqual([
      expect.objectContaining({
        query: expect.not.stringContaining("cursor="),
      }),
      expect.objectContaining({ query: expect.stringContaining("cursor=") }),
      expect.objectContaining({
        query: expect.not.stringContaining("cursor="),
      }),
    ]);
  });

  test("saves a closed query and layout snapshot with optimistic evidence", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page, "en");
    await openWorkspace(page, "en");

    await page.getByLabel("Search Tooling").fill("insert");
    await page.getByLabel("Sort by").selectOption("physical_set_count");
    await page.getByLabel("Direction").selectOption("desc");
    await page.getByLabel("Group by").selectOption("physical_set_presence");
    await page.getByText("Columns", { exact: true }).click();
    await page.getByRole("checkbox", { name: "Design Revisions" }).uncheck();
    await page.getByRole("button", { name: "Save view" }).click();

    await expect(
      page.getByText("Personal Tooling List view saved."),
    ).toBeVisible();
    const save = observed.find(
      (request) =>
        request.method === "PUT" &&
        request.path.includes("/tooling-list/preferences/"),
    );
    expect(save?.payload).toMatchObject({
      expectedSnapshotHash: "d".repeat(64),
      expectedVersion: 1,
      preference: {
        filter: {
          groupKey: "physical_set_presence",
          search: "insert",
          sortDirection: "desc",
          sortKey: "physical_set_count",
          viewId: "all",
        },
        hiddenColumns: ["design_revisions"],
      },
    });
  });

  test("reviews, creates and downloads one private exact package", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page, "en", {
      delayExport: true,
      downloadReplayed: true,
    });
    await openWorkspace(page, "en");
    await selectFirstObject(page);

    await page.getByRole("button", { name: "Export object package" }).click();
    const review = page.getByRole("dialog", {
      name: "Review Tooling object package export",
    });
    await expect(review).toContainText("Exact selected objects");
    await expect(review).toContainText("One hour");
    await review.getByRole("button", { name: "Create object package" }).click();
    await expect(
      page.getByText("Creating immutable Tooling object package"),
    ).toBeVisible();
    await expect(page.getByText("Package created")).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download object package" }).click();
    expect((await download).suggestedFilename()).toBe(
      "tooling-object-package.zip",
    );
    await expect(
      page.getByText("The exact package download was replayed safely."),
    ).toBeVisible();
    const commands = observed.filter((request) => request.method === "POST");
    expect(commands[0]?.payload).toMatchObject({
      mode: "selection",
      selection: [
        {
          snapshotHash: "a".repeat(64),
          toolingMasterGlobalId: toolingListIds.masterOne,
        },
      ],
    });
    expect(commands[1]?.payload).toEqual({
      expectedSnapshotHash: "1".repeat(64),
    });
  });

  test("retries a stale transport with the same idempotency key and shows replay truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page, "en", {
      exportFailure: 409,
      exportFailureOnce: true,
    });
    await openWorkspace(page, "en");
    await selectFirstObject(page);
    await createReviewedPackage(page);

    await expect(
      page.getByText(
        "The reviewed Tooling List changed. Reload the list and review the export again.",
      ),
    ).toBeVisible();
    await page.getByRole("button", { name: "Retry exact export" }).click();
    await expect(page.getByText("Replayed exact package")).toBeVisible();
    const exports = observed.filter((request) =>
      request.path.endsWith("/tooling-exports"),
    );
    expect(exports).toHaveLength(2);
    expect(exports[0]?.idempotencyKey).toBe(exports[1]?.idempotencyKey);
  });

  test("closes preference conflict, invalid export, expiry and retryable download states", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installApi(page, "en", { preferenceConflict: true });
    await openWorkspace(page, "en");
    await page.getByLabel("Search Tooling").fill("housing");
    await page.getByRole("button", { name: "Save view" }).click();
    await expect(
      page.getByText(
        "The saved view changed in another session. Reload it before saving again.",
      ),
    ).toBeVisible();

    await page.unroute(projectEndpoint);
    await installApi(page, "en", { exportFailure: 422 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByText("Front housing mould").first()).toBeVisible();
    await selectFirstObject(page);
    await createReviewedPackage(page);
    await expect(
      page.getByText(
        "The export request is outside the supported one-to-one-hundred object boundary.",
      ),
    ).toBeVisible();

    await page.unroute(projectEndpoint);
    await installApi(page, "en", { packageExpired: true });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByText("Front housing mould").first()).toBeVisible();
    await selectFirstObject(page);
    await createReviewedPackage(page);
    await expect(page.getByText("Expired", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Download object package" }),
    ).toBeDisabled();

    await page.unroute(projectEndpoint);
    const observed = await installApi(page, "en", {
      downloadFailureOnce: true,
    });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByText("Front housing mould").first()).toBeVisible();
    await selectFirstObject(page);
    await createReviewedPackage(page);
    await expect(page.getByText("Package created")).toBeVisible();
    await page.getByRole("button", { name: "Download object package" }).click();
    await expect(
      page.getByText(
        "The secure package download failed. No raw private URL was exposed.",
      ),
    ).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Retry exact download" }).click();
    await download;
    const downloads = observed.filter((request) =>
      request.path.endsWith(":content"),
    );
    expect(downloads).toHaveLength(2);
    expect(downloads[0]?.idempotencyKey).toBe(downloads[1]?.idempotencyKey);
  });

  test("shows explicit loading, empty and no-export truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installApi(page, "en", {
      canExport: false,
      delayList: true,
      delayPreference: true,
      empty: true,
    });
    await page.goto(`/projects/${toolingListIds.project}/tooling?lang=en`, {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByText("Loading saved Tooling List view"),
    ).toBeVisible();
    await expect(
      page.getByText("No Tooling Masters match this view."),
    ).toBeVisible();
    await expect(
      page.getByText("Tooling List export is unavailable."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Export object package" }),
    ).toBeDisabled();
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p6-08-tooling-list-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p6-08-tooling-list-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p6-08-tooling-list-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P6-08 Tooling List evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installApi(page, visual.locale);
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
      await openWorkspace(page, visual.locale);
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      const workspace = page.locator("#tooling-list-workspace");
      await workspace.scrollIntoViewIfNeeded();
      await expect(workspace).toHaveScreenshot(`${visual.name}.png`);
    });
  }
});
