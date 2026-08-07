import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  ToolingCockpitViewModel,
  ToolingSetCollectionViewModel,
  ToolingSetDetailViewModel,
} from "../../src/api/tooling-data-source";
import {
  controlledDocumentId,
  controlledDocumentPageFixture,
  controlledDocumentWorkspaceFixture,
  fileRevisionId,
} from "../support/document-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const requirementId = "33333333-3333-4333-8333-333333333333";
const setId = "44444444-4444-4444-8444-444444444444";
const intakeId = "55555555-5555-4555-8555-555555555555";
const differenceId = "66666666-6666-4666-8666-666666666666";
const inspectionIds = [
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5",
] as const;
const csrfToken = "p6-02-tooling-set-browser-csrf-0001";
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const projectEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/.+/u;

interface ObservedRequest {
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
}

function cockpit(): ToolingCockpitViewModel {
  const source = {
    editableIn: "NPI_ONE" as const,
    sourceSystem: "NPI_ONE" as const,
    syncState: "local" as const,
  };
  return {
    applicability: [],
    downstream: {
      erp: { reasonCode: "erp_projection_unavailable", state: "unavailable" },
      lifecycle: {
        reasonCode: "lifecycle_policy_unavailable",
        state: "unavailable",
      },
      physicalSet: {
        reasonCode: "physical_set_not_delivered",
        state: "unavailable",
      },
      revision: {
        reasonCode: "tooling_revision_not_delivered",
        state: "unavailable",
      },
      trial: { reasonCode: "trial_not_delivered", state: "unavailable" },
    },
    masters: [
      {
        globalId: masterId,
        originatingProjectGlobalId: projectId,
        snapshotHash: "1".repeat(64),
        source,
        title: "Synthetic customer-owned mold",
      },
    ],
    parts: [],
    permissions: {
      createApplicability: false,
      createMaster: false,
      createPart: false,
      createRequirement: false,
      transitionLifecycle: false,
      view: true,
    },
    project: {
      businessCode: "SYN-PROJECT-002",
      globalId: projectId,
      title: "Synthetic Set Intake Project",
    },
    requirements: [
      {
        globalId: requirementId,
        kind: "customer_owned_intake",
        projectGlobalId: projectId,
        reason: "Customer-owned mold arrival",
        snapshotHash: "2".repeat(64),
        targetDate: null,
        targetPartRevisionGlobalId: null,
        title: "Customer mold intake",
      },
    ],
  };
}

function collection(): ToolingSetCollectionViewModel {
  return {
    items: [
      {
        custodyResponsibility: "Customer-owned custody",
        customer: { sourceObjectId: "CUST-002", sourceSystem: "ERPNEXT" },
        erpLocationAndAsset: {
          reasonCode: "erp_projection_unavailable",
          state: "unavailable",
        },
        globalId: setId,
        lifecycle: {
          reasonCode: "lifecycle_policy_unavailable",
          state: "unavailable",
        },
        physicalSerial: "SET-CUST-002",
        projectGlobalId: projectId,
        repairAuthorizationReference: "AUTH-CUST-002",
        requirementKind: "customer_owned_intake",
        returnConditions: "Return on written customer request",
        snapshotHash: "3".repeat(64),
        sourceRevision: {
          reasonCode: "tooling_revision_not_delivered",
          state: "unavailable",
        },
        supplier: {
          reasonCode: "formal_supplier_unavailable",
          state: "unavailable",
        },
        toolingMasterGlobalId: masterId,
        toolingRequirementGlobalId: requirementId,
      },
    ],
    permissions: {
      attachEvidence: true,
      createIntake: true,
      createSet: true,
      transitionLifecycle: false,
      view: true,
    },
    toolingMasterGlobalId: masterId,
  };
}

function detail(): ToolingSetDetailViewModel {
  const toolingSet = collection().items[0];
  if (!toolingSet) throw new Error("The Set fixture is required.");
  const inspections = (
    [
      "appearance",
      "water_circuit",
      "hot_runner",
      "electrical",
      "safety",
    ] as const
  ).map((category, index) => ({
    category,
    differenceObserved: index === 0,
    globalId: inspectionIds[index] ?? inspectionIds[0],
    observation:
      index === 0 ? "Surface scratch at cavity edge" : "No difference observed",
  }));
  return {
    evidence: [
      {
        differenceGlobalIds: [differenceId],
        evidenceRole: "arrival_photo",
        fileContentHash: "4".repeat(64),
        fileName: "synthetic-drawing.pdf",
        fileOptimisticVersion: 1,
        fileRevisionGlobalId: fileRevisionId,
        globalId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        intakeSnapshotHash: "5".repeat(64),
        mimeType: "application/pdf",
        sha256: "6".repeat(64),
        sizeBytes: 4,
        snapshotHash: "7".repeat(64),
        toolingIntakeGlobalId: intakeId,
      },
    ],
    intakes: [
      {
        accessories: [
          {
            declaredQuantity: 2,
            description: "Lifting ring",
            globalId: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            receivedQuantity: 2,
            unit: "pcs",
          },
        ],
        arrivedAt: "2026-08-07T08:00:00Z",
        custodyHandover: "Accepted by Tooling receiver",
        differences: [
          {
            customerConfirmationRequired: true,
            description: "Surface scratch at cavity edge",
            globalId: differenceId,
            sourceGlobalId: inspectionIds[0],
            sourceKind: "inspection",
          },
        ],
        globalId: intakeId,
        inspections,
        predecessorGlobalId: null,
        snapshotHash: "5".repeat(64),
        toolingSetGlobalId: setId,
        transportProvider: "Synthetic carrier",
        transportReference: "SHIP-CUST-002",
        version: 1,
      },
    ],
    permissions: collection().permissions,
    toolingSet,
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
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(route.request().headers()["idempotency-key"]
        ? { "Idempotency-Replayed": "false" }
        : {}),
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p6-02-tooling-set-browser",
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
      userId: "tooling.receiver@example.invalid",
    });
  });
}

async function installApi(page: Page): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(projectEndpoint, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    observed.push({
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path,
      payload: request.method() === "POST" ? request.postDataJSON() : null,
    });
    if (request.method() === "POST") {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(/^tooling-/u);
    }
    if (path.endsWith(`/tooling/${masterId}`)) {
      await fulfillJson(route, cockpit());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/sets`)) {
      await fulfillJson(
        route,
        collection(),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.includes(`/tooling/${masterId}/sets/${setId}`)) {
      await fulfillJson(
        route,
        detail(),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.endsWith("/documents")) {
      const value = controlledDocumentPageFixture();
      await fulfillJson(route, {
        ...value,
        project: { ...value.project, globalId: projectId },
      });
      return;
    }
    if (path.endsWith(`/documents/${controlledDocumentId}`)) {
      const value = controlledDocumentWorkspaceFixture();
      await fulfillJson(route, {
        ...value,
        project: { ...value.project, globalId: projectId },
      });
      return;
    }
    await route.abort();
  });
  return observed;
}

async function openWorkspace(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/projects/${projectId}/tooling/${masterId}?lang=${locale}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.getByText("SET-CUST-002").first()).toBeVisible();
  await expect(
    page.getByText("Synthetic carrier · SHIP-CUST-002"),
  ).toBeVisible();
  await expect(
    page.locator(".tooling-set__toolbar button").first(),
  ).toBeEnabled();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P6-02 live physical Tooling Set workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders Set, intake, difference and exact evidence truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installApi(page);
      await openWorkspace(page, locale);

      await expect(page.getByText("synthetic-drawing.pdf")).toBeVisible();
      await expect(
        page.locator(".tooling-set__inspector .semantic-status"),
      ).toHaveCount(4);
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("binds one clean Project File Revision to one exact intake and difference", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page);
    await openWorkspace(page, "en");

    await page.getByRole("button", { name: "Attach evidence" }).click();
    await page
      .getByLabel("Controlled document")
      .selectOption(controlledDocumentId);
    await page.getByLabel("Exact File Revision").selectOption(fileRevisionId);
    await page.getByLabel("Surface scratch at cavity edge").check();
    await page
      .getByRole("button", { name: "Attach evidence", exact: true })
      .last()
      .click();

    await expect
      .poll(
        () =>
          observed.filter(
            (request) =>
              request.path.endsWith(`/${intakeId}/evidence`) &&
              request.method === "POST",
          ).length,
      )
      .toBe(1);
    expect(
      observed.find((request) =>
        request.path.endsWith(`/${intakeId}/evidence`),
      ),
    ).toMatchObject({
      payload: {
        differenceGlobalIds: [differenceId],
        evidenceRole: "arrival_photo",
        fileRevisionGlobalId: fileRevisionId,
      },
    });
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p6-02-tooling-set-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p6-02-tooling-set-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p6-02-tooling-set-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P6-02 live physical Tooling Set evidence", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installApi(page);
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
      await page.locator("#tooling-live-sets").scrollIntoViewIfNeeded();
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
