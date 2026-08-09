import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ToolingDataSource,
  ToolingMasterSummaryViewModel,
  ToolingRevisionCollectionViewModel,
  ToolingSetCollectionViewModel,
} from "../../src/api/tooling-data-source";
import { NpiTransportError } from "../../src/api/http";
import ToolingAcceptanceAssetWorkspace from "../../src/pages/tooling-acceptance-asset-workspace";
import {
  acceptanceContext,
  acceptanceRevision,
  assetRequest,
  assetRequestCollection,
  toolingAcceptanceHash as hash,
  toolingAcceptanceIds as ids,
} from "../support/tooling-acceptance-fixture";
import { renderWithLocale } from "../support/render";

function master(): ToolingMasterSummaryViewModel {
  return {
    globalId: ids.master,
    originatingProjectGlobalId: ids.project,
    snapshotHash: hash("d"),
    source: {
      editableIn: "NPI_ONE",
      sourceSystem: "NPI_ONE",
      syncState: "local",
    },
    title: "Customer tool family A",
  };
}

function sets(): ToolingSetCollectionViewModel {
  return {
    items: [
      {
        custodyResponsibility: "NPI Tooling team",
        customer: null,
        erpLocationAndAsset: {
          reasonCode: "erp_projection_unavailable",
          state: "unavailable",
        },
        globalId: ids.set,
        lifecycle: {
          reasonCode: "lifecycle_policy_unavailable",
          state: "unavailable",
        },
        physicalSerial: "SET-001",
        projectGlobalId: ids.project,
        repairAuthorizationReference: "AUTH-001",
        requirementKind: "copy_or_additional_set",
        returnConditions: "Return after validated production handoff",
        snapshotHash: hash("f"),
        sourceRevision: {
          globalId: ids.binding,
          reason: "Bind exact released design intent",
          snapshotHash: hash("b"),
          toolingMasterGlobalId: ids.master,
          toolingRevisionGlobalId: ids.revision,
          toolingRevisionSnapshotHash: hash("e"),
          toolingSetGlobalId: ids.set,
          toolingSetSnapshotHash: hash("f"),
        },
        supplier: {
          reasonCode: "formal_supplier_unavailable",
          state: "unavailable",
        },
        toolingMasterGlobalId: ids.master,
        toolingRequirementGlobalId: ids.acceptance,
      },
    ],
    permissions: {
      attachEvidence: false,
      createIntake: false,
      createSet: false,
      transitionLifecycle: false,
      view: true,
    },
    toolingMasterGlobalId: ids.master,
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
        globalId: ids.revision,
        revisionLabel: "R1",
        revisionNumber: 1,
        snapshotHash: hash("e"),
        toolingMasterGlobalId: ids.master,
      },
    ],
    lifecycle: {
      reasonCode: "lifecycle_policy_unavailable",
      state: "unavailable",
    },
    permissions: {
      bindSetSource: false,
      createPartSpecification: false,
      createProcessChain: false,
      createRevision: false,
      transitionLifecycle: false,
      view: true,
    },
    projectGlobalId: ids.project,
    supplier: {
      reasonCode: "formal_supplier_unavailable",
      state: "unavailable",
    },
    toolingMasterGlobalId: ids.master,
  } as unknown as ToolingRevisionCollectionViewModel;
}

function dataSource(
  overrides: Partial<ToolingDataSource> = {},
): ToolingDataSource {
  return {
    createToolAssetRequest: vi.fn(() => Promise.resolve(assetRequest())),
    createToolingAcceptanceRevision: vi.fn(() =>
      Promise.resolve(acceptanceRevision()),
    ),
    loadAcceptanceAssets: vi.fn(() => Promise.resolve(acceptanceContext())),
    loadSets: vi.fn(() => Promise.resolve(sets())),
    loadToolAssetRequests: vi.fn(() =>
      Promise.resolve(assetRequestCollection()),
    ),
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
            csrfToken: "acceptance-asset-workspace-csrf-token",
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
    <ToolingAcceptanceAssetWorkspace
      dataSource={source}
      master={master()}
      projectId={ids.project}
    />,
    "en",
    `/projects/${ids.project}/tooling/${ids.master}`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Tooling acceptance and Asset workspace", () => {
  it("keeps loading, empty and read-only truth explicit", async () => {
    let resolveAcceptance:
      | ((value: ReturnType<typeof acceptanceContext>) => void)
      | undefined;
    const pending = new Promise<ReturnType<typeof acceptanceContext>>(
      (resolve) => {
        resolveAcceptance = resolve;
      },
    );
    renderWorkspace(dataSource({ loadAcceptanceAssets: () => pending }));
    expect(
      await screen.findByText("Loading acceptance and Asset workspace"),
    ).toBeInTheDocument();

    act(() => {
      resolveAcceptance?.(acceptanceContext({ acceptanceRevisions: [] }));
    });
    expect(
      await screen.findByText(
        "No acceptance evidence Revision has been recorded.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Acceptance and Asset commands are read only in this session.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Approval unavailable")).toBeInTheDocument();
    expect(screen.getByText("Dispatch prohibited")).toBeInTheDocument();
  });

  it("renders immutable lineage, separated Mock axes and unavailable ERP truth", async () => {
    renderWorkspace(dataSource());
    expect((await screen.findAllByText("SET-001")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Validated Mock").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Prohibited").length).toBeGreaterThan(0);
    expect(screen.getByText("Not requested")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Formal Asset mapping has not been observed from ERPNext.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Approved")).not.toBeInTheDocument();
    expect(screen.queryByText("Dispatched")).not.toBeInTheDocument();
  });

  it("retries an acceptance workspace transport failure", async () => {
    const loadAcceptanceAssets = vi
      .fn<ToolingDataSource["loadAcceptanceAssets"]>()
      .mockRejectedValueOnce(
        new NpiTransportError(
          "network",
          "trace-tooling-acceptance-network",
          "trace",
        ),
      )
      .mockResolvedValueOnce(acceptanceContext());
    const user = userEvent.setup();
    renderWorkspace(dataSource({ loadAcceptanceAssets }));

    await user.click(
      await screen.findByRole("button", {
        name: "Retry acceptance and Asset workspace",
      }),
    );
    expect((await screen.findAllByText("SET-001")).length).toBeGreaterThan(0);
    expect(loadAcceptanceAssets).toHaveBeenCalledTimes(2);
  });

  it("appends exactly nine acceptance categories without approval fields", async () => {
    enableCommandSession();
    const create = vi.fn<ToolingDataSource["createToolingAcceptanceRevision"]>(
      () => Promise.resolve(acceptanceRevision()),
    );
    renderWorkspace(dataSource({ createToolingAcceptanceRevision: create }));
    await screen.findAllByText("SET-001");
    fireEvent.click(screen.getByRole("button", { name: "Append Revision" }));
    fireEvent.change(screen.getByLabelText("Append reason"), {
      target: { value: "Refresh controlled acceptance evidence" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Append evidence Revision" }),
    );

    await waitFor(() => {
      expect(create).toHaveBeenCalledTimes(1);
    });
    const payload = create.mock.calls[0]?.[2];
    expect(payload).toMatchObject({
      acceptanceGlobalId: ids.acceptance,
      expectedVersion: 1,
      reason: "Refresh controlled acceptance evidence",
      setRevisionBindingGlobalId: ids.binding,
      toolingRevisionGlobalId: ids.revision,
      toolingSetGlobalId: ids.set,
    });
    expect(payload?.checklist).toHaveLength(9);
    expect(payload).not.toHaveProperty("approvalState");
    expect(payload).not.toHaveProperty("targetPayload");
  });

  it("prepares only an acknowledged local Mock request", async () => {
    enableCommandSession();
    const create = vi.fn<ToolingDataSource["createToolAssetRequest"]>(() =>
      Promise.resolve(assetRequest()),
    );
    const user = userEvent.setup();
    renderWorkspace(dataSource({ createToolAssetRequest: create }));
    const prepare = await screen.findByRole("button", {
      name: "Prepare Mock Asset request",
    });
    expect(prepare).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: /only validates a local Mock draft/u,
      }),
    );
    await user.click(prepare);

    await waitFor(() => {
      expect(create).toHaveBeenCalledTimes(1);
    });
    const payload = create.mock.calls[0]?.[3];
    expect(payload).toMatchObject({
      acceptanceRevisionGlobalId: ids.acceptanceRevision,
      targetMode: "mock",
    });
    expect(payload).not.toHaveProperty("dispatch");
    expect(payload).not.toHaveProperty("targetPayload");
    expect(payload).not.toHaveProperty("approvalState");
  });
});
