import { afterEach, describe, expect, it, vi } from "vitest";

import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  ITEM_PUBLISH_ACKNOWLEDGEMENT,
  isItemPublishRequest,
  isItemPublishRequestDetail,
  isItemPublishRequestList,
  LiveItemPublishDataSource,
  type CreateItemPublishRequestCommand,
} from "../../src/api/item-publish-data-source";
import { ebomProjectId } from "../support/ebom-fixture";
import {
  itemPublishDetailFixture,
  itemPublishListFixture,
  itemPublishRequestId,
  itemPublishSiblingNodeId,
} from "../support/item-publish-fixture";
import {
  publishNodeId,
  publishRequestId,
} from "../support/publish-request-fixture";

function context(signal = new AbortController().signal) {
  return {
    csrfToken: "csrf-item-publish-fixture",
    idempotencyKey: "fixture-key",
    signal,
  };
}

function command(): CreateItemPublishRequestCommand {
  return {
    publishRequestGlobalId: publishRequestId,
    selectedPublishNodeGlobalId: publishNodeId,
    expectedMappingVersion: 0,
    acknowledgement: ITEM_PUBLISH_ACKNOWLEDGEMENT,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Item publish response validation", () => {
  it("accepts exact Mock, synthetic and authoritative detail truth", () => {
    const synthetic = itemPublishDetailFixture();
    const mock = itemPublishDetailFixture({ targetMode: "mock" });
    const authoritative = itemPublishDetailFixture({
      authoritativeMapping: true,
      state: "succeeded",
      targetMode: "sandbox",
    });
    expect(isItemPublishRequest(synthetic.request)).toBe(true);
    expect(isItemPublishRequestDetail(synthetic)).toBe(true);
    expect(isItemPublishRequestDetail(mock)).toBe(true);
    expect(isItemPublishRequestDetail(authoritative)).toBe(true);
    expect(isItemPublishRequestList(itemPublishListFixture(synthetic))).toBe(
      true,
    );
  });

  it("keeps mapping-conflict request truth separate from authoritative result truth", () => {
    const conflict = itemPublishDetailFixture({ state: "mapping_conflict" });
    expect(conflict.request.state).toBe("mapping_conflict");
    expect(conflict.result?.state).toBe("succeeded");
    expect(conflict.result?.authority).toBe("authoritative_sandbox");
    expect(conflict.result?.responseAuthenticated).toBe(true);
    expect(conflict.currentMapping?.head.mappingVersion).toBe(1);
    expect(conflict.currentMapping?.observation.resultGlobalId).not.toBe(
      conflict.result?.globalId,
    );
    expect(isItemPublishRequestDetail(conflict)).toBe(true);
    if (!conflict.result)
      throw new Error("The conflict fixture requires a result.");
    expect(
      isItemPublishRequestDetail({
        ...conflict,
        result: { ...conflict.result, state: "synthetic_verified" },
      }),
    ).toBe(false);
  });

  it.each([
    "validated_mock",
    "queued",
    "processing",
    "synthetic_verified",
    "succeeded",
    "failed_retryable",
    "failed_final",
    "uncertain_after_timeout",
    "mapping_conflict",
  ] as const)("accepts the closed %s state matrix", (state) => {
    const detail = itemPublishDetailFixture({ state });
    expect(isItemPublishRequestDetail(detail)).toBe(true);
  });

  it.each([
    ["validated_mock", "mock"],
    ["queued", "synthetic"],
    ["processing", "synthetic"],
    ["synthetic_verified", "synthetic"],
    ["failed_retryable", "sandbox"],
    ["failed_final", "sandbox"],
    ["uncertain_after_timeout", "synthetic"],
    ["uncertain_after_timeout", "sandbox"],
    ["mapping_conflict", "sandbox"],
  ] as const)(
    "accepts a validated current mapping for %s/%s",
    (state, targetMode) => {
      const detail = itemPublishDetailFixture({
        state,
        targetMode,
        mapped: true,
      });
      expect(detail.currentMapping).not.toBeNull();
      expect(isItemPublishRequestDetail(detail)).toBe(true);
    },
  );

  it("accepts a mapped Mock update expectation without dispatch evidence", () => {
    const detail = itemPublishDetailFixture({
      state: "validated_mock",
      targetMode: "mock",
      mapped: true,
    });
    expect(detail.request.intent).toBe("update_item_engineering_fields");
    expect(detail.request.mappingExpectation.mappingVersion).toBeGreaterThan(0);
    expect(detail.request.dispatchAllowed).toBe(false);
    expect(detail.attempts).toHaveLength(0);
    expect(detail.result).toBeNull();
    expect(isItemPublishRequestDetail(detail)).toBe(true);
  });

  it("keeps prior and later current mapping evidence separate from a queued request", () => {
    const prior = itemPublishDetailFixture({
      state: "queued",
      targetMode: "synthetic",
      mappingOrigin: "prior",
    });
    const later = itemPublishDetailFixture({
      state: "queued",
      targetMode: "synthetic",
      mappingOrigin: "later",
    });
    expect(prior.currentMapping?.observation.requestGlobalId).not.toBe(
      prior.request.globalId,
    );
    expect(later.currentMapping?.observation.requestGlobalId).not.toBe(
      later.request.globalId,
    );
    expect(prior.currentMapping?.head.formalItemCode).toBe("ITEM-SANDBOX-0001");
    expect(later.currentMapping?.head.formalItemCode).toBe("ITEM-SANDBOX-0002");
    expect(isItemPublishRequestDetail(prior)).toBe(true);
    expect(isItemPublishRequestDetail(later)).toBe(true);
  });

  it("matches a selected sibling through occurrences rather than the selected occurrence field", () => {
    const detail = itemPublishDetailFixture();
    const list = itemPublishListFixture(detail);
    const siblingList = {
      ...list,
      sourceFilters: {
        ...list.sourceFilters,
        selectedPublishNodeGlobalId: itemPublishSiblingNodeId,
      },
    };
    expect(isItemPublishRequestList(siblingList)).toBe(true);
  });

  it("requires a server mapping expectation for exact-source list responses", () => {
    const list = itemPublishListFixture(null);
    expect(list.mappingExpectation?.mappingVersion).toBe(0);
    expect(isItemPublishRequestList(list)).toBe(true);
    expect(
      isItemPublishRequestList({ ...list, mappingExpectation: null }),
    ).toBe(false);
  });

  it.each([
    [
      "a synthetic formal Item identity",
      () => {
        const detail = itemPublishDetailFixture();
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: { ...detail.result, formalItemCode: "ITEM-FAKE" },
        };
      },
    ],
    [
      "a detached attempt",
      () => {
        const detail = itemPublishDetailFixture();
        const attempt = detail.attempts[0];
        if (!attempt) throw new Error("The fixture requires an attempt.");
        return {
          ...detail,
          attempts: [
            {
              ...attempt,
              requestGlobalId: "76000000-0000-4000-8000-000000000099",
            },
          ],
        };
      },
    ],
    [
      "a Mock outbox",
      () => {
        const detail = itemPublishDetailFixture({ targetMode: "mock" });
        return {
          ...detail,
          request: {
            ...detail.request,
            outboxEventId: "76000000-0000-4000-8000-000000000004",
          },
        };
      },
    ],
    [
      "a fake succeeded result",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: {
            ...detail.result,
            authority: "none" as const,
            responseAuthenticated: false,
          },
        };
      },
    ],
    [
      "a profile and state mismatch",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        return {
          ...detail,
          request: {
            ...detail.request,
            profile: {
              ...detail.request.profile,
              targetMode: "synthetic" as const,
            },
          },
        };
      },
    ],
    [
      "a queued attempt",
      () => {
        const detail = itemPublishDetailFixture({ state: "queued" });
        const processing = itemPublishDetailFixture({ state: "processing" });
        return { ...detail, attempts: processing.attempts };
      },
    ],
    [
      "a terminal processing attempt",
      () => {
        const detail = itemPublishDetailFixture({ state: "processing" });
        const attempt = detail.attempts[0];
        if (!attempt) throw new Error("The fixture requires an attempt.");
        return {
          ...detail,
          attempts: [{ ...attempt, finishedAt: "2026-08-16T08:00:02Z" }],
        };
      },
    ],
    [
      "a terminal response without a result",
      () => {
        const detail = itemPublishDetailFixture({
          state: "failed_final",
        });
        return {
          ...detail,
          request: { ...detail.request, resultGlobalId: null },
          result: null,
        };
      },
    ],
    [
      "a result bound to a non-last attempt",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        const attempt = detail.attempts[0];
        if (!attempt) throw new Error("The fixture requires an attempt.");
        return {
          ...detail,
          attempts: [{ ...attempt, attemptNumber: 2 }],
        };
      },
    ],
    [
      "attempt outbox binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        const attempt = detail.attempts[0];
        if (!attempt) throw new Error("The fixture requires an attempt.");
        return {
          ...detail,
          attempts: [
            {
              ...attempt,
              outboxEventId: "76000000-0000-4000-8000-000000000099",
            },
          ],
        };
      },
    ],
    [
      "attempt source binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        const attempt = detail.attempts[0];
        if (!attempt) throw new Error("The fixture requires an attempt.");
        return {
          ...detail,
          attempts: [{ ...attempt, sourceHash: "e".repeat(64) }],
        };
      },
    ],
    [
      "attempt target binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        const attempt = detail.attempts[0];
        if (!attempt) throw new Error("The fixture requires an attempt.");
        return {
          ...detail,
          attempts: [{ ...attempt, targetIdempotencyKeyHash: "e".repeat(64) }],
        };
      },
    ],
    [
      "attempt profile binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        const attempt = detail.attempts[0];
        if (!attempt) throw new Error("The fixture requires an attempt.");
        return {
          ...detail,
          attempts: [{ ...attempt, profileVersion: 2 }],
        };
      },
    ],
    [
      "result request binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: {
            ...detail.result,
            requestGlobalId: "76000000-0000-4000-8000-000000000099",
          },
        };
      },
    ],
    [
      "result outbox binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: {
            ...detail.result,
            outboxEventId: "76000000-0000-4000-8000-000000000099",
          },
        };
      },
    ],
    [
      "result source binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: { ...detail.result, sourceHash: "e".repeat(64) },
        };
      },
    ],
    [
      "result idempotency binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: {
            ...detail.result,
            idempotencyKeyHash: "e".repeat(64),
          },
        };
      },
    ],
    [
      "result response binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: { ...detail.result, responseHash: "e".repeat(64) },
        };
      },
    ],
    [
      "result fault binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: { ...detail.result, faultKind: "target_unavailable" },
        };
      },
    ],
    [
      "result target binding drift",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.result) throw new Error("The fixture requires a result.");
        return {
          ...detail,
          result: {
            ...detail.result,
            expectedTargetVersion: "8",
          },
        };
      },
    ],
    [
      "an invalid mapping head binding",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.currentMapping)
          throw new Error("The fixture requires a head.");
        return {
          ...detail,
          currentMapping: {
            ...detail.currentMapping,
            head: {
              ...detail.currentMapping.head,
              currentObservationHash: "e".repeat(64),
            },
          },
        };
      },
    ],
    [
      "an invalid mapping head identity binding",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.currentMapping)
          throw new Error("The fixture requires a head.");
        return {
          ...detail,
          currentMapping: {
            ...detail.currentMapping,
            head: {
              ...detail.currentMapping.head,
              currentObservationGlobalId:
                "76000000-0000-4000-8000-000000000099",
            },
          },
        };
      },
    ],
    [
      "an invalid mapping observation binding",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.currentMapping)
          throw new Error("The fixture requires an observation.");
        return {
          ...detail,
          currentMapping: {
            ...detail.currentMapping,
            observation: {
              ...detail.currentMapping.observation,
              sourceStreamKeyHash: "e".repeat(64),
            },
          },
        };
      },
    ],
    [
      "an invalid mapping provenance binding",
      () => {
        const detail = itemPublishDetailFixture({ state: "succeeded" });
        if (!detail.currentMapping)
          throw new Error("The fixture requires an observation.");
        return {
          ...detail,
          currentMapping: {
            ...detail.currentMapping,
            observation: {
              ...detail.currentMapping.observation,
              resultGlobalId: "76000000-0000-4000-8000-000000000099",
            },
          },
        };
      },
    ],
    [
      "a mapping conflict pointing to its observed result",
      () => {
        const detail = itemPublishDetailFixture({ state: "mapping_conflict" });
        if (!detail.currentMapping || !detail.result)
          throw new Error("The fixture requires conflict evidence.");
        return {
          ...detail,
          currentMapping: {
            ...detail.currentMapping,
            observation: {
              ...detail.currentMapping.observation,
              resultGlobalId: detail.result.globalId,
            },
          },
        };
      },
    ],
    [
      "a selected observation without its selected result",
      () => {
        const detail = itemPublishDetailFixture({
          state: "queued",
          targetMode: "sandbox",
          mapped: true,
        });
        if (!detail.currentMapping)
          throw new Error("The fixture requires an observation.");
        return {
          ...detail,
          currentMapping: {
            ...detail.currentMapping,
            observation: {
              ...detail.currentMapping.observation,
              requestGlobalId: detail.request.globalId,
            },
          },
        };
      },
    ],
    [
      "a synthetic current mapping authority",
      () => {
        const detail = itemPublishDetailFixture({
          state: "queued",
          targetMode: "synthetic",
          mapped: true,
        });
        if (!detail.currentMapping)
          throw new Error("The fixture requires an observation.");
        return {
          ...detail,
          currentMapping: {
            ...detail.currentMapping,
            observation: {
              ...detail.currentMapping.observation,
              authority: "synthetic" as const,
            },
          },
        };
      },
    ],
  ])("rejects %s", (_name, build) => {
    expect(isItemPublishRequestDetail(build())).toBe(false);
  });

  it("rejects list results outside the exact Project and Phase 5 node", () => {
    const list = itemPublishListFixture();
    const request = list.items[0];
    if (!request) throw new Error("The fixture requires a request.");
    expect(
      isItemPublishRequestList({
        ...list,
        items: [
          {
            ...request,
            source: {
              ...request.source,
              selectedPublishNodeGlobalId:
                "76000000-0000-4000-8000-000000000099",
            },
          },
        ],
      }),
    ).toBe(false);
  });
});

describe("Live Item publish data source", () => {
  it("loads exact Project/source list and detail routes", async () => {
    const list = itemPublishListFixture();
    const detail = itemPublishDetailFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(list)
      .mockResolvedValueOnce(detail);
    const source = new LiveItemPublishDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadRequests(
        ebomProjectId,
        publishRequestId,
        publishNodeId,
        signal,
      ),
    ).resolves.toEqual(list);
    await expect(
      source.loadRequest(ebomProjectId, itemPublishRequestId, signal),
    ).resolves.toEqual(detail);

    const base = `/projects/${ebomProjectId}/item-publish-requests`;
    expect(request.mock.calls[0]?.[0]).toBe(base);
    expect(request.mock.calls[0]?.[2]).toMatchObject({
      query: {
        publishRequestGlobalId: publishRequestId,
        selectedPublishNodeGlobalId: publishNodeId,
      },
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(request.mock.calls[1]?.[0]).toBe(`${base}/${itemPublishRequestId}`);
  });

  it("creates only the closed acknowledged command with replay protection", async () => {
    const response = itemPublishDetailFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new LiveItemPublishDataSource(http);
    const commandValue = command();
    const commandContext = context();

    await expect(
      source.createRequest(ebomProjectId, commandValue, commandContext),
    ).resolves.toEqual(response);
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(`/projects/${ebomProjectId}/item-publish-requests`);
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
      commandContext.idempotencyKey,
    );
    expect(options).toMatchObject({
      csrfToken: commandContext.csrfToken,
      requireIdempotencyReplay: true,
      requirePrivateNoStore: true,
    });
    if (typeof init?.body !== "string")
      throw new Error("The command body is unavailable.");
    expect(JSON.parse(init.body)).toEqual(commandValue);
  });

  it("rejects mutable source identities and incorrect acknowledgement before transport", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveItemPublishDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadRequests(ebomProjectId, publishRequestId, "latest", signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.createRequest(
        ebomProjectId,
        {
          ...command(),
          acknowledgement: "Execute this Item.",
        } as unknown as CreateItemPublishRequestCommand,
        context(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
