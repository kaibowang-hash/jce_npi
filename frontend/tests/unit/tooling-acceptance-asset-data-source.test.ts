import { afterEach, describe, expect, it, vi } from "vitest";

import {
  confirmedToolAssetProjection,
  LiveToolingAcceptanceAssetDataSource,
} from "../../src/api/tooling-acceptance-asset-data-source";
import {
  isCreateToolAssetRequestCommand,
  isCreateToolingAcceptanceEvidenceRevisionCommand,
  isToolAssetRequest,
  isToolAssetRequestCollection,
  isToolingAcceptanceAssetContext,
  LiveToolingDataSource,
} from "../../src/api/tooling-data-source";
import {
  acceptanceCommand,
  acceptanceContext,
  acceptanceRevision,
  assetRequest,
  assetRequestCollection,
  assetRequestCommand,
  toolAssetProjectionCollection,
  toolingAcceptanceIds as ids,
} from "../support/tooling-acceptance-fixture";

function required<T>(value: T | undefined, message: string): T {
  if (value === undefined) throw new Error(message);
  return value;
}

function governedResponse(value: unknown, init?: RequestInit): Response {
  const headers = new Headers(init?.headers);
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Idempotency-Replayed": "false",
      "X-Request-ID": headers.get("X-Request-ID") ?? "",
      "X-Trace-ID": "trace-tooling-acceptance-source",
    },
    status: init?.method === "POST" ? 201 : 200,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Tooling acceptance and Asset live data source", () => {
  it("delegates the governed Asset kind and confirms only exact current truth", async () => {
    const collection = toolAssetProjectionCollection();
    const loadProjectProjections = vi.fn(() => Promise.resolve(collection));
    const source = new LiveToolingAcceptanceAssetDataSource({
      loadProjectProjections,
    });
    const signal = new AbortController().signal;

    await expect(
      source.loadAssetProjections(ids.project, signal),
    ).resolves.toBe(collection);
    expect(loadProjectProjections).toHaveBeenCalledWith(
      ids.project,
      signal,
      "tool_asset_status",
    );
    const item = required(collection.items[0], "The Asset item is required.");
    expect(confirmedToolAssetProjection(item)).toMatchObject({
      values: { formalAssetId: "ASSET-00042" },
    });

    const stale = structuredClone(item);
    stale.freshness = "stale";
    expect(confirmedToolAssetProjection(stale)).toBeNull();

    const conflicted = structuredClone(item);
    conflicted.disposition = "conflicted";
    expect(confirmedToolAssetProjection(conflicted)).toBeNull();

    const mismatched = structuredClone(item);
    if (!mismatched.currentTruth)
      throw new Error("The Asset current truth is required.");
    mismatched.currentTruth.payloadHash = "f".repeat(64);
    expect(confirmedToolAssetProjection(mismatched)).toBeNull();
  });

  it("accepts only exact unavailable ERP projection and separated Mock truth", () => {
    expect(isToolingAcceptanceAssetContext(acceptanceContext())).toBe(true);
    expect(isToolAssetRequestCollection(assetRequestCollection())).toBe(true);
    expect(isToolAssetRequest(assetRequest())).toBe(true);
    expect(
      isToolingAcceptanceAssetContext({
        ...acceptanceContext(),
        assetProjection: {
          ...acceptanceContext().assetProjection,
          formalAssetId: "ASSET-001",
          state: "available",
        },
      }),
    ).toBe(false);
    expect(
      isToolAssetRequest({
        ...assetRequest(),
        dispatchState: "dispatched",
        targetResultState: "succeeded",
      }),
    ).toBe(false);
  });

  it("rejects caller approval, dispatch and invented target payload fields", () => {
    expect(
      isCreateToolingAcceptanceEvidenceRevisionCommand(acceptanceCommand()),
    ).toBe(true);
    expect(isCreateToolAssetRequestCommand(assetRequestCommand())).toBe(true);
    expect(
      isCreateToolingAcceptanceEvidenceRevisionCommand({
        ...acceptanceCommand(),
        approvalState: "approved",
      }),
    ).toBe(false);
    expect(
      isCreateToolAssetRequestCommand({
        ...assetRequestCommand(),
        targetPayload: { assetName: "Invented target" },
      }),
    ).toBe(false);
    expect(
      isCreateToolAssetRequestCommand({
        ...assetRequestCommand(),
        acknowledgement: "Approve and dispatch",
      }),
    ).toBe(false);
  });

  it("uses exactly five governed Project-first routes", async () => {
    const fetch = vi.fn((request: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof request === "string"
          ? request
          : request instanceof URL
            ? request.href
            : request.url;
      let value: unknown;
      if (url.endsWith("/acceptance-assets")) value = acceptanceContext();
      else if (url.endsWith("/acceptance-revisions"))
        value = { acceptanceEvidence: acceptanceRevision() };
      else if (url.endsWith(`/asset-requests/${ids.request}`))
        value = assetRequest();
      else if (init?.method === "POST") value = assetRequest();
      else value = assetRequestCollection();
      return Promise.resolve(governedResponse(value, init));
    });
    vi.stubGlobal("fetch", fetch);
    const source = new LiveToolingDataSource();
    const signal = new AbortController().signal;
    const context = (suffix: string) => ({
      csrfToken: "c".repeat(32),
      idempotencyKey: `tooling-acceptance-${suffix}-12345678`,
      signal,
    });

    await source.loadAcceptanceAssets(ids.project, ids.master, signal);
    await source.createToolingAcceptanceRevision(
      ids.project,
      ids.master,
      acceptanceCommand(),
      context("evidence"),
    );
    await source.loadToolAssetRequests(ids.project, ids.master, signal);
    await source.createToolAssetRequest(
      ids.project,
      ids.master,
      ids.set,
      assetRequestCommand(),
      context("mock"),
    );
    await source.loadToolAssetRequest(
      ids.project,
      ids.master,
      ids.request,
      signal,
    );

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/acceptance-assets`,
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/acceptance-revisions`,
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/asset-requests`,
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/sets/${ids.set}/asset-requests`,
      `/api/npi/v1/projects/${ids.project}/tooling/${ids.master}/asset-requests/${ids.request}`,
    ]);
    expect(
      fetch.mock.calls
        .filter(([, init]) => init?.method === "POST")
        .every(([, init]) => {
          const headers = new Headers(init?.headers);
          return (
            headers.get("X-Frappe-CSRF-Token") === "c".repeat(32) &&
            headers.get("Idempotency-Key")?.startsWith("tooling-acceptance-")
          );
        }),
    ).toBe(true);
  });

  it("fails closed when an exact response escapes Project containment", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_request: RequestInfo | URL, init?: RequestInit) =>
        Promise.resolve(
          governedResponse(
            {
              ...acceptanceContext(),
              projectGlobalId: ids.acceptanceRevision,
            },
            init,
          ),
        ),
      ),
    );
    await expect(
      new LiveToolingDataSource().loadAcceptanceAssets(
        ids.project,
        ids.master,
        new AbortController().signal,
      ),
    ).rejects.toThrow();
  });
});
