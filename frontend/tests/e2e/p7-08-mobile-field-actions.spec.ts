import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  TrialExecutionWorkspace,
  TrialQualityWorkspace,
} from "../../src/api/trial-data-source";
import type {
  GateReviewOutcome,
  GateReviewViewModel,
} from "../../src/domain/view-models";
import { translate } from "../translate";
import {
  gateReviewFixture,
  gateReviewReadOnlyFixture,
} from "../support/gate-review-fixture";
import {
  trialExecutionIds,
  trialExecutionWorkspace,
} from "../support/trial-execution-fixture";
import {
  trialPlanDetail,
  trialPlanningIds,
  trialPlanningWorkspace,
} from "../support/trial-planning-fixture";
import { trialQualityWorkspace } from "../support/trial-quality-fixture";
import { emptyTrialReviewWorkspace } from "../support/trial-review-fixture";
import { emptyReleasedTrialSummaryWorkspace } from "../support/released-trial-summary-fixture";
import {
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const csrfToken = "p7-08-mobile-field-browser-csrf-token-0001";
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const trialEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/(?:trials|trial-plans(?:\/.*)?|trial-rounds(?:\/.*|:[^/?]+))$/u;
const gateReviewEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/gates\/[^/?]+\/review(?:\?.*)?$/u;
const submitGateReviewEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/gates\/[^/?]+\/review-cycles\/[^/?]+\/reviews(?:\?.*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

interface ObservedRequest {
  readonly contentType: string | undefined;
  readonly csrf: string | undefined;
  readonly idempotencyKey: string | undefined;
  readonly method: string;
  readonly path: string;
  readonly payload: unknown;
}

interface ApiOptions {
  readonly execution?: TrialExecutionWorkspace;
  readonly quality?: TrialQualityWorkspace;
}

interface GateReviewSubmitPayload {
  readonly expectedCycleVersion: number;
  readonly expectedInputHash: string;
  readonly opinion: string;
  readonly outcome: GateReviewOutcome;
  readonly stepKey: string;
}

function isGateReviewSubmitPayload(
  value: unknown,
): value is GateReviewSubmitPayload {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.expectedCycleVersion === "number" &&
    typeof candidate.expectedInputHash === "string" &&
    typeof candidate.opinion === "string" &&
    (candidate.outcome === "approved" || candidate.outcome === "rejected") &&
    typeof candidate.stepKey === "string"
  );
}

function submittedGateReviewView(
  view: GateReviewViewModel,
  body: GateReviewSubmitPayload,
): GateReviewViewModel {
  const cycle = view.activeCycle;
  if (!cycle)
    throw new Error("The Gate field fixture requires an active cycle.");
  return {
    ...view,
    activeCycle: {
      ...cycle,
      selectedSteps: cycle.selectedSteps.map((step) => {
        if (step.stepKey === body.stepKey) {
          return {
            ...step,
            review: {
              actor: step.assignedMember.userId,
              globalId: "d1d1d1d1-d1d1-4d1d-8d1d-d1d1d1d1d1d1",
              inputHash: body.expectedInputHash,
              opinion: body.opinion.trim(),
              outcome: body.outcome,
              reviewedAt: "2026-08-15T16:00:00Z",
              snapshotHash: "d".repeat(64),
              stepKey: step.stepKey,
            },
            state: body.outcome,
          };
        }
        if (step.sequence === 2 && body.outcome === "approved") {
          return { ...step, state: "available" as const };
        }
        return step;
      }),
      version: body.expectedCycleVersion + 1,
    },
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
  replayed?: boolean,
  traceId = "trace-p7-08-mobile-field-browser",
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
      "X-Trace-ID": traceId,
    },
    status,
  });
}

async function installSession(
  page: Page,
  locale: TestLocale,
  userId = "field.engineer@example.invalid",
): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "8".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId,
    });
  });
}

async function installGateReviewApi(
  page: Page,
  view: GateReviewViewModel,
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(gateReviewEndpoint, async (route) => {
    const request = route.request();
    observed.push({
      contentType: request.headers()["content-type"],
      csrf: request.headers()["x-frappe-csrf-token"],
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path: new URL(request.url()).pathname,
      payload: null,
    });
    await fulfillJson(route, view);
  });
  return observed;
}

async function installTrialApi(
  page: Page,
  options: ApiOptions = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const execution = options.execution ?? trialExecutionWorkspace();
  const quality = options.quality ?? trialQualityWorkspace();
  await page.route(trialEndpoint, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const isFileUpload = request.method() === "POST" && path.endsWith("/files");
    const payload: unknown =
      request.method() === "POST" && !isFileUpload
        ? request.postDataJSON()
        : null;
    observed.push({
      contentType: request.headers()["content-type"],
      csrf: request.headers()["x-frappe-csrf-token"],
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path,
      payload,
    });

    if (isFileUpload) {
      await fulfillJson(
        route,
        trialExecutionWorkspace({
          pendingFiles: [
            ...execution.pendingFiles,
            {
              fileName: "field-photo.png",
              globalId: "10000000-0000-4000-8000-00000000000e",
              mimeType: "image/png",
              optimisticVersion: 1,
              privacy: "private",
              scanState: "pending",
              sha256: "8".repeat(64),
              sizeBytes: 16,
            },
          ],
        }),
        201,
        false,
      );
      return;
    }
    if (request.method() === "POST" && path.endsWith("/defects")) {
      await fulfillJson(route, quality, 201, false);
      return;
    }
    if (request.method() === "GET" && path.endsWith("/trials")) {
      await fulfillJson(route, trialPlanningWorkspace());
      return;
    }
    if (request.method() === "GET" && path.endsWith("/execution")) {
      await fulfillJson(route, execution);
      return;
    }
    if (request.method() === "GET" && path.endsWith("/quality")) {
      await fulfillJson(route, quality);
      return;
    }
    if (request.method() === "GET" && path.endsWith("/review")) {
      await fulfillJson(route, emptyTrialReviewWorkspace(quality.trialRound));
      return;
    }
    if (
      request.method() === "GET" &&
      path.endsWith("/released-trial-summaries")
    ) {
      await fulfillJson(route, emptyReleasedTrialSummaryWorkspace());
      return;
    }
    if (request.method() === "GET") {
      await fulfillJson(route, trialPlanDetail());
      return;
    }
    throw new Error(
      `Unexpected P7-08 browser request: ${request.method()} ${path}`,
    );
  });
  return observed;
}

async function openFieldWorkspace(
  page: Page,
  locale: TestLocale,
  viewport: { readonly height: number; readonly width: number },
): Promise<void> {
  await page.setViewportSize(viewport);
  await page.goto(
    `/projects/${trialPlanningIds.project}/trials?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.getByTestId("mobile-trial-field-summary")).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include(".trial-live")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function openGateFieldWorkspace(
  page: Page,
  locale: TestLocale,
  viewport: { readonly height: number; readonly width: number },
): Promise<void> {
  await page.setViewportSize(viewport);
  await page.goto(
    `/projects/${trialPlanningIds.project}/gates/44444444-4444-4444-8444-444444444444?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator(".gate-review-room")).toBeVisible();
}

async function expectGateAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include(".gate-review-room")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

function posted(observed: readonly ObservedRequest[]): ObservedRequest[] {
  return observed.filter((request) => request.method === "POST");
}

test.describe("P7-08 live Trial mobile field actions", () => {
  const responsiveCases = [
    { locale: "en", viewport: { height: 844, width: 390 } },
    { locale: "zh", viewport: { height: 1024, width: 768 } },
    { locale: "zh-TW", viewport: { height: 844, width: 390 } },
  ] as const;

  for (const responsive of responsiveCases) {
    test(`shows bounded field truth and desktop handoff in ${responsive.locale} at ${String(responsive.viewport.width)}px`, async ({
      page,
    }) => {
      await installSession(page, responsive.locale);
      await installTrialApi(page);
      await openFieldWorkspace(page, responsive.locale, responsive.viewport);

      const summary = page.getByTestId("mobile-trial-field-summary");
      await expect(summary).toContainText(trialPlanningIds.project);
      await expect(summary).toContainText(trialPlanningIds.plan);
      await expect(page.locator(".mobile-engineering-handoff")).toBeVisible();
      await expect(
        page.getByRole("table", { name: "Proposed resources" }),
      ).toBeHidden();
      await expectNoMixedLanguage(page, responsive.locale);
      await expectNoDocumentOverflow(page);
      await expect(summary).toHaveCSS("border-radius", "0px");
      await expectAxeClean(page);
    });
  }

  test("shows pending, clean, failed and permission truth without inventing an upload action", async ({
    page,
  }) => {
    const base = trialExecutionWorkspace();
    const pending = base.pendingFiles[0];
    if (!pending) throw new Error("P7-08 requires one pending file fixture.");
    const execution = trialExecutionWorkspace({
      pendingFiles: [
        pending,
        {
          ...pending,
          fileName: "clean-field-photo.png",
          globalId: "10000000-0000-4000-8000-00000000000e",
          mimeType: "image/png",
          scanState: "clean",
        },
        {
          ...pending,
          fileName: "failed-field-photo.png",
          globalId: "10000000-0000-4000-8000-00000000000f",
          mimeType: "image/png",
          scanState: "failed",
        },
      ],
      permissions: { ...base.permissions, canManageEvidence: false },
    });
    await installSession(page, "en");
    await installTrialApi(page, { execution });
    await openFieldWorkspace(page, "en", { height: 844, width: 390 });

    const summary = page.getByTestId("mobile-trial-field-summary");
    await expect(
      summary
        .locator("dt", { hasText: "Files not in clean state" })
        .locator(".."),
    ).toContainText("2");
    await expect(
      summary.locator("dt", { hasText: "Evidence photo action" }).locator(".."),
    ).toContainText("Unavailable");
    await expect(
      summary.locator("dt", { hasText: "Open blocking defects" }).locator(".."),
    ).toContainText("1");
    await expect(page.getByText("Pending scan", { exact: true })).toBeVisible();
    await expect(page.getByText("Clean", { exact: true })).toBeVisible();
    await expect(page.getByText("Scan failed", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Upload private evidence file" }),
    ).toHaveCount(0);
    await expectNoDocumentOverflow(page);
  });

  test("keeps a camera-facing photo local until explicit private upload", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installTrialApi(page);
    await openFieldWorkspace(page, "en", { height: 844, width: 390 });

    await page
      .getByRole("button", { name: "Upload private evidence file" })
      .click();
    const input = page.locator("#trial-evidence-photo");
    await expect(input).toHaveAttribute("accept", "image/*");
    await expect(input).toHaveAttribute("capture", "environment");
    await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();
    await input.setInputFiles({
      buffer: Buffer.from("field-photo-bytes"),
      mimeType: "image/png",
      name: "field-photo.png",
    });
    await expect(
      page.getByText("Local selection", { exact: true }),
    ).toBeVisible();
    expect(posted(observed)).toHaveLength(0);

    await page.getByRole("button", { name: "Clear local selection" }).click();
    await expect(
      page.getByText("No local selection", { exact: true }),
    ).toBeVisible();
    expect(posted(observed)).toHaveLength(0);

    await input.setInputFiles({
      buffer: Buffer.from("field-photo-bytes"),
      mimeType: "image/png",
      name: "field-photo.png",
    });
    await page.getByRole("button", { name: "Start file transport" }).click();
    await expect(
      page.getByText(
        "The execution command completed with immutable audit truth.",
      ),
    ).toBeVisible();

    const upload = posted(observed).find((request) =>
      request.path.endsWith("/files"),
    );
    expect(upload).toMatchObject({
      contentType: expect.stringContaining("multipart/form-data"),
      csrf: csrfToken,
      idempotencyKey: expect.stringMatching(/^trial-evidence-upload-/u),
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-rounds/${trialPlanningIds.round}/files`,
    });
  });

  test("applies a reviewed cavity without submitting, then records the unchanged defect command", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installTrialApi(page);
    await openFieldWorkspace(page, "en", { height: 1024, width: 768 });

    await page.getByRole("button", { name: "Record Trial defect" }).click();
    await page.getByLabel("Scanned value").fill(trialExecutionIds.cavity);
    const reviewScan = page.getByRole("button", {
      name: "Review scanned value",
    });
    const reviewScanBox = await reviewScan.boundingBox();
    expect(reviewScanBox?.height).toBeGreaterThanOrEqual(44);
    await reviewScan.click();
    await expect(
      page.getByText("Ready to use. No command has been submitted."),
    ).toBeVisible();
    await page.getByRole("button", { name: "Use reviewed value" }).click();
    await expect(page.getByLabel("Cavity stable ID")).toHaveValue(
      trialExecutionIds.cavity,
    );
    expect(posted(observed)).toHaveLength(0);

    await page.getByLabel("Defect code").fill("DEF-FIELD-001");
    await page.getByLabel("Title").fill("Field-observed short shot");
    await page.getByLabel("Category key").fill("short_shot");
    await page.getByLabel("Location").fill("Rib end");
    await page
      .getByLabel("Description")
      .fill("The operator observed a short shot during the active Trial.");
    await page.getByRole("button", { name: "Review command" }).click();
    const review = page.getByRole("dialog", {
      name: "Review immutable Trial quality command",
    });
    await review
      .getByLabel("Reason")
      .fill("Record the reviewed field observation against the exact cavity");
    await review.getByRole("button", { name: "Record Trial defect" }).click();
    await expect(
      page.getByText(
        "The quality command completed with immutable audit truth.",
      ),
    ).toBeVisible();

    const defect = posted(observed).find((request) =>
      request.path.endsWith("/defects"),
    );
    expect(defect).toMatchObject({
      csrf: csrfToken,
      idempotencyKey: expect.stringMatching(/^trial-quality-/u),
      path: `/api/npi/v1/projects/${trialPlanningIds.project}/trial-rounds/${trialPlanningIds.round}/defects`,
      payload: expect.objectContaining({
        cavityGlobalId: trialExecutionIds.cavity,
        businessCode: "DEF-FIELD-001",
      }),
    });
  });
});

test.describe("P7-08 live Gate mobile field review", () => {
  const responsiveCases = [
    { locale: "en", viewport: { height: 844, width: 390 } },
    { locale: "zh", viewport: { height: 1024, width: 768 } },
    { locale: "zh-TW", viewport: { height: 844, width: 390 } },
  ] as const;

  for (const responsive of responsiveCases) {
    test(`shows exact Gate authority and blocker truth in ${responsive.locale} at ${String(responsive.viewport.width)}px`, async ({
      page,
    }) => {
      const locale = responsive.locale;
      const view = gateReviewFixture();
      await installSession(page, locale, "reviewer@example.invalid");
      await installGateReviewApi(page, view);
      await openGateFieldWorkspace(page, locale, responsive.viewport);

      const summary = page.getByTestId("mobile-gate-field-summary");
      await expect(summary).toBeVisible();
      await expect(summary).toContainText(view.project.globalId);
      await expect(summary).toContainText(view.gate.globalId);
      await expect(summary).toContainText(view.activeCycle?.globalId ?? "");
      await expect(summary).toContainText(
        view.activeCycle?.policyRef.globalId ?? "",
      );
      await expect(summary).toContainText(
        "Synthetic unresolved dimensional issue",
      );
      await expect(summary).toContainText(
        translate(locale, "The assigned decision authority is required."),
      );
      await expect(summary).toContainText(
        translate(locale, "Downstream use denied"),
      );
      await expect(summary).toContainText(translate(locale, "Submit review"));
      await expect(
        page.getByRole("table", {
          name: translate(locale, "Frozen Gate requirements"),
        }),
      ).toBeHidden();
      const inspector = page.getByRole("complementary", {
        name: translate(locale, "Review inspector"),
      });
      await expect(inspector).toBeVisible();
      await expect(
        page.getByRole("button", {
          name: translate(locale, "Submit review"),
        }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: translate(locale, "Decide Gate") }),
      ).toHaveCount(0);
      await expect(
        page.locator('[data-visual-primary="true"]:visible'),
      ).toHaveCount(1);
      await expect(page.locator(".mobile-engineering-handoff")).toBeVisible();
      expect(
        await summary.evaluate(
          (element) => globalThis.getComputedStyle(element).borderRadius,
        ),
      ).toBe("0px");
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectGateAxeClean(page);
    });
  }

  test("submits one already-authorized phone review through the unchanged command boundary", async ({
    page,
  }) => {
    const view = gateReviewFixture();
    const observed: ObservedRequest[] = [];
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await installSession(page, "en", "reviewer@example.invalid");
    await installGateReviewApi(page, view);
    await page.route(submitGateReviewEndpoint, async (route) => {
      const request = route.request();
      const payload: unknown = request.postDataJSON();
      if (!isGateReviewSubmitPayload(payload)) {
        throw new Error("The Gate field fixture received an invalid command.");
      }
      observed.push({
        contentType: request.headers()["content-type"],
        csrf: request.headers()["x-frappe-csrf-token"],
        idempotencyKey: request.headers()["idempotency-key"],
        method: request.method(),
        path: new URL(request.url()).pathname,
        payload,
      });
      await responseMayComplete;
      await fulfillJson(
        route,
        submittedGateReviewView(view, payload),
        200,
        false,
      );
    });
    await openGateFieldWorkspace(page, "en", { height: 844, width: 390 });

    await page
      .getByRole("textbox", { name: "Complete review opinion" })
      .fill("Exact field review completed against the frozen input.");
    await page.getByRole("button", { name: "Submit review" }).click();

    await expect.poll(() => observed.length).toBe(1);
    const processingAction = page.locator(
      '[data-visual-primary="true"]:visible',
    );
    await expect(processingAction).toHaveText("Processing Gate review command");
    await expect(processingAction).toHaveAttribute("disabled");
    expect(observed[0]).toMatchObject({
      csrf: csrfToken,
      method: "POST",
      payload: {
        expectedCycleVersion: view.activeCycle?.version,
        expectedInputHash: view.activeCycle?.inputHash,
        opinion: "Exact field review completed against the frozen input.",
        outcome: "approved",
        stepKey: "ENGINEERING_REVIEW",
      },
    });
    expect(observed[0]?.idempotencyKey).toMatch(/^gate-review:/u);

    releaseResponse?.();
    await expect(
      page.getByText("Server confirmed", { exact: true }),
    ).toBeVisible();
  });

  test("keeps a phone read-only review free of command actions", async ({
    page,
  }) => {
    const view = gateReviewReadOnlyFixture();
    const observed = await installGateReviewApi(page, view);
    await installSession(page, "en", "reviewer@example.invalid");
    await openGateFieldWorkspace(page, "en", { height: 844, width: 390 });

    const summary = page.getByTestId("mobile-gate-field-summary");
    await expect(summary).toContainText("No permitted review action");
    await expect(
      page.getByRole("button", { name: "Submit review" }),
    ).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Decide Gate" })).toHaveCount(
      0,
    );
    expect(
      observed.filter((request) => request.method === "POST"),
    ).toHaveLength(0);
  });

  test("keeps protected Gate truth absent from a denied phone", async ({
    page,
  }) => {
    await installSession(page, "en", "reviewer@example.invalid");
    await page.route(gateReviewEndpoint, async (route) => {
      await fulfillJson(
        route,
        {
          code: "GATE_REVIEW_ACCESS_DENIED",
          retryable: false,
          status: 403,
          title: "Gate review access is not available",
          traceId: "trace-p7-08-gate-denied",
          type: "urn:npi:problem:gate_review_access_denied",
        },
        403,
        undefined,
        "trace-p7-08-gate-denied",
      );
    });
    await page.setViewportSize({ height: 844, width: 390 });
    await page.goto(
      `/projects/${trialPlanningIds.project}/gates/44444444-4444-4444-8444-444444444444?lang=en`,
      { waitUntil: "domcontentloaded" },
    );
    await expect(page.locator(".route-loading")).toHaveCount(0);

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "Gate review access is not available",
      }),
    ).toBeVisible();
    await expect(page.getByTestId("mobile-gate-field-summary")).toHaveCount(0);
    await expect(page.getByText("Synthetic initiation evidence")).toHaveCount(
      0,
    );
    await expect(
      page.getByRole("button", { name: "Submit review" }),
    ).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Decide Gate" })).toHaveCount(
      0,
    );
  });

  test("fails a stale phone review closed without exposing another command", async ({
    page,
  }) => {
    const view = gateReviewFixture();
    await installSession(page, "en", "reviewer@example.invalid");
    await installGateReviewApi(page, view);
    await page.route(submitGateReviewEndpoint, async (route) => {
      await fulfillJson(
        route,
        {
          code: "GATE_REVIEW_VERSION_CONFLICT",
          retryable: false,
          status: 409,
          title: "Version conflict",
          traceId: "trace-p7-08-gate-conflict",
          type: "urn:npi:problem:gate_review_version_conflict",
        },
        409,
        undefined,
        "trace-p7-08-gate-conflict",
      );
    });
    await openGateFieldWorkspace(page, "en", { height: 844, width: 390 });
    await page
      .getByRole("textbox", { name: "Complete review opinion" })
      .fill("This stale review must fail closed.");
    await page.getByRole("button", { name: "Submit review" }).click();

    await expect(
      page.getByRole("alert", { name: "Gate review command failure" }),
    ).toContainText("trace-p7-08-gate-conflict");
    await expect(
      page.getByRole("button", { name: "Reload Gate review" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Submit review" }),
    ).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Decide Gate" })).toHaveCount(
      0,
    );
  });
});

test.describe("@visual P7-08 Gate mobile field evidence", () => {
  const cases = [
    {
      locale: "en",
      name: "p7-08-gate-field-en-390x844",
      viewport: { height: 844, width: 390 },
    },
    {
      locale: "zh",
      name: "p7-08-gate-field-zh-768x1024",
      viewport: { height: 1024, width: 768 },
    },
    {
      locale: "zh-TW",
      name: "p7-08-gate-field-zh-TW-390x844",
      viewport: { height: 844, width: 390 },
    },
  ] as const;

  for (const visualCase of cases) {
    test(`@visual ${visualCase.name}`, async ({ page }) => {
      await installSession(page, visualCase.locale, "reviewer@example.invalid");
      await installGateReviewApi(page, gateReviewFixture());
      await openGateFieldWorkspace(
        page,
        visualCase.locale,
        visualCase.viewport,
      );
      await expect(page.getByTestId("mobile-gate-field-summary")).toBeVisible();

      await expect(page.locator("#main-content")).toHaveScreenshot(
        `${visualCase.name}.png`,
        { animations: "disabled" },
      );
    });
  }

  test("@visual p7-08-gate-desktop-engineering-guard-en-1440x900", async ({
    page,
  }) => {
    await installSession(page, "en", "reviewer@example.invalid");
    await installGateReviewApi(page, gateReviewFixture());
    await openGateFieldWorkspace(page, "en", { height: 900, width: 1440 });

    await expect(page.getByTestId("mobile-gate-field-summary")).toBeHidden();
    await expect(
      page.getByRole("table", { name: "Frozen Gate requirements" }),
    ).toBeVisible();
    await expect(page.locator(".mobile-engineering-handoff")).toBeHidden();
    await expect(page.locator("#main-content")).toHaveScreenshot(
      "p7-08-gate-desktop-engineering-guard-en-1440x900.png",
      { animations: "disabled" },
    );
  });
});
