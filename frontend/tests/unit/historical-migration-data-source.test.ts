import { describe, expect, it, vi } from "vitest";

import {
  LiveHistoricalMigrationDataSource,
  type HistoricalMigrationJob,
  type HistoricalMigrationPreview,
  type HistoricalMigrationWorkspace,
} from "../../src/api/historical-migration-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";

const preview: HistoricalMigrationPreview = {
  schemaVersion: "historical-migration-preview.v1",
  globalId: "11111111-1111-4111-8111-111111111111",
  bundleId: "22222222-2222-4222-8222-222222222222",
  manifestHash: "a".repeat(64),
  sourceSha256: "b".repeat(64),
  sourceFileRevisionGlobalId: "33333333-3333-4333-8333-333333333333",
  sourceFileOptimisticVersion: 2,
  tenantId: "tenant-a",
  version: 1,
  summary: { create: 1, link: 0, skip: 0, blocked: 0 },
  rows: [
    {
      family: "project",
      ordinal: 2,
      sourceKey: "project-01",
      sourceHash: "c".repeat(64),
      action: "create",
      targetGlobalId: null,
      targetVersion: null,
      targetSnapshotHash: null,
      differences: [],
      findings: [],
    },
  ],
  createdByUserId: "manager@example.invalid",
  createdAt: "2026-09-03T08:00:00Z",
  requestId: "44444444-4444-4444-8444-444444444444",
  traceId: "trace-p9-05-preview",
  snapshotHash: "d".repeat(64),
};

const job: HistoricalMigrationJob = {
  schemaVersion: "historical-migration-job.v1",
  globalId: "55555555-5555-4555-8555-555555555555",
  batchGlobalId: preview.bundleId,
  previewGlobalId: preview.globalId,
  previewSnapshotHash: preview.snapshotHash,
  state: "queued",
  optimisticVersion: 1,
  results: [],
  queuedAt: "2026-09-03T08:01:00Z",
  updatedAt: "2026-09-03T08:01:00Z",
  actorUserId: "manager@example.invalid",
  requestId: "66666666-6666-4666-8666-666666666666",
  traceId: "trace-p9-05-job",
  productionContact: false,
  snapshotHash: "e".repeat(64),
};

const workspace: HistoricalMigrationWorkspace = {
  schemaVersion: "historical-migration-rehearsal.v1",
  mode: "non_production_rehearsal",
  executionEnabled: true,
  productionContact: false,
  previews: [preview],
  jobs: [job],
};

const context = {
  csrfToken: "csrf-" + "a".repeat(48),
  idempotencyKey: "p9-05-command-0001",
  signal: new AbortController().signal,
};

describe("historical migration data source", () => {
  it("uses only fixed administration routes with command protections", async () => {
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(workspace)
      .mockResolvedValueOnce(preview)
      .mockResolvedValueOnce(job)
      .mockResolvedValueOnce(job)
      .mockResolvedValueOnce(job);
    const source = new LiveHistoricalMigrationDataSource(http);
    await source.load(context.signal);
    await source.createPreview(
      {
        tenantId: "tenant-a",
        fileRevisionGlobalId: preview.sourceFileRevisionGlobalId,
        fileOptimisticVersion: 2,
        sha256: preview.sourceSha256,
      },
      context,
    );
    await source.execute(preview, context);
    await source.reconcile(job, context);
    await source.rollback(job, context);
    expect(request.mock.calls.map((call) => call[0])).toEqual([
      "/administration/historical-migration-rehearsals",
      "/administration/historical-migration-rehearsals",
      `/administration/historical-migration-rehearsals/${preview.globalId}:execute`,
      `/administration/historical-migration-jobs/${job.globalId}:reconcile`,
      `/administration/historical-migration-jobs/${job.globalId}:rollback`,
    ]);
    for (const call of request.mock.calls.slice(1)) {
      expect(call[2]).toMatchObject({
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
      });
    }
  });

  it("fails before transport for untrusted identity hash version and session shapes", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveHistoricalMigrationDataSource(http);
    for (const command of [
      {
        tenantId: "",
        fileRevisionGlobalId: preview.sourceFileRevisionGlobalId,
        fileOptimisticVersion: 2,
        sha256: preview.sourceSha256,
      },
      {
        tenantId: "tenant-a",
        fileRevisionGlobalId: "not-a-uuid",
        fileOptimisticVersion: 2,
        sha256: preview.sourceSha256,
      },
      {
        tenantId: "tenant-a",
        fileRevisionGlobalId: preview.sourceFileRevisionGlobalId,
        fileOptimisticVersion: 0,
        sha256: preview.sourceSha256,
      },
      {
        tenantId: "tenant-a",
        fileRevisionGlobalId: preview.sourceFileRevisionGlobalId,
        fileOptimisticVersion: 2,
        sha256: "not-a-hash",
      },
    ]) {
      await expect(
        source.createPreview(command, context),
      ).rejects.toBeInstanceOf(NpiTransportError);
    }
    expect(request).not.toHaveBeenCalled();
  });

  it("downloads only the exact private correction artifact bound to the job snapshot", async () => {
    const correctedJob: HistoricalMigrationJob = {
      ...job,
      correction: {
        schemaVersion: "historical-migration-correction.v1",
        jobGlobalId: job.globalId,
        fileName: "historical-migration-correction.csv",
        sizeBytes: 3,
        sha256: "f".repeat(64),
        failedRowCount: 1,
        private: true,
      },
    };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValue(new Blob(["a,b"], { type: "text/csv" }));
    const source = new LiveHistoricalMigrationDataSource(http);
    const result = await source.downloadCorrection(correctedJob, context);
    expect(result.fileName).toBe("historical-migration-correction.csv");
    expect(request).toHaveBeenCalledWith(
      `/administration/historical-migration-jobs/${job.globalId}/correction-artifact:content`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expectedSnapshotHash: job.snapshotHash }),
      }),
      expect.objectContaining({
        responseType: "blob",
        requirePrivateNoStore: true,
      }),
    );
  });

  it("loads one exact job and creates its bound private correction artifact", async () => {
    const correction = {
      schemaVersion: "historical-migration-correction.v1" as const,
      jobGlobalId: job.globalId,
      fileName: "historical-migration-correction.csv",
      sizeBytes: 16,
      sha256: "f".repeat(64),
      failedRowCount: 2,
      private: true as const,
    };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(job)
      .mockResolvedValueOnce(correction);
    const source = new LiveHistoricalMigrationDataSource(http);

    await expect(source.loadJob(job.globalId, context.signal)).resolves.toEqual(
      job,
    );
    await expect(
      source.createCorrection(job.globalId, context),
    ).resolves.toEqual(correction);
    expect(request.mock.calls.map((call) => call[0])).toEqual([
      `/administration/historical-migration-jobs/${job.globalId}`,
      `/administration/historical-migration-jobs/${job.globalId}/correction-artifacts`,
    ]);
  });

  it("passes a strict validator that rejects extra response fields", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request").mockResolvedValue(workspace);
    const source = new LiveHistoricalMigrationDataSource(http);
    await source.load(context.signal);
    const validate = request.mock.calls[0]?.[2]?.validate;
    expect(validate?.(workspace)).toBe(true);
    expect(validate?.({ ...workspace, productionEndpoint: "hidden" })).toBe(
      false,
    );
    expect(validate?.({ ...workspace, productionContact: true })).toBe(false);
  });
});
