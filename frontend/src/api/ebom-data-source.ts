import { NpiHttpClient, NpiTransportError } from "./http";

export type EngineeringBomLifecycleState =
  | "draft"
  | "in_review"
  | "approved"
  | "released";
export type EngineeringBomReviewDecision = "approve" | "reject";
export type EngineeringBomChangeType =
  | "added"
  | "removed"
  | "quantity"
  | "substitution"
  | "attribute";

export interface EngineeringBomProjectViewModel {
  globalId: string;
  businessCode: string;
  title: string;
  lifecycleState: string;
  optimisticVersion: number;
}

export interface EngineeringBomPermissionsViewModel {
  view: boolean;
  create: boolean;
}

export interface EngineeringBomPolicyReferenceViewModel {
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface EngineeringBomPolicyOptionViewModel extends EngineeringBomPolicyReferenceViewModel {
  key: string;
  title: string;
  syntheticNamespace: string;
  quantityScale: number;
  maximumNodes: number;
  engineeringUoms: readonly string[];
  attributeKeys: readonly string[];
}

export interface EngineeringBomRevisionReferenceViewModel {
  globalId: string;
  revisionNumber: number;
  snapshotHash: string;
}

export interface EngineeringBomSummaryViewModel {
  globalId: string;
  engineeringBomKey: string;
  title: string;
  policy: EngineeringBomPolicyReferenceViewModel;
  optimisticVersion: number;
  latestRevision: EngineeringBomRevisionReferenceViewModel | null;
}

export interface EngineeringBomLineInput {
  lineKey: string;
  parentLineKey: string | null;
  engineeringItemId: string;
  description: string;
  quantity: string;
  engineeringUom: string;
  alternateForLineKey: string | null;
  alternateGroupKey: string | null;
  effectivityStart: string | null;
  effectivityEnd: string | null;
  attributes: Readonly<Record<string, string>>;
}

export interface EngineeringBomLineViewModel extends EngineeringBomLineInput {
  globalId: string;
}

export interface EngineeringBomLifecycleViewModel {
  state: EngineeringBomLifecycleState;
  version: number;
  lastEventId: string | null;
}

export interface EngineeringBomLifecycleEventViewModel {
  globalId: string;
  eventType:
    | "review_submitted"
    | "review_approved"
    | "review_rejected"
    | "released";
  fromState: EngineeringBomLifecycleState;
  toState: EngineeringBomLifecycleState;
  fromVersion: number;
  toVersion: number;
  actorUserId: string;
  decision: EngineeringBomReviewDecision | null;
  reason: string | null;
  confirmationIntent: "release_exact_ebom_revision" | null;
  occurredAt: string;
  eventHash: string;
}

export interface EngineeringBomCapabilitiesViewModel {
  revise: boolean;
  submitReview: boolean;
  review: boolean;
  release: boolean;
  compare: boolean;
}

export interface EngineeringBomRevisionViewModel extends EngineeringBomRevisionReferenceViewModel {
  predecessorRevisionId: string | null;
  predecessorSnapshotHash: string | null;
  reason: string;
  effectivityNote: string | null;
  policy: EngineeringBomPolicyReferenceViewModel;
  quantityScale: number;
  lines: readonly EngineeringBomLineViewModel[];
  createdByUserId: string;
  createdAt: string;
  lifecycle: EngineeringBomLifecycleViewModel;
  events: readonly EngineeringBomLifecycleEventViewModel[];
  capabilities: EngineeringBomCapabilitiesViewModel;
}

export interface EngineeringBomListViewModel {
  project: EngineeringBomProjectViewModel;
  permissions: EngineeringBomPermissionsViewModel;
  policies: readonly EngineeringBomPolicyOptionViewModel[];
  items: readonly EngineeringBomSummaryViewModel[];
}

export interface EngineeringBomDetailViewModel {
  project: EngineeringBomProjectViewModel;
  permissions: EngineeringBomPermissionsViewModel;
  policy: EngineeringBomPolicyOptionViewModel;
  ebom: EngineeringBomSummaryViewModel;
  revisions: readonly EngineeringBomRevisionViewModel[];
}

export interface EngineeringBomCommandViewModel {
  ebom: EngineeringBomSummaryViewModel;
  revision: EngineeringBomRevisionViewModel;
}

export interface EngineeringBomDifferenceValueViewModel extends EngineeringBomLineInput {
  globalId: string;
}

export interface EngineeringBomDifferenceViewModel {
  lineKey: string;
  changeType: EngineeringBomChangeType;
  changedFields: readonly string[];
  before: EngineeringBomDifferenceValueViewModel | null;
  after: EngineeringBomDifferenceValueViewModel | null;
}

export interface EngineeringBomComparisonViewModel {
  ebom: EngineeringBomSummaryViewModel;
  fromRevision: EngineeringBomRevisionReferenceViewModel;
  toRevision: EngineeringBomRevisionReferenceViewModel;
  identical: boolean;
  summary: Readonly<Record<EngineeringBomChangeType, number>>;
  changes: readonly EngineeringBomDifferenceViewModel[];
}

export interface EngineeringBomCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface CreateEngineeringBomCommand {
  policyGlobalId: string;
  policyVersion: number;
  policySnapshotHash: string;
  engineeringBomKey: string;
  title: string;
  reason: string;
  effectivityNote: string | null;
  lines: readonly EngineeringBomLineInput[];
}

export interface CreateEngineeringBomRevisionCommand {
  expectedEbomVersion: number;
  predecessorRevisionId: string;
  expectedPredecessorSnapshotHash: string;
  policyGlobalId: string;
  policyVersion: number;
  policySnapshotHash: string;
  reason: string;
  effectivityNote: string | null;
  lines: readonly EngineeringBomLineInput[];
}

export interface EngineeringBomTransitionCommand {
  expectedEbomVersion: number;
  expectedRevisionSnapshotHash: string;
  expectedLifecycleVersion: number;
  policyGlobalId: string;
  policyVersion: number;
  policySnapshotHash: string;
}

export interface SubmitEngineeringBomReviewCommand extends EngineeringBomTransitionCommand {
  reason: string | null;
}

export interface ReviewEngineeringBomRevisionCommand extends EngineeringBomTransitionCommand {
  decision: EngineeringBomReviewDecision;
  reason: string | null;
}

export interface ReleaseEngineeringBomRevisionCommand extends EngineeringBomTransitionCommand {
  confirmed: true;
  confirmationIntent: "release_exact_ebom_revision";
}

export interface EngineeringBomDataSource {
  loadEboms(
    projectId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomListViewModel>;
  loadEbom(
    projectId: string,
    ebomId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomDetailViewModel>;
  createEbom(
    projectId: string,
    command: CreateEngineeringBomCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel>;
  createRevision(
    projectId: string,
    ebomId: string,
    command: CreateEngineeringBomRevisionCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel>;
  submitReview(
    projectId: string,
    ebomId: string,
    revisionId: string,
    command: SubmitEngineeringBomReviewCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel>;
  review(
    projectId: string,
    ebomId: string,
    revisionId: string,
    command: ReviewEngineeringBomRevisionCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel>;
  release(
    projectId: string,
    ebomId: string,
    revisionId: string,
    command: ReleaseEngineeringBomRevisionCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel>;
  compare(
    projectId: string,
    ebomId: string,
    fromRevisionId: string,
    toRevisionId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomComparisonViewModel>;
}

export class EngineeringBomRequestCancelledError extends Error {
  constructor() {
    super("The EBOM request was cancelled.");
    this.name = "EngineeringBomRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const keyPattern = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u;
const lineKeyPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/u;
const engineeringBomKeyPattern = /^[a-z][a-z0-9._-]{0,63}$/u;
const attributeKeyPattern = /^[a-z][a-z0-9_.-]{0,63}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const decimalPattern = /^[0-9]+(?:\.[0-9]+)?$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u;
const lifecycleStates = new Set<EngineeringBomLifecycleState>([
  "draft",
  "in_review",
  "approved",
  "released",
]);
const changeTypes = new Set<EngineeringBomChangeType>([
  "added",
  "removed",
  "quantity",
  "substitution",
  "attribute",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return (
    keys.length === required.length && required.every((key) => key in value)
  );
}

function isString(
  value: unknown,
  minimum: number,
  maximum: number,
  pattern?: RegExp,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    (pattern?.test(value) ?? true)
  );
}

function isUuid(value: unknown): value is string {
  return isString(value, 36, 36, uuidPattern);
}

function isHash(value: unknown): value is string {
  return isString(value, 64, 64, hashPattern);
}

function isPositiveInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) > 0;
}

function isNonnegativeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}

function isValidDate(value: unknown): value is string {
  if (!isString(value, 10, 10, datePattern)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value
  );
}

function isValidTimestamp(value: unknown): value is string {
  return (
    isString(value, 20, 35, timestampPattern) &&
    !Number.isNaN(Date.parse(value))
  );
}

function isNullable<T>(
  value: unknown,
  validate: (candidate: unknown) => candidate is T,
): value is T | null {
  return value === null || validate(value);
}

function hasUnique<T>(
  values: readonly T[],
  key: (value: T) => string,
): boolean {
  return new Set(values.map(key)).size === values.length;
}

function isProject(value: unknown): value is EngineeringBomProjectViewModel {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, [
      "globalId",
      "businessCode",
      "title",
      "lifecycleState",
      "optimisticVersion",
    ]) &&
    isUuid(value.globalId) &&
    isString(value.businessCode, 1, 64) &&
    isString(value.title, 1, 280) &&
    isString(value.lifecycleState, 1, 64) &&
    isPositiveInteger(value.optimisticVersion)
  );
}

function isPermissions(
  value: unknown,
): value is EngineeringBomPermissionsViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["view", "create"]) &&
    value.view === true &&
    typeof value.create === "boolean"
  );
}

function isPolicyReference(
  value: unknown,
): value is EngineeringBomPolicyReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "version", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    isHash(value.snapshotHash)
  );
}

function isPolicyOption(
  value: unknown,
): value is EngineeringBomPolicyOptionViewModel {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, [
      "globalId",
      "version",
      "snapshotHash",
      "key",
      "title",
      "syntheticNamespace",
      "quantityScale",
      "maximumNodes",
      "engineeringUoms",
      "attributeKeys",
    ]) &&
    isPolicyReference({
      globalId: value.globalId,
      version: value.version,
      snapshotHash: value.snapshotHash,
    }) &&
    isString(value.key, 1, 64) &&
    isString(value.title, 1, 140) &&
    isString(value.syntheticNamespace, 11, 32, /^synthetic_[a-z0-9_.-]+$/u) &&
    isNonnegativeInteger(value.quantityScale) &&
    value.quantityScale <= 6 &&
    isPositiveInteger(value.maximumNodes) &&
    value.maximumNodes <= 500 &&
    Array.isArray(value.engineeringUoms) &&
    value.engineeringUoms.length >= 1 &&
    value.engineeringUoms.length <= 50 &&
    value.engineeringUoms.every((item) => isString(item, 1, 16)) &&
    hasUnique(value.engineeringUoms, (item) => item) &&
    Array.isArray(value.attributeKeys) &&
    value.attributeKeys.length <= 50 &&
    value.attributeKeys.every((item) =>
      isString(item, 1, 64, attributeKeyPattern),
    ) &&
    hasUnique(value.attributeKeys, (item) => item)
  );
}

function isRevisionReference(
  value: unknown,
): value is EngineeringBomRevisionReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "revisionNumber", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.revisionNumber) &&
    isHash(value.snapshotHash)
  );
}

function isSummary(value: unknown): value is EngineeringBomSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "engineeringBomKey",
      "title",
      "policy",
      "optimisticVersion",
      "latestRevision",
    ]) &&
    isUuid(value.globalId) &&
    isString(value.engineeringBomKey, 1, 64) &&
    isString(value.title, 1, 140) &&
    isPolicyReference(value.policy) &&
    isPositiveInteger(value.optimisticVersion) &&
    isNullable(value.latestRevision, isRevisionReference)
  );
}

function isAttributes(
  value: unknown,
): value is Readonly<Record<string, string>> {
  return (
    isRecord(value) &&
    Object.keys(value).length <= 50 &&
    Object.entries(value).every(
      ([key, attribute]) =>
        attributeKeyPattern.test(key) && isString(attribute, 0, 280),
    )
  );
}

function isLineInput(value: unknown): value is EngineeringBomLineInput {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, [
      "lineKey",
      "parentLineKey",
      "engineeringItemId",
      "description",
      "quantity",
      "engineeringUom",
      "alternateForLineKey",
      "alternateGroupKey",
      "effectivityStart",
      "effectivityEnd",
      "attributes",
    ]) &&
    isString(value.lineKey, 1, 64, lineKeyPattern) &&
    isNullable(value.parentLineKey, (candidate): candidate is string =>
      isString(candidate, 1, 64, lineKeyPattern),
    ) &&
    isString(value.engineeringItemId, 1, 128, keyPattern) &&
    isString(value.description, 1, 280) &&
    isString(value.quantity, 1, 64, decimalPattern) &&
    Number(value.quantity) > 0 &&
    isString(value.engineeringUom, 1, 16) &&
    isNullable(value.alternateForLineKey, (candidate): candidate is string =>
      isString(candidate, 1, 64, lineKeyPattern),
    ) &&
    isNullable(value.alternateGroupKey, (candidate): candidate is string =>
      isString(candidate, 1, 64, lineKeyPattern),
    ) &&
    isNullable(value.effectivityStart, isValidDate) &&
    isNullable(value.effectivityEnd, isValidDate) &&
    isAttributes(value.attributes)
  );
}

function isLine(value: unknown): value is EngineeringBomLineViewModel {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, ["globalId", ...lineInputKeys]) &&
    isUuid(value.globalId) &&
    isLineInput({
      lineKey: value.lineKey,
      parentLineKey: value.parentLineKey,
      engineeringItemId: value.engineeringItemId,
      description: value.description,
      quantity: value.quantity,
      engineeringUom: value.engineeringUom,
      alternateForLineKey: value.alternateForLineKey,
      alternateGroupKey: value.alternateGroupKey,
      effectivityStart: value.effectivityStart,
      effectivityEnd: value.effectivityEnd,
      attributes: value.attributes,
    })
  );
}

const lineInputKeys = [
  "lineKey",
  "parentLineKey",
  "engineeringItemId",
  "description",
  "quantity",
  "engineeringUom",
  "alternateForLineKey",
  "alternateGroupKey",
  "effectivityStart",
  "effectivityEnd",
  "attributes",
] as const;

function isLifecycle(
  value: unknown,
): value is EngineeringBomLifecycleViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "version", "lastEventId"]) &&
    typeof value.state === "string" &&
    lifecycleStates.has(value.state as EngineeringBomLifecycleState) &&
    isPositiveInteger(value.version) &&
    isNullable(value.lastEventId, isUuid)
  );
}

function isLifecycleEvent(
  value: unknown,
): value is EngineeringBomLifecycleEventViewModel {
  if (!isRecord(value)) return false;
  const eventTypes = new Set([
    "review_submitted",
    "review_approved",
    "review_rejected",
    "released",
  ]);
  return (
    hasExactKeys(value, [
      "globalId",
      "eventType",
      "fromState",
      "toState",
      "fromVersion",
      "toVersion",
      "actorUserId",
      "decision",
      "reason",
      "confirmationIntent",
      "occurredAt",
      "eventHash",
    ]) &&
    isUuid(value.globalId) &&
    typeof value.eventType === "string" &&
    eventTypes.has(value.eventType) &&
    typeof value.fromState === "string" &&
    lifecycleStates.has(value.fromState as EngineeringBomLifecycleState) &&
    typeof value.toState === "string" &&
    lifecycleStates.has(value.toState as EngineeringBomLifecycleState) &&
    isPositiveInteger(value.fromVersion) &&
    isPositiveInteger(value.toVersion) &&
    value.toVersion === value.fromVersion + 1 &&
    isString(value.actorUserId, 1, 254) &&
    (value.decision === null ||
      value.decision === "approve" ||
      value.decision === "reject") &&
    isNullable(value.reason, (candidate): candidate is string =>
      isString(candidate, 1, 280),
    ) &&
    (value.confirmationIntent === null ||
      value.confirmationIntent === "release_exact_ebom_revision") &&
    isValidTimestamp(value.occurredAt) &&
    isHash(value.eventHash)
  );
}

function isCapabilities(
  value: unknown,
): value is EngineeringBomCapabilitiesViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "revise",
      "submitReview",
      "review",
      "release",
      "compare",
    ]) &&
    Object.values(value).every((item) => typeof item === "boolean")
  );
}

function samePolicyReference(
  left: EngineeringBomPolicyReferenceViewModel,
  right: EngineeringBomPolicyReferenceViewModel,
): boolean {
  return (
    left.globalId === right.globalId &&
    left.version === right.version &&
    left.snapshotHash === right.snapshotHash
  );
}

function isRevision(value: unknown): value is EngineeringBomRevisionViewModel {
  if (!isRecord(value)) return false;
  if (
    !hasExactKeys(value, [
      "globalId",
      "revisionNumber",
      "snapshotHash",
      "predecessorRevisionId",
      "predecessorSnapshotHash",
      "reason",
      "effectivityNote",
      "policy",
      "quantityScale",
      "lines",
      "createdByUserId",
      "createdAt",
      "lifecycle",
      "events",
      "capabilities",
    ]) ||
    !isRevisionReference({
      globalId: value.globalId,
      revisionNumber: value.revisionNumber,
      snapshotHash: value.snapshotHash,
    }) ||
    !isNullable(value.predecessorRevisionId, isUuid) ||
    !isNullable(value.predecessorSnapshotHash, isHash) ||
    (value.predecessorRevisionId === null) !==
      (value.predecessorSnapshotHash === null) ||
    !isString(value.reason, 1, 280) ||
    !isNullable(value.effectivityNote, (candidate): candidate is string =>
      isString(candidate, 1, 280),
    ) ||
    !isPolicyReference(value.policy) ||
    !isNonnegativeInteger(value.quantityScale) ||
    value.quantityScale > 6 ||
    !Array.isArray(value.lines) ||
    value.lines.length < 1 ||
    value.lines.length > 500 ||
    !value.lines.every(isLine) ||
    !hasUnique(value.lines, (line) => line.lineKey) ||
    !hasUnique(value.lines, (line) => line.globalId) ||
    !isString(value.createdByUserId, 1, 254) ||
    !isValidTimestamp(value.createdAt) ||
    !isLifecycle(value.lifecycle) ||
    !Array.isArray(value.events) ||
    value.events.length > 1000 ||
    !value.events.every(isLifecycleEvent) ||
    !hasUnique(value.events, (event) => event.globalId) ||
    !isCapabilities(value.capabilities)
  )
    return false;
  const events =
    value.events as readonly EngineeringBomLifecycleEventViewModel[];
  const latestEvent = events.at(-1);
  return (
    (latestEvent?.globalId ?? null) === value.lifecycle.lastEventId &&
    (latestEvent?.toVersion ?? 1) === value.lifecycle.version &&
    (latestEvent?.toState ?? "draft") === value.lifecycle.state &&
    events.every((event, index) =>
      index === 0
        ? event.fromVersion === 1 && event.fromState === "draft"
        : event.fromVersion === events[index - 1]?.toVersion &&
          event.fromState === events[index - 1]?.toState,
    )
  );
}

export function isEngineeringBomListResponse(
  value: unknown,
): value is EngineeringBomListViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["project", "permissions", "policies", "items"]) ||
    !isProject(value.project) ||
    !isPermissions(value.permissions) ||
    !Array.isArray(value.policies) ||
    value.policies.length > 100 ||
    !value.policies.every(isPolicyOption) ||
    !hasUnique(
      value.policies,
      (policy) =>
        `${policy.globalId}:${String(policy.version)}:${policy.snapshotHash}`,
    ) ||
    !Array.isArray(value.items) ||
    value.items.length > 200 ||
    !value.items.every(isSummary) ||
    !hasUnique(value.items, (item) => item.globalId) ||
    !hasUnique(value.items, (item) => item.engineeringBomKey)
  )
    return false;
  const policies =
    value.policies as readonly EngineeringBomPolicyOptionViewModel[];
  return value.items.every((item) =>
    policies.some((policy) => samePolicyReference(item.policy, policy)),
  );
}

export function isEngineeringBomDetailResponse(
  value: unknown,
): value is EngineeringBomDetailViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "project",
      "permissions",
      "policy",
      "ebom",
      "revisions",
    ]) ||
    !isProject(value.project) ||
    !isPermissions(value.permissions) ||
    !isPolicyOption(value.policy) ||
    !isSummary(value.ebom) ||
    !samePolicyReference(value.ebom.policy, value.policy) ||
    !Array.isArray(value.revisions) ||
    value.revisions.length > 200 ||
    !value.revisions.every(isRevision) ||
    !hasUnique(value.revisions, (revision) => revision.globalId) ||
    !hasUnique(value.revisions, (revision) =>
      String(revision.revisionNumber),
    ) ||
    !value.revisions.every((revision) =>
      samePolicyReference(
        revision.policy,
        value.policy as EngineeringBomPolicyOptionViewModel,
      ),
    )
  )
    return false;
  const byId = new Map(
    value.revisions.map((revision) => [revision.globalId, revision]),
  );
  const latest = value.ebom.latestRevision;
  if (latest === null) return value.revisions.length === 0;
  const exactLatest = byId.get(latest.globalId);
  if (
    exactLatest?.revisionNumber !== latest.revisionNumber ||
    exactLatest.snapshotHash !== latest.snapshotHash
  )
    return false;
  return value.revisions.every((revision) => {
    if (revision.revisionNumber === 1)
      return revision.predecessorRevisionId === null;
    const predecessor = revision.predecessorRevisionId
      ? byId.get(revision.predecessorRevisionId)
      : undefined;
    return (
      predecessor?.revisionNumber === revision.revisionNumber - 1 &&
      predecessor.snapshotHash === revision.predecessorSnapshotHash
    );
  });
}

export function isEngineeringBomCommandResponse(
  value: unknown,
): value is EngineeringBomCommandViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["ebom", "revision"]) &&
    isSummary(value.ebom) &&
    isRevision(value.revision) &&
    value.ebom.latestRevision?.globalId === value.revision.globalId &&
    value.ebom.latestRevision.revisionNumber ===
      value.revision.revisionNumber &&
    value.ebom.latestRevision.snapshotHash === value.revision.snapshotHash &&
    samePolicyReference(value.revision.policy, value.ebom.policy)
  );
}

function isDifferenceValue(
  value: unknown,
): value is EngineeringBomDifferenceValueViewModel {
  return isLine(value);
}

export function isEngineeringBomComparisonResponse(
  value: unknown,
): value is EngineeringBomComparisonViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "ebom",
      "fromRevision",
      "toRevision",
      "identical",
      "summary",
      "changes",
    ]) ||
    !isSummary(value.ebom) ||
    !isRevisionReference(value.fromRevision) ||
    !isRevisionReference(value.toRevision) ||
    typeof value.identical !== "boolean" ||
    !isRecord(value.summary) ||
    !hasExactKeys(value.summary, [
      "added",
      "removed",
      "quantity",
      "substitution",
      "attribute",
    ]) ||
    !Object.values(value.summary).every(isNonnegativeInteger) ||
    !Array.isArray(value.changes) ||
    value.changes.length > 2500
  )
    return false;
  const changes = value.changes;
  if (
    !changes.every((change): change is EngineeringBomDifferenceViewModel => {
      if (!isRecord(change)) return false;
      return (
        hasExactKeys(change, [
          "lineKey",
          "changeType",
          "changedFields",
          "before",
          "after",
        ]) &&
        isString(change.lineKey, 1, 64, lineKeyPattern) &&
        typeof change.changeType === "string" &&
        changeTypes.has(change.changeType as EngineeringBomChangeType) &&
        Array.isArray(change.changedFields) &&
        change.changedFields.length >= 1 &&
        change.changedFields.length <= 6 &&
        change.changedFields.every((field) => isString(field, 1, 64)) &&
        hasUnique(change.changedFields, String) &&
        isNullable(change.before, isDifferenceValue) &&
        isNullable(change.after, isDifferenceValue) &&
        (change.before !== null || change.after !== null) &&
        (change.before?.lineKey ?? change.after?.lineKey) === change.lineKey
      );
    }) ||
    !hasUnique(changes, (change) => change.lineKey)
  )
    return false;
  const counts: Record<EngineeringBomChangeType, number> = {
    added: 0,
    removed: 0,
    quantity: 0,
    substitution: 0,
    attribute: 0,
  };
  for (const change of changes) counts[change.changeType] += 1;
  const summary = value.summary as Record<EngineeringBomChangeType, number>;
  return (
    Object.entries(counts).every(
      ([key, count]) => summary[key as EngineeringBomChangeType] === count,
    ) && value.identical === (changes.length === 0)
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function throwIfCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new EngineeringBomRequestCancelledError();
}

function isCommandContext(value: EngineeringBomCommandContext): boolean {
  return (
    isString(value.csrfToken, 1, 2048) &&
    isString(value.idempotencyKey, 8, 128, idempotencyPattern) &&
    value.signal instanceof AbortSignal
  );
}

function isLineCollection(
  lines: readonly EngineeringBomLineInput[],
  maximum = 500,
): boolean {
  return (
    Array.isArray(lines) &&
    lines.length >= 1 &&
    lines.length <= maximum &&
    lines.every(isLineInput) &&
    hasUnique(lines, (line) => line.lineKey)
  );
}

function trimOptional(value: string | null): string | null {
  const trimmed = value?.trim();
  return trimmed && trimmed.length > 0 ? trimmed : null;
}

function validPolicyFields(value: EngineeringBomTransitionCommand): boolean {
  return (
    isPositiveInteger(value.expectedEbomVersion) &&
    isHash(value.expectedRevisionSnapshotHash) &&
    isPositiveInteger(value.expectedLifecycleVersion) &&
    isUuid(value.policyGlobalId) &&
    isPositiveInteger(value.policyVersion) &&
    isHash(value.policySnapshotHash)
  );
}

export class LiveEngineeringBomDataSource implements EngineeringBomDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadEboms(
    projectId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomListViewModel> {
    if (!isUuid(projectId)) throw requestNotReady();
    return this.query(
      `/projects/${projectId}/eboms`,
      signal,
      {},
      (value): value is EngineeringBomListViewModel =>
        isEngineeringBomListResponse(value) &&
        value.project.globalId === projectId,
    );
  }

  async loadEbom(
    projectId: string,
    ebomId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomDetailViewModel> {
    if (!isUuid(projectId) || !isUuid(ebomId)) throw requestNotReady();
    return this.query(
      `/projects/${projectId}/eboms/${ebomId}`,
      signal,
      {},
      (value): value is EngineeringBomDetailViewModel =>
        isEngineeringBomDetailResponse(value) &&
        value.project.globalId === projectId &&
        value.ebom.globalId === ebomId,
    );
  }

  async createEbom(
    projectId: string,
    command: CreateEngineeringBomCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel> {
    const body = {
      policyGlobalId: command.policyGlobalId,
      policyVersion: command.policyVersion,
      policySnapshotHash: command.policySnapshotHash,
      engineeringBomKey: command.engineeringBomKey.trim(),
      title: command.title.trim(),
      reason: command.reason.trim(),
      effectivityNote: trimOptional(command.effectivityNote),
      lines: command.lines,
    };
    if (
      !isUuid(projectId) ||
      !isUuid(body.policyGlobalId) ||
      !isPositiveInteger(body.policyVersion) ||
      !isHash(body.policySnapshotHash) ||
      !isString(body.engineeringBomKey, 1, 64, engineeringBomKeyPattern) ||
      !isString(body.title, 1, 140) ||
      !isString(body.reason, 1, 280) ||
      !isNullable(body.effectivityNote, (value): value is string =>
        isString(value, 1, 280),
      ) ||
      !isLineCollection(body.lines)
    )
      throw requestNotReady();
    return this.command(
      `/projects/${projectId}/eboms`,
      body,
      context,
      (value): value is EngineeringBomCommandViewModel =>
        isEngineeringBomCommandResponse(value) &&
        value.ebom.engineeringBomKey === body.engineeringBomKey &&
        value.ebom.title === body.title &&
        value.revision.revisionNumber === 1,
    );
  }

  async createRevision(
    projectId: string,
    ebomId: string,
    command: CreateEngineeringBomRevisionCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel> {
    const body = {
      expectedEbomVersion: command.expectedEbomVersion,
      predecessorRevisionId: command.predecessorRevisionId,
      expectedPredecessorSnapshotHash: command.expectedPredecessorSnapshotHash,
      policyGlobalId: command.policyGlobalId,
      policyVersion: command.policyVersion,
      policySnapshotHash: command.policySnapshotHash,
      reason: command.reason.trim(),
      effectivityNote: trimOptional(command.effectivityNote),
      lines: command.lines,
    };
    if (
      !isUuid(projectId) ||
      !isUuid(ebomId) ||
      !isPositiveInteger(body.expectedEbomVersion) ||
      !isUuid(body.predecessorRevisionId) ||
      !isHash(body.expectedPredecessorSnapshotHash) ||
      !isUuid(body.policyGlobalId) ||
      !isPositiveInteger(body.policyVersion) ||
      !isHash(body.policySnapshotHash) ||
      !isString(body.reason, 1, 280) ||
      !isNullable(body.effectivityNote, (value): value is string =>
        isString(value, 1, 280),
      ) ||
      !isLineCollection(body.lines)
    )
      throw requestNotReady();
    return this.command(
      `/projects/${projectId}/eboms/${ebomId}/revisions`,
      body,
      context,
      (value): value is EngineeringBomCommandViewModel =>
        isEngineeringBomCommandResponse(value) &&
        value.ebom.globalId === ebomId &&
        value.ebom.optimisticVersion === body.expectedEbomVersion + 1 &&
        value.revision.predecessorRevisionId === body.predecessorRevisionId &&
        value.revision.predecessorSnapshotHash ===
          body.expectedPredecessorSnapshotHash,
    );
  }

  async submitReview(
    projectId: string,
    ebomId: string,
    revisionId: string,
    command: SubmitEngineeringBomReviewCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel> {
    const body = {
      expectedEbomVersion: command.expectedEbomVersion,
      expectedRevisionSnapshotHash: command.expectedRevisionSnapshotHash,
      expectedLifecycleVersion: command.expectedLifecycleVersion,
      policyGlobalId: command.policyGlobalId,
      policyVersion: command.policyVersion,
      policySnapshotHash: command.policySnapshotHash,
      reason: trimOptional(command.reason),
    };
    if (
      !validPolicyFields(body) ||
      !isNullable(body.reason, (value): value is string =>
        isString(value, 1, 280),
      )
    )
      throw requestNotReady();
    return this.transition(
      projectId,
      ebomId,
      revisionId,
      ":submit-review",
      body,
      context,
      "in_review",
    );
  }

  async review(
    projectId: string,
    ebomId: string,
    revisionId: string,
    command: ReviewEngineeringBomRevisionCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel> {
    const decision: unknown = command.decision;
    const body = {
      expectedEbomVersion: command.expectedEbomVersion,
      expectedRevisionSnapshotHash: command.expectedRevisionSnapshotHash,
      expectedLifecycleVersion: command.expectedLifecycleVersion,
      policyGlobalId: command.policyGlobalId,
      policyVersion: command.policyVersion,
      policySnapshotHash: command.policySnapshotHash,
      decision,
      reason: trimOptional(command.reason),
    };
    if (
      !validPolicyFields(body) ||
      (body.decision !== "approve" && body.decision !== "reject") ||
      !isNullable(body.reason, (value): value is string =>
        isString(value, 1, 280),
      ) ||
      (body.decision === "reject" && body.reason === null)
    )
      throw requestNotReady();
    return this.transition(
      projectId,
      ebomId,
      revisionId,
      ":review",
      body,
      context,
      body.decision === "approve" ? "approved" : "draft",
    );
  }

  async release(
    projectId: string,
    ebomId: string,
    revisionId: string,
    command: ReleaseEngineeringBomRevisionCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomCommandViewModel> {
    const confirmed: unknown = command.confirmed;
    const confirmationIntent: unknown = command.confirmationIntent;
    const body = {
      expectedEbomVersion: command.expectedEbomVersion,
      expectedRevisionSnapshotHash: command.expectedRevisionSnapshotHash,
      expectedLifecycleVersion: command.expectedLifecycleVersion,
      policyGlobalId: command.policyGlobalId,
      policyVersion: command.policyVersion,
      policySnapshotHash: command.policySnapshotHash,
      confirmed,
      confirmationIntent,
    };
    if (
      !validPolicyFields(body) ||
      body.confirmed !== true ||
      body.confirmationIntent !== "release_exact_ebom_revision"
    )
      throw requestNotReady();
    return this.transition(
      projectId,
      ebomId,
      revisionId,
      ":release",
      body,
      context,
      "released",
    );
  }

  async compare(
    projectId: string,
    ebomId: string,
    fromRevisionId: string,
    toRevisionId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomComparisonViewModel> {
    if (
      ![projectId, ebomId, fromRevisionId, toRevisionId].every(isUuid) ||
      fromRevisionId === toRevisionId
    )
      throw requestNotReady();
    return this.query(
      `/projects/${projectId}/eboms/${ebomId}/compare`,
      signal,
      { fromRevisionId, toRevisionId },
      (value): value is EngineeringBomComparisonViewModel =>
        isEngineeringBomComparisonResponse(value) &&
        value.ebom.globalId === ebomId &&
        value.fromRevision.globalId === fromRevisionId &&
        value.toRevision.globalId === toRevisionId,
    );
  }

  private async transition(
    projectId: string,
    ebomId: string,
    revisionId: string,
    suffix: ":submit-review" | ":review" | ":release",
    body: EngineeringBomTransitionCommand,
    context: EngineeringBomCommandContext,
    expectedState: EngineeringBomLifecycleState,
  ): Promise<EngineeringBomCommandViewModel> {
    if (![projectId, ebomId, revisionId].every(isUuid)) throw requestNotReady();
    return this.command(
      `/projects/${projectId}/eboms/${ebomId}/revisions/${revisionId}${suffix}`,
      body,
      context,
      (value): value is EngineeringBomCommandViewModel =>
        isEngineeringBomCommandResponse(value) &&
        value.ebom.globalId === ebomId &&
        value.ebom.optimisticVersion === body.expectedEbomVersion &&
        value.revision.globalId === revisionId &&
        value.revision.snapshotHash === body.expectedRevisionSnapshotHash &&
        value.revision.lifecycle.version ===
          body.expectedLifecycleVersion + 1 &&
        value.revision.lifecycle.state === expectedState,
    );
  }

  private async query<T>(
    path: string,
    signal: AbortSignal,
    query: Readonly<Record<string, string>>,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    throwIfCancelled(signal);
    try {
      return await this.http.request<T>(
        path,
        { signal },
        {
          query,
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate,
        },
      );
    } catch (error) {
      throwIfCancelled(signal);
      throw error;
    }
  }

  private async command<T>(
    path: string,
    body: object,
    context: EngineeringBomCommandContext,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    if (!isCommandContext(context)) throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<T>(
        path,
        {
          body: JSON.stringify(body),
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
          validate,
        },
      );
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }
}
