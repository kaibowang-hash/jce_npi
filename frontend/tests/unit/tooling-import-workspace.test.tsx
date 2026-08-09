import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ToolingImportCorrectionArtifact,
  ToolingImportDataSource,
} from "../../src/api/tooling-import-data-source";
import { NpiTransportError } from "../../src/api/http";
import ToolingImportWorkspace from "../../src/pages/tooling-import-workspace";
import { renderWithLocale } from "../support/render";
import {
  toolingImportCollection,
  toolingImportDetail,
  toolingImportIds,
  toolingImportJob,
  toolingImportReconciliation,
} from "../support/tooling-import-fixture";

const correctionArtifact: ToolingImportCorrectionArtifact = {
  batchGlobalId: toolingImportIds.batch,
  createdAt: "2026-08-09T08:02:00Z",
  createdByUserId: "tooling.engineer@example.invalid",
  entryCount: 1,
  fileName: "tooling-import-correction.csv",
  frappeFileId: "private/files/tooling-import-correction.csv",
  globalId: toolingImportIds.correction,
  jobGlobalId: toolingImportIds.job,
  jobSnapshotHash: "a".repeat(64),
  mimeType: "text/csv",
  requestId: toolingImportIds.request,
  schemaVersion: "tooling-import-correction.v1",
  sha256: "e".repeat(64),
  sizeBytes: 16,
  snapshotHash: "d".repeat(64),
  traceId: "trace-correction",
};

function dataSource(
  overrides: Partial<ToolingImportDataSource> = {},
): ToolingImportDataSource {
  const detail = toolingImportDetail();
  const inspection = detail.inspections[0];
  const mapping = detail.mappingProposals[0];
  const preview = detail.previews[0];
  const batch = detail.batch;
  if (!inspection || !mapping || !preview)
    throw new Error("The exact import fixture revisions are required.");
  return {
    confirmPreview: () => Promise.resolve(preview),
    createCorrectionArtifact: () => Promise.resolve(correctionArtifact),
    createMappingProposal: () => Promise.resolve(mapping),
    createPreview: () => Promise.resolve(preview),
    downloadCorrectionArtifact: () =>
      Promise.resolve({
        blob: new Blob(["row,field,value\n"], { type: "text/csv" }),
        fileName: correctionArtifact.fileName,
      }),
    evaluateRollback: () =>
      Promise.resolve({
        ...toolingImportReconciliation(),
        kind: "rollback_eligibility",
      }),
    execute: () => Promise.resolve(toolingImportJob("queued")),
    inspect: () => Promise.resolve(inspection),
    loadBatch: () => Promise.resolve(detail),
    loadBatches: () => Promise.resolve(toolingImportCollection()),
    loadJob: () => Promise.resolve(toolingImportJob("succeeded")),
    reconcile: () => Promise.resolve(toolingImportReconciliation()),
    registerSource: () => Promise.resolve(batch),
    retry: () => Promise.resolve(toolingImportJob("queued")),
    rollback: () =>
      Promise.resolve({
        job: toolingImportJob("rolled_back"),
        rollback: {
          ...toolingImportReconciliation("rolled_back"),
          kind: "rollback_result",
        },
      }),
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
            catalog: { language: "en", messages: {}, version: "a".repeat(64) },
            csrfToken: "tooling-import-workspace-csrf-token",
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

function renderWorkspace(source: ToolingImportDataSource): void {
  renderWithLocale(
    <ToolingImportWorkspace
      dataSource={source}
      navigate={vi.fn()}
      projectId={toolingImportIds.project}
    />,
    "en",
    `/projects/${toolingImportIds.project}/tooling?workspace=import`,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Tooling List import workspace", () => {
  it("renders the stable eight-step rail and exact partial worker truth", async () => {
    renderWorkspace(dataSource());
    const user = userEvent.setup();

    expect(
      (await screen.findAllByText("synthetic-tooling-list.xlsx"))[0],
    ).toBeVisible();
    expect(
      screen.getByRole("navigation", { name: "Tooling import steps" }),
    ).toBeVisible();
    for (const label of [
      "Upload",
      "Detect",
      "Map",
      "Transform",
      "Validate",
      "Preview",
      "Execute",
      "Audit",
    ]) {
      expect(
        screen.getByRole("button", { name: new RegExp(label, "u") }),
      ).toBeVisible();
    }

    await user.click(screen.getByRole("button", { name: /Execute/u }));
    expect(
      (await screen.findAllByText("Partially succeeded"))[0],
    ).toBeVisible();
    expect(
      screen.getByText(
        "The row could not be imported. Retry with the trace identifier.",
      ),
    ).toBeVisible();
    expect(screen.getByText("trace-worker-row")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Create controlled correction file" }),
    ).toBeDisabled();
  });

  it("creates an exact correction artifact and retries only failed rows", async () => {
    enableCommandSession();
    const createCorrectionArtifact = vi.fn<
      ToolingImportDataSource["createCorrectionArtifact"]
    >(() => Promise.resolve(correctionArtifact));
    const retry = vi.fn<ToolingImportDataSource["retry"]>(() =>
      Promise.resolve(toolingImportJob("queued")),
    );
    renderWorkspace(dataSource({ createCorrectionArtifact, retry }));
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Execute/u }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", {
          name: "Create controlled correction file",
        }),
      ).toBeEnabled();
    });
    await user.type(screen.getByLabelText("Worksheet"), "Tooling List");
    await user.type(screen.getByLabelText("Source row"), "3");
    await user.type(screen.getByLabelText("Source column"), "Tooling No.");
    await user.type(screen.getByLabelText("Corrected value"), "TL-SYN-002");
    await user.click(
      screen.getByRole("button", { name: "Create controlled correction file" }),
    );

    expect(
      await screen.findByText("tooling-import-correction.csv"),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Retry exact failed rows" }),
    );
    await waitFor(() => {
      expect(retry).toHaveBeenCalledOnce();
    });
    expect(createCorrectionArtifact.mock.calls[0]?.[3].corrections).toEqual([
      {
        correctedValue: "TL-SYN-002",
        sourceHeader: "Tooling No.",
        sourceRow: 3,
        worksheetName: "Tooling List",
      },
    ]);
    expect(retry.mock.calls[0]?.[3]).toMatchObject({
      correctionArtifactGlobalId: toolingImportIds.correction,
      correctionArtifactSnapshotHash: correctionArtifact.snapshotHash,
      expectedVersion: 1,
    });
  });

  it("advances exact detection, mapping, preview review and execution commands", async () => {
    enableCommandSession();
    const inspection = toolingImportDetail(null).inspections[0];
    const mapping = toolingImportDetail(null).mappingProposals[0];
    const preview = toolingImportDetail(null).previews[0];
    if (!inspection || !mapping || !preview)
      throw new Error("The exact fixture revisions are required.");
    const inspect = vi.fn<ToolingImportDataSource["inspect"]>(() =>
      Promise.resolve(inspection),
    );
    const createMappingProposal = vi.fn<
      ToolingImportDataSource["createMappingProposal"]
    >(() => Promise.resolve(mapping));
    const createPreview = vi.fn<ToolingImportDataSource["createPreview"]>(() =>
      Promise.resolve(preview),
    );
    const execute = vi.fn<ToolingImportDataSource["execute"]>(() =>
      Promise.resolve(toolingImportJob("queued")),
    );
    renderWorkspace(
      dataSource({
        createMappingProposal,
        createPreview,
        execute,
        inspect,
        loadBatch: () => Promise.resolve(toolingImportDetail(null)),
      }),
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Detect/u }));
    expect(screen.getByText("Tooling No.")).toBeVisible();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Detect workbook structure" }),
      ).toBeEnabled();
    });
    await user.click(
      screen.getByRole("button", { name: "Detect workbook structure" }),
    );
    expect(
      await screen.findByDisplayValue("synthetic-tooling-list.v1"),
    ).toBeVisible();
    await user.type(
      screen.getByLabelText("Proposal reason"),
      "Exact fixture mapping",
    );
    await user.click(
      screen.getByRole("button", { name: "Create mapping proposal" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Transform and validate" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Review immutable preview" }),
    );
    await user.click(
      screen.getByLabelText(
        "I reviewed the exact immutable preview and execution eligibility.",
      ),
    );
    await user.click(
      screen.getByRole("button", { name: "Continue to execution" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Execute exact preview" }),
    );

    await waitFor(() => {
      expect(execute).toHaveBeenCalledOnce();
    });
    expect(inspect).toHaveBeenCalledOnce();
    expect(createMappingProposal.mock.calls[0]?.[2]).toMatchObject({
      inspectionGlobalId: toolingImportIds.inspection,
      reason: "Exact fixture mapping",
    });
    expect(createPreview).toHaveBeenCalledOnce();
    expect(execute.mock.calls[0]?.[3]).toEqual({
      expectedSnapshotHash: preview.snapshotHash,
      expectedVersion: preview.previewVersion,
    });
  });

  it("registers an existing private workbook revision without browser parsing", async () => {
    enableCommandSession();
    const batch = toolingImportCollection().batches[0];
    if (!batch) throw new Error("The exact import batch is required.");
    const registerSource = vi.fn<ToolingImportDataSource["registerSource"]>(
      () => Promise.resolve(batch),
    );
    renderWorkspace(
      dataSource({
        loadBatches: () =>
          Promise.resolve(toolingImportCollection({ batches: [] })),
        registerSource,
      }),
    );
    const user = userEvent.setup();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Register controlled workbook" }),
      ).toBeEnabled();
    });
    await user.type(
      screen.getByLabelText("Customer scope"),
      "SYNTHETIC-CUSTOMER",
    );
    await user.type(
      screen.getByLabelText("File Revision identity"),
      toolingImportIds.fileRevision,
    );
    await user.type(
      screen.getByLabelText("Frappe content hash"),
      "d".repeat(32),
    );
    await user.type(screen.getByLabelText("SHA-256 digest"), "3".repeat(64));
    await user.click(
      screen.getByRole("button", { name: "Register controlled workbook" }),
    );

    await waitFor(() => {
      expect(registerSource).toHaveBeenCalledOnce();
    });
    expect(registerSource.mock.calls[0]?.[1]).toEqual({
      customerScopeId: "SYNTHETIC-CUSTOMER",
      fileOptimisticVersion: 1,
      fileRevisionGlobalId: toolingImportIds.fileRevision,
      frappeContentHash: "d".repeat(32),
      sha256: "3".repeat(64),
    });
    expect(
      await screen.findByText("2. Detect workbook structure"),
    ).toBeVisible();
  });

  it("submits a version-bound required relationship confirmation", async () => {
    enableCommandSession();
    const value = toolingImportDetail(null);
    const preview = value.previews[0];
    const row = preview?.rows[0];
    if (!preview || !row) throw new Error("The exact preview row is required.");
    const requiredPreview = {
      ...preview,
      executionEligible: false,
      rows: [
        {
          ...row,
          reasonCodes: ["relationship_confirmation_required"],
          requiresConfirmation: true,
        },
      ],
    };
    const confirmPreview = vi.fn<ToolingImportDataSource["confirmPreview"]>(
      () => Promise.resolve(preview),
    );
    renderWorkspace(
      dataSource({
        confirmPreview,
        loadBatch: () =>
          Promise.resolve({ ...value, previews: [requiredPreview] }),
      }),
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Preview/u }));
    await user.click(
      screen.getByRole("button", { name: "Confirm preview relationship" }),
    );
    expect(
      screen.getByText("Enter every required confirmation value."),
    ).toBeVisible();
    await user.selectOptions(
      screen.getByLabelText("Confirmation kind"),
      "image_anchor",
    );
    await user.type(screen.getByLabelText("Worksheet"), "Tooling List");
    await user.type(screen.getByLabelText("Source row"), "3");
    await user.type(screen.getByLabelText("Anchor key"), "image.anchor.1");
    await user.type(
      screen.getByLabelText("Target identity"),
      toolingImportIds.target,
    );
    await user.type(
      screen.getByLabelText("Target snapshot hash"),
      "c".repeat(64),
    );
    await user.type(
      screen.getByLabelText("Reason"),
      "Confirmed exact image relationship",
    );
    await user.click(
      screen.getByRole("button", { name: "Confirm preview relationship" }),
    );

    await waitFor(() => {
      expect(confirmPreview).toHaveBeenCalledOnce();
    });
    expect(confirmPreview.mock.calls[0]?.[3]).toMatchObject({
      confirmations: [
        {
          anchorKey: "image.anchor.1",
          kind: "image_anchor",
          reason: "Confirmed exact image relationship",
          selectedTargetGlobalId: toolingImportIds.target,
          sourceRow: 3,
          worksheetName: "Tooling List",
        },
      ],
      expectedVersion: 1,
    });
  });

  it("reconciles and confirms rollback only for an eligible immutable revision", async () => {
    enableCommandSession();
    const eligibility = {
      ...toolingImportReconciliation(),
      kind: "rollback_eligibility" as const,
    };
    const reconcile = vi.fn<ToolingImportDataSource["reconcile"]>(() =>
      Promise.resolve(toolingImportReconciliation()),
    );
    const evaluateRollback = vi.fn<ToolingImportDataSource["evaluateRollback"]>(
      () => Promise.resolve(eligibility),
    );
    const rollback = vi.fn<ToolingImportDataSource["rollback"]>(() =>
      Promise.resolve({
        job: toolingImportJob("rolled_back"),
        rollback: {
          ...toolingImportReconciliation("rolled_back"),
          kind: "rollback_result",
        },
      }),
    );
    renderWorkspace(
      dataSource({
        evaluateRollback,
        loadBatch: () => Promise.resolve(toolingImportDetail("succeeded")),
        reconcile,
        rollback,
      }),
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Audit/u }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Reconcile imported targets" }),
      ).toBeEnabled();
    });
    await user.click(
      screen.getByRole("button", { name: "Reconcile imported targets" }),
    );
    await waitFor(() => {
      expect(reconcile).toHaveBeenCalledOnce();
    });
    await user.click(
      screen.getByRole("button", { name: "Evaluate rollback eligibility" }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Rollback imported unused objects",
      }),
    );
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Rollback imported unused objects",
      }),
    );

    await waitFor(() => {
      expect(rollback).toHaveBeenCalledOnce();
    });
    expect(rollback.mock.calls[0]?.[3]).toEqual({
      eligibilityGlobalId: eligibility.globalId,
      eligibilitySnapshotHash: eligibility.snapshotHash,
      expectedSnapshotHash: toolingImportJob("succeeded").snapshotHash,
      expectedVersion: 1,
    });
  });

  it("shows rollback denial from immutable eligibility without a destructive action", async () => {
    enableCommandSession();
    const evaluateRollback = vi.fn<ToolingImportDataSource["evaluateRollback"]>(
      () =>
        Promise.resolve({
          ...toolingImportReconciliation("downstream_used"),
          kind: "rollback_eligibility",
        }),
    );
    renderWorkspace(dataSource({ evaluateRollback }));
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Audit/u }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Evaluate rollback eligibility" }),
      ).toBeEnabled();
    });
    await user.click(
      screen.getByRole("button", { name: "Evaluate rollback eligibility" }),
    );

    expect(
      await screen.findByText(
        "Rollback is denied by current target usage or changes.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", {
        name: "Rollback imported unused objects",
      }),
    ).not.toBeInTheDocument();
  });

  it("keeps commands disabled when session verification is unavailable", async () => {
    renderWorkspace(dataSource());
    expect(
      await screen.findByText(
        "Tooling List import is read only in this session.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Register controlled workbook" }),
    ).toBeDisabled();
  });

  it("blocks incomplete source, mapping and correction commands in the browser", async () => {
    enableCommandSession();
    renderWorkspace(dataSource());
    const user = userEvent.setup();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Register controlled workbook" }),
      ).toBeEnabled();
    });
    await user.click(
      screen.getByRole("button", { name: "Register controlled workbook" }),
    );
    expect(
      screen.getByText("Enter every required registered workbook reference."),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: /Map/u }));
    await user.click(
      screen.getByRole("button", { name: "Create mapping proposal" }),
    );
    expect(
      screen.getByText("Enter a reason for the mapping proposal."),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: /Execute/u }));
    await user.click(
      screen.getByRole("button", { name: "Create controlled correction file" }),
    );
    expect(
      screen.getByText("Enter the exact failed field and its corrected value."),
    ).toBeVisible();
  });

  it.each([
    "queued",
    "processing",
    "failed_final",
    "rolled_back",
    "rollback_denied",
  ] as const)("renders the exact %s worker state", async (state) => {
    renderWorkspace(
      dataSource({
        loadBatch: () => Promise.resolve(toolingImportDetail(state)),
      }),
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Execute/u }));
    const expectedLabel = {
      failed_final: "Final failure",
      processing: "Processing",
      queued: "Queued",
      rollback_denied: "Rollback denied",
      rolled_back: "Rolled back",
    }[state];
    expect(screen.getAllByText(expectedLabel)[0]).toBeVisible();
  });

  it("renders a governed collection failure and exposes bounded retry", async () => {
    renderWorkspace(
      dataSource({
        loadBatches: () =>
          Promise.reject(
            new NpiTransportError("network", "client-import-test", "client"),
          ),
      }),
    );
    expect(
      await screen.findByText("The service could not be reached."),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Return to Tooling cockpit" }),
    ).toBeVisible();
  });
});
