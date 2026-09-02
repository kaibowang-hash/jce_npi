import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ProblemDetails } from "../../src/api/http";
import type {
  GateReviewDecisionBlockedReasonCode,
  GateReviewOutcome,
  GateReviewViewModel,
} from "../../src/domain/view-models";
import { translate } from "../translate";
import { documentBaselineWorkspaceFixture } from "../support/document-fixture";
import {
  gateReviewDecidedFixture,
  gateReviewDecisionReadyFixture,
  gateReviewExceptionEligibleFixture,
  gateReviewExceptionHistoryFixture,
  gateReviewFixture,
  gateReviewNoCycleFixture,
  gateReviewPendingExceptionFixture,
  gateReviewReadOnlyFixture,
  gateReviewReopenedFixture,
  gateReviewRequiresReviewFixture,
} from "../support/gate-review-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  expectSinglePrimaryAction,
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
const documentBaselinesEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/document-baselines(?:\?.*)?$/u;
const attachEvidenceEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/gates\/[^/?]+\/requirements\/[^/?]+\/evidence(?:\?.*)?$/u;
const browserDecisionBlockedReasonCases = [
  ["REQUIRED_P0_EVIDENCE_MISSING", "Required P0 evidence is missing."],
  ["FILE_EVIDENCE_UNSAFE", "File evidence is not safe and current."],
  ["GATE_BLOCKED", "Resolve every blocking item before this outcome."],
  ["GATE_INPUT_CHANGED", "The Gate input changed."],
] as const satisfies readonly (readonly [
  GateReviewDecisionBlockedReasonCode,
  string,
])[];
const commandFailureAccessibilityCases = [
  {
    code: "REQUEST_VALIDATION_FAILED",
    failureSource: "Validation error",
    name: "validation",
    retryable: false,
    status: 422,
    writeSource: "No successful write was confirmed for this command.",
  },
  {
    code: "GATE_REVIEW_VERSION_CONFLICT",
    failureSource: "Version conflict",
    name: "conflict",
    retryable: false,
    status: 409,
    writeSource: "No successful write was confirmed for this command.",
  },
  {
    code: "GATE_REVIEW_UNAVAILABLE",
    failureSource: "Retryable failure",
    name: "retryable",
    retryable: true,
    status: 503,
    writeSource: "No successful write was confirmed for this command.",
  },
  {
    code: "GATE_REVIEW_FINAL_FAILURE",
    failureSource: "Final failure",
    name: "final",
    retryable: false,
    status: 500,
    writeSource: "No successful write was confirmed for this command.",
  },
] as const;

function syntheticReviewOpinion(locale: TestLocale): string {
  return locale === "en"
    ? "Synthetic controlled review opinion."
    : locale === "zh"
      ? "合成受控评审意见。"
      : "合成受控評審意見。";
}

function syntheticExceptionRisk(locale: TestLocale): string {
  return locale === "en"
    ? "Synthetic bounded risk."
    : locale === "zh"
      ? "合成受控风险。"
      : "合成受控風險。";
}

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
  title = "The protected Gate review request could not be completed.",
): ProblemDetails {
  return {
    code,
    retryable,
    status,
    title,
    traceId,
    type: `urn:npi:problem:${code.toLowerCase()}`,
  };
}

function projectBaselineWorkspace() {
  const workspace = documentBaselineWorkspaceFixture();
  return {
    ...workspace,
    project: {
      ...workspace.project,
      globalId: projectGlobalId,
    },
  };
}

function releaseBaselineReview(options: {
  attached: boolean;
  impacted?: boolean;
}): GateReviewViewModel {
  const base = gateReviewFixture();
  const workspace = projectBaselineWorkspace();
  const baseline = workspace.items[0];
  const sourceImpact = workspace.impacts[0];
  const firstRequirement = base.evidence.requirements[0];
  if (!baseline || !sourceImpact || !firstRequirement)
    throw new Error("The browser Gate baseline fixture is incomplete.");
  const reference = {
    globalId: "31313131-3131-4313-8313-313131313131",
    kind: "release_baseline" as const,
    sourceObjectType: "release_baseline" as const,
    sourceGlobalId: baseline.globalId,
    revision: baseline.version,
    objectHash: baseline.snapshotHash,
    createdAt: "2026-07-31T12:00:00Z",
    createdBy: "reviewer@example.invalid",
    baseline,
  };
  const attached = options.attached ? [reference] : [];
  const evidence = {
    ...base.evidence,
    baselineImpacts:
      options.attached && options.impacted
        ? [
            {
              ...sourceImpact,
              gateGlobalId: base.gate.globalId,
              requirementGlobalId: firstRequirement.globalId,
              evidenceReferenceGlobalId: reference.globalId,
              occurredAt: "2026-08-01T09:00:00Z",
            },
          ]
        : [],
    permissions: {
      ...base.evidence.permissions,
      canAttachEvidence: true,
    },
    requirements: base.evidence.requirements.map((requirement, index) =>
      index === 0
        ? {
            ...requirement,
            allowedEvidenceKinds: [
              ...requirement.allowedEvidenceKinds,
              "release_baseline" as const,
            ],
            evidence: [...requirement.evidence, ...attached],
          }
        : requirement,
    ),
    summary: {
      ...base.evidence.summary,
      evidenceCount: base.evidence.summary.evidenceCount + attached.length,
    },
  };
  return { ...base, evidence };
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
        preferences: { navigationCollapsed: false },
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

async function installDelayedReview(
  page: Page,
  view: GateReviewViewModel,
): Promise<() => void> {
  let releaseResponse: (() => void) | undefined;
  const responseMayComplete = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  await page.route(reviewEndpoint, async (route) => {
    await responseMayComplete;
    await fulfillApi(route, view);
  });
  return () => {
    releaseResponse?.();
  };
}

async function installReviewFailure(
  page: Page,
  locale: TestLocale,
  options: {
    code: string;
    retryable?: boolean;
    status: number;
    titleSource: string;
    traceId: string;
  },
): Promise<void> {
  await page.route(reviewEndpoint, async (route) => {
    await fulfillApi(
      route,
      problem(
        options.status,
        options.code,
        options.traceId,
        options.retryable ?? false,
        translate(locale, options.titleSource),
      ),
      { status: options.status, traceId: options.traceId },
    );
  });
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

async function openGateLoading(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${projectGlobalId}/gates/${gateGlobalId}?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(
    page.getByRole("status", {
      name: translate(locale, "Loading Gate Review Room"),
    }),
  ).toBeVisible();
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

async function expectLocalizedReviewRoomLoaded(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  const frozenRequirements = page.getByRole("table", {
    name: translate(locale, "Frozen Gate requirements"),
  });
  const mobileFieldLayout = await page.evaluate(
    () => globalThis.matchMedia("(width <= 920px)").matches,
  );
  if (mobileFieldLayout) {
    await expect(page.locator(".mobile-gate-field-summary")).toBeVisible();
    await expect(frozenRequirements).toBeHidden();
    await expect(page.locator(".mobile-engineering-handoff")).toBeVisible();
  } else {
    await expect(frozenRequirements).toBeVisible();
  }
  await expect(
    page.getByRole("complementary", {
      name: translate(locale, "Review inspector"),
    }),
  ).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
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
      page
        .getByText("Synthetic unresolved dimensional issue")
        .filter({ visible: true }),
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

  test("attaches one exact immutable release baseline and reloads authoritative Gate truth", async ({
    page,
  }) => {
    await installSession(page, "en");
    const initial = releaseBaselineReview({ attached: false });
    const attached = releaseBaselineReview({ attached: true });
    const baselineWorkspace = projectBaselineWorkspace();
    const baseline = baselineWorkspace.items[0];
    const requirement = initial.evidence.requirements[0];
    if (!baseline || !requirement)
      throw new Error("The browser Gate baseline fixture is incomplete.");
    let current = initial;
    let reviewLoads = 0;
    let attachBody: unknown = null;
    await page.route(reviewEndpoint, async (route) => {
      expect(route.request().method()).toBe("GET");
      reviewLoads += 1;
      await fulfillApi(route, current);
    });
    await page.route(documentBaselinesEndpoint, async (route) => {
      expect(route.request().method()).toBe("GET");
      await fulfillApi(route, baselineWorkspace);
    });
    await page.route(attachEvidenceEndpoint, async (route) => {
      const request = route.request();
      expect(request.method()).toBe("POST");
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(
        /^gate-baseline-evidence-/u,
      );
      attachBody = request.postDataJSON();
      current = attached;
      await fulfillApi(route, attached.evidence, {
        idempotencyReplayed: false,
        status: 201,
        traceId: "trace-p5-03-gate-baseline-attach",
      });
    });

    await openGate(page);
    await expectReviewRoomLoaded(page);
    await expect(
      page.getByRole("heading", { name: "Exact baseline evidence source" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Attach exact baseline evidence" })
      .click();

    await expect.poll(() => reviewLoads).toBeGreaterThanOrEqual(2);
    await expect(page.getByText(baseline.globalId).first()).toBeVisible();
    expect(attachBody).toEqual({
      expectedGateVersion: initial.gate.version,
      evidenceKind: "release_baseline",
      sourceGlobalId: baseline.globalId,
      sourceVersion: baseline.version,
      sourceHash: baseline.snapshotHash,
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
      page
        .getByText("Processing Gate review command")
        .filter({ visible: true }),
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
    await expect(
      page.getByText("5".repeat(64)).filter({ visible: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByText("c".repeat(64)).filter({ visible: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: "Acknowledge change and start review",
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Submit review" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Request controlled exception" }),
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
        name: "The Gate Review Room could not be loaded",
      }),
    ).toBeVisible();
    await expect(page.getByText(traceId)).toBeVisible();
    await expect(page.getByText("Synthetic initiation evidence")).toHaveCount(
      0,
    );
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
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

test.describe("Gate Review Room command failure accessibility", () => {
  for (const failureCase of commandFailureAccessibilityCases) {
    test(`renders one accessible ${failureCase.name} command alert with honest write status`, async ({
      page,
    }) => {
      const locale = "en";
      const view = gateReviewFixture();
      const traceId = `trace-gate-review-command-${failureCase.name}`;
      await installSession(page, locale);
      await installReview(page, view);
      await page.route(submitReviewEndpoint, async (route) => {
        const body: unknown = route.request().postDataJSON();
        if (!isSubmitReviewBody(body)) {
          throw new Error("The browser submitted an invalid review command.");
        }
        await fulfillApi(
          route,
          problem(
            failureCase.status,
            failureCase.code,
            traceId,
            failureCase.retryable,
            translate(locale, failureCase.failureSource),
          ),
          { status: failureCase.status, traceId },
        );
      });
      await openGate(page, locale);
      await expectLocalizedReviewRoomLoaded(page, locale);
      await page
        .getByRole("textbox", {
          name: translate(locale, "Complete review opinion"),
        })
        .fill(syntheticReviewOpinion(locale));
      await page
        .getByRole("button", { name: translate(locale, "Submit review") })
        .click();

      const alert = page.getByRole("alert", {
        name: translate(locale, "Gate review command failure"),
      });
      await expect(alert).toBeVisible();
      await expect(page.getByRole("alert")).toHaveCount(1);
      await expect(alert).toContainText(
        translate(locale, failureCase.failureSource),
      );
      await expect(alert).toContainText(translate(locale, "Failed step"));
      await expect(alert).toContainText(translate(locale, "Submit review"));
      await expect(alert).toContainText(
        translate(locale, "Write confirmation"),
      );
      await expect(alert).toContainText(
        translate(locale, failureCase.writeSource),
      );
      await expect(alert).toContainText(traceId);

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(results.violations).toEqual([]);
    });
  }
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

test.describe("trilingual Gate decision-readiness denial reasons", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    for (const [code, source] of browserDecisionBlockedReasonCases) {
      test(`renders ${code} without mixed language in ${locale}`, async ({
        page,
      }) => {
        const fixture = gateReviewFixture();
        const view: GateReviewViewModel = {
          ...fixture,
          decisionReadiness: {
            allowedOutcomes: [],
            blockedReasons: (
              ["pass", "conditional_pass", "reject"] as const
            ).map((outcome) => ({ code, outcome })),
          },
        };
        await installSession(page, locale);
        await installReview(page, view);
        await openGate(page, locale);
        await expectLocalizedReviewRoomLoaded(page, locale);

        const readiness = page
          .getByRole("heading", {
            name: translate(locale, "Gate decision readiness"),
          })
          .locator("..");
        await expect(readiness).toContainText(translate(locale, source));
        await expectNoMixedLanguage(page, locale);
        await expectNoDocumentOverflow(page);
      });
    }
  }
});

interface LoadedReviewStateCase {
  expectedSource: string;
  name: string;
  view: () => GateReviewViewModel;
}

const loadedReviewStateCases: readonly LoadedReviewStateCase[] = [
  {
    expectedSource: "No active review cycle",
    name: "no active cycle",
    view: gateReviewNoCycleFixture,
  },
  {
    expectedSource: "No permitted review action",
    name: "read only",
    view: gateReviewReadOnlyFixture,
  },
  {
    expectedSource: "Pending approval",
    name: "pending exception",
    view: gateReviewPendingExceptionFixture,
  },
  {
    expectedSource: "Approved",
    name: "closed exception",
    view: gateReviewExceptionHistoryFixture,
  },
  {
    expectedSource: "Decided",
    name: "decided",
    view: gateReviewDecidedFixture,
  },
  {
    expectedSource: "Manual reopen",
    name: "reopened",
    view: gateReviewReopenedFixture,
  },
  {
    expectedSource: "Gate input snapshot changed",
    name: "requires review",
    view: gateReviewRequiresReviewFixture,
  },
];

interface FailedReviewStateCase {
  code: string;
  expectedSource: string;
  name: string;
  retryable?: boolean;
  status: number;
}

const failedReviewStateCases: readonly FailedReviewStateCase[] = [
  {
    code: "GATE_REVIEW_ACCESS_DENIED",
    expectedSource: "Gate review access is not available",
    name: "no permission",
    status: 403,
  },
  {
    code: "GATE_REVIEW_UNAVAILABLE",
    expectedSource: "The Gate Review Room could not be loaded",
    name: "retryable load error",
    retryable: true,
    status: 503,
  },
  {
    code: "GATE_REVIEW_VERSION_CONFLICT",
    expectedSource: "The Gate review workspace is out of date",
    name: "load conflict",
    status: 409,
  },
  {
    code: "GATE_REVIEW_FINAL_FAILURE",
    expectedSource: "The Gate review response could not be used safely",
    name: "final error",
    status: 500,
  },
  {
    code: "GATE_REVIEW_UNAVAILABLE",
    expectedSource: "Gate Review Room is unavailable",
    name: "not found",
    status: 404,
  },
];

test.describe("trilingual Gate Review Room non-normal state matrix", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders loading without mixed language in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      const release = await installDelayedReview(page, gateReviewFixture());
      try {
        await openGateLoading(page, locale);
        await expectNoMixedLanguage(page, locale);
        await expectNoDocumentOverflow(page);
      } finally {
        release();
      }
      await expectLocalizedReviewRoomLoaded(page, locale);
    });

    for (const state of loadedReviewStateCases) {
      test(`renders ${state.name} without mixed language in ${locale}`, async ({
        page,
      }) => {
        await installSession(page, locale);
        await installReview(page, state.view());
        await openGate(page, locale);
        await expectLocalizedReviewRoomLoaded(page, locale);
        await expect(
          page
            .getByText(translate(locale, state.expectedSource))
            .filter({ visible: true })
            .first(),
        ).toBeVisible();
        await expectNoMixedLanguage(page, locale);
        await expectNoDocumentOverflow(page);
      });
    }

    for (const state of failedReviewStateCases) {
      test(`renders ${state.name} without protected data or mixed language in ${locale}`, async ({
        page,
      }) => {
        const traceId = `trace-${state.name.replaceAll(" ", "-")}-${locale}`;
        await installSession(page, locale);
        await installReviewFailure(page, locale, {
          code: state.code,
          ...(state.retryable === undefined
            ? {}
            : { retryable: state.retryable }),
          status: state.status,
          titleSource: state.expectedSource,
          traceId,
        });
        await openGate(page, locale);
        await expect(
          page.getByRole("heading", {
            level: 1,
            name: translate(locale, state.expectedSource),
          }),
        ).toBeVisible();
        await expect(page.getByText(traceId)).toBeVisible();
        await expect(
          page.getByText("Synthetic initiation evidence"),
        ).toHaveCount(0);
        await expectNoMixedLanguage(page, locale);
        await expectNoDocumentOverflow(page);
      });
    }
  }
});

type ReviewRoomVisualState =
  | "normal"
  | "loading"
  | "no_cycle"
  | "read_only"
  | "no_permission"
  | "retryable"
  | "final"
  | "not_found"
  | "validation"
  | "command_conflict"
  | "processing"
  | "pending_exception"
  | "closed_exception"
  | "decided"
  | "reopened"
  | "requires_review"
  | "dialog_request_exception"
  | "dialog_decide_exception"
  | "dialog_decide_gate"
  | "dialog_reopen";

interface ReviewRoomVisualCase {
  dialogPosition?: "top" | "bottom";
  height: number;
  locale: TestLocale;
  name: string;
  state: ReviewRoomVisualState;
  width: number;
  zoom: 1 | 1.25 | 1.5;
}

const reviewRoomVisualCases: readonly ReviewRoomVisualCase[] = [
  {
    height: 768,
    locale: "en",
    name: "gate-review-room-en-1366x768-100",
    state: "normal",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh",
    name: "gate-review-room-zh-1920x1080-125",
    state: "normal",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "gate-review-room-zh-TW-1366x768-150",
    state: "normal",
    width: 1366,
    zoom: 1.5,
  },
  {
    dialogPosition: "bottom",
    height: 768,
    locale: "zh-TW",
    name: "gate-review-dialog-decide-gate-confirm-zh-TW-1366x768-150",
    state: "dialog_decide_gate",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "en",
    name: "gate-review-loading-en-1920x1080-150",
    state: "loading",
    width: 1920,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "zh",
    name: "gate-review-no-cycle-zh-1366x768-125",
    state: "no_cycle",
    width: 1366,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "gate-review-read-only-zh-TW-1920x1080-100",
    state: "read_only",
    width: 1920,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh",
    name: "gate-review-no-permission-zh-1920x1080-125",
    state: "no_permission",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh",
    name: "gate-review-retryable-zh-1366x768-100",
    state: "retryable",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "gate-review-final-zh-TW-1920x1080-125",
    state: "final",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "en",
    name: "gate-review-not-found-en-1366x768-150",
    state: "not_found",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "gate-review-validation-zh-TW-1366x768-100",
    state: "validation",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "en",
    name: "gate-review-command-conflict-en-1920x1080-150",
    state: "command_conflict",
    width: 1920,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "gate-review-processing-zh-TW-1366x768-150",
    state: "processing",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 768,
    locale: "en",
    name: "gate-review-exception-pending-en-1366x768-100",
    state: "pending_exception",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh",
    name: "gate-review-exception-closed-approved-zh-1920x1080-125",
    state: "closed_exception",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "gate-review-decided-zh-TW-1366x768-150",
    state: "decided",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "en",
    name: "gate-review-reopened-en-1920x1080-100",
    state: "reopened",
    width: 1920,
    zoom: 1,
  },
  {
    height: 768,
    locale: "zh",
    name: "gate-review-requires-review-zh-1366x768-125",
    state: "requires_review",
    width: 1366,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "en",
    name: "gate-review-dialog-request-exception-en-1366x768-100",
    state: "dialog_request_exception",
    width: 1366,
    zoom: 1,
  },
  {
    height: 1080,
    locale: "zh",
    name: "gate-review-dialog-decide-exception-zh-1920x1080-125",
    state: "dialog_decide_exception",
    width: 1920,
    zoom: 1.25,
  },
  {
    height: 768,
    locale: "zh-TW",
    name: "gate-review-dialog-decide-gate-zh-TW-1366x768-150",
    state: "dialog_decide_gate",
    width: 1366,
    zoom: 1.5,
  },
  {
    height: 1080,
    locale: "en",
    name: "gate-review-dialog-reopen-en-1920x1080-150",
    state: "dialog_reopen",
    width: 1920,
    zoom: 1.5,
  },
];

async function prepareReviewVisualCase(
  page: Page,
  visual: ReviewRoomVisualCase,
): Promise<() => Promise<void>> {
  const { locale, state } = visual;
  const noCleanup = (): Promise<void> => Promise.resolve();
  const openView = async (
    view: GateReviewViewModel,
    userId = "reviewer@example.invalid",
  ): Promise<void> => {
    await installSession(page, locale, userId);
    await installReview(page, view);
    await openGate(page, locale);
    await expectLocalizedReviewRoomLoaded(page, locale);
  };

  if (state === "loading") {
    await installSession(page, locale);
    const release = await installDelayedReview(page, gateReviewFixture());
    try {
      await openGateLoading(page, locale);
    } catch (error) {
      release();
      throw error;
    }
    return async () => {
      release();
      await expectLocalizedReviewRoomLoaded(page, locale);
    };
  }

  if (
    state === "no_permission" ||
    state === "retryable" ||
    state === "final" ||
    state === "not_found"
  ) {
    const failure = {
      final: {
        code: "GATE_REVIEW_FINAL_FAILURE",
        expectedSource: "The Gate review response could not be used safely",
        status: 500,
      },
      no_permission: {
        code: "GATE_REVIEW_ACCESS_DENIED",
        expectedSource: "Gate review access is not available",
        status: 403,
      },
      not_found: {
        code: "GATE_REVIEW_UNAVAILABLE",
        expectedSource: "Gate Review Room is unavailable",
        status: 404,
      },
      retryable: {
        code: "GATE_REVIEW_UNAVAILABLE",
        expectedSource: "The Gate Review Room could not be loaded",
        retryable: true,
        status: 503,
      },
    }[state];
    await installSession(page, locale);
    await installReviewFailure(page, locale, {
      code: failure.code,
      retryable: "retryable" in failure ? failure.retryable : false,
      status: failure.status,
      titleSource: failure.expectedSource,
      traceId: `trace-gate-review-${state}`,
    });
    await openGate(page, locale);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: translate(locale, failure.expectedSource),
      }),
    ).toBeVisible();
    return noCleanup;
  }

  if (state === "validation") {
    await installSession(page, locale);
    await installReview(page, gateReviewFixture());
    await openGate(page, locale, "not-a-uuid");
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: translate(locale, "The Gate review address is invalid"),
      }),
    ).toBeVisible();
    return noCleanup;
  }

  if (state === "command_conflict" || state === "processing") {
    const view = gateReviewFixture();
    let releaseResponse: (() => void) | undefined;
    const responseMayComplete =
      state === "processing"
        ? new Promise<void>((resolve) => {
            releaseResponse = resolve;
          })
        : Promise.resolve();
    await installSession(page, locale);
    await installReview(page, view);
    await page.route(submitReviewEndpoint, async (route) => {
      const body: unknown = route.request().postDataJSON();
      if (!isSubmitReviewBody(body)) {
        throw new Error("The browser submitted an invalid review command.");
      }
      if (state === "processing") {
        await responseMayComplete;
        await fulfillApi(route, submittedReviewView(view, body), {
          idempotencyReplayed: false,
        });
        return;
      }
      await fulfillApi(
        route,
        problem(
          409,
          "GATE_REVIEW_VERSION_CONFLICT",
          "trace-gate-review-command-conflict",
          false,
          translate(locale, "Version conflict"),
        ),
        { status: 409, traceId: "trace-gate-review-command-conflict" },
      );
    });
    try {
      await openGate(page, locale);
      await expectLocalizedReviewRoomLoaded(page, locale);
      await page
        .getByRole("textbox", {
          name: translate(locale, "Complete review opinion"),
        })
        .fill(syntheticReviewOpinion(locale));
      await page
        .getByRole("button", { name: translate(locale, "Submit review") })
        .click();
      const statusLabel = translate(
        locale,
        state === "processing"
          ? "Processing Gate review command"
          : "Version conflict",
      );
      await expect(
        state === "processing"
          ? page.getByText(statusLabel).filter({ visible: true })
          : page.getByRole("heading", { name: statusLabel }),
      ).toBeVisible();
    } catch (error) {
      releaseResponse?.();
      throw error;
    }
    return async () => {
      if (state === "processing") {
        releaseResponse?.();
        await expect(
          page.getByText(translate(locale, "Server confirmed"), {
            exact: true,
          }),
        ).toBeVisible();
      }
    };
  }

  const view = {
    closed_exception: gateReviewExceptionHistoryFixture,
    decided: gateReviewDecidedFixture,
    dialog_decide_exception: gateReviewPendingExceptionFixture,
    dialog_decide_gate: gateReviewDecisionReadyFixture,
    dialog_reopen: gateReviewDecidedFixture,
    dialog_request_exception: gateReviewExceptionEligibleFixture,
    no_cycle: gateReviewNoCycleFixture,
    normal: gateReviewFixture,
    pending_exception: gateReviewPendingExceptionFixture,
    read_only: gateReviewReadOnlyFixture,
    reopened: gateReviewReopenedFixture,
    requires_review: gateReviewRequiresReviewFixture,
  }[state]();
  const userId =
    state === "pending_exception" || state === "dialog_decide_exception"
      ? "exception.authority@example.invalid"
      : state === "decided" || state === "dialog_reopen"
        ? "reopen.authority@example.invalid"
        : state === "dialog_decide_gate"
          ? "decision.authority@example.invalid"
          : "reviewer@example.invalid";
  await openView(view, userId);

  const expectedSource = {
    closed_exception: "Approved",
    decided: "Decided",
    no_cycle: "No active review cycle",
    normal: undefined,
    pending_exception: "Pending approval",
    read_only: "No permitted review action",
    reopened: "Manual reopen",
    requires_review: "Gate input snapshot changed",
  }[
    state as
      | "closed_exception"
      | "decided"
      | "no_cycle"
      | "normal"
      | "pending_exception"
      | "read_only"
      | "reopened"
      | "requires_review"
  ];
  if (expectedSource) {
    await expect(
      page.getByText(translate(locale, expectedSource)).first(),
    ).toBeVisible();
  }

  if (state === "pending_exception" || state === "closed_exception") {
    const exceptions = page.getByRole("list", {
      name: translate(locale, "Gate review exceptions"),
    });
    await expect(exceptions).toBeVisible();
    await expect(
      exceptions
        .getByText(
          translate(
            locale,
            state === "pending_exception" ? "Pending approval" : "Approved",
          ),
        )
        .first(),
    ).toBeVisible();
    if (state === "closed_exception") {
      await expect(
        exceptions.getByText("The bounded synthetic exception is approved.", {
          exact: true,
        }),
      ).toBeVisible();
    }
    await exceptions.scrollIntoViewIfNeeded();
  } else if (state === "reopened") {
    const historyHeading = page.getByRole("heading", {
      name: translate(locale, "Input version and prior decisions"),
    });
    await historyHeading.scrollIntoViewIfNeeded();
    const history = page.getByRole("list", {
      name: translate(locale, "Immutable Gate decision history"),
    });
    await expect(history).toBeVisible();
    const downstreamCurrent = history.getByText(
      translate(locale, "Downstream current"),
      { exact: true },
    );
    await expect(
      downstreamCurrent
        .locator("..")
        .getByText(translate(locale, "No"), { exact: true }),
    ).toBeVisible();
  }

  if (state === "dialog_request_exception") {
    await page.getByRole("button", { name: /CUSTOMER_CONFIRMATION/u }).click();
    const action = page.getByRole("combobox", {
      name: translate(locale, "Review action"),
    });
    const reviewOption = action.locator(
      'option[value="review:ENGINEERING_REVIEW"]',
    );
    const reviewOptionLabel = translate(locale, "Submit review: {{step}}", {
      step: "ENGINEERING_REVIEW",
    });
    await expect(reviewOption).toHaveText(reviewOptionLabel);
    await expect(reviewOption).toHaveAttribute("aria-label", reviewOptionLabel);
    await expect(reviewOption).toHaveAttribute(
      "data-language-exempt-tokens",
      JSON.stringify(["ENGINEERING_REVIEW"]),
    );
    const requestOption = action.locator('option[value^="request_exception:"]');
    const requestOptionLabel = translate(
      locale,
      "Request exception: {{requirement}} / {{kind}}",
      {
        kind: "controlled_deviation",
        requirement: "CUSTOMER_CONFIRMATION",
      },
    );
    await expect(requestOption).toHaveText(requestOptionLabel);
    await expect(requestOption).toHaveAttribute(
      "aria-label",
      requestOptionLabel,
    );
    await expect(requestOption).toHaveAttribute(
      "data-language-exempt-tokens",
      JSON.stringify(["CUSTOMER_CONFIRMATION", "controlled_deviation"]),
    );
    const optionValue = await requestOption.getAttribute("value");
    if (!optionValue) throw new Error("Missing exception-request action.");
    await action.selectOption(optionValue);
    await page
      .getByRole("textbox", { name: translate(locale, "Risk if accepted") })
      .fill(syntheticExceptionRisk(locale));
    await page
      .getByLabel(translate(locale, "Exception expiry date"))
      .fill("2026-08-12");
    await page.locator('[data-visual-primary="true"]:visible').click();
    await expect(
      page.getByRole("dialog", {
        name: translate(locale, "Review controlled exception request"),
      }),
    ).toBeVisible();
    await expectSinglePrimaryAction(page);
  } else if (state === "dialog_decide_exception") {
    await page
      .getByRole("combobox", {
        name: translate(locale, "Exception decision"),
      })
      .selectOption("rejected");
    await page.locator('[data-visual-primary="true"]:visible').click();
    await expect(
      page.getByRole("dialog", {
        name: translate(locale, "Review exception decision"),
      }),
    ).toBeVisible();
    await expectSinglePrimaryAction(page);
  } else if (state === "dialog_decide_gate") {
    await page
      .getByRole("combobox", {
        name: translate(locale, "Decision outcome"),
      })
      .selectOption("pass");
    await page.locator('[data-visual-primary="true"]:visible').click();
    await expect(
      page.getByRole("dialog", {
        name: translate(locale, "Review immutable Gate decision"),
      }),
    ).toBeVisible();
    await expectSinglePrimaryAction(page);
  } else if (state === "dialog_reopen") {
    await page.locator('[data-visual-primary="true"]:visible').click();
    await expect(
      page.getByRole("dialog", {
        name: translate(locale, "Review Gate reopen"),
      }),
    ).toBeVisible();
    await expectSinglePrimaryAction(page);
  }

  if (state.startsWith("dialog_")) {
    const dialog = page.getByRole("dialog");
    const surface = dialog.locator(".impact-review__surface");
    await expect(surface).toBeVisible();
    await surface.evaluate((element, position) => {
      element.scrollTop = position === "bottom" ? element.scrollHeight : 0;
    }, visual.dialogPosition ?? "top");
    await expect
      .poll(() => surface.evaluate((element) => element.scrollTop))
      .toBe(
        visual.dialogPosition === "bottom"
          ? await surface.evaluate(
              (element) => element.scrollHeight - element.clientHeight,
            )
          : 0,
      );
  }

  return noCleanup;
}

const dialogAccessibilityStates = [
  "dialog_request_exception",
  "dialog_decide_exception",
  "dialog_decide_gate",
  "dialog_reopen",
] as const satisfies readonly ReviewRoomVisualState[];

test.describe("Gate Review Room impact dialog accessibility", () => {
  for (const state of dialogAccessibilityStates) {
    test(`manages focus and passes Axe for ${state}`, async ({ page }) => {
      const visual: ReviewRoomVisualCase = {
        height: 768,
        locale: "en",
        name: `non-visual-accessibility-${state}`,
        state,
        width: 1366,
        zoom: 1,
      };
      const cleanup = await prepareReviewVisualCase(page, visual);
      try {
        const dialog = page.getByRole("dialog");
        const heading = dialog.getByRole("heading", { level: 2 });
        await expect(dialog).toBeVisible();
        await expect(heading).toBeFocused();
        await expect(heading).toHaveAttribute("tabindex", "-1");
        await expect(page.getByRole("alert")).toHaveCount(0);

        const results = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
          .analyze();
        expect(results.violations).toEqual([]);

        await page.keyboard.press("Shift+Tab");
        await expect
          .poll(() =>
            page.evaluate(() => {
              const currentDialog = document.querySelector('[role="dialog"]');
              return Boolean(
                currentDialog?.contains(document.activeElement) &&
                document.activeElement !== currentDialog,
              );
            }),
          )
          .toBe(true);
        await page.keyboard.press("Tab");
        await expect
          .poll(() =>
            page.evaluate(() => {
              const currentDialog = document.querySelector('[role="dialog"]');
              return Boolean(
                currentDialog?.contains(document.activeElement) &&
                document.activeElement !== currentDialog,
              );
            }),
          )
          .toBe(true);

        await page.keyboard.press("Escape");
        await expect(dialog).toHaveCount(0);
        await expect(
          page.locator('[data-visual-primary="true"]:visible'),
        ).toBeFocused();
      } finally {
        await cleanup();
      }
    });
  }
});

const commandAndDialogStates: readonly ReviewRoomVisualState[] = [
  "validation",
  "command_conflict",
  "processing",
  "dialog_request_exception",
  "dialog_decide_exception",
  "dialog_decide_gate",
  "dialog_reopen",
];

test.describe("trilingual Gate Review Room command and dialog matrix", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    for (const state of commandAndDialogStates) {
      test(`renders ${state} without mixed language in ${locale}`, async ({
        page,
      }) => {
        const visual: ReviewRoomVisualCase = {
          height: 768,
          locale,
          name: `non-visual-${state}-${locale}`,
          state,
          width: 1366,
          zoom: 1,
        };
        const cleanup = await prepareReviewVisualCase(page, visual);
        try {
          await expectNoMixedLanguage(page, locale);
          await expectNoDocumentOverflow(page);
        } finally {
          await cleanup();
        }
      });
    }
  }
});

test.describe("@visual live Gate Review Room", () => {
  for (const visual of reviewRoomVisualCases) {
    test(visual.name, async ({ page }) => {
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
      let cleanup = (): Promise<void> => Promise.resolve();
      try {
        cleanup = await prepareReviewVisualCase(page, visual);
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
          ...(visual.state === "validation"
            ? { mask: [page.locator(".trace-reference code")] }
            : {}),
        });
      } finally {
        await cleanup();
      }
    });
  }
});

const baselineImpactVisualCases = [
  {
    height: 768,
    locale: "en",
    name: "p5-03-gate-baseline-impact-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p5-03-gate-baseline-impact-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p5-03-gate-baseline-impact-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P5-03 Gate baseline evidence and impact lineage", () => {
  for (const visual of baselineImpactVisualCases) {
    test(visual.name, async ({ page }) => {
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
      await installSession(page, visual.locale);
      await installReview(
        page,
        releaseBaselineReview({ attached: true, impacted: true }),
      );
      await page.route(documentBaselinesEndpoint, async (route) => {
        await fulfillApi(route, projectBaselineWorkspace());
      });
      await openGate(page, visual.locale);
      await expectLocalizedReviewRoomLoaded(page, visual.locale);
      const impactHeading = page.getByRole("heading", {
        name: translate(visual.locale, "Baseline successor impact"),
      });
      await expect(impactHeading).toBeVisible();
      await expect(
        page.getByRole("table", {
          name: translate(visual.locale, "Baseline successor impact lineage"),
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
      await impactHeading.scrollIntoViewIfNeeded();
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
