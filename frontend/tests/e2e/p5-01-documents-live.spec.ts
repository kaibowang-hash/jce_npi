import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  ControlledDocumentPageViewModel,
  ControlledDocumentWorkspaceViewModel,
} from "../../src/api/document-data-source";
import type { ProblemDetails } from "../../src/api/http";
import { translate } from "../../src/i18n/runtime";
import {
  controlledDocumentInReviewWorkspaceFixture,
  controlledDocumentPageFixture,
  controlledDocumentReleasedWorkspaceFixture,
  controlledDocumentWorkspaceFixture,
  documentReleaseTransitionFixture,
} from "../support/document-fixture";
import { projectWorkCockpitFixture } from "../support/project-work-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const csrfToken = "p5-document-browser-csrf-token-0001";
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const projectApiEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/.+/u;
const pdfContent = "%PDF";

interface DocumentApiOptions {
  readonly delayList?: Promise<void>;
  readonly invalidList?: boolean;
  readonly listProblem?: ProblemDetails;
  readonly noPolicy?: boolean;
  readonly readOnly?: boolean;
  readonly releaseState?: "draft" | "released";
}

interface ObservedRequest {
  readonly accept: string | undefined;
  readonly contentType: string | undefined;
  readonly csrfToken: string | undefined;
  readonly idempotencyKey: string | undefined;
  readonly method: string;
  readonly path: string;
  readonly payload: unknown;
  readonly requestId: string;
}

function documentPage(
  options: Pick<DocumentApiOptions, "noPolicy" | "readOnly"> = {},
): ControlledDocumentPageViewModel {
  const fixture = controlledDocumentPageFixture();
  return {
    ...fixture,
    project: {
      ...fixture.project,
      globalId: projectId,
      optimisticVersion: 4,
    },
    permissions: options.readOnly
      ? {
          ...fixture.permissions,
          create: false,
          revise: false,
          lock: false,
          recoverLock: false,
          preview: false,
          download: false,
        }
      : fixture.permissions,
    policies: options.noPolicy ? [] : fixture.policies,
    items: options.noPolicy ? [] : fixture.items,
  };
}

function documentWorkspace(
  options: Pick<DocumentApiOptions, "readOnly" | "releaseState"> = {},
): ControlledDocumentWorkspaceViewModel {
  const fixture =
    options.releaseState === "released"
      ? controlledDocumentReleasedWorkspaceFixture()
      : controlledDocumentWorkspaceFixture();
  return {
    ...fixture,
    project: {
      ...fixture.project,
      globalId: projectId,
      optimisticVersion: 4,
    },
    permissions: options.readOnly
      ? {
          ...fixture.permissions,
          create: false,
          revise: false,
          lock: false,
          recoverLock: false,
          preview: false,
          download: false,
        }
      : fixture.permissions,
    relationships: fixture.relationships.map((relationship) =>
      relationship.kind === "project"
        ? {
            ...relationship,
            targetIdentity: projectId,
            targetVersion: 4,
          }
        : relationship,
    ),
  };
}

function problem(locale: TestLocale): ProblemDetails {
  return {
    type: "urn:npi:problem:document_unavailable",
    title: translate(locale, "The requested document is unavailable."),
    status: 404,
    code: "DOCUMENT_UNAVAILABLE",
    traceId: "trace-p5-01-document-unavailable",
    retryable: false,
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
  options: {
    readonly status?: number;
    readonly traceId?: string;
  } = {},
): Promise<void> {
  const status = options.status ?? 200;
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type":
        status >= 400 ? "application/problem+json" : "application/json",
      ...(route.request().headers()["idempotency-key"]
        ? { "Idempotency-Replayed": "false" }
        : {}),
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": options.traceId ?? "trace-p5-01-document-browser",
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    const request = route.request();
    expect(request.method()).toBe("GET");
    expect(request.headers().accept).toBe(
      "application/json, application/problem+json",
    );
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: {
        language: locale,
        messages: {},
        version: "f".repeat(64),
      },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "administrator@example.invalid",
    });
  });
}

async function installDocumentApi(
  page: Page,
  options: DocumentApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const pageFixture = documentPage(options);
  let workspaceFixture = documentWorkspace(options);
  await page.route(projectApiEndpoint, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = request.headers();
    const requestId = requestIdentity(route);
    observed.push({
      accept: headers.accept,
      contentType: headers["content-type"],
      csrfToken: headers["x-frappe-csrf-token"],
      idempotencyKey: headers["idempotency-key"],
      method: request.method(),
      path: url.pathname,
      payload: request.method() === "POST" ? request.postDataJSON() : null,
      requestId,
    });
    if (url.pathname.endsWith("/cockpit")) {
      await fulfillJson(route, projectWorkCockpitFixture());
      return;
    }
    if (url.pathname.endsWith("/documents") && request.method() === "GET") {
      await options.delayList;
      if (options.listProblem) {
        await fulfillJson(route, options.listProblem, {
          status: options.listProblem.status,
          traceId: options.listProblem.traceId,
        });
        return;
      }
      await fulfillJson(
        route,
        options.invalidList
          ? { ...pageFixture, unsupportedDebugField: true }
          : pageFixture,
      );
      return;
    }
    if (url.pathname.endsWith("/capabilities")) {
      const file = workspaceFixture.revisions[0]?.files[0];
      if (!file) throw new Error("Document browser fixture has no file.");
      await fulfillJson(route, {
        projectId,
        documentId: workspaceFixture.document.globalId,
        revisionId: workspaceFixture.revisions[0]?.globalId,
        fileRevisionId: file.globalId,
        file: {
          globalId: file.globalId,
          fileDocumentId: file.fileDocumentId,
          revision: file.revision,
          optimisticVersion: file.optimisticVersion,
          fileName: file.fileName,
          mimeType: file.mimeType,
          sizeBytes: file.sizeBytes,
          sha256: file.sha256,
          scanState: file.scanState,
          scanObservedAt: file.scanObservedAt,
          private: file.private,
          released: file.released,
        },
        capabilities: file.capabilities,
      });
      return;
    }
    if (url.pathname.endsWith(":content")) {
      expect(request.method()).toBe("POST");
      expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(headers["idempotency-key"]).toMatch(/^inline-/u);
      await route.fulfill({
        body: pdfContent,
        headers: {
          "Cache-Control": "private, no-store",
          "Content-Disposition":
            "inline; filename=\"synthetic-drawing.pdf\"; filename*=UTF-8''synthetic-drawing.pdf",
          "Content-Length": String(new TextEncoder().encode(pdfContent).length),
          "Content-Security-Policy": "sandbox; default-src 'none'",
          "Content-Type": "application/pdf",
          "Idempotency-Replayed": "false",
          "Referrer-Policy": "no-referrer",
          "X-Content-Type-Options": "nosniff",
          "X-Request-ID": requestId,
          "X-Trace-ID": "trace-p5-01-document-content",
        },
        status: 200,
      });
      return;
    }
    if (url.pathname.endsWith(":submit-review")) {
      expect(request.method()).toBe("POST");
      expect(headers["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(headers["idempotency-key"]).toMatch(/^document-release-/u);
      const payload = request.postDataJSON() as Record<string, unknown>;
      expect(payload).toEqual({
        confirmationIntent: "submit_review",
        confirmed: true,
        expectedDocumentVersion: 3,
        expectedLifecycleVersion: 0,
        policyGlobalId:
          controlledDocumentWorkspaceFixture().releaseWorkspace.policies[0]
            ?.globalId,
        policySnapshotHash: "a".repeat(64),
        policyVersion: 1,
      });
      expect(payload).not.toHaveProperty("actorUserId");
      expect(payload).not.toHaveProperty("scanState");
      expect(payload).not.toHaveProperty("sha256");
      workspaceFixture = {
        ...documentWorkspace(),
        ...controlledDocumentInReviewWorkspaceFixture(),
        project: workspaceFixture.project,
        relationships: workspaceFixture.relationships,
      };
      await fulfillJson(
        route,
        documentReleaseTransitionFixture({
          projectId,
          documentId: workspaceFixture.document.globalId,
        }),
        { status: 201, traceId: "trace-p5-02-submit-review" },
      );
      return;
    }
    if (url.pathname.includes("/documents/")) {
      await fulfillJson(route, workspaceFixture);
      return;
    }
    throw new Error(
      `Unhandled P5-01 browser request: ${request.method()} ${url}`,
    );
  });
  return observed;
}

async function openDocuments(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/projects/${projectId}?lang=${locale}&tab=documents`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("tab", {
      name: translate(locale, "Design and documents"),
    }),
  ).toHaveAttribute("aria-selected", "true");
}

async function expectDocumentLoaded(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await expect(
    page.getByRole("heading", {
      name: translate(locale, "Immutable revision history"),
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "DRW-000071", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("synthetic-drawing.pdf")).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function expectNoPrivateUrl(page: Page): Promise<void> {
  const exposure = await page.locator("body").evaluate((body) => ({
    privatePathInMarkup: body.innerHTML.includes("/private/files/"),
    rawResource: Array.from(
      body.querySelectorAll<HTMLElement>("[href], [src]"),
    ).some((element) =>
      ["href", "src"].some(
        (attribute) =>
          element.getAttribute(attribute)?.includes("/private/files/") ?? false,
      ),
    ),
  }));
  expect(exposure).toEqual({
    privatePathInMarkup: false,
    rawResource: false,
  });
}

test.describe("P5-01 live controlled-document workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders exact revision, file, provider, and lock truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      const observed = await installDocumentApi(page);
      await openDocuments(page, locale);
      await expectDocumentLoaded(page, locale);

      await expect(
        page.getByText(translate(locale, "No outbound request was made")),
      ).toBeVisible();
      await expect(
        page
          .getByRole("heading", {
            name: translate(locale, "Provider boundaries"),
          })
          .locator("xpath=ancestor::section[1]")
          .getByText(translate(locale, "Unavailable"), { exact: true }),
      ).toHaveCount(2);
      await expect(page.getByText(/^SHA-256 a{64}$/u)).toBeVisible();
      await expectNoPrivateUrl(page);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);

      const documentRequests = observed.filter((request) =>
        request.path.includes("/documents"),
      );
      expect(documentRequests.length).toBeGreaterThanOrEqual(2);
      expect(
        documentRequests.filter(
          (request) =>
            request.path ===
            `/api/npi/v1/projects/${projectId}/documents/${controlledDocumentWorkspaceFixture().document.globalId}`,
        ),
      ).toHaveLength(1);
      expect(
        documentRequests.every(
          (request) =>
            request.method === "GET" &&
            request.accept === "application/json, application/problem+json" &&
            request.csrfToken === undefined &&
            request.idempotencyKey === undefined,
        ),
      ).toBe(true);
      expect(new Set(observed.map((request) => request.requestId)).size).toBe(
        observed.length,
      );
    });
  }

  test("streams a reauthorized native preview without exposing a private URL", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installDocumentApi(page);
    await openDocuments(page, "en");
    await expectDocumentLoaded(page, "en");

    await page.getByRole("button", { name: "Preview", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Secure native preview" }),
    ).toBeVisible();
    await expect(
      page.getByTitle("Preview of synthetic-drawing.pdf"),
    ).toHaveAttribute("sandbox", "");
    await expectNoPrivateUrl(page);

    const capability = observed.find((request) =>
      request.path.endsWith("/capabilities"),
    );
    const content = observed.find((request) =>
      request.path.endsWith(":content"),
    );
    expect(capability).toMatchObject({
      accept: "application/json, application/problem+json",
      method: "GET",
    });
    expect(content).toMatchObject({
      accept: "application/pdf",
      contentType: "application/json",
      csrfToken,
      method: "POST",
    });
    expect(content?.idempotencyKey).toMatch(/^inline-/u);
  });

  test("requires an explicit authenticated confirmation and refreshes immutable review truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installDocumentApi(page);
    await openDocuments(page, "en");
    await expectDocumentLoaded(page, "en");

    const start = page.getByRole("button", {
      name: "Submit for review",
      exact: true,
    });
    await expect(start).toBeEnabled();
    await start.click();
    const confirmation = page.getByRole("checkbox", {
      name: "I confirm this exact action using my authenticated session.",
    });
    const submit = page.getByRole("button", {
      name: "Submit for review",
      exact: true,
    });
    await expect(submit).toBeDisabled();
    await confirmation.check();
    await expect(submit).toBeEnabled();
    await submit.click();

    await expect(
      page.getByRole("heading", { name: "Reviewer progress" }),
    ).toBeVisible();
    await expect(page.getByText("reviewer@example.invalid")).toBeVisible();
    await expect(
      page.getByText("In review", { exact: true }).first(),
    ).toBeVisible();
    await expectNoPrivateUrl(page);
    await expectNoDocumentOverflow(page);
    await expectAxeClean(page);

    const command = observed.find((request) =>
      request.path.endsWith(":submit-review"),
    );
    expect(command).toMatchObject({
      accept: "application/json, application/problem+json",
      contentType: "application/json",
      csrfToken,
      method: "POST",
    });
    expect(command?.idempotencyKey).toMatch(/^document-release-/u);
    expect(command?.payload).toEqual({
      confirmationIntent: "submit_review",
      confirmed: true,
      expectedDocumentVersion: 3,
      expectedLifecycleVersion: 0,
      policyGlobalId:
        controlledDocumentWorkspaceFixture().releaseWorkspace.policies[0]
          ?.globalId,
      policySnapshotHash: "a".repeat(64),
      policyVersion: 1,
    });
  });

  test("uses the real App dirty guard for Project-tab navigation", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installDocumentApi(page);
    await openDocuments(page, "en");
    await expectDocumentLoaded(page, "en");

    await page
      .getByRole("button", { name: "Create document", exact: true })
      .first()
      .click();
    const title = page.getByRole("textbox", { name: "Title" });
    await title.fill("Unsubmitted controlled browser drawing");
    await page.getByRole("tab", { name: "Overview" }).click();
    const review = page.getByRole("dialog", { name: "Unsaved changes" });
    await expect(review).toBeVisible();
    await review.getByRole("button", { name: "Cancel" }).click();
    await expect(title).toHaveValue("Unsubmitted controlled browser drawing");
    await expect(page.getByRole("tab", { name: "Overview" })).toBeFocused();
    await expect(
      page.getByRole("tab", { name: "Design and documents" }),
    ).toHaveAttribute("aria-selected", "true");

    await page.getByRole("tab", { name: "Overview" }).click();
    const discardReview = page.getByRole("dialog", {
      name: "Unsaved changes",
    });
    const discard = discardReview.getByRole("button", {
      name: "Discard changes and leave",
    });
    await expect(discard).toBeDisabled();
    await discardReview
      .getByRole("textbox", { name: "Reason" })
      .fill("Discard the unsubmitted controlled document");
    await expect(discard).toBeEnabled();
    await discard.click();
    await expect(page.getByRole("tab", { name: "Overview" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByRole("textbox", { name: "Title" })).toHaveCount(0);
  });

  test("keeps loading, no-policy, read-only, unavailable, and invalid responses honest", async ({
    page,
  }) => {
    let releaseList: (() => void) | undefined;
    const delayed = new Promise<void>((resolve) => {
      releaseList = resolve;
    });
    await installSession(page, "en");
    await installDocumentApi(page, { delayList: delayed });
    await openDocuments(page, "en");
    await expect(
      page.getByRole("status", { name: "Loading project documents" }),
    ).toBeVisible();
    releaseList?.();
    await expectDocumentLoaded(page, "en");

    for (const state of [
      "no-policy",
      "read-only",
      "unavailable",
      "invalid",
    ] as const) {
      await page.unroute(projectApiEndpoint);
      await installDocumentApi(
        page,
        state === "no-policy"
          ? { noPolicy: true }
          : state === "read-only"
            ? { readOnly: true }
            : state === "unavailable"
              ? { listProblem: problem("en") }
              : { invalidList: true },
      );
      await page.reload({ waitUntil: "domcontentloaded" });
      if (state === "no-policy") {
        await expect(
          page.getByRole("heading", { name: "No controlled documents" }),
        ).toBeVisible();
        await expect(
          page
            .getByText(
              "Document creation is unavailable because no accepted document policy is configured.",
            )
            .first(),
        ).toBeVisible();
      } else if (state === "read-only") {
        await expectDocumentLoaded(page, "en");
        await expect(
          page.getByRole("button", { name: "Create document" }).first(),
        ).toBeDisabled();
        await expect(
          page.getByRole("button", { name: "Check in" }),
        ).toBeDisabled();
      } else {
        await expect(
          page.getByRole("heading", {
            name:
              state === "unavailable"
                ? "Project documents are not available"
                : "Project documents could not be loaded",
          }),
        ).toBeVisible();
        await expect(page.getByText("DRW-000071")).toHaveCount(0);
      }
      await expectNoPrivateUrl(page);
    }
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p5-01-documents-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p5-01-documents-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p5-01-documents-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P5-01 controlled-document evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installDocumentApi(page);
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
      await openDocuments(page, visual.locale);
      await expectDocumentLoaded(page, visual.locale);
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
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

const releaseVisualCases = [
  {
    height: 768,
    locale: "en",
    name: "p5-02-document-release-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p5-02-document-release-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p5-02-document-release-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P5-02 review and release evidence", () => {
  for (const visual of releaseVisualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installDocumentApi(page, { releaseState: "released" });
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
      await openDocuments(page, visual.locale);
      await expectDocumentLoaded(page, visual.locale);
      const releasePanel = page.getByRole("heading", {
        name: translate(visual.locale, "Review and release"),
      });
      await expect(releasePanel).toBeVisible();
      await expect(
        page.getByRole("heading", {
          name: translate(visual.locale, "Electronic confirmations"),
        }),
      ).toBeVisible();
      await expect(
        page.getByRole("heading", {
          name: translate(visual.locale, "Lifecycle events"),
        }),
      ).toBeVisible();
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await releasePanel.scrollIntoViewIfNeeded();
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
