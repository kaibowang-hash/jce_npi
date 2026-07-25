import { describe, expect, it, vi } from "vitest";

import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  isDomainWorkItemPageResponse,
  isProjectWorkContextResponse,
  LiveProjectDomainWorkItemsDataSource,
  LiveProjectWorkContextDataSource,
  ProjectWorkRequestCancelledError,
} from "../../src/api/project-work-data-source";
import {
  projectDomainWorkItemsFixture,
  projectWorkContextFixture,
} from "../support/project-work-fixture";

describe("live Project work data sources", () => {
  it("loads the exact work-context BFF path with strict validation", async () => {
    const fixture = projectWorkContextFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(fixture as T));
    const source = new LiveProjectWorkContextDataSource(http);
    const controller = new AbortController();

    await expect(
      source.load(fixture.projectId, fixture.projectVersion, controller.signal),
    ).resolves.toEqual(fixture);
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(`/projects/${fixture.projectId}/work-context`);
    expect(init).toEqual({ signal: controller.signal });
    expect(options?.requireRequestIdEcho).toBe(true);
    expect(options?.requireTraceId).toBe(true);
    expect(typeof options?.validate).toBe("function");
    expect(
      options?.validate?.({
        ...fixture,
        projectVersion: fixture.projectVersion + 1,
      }),
    ).toBe(false);
  });

  it("loads a project-scoped Domain WorkItem query without putting raw query text in the BFF path", async () => {
    const fixture = projectDomainWorkItemsFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(fixture as T));
    const source = new LiveProjectDomainWorkItemsDataSource(http);
    const controller = new AbortController();
    const query = {
      stageId: "44444444-4444-4444-8444-444444444444",
      ownerUserId: "QUALITY.LEAD@EXAMPLE.INVALID",
      overdue: false,
      kind: "issue",
      cursor: "opaque-cursor_value~v1",
      limit: 25,
    } as const;

    await expect(
      source.load(
        fixture.projectId,
        fixture.projectVersion,
        query,
        controller.signal,
      ),
    ).resolves.toEqual(fixture);
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(`/projects/${fixture.projectId}/domain-work-items`);
    expect(init).toEqual({ signal: controller.signal });
    expect(options?.query).toEqual({
      stageId: query.stageId,
      ownerUserId: "quality.lead@example.invalid",
      overdue: "false",
      kind: query.kind,
      cursor: query.cursor,
      limit: "25",
    });
    expect(options?.requireRequestIdEcho).toBe(true);
    expect(options?.requireTraceId).toBe(true);
    expect(typeof options?.validate).toBe("function");
    expect(
      options?.validate?.({
        ...fixture,
        items: [fixture.items[1]],
      }),
    ).toBe(true);
    expect(
      options?.validate?.({
        ...fixture,
        projectVersion: fixture.projectVersion + 1,
      }),
    ).toBe(false);
  });

  it("loads one exact deep-link target and rejects unrelated or paginated responses", async () => {
    const fixture = projectDomainWorkItemsFixture();
    const target = fixture.items[1];
    if (!target) throw new Error("The exact-target fixture is unavailable.");
    const exactPage = {
      ...fixture,
      items: [target],
      nextCursor: null,
    };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(exactPage as T));
    const source = new LiveProjectDomainWorkItemsDataSource(http);
    const controller = new AbortController();

    await expect(
      source.load(
        fixture.projectId,
        fixture.projectVersion,
        { workItemId: target.globalId },
        controller.signal,
      ),
    ).resolves.toEqual(exactPage);
    const options = request.mock.calls[0]?.[2];
    expect(options?.query).toEqual({ workItemId: target.globalId });
    expect(
      options?.validate?.({
        ...exactPage,
        items: [fixture.items[0]],
      }),
    ).toBe(false);
    expect(
      options?.validate?.({
        ...exactPage,
        nextCursor: "unexpected-cursor",
      }),
    ).toBe(false);
    expect(
      options?.validate?.({
        ...exactPage,
        items: [],
      }),
    ).toBe(false);
  });

  it.each([
    ["invalid Project ID", "not-a-uuid", {}, "context"],
    [
      "invalid stage filter",
      projectWorkContextFixture().projectId,
      { stageId: "G1" },
      "items",
    ],
    [
      "oversized page",
      projectWorkContextFixture().projectId,
      { limit: 101 },
      "items",
    ],
    [
      "non-contract cursor characters",
      projectWorkContextFixture().projectId,
      { cursor: "opaque+cursor/value" },
      "items",
    ],
    [
      "invalid exact work item identity",
      projectWorkContextFixture().projectId,
      { workItemId: "not-a-uuid" },
      "items",
    ],
    [
      "exact work item combined with a collection filter",
      projectWorkContextFixture().projectId,
      {
        workItemId: "80000000-0000-4000-8000-000000000002",
        kind: "issue",
      },
      "items",
    ],
  ] as const)(
    "rejects %s before issuing a live request",
    async (_name, projectId, query, resource) => {
      const http = new NpiHttpClient();
      const request = vi.spyOn(http, "request");
      const controller = new AbortController();

      const result =
        resource === "context"
          ? new LiveProjectWorkContextDataSource(http).load(
              projectId,
              projectWorkContextFixture().projectVersion,
              controller.signal,
            )
          : new LiveProjectDomainWorkItemsDataSource(http).load(
              projectId,
              projectWorkContextFixture().projectVersion,
              query,
              controller.signal,
            );
      await expect(result).rejects.toBeInstanceOf(NpiTransportError);
      expect(request).not.toHaveBeenCalled();
    },
  );

  it("converts an aborted work request into a cancellation result", async () => {
    const fixture = projectWorkContextFixture();
    const http = new NpiHttpClient();
    vi.spyOn(http, "request").mockImplementation(
      <T>(_path: string, init: RequestInit = {}): Promise<T> =>
        new Promise<T>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(
              new NpiTransportError("network", "request-aborted", "request"),
            );
          });
        }),
    );
    const source = new LiveProjectWorkContextDataSource(http);
    const controller = new AbortController();
    const request = source.load(
      fixture.projectId,
      fixture.projectVersion,
      controller.signal,
    );

    controller.abort();
    await expect(request).rejects.toBeInstanceOf(
      ProjectWorkRequestCancelledError,
    );
  });

  it("rejects an invalid expected Project version before a live request", async () => {
    const fixture = projectWorkContextFixture();
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");

    await expect(
      new LiveProjectWorkContextDataSource(http).load(
        fixture.projectId,
        0,
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});

describe("Project work-context response validation", () => {
  it("accepts the exact initialized and uninitialized contracts", () => {
    const fixture = projectWorkContextFixture();
    expect(isProjectWorkContextResponse(fixture)).toBe(true);
    expect(
      isProjectWorkContextResponse({
        ...fixture,
        initialized: false,
        workPolicyRef: null,
        members: [],
        roleAssignments: [],
        substitutions: [],
        raciAssignments: [],
        wbsItems: [],
        dependencies: [],
        baselines: [],
        baselineComparison: null,
      }),
    ).toBe(true);
  });

  it.each([
    [
      "unknown response fields",
      (fixture: Record<string, unknown>) => ({ ...fixture, debug: true }),
    ],
    [
      "a malformed WBS state key",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        wbsItems: [
          {
            ...(fixture.wbsItems as readonly Record<string, unknown>[])[0],
            statusKey: "Active state",
          },
        ],
      }),
    ],
    [
      "an unregistered WBS policy label source",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        wbsItems: (fixture.wbsItems as readonly Record<string, unknown>[]).map(
          (item, index) =>
            index === 0
              ? { ...item, statusLabelSource: "Unpublished state" }
              : item,
        ),
      }),
    ],
    [
      "a cross-Project member",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        members: [
          {
            ...(fixture.members as readonly Record<string, unknown>[])[0],
            projectId: "99999999-9999-4999-8999-999999999999",
          },
          ...(fixture.members as readonly unknown[]).slice(1),
        ],
      }),
    ],
    [
      "a cyclic WBS parent graph",
      (fixture: Record<string, unknown>) => {
        const items = fixture.wbsItems as readonly Record<string, unknown>[];
        return {
          ...fixture,
          wbsItems: [
            { ...items[0], parentId: items[1]?.globalId },
            { ...items[1], parentId: items[0]?.globalId },
          ],
        };
      },
    ],
    [
      "a baseline comparison that disagrees with current dates",
      (fixture: Record<string, unknown>) => {
        const comparison = fixture.baselineComparison as Record<
          string,
          unknown
        >;
        const items = comparison.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          baselineComparison: {
            ...comparison,
            items: [
              { ...items[0], currentPlannedFinish: "2026-08-11" },
              ...items.slice(1),
            ],
          },
        };
      },
    ],
    [
      "a baseline comparison with a forged start variance",
      (fixture: Record<string, unknown>) => {
        const comparison = fixture.baselineComparison as Record<
          string,
          unknown
        >;
        const items = comparison.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          baselineComparison: {
            ...comparison,
            items: [{ ...items[0], startVarianceDays: 999 }, ...items.slice(1)],
          },
        };
      },
    ],
    [
      "a baseline comparison with a forged finish variance",
      (fixture: Record<string, unknown>) => {
        const comparison = fixture.baselineComparison as Record<
          string,
          unknown
        >;
        const items = comparison.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          baselineComparison: {
            ...comparison,
            items: [
              { ...items[0], finishVarianceDays: -999 },
              ...items.slice(1),
            ],
          },
        };
      },
    ],
    [
      "a baseline comparison captured at a future Project version",
      (fixture: Record<string, unknown>) => {
        const comparison = fixture.baselineComparison as Record<
          string,
          unknown
        >;
        const baselines = fixture.baselines as readonly Record<
          string,
          unknown
        >[];
        const futureVersion = (fixture.projectVersion as number) + 1;
        return {
          ...fixture,
          baselines: baselines.map((baseline) =>
            baseline.globalId === comparison.baselineId
              ? { ...baseline, projectVersion: futureVersion }
              : baseline,
          ),
          baselineComparison: {
            ...comparison,
            baselineProjectVersion: futureVersion,
          },
        };
      },
    ],
    [
      "a baseline with an impossible UTC calendar timestamp",
      (fixture: Record<string, unknown>) => {
        const baselines = fixture.baselines as readonly Record<
          string,
          unknown
        >[];
        return {
          ...fixture,
          baselines: baselines.map((baseline, index) =>
            index === 0
              ? { ...baseline, capturedAt: "2026-02-30T10:00:00Z" }
              : baseline,
          ),
        };
      },
    ],
    [
      "a baseline comparison that disagrees with the current critical flag",
      (fixture: Record<string, unknown>) => {
        const comparison = fixture.baselineComparison as Record<
          string,
          unknown
        >;
        const items = comparison.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          baselineComparison: {
            ...comparison,
            items: [
              { ...items[0], critical: !items[0]?.critical },
              ...items.slice(1),
            ],
          },
        };
      },
    ],
  ])("rejects %s", (_name, mutate) => {
    const fixture = projectWorkContextFixture() as unknown as Record<
      string,
      unknown
    >;
    expect(isProjectWorkContextResponse(mutate(fixture))).toBe(false);
  });

  it("accepts an arbitrary controlled WBS state with its policy label source", () => {
    const fixture = projectWorkContextFixture();
    expect(
      isProjectWorkContextResponse({
        ...fixture,
        wbsItems: fixture.wbsItems.map((item, index) =>
          index === 0
            ? {
                ...item,
                statusKey: "supplier_review",
                statusLabelSource: "Open",
              }
            : item,
        ),
      }),
    ).toBe(true);
  });

  it("accepts exactly recomputed UTC calendar variance across a leap day", () => {
    const fixture = projectWorkContextFixture();
    const comparedItem = fixture.baselineComparison?.items[0];
    expect(comparedItem).toBeDefined();
    expect(
      isProjectWorkContextResponse({
        ...fixture,
        wbsItems: fixture.wbsItems.map((item) =>
          item.globalId === comparedItem?.wbsItemId
            ? {
                ...item,
                plannedStart: "2024-03-01",
                plannedFinish: "2024-03-03",
              }
            : item,
        ),
        baselineComparison: fixture.baselineComparison
          ? {
              ...fixture.baselineComparison,
              items: fixture.baselineComparison.items.map((item) =>
                item.wbsItemId === comparedItem?.wbsItemId
                  ? {
                      ...item,
                      baselinePlannedStart: "2024-02-28",
                      baselinePlannedFinish: "2024-03-05",
                      currentPlannedStart: "2024-03-01",
                      currentPlannedFinish: "2024-03-03",
                      startVarianceDays: 2,
                      finishVarianceDays: -2,
                    }
                  : item,
              ),
            }
          : null,
      }),
    ).toBe(true);
  });
});

describe("Domain WorkItem page response validation", () => {
  it("accepts the exact closed project page", () => {
    expect(isDomainWorkItemPageResponse(projectDomainWorkItemsFixture())).toBe(
      true,
    );
  });

  it.each([
    [
      "unknown item fields",
      (fixture: Record<string, unknown>) => {
        const items = fixture.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          items: [{ ...items[0], whyMe: "unsafe projection leak" }],
        };
      },
    ],
    [
      "a Project mismatch",
      (fixture: Record<string, unknown>) => {
        const items = fixture.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          items: [
            {
              ...items[0],
              projectId: "99999999-9999-4999-8999-999999999999",
            },
          ],
        };
      },
    ],
    [
      "a malformed state key",
      (fixture: Record<string, unknown>) => {
        const items = fixture.items as readonly Record<string, unknown>[];
        return { ...fixture, items: [{ ...items[0], stateKey: "Open state" }] };
      },
    ],
    [
      "an unregistered state policy label source",
      (fixture: Record<string, unknown>) => {
        const items = fixture.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          items: [{ ...items[0], stateLabelSource: "Unpublished state" }],
        };
      },
    ],
    [
      "a continuation cursor outside the contract alphabet",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        nextCursor: "opaque+cursor/value",
      }),
    ],
    [
      "an impossible UTC calendar due timestamp",
      (fixture: Record<string, unknown>) => {
        const items = fixture.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          items: [
            { ...items[0], dueAt: "2026-02-30T12:00:00Z" },
            ...items.slice(1),
          ],
        };
      },
    ],
    [
      "a last-changed timestamp before creation at fractional precision",
      (fixture: Record<string, unknown>) => {
        const items = fixture.items as readonly Record<string, unknown>[];
        return {
          ...fixture,
          items: [
            {
              ...items[0],
              createdAt: "2026-07-23T10:10:00.1Z",
              lastChangedAt: "2026-07-23T10:10:00Z",
            },
            ...items.slice(1),
          ],
        };
      },
    ],
    [
      "unstable result order",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        items: [...(fixture.items as readonly unknown[])].reverse(),
      }),
    ],
  ])("rejects %s", (_name, mutate) => {
    const fixture = projectDomainWorkItemsFixture() as unknown as Record<
      string,
      unknown
    >;
    expect(isDomainWorkItemPageResponse(mutate(fixture))).toBe(false);
  });

  it("accepts catalog-governed policy labels beyond the fixture set", () => {
    const context = projectWorkContextFixture();
    expect(
      isProjectWorkContextResponse({
        ...context,
        wbsItems: context.wbsItems.map((item, index) =>
          index === 0
            ? {
                ...item,
                statusKey: "draft_review",
                statusLabelSource: "Draft",
              }
            : item,
        ),
      }),
    ).toBe(true);

    const fixture = projectDomainWorkItemsFixture();
    expect(
      isDomainWorkItemPageResponse({
        ...fixture,
        items: fixture.items.map((item, index) =>
          index === 0
            ? {
                ...item,
                stateKey: "supplier_review",
                stateLabelSource: "Draft",
              }
            : item,
        ),
      }),
    ).toBe(true);
  });

  it("accepts a contract cursor and orders UTC timestamps by instant precision", () => {
    const fixture = projectDomainWorkItemsFixture();
    expect(
      isDomainWorkItemPageResponse({
        ...fixture,
        items: fixture.items.slice(0, 2).map((item, index) => ({
          ...item,
          dueAt:
            index === 0 ? "2026-07-24T12:00:00Z" : "2026-07-24T12:00:00.1Z",
        })),
        nextCursor: "next_page:2~stable",
      }),
    ).toBe(true);
  });
});
