import { afterEach, describe, expect, it, vi } from "vitest";

import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  isMbomRequestDetail,
  isMbomRequestList,
  LiveMbomPublishDataSource,
  MBOM_PUBLISH_ACKNOWLEDGEMENT,
  type CreateMbomRequestCommand,
} from "../../src/api/mbom-publish-data-source";
import { ebomProjectId } from "../support/ebom-fixture";
import {
  mbomPublishDetailFixture,
  mbomPublishListFixture,
  mbomRequestId,
} from "../support/mbom-publish-fixture";
import { publishRequestId } from "../support/publish-request-fixture";

const context = () => ({
  csrfToken: "csrf-mbom-publish-fixture",
  idempotencyKey: "mbom-fixture-key",
  signal: new AbortController().signal,
});

function command(): CreateMbomRequestCommand {
  const detail = mbomPublishDetailFixture({
    state: "queued",
    targetMode: "synthetic",
  });
  return {
    phase5PublishRequestGlobalId: publishRequestId,
    expectedSourceHash: detail.request.source.sourceHash,
    expectedTopologyHash: detail.request.source.topologyHash,
    expectedItemMappingSetHash: detail.request.itemMappingSetHash,
    expectedMbomMappingSetHash: detail.request.mbomMappingSetHash,
    acknowledgement: MBOM_PUBLISH_ACKNOWLEDGEMENT,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MBOM publish response validation", () => {
  it.each([
    ["validated_mock", "mock"],
    ["queued", "synthetic"],
    ["processing", "synthetic"],
    ["synthetic_verified", "synthetic"],
    ["partially_succeeded", "sandbox"],
    ["succeeded", "sandbox"],
    ["failed_retryable", "synthetic"],
    ["failed_final", "synthetic"],
    ["uncertain_after_timeout", "sandbox"],
    ["mapping_conflict", "sandbox"],
  ] as const)("accepts exact %s/%s truth", (state, targetMode) => {
    const detail = mbomPublishDetailFixture({ state, targetMode });
    expect(isMbomRequestDetail(detail)).toBe(true);
    expect(isMbomRequestList(mbomPublishListFixture(detail))).toBe(true);
  });

  it("rejects detached attempt, result and node-result evidence", () => {
    const detail = mbomPublishDetailFixture({ state: "succeeded" });
    const attempt = detail.attempts[0];
    const result = detail.result;
    const nodeResult = detail.nodeResults[0];
    if (!attempt || !result || !nodeResult)
      throw new Error("Fixture evidence is unavailable.");
    expect(
      isMbomRequestDetail({
        ...detail,
        attempts: [{ ...attempt, requestGlobalId: mbomAssemblyId }],
      }),
    ).toBe(false);
    expect(
      isMbomRequestDetail({
        ...detail,
        result: { ...result, sourceHash: "e".repeat(64) },
      }),
    ).toBe(false);
    expect(
      isMbomRequestDetail({
        ...detail,
        nodeResults: [{ ...nodeResult, nodeGlobalId: mbomAssemblyId }],
      }),
    ).toBe(false);
    expect(
      isMbomRequestDetail({
        ...detail,
        result: { ...result, state: "partially_succeeded" },
      }),
    ).toBe(false);
  });

  it("allows formal BOM identity only through matching authenticated current mapping", () => {
    const authoritative = mbomPublishDetailFixture({
      state: "succeeded",
      targetMode: "sandbox",
    });
    expect(authoritative.currentMappings[0]?.formalBomId).toBe(
      "BOM-SANDBOX-0001",
    );
    expect(isMbomRequestDetail(authoritative)).toBe(true);
    expect(isMbomRequestDetail({ ...authoritative, currentMappings: [] })).toBe(
      false,
    );
    const redacted = {
      ...authoritative,
      currentMappings: [],
      nodeResults: authoritative.nodeResults.map((item) => ({
        ...item,
        formalBomId: null,
        targetSubmissionState: null,
        targetVersion: null,
      })),
      permissions: { canExecute: false, canView: false },
    };
    expect(isMbomRequestDetail(redacted)).toBe(true);
    expect(
      isMbomRequestDetail({
        ...redacted,
        currentMappings: authoritative.currentMappings,
      }),
    ).toBe(false);
    const synthetic = mbomPublishDetailFixture({ state: "synthetic_verified" });
    const node = synthetic.nodeResults[0];
    if (!node) throw new Error("Synthetic evidence is unavailable.");
    expect(
      isMbomRequestDetail({
        ...synthetic,
        nodeResults: [{ ...node, formalBomId: "BOM-LEAK" }],
      }),
    ).toBe(false);
  });

  it("rejects Project/source drift and invalid create context", () => {
    const list = mbomPublishListFixture();
    expect(
      isMbomRequestList({ ...list, projectGlobalId: mbomAssemblyId }),
    ).toBe(false);
    expect(
      isMbomRequestList({
        ...list,
        createContext: list.createContext
          ? {
              ...list.createContext,
              phase5PublishRequestGlobalId: mbomAssemblyId,
            }
          : null,
      }),
    ).toBe(false);
  });
});

const mbomAssemblyId = "78000000-0000-4000-8000-000000000099";

describe("Live MBOM publish data source", () => {
  it("uses only fixed Project-first list and detail routes", async () => {
    const list = mbomPublishListFixture();
    const detail = mbomPublishDetailFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(list)
      .mockResolvedValueOnce(detail);
    const source = new LiveMbomPublishDataSource(http);
    const signal = new AbortController().signal;
    await source.loadRequests(ebomProjectId, publishRequestId, signal);
    await source.loadRequest(ebomProjectId, mbomRequestId, signal);
    const base = `/projects/${ebomProjectId}/mbom-publish-requests`;
    expect(request.mock.calls[0]?.[0]).toBe(base);
    expect(request.mock.calls[0]?.[2]).toMatchObject({
      query: { phase5PublishRequestGlobalId: publishRequestId },
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(request.mock.calls[1]?.[0]).toBe(`${base}/${mbomRequestId}`);
  });

  it("sends only the exact acknowledged CSRF/idempotent command", async () => {
    const response = mbomPublishListFixture().items[0];
    if (!response) throw new Error("Fixture summary is unavailable.");
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new LiveMbomPublishDataSource(http);
    await source.createRequest(ebomProjectId, command(), context());
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(`/projects/${ebomProjectId}/mbom-publish-requests`);
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
      "mbom-fixture-key",
    );
    expect(options).toMatchObject({
      csrfToken: "csrf-mbom-publish-fixture",
      requireIdempotencyReplay: true,
      requirePrivateNoStore: true,
    });
    if (typeof init?.body !== "string")
      throw new Error("Command body is unavailable.");
    expect(JSON.parse(init.body)).toEqual(command());
  });

  it("fails closed before transport for mutable identities and wrong acknowledgement", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveMbomPublishDataSource(http);
    await expect(
      source.loadRequests(
        ebomProjectId,
        "latest",
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.createRequest(
        ebomProjectId,
        {
          ...command(),
          acknowledgement: "Submit the BOM.",
        } as unknown as CreateMbomRequestCommand,
        context(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
