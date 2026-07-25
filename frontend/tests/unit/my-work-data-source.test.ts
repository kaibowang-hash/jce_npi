import { describe, expect, it, vi } from "vitest";

import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  isMyWorkPageResponse,
  LiveMyWorkDataSource,
  MyWorkRequestCancelledError,
} from "../../src/api/my-work-data-source";
import type {
  MyWorkQuery,
  MyWorkView,
} from "../../src/api/my-work-data-source";
import type {
  MyWorkItemViewModel,
  MyWorkPageViewModel,
} from "../../src/domain/view-models";

const projectId = "11111111-1111-4111-8111-111111111111";
const otherProjectId = "99999999-9999-4999-8999-999999999999";
const domainWorkItemId = "22222222-2222-4222-8222-222222222222";
const gateId = "33333333-3333-4333-8333-333333333333";
const invalidatedGateId = "44444444-4444-4444-8444-444444444444";

function myWorkPageFixture(): MyWorkPageViewModel {
  return {
    asOf: "2026-07-25T12:00:00Z",
    timeZone: "UTC",
    projectOptions: [
      {
        globalId: projectId,
        businessCode: "NPI-26018",
        title: "Battery housing",
      },
    ],
    items: [
      {
        id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        category: "risk",
        title: "Hot runner delivery risk",
        project: {
          globalId: projectId,
          businessCode: "NPI-26018",
          title: "Battery housing",
        },
        context: {
          type: "domain_work_item",
          globalId: domainWorkItemId,
          code: "RISK-014",
          title: "Hot runner delivery risk",
        },
        source: {
          type: "domain_work_item",
          globalId: domainWorkItemId,
          version: 4,
        },
        why: "domain_work_item_owner",
        status: "ready",
        dueAt: "2026-07-25T09:00:00Z",
        dueState: "overdue",
        priority: {
          scheme: "domain_severity",
          value: "high",
        },
        blocking: true,
        action: "view_work_item",
        target: {
          kind: "my_work_item",
          workItemId: domainWorkItemId,
        },
        sourceStatus: {
          sourceSystem: "NPI_ONE",
          editableIn: "NPI_ONE",
          syncState: "local",
        },
      },
      {
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        category: "approval",
        title: "Review Gate G3 evidence",
        project: {
          globalId: projectId,
          businessCode: "NPI-26018",
          title: "Battery housing",
        },
        context: {
          type: "gate",
          globalId: gateId,
          code: "G3",
          title: "Tooling release",
        },
        source: {
          type: "gate_review_assignment",
          globalId: gateId,
          version: 7,
        },
        why: "gate_review_step",
        status: "waiting",
        dueAt: "2026-07-25T10:00:00Z",
        dueState: "overdue",
        priority: {
          scheme: "gate_requirement_priority",
          value: "P0",
        },
        blocking: false,
        action: "open_gate_review",
        target: {
          kind: "gate_review",
          projectId,
          gateId,
        },
        sourceStatus: {
          sourceSystem: "NPI_ONE",
          editableIn: "NPI_ONE",
          syncState: "local",
        },
      },
      {
        id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        category: "blocker",
        title: "Re-review invalidated Gate G4",
        project: {
          globalId: projectId,
          businessCode: "NPI-26018",
          title: "Battery housing",
        },
        context: {
          type: "gate",
          globalId: invalidatedGateId,
          code: "G4",
          title: "Trial approval",
        },
        source: {
          type: "gate_review_invalidation",
          globalId: invalidatedGateId,
          version: 3,
        },
        why: "gate_dependency_change",
        status: "blocked",
        dueAt: null,
        dueState: "unscheduled",
        priority: null,
        blocking: true,
        action: "open_gate_review",
        target: {
          kind: "gate_review",
          projectId,
          gateId: invalidatedGateId,
        },
        sourceStatus: {
          sourceSystem: "NPI_ONE",
          editableIn: "NPI_ONE",
          syncState: "local",
        },
      },
    ],
    nextCursor: null,
    counts: {
      all: { availability: "available", value: 3 },
      today: { availability: "available", value: 2 },
      overdue: { availability: "available", value: 2 },
      approvals: { availability: "available", value: 1 },
      blockers: { availability: "available", value: 2 },
      waiting: { availability: "available", value: 1 },
      integration: {
        availability: "unavailable",
        reason: "source_not_available",
      },
    },
  };
}

function recordFixture(): Record<string, unknown> {
  return structuredClone(myWorkPageFixture()) as unknown as Record<
    string,
    unknown
  >;
}

function itemRecords(
  fixture: Record<string, unknown>,
): Record<string, unknown>[] {
  return fixture.items as Record<string, unknown>[];
}

function itemAt(
  items: readonly MyWorkItemViewModel[],
  index: number,
): MyWorkItemViewModel {
  const item = items[index];
  if (!item) throw new Error(`Missing My Work fixture item ${String(index)}.`);
  return item;
}

function itemRecordAt(
  fixture: Record<string, unknown>,
  index: number,
): Record<string, unknown> {
  const item = itemRecords(fixture)[index];
  if (!item)
    throw new Error(`Missing My Work record fixture item ${String(index)}.`);
  return item;
}

function pageWithItems(
  items: readonly MyWorkItemViewModel[],
  overrides: Partial<MyWorkPageViewModel> = {},
): MyWorkPageViewModel {
  return {
    ...myWorkPageFixture(),
    items,
    ...overrides,
  };
}

async function responseValidatorFor(
  query: MyWorkQuery,
): Promise<(value: unknown) => boolean> {
  const http = new NpiHttpClient();
  const request = vi
    .spyOn(http, "request")
    .mockImplementation(
      <T>(): Promise<T> => Promise.resolve(myWorkPageFixture() as T),
    );

  await new LiveMyWorkDataSource(http).load(
    query,
    new AbortController().signal,
  );
  const validate = request.mock.calls[0]?.[2]?.validate;
  expect(validate).toBeTypeOf("function");
  return (value: unknown): boolean => validate?.(value) ?? false;
}

describe("live My Work data source", () => {
  it("loads the exact current-user BFF query with strict response requirements", async () => {
    const fixture = myWorkPageFixture();
    const response = pageWithItems([itemAt(fixture.items, 0)]);
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new LiveMyWorkDataSource(http);
    const controller = new AbortController();
    const query = {
      view: "blockers",
      projectId,
      priority: {
        scheme: "domain_severity",
        value: "high",
      },
      search: "",
      cursor: "work:page_1~opaque",
      limit: 25,
    } as const;

    await expect(source.load(query, controller.signal)).resolves.toEqual(
      response,
    );
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe("/me/work");
    expect(init).toEqual({ method: "GET", signal: controller.signal });
    expect(options?.query).toEqual({
      view: "blockers",
      projectId,
      priorityScheme: "domain_severity",
      priorityValue: "high",
      search: "",
      cursor: "work:page_1~opaque",
      limit: "25",
    });
    expect(options?.requirePrivateNoStore).toBe(true);
    expect(options?.requireRequestIdEcho).toBe(true);
    expect(options?.requireTraceId).toBe(true);
    expect(options?.validate?.(response)).toBe(true);
    expect(options?.validate?.(fixture)).toBe(false);
  });

  it.each([
    ["a missing view", {}],
    ["an unknown query field", { view: "all", owner: "me" }],
    ["an unsupported view", { view: "project" }],
    ["a malformed Project UUID", { view: "all", projectId: "NPI-26018" }],
    [
      "a cross-vocabulary priority",
      {
        view: "all",
        priority: { scheme: "domain_severity", value: "P0" },
      },
    ],
    [
      "an extended priority object",
      {
        view: "all",
        priority: {
          scheme: "domain_severity",
          value: "high",
          rank: 1,
        },
      },
    ],
    ["an oversized search", { view: "all", search: "s".repeat(141) }],
    ["an empty cursor", { view: "all", cursor: "" }],
    ["a cursor outside the alphabet", { view: "all", cursor: "page+1/value" }],
    ["an oversized cursor", { view: "all", cursor: "c".repeat(501) }],
    ["a zero limit", { view: "all", limit: 0 }],
    ["a fractional limit", { view: "all", limit: 1.5 }],
    ["an oversized limit", { view: "all", limit: 101 }],
  ])("rejects %s before issuing a request", async (_name, candidate) => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");

    await expect(
      new LiveMyWorkDataSource(http).load(
        candidate as MyWorkQuery,
        new AbortController().signal,
      ),
    ).rejects.toMatchObject({
      kind: "request_not_ready",
      name: "NpiTransportError",
      referenceKind: "client",
    });
    expect(request).not.toHaveBeenCalled();
  });

  it("maps an in-flight abort to the dedicated cancellation error", async () => {
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
    const controller = new AbortController();
    const request = new LiveMyWorkDataSource(http).load(
      { view: "all" },
      controller.signal,
    );

    controller.abort();
    await expect(request).rejects.toBeInstanceOf(MyWorkRequestCancelledError);
  });

  it("rejects an already-aborted request without contacting the BFF", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const controller = new AbortController();
    controller.abort();

    await expect(
      new LiveMyWorkDataSource(http).load({ view: "all" }, controller.signal),
    ).rejects.toBeInstanceOf(MyWorkRequestCancelledError);
    expect(request).not.toHaveBeenCalled();
  });
});

describe("My Work page response validation", () => {
  it("accepts the exact contract and bounded optional source status metadata", () => {
    const fixture = myWorkPageFixture();
    const first = itemAt(fixture.items, 0);
    expect(isMyWorkPageResponse(fixture)).toBe(true);
    expect(
      isMyWorkPageResponse(
        pageWithItems([
          {
            ...first,
            sourceStatus: {
              ...first.sourceStatus,
              lastSyncedAt: "2026-07-25T08:30:00.123456Z",
              externalReference: "DWI:RISK-014",
            },
          },
          ...fixture.items.slice(1),
        ]),
      ),
    ).toBe(true);
  });

  it("requires complete unique Project filter options consistent with every row", () => {
    const fixture = myWorkPageFixture();
    const projectOption = fixture.projectOptions[0];
    if (!projectOption) {
      throw new Error("The My Work fixture requires one Project option.");
    }
    expect(isMyWorkPageResponse(fixture)).toBe(true);
    expect(isMyWorkPageResponse({ ...fixture, projectOptions: [] })).toBe(
      false,
    );
    expect(
      isMyWorkPageResponse({
        ...fixture,
        projectOptions: [...fixture.projectOptions, ...fixture.projectOptions],
      }),
    ).toBe(false);
    expect(
      isMyWorkPageResponse({
        ...fixture,
        projectOptions: [
          {
            ...projectOption,
            title: "Unrelated title",
          },
        ],
      }),
    ).toBe(false);
  });

  it("accepts an exact empty page without representing integration as zero", () => {
    const fixture = myWorkPageFixture();
    expect(
      isMyWorkPageResponse({
        ...fixture,
        items: [],
        counts: {
          ...fixture.counts,
          all: { availability: "available", value: 0 },
          today: { availability: "available", value: 0 },
          overdue: { availability: "available", value: 0 },
          approvals: { availability: "available", value: 0 },
          blockers: { availability: "available", value: 0 },
          waiting: { availability: "available", value: 0 },
        },
      }),
    ).toBe(true);
  });

  it.each([
    [
      "unknown response fields",
      (fixture: Record<string, unknown>) => ({ ...fixture, debug: true }),
    ],
    [
      "unknown item fields",
      (fixture: Record<string, unknown>) => {
        const items = itemRecords(fixture);
        return {
          ...fixture,
          items: [{ ...items[0], targetPath: "/unsafe" }, ...items.slice(1)],
        };
      },
    ],
    [
      "a missing required item field",
      (fixture: Record<string, unknown>) => {
        const items = itemRecords(fixture);
        const first = { ...items[0] };
        delete first.title;
        return { ...fixture, items: [first, ...items.slice(1)] };
      },
    ],
    [
      "a missing due state",
      (fixture: Record<string, unknown>) => {
        const first = itemRecordAt(fixture, 0);
        delete first.dueState;
        return fixture;
      },
    ],
    [
      "an unknown due state",
      (fixture: Record<string, unknown>) => {
        itemRecordAt(fixture, 0).dueState = "due_soon";
        return fixture;
      },
    ],
    [
      "a due state inconsistent with the fixed page clock",
      (fixture: Record<string, unknown>) => {
        itemRecordAt(fixture, 0).dueState = "today";
        return fixture;
      },
    ],
    [
      "an unscheduled due state with a timestamp",
      (fixture: Record<string, unknown>) => {
        itemRecordAt(fixture, 0).dueState = "unscheduled";
        return fixture;
      },
    ],
    [
      "unknown Project fields",
      (fixture: Record<string, unknown>) => {
        const items = itemRecords(fixture);
        return {
          ...fixture,
          items: [
            {
              ...items[0],
              project: {
                ...(items[0]?.project as Record<string, unknown>),
                tenantId: "leak",
              },
            },
            ...items.slice(1),
          ],
        };
      },
    ],
    [
      "unknown context fields",
      (fixture: Record<string, unknown>) => {
        const items = itemRecords(fixture);
        return {
          ...fixture,
          items: [
            {
              ...items[0],
              context: {
                ...(items[0]?.context as Record<string, unknown>),
                owner: "leak",
              },
            },
            ...items.slice(1),
          ],
        };
      },
    ],
    [
      "unknown source fields",
      (fixture: Record<string, unknown>) => {
        const items = itemRecords(fixture);
        return {
          ...fixture,
          items: [
            {
              ...items[0],
              source: {
                ...(items[0]?.source as Record<string, unknown>),
                rawDoctype: "NPI Domain Work Item",
              },
            },
            ...items.slice(1),
          ],
        };
      },
    ],
    [
      "an arbitrary target path",
      (fixture: Record<string, unknown>) => {
        const items = itemRecords(fixture);
        return {
          ...fixture,
          items: [
            {
              ...items[0],
              target: {
                ...(items[0]?.target as Record<string, unknown>),
                targetPath: "/app/user",
              },
            },
            ...items.slice(1),
          ],
        };
      },
    ],
    [
      "unknown source-status fields",
      (fixture: Record<string, unknown>) => {
        const items = itemRecords(fixture);
        return {
          ...fixture,
          items: [
            {
              ...items[0],
              sourceStatus: {
                ...(items[0]?.sourceStatus as Record<string, unknown>),
                externalUrl: "https://example.invalid",
              },
            },
            ...items.slice(1),
          ],
        };
      },
    ],
    [
      "unknown count fields",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        counts: {
          ...(fixture.counts as Record<string, unknown>),
          notifications: { availability: "available", value: 0 },
        },
      }),
    ],
    [
      "mixed available and unavailable count fields",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        counts: {
          ...(fixture.counts as Record<string, unknown>),
          all: {
            availability: "available",
            value: 3,
            reason: "source_not_available",
          },
        },
      }),
    ],
  ])("rejects %s", (_name, mutate) => {
    expect(isMyWorkPageResponse(mutate(recordFixture()))).toBe(false);
  });

  it.each([
    [
      "a non-UUID item identity",
      (fixture: Record<string, unknown>) => {
        itemRecordAt(fixture, 0).id = "work-1";
        return fixture;
      },
    ],
    [
      "an impossible as-of timestamp",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        asOf: "2026-02-30T12:00:00Z",
      }),
    ],
    [
      "a non-UTC as-of timestamp",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        asOf: "2026-07-25T12:00:00+08:00",
      }),
    ],
    [
      "an empty time zone",
      (fixture: Record<string, unknown>) => ({ ...fixture, timeZone: "" }),
    ],
    [
      "an unresolved time zone",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        timeZone: "Mars/Olympus",
      }),
    ],
    [
      "an oversized time zone",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        timeZone: "T".repeat(65),
      }),
    ],
    [
      "a blank business-data title",
      (fixture: Record<string, unknown>) => {
        itemRecordAt(fixture, 0).title = "   ";
        return fixture;
      },
    ],
    [
      "an oversized business-data title",
      (fixture: Record<string, unknown>) => {
        itemRecordAt(fixture, 0).title = "T".repeat(281);
        return fixture;
      },
    ],
    [
      "an oversized Project business code",
      (fixture: Record<string, unknown>) => {
        const first = itemRecordAt(fixture, 0);
        (first.project as Record<string, unknown>).businessCode = "P".repeat(
          65,
        );
        return fixture;
      },
    ],
    [
      "an oversized context code",
      (fixture: Record<string, unknown>) => {
        const first = itemRecordAt(fixture, 0);
        (first.context as Record<string, unknown>).code = "C".repeat(65);
        return fixture;
      },
    ],
    [
      "a non-positive source version",
      (fixture: Record<string, unknown>) => {
        const first = itemRecordAt(fixture, 0);
        (first.source as Record<string, unknown>).version = 0;
        return fixture;
      },
    ],
    [
      "an impossible due timestamp",
      (fixture: Record<string, unknown>) => {
        itemRecordAt(fixture, 0).dueAt = "2026-02-30T12:00:00Z";
        return fixture;
      },
    ],
    [
      "a non-UTC due timestamp",
      (fixture: Record<string, unknown>) => {
        itemRecordAt(fixture, 0).dueAt = "2026-07-25T17:00:00+08:00";
        return fixture;
      },
    ],
    [
      "an invalid source status",
      (fixture: Record<string, unknown>) => {
        const first = itemRecordAt(fixture, 0);
        (first.sourceStatus as Record<string, unknown>).syncState = "success";
        return fixture;
      },
    ],
    [
      "an invalid source synchronization timestamp",
      (fixture: Record<string, unknown>) => {
        const first = itemRecordAt(fixture, 0);
        (first.sourceStatus as Record<string, unknown>).lastSyncedAt =
          "yesterday";
        return fixture;
      },
    ],
    [
      "an oversized external reference",
      (fixture: Record<string, unknown>) => {
        const first = itemRecordAt(fixture, 0);
        (first.sourceStatus as Record<string, unknown>).externalReference =
          "X".repeat(2049);
        return fixture;
      },
    ],
    [
      "a cursor outside the contract alphabet",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        nextCursor: "next+page/value",
      }),
    ],
    [
      "an oversized cursor",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        nextCursor: "n".repeat(501),
      }),
    ],
    [
      "a negative count",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        counts: {
          ...(fixture.counts as Record<string, unknown>),
          all: { availability: "available", value: -1 },
        },
      }),
    ],
    [
      "a fractional count",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        counts: {
          ...(fixture.counts as Record<string, unknown>),
          all: { availability: "available", value: 3.5 },
        },
      }),
    ],
    [
      "an unavailable owned-source count",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        counts: {
          ...(fixture.counts as Record<string, unknown>),
          today: {
            availability: "unavailable",
            reason: "source_not_available",
          },
        },
      }),
    ],
    [
      "a misleading integration zero",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        counts: {
          ...(fixture.counts as Record<string, unknown>),
          integration: { availability: "available", value: 0 },
        },
      }),
    ],
    [
      "an unsupported unavailable reason",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        counts: {
          ...(fixture.counts as Record<string, unknown>),
          integration: {
            availability: "unavailable",
            reason: "not_configured",
          },
        },
      }),
    ],
    [
      "a subgroup count above the all count",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        counts: {
          ...(fixture.counts as Record<string, unknown>),
          today: { availability: "available", value: 4 },
        },
      }),
    ],
  ])("rejects %s", (_name, mutate) => {
    expect(isMyWorkPageResponse(mutate(recordFixture()))).toBe(false);
  });

  it("rejects more than 100 items", () => {
    const fixture = myWorkPageFixture();
    const first = itemAt(fixture.items, 0);
    const items = Array.from({ length: 101 }, (_, index) => ({
      ...first,
      id: `00000000-0000-4000-8000-${index.toString(16).padStart(12, "0")}`,
    }));
    expect(
      isMyWorkPageResponse({
        ...fixture,
        items,
        counts: {
          ...fixture.counts,
          all: { availability: "available", value: 101 },
        },
      }),
    ).toBe(false);
  });

  it("rejects duplicate item identities", () => {
    const fixture = myWorkPageFixture();
    const first = itemAt(fixture.items, 0);
    expect(
      isMyWorkPageResponse({
        ...fixture,
        items: [first, first],
      }),
    ).toBe(false);
  });
});

describe("My Work source and target consistency", () => {
  it.each([
    [
      "a Domain WorkItem context identity mismatch",
      (item: Record<string, unknown>) => {
        (item.context as Record<string, unknown>).globalId = gateId;
      },
    ],
    [
      "a Domain WorkItem target identity mismatch",
      (item: Record<string, unknown>) => {
        (item.target as Record<string, unknown>).workItemId = gateId;
      },
    ],
    [
      "a Domain WorkItem Gate target",
      (item: Record<string, unknown>) => {
        item.target = { kind: "gate_review", projectId, gateId };
      },
    ],
    [
      "a Domain WorkItem Gate action",
      (item: Record<string, unknown>) => {
        item.action = "open_gate_review";
      },
    ],
    [
      "a Domain WorkItem Gate assignment reason",
      (item: Record<string, unknown>) => {
        item.why = "gate_review_step";
      },
    ],
    [
      "a Domain WorkItem approval category",
      (item: Record<string, unknown>) => {
        item.category = "approval";
      },
    ],
    [
      "a Domain WorkItem Gate priority",
      (item: Record<string, unknown>) => {
        item.priority = {
          scheme: "gate_requirement_priority",
          value: "P0",
        };
      },
    ],
  ])("rejects %s", (_name, mutate) => {
    const fixture = recordFixture();
    mutate(itemRecordAt(fixture, 0));
    expect(isMyWorkPageResponse(fixture)).toBe(false);
  });

  it.each([
    [
      "a cross-Project Gate target",
      (item: Record<string, unknown>) => {
        (item.target as Record<string, unknown>).projectId = otherProjectId;
      },
    ],
    [
      "a Gate target identity mismatch",
      (item: Record<string, unknown>) => {
        (item.target as Record<string, unknown>).gateId = invalidatedGateId;
      },
    ],
    [
      "a Gate context identity mismatch",
      (item: Record<string, unknown>) => {
        (item.context as Record<string, unknown>).globalId = invalidatedGateId;
      },
    ],
    [
      "a Gate WorkItem target",
      (item: Record<string, unknown>) => {
        item.target = {
          kind: "my_work_item",
          workItemId: domainWorkItemId,
        };
      },
    ],
    [
      "a Gate WorkItem action",
      (item: Record<string, unknown>) => {
        item.action = "view_work_item";
      },
    ],
    [
      "a Gate Domain priority",
      (item: Record<string, unknown>) => {
        item.priority = { scheme: "domain_severity", value: "high" };
      },
    ],
    [
      "an assignment blocker category",
      (item: Record<string, unknown>) => {
        item.category = "blocker";
      },
    ],
    [
      "an assignment dependency-change reason",
      (item: Record<string, unknown>) => {
        item.why = "gate_dependency_change";
      },
    ],
  ])("rejects %s", (_name, mutate) => {
    const fixture = recordFixture();
    mutate(itemRecordAt(fixture, 1));
    expect(isMyWorkPageResponse(fixture)).toBe(false);
  });

  it.each([
    [
      "an invalidation approval category",
      (item: Record<string, unknown>) => {
        item.category = "approval";
      },
    ],
    [
      "an invalidation that is not blocking",
      (item: Record<string, unknown>) => {
        item.blocking = false;
      },
    ],
    [
      "an invalidation without the dependency-change reason",
      (item: Record<string, unknown>) => {
        item.why = "gate_reopen";
      },
    ],
  ])("rejects %s", (_name, mutate) => {
    const fixture = recordFixture();
    mutate(itemRecordAt(fixture, 2));
    expect(isMyWorkPageResponse(fixture)).toBe(false);
  });
});

describe("My Work canonical order", () => {
  it("accepts due timestamps by exact fractional precision and nulls last", () => {
    const fixture = myWorkPageFixture();
    const first = itemAt(fixture.items, 0);
    const second = itemAt(fixture.items, 1);
    const third = itemAt(fixture.items, 2);
    expect(
      isMyWorkPageResponse({
        ...fixture,
        items: [
          {
            ...first,
            dueAt: "2026-07-25T09:00:00.000001Z",
          },
          {
            ...second,
            dueAt: "2026-07-25T09:00:00.000010Z",
          },
          third,
        ],
      }),
    ).toBe(true);
  });

  it.each([
    [
      "later due timestamps before earlier ones",
      (fixture: MyWorkPageViewModel) => {
        const first = itemAt(fixture.items, 0);
        const second = itemAt(fixture.items, 1);
        const third = itemAt(fixture.items, 2);
        return { ...fixture, items: [second, first, third] };
      },
    ],
    [
      "null due timestamps before bounded ones",
      (fixture: MyWorkPageViewModel) => {
        const first = itemAt(fixture.items, 0);
        const second = itemAt(fixture.items, 1);
        const third = itemAt(fixture.items, 2);
        return { ...fixture, items: [third, first, second] };
      },
    ],
    [
      "descending IDs for equal due timestamps",
      (fixture: MyWorkPageViewModel) => {
        const first = itemAt(fixture.items, 0);
        const second = itemAt(fixture.items, 1);
        const third = itemAt(fixture.items, 2);
        return {
          ...fixture,
          items: [
            {
              ...first,
              id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            },
            {
              ...second,
              id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
              dueAt: first.dueAt,
            },
            third,
          ],
        };
      },
    ],
  ])("rejects %s", (_name, mutate) => {
    expect(isMyWorkPageResponse(mutate(myWorkPageFixture()))).toBe(false);
  });
});

describe("My Work response-to-query consistency", () => {
  it("matches exact Project and priority filters", async () => {
    const fixture = myWorkPageFixture();
    const domainItem = itemAt(fixture.items, 0);
    const gateItem = itemAt(fixture.items, 1);
    const validate = await responseValidatorFor({
      view: "all",
      projectId,
      priority: { scheme: "domain_severity", value: "high" },
    });
    const filtered = pageWithItems([domainItem]);
    expect(validate(filtered)).toBe(true);
    expect(
      validate(
        pageWithItems([
          {
            ...domainItem,
            project: {
              ...domainItem.project,
              globalId: otherProjectId,
            },
          },
        ]),
      ),
    ).toBe(false);
    expect(validate(pageWithItems([gateItem]))).toBe(false);
  });

  it("matches today in the server-resolved time zone", async () => {
    const fixture = myWorkPageFixture();
    const validate = await responseValidatorFor({ view: "today" });
    const item = itemAt(fixture.items, 0);
    expect(
      validate(
        pageWithItems([item], {
          asOf: "2026-07-25T00:30:00Z",
          timeZone: "America/Los_Angeles",
          items: [{ ...item, dueAt: "2026-07-24T23:00:00Z" }],
        }),
      ),
    ).toBe(true);
    expect(
      validate(
        pageWithItems([item], {
          asOf: "2026-07-25T00:30:00Z",
          timeZone: "America/Los_Angeles",
          items: [
            {
              ...item,
              dueAt: "2026-07-25T08:00:00Z",
              dueState: "upcoming",
            },
          ],
        }),
      ),
    ).toBe(false);
  });

  it("matches overdue by exact as-of instant", async () => {
    const fixture = myWorkPageFixture();
    const domainItem = itemAt(fixture.items, 0);
    const validate = await responseValidatorFor({ view: "overdue" });
    expect(validate(pageWithItems(fixture.items.slice(0, 2)))).toBe(true);
    expect(
      validate(
        pageWithItems([
          {
            ...domainItem,
            dueAt: "2026-07-25T12:00:00.000001Z",
            dueState: "today",
          },
        ]),
      ),
    ).toBe(false);
  });

  it.each([
    ["approvals", 1],
    ["blockers", 0],
    ["blockers", 2],
    ["waiting", 1],
  ] as const)("matches the %s projection", async (view, itemIndex) => {
    const fixture = myWorkPageFixture();
    const validate = await responseValidatorFor({ view });
    expect(validate(pageWithItems([itemAt(fixture.items, itemIndex)]))).toBe(
      true,
    );
  });

  it("keeps integration unavailable and empty", async () => {
    const fixture = myWorkPageFixture();
    const domainItem = itemAt(fixture.items, 0);
    const validate = await responseValidatorFor({ view: "integration" });
    expect(
      validate(
        pageWithItems([], {
          nextCursor: null,
        }),
      ),
    ).toBe(true);
    expect(validate(pageWithItems([domainItem]))).toBe(false);
  });

  it("rejects a page beyond the requested limit or a repeated cursor", async () => {
    const fixture = myWorkPageFixture();
    const domainItem = itemAt(fixture.items, 0);
    const limited = await responseValidatorFor({ view: "all", limit: 1 });
    expect(limited(pageWithItems(fixture.items.slice(0, 2)))).toBe(false);

    const cursor = "work:page_2~opaque";
    const paged = await responseValidatorFor({ view: "all", cursor });
    expect(
      paged(
        pageWithItems([domainItem], {
          nextCursor: cursor,
        }),
      ),
    ).toBe(false);
  });

  it("rejects a selected-view count below the returned page size", async () => {
    const fixture = myWorkPageFixture();
    const gateItem = itemAt(fixture.items, 1);
    const validate = await responseValidatorFor({ view: "approvals" });
    expect(
      validate(
        pageWithItems([gateItem], {
          counts: {
            ...fixture.counts,
            approvals: { availability: "available", value: 0 },
          },
        }),
      ),
    ).toBe(false);
  });

  it.each<MyWorkView>([
    "all",
    "today",
    "overdue",
    "approvals",
    "blockers",
    "waiting",
    "integration",
  ])("serializes the supported %s view", async (view) => {
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(
        <T>(): Promise<T> => Promise.resolve(myWorkPageFixture() as T),
      );

    await new LiveMyWorkDataSource(http).load(
      { view },
      new AbortController().signal,
    );
    expect(request.mock.calls[0]?.[2]?.query).toEqual({ view });
  });
});
