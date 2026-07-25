import { describe, expect, it, vi } from "vitest";

import {
  isProjectCockpitResponse,
  LiveProjectCockpitDataSource,
  ProjectRequestCancelledError,
} from "../../src/api/project-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import { projectCockpitFixture } from "../support/project-fixture";

describe("live Project cockpit data source", () => {
  it("loads the exact same-origin BFF path with cancellation and strict validation", async () => {
    const fixture = projectCockpitFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(fixture as T));
    const dataSource = new LiveProjectCockpitDataSource(http);
    const controller = new AbortController();

    await expect(
      dataSource.load(fixture.project.globalId, controller.signal),
    ).resolves.toEqual(fixture);
    expect(request).toHaveBeenCalledWith(
      `/projects/${fixture.project.globalId}/cockpit`,
      { signal: controller.signal },
      {
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isProjectCockpitResponse,
      },
    );
  });

  it("rejects a non-UUID route before issuing a request", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const dataSource = new LiveProjectCockpitDataSource(http);

    await expect(
      dataSource.load("PJ-26018", new AbortController().signal),
    ).rejects.toMatchObject({
      kind: "request_not_ready",
      name: "NpiTransportError",
      referenceKind: "client",
    });
    expect(request).not.toHaveBeenCalled();
  });

  it("converts an aborted transport into a cancellation result", async () => {
    const fixture = projectCockpitFixture();
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
    const dataSource = new LiveProjectCockpitDataSource(http);
    const controller = new AbortController();
    const request = dataSource.load(
      fixture.project.globalId,
      controller.signal,
    );

    controller.abort();
    await expect(request).rejects.toBeInstanceOf(ProjectRequestCancelledError);
  });
});

describe("Project cockpit response validation", () => {
  it("accepts the exact contract and an omitted reference global ID", () => {
    expect(isProjectCockpitResponse(projectCockpitFixture())).toBe(true);
  });

  it("accepts the canonical UUID syntax allowed by the server and OpenAPI", () => {
    const fixture = projectCockpitFixture();
    expect(
      isProjectCockpitResponse({
        ...fixture,
        references: [
          {
            ...fixture.references[0],
            globalId: "00000000-0000-0000-0000-000000000000",
          },
          ...fixture.references.slice(1),
        ],
      }),
    ).toBe(true);
  });

  it.each([
    [
      "unknown top-level fields",
      (fixture: Record<string, unknown>) => ({ ...fixture, debug: true }),
    ],
    [
      "unknown nested fields",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        project: {
          ...(fixture.project as Record<string, unknown>),
          health: "green",
        },
      }),
    ],
    [
      "nullable reference identities",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        references: [
          {
            type: "customer",
            sourceSystem: "NPI_ONE",
            sourceObjectId: "SYN-CUSTOMER-001",
            globalId: null,
          },
        ],
      }),
    ],
    [
      "out-of-order Gates",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        gates: [...(fixture.gates as readonly unknown[])].reverse(),
      }),
    ],
    [
      "an empty Gate list",
      (fixture: Record<string, unknown>) => ({ ...fixture, gates: [] }),
    ],
    [
      "duplicate references",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        references: [
          ...(fixture.references as readonly unknown[]),
          (fixture.references as readonly unknown[])[0],
        ],
      }),
    ],
    [
      "guessed project health",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        project: {
          ...(fixture.project as Record<string, unknown>),
          health: "green",
        },
      }),
    ],
    [
      "unsupported project states",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        project: {
          ...(fixture.project as Record<string, unknown>),
          state: "archived",
        },
      }),
    ],
  ])("rejects %s", (_name, mutate) => {
    const fixture = projectCockpitFixture() as unknown as Record<
      string,
      unknown
    >;
    expect(isProjectCockpitResponse(mutate(fixture))).toBe(false);
  });
});
