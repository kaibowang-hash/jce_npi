import { NpiHttpClient, NpiTransportError } from "./http";

export type ToolingRequirementKind =
  | "new_tool"
  | "customer_owned_intake"
  | "copy_or_additional_set"
  | "modification"
  | "repair"
  | "capacity_need";

export interface ToolingProjectViewModel {
  globalId: string;
  businessCode: string;
  title: string;
}

export interface ToolingSourceViewModel {
  sourceSystem: "NPI_ONE";
  editableIn: "NPI_ONE";
  syncState: "local";
}

export interface EngineeringPartRevisionReferenceViewModel {
  globalId: string;
  partGlobalId: string;
  revisionNumber: number;
  revisionLabel: string;
  snapshotHash: string;
}

export interface EngineeringPartSummaryViewModel {
  globalId: string;
  title: string;
  version: number;
  currentRevision: EngineeringPartRevisionReferenceViewModel;
  source: ToolingSourceViewModel;
}

export interface ToolingRequirementSummaryViewModel {
  globalId: string;
  projectGlobalId: string;
  kind: ToolingRequirementKind;
  title: string;
  reason: string;
  targetPartRevisionGlobalId: string | null;
  targetDate: string | null;
  snapshotHash: string;
}

export interface ToolingMasterSummaryViewModel {
  globalId: string;
  title: string;
  originatingProjectGlobalId: string;
  snapshotHash: string;
  source: ToolingSourceViewModel;
}

export interface ToolingExternalReferenceViewModel {
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
}

export interface ToolingApplicabilitySummaryViewModel {
  globalId: string;
  relationshipGlobalId: string;
  relationshipKeyHash: string;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  part: EngineeringPartRevisionReferenceViewModel;
  product: ToolingExternalReferenceViewModel | null;
  model: ToolingExternalReferenceViewModel | null;
  version: number;
  predecessorGlobalId: string | null;
  effectiveFrom: string;
  effectiveTo: string | null;
  snapshotHash: string;
}

export interface ToolingPermissionsViewModel {
  view: boolean;
  createPart: boolean;
  createRequirement: boolean;
  createMaster: boolean;
  createApplicability: boolean;
  transitionLifecycle: false;
}

export type ToolingDownstreamReason =
  | "lifecycle_policy_unavailable"
  | "physical_set_not_delivered"
  | "tooling_revision_not_delivered"
  | "trial_not_delivered"
  | "erp_projection_unavailable";

export interface ToolingDownstreamCapabilityViewModel {
  state: "unavailable";
  reasonCode: ToolingDownstreamReason;
}

export interface ToolingCockpitViewModel {
  project: ToolingProjectViewModel;
  permissions: ToolingPermissionsViewModel;
  masters: readonly ToolingMasterSummaryViewModel[];
  requirements: readonly ToolingRequirementSummaryViewModel[];
  parts: readonly EngineeringPartSummaryViewModel[];
  applicability: readonly ToolingApplicabilitySummaryViewModel[];
  downstream: Readonly<{
    lifecycle: ToolingDownstreamCapabilityViewModel;
    revision: ToolingDownstreamCapabilityViewModel;
    physicalSet: ToolingDownstreamCapabilityViewModel;
    trial: ToolingDownstreamCapabilityViewModel;
    erp: ToolingDownstreamCapabilityViewModel;
  }>;
}

export interface ToolingCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface CreateEngineeringPartCommand {
  title: string;
  revisionLabel: string;
  reason: string;
}

export interface CreateEngineeringPartRevisionCommand {
  expectedVersion: number;
  revisionLabel: string;
  title: string;
  reason: string;
}

export interface CreateToolingRequirementCommand {
  kind: ToolingRequirementKind;
  title: string;
  reason: string;
  targetPartRevisionGlobalId?: string | undefined;
  targetDate?: string | undefined;
}

export interface CreateToolingMasterCommand {
  title: string;
}

export interface CreateToolingApplicabilityCommand {
  toolingMasterGlobalId: string;
  partRevisionGlobalId: string;
  product?: ToolingExternalReferenceViewModel | undefined;
  model?: ToolingExternalReferenceViewModel | undefined;
  relationshipGlobalId?: string | undefined;
  expectedVersion?: number | undefined;
  effectiveFrom: string;
  effectiveTo?: string | undefined;
  reason: string;
}

export type ToolingSetRequirementKind =
  | "customer_owned_intake"
  | "copy_or_additional_set";
export type ToolingIntakeInspectionCategory =
  | "appearance"
  | "water_circuit"
  | "hot_runner"
  | "electrical"
  | "safety";
export type ToolingIntakeEvidenceRole =
  | "arrival_photo"
  | "transport_document"
  | "accessory_document"
  | "inspection_evidence"
  | "customer_confirmation";

export interface ToolingSetPermissionsViewModel {
  view: boolean;
  createSet: boolean;
  createIntake: boolean;
  attachEvidence: boolean;
  transitionLifecycle: false;
}

export interface ToolingSetUnavailableFieldViewModel {
  state: "unavailable";
  reasonCode:
    | "lifecycle_policy_unavailable"
    | "tooling_revision_not_delivered"
    | "formal_supplier_unavailable"
    | "erp_projection_unavailable";
}

export interface ToolingSetSummaryViewModel {
  globalId: string;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  toolingRequirementGlobalId: string;
  requirementKind: ToolingSetRequirementKind;
  physicalSerial: string;
  customer: ToolingExternalReferenceViewModel | null;
  custodyResponsibility: string;
  repairAuthorizationReference: string;
  returnConditions: string;
  sourceRevision: ToolingSetUnavailableFieldViewModel;
  supplier: ToolingSetUnavailableFieldViewModel;
  lifecycle: ToolingSetUnavailableFieldViewModel;
  erpLocationAndAsset: ToolingSetUnavailableFieldViewModel;
  snapshotHash: string;
}

export interface ToolingIntakeAccessoryViewModel {
  globalId: string;
  description: string;
  declaredQuantity: number;
  receivedQuantity: number;
  unit: string;
}

export interface ToolingIntakeInspectionViewModel {
  globalId: string;
  category: ToolingIntakeInspectionCategory;
  observation: string;
  differenceObserved: boolean;
}

export interface ToolingIntakeDifferenceViewModel {
  globalId: string;
  sourceKind: "accessory" | "inspection";
  sourceGlobalId: string;
  description: string;
  customerConfirmationRequired: boolean;
}

export interface ToolingIntakeSummaryViewModel {
  globalId: string;
  toolingSetGlobalId: string;
  version: number;
  predecessorGlobalId: string | null;
  transportProvider: string;
  transportReference: string;
  arrivedAt: string;
  custodyHandover: string;
  accessories: readonly ToolingIntakeAccessoryViewModel[];
  inspections: readonly ToolingIntakeInspectionViewModel[];
  differences: readonly ToolingIntakeDifferenceViewModel[];
  snapshotHash: string;
}

export interface ToolingIntakeEvidenceReferenceViewModel {
  globalId: string;
  toolingIntakeGlobalId: string;
  intakeSnapshotHash: string;
  evidenceRole: ToolingIntakeEvidenceRole;
  differenceGlobalIds: readonly string[];
  fileRevisionGlobalId: string;
  fileOptimisticVersion: number;
  fileContentHash: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  sha256: string;
  snapshotHash: string;
}

export interface ToolingSetCollectionViewModel {
  toolingMasterGlobalId: string;
  permissions: ToolingSetPermissionsViewModel;
  items: readonly ToolingSetSummaryViewModel[];
}

export interface ToolingSetDetailViewModel {
  toolingSet: ToolingSetSummaryViewModel;
  permissions: ToolingSetPermissionsViewModel;
  intakes: readonly ToolingIntakeSummaryViewModel[];
  evidence: readonly ToolingIntakeEvidenceReferenceViewModel[];
}

export interface CreateToolingSetCommand {
  toolingRequirementGlobalId: string;
  physicalSerial: string;
  customer?: ToolingExternalReferenceViewModel | undefined;
  custodyResponsibility: string;
  repairAuthorizationReference: string;
  returnConditions: string;
}

export interface CreateToolingIntakeCommand {
  expectedVersion?: number | undefined;
  transportProvider: string;
  transportReference: string;
  arrivedAt: string;
  custodyHandover: string;
  accessories: readonly ToolingIntakeAccessoryViewModel[];
  inspections: readonly ToolingIntakeInspectionViewModel[];
  differences: readonly ToolingIntakeDifferenceViewModel[];
}

export interface CreateToolingIntakeEvidenceCommand {
  evidenceRole: ToolingIntakeEvidenceRole;
  differenceGlobalIds: readonly string[];
  fileRevisionGlobalId: string;
}

export interface ToolingDataSource {
  loadCockpit(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel>;
  loadMaster(
    projectId: string,
    masterId: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel>;
  createPart(
    projectId: string,
    command: CreateEngineeringPartCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  createPartRevision(
    projectId: string,
    partId: string,
    command: CreateEngineeringPartRevisionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  createRequirement(
    projectId: string,
    command: CreateToolingRequirementCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  createMaster(
    projectId: string,
    command: CreateToolingMasterCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  createApplicability(
    projectId: string,
    command: CreateToolingApplicabilityCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  loadSets(
    projectId: string,
    masterId: string,
    signal: AbortSignal,
  ): Promise<ToolingSetCollectionViewModel>;
  loadSet(
    projectId: string,
    masterId: string,
    setId: string,
    signal: AbortSignal,
  ): Promise<ToolingSetDetailViewModel>;
  createSet(
    projectId: string,
    masterId: string,
    command: CreateToolingSetCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingSetCollectionViewModel>;
  createIntake(
    projectId: string,
    masterId: string,
    setId: string,
    command: CreateToolingIntakeCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingSetDetailViewModel>;
  attachIntakeEvidence(
    projectId: string,
    masterId: string,
    setId: string,
    intakeId: string,
    command: CreateToolingIntakeEvidenceCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingSetDetailViewModel>;
}

export class ToolingRequestCancelledError extends Error {
  constructor() {
    super("The Tooling request was cancelled.");
    this.name = "ToolingRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const referencePattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$/u;
const requirementKinds = new Set<ToolingRequirementKind>([
  "new_tool",
  "customer_owned_intake",
  "copy_or_additional_set",
  "modification",
  "repair",
  "capacity_need",
]);
const downstreamReasons = new Set<ToolingDownstreamReason>([
  "lifecycle_policy_unavailable",
  "physical_set_not_delivered",
  "tooling_revision_not_delivered",
  "trial_not_delivered",
  "erp_projection_unavailable",
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

function isString(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= maximum
  );
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isHash(value: unknown): value is string {
  return typeof value === "string" && hashPattern.test(value);
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function isDate(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value)
  );
}

function isNullableUuid(value: unknown): value is string | null {
  return value === null || isUuid(value);
}

function isNullableDate(value: unknown): value is string | null {
  return value === null || isDate(value);
}

function isProject(value: unknown): value is ToolingProjectViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "businessCode", "title"]) &&
    isUuid(value.globalId) &&
    isString(value.businessCode, 64) &&
    isString(value.title, 140)
  );
}

function isSource(value: unknown): value is ToolingSourceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["sourceSystem", "editableIn", "syncState"]) &&
    value.sourceSystem === "NPI_ONE" &&
    value.editableIn === "NPI_ONE" &&
    value.syncState === "local"
  );
}

function isRevision(
  value: unknown,
): value is EngineeringPartRevisionReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "partGlobalId",
      "revisionNumber",
      "revisionLabel",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.partGlobalId) &&
    isPositiveInteger(value.revisionNumber) &&
    isString(value.revisionLabel, 40) &&
    isHash(value.snapshotHash)
  );
}

function isPart(value: unknown): value is EngineeringPartSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "title",
      "version",
      "currentRevision",
      "source",
    ]) &&
    isUuid(value.globalId) &&
    isString(value.title, 140) &&
    isPositiveInteger(value.version) &&
    isRevision(value.currentRevision) &&
    value.currentRevision.partGlobalId === value.globalId &&
    isSource(value.source)
  );
}

function isRequirement(
  value: unknown,
): value is ToolingRequirementSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "projectGlobalId",
      "kind",
      "title",
      "reason",
      "targetPartRevisionGlobalId",
      "targetDate",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.projectGlobalId) &&
    typeof value.kind === "string" &&
    requirementKinds.has(value.kind as ToolingRequirementKind) &&
    isString(value.title, 140) &&
    isString(value.reason, 500) &&
    isNullableUuid(value.targetPartRevisionGlobalId) &&
    isNullableDate(value.targetDate) &&
    isHash(value.snapshotHash)
  );
}

function isMaster(value: unknown): value is ToolingMasterSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "title",
      "originatingProjectGlobalId",
      "snapshotHash",
      "source",
    ]) &&
    isUuid(value.globalId) &&
    isString(value.title, 140) &&
    isUuid(value.originatingProjectGlobalId) &&
    isHash(value.snapshotHash) &&
    isSource(value.source)
  );
}

function isExternalReference(
  value: unknown,
): value is ToolingExternalReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["sourceSystem", "sourceObjectId"]) &&
    (value.sourceSystem === "NPI_ONE" || value.sourceSystem === "ERPNEXT") &&
    typeof value.sourceObjectId === "string" &&
    referencePattern.test(value.sourceObjectId)
  );
}

function isNullableReference(
  value: unknown,
): value is ToolingExternalReferenceViewModel | null {
  return value === null || isExternalReference(value);
}

function isApplicability(
  value: unknown,
): value is ToolingApplicabilitySummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "relationshipGlobalId",
      "relationshipKeyHash",
      "projectGlobalId",
      "toolingMasterGlobalId",
      "part",
      "product",
      "model",
      "version",
      "predecessorGlobalId",
      "effectiveFrom",
      "effectiveTo",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.relationshipGlobalId) &&
    isHash(value.relationshipKeyHash) &&
    isUuid(value.projectGlobalId) &&
    isUuid(value.toolingMasterGlobalId) &&
    isRevision(value.part) &&
    isNullableReference(value.product) &&
    isNullableReference(value.model) &&
    isPositiveInteger(value.version) &&
    isNullableUuid(value.predecessorGlobalId) &&
    isDate(value.effectiveFrom) &&
    isNullableDate(value.effectiveTo) &&
    (value.effectiveTo === null || value.effectiveFrom < value.effectiveTo) &&
    isHash(value.snapshotHash)
  );
}

function isPermissions(value: unknown): value is ToolingPermissionsViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "view",
      "createPart",
      "createRequirement",
      "createMaster",
      "createApplicability",
      "transitionLifecycle",
    ]) &&
    value.view === true &&
    typeof value.createPart === "boolean" &&
    typeof value.createRequirement === "boolean" &&
    typeof value.createMaster === "boolean" &&
    typeof value.createApplicability === "boolean" &&
    value.transitionLifecycle === false
  );
}

function isDownstreamCapability(
  value: unknown,
): value is ToolingDownstreamCapabilityViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "reasonCode"]) &&
    value.state === "unavailable" &&
    typeof value.reasonCode === "string" &&
    downstreamReasons.has(value.reasonCode as ToolingDownstreamReason)
  );
}

function isDownstream(
  value: unknown,
): value is ToolingCockpitViewModel["downstream"] {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "lifecycle",
      "revision",
      "physicalSet",
      "trial",
      "erp",
    ]) &&
    isDownstreamCapability(value.lifecycle) &&
    value.lifecycle.reasonCode === "lifecycle_policy_unavailable" &&
    isDownstreamCapability(value.revision) &&
    value.revision.reasonCode === "tooling_revision_not_delivered" &&
    isDownstreamCapability(value.physicalSet) &&
    value.physicalSet.reasonCode === "physical_set_not_delivered" &&
    isDownstreamCapability(value.trial) &&
    value.trial.reasonCode === "trial_not_delivered" &&
    isDownstreamCapability(value.erp) &&
    value.erp.reasonCode === "erp_projection_unavailable"
  );
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

export function isToolingCockpitResponse(
  value: unknown,
): value is ToolingCockpitViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "project",
      "permissions",
      "masters",
      "requirements",
      "parts",
      "applicability",
      "downstream",
    ]) ||
    !isProject(value.project) ||
    !isPermissions(value.permissions) ||
    !Array.isArray(value.masters) ||
    value.masters.length > 200 ||
    !value.masters.every(isMaster) ||
    !Array.isArray(value.requirements) ||
    value.requirements.length > 200 ||
    !value.requirements.every(isRequirement) ||
    !Array.isArray(value.parts) ||
    value.parts.length > 500 ||
    !value.parts.every(isPart) ||
    !Array.isArray(value.applicability) ||
    value.applicability.length > 1_000 ||
    !value.applicability.every(isApplicability) ||
    !isDownstream(value.downstream)
  ) {
    return false;
  }
  const project = value.project;
  const masters = value.masters as readonly ToolingMasterSummaryViewModel[];
  const requirements =
    value.requirements as readonly ToolingRequirementSummaryViewModel[];
  const parts = value.parts as readonly EngineeringPartSummaryViewModel[];
  const applicability =
    value.applicability as readonly ToolingApplicabilitySummaryViewModel[];
  const masterIds = new Set(masters.map((item) => item.globalId));
  const partIds = new Set(parts.map((item) => item.globalId));
  return (
    unique(masters.map((item) => item.globalId)) &&
    unique(requirements.map((item) => item.globalId)) &&
    unique(parts.map((item) => item.globalId)) &&
    unique(applicability.map((item) => item.globalId)) &&
    requirements.every((item) => item.projectGlobalId === project.globalId) &&
    applicability.every(
      (item) =>
        item.projectGlobalId === project.globalId &&
        masterIds.has(item.toolingMasterGlobalId) &&
        partIds.has(item.part.partGlobalId),
    )
  );
}

const toolingSetRequirementKinds = new Set<ToolingSetRequirementKind>([
  "customer_owned_intake",
  "copy_or_additional_set",
]);
const inspectionCategories = new Set<ToolingIntakeInspectionCategory>([
  "appearance",
  "water_circuit",
  "hot_runner",
  "electrical",
  "safety",
]);
const evidenceRoles = new Set<ToolingIntakeEvidenceRole>([
  "arrival_photo",
  "transport_document",
  "accessory_document",
  "inspection_evidence",
  "customer_confirmation",
]);
const unavailableReasons = new Set<
  ToolingSetUnavailableFieldViewModel["reasonCode"]
>([
  "lifecycle_policy_unavailable",
  "tooling_revision_not_delivered",
  "formal_supplier_unavailable",
  "erp_projection_unavailable",
]);

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isDateTime(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 40 &&
    !Number.isNaN(Date.parse(value)) &&
    /(?:Z|[+-]\d{2}:\d{2})$/u.test(value)
  );
}

function isUnavailableField(
  value: unknown,
  reasonCode: ToolingSetUnavailableFieldViewModel["reasonCode"],
): value is ToolingSetUnavailableFieldViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "reasonCode"]) &&
    value.state === "unavailable" &&
    value.reasonCode === reasonCode &&
    unavailableReasons.has(reasonCode)
  );
}

function isToolingSetPermissions(
  value: unknown,
): value is ToolingSetPermissionsViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "view",
      "createSet",
      "createIntake",
      "attachEvidence",
      "transitionLifecycle",
    ]) &&
    typeof value.view === "boolean" &&
    typeof value.createSet === "boolean" &&
    typeof value.createIntake === "boolean" &&
    typeof value.attachEvidence === "boolean" &&
    value.transitionLifecycle === false
  );
}

function isToolingSetSummary(
  value: unknown,
): value is ToolingSetSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "projectGlobalId",
      "toolingMasterGlobalId",
      "toolingRequirementGlobalId",
      "requirementKind",
      "physicalSerial",
      "customer",
      "custodyResponsibility",
      "repairAuthorizationReference",
      "returnConditions",
      "sourceRevision",
      "supplier",
      "lifecycle",
      "erpLocationAndAsset",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.projectGlobalId) &&
    isUuid(value.toolingMasterGlobalId) &&
    isUuid(value.toolingRequirementGlobalId) &&
    typeof value.requirementKind === "string" &&
    toolingSetRequirementKinds.has(
      value.requirementKind as ToolingSetRequirementKind,
    ) &&
    isString(value.physicalSerial, 80) &&
    isNullableReference(value.customer) &&
    isString(value.custodyResponsibility, 500) &&
    isString(value.repairAuthorizationReference, 500) &&
    isString(value.returnConditions, 500) &&
    isUnavailableField(
      value.sourceRevision,
      "tooling_revision_not_delivered",
    ) &&
    isUnavailableField(value.supplier, "formal_supplier_unavailable") &&
    isUnavailableField(value.lifecycle, "lifecycle_policy_unavailable") &&
    isUnavailableField(
      value.erpLocationAndAsset,
      "erp_projection_unavailable",
    ) &&
    isHash(value.snapshotHash)
  );
}

function isAccessory(value: unknown): value is ToolingIntakeAccessoryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "description",
      "declaredQuantity",
      "receivedQuantity",
      "unit",
    ]) &&
    isUuid(value.globalId) &&
    isString(value.description, 200) &&
    isNonnegativeInteger(value.declaredQuantity) &&
    isNonnegativeInteger(value.receivedQuantity) &&
    isString(value.unit, 24)
  );
}

function isInspection(
  value: unknown,
): value is ToolingIntakeInspectionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "category",
      "observation",
      "differenceObserved",
    ]) &&
    isUuid(value.globalId) &&
    typeof value.category === "string" &&
    inspectionCategories.has(
      value.category as ToolingIntakeInspectionCategory,
    ) &&
    isString(value.observation, 500) &&
    typeof value.differenceObserved === "boolean"
  );
}

function isDifference(
  value: unknown,
): value is ToolingIntakeDifferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "sourceKind",
      "sourceGlobalId",
      "description",
      "customerConfirmationRequired",
    ]) &&
    isUuid(value.globalId) &&
    (value.sourceKind === "accessory" || value.sourceKind === "inspection") &&
    isUuid(value.sourceGlobalId) &&
    isString(value.description, 500) &&
    typeof value.customerConfirmationRequired === "boolean"
  );
}

function isCoherentIntakeParts(
  accessories: readonly ToolingIntakeAccessoryViewModel[],
  inspections: readonly ToolingIntakeInspectionViewModel[],
  differences: readonly ToolingIntakeDifferenceViewModel[],
): boolean {
  const accessoryIds = new Set(accessories.map((item) => item.globalId));
  const inspectionIds = new Set(inspections.map((item) => item.globalId));
  return (
    unique(accessories.map((item) => item.globalId)) &&
    unique(inspections.map((item) => item.globalId)) &&
    unique(inspections.map((item) => item.category)) &&
    inspectionCategories.size === inspections.length &&
    unique(differences.map((item) => item.globalId)) &&
    differences.every((item) =>
      item.sourceKind === "accessory"
        ? accessoryIds.has(item.sourceGlobalId)
        : inspectionIds.has(item.sourceGlobalId),
    )
  );
}

function isIntake(value: unknown): value is ToolingIntakeSummaryViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "toolingSetGlobalId",
      "version",
      "predecessorGlobalId",
      "transportProvider",
      "transportReference",
      "arrivedAt",
      "custodyHandover",
      "accessories",
      "inspections",
      "differences",
      "snapshotHash",
    ]) ||
    !isUuid(value.globalId) ||
    !isUuid(value.toolingSetGlobalId) ||
    !isPositiveInteger(value.version) ||
    !isNullableUuid(value.predecessorGlobalId) ||
    !isString(value.transportProvider, 140) ||
    !isString(value.transportReference, 140) ||
    !isDateTime(value.arrivedAt) ||
    !isString(value.custodyHandover, 500) ||
    !Array.isArray(value.accessories) ||
    value.accessories.length > 100 ||
    !value.accessories.every(isAccessory) ||
    !Array.isArray(value.inspections) ||
    value.inspections.length !== 5 ||
    !value.inspections.every(isInspection) ||
    !Array.isArray(value.differences) ||
    value.differences.length > 100 ||
    !value.differences.every(isDifference) ||
    !isHash(value.snapshotHash)
  ) {
    return false;
  }
  return isCoherentIntakeParts(
    value.accessories,
    value.inspections,
    value.differences,
  );
}

function isEvidence(
  value: unknown,
): value is ToolingIntakeEvidenceReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "toolingIntakeGlobalId",
      "intakeSnapshotHash",
      "evidenceRole",
      "differenceGlobalIds",
      "fileRevisionGlobalId",
      "fileOptimisticVersion",
      "fileContentHash",
      "fileName",
      "mimeType",
      "sizeBytes",
      "sha256",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.toolingIntakeGlobalId) &&
    isHash(value.intakeSnapshotHash) &&
    typeof value.evidenceRole === "string" &&
    evidenceRoles.has(value.evidenceRole as ToolingIntakeEvidenceRole) &&
    Array.isArray(value.differenceGlobalIds) &&
    value.differenceGlobalIds.length <= 100 &&
    value.differenceGlobalIds.every(isUuid) &&
    unique(value.differenceGlobalIds) &&
    isUuid(value.fileRevisionGlobalId) &&
    isPositiveInteger(value.fileOptimisticVersion) &&
    typeof value.fileContentHash === "string" &&
    /^[a-f0-9]{32,128}$/u.test(value.fileContentHash) &&
    isString(value.fileName, 255) &&
    isString(value.mimeType, 255) &&
    isPositiveInteger(value.sizeBytes) &&
    isHash(value.sha256) &&
    isHash(value.snapshotHash)
  );
}

export function isToolingSetCollectionResponse(
  value: unknown,
): value is ToolingSetCollectionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["toolingMasterGlobalId", "permissions", "items"]) &&
    isUuid(value.toolingMasterGlobalId) &&
    isToolingSetPermissions(value.permissions) &&
    Array.isArray(value.items) &&
    value.items.length <= 200 &&
    value.items.every(isToolingSetSummary) &&
    unique(
      (value.items as readonly ToolingSetSummaryViewModel[]).map(
        (item) => item.globalId,
      ),
    ) &&
    (value.items as readonly ToolingSetSummaryViewModel[]).every(
      (item) => item.toolingMasterGlobalId === value.toolingMasterGlobalId,
    )
  );
}

export function isToolingSetDetailResponse(
  value: unknown,
): value is ToolingSetDetailViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "toolingSet",
      "permissions",
      "intakes",
      "evidence",
    ]) ||
    !isToolingSetSummary(value.toolingSet) ||
    !isToolingSetPermissions(value.permissions) ||
    !Array.isArray(value.intakes) ||
    value.intakes.length > 100 ||
    !value.intakes.every(isIntake) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 500 ||
    !value.evidence.every(isEvidence)
  ) {
    return false;
  }
  const toolingSet = value.toolingSet;
  const intakes = value.intakes as readonly ToolingIntakeSummaryViewModel[];
  const evidence =
    value.evidence as readonly ToolingIntakeEvidenceReferenceViewModel[];
  const intakeById = new Map(intakes.map((item) => [item.globalId, item]));
  return (
    unique(intakes.map((item) => item.globalId)) &&
    unique(evidence.map((item) => item.globalId)) &&
    intakes.every((item) => item.toolingSetGlobalId === toolingSet.globalId) &&
    evidence.every((item) => {
      const intake = intakeById.get(item.toolingIntakeGlobalId);
      return (
        item.intakeSnapshotHash === intake?.snapshotHash &&
        item.differenceGlobalIds.every((differenceId) =>
          intake.differences.some(
            (difference) => difference.globalId === differenceId,
          ),
        )
      );
    })
  );
}

function isCreateSetCommand(value: CreateToolingSetCommand): boolean {
  return (
    isUuid(value.toolingRequirementGlobalId) &&
    isString(value.physicalSerial, 80) &&
    (value.customer === undefined || isExternalReference(value.customer)) &&
    isString(value.custodyResponsibility, 500) &&
    isString(value.repairAuthorizationReference, 500) &&
    isString(value.returnConditions, 500)
  );
}

function isCreateIntakeCommand(value: CreateToolingIntakeCommand): boolean {
  return (
    (value.expectedVersion === undefined ||
      isPositiveInteger(value.expectedVersion)) &&
    isString(value.transportProvider, 140) &&
    isString(value.transportReference, 140) &&
    isDateTime(value.arrivedAt) &&
    isString(value.custodyHandover, 500) &&
    value.accessories.length <= 100 &&
    value.accessories.every(isAccessory) &&
    value.inspections.length === 5 &&
    value.inspections.every(isInspection) &&
    value.differences.length <= 100 &&
    value.differences.every(isDifference) &&
    isCoherentIntakeParts(
      value.accessories,
      value.inspections,
      value.differences,
    )
  );
}

function isCreateEvidenceCommand(
  value: CreateToolingIntakeEvidenceCommand,
): boolean {
  return (
    evidenceRoles.has(value.evidenceRole) &&
    value.differenceGlobalIds.length <= 100 &&
    value.differenceGlobalIds.every(isUuid) &&
    unique(value.differenceGlobalIds) &&
    isUuid(value.fileRevisionGlobalId)
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

function throwIfCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ToolingRequestCancelledError();
}

function isCommandContext(value: ToolingCommandContext): boolean {
  return (
    typeof value.csrfToken === "string" &&
    value.csrfToken.length >= 32 &&
    value.csrfToken.length <= 128 &&
    !/[\r\n]/u.test(value.csrfToken) &&
    idempotencyPattern.test(value.idempotencyKey) &&
    value.signal instanceof AbortSignal
  );
}

export class LiveToolingDataSource implements ToolingDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadCockpit(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel> {
    return await this.query(
      `/projects/${requireUuid(projectId)}/tooling`,
      signal,
    );
  }

  async loadMaster(
    projectId: string,
    masterId: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel> {
    return await this.query(
      `/projects/${requireUuid(projectId)}/tooling/${requireUuid(masterId)}`,
      signal,
    );
  }

  async createPart(
    projectId: string,
    command: CreateEngineeringPartCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/parts`,
      command,
      context,
    );
  }

  async createPartRevision(
    projectId: string,
    partId: string,
    command: CreateEngineeringPartRevisionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/parts/${requireUuid(partId)}/revisions`,
      command,
      context,
    );
  }

  async createRequirement(
    projectId: string,
    command: CreateToolingRequirementCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/tooling-requirements`,
      command,
      context,
    );
  }

  async createMaster(
    projectId: string,
    command: CreateToolingMasterCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/tooling-masters`,
      command,
      context,
    );
  }

  async createApplicability(
    projectId: string,
    command: CreateToolingApplicabilityCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/tooling-applicabilities`,
      command,
      context,
    );
  }

  async loadSets(
    projectId: string,
    masterId: string,
    signal: AbortSignal,
  ): Promise<ToolingSetCollectionViewModel> {
    const expectedProjectId = requireUuid(projectId);
    const expectedMasterId = requireUuid(masterId);
    return await this.queryValidated(
      `/projects/${expectedProjectId}/tooling/${expectedMasterId}/sets`,
      signal,
      (value): value is ToolingSetCollectionViewModel =>
        isToolingSetCollectionResponse(value) &&
        value.toolingMasterGlobalId === expectedMasterId &&
        value.items.every((item) => item.projectGlobalId === expectedProjectId),
    );
  }

  async loadSet(
    projectId: string,
    masterId: string,
    setId: string,
    signal: AbortSignal,
  ): Promise<ToolingSetDetailViewModel> {
    const expectedProjectId = requireUuid(projectId);
    const expectedMasterId = requireUuid(masterId);
    const expectedSetId = requireUuid(setId);
    return await this.queryValidated(
      `/projects/${expectedProjectId}/tooling/${expectedMasterId}/sets/${expectedSetId}`,
      signal,
      (value): value is ToolingSetDetailViewModel =>
        isToolingSetDetailResponse(value) &&
        value.toolingSet.globalId === expectedSetId &&
        value.toolingSet.projectGlobalId === expectedProjectId &&
        value.toolingSet.toolingMasterGlobalId === expectedMasterId,
    );
  }

  async createSet(
    projectId: string,
    masterId: string,
    command: CreateToolingSetCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingSetCollectionViewModel> {
    if (!isCreateSetCommand(command)) throw requestNotReady();
    const expectedProjectId = requireUuid(projectId);
    const expectedMasterId = requireUuid(masterId);
    return await this.commandValidated(
      `/projects/${expectedProjectId}/tooling/${expectedMasterId}/sets`,
      command,
      context,
      (value): value is ToolingSetCollectionViewModel =>
        isToolingSetCollectionResponse(value) &&
        value.toolingMasterGlobalId === expectedMasterId &&
        value.items.every((item) => item.projectGlobalId === expectedProjectId),
    );
  }

  async createIntake(
    projectId: string,
    masterId: string,
    setId: string,
    command: CreateToolingIntakeCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingSetDetailViewModel> {
    if (!isCreateIntakeCommand(command)) throw requestNotReady();
    const expectedProjectId = requireUuid(projectId);
    const expectedMasterId = requireUuid(masterId);
    const expectedSetId = requireUuid(setId);
    return await this.commandValidated(
      `/projects/${expectedProjectId}/tooling/${expectedMasterId}/sets/${expectedSetId}/intakes`,
      command,
      context,
      (value): value is ToolingSetDetailViewModel =>
        isToolingSetDetailResponse(value) &&
        value.toolingSet.globalId === expectedSetId &&
        value.toolingSet.projectGlobalId === expectedProjectId &&
        value.toolingSet.toolingMasterGlobalId === expectedMasterId,
    );
  }

  async attachIntakeEvidence(
    projectId: string,
    masterId: string,
    setId: string,
    intakeId: string,
    command: CreateToolingIntakeEvidenceCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingSetDetailViewModel> {
    if (!isCreateEvidenceCommand(command)) throw requestNotReady();
    const expectedProjectId = requireUuid(projectId);
    const expectedMasterId = requireUuid(masterId);
    const expectedSetId = requireUuid(setId);
    const expectedIntakeId = requireUuid(intakeId);
    return await this.commandValidated(
      `/projects/${expectedProjectId}/tooling/${expectedMasterId}/sets/${expectedSetId}/intakes/${expectedIntakeId}/evidence`,
      command,
      context,
      (value): value is ToolingSetDetailViewModel =>
        isToolingSetDetailResponse(value) &&
        value.toolingSet.globalId === expectedSetId &&
        value.toolingSet.projectGlobalId === expectedProjectId &&
        value.toolingSet.toolingMasterGlobalId === expectedMasterId &&
        value.intakes.some((item) => item.globalId === expectedIntakeId),
    );
  }

  private async query(
    path: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel> {
    throwIfCancelled(signal);
    try {
      return await this.http.request<ToolingCockpitViewModel>(
        path,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: isToolingCockpitResponse,
        },
      );
    } catch (error) {
      throwIfCancelled(signal);
      throw error;
    }
  }

  private async command(
    path: string,
    body: object,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    if (!isCommandContext(context)) throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<ToolingCockpitViewModel>(
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
          validate: isToolingCockpitResponse,
        },
      );
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }

  private async queryValidated<T>(
    path: string,
    signal: AbortSignal,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    throwIfCancelled(signal);
    try {
      return await this.http.request<T>(
        path,
        { signal },
        {
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

  private async commandValidated<T>(
    path: string,
    body: object,
    context: ToolingCommandContext,
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
