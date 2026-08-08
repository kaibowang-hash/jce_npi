import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ControlledDocumentPageViewModel,
  ControlledDocumentWorkspaceViewModel,
  DocumentDataSource,
} from "../../src/api/document-data-source";
import type {
  ToolingCockpitViewModel,
  ToolingDataSource,
  ToolingRequirementSummaryViewModel,
  ToolingRevisionCollectionViewModel,
  ToolingSetCollectionViewModel,
  ToolingSetDetailViewModel,
} from "../../src/api/tooling-data-source";
import { NpiTransportError } from "../../src/api/http";
import ToolingSetWorkspace from "../../src/pages/tooling-set-workspace";
import { renderWithLocale } from "../support/render";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const requirementId = "33333333-3333-4333-8333-333333333333";
const setId = "44444444-4444-4444-8444-444444444444";
const intakeId = "55555555-5555-4555-8555-555555555555";
const differenceId = "66666666-6666-4666-8666-666666666666";
const documentId = "77777777-7777-4777-8777-777777777777";
const documentRevisionId = "88888888-8888-4888-8888-888888888888";
const fileRevisionId = "99999999-9999-4999-8999-999999999999";
const toolingRevisionId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const inspectionIds = [
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5",
] as const;

function required<T>(value: T | undefined): T {
  if (value === undefined)
    throw new Error("The test fixture value is required.");
  return value;
}

const requirement: ToolingRequirementSummaryViewModel = {
  globalId: requirementId,
  kind: "customer_owned_intake",
  projectGlobalId: projectId,
  reason: "Customer-owned tool received",
  snapshotHash: "1".repeat(64),
  targetDate: null,
  targetPartRevisionGlobalId: null,
  title: "Customer mold intake",
};

function collection(
  overrides: Partial<ToolingSetCollectionViewModel> = {},
): ToolingSetCollectionViewModel {
  return {
    items: [
      {
        custodyResponsibility: "Customer-owned custody",
        customer: { sourceObjectId: "CUST-001", sourceSystem: "ERPNEXT" },
        erpLocationAndAsset: {
          reasonCode: "erp_projection_unavailable",
          state: "unavailable",
        },
        globalId: setId,
        lifecycle: {
          reasonCode: "lifecycle_policy_unavailable",
          state: "unavailable",
        },
        physicalSerial: "SET-001",
        projectGlobalId: projectId,
        repairAuthorizationReference: "AUTH-001",
        requirementKind: "customer_owned_intake",
        returnConditions: "Return on customer request",
        snapshotHash: "2".repeat(64),
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
    ...overrides,
  };
}

function detail(): ToolingSetDetailViewModel {
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
    globalId: required(inspectionIds[index]),
    observation: index === 0 ? "Scratch observed" : "No difference",
  }));
  return {
    evidence: [
      {
        differenceGlobalIds: [differenceId],
        evidenceRole: "arrival_photo",
        fileContentHash: "3".repeat(64),
        fileName: "arrival.jpg",
        fileOptimisticVersion: 1,
        fileRevisionGlobalId: fileRevisionId,
        globalId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        intakeSnapshotHash: "4".repeat(64),
        mimeType: "image/jpeg",
        sha256: "5".repeat(64),
        sizeBytes: 512,
        snapshotHash: "6".repeat(64),
        toolingIntakeGlobalId: intakeId,
      },
    ],
    intakes: [
      {
        accessories: [],
        arrivedAt: "2026-08-07T08:00:00Z",
        custodyHandover: "Accepted at receiving dock",
        differences: [
          {
            customerConfirmationRequired: true,
            description: "Scratch observed",
            globalId: differenceId,
            sourceGlobalId: inspectionIds[0],
            sourceKind: "inspection",
          },
        ],
        globalId: intakeId,
        inspections,
        predecessorGlobalId: null,
        snapshotHash: "4".repeat(64),
        toolingSetGlobalId: setId,
        transportProvider: "Synthetic carrier",
        transportReference: "SHIP-001",
        version: 1,
      },
    ],
    permissions: collection().permissions,
    toolingSet: required(collection().items[0]),
  };
}

function boundDetail(): ToolingSetDetailViewModel {
  const value = detail();
  return {
    ...value,
    toolingSet: {
      ...value.toolingSet,
      sourceRevision: {
        globalId: "ffffffff-ffff-4fff-8fff-ffffffffffff",
        reason: "Approved exact source",
        snapshotHash: "d".repeat(64),
        toolingMasterGlobalId: masterId,
        toolingRevisionGlobalId: toolingRevisionId,
        toolingRevisionSnapshotHash: "e".repeat(64),
        toolingSetGlobalId: setId,
        toolingSetSnapshotHash: value.toolingSet.snapshotHash,
      },
    },
  };
}

function revisions(): ToolingRevisionCollectionViewModel {
  return {
    combinedTrial: {
      reasonCode: "combined_trial_not_delivered",
      state: "unavailable",
    },
    erpLocationAndAsset: {
      reasonCode: "erp_projection_unavailable",
      state: "unavailable",
    },
    items: [
      {
        globalId: toolingRevisionId,
        revisionLabel: "R1",
        revisionNumber: 1,
      } as ToolingRevisionCollectionViewModel["items"][number],
    ],
    lifecycle: {
      reasonCode: "lifecycle_policy_unavailable",
      state: "unavailable",
    },
    permissions: {
      bindSetSource: true,
      createPartSpecification: true,
      createProcessChain: true,
      createRevision: true,
      transitionLifecycle: false,
      view: true,
    },
    projectGlobalId: projectId,
    supplier: {
      reasonCode: "formal_supplier_unavailable",
      state: "unavailable",
    },
    toolingMasterGlobalId: masterId,
  };
}

function cockpit(): ToolingCockpitViewModel {
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
    masters: [],
    parts: [],
    permissions: {
      createApplicability: false,
      createMaster: false,
      createPart: false,
      createRequirement: false,
      transitionLifecycle: false,
      view: true,
    },
    project: { businessCode: "P-001", globalId: projectId, title: "Project" },
    requirements: [requirement],
  };
}

function dataSource(
  overrides: Partial<ToolingDataSource> = {},
): ToolingDataSource {
  return {
    attachIntakeEvidence: () => Promise.resolve(detail()),
    createPartControlledSpecification: () =>
      Promise.reject(new Error("not used")),
    createToolingProcessChainRevision: () =>
      Promise.reject(new Error("not used")),
    createToolingRevision: () => Promise.reject(new Error("not used")),
    createToolingSetRevisionBinding: () =>
      Promise.reject(new Error("not used")),
    createApplicability: () => Promise.resolve(cockpit()),
    createIntake: () => Promise.resolve(detail()),
    createMaster: () => Promise.resolve(cockpit()),
    createPart: () => Promise.resolve(cockpit()),
    createPartRevision: () => Promise.resolve(cockpit()),
    createRequirement: () => Promise.resolve(cockpit()),
    createSet: () => Promise.resolve(collection()),
    loadCockpit: () => Promise.resolve(cockpit()),
    loadMaster: () => Promise.resolve(cockpit()),
    loadPartControlledSpecification: () =>
      Promise.reject(new Error("not used")),
    loadSet: () => Promise.resolve(detail()),
    loadSets: () => Promise.resolve(collection()),
    loadToolingProcessChain: () => Promise.reject(new Error("not used")),
    loadToolingProcessChains: () => Promise.reject(new Error("not used")),
    loadToolingRevision: () => Promise.reject(new Error("not used")),
    loadToolingRevisions: () => Promise.reject(new Error("not used")),
    ...overrides,
  };
}

function documents(): Pick<
  DocumentDataSource,
  "loadDocuments" | "loadDocument"
> {
  const document = {
    confidentialityKey: "internal",
    currentLock: null,
    currentRevision: {
      globalId: documentRevisionId,
      major: 1,
      minor: 0,
      snapshotHash: "7".repeat(64),
    },
    documentNumber: "DOC-001",
    documentPolicyRef: {
      globalId: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      snapshotHash: "8".repeat(64),
      version: 1,
    },
    documentTypeKey: "arrival_evidence",
    globalId: documentId,
    optimisticVersion: 1,
    source: {
      editableIn: "NPI_ONE" as const,
      sourceSystem: "NPI_ONE" as const,
      syncState: "local" as const,
    },
    title: "Arrival evidence",
  };
  return {
    loadDocuments: () =>
      Promise.resolve({
        items: [document],
        nextCursor: null,
      } as unknown as ControlledDocumentPageViewModel),
    loadDocument: () =>
      Promise.resolve({
        document,
        revisions: [
          {
            files: [
              {
                capabilities: {
                  connector: {
                    reasonCode: "connector_unavailable",
                    state: "unavailable",
                  },
                  download: { reasonCode: "available", state: "available" },
                  externalRetrieval: {
                    reasonCode: "external_access_policy_unavailable",
                    state: "unavailable",
                  },
                  integrity: { reasonCode: "available", state: "available" },
                  preview: {
                    mode: "native_image",
                    reasonCode: "available",
                    state: "available",
                  },
                },
                fileName: "arrival.jpg",
                globalId: fileRevisionId,
                scanState: "clean",
                revision: 1,
              },
            ],
          },
        ],
      } as unknown as ControlledDocumentWorkspaceViewModel),
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
            catalog: { language: "en", messages: {}, version: "a".repeat(64) },
            csrfToken: "tooling-set-workspace-csrf-token",
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

function renderWorkspace(
  source: ToolingDataSource,
  documentSource?: Pick<DocumentDataSource, "loadDocuments" | "loadDocument">,
  revisionCapabilityAvailable = false,
): void {
  renderWithLocale(
    <ToolingSetWorkspace
      dataSource={source}
      documentDataSource={documentSource}
      masterId={masterId}
      projectId={projectId}
      requirements={[requirement]}
      revisionCapabilityAvailable={revisionCapabilityAvailable}
    />,
    "en",
    `/projects/${projectId}/tooling/${masterId}`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("physical Tooling Set workspace", () => {
  it("renders dense Set, intake, evidence and explicit unavailable truth", async () => {
    renderWorkspace(dataSource());

    expect((await screen.findAllByText("SET-001"))[0]).toBeVisible();
    expect(
      await screen.findByText("Synthetic carrier · SHIP-001"),
    ).toBeVisible();
    expect(await screen.findByText("arrival.jpg")).toBeVisible();
    expect(screen.getAllByText("Unavailable")).toHaveLength(4);
    expect(
      screen.getByRole("button", { name: "Create physical Set" }),
    ).toBeDisabled();
    expect(
      screen.getByText(
        "Physical Set data is read only until this session is verified.",
      ),
    ).toBeVisible();
  });

  it("submits the exact eligible requirement and custody fields for a new Set", async () => {
    enableCommandSession();
    const createSet = vi.fn<ToolingDataSource["createSet"]>(() =>
      Promise.resolve(collection()),
    );
    renderWorkspace(dataSource({ createSet }));
    const user = userEvent.setup();

    const open = await screen.findByRole("button", {
      name: "Create physical Set",
    });
    await waitFor(() => {
      expect(open).toBeEnabled();
    });
    await user.click(open);
    await user.type(screen.getByLabelText("Physical serial"), "SET-002");
    await user.type(
      screen.getByLabelText("Custody responsibility"),
      "Plant custody",
    );
    await user.type(
      screen.getByLabelText("Repair authorization reference"),
      "AUTH-002",
    );
    await user.type(
      screen.getByLabelText("Return conditions"),
      "Return after validation",
    );
    await user.click(
      required(
        screen.getAllByRole("button", { name: "Create physical Set" }).at(-1),
      ),
    );

    await waitFor(() => {
      expect(createSet).toHaveBeenCalledOnce();
    });
    expect(createSet.mock.calls[0]?.[2]).toEqual({
      custodyResponsibility: "Plant custody",
      physicalSerial: "SET-002",
      repairAuthorizationReference: "AUTH-002",
      returnConditions: "Return after validation",
      toolingRequirementGlobalId: requirementId,
    });
  });

  it("records all five inspections, an observed difference and accessory counts", async () => {
    enableCommandSession();
    const createIntake = vi.fn<ToolingDataSource["createIntake"]>(() =>
      Promise.resolve(detail()),
    );
    renderWorkspace(dataSource({ createIntake }));
    const user = userEvent.setup();

    const open = await screen.findByRole("button", { name: "Record intake" });
    await waitFor(() => {
      expect(open).toBeEnabled();
    });
    await user.click(open);
    await user.type(screen.getByLabelText("Transport provider"), "Carrier B");
    await user.type(screen.getByLabelText("Transport reference"), "SHIP-002");
    await user.type(
      screen.getByLabelText("Custody handover"),
      "Accepted by receiver",
    );
    for (const label of [
      "Appearance",
      "Water circuit",
      "Hot runner",
      "Electrical",
      "Safety",
    ]) {
      await user.type(screen.getByLabelText(label), `${label} checked`);
    }
    await user.click(
      required(screen.getAllByLabelText("Difference observed")[0]),
    );
    await user.click(
      required(screen.getAllByLabelText("Customer confirmation required")[0]),
    );
    await user.click(screen.getByRole("button", { name: "Add accessory" }));
    await user.type(screen.getByLabelText("Accessory"), "Lifting ring");
    await user.type(screen.getByLabelText("Declared"), "2");
    await user.type(screen.getByLabelText("Received"), "1");
    await user.type(screen.getByLabelText("Unit"), "pcs");
    await user.click(
      required(screen.getAllByRole("button", { name: "Record intake" }).at(-1)),
    );

    await waitFor(() => {
      expect(createIntake).toHaveBeenCalledOnce();
    });
    const command = createIntake.mock.calls[0]?.[3];
    expect(command?.expectedVersion).toBe(1);
    expect(command?.inspections).toHaveLength(5);
    expect(command?.differences).toEqual([
      expect.objectContaining({
        customerConfirmationRequired: true,
        description: "Appearance checked",
        sourceKind: "inspection",
      }),
    ]);
    expect(command?.accessories).toEqual([
      expect.objectContaining({
        declaredQuantity: 2,
        description: "Lifting ring",
        receivedQuantity: 1,
        unit: "pcs",
      }),
    ]);
  });

  it("selects a clean Project File Revision and binds exact differences", async () => {
    enableCommandSession();
    const attachIntakeEvidence = vi.fn<
      ToolingDataSource["attachIntakeEvidence"]
    >(() => Promise.resolve(detail()));
    renderWorkspace(dataSource({ attachIntakeEvidence }), documents());
    const user = userEvent.setup();

    const open = await screen.findByRole("button", { name: "Attach evidence" });
    await waitFor(() => {
      expect(open).toBeEnabled();
    });
    await user.click(open);
    await waitFor(() => {
      expect(screen.getByLabelText("Controlled document")).toBeEnabled();
    });
    await user.selectOptions(
      screen.getByLabelText("Controlled document"),
      documentId,
    );
    await waitFor(() => {
      expect(screen.getByLabelText("Exact File Revision")).toBeEnabled();
    });
    await user.selectOptions(
      screen.getByLabelText("Exact File Revision"),
      fileRevisionId,
    );
    await user.click(screen.getByLabelText("Scratch observed"));
    await user.click(
      required(
        screen.getAllByRole("button", { name: "Attach evidence" }).at(-1),
      ),
    );

    await waitFor(() => {
      expect(attachIntakeEvidence).toHaveBeenCalledOnce();
    });
    expect(attachIntakeEvidence.mock.calls[0]?.slice(0, 5)).toEqual([
      projectId,
      masterId,
      setId,
      intakeId,
      {
        differenceGlobalIds: [differenceId],
        evidenceRole: "arrival_photo",
        fileRevisionGlobalId: fileRevisionId,
      },
    ]);
  });

  it("binds one immutable Tooling Revision to one exact unbound Set", async () => {
    enableCommandSession();
    const createToolingSetRevisionBinding = vi.fn<
      ToolingDataSource["createToolingSetRevisionBinding"]
    >(() => Promise.resolve(boundDetail()));
    renderWorkspace(
      dataSource({
        createToolingSetRevisionBinding,
        loadToolingRevisions: () => Promise.resolve(revisions()),
      }),
      undefined,
      true,
    );
    const user = userEvent.setup();

    const open = await screen.findByRole("button", {
      name: "Bind source Tooling Revision",
    });
    await waitFor(() => {
      expect(open).toBeEnabled();
    });
    await user.click(open);
    await user.selectOptions(
      screen.getByLabelText("Source Tooling Revision"),
      toolingRevisionId,
    );
    await user.type(
      screen.getByLabelText("Binding reason"),
      "Approved exact source",
    );
    await user.click(
      screen.getByRole("button", { name: "Bind exact source Revision" }),
    );

    await waitFor(() => {
      expect(createToolingSetRevisionBinding).toHaveBeenCalledOnce();
    });
    expect(createToolingSetRevisionBinding.mock.calls[0]?.slice(0, 4)).toEqual([
      projectId,
      masterId,
      setId,
      {
        reason: "Approved exact source",
        toolingRevisionGlobalId: toolingRevisionId,
      },
    ]);
    expect(await screen.findByText("Approved exact source")).toBeVisible();
  });

  it("shows a retry only for evidence-backed retryable collection failures", async () => {
    const loadSets = vi
      .fn<ToolingDataSource["loadSets"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "trace-set", "trace"),
      )
      .mockResolvedValueOnce(collection());
    renderWorkspace(dataSource({ loadSets }));
    const user = userEvent.setup();

    const retry = await screen.findByRole("button", { name: "Retry" });
    await user.click(retry);
    expect((await screen.findAllByText("SET-001"))[0]).toBeVisible();
    expect(loadSets).toHaveBeenCalledTimes(2);
  });
});
