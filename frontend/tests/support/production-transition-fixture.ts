import type {
  ProductionTransitionAcknowledgementCommandResult,
  ProductionTransitionExternalUnavailableProviders,
  ProductionTransitionWorkspace,
} from "../../src/api/production-transition-data-source";

type HandoverView = NonNullable<
  ProductionTransitionWorkspace["currentHandover"]
>;
type HandoverRevision = HandoverView["revision"];
type Acknowledgement = HandoverView["acknowledgements"][number];
type ObservationRevision = NonNullable<
  ProductionTransitionWorkspace["currentObservation"]
>;
type FrozenSlot = HandoverRevision["slots"][number];

const hash = (digit: string): string => digit.repeat(64);

export const productionTransitionIds = {
  currentHandoverRevision: "8810c1d0-ddf7-561c-853b-c9387cbbe2a4",
  currentObservationRevision: "a00bded0-4762-5880-a393-704b32864dc0",
  handover: "81000000-0000-4000-8000-000000000001",
  historicalHandoverRevision: "732b1638-44fb-5c38-b18c-2a22cb562e0f",
  historicalObservationRevision: "23158a14-eb26-5c26-8702-3c3d8d127f24",
  manifestReadiness: "80000000-0000-4000-8000-000000000003",
  manifestReleasedDocument: "81000000-0000-4000-8000-000000000022",
  observation: "82000000-0000-4000-8000-000000000001",
  policyRevision: "80000000-0000-4000-8000-000000000002",
  project: "11111111-1111-4111-8111-111111111111",
  readinessRevision: "80000000-0000-4000-8000-000000000003",
  receiverMember: "80000000-0000-4000-8000-000000000012",
  receiverRole: "80000000-0000-4000-8000-000000000014",
  senderMember: "80000000-0000-4000-8000-000000000011",
  senderRole: "80000000-0000-4000-8000-000000000013",
  unresolvedAction: "80000000-0000-4000-8000-000000000031",
  unresolvedRisk: "80000000-0000-4000-8000-000000000032",
} as const;

export const productionTransitionUsers = {
  receiver: "quality.receiver@example.invalid",
  sender: "npi.sender@example.invalid",
} as const;

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value))
      throw new Error("Unsafe canonical fixture number.");
    return String(value);
  }
  if (Array.isArray(value))
    return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
  if (record(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((field) => `${JSON.stringify(field)}:${canonicalJson(value[field])}`)
      .join(",")}}`;
  }
  throw new Error("Unsupported canonical fixture value.");
}

function bytesToHex(value: Uint8Array<ArrayBuffer>): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

async function digest(
  algorithm: "SHA-1" | "SHA-256",
  value: Uint8Array<ArrayBuffer>,
): Promise<Uint8Array<ArrayBuffer>> {
  return new Uint8Array(
    await globalThis.crypto.subtle.digest(algorithm, value),
  );
}

async function canonicalSha256(value: unknown): Promise<string> {
  return bytesToHex(
    await digest("SHA-256", new TextEncoder().encode(canonicalJson(value))),
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
  const bytes = (await digest("SHA-1", payload)).slice(0, 16);
  const versionByte = bytes[6];
  const variantByte = bytes[8];
  if (versionByte === undefined || variantByte === undefined)
    throw new Error("The fixture UUID digest is incomplete.");
  bytes[6] = (versionByte & 0x0f) | 0x50;
  bytes[8] = (variantByte & 0x3f) | 0x80;
  const hex = bytesToHex(bytes);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function withSnapshotHash<T extends object>(
  value: T,
): Promise<T & { snapshotHash: string }> {
  return { ...value, snapshotHash: await canonicalSha256(value) };
}

function projectSnapshot(): HandoverRevision["project"] {
  return {
    businessCode: "NPI-2026-001",
    customerReferenceKeys: ["ERPNEXT:CUST-001"],
    globalId: productionTransitionIds.project,
    lifecycleState: "active",
    optimisticVersion: 7,
    ownerUserId: "owner@example.invalid",
    projectType: "new_tool",
    targetSopDate: "2026-09-01",
    targetSopState: "planned_only",
    templateRef: {
      globalId: "80000000-0000-4000-8000-000000000041",
      snapshotHash: hash("4"),
      version: 3,
    },
    tenantId: "tenant-a",
    title: "Synthetic production transition",
    workPolicyRef: {
      globalId: "80000000-0000-4000-8000-000000000042",
      snapshotHash: hash("5"),
      version: 2,
    },
  };
}

async function slot(
  direction: "receiver" | "sender",
  userId: string,
  memberGlobalId: string,
  roleGlobalId: string,
): Promise<FrozenSlot> {
  const receiver = direction === "receiver";
  const member: FrozenSlot["member"] = {
    effectiveFrom: "2026-01-01",
    effectiveTo: null,
    globalId: memberGlobalId,
    optimisticVersion: 2,
    projectGlobalId: productionTransitionIds.project,
    tenantId: "tenant-a",
    userId,
  };
  const role: FrozenSlot["role"] = {
    effectiveFrom: "2026-01-01",
    effectiveTo: null,
    globalId: roleGlobalId,
    memberGlobalId,
    optimisticVersion: 3,
    projectGlobalId: productionTransitionIds.project,
    roleKey: receiver ? "production_receiver" : "npi_owner",
    tenantId: "tenant-a",
  };
  return {
    direction,
    groupKey: receiver ? "production_receiver" : "npi_sender",
    member,
    memberSnapshotHash: await canonicalSha256(member),
    role,
    roleSnapshotHash: await canonicalSha256(role),
    slotKey: direction,
  };
}

async function frozenSlots(): Promise<readonly [FrozenSlot, FrozenSlot]> {
  return [
    await slot(
      "sender",
      productionTransitionUsers.sender,
      productionTransitionIds.senderMember,
      productionTransitionIds.senderRole,
    ),
    await slot(
      "receiver",
      productionTransitionUsers.receiver,
      productionTransitionIds.receiverMember,
      productionTransitionIds.receiverRole,
    ),
  ];
}

function readinessReference() {
  return {
    globalId: productionTransitionIds.readinessRevision,
    snapshotHash: hash("e"),
    version: 4,
  };
}

async function handoverRevision(
  version: 1 | 2,
  predecessor: HandoverRevision | null,
): Promise<HandoverRevision> {
  const current = version === 2;
  const project = projectSnapshot();
  const readinessRef = readinessReference();
  const globalId = await uuidV5(
    productionTransitionIds.handover,
    `npi-handover-package-revision:${String(version)}`,
  );
  const revision: Omit<HandoverRevision, "snapshotHash"> = {
    createdAt: current ? "2026-08-14T10:30:00Z" : "2026-08-14T09:00:00Z",
    createdByUserId: "system.manager@example.invalid",
    globalId,
    handoverGlobalId: productionTransitionIds.handover,
    handoverVersion: version,
    manifest: [
      {
        globalId: readinessRef.globalId,
        kind: "readiness_instance_revision",
        requirementKey: "readiness_snapshot",
        role: "technical_readiness",
        snapshotHash: readinessRef.snapshotHash,
        sourceVersion: readinessRef.version,
      },
      {
        globalId: productionTransitionIds.manifestReleasedDocument,
        kind: "released_document",
        requirementKey: "released_trial_summary",
        role: "controlled_release_context",
        snapshotHash: hash("b"),
        sourceVersion: 2,
      },
    ],
    policyRef: {
      globalId: productionTransitionIds.policyRevision,
      snapshotHash: hash("c"),
      version: 1,
    },
    predecessorGlobalId: predecessor?.globalId ?? null,
    predecessorSnapshotHash: predecessor?.snapshotHash ?? null,
    project,
    projectSnapshotHash: await canonicalSha256(project),
    readinessRef,
    reason: current
      ? "Refresh the exact unresolved action set without inheriting acknowledgement facts."
      : "Freeze the exact technical handover package.",
    requestId: current
      ? "81000000-0000-4000-8000-000000000052"
      : "81000000-0000-4000-8000-000000000051",
    schemaVersion: 1,
    slots: await frozenSlots(),
    tenantId: "tenant-a",
    traceId: current
      ? "trace-p706-handover-current"
      : "trace-p706-handover-history",
    unresolvedActionSelector: {
      kinds: ["action", "decision_request", "issue", "risk"],
      mode: "all_non_terminal",
    },
    unresolvedActions: [
      {
        dueDate: "2026-09-10",
        globalId: productionTransitionIds.unresolvedAction,
        kind: "action",
        ownerUserId: "owner@example.invalid",
        snapshotHash: hash("f"),
        sourceVersion: current ? 5 : 4,
        state: "open",
      },
      {
        dueDate: "2026-09-15",
        globalId: productionTransitionIds.unresolvedRisk,
        kind: "risk",
        ownerUserId: "quality.owner@example.invalid",
        snapshotHash: hash("0"),
        sourceVersion: 2,
        state: "mitigating",
      },
    ],
    versionKeyHash: await canonicalSha256({
      handoverGlobalId: productionTransitionIds.handover,
      handoverVersion: version,
    }),
  };
  return withSnapshotHash(revision);
}

function acknowledgementRequestId(
  slotKey: "receiver" | "sender",
  packageVersion: 1 | 2,
): string {
  if (packageVersion === 1)
    return slotKey === "receiver"
      ? "84000000-0000-4000-8000-000000000012"
      : "84000000-0000-4000-8000-000000000011";
  return slotKey === "receiver"
    ? "84000000-0000-4000-8000-000000000022"
    : "84000000-0000-4000-8000-000000000021";
}

async function acknowledgement(
  slotKey: "receiver" | "sender",
  revision: HandoverRevision,
): Promise<Acknowledgement> {
  const receiver = slotKey === "receiver";
  const packageVersion = revision.handoverVersion;
  if (packageVersion !== 1 && packageVersion !== 2)
    throw new Error("The fixture only defines handover versions 1 and 2.");
  const current = packageVersion === 2;
  const frozenSlot = revision.slots.find(
    (candidate) => candidate.slotKey === slotKey,
  );
  if (!frozenSlot) throw new Error(`Fixture slot ${slotKey} is missing.`);
  const value: Omit<Acknowledgement, "snapshotHash"> = {
    acknowledgedAt: current
      ? receiver
        ? "2026-08-14T11:20:00Z"
        : "2026-08-14T11:00:00Z"
      : receiver
        ? "2026-08-14T10:00:00Z"
        : "2026-08-14T09:45:00Z",
    acknowledgementIntent: "acknowledge_exact_package_slot",
    actorUserId: frozenSlot.member.userId,
    globalId: await uuidV5(
      revision.globalId,
      `npi-handover-acknowledgement:${slotKey}`,
    ),
    handoverGlobalId: revision.handoverGlobalId,
    memberGlobalId: frozenSlot.member.globalId,
    memberOptimisticVersion: frozenSlot.member.optimisticVersion,
    memberSnapshotHash: frozenSlot.memberSnapshotHash,
    packageRevisionGlobalId: revision.globalId,
    packageSnapshotHash: revision.snapshotHash,
    packageVersion,
    requestId: acknowledgementRequestId(slotKey, packageVersion),
    roleGlobalId: frozenSlot.role.globalId,
    roleOptimisticVersion: frozenSlot.role.optimisticVersion,
    roleSnapshotHash: frozenSlot.roleSnapshotHash,
    schemaVersion: 1,
    slotKey,
    traceId: receiver ? "trace-p706-ack-receiver" : "trace-p706-ack-sender",
  };
  return withSnapshotHash(value);
}

export const productionTransitionUnavailableProviders = [
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
] as const satisfies ProductionTransitionExternalUnavailableProviders;

async function observationRevision(
  version: 1 | 2,
  predecessor: ObservationRevision | null,
  handover: HandoverRevision,
): Promise<ObservationRevision> {
  const current = version === 2;
  const project = projectSnapshot();
  const readinessRef = readinessReference();
  const revision: Omit<ObservationRevision, "snapshotHash"> = {
    authorityBoundary: "technical_observation_only",
    contextReferences: [
      {
        globalId: readinessRef.globalId,
        kind: "readiness_instance_revision",
        snapshotHash: readinessRef.snapshotHash,
        sourceVersion: readinessRef.version,
        usage: "context",
      },
    ],
    createdAt: current ? "2026-08-14T12:00:00Z" : "2026-08-14T11:30:00Z",
    createdByUserId: "system.manager@example.invalid",
    globalId: await uuidV5(
      productionTransitionIds.observation,
      `npi-observation-period-revision:${String(version)}`,
    ),
    handoverPackageRef: {
      globalId: handover.globalId,
      snapshotHash: handover.snapshotHash,
      version: handover.handoverVersion,
    },
    observationGlobalId: productionTransitionIds.observation,
    observationState: "not_evaluable",
    observationVersion: version,
    observedEndDate: null,
    observedStartDate: null,
    policyRef: {
      globalId: productionTransitionIds.policyRevision,
      snapshotHash: hash("c"),
      version: 1,
    },
    predecessorGlobalId: predecessor?.globalId ?? null,
    predecessorSnapshotHash: predecessor?.snapshotHash ?? null,
    project,
    projectSnapshotHash: await canonicalSha256(project),
    providers: productionTransitionUnavailableProviders,
    reason: current
      ? "Append the exact retrospective context without claiming production actuals."
      : "Create the independent technical observation period.",
    requestId: current
      ? "82000000-0000-4000-8000-000000000052"
      : "82000000-0000-4000-8000-000000000051",
    retrospectiveNote: current
      ? "The retained evidence is NPI context, not an external production result."
      : null,
    retrospectiveReferences: current
      ? [
          {
            globalId: productionTransitionIds.manifestReleasedDocument,
            kind: "released_document",
            snapshotHash: hash("b"),
            sourceVersion: 2,
            usage: "retrospective",
          },
        ]
      : [],
    schemaVersion: 1,
    technicalDisposition: "not_evaluable",
    tenantId: "tenant-a",
    traceId: current
      ? "trace-p706-observation-current"
      : "trace-p706-observation-history",
    versionKeyHash: await canonicalSha256({
      observationGlobalId: productionTransitionIds.observation,
      observationVersion: version,
    }),
  };
  return withSnapshotHash(revision);
}

interface ProductionTransitionFixtureModel {
  currentHandover: HandoverRevision;
  currentObservation: ObservationRevision;
  historicalHandover: HandoverRevision;
  historicalObservation: ObservationRevision;
  receiverCurrentAcknowledgement: Acknowledgement;
  receiverHistoricalAcknowledgement: Acknowledgement;
  senderCurrentAcknowledgement: Acknowledgement;
  senderHistoricalAcknowledgement: Acknowledgement;
}

async function fixtureModel(): Promise<ProductionTransitionFixtureModel> {
  const historicalHandover = await handoverRevision(1, null);
  const currentHandover = await handoverRevision(2, historicalHandover);
  const historicalObservation = await observationRevision(
    1,
    null,
    historicalHandover,
  );
  const currentObservation = await observationRevision(
    2,
    historicalObservation,
    currentHandover,
  );
  return {
    currentHandover,
    currentObservation,
    historicalHandover,
    historicalObservation,
    receiverCurrentAcknowledgement: await acknowledgement(
      "receiver",
      currentHandover,
    ),
    receiverHistoricalAcknowledgement: await acknowledgement(
      "receiver",
      historicalHandover,
    ),
    senderCurrentAcknowledgement: await acknowledgement(
      "sender",
      currentHandover,
    ),
    senderHistoricalAcknowledgement: await acknowledgement(
      "sender",
      historicalHandover,
    ),
  };
}

function workspaceFromModel(
  model: ProductionTransitionFixtureModel,
  currentAcknowledged: boolean,
): ProductionTransitionWorkspace {
  const historicalView: HandoverView = {
    acknowledgements: [
      model.senderHistoricalAcknowledgement,
      model.receiverHistoricalAcknowledgement,
    ],
    fullyAcknowledged: true,
    revision: model.historicalHandover,
  };
  const currentView: HandoverView = {
    acknowledgements: currentAcknowledged
      ? [
          model.senderCurrentAcknowledgement,
          model.receiverCurrentAcknowledgement,
        ]
      : [model.senderCurrentAcknowledgement],
    fullyAcknowledged: currentAcknowledged,
    revision: model.currentHandover,
  };
  return {
    currentHandover: currentView,
    currentObservation: model.currentObservation,
    handoverHistory: [historicalView, currentView],
    observationHistory: [model.historicalObservation, model.currentObservation],
    permissions: {
      canAcknowledgeSlots: currentAcknowledged ? [] : ["receiver"],
      canCreateHandover: false,
      canCreateObservation: false,
      canManagePolicies: false,
      canReviseHandover: false,
      canReviseObservation: false,
    },
    projectGlobalId: productionTransitionIds.project,
    unavailableProviders: productionTransitionUnavailableProviders,
  };
}

export async function productionTransitionWorkspace(): Promise<ProductionTransitionWorkspace> {
  return workspaceFromModel(await fixtureModel(), false);
}

export function productionTransitionEmptyWorkspace(): ProductionTransitionWorkspace {
  return {
    currentHandover: null,
    currentObservation: null,
    handoverHistory: [],
    observationHistory: [],
    permissions: {
      canAcknowledgeSlots: [],
      canCreateHandover: false,
      canCreateObservation: false,
      canManagePolicies: false,
      canReviseHandover: false,
      canReviseObservation: false,
    },
    projectGlobalId: productionTransitionIds.project,
    unavailableProviders: productionTransitionUnavailableProviders,
  };
}

export async function productionTransitionAcknowledgedWorkspace(): Promise<ProductionTransitionWorkspace> {
  return workspaceFromModel(await fixtureModel(), true);
}

export async function productionTransitionAcknowledgementResult(
  replayed = false,
): Promise<ProductionTransitionAcknowledgementCommandResult> {
  const model = await fixtureModel();
  return {
    acknowledgement: model.receiverCurrentAcknowledgement,
    handoverPackage: model.currentHandover,
    projectGlobalId: productionTransitionIds.project,
    replayed,
  };
}
