import { describe, expect, it, vi } from "vitest";

import {
  LiveDataExchangeDataSource,
  type DataExchangeExport,
  type DataExchangeProfile,
  type DataExchangeWorkspace,
  type RetentionArchiveRecord,
  type RetentionPolicyVersion,
} from "../../src/api/data-exchange-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";

const profile: DataExchangeProfile = {
  schemaVersion: "data-exchange-export-profile.v1",
  globalId: "11111111-1111-4111-8111-111111111111",
  version: 1,
  datasetId: "project_portfolio.v1",
  columns: ["projectCode", "title"],
  language: "en",
  redactionProfile: "minimum_disclosure.v1",
  query: {},
  outputs: ["csv", "xlsx", "pdf", "readme"],
  maxRows: 100,
  maxBytes: 1_000_000,
  publishedByUserId: "manager@example.invalid",
  publishedAt: "2026-09-03T08:00:00Z",
  definitionHash: "a".repeat(64),
};
const exportRecord: DataExchangeExport = {
  schemaVersion: "data-exchange-export.v1",
  globalId: "22222222-2222-4222-8222-222222222222",
  tenantId: "tenant-a",
  datasetId: "project_portfolio.v1",
  profileGlobalId: profile.globalId,
  profileVersion: 1,
  profileHash: profile.definitionHash,
  sourceHash: "b".repeat(64),
  dataHash: "c".repeat(64),
  rowCount: 2,
  artifact: {
    fileName: "data-exchange.zip",
    mimeType: "application/zip",
    sizeBytes: 3,
    sha256: "d".repeat(64),
    manifestSha256: "e".repeat(64),
  },
  createdByUserId: "manager@example.invalid",
  createdAt: "2026-09-03T08:01:00Z",
  requestId: "33333333-3333-4333-8333-333333333333",
  traceId: "trace-data-exchange",
  privateFileBound: true,
  recordHash: "f".repeat(64),
};
const policy: RetentionPolicyVersion = {
  schemaVersion: "retention-policy.v1",
  globalId: "44444444-4444-4444-8444-444444444444",
  version: 1,
  scope: "tenant",
  scopeReference: null,
  effectiveFrom: "2026-01-01",
  effectiveUntil: null,
  retentionYears: {
    project: 7,
    quality: 7,
    change: 7,
    file: 7,
    data_exchange_export: 7,
    controlled_print: 7,
  },
  publishedByUserId: "manager@example.invalid",
  publishedAt: "2026-09-03T08:02:00Z",
  definitionHash: "1".repeat(64),
};
const archive: RetentionArchiveRecord = {
  schemaVersion: "retention-archive-record.v1",
  globalId: "55555555-5555-4555-8555-555555555555",
  tenantId: "tenant-a",
  sourceKind: "file_revision",
  category: "file",
  sourceId: "66666666-6666-4666-8666-666666666666",
  sourceVersion: 2,
  sourceHash: "2".repeat(64),
  sourceDate: "2026-09-01",
  sourceSnapshot: { privateFileBound: true },
  policyId: policy.globalId,
  policyVersion: policy.version,
  policyHash: policy.definitionHash,
  retainUntil: "2033-09-01",
  createdByUserId: "manager@example.invalid",
  createdAt: "2026-09-03T08:03:00Z",
  requestId: "77777777-7777-4777-8777-777777777777",
  traceId: "trace-data-exchange",
  recordHash: "3".repeat(64),
};
const workspace: DataExchangeWorkspace = {
  schemaVersion: "data-exchange.v1",
  mode: "closed_operation_specific",
  routesEnabled: true,
  productionContact: false,
  genericWriterAvailable: false,
  automaticDispositionAvailable: false,
  capabilities: [],
  profiles: [profile],
  exports: [exportRecord],
  retentionPolicies: [policy],
  archiveRecords: [archive],
};
const context = {
  csrfToken: "csrf-" + "a".repeat(48),
  idempotencyKey: "p9-06-command-0001",
  signal: new AbortController().signal,
};

describe("Data Exchange data source", () => {
  it("uses only fixed BFF routes with command protections", async () => {
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(workspace)
      .mockResolvedValueOnce(profile)
      .mockResolvedValueOnce(exportRecord)
      .mockResolvedValueOnce(policy)
      .mockResolvedValueOnce(archive);
    const source = new LiveDataExchangeDataSource(http);
    await source.load(context.signal);
    await source.publishProfile(
      {
        globalId: profile.globalId,
        version: 1,
        datasetId: profile.datasetId,
        columns: profile.columns,
        language: profile.language,
        redactionProfile: profile.redactionProfile,
        query: {},
        maxRows: 100,
        maxBytes: 1_000_000,
      },
      context,
    );
    await source.createExport(profile, context);
    await source.publishPolicy(policy, context);
    await source.createArchive(
      {
        globalId: archive.globalId,
        sourceKind: archive.sourceKind,
        sourceId: archive.sourceId,
        sourceVersion: archive.sourceVersion,
        sourceHash: archive.sourceHash,
        policyId: policy.globalId,
        policyVersion: policy.version,
        policyHash: policy.definitionHash,
        scope: policy.scope,
        scopeReference: null,
      },
      context,
    );
    expect(request.mock.calls.map((call) => call[0])).toEqual([
      "/administration/data-exchange",
      "/administration/data-exchange/profiles",
      "/administration/data-exchange/exports",
      "/administration/data-exchange/retention-policies",
      "/administration/data-exchange/archive-records",
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

  it("rejects malformed identities before transport and extra server truth", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveDataExchangeDataSource(http);
    await expect(
      source.publishProfile(
        {
          globalId: "not-a-uuid",
          version: 1,
          datasetId: "project_portfolio.v1",
          columns: ["projectCode"],
          language: "en",
          redactionProfile: "minimum_disclosure.v1",
          query: {},
          maxRows: 100,
          maxBytes: 1_000_000,
        },
        context,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
    request.mockResolvedValue({ ...workspace, productionEndpoint: "hidden" });
    await source.load(context.signal);
    const validate = request.mock.calls[0]?.[2]?.validate;
    expect(validate?.(workspace)).toBe(true);
    expect(validate?.({ ...workspace, productionEndpoint: "hidden" })).toBe(
      false,
    );
    expect(validate?.({ ...workspace, productionContact: true })).toBe(false);
  });

  it("downloads only the exact immutable private ZIP", async () => {
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValue(new Blob(["zip"]));
    const source = new LiveDataExchangeDataSource(http);
    await source.downloadExport(exportRecord, context);
    expect(request).toHaveBeenCalledWith(
      `/administration/data-exchange/exports/${exportRecord.globalId}:content`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expectedPackageHash: exportRecord.artifact.sha256,
        }),
      }),
      expect.objectContaining({
        responseType: "blob",
        requirePrivateNoStore: true,
      }),
    );
  });
});

export { archive, exportRecord, policy, profile, workspace };
