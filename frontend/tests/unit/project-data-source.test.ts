import { describe, expect, it, vi } from "vitest";

import {
  isProjectCreationContextResponse,
  isProjectCockpitResponse,
  LiveProjectCockpitDataSource,
  LiveProjectCreationDataSource,
  ProjectRequestCancelledError,
  type ProjectCreationContext,
} from "../../src/api/project-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import { projectCockpitFixture } from "../support/project-fixture";

const creationContext: ProjectCreationContext = {
  ownerUserId: "manager@example.invalid",
  templates: [
    {
      applicableProjectTypes: ["new_tool", "tool_change"],
      code: "NEW-TOOL",
      expectedVersion: 2,
      globalId: "11111111-1111-4111-8111-111111111111",
      referenceRules: [
        { allowMultiple: false, required: false, type: "factory" },
      ],
      title: "New Tool Project",
      version: 1,
    },
  ],
  tenantId: "TENANT-A",
};
const creationTemplate = creationContext.templates[0];
if (!creationTemplate)
  throw new Error("The creation fixture needs one template.");

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

  it.each([
    ["linking", null],
    ["failed", "ERP_PROJECT_CREATE_REJECTED"],
  ] as const)(
    "accepts a complete %s ERP Project publication state",
    (state, errorCode) => {
      const fixture = projectCockpitFixture();
      expect(
        isProjectCockpitResponse({
          ...fixture,
          erpProjectBinding: {
            sourceSystem: "ERPNEXT",
            state,
            sourceObjectId: null,
            lastProcessedAt: "2026-09-06T08:00:00Z",
            requestGlobalId: "66666666-6666-4666-8666-666666666666",
            errorCode,
          },
        }),
      ).toBe(true);
    },
  );

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
      "invalid ERP Project binding identity",
      (fixture: Record<string, unknown>) => ({
        ...fixture,
        erpProjectBinding: {
          sourceSystem: "ERPNEXT",
          state: "bound",
          sourceObjectId: null,
          lastProcessedAt: null,
          requestGlobalId: null,
          errorCode: null,
        },
      }),
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

describe("live Project creation data source", () => {
  it("loads the actor-bound creation context and accepts the complete closed shape", async () => {
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(
        <T>(): Promise<T> => Promise.resolve(creationContext as T),
      );
    const dataSource = new LiveProjectCreationDataSource(http);
    const controller = new AbortController();

    await expect(
      dataSource.loadCreationContext(controller.signal),
    ).resolves.toEqual(creationContext);
    expect(request).toHaveBeenCalledWith(
      "/projects/creation-context",
      { signal: controller.signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isProjectCreationContextResponse,
      },
    );
    expect(isProjectCreationContextResponse(creationContext)).toBe(true);
  });

  it("submits the current user, exact template version and empty references", async () => {
    const created = projectCockpitFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(created as T));
    const dataSource = new LiveProjectCreationDataSource(http);
    const controller = new AbortController();

    await expect(
      dataSource.create(
        {
          businessCode: "P-26001",
          expectedVersion: 2,
          projectType: "new_tool",
          targetSop: "2027-01-31",
          templateGlobalId: creationTemplate.globalId,
          templateVersion: 1,
          title: "Program Alpha",
        },
        creationContext,
        {
          csrfToken: "c".repeat(32),
          idempotencyKey: "11111111-1111-4111-8111-111111111111",
          signal: controller.signal,
        },
      ),
    ).resolves.toEqual(created);
    expect(request).toHaveBeenCalledWith(
      "/projects",
      {
        body: JSON.stringify({
          tenantId: "TENANT-A",
          businessCode: "P-26001",
          title: "Program Alpha",
          projectType: "new_tool",
          ownerUserId: "manager@example.invalid",
          targetSop: "2027-01-31",
          templateGlobalId: "11111111-1111-4111-8111-111111111111",
          templateVersion: 1,
          expectedVersion: 2,
          references: [],
        }),
        headers: {
          "Idempotency-Key": "11111111-1111-4111-8111-111111111111",
        },
        method: "POST",
        signal: controller.signal,
      },
      {
        csrfToken: "c".repeat(32),
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isProjectCockpitResponse,
      },
    );
  });

  it("submits the exact Unicode ERP customer allowed by the selected template", async () => {
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(
        <T>(): Promise<T> => Promise.resolve(projectCockpitFixture() as T),
      );
    const source = new LiveProjectCreationDataSource(http);
    const creation = {
      ...creationContext,
      templates: [
        {
          ...creationTemplate,
          referenceRules: [
            { type: "customer" as const, required: true, allowMultiple: false },
          ],
        },
      ],
    };
    await source.create(
      {
        businessCode: "P-26002",
        title: "Customer project",
        projectType: "new_tool",
        targetSop: "2027-01-31",
        templateGlobalId: creationTemplate.globalId,
        templateVersion: 1,
        expectedVersion: 2,
        customerSourceKey: "客户 A",
      },
      creation,
      {
        csrfToken: "c".repeat(32),
        idempotencyKey: "11111111-1111-4111-8111-111111111111",
        signal: new AbortController().signal,
      },
    );
    const call = request.mock.calls[0];
    if (!call || typeof call[1]?.body !== "string")
      throw new Error("Project request body missing");
    expect(JSON.parse(call[1].body)).toMatchObject({
      references: [
        { type: "customer", sourceSystem: "ERPNEXT", sourceObjectId: "客户 A" },
      ],
    });
  });

  it("fails before transport for stale templates, required references and invalid command context", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const dataSource = new LiveProjectCreationDataSource(http);
    const signal = new AbortController().signal;
    const command = {
      businessCode: "P-26001",
      expectedVersion: 2,
      projectType: "new_tool" as const,
      targetSop: "2027-01-31",
      templateGlobalId: creationTemplate.globalId,
      templateVersion: 1,
      title: "Program Alpha",
    };

    await expect(
      dataSource.create(command, creationContext, {
        csrfToken: "short",
        idempotencyKey: "short",
        signal,
      }),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    await expect(
      dataSource.create(
        command,
        {
          ...creationContext,
          templates: [
            {
              ...creationTemplate,
              referenceRules: [
                { allowMultiple: false, required: true, type: "customer" },
              ],
            },
          ],
        },
        {
          csrfToken: "c".repeat(32),
          idempotencyKey: "11111111-1111-4111-8111-111111111111",
          signal,
        },
      ),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    expect(request).not.toHaveBeenCalled();
  });

  it("rejects duplicate template and reference-rule identities", () => {
    expect(
      isProjectCreationContextResponse({
        ...creationContext,
        templates: [creationContext.templates[0], creationContext.templates[0]],
      }),
    ).toBe(false);
    expect(
      isProjectCreationContextResponse({
        ...creationContext,
        templates: [
          {
            ...creationContext.templates[0],
            referenceRules: [
              { allowMultiple: false, required: false, type: "factory" },
              { allowMultiple: true, required: false, type: "factory" },
            ],
          },
        ],
      }),
    ).toBe(false);
  });

  it("converts an aborted creation-context request into a cancellation result", async () => {
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
    const dataSource = new LiveProjectCreationDataSource(http);
    const controller = new AbortController();
    const request = dataSource.loadCreationContext(controller.signal);

    controller.abort();
    await expect(request).rejects.toBeInstanceOf(ProjectRequestCancelledError);
  });
});
