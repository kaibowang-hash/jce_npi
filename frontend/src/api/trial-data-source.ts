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

export const trialLockedReferenceKinds = [
  "design_baseline",
  "part_revision",
  "tooling_revision",
  "tooling_set",
  "tooling_set_binding",
  "cavity",
  "process_chain",
  "inspection_document",
] as const;
export type TrialLockedReferenceKind =
  (typeof trialLockedReferenceKinds)[number];

export const trialParameterValueKinds = [
  "decimal",
  "integer",
  "text",
  "boolean",
] as const;
export type TrialParameterValueKind = (typeof trialParameterValueKinds)[number];

export const trialEvidenceRoles = [
  "photo",
  "video",
  "parameter_curve",
  "measurement_report",
  "customer_feedback",
] as const;
export type TrialEvidenceRole = (typeof trialEvidenceRoles)[number];

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

export interface TrialLockedReferenceInput {
  globalId: string;
  kind: TrialLockedReferenceKind;
  expectedOptimisticVersion: number;
}

export interface TrialLockedReference {
  globalId: string;
  kind: TrialLockedReferenceKind;
  optimisticVersion: number;
  snapshotHash: string;
}

export interface TrialMaterialObservationInput {
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
  lotBatchCode: string;
  label: string;
  color: string | null;
  additive: string | null;
  observedAt: string;
}

export interface TrialMaterialObservation extends TrialMaterialObservationInput {
  confirmedByUserId: string;
  erpVerification: "unavailable";
}

export interface TrialParameterDefinitionInput {
  key: string;
  category: string;
  valueKind: TrialParameterValueKind;
  required: boolean;
  unit: string | null;
  targetValue: string | null;
  lowerLimit: string | null;
  upperLimit: string | null;
}

export type TrialParameterDefinition = TrialParameterDefinitionInput;

export interface TrialRoundInputLockRevision {
  schemaVersion: 1;
  globalId: string;
  inputLockGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  trialRoundGlobalId: string;
  trialPlanRevisionGlobalId: string;
  trialPlanRevisionSnapshotHash: string;
  lockVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  references: readonly TrialLockedReference[];
  material: TrialMaterialObservation;
  parameterDefinitions: readonly TrialParameterDefinition[];
  reason: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface TrialActualResourceInput {
  kind: "machine" | "auxiliary_equipment";
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
  label: string;
}

export interface TrialActualResource extends TrialActualResourceInput {
  erpVerification: "unavailable";
}

export interface TrialEnvironmentObservationInput {
  key: string;
  value: string;
  unit: string | null;
  observedAt: string;
}

export type TrialEnvironmentObservation = TrialEnvironmentObservationInput;

export interface TrialParameterObservationInput {
  definitionKey: string;
  state: "measured" | "not_measured";
  value: string | null;
  unit: string | null;
  source: "manual" | null;
  observedAt: string | null;
}

export type TrialParameterObservation = TrialParameterObservationInput;

export interface TrialRoundActualRevision {
  schemaVersion: 1;
  globalId: string;
  actualGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  trialRoundGlobalId: string;
  inputLockRevisionGlobalId: string;
  inputLockRevisionSnapshotHash: string;
  actualVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  acquisitionMode: "manual";
  resources: readonly TrialActualResource[];
  material: TrialMaterialObservation;
  environment: readonly TrialEnvironmentObservation[];
  parameters: readonly TrialParameterObservation[];
  operatorUserId: string;
  confirmedByUserId: string;
  executionStartedAt: string;
  machineImport: "unavailable";
  reason: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface TrialSampleBatchInput {
  label: string;
  cavityGlobalIds: readonly string[];
  quantity: number;
  unit: string;
  packaging: string;
  destination: string;
  feedbackText: string | null;
  feedbackSource: string | null;
  feedbackObservedAt: string | null;
}

export interface TrialSampleBatchRevision extends TrialSampleBatchInput {
  schemaVersion: 1;
  globalId: string;
  sampleBatchGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  trialRoundGlobalId: string;
  inputLockRevisionGlobalId: string;
  inputLockRevisionSnapshotHash: string;
  sampleVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  materialSnapshotHash: string;
  reason: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface TrialEvidenceReference {
  schemaVersion: 1;
  globalId: string;
  tenantId: string;
  projectGlobalId: string;
  trialRoundGlobalId: string;
  role: TrialEvidenceRole;
  sampleBatchRevisionGlobalId: string | null;
  sampleBatchRevisionSnapshotHash: string | null;
  fileRevisionGlobalId: string;
  fileSha256: string;
  fileSizeBytes: number;
  fileMimeType: string;
  scanState: "clean";
  privacy: "private";
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface TrialPendingFileRevision {
  globalId: string;
  optimisticVersion: number;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  sha256: string;
  scanState: "pending" | "clean" | "infected" | "failed";
  privacy: "private";
}

export interface TrialExecutionPermissions {
  canPrepare: boolean;
  canStart: boolean;
  canRecordActual: boolean;
  canManageSamples: boolean;
  canManageEvidence: boolean;
}

export interface TrialExecutionWorkspace {
  projectGlobalId: string;
  round: TrialRoundSummary;
  inputLocks: readonly TrialRoundInputLockRevision[];
  actualRevisions: readonly TrialRoundActualRevision[];
  sampleBatchRevisions: readonly TrialSampleBatchRevision[];
  evidence: readonly TrialEvidenceReference[];
  pendingFiles: readonly TrialPendingFileRevision[];
  missingFacts: readonly string[];
  capabilities: {
    machineImport: "unavailable";
    erpQuality: "unavailable";
    conclusion: "unavailable";
    gateEffect: "unavailable";
    approvedBaseline: "unavailable";
  };
  permissions: TrialExecutionPermissions;
}

export interface PrepareTrialRoundCommand {
  expectedRoundOptimisticVersion: number;
  references: readonly TrialLockedReferenceInput[];
  material: TrialMaterialObservationInput;
  parameterDefinitions: readonly TrialParameterDefinitionInput[];
  reason: string;
}

export interface TrialActualContextInput {
  resources: readonly TrialActualResourceInput[];
  material: TrialMaterialObservationInput;
  environment: readonly TrialEnvironmentObservationInput[];
  parameters: readonly TrialParameterObservationInput[];
  operatorUserId: string;
  executionStartedAt: string;
  reason: string;
}

export interface StartTrialRoundCommand extends TrialActualContextInput {
  expectedRoundOptimisticVersion: number;
  expectedInputLockRevisionGlobalId: string;
  expectedInputLockVersion: number;
}

export interface AppendTrialActualRevisionCommand extends TrialActualContextInput {
  expectedRoundOptimisticVersion: number;
  expectedActualRevisionGlobalId: string;
  expectedActualVersion: number;
}

export interface CreateTrialSampleBatchCommand {
  expectedRoundOptimisticVersion: number;
  expectedInputLockRevisionGlobalId: string;
  sample: TrialSampleBatchInput;
  reason: string;
}

export interface AppendTrialSampleBatchRevisionCommand {
  expectedRoundOptimisticVersion: number;
  expectedRevisionGlobalId: string;
  expectedSampleVersion: number;
  sample: TrialSampleBatchInput;
  reason: string;
}

export interface UploadTrialEvidenceFileCommand {
  expectedRoundOptimisticVersion: number;
  file: File;
}

export interface BindTrialEvidenceCommand {
  expectedRoundOptimisticVersion: number;
  role: TrialEvidenceRole;
  fileRevisionGlobalId: string;
  expectedFileOptimisticVersion: number;
  sampleBatchRevisionGlobalId?: string | null | undefined;
  expectedSampleVersion?: number | null | undefined;
}

export interface TrialExecutionCommandResult {
  workspace: TrialExecutionWorkspace;
  replayed: boolean;
}

export interface TrialEvidenceDownload {
  blob: Blob;
  fileName: string;
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
  loadRoundExecution(
    projectId: string,
    roundId: string,
    signal: AbortSignal,
  ): Promise<TrialExecutionWorkspace>;
  prepareRound(
    projectId: string,
    roundId: string,
    command: PrepareTrialRoundCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult>;
  startRound(
    projectId: string,
    roundId: string,
    command: StartTrialRoundCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult>;
  appendActualRevision(
    projectId: string,
    roundId: string,
    command: AppendTrialActualRevisionCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult>;
  createSampleBatch(
    projectId: string,
    roundId: string,
    command: CreateTrialSampleBatchCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult>;
  appendSampleBatchRevision(
    projectId: string,
    roundId: string,
    sampleBatchId: string,
    command: AppendTrialSampleBatchRevisionCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult>;
  uploadEvidenceFile(
    projectId: string,
    roundId: string,
    command: UploadTrialEvidenceFileCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult>;
  bindEvidence(
    projectId: string,
    roundId: string,
    command: BindTrialEvidenceCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult>;
  downloadEvidence(
    projectId: string,
    roundId: string,
    evidence: TrialEvidenceReference,
    context: Omit<TrialCommandContext, "idempotencyKey">,
  ): Promise<TrialEvidenceDownload>;
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

function nullableText(value: unknown, maximum: number): value is string | null {
  return value === null || textValue(value, 1, maximum);
}

function email(value: unknown): value is string {
  return textValue(value, 3, 254) && value.includes("@");
}

function nullableUuid(value: unknown): value is string | null {
  return (
    value === null || (typeof value === "string" && uuidPattern.test(value))
  );
}

function nullableHash(value: unknown): value is string | null {
  return (
    value === null || (typeof value === "string" && hashPattern.test(value))
  );
}

function isLockedReference(value: unknown): value is TrialLockedReference {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["globalId", "kind", "optimisticVersion", "snapshotHash"]) &&
    typeof item.globalId === "string" &&
    uuidPattern.test(item.globalId) &&
    member(item.kind, trialLockedReferenceKinds) &&
    whole(item.optimisticVersion, 1) &&
    typeof item.snapshotHash === "string" &&
    hashPattern.test(item.snapshotHash)
  );
}

function isMaterialObservation(
  value: unknown,
): value is TrialMaterialObservation {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "sourceSystem",
      "sourceObjectId",
      "lotBatchCode",
      "label",
      "color",
      "additive",
      "observedAt",
      "confirmedByUserId",
      "erpVerification",
    ]) &&
    member(item.sourceSystem, ["NPI_ONE", "ERPNEXT"] as const) &&
    typeof item.sourceObjectId === "string" &&
    referencePattern.test(item.sourceObjectId) &&
    typeof item.lotBatchCode === "string" &&
    referencePattern.test(item.lotBatchCode) &&
    textValue(item.label, 1, 140) &&
    nullableText(item.color, 80) &&
    nullableText(item.additive, 140) &&
    dateTime(item.observedAt) &&
    email(item.confirmedByUserId) &&
    item.erpVerification === "unavailable"
  );
}

function isParameterDefinition(
  value: unknown,
): value is TrialParameterDefinition {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "key",
      "category",
      "valueKind",
      "required",
      "unit",
      "targetValue",
      "lowerLimit",
      "upperLimit",
    ]) &&
    typeof item.key === "string" &&
    referencePattern.test(item.key) &&
    textValue(item.category, 1, 80) &&
    member(item.valueKind, trialParameterValueKinds) &&
    typeof item.required === "boolean" &&
    nullableText(item.unit, 32) &&
    nullableText(item.targetValue, 280) &&
    nullableText(item.lowerLimit, 64) &&
    nullableText(item.upperLimit, 64)
  );
}

function isInputLock(value: unknown): value is TrialRoundInputLockRevision {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "schemaVersion",
      "globalId",
      "inputLockGlobalId",
      "tenantId",
      "projectGlobalId",
      "trialRoundGlobalId",
      "trialPlanRevisionGlobalId",
      "trialPlanRevisionSnapshotHash",
      "lockVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "references",
      "material",
      "parameterDefinitions",
      "reason",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) ||
    item.schemaVersion !== 1 ||
    ![
      item.globalId,
      item.inputLockGlobalId,
      item.projectGlobalId,
      item.trialRoundGlobalId,
      item.trialPlanRevisionGlobalId,
      item.requestId,
    ].every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) ||
    typeof item.tenantId !== "string" ||
    !referencePattern.test(item.tenantId) ||
    typeof item.trialPlanRevisionSnapshotHash !== "string" ||
    !hashPattern.test(item.trialPlanRevisionSnapshotHash) ||
    !whole(item.lockVersion, 1) ||
    !nullableUuid(item.predecessorGlobalId) ||
    !nullableHash(item.predecessorSnapshotHash) ||
    !Array.isArray(item.references) ||
    item.references.length < 8 ||
    item.references.length > 100 ||
    !item.references.every(isLockedReference) ||
    !unique(
      item.references.map(
        (reference) => `${reference.kind}:${reference.globalId}`,
      ),
    ) ||
    !isMaterialObservation(item.material) ||
    !Array.isArray(item.parameterDefinitions) ||
    item.parameterDefinitions.length < 1 ||
    item.parameterDefinitions.length > 250 ||
    !item.parameterDefinitions.every(isParameterDefinition) ||
    !unique(item.parameterDefinitions.map((definition) => definition.key)) ||
    !textValue(item.reason, 1, 500) ||
    !email(item.createdByUserId) ||
    !dateTime(item.createdAt) ||
    !textValue(item.traceId, 8, 128) ||
    typeof item.snapshotHash !== "string" ||
    !hashPattern.test(item.snapshotHash)
  )
    return false;
  return item.lockVersion === 1
    ? item.predecessorGlobalId === null && item.predecessorSnapshotHash === null
    : item.predecessorGlobalId !== null &&
        item.predecessorSnapshotHash !== null;
}

function isActualResource(value: unknown): value is TrialActualResource {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "kind",
      "sourceSystem",
      "sourceObjectId",
      "label",
      "erpVerification",
    ]) &&
    member(item.kind, ["machine", "auxiliary_equipment"] as const) &&
    member(item.sourceSystem, ["NPI_ONE", "ERPNEXT"] as const) &&
    typeof item.sourceObjectId === "string" &&
    referencePattern.test(item.sourceObjectId) &&
    textValue(item.label, 1, 140) &&
    item.erpVerification === "unavailable"
  );
}

function isEnvironmentObservation(
  value: unknown,
): value is TrialEnvironmentObservation {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["key", "value", "unit", "observedAt"]) &&
    typeof item.key === "string" &&
    referencePattern.test(item.key) &&
    textValue(item.value, 1, 140) &&
    nullableText(item.unit, 32) &&
    dateTime(item.observedAt)
  );
}

function isParameterObservation(
  value: unknown,
): value is TrialParameterObservation {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "definitionKey",
      "state",
      "value",
      "unit",
      "source",
      "observedAt",
    ]) ||
    typeof item.definitionKey !== "string" ||
    !referencePattern.test(item.definitionKey) ||
    !member(item.state, ["measured", "not_measured"] as const) ||
    !nullableText(item.value, 280) ||
    !nullableText(item.unit, 32) ||
    !(item.source === null || item.source === "manual") ||
    !(item.observedAt === null || dateTime(item.observedAt))
  )
    return false;
  return item.state === "measured"
    ? item.value !== null &&
        item.source === "manual" &&
        item.observedAt !== null
    : item.value === null &&
        item.unit === null &&
        item.source === null &&
        item.observedAt === null;
}

function isActualRevision(value: unknown): value is TrialRoundActualRevision {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "schemaVersion",
      "globalId",
      "actualGlobalId",
      "tenantId",
      "projectGlobalId",
      "trialRoundGlobalId",
      "inputLockRevisionGlobalId",
      "inputLockRevisionSnapshotHash",
      "actualVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "acquisitionMode",
      "resources",
      "material",
      "environment",
      "parameters",
      "operatorUserId",
      "confirmedByUserId",
      "executionStartedAt",
      "machineImport",
      "reason",
      "createdAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) ||
    item.schemaVersion !== 1 ||
    ![
      item.globalId,
      item.actualGlobalId,
      item.projectGlobalId,
      item.trialRoundGlobalId,
      item.inputLockRevisionGlobalId,
      item.requestId,
    ].every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) ||
    typeof item.tenantId !== "string" ||
    !referencePattern.test(item.tenantId) ||
    typeof item.inputLockRevisionSnapshotHash !== "string" ||
    !hashPattern.test(item.inputLockRevisionSnapshotHash) ||
    !whole(item.actualVersion, 1) ||
    !nullableUuid(item.predecessorGlobalId) ||
    !nullableHash(item.predecessorSnapshotHash) ||
    item.acquisitionMode !== "manual" ||
    !Array.isArray(item.resources) ||
    item.resources.length < 1 ||
    item.resources.length > 25 ||
    !item.resources.every(isActualResource) ||
    !isMaterialObservation(item.material) ||
    !Array.isArray(item.environment) ||
    item.environment.length > 50 ||
    !item.environment.every(isEnvironmentObservation) ||
    !Array.isArray(item.parameters) ||
    item.parameters.length < 1 ||
    item.parameters.length > 250 ||
    !item.parameters.every(isParameterObservation) ||
    !unique(item.parameters.map((parameter) => parameter.definitionKey)) ||
    !email(item.operatorUserId) ||
    !email(item.confirmedByUserId) ||
    !dateTime(item.executionStartedAt) ||
    item.machineImport !== "unavailable" ||
    !textValue(item.reason, 1, 500) ||
    !dateTime(item.createdAt) ||
    !textValue(item.traceId, 8, 128) ||
    typeof item.snapshotHash !== "string" ||
    !hashPattern.test(item.snapshotHash)
  )
    return false;
  return item.actualVersion === 1
    ? item.predecessorGlobalId === null && item.predecessorSnapshotHash === null
    : item.predecessorGlobalId !== null &&
        item.predecessorSnapshotHash !== null;
}

function isSampleRevision(value: unknown): value is TrialSampleBatchRevision {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "schemaVersion",
      "globalId",
      "sampleBatchGlobalId",
      "tenantId",
      "projectGlobalId",
      "trialRoundGlobalId",
      "inputLockRevisionGlobalId",
      "inputLockRevisionSnapshotHash",
      "sampleVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "label",
      "cavityGlobalIds",
      "materialSnapshotHash",
      "quantity",
      "unit",
      "packaging",
      "destination",
      "feedbackText",
      "feedbackSource",
      "feedbackObservedAt",
      "reason",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) ||
    item.schemaVersion !== 1 ||
    ![
      item.globalId,
      item.sampleBatchGlobalId,
      item.projectGlobalId,
      item.trialRoundGlobalId,
      item.inputLockRevisionGlobalId,
      item.requestId,
    ].every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) ||
    typeof item.tenantId !== "string" ||
    !referencePattern.test(item.tenantId) ||
    typeof item.inputLockRevisionSnapshotHash !== "string" ||
    !hashPattern.test(item.inputLockRevisionSnapshotHash) ||
    !whole(item.sampleVersion, 1) ||
    !nullableUuid(item.predecessorGlobalId) ||
    !nullableHash(item.predecessorSnapshotHash) ||
    typeof item.label !== "string" ||
    !referencePattern.test(item.label) ||
    !Array.isArray(item.cavityGlobalIds) ||
    item.cavityGlobalIds.length < 1 ||
    item.cavityGlobalIds.length > 128 ||
    !item.cavityGlobalIds.every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) ||
    !unique(item.cavityGlobalIds) ||
    typeof item.materialSnapshotHash !== "string" ||
    !hashPattern.test(item.materialSnapshotHash) ||
    !whole(item.quantity, 1) ||
    !textValue(item.unit, 1, 32) ||
    !textValue(item.packaging, 1, 280) ||
    !textValue(item.destination, 1, 280) ||
    !nullableText(item.feedbackText, 4000) ||
    !nullableText(item.feedbackSource, 140) ||
    !(item.feedbackObservedAt === null || dateTime(item.feedbackObservedAt)) ||
    !textValue(item.reason, 1, 500) ||
    !email(item.createdByUserId) ||
    !dateTime(item.createdAt) ||
    !textValue(item.traceId, 8, 128) ||
    typeof item.snapshotHash !== "string" ||
    !hashPattern.test(item.snapshotHash)
  )
    return false;
  const feedback = [
    item.feedbackText,
    item.feedbackSource,
    item.feedbackObservedAt,
  ];
  if (
    !feedback.every((candidate) => candidate === null) &&
    feedback.some((candidate) => candidate === null)
  )
    return false;
  return item.sampleVersion === 1
    ? item.predecessorGlobalId === null && item.predecessorSnapshotHash === null
    : item.predecessorGlobalId !== null &&
        item.predecessorSnapshotHash !== null;
}

function isEvidence(value: unknown): value is TrialEvidenceReference {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "schemaVersion",
      "globalId",
      "tenantId",
      "projectGlobalId",
      "trialRoundGlobalId",
      "role",
      "sampleBatchRevisionGlobalId",
      "sampleBatchRevisionSnapshotHash",
      "fileRevisionGlobalId",
      "fileSha256",
      "fileSizeBytes",
      "fileMimeType",
      "scanState",
      "privacy",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) ||
    item.schemaVersion !== 1 ||
    ![
      item.globalId,
      item.projectGlobalId,
      item.trialRoundGlobalId,
      item.fileRevisionGlobalId,
      item.requestId,
    ].every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) ||
    typeof item.tenantId !== "string" ||
    !referencePattern.test(item.tenantId) ||
    !member(item.role, trialEvidenceRoles) ||
    !nullableUuid(item.sampleBatchRevisionGlobalId) ||
    !nullableHash(item.sampleBatchRevisionSnapshotHash) ||
    typeof item.fileSha256 !== "string" ||
    !hashPattern.test(item.fileSha256) ||
    !whole(item.fileSizeBytes, 1) ||
    !textValue(item.fileMimeType, 1, 140) ||
    item.scanState !== "clean" ||
    item.privacy !== "private" ||
    !email(item.createdByUserId) ||
    !dateTime(item.createdAt) ||
    !textValue(item.traceId, 8, 128) ||
    typeof item.snapshotHash !== "string" ||
    !hashPattern.test(item.snapshotHash)
  )
    return false;
  return (
    (item.sampleBatchRevisionGlobalId === null) ===
    (item.sampleBatchRevisionSnapshotHash === null)
  );
}

function isPendingFile(value: unknown): value is TrialPendingFileRevision {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "globalId",
      "optimisticVersion",
      "fileName",
      "mimeType",
      "sizeBytes",
      "sha256",
      "scanState",
      "privacy",
    ]) &&
    typeof item.globalId === "string" &&
    uuidPattern.test(item.globalId) &&
    whole(item.optimisticVersion, 1) &&
    textValue(item.fileName, 1, 255) &&
    textValue(item.mimeType, 1, 140) &&
    whole(item.sizeBytes, 1) &&
    typeof item.sha256 === "string" &&
    hashPattern.test(item.sha256) &&
    member(item.scanState, [
      "pending",
      "clean",
      "infected",
      "failed",
    ] as const) &&
    item.privacy === "private"
  );
}

function isExecutionCapabilities(
  value: unknown,
): value is TrialExecutionWorkspace["capabilities"] {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "machineImport",
      "erpQuality",
      "conclusion",
      "gateEffect",
      "approvedBaseline",
    ]) && Object.values(item).every((candidate) => candidate === "unavailable")
  );
}

function isExecutionPermissions(
  value: unknown,
): value is TrialExecutionPermissions {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "canPrepare",
      "canStart",
      "canRecordActual",
      "canManageSamples",
      "canManageEvidence",
    ]) &&
    Object.values(item).every((candidate) => typeof candidate === "boolean")
  );
}

export function isTrialExecutionWorkspace(
  value: unknown,
): value is TrialExecutionWorkspace {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "projectGlobalId",
      "round",
      "inputLocks",
      "actualRevisions",
      "sampleBatchRevisions",
      "evidence",
      "pendingFiles",
      "missingFacts",
      "capabilities",
      "permissions",
    ]) ||
    typeof item.projectGlobalId !== "string" ||
    !uuidPattern.test(item.projectGlobalId) ||
    !isTrialRound(item.round) ||
    !Array.isArray(item.inputLocks) ||
    item.inputLocks.length > 1000 ||
    !item.inputLocks.every(isInputLock) ||
    !Array.isArray(item.actualRevisions) ||
    item.actualRevisions.length > 1000 ||
    !item.actualRevisions.every(isActualRevision) ||
    !Array.isArray(item.sampleBatchRevisions) ||
    item.sampleBatchRevisions.length > 5000 ||
    !item.sampleBatchRevisions.every(isSampleRevision) ||
    !Array.isArray(item.evidence) ||
    item.evidence.length > 5000 ||
    !item.evidence.every(isEvidence) ||
    !Array.isArray(item.pendingFiles) ||
    item.pendingFiles.length > 500 ||
    !item.pendingFiles.every(isPendingFile) ||
    !Array.isArray(item.missingFacts) ||
    item.missingFacts.length > 250 ||
    !item.missingFacts.every((candidate) => textValue(candidate, 1, 128)) ||
    !unique(item.missingFacts) ||
    !isExecutionCapabilities(item.capabilities) ||
    !isExecutionPermissions(item.permissions)
  )
    return false;
  const projectId = item.projectGlobalId;
  const roundId = item.round.globalId;
  const nested = [
    ...item.inputLocks,
    ...item.actualRevisions,
    ...item.sampleBatchRevisions,
    ...item.evidence,
  ];
  return (
    item.round.projectGlobalId === projectId &&
    nested.every(
      (candidate) =>
        candidate.projectGlobalId === projectId &&
        candidate.trialRoundGlobalId === roundId,
    ) &&
    unique(item.inputLocks.map((candidate) => candidate.globalId)) &&
    unique(item.actualRevisions.map((candidate) => candidate.globalId)) &&
    unique(item.sampleBatchRevisions.map((candidate) => candidate.globalId)) &&
    unique(item.evidence.map((candidate) => candidate.globalId)) &&
    unique(item.pendingFiles.map((candidate) => candidate.globalId))
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

function validMaterialInput(
  value: unknown,
): value is TrialMaterialObservationInput {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "sourceSystem",
      "sourceObjectId",
      "lotBatchCode",
      "label",
      "color",
      "additive",
      "observedAt",
    ]) &&
    member(item.sourceSystem, ["NPI_ONE", "ERPNEXT"] as const) &&
    typeof item.sourceObjectId === "string" &&
    referencePattern.test(item.sourceObjectId) &&
    typeof item.lotBatchCode === "string" &&
    referencePattern.test(item.lotBatchCode) &&
    textValue(item.label, 1, 140) &&
    nullableText(item.color, 80) &&
    nullableText(item.additive, 140) &&
    dateTime(item.observedAt)
  );
}

function validReferenceInput(
  value: unknown,
): value is TrialLockedReferenceInput {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["globalId", "kind", "expectedOptimisticVersion"]) &&
    typeof item.globalId === "string" &&
    uuidPattern.test(item.globalId) &&
    member(item.kind, trialLockedReferenceKinds) &&
    whole(item.expectedOptimisticVersion, 1)
  );
}

function validParameterDefinitionInput(
  value: unknown,
): value is TrialParameterDefinitionInput {
  return isParameterDefinition(value);
}

function validPrepare(value: PrepareTrialRoundCommand): boolean {
  return (
    exact(value, [
      "expectedRoundOptimisticVersion",
      "references",
      "material",
      "parameterDefinitions",
      "reason",
    ]) &&
    whole(value.expectedRoundOptimisticVersion, 1) &&
    value.references.length >= 8 &&
    value.references.length <= 100 &&
    value.references.every(validReferenceInput) &&
    unique(
      value.references.map(
        (reference) => `${reference.kind}:${reference.globalId}`,
      ),
    ) &&
    validMaterialInput(value.material) &&
    value.parameterDefinitions.length >= 1 &&
    value.parameterDefinitions.length <= 250 &&
    value.parameterDefinitions.every(validParameterDefinitionInput) &&
    unique(value.parameterDefinitions.map((definition) => definition.key)) &&
    textValue(value.reason, 1, 500)
  );
}

function validActualResourceInput(
  value: unknown,
): value is TrialActualResourceInput {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["kind", "sourceSystem", "sourceObjectId", "label"]) &&
    member(item.kind, ["machine", "auxiliary_equipment"] as const) &&
    member(item.sourceSystem, ["NPI_ONE", "ERPNEXT"] as const) &&
    typeof item.sourceObjectId === "string" &&
    referencePattern.test(item.sourceObjectId) &&
    textValue(item.label, 1, 140)
  );
}

function validEnvironmentInput(
  value: unknown,
): value is TrialEnvironmentObservationInput {
  return isEnvironmentObservation(value);
}

function validParameterInput(
  value: unknown,
): value is TrialParameterObservationInput {
  return isParameterObservation(value);
}

function validActualContext(value: TrialActualContextInput): boolean {
  return (
    value.resources.length >= 1 &&
    value.resources.length <= 25 &&
    value.resources.every(validActualResourceInput) &&
    validMaterialInput(value.material) &&
    value.environment.length <= 50 &&
    value.environment.every(validEnvironmentInput) &&
    value.parameters.length >= 1 &&
    value.parameters.length <= 250 &&
    value.parameters.every(validParameterInput) &&
    unique(value.parameters.map((parameter) => parameter.definitionKey)) &&
    email(value.operatorUserId) &&
    dateTime(value.executionStartedAt) &&
    textValue(value.reason, 1, 500)
  );
}

function validStart(value: StartTrialRoundCommand): boolean {
  return (
    exact(value, [
      "expectedRoundOptimisticVersion",
      "expectedInputLockRevisionGlobalId",
      "expectedInputLockVersion",
      "resources",
      "material",
      "environment",
      "parameters",
      "operatorUserId",
      "executionStartedAt",
      "reason",
    ]) &&
    whole(value.expectedRoundOptimisticVersion, 1) &&
    uuidPattern.test(value.expectedInputLockRevisionGlobalId) &&
    whole(value.expectedInputLockVersion, 1) &&
    validActualContext(value)
  );
}

function validActualRevision(value: AppendTrialActualRevisionCommand): boolean {
  return (
    exact(value, [
      "expectedRoundOptimisticVersion",
      "expectedActualRevisionGlobalId",
      "expectedActualVersion",
      "resources",
      "material",
      "environment",
      "parameters",
      "operatorUserId",
      "executionStartedAt",
      "reason",
    ]) &&
    whole(value.expectedRoundOptimisticVersion, 1) &&
    uuidPattern.test(value.expectedActualRevisionGlobalId) &&
    whole(value.expectedActualVersion, 1) &&
    validActualContext(value)
  );
}

function validSampleInput(value: unknown): value is TrialSampleBatchInput {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "label",
      "cavityGlobalIds",
      "quantity",
      "unit",
      "packaging",
      "destination",
      "feedbackText",
      "feedbackSource",
      "feedbackObservedAt",
    ]) ||
    typeof item.label !== "string" ||
    !referencePattern.test(item.label) ||
    !Array.isArray(item.cavityGlobalIds) ||
    item.cavityGlobalIds.length < 1 ||
    item.cavityGlobalIds.length > 128 ||
    !item.cavityGlobalIds.every(
      (candidate) =>
        typeof candidate === "string" && uuidPattern.test(candidate),
    ) ||
    !unique(item.cavityGlobalIds) ||
    !whole(item.quantity, 1) ||
    !textValue(item.unit, 1, 32) ||
    !textValue(item.packaging, 1, 280) ||
    !textValue(item.destination, 1, 280) ||
    !nullableText(item.feedbackText, 4000) ||
    !nullableText(item.feedbackSource, 140) ||
    !(item.feedbackObservedAt === null || dateTime(item.feedbackObservedAt))
  )
    return false;
  const feedback = [
    item.feedbackText,
    item.feedbackSource,
    item.feedbackObservedAt,
  ];
  return (
    feedback.every((candidate) => candidate === null) ||
    feedback.every((candidate) => candidate !== null)
  );
}

function validCreateSample(value: CreateTrialSampleBatchCommand): boolean {
  return (
    exact(value, [
      "expectedRoundOptimisticVersion",
      "expectedInputLockRevisionGlobalId",
      "sample",
      "reason",
    ]) &&
    whole(value.expectedRoundOptimisticVersion, 1) &&
    uuidPattern.test(value.expectedInputLockRevisionGlobalId) &&
    validSampleInput(value.sample) &&
    textValue(value.reason, 1, 500)
  );
}

function validReviseSample(
  value: AppendTrialSampleBatchRevisionCommand,
): boolean {
  return (
    exact(value, [
      "expectedRoundOptimisticVersion",
      "expectedRevisionGlobalId",
      "expectedSampleVersion",
      "sample",
      "reason",
    ]) &&
    whole(value.expectedRoundOptimisticVersion, 1) &&
    uuidPattern.test(value.expectedRevisionGlobalId) &&
    whole(value.expectedSampleVersion, 1) &&
    validSampleInput(value.sample) &&
    textValue(value.reason, 1, 500)
  );
}

function validBindEvidence(value: BindTrialEvidenceCommand): boolean {
  const sampleId = value.sampleBatchRevisionGlobalId;
  const sampleVersion = value.expectedSampleVersion;
  return (
    exactWithOptional(
      value,
      [
        "expectedRoundOptimisticVersion",
        "role",
        "fileRevisionGlobalId",
        "expectedFileOptimisticVersion",
      ],
      ["sampleBatchRevisionGlobalId", "expectedSampleVersion"],
    ) &&
    whole(value.expectedRoundOptimisticVersion, 1) &&
    member(value.role, trialEvidenceRoles) &&
    uuidPattern.test(value.fileRevisionGlobalId) &&
    whole(value.expectedFileOptimisticVersion, 1) &&
    (sampleId === undefined || sampleId === null) ===
      (sampleVersion === undefined || sampleVersion === null) &&
    (sampleId === undefined ||
      sampleId === null ||
      uuidPattern.test(sampleId)) &&
    (sampleVersion === undefined ||
      sampleVersion === null ||
      whole(sampleVersion, 1))
  );
}

async function sha256Blob(value: Blob): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    await value.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
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

  async loadRoundExecution(
    projectId: string,
    roundId: string,
    signal: AbortSignal,
  ): Promise<TrialExecutionWorkspace> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    cancelled(signal);
    try {
      return await this.http.request<TrialExecutionWorkspace>(
        `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}/execution`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is TrialExecutionWorkspace =>
            isTrialExecutionWorkspace(value) &&
            value.projectGlobalId === expectedProjectId &&
            value.round.globalId === expectedRoundId,
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

  private async executionCommand(
    path: string,
    projectId: string,
    roundId: string,
    body: object | FormData,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult> {
    cancelled(context.signal);
    let replayed = false;
    try {
      const workspace = await this.http.request<TrialExecutionWorkspace>(
        path,
        {
          body: body instanceof FormData ? body : JSON.stringify(body),
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
          validate: (value): value is TrialExecutionWorkspace =>
            isTrialExecutionWorkspace(value) &&
            value.projectGlobalId === projectId &&
            value.round.globalId === roundId,
          validateResponse: (response) => {
            const header = replayHeader(response);
            if (header === null) return false;
            replayed = header;
            return true;
          },
        },
      );
      return { replayed, workspace };
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

  prepareRound(
    projectId: string,
    roundId: string,
    command: PrepareTrialRoundCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    if (!validContext(context) || !validPrepare(command))
      return Promise.reject(requestNotReady());
    return this.executionCommand(
      `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}:prepare`,
      expectedProjectId,
      expectedRoundId,
      command,
      context,
    );
  }

  startRound(
    projectId: string,
    roundId: string,
    command: StartTrialRoundCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    if (!validContext(context) || !validStart(command))
      return Promise.reject(requestNotReady());
    return this.executionCommand(
      `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}:start`,
      expectedProjectId,
      expectedRoundId,
      command,
      context,
    );
  }

  appendActualRevision(
    projectId: string,
    roundId: string,
    command: AppendTrialActualRevisionCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    if (!validContext(context) || !validActualRevision(command))
      return Promise.reject(requestNotReady());
    return this.executionCommand(
      `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}/actual-revisions`,
      expectedProjectId,
      expectedRoundId,
      command,
      context,
    );
  }

  createSampleBatch(
    projectId: string,
    roundId: string,
    command: CreateTrialSampleBatchCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    if (!validContext(context) || !validCreateSample(command))
      return Promise.reject(requestNotReady());
    return this.executionCommand(
      `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}/sample-batches`,
      expectedProjectId,
      expectedRoundId,
      command,
      context,
    );
  }

  appendSampleBatchRevision(
    projectId: string,
    roundId: string,
    sampleBatchId: string,
    command: AppendTrialSampleBatchRevisionCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    const expectedSampleBatchId = requireUuid(sampleBatchId);
    if (!validContext(context) || !validReviseSample(command))
      return Promise.reject(requestNotReady());
    return this.executionCommand(
      `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}/sample-batches/${expectedSampleBatchId}/revisions`,
      expectedProjectId,
      expectedRoundId,
      command,
      context,
    );
  }

  uploadEvidenceFile(
    projectId: string,
    roundId: string,
    command: UploadTrialEvidenceFileCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    if (
      !validContext(context) ||
      !exact(command, ["expectedRoundOptimisticVersion", "file"]) ||
      !whole(command.expectedRoundOptimisticVersion, 1) ||
      !(command.file instanceof File) ||
      !textValue(command.file.name, 1, 255) ||
      command.file.size < 1 ||
      command.file.size > 67_108_864
    )
      return Promise.reject(requestNotReady());
    const form = new FormData();
    form.append(
      "expectedRoundOptimisticVersion",
      String(command.expectedRoundOptimisticVersion),
    );
    form.append("file", command.file, command.file.name);
    return this.executionCommand(
      `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}/files`,
      expectedProjectId,
      expectedRoundId,
      form,
      context,
    );
  }

  bindEvidence(
    projectId: string,
    roundId: string,
    command: BindTrialEvidenceCommand,
    context: TrialCommandContext,
  ): Promise<TrialExecutionCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    if (!validContext(context) || !validBindEvidence(command))
      return Promise.reject(requestNotReady());
    return this.executionCommand(
      `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}/evidence`,
      expectedProjectId,
      expectedRoundId,
      command,
      context,
    );
  }

  async downloadEvidence(
    projectId: string,
    roundId: string,
    evidence: TrialEvidenceReference,
    context: Omit<TrialCommandContext, "idempotencyKey">,
  ): Promise<TrialEvidenceDownload> {
    const expectedProjectId = requireUuid(projectId);
    const expectedRoundId = requireUuid(roundId);
    if (
      !isEvidence(evidence) ||
      evidence.projectGlobalId !== expectedProjectId ||
      evidence.trialRoundGlobalId !== expectedRoundId ||
      !validContext({ ...context, idempotencyKey: "download-12345678" })
    )
      throw requestNotReady();
    cancelled(context.signal);
    let fileName = "";
    try {
      const blob = await this.http.request<Blob>(
        `/projects/${expectedProjectId}/trial-rounds/${expectedRoundId}/evidence/${evidence.globalId}:content`,
        {
          headers: { Accept: evidence.fileMimeType },
          method: "POST",
          signal: context.signal,
        },
        {
          csrfToken: context.csrfToken,
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          responseType: "blob",
          validate: (value): value is Blob =>
            value instanceof Blob &&
            value.size === evidence.fileSizeBytes &&
            value.type === evidence.fileMimeType,
          validateResponse: (response) => {
            const disposition =
              response.headers.get("Content-Disposition") ?? "";
            const match = /filename\*=UTF-8''([^;]+)$/u.exec(disposition);
            if (!match?.[1]) return false;
            try {
              fileName = decodeURIComponent(match[1]);
            } catch {
              return false;
            }
            return (
              fileName.length >= 1 &&
              fileName.length <= 255 &&
              !/[\r\n/\\]/u.test(fileName) &&
              response.headers.get("Content-Type")?.split(";", 1)[0]?.trim() ===
                evidence.fileMimeType &&
              response.headers.get("X-Content-Type-Options")?.toLowerCase() ===
                "nosniff" &&
              response.headers.get("Content-Security-Policy") ===
                "sandbox; default-src 'none'" &&
              response.headers.get("Referrer-Policy")?.toLowerCase() ===
                "no-referrer"
            );
          },
        },
      );
      if ((await sha256Blob(blob)) !== evidence.fileSha256)
        throw requestNotReady();
      return { blob, fileName };
    } catch (error) {
      cancelled(context.signal);
      throw error;
    }
  }
}
