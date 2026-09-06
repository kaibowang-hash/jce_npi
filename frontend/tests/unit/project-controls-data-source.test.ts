import { describe, expect, it, vi } from "vitest";

import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  isProjectActivityItemResponse,
  isProjectActivityPageResponse,
  isProjectControlsResponse,
  isProjectFollowStateResponse,
  isProjectLearningPageResponse,
  isProjectLearningResponse,
  LiveProjectControlsDataSource,
  mergeProjectActivityPages,
} from "../../src/api/project-controls-data-source";
import {
  projectActivityFixture,
  projectControlIds,
  projectControlsFixture,
  projectLearningFixture,
} from "../support/project-controls-fixture";

const commandContext = {
  csrfToken: "csrf-token-for-project-controls-1234567890",
  idempotencyKey: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  signal: new AbortController().signal,
};

function record(value: unknown): Record<string, unknown> {
  return structuredClone(value) as Record<string, unknown>;
}

function parseRequestBody(body: BodyInit | null | undefined): unknown {
  if (typeof body !== "string") {
    throw new Error("Expected a JSON string request body.");
  }
  return JSON.parse(body) as unknown;
}

describe("live Project controls data source", () => {
  it("accepts only the closed controls, activity, follow, and learning shapes", () => {
    expect(isProjectControlsResponse(projectControlsFixture())).toBe(true);
    expect(isProjectActivityPageResponse(projectActivityFixture())).toBe(true);
    expect(
      isProjectActivityItemResponse(
        projectActivityFixture().items[0],
        projectControlIds.project,
      ),
    ).toBe(true);
    expect(isProjectLearningPageResponse(projectLearningFixture())).toBe(true);
    expect(
      isProjectLearningResponse(
        projectLearningFixture().items[0],
        projectControlIds.project,
      ),
    ).toBe(true);
    expect(
      isProjectFollowStateResponse({
        projectId: projectControlIds.project,
        following: false,
        version: 3,
        changedAt: "2026-07-25T13:00:00Z",
      }),
    ).toBe(true);

    const orphanedAuthority = record(projectControlsFixture());
    const lifecycleActions = orphanedAuthority.lifecycleActions as Record<
      string,
      unknown
    >[];
    if (!lifecycleActions[0]) {
      throw new Error("Missing lifecycle action fixture.");
    }
    lifecycleActions[0].authoritySlot = "unbound_authority";
    expect(isProjectControlsResponse(orphanedAuthority)).toBe(false);
  });

  it("accepts Frappe singleton actors and rejects whitespace or control characters", () => {
    const administratorActivity = record(projectActivityFixture());
    const administratorEvent = (
      administratorActivity.items as Record<string, unknown>[]
    )[0];
    if (!administratorEvent) throw new Error("Missing activity event fixture.");
    administratorEvent.actorUserId = "Administrator";
    expect(isProjectActivityPageResponse(administratorActivity)).toBe(true);

    const administratorLearning = record(projectLearningFixture());
    const administratorRecord = (
      administratorLearning.items as Record<string, unknown>[]
    )[0];
    if (!administratorRecord) throw new Error("Missing learning fixture.");
    administratorRecord.createdBy = "Administrator";
    expect(isProjectLearningPageResponse(administratorLearning)).toBe(true);

    for (const invalidUserId of ["bad actor", "bad\u0000actor"]) {
      const invalidActivity = record(administratorActivity);
      const invalidEvent = (
        invalidActivity.items as Record<string, unknown>[]
      )[0];
      if (!invalidEvent) throw new Error("Missing activity event fixture.");
      invalidEvent.actorUserId = invalidUserId;
      expect(isProjectActivityPageResponse(invalidActivity)).toBe(false);

      const invalidLearning = record(administratorLearning);
      const invalidRecord = (
        invalidLearning.items as Record<string, unknown>[]
      )[0];
      if (!invalidRecord) throw new Error("Missing learning fixture.");
      invalidRecord.createdBy = invalidUserId;
      expect(isProjectLearningPageResponse(invalidLearning)).toBe(false);
    }
  });

  it("requires an explicit boolean truncation marker for comment choices", () => {
    const missing = record(projectActivityFixture());
    const missingOptions = missing.commentOptions as Record<string, unknown>;
    delete missingOptions.truncated;
    expect(isProjectActivityPageResponse(missing)).toBe(false);

    const invalid = record(projectActivityFixture());
    const invalidOptions = invalid.commentOptions as Record<string, unknown>;
    invalidOptions.truncated = "yes";
    expect(isProjectActivityPageResponse(invalid)).toBe(false);

    const truncated = record(projectActivityFixture());
    const truncatedOptions = truncated.commentOptions as Record<
      string,
      unknown
    >;
    truncatedOptions.truncated = true;
    expect(isProjectActivityPageResponse(truncated)).toBe(true);
  });

  it("requires a bounded cursor and strict descending activity tuple order", () => {
    const base = projectActivityFixture();
    const newer = structuredClone(base.items[0]);
    if (!newer) throw new Error("Missing activity item fixture.");
    newer.globalId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
    newer.occurredAt = base.items[0]?.occurredAt ?? "";

    const ordered = record(base);
    ordered.items = [newer, structuredClone(base.items[0])];
    ordered.nextCursor = "opaque.activity.cursor";
    expect(isProjectActivityPageResponse(ordered)).toBe(true);

    const reversed = structuredClone(ordered);
    reversed.items = [...(reversed.items as unknown[])].reverse();
    expect(isProjectActivityPageResponse(reversed)).toBe(false);

    const repeated = structuredClone(ordered);
    repeated.items = [newer, structuredClone(newer)];
    expect(isProjectActivityPageResponse(repeated)).toBe(false);

    const invalidCursor = structuredClone(ordered);
    invalidCursor.nextCursor = "cursor with spaces";
    expect(isProjectActivityPageResponse(invalidCursor)).toBe(false);

    const emptyContinuation = structuredClone(ordered);
    emptyContinuation.items = [];
    expect(isProjectActivityPageResponse(emptyContinuation)).toBe(false);
  });

  it("merges continuation pages immutably with deduplication and tuple ordering", () => {
    const first = projectActivityFixture();
    const duplicate = structuredClone(first.items[0]);
    if (!duplicate) throw new Error("Missing activity item fixture.");
    const older = {
      ...structuredClone(duplicate),
      globalId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      occurredAt: "2026-07-25T10:00:00.123456Z",
    };
    const continuation = {
      ...projectActivityFixture(),
      items: [duplicate, older],
      nextCursor: null,
    };
    const merged = mergeProjectActivityPages(first, continuation);
    expect(merged?.items.map((item) => item.globalId)).toEqual([
      projectControlIds.comment,
      older.globalId,
    ]);
    expect(merged?.nextCursor).toBeNull();
    expect(first.items).toHaveLength(1);

    const conflicting = structuredClone(continuation);
    const conflictingDuplicate = conflicting.items[0];
    if (!conflictingDuplicate) throw new Error("Missing duplicate fixture.");
    conflictingDuplicate.actorUserId = "other@example.invalid";
    expect(mergeProjectActivityPages(first, conflicting)).toBeNull();

    expect(
      mergeProjectActivityPages(first, {
        ...continuation,
        projectId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      }),
    ).toBeNull();
  });

  it("requires exact collaboration and learning command permissions", () => {
    const activity = record(projectActivityFixture());
    const activityPermissions = activity.permissions as Record<string, unknown>;
    activityPermissions.canComment = "yes";
    expect(isProjectActivityPageResponse(activity)).toBe(false);

    const learning = record(projectLearningFixture());
    const learningPermissions = learning.permissions as Record<string, unknown>;
    learningPermissions.canCreate = false;
    expect(isProjectLearningPageResponse(learning)).toBe(true);
    learningPermissions.extra = true;
    expect(isProjectLearningPageResponse(learning)).toBe(false);
  });

  it("rejects extra keys, unsafe targets, incomplete dimensions, and red without recovery evidence", () => {
    const extra = record(projectControlsFixture());
    extra.rawUrl = "/desk";
    expect(isProjectControlsResponse(extra)).toBe(false);

    const incomplete = record(projectControlsFixture());
    const health = incomplete.health as Record<string, unknown>;
    health.dimensions = (
      health.dimensions as readonly Record<string, unknown>[]
    ).slice(0, 3);
    expect(isProjectControlsResponse(incomplete)).toBe(false);

    const red = record(projectControlsFixture());
    const redHealth = red.health as Record<string, unknown>;
    redHealth.overallStatus = "red";
    expect(isProjectControlsResponse(red)).toBe(false);

    const activity = record(projectActivityFixture());
    const item = (activity.items as Record<string, unknown>[])[0];
    const detail = item?.detail as Record<string, unknown>;
    const link = (detail.objectLinks as Record<string, unknown>[])[0];
    if (!link) throw new Error("Missing object link fixture.");
    link.target = { kind: "url", path: "/admin" };
    expect(isProjectActivityPageResponse(activity)).toBe(false);
  });

  it("enforces server-resolved binding options exactly when binding is permitted", () => {
    const absent = record(projectControlsFixture());
    absent.bindingOptions = null;
    expect(isProjectControlsResponse(absent)).toBe(false);

    const duplicate = record(projectControlsFixture());
    const options = duplicate.bindingOptions as Record<string, unknown>;
    const policies = options.policies as Record<string, unknown>[];
    options.policies = [policies[0], structuredClone(policies[0])];
    expect(isProjectControlsResponse(duplicate)).toBe(false);

    const hidden = record(projectControlsFixture());
    const permissions = hidden.permissions as Record<string, unknown>;
    permissions.canBindPolicy = false;
    expect(isProjectControlsResponse(hidden)).toBe(false);
    hidden.bindingOptions = null;
    expect(isProjectControlsResponse(hidden)).toBe(true);
  });

  it("loads each private query with request and trace validation", async () => {
    const controls = projectControlsFixture();
    const activity = projectActivityFixture();
    const learning = projectLearningFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(controls)
      .mockResolvedValueOnce(activity)
      .mockResolvedValueOnce(learning);
    const source = new LiveProjectControlsDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadControls(projectControlIds.project, signal),
    ).resolves.toEqual(controls);
    await expect(
      source.loadActivity(projectControlIds.project, signal, 25),
    ).resolves.toEqual(activity);
    await expect(
      source.loadLearning(
        projectControlIds.project,
        {
          kind: "retrospective",
          search: "runner",
          limit: 20,
        },
        signal,
      ),
    ).resolves.toEqual(learning);

    expect(request.mock.calls.map(([path]) => path)).toEqual([
      `/projects/${projectControlIds.project}/controls`,
      `/projects/${projectControlIds.project}/activity`,
      `/projects/${projectControlIds.project}/learning`,
    ]);
    expect(request.mock.calls[1]?.[2]).toMatchObject({
      query: { limit: "25" },
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(request.mock.calls[2]?.[2]?.query).toEqual({
      kind: "retrospective",
      limit: "20",
      search: "runner",
    });
  });

  it("keeps exact learning identity mutually exclusive and fail closed", async () => {
    const learning = projectLearningFixture();
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request").mockResolvedValue(learning);
    const source = new LiveProjectControlsDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadLearning(
        projectControlIds.project,
        { learningId: projectControlIds.learning, limit: 1 },
        signal,
      ),
    ).resolves.toEqual(learning);
    expect(request.mock.calls[0]?.[2]?.query).toEqual({
      learningId: projectControlIds.learning,
      limit: "1",
    });

    const validate = request.mock.calls[0]?.[2]?.validate;
    expect(validate?.(learning)).toBe(true);
    expect(validate?.({ ...learning, items: [] })).toBe(false);
    expect(
      validate?.({
        ...learning,
        items: [
          {
            ...learning.items[0],
            globalId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          },
        ],
      }),
    ).toBe(false);
    expect(
      validate?.({
        ...learning,
        items: [learning.items[0], learning.items[0]],
      }),
    ).toBe(false);

    await expect(
      source.loadLearning(
        projectControlIds.project,
        {
          kind: "retrospective",
          learningId: projectControlIds.learning,
          limit: 1,
        },
        signal,
      ),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("binds continuation cursor and rejects local or looping cursor input", async () => {
    const activity = {
      ...projectActivityFixture(),
      nextCursor: "opaque.next.cursor",
    };
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request").mockResolvedValue(activity);
    const source = new LiveProjectControlsDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadActivity(
        projectControlIds.project,
        signal,
        25,
        "opaque.current.cursor",
      ),
    ).resolves.toEqual(activity);
    expect(request.mock.calls[0]?.[2]?.query).toEqual({
      cursor: "opaque.current.cursor",
      limit: "25",
    });
    const validate = request.mock.calls[0]?.[2]?.validate;
    expect(validate?.(activity)).toBe(true);
    expect(
      validate?.({
        ...activity,
        nextCursor: "opaque.current.cursor",
      }),
    ).toBe(false);

    await expect(
      source.loadActivity(
        projectControlIds.project,
        signal,
        25,
        "cursor with spaces",
      ),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("binds only an exact server-selected policy and every selected authority slot", async () => {
    const result = projectControlsFixture();
    result.project.version = 8;
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(result as T));
    const source = new LiveProjectControlsDataSource(http);
    const option = projectControlsFixture().bindingOptions?.policies[0];
    if (!option) throw new Error("Missing binding option fixture.");

    await expect(
      source.bindPolicy(
        projectControlIds.project,
        {
          expectedProjectVersion: 7,
          policyRef: option.policyRef,
          bindings: [
            {
              slot: "project_manager",
              memberGlobalId: projectControlIds.managerMember,
            },
            {
              slot: "quality_lead",
              memberGlobalId: projectControlIds.qualityMember,
            },
          ],
        },
        commandContext,
      ),
    ).resolves.toEqual(result);

    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(
      `/projects/${projectControlIds.project}:bind-control-policy`,
    );
    expect(parseRequestBody(init?.body)).toEqual({
      expectedProjectVersion: 7,
      policyRef: option.policyRef,
      bindings: [
        {
          slot: "project_manager",
          memberGlobalId: projectControlIds.managerMember,
        },
        {
          slot: "quality_lead",
          memberGlobalId: projectControlIds.qualityMember,
        },
      ],
    });
    expect(options).toMatchObject({
      csrfToken: commandContext.csrfToken,
      requireIdempotencyReplay: true,
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
  });

  it("uses exact expected project versions for health and lifecycle commands", async () => {
    const assessed = projectControlsFixture();
    assessed.project.version = 8;
    const transitioned = projectControlsFixture();
    transitioned.project.version = 8;
    transitioned.project.state = "on_hold";
    transitioned.lifecycleActions = transitioned.lifecycleActions.map(
      (action) =>
        action.action === "pause"
          ? {
              ...action,
              available: false,
              reasonCode: "transition_not_defined" as const,
            }
          : action,
    );
    transitioned.permissions.canTransition = false;
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementationOnce(
        <T>(): Promise<T> => Promise.resolve(assessed as T),
      )
      .mockImplementationOnce(
        <T>(): Promise<T> => Promise.resolve(transitioned as T),
      );
    const source = new LiveProjectControlsDataSource(http);

    await source.assessHealth(
      projectControlIds.project,
      {
        expectedProjectVersion: 7,
        measurements: [
          {
            dimension: "quality",
            manualStatus: "green",
            numericValue: null,
          },
        ],
        reason: null,
        recoveryPlan: null,
      },
      commandContext,
    );
    await source.transition(
      projectControlIds.project,
      {
        action: "pause",
        expectedProjectVersion: 7,
        reason: "Supplier evidence is not ready.",
      },
      commandContext,
    );

    expect(request.mock.calls.map(([path]) => path)).toEqual([
      `/projects/${projectControlIds.project}:assess-health`,
      `/projects/${projectControlIds.project}:transition`,
    ]);
    expect(parseRequestBody(request.mock.calls[1]?.[1]?.body)).toEqual({
      action: "pause",
      expectedProjectVersion: 7,
      reason: "Supplier evidence is not ready.",
    });
  });

  it("posts append-only collaboration with no arbitrary navigation field", async () => {
    const activity = projectActivityFixture().items[0];
    const learning = projectLearningFixture().items[0];
    if (activity?.eventType !== "comment_added" || !learning) {
      throw new Error("Missing collaboration fixture.");
    }
    const follow = {
      projectId: projectControlIds.project,
      following: false,
      version: 3,
      changedAt: "2026-07-25T13:00:00Z",
    } as const;
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementationOnce(
        <T>(): Promise<T> => Promise.resolve(activity as T),
      )
      .mockImplementationOnce(<T>(): Promise<T> => Promise.resolve(follow as T))
      .mockImplementationOnce(
        <T>(): Promise<T> => Promise.resolve(learning as T),
      );
    const source = new LiveProjectControlsDataSource(http);

    await source.addComment(
      projectControlIds.project,
      {
        body: activity.detail.body,
        mentions: [{ memberGlobalId: projectControlIds.qualityMember }],
        attachments: [{ globalId: projectControlIds.fileRevision, version: 4 }],
        objectLinks: [
          { type: "gate", globalId: projectControlIds.gate, version: 3 },
        ],
      },
      commandContext,
    );
    await source.changeFollowing(
      projectControlIds.project,
      false,
      2,
      commandContext,
    );
    await source.createLearning(
      projectControlIds.project,
      {
        kind: learning.kind,
        title: learning.title,
        content: learning.content,
        recommendation: learning.recommendation,
        tags: learning.tags,
      },
      commandContext,
    );

    const bodies = request.mock.calls.map(([, init]) =>
      parseRequestBody(init?.body),
    );
    expect(bodies[0]).toEqual({
      body: activity.detail.body,
      mentions: [{ memberGlobalId: projectControlIds.qualityMember }],
      attachments: [{ globalId: projectControlIds.fileRevision, version: 4 }],
      objectLinks: [
        { type: "gate", globalId: projectControlIds.gate, version: 3 },
      ],
    });
    expect(JSON.stringify(bodies)).not.toContain("targetPath");
    expect(JSON.stringify(bodies)).not.toContain("url");
  });

  it("fails locally for invalid IDs, duplicate slots, and aborted command contexts", async () => {
    const source = new LiveProjectControlsDataSource();
    await expect(
      source.loadControls("../desk", new AbortController().signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.bindPolicy(
        projectControlIds.project,
        {
          expectedProjectVersion: 7,
          policyRef: {
            globalId: projectControlIds.policy,
            version: 3,
            snapshotHash: "a".repeat(64),
          },
          bindings: [
            {
              slot: "quality_lead",
              memberGlobalId: projectControlIds.qualityMember,
            },
            {
              slot: "quality_lead",
              memberGlobalId: projectControlIds.managerMember,
            },
          ],
        },
        commandContext,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    const controller = new AbortController();
    controller.abort();
    await expect(
      source.changeFollowing(projectControlIds.project, true, 0, {
        ...commandContext,
        signal: controller.signal,
      }),
    ).rejects.toBeInstanceOf(NpiTransportError);
  });
});
