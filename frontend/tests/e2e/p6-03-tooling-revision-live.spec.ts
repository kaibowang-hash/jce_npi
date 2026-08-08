import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  PartControlledSpecificationContextViewModel,
  ToolingCockpitViewModel,
  ToolingMeasurementViewModel,
  ToolingProcessChainCollectionViewModel,
  ToolingProcessChainRevisionViewModel,
  ToolingRevisionCollectionViewModel,
  ToolingRevisionDetailViewModel,
  ToolingRevisionViewModel,
  ToolingSetCollectionViewModel,
  ToolingSetDetailViewModel,
} from "../../src/api/tooling-data-source";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const toolingRevisionId = "33333333-3333-4333-8333-333333333333";
const applicabilityId = "44444444-4444-4444-8444-444444444444";
const cavityId = "55555555-5555-4555-8555-555555555555";
const partId = "66666666-6666-4666-8666-666666666666";
const partRevisionId = "77777777-7777-4777-8777-777777777777";
const requirementId = "88888888-8888-4888-8888-888888888888";
const controlledSpecificationId = "99999999-9999-4999-8999-999999999999";
const specificationItemId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const processChainId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const processChainRevisionId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const firstStepId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const secondStepId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const setId = "ffffffff-ffff-4fff-8fff-ffffffffffff";
const bindingId = "12345678-1234-4234-8234-123456789abc";
const csrfToken = "p6-03-tooling-revision-browser-csrf";
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

const unavailable = {
  combinedTrial: {
    reasonCode: "combined_trial_not_delivered" as const,
    state: "unavailable" as const,
  },
  erpLocationAndAsset: {
    reasonCode: "erp_projection_unavailable" as const,
    state: "unavailable" as const,
  },
  lifecycle: {
    reasonCode: "lifecycle_policy_unavailable" as const,
    state: "unavailable" as const,
  },
  supplier: {
    reasonCode: "formal_supplier_unavailable" as const,
    state: "unavailable" as const,
  },
};

const permissions = {
  bindSetSource: true,
  createPartSpecification: true,
  createProcessChain: true,
  createRevision: true,
  transitionLifecycle: false as const,
  view: true,
};

function measurement(value: string, unit: string): ToolingMeasurementViewModel {
  return { source: "Engineering", unit, value };
}

function revision(): ToolingRevisionViewModel {
  return {
    cavities: [
      {
        cavityIdentifier: "C01",
        globalId: cavityId,
        partRevisionGlobalId: partRevisionId,
        structuralState: "enabled",
        toolingApplicabilityGlobalId: applicabilityId,
      },
    ],
    designDocumentRevisions: [],
    externalIdentities: [],
    globalId: toolingRevisionId,
    inserts: [],
    predecessorGlobalId: null,
    reason: "Controlled production release",
    revisionLabel: "R1",
    revisionNumber: 1,
    snapshotHash: "a".repeat(64),
    specification: {
      cavityCount: 1,
      clampTonnage: measurement("180", "t"),
      coreMaterial: "H13",
      customerStandard: "STD-001",
      deliveryDocuments: ["Inspection report"],
      hardness: measurement("48", "HRC"),
      height: measurement("320", "mm"),
      hotRunner: "Valve gate",
      injectionCapacity: measurement("450", "g"),
      interfaceRequirement: "EUROMAP",
      length: measurement("600", "mm"),
      machineType: "Injection molding",
      moldBaseMaterial: "P20",
      spareParts: ["Seal kit"],
      surfaceTreatment: "Nitrided",
      targetCycle: measurement("35", "s"),
      targetLife: measurement("500000", "cycles"),
      tieBarSpacingX: measurement("700", "mm"),
      tieBarSpacingY: measurement("650", "mm"),
      toolingType: "Two-plate mold",
      warranty: "12 months",
      weight: measurement("820", "kg"),
      width: measurement("520", "mm"),
    },
    toolingMasterGlobalId: masterId,
  };
}

function revisionCollection(): ToolingRevisionCollectionViewModel {
  return {
    ...unavailable,
    items: [revision()],
    permissions,
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function revisionDetail(): ToolingRevisionDetailViewModel {
  return {
    ...unavailable,
    permissions,
    projectGlobalId: projectId,
    revision: revision(),
  };
}

function partContext(
  recorded = true,
): PartControlledSpecificationContextViewModel {
  return {
    automaticImpact: {
      reasonCode: "automatic_impact_not_delivered",
      state: "unavailable",
    },
    controlledSpecification: recorded
      ? {
          externalIdentities: [],
          globalId: controlledSpecificationId,
          items: [
            {
              effectiveFrom: "2026-08-08",
              effectiveTo: null,
              globalId: specificationItemId,
              kind: "material_family",
              normalizedValue: "PA66",
              rawValue: "PA66-GF30",
              sourceObjectId: "PART-SPEC-001",
              sourceSystem: "NPI_ONE",
              unit: null,
            },
          ],
          partGlobalId: partId,
          partRevisionGlobalId: partRevisionId,
          partRevisionSnapshotHash: "b".repeat(64),
          snapshotHash: "c".repeat(64),
        }
      : {
          reasonCode: "controlled_part_specification_not_recorded",
          state: "unavailable",
        },
    partGlobalId: partId,
    partRevision: {
      globalId: partRevisionId,
      partGlobalId: partId,
      revisionLabel: "A",
      revisionNumber: 1,
      snapshotHash: "b".repeat(64),
    },
    permissions,
    projectGlobalId: projectId,
  };
}

function processChain(): ToolingProcessChainRevisionViewModel {
  return {
    chainVersion: 1,
    globalId: processChainRevisionId,
    predecessorGlobalId: null,
    processChainGlobalId: processChainId,
    reason: "Primary molding and overmold sequence",
    snapshotHash: "d".repeat(64),
    steps: [
      {
        clampTonnage: measurement("180", "t"),
        globalId: firstStepId,
        inputPartRevisionGlobalIds: [partRevisionId],
        machineType: "Injection molding",
        outputPartRevisionGlobalId: partRevisionId,
        parentStepGlobalId: null,
        processKind: "primary_molding",
        stepOrder: 1,
        toolingRevisionGlobalId: toolingRevisionId,
        toolingRevisionSnapshotHash: "a".repeat(64),
      },
      {
        clampTonnage: measurement("120", "t"),
        globalId: secondStepId,
        inputPartRevisionGlobalIds: [partRevisionId],
        machineType: "Overmolding",
        outputPartRevisionGlobalId: partRevisionId,
        parentStepGlobalId: firstStepId,
        processKind: "overmold",
        stepOrder: 2,
        toolingRevisionGlobalId: toolingRevisionId,
        toolingRevisionSnapshotHash: "a".repeat(64),
      },
    ],
  };
}

function chainCollection(): ToolingProcessChainCollectionViewModel {
  return {
    combinedTrial: unavailable.combinedTrial,
    items: [processChain()],
    permissions,
    projectGlobalId: projectId,
  };
}

function cockpit(): ToolingCockpitViewModel {
  const source = {
    editableIn: "NPI_ONE" as const,
    sourceSystem: "NPI_ONE" as const,
    syncState: "local" as const,
  };
  return {
    applicability: [
      {
        effectiveFrom: "2026-08-08",
        effectiveTo: null,
        globalId: applicabilityId,
        model: null,
        part: {
          globalId: partRevisionId,
          partGlobalId: partId,
          revisionLabel: "A",
          revisionNumber: 1,
          snapshotHash: "b".repeat(64),
        },
        predecessorGlobalId: null,
        product: null,
        projectGlobalId: projectId,
        relationshipGlobalId: "87654321-4321-4321-8321-cba987654321",
        relationshipKeyHash: "e".repeat(64),
        snapshotHash: "f".repeat(64),
        toolingMasterGlobalId: masterId,
        version: 1,
      },
    ],
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
        reasonCode: "tooling_revision_available",
        revisionCount: 1,
        state: "available",
      },
      trial: { reasonCode: "trial_not_delivered", state: "unavailable" },
    },
    masters: [
      {
        globalId: masterId,
        originatingProjectGlobalId: projectId,
        snapshotHash: "1".repeat(64),
        source,
        title: "Synthetic revision-controlled mold",
      },
    ],
    parts: [
      {
        currentRevision: {
          globalId: partRevisionId,
          partGlobalId: partId,
          revisionLabel: "A",
          revisionNumber: 1,
          snapshotHash: "b".repeat(64),
        },
        globalId: partId,
        source,
        title: "Synthetic valve body",
        version: 1,
      },
    ],
    permissions: {
      createApplicability: false,
      createMaster: false,
      createPart: false,
      createRequirement: false,
      transitionLifecycle: false,
      view: true,
    },
    project: {
      businessCode: "SYN-PROJECT-003",
      globalId: projectId,
      title: "Synthetic Revision Project",
    },
    requirements: [
      {
        globalId: requirementId,
        kind: "customer_owned_intake",
        projectGlobalId: projectId,
        reason: "Controlled physical Set",
        snapshotHash: "2".repeat(64),
        targetDate: null,
        targetPartRevisionGlobalId: partRevisionId,
        title: "Controlled Set requirement",
      },
    ],
  };
}

function setCollection(): ToolingSetCollectionViewModel {
  return {
    items: [
      {
        custodyResponsibility: "Tool room custody",
        customer: null,
        erpLocationAndAsset: unavailable.erpLocationAndAsset,
        globalId: setId,
        lifecycle: unavailable.lifecycle,
        physicalSerial: "SET-REV-001",
        projectGlobalId: projectId,
        repairAuthorizationReference: "AUTH-REV-001",
        requirementKind: "customer_owned_intake",
        returnConditions: "Return after approved request",
        snapshotHash: "3".repeat(64),
        sourceRevision: {
          reasonCode: "tooling_revision_not_delivered",
          state: "unavailable",
        },
        supplier: unavailable.supplier,
        toolingMasterGlobalId: masterId,
        toolingRequirementGlobalId: requirementId,
      },
    ],
    permissions: {
      attachEvidence: false,
      createIntake: false,
      createSet: false,
      transitionLifecycle: false,
      view: true,
    },
    toolingMasterGlobalId: masterId,
  };
}

function setDetail(bound = false): ToolingSetDetailViewModel {
  const toolingSet = setCollection().items[0];
  if (!toolingSet) throw new Error("The Set fixture is required.");
  return {
    evidence: [],
    intakes: [],
    permissions: setCollection().permissions,
    toolingSet: bound
      ? {
          ...toolingSet,
          sourceRevision: {
            globalId: bindingId,
            reason: "Approved immutable source",
            snapshotHash: "4".repeat(64),
            toolingMasterGlobalId: masterId,
            toolingRevisionGlobalId: toolingRevisionId,
            toolingRevisionSnapshotHash: revision().snapshotHash,
            toolingSetGlobalId: setId,
            toolingSetSnapshotHash: toolingSet.snapshotHash,
          },
        }
      : toolingSet,
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
      "X-Trace-ID": "trace-p6-03-tooling-revision-browser",
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "5".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "tooling.engineer@example.invalid",
    });
  });
}

async function installApi(
  page: Page,
  options: { partRecorded?: boolean } = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(projectEndpoint, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
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
    if (path.endsWith(`/tooling/${masterId}/sets/${setId}/revision-binding`)) {
      await fulfillJson(route, setDetail(true), 201);
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/sets/${setId}`)) {
      await fulfillJson(route, setDetail());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/sets`)) {
      await fulfillJson(route, setCollection());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/revisions/${toolingRevisionId}`)) {
      await fulfillJson(route, revisionDetail());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/revisions`)) {
      await fulfillJson(
        route,
        request.method() === "POST" ? revisionDetail() : revisionCollection(),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.endsWith("/controlled-specification")) {
      await fulfillJson(
        route,
        partContext(
          request.method() === "POST" || options.partRecorded !== false,
        ),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.endsWith(`/tooling-process-chains/${processChainRevisionId}`)) {
      await fulfillJson(route, processChain());
      return;
    }
    if (path.endsWith("/tooling-process-chains")) {
      await fulfillJson(
        route,
        request.method() === "POST" ? processChain() : chainCollection(),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.endsWith(`/tooling/${masterId}`)) {
      await fulfillJson(route, cockpit());
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
  await expect(page.locator("#tooling-revision-workspace")).toBeVisible();
  await expect(page.getByText("R1 · 1")).toBeVisible();
  await expect(page.getByText("PA66", { exact: true })).toBeVisible();
  await expect(page.getByText("SET-REV-001").first()).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test.describe("P6-03 live immutable Tooling Revision workspace", () => {
  for (const locale of ["en", "zh", "zh-TW"] as const) {
    test(`renders Revision, controlled Part, process-chain and Set source truth in ${locale}`, async ({
      page,
    }) => {
      await installSession(page, locale);
      await installApi(page);
      await openWorkspace(page, locale);

      await expect(page.getByText("C01")).toBeVisible();
      await expect(page.getByText(processChainId)).toBeVisible();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }

  test("records one controlled Part specification through the frozen command", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page, { partRecorded: false });
    await page.goto(`/projects/${projectId}/tooling/${masterId}?lang=en`);
    const open = page.getByRole("button", {
      name: "Record controlled Part specification",
    });
    await expect(open).toBeVisible();
    await open.click();
    await page.getByLabel("Normalized value").fill("PA66");
    await page.getByLabel("Raw source value").fill("PA66-GF30");
    await page.getByLabel("Source object").fill("PART-SPEC-001");
    await page
      .getByRole("button", { name: "Record immutable specification" })
      .click();

    await expect
      .poll(
        () =>
          observed.filter(
            (request) =>
              request.method === "POST" &&
              request.path.endsWith("/controlled-specification"),
          ).length,
      )
      .toBe(1);
    expect(
      observed.find(
        (request) =>
          request.method === "POST" &&
          request.path.endsWith("/controlled-specification"),
      ),
    ).toMatchObject({
      payload: {
        externalIdentities: [],
        items: [
          {
            kind: "material_family",
            normalizedValue: "PA66",
            rawValue: "PA66-GF30",
            sourceObjectId: "PART-SPEC-001",
            sourceSystem: "NPI_ONE",
          },
        ],
      },
    });
  });

  test("creates one exact two-step process chain without guessing a predecessor", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page);
    await openWorkspace(page, "en");
    await page
      .getByRole("button", { name: "Create process chain Revision" })
      .click();
    await page.getByLabel("Reason").last().fill("Second controlled route");
    await page.getByLabel("Machine type").nth(0).fill("Press A");
    await page.getByLabel("Machine type").nth(1).fill("Press B");
    await page
      .getByRole("button", { name: "Create immutable process chain" })
      .click();

    await expect
      .poll(
        () =>
          observed.filter(
            (request) =>
              request.method === "POST" &&
              request.path.endsWith("/tooling-process-chains"),
          ).length,
      )
      .toBe(1);
    const command = observed.find(
      (request) =>
        request.method === "POST" &&
        request.path.endsWith("/tooling-process-chains"),
    );
    expect(command?.payload).toMatchObject({
      reason: "Second controlled route",
      steps: [
        { processKind: "primary_molding", stepOrder: 1 },
        { parentStepOrder: 1, processKind: "overmold", stepOrder: 2 },
      ],
    });
    expect(command?.payload).not.toHaveProperty("processChainGlobalId");
    expect(command?.payload).not.toHaveProperty("expectedVersion");
  });

  test("binds one exact immutable Revision to one physical Set", async ({
    page,
  }) => {
    await installSession(page, "en");
    const observed = await installApi(page);
    await openWorkspace(page, "en");
    await page
      .getByRole("button", { name: "Bind source Tooling Revision" })
      .click();
    await page.getByLabel("Binding reason").fill("Approved immutable source");
    await page
      .getByRole("button", { name: "Bind exact source Revision" })
      .click();

    await expect
      .poll(
        () =>
          observed.filter((request) =>
            request.path.endsWith(`/sets/${setId}/revision-binding`),
          ).length,
      )
      .toBe(1);
    expect(
      observed.find((request) =>
        request.path.endsWith(`/sets/${setId}/revision-binding`),
      ),
    ).toMatchObject({
      payload: {
        reason: "Approved immutable source",
        toolingRevisionGlobalId: toolingRevisionId,
      },
    });
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p6-03-tooling-revision-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p6-03-tooling-revision-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p6-03-tooling-revision-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P6-03 immutable Tooling Revision evidence", () => {
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
      await page
        .locator("#tooling-revision-workspace")
        .scrollIntoViewIfNeeded();
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
