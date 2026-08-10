import { NpiHttpClient, NpiTransportError } from "./http";

export const trialPurposes = [
  "first_trial",
  "tooling_change_verification",
  "design_verification",
  "material_color_verification",
  "capability_study",
  "customer_sample",
  "other",
] as const;
export type TrialPurpose = (typeof trialPurposes)[number];

export const trialResourceKinds = [
  "machine",
  "auxiliary_equipment",
  "material",
] as const;
export type TrialResourceKind = (typeof trialResourceKinds)[number];

export const trialRoundStates = [
  "planned",
  "prepared",
  "running",
  "analysis",
  "submitted",
  "approved",
  "rejected",
  "cancelled",
] as const;
export type TrialRoundState = (typeof trialRoundStates)[number];

export const trialActionSeverities = [
  "low",
  "medium",
  "high",
  "critical",
] as const;
export type TrialActionSeverity = (typeof trialActionSeverities)[number];

export interface TrialResourceProposalInput {
  kind: TrialResourceKind;
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
  label: string;
  quantity: number | null;
  unit: string | null;
}

export interface TrialResourceProposal extends TrialResourceProposalInput {
  globalId: string;
  bookingState: "unavailable";
}

export interface TrialProjectMemberReference {
  globalId: string;
  userId: string;
  optimisticVersion: number;
}

export interface TrialMeasurementPlanInput {
  description: string;
}

export interface TrialMeasurementPlanIntent {
  description: string | null;
  documentRevisionGlobalId: string | null;
  documentRevisionSnapshotHash: string | null;
  documentOptimisticVersion: number | null;
  lockState: "planning_intent_only";
}

export interface TrialPlanRevision {
  globalId: string;
  planGlobalId: string;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  planVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  purpose: TrialPurpose;
  objective: string;
  plannedStartAt: string;
  plannedEndAt: string;
  resources: readonly TrialResourceProposal[];
  responsibleMembers: readonly TrialProjectMemberReference[];
  sampleQuantity: number;
  measurementPlan: TrialMeasurementPlanIntent;
  reason: string;
  createdByUserId: string;
  createdAt: string;
  snapshotHash: string;
}

export interface TrialRoundSummary {
  globalId: string;
  projectGlobalId: string;
  trialPlanGlobalId: string;
  trialPlanRevisionGlobalId: string;
  trialPlanRevisionSnapshotHash: string;
  toolingMasterGlobalId: string;
  roundSequence: number;
  displayLabel: string;
  purpose: TrialPurpose;
  plannedStartAt: string;
  plannedEndAt: string;
  currentState: TrialRoundState;
  optimisticVersion: number;
  createdByUserId: string;
  createdAt: string;
  snapshotHash: string;
}

export interface TrialPlanWorkLink {
  globalId: string;
  projectGlobalId: string;
  trialPlanGlobalId: string;
  trialPlanRevisionGlobalId: string;
  trialPlanRevisionSnapshotHash: string;
  trialRoundGlobalId: string | null;
  domainWorkItemGlobalId: string;
  createdByUserId: string;
  createdAt: string;
  snapshotHash: string;
}

export interface TrialPlanSummary {
  planGlobalId: string;
  latestRevision: TrialPlanRevision;
  roundCount: number;
  actionCount: number;
}

export type TrialUnavailableCapability =
  | {
      key: "resource_availability";
      availability: "unavailable";
      reasonCode: "approved_resource_reader_not_configured";
    }
  | {
      key: "resource_reservation";
      availability: "unavailable";
      reasonCode: "approved_booking_policy_not_configured";
    };

export interface TrialPermissions {
  canCreatePlan: boolean;
  canRevisePlan: boolean;
  canCreateRound: boolean;
  canGenerateActions: boolean;
}

export interface TrialPlanningWorkspace {
  projectGlobalId: string;
  plans: readonly TrialPlanSummary[];
  capabilities: readonly TrialUnavailableCapability[];
  permissions: TrialPermissions;
}

export interface TrialPlanDetail {
  projectGlobalId: string;
  planGlobalId: string;
  latestRevision: TrialPlanRevision;
  revisions: readonly TrialPlanRevision[];
  rounds: readonly TrialRoundSummary[];
  actionLinks: readonly TrialPlanWorkLink[];
  capabilities: readonly TrialUnavailableCapability[];
  permissions: TrialPermissions;
}

export interface CreateTrialPlanCommand {
  toolingMasterGlobalId: string;
  purpose: TrialPurpose;
  objective: string;
  plannedStartAt: string;
  plannedEndAt: string;
  resources: readonly TrialResourceProposalInput[];
  responsibleMemberGlobalIds: readonly string[];
  sampleQuantity: number;
  measurementPlan: TrialMeasurementPlanInput;
  reason: string;
}

export interface CreateTrialPlanRevisionCommand extends Omit<
  CreateTrialPlanCommand,
  "toolingMasterGlobalId"
> {
  expectedRevisionGlobalId: string;
  expectedRevisionSnapshotHash: string;
  expectedPlanVersion: number;
}

export interface CreatePlannedTrialRoundCommand {
  expectedPlanRevisionGlobalId: string;
  expectedPlanRevisionSnapshotHash: string;
  displayLabel?: string | null | undefined;
  reason: string;
}

export interface TrialPlanActionInput {
  actionKey: string;
  title: string;
  description: string | null;
  responsibleMemberGlobalId: string;
  dueAt: string;
  severity: TrialActionSeverity;
  blocking: boolean;
}

export interface GenerateTrialPlanActionsCommand {
  expectedPlanRevisionGlobalId: string;
  expectedPlanRevisionSnapshotHash: string;
  trialRoundGlobalId?: string | null | undefined;
  actions: readonly TrialPlanActionInput[];
  reason: string;
}

export interface TrialCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface TrialCommandResult {
  detail: TrialPlanDetail;
  replayed: boolean;
}

export interface TrialDataSource {
  loadWorkspace(
    projectId: string,
    signal: AbortSignal,
  ): Promise<TrialPlanningWorkspace>;
  loadPlan(
    projectId: string,
    planId: string,
    signal: AbortSignal,
  ): Promise<TrialPlanDetail>;
  createPlan(
    projectId: string,
    command: CreateTrialPlanCommand,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult>;
  revisePlan(
    projectId: string,
    planId: string,
    command: CreateTrialPlanRevisionCommand,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult>;
  createRound(
    projectId: string,
    planId: string,
    command: CreatePlannedTrialRoundCommand,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult>;
  generateActions(
    projectId: string,
    planId: string,
    command: GenerateTrialPlanActionsCommand,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult>;
}

export class TrialRequestCancelledError extends Error {
  constructor() {
    super("The Trial request was cancelled.");
    this.name = "TrialRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const referencePattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$/u;
const actionKeyPattern = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/u;
const roundLabelPattern = /^T(?:0|[1-9][0-9]{0,3})$/u;

function exact(value: object, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function exactWithOptional(
  value: object,
  required: readonly string[],
  optional: readonly string[],
): boolean {
  const keys = Object.keys(value);
  const allowed = new Set([...required, ...optional]);
  return (
    required.every((key) => keys.includes(key)) &&
    keys.every((key) => allowed.has(key))
  );
}

function member<T extends string>(
  value: unknown,
  values: readonly T[],
): value is T {
  return typeof value === "string" && values.includes(value as T);
}

function whole(
  value: unknown,
  minimum = 0,
  maximum = Number.MAX_SAFE_INTEGER,
): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function hasControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    return codePoint <= 31 || codePoint === 127;
  });
}

function textValue(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    !hasControlCharacter(value)
  );
}

function dateTime(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length >= 20 &&
    value.length <= 40 &&
    value.includes("T") &&
    Number.isFinite(Date.parse(value))
  );
}

function unique(values: readonly unknown[]): boolean {
  return new Set(values).size === values.length;
}

function isResourceInput(value: unknown): value is TrialResourceProposalInput {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "kind",
      "sourceSystem",
      "sourceObjectId",
      "label",
      "quantity",
      "unit",
    ]) &&
    member(item.kind, trialResourceKinds) &&
    member(item.sourceSystem, ["NPI_ONE", "ERPNEXT"] as const) &&
    typeof item.sourceObjectId === "string" &&
    referencePattern.test(item.sourceObjectId) &&
    textValue(item.label, 1, 140) &&
    (item.quantity === null || whole(item.quantity, 1)) &&
    (item.unit === null || textValue(item.unit, 1, 32)) &&
    ((item.quantity === null && item.unit === null) ||
      (item.quantity !== null && item.unit !== null))
  );
}

function isResource(value: unknown): value is TrialResourceProposal {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "globalId",
      "kind",
      "sourceSystem",
      "sourceObjectId",
      "label",
      "quantity",
      "unit",
      "bookingState",
    ]) &&
    typeof item.globalId === "string" &&
    uuidPattern.test(item.globalId) &&
    item.bookingState === "unavailable" &&
    isResourceInput({
      kind: item.kind,
      sourceSystem: item.sourceSystem,
      sourceObjectId: item.sourceObjectId,
      label: item.label,
      quantity: item.quantity,
      unit: item.unit,
    })
  );
}

function isMemberReference(
  value: unknown,
): value is TrialProjectMemberReference {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["globalId", "userId", "optimisticVersion"]) &&
    typeof item.globalId === "string" &&
    uuidPattern.test(item.globalId) &&
    textValue(item.userId, 3, 254) &&
    item.userId.includes("@") &&
    whole(item.optimisticVersion, 1)
  );
}

function isMeasurementIntent(
  value: unknown,
): value is TrialMeasurementPlanIntent {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "description",
      "documentRevisionGlobalId",
      "documentRevisionSnapshotHash",
      "documentOptimisticVersion",
      "lockState",
    ]) ||
    item.lockState !== "planning_intent_only" ||
    (item.description !== null && !textValue(item.description, 1, 1000))
  )
    return false;
  const noDocument =
    item.documentRevisionGlobalId === null &&
    item.documentRevisionSnapshotHash === null &&
    item.documentOptimisticVersion === null;
  const exactDocument =
    typeof item.documentRevisionGlobalId === "string" &&
    uuidPattern.test(item.documentRevisionGlobalId) &&
    typeof item.documentRevisionSnapshotHash === "string" &&
    hashPattern.test(item.documentRevisionSnapshotHash) &&
    whole(item.documentOptimisticVersion, 1);
  return (
    (noDocument || exactDocument) &&
    (item.description !== null || exactDocument)
  );
}

export function isTrialPlanRevision(
  value: unknown,
): value is TrialPlanRevision {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "globalId",
      "planGlobalId",
      "projectGlobalId",
      "toolingMasterGlobalId",
      "planVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "purpose",
      "objective",
      "plannedStartAt",
      "plannedEndAt",
      "resources",
      "responsibleMembers",
      "sampleQuantity",
      "measurementPlan",
      "reason",
      "createdByUserId",
      "createdAt",
      "snapshotHash",
    ]) ||
    ![
      item.globalId,
      item.planGlobalId,
      item.projectGlobalId,
      item.toolingMasterGlobalId,
    ].every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) ||
    !whole(item.planVersion, 1) ||
    !member(item.purpose, trialPurposes) ||
    !textValue(item.objective, 1, 2000) ||
    !dateTime(item.plannedStartAt) ||
    !dateTime(item.plannedEndAt) ||
    Date.parse(item.plannedStartAt) >= Date.parse(item.plannedEndAt) ||
    !Array.isArray(item.resources) ||
    item.resources.length < 2 ||
    item.resources.length > 50 ||
    !item.resources.every(isResource) ||
    !unique(item.resources.map((resource) => resource.globalId)) ||
    !Array.isArray(item.responsibleMembers) ||
    item.responsibleMembers.length < 1 ||
    item.responsibleMembers.length > 50 ||
    !item.responsibleMembers.every(isMemberReference) ||
    !unique(item.responsibleMembers.map((reference) => reference.globalId)) ||
    !whole(item.sampleQuantity, 1) ||
    !isMeasurementIntent(item.measurementPlan) ||
    !textValue(item.reason, 1, 500) ||
    !textValue(item.createdByUserId, 1, 254) ||
    !dateTime(item.createdAt) ||
    typeof item.snapshotHash !== "string" ||
    !hashPattern.test(item.snapshotHash)
  )
    return false;
  const first = item.planVersion === 1;
  return first
    ? item.predecessorGlobalId === null && item.predecessorSnapshotHash === null
    : typeof item.predecessorGlobalId === "string" &&
        uuidPattern.test(item.predecessorGlobalId) &&
        typeof item.predecessorSnapshotHash === "string" &&
        hashPattern.test(item.predecessorSnapshotHash);
}

function isTrialRound(value: unknown): value is TrialRoundSummary {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "globalId",
      "projectGlobalId",
      "trialPlanGlobalId",
      "trialPlanRevisionGlobalId",
      "trialPlanRevisionSnapshotHash",
      "toolingMasterGlobalId",
      "roundSequence",
      "displayLabel",
      "purpose",
      "plannedStartAt",
      "plannedEndAt",
      "currentState",
      "optimisticVersion",
      "createdByUserId",
      "createdAt",
      "snapshotHash",
    ]) &&
    [
      item.globalId,
      item.projectGlobalId,
      item.trialPlanGlobalId,
      item.trialPlanRevisionGlobalId,
      item.toolingMasterGlobalId,
    ].every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) &&
    typeof item.trialPlanRevisionSnapshotHash === "string" &&
    hashPattern.test(item.trialPlanRevisionSnapshotHash) &&
    whole(item.roundSequence) &&
    typeof item.displayLabel === "string" &&
    roundLabelPattern.test(item.displayLabel) &&
    member(item.purpose, trialPurposes) &&
    dateTime(item.plannedStartAt) &&
    dateTime(item.plannedEndAt) &&
    Date.parse(item.plannedStartAt) < Date.parse(item.plannedEndAt) &&
    member(item.currentState, trialRoundStates) &&
    whole(item.optimisticVersion, 1) &&
    textValue(item.createdByUserId, 1, 254) &&
    dateTime(item.createdAt) &&
    typeof item.snapshotHash === "string" &&
    hashPattern.test(item.snapshotHash)
  );
}

function isWorkLink(value: unknown): value is TrialPlanWorkLink {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "globalId",
      "projectGlobalId",
      "trialPlanGlobalId",
      "trialPlanRevisionGlobalId",
      "trialPlanRevisionSnapshotHash",
      "trialRoundGlobalId",
      "domainWorkItemGlobalId",
      "createdByUserId",
      "createdAt",
      "snapshotHash",
    ]) &&
    [
      item.globalId,
      item.projectGlobalId,
      item.trialPlanGlobalId,
      item.trialPlanRevisionGlobalId,
      item.domainWorkItemGlobalId,
    ].every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) &&
    (item.trialRoundGlobalId === null ||
      (typeof item.trialRoundGlobalId === "string" &&
        uuidPattern.test(item.trialRoundGlobalId))) &&
    typeof item.trialPlanRevisionSnapshotHash === "string" &&
    hashPattern.test(item.trialPlanRevisionSnapshotHash) &&
    textValue(item.createdByUserId, 1, 254) &&
    dateTime(item.createdAt) &&
    typeof item.snapshotHash === "string" &&
    hashPattern.test(item.snapshotHash)
  );
}

function isCapabilities(
  value: unknown,
): value is readonly TrialUnavailableCapability[] {
  if (!Array.isArray(value) || value.length !== 2) return false;
  const valid = value.every((candidate) => {
    if (!candidate || typeof candidate !== "object") return false;
    const item = candidate as Record<string, unknown>;
    if (!exact(item, ["key", "availability", "reasonCode"])) return false;
    return (
      item.availability === "unavailable" &&
      ((item.key === "resource_availability" &&
        item.reasonCode === "approved_resource_reader_not_configured") ||
        (item.key === "resource_reservation" &&
          item.reasonCode === "approved_booking_policy_not_configured"))
    );
  });
  const capabilities = value as TrialUnavailableCapability[];
  return valid && unique(capabilities.map((candidate) => candidate.key));
}

function isPermissions(value: unknown): value is TrialPermissions {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "canCreatePlan",
      "canRevisePlan",
      "canCreateRound",
      "canGenerateActions",
    ]) &&
    [
      item.canCreatePlan,
      item.canRevisePlan,
      item.canCreateRound,
      item.canGenerateActions,
    ].every((candidate) => typeof candidate === "boolean")
  );
}

function isPlanSummary(value: unknown): value is TrialPlanSummary {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "planGlobalId",
      "latestRevision",
      "roundCount",
      "actionCount",
    ]) &&
    typeof item.planGlobalId === "string" &&
    uuidPattern.test(item.planGlobalId) &&
    isTrialPlanRevision(item.latestRevision) &&
    item.latestRevision.planGlobalId === item.planGlobalId &&
    whole(item.roundCount) &&
    whole(item.actionCount)
  );
}

export function isTrialPlanningWorkspace(
  value: unknown,
): value is TrialPlanningWorkspace {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, ["projectGlobalId", "plans", "capabilities", "permissions"]) ||
    typeof item.projectGlobalId !== "string" ||
    !uuidPattern.test(item.projectGlobalId) ||
    !Array.isArray(item.plans) ||
    item.plans.length > 500 ||
    !item.plans.every(isPlanSummary) ||
    !isCapabilities(item.capabilities) ||
    !isPermissions(item.permissions)
  )
    return false;
  return (
    unique(item.plans.map((plan) => plan.planGlobalId)) &&
    item.plans.every(
      (plan) => plan.latestRevision.projectGlobalId === item.projectGlobalId,
    )
  );
}

export function isTrialPlanDetail(value: unknown): value is TrialPlanDetail {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "projectGlobalId",
      "planGlobalId",
      "latestRevision",
      "revisions",
      "rounds",
      "actionLinks",
      "capabilities",
      "permissions",
    ]) ||
    typeof item.projectGlobalId !== "string" ||
    !uuidPattern.test(item.projectGlobalId) ||
    typeof item.planGlobalId !== "string" ||
    !uuidPattern.test(item.planGlobalId) ||
    !isTrialPlanRevision(item.latestRevision) ||
    !Array.isArray(item.revisions) ||
    item.revisions.length < 1 ||
    item.revisions.length > 1000 ||
    !item.revisions.every(isTrialPlanRevision) ||
    !Array.isArray(item.rounds) ||
    item.rounds.length > 1000 ||
    !item.rounds.every(isTrialRound) ||
    !Array.isArray(item.actionLinks) ||
    item.actionLinks.length > 5000 ||
    !item.actionLinks.every(isWorkLink) ||
    !isCapabilities(item.capabilities) ||
    !isPermissions(item.permissions)
  )
    return false;
  const projectId = item.projectGlobalId;
  const planId = item.planGlobalId;
  const latest = item.latestRevision;
  const revisions = item.revisions;
  const rounds = item.rounds;
  const links = item.actionLinks;
  return (
    latest.projectGlobalId === projectId &&
    latest.planGlobalId === planId &&
    revisions.every(
      (revision) =>
        revision.projectGlobalId === projectId &&
        revision.planGlobalId === planId,
    ) &&
    revisions.every((revision, index) => revision.planVersion === index + 1) &&
    revisions.at(-1)?.globalId === latest.globalId &&
    revisions.at(-1)?.snapshotHash === latest.snapshotHash &&
    unique(revisions.map((revision) => revision.globalId)) &&
    rounds.every(
      (round) =>
        round.projectGlobalId === projectId &&
        round.trialPlanGlobalId === planId,
    ) &&
    unique(rounds.map((round) => round.globalId)) &&
    unique(rounds.map((round) => round.displayLabel)) &&
    links.every(
      (link) =>
        link.projectGlobalId === projectId && link.trialPlanGlobalId === planId,
    ) &&
    unique(links.map((link) => link.globalId))
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function requireUuid(value: string): string {
  if (!uuidPattern.test(value)) throw requestNotReady();
  return value;
}

function validContext(value: TrialCommandContext): boolean {
  return (
    typeof value.csrfToken === "string" &&
    value.csrfToken.length >= 32 &&
    value.csrfToken.length <= 128 &&
    !hasControlCharacter(value.csrfToken) &&
    idempotencyPattern.test(value.idempotencyKey) &&
    value.signal instanceof AbortSignal
  );
}

function validPlanFields(value: {
  purpose: TrialPurpose;
  objective: string;
  plannedStartAt: string;
  plannedEndAt: string;
  resources: readonly TrialResourceProposalInput[];
  responsibleMemberGlobalIds: readonly string[];
  sampleQuantity: number;
  measurementPlan: TrialMeasurementPlanInput;
  reason: string;
}): boolean {
  return (
    member(value.purpose, trialPurposes) &&
    textValue(value.objective, 1, 2000) &&
    dateTime(value.plannedStartAt) &&
    dateTime(value.plannedEndAt) &&
    Date.parse(value.plannedStartAt) < Date.parse(value.plannedEndAt) &&
    value.resources.length >= 2 &&
    value.resources.length <= 50 &&
    value.resources.every(isResourceInput) &&
    value.responsibleMemberGlobalIds.length >= 1 &&
    value.responsibleMemberGlobalIds.length <= 50 &&
    value.responsibleMemberGlobalIds.every((memberId) =>
      uuidPattern.test(memberId),
    ) &&
    unique(value.responsibleMemberGlobalIds) &&
    whole(value.sampleQuantity, 1) &&
    exact(value.measurementPlan, ["description"]) &&
    textValue(value.measurementPlan.description, 1, 1000) &&
    textValue(value.reason, 1, 500)
  );
}

function validCreatePlan(value: CreateTrialPlanCommand): boolean {
  return (
    exact(value, [
      "toolingMasterGlobalId",
      "purpose",
      "objective",
      "plannedStartAt",
      "plannedEndAt",
      "resources",
      "responsibleMemberGlobalIds",
      "sampleQuantity",
      "measurementPlan",
      "reason",
    ]) &&
    uuidPattern.test(value.toolingMasterGlobalId) &&
    validPlanFields(value)
  );
}

function validRevisePlan(value: CreateTrialPlanRevisionCommand): boolean {
  return (
    exact(value, [
      "expectedRevisionGlobalId",
      "expectedRevisionSnapshotHash",
      "expectedPlanVersion",
      "purpose",
      "objective",
      "plannedStartAt",
      "plannedEndAt",
      "resources",
      "responsibleMemberGlobalIds",
      "sampleQuantity",
      "measurementPlan",
      "reason",
    ]) &&
    uuidPattern.test(value.expectedRevisionGlobalId) &&
    hashPattern.test(value.expectedRevisionSnapshotHash) &&
    whole(value.expectedPlanVersion, 1) &&
    validPlanFields(value)
  );
}

function validRound(value: CreatePlannedTrialRoundCommand): boolean {
  return (
    exactWithOptional(
      value,
      [
        "expectedPlanRevisionGlobalId",
        "expectedPlanRevisionSnapshotHash",
        "reason",
      ],
      ["displayLabel"],
    ) &&
    uuidPattern.test(value.expectedPlanRevisionGlobalId) &&
    hashPattern.test(value.expectedPlanRevisionSnapshotHash) &&
    (value.displayLabel === undefined ||
      value.displayLabel === null ||
      roundLabelPattern.test(value.displayLabel)) &&
    textValue(value.reason, 1, 500)
  );
}

function isActionInput(value: unknown): value is TrialPlanActionInput {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "actionKey",
      "title",
      "description",
      "responsibleMemberGlobalId",
      "dueAt",
      "severity",
      "blocking",
    ]) &&
    typeof item.actionKey === "string" &&
    actionKeyPattern.test(item.actionKey) &&
    textValue(item.title, 1, 280) &&
    (item.description === null || textValue(item.description, 1, 2000)) &&
    typeof item.responsibleMemberGlobalId === "string" &&
    uuidPattern.test(item.responsibleMemberGlobalId) &&
    dateTime(item.dueAt) &&
    member(item.severity, trialActionSeverities) &&
    typeof item.blocking === "boolean"
  );
}

function validGenerateActions(value: GenerateTrialPlanActionsCommand): boolean {
  return (
    exactWithOptional(
      value,
      [
        "expectedPlanRevisionGlobalId",
        "expectedPlanRevisionSnapshotHash",
        "actions",
        "reason",
      ],
      ["trialRoundGlobalId"],
    ) &&
    uuidPattern.test(value.expectedPlanRevisionGlobalId) &&
    hashPattern.test(value.expectedPlanRevisionSnapshotHash) &&
    (value.trialRoundGlobalId === undefined ||
      value.trialRoundGlobalId === null ||
      uuidPattern.test(value.trialRoundGlobalId)) &&
    value.actions.length >= 1 &&
    value.actions.length <= 50 &&
    value.actions.every(isActionInput) &&
    unique(value.actions.map((action) => action.actionKey)) &&
    textValue(value.reason, 1, 500)
  );
}

function cancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new TrialRequestCancelledError();
}

function replayHeader(response: Response): boolean | null {
  const value = response.headers.get("Idempotency-Replayed");
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

export class LiveTrialDataSource implements TrialDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadWorkspace(
    projectId: string,
    signal: AbortSignal,
  ): Promise<TrialPlanningWorkspace> {
    const expectedProjectId = requireUuid(projectId);
    cancelled(signal);
    try {
      return await this.http.request<TrialPlanningWorkspace>(
        `/projects/${expectedProjectId}/trials`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is TrialPlanningWorkspace =>
            isTrialPlanningWorkspace(value) &&
            value.projectGlobalId === expectedProjectId,
        },
      );
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  async loadPlan(
    projectId: string,
    planId: string,
    signal: AbortSignal,
  ): Promise<TrialPlanDetail> {
    const expectedProjectId = requireUuid(projectId);
    const expectedPlanId = requireUuid(planId);
    cancelled(signal);
    try {
      return await this.http.request<TrialPlanDetail>(
        `/projects/${expectedProjectId}/trial-plans/${expectedPlanId}`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is TrialPlanDetail =>
            isTrialPlanDetail(value) &&
            value.projectGlobalId === expectedProjectId &&
            value.planGlobalId === expectedPlanId,
        },
      );
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  private async command(
    path: string,
    projectId: string,
    planId: string | null,
    body: object,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult> {
    cancelled(context.signal);
    let replayed = false;
    try {
      const detail = await this.http.request<TrialPlanDetail>(
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
          validate: (value): value is TrialPlanDetail =>
            isTrialPlanDetail(value) &&
            value.projectGlobalId === projectId &&
            (planId === null || value.planGlobalId === planId),
          validateResponse: (response) => {
            const header = replayHeader(response);
            if (header === null) return false;
            replayed = header;
            return true;
          },
        },
      );
      return { detail, replayed };
    } catch (error) {
      cancelled(context.signal);
      throw error;
    }
  }

  createPlan(
    projectId: string,
    command: CreateTrialPlanCommand,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    if (!validContext(context) || !validCreatePlan(command))
      return Promise.reject(requestNotReady());
    return this.command(
      `/projects/${expectedProjectId}/trials`,
      expectedProjectId,
      null,
      command,
      context,
    );
  }

  revisePlan(
    projectId: string,
    planId: string,
    command: CreateTrialPlanRevisionCommand,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedPlanId = requireUuid(planId);
    if (!validContext(context) || !validRevisePlan(command))
      return Promise.reject(requestNotReady());
    return this.command(
      `/projects/${expectedProjectId}/trial-plans/${expectedPlanId}/revisions`,
      expectedProjectId,
      expectedPlanId,
      command,
      context,
    );
  }

  createRound(
    projectId: string,
    planId: string,
    command: CreatePlannedTrialRoundCommand,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedPlanId = requireUuid(planId);
    if (!validContext(context) || !validRound(command))
      return Promise.reject(requestNotReady());
    return this.command(
      `/projects/${expectedProjectId}/trial-plans/${expectedPlanId}/rounds`,
      expectedProjectId,
      expectedPlanId,
      command,
      context,
    );
  }

  generateActions(
    projectId: string,
    planId: string,
    command: GenerateTrialPlanActionsCommand,
    context: TrialCommandContext,
  ): Promise<TrialCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedPlanId = requireUuid(planId);
    if (!validContext(context) || !validGenerateActions(command))
      return Promise.reject(requestNotReady());
    return this.command(
      `/projects/${expectedProjectId}/trial-plans/${expectedPlanId}/actions:generate`,
      expectedProjectId,
      expectedPlanId,
      command,
      context,
    );
  }
}
