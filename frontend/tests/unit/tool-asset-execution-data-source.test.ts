import { describe, expect, it, vi } from "vitest";

import { NpiHttpClient } from "../../src/api/http";
import {
  confirmedToolAssetExecutionProjection,
  LiveToolAssetExecutionDataSource,
} from "../../src/api/tool-asset-execution-data-source";
import { confirmedToolAssetProjection } from "../../src/api/tooling-acceptance-asset-data-source";
import {
  toolAssetProjectionCollection,
  toolingAcceptanceIds as ids,
} from "../support/tooling-acceptance-fixture";
import {
  toolAssetExecutionCollection,
  toolAssetExecutionContext,
  toolAssetExecutionDetail,
  toolAssetExecutionRequestId,
} from "../support/tool-asset-execution-fixture";

describe("Tool Asset execution data source", () => {
  it("uses only exact Project-first collection, detail and operation-specific routes", async () => {
    const http = new NpiHttpClient();
    const detail = toolAssetExecutionDetail();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(toolAssetExecutionCollection(detail))
      .mockResolvedValueOnce(detail)
      .mockResolvedValueOnce(detail);
    const source = new LiveToolAssetExecutionDataSource(http);
    const signal = new AbortController().signal;
    await source.loadRequests(
      ids.project,
      ids.master,
      ids.set,
      ids.acceptanceRevision,
      signal,
    );
    await source.loadRequest(
      ids.project,
      ids.master,
      ids.set,
      toolAssetExecutionRequestId,
      signal,
    );
    await source.createRequest(
      ids.project,
      ids.master,
      ids.set,
      toolAssetExecutionContext(),
      { csrfToken: "csrf", idempotencyKey: "tool-asset-test", signal },
    );
    const base = `/projects/${ids.project}/tooling/${ids.master}/sets/${ids.set}/asset-execution-requests`;
    expect(request.mock.calls[0]?.[0]).toBe(base);
    expect(request.mock.calls[0]?.[2]).toMatchObject({
      query: { acceptanceRevisionGlobalId: ids.acceptanceRevision },
    });
    expect(request.mock.calls[1]?.[0]).toBe(
      `${base}/${toolAssetExecutionRequestId}`,
    );
    expect(request.mock.calls[2]?.[0]).toBe(`${base}:create`);
    expect(request.mock.calls[2]?.[1]).toMatchObject({
      method: "POST",
      headers: { "Idempotency-Key": "tool-asset-test" },
    });
  });

  it("withholds formal identity unless execution and fresh P8-01 truth match", () => {
    const detail = toolAssetExecutionDetail("succeeded");
    const projectionItem = toolAssetProjectionCollection().items[0];
    expect(projectionItem).toBeDefined();
    if (!projectionItem) throw new Error("fixture projection is missing");
    const projection = confirmedToolAssetProjection(projectionItem);
    expect(
      confirmedToolAssetExecutionProjection(detail, projection)?.formalAssetId,
    ).toBe("ASSET-00042");
    expect(
      confirmedToolAssetExecutionProjection(
        { ...detail, permissions: { ...detail.permissions, canView: false } },
        projection,
      ),
    ).toBeNull();
    expect(
      confirmedToolAssetExecutionProjection(
        toolAssetExecutionDetail("synthetic_verified"),
        projection,
      ),
    ).toBeNull();
  });

  it("rejects extra response fields and target identity outside current mapping", async () => {
    const http = new NpiHttpClient();
    const invalid = {
      ...toolAssetExecutionDetail("synthetic_verified"),
      leakedTarget: "ASSET-LEAK",
    };
    vi.spyOn(http, "request").mockImplementation((_path, _init, options) => {
      if (!options?.validate?.(invalid))
        return Promise.reject(new Error("invalid"));
      return Promise.resolve(invalid);
    });
    await expect(
      new LiveToolAssetExecutionDataSource(http).loadRequest(
        ids.project,
        ids.master,
        ids.set,
        toolAssetExecutionRequestId,
        new AbortController().signal,
      ),
    ).rejects.toThrow("invalid");
  });
});
