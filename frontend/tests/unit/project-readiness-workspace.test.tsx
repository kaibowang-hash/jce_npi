import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ReportWorkspaceDirty,
  RequestWorkspaceTransition,
} from "../../src/app/workspace-navigation";
import type {
  ReadinessDataSource,
  ReadinessInstanceRevision,
  ReadinessItemDefinition,
  ReadinessItemSnapshot,
  ReadinessTemplateVersion,
  ReadinessWorkspace,
} from "../../src/api/readiness-data-source";
import {
  NpiApiError,
  NpiTransportError,
  type ProblemDetails,
} from "../../src/api/http";
import type { ProjectMemberViewModel } from "../../src/domain/view-models";
import { ProjectReadinessWorkspace } from "../../src/pages/project-readiness-workspace";
import { renderWithLocale } from "../support/render";

const ids = {
  project: "10000000-0000-4000-8000-000000000001",
  instance: "20000000-0000-4000-8000-000000000001",
  currentRevision: "30000000-0000-4000-8000-000000000002",
  historicalRevision: "30000000-0000-4000-8000-000000000001",
  templateRevision: "40000000-0000-4000-8000-000000000001",
  template: "41000000-0000-4000-8000-000000000001",
  qualityItem: "50000000-0000-4000-8000-000000000001",
  supplierItem: "50000000-0000-4000-8000-000000000002",
  launchItem: "50000000-0000-4000-8000-000000000003",
  gate: "60000000-0000-4000-8000-000000000001",
  memberOne: "70000000-0000-4000-8000-000000000001",
  memberTwo: "70000000-0000-4000-8000-000000000002",
  sourceOption: "80000000-0000-4000-8000-000000000001",
  controlledSource: "90000000-0000-4000-8000-000000000001",
} as const;

const csrfToken = "readiness-workspace-csrf-token-fixture-0001";

function hash(character: string): string {
  return character.repeat(64);
}

const members: readonly ProjectMemberViewModel[] = [
  {
    effectiveFrom: "2026-01-01",
    globalId: ids.memberOne,
    projectId: ids.project,
    userId: "quality@example.invalid",
    version: 1,
  },
  {
    effectiveFrom: "2026-01-01",
    globalId: ids.memberTwo,
    projectId: ids.project,
    userId: "supplier@example.invalid",
    version: 2,
  },
];

function gate() {
  return {
    gateKey: "G5",
    globalId: ids.gate,
    optimisticVersion: 3,
    snapshotHash: hash("a"),
  } as const;
}

function definition(
  key: string,
  title: string,
  categoryKey: string,
  options: Partial<ReadinessItemDefinition> = {},
): ReadinessItemDefinition {
  return {
    applicability: {
      customerReferenceKeys: [],
      industryKeys: [],
      projectTypes: [],
    },
    blockingLevel: "P1",
    categoryKey,
    completionRule: "exact_evidence",
    evidenceRequirements: [],
    gateKey: "G5",
    key,
    required: true,
    title,
    weight: 1,
    ...options,
  };
}

const qualityDefinition = definition(
  "quality-release",
  "Mandatory quality approval",
  "launch",
  {
    blockingLevel: "P0",
    completionRule: "exact_source_result",
    evidenceRequirements: [
      {
        acceptedSourceKinds: ["erp_quality_result"],
        key: "formal-quality",
        minimumCount: 1,
        unavailableBlocks: true,
      },
    ],
  },
);

const supplierDefinition = definition(
  "supplier-apqp",
  "Supplier APQP evidence",
  "supplier",
  {
    evidenceRequirements: [
      {
        acceptedSourceKinds: ["domain_work_item"],
        key: "supplier-action",
        minimumCount: 1,
        unavailableBlocks: false,
      },
      {
        acceptedSourceKinds: ["controlled_quality_result"],
        key: "supplier-report",
        minimumCount: 1,
        unavailableBlocks: false,
      },
    ],
  },
);

const launchDefinition = definition(
  "launch-plan",
  "Released launch plan",
  "launch",
  {
    blockingLevel: "none",
    completionRule: "confirmation",
    weight: 6,
  },
);

function owner(
  globalId: string = ids.memberOne,
  userId = "quality@example.invalid",
) {
  return { globalId, optimisticVersion: 1, userId };
}

function item(
  globalId: string,
  value: ReadinessItemDefinition,
  options: Partial<ReadinessItemSnapshot> = {},
): ReadinessItemSnapshot {
  return {
    applicable: true,
    confirmationValue: null,
    definition: value,
    dueDate: "2026-08-31",
    gate: gate(),
    globalId,
    itemVersion: 2,
    owner: owner(),
    sources: [],
    state: "complete",
    ...options,
  };
}

function revision(version: 1 | 2): ReadinessInstanceRevision {
  const quality = item(ids.qualityItem, qualityDefinition, {
    itemVersion: version,
    sources: [
      {
        globalId: null,
        kind: "erp_quality_result",
        reasonCode: "erp_quality_result_provider_unavailable",
        requirementKey: "formal-quality",
        snapshotHash: null,
        sourceVersion: null,
        state: "unavailable",
      },
    ],
    state: "failed",
  });
  const supplier = item(ids.supplierItem, supplierDefinition, {
    confirmationValue: "Controlled supplier review retained.",
    itemVersion: version,
    owner: owner(ids.memberTwo, "supplier@example.invalid"),
    sources: [
      {
        globalId: ids.controlledSource,
        kind: "controlled_quality_result",
        reasonCode: null,
        requirementKey: "supplier-report",
        snapshotHash: hash("b"),
        sourceVersion: 4,
        state: "satisfied",
      },
    ],
    state: version === 1 ? "in_progress" : "complete",
  });
  const launch = item(ids.launchItem, launchDefinition, {
    confirmationValue: "Launch plan released.",
    itemVersion: version,
  });
  const earnedWeight = version === 1 ? 6 : 7;
  const current = version === 2;
  return {
    categories: [
      { key: "launch", title: "Launch readiness" },
      { key: "supplier", title: "Supplier readiness" },
    ],
    createdAt: current ? "2026-08-11T08:30:00Z" : "2026-08-10T08:30:00Z",
    createdByUserId: "administrator@example.invalid",
    evaluation: {
      blockers: [
        {
          code: "required_source_unavailable",
          gate: gate(),
          itemGlobalId: ids.qualityItem,
          itemKey: qualityDefinition.key,
        },
      ],
      categoryScores: [
        {
          applicableWeight: 7,
          basisPoints: 8571,
          categoryKey: "launch",
          earnedWeight: 6,
          state: "scored",
        },
        {
          applicableWeight: 1,
          basisPoints: current ? 10_000 : 0,
          categoryKey: "supplier",
          earnedWeight: current ? 1 : 0,
          state: "scored",
        },
      ],
      formulaVersion: "readiness-score.v1",
      ready: false,
      totalScore: {
        applicableWeight: 8,
        basisPoints: current ? 8750 : 7500,
        categoryKey: null,
        earnedWeight,
        state: "scored",
      },
    },
    globalId: current ? ids.currentRevision : ids.historicalRevision,
    instanceGlobalId: ids.instance,
    instanceVersion: version,
    items: [quality, supplier, launch],
    predecessorGlobalId: current ? ids.historicalRevision : null,
    predecessorSnapshotHash: current ? hash("c") : null,
    project: {
      customerReferenceKeys: ["customer-ref-1"],
      globalId: ids.project,
      industryKey: "automotive",
      optimisticVersion: 7,
      projectType: "new_tool",
      snapshotHash: hash("d"),
    },
    requestId: current
      ? "a0000000-0000-4000-8000-000000000002"
      : "a0000000-0000-4000-8000-000000000001",
    snapshotHash: current ? hash("e") : hash("c"),
    templateRevision: {
      globalId: ids.templateRevision,
      snapshotHash: hash("f"),
      version: 1,
    },
    tenantId: "tenant-fixture",
    traceId: current ? "trace-readiness-2" : "trace-readiness-1",
    versionKeyHash: current ? hash("1") : hash("2"),
  };
}

function workspace(
  options: {
    empty?: boolean;
    canInitialize?: boolean;
    canRevise?: boolean;
  } = {},
): ReadinessWorkspace {
  const historical = revision(1);
  const current = revision(2);
  return {
    currentRevision: options.empty ? null : current,
    permissions: {
      canInitialize: options.canInitialize ?? true,
      canManageTemplates: false,
      canRevise: options.canRevise ?? true,
    },
    projectGlobalId: ids.project,
    revisions: options.empty ? [] : [historical, current],
    sourceOptions: [
      {
        globalId: ids.sourceOption,
        kind: "domain_work_item",
        label: "Close supplier capability action",
        snapshotHash: hash("3"),
        sourceVersion: 5,
        stateLabelSource: "Open",
        stateTerminal: false,
      },
    ],
    unavailableProjections: [
      {
        kind: "erp_hr_qualification",
        reasonCode: "erp_hr_qualification_provider_unavailable",
        state: "unavailable",
      },
      {
        kind: "erp_material_specification",
        reasonCode: "erp_material_specification_provider_unavailable",
        state: "unavailable",
      },
      {
        kind: "erp_quality_result",
        reasonCode: "erp_quality_result_provider_unavailable",
        state: "unavailable",
      },
      {
        kind: "erp_run_at_rate",
        reasonCode: "erp_run_at_rate_provider_unavailable",
        state: "unavailable",
      },
      {
        kind: "erp_supplier_execution",
        reasonCode: "erp_supplier_execution_provider_unavailable",
        state: "unavailable",
      },
    ],
  };
}

function template(): ReadinessTemplateVersion {
  return {
    applicability: {
      customerReferenceKeys: [],
      industryKeys: [],
      projectTypes: [],
    },
    categories: [
      { key: "launch", title: "Launch readiness" },
      { key: "supplier", title: "Supplier readiness" },
    ],
    changedAt: "2026-08-09T08:00:00Z",
    changedByUserId: "administrator@example.invalid",
    globalId: ids.templateRevision,
    items: [qualityDefinition, supplierDefinition, launchDefinition],
    optimisticVersion: 1,
    publicationState: "published",
    requestId: "b0000000-0000-4000-8000-000000000001",
    snapshotHash: hash("f"),
    templateCode: "NPI-AUTO",
    templateGlobalId: ids.template,
    templateVersion: 1,
    title: "Automotive launch readiness",
    traceId: "trace-template-1",
  };
}

function createDataSource(
  overrides: Partial<ReadinessDataSource> = {},
): ReadinessDataSource {
  const value = workspace();
  return {
    createTemplate: () => Promise.reject(new Error("not configured")),
    editTemplate: () => Promise.reject(new Error("not configured")),
    initialize: () => Promise.resolve({ replayed: false, workspace: value }),
    listEligibleTemplates: () =>
      Promise.resolve({
        projectGlobalId: ids.project,
        templates: [template()],
      }),
    loadWorkspace: () => Promise.resolve(value),
    publishTemplate: () => Promise.reject(new Error("not configured")),
    reviseItem: () => Promise.resolve({ replayed: false, workspace: value }),
    ...overrides,
  };
}

function enableCommandSession(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: {
              language: "en",
              messages: {},
              version: hash("4"),
            },
            csrfToken,
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "administrator@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

function problem(
  status: number,
  code: string,
  options: {
    fieldErrors?: ProblemDetails["fieldErrors"];
    retryable?: boolean;
  } = {},
): NpiApiError {
  return new NpiApiError({
    code,
    ...(options.fieldErrors ? { fieldErrors: options.fieldErrors } : {}),
    retryable: options.retryable ?? false,
    status,
    title: `Controlled ${code} response`,
    traceId: `trace-${code.toLowerCase()}`,
    type: `urn:npi:problem:${code.toLowerCase()}`,
  });
}

function renderWorkspace(
  dataSource: ReadinessDataSource,
  options: {
    members?: readonly ProjectMemberViewModel[];
    reportWorkspaceDirty?: ReportWorkspaceDirty;
    requestWorkspaceTransition?: RequestWorkspaceTransition;
  } = {},
): void {
  renderWithLocale(
    <ProjectReadinessWorkspace
      dataSource={dataSource}
      members={options.members ?? members}
      projectId={ids.project}
      reportWorkspaceDirty={options.reportWorkspaceDirty}
      requestWorkspaceTransition={options.requestWorkspaceTransition}
    />,
    "en",
    `/projects/${ids.project}?tab=readiness`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Project readiness workspace", () => {
  it("shows an honest loading state before protected readiness data resolves", () => {
    renderWorkspace(
      createDataSource({
        loadWorkspace: () => new Promise<ReadinessWorkspace>(() => undefined),
      }),
    );

    expect(screen.getByTestId("readiness-loading")).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(
      screen.queryByText("Mandatory quality approval"),
    ).not.toBeInTheDocument();
  });

  it("renders blocker-first server scores, exact evidence, and unavailable formal holds", async () => {
    renderWorkspace(createDataSource());

    expect(
      await screen.findByRole("heading", {
        name: "Readiness blockers and score",
      }),
    ).toBeVisible();
    const blocker = screen.getByTestId("readiness-blocker-summary");
    const score = screen.getByTestId("readiness-score-summary");
    expect(
      blocker.compareDocumentPosition(score) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(within(blocker).getByText("1 active blockers")).toBeVisible();
    expect(within(score).getByText("88%")).toBeVisible();
    expect(
      screen.getAllByText("Mandatory quality approval").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByTestId("readiness-source-formal-quality-erp_quality_result"),
    ).toBeVisible();
    expect(screen.getAllByText("Formal ERP quality result")[0]).toBeVisible();
    expect(
      screen.getByTestId("readiness-unavailable-projections"),
    ).toBeVisible();
  });

  it("opens an exact item by keyboard and keeps historical revisions read-only", async () => {
    const user = userEvent.setup();
    renderWorkspace(createDataSource());

    const supplier = await screen.findByTestId("readiness-item-supplier-apqp");
    expect(supplier).toHaveAttribute(
      "data-language-exempt-tokens",
      JSON.stringify(["Supplier APQP evidence"]),
    );
    supplier.focus();
    await user.keyboard("{Enter}");
    expect(screen.getAllByText("Supplier APQP evidence")[0]).toBeVisible();
    expect(
      screen.getByTestId(
        "readiness-source-supplier-report-controlled_quality_result",
      ),
    ).toBeVisible();

    await user.click(screen.getByTestId("readiness-revision-1"));
    expect(screen.getByText("Historical revision")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Review readiness revision" }),
    ).not.toBeInTheDocument();
    expect(
      within(screen.getByTestId("readiness-score-summary")).getByText("75%"),
    ).toBeVisible();
  });

  it("guards category, item, and history navigation while an item draft is dirty", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const requestWorkspaceTransition = vi.fn<RequestWorkspaceTransition>(
      (perform) => {
        perform();
      },
    );
    renderWorkspace(createDataSource(), { requestWorkspaceTransition });

    await user.click(await screen.findByTestId("readiness-item-supplier-apqp"));
    requestWorkspaceTransition.mockClear();
    requestWorkspaceTransition.mockImplementation(() => undefined);
    const dueDate = screen.getByTestId("readiness-due-date");
    await user.clear(dueDate);
    await user.type(dueDate, "2026-09-18");

    await user.click(screen.getByTestId("readiness-category-launch"));
    await user.click(screen.getByTestId("readiness-item-launch-plan"));
    await user.click(screen.getByTestId("readiness-revision-1"));

    expect(requestWorkspaceTransition).toHaveBeenCalledTimes(3);
    expect(screen.getByTestId("readiness-due-date")).toHaveValue("2026-09-18");
    expect(screen.queryByText("Historical revision")).not.toBeInTheDocument();
  });

  it("reviews before revise, preserves exact sources, retries the same identity, and reports replay", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const firstFailure = new NpiTransportError(
      "network",
      "request-readiness-retry",
      "request",
    );
    const reviseItem = vi
      .fn<ReadinessDataSource["reviseItem"]>()
      .mockRejectedValueOnce(firstFailure)
      .mockResolvedValueOnce({ replayed: true, workspace: workspace() });
    const reportWorkspaceDirty = vi.fn<ReportWorkspaceDirty>();
    renderWorkspace(createDataSource({ reviseItem }), { reportWorkspaceDirty });

    await user.click(await screen.findByTestId("readiness-item-supplier-apqp"));
    const review = await screen.findByRole("button", {
      name: "Review readiness revision",
    });
    await user.selectOptions(
      screen.getByTestId("readiness-owner"),
      ids.memberOne,
    );
    await user.clear(screen.getByTestId("readiness-due-date"));
    await user.type(screen.getByTestId("readiness-due-date"), "2026-09-15");
    const source = within(
      screen.getByTestId("readiness-source-options"),
    ).getByRole("checkbox");
    await user.click(source);

    await waitFor(() => {
      expect(reportWorkspaceDirty).toHaveBeenLastCalledWith(
        expect.objectContaining({
          objectIdentity: `${ids.instance}:${ids.supplierItem}`,
          version: "readiness-v2",
        }),
      );
    });
    await user.click(review);
    expect(reviseItem).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog", {
      name: "Review readiness revision",
    });
    await user.click(
      within(dialog).getByRole("button", { name: "Append readiness revision" }),
    );
    await waitFor(() => {
      expect(reviseItem).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText("Command failed")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Retry same command" }),
    );
    await waitFor(() => {
      expect(reviseItem).toHaveBeenCalledTimes(2);
    });

    const firstCall = reviseItem.mock.calls[0];
    const retryCall = reviseItem.mock.calls[1];
    expect(firstCall?.[0]).toBe(ids.project);
    expect(firstCall?.[1]).toBe(ids.instance);
    expect(firstCall?.[2]).toMatchObject({
      dueDate: "2026-09-15",
      expectedInstanceVersion: 2,
      expectedRevisionGlobalId: ids.currentRevision,
      itemKey: "supplier-apqp",
      ownerMemberGlobalId: ids.memberOne,
      state: "complete",
    });
    expect(firstCall?.[2].sources).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          globalId: ids.controlledSource,
          kind: "controlled_quality_result",
          requirementKey: "supplier-report",
          sourceVersion: 4,
        }),
        expect.objectContaining({
          globalId: ids.sourceOption,
          kind: "domain_work_item",
          requirementKey: "supplier-action",
          sourceVersion: 5,
        }),
      ]),
    );
    expect(firstCall?.[2]).not.toHaveProperty("evaluation");
    expect(firstCall?.[2]).not.toHaveProperty("ready");
    expect(firstCall?.[3].idempotencyKey).toMatch(/^readiness-revise-/u);
    expect(retryCall?.[3].idempotencyKey).toBe(firstCall?.[3].idempotencyKey);
    expect(await screen.findByTestId("readiness-replay-receipt")).toBeVisible();
    await waitFor(() => {
      expect(reportWorkspaceDirty).toHaveBeenLastCalledWith(null);
    });
  });

  it("blocks an incomplete controlled confirmation before opening review", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const reviseItem = vi.fn<ReadinessDataSource["reviseItem"]>();
    renderWorkspace(createDataSource({ reviseItem }));

    await user.click(await screen.findByTestId("readiness-item-launch-plan"));
    const confirmation = await screen.findByTestId("readiness-confirmation");
    await user.clear(confirmation);
    await user.click(
      screen.getByRole("button", { name: "Review readiness revision" }),
    );

    expect(
      screen.getByText("Enter the controlled confirmation before completion."),
    ).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(reviseItem).not.toHaveBeenCalled();
  });

  it("initializes only after impact review with exact template and member assignments", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const initialize = vi.fn<ReadinessDataSource["initialize"]>(() =>
      Promise.resolve({ replayed: true, workspace: workspace() }),
    );
    const reportWorkspaceDirty = vi.fn<ReportWorkspaceDirty>();
    renderWorkspace(
      createDataSource({
        initialize,
        loadWorkspace: () => Promise.resolve(workspace({ empty: true })),
      }),
      { reportWorkspaceDirty },
    );

    expect(
      await screen.findByRole("heading", {
        name: "NPI readiness has not been initialized",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("option", { name: "Automotive launch readiness" }),
    ).toHaveAttribute(
      "data-language-exempt-tokens",
      JSON.stringify(["Automotive launch readiness"]),
    );
    await user.selectOptions(
      screen.getByTestId("readiness-template"),
      ids.templateRevision,
    );
    await user.type(screen.getByTestId("readiness-industry-key"), "automotive");
    for (const itemKey of ["quality-release", "supplier-apqp", "launch-plan"]) {
      await user.selectOptions(
        screen.getByTestId(`readiness-assignment-owner-${itemKey}`),
        ids.memberOne,
      );
      await user.type(
        screen.getByTestId(`readiness-assignment-due-${itemKey}`),
        "2026-10-01",
      );
    }
    await user.click(screen.getByTestId("readiness-initialize"));
    expect(initialize).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog", {
      name: "Review readiness initialization",
    });
    await user.click(
      within(dialog).getByRole("button", { name: "Initialize NPI readiness" }),
    );
    await waitFor(() => {
      expect(initialize).toHaveBeenCalledTimes(1);
    });
    const call = initialize.mock.calls[0];
    expect(call?.[0]).toBe(ids.project);
    expect(call?.[1]).toMatchObject({
      industryKey: "automotive",
      templateRevisionGlobalId: ids.templateRevision,
      templateSnapshotHash: hash("f"),
      templateVersion: 1,
    });
    expect(call?.[1].assignments).toHaveLength(3);
    expect(call?.[2].idempotencyKey).toMatch(/^readiness-initialize-/u);
    expect(await screen.findByTestId("readiness-replay-receipt")).toBeVisible();
    await waitFor(() => {
      expect(reportWorkspaceDirty).toHaveBeenLastCalledWith(null);
    });
  });

  it("blocks Project/customer selector guessing and an ineligible template industry without POST", async () => {
    enableCommandSession();
    const initialize = vi.fn<ReadinessDataSource["initialize"]>();
    const constrainedTemplate: ReadinessTemplateVersion = {
      ...template(),
      items: [
        {
          ...qualityDefinition,
          applicability: {
            customerReferenceKeys: [],
            industryKeys: [],
            projectTypes: ["new_tool"],
          },
        },
      ],
    };
    const constrained = renderWithLocale(
      <ProjectReadinessWorkspace
        dataSource={createDataSource({
          initialize,
          listEligibleTemplates: () =>
            Promise.resolve({
              projectGlobalId: ids.project,
              templates: [constrainedTemplate],
            }),
          loadWorkspace: () => Promise.resolve(workspace({ empty: true })),
        })}
        members={members}
        projectId={ids.project}
      />,
      "en",
      `/projects/${ids.project}?tab=readiness`,
    );

    expect(
      await screen.findByText("No safely initializable readiness template"),
    ).toBeVisible();
    expect(
      screen.queryByTestId("readiness-initialize"),
    ).not.toBeInTheDocument();
    expect(initialize).not.toHaveBeenCalled();
    constrained.unmount();

    const user = userEvent.setup();
    const industryTemplate: ReadinessTemplateVersion = {
      ...template(),
      applicability: {
        customerReferenceKeys: [],
        industryKeys: ["medical"],
        projectTypes: [],
      },
    };
    renderWorkspace(
      createDataSource({
        initialize,
        listEligibleTemplates: () =>
          Promise.resolve({
            projectGlobalId: ids.project,
            templates: [industryTemplate],
          }),
        loadWorkspace: () => Promise.resolve(workspace({ empty: true })),
      }),
    );
    await user.selectOptions(
      await screen.findByTestId("readiness-template"),
      ids.templateRevision,
    );
    await user.type(screen.getByTestId("readiness-industry-key"), "automotive");
    for (const itemKey of ["quality-release", "supplier-apqp", "launch-plan"]) {
      await user.selectOptions(
        screen.getByTestId(`readiness-assignment-owner-${itemKey}`),
        ids.memberOne,
      );
      await user.type(
        screen.getByTestId(`readiness-assignment-due-${itemKey}`),
        "2026-10-01",
      );
    }
    await user.click(screen.getByTestId("readiness-initialize"));
    expect(
      screen.getByText(
        "The selected template does not apply to this industry key.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(initialize).not.toHaveBeenCalled();
  });

  it("submits only industry-applicable items from the safe initialization subset", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const initialize = vi.fn<ReadinessDataSource["initialize"]>(() =>
      Promise.resolve({ replayed: false, workspace: workspace() }),
    );
    const industryTemplate: ReadinessTemplateVersion = {
      ...template(),
      items: [
        {
          ...qualityDefinition,
          applicability: {
            customerReferenceKeys: [],
            industryKeys: ["automotive"],
            projectTypes: [],
          },
        },
        {
          ...supplierDefinition,
          applicability: {
            customerReferenceKeys: [],
            industryKeys: ["medical"],
            projectTypes: [],
          },
        },
        launchDefinition,
      ],
    };
    renderWorkspace(
      createDataSource({
        initialize,
        listEligibleTemplates: () =>
          Promise.resolve({
            projectGlobalId: ids.project,
            templates: [industryTemplate],
          }),
        loadWorkspace: () => Promise.resolve(workspace({ empty: true })),
      }),
    );

    await user.selectOptions(
      await screen.findByTestId("readiness-template"),
      ids.templateRevision,
    );
    await user.type(screen.getByTestId("readiness-industry-key"), "automotive");
    expect(
      screen.queryByTestId("readiness-assignment-owner-supplier-apqp"),
    ).not.toBeInTheDocument();
    for (const itemKey of ["quality-release", "launch-plan"]) {
      await user.selectOptions(
        screen.getByTestId(`readiness-assignment-owner-${itemKey}`),
        ids.memberOne,
      );
      await user.type(
        screen.getByTestId(`readiness-assignment-due-${itemKey}`),
        "2026-10-01",
      );
    }
    await user.click(screen.getByTestId("readiness-initialize"));
    await user.click(
      within(
        screen.getByRole("dialog", {
          name: "Review readiness initialization",
        }),
      ).getByRole("button", { name: "Initialize NPI readiness" }),
    );
    await waitFor(() => {
      expect(initialize).toHaveBeenCalledTimes(1);
    });
    expect(initialize.mock.calls[0]?.[1].assignments).toEqual([
      {
        dueDate: "2026-10-01",
        itemKey: "quality-release",
        ownerMemberGlobalId: ids.memberOne,
      },
      {
        dueDate: "2026-10-01",
        itemKey: "launch-plan",
        ownerMemberGlobalId: ids.memberOne,
      },
    ]);
  });

  it("shows honest empty, no-template, no-member, and read-only states", async () => {
    const source = createDataSource({
      listEligibleTemplates: () =>
        Promise.resolve({ projectGlobalId: ids.project, templates: [] }),
      loadWorkspace: () => Promise.resolve(workspace({ empty: true })),
    });
    const rendered = renderWithLocale(
      <ProjectReadinessWorkspace
        dataSource={source}
        members={[]}
        projectId={ids.project}
      />,
      "en",
      `/projects/${ids.project}?tab=readiness`,
    );

    expect(
      await screen.findByText("No eligible published readiness template"),
    ).toBeVisible();
    rendered.unmount();

    const noMembers = renderWithLocale(
      <ProjectReadinessWorkspace
        dataSource={createDataSource({
          loadWorkspace: () => Promise.resolve(workspace({ empty: true })),
        })}
        members={[]}
        projectId={ids.project}
      />,
      "en",
      `/projects/${ids.project}?tab=readiness`,
    );
    expect(
      await screen.findByText("No Project members available"),
    ).toBeVisible();
    expect(
      screen.queryByTestId("readiness-initialize"),
    ).not.toBeInTheDocument();
    noMembers.unmount();

    renderWorkspace(
      createDataSource({
        loadWorkspace: () =>
          Promise.resolve(workspace({ canInitialize: false, empty: true })),
      }),
      { members: [] },
    );
    expect(
      await screen.findByText("You have read-only access to this workspace."),
    ).toBeVisible();
    expect(
      screen.queryByTestId("readiness-initialize"),
    ).not.toBeInTheDocument();
  });

  it("does not expose revision controls without server permission", async () => {
    enableCommandSession();
    renderWorkspace(
      createDataSource({
        loadWorkspace: () => Promise.resolve(workspace({ canRevise: false })),
      }),
    );

    expect(
      (await screen.findAllByText("Read-only workspace"))[0],
    ).toBeVisible();
    expect(screen.queryByTestId("readiness-revise")).not.toBeInTheDocument();
    expect(screen.getByTestId("readiness-history")).toBeVisible();
  });

  it("offers no owner candidate when Project member containment is ambiguous", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const firstMember = members[0];
    const secondMember = members[1];
    if (!firstMember || !secondMember)
      throw new Error("The readiness fixture requires two Project members.");
    const duplicateMembers: readonly ProjectMemberViewModel[] = [
      firstMember,
      {
        ...secondMember,
        globalId: ids.memberOne,
      },
    ];
    renderWorkspace(createDataSource(), { members: duplicateMembers });

    await user.click(await screen.findByTestId("readiness-item-supplier-apqp"));
    expect(screen.getByText("No exact owner candidates")).toBeVisible();
    expect(screen.queryByTestId("readiness-owner")).not.toBeInTheDocument();
    expect(screen.getAllByText("supplier@example.invalid")[0]).toBeVisible();
  });

  it("blocks a retained owner outside the exact Project member candidates", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const reviseItem = vi.fn<ReadinessDataSource["reviseItem"]>();
    const firstMember = members[0];
    if (!firstMember)
      throw new Error("The readiness fixture requires a Project member.");
    renderWorkspace(createDataSource({ reviseItem }), {
      members: [firstMember],
    });

    await user.click(await screen.findByTestId("readiness-item-supplier-apqp"));
    await user.clear(screen.getByTestId("readiness-due-date"));
    await user.type(screen.getByTestId("readiness-due-date"), "2026-09-19");
    await user.click(
      screen.getByRole("button", { name: "Review readiness revision" }),
    );

    expect(screen.getByText("Select an exact Project member.")).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(reviseItem).not.toHaveBeenCalled();
  });

  it("renders optimistic conflict as input drift and requires a fresh reload", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const reviseItem = vi
      .fn<ReadinessDataSource["reviseItem"]>()
      .mockRejectedValue(problem(409, "READINESS_CONFLICT"));
    renderWorkspace(createDataSource({ reviseItem }));

    await user.click(await screen.findByTestId("readiness-item-supplier-apqp"));
    await user.clear(screen.getByTestId("readiness-due-date"));
    await user.type(screen.getByTestId("readiness-due-date"), "2026-09-16");
    await user.click(
      screen.getByRole("button", { name: "Review readiness revision" }),
    );
    await user.click(
      within(
        screen.getByRole("dialog", { name: "Review readiness revision" }),
      ).getByRole("button", { name: "Append readiness revision" }),
    );

    expect(await screen.findByText("Input drift")).toBeVisible();
    expect(
      screen.getByText(
        "The retained readiness revision changed. Reload before editing again.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry same command" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reload latest data" }),
    ).toBeVisible();
  });

  it("maps permission and drift failures without exposing protected readiness data", async () => {
    const loadWorkspace = vi
      .fn<ReadinessDataSource["loadWorkspace"]>()
      .mockRejectedValue(
        problem(403, "READINESS_PERMISSION_DENIED", { retryable: false }),
      );
    renderWorkspace(createDataSource({ loadWorkspace }));

    expect(
      await screen.findByRole("heading", {
        name: "NPI readiness access is not available",
      }),
    ).toBeVisible();
    expect(
      screen.getByText("No protected readiness data was displayed."),
    ).toBeVisible();
    expect(
      screen.queryByText("Mandatory quality approval"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
  });
});
