import { afterEach, describe, expect, it, vi } from "vitest";

import { NpiApiError, NpiTransportError } from "../../src/api/http";
import {
  isCanonicalProductionTransitionWorkspace,
  isProductionTransitionWorkspace,
  LiveProductionTransitionDataSource,
  ProductionTransitionRequestCancelledError,
  type AcknowledgeProductionHandoverSlotCommand,
  type HandoverAcknowledgement,
  type HandoverPackageRevision,
  type ObservationPeriodRevision,
  type ProductionTransitionCommandContext,
  type ProductionTransitionExternalUnavailableProviders,
  type ProductionTransitionProjectSnapshot,
  type ProductionTransitionWorkspace,
} from "../../src/api/production-transition-data-source";

const ids = {
  project: "76000000-0000-4000-8000-000000000001",
  handover: "76000000-0000-4000-8000-000000000002",
  observation: "76000000-0000-4000-8000-000000000003",
  template: "76000000-0000-4000-8000-000000000004",
  workPolicy: "76000000-0000-4000-8000-000000000005",
  policy: "76000000-0000-4000-8000-000000000006",
  readiness: "76000000-0000-4000-8000-000000000007",
  senderMember: "76000000-0000-4000-8000-000000000008",
  senderRole: "76000000-0000-4000-8000-000000000009",
  receiverMember: "76000000-0000-4000-8000-00000000000a",
  receiverRole: "76000000-0000-4000-8000-00000000000b",
  unresolved: "76000000-0000-4000-8000-00000000000c",
  source: "76000000-0000-4000-8000-00000000000d",
  handoverRequest: "76000000-0000-4000-8000-00000000000e",
  acknowledgementRequest: "76000000-0000-4000-8000-00000000000f",
  observationRequest: "76000000-0000-4000-8000-000000000010",
} as const;

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (Array.isArray(value))
    return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
  if (record(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((field) => `${JSON.stringify(field)}:${canonicalJson(value[field])}`)
      .join(",")}}`;
  }
  throw new Error("Unsupported fixture value.");
}

function bytesToHex(value: Uint8Array<ArrayBuffer>): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

async function sha256(value: unknown): Promise<string> {
  return bytesToHex(
    new Uint8Array(
      await globalThis.crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(canonicalJson(value)),
      ),
    ),
  );
}

function uuidBytes(value: string): Uint8Array<ArrayBuffer> {
  const raw = value.replaceAll("-", "");
  const result = new Uint8Array(16);
  for (let index = 0; index < result.length; index += 1)
    result[index] = Number.parseInt(raw.slice(index * 2, index * 2 + 2), 16);
  return result;
}

async function uuidV5(namespace: string, name: string): Promise<string> {
  const namespaceBytes = uuidBytes(namespace);
  const nameBytes = new TextEncoder().encode(name);
  const payload = new Uint8Array(namespaceBytes.length + nameBytes.length);
  payload.set(namespaceBytes);
  payload.set(nameBytes, namespaceBytes.length);
  const bytes = new Uint8Array(
    await globalThis.crypto.subtle.digest("SHA-1", payload),
  ).slice(0, 16);
  const version = bytes[6];
  const variant = bytes[8];
  if (version === undefined || variant === undefined)
    throw new Error("The fixture UUID digest is incomplete.");
  bytes[6] = (version & 0x0f) | 0x50;
  bytes[8] = (variant & 0x3f) | 0x80;
  const hex = bytesToHex(bytes);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function withHash<T extends Record<string, unknown>>(
  value: T,
): Promise<T & { snapshotHash: string }> {
  return { ...value, snapshotHash: await sha256(value) };
}

function unavailableProviders(): ProductionTransitionExternalUnavailableProviders {
  return [
    {
      kind: "actual_sop",
      observedAt: null,
      reasonCode: "actual_sop_provider_unavailable",
      sourceIdentity: null,
      state: "unavailable",
      unit: null,
      value: null,
    },
    {
      kind: "first_batch_yield",
      observedAt: null,
      reasonCode: "first_batch_yield_provider_unavailable",
      sourceIdentity: null,
      state: "unavailable",
      unit: null,
      value: null,
    },
    {
      kind: "customer_complaint",
      observedAt: null,
      reasonCode: "customer_complaint_provider_unavailable",
      sourceIdentity: null,
      state: "unavailable",
      unit: null,
      value: null,
    },
    {
      kind: "production_cycle_time",
      observedAt: null,
      reasonCode: "production_cycle_time_provider_unavailable",
      sourceIdentity: null,
      state: "unavailable",
      unit: null,
      value: null,
    },
    {
      kind: "tooling_stability",
      observedAt: null,
      reasonCode: "tooling_stability_provider_unavailable",
      sourceIdentity: null,
      state: "unavailable",
      unit: null,
      value: null,
    },
  ];
}

interface Fixture {
  workspace: ProductionTransitionWorkspace;
  handover: HandoverPackageRevision;
  acknowledgement: HandoverAcknowledgement;
  command: AcknowledgeProductionHandoverSlotCommand;
}

async function fixture(): Promise<Fixture> {
  const project: ProductionTransitionProjectSnapshot = {
    businessCode: "PRJ-7600",
    customerReferenceKeys: ["customer-program-a"],
    globalId: ids.project,
    lifecycleState: "active",
    optimisticVersion: 4,
    ownerUserId: "project.owner@example.invalid",
    projectType: "new_tool",
    targetSopDate: "2026-11-30",
    targetSopState: "planned_only",
    templateRef: {
      globalId: ids.template,
      snapshotHash: "1".repeat(64),
      version: 2,
    },
    tenantId: "tenant-alpha",
    title: "Valve housing program",
    workPolicyRef: {
      globalId: ids.workPolicy,
      snapshotHash: "2".repeat(64),
      version: 3,
    },
  };
  const senderMember = {
    effectiveFrom: "2026-01-01",
    effectiveTo: null,
    globalId: ids.senderMember,
    optimisticVersion: 2,
    projectGlobalId: ids.project,
    tenantId: "tenant-alpha",
    userId: "sender@example.invalid",
  };
  const senderRole = {
    effectiveFrom: "2026-01-01",
    effectiveTo: null,
    globalId: ids.senderRole,
    memberGlobalId: ids.senderMember,
    optimisticVersion: 3,
    projectGlobalId: ids.project,
    roleKey: "project_engineer",
    tenantId: "tenant-alpha",
  };
  const receiverMember = {
    effectiveFrom: "2026-01-01",
    effectiveTo: null,
    globalId: ids.receiverMember,
    optimisticVersion: 4,
    projectGlobalId: ids.project,
    tenantId: "tenant-alpha",
    userId: "receiver@example.invalid",
  };
  const receiverRole = {
    effectiveFrom: "2026-01-01",
    effectiveTo: null,
    globalId: ids.receiverRole,
    memberGlobalId: ids.receiverMember,
    optimisticVersion: 5,
    projectGlobalId: ids.project,
    roleKey: "production_receiver",
    tenantId: "tenant-alpha",
  };
  const revisionId = await uuidV5(
    ids.handover,
    "npi-handover-package-revision:1",
  );
  const handoverWithoutHash = {
    createdAt: "2026-08-14T09:00:00Z",
    createdByUserId: "system.manager@example.invalid",
    globalId: revisionId,
    handoverGlobalId: ids.handover,
    handoverVersion: 1,
    manifest: [
      {
        globalId: ids.readiness,
        kind: "readiness_instance_revision" as const,
        requirementKey: "readiness_package",
        role: "readiness_evidence",
        snapshotHash: "3".repeat(64),
        sourceVersion: 2,
      },
    ],
    policyRef: {
      globalId: ids.policy,
      snapshotHash: "4".repeat(64),
      version: 1,
    },
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    project,
    projectSnapshotHash: await sha256(project),
    readinessRef: {
      globalId: ids.readiness,
      snapshotHash: "3".repeat(64),
      version: 2,
    },
    reason: "Freeze the exact technical handover set.",
    requestId: ids.handoverRequest,
    schemaVersion: 1 as const,
    slots: [
      {
        direction: "sender" as const,
        groupKey: "npi_sender",
        member: senderMember,
        memberSnapshotHash: await sha256(senderMember),
        role: senderRole,
        roleSnapshotHash: await sha256(senderRole),
        slotKey: "sender_confirm",
      },
      {
        direction: "receiver" as const,
        groupKey: "production_receiver",
        member: receiverMember,
        memberSnapshotHash: await sha256(receiverMember),
        role: receiverRole,
        roleSnapshotHash: await sha256(receiverRole),
        slotKey: "receiver_confirm",
      },
    ],
    tenantId: "tenant-alpha",
    traceId: "trace-handover-fixture",
    unresolvedActionSelector: {
      kinds: ["action", "decision_request", "issue", "risk"] as const,
      mode: "all_non_terminal" as const,
    },
    unresolvedActions: [
      {
        dueDate: "2026-09-01",
        globalId: ids.unresolved,
        kind: "action" as const,
        ownerUserId: "action.owner@example.invalid",
        snapshotHash: "5".repeat(64),
        sourceVersion: 6,
        state: "open",
      },
    ],
    versionKeyHash: await sha256({
      handoverGlobalId: ids.handover,
      handoverVersion: 1,
    }),
  };
  const handover = (await withHash(
    handoverWithoutHash,
  )) as unknown as HandoverPackageRevision;
  const acknowledgementId = await uuidV5(
    handover.globalId,
    "npi-handover-acknowledgement:sender_confirm",
  );
  const acknowledgement = (await withHash({
    acknowledgedAt: "2026-08-14T09:30:00Z",
    acknowledgementIntent: "acknowledge_exact_package_slot" as const,
    actorUserId: senderMember.userId,
    globalId: acknowledgementId,
    handoverGlobalId: ids.handover,
    memberGlobalId: senderMember.globalId,
    memberOptimisticVersion: senderMember.optimisticVersion,
    memberSnapshotHash: await sha256(senderMember),
    packageRevisionGlobalId: handover.globalId,
    packageSnapshotHash: handover.snapshotHash,
    packageVersion: handover.handoverVersion,
    requestId: ids.acknowledgementRequest,
    roleGlobalId: senderRole.globalId,
    roleOptimisticVersion: senderRole.optimisticVersion,
    roleSnapshotHash: await sha256(senderRole),
    schemaVersion: 1 as const,
    slotKey: "sender_confirm",
    traceId: "trace-acknowledgement-fixture",
  })) as unknown as HandoverAcknowledgement;
  const observationId = await uuidV5(
    ids.observation,
    "npi-observation-period-revision:1",
  );
  const observationWithoutHash = {
    authorityBoundary: "technical_observation_only" as const,
    contextReferences: [
      {
        globalId: ids.source,
        kind: "released_document" as const,
        snapshotHash: "6".repeat(64),
        sourceVersion: 7,
        usage: "context" as const,
      },
    ],
    createdAt: "2026-08-14T10:00:00Z",
    createdByUserId: "system.manager@example.invalid",
    globalId: observationId,
    handoverPackageRef: {
      globalId: handover.globalId,
      snapshotHash: handover.snapshotHash,
      version: handover.handoverVersion,
    },
    observationGlobalId: ids.observation,
    observationState: "not_evaluable" as const,
    observationVersion: 1,
    observedEndDate: null,
    observedStartDate: null,
    policyRef: handover.policyRef,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    project,
    projectSnapshotHash: await sha256(project),
    providers: unavailableProviders(),
    reason: "Open the technical observation review.",
    requestId: ids.observationRequest,
    retrospectiveNote: "External actuals remain unavailable.",
    retrospectiveReferences: [
      {
        globalId: ids.source,
        kind: "released_document" as const,
        snapshotHash: "6".repeat(64),
        sourceVersion: 7,
        usage: "retrospective" as const,
      },
    ],
    schemaVersion: 1 as const,
    technicalDisposition: "not_evaluable" as const,
    tenantId: "tenant-alpha",
    traceId: "trace-observation-fixture",
    versionKeyHash: await sha256({
      observationGlobalId: ids.observation,
      observationVersion: 1,
    }),
  };
  const observation = (await withHash(
    observationWithoutHash,
  )) as unknown as ObservationPeriodRevision;
  const handoverView = {
    acknowledgements: [acknowledgement],
    fullyAcknowledged: false,
    revision: handover,
  };
  const workspace: ProductionTransitionWorkspace = {
    currentHandover: handoverView,
    currentObservation: observation,
    handoverHistory: [handoverView],
    observationHistory: [observation],
    permissions: {
      canAcknowledgeSlots: ["receiver_confirm"],
      canCreateHandover: false,
      canCreateObservation: false,
      canManagePolicies: false,
      canReviseHandover: false,
      canReviseObservation: false,
    },
    projectGlobalId: ids.project,
    unavailableProviders: unavailableProviders(),
  };
  return {
    acknowledgement,
    command: {
      expectedRevisionGlobalId: handover.globalId,
      expectedSnapshotHash: handover.snapshotHash,
      intent: "acknowledge",
      slotKey: "sender_confirm",
    },
    handover,
    workspace,
  };
}

function context(
  signal = new AbortController().signal,
): ProductionTransitionCommandContext {
  return {
    csrfToken: "c".repeat(32),
    idempotencyKey: "production-transition-12345678",
    signal,
  };
}

function response(
  value: unknown,
  init: RequestInit | undefined,
  status: number,
  replayed?: boolean,
  headers: Record<string, string> = {},
): Response {
  const requestId = new Headers(init?.headers).get("X-Request-ID") ?? "";
  return new Response(JSON.stringify(value), {
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(replayed === undefined
        ? {}
        : { "Idempotency-Replayed": String(replayed) }),
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-production-transition",
      ...headers,
    },
    status,
  });
}

function requestUrl(request: RequestInfo | URL): string {
  if (typeof request === "string") return request;
  if (request instanceof URL) return request.href;
  return request.url;
}

function requestBody(init: RequestInit | undefined): unknown {
  if (typeof init?.body !== "string")
    throw new Error("The exact acknowledgement body is required.");
  return JSON.parse(init.body) as unknown;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Production Transition response validation", () => {
  it("accepts the exact canonical Project workspace", async () => {
    const value = await fixture();
    expect(isProductionTransitionWorkspace(value.workspace)).toBe(true);
    await expect(
      isCanonicalProductionTransitionWorkspace(value.workspace),
    ).resolves.toBe(true);
  });

  it("rejects closed-record extras at every response layer", async () => {
    const { workspace } = await fixture();
    expect(
      isProductionTransitionWorkspace({ ...workspace, latest: true }),
    ).toBe(false);

    const nested = structuredClone(workspace);
    if (!nested.currentHandover)
      throw new Error("The fixture requires a current handover.");
    Object.assign(nested.currentHandover.revision.project, {
      actualSopDate: "2026-08-14",
    });
    nested.handoverHistory = [nested.currentHandover];
    expect(isProductionTransitionWorkspace(nested)).toBe(false);

    const provider = structuredClone(workspace);
    Object.assign(provider.unavailableProviders[0], { providerId: "latest" });
    expect(isProductionTransitionWorkspace(provider)).toBe(false);
  });

  it("rejects canonical ID/hash drift, current/history mismatch and tenant drift", async () => {
    const { workspace } = await fixture();
    const wrongId = structuredClone(workspace);
    if (!wrongId.currentHandover)
      throw new Error("The fixture requires a current handover.");
    wrongId.currentHandover.revision.globalId = ids.source;
    for (const acknowledgement of wrongId.currentHandover.acknowledgements)
      acknowledgement.packageRevisionGlobalId = ids.source;
    wrongId.handoverHistory = [wrongId.currentHandover];
    if (!wrongId.currentObservation?.handoverPackageRef)
      throw new Error("The fixture requires a handover observation reference.");
    wrongId.currentObservation.handoverPackageRef.globalId = ids.source;
    wrongId.observationHistory = [wrongId.currentObservation];
    expect(isProductionTransitionWorkspace(wrongId)).toBe(true);
    await expect(
      isCanonicalProductionTransitionWorkspace(wrongId),
    ).resolves.toBe(false);

    const wrongHash = structuredClone(workspace);
    if (!wrongHash.currentHandover)
      throw new Error("The fixture requires a current handover.");
    wrongHash.currentHandover.revision.snapshotHash = "f".repeat(64);
    for (const acknowledgement of wrongHash.currentHandover.acknowledgements)
      acknowledgement.packageSnapshotHash = "f".repeat(64);
    wrongHash.handoverHistory = [wrongHash.currentHandover];
    if (!wrongHash.currentObservation?.handoverPackageRef)
      throw new Error("The fixture requires a handover observation reference.");
    wrongHash.currentObservation.handoverPackageRef.snapshotHash = "f".repeat(
      64,
    );
    wrongHash.observationHistory = [wrongHash.currentObservation];
    expect(isProductionTransitionWorkspace(wrongHash)).toBe(true);
    await expect(
      isCanonicalProductionTransitionWorkspace(wrongHash),
    ).resolves.toBe(false);

    const notCurrent = structuredClone(workspace);
    if (!notCurrent.currentHandover)
      throw new Error("The fixture requires a current handover.");
    notCurrent.currentHandover.fullyAcknowledged = true;
    expect(isProductionTransitionWorkspace(notCurrent)).toBe(false);

    const crossTenant = structuredClone(workspace);
    if (!crossTenant.currentObservation)
      throw new Error("The fixture requires a current observation.");
    crossTenant.currentObservation.tenantId = "tenant-beta";
    crossTenant.currentObservation.project.tenantId = "tenant-beta";
    crossTenant.observationHistory = [crossTenant.currentObservation];
    expect(isProductionTransitionWorkspace(crossTenant)).toBe(false);
  });

  it("rejects acknowledgement/slot projection drift and ineligible permissions", async () => {
    const { workspace } = await fixture();
    const actor = structuredClone(workspace);
    const actorHandover = actor.currentHandover;
    const acknowledgement = actorHandover?.acknowledgements[0];
    if (!actorHandover || !acknowledgement)
      throw new Error("The fixture requires one acknowledgement.");
    acknowledgement.actorUserId = "proxy@example.invalid";
    actor.handoverHistory = [actorHandover];
    expect(isProductionTransitionWorkspace(actor)).toBe(false);

    const derived = structuredClone(workspace);
    if (!derived.currentHandover)
      throw new Error("The fixture requires a current handover.");
    derived.currentHandover.fullyAcknowledged = true;
    derived.handoverHistory = [derived.currentHandover];
    expect(isProductionTransitionWorkspace(derived)).toBe(false);

    const permission = structuredClone(workspace);
    permission.permissions.canAcknowledgeSlots = ["unknown_slot"];
    expect(isProductionTransitionWorkspace(permission)).toBe(false);
  });

  it("rejects missing, reordered or caller-populated external providers", async () => {
    const { workspace } = await fixture();
    const missing = structuredClone(workspace);
    missing.unavailableProviders = missing.unavailableProviders.slice(
      0,
      4,
    ) as unknown as ProductionTransitionExternalUnavailableProviders;
    expect(isProductionTransitionWorkspace(missing)).toBe(false);

    const reordered = structuredClone(workspace);
    reordered.unavailableProviders = [
      reordered.unavailableProviders[1],
      reordered.unavailableProviders[0],
      ...reordered.unavailableProviders.slice(2),
    ] as unknown as ProductionTransitionExternalUnavailableProviders;
    expect(isProductionTransitionWorkspace(reordered)).toBe(false);

    const populated = structuredClone(workspace);
    populated.unavailableProviders[0].value = "2026-08-14" as never;
    expect(isProductionTransitionWorkspace(populated)).toBe(false);
  });
});

describe("LiveProductionTransitionDataSource", () => {
  it("loads the exact Project workspace with request/trace and private no-store guards", async () => {
    const { workspace } = await fixture();
    const fetchMock = vi.fn<typeof fetch>((request, init) => {
      expect(requestUrl(request)).toBe(
        `/api/npi/v1/projects/${ids.project}/production-transition`,
      );
      const headers = new Headers(init?.headers);
      expect(headers.has("X-Frappe-CSRF-Token")).toBe(false);
      expect(headers.get("X-Request-ID")).toMatch(/^[0-9a-f-]{36}$/u);
      expect(headers.get("X-Trace-ID")).toMatch(/^trace-/u);
      return Promise.resolve(response(workspace, init, 200));
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      new LiveProductionTransitionDataSource().loadWorkspace(
        ids.project,
        new AbortController().signal,
      ),
    ).resolves.toEqual(workspace);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("posts only the current actor exact-slot command with CSRF/idempotency and keeps reload separate", async () => {
    const value = await fixture();
    const commandContext = context();
    const fetchMock = vi.fn<typeof fetch>((request, init) => {
      expect(requestUrl(request)).toBe(
        `/api/npi/v1/projects/${ids.project}/production-handover/${ids.handover}/revisions/1/acknowledgements`,
      );
      expect(init?.method).toBe("POST");
      const headers = new Headers(init?.headers);
      expect(headers.get("X-Frappe-CSRF-Token")).toBe(commandContext.csrfToken);
      expect(headers.get("Idempotency-Key")).toBe(
        commandContext.idempotencyKey,
      );
      expect(requestBody(init)).toEqual(value.command);
      return Promise.resolve(
        response(
          {
            acknowledgement: value.acknowledgement,
            handoverPackage: value.handover,
            projectGlobalId: ids.project,
          },
          init,
          201,
          false,
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      new LiveProductionTransitionDataSource().acknowledgeSlot(
        ids.project,
        ids.handover,
        1,
        value.command,
        commandContext,
      ),
    ).resolves.toEqual({
      acknowledgement: value.acknowledgement,
      handoverPackage: value.handover,
      projectGlobalId: ids.project,
      replayed: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns replay evidence without changing the exact body or idempotency key", async () => {
    const value = await fixture();
    const commandContext = context();
    const bodies: unknown[] = [];
    const keys: (string | null)[] = [];
    let call = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((_request, init) => {
        bodies.push(requestBody(init));
        keys.push(new Headers(init?.headers).get("Idempotency-Key"));
        const replayed = call > 0;
        call += 1;
        return Promise.resolve(
          response(
            {
              acknowledgement: value.acknowledgement,
              handoverPackage: value.handover,
              projectGlobalId: ids.project,
            },
            init,
            201,
            replayed,
          ),
        );
      }),
    );
    const source = new LiveProductionTransitionDataSource();

    await expect(
      source.acknowledgeSlot(
        ids.project,
        ids.handover,
        1,
        value.command,
        commandContext,
      ),
    ).resolves.toMatchObject({ replayed: false });
    await expect(
      source.acknowledgeSlot(
        ids.project,
        ids.handover,
        1,
        value.command,
        commandContext,
      ),
    ).resolves.toMatchObject({ replayed: true });
    expect(bodies).toEqual([value.command, value.command]);
    expect(keys).toEqual([
      commandContext.idempotencyKey,
      commandContext.idempotencyKey,
    ]);
  });

  it("fails closed for missing transport evidence and invalid command fields", async () => {
    const value = await fixture();
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((_request, init) =>
        Promise.resolve(
          response(value.workspace, init, 200, undefined, {
            "Cache-Control": "private",
          }),
        ),
      ),
    );
    await expect(
      new LiveProductionTransitionDataSource().loadWorkspace(
        ids.project,
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);

    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      new LiveProductionTransitionDataSource().acknowledgeSlot(
        ids.project,
        ids.handover,
        1,
        { ...value.command, intent: "approve" as never },
        context(),
      ),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps an aborted request to the domain cancellation error", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      new LiveProductionTransitionDataSource().loadWorkspace(
        ids.project,
        controller.signal,
      ),
    ).rejects.toBeInstanceOf(ProductionTransitionRequestCancelledError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces a 409 once and never blindly retries the acknowledgement", async () => {
    const value = await fixture();
    const fetchMock = vi.fn<typeof fetch>((_request, init) =>
      Promise.resolve(
        response(
          {
            code: "PRODUCTION_TRANSITION_VERSION_CONFLICT",
            retryable: false,
            status: 409,
            title: "The production transition record changed.",
            traceId: "trace-production-transition",
            type: "/problems/production-transition-version-conflict",
          },
          init,
          409,
          undefined,
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      new LiveProductionTransitionDataSource().acknowledgeSlot(
        ids.project,
        ids.handover,
        1,
        value.command,
        context(),
      ),
    ).rejects.toBeInstanceOf(NpiApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
