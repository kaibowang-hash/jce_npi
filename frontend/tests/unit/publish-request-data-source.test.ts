import { afterEach, describe, expect, it, vi } from "vitest";

import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  isEngineeringBomPublishRequestListResponse,
  isEngineeringBomPublishRequestResponse,
  LiveEngineeringBomPublishRequestDataSource,
  type CreateEngineeringBomPublishRequestCommand,
} from "../../src/api/publish-request-data-source";
import {
  ebomId,
  ebomProjectId,
  ebomRevisionOneId,
} from "../support/ebom-fixture";
import {
  publishPolicyId,
  publishRequestFixture,
  publishRequestId,
  publishRequestListFixture,
} from "../support/publish-request-fixture";

const hashB = "b".repeat(64);
const hashD = "d".repeat(64);

function context(signal = new AbortController().signal) {
  return {
    csrfToken: "csrf-publish-request-fixture",
    idempotencyKey: "publish-request-fixture-0001",
    signal,
  };
}

function command(): CreateEngineeringBomPublishRequestCommand {
  return {
    expectedEbomVersion: 2,
    expectedRevisionSnapshotHash: hashB,
    expectedLifecycleVersion: 4,
    publishPolicyGlobalId: publishPolicyId,
    publishPolicyVersion: 1,
    publishPolicySnapshotHash: hashD,
    targetMode: "mock",
    confirmed: true,
    confirmationIntent: "validate_exact_released_ebom_for_item_mbom_publish",
    reason: "  Validate exact released EBOM  ",
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("publish-request response validation", () => {
  it("accepts only the exact closed list and detail truth", () => {
    expect(
      isEngineeringBomPublishRequestResponse(publishRequestFixture()),
    ).toBe(true);
    expect(
      isEngineeringBomPublishRequestListResponse(publishRequestListFixture()),
    ).toBe(true);
  });

  it.each([
    [
      "a formal target identifier",
      () => {
        const request = publishRequestFixture();
        const node = request.nodes[0];
        if (!node) throw new Error("The fixture requires one node.");
        return {
          ...request,
          nodes: [
            {
              ...node,
              mapping: { ...node.mapping, formalItemCode: "ITEM-001" },
            },
          ],
        };
      },
    ],
    [
      "Phase 5 dispatch permission",
      () => ({ ...publishRequestFixture(), dispatchAllowed: true }),
    ],
    [
      "a result detached from its node hash",
      () => {
        const request = publishRequestFixture();
        const node = request.nodes[0];
        const result = node?.results[0];
        if (!node || !result)
          throw new Error("The fixture requires node truth.");
        return {
          ...request,
          nodes: [
            {
              ...node,
              results: [{ ...result, nodeInputHash: "9".repeat(64) }],
            },
          ],
        };
      },
    ],
  ])("rejects %s", (_name, build) => {
    expect(isEngineeringBomPublishRequestResponse(build())).toBe(false);
  });

  it("rejects a list whose request belongs to another exact revision", () => {
    const list = publishRequestListFixture();
    const request = list.items[0];
    if (!request) throw new Error("The fixture requires a request.");
    expect(
      isEngineeringBomPublishRequestListResponse({
        ...list,
        items: [
          {
            ...request,
            releasedEbom: {
              ...request.releasedEbom,
              revisionGlobalId: "75000000-0000-4000-8000-000000000099",
            },
          },
        ],
      }),
    ).toBe(false);
  });
});

describe("Live publish-request data source", () => {
  it("loads exact Project/EBOM/revision list and detail routes", async () => {
    const list = publishRequestListFixture();
    const detail = publishRequestFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(list)
      .mockResolvedValueOnce(detail);
    const source = new LiveEngineeringBomPublishRequestDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadRequests(ebomProjectId, ebomId, ebomRevisionOneId, signal),
    ).resolves.toEqual(list);
    await expect(
      source.loadRequest(
        ebomProjectId,
        ebomId,
        ebomRevisionOneId,
        publishRequestId,
        signal,
      ),
    ).resolves.toEqual(detail);
    const base = `/projects/${ebomProjectId}/eboms/${ebomId}/revisions/${ebomRevisionOneId}/publish-requests`;
    expect(request.mock.calls[0]?.[0]).toBe(base);
    expect(request.mock.calls[1]?.[0]).toBe(`${base}/${publishRequestId}`);
    expect(request.mock.calls[0]?.[2]).toMatchObject({
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
  });

  it("creates only the closed confirmed Mock command with replay headers", async () => {
    const response = publishRequestFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new LiveEngineeringBomPublishRequestDataSource(http);
    const commandValue = command();
    const commandContext = context();

    await expect(
      source.createRequest(
        ebomProjectId,
        ebomId,
        ebomRevisionOneId,
        commandValue,
        commandContext,
      ),
    ).resolves.toEqual(response);

    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toContain(`/revisions/${ebomRevisionOneId}/publish-requests`);
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
    expect(JSON.parse(init.body)).toEqual({
      ...commandValue,
      reason: "Validate exact released EBOM",
    });
  });

  it("rejects production mode, missing confirmation and mutable latest identities before transport", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveEngineeringBomPublishRequestDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.createRequest(
        ebomProjectId,
        ebomId,
        ebomRevisionOneId,
        {
          ...command(),
          targetMode: "production",
        } as unknown as CreateEngineeringBomPublishRequestCommand,
        context(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.createRequest(
        ebomProjectId,
        ebomId,
        ebomRevisionOneId,
        {
          ...command(),
          confirmed: false,
        } as unknown as CreateEngineeringBomPublishRequestCommand,
        context(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.loadRequests(ebomProjectId, ebomId, "latest", signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
