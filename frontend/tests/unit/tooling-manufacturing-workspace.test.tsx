import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ToolingDataSource,
  ToolingManufacturingMilestoneObservationViewModel,
  ToolingManufacturingPlanCollectionViewModel,
  ToolingManufacturingPlanDetailViewModel,
  ToolingManufacturingPlanRevisionViewModel,
  ToolingReleasedDocumentEvidenceViewModel,
  ToolingRevisionCollectionViewModel,
} from "../../src/api/tooling-data-source";
import { NpiApiError, NpiTransportError } from "../../src/api/http";
import ToolingManufacturingWorkspace from "../../src/pages/tooling-manufacturing-workspace";
import { renderWithLocale } from "../support/render";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const revisionId = "33333333-3333-4333-8333-333333333333";
const planId = "44444444-4444-4444-8444-444444444444";
const planRevisionId = "55555555-5555-4555-8555-555555555555";
const memberId = "66666666-6666-4666-8666-666666666666";
const milestoneId = "77777777-7777-4777-8777-777777777777";
const observationId = "88888888-8888-4888-8888-888888888888";
const documentRevisionId = "99999999-9999-4999-8999-999999999999";
const lifecycleId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const releaseEventId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const hash = (value: string) => value.repeat(64);

function required<T>(value: T | undefined): T {
  if (value === undefined)
    throw new Error("The test fixture value is required.");
  return value;
}

function released(): ToolingReleasedDocumentEvidenceViewModel {
  return {
    lifecycleGlobalId: lifecycleId,
    lifecycleVersion: 2,
    releaseEventGlobalId: releaseEventId,
    releaseEventHash: hash("b"),
    releaseSnapshotHash: hash("c"),
    revisionGlobalId: documentRevisionId,
    revisionSnapshotHash: hash("a"),
  };
}

function plan(): ToolingManufacturingPlanRevisionViewModel {
  return {
    budget: { amount: "125000.00", currency: "CNY" },
    designReleaseEvidence: [released()],
    engineeringEstimate: { amount: "120000", currency: "CNY" },
    evidence: [{ document: released(), role: "dfm" }],
    globalId: planRevisionId,
    milestones: [
      {
        category: "machining",
        globalId: milestoneId,
        plannedFinish: "2026-09-20",
        plannedStart: "2026-09-01",
        predecessorGlobalIds: [],
        responsibleMember: null,
        responsibilityKind: "supplier",
        sequence: 1,
        snapshotHash: hash("d"),
      },
    ],
    planGlobalId: planId,
    planVersion: 1,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    reason: "Initial controlled manufacturing plan",
    responsibleMember: {
      globalId: memberId,
      optimisticVersion: 3,
      userId: "tooling.engineer@example.invalid",
    },
    snapshotHash: hash("e"),
    sourcingStrategy: "hybrid",
    toolingMasterGlobalId: masterId,
    toolingRevisionGlobalId: revisionId,
    toolingRevisionSnapshotHash: hash("f"),
  };
}

function observation(
  version = 1,
): ToolingManufacturingMilestoneObservationViewModel {
  return {
    actualFinish: null,
    actualStart: "2026-09-02",
    evidence: [],
    globalId: observationId,
    milestoneGlobalId: milestoneId,
    milestoneSnapshotHash: hash("d"),
    note: "Machining fixture completed",
    observationVersion: version,
    planRevisionGlobalId: planRevisionId,
    planRevisionSnapshotHash: hash("e"),
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    progressPercentage: 40,
    reportedByMember: {
      globalId: memberId,
      optimisticVersion: 3,
      userId: "tooling.engineer@example.invalid",
    },
    risk: "Cooling insert lead time",
    snapshotHash: hash("1"),
  };
}

function collection(
  overrides: Partial<ToolingManufacturingPlanCollectionViewModel> = {},
): ToolingManufacturingPlanCollectionViewModel {
  return {
    erpProjection: {
      editableIn: "ERPNEXT",
      reasonCode: "erp_projection_unavailable",
      sourceSystem: "ERPNEXT",
      state: "unavailable",
    },
    items: [
      {
        designReleaseEvidence: {
          items: [released()],
          reasonCode: null,
          state: "satisfied",
        },
        observations: [observation()],
        plan: plan(),
      },
    ],
    manufacturingAuthorization: {
      reasonCode: "tooling_lifecycle_policy_unavailable",
      state: "unavailable",
    },
    permissions: {
      createPlan: true,
      editErpProjection: false,
      observeMilestone: true,
      transitionLifecycle: false,
      view: true,
    },
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
    ...overrides,
  };
}

function detail(value = collection()): ToolingManufacturingPlanDetailViewModel {
  const item = value.items[0];
  if (!item) throw new Error("The manufacturing item fixture is required.");
  return {
    erpProjection: value.erpProjection,
    item,
    manufacturingAuthorization: value.manufacturingAuthorization,
    permissions: value.permissions,
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function revisions(): ToolingRevisionCollectionViewModel {
  return {
    items: [
      {
        globalId: revisionId,
        revisionLabel: "R1",
        revisionNumber: 1,
        snapshotHash: hash("f"),
      },
    ],
  } as unknown as ToolingRevisionCollectionViewModel;
}

function dataSource(
  overrides: Partial<ToolingDataSource> = {},
): ToolingDataSource {
  const value = collection();
  return {
    createManufacturingObservation: vi.fn(() =>
      Promise.resolve({ observation: observation(2) }),
    ),
    createManufacturingPlan: vi.fn(() =>
      Promise.resolve({
        designReleaseEvidence: value.items[0]?.designReleaseEvidence,
        plan: plan(),
      }),
    ),
    loadManufacturingPlan: vi.fn(() => Promise.resolve(detail(value))),
    loadManufacturingPlans: vi.fn(() => Promise.resolve(value)),
    loadToolingRevisions: vi.fn(() => Promise.resolve(revisions())),
    ...overrides,
  } as unknown as ToolingDataSource;
}

function enableCommandSession(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: { language: "en", messages: {}, version: hash("a") },
            csrfToken: "tooling-manufacturing-workspace-csrf-token",
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "tooling.engineer@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

function renderWorkspace(source: ToolingDataSource): void {
  renderWithLocale(
    <ToolingManufacturingWorkspace
      dataSource={source}
      masterId={masterId}
      projectId={projectId}
    />,
    "en",
    `/projects/${projectId}/tooling/${masterId}`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Tooling manufacturing workspace", () => {
  it("keeps loading explicit and renders a server-controlled empty read-only state", async () => {
    let resolvePlans:
      | ((value: ToolingManufacturingPlanCollectionViewModel) => void)
      | undefined;
    const plans = new Promise<ToolingManufacturingPlanCollectionViewModel>(
      (resolve) => {
        resolvePlans = resolve;
      },
    );
    renderWorkspace(dataSource({ loadManufacturingPlans: () => plans }));

    expect(
      await screen.findByText("Loading manufacturing plan workspace"),
    ).toBeVisible();
    resolvePlans?.(
      collection({
        items: [],
        permissions: {
          createPlan: false,
          editErpProjection: false,
          observeMilestone: false,
          transitionLifecycle: false,
          view: true,
        },
      }),
    );

    expect(
      await screen.findByText("No manufacturing plan has been recorded."),
    ).toBeVisible();
    expect(
      screen.getByText("Manufacturing history is read only for this account."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Create manufacturing plan" }),
    ).not.toBeInTheDocument();
  });

  it("retries an evidence-backed collection transport failure", async () => {
    const loadPlans = vi
      .fn<ToolingDataSource["loadManufacturingPlans"]>()
      .mockRejectedValueOnce(
        new NpiTransportError(
          "network",
          "trace-manufacturing-network",
          "trace",
        ),
      )
      .mockResolvedValueOnce(collection());
    const user = userEvent.setup();
    renderWorkspace(dataSource({ loadManufacturingPlans: loadPlans }));

    await user.click(await screen.findByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("region", { name: "Manufacturing plan history" }),
    ).toBeVisible();
    expect(loadPlans).toHaveBeenCalledTimes(2);
  });

  it("separates design release, manufacturing authorization and ERP truth", async () => {
    renderWorkspace(dataSource());

    expect(
      await screen.findByRole("region", { name: "Manufacturing plan history" }),
    ).toBeVisible();
    expect(
      screen.getByText("Every exact Design Document Revision is released."),
    ).toBeVisible();
    expect(
      screen.getByText("Tooling lifecycle policy is not approved."),
    ).toBeVisible();
    expect(
      screen.getByText("ERPNext source truth is unavailable."),
    ).toBeVisible();
    expect(
      screen.getByText("Supplier-responsible, internally reported"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Append plan Revision" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Manufacturing data is read only in this session."),
    ).toBeVisible();
  });

  it("blocks an incomplete immutable plan before transport", async () => {
    enableCommandSession();
    const createPlan = vi.fn<ToolingDataSource["createManufacturingPlan"]>();
    const source = dataSource({ createManufacturingPlan: createPlan });
    const user = userEvent.setup();
    renderWorkspace(source);

    await user.click(
      await screen.findByRole("button", { name: "Append plan Revision" }),
    );
    await user.clear(screen.getByLabelText("Responsible member identity"));
    await user.click(
      screen.getByRole("button", {
        name: "Append immutable plan Revision",
      }),
    );

    expect(
      await screen.findByText(
        "Complete the exact Revision, member, release evidence and milestone schedule.",
      ),
    ).toBeVisible();
    expect(createPlan).not.toHaveBeenCalled();
  });

  it("submits one complete successor plan with exact release and predecessor truth", async () => {
    enableCommandSession();
    const capability = required(collection().items[0]).designReleaseEvidence;
    const createPlan = vi
      .fn<ToolingDataSource["createManufacturingPlan"]>()
      .mockResolvedValue({
        designReleaseEvidence: capability,
        plan: { ...plan(), planVersion: 2 },
      });
    const source = dataSource({ createManufacturingPlan: createPlan });
    const user = userEvent.setup();
    renderWorkspace(source);

    await user.click(
      await screen.findByRole("button", { name: "Append plan Revision" }),
    );
    const editor = screen
      .getByRole("heading", {
        name: "Append immutable manufacturing plan Revision",
      })
      .closest("form");
    if (!editor) throw new Error("The plan editor is required.");
    const form = within(editor);
    await user.selectOptions(
      form.getByLabelText("Sourcing strategy"),
      "supplier",
    );
    await user.clear(form.getByLabelText("Engineering estimate"));
    await user.type(form.getByLabelText("Engineering estimate"), "121500.25");
    await user.clear(form.getByLabelText("Budget fact"));
    await user.type(form.getByLabelText("Budget fact"), "126000");
    await user.clear(form.getByLabelText("Revision reason"));
    await user.type(
      form.getByLabelText("Revision reason"),
      "Approved planning adjustment",
    );
    await user.click(
      form.getByRole("button", { name: "Add released Document" }),
    );
    await user.click(
      required(
        form
          .getAllByRole("button", { name: "Remove released Document" })
          .at(-1),
      ),
    );
    await user.click(form.getByRole("button", { name: "Add milestone" }));
    await user.selectOptions(
      required(form.getAllByLabelText("Category")[1]),
      "delivery",
    );
    await user.selectOptions(
      required(form.getAllByLabelText("Responsibility")[1]),
      "supplier",
    );
    await user.click(
      required(
        form.getAllByRole("button", { name: "Remove milestone" }).at(-1),
      ),
    );
    await user.click(
      form.getByRole("button", { name: "Append immutable plan Revision" }),
    );

    await waitFor(() => {
      expect(createPlan).toHaveBeenCalledOnce();
    });
    expect(createPlan.mock.calls[0]?.[2]).toMatchObject({
      budget: { amount: "126000", currency: "CNY" },
      engineeringEstimate: { amount: "121500.25", currency: "CNY" },
      expectedVersion: 1,
      planGlobalId: planId,
      reason: "Approved planning adjustment",
      sourcingStrategy: "supplier",
      toolingRevisionGlobalId: revisionId,
      toolingRevisionSnapshotHash: hash("f"),
    });
    expect(createPlan.mock.calls[0]?.[2].designReleaseEvidence).toEqual([
      released(),
    ]);
  });

  it("renders formal ERP truth as read only without a write action", async () => {
    renderWorkspace(
      dataSource({
        loadManufacturingPlans: () =>
          Promise.resolve(
            collection({
              erpProjection: {
                editableIn: "ERPNEXT",
                observedAt: "2026-08-08T12:00:00Z",
                rows: [
                  {
                    actualCostSourceId: "ACT-001",
                    amount: "110.00",
                    costTypeCode: "MATERIAL",
                    currency: "CNY",
                    postingDate: "2026-08-08",
                    purchaseInvoiceSourceId: "PINV-001",
                    purchaseOrderSourceId: "PO-001",
                    purchaseReceiptSourceId: "PREC-001",
                    sourceRowId: "ROW-001",
                    sourceRowVersion: "1",
                    supplierSourceObjectId: "SUP-001",
                    toolingMasterGlobalId: masterId,
                  },
                ],
                sourceSystem: "ERPNEXT",
                state: "available",
                summaries: [
                  {
                    amount: "110.00",
                    costTypeCode: "MATERIAL",
                    currency: "CNY",
                    supplierSourceObjectId: "SUP-001",
                    toolingMasterGlobalId: masterId,
                  },
                ],
                supplier: {
                  sourceObjectId: "SUP-001",
                  supplierCode: "SUP-001",
                  supplierName: "Synthetic formal supplier",
                  targetVersion: "5",
                },
                targetVersion: "42",
                toolingMasterGlobalId: masterId,
              },
            }),
          ),
      }),
    );

    expect(await screen.findByText("Synthetic formal supplier")).toBeVisible();
    expect(screen.getByText("110.00")).toBeVisible();
    expect(screen.getAllByText("Read only").length).toBeGreaterThan(0);
    expect(
      screen.queryByRole("button", { name: /ERPNext/u }),
    ).not.toBeInTheDocument();
  });

  it("records complete clean File evidence on an internal observation", async () => {
    enableCommandSession();
    const createObservation = vi
      .fn<ToolingDataSource["createManufacturingObservation"]>()
      .mockResolvedValue({ observation: observation(2) });
    const source = dataSource({
      createManufacturingObservation: createObservation,
    });
    const user = userEvent.setup();
    renderWorkspace(source);

    await user.click(
      await screen.findByRole("button", { name: "Record observation" }),
    );
    const editor = screen
      .getByRole("heading", { name: "Record internal milestone observation" })
      .closest("form");
    if (!editor) throw new Error("The observation editor is required.");
    const form = within(editor);
    await user.clear(form.getByLabelText("Progress percentage"));
    await user.type(form.getByLabelText("Progress percentage"), "65");
    await user.type(form.getByLabelText("Actual start"), "2026-09-03");
    await user.type(form.getByLabelText("Actual finish"), "2026-09-10");
    await user.type(form.getByLabelText("Risk"), "Insert delivery risk");
    await user.type(
      form.getByLabelText("Observation note"),
      "Internal verified update",
    );
    await user.selectOptions(
      form.getByLabelText("Evidence role"),
      "technical_evidence",
    );
    await user.type(
      form.getByLabelText("File Revision identity"),
      documentRevisionId,
    );
    await user.clear(form.getByLabelText("File version"));
    await user.type(form.getByLabelText("File version"), "4");
    await user.type(form.getByLabelText("Frappe content hash"), hash("2"));
    await user.type(form.getByLabelText("SHA-256"), hash("3"));
    await user.click(
      form.getByRole("button", { name: "Record immutable observation" }),
    );

    await waitFor(() => {
      expect(createObservation).toHaveBeenCalledOnce();
    });
    expect(createObservation.mock.calls[0]?.[4]).toMatchObject({
      actualFinish: "2026-09-10",
      actualStart: "2026-09-03",
      evidence: [
        {
          fileOptimisticVersion: 4,
          fileRevisionGlobalId: documentRevisionId,
          frappeContentHash: hash("2"),
          role: "technical_evidence",
          sha256: hash("3"),
        },
      ],
      expectedVersion: 1,
      note: "Internal verified update",
      progressPercentage: 65,
      risk: "Insert delivery risk",
    });
  });

  it("retries a conflicting observation with the same idempotency key", async () => {
    enableCommandSession();
    const createObservation = vi
      .fn<ToolingDataSource["createManufacturingObservation"]>()
      .mockRejectedValueOnce(
        new NpiApiError({
          code: "TOOLING_MANUFACTURING_OBSERVATION_CONFLICT",
          retryable: true,
          status: 409,
          title: "The observation conflicts with exact manufacturing truth",
          traceId: "trace-manufacturing-observation-conflict",
          type: "urn:npi:problem:tooling-manufacturing-observation-conflict",
        }),
      )
      .mockResolvedValueOnce({ observation: observation(2) });
    const source = dataSource({
      createManufacturingObservation: createObservation,
    });
    const user = userEvent.setup();
    renderWorkspace(source);

    await user.click(
      await screen.findByRole("button", { name: "Record observation" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Record immutable observation" }),
    );
    expect(
      await screen.findByText(
        "The observation conflicts with exact manufacturing truth",
      ),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Retry exact command" }),
    );

    await waitFor(() => {
      expect(createObservation).toHaveBeenCalledTimes(2);
    });
    expect(createObservation.mock.calls[0]?.[5].idempotencyKey).toBe(
      createObservation.mock.calls[1]?.[5].idempotencyKey,
    );
  });
});
