import { NpiHttpClient, NpiTransportError } from "./http";

export const productionTransitionSourceKinds = [
  "readiness_instance_revision",
  "domain_work_item",
  "released_document",
  "release_baseline",
  "file_revision",
  "tooling_capacity_scenario",
  "trial_defect_revision",
  "trial_review_reference",
  "trial_conclusion",
] as const;
export type ProductionTransitionSourceKind =
  (typeof productionTransitionSourceKinds)[number];

export const productionTransitionProviderKinds = [
  "actual_sop",
  "first_batch_yield",
  "customer_complaint",
  "production_cycle_time",
  "tooling_stability",
] as const;
export type ProductionTransitionProviderKind =
  (typeof productionTransitionProviderKinds)[number];

export type ProductionTransitionProjectType =
  | "customer_owned_tool"
  | "new_tool"
  | "tool_change";
export type ProductionTransitionAcknowledgementDirection =
  | "sender"
  | "receiver";
export type ProductionTransitionWorkItemKind =
  | "action"
  | "decision_request"
  | "issue"
  | "risk";

export interface ProductionTransitionExactVersionReference {
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface ProductionTransitionProjectSnapshot {
  globalId: string;
  tenantId: string;
  optimisticVersion: number;
  businessCode: string;
  title: string;
  projectType: ProductionTransitionProjectType;
  ownerUserId: string;
  targetSopDate: string | null;
  targetSopState: "planned_only";
  lifecycleState: string;
  templateRef: ProductionTransitionExactVersionReference;
  workPolicyRef: ProductionTransitionExactVersionReference;
  customerReferenceKeys: readonly string[];
}

export interface ProductionTransitionMemberSnapshot {
  globalId: string;
  tenantId: string;
  projectGlobalId: string;
  userId: string;
  effectiveFrom: string;
  effectiveTo: string | null;
  optimisticVersion: number;
}

export interface ProductionTransitionRoleSnapshot {
  globalId: string;
  tenantId: string;
  projectGlobalId: string;
  memberGlobalId: string;
  roleKey: string;
  effectiveFrom: string;
  effectiveTo: string | null;
  optimisticVersion: number;
}

export interface ProductionTransitionFrozenSlot {
  slotKey: string;
  groupKey: string;
  direction: ProductionTransitionAcknowledgementDirection;
  member: ProductionTransitionMemberSnapshot;
  memberSnapshotHash: string;
  role: ProductionTransitionRoleSnapshot;
  roleSnapshotHash: string;
}

export interface ProductionTransitionExactSourceReference {
  requirementKey: string;
  kind: ProductionTransitionSourceKind;
  globalId: string;
  sourceVersion: number;
  snapshotHash: string;
  role: string;
}

export interface ProductionTransitionObservationSourceReference {
  kind: ProductionTransitionSourceKind;
  globalId: string;
  sourceVersion: number;
  snapshotHash: string;
  usage: "context" | "retrospective";
}

export interface ProductionTransitionUnresolvedWorkItemSnapshot {
  globalId: string;
  sourceVersion: number;
  snapshotHash: string;
  kind: ProductionTransitionWorkItemKind;
  state: string;
  ownerUserId: string;
  dueDate: string;
}

export interface HandoverPackageRevision {
  schemaVersion: 1;
  globalId: string;
  handoverGlobalId: string;
  handoverVersion: number;
  versionKeyHash: string;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  tenantId: string;
  project: ProductionTransitionProjectSnapshot;
  projectSnapshotHash: string;
  policyRef: ProductionTransitionExactVersionReference;
  readinessRef: ProductionTransitionExactVersionReference | null;
  slots: readonly ProductionTransitionFrozenSlot[];
  manifest: readonly ProductionTransitionExactSourceReference[];
  unresolvedActionSelector: Readonly<{
    mode: "all_non_terminal";
    kinds: readonly ["action", "decision_request", "issue", "risk"];
  }>;
  unresolvedActions: readonly ProductionTransitionUnresolvedWorkItemSnapshot[];
  reason: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface HandoverAcknowledgement {
  schemaVersion: 1;
  globalId: string;
  handoverGlobalId: string;
  packageRevisionGlobalId: string;
  packageVersion: number;
  packageSnapshotHash: string;
  slotKey: string;
  acknowledgementIntent: "acknowledge_exact_package_slot";
  actorUserId: string;
  memberGlobalId: string;
  memberOptimisticVersion: number;
  memberSnapshotHash: string;
  roleGlobalId: string;
  roleOptimisticVersion: number;
  roleSnapshotHash: string;
  acknowledgedAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface HandoverPackageView {
  revision: HandoverPackageRevision;
  acknowledgements: readonly HandoverAcknowledgement[];
  fullyAcknowledged: boolean;
}

export type ProductionTransitionExternalUnavailableProvider = {
  [Kind in ProductionTransitionProviderKind]: {
    kind: Kind;
    state: "unavailable";
    reasonCode: `${Kind}_provider_unavailable`;
    sourceIdentity: null;
    observedAt: null;
    value: null;
    unit: null;
  };
}[ProductionTransitionProviderKind];

export type ProductionTransitionExternalUnavailableProviders = readonly [
  Extract<
    ProductionTransitionExternalUnavailableProvider,
    { kind: "actual_sop" }
  >,
  Extract<
    ProductionTransitionExternalUnavailableProvider,
    { kind: "first_batch_yield" }
  >,
  Extract<
    ProductionTransitionExternalUnavailableProvider,
    { kind: "customer_complaint" }
  >,
  Extract<
    ProductionTransitionExternalUnavailableProvider,
    { kind: "production_cycle_time" }
  >,
  Extract<
    ProductionTransitionExternalUnavailableProvider,
    { kind: "tooling_stability" }
  >,
];

export interface ObservationPeriodRevision {
  schemaVersion: 1;
  globalId: string;
  observationGlobalId: string;
  observationVersion: number;
  versionKeyHash: string;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  tenantId: string;
  project: ProductionTransitionProjectSnapshot;
  projectSnapshotHash: string;
  policyRef: ProductionTransitionExactVersionReference;
  handoverPackageRef: ProductionTransitionExactVersionReference | null;
  contextReferences: readonly ProductionTransitionObservationSourceReference[];
  retrospectiveReferences: readonly ProductionTransitionObservationSourceReference[];
  providers: ProductionTransitionExternalUnavailableProviders;
  observedStartDate: null;
  observedEndDate: null;
  observationState: "not_evaluable";
  technicalDisposition: "not_evaluable";
  authorityBoundary: "technical_observation_only";
  retrospectiveNote: string | null;
  reason: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface ProductionTransitionPermissions {
  canManagePolicies: boolean;
  canCreateHandover: boolean;
  canReviseHandover: boolean;
  canAcknowledgeSlots: readonly string[];
  canCreateObservation: boolean;
  canReviseObservation: boolean;
}

export interface ProductionTransitionWorkspace {
  projectGlobalId: string;
  currentHandover: HandoverPackageView | null;
  handoverHistory: readonly HandoverPackageView[];
  currentObservation: ObservationPeriodRevision | null;
  observationHistory: readonly ObservationPeriodRevision[];
  unavailableProviders: ProductionTransitionExternalUnavailableProviders;
  permissions: ProductionTransitionPermissions;
}

export interface AcknowledgeProductionHandoverSlotCommand {
  expectedRevisionGlobalId: string;
  expectedSnapshotHash: string;
  slotKey: string;
  intent: "acknowledge";
}

export interface ProductionTransitionCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface ProductionTransitionAcknowledgementCommandResult {
  projectGlobalId: string;
  handoverPackage: HandoverPackageRevision;
  acknowledgement: HandoverAcknowledgement;
  replayed: boolean;
}

export interface ProductionTransitionDataSource {
  loadWorkspace(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ProductionTransitionWorkspace>;
  acknowledgeSlot(
    projectId: string,
    handoverId: string,
    handoverVersion: number,
    command: AcknowledgeProductionHandoverSlotCommand,
    context: ProductionTransitionCommandContext,
  ): Promise<ProductionTransitionAcknowledgementCommandResult>;
}

export class ProductionTransitionRequestCancelledError extends Error {
  constructor() {
    super("The Production Transition request was cancelled.");
    this.name = "ProductionTransitionRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[0-9a-f]{64}$/u;
const codePattern = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$/u;
const keyPattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$/u;
const tenantPattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const tracePattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{7,127}$/u;
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/u;

const sourceKindSet = new Set<ProductionTransitionSourceKind>(
  productionTransitionSourceKinds,
);
const projectTypeSet = new Set<ProductionTransitionProjectType>([
  "customer_owned_tool",
  "new_tool",
  "tool_change",
]);
const directionSet = new Set<ProductionTransitionAcknowledgementDirection>([
  "sender",
  "receiver",
]);
const workItemKindSet = new Set<ProductionTransitionWorkItemKind>([
  "action",
  "decision_request",
  "issue",
  "risk",
]);
const unavailableReasonByKind: Readonly<
  Record<ProductionTransitionProviderKind, string>
> = {
  actual_sop: "actual_sop_provider_unavailable",
  first_batch_yield: "first_batch_yield_provider_unavailable",
  customer_complaint: "customer_complaint_provider_unavailable",
  production_cycle_time: "production_cycle_time_provider_unavailable",
  tooling_stability: "tooling_stability_provider_unavailable",
};
const unresolvedKinds = [
  "action",
  "decision_request",
  "issue",
  "risk",
] as const;

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function exact(
  value: Record<string, unknown>,
  fields: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return (
    keys.length === fields.length &&
    fields.every((field) => Object.hasOwn(value, field))
  );
}

function text(
  value: unknown,
  minimum: number,
  maximum: number,
  pattern?: RegExp,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    value === value.trim() &&
    (pattern?.test(value) ?? true)
  );
}

function member<T extends string>(value: unknown, values: Set<T>): value is T {
  return typeof value === "string" && values.has(value as T);
}

function uuid(value: unknown): value is string {
  return text(value, 36, 36, uuidPattern);
}

function hash(value: unknown): value is string {
  return text(value, 64, 64, hashPattern);
}

function positive(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 1;
}

function boolean(value: unknown): value is boolean {
  return typeof value === "boolean";
}

function array(
  value: unknown,
  minimum: number,
  maximum: number,
): value is readonly unknown[] {
  return (
    Array.isArray(value) && value.length >= minimum && value.length <= maximum
  );
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

function sorted(values: readonly string[]): boolean {
  return values.every(
    (value, index) => index === 0 || String(values[index - 1]) <= value,
  );
}

function date(value: unknown): value is string {
  if (!text(value, 10, 10, datePattern)) return false;
  const [year, month, day] = value.split("-").map(Number);
  if (year === undefined || month === undefined || day === undefined)
    return false;
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

function timestamp(value: unknown): value is string {
  return (
    text(value, 20, 32, timestampPattern) && !Number.isNaN(Date.parse(value))
  );
}

function email(value: unknown): value is string {
  return (
    text(value, 3, 254, emailPattern) && value === value.toLocaleLowerCase("en")
  );
}

function deepEqual(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) && Array.isArray(right))
    return (
      left.length === right.length &&
      left.every((entry, index) => deepEqual(entry, right[index]))
    );
  if (record(left) && record(right)) {
    const leftKeys = Object.keys(left).sort();
    const rightKeys = Object.keys(right).sort();
    return (
      leftKeys.length === rightKeys.length &&
      leftKeys.every(
        (key, index) =>
          key === rightKeys[index] && deepEqual(left[key], right[key]),
      )
    );
  }
  return false;
}

function isExactVersionReference(
  value: unknown,
): value is ProductionTransitionExactVersionReference {
  return (
    record(value) &&
    exact(value, ["globalId", "version", "snapshotHash"]) &&
    uuid(value.globalId) &&
    positive(value.version) &&
    hash(value.snapshotHash)
  );
}

function isProjectSnapshot(
  value: unknown,
): value is ProductionTransitionProjectSnapshot {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "tenantId",
      "optimisticVersion",
      "businessCode",
      "title",
      "projectType",
      "ownerUserId",
      "targetSopDate",
      "targetSopState",
      "lifecycleState",
      "templateRef",
      "workPolicyRef",
      "customerReferenceKeys",
    ]) &&
    uuid(value.globalId) &&
    text(value.tenantId, 1, 128, tenantPattern) &&
    positive(value.optimisticVersion) &&
    text(value.businessCode, 1, 64, codePattern) &&
    text(value.title, 1, 200) &&
    member(value.projectType, projectTypeSet) &&
    email(value.ownerUserId) &&
    (value.targetSopDate === null || date(value.targetSopDate)) &&
    value.targetSopState === "planned_only" &&
    text(value.lifecycleState, 1, 64, keyPattern) &&
    isExactVersionReference(value.templateRef) &&
    isExactVersionReference(value.workPolicyRef) &&
    array(value.customerReferenceKeys, 0, 1000) &&
    value.customerReferenceKeys.every((entry) => text(entry, 1, 256)) &&
    unique(value.customerReferenceKeys) &&
    sorted(value.customerReferenceKeys)
  );
}

function isMemberSnapshot(
  value: unknown,
): value is ProductionTransitionMemberSnapshot {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "tenantId",
      "projectGlobalId",
      "userId",
      "effectiveFrom",
      "effectiveTo",
      "optimisticVersion",
    ]) &&
    uuid(value.globalId) &&
    text(value.tenantId, 1, 128, tenantPattern) &&
    uuid(value.projectGlobalId) &&
    email(value.userId) &&
    date(value.effectiveFrom) &&
    (value.effectiveTo === null || date(value.effectiveTo)) &&
    (value.effectiveTo === null || value.effectiveTo >= value.effectiveFrom) &&
    positive(value.optimisticVersion)
  );
}

function isRoleSnapshot(
  value: unknown,
): value is ProductionTransitionRoleSnapshot {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "tenantId",
      "projectGlobalId",
      "memberGlobalId",
      "roleKey",
      "effectiveFrom",
      "effectiveTo",
      "optimisticVersion",
    ]) &&
    uuid(value.globalId) &&
    text(value.tenantId, 1, 128, tenantPattern) &&
    uuid(value.projectGlobalId) &&
    uuid(value.memberGlobalId) &&
    text(value.roleKey, 1, 128, keyPattern) &&
    date(value.effectiveFrom) &&
    (value.effectiveTo === null || date(value.effectiveTo)) &&
    (value.effectiveTo === null || value.effectiveTo >= value.effectiveFrom) &&
    positive(value.optimisticVersion)
  );
}

function isFrozenSlot(
  value: unknown,
  tenantId: string,
  projectId: string,
): value is ProductionTransitionFrozenSlot {
  if (
    !record(value) ||
    !exact(value, [
      "slotKey",
      "groupKey",
      "direction",
      "member",
      "memberSnapshotHash",
      "role",
      "roleSnapshotHash",
    ]) ||
    !text(value.slotKey, 1, 128, keyPattern) ||
    !text(value.groupKey, 1, 128, keyPattern) ||
    !member(value.direction, directionSet) ||
    !isMemberSnapshot(value.member) ||
    !hash(value.memberSnapshotHash) ||
    !isRoleSnapshot(value.role) ||
    !hash(value.roleSnapshotHash)
  )
    return false;
  return (
    value.member.tenantId === tenantId &&
    value.role.tenantId === tenantId &&
    value.member.projectGlobalId === projectId &&
    value.role.projectGlobalId === projectId &&
    value.role.memberGlobalId === value.member.globalId
  );
}

function isManifestReference(
  value: unknown,
): value is ProductionTransitionExactSourceReference {
  return (
    record(value) &&
    exact(value, [
      "requirementKey",
      "kind",
      "globalId",
      "sourceVersion",
      "snapshotHash",
      "role",
    ]) &&
    text(value.requirementKey, 1, 128, keyPattern) &&
    member(value.kind, sourceKindSet) &&
    uuid(value.globalId) &&
    positive(value.sourceVersion) &&
    hash(value.snapshotHash) &&
    text(value.role, 1, 128, keyPattern)
  );
}

function isObservationReference(
  value: unknown,
  usage: "context" | "retrospective",
): value is ProductionTransitionObservationSourceReference {
  return (
    record(value) &&
    exact(value, [
      "kind",
      "globalId",
      "sourceVersion",
      "snapshotHash",
      "usage",
    ]) &&
    member(value.kind, sourceKindSet) &&
    uuid(value.globalId) &&
    positive(value.sourceVersion) &&
    hash(value.snapshotHash) &&
    value.usage === usage
  );
}

function isUnresolvedAction(
  value: unknown,
): value is ProductionTransitionUnresolvedWorkItemSnapshot {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "sourceVersion",
      "snapshotHash",
      "kind",
      "state",
      "ownerUserId",
      "dueDate",
    ]) &&
    uuid(value.globalId) &&
    positive(value.sourceVersion) &&
    hash(value.snapshotHash) &&
    member(value.kind, workItemKindSet) &&
    text(value.state, 1, 64, keyPattern) &&
    email(value.ownerUserId) &&
    date(value.dueDate)
  );
}

function isUnresolvedSelector(value: unknown): boolean {
  return (
    record(value) &&
    exact(value, ["mode", "kinds"]) &&
    value.mode === "all_non_terminal" &&
    deepEqual(value.kinds, unresolvedKinds)
  );
}

function isHandoverPackageRevision(
  value: unknown,
): value is HandoverPackageRevision {
  if (
    !record(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "handoverGlobalId",
      "handoverVersion",
      "versionKeyHash",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "tenantId",
      "project",
      "projectSnapshotHash",
      "policyRef",
      "readinessRef",
      "slots",
      "manifest",
      "unresolvedActionSelector",
      "unresolvedActions",
      "reason",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) ||
    value.schemaVersion !== 1 ||
    !uuid(value.globalId) ||
    !uuid(value.handoverGlobalId) ||
    !positive(value.handoverVersion) ||
    !hash(value.versionKeyHash) ||
    !(value.predecessorGlobalId === null || uuid(value.predecessorGlobalId)) ||
    !(
      value.predecessorSnapshotHash === null ||
      hash(value.predecessorSnapshotHash)
    ) ||
    (value.handoverVersion === 1) !==
      (value.predecessorGlobalId === null &&
        value.predecessorSnapshotHash === null) ||
    !text(value.tenantId, 1, 128, tenantPattern) ||
    !isProjectSnapshot(value.project) ||
    value.project.tenantId !== value.tenantId ||
    !hash(value.projectSnapshotHash) ||
    !isExactVersionReference(value.policyRef) ||
    !(
      value.readinessRef === null || isExactVersionReference(value.readinessRef)
    ) ||
    !array(value.slots, 2, 100) ||
    !value.slots.every((slot) =>
      isFrozenSlot(
        slot,
        value.tenantId as string,
        (value.project as ProductionTransitionProjectSnapshot).globalId,
      ),
    ) ||
    !array(value.manifest, 0, 1000) ||
    !value.manifest.every(isManifestReference) ||
    !isUnresolvedSelector(value.unresolvedActionSelector) ||
    !array(value.unresolvedActions, 0, 10_000) ||
    !value.unresolvedActions.every(isUnresolvedAction) ||
    !text(value.reason, 1, 1000) ||
    !email(value.createdByUserId) ||
    !timestamp(value.createdAt) ||
    !uuid(value.requestId) ||
    !text(value.traceId, 8, 128, tracePattern) ||
    !hash(value.snapshotHash)
  )
    return false;
  const revision = value as unknown as HandoverPackageRevision;
  if (
    !unique(
      revision.slots.map((slot) => slot.slotKey.toLocaleLowerCase("en")),
    ) ||
    !revision.slots.some((slot) => slot.direction === "sender") ||
    !revision.slots.some((slot) => slot.direction === "receiver") ||
    !unique(
      revision.manifest.map((source) =>
        [source.kind, source.globalId].join("\u0000"),
      ),
    ) ||
    !unique(revision.unresolvedActions.map((action) => action.globalId)) ||
    !sorted(revision.unresolvedActions.map((action) => action.globalId))
  )
    return false;
  return (
    revision.readinessRef === null ||
    revision.manifest.some(
      (source) =>
        source.kind === "readiness_instance_revision" &&
        source.globalId === revision.readinessRef?.globalId &&
        source.sourceVersion === revision.readinessRef.version &&
        source.snapshotHash === revision.readinessRef.snapshotHash,
    )
  );
}

function isAcknowledgement(value: unknown): value is HandoverAcknowledgement {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "globalId",
      "handoverGlobalId",
      "packageRevisionGlobalId",
      "packageVersion",
      "packageSnapshotHash",
      "slotKey",
      "acknowledgementIntent",
      "actorUserId",
      "memberGlobalId",
      "memberOptimisticVersion",
      "memberSnapshotHash",
      "roleGlobalId",
      "roleOptimisticVersion",
      "roleSnapshotHash",
      "acknowledgedAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) &&
    value.schemaVersion === 1 &&
    uuid(value.globalId) &&
    uuid(value.handoverGlobalId) &&
    uuid(value.packageRevisionGlobalId) &&
    positive(value.packageVersion) &&
    hash(value.packageSnapshotHash) &&
    text(value.slotKey, 1, 128, keyPattern) &&
    value.acknowledgementIntent === "acknowledge_exact_package_slot" &&
    email(value.actorUserId) &&
    uuid(value.memberGlobalId) &&
    positive(value.memberOptimisticVersion) &&
    hash(value.memberSnapshotHash) &&
    uuid(value.roleGlobalId) &&
    positive(value.roleOptimisticVersion) &&
    hash(value.roleSnapshotHash) &&
    timestamp(value.acknowledgedAt) &&
    uuid(value.requestId) &&
    text(value.traceId, 8, 128, tracePattern) &&
    hash(value.snapshotHash)
  );
}

function acknowledgementMatchesPackage(
  acknowledgement: HandoverAcknowledgement,
  packageRevision: HandoverPackageRevision,
): boolean {
  const slot = packageRevision.slots.find(
    (candidate) => candidate.slotKey === acknowledgement.slotKey,
  );
  if (!slot) return false;
  const acknowledgedDate = acknowledgement.acknowledgedAt.slice(0, 10);
  const memberEffective =
    slot.member.effectiveFrom <= acknowledgedDate &&
    (slot.member.effectiveTo === null ||
      acknowledgedDate <= slot.member.effectiveTo);
  const roleEffective =
    slot.role.effectiveFrom <= acknowledgedDate &&
    (slot.role.effectiveTo === null ||
      acknowledgedDate <= slot.role.effectiveTo);
  return (
    acknowledgement.handoverGlobalId === packageRevision.handoverGlobalId &&
    acknowledgement.packageRevisionGlobalId === packageRevision.globalId &&
    acknowledgement.packageVersion === packageRevision.handoverVersion &&
    acknowledgement.packageSnapshotHash === packageRevision.snapshotHash &&
    acknowledgement.actorUserId === slot.member.userId &&
    acknowledgement.memberGlobalId === slot.member.globalId &&
    acknowledgement.memberOptimisticVersion === slot.member.optimisticVersion &&
    acknowledgement.memberSnapshotHash === slot.memberSnapshotHash &&
    acknowledgement.roleGlobalId === slot.role.globalId &&
    acknowledgement.roleOptimisticVersion === slot.role.optimisticVersion &&
    acknowledgement.roleSnapshotHash === slot.roleSnapshotHash &&
    memberEffective &&
    roleEffective
  );
}

function isHandoverView(value: unknown): value is HandoverPackageView {
  if (
    !record(value) ||
    !exact(value, ["revision", "acknowledgements", "fullyAcknowledged"]) ||
    !isHandoverPackageRevision(value.revision) ||
    !array(value.acknowledgements, 0, 100) ||
    !value.acknowledgements.every(isAcknowledgement) ||
    !boolean(value.fullyAcknowledged)
  )
    return false;
  const view = value as unknown as HandoverPackageView;
  const slots = view.revision.slots.map((slot) => slot.slotKey);
  const acknowledgementSlots = view.acknowledgements.map(
    (acknowledgement) => acknowledgement.slotKey,
  );
  return (
    unique(
      view.acknowledgements.map((acknowledgement) => acknowledgement.globalId),
    ) &&
    unique(acknowledgementSlots) &&
    view.acknowledgements.every((acknowledgement) =>
      acknowledgementMatchesPackage(acknowledgement, view.revision),
    ) &&
    view.fullyAcknowledged ===
      (slots.length > 0 &&
        acknowledgementSlots.length === slots.length &&
        slots.every((slot) => acknowledgementSlots.includes(slot)))
  );
}

function isUnavailableProvider(
  value: unknown,
  expectedKind: ProductionTransitionProviderKind,
): value is ProductionTransitionExternalUnavailableProvider {
  return (
    record(value) &&
    exact(value, [
      "kind",
      "state",
      "reasonCode",
      "sourceIdentity",
      "observedAt",
      "value",
      "unit",
    ]) &&
    value.kind === expectedKind &&
    value.state === "unavailable" &&
    value.reasonCode === unavailableReasonByKind[expectedKind] &&
    value.sourceIdentity === null &&
    value.observedAt === null &&
    value.value === null &&
    value.unit === null
  );
}

function isUnavailableProviders(
  value: unknown,
): value is ProductionTransitionExternalUnavailableProviders {
  return (
    array(value, 5, 5) &&
    value.every((provider, index) => {
      const expectedKind = productionTransitionProviderKinds[index];
      return (
        expectedKind !== undefined &&
        isUnavailableProvider(provider, expectedKind)
      );
    })
  );
}

function isObservationRevision(
  value: unknown,
): value is ObservationPeriodRevision {
  if (
    !record(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "observationGlobalId",
      "observationVersion",
      "versionKeyHash",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "tenantId",
      "project",
      "projectSnapshotHash",
      "policyRef",
      "handoverPackageRef",
      "contextReferences",
      "retrospectiveReferences",
      "providers",
      "observedStartDate",
      "observedEndDate",
      "observationState",
      "technicalDisposition",
      "authorityBoundary",
      "retrospectiveNote",
      "reason",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) ||
    value.schemaVersion !== 1 ||
    !uuid(value.globalId) ||
    !uuid(value.observationGlobalId) ||
    !positive(value.observationVersion) ||
    !hash(value.versionKeyHash) ||
    !(value.predecessorGlobalId === null || uuid(value.predecessorGlobalId)) ||
    !(
      value.predecessorSnapshotHash === null ||
      hash(value.predecessorSnapshotHash)
    ) ||
    (value.observationVersion === 1) !==
      (value.predecessorGlobalId === null &&
        value.predecessorSnapshotHash === null) ||
    !text(value.tenantId, 1, 128, tenantPattern) ||
    !isProjectSnapshot(value.project) ||
    value.project.tenantId !== value.tenantId ||
    !hash(value.projectSnapshotHash) ||
    !isExactVersionReference(value.policyRef) ||
    !(
      value.handoverPackageRef === null ||
      isExactVersionReference(value.handoverPackageRef)
    ) ||
    !array(value.contextReferences, 0, 1000) ||
    !value.contextReferences.every((entry) =>
      isObservationReference(entry, "context"),
    ) ||
    !array(value.retrospectiveReferences, 0, 1000) ||
    !value.retrospectiveReferences.every((entry) =>
      isObservationReference(entry, "retrospective"),
    ) ||
    !isUnavailableProviders(value.providers) ||
    value.observedStartDate !== null ||
    value.observedEndDate !== null ||
    value.observationState !== "not_evaluable" ||
    value.technicalDisposition !== "not_evaluable" ||
    value.authorityBoundary !== "technical_observation_only" ||
    !(
      value.retrospectiveNote === null || text(value.retrospectiveNote, 1, 4000)
    ) ||
    !text(value.reason, 1, 1000) ||
    !email(value.createdByUserId) ||
    !timestamp(value.createdAt) ||
    !uuid(value.requestId) ||
    !text(value.traceId, 8, 128, tracePattern) ||
    !hash(value.snapshotHash)
  )
    return false;
  const revision = value as unknown as ObservationPeriodRevision;
  const contextKeys = revision.contextReferences.map((reference) =>
    [reference.kind, reference.globalId].join("\u0000"),
  );
  const retrospectiveKeys = revision.retrospectiveReferences.map((reference) =>
    [reference.kind, reference.globalId].join("\u0000"),
  );
  if (!unique(contextKeys) || !unique(retrospectiveKeys)) return false;
  const contextByKey = new Map(
    revision.contextReferences.map((reference) => [
      [reference.kind, reference.globalId].join("\u0000"),
      reference,
    ]),
  );
  return revision.retrospectiveReferences.every((reference) => {
    const context = contextByKey.get(
      [reference.kind, reference.globalId].join("\u0000"),
    );
    return (
      context === undefined ||
      (context.sourceVersion === reference.sourceVersion &&
        context.snapshotHash === reference.snapshotHash)
    );
  });
}

function isPermissions(
  value: unknown,
  currentHandover: HandoverPackageView | null,
): value is ProductionTransitionPermissions {
  if (
    !record(value) ||
    !exact(value, [
      "canManagePolicies",
      "canCreateHandover",
      "canReviseHandover",
      "canAcknowledgeSlots",
      "canCreateObservation",
      "canReviseObservation",
    ]) ||
    !boolean(value.canManagePolicies) ||
    !boolean(value.canCreateHandover) ||
    !boolean(value.canReviseHandover) ||
    !array(value.canAcknowledgeSlots, 0, 100) ||
    !value.canAcknowledgeSlots.every((slot) =>
      text(slot, 1, 128, keyPattern),
    ) ||
    !unique(value.canAcknowledgeSlots) ||
    !sorted(value.canAcknowledgeSlots) ||
    !boolean(value.canCreateObservation) ||
    !boolean(value.canReviseObservation)
  )
    return false;
  const availableSlots = new Set(
    currentHandover?.revision.slots.map((slot) => slot.slotKey) ?? [],
  );
  const acknowledgedSlots = new Set(
    currentHandover?.acknowledgements.map(
      (acknowledgement) => acknowledgement.slotKey,
    ) ?? [],
  );
  return value.canAcknowledgeSlots.every(
    (slot) => availableSlots.has(slot) && !acknowledgedSlots.has(slot),
  );
}

function handoverSuccessor(
  current: HandoverPackageRevision,
  successor: HandoverPackageRevision,
): boolean {
  return (
    successor.handoverGlobalId === current.handoverGlobalId &&
    successor.tenantId === current.tenantId &&
    successor.project.globalId === current.project.globalId &&
    successor.handoverVersion === current.handoverVersion + 1 &&
    successor.predecessorGlobalId === current.globalId &&
    successor.predecessorSnapshotHash === current.snapshotHash
  );
}

function observationSuccessor(
  current: ObservationPeriodRevision,
  successor: ObservationPeriodRevision,
): boolean {
  return (
    successor.observationGlobalId === current.observationGlobalId &&
    successor.tenantId === current.tenantId &&
    successor.project.globalId === current.project.globalId &&
    successor.observationVersion === current.observationVersion + 1 &&
    successor.predecessorGlobalId === current.globalId &&
    successor.predecessorSnapshotHash === current.snapshotHash
  );
}

export function isProductionTransitionWorkspace(
  value: unknown,
): value is ProductionTransitionWorkspace {
  if (
    !record(value) ||
    !exact(value, [
      "projectGlobalId",
      "currentHandover",
      "handoverHistory",
      "currentObservation",
      "observationHistory",
      "unavailableProviders",
      "permissions",
    ]) ||
    !uuid(value.projectGlobalId) ||
    !(
      value.currentHandover === null || isHandoverView(value.currentHandover)
    ) ||
    !array(value.handoverHistory, 0, 1000) ||
    !value.handoverHistory.every(isHandoverView) ||
    !(
      value.currentObservation === null ||
      isObservationRevision(value.currentObservation)
    ) ||
    !array(value.observationHistory, 0, 1000) ||
    !value.observationHistory.every(isObservationRevision) ||
    !isUnavailableProviders(value.unavailableProviders)
  )
    return false;
  const workspace = value as unknown as ProductionTransitionWorkspace;
  const handoverRevisions = workspace.handoverHistory.map(
    (view) => view.revision,
  );
  const observationRevisions = workspace.observationHistory;
  if (
    handoverRevisions.some(
      (revision) => revision.project.globalId !== workspace.projectGlobalId,
    ) ||
    observationRevisions.some(
      (revision) => revision.project.globalId !== workspace.projectGlobalId,
    ) ||
    (handoverRevisions.length > 0 &&
      handoverRevisions[0]?.handoverVersion !== 1) ||
    (observationRevisions.length > 0 &&
      observationRevisions[0]?.observationVersion !== 1) ||
    !unique(handoverRevisions.map((revision) => revision.globalId)) ||
    !unique(observationRevisions.map((revision) => revision.globalId)) ||
    new Set(handoverRevisions.map((revision) => revision.handoverGlobalId))
      .size > 1 ||
    new Set(
      observationRevisions.map((revision) => revision.observationGlobalId),
    ).size > 1 ||
    handoverRevisions.some((revision, index) => {
      const previous = handoverRevisions[index - 1];
      return index > 0 && (!previous || !handoverSuccessor(previous, revision));
    }) ||
    observationRevisions.some((revision, index) => {
      const previous = observationRevisions[index - 1];
      return (
        index > 0 && (!previous || !observationSuccessor(previous, revision))
      );
    }) ||
    (workspace.currentHandover === null) !==
      (workspace.handoverHistory.length === 0) ||
    (workspace.currentHandover !== null &&
      !deepEqual(
        workspace.currentHandover,
        workspace.handoverHistory.at(-1),
      )) ||
    (workspace.currentObservation === null) !==
      (workspace.observationHistory.length === 0) ||
    (workspace.currentObservation !== null &&
      !deepEqual(
        workspace.currentObservation,
        workspace.observationHistory.at(-1),
      )) ||
    (handoverRevisions[0]?.handoverGlobalId !== undefined &&
      handoverRevisions[0].handoverGlobalId ===
        observationRevisions[0]?.observationGlobalId) ||
    !isPermissions(workspace.permissions, workspace.currentHandover)
  )
    return false;
  const tenantIds = [
    ...handoverRevisions.map((revision) => revision.tenantId),
    ...observationRevisions.map((revision) => revision.tenantId),
  ];
  if (
    tenantIds.length > 0 &&
    !tenantIds.every((tenant) => tenant === tenantIds[0])
  )
    return false;
  const handoverByRevision = new Map(
    handoverRevisions.map((revision) => [revision.globalId, revision]),
  );
  return observationRevisions.every((observation) => {
    const reference = observation.handoverPackageRef;
    if (reference === null) return true;
    const handover = handoverByRevision.get(reference.globalId);
    return (
      handover?.handoverVersion === reference.version &&
      reference.snapshotHash === handover.snapshotHash
    );
  });
}

function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value))
      throw new Error("Unsafe canonical number.");
    return String(value);
  }
  if (Array.isArray(value))
    return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
  if (record(value)) {
    const fields = Object.keys(value).sort();
    return `{${fields
      .map((field) => `${JSON.stringify(field)}:${canonicalJson(value[field])}`)
      .join(",")}}`;
  }
  throw new Error("Unsupported canonical JSON value.");
}

async function digest(
  algorithm: "SHA-1" | "SHA-256",
  value: Uint8Array<ArrayBuffer>,
): Promise<Uint8Array<ArrayBuffer>> {
  return new Uint8Array(
    await globalThis.crypto.subtle.digest(algorithm, value),
  );
}

function bytesToHex(value: Uint8Array<ArrayBuffer>): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

async function canonicalSha256(value: unknown): Promise<string> {
  return bytesToHex(
    await digest("SHA-256", new TextEncoder().encode(canonicalJson(value))),
  );
}

function withoutField(
  value: Record<string, unknown>,
  omitted: string,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).filter(([field]) => field !== omitted),
  );
}

function uuidBytes(value: string): Uint8Array<ArrayBuffer> {
  const hex = value.replaceAll("-", "");
  const result = new Uint8Array(16);
  for (let index = 0; index < result.length; index += 1)
    result[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
  return result;
}

function concatBytes(
  left: Uint8Array<ArrayBuffer>,
  right: Uint8Array<ArrayBuffer>,
): Uint8Array<ArrayBuffer> {
  const result = new Uint8Array(left.length + right.length);
  result.set(left);
  result.set(right, left.length);
  return result;
}

async function uuidV5(namespace: string, name: string): Promise<string> {
  const bytes = (
    await digest(
      "SHA-1",
      concatBytes(uuidBytes(namespace), new TextEncoder().encode(name)),
    )
  ).slice(0, 16);
  const versionByte = bytes[6];
  const variantByte = bytes[8];
  if (versionByte === undefined || variantByte === undefined)
    throw new Error("The UUID digest is incomplete.");
  bytes[6] = (versionByte & 0x0f) | 0x50;
  bytes[8] = (variantByte & 0x3f) | 0x80;
  const hex = bytesToHex(bytes);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function hasCanonicalProject(
  project: ProductionTransitionProjectSnapshot,
): Promise<boolean> {
  return canonicalSha256(project).then((value) => value.length === 64);
}

async function hasCanonicalHandover(
  view: HandoverPackageView,
  signal?: AbortSignal,
): Promise<boolean> {
  const revision = view.revision;
  const expectedRevisionId = await uuidV5(
    revision.handoverGlobalId,
    `npi-handover-package-revision:${String(revision.handoverVersion)}`,
  );
  if (signal?.aborted || revision.globalId !== expectedRevisionId) return false;
  const expectedVersionKeyHash = await canonicalSha256({
    handoverGlobalId: revision.handoverGlobalId,
    handoverVersion: revision.handoverVersion,
  });
  const expectedProjectHash = await canonicalSha256(revision.project);
  if (
    revision.versionKeyHash !== expectedVersionKeyHash ||
    revision.projectSnapshotHash !== expectedProjectHash ||
    !(await hasCanonicalProject(revision.project))
  )
    return false;
  for (const slot of revision.slots) {
    if (
      signal?.aborted ||
      slot.memberSnapshotHash !== (await canonicalSha256(slot.member)) ||
      slot.roleSnapshotHash !== (await canonicalSha256(slot.role))
    )
      return false;
  }
  const expectedSnapshotHash = await canonicalSha256(
    withoutField(
      revision as unknown as Record<string, unknown>,
      "snapshotHash",
    ),
  );
  if (revision.snapshotHash !== expectedSnapshotHash) return false;
  for (const acknowledgement of view.acknowledgements) {
    const expectedAckId = await uuidV5(
      revision.globalId,
      `npi-handover-acknowledgement:${acknowledgement.slotKey}`,
    );
    const expectedAckHash = await canonicalSha256(
      withoutField(
        acknowledgement as unknown as Record<string, unknown>,
        "snapshotHash",
      ),
    );
    if (
      signal?.aborted ||
      acknowledgement.globalId !== expectedAckId ||
      acknowledgement.snapshotHash !== expectedAckHash
    )
      return false;
  }
  return !signal?.aborted;
}

async function hasCanonicalObservation(
  revision: ObservationPeriodRevision,
  signal?: AbortSignal,
): Promise<boolean> {
  const expectedRevisionId = await uuidV5(
    revision.observationGlobalId,
    `npi-observation-period-revision:${String(revision.observationVersion)}`,
  );
  const expectedVersionKeyHash = await canonicalSha256({
    observationGlobalId: revision.observationGlobalId,
    observationVersion: revision.observationVersion,
  });
  const expectedProjectHash = await canonicalSha256(revision.project);
  const expectedSnapshotHash = await canonicalSha256(
    withoutField(
      revision as unknown as Record<string, unknown>,
      "snapshotHash",
    ),
  );
  return (
    !signal?.aborted &&
    revision.globalId === expectedRevisionId &&
    revision.versionKeyHash === expectedVersionKeyHash &&
    revision.projectSnapshotHash === expectedProjectHash &&
    revision.snapshotHash === expectedSnapshotHash
  );
}

export async function isCanonicalProductionTransitionWorkspace(
  value: unknown,
  signal?: AbortSignal,
): Promise<boolean> {
  if (!isProductionTransitionWorkspace(value)) return false;
  try {
    for (const view of value.handoverHistory) {
      if (signal?.aborted || !(await hasCanonicalHandover(view, signal)))
        return false;
    }
    for (const revision of value.observationHistory) {
      if (signal?.aborted || !(await hasCanonicalObservation(revision, signal)))
        return false;
    }
    return !signal?.aborted;
  } catch {
    return false;
  }
}

function isAcknowledgementCommand(
  value: unknown,
): value is AcknowledgeProductionHandoverSlotCommand {
  return (
    record(value) &&
    exact(value, [
      "expectedRevisionGlobalId",
      "expectedSnapshotHash",
      "slotKey",
      "intent",
    ]) &&
    uuid(value.expectedRevisionGlobalId) &&
    hash(value.expectedSnapshotHash) &&
    text(value.slotKey, 1, 128, keyPattern) &&
    value.intent === "acknowledge"
  );
}

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit < 32 || codeUnit === 127) return true;
  }
  return false;
}

function isContext(value: ProductionTransitionCommandContext): boolean {
  return (
    typeof value.csrfToken === "string" &&
    value.csrfToken.length >= 32 &&
    value.csrfToken.length <= 128 &&
    !hasControlCharacter(value.csrfToken) &&
    idempotencyPattern.test(value.idempotencyKey) &&
    value.signal instanceof AbortSignal
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function invalidResponse(traceId?: string): NpiTransportError {
  return new NpiTransportError(
    "invalid_response",
    traceId ?? `client-${globalThis.crypto.randomUUID()}`,
    traceId ? "trace" : "client",
  );
}

function requireUuid(value: string): string {
  if (!uuid(value)) throw requestNotReady();
  return value;
}

function requirePositive(value: number): number {
  if (!positive(value)) throw requestNotReady();
  return value;
}

function cancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ProductionTransitionRequestCancelledError();
}

function replayHeader(response: Response): boolean | null {
  const header = response.headers.get("Idempotency-Replayed");
  if (header === "true") return true;
  if (header === "false") return false;
  return null;
}

interface AcknowledgementResponse {
  projectGlobalId: string;
  handoverPackage: HandoverPackageRevision;
  acknowledgement: HandoverAcknowledgement;
}

function isAcknowledgementResponse(
  value: unknown,
  projectId: string,
  handoverId: string,
  handoverVersion: number,
  command: AcknowledgeProductionHandoverSlotCommand,
): value is AcknowledgementResponse {
  if (
    !record(value) ||
    !exact(value, ["projectGlobalId", "handoverPackage", "acknowledgement"]) ||
    value.projectGlobalId !== projectId ||
    !isHandoverPackageRevision(value.handoverPackage) ||
    !isAcknowledgement(value.acknowledgement)
  )
    return false;
  const response = value as unknown as AcknowledgementResponse;
  return (
    response.handoverPackage.handoverGlobalId === handoverId &&
    response.handoverPackage.handoverVersion === handoverVersion &&
    response.handoverPackage.globalId === command.expectedRevisionGlobalId &&
    response.handoverPackage.snapshotHash === command.expectedSnapshotHash &&
    response.acknowledgement.slotKey === command.slotKey &&
    acknowledgementMatchesPackage(
      response.acknowledgement,
      response.handoverPackage,
    )
  );
}

async function isCanonicalAcknowledgementResponse(
  value: AcknowledgementResponse,
  signal: AbortSignal,
): Promise<boolean> {
  return hasCanonicalHandover(
    {
      revision: value.handoverPackage,
      acknowledgements: [value.acknowledgement],
      fullyAcknowledged: value.handoverPackage.slots.length === 1,
    },
    signal,
  );
}

export class LiveProductionTransitionDataSource implements ProductionTransitionDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadWorkspace(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ProductionTransitionWorkspace> {
    const expectedProjectId = requireUuid(projectId);
    cancelled(signal);
    try {
      const workspace = await this.http.request<ProductionTransitionWorkspace>(
        `/projects/${expectedProjectId}/production-transition`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ProductionTransitionWorkspace =>
            isProductionTransitionWorkspace(value) &&
            value.projectGlobalId === expectedProjectId,
          validateResponse: (response) => response.status === 200,
        },
      );
      if (!(await isCanonicalProductionTransitionWorkspace(workspace, signal)))
        throw invalidResponse(
          workspace.currentHandover?.revision.traceId ??
            workspace.currentObservation?.traceId,
        );
      return workspace;
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  async acknowledgeSlot(
    projectId: string,
    handoverId: string,
    handoverVersion: number,
    command: AcknowledgeProductionHandoverSlotCommand,
    context: ProductionTransitionCommandContext,
  ): Promise<ProductionTransitionAcknowledgementCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedHandoverId = requireUuid(handoverId);
    const expectedHandoverVersion = requirePositive(handoverVersion);
    if (!isAcknowledgementCommand(command) || !isContext(context))
      throw requestNotReady();
    cancelled(context.signal);
    let replayed = false;
    try {
      const response = await this.http.request<AcknowledgementResponse>(
        `/projects/${expectedProjectId}/production-handover/${expectedHandoverId}/revisions/${String(expectedHandoverVersion)}/acknowledgements`,
        {
          body: JSON.stringify(command),
          headers: { "Idempotency-Key": context.idempotencyKey },
          method: "POST",
          signal: context.signal,
        },
        {
          csrfToken: context.csrfToken,
          requireIdempotencyReplay: true,
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is AcknowledgementResponse =>
            isAcknowledgementResponse(
              value,
              expectedProjectId,
              expectedHandoverId,
              expectedHandoverVersion,
              command,
            ),
          validateResponse: (result) => {
            const header = replayHeader(result);
            if (result.status !== 201 || header === null) return false;
            replayed = header;
            return true;
          },
        },
      );
      if (!(await isCanonicalAcknowledgementResponse(response, context.signal)))
        throw invalidResponse(response.acknowledgement.traceId);
      return { ...response, replayed };
    } catch (error) {
      cancelled(context.signal);
      throw error;
    }
  }
}
