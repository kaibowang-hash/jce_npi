import { describe, expect, it, vi } from "vitest";

import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  isIntegrationOperationCollection,
  isIntegrationOperationDetail,
  isIntegrationOperationItem,
  LiveIntegrationOperationsDataSource,
} from "../../src/api/integration-operations-data-source";
import {
  integrationOperationCollection,
  integrationOperationDetail,
  integrationOperationItem,
  integrationOperationsProjectId as projectId,
} from "../support/integration-operations-fixture";

describe("integration operations data source", () => {
  it("uses only Project-first reads and fixed operation-specific command paths", async () => {
    const http = new NpiHttpClient();
    const item = integrationOperationItem("failed_retryable", 4);
    const collection = integrationOperationCollection({ items: [item] });
    const detail = integrationOperationDetail(item);
    const result = {
      actionGlobalId: "90000000-0000-4000-8000-000000000001",
      operationGlobalId: item.operationGlobalId,
      outcomeState: "replay_requested",
      outcomeReferenceGlobalId: item.operationGlobalId,
    };
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(collection)
      .mockResolvedValueOnce(collection)
      .mockResolvedValueOnce(detail)
      .mockResolvedValueOnce(result);
    const source = new LiveIntegrationOperationsDataSource(http);
    const signal = new AbortController().signal;

    await source.loadOperations(
      projectId,
      { operationKind: "create_tool_asset", limit: 50 },
      signal,
    );
    await source.loadOperations(projectId, { logicalDlq: true }, signal);
    await source.loadOperation(
      projectId,
      item.operationKind,
      item.operationGlobalId,
      signal,
    );
    await source.requestAction(projectId, item, "replay", {
      csrfToken: "c".repeat(32),
      idempotencyKey: "p807-replay-fixed-0001",
      signal,
    });

    expect(request.mock.calls[0]?.[0]).toBe(
      `/projects/${projectId}/integration-operations`,
    );
    expect(request.mock.calls[0]?.[2]).toMatchObject({
      query: { limit: "50", operationKind: "create_tool_asset" },
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(request.mock.calls[1]?.[0]).toBe(
      `/projects/${projectId}/integration-operations/dlq`,
    );
    expect(request.mock.calls[2]?.[0]).toBe(
      `/projects/${projectId}/integration-operations/create_tool_asset/${item.operationGlobalId}`,
    );
    expect(request.mock.calls[3]?.[0]).toBe(
      `/projects/${projectId}/integration-operations/tool-asset-creates/${item.operationGlobalId}:replay`,
    );
    expect(request.mock.calls[3]?.[1]).toMatchObject({
      body: JSON.stringify({
        expectedRawState: item.rawState,
        expectedVersion: item.operationVersion,
      }),
      headers: { "Idempotency-Key": "p807-replay-fixed-0001" },
      method: "POST",
    });
  });

  it("rejects extra fields, foreign Projects and inconsistent replay truth", () => {
    const item = integrationOperationItem("failed_retryable", 4);
    expect(isIntegrationOperationItem(item, projectId)).toBe(true);
    expect(
      isIntegrationOperationCollection(
        integrationOperationCollection(),
        projectId,
      ),
    ).toBe(true);
    expect(
      isIntegrationOperationCollection(
        { ...integrationOperationCollection(), leakedPayload: "secret" },
        projectId,
      ),
    ).toBe(false);
    expect(
      isIntegrationOperationItem(
        { ...item, projectGlobalId: "22222222-2222-4222-8222-222222222222" },
        projectId,
      ),
    ).toBe(false);
    expect(
      isIntegrationOperationItem(
        {
          ...item,
          replayEligible: true,
          replayEligibilityReason: "state_not_retryable",
        },
        projectId,
      ),
    ).toBe(false);
    expect(
      isIntegrationOperationDetail(
        { ...integrationOperationDetail(item), secret: "not allowed" },
        projectId,
        item.operationKind,
        item.operationGlobalId,
      ),
    ).toBe(false);
  });

  it("fails before transport for caller-selected or unsafe action authority", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveIntegrationOperationsDataSource(http);
    const signal = new AbortController().signal;
    const final = integrationOperationItem("failed_final", 5);

    await expect(
      source.requestAction(projectId, final, "replay", {
        csrfToken: "c".repeat(32),
        idempotencyKey: "p807-replay-fixed-0002",
        signal,
      }),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.requestAction(
        projectId,
        integrationOperationItem("failed_retryable", 4),
        "request_reconciliation",
        {
          csrfToken: "c".repeat(32),
          idempotencyKey: "p807-reconcile-fixed-0001",
          signal,
        },
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.loadOperations("not-a-project", {}, signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
