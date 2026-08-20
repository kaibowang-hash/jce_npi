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
    expect(conflict.currentMapping?.mappingVersion).toBe(1);
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
