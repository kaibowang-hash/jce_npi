import { afterEach, describe, expect, it, vi } from "vitest";
import {
  LiveProjectSetupDataSource,
  type SetupOptions,
} from "../../src/api/project-setup-data-source";
import { NpiTransportError } from "../../src/api/http";
import {
  projectWorkContextFixture,
  projectWorkPolicyFixture,
} from "../support/project-work-fixture";
const context = projectWorkContextFixture();
const reference = projectWorkPolicyFixture;
const request = () => ({
  csrfToken: "c".repeat(32),
  idempotencyKey: "setup-request-12345678",
  signal: new AbortController().signal,
});
function response(
  value: unknown,
  init?: RequestInit,
  status = 200,
  replayed?: boolean,
) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "private, no-store",
      "X-Request-ID": new Headers(init?.headers).get("X-Request-ID") ?? "",
      "X-Trace-ID": "trace-setup",
      ...(replayed === undefined
        ? {}
        : { "Idempotency-Replayed": String(replayed) }),
    },
  });
}
function catalog(): SetupOptions {
  return {
    projectId: context.projectId,
    projectVersion: context.projectVersion,
    nextCursor: null,
    policies: [
      {
        reference,
        title: "Test policy",
        roleKeys: ["engineering"],
        wbsLifecycle: {
          initialStateKey: "not_started",
          states: [
            { key: "not_started", labelSource: "Not started", terminal: false },
            { key: "completed", labelSource: "Completed", terminal: true },
          ],
        },
      },
    ],
  };
}
afterEach(() => {
  vi.unstubAllGlobals();
});
describe("Project setup transport", () => {
  it("initializes role definitions without sending people or dates and rejects an unbound response", async () => {
    const source = new LiveProjectSetupDataSource();
    let value = {
      ...context,
      projectVersion: context.projectVersion + 1,
      baselineComparison: context.baselineComparison
        ? {
            ...context.baselineComparison,
            currentProjectVersion: context.projectVersion + 1,
          }
        : null,
    };
    const fetcher = vi.fn<typeof fetch>((_, init) =>
      Promise.resolve(response(value, init, 200, false)),
    );
    vi.stubGlobal("fetch", fetcher);
    const command = {
      kind: "roles",
      body: {
        expectedProjectVersion: context.projectVersion,
        workPolicyRef: reference,
      },
    } as const;
    await expect(
      source.execute(context.projectId, command, request()),
    ).resolves.toMatchObject({
      projectVersion: context.projectVersion + 1,
      context: value,
      replayed: false,
    });
    const call = fetcher.mock.calls[0];
    if (!call) throw new Error("Expected a role initialization request");
    const [url, init] = call;
    expect(url).toContain(":initialize-work-roles");
    if (typeof init?.body !== "string")
      throw new Error("Expected a JSON role initialization command");
    expect(JSON.parse(init.body)).toEqual(command.body);
    value = { ...value, initialized: false };
    await expect(
      source.execute(context.projectId, command, request()),
    ).rejects.toBeInstanceOf(NpiTransportError);
  });
  it("accepts only an exact correlated catalog and rejects stale versions, extra fields and unregistered states", async () => {
    const source = new LiveProjectSetupDataSource();
    let value: unknown = catalog();
    const fetcher = vi.fn<typeof fetch>((_, init) =>
      Promise.resolve(response(value, init)),
    );
    vi.stubGlobal("fetch", fetcher);
    await expect(
      source.loadOptions(
        context.projectId,
        context.projectVersion,
        request().signal,
      ),
    ).resolves.toEqual(value);
    for (const invalid of [
      { ...catalog(), projectVersion: context.projectVersion + 1 },
      { ...catalog(), privateData: "unexpected" },
      {
        ...catalog(),
        policies: [
          {
            ...catalog().policies[0],
            wbsLifecycle: {
              initialStateKey: "open",
              states: [
                { key: "open", labelSource: "Unregistered", terminal: false },
              ],
            },
          },
        ],
      },
    ]) {
      value = invalid;
      await expect(
        source.loadOptions(
          context.projectId,
          context.projectVersion,
          request().signal,
        ),
      ).rejects.toBeInstanceOf(NpiTransportError);
    }
    expect(fetcher).toHaveBeenCalledTimes(4);
  });
  it("does not report a team save as successful when the server retained different member details", async () => {
    const member = context.members[0];
    if (!member) throw new Error("Expected an existing member");
    const source = new LiveProjectSetupDataSource();
    let members = context.members;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((_, init) =>
        Promise.resolve(
          response(
            {
              ...context,
              projectVersion: context.projectVersion + 1,
              members,
              baselineComparison: context.baselineComparison
                ? {
                    ...context.baselineComparison,
                    currentProjectVersion: context.projectVersion + 1,
                  }
                : null,
            },
            init,
            200,
            false,
          ),
        ),
      ),
    );
    const command = {
      kind: "team",
      body: {
        expectedProjectVersion: context.projectVersion,
        workPolicyRef: reference,
        members: [
          {
            globalId: member.globalId,
            userId: member.userId,
            effectiveFrom: member.effectiveFrom,
          },
        ],
        roleAssignments: [],
        substitutions: [],
        raciAssignments: [],
      },
    } as const;
    await expect(
      source.execute(context.projectId, command, request()),
    ).resolves.toMatchObject({ projectVersion: context.projectVersion + 1 });
    members = context.members.map((value) =>
      value.globalId === member.globalId
        ? { ...value, userId: "different.member@example.invalid" }
        : value,
    );
    await expect(
      source.execute(context.projectId, command, request()),
    ).rejects.toBeInstanceOf(NpiTransportError);
  });
  it("requires the exact baseline label, project version and replay header", async () => {
    const source = new LiveProjectSetupDataSource();
    const retainedBaseline = context.baselines[0];
    if (!retainedBaseline) throw new Error("Expected a baseline fixture");
    const baseline = {
      ...retainedBaseline,
      projectVersion: context.projectVersion,
    };
    let value: unknown = baseline;
    let replay: boolean | undefined = true;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((_, init) =>
        Promise.resolve(response(value, init, 201, replay)),
      ),
    );
    const command = {
      kind: "baseline",
      body: {
        expectedProjectVersion: context.projectVersion,
        workPolicyRef: reference,
        label: baseline.label,
      },
    } as const;
    await expect(
      source.execute(context.projectId, command, request()),
    ).resolves.toEqual({
      projectVersion: context.projectVersion + 1,
      replayed: true,
    });
    value = { ...baseline, label: "Different baseline" };
    await expect(
      source.execute(context.projectId, command, request()),
    ).rejects.toBeInstanceOf(NpiTransportError);
    value = baseline;
    replay = undefined;
    await expect(
      source.execute(context.projectId, command, request()),
    ).rejects.toBeInstanceOf(NpiTransportError);
  });
  it("never accepts a published template from the draft-only command", async () => {
    const source = new LiveProjectSetupDataSource();
    let state = "draft";
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((_, init) =>
        Promise.resolve(
          response(
            {
              projectId: context.projectId,
              projectVersion: context.projectVersion,
              templateGlobalId: reference.globalId,
              policyGlobalId: reference.globalId,
              templateVersion: 1,
              policyVersion: 1,
              publicationState: state,
            },
            init,
            201,
            false,
          ),
        ),
      ),
    );
    const command = {
      expectedProjectVersion: context.projectVersion,
      templateCode: "REVIEW",
      title: "Review",
    };
    await expect(
      source.createDrafts(context.projectId, command, request()),
    ).resolves.toMatchObject({ publicationState: "draft" });
    state = "published";
    await expect(
      source.createDrafts(context.projectId, command, request()),
    ).rejects.toBeInstanceOf(NpiTransportError);
  });
});
