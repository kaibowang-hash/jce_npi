import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ProblemDetails } from "../../src/api/http";
import type {
  GateReviewOutcome,
  GateReviewViewModel,
} from "../../src/domain/view-models";
import { translate } from "../../src/i18n/runtime";
import {
  gateReviewFixture,
  gateReviewRequiresReviewFixture,
} from "../support/gate-review-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectGlobalId = "11111111-1111-4111-8111-111111111111";
const gateGlobalId = "44444444-4444-4444-8444-444444444444";
const csrfToken = "c".repeat(32);
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const reviewEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/gates\/[^/?]+\/review(?:\?.*)?$/u;
const submitReviewEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/gates\/[^/?]+\/review-cycles\/[^/?]+\/reviews(?:\?.*)?$/u;
const receiptEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/gates\/[^/?]+\/review-command-receipts\/gate\.review\.submit(?:\?.*)?$/u;

interface ObservedRequest {
  body: unknown;
  csrf: string | undefined;
  idempotencyKey: string | undefined;
  method: string;
  requestId: string;
  url: string;
}

interface SubmitReviewBody {
  expectedCycleVersion: number;
  expectedInputHash: string;
  opinion: string;
  outcome: GateReviewOutcome;
  stepKey: string;
}

function activeCycle(view: GateReviewViewModel) {
  if (!view.activeCycle) {
    throw new Error("The browser fixture requires an active review cycle.");
  }
  return view.activeCycle;
}

function isSubmitReviewBody(value: unknown): value is SubmitReviewBody {
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

function submittedReviewView(
  view: GateReviewViewModel,
  body: SubmitReviewBody,
): GateReviewViewModel {
  const cycle = activeCycle(view);
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
              reviewedAt: "2026-07-24T10:08:00Z",
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

function problem(
  status: number,
  code: string,
  traceId: string,
  retryable = false,
): ProblemDetails {
  return {
    code,
    retryable,
    status,
    title: "The protected Gate review request could not be completed.",
    traceId,
    type: `urn:npi:problem:${code.toLowerCase()}`,
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
      "X-Trace-ID": options.traceId ?? "trace-gate-review-success",
    },
    status,
  });
}

async function installSession(
  page: Page,
  locale: TestLocale,
  userId = "reviewer@example.invalid",
): Promise<void> {
  await page.route(
    /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u,
    async (route) => {
      await fulfillApi(route, {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: {
          language: locale,
          messages: {},
          version: "f".repeat(64),
        },
        csrfToken,
        language: locale,
        userId,
      });
    },
  );
}

async function installReview(
  page: Page,
  view: GateReviewViewModel,
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(reviewEndpoint, async (route) => {
    const headers = route.request().headers();
    const requestId = headers["x-request-id"] ?? "";
    observed.push({
      body: null,
      csrf: headers["x-frappe-csrf-token"],
      idempotencyKey: headers["idempotency-key"],
      method: route.request().method(),
      requestId,
      url: route.request().url(),
    });
    await fulfillApi(route, view);
  });
  return observed;
}

async function openGate(
  page: Page,
  locale: TestLocale = "en",
  projectId = projectGlobalId,
): Promise<void> {
  await page.goto(
    `/projects/${projectId}/gates/${gateGlobalId}?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
}

async function expectReviewRoomLoaded(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: /Synthetic initiation evidence/u,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Frozen Gate requirements" }),
  ).toBeVisible();
}

test.describe("live Gate Review Room", () => {
  test("renders one dense three-pane workspace with embedded controlled evidence", async ({
    page,
  }) => {
    await installSession(page, "en");
    const requests = await installReview(page, gateReviewFixture());
    await openGate(page);
    await expectReviewRoomLoaded(page);

    await expect(
      page.getByRole("table", { name: "Selected review steps" }),
    ).toBeVisible();
    await expect(
      page.getByRole("complementary", { name: "Review inspector" }),
    ).toBeVisible();
    await expect(page.getByText("Waiting for prior sequence")).toBeVisible();
    await expect(
      page.getByText("Synthetic unresolved dimensional issue"),
    ).toBeVisible();
    await page
      .getByRole("button", {
        name: /DIMENSIONAL_REPORT Synthetic dimensional report/u,
      })
      .click();
    await expect(page.getByText("SYN-DIMENSIONAL-REPORT.pdf")).toBeVisible();
    await expect(page.getByText("/private/files/")).toHaveCount(0);
    await expect(
      page.locator('[data-visual-primary="true"]:visible'),
    ).toHaveCount(1);
    await expectNoMixedLanguage(page, "en");

    expect(requests.length).toBeGreaterThanOrEqual(1);
    expect(requests[0]).toMatchObject({
      csrf: undefined,
      idempotencyKey: undefined,
      method: "GET",
      url: `http://127.0.0.1:4173/api/npi/v1/projects/${projectGlobalId}/gates/${gateGlobalId}/review`,
    });
  });

  test("keeps one assigned review processing until a validated server response arrives", async ({
    page,
  }) => {
    const fixture = gateReviewFixture();
    const commandRequests: ObservedRequest[] = [];
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await installSession(page, "en");
    await installReview(page, fixture);
    await page.route(submitReviewEndpoint, async (route) => {
      const headers = route.request().headers();
      const body: unknown = route.request().postDataJSON();
      if (!isSubmitReviewBody(body)) {
        throw new Error("The browser submitted an invalid review command.");
      }
      commandRequests.push({
        body,
        csrf: headers["x-frappe-csrf-token"],
        idempotencyKey: headers["idempotency-key"],
        method: route.request().method(),
        requestId: headers["x-request-id"] ?? "",
        url: route.request().url(),
      });
      await responseMayComplete;
      await fulfillApi(route, submittedReviewView(fixture, body), {
        idempotencyReplayed: false,
      });
    });
    await openGate(page);
    await expectReviewRoomLoaded(page);

    await page
      .getByRole("textbox", { name: "Complete review opinion" })
      .fill("The exact synthetic input is acceptable.");
    await page.getByRole("button", { name: "Submit review" }).click();

    await expect(
      page.getByText("Processing Gate review command"),
    ).toBeVisible();
    await expect(page.getByText("Server confirmed")).toHaveCount(0);
    await expect.poll(() => commandRequests.length).toBe(1);
    await expect(
      page.locator('[data-visual-primary="true"]:visible'),
    ).toHaveAttribute("disabled");

    releaseResponse?.();
    await expect(
      page.getByText("Server confirmed", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Selected review steps" }),
    ).toContainText("Approved");
    expect(commandRequests).toHaveLength(1);
    expect(commandRequests[0]).toMatchObject({
      body: {
        expectedCycleVersion: activeCycle(fixture).version,
        expectedInputHash: activeCycle(fixture).inputHash,
        opinion: "The exact synthetic input is acceptable.",
        outcome: "approved",
        stepKey: "ENGINEERING_REVIEW",
      },
      csrf: csrfToken,
      method: "POST",
    });
    expect(commandRequests[0]?.idempotencyKey).toMatch(/^gate-review:/u);
    expect(commandRequests[0]?.requestId).toMatch(requestIdPattern);
  });

  test("reconciles a committed command after a hard browser reload loses the response", async ({
    page,
  }) => {
    const initial = gateReviewFixture();
    let authoritative = initial;
    let commandCount = 0;
    let receiptCount = 0;
    let commandKey = "";
    await installSession(page, "en");
    await page.route(reviewEndpoint, async (route) => {
      await fulfillApi(route, authoritative);
    });
    await page.route(submitReviewEndpoint, async (route) => {
      const body: unknown = route.request().postDataJSON();
      if (!isSubmitReviewBody(body)) {
        throw new Error("The browser submitted an invalid review command.");
      }
      commandCount += 1;
      commandKey = route.request().headers()["idempotency-key"] ?? "";
      authoritative = submittedReviewView(initial, body);
      await route.abort("connectionfailed");
    });
    await page.route(receiptEndpoint, async (route) => {
      receiptCount += 1;
      expect(route.request().method()).toBe("GET");
      expect(route.request().headers()["idempotency-key"]).toBe(commandKey);
      await fulfillApi(route, {
        operation: "gate.review.submit",
        status: "completed",
        workspaceReloadRequired: true,
      });
    });
    await openGate(page);
    await expectReviewRoomLoaded(page);

    await page
      .getByRole("textbox", { name: "Complete review opinion" })
      .fill("The committed review response was lost during navigation.");
    await page.getByRole("button", { name: "Submit review" }).click();
    await expect.poll(() => commandCount).toBe(1);
    await expect(page.getByText("Retryable failure")).toBeVisible();

    await page.reload({ waitUntil: "domcontentloaded" });

    await expectReviewRoomLoaded(page);
    await expect(
      page.getByText("The server confirmed the review workspace update."),
    ).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Selected review steps" }),
    ).toContainText("Approved");
    expect(commandCount).toBe(1);
    expect(receiptCount).toBe(1);
    expect(commandKey).toMatch(/^gate-review:/u);
    await expect
      .poll(() =>
        page.evaluate(() =>
          globalThis.sessionStorage.getItem(
            "npi-one:gate-review-command-receipt",
          ),
        ),
      )
      .toBeNull();
  });

  test("hard reload bounds absent receipt checks and requires fresh command inputs", async ({
    page,
  }) => {
    const fixture = gateReviewFixture();
    let receiptCount = 0;
    let commandCount = 0;
    await page.addInitScript(
      ({ gate, project }) => {
        globalThis.sessionStorage.setItem(
          "npi-one:gate-review-command-receipt",
          JSON.stringify({
            actor: "reviewer@example.invalid",
            gate,
            issuedAt: "2026-07-24T09:30:00.000Z",
            key: "gate-review:11111111-1111-4111-8111-111111111111",
            operation: "gate.review.submit",
            project,
          }),
        );
      },
      { gate: gateGlobalId, project: projectGlobalId },
    );
    await installSession(page, "en");
    await installReview(page, fixture);
    await page.route(submitReviewEndpoint, async (route) => {
      commandCount += 1;
      await route.abort("failed");
    });
    await page.route(receiptEndpoint, async (route) => {
      receiptCount += 1;
      await fulfillApi(route, {
        operation: "gate.review.submit",
        status: "absent",
        workspaceReloadRequired: true,
      });
    });

    await openGate(page);
    await expectReviewRoomLoaded(page);

    await expect(
      page.getByText(
        "No completed command record was found yet. The workspace was reloaded; verify its current state and re-enter the command inputs before submitting again.",
      ),
    ).toBeVisible();
    expect(receiptCount).toBe(4);
    expect(commandCount).toBe(0);
    await expect(
      page.getByRole("textbox", { name: "Complete review opinion" }),
    ).toHaveValue("");
  });

  test("requires review exposes only exact input-change acknowledgement", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installReview(page, gateReviewRequiresReviewFixture());
    await openGate(page);
    await expectReviewRoomLoaded(page);

    await expect(
      page.getByText("Gate input snapshot changed").first(),
    ).toBeVisible();
    await expect(page.getByText("Decision invalidated")).toBeVisible();
    await expect(page.getByText("5".repeat(64)).first()).toBeVisible();
    await expect(page.getByText("c".repeat(64)).first()).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: "Acknowledge change and start review",
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Submit review" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /^Request exception:/u }),
    ).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Decide Gate" })).toHaveCount(
      0,
    );
    await expect(
      page.locator('[data-visual-primary="true"]:visible'),
    ).toHaveCount(1);
  });

  test("keeps protected Gate review data hidden on authorization failure", async ({
    page,
  }) => {
    const traceId = "trace-gate-review-denied";
    await installSession(page, "en");
    await page.route(reviewEndpoint, async (route) => {
      await fulfillApi(
        route,
        problem(403, "GATE_REVIEW_ACCESS_DENIED", traceId),
        { status: 403, traceId },
      );
    });
    await openGate(page);

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "Gate review access is not available",
      }),
    ).toBeVisible();
    await expect(page.getByText(traceId)).toBeVisible();
    await expect(page.getByText("Synthetic initiation evidence")).toHaveCount(
      0,
    );
    await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
  });

  test("fails closed when the review response contains an unknown field", async ({
    page,
  }) => {
    const traceId = "trace-gate-review-invalid";
    await installSession(page, "en");
    await page.route(reviewEndpoint, async (route) => {
      await fulfillApi(
        route,
        { ...gateReviewFixture(), untrustedDebugField: true },
        { traceId },
      );
    });
    await openGate(page);

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The Gate review response could not be used safely",
      }),
    ).toBeVisible();
    await expect(page.getByText(traceId)).toBeVisible();
    await expect(page.getByText("Synthetic initiation evidence")).toHaveCount(
      0,
    );
  });

  test("supports keyboard review selection and has no serious accessibility violations", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installReview(page, gateReviewFixture());
    await openGate(page);
    await expectReviewRoomLoaded(page);

    const dimensionalRequirement = page.getByRole("button", {
      name: /DIMENSIONAL_REPORT Synthetic dimensional report/u,
    });
    await dimensionalRequirement.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByText("SYN-DIMENSIONAL-REPORT.pdf")).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
    await expectIndustrialComputedStyles(page);
    await expectNoDocumentOverflow(page);
  });

  test("rejects an invalid route identity before requesting protected review data", async ({
    page,
  }) => {
    await installSession(page, "en");
    const requests = await installReview(page, gateReviewFixture());
    await openGate(page, "en", "not-a-uuid");

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "The Gate review address is invalid",
      }),
    ).toBeVisible();
    await expect(page.locator(".trace-reference code")).toContainText(
      /^client-/u,
    );
    expect(requests).toHaveLength(0);
  });
});

test.describe("trilingual Gate Review Room state purity", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders the accepted review state without mixed language in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installReview(page, gateReviewFixture());
      await openGate(page, locale);
      await expect(
        page.getByRole("table", {
          name: translate(locale, "Frozen Gate requirements"),
        }),
      ).toBeVisible();
      await expect(
        page.getByRole("complementary", {
          name: translate(locale, "Review inspector"),
        }),
      ).toBeVisible();
      await expectNoMixedLanguage(page, locale);
    });
  }
});

interface ReviewRoomVisualCase {
  height: number;
  locale: TestLocale;
  name: string;
  width: number;
  zoom: 1 | 1.25 | 1.5;
}

const reviewRoomVisualCases: readonly ReviewRoomVisualCase[] = [
  {
    height: 768,
    locale: "en",
    name: "gate-review-room-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh",
    name: "gate-review-room-zh-1920x1080-125",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "gate-review-room-zh-TW-1366x768-150",
    width: 1366,
    zoom: 1.5,
  },
];

test.describe("@visual live Gate Review Room", () => {
  for (const fixture of reviewRoomVisualCases) {
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
      await installSession(page, fixture.locale);
      await installReview(page, gateReviewFixture());
      await openGate(page, fixture.locale);
      await expect(
        page.getByRole("table", {
          name: translate(fixture.locale, "Frozen Gate requirements"),
        }),
      ).toBeVisible();
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
