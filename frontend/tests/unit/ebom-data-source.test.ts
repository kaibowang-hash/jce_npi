import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isEngineeringBomCommandResponse,
  isEngineeringBomComparisonResponse,
  isEngineeringBomDetailResponse,
  isEngineeringBomListResponse,
  LiveEngineeringBomDataSource,
  type EngineeringBomCommandViewModel,
  type ReleaseEngineeringBomRevisionCommand,
  type ReviewEngineeringBomRevisionCommand,
} from "../../src/api/ebom-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  ebomId,
  ebomPolicyId,
  ebomProjectId,
  ebomRevisionOneId,
  ebomRevisionTwoId,
  engineeringBomCommandFixture,
  engineeringBomComparisonFixture,
  engineeringBomDetailFixture,
  engineeringBomListFixture,
} from "../support/ebom-fixture";

function commandContext(signal = new AbortController().signal) {
  return {
    csrfToken: "csrf-ebom-fixture",
    idempotencyKey: "ebom-command-fixture",
    signal,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("EBOM response validation", () => {
  it("accepts exact closed list, detail, command and comparison contracts", () => {
    expect(isEngineeringBomListResponse(engineeringBomListFixture())).toBe(
      true,
    );
    expect(isEngineeringBomDetailResponse(engineeringBomDetailFixture())).toBe(
      true,
    );
    expect(
      isEngineeringBomCommandResponse(engineeringBomCommandFixture()),
    ).toBe(true);
    expect(
      isEngineeringBomComparisonResponse(engineeringBomComparisonFixture()),
    ).toBe(true);
  });

  it.each([
    [
      "an undeclared formal MBOM field",
      () => ({ ...engineeringBomListFixture(), formalMbomId: "MBOM-001" }),
      isEngineeringBomListResponse,
    ],
    [
      "a mutable latest selector",
      () => ({ ...engineeringBomDetailFixture(), selectedRevision: "latest" }),
      isEngineeringBomDetailResponse,
    ],
    [
      "a latest pointer outside immutable history",
      () => {
        const fixture = engineeringBomDetailFixture();
        return {
          ...fixture,
          ebom: {
            ...fixture.ebom,
            latestRevision: {
              ...fixture.ebom.latestRevision,
              globalId: "75000000-0000-4000-8000-000000000099",
            },
          },
        };
      },
      isEngineeringBomDetailResponse,
    ],
    [
      "comparison counts that disagree with typed differences",
      () => ({
        ...engineeringBomComparisonFixture(),
        summary: {
          ...engineeringBomComparisonFixture().summary,
          quantity: 0,
        },
      }),
      isEngineeringBomComparisonResponse,
    ],
  ])("rejects %s", (_name, build, validate) => {
    expect(validate(build())).toBe(false);
  });

  it("rejects broken predecessor lineage and mutable line identity", () => {
    const fixture = engineeringBomDetailFixture();
    const latest = fixture.revisions[0];
    if (!latest)
      throw new Error("The EBOM fixture requires a latest revision.");
    expect(
      isEngineeringBomDetailResponse({
        ...fixture,
        revisions: [
          {
            ...latest,
            predecessorSnapshotHash: "9".repeat(64),
          },
          ...fixture.revisions.slice(1),
        ],
      }),
    ).toBe(false);
    expect(
      isEngineeringBomDetailResponse({
        ...fixture,
        revisions: [
          {
            ...latest,
            lines: [latest.lines[0], latest.lines[0]],
          },
          ...fixture.revisions.slice(1),
        ],
      }),
    ).toBe(false);
  });
});

describe("Live EBOM data source", () => {
  it("loads only Project-scoped exact list and detail paths", async () => {
    const list = engineeringBomListFixture();
    const detail = engineeringBomDetailFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(list)
      .mockResolvedValueOnce(detail);
    const source = new LiveEngineeringBomDataSource(http);
    const signal = new AbortController().signal;

    await expect(source.loadEboms(ebomProjectId, signal)).resolves.toEqual(
      list,
    );
    await expect(
      source.loadEbom(ebomProjectId, ebomId, signal),
    ).resolves.toEqual(detail);
    expect(request.mock.calls[0]?.[0]).toBe(`/projects/${ebomProjectId}/eboms`);
    expect(request.mock.calls[1]?.[0]).toBe(
      `/projects/${ebomProjectId}/eboms/${ebomId}`,
    );
    expect(request.mock.calls[0]?.[2]?.requirePrivateNoStore).toBe(true);
    expect(request.mock.calls[0]?.[2]?.requireTraceId).toBe(true);
  });

  it("creates an immutable successor with exact predecessor and policy truth", async () => {
    const response = engineeringBomCommandFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new LiveEngineeringBomDataSource(http);
    const context = commandContext();
    const predecessor = engineeringBomDetailFixture().revisions[1];
    if (!predecessor)
      throw new Error("The predecessor fixture is unavailable.");

    const command = {
      expectedEbomVersion: 1,
      predecessorRevisionId: predecessor.globalId,
      expectedPredecessorSnapshotHash: predecessor.snapshotHash,
      policyGlobalId: ebomPolicyId,
      policyVersion: 1,
      policySnapshotHash: "a".repeat(64),
      reason: "  Exact successor  ",
      effectivityNote: "  Synthetic only  ",
      lines: response.revision.lines.map((line) => ({
        lineKey: line.lineKey,
        parentLineKey: line.parentLineKey,
        engineeringItemId: line.engineeringItemId,
        description: line.description,
        quantity: line.quantity,
        engineeringUom: line.engineeringUom,
        alternateForLineKey: line.alternateForLineKey,
        alternateGroupKey: line.alternateGroupKey,
        effectivityStart: line.effectivityStart,
        effectivityEnd: line.effectivityEnd,
        attributes: line.attributes,
      })),
      formalMbomId: "MBOM-MUST-NOT-LEAK",
    };
    await expect(
      source.createRevision(ebomProjectId, ebomId, command, context),
    ).resolves.toEqual(response);

    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(`/projects/${ebomProjectId}/eboms/${ebomId}/revisions`);
    const body = init?.body;
    if (typeof body !== "string")
      throw new Error("The EBOM body was not JSON.");
    const parsedBody = JSON.parse(body) as Record<string, unknown>;
    expect(parsedBody).toMatchObject({
      expectedEbomVersion: 1,
      predecessorRevisionId: ebomRevisionOneId,
      reason: "Exact successor",
      effectivityNote: "Synthetic only",
    });
    expect(parsedBody).not.toHaveProperty("formalMbomId");
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
      context.idempotencyKey,
    );
    expect(options?.csrfToken).toBe(context.csrfToken);
    expect(options?.requireIdempotencyReplay).toBe(true);
  });

  it("submits review with exact lifecycle concurrency and actor-bound command headers", async () => {
    const base = engineeringBomCommandFixture();
    const response: EngineeringBomCommandViewModel = {
      ...base,
      revision: {
        ...base.revision,
        lifecycle: {
          state: "in_review",
          version: 2,
          lastEventId: "75000000-0000-4000-8000-000000000011",
        },
        events: [
          {
            globalId: "75000000-0000-4000-8000-000000000011",
            eventType: "review_submitted",
            fromState: "draft",
            toState: "in_review",
            fromVersion: 1,
            toVersion: 2,
            actorUserId: "engineer@example.invalid",
            decision: null,
            reason: "Ready",
            confirmationIntent: null,
            occurredAt: "2026-08-05T10:00:00Z",
            eventHash: "d".repeat(64),
          },
        ],
      },
    };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new LiveEngineeringBomDataSource(http);

    await expect(
      source.submitReview(
        ebomProjectId,
        ebomId,
        ebomRevisionTwoId,
        {
          expectedEbomVersion: 2,
          expectedRevisionSnapshotHash: "c".repeat(64),
          expectedLifecycleVersion: 1,
          policyGlobalId: ebomPolicyId,
          policyVersion: 1,
          policySnapshotHash: "a".repeat(64),
          reason: "Ready",
        },
        commandContext(),
      ),
    ).resolves.toEqual(response);
    expect(request.mock.calls[0]?.[0]).toBe(
      `/projects/${ebomProjectId}/eboms/${ebomId}/revisions/${ebomRevisionTwoId}:submit-review`,
    );
  });

  it("compares two explicit revisions and rejects identical or invalid identities before fetch", async () => {
    const comparison = engineeringBomComparisonFixture();
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request").mockResolvedValue(comparison);
    const source = new LiveEngineeringBomDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.compare(
        ebomProjectId,
        ebomId,
        ebomRevisionOneId,
        ebomRevisionTwoId,
        signal,
      ),
    ).resolves.toEqual(comparison);
    expect(request.mock.calls[0]?.[0]).toBe(
      `/projects/${ebomProjectId}/eboms/${ebomId}/compare`,
    );
    expect(request.mock.calls[0]?.[2]?.query).toEqual({
      fromRevisionId: ebomRevisionOneId,
      toRevisionId: ebomRevisionTwoId,
    });

    await expect(
      source.compare(
        ebomProjectId,
        ebomId,
        ebomRevisionOneId,
        ebomRevisionOneId,
        signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.loadEbom(ebomProjectId, "latest", signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).toHaveBeenCalledOnce();
  });

  it("rejects undeclared review decisions and unconfirmed release intent before transport", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveEngineeringBomDataSource(http);
    const transition = {
      expectedEbomVersion: 2,
      expectedRevisionSnapshotHash: "c".repeat(64),
      expectedLifecycleVersion: 2,
      policyGlobalId: ebomPolicyId,
      policyVersion: 1,
      policySnapshotHash: "a".repeat(64),
    };

    await expect(
      source.review(
        ebomProjectId,
        ebomId,
        ebomRevisionTwoId,
        {
          ...transition,
          decision: "ship",
          reason: null,
        } as unknown as ReviewEngineeringBomRevisionCommand,
        commandContext(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.release(
        ebomProjectId,
        ebomId,
        ebomRevisionTwoId,
        {
          ...transition,
          confirmed: false,
          confirmationIntent: "release_exact_ebom_revision",
        } as unknown as ReleaseEngineeringBomRevisionCommand,
        commandContext(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
