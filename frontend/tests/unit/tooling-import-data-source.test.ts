import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isToolingImportBatchCollection,
  isToolingImportBatchDetail,
  isToolingImportJob,
} from "../../src/api/tooling-import-contract";
import { LiveToolingImportDataSource } from "../../src/api/tooling-import-data-source";
import {
  toolingImportCollection,
  toolingImportDetail,
  toolingImportIds,
  toolingImportJob,
  toolingImportReconciliation,
} from "../support/tooling-import-fixture";

const correctionArtifact = {
  batchGlobalId: toolingImportIds.batch,
  createdAt: "2026-08-09T08:02:00Z",
  createdByUserId: "tooling.engineer@example.invalid",
  entryCount: 1,
  fileName: "tooling-import-correction.csv",
  frappeFileId: "private/files/tooling-import-correction.csv",
  globalId: toolingImportIds.correction,
  jobGlobalId: toolingImportIds.job,
  jobSnapshotHash: "a".repeat(64),
  mimeType: "text/csv" as const,
  requestId: toolingImportIds.request,
  schemaVersion: "tooling-import-correction.v1" as const,
  sha256: "e".repeat(64),
  sizeBytes: 16,
  snapshotHash: "d".repeat(64),
  traceId: "trace-correction",
};

function governedResponse(
  value: unknown,
  init?: RequestInit,
  contentType = "application/json",
): Response {
  const headers = new Headers(init?.headers);
  return new Response(
    contentType === "text/csv" ? (value as Blob) : JSON.stringify(value),
    {
      headers: {
        "Cache-Control": "private, no-store",
        "Content-Disposition":
          contentType === "text/csv"
            ? 'attachment; filename="tooling-import-correction.csv"'
            : "inline",
        "Content-Type": contentType,
        "Idempotency-Replayed": "false",
        "X-Content-Type-Options": "nosniff",
        "X-Request-ID": headers.get("X-Request-ID") ?? "",
        "X-Trace-ID": "trace-tooling-import-test",
      },
      status: init?.method === "POST" ? 201 : 200,
    },
  );
}

function responseFor(request: RequestInfo | URL, init?: RequestInit): Response {
  const url =
    typeof request === "string"
      ? request
      : request instanceof URL
        ? request.href
        : request.url;
  const detail = toolingImportDetail();
  const inspection = detail.inspections[0];
  const mapping = detail.mappingProposals[0];
  const preview = detail.previews[0];
  if (!inspection || !mapping || !preview)
    throw new Error("The exact import fixture revisions are required.");
  if (url.endsWith(":content")) {
    return governedResponse(
      new Blob(["row,field,value\n"], { type: "text/csv" }),
      init,
      "text/csv",
    );
  }
  if (url.endsWith(":rollback")) {
    return governedResponse(
      {
        job: toolingImportJob("rolled_back"),
        rollback: {
          ...toolingImportReconciliation("rolled_back"),
          kind: "rollback_result",
        },
      },
      init,
    );
  }
  if (url.endsWith(":evaluate-rollback")) {
    return governedResponse(
      {
        rollbackEligibility: {
          ...toolingImportReconciliation(),
          kind: "rollback_eligibility",
        },
      },
      init,
    );
  }
  if (url.endsWith(":reconcile")) {
    return governedResponse(
      { reconciliation: toolingImportReconciliation() },
      init,
    );
  }
  if (url.endsWith(":retry")) {
    return governedResponse({ job: toolingImportJob("queued") }, init);
  }
  if (url.endsWith("/correction-artifacts")) {
    return governedResponse({ correctionArtifact }, init);
  }
  if (url.endsWith(":execute")) {
    return governedResponse({ job: toolingImportJob("queued") }, init);
  }
  if (url.endsWith("/confirmations")) {
    return governedResponse(
      { mappingAuthority: detail.mappingAuthority, preview },
      init,
    );
  }
  if (url.endsWith("/previews")) {
    return governedResponse(
      { mappingAuthority: detail.mappingAuthority, preview },
      init,
    );
  }
  if (url.endsWith("/mapping-proposals")) {
    return governedResponse(
      { mappingAuthority: detail.mappingAuthority, mappingProposal: mapping },
      init,
    );
  }
  if (url.endsWith("/inspections")) {
    return governedResponse({ inspection }, init);
  }
  if (url.endsWith(`/jobs/${toolingImportIds.job}`)) {
    return governedResponse(toolingImportJob(), init);
  }
  if (url.endsWith(`/tooling-imports/${toolingImportIds.batch}`)) {
    return governedResponse(detail, init);
  }
  if (url.endsWith("/tooling-imports") && init?.method === "POST") {
    return governedResponse(
      {
        batch: toolingImportCollection().batches[0],
        mappingAuthority: toolingImportCollection().mappingAuthority,
      },
      init,
    );
  }
  return governedResponse(toolingImportCollection(), init);
}

function context(suffix: string) {
  return {
    csrfToken: "c".repeat(32),
    idempotencyKey: `tooling-import-${suffix}-12345678`,
    signal: new AbortController().signal,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Tooling List import data source", () => {
  it("accepts only exact bounded collection, detail and job snapshots", () => {
    const collection = toolingImportCollection();
    const detail = toolingImportDetail();
    const job = toolingImportJob();
    expect(isToolingImportBatchCollection(collection)).toBe(true);
    expect(isToolingImportBatchDetail(detail)).toBe(true);
    expect(isToolingImportJob(job)).toBe(true);
    expect(isToolingImportBatchCollection({ ...collection, extra: true })).toBe(
      false,
    );
    expect(
      isToolingImportBatchDetail({
        ...detail,
        projectGlobalId: toolingImportIds.target,
      }),
    ).toBe(false);
    expect(
      isToolingImportJob({
        ...job,
        counts: { ...job.counts, created: -1 },
      }),
    ).toBe(false);
  });

  it("loads only the selected Project collection, batch and exact job paths", async () => {
    const fetch = vi.fn(responseFor);
    vi.stubGlobal("fetch", fetch);
    const source = new LiveToolingImportDataSource();

    await source.loadBatches(
      toolingImportIds.project,
      new AbortController().signal,
    );
    await source.loadBatch(
      toolingImportIds.project,
      toolingImportIds.batch,
      new AbortController().signal,
    );
    await source.loadJob(
      toolingImportIds.project,
      toolingImportIds.batch,
      toolingImportIds.job,
      new AbortController().signal,
    );

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      `/api/npi/v1/projects/${toolingImportIds.project}/tooling-imports`,
      `/api/npi/v1/projects/${toolingImportIds.project}/tooling-imports/${toolingImportIds.batch}`,
      `/api/npi/v1/projects/${toolingImportIds.project}/tooling-imports/${toolingImportIds.batch}/jobs/${toolingImportIds.job}`,
    ]);
  });

  it("submits version-bound preview, correction, retry and rollback commands", async () => {
    const fetch = vi.fn(responseFor);
    vi.stubGlobal("fetch", fetch);
    const source = new LiveToolingImportDataSource();
    const detail = toolingImportDetail();
    const inspection = detail.inspections[0];
    const mapping = detail.mappingProposals[0];
    const preview = detail.previews[0];
    const job = toolingImportJob();
    if (!inspection || !mapping || !preview)
      throw new Error("The exact fixture revisions are required.");

    await source.inspect(
      toolingImportIds.project,
      toolingImportIds.batch,
      context("inspect"),
    );
    await source.createMappingProposal(
      toolingImportIds.project,
      toolingImportIds.batch,
      {
        inspectionGlobalId: inspection.globalId,
        inspectionSnapshotHash: inspection.snapshotHash,
        reason: "Exact synthetic mapping",
        templateKey: "synthetic-tooling-list.v1",
      },
      context("mapping"),
    );
    await source.createPreview(
      toolingImportIds.project,
      toolingImportIds.batch,
      {
        inspectionGlobalId: inspection.globalId,
        inspectionSnapshotHash: inspection.snapshotHash,
        mappingGlobalId: mapping.globalId,
        mappingSnapshotHash: mapping.snapshotHash,
      },
      context("preview"),
    );
    await source.confirmPreview(
      toolingImportIds.project,
      toolingImportIds.batch,
      toolingImportIds.preview,
      {
        confirmations: [
          {
            kind: "relationship",
            reason: "Exact target confirmed",
            selectedTargetGlobalId: toolingImportIds.target,
            selectedTargetObject: "tooling_master",
            selectedTargetSnapshotHash: "c".repeat(64),
            sourceRow: 3,
            worksheetName: "Tooling List",
          },
        ],
        expectedSnapshotHash: preview.snapshotHash,
        expectedVersion: preview.previewVersion,
      },
      context("confirm"),
    );
    await source.execute(
      toolingImportIds.project,
      toolingImportIds.batch,
      toolingImportIds.preview,
      { expectedSnapshotHash: preview.snapshotHash, expectedVersion: 1 },
      context("execute"),
    );
    await source.createCorrectionArtifact(
      toolingImportIds.project,
      toolingImportIds.batch,
      toolingImportIds.job,
      {
        corrections: [
          {
            correctedValue: "TL-SYN-002",
            sourceHeader: "Tooling No.",
            sourceRow: 3,
            worksheetName: "Tooling List",
          },
        ],
        expectedSnapshotHash: job.snapshotHash,
        expectedVersion: job.optimisticVersion,
      },
      context("correction"),
    );
    await source.retry(
      toolingImportIds.project,
      toolingImportIds.batch,
      toolingImportIds.job,
      {
        correctionArtifactGlobalId: toolingImportIds.correction,
        correctionArtifactSnapshotHash: correctionArtifact.snapshotHash,
        expectedSnapshotHash: job.snapshotHash,
        expectedVersion: job.optimisticVersion,
      },
      context("retry"),
    );
    await source.reconcile(
      toolingImportIds.project,
      toolingImportIds.batch,
      toolingImportIds.job,
      {
        expectedSnapshotHash: job.snapshotHash,
        expectedVersion: job.optimisticVersion,
      },
      context("reconcile"),
    );
    await source.evaluateRollback(
      toolingImportIds.project,
      toolingImportIds.batch,
      toolingImportIds.job,
      {
        expectedSnapshotHash: job.snapshotHash,
        expectedVersion: job.optimisticVersion,
      },
      context("evaluate"),
    );
    await source.rollback(
      toolingImportIds.project,
      toolingImportIds.batch,
      toolingImportIds.job,
      {
        eligibilityGlobalId: toolingImportIds.reconciliation,
        eligibilitySnapshotHash: "f".repeat(64),
        expectedSnapshotHash: job.snapshotHash,
        expectedVersion: job.optimisticVersion,
      },
      context("rollback"),
    );

    expect(fetch).toHaveBeenCalledTimes(10);
    for (const [, init] of fetch.mock.calls) {
      const headers = new Headers(init?.headers);
      expect(headers.get("X-Frappe-CSRF-Token")).toBe("c".repeat(32));
      expect(headers.get("Idempotency-Key")).toMatch(/^tooling-import-/u);
      expect(init?.method).toBe("POST");
    }
  });

  it("rejects malformed identities before any request leaves the browser", async () => {
    const fetch = vi.fn(responseFor);
    vi.stubGlobal("fetch", fetch);
    await expect(
      new LiveToolingImportDataSource().loadBatches(
        "not-a-project",
        new AbortController().signal,
      ),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    expect(fetch).not.toHaveBeenCalled();
  });
});
