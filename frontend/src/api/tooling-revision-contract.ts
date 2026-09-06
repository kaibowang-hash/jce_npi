export interface ToolingMeasurementViewModel {
  value: string;
  unit: string;
  source: string;
}

export interface ToolingSpecificationViewModel {
  toolingType: string;
  moldBaseMaterial: string;
  coreMaterial: string;
  hardness: ToolingMeasurementViewModel;
  surfaceTreatment: string;
  cavityCount: number;
  hotRunner: string;
  length: ToolingMeasurementViewModel;
  width: ToolingMeasurementViewModel;
  height: ToolingMeasurementViewModel;
  weight: ToolingMeasurementViewModel;
  clampTonnage: ToolingMeasurementViewModel;
  tieBarSpacingX: ToolingMeasurementViewModel;
  tieBarSpacingY: ToolingMeasurementViewModel;
  injectionCapacity: ToolingMeasurementViewModel;
  machineType: string;
  targetCycle: ToolingMeasurementViewModel;
  targetLife: ToolingMeasurementViewModel;
  warranty: string;
  customerStandard: string;
  interfaceRequirement: string;
  spareParts: readonly string[];
  deliveryDocuments: readonly string[];
}

export interface ToolingCavityMappingViewModel {
  globalId: string;
  cavityIdentifier: string;
  toolingApplicabilityGlobalId: string;
  partRevisionGlobalId: string;
  structuralState: "enabled" | "sealed";
}

export interface CreateToolingCavityMappingCommand {
  cavityIdentifier: string;
  toolingApplicabilityGlobalId: string;
  partRevisionGlobalId: string;
  structuralState: "enabled" | "sealed";
}

export interface ToolingInsertApplicabilityViewModel {
  globalId: string;
  insertCode: string;
  insertVersion: number;
  toolingApplicabilityGlobalId: string;
  partRevisionGlobalId: string;
  modelSourceSystem: "npi_one" | "plm" | null;
  modelSourceObjectId: string | null;
  changeoverDuration: ToolingMeasurementViewModel;
  validationState: "not_validated" | "validated";
  validatedByUserId: string | null;
  validatedAt: string | null;
  validationReason: string | null;
}

export interface ToolingRevisionExternalReferenceCommand {
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
}

export interface CreateToolingInsertApplicabilityCommand {
  insertCode: string;
  insertVersion: number;
  toolingApplicabilityGlobalId: string;
  partRevisionGlobalId: string;
  model?: ToolingRevisionExternalReferenceCommand | undefined;
  changeoverDuration: ToolingMeasurementViewModel;
  validationState: "not_validated" | "validated";
  validationReason?: string | undefined;
}

export type ToolingExternalIdentityKind =
  | "customer"
  | "sn"
  | "kw"
  | "th"
  | "supplier_reference";

export interface ToolingExternalIdentityViewModel {
  globalId: string;
  identityType: ToolingExternalIdentityKind;
  value: string;
  rawValue: string;
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
  effectiveFrom: string;
  effectiveTo: string | null;
}

export interface CreateToolingExternalIdentityCommand {
  identityType: ToolingExternalIdentityKind;
  value: string;
  rawValue: string;
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
  effectiveFrom: string;
  effectiveTo?: string | undefined;
}

export interface ToolingDocumentRevisionReferenceViewModel {
  globalId: string;
  snapshotHash: string;
}

export interface ToolingRevisionViewModel {
  globalId: string;
  toolingMasterGlobalId: string;
  revisionNumber: number;
  revisionLabel: string;
  predecessorGlobalId: string | null;
  specification: ToolingSpecificationViewModel;
  cavities: readonly ToolingCavityMappingViewModel[];
  inserts: readonly ToolingInsertApplicabilityViewModel[];
  externalIdentities: readonly ToolingExternalIdentityViewModel[];
  designDocumentRevisions: readonly ToolingDocumentRevisionReferenceViewModel[];
  reason: string;
  snapshotHash: string;
}

export type ToolingRevisionUnavailableReason =
  | "lifecycle_policy_unavailable"
  | "formal_supplier_unavailable"
  | "erp_projection_unavailable"
  | "combined_trial_not_delivered"
  | "automatic_impact_not_delivered"
  | "controlled_part_specification_not_recorded";

export interface ToolingRevisionUnavailableViewModel {
  state: "unavailable";
  reasonCode: ToolingRevisionUnavailableReason;
}

export interface ToolingRevisionNotDeliveredViewModel {
  state: "unavailable";
  reasonCode: "tooling_revision_not_delivered";
}

export interface ToolingRevisionAvailableCapabilityViewModel {
  state: "available";
  reasonCode: "tooling_revision_available";
  revisionCount: number;
}

export type ToolingRevisionCapabilityViewModel =
  | ToolingRevisionNotDeliveredViewModel
  | ToolingRevisionAvailableCapabilityViewModel;

export interface ToolingRevisionPermissionsViewModel {
  view: boolean;
  createRevision: boolean;
  createPartSpecification: boolean;
  createProcessChain: boolean;
  bindSetSource: boolean;
  transitionLifecycle: false;
}

export interface ToolingRevisionCollectionViewModel {
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  permissions: ToolingRevisionPermissionsViewModel;
  lifecycle: ToolingRevisionUnavailableViewModel;
  supplier: ToolingRevisionUnavailableViewModel;
  erpLocationAndAsset: ToolingRevisionUnavailableViewModel;
  combinedTrial: ToolingRevisionUnavailableViewModel;
  items: readonly ToolingRevisionViewModel[];
}

export interface ToolingRevisionDetailViewModel {
  projectGlobalId: string;
  permissions: ToolingRevisionPermissionsViewModel;
  lifecycle: ToolingRevisionUnavailableViewModel;
  supplier: ToolingRevisionUnavailableViewModel;
  erpLocationAndAsset: ToolingRevisionUnavailableViewModel;
  combinedTrial: ToolingRevisionUnavailableViewModel;
  revision: ToolingRevisionViewModel;
}

export type PartControlledSpecificationKind =
  | "material_family"
  | "grade"
  | "trademark"
  | "color"
  | "color_masterbatch"
  | "fda_compliance"
  | "regulatory_compliance"
  | "secondary_process";

export interface PartControlledSpecificationItemViewModel {
  globalId: string;
  kind: PartControlledSpecificationKind;
  normalizedValue: string;
  rawValue: string;
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
  effectiveFrom: string;
  effectiveTo: string | null;
  unit: string | null;
}

export interface CreatePartControlledSpecificationItemCommand {
  kind: PartControlledSpecificationKind;
  normalizedValue: string;
  rawValue: string;
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
  effectiveFrom: string;
  effectiveTo?: string | undefined;
  unit?: string | undefined;
}

export interface PartControlledSpecificationViewModel {
  globalId: string;
  partGlobalId: string;
  partRevisionGlobalId: string;
  partRevisionSnapshotHash: string;
  items: readonly PartControlledSpecificationItemViewModel[];
  externalIdentities: readonly ToolingExternalIdentityViewModel[];
  snapshotHash: string;
}

export interface EngineeringPartRevisionReferenceForToolingViewModel {
  globalId: string;
  partGlobalId: string;
  revisionNumber: number;
  revisionLabel: string;
  snapshotHash: string;
}

export interface PartControlledSpecificationContextViewModel {
  projectGlobalId: string;
  partGlobalId: string;
  partRevision: EngineeringPartRevisionReferenceForToolingViewModel;
  permissions: ToolingRevisionPermissionsViewModel;
  automaticImpact: ToolingRevisionUnavailableViewModel;
  controlledSpecification:
    | PartControlledSpecificationViewModel
    | ToolingRevisionUnavailableViewModel;
}

export type ToolingProcessKind = "primary_molding" | "second_shot" | "overmold";

export interface ToolingProcessStepViewModel {
  globalId: string;
  stepOrder: number;
  processKind: ToolingProcessKind;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  inputPartRevisionGlobalIds: readonly string[];
  outputPartRevisionGlobalId: string;
  parentStepGlobalId: string | null;
  machineType: string;
  clampTonnage: ToolingMeasurementViewModel;
}

export interface CreateToolingProcessStepCommand {
  stepOrder: number;
  processKind: ToolingProcessKind;
  toolingRevisionGlobalId: string;
  inputPartRevisionGlobalIds: readonly string[];
  outputPartRevisionGlobalId: string;
  parentStepOrder?: number | undefined;
  machineType: string;
  clampTonnage: ToolingMeasurementViewModel;
}

export interface ToolingProcessChainRevisionViewModel {
  globalId: string;
  processChainGlobalId: string;
  chainVersion: number;
  predecessorGlobalId: string | null;
  steps: readonly ToolingProcessStepViewModel[];
  reason: string;
  snapshotHash: string;
}

export interface ToolingProcessChainCollectionViewModel {
  projectGlobalId: string;
  permissions: ToolingRevisionPermissionsViewModel;
  combinedTrial: ToolingRevisionUnavailableViewModel;
  items: readonly ToolingProcessChainRevisionViewModel[];
}

export interface ToolingSetRevisionBindingViewModel {
  globalId: string;
  toolingMasterGlobalId: string;
  toolingSetGlobalId: string;
  toolingSetSnapshotHash: string;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  reason: string;
  snapshotHash: string;
}

export type ToolingSetSourceRevisionViewModel =
  | ToolingRevisionNotDeliveredViewModel
  | ToolingSetRevisionBindingViewModel;

export interface CreateToolingRevisionCommand {
  expectedVersion?: number | undefined;
  revisionLabel: string;
  specification: ToolingSpecificationViewModel;
  cavities: readonly CreateToolingCavityMappingCommand[];
  inserts: readonly CreateToolingInsertApplicabilityCommand[];
  externalIdentities: readonly CreateToolingExternalIdentityCommand[];
  designDocumentRevisions: readonly ToolingDocumentRevisionReferenceViewModel[];
  reason: string;
}

export interface CreatePartControlledSpecificationCommand {
  items: readonly CreatePartControlledSpecificationItemCommand[];
  externalIdentities: readonly CreateToolingExternalIdentityCommand[];
}

export interface CreateToolingProcessChainRevisionCommand {
  processChainGlobalId?: string | undefined;
  expectedVersion?: number | undefined;
  steps: readonly CreateToolingProcessStepCommand[];
  reason: string;
}

export interface CreateToolingSetRevisionBindingCommand {
  toolingRevisionGlobalId: string;
  reason: string;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const decimalPattern = /^[0-9]+(?:\.[0-9]+)?$/u;
const identityKinds = new Set<ToolingExternalIdentityKind>([
  "customer",
  "sn",
  "kw",
  "th",
  "supplier_reference",
]);
const specificationKinds = new Set<PartControlledSpecificationKind>([
  "material_family",
  "grade",
  "trademark",
  "color",
  "color_masterbatch",
  "fda_compliance",
  "regulatory_compliance",
  "secondary_process",
]);
const unavailableReasons = new Set<ToolingRevisionUnavailableReason>([
  "lifecycle_policy_unavailable",
  "formal_supplier_unavailable",
  "erp_projection_unavailable",
  "combined_trial_not_delivered",
  "automatic_impact_not_delivered",
  "controlled_part_specification_not_recorded",
]);

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function exact(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => key in value);
}

function closed(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[],
): boolean {
  const allowed = new Set([...required, ...optional]);
  return (
    required.every((key) => key in value) &&
    Object.keys(value).every((key) => allowed.has(key))
  );
}

function text(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= maximum
  );
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function hash(value: unknown): value is string {
  return typeof value === "string" && hashPattern.test(value);
}

function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function date(value: unknown): value is string {
  return typeof value === "string" && datePattern.test(value);
}

function unique(values: readonly unknown[]): boolean {
  return new Set(values).size === values.length;
}

function optionalText(value: unknown, maximum: number): value is string | null {
  return value === null || text(value, maximum);
}

function nullableUuid(value: unknown): value is string | null {
  return value === null || uuid(value);
}

function nullableDate(value: unknown): value is string | null {
  return value === null || date(value);
}

export function isToolingMeasurement(
  value: unknown,
): value is ToolingMeasurementViewModel {
  return (
    record(value) &&
    exact(value, ["value", "unit", "source"]) &&
    text(value.value, 32) &&
    decimalPattern.test(value.value) &&
    text(value.unit, 32) &&
    text(value.source, 120)
  );
}

export function isToolingSpecification(
  value: unknown,
): value is ToolingSpecificationViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "toolingType",
      "moldBaseMaterial",
      "coreMaterial",
      "hardness",
      "surfaceTreatment",
      "cavityCount",
      "hotRunner",
      "length",
      "width",
      "height",
      "weight",
      "clampTonnage",
      "tieBarSpacingX",
      "tieBarSpacingY",
      "injectionCapacity",
      "machineType",
      "targetCycle",
      "targetLife",
      "warranty",
      "customerStandard",
      "interfaceRequirement",
      "spareParts",
      "deliveryDocuments",
    ])
  )
    return false;
  return (
    text(value.toolingType, 80) &&
    text(value.moldBaseMaterial, 160) &&
    text(value.coreMaterial, 160) &&
    isToolingMeasurement(value.hardness) &&
    text(value.surfaceTreatment, 160) &&
    positive(value.cavityCount) &&
    value.cavityCount <= 200 &&
    text(value.hotRunner, 160) &&
    isToolingMeasurement(value.length) &&
    isToolingMeasurement(value.width) &&
    isToolingMeasurement(value.height) &&
    isToolingMeasurement(value.weight) &&
    isToolingMeasurement(value.clampTonnage) &&
    isToolingMeasurement(value.tieBarSpacingX) &&
    isToolingMeasurement(value.tieBarSpacingY) &&
    isToolingMeasurement(value.injectionCapacity) &&
    text(value.machineType, 120) &&
    isToolingMeasurement(value.targetCycle) &&
    isToolingMeasurement(value.targetLife) &&
    text(value.warranty, 240) &&
    text(value.customerStandard, 500) &&
    text(value.interfaceRequirement, 500) &&
    Array.isArray(value.spareParts) &&
    value.spareParts.length <= 100 &&
    value.spareParts.every((item) => text(item, 200)) &&
    unique(value.spareParts) &&
    Array.isArray(value.deliveryDocuments) &&
    value.deliveryDocuments.length <= 100 &&
    value.deliveryDocuments.every((item) => text(item, 200)) &&
    unique(value.deliveryDocuments)
  );
}

function isCavity(value: unknown): value is ToolingCavityMappingViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "cavityIdentifier",
      "toolingApplicabilityGlobalId",
      "partRevisionGlobalId",
      "structuralState",
    ]) &&
    uuid(value.globalId) &&
    text(value.cavityIdentifier, 64) &&
    uuid(value.toolingApplicabilityGlobalId) &&
    uuid(value.partRevisionGlobalId) &&
    (value.structuralState === "enabled" || value.structuralState === "sealed")
  );
}

function isExternalIdentity(
  value: unknown,
): value is ToolingExternalIdentityViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "identityType",
      "value",
      "rawValue",
      "sourceSystem",
      "sourceObjectId",
      "effectiveFrom",
      "effectiveTo",
    ]) &&
    uuid(value.globalId) &&
    identityKinds.has(value.identityType as ToolingExternalIdentityKind) &&
    text(value.value, 160) &&
    text(value.rawValue, 500) &&
    (value.sourceSystem === "NPI_ONE" || value.sourceSystem === "ERPNEXT") &&
    text(value.sourceObjectId, 128) &&
    date(value.effectiveFrom) &&
    nullableDate(value.effectiveTo)
  );
}

function isInsert(
  value: unknown,
): value is ToolingInsertApplicabilityViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "globalId",
      "insertCode",
      "insertVersion",
      "toolingApplicabilityGlobalId",
      "partRevisionGlobalId",
      "modelSourceSystem",
      "modelSourceObjectId",
      "changeoverDuration",
      "validationState",
      "validatedByUserId",
      "validatedAt",
      "validationReason",
    ])
  )
    return false;
  const modelCoherent =
    (value.modelSourceSystem === null && value.modelSourceObjectId === null) ||
    ((value.modelSourceSystem === "npi_one" ||
      value.modelSourceSystem === "plm") &&
      text(value.modelSourceObjectId, 200));
  const validationCoherent =
    (value.validationState === "not_validated" &&
      value.validatedByUserId === null &&
      value.validatedAt === null &&
      value.validationReason === null) ||
    (value.validationState === "validated" &&
      text(value.validatedByUserId, 254) &&
      typeof value.validatedAt === "string" &&
      !Number.isNaN(Date.parse(value.validatedAt)) &&
      text(value.validationReason, 500));
  return (
    uuid(value.globalId) &&
    text(value.insertCode, 80) &&
    positive(value.insertVersion) &&
    uuid(value.toolingApplicabilityGlobalId) &&
    uuid(value.partRevisionGlobalId) &&
    modelCoherent &&
    isToolingMeasurement(value.changeoverDuration) &&
    validationCoherent
  );
}

function isDocumentRevision(
  value: unknown,
): value is ToolingDocumentRevisionReferenceViewModel {
  return (
    record(value) &&
    exact(value, ["globalId", "snapshotHash"]) &&
    uuid(value.globalId) &&
    hash(value.snapshotHash)
  );
}

export function isToolingRevision(
  value: unknown,
): value is ToolingRevisionViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "toolingMasterGlobalId",
      "revisionNumber",
      "revisionLabel",
      "predecessorGlobalId",
      "specification",
      "cavities",
      "inserts",
      "externalIdentities",
      "designDocumentRevisions",
      "reason",
      "snapshotHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.toolingMasterGlobalId) &&
    positive(value.revisionNumber) &&
    text(value.revisionLabel, 40) &&
    nullableUuid(value.predecessorGlobalId) &&
    isToolingSpecification(value.specification) &&
    Array.isArray(value.cavities) &&
    value.cavities.length >= 1 &&
    value.cavities.length <= 200 &&
    value.cavities.every(isCavity) &&
    Array.isArray(value.inserts) &&
    value.inserts.length <= 200 &&
    value.inserts.every(isInsert) &&
    Array.isArray(value.externalIdentities) &&
    value.externalIdentities.length <= 100 &&
    value.externalIdentities.every(isExternalIdentity) &&
    Array.isArray(value.designDocumentRevisions) &&
    value.designDocumentRevisions.length <= 50 &&
    value.designDocumentRevisions.every(isDocumentRevision) &&
    text(value.reason, 500) &&
    hash(value.snapshotHash)
  );
}

export function isToolingRevisionUnavailable(
  value: unknown,
): value is ToolingRevisionUnavailableViewModel {
  return (
    record(value) &&
    exact(value, ["state", "reasonCode"]) &&
    value.state === "unavailable" &&
    unavailableReasons.has(value.reasonCode as ToolingRevisionUnavailableReason)
  );
}

export function isToolingRevisionCapability(
  value: unknown,
): value is ToolingRevisionCapabilityViewModel {
  if (!record(value)) return false;
  if (value.state === "unavailable") {
    return (
      exact(value, ["state", "reasonCode"]) &&
      value.reasonCode === "tooling_revision_not_delivered"
    );
  }
  return (
    exact(value, ["state", "reasonCode", "revisionCount"]) &&
    value.state === "available" &&
    value.reasonCode === "tooling_revision_available" &&
    typeof value.revisionCount === "number" &&
    Number.isInteger(value.revisionCount) &&
    value.revisionCount >= 0 &&
    value.revisionCount <= 200
  );
}

function isPermissions(
  value: unknown,
): value is ToolingRevisionPermissionsViewModel {
  return (
    record(value) &&
    exact(value, [
      "view",
      "createRevision",
      "createPartSpecification",
      "createProcessChain",
      "bindSetSource",
      "transitionLifecycle",
    ]) &&
    typeof value.view === "boolean" &&
    typeof value.createRevision === "boolean" &&
    typeof value.createPartSpecification === "boolean" &&
    typeof value.createProcessChain === "boolean" &&
    typeof value.bindSetSource === "boolean" &&
    value.transitionLifecycle === false
  );
}

function isRevisionContextFields(value: Record<string, unknown>): boolean {
  return (
    isPermissions(value.permissions) &&
    isToolingRevisionUnavailable(value.lifecycle) &&
    value.lifecycle.reasonCode === "lifecycle_policy_unavailable" &&
    isToolingRevisionUnavailable(value.supplier) &&
    value.supplier.reasonCode === "formal_supplier_unavailable" &&
    isToolingRevisionUnavailable(value.erpLocationAndAsset) &&
    value.erpLocationAndAsset.reasonCode === "erp_projection_unavailable" &&
    isToolingRevisionUnavailable(value.combinedTrial) &&
    value.combinedTrial.reasonCode === "combined_trial_not_delivered"
  );
}

export function isToolingRevisionCollection(
  value: unknown,
): value is ToolingRevisionCollectionViewModel {
  return (
    record(value) &&
    exact(value, [
      "projectGlobalId",
      "toolingMasterGlobalId",
      "permissions",
      "lifecycle",
      "supplier",
      "erpLocationAndAsset",
      "combinedTrial",
      "items",
    ]) &&
    uuid(value.projectGlobalId) &&
    uuid(value.toolingMasterGlobalId) &&
    isRevisionContextFields(value) &&
    Array.isArray(value.items) &&
    value.items.length <= 200 &&
    value.items.every(isToolingRevision)
  );
}

export function isToolingRevisionDetail(
  value: unknown,
): value is ToolingRevisionDetailViewModel {
  return (
    record(value) &&
    exact(value, [
      "projectGlobalId",
      "permissions",
      "lifecycle",
      "supplier",
      "erpLocationAndAsset",
      "combinedTrial",
      "revision",
    ]) &&
    uuid(value.projectGlobalId) &&
    isRevisionContextFields(value) &&
    isToolingRevision(value.revision)
  );
}

function isEngineeringPartRevision(
  value: unknown,
): value is EngineeringPartRevisionReferenceForToolingViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "partGlobalId",
      "revisionNumber",
      "revisionLabel",
      "snapshotHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.partGlobalId) &&
    positive(value.revisionNumber) &&
    text(value.revisionLabel, 40) &&
    hash(value.snapshotHash)
  );
}

function isPartSpecificationItem(
  value: unknown,
): value is PartControlledSpecificationItemViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "kind",
      "normalizedValue",
      "rawValue",
      "sourceSystem",
      "sourceObjectId",
      "effectiveFrom",
      "effectiveTo",
      "unit",
    ]) &&
    uuid(value.globalId) &&
    specificationKinds.has(value.kind as PartControlledSpecificationKind) &&
    text(value.normalizedValue, 240) &&
    text(value.rawValue, 500) &&
    (value.sourceSystem === "NPI_ONE" || value.sourceSystem === "ERPNEXT") &&
    text(value.sourceObjectId, 128) &&
    date(value.effectiveFrom) &&
    nullableDate(value.effectiveTo) &&
    optionalText(value.unit, 32)
  );
}

function isPartSpecification(
  value: unknown,
): value is PartControlledSpecificationViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "partGlobalId",
      "partRevisionGlobalId",
      "partRevisionSnapshotHash",
      "items",
      "externalIdentities",
      "snapshotHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.partGlobalId) &&
    uuid(value.partRevisionGlobalId) &&
    hash(value.partRevisionSnapshotHash) &&
    Array.isArray(value.items) &&
    value.items.length >= 1 &&
    value.items.length <= 100 &&
    value.items.every(isPartSpecificationItem) &&
    Array.isArray(value.externalIdentities) &&
    value.externalIdentities.length <= 100 &&
    value.externalIdentities.every(isExternalIdentity) &&
    hash(value.snapshotHash)
  );
}

export function isPartControlledSpecificationContext(
  value: unknown,
): value is PartControlledSpecificationContextViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "projectGlobalId",
      "partGlobalId",
      "partRevision",
      "permissions",
      "automaticImpact",
      "controlledSpecification",
    ])
  )
    return false;
  return (
    uuid(value.projectGlobalId) &&
    uuid(value.partGlobalId) &&
    isEngineeringPartRevision(value.partRevision) &&
    value.partRevision.partGlobalId === value.partGlobalId &&
    isPermissions(value.permissions) &&
    isToolingRevisionUnavailable(value.automaticImpact) &&
    value.automaticImpact.reasonCode === "automatic_impact_not_delivered" &&
    (isPartSpecification(value.controlledSpecification) ||
      (isToolingRevisionUnavailable(value.controlledSpecification) &&
        value.controlledSpecification.reasonCode ===
          "controlled_part_specification_not_recorded"))
  );
}

function isProcessStep(value: unknown): value is ToolingProcessStepViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "stepOrder",
      "processKind",
      "toolingRevisionGlobalId",
      "toolingRevisionSnapshotHash",
      "inputPartRevisionGlobalIds",
      "outputPartRevisionGlobalId",
      "parentStepGlobalId",
      "machineType",
      "clampTonnage",
    ]) &&
    uuid(value.globalId) &&
    positive(value.stepOrder) &&
    value.stepOrder <= 20 &&
    (value.processKind === "primary_molding" ||
      value.processKind === "second_shot" ||
      value.processKind === "overmold") &&
    uuid(value.toolingRevisionGlobalId) &&
    hash(value.toolingRevisionSnapshotHash) &&
    Array.isArray(value.inputPartRevisionGlobalIds) &&
    value.inputPartRevisionGlobalIds.length >= 1 &&
    value.inputPartRevisionGlobalIds.length <= 20 &&
    value.inputPartRevisionGlobalIds.every(uuid) &&
    unique(value.inputPartRevisionGlobalIds) &&
    uuid(value.outputPartRevisionGlobalId) &&
    nullableUuid(value.parentStepGlobalId) &&
    text(value.machineType, 120) &&
    isToolingMeasurement(value.clampTonnage)
  );
}

export function isToolingProcessChainRevision(
  value: unknown,
): value is ToolingProcessChainRevisionViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "processChainGlobalId",
      "chainVersion",
      "predecessorGlobalId",
      "steps",
      "reason",
      "snapshotHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.processChainGlobalId) &&
    positive(value.chainVersion) &&
    nullableUuid(value.predecessorGlobalId) &&
    Array.isArray(value.steps) &&
    value.steps.length >= 2 &&
    value.steps.length <= 20 &&
    value.steps.every(isProcessStep) &&
    text(value.reason, 500) &&
    hash(value.snapshotHash)
  );
}

export function isToolingProcessChainCollection(
  value: unknown,
): value is ToolingProcessChainCollectionViewModel {
  return (
    record(value) &&
    exact(value, [
      "projectGlobalId",
      "permissions",
      "combinedTrial",
      "items",
    ]) &&
    uuid(value.projectGlobalId) &&
    isPermissions(value.permissions) &&
    isToolingRevisionUnavailable(value.combinedTrial) &&
    value.combinedTrial.reasonCode === "combined_trial_not_delivered" &&
    Array.isArray(value.items) &&
    value.items.length <= 500 &&
    value.items.every(isToolingProcessChainRevision)
  );
}

export function isToolingSetRevisionBinding(
  value: unknown,
): value is ToolingSetRevisionBindingViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "toolingMasterGlobalId",
      "toolingSetGlobalId",
      "toolingSetSnapshotHash",
      "toolingRevisionGlobalId",
      "toolingRevisionSnapshotHash",
      "reason",
      "snapshotHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.toolingMasterGlobalId) &&
    uuid(value.toolingSetGlobalId) &&
    hash(value.toolingSetSnapshotHash) &&
    uuid(value.toolingRevisionGlobalId) &&
    hash(value.toolingRevisionSnapshotHash) &&
    text(value.reason, 500) &&
    hash(value.snapshotHash)
  );
}

export function isToolingSetSourceRevision(
  value: unknown,
): value is ToolingSetSourceRevisionViewModel {
  return (
    isToolingSetRevisionBinding(value) ||
    (record(value) &&
      exact(value, ["state", "reasonCode"]) &&
      value.state === "unavailable" &&
      value.reasonCode === "tooling_revision_not_delivered")
  );
}

function isExternalReference(value: unknown): boolean {
  return (
    record(value) &&
    exact(value, ["sourceSystem", "sourceObjectId"]) &&
    (value.sourceSystem === "NPI_ONE" || value.sourceSystem === "ERPNEXT") &&
    text(value.sourceObjectId, 128)
  );
}

function isCreateCavity(value: unknown): boolean {
  return (
    record(value) &&
    exact(value, [
      "cavityIdentifier",
      "toolingApplicabilityGlobalId",
      "partRevisionGlobalId",
      "structuralState",
    ]) &&
    text(value.cavityIdentifier, 64) &&
    uuid(value.toolingApplicabilityGlobalId) &&
    uuid(value.partRevisionGlobalId) &&
    (value.structuralState === "enabled" || value.structuralState === "sealed")
  );
}

function isCreateInsert(value: unknown): boolean {
  if (!record(value)) return false;
  const required = [
    "insertCode",
    "insertVersion",
    "toolingApplicabilityGlobalId",
    "partRevisionGlobalId",
    "changeoverDuration",
    "validationState",
  ];
  const optional = ["model", "validationReason"];
  if (
    !Object.keys(value).every((key) => [...required, ...optional].includes(key))
  )
    return false;
  return (
    required.every((key) => key in value) &&
    text(value.insertCode, 80) &&
    positive(value.insertVersion) &&
    uuid(value.toolingApplicabilityGlobalId) &&
    uuid(value.partRevisionGlobalId) &&
    (value.model === undefined || isExternalReference(value.model)) &&
    isToolingMeasurement(value.changeoverDuration) &&
    (value.validationState === "not_validated" ||
      value.validationState === "validated") &&
    (value.validationState === "validated"
      ? text(value.validationReason, 500)
      : value.validationReason === undefined)
  );
}

function isCreateExternalIdentity(value: unknown): boolean {
  if (!record(value)) return false;
  const required = [
    "identityType",
    "value",
    "rawValue",
    "sourceSystem",
    "sourceObjectId",
    "effectiveFrom",
  ];
  if (
    !Object.keys(value).every((key) =>
      [...required, "effectiveTo"].includes(key),
    )
  )
    return false;
  return (
    required.every((key) => key in value) &&
    identityKinds.has(value.identityType as ToolingExternalIdentityKind) &&
    text(value.value, 160) &&
    text(value.rawValue, 500) &&
    (value.sourceSystem === "NPI_ONE" || value.sourceSystem === "ERPNEXT") &&
    text(value.sourceObjectId, 128) &&
    date(value.effectiveFrom) &&
    (value.effectiveTo === undefined || date(value.effectiveTo))
  );
}

export function isCreateToolingRevisionCommand(
  value: unknown,
): value is CreateToolingRevisionCommand {
  if (
    !record(value) ||
    !closed(
      value,
      [
        "revisionLabel",
        "specification",
        "cavities",
        "inserts",
        "externalIdentities",
        "designDocumentRevisions",
        "reason",
      ],
      ["expectedVersion"],
    ) ||
    !Array.isArray(value.cavities) ||
    !Array.isArray(value.inserts) ||
    !Array.isArray(value.externalIdentities) ||
    !Array.isArray(value.designDocumentRevisions)
  )
    return false;
  return (
    (value.expectedVersion === undefined || positive(value.expectedVersion)) &&
    text(value.revisionLabel, 40) &&
    isToolingSpecification(value.specification) &&
    value.cavities.length >= 1 &&
    value.cavities.length <= 200 &&
    value.cavities.every(isCreateCavity) &&
    unique(
      value.cavities.map((item) =>
        record(item) ? item.cavityIdentifier : undefined,
      ),
    ) &&
    value.inserts.length <= 200 &&
    value.inserts.every(isCreateInsert) &&
    value.externalIdentities.length <= 100 &&
    value.externalIdentities.every(isCreateExternalIdentity) &&
    value.designDocumentRevisions.length <= 50 &&
    value.designDocumentRevisions.every(isDocumentRevision) &&
    unique(value.designDocumentRevisions.map((item) => item.globalId)) &&
    text(value.reason, 500)
  );
}

function isCreatePartSpecificationItem(value: unknown): boolean {
  if (!record(value)) return false;
  const required = [
    "kind",
    "normalizedValue",
    "rawValue",
    "sourceSystem",
    "sourceObjectId",
    "effectiveFrom",
  ];
  const optional = ["effectiveTo", "unit"];
  if (
    !Object.keys(value).every((key) => [...required, ...optional].includes(key))
  )
    return false;
  return (
    required.every((key) => key in value) &&
    specificationKinds.has(value.kind as PartControlledSpecificationKind) &&
    text(value.normalizedValue, 240) &&
    text(value.rawValue, 500) &&
    (value.sourceSystem === "NPI_ONE" || value.sourceSystem === "ERPNEXT") &&
    text(value.sourceObjectId, 128) &&
    date(value.effectiveFrom) &&
    (value.effectiveTo === undefined || date(value.effectiveTo)) &&
    (value.unit === undefined || text(value.unit, 32))
  );
}

export function isCreatePartControlledSpecificationCommand(
  value: unknown,
): value is CreatePartControlledSpecificationCommand {
  if (
    !record(value) ||
    !exact(value, ["items", "externalIdentities"]) ||
    !Array.isArray(value.items) ||
    !Array.isArray(value.externalIdentities)
  )
    return false;
  return (
    value.items.length >= 1 &&
    value.items.length <= 100 &&
    value.items.every(isCreatePartSpecificationItem) &&
    value.externalIdentities.length <= 100 &&
    value.externalIdentities.every(isCreateExternalIdentity)
  );
}

function isCreateProcessStep(value: unknown): boolean {
  if (!record(value)) return false;
  const required = [
    "stepOrder",
    "processKind",
    "toolingRevisionGlobalId",
    "inputPartRevisionGlobalIds",
    "outputPartRevisionGlobalId",
    "machineType",
    "clampTonnage",
  ];
  if (
    !Object.keys(value).every((key) =>
      [...required, "parentStepOrder"].includes(key),
    )
  )
    return false;
  return (
    required.every((key) => key in value) &&
    positive(value.stepOrder) &&
    value.stepOrder <= 20 &&
    (value.processKind === "primary_molding" ||
      value.processKind === "second_shot" ||
      value.processKind === "overmold") &&
    uuid(value.toolingRevisionGlobalId) &&
    Array.isArray(value.inputPartRevisionGlobalIds) &&
    value.inputPartRevisionGlobalIds.length >= 1 &&
    value.inputPartRevisionGlobalIds.length <= 20 &&
    value.inputPartRevisionGlobalIds.every(uuid) &&
    unique(value.inputPartRevisionGlobalIds) &&
    uuid(value.outputPartRevisionGlobalId) &&
    (value.parentStepOrder === undefined ||
      (positive(value.parentStepOrder) &&
        value.parentStepOrder < value.stepOrder)) &&
    text(value.machineType, 120) &&
    isToolingMeasurement(value.clampTonnage)
  );
}

export function isCreateToolingProcessChainRevisionCommand(
  value: unknown,
): value is CreateToolingProcessChainRevisionCommand {
  if (
    !record(value) ||
    !closed(
      value,
      ["steps", "reason"],
      ["processChainGlobalId", "expectedVersion"],
    ) ||
    !Array.isArray(value.steps)
  )
    return false;
  const stepOrders = value.steps
    .filter(record)
    .map((item) => item.stepOrder)
    .filter((item): item is number => typeof item === "number");
  return (
    (value.processChainGlobalId === undefined ||
      uuid(value.processChainGlobalId)) &&
    (value.expectedVersion === undefined || positive(value.expectedVersion)) &&
    ((value.processChainGlobalId === undefined &&
      value.expectedVersion === undefined) ||
      (value.processChainGlobalId !== undefined &&
        value.expectedVersion !== undefined)) &&
    value.steps.length >= 2 &&
    value.steps.length <= 20 &&
    value.steps.every(isCreateProcessStep) &&
    unique(stepOrders) &&
    value.steps.every((item) => {
      if (!record(item)) return false;
      return (
        item.parentStepOrder === undefined ||
        (typeof item.parentStepOrder === "number" &&
          stepOrders.includes(item.parentStepOrder))
      );
    }) &&
    text(value.reason, 500)
  );
}

export function isCreateToolingSetRevisionBindingCommand(
  value: unknown,
): value is CreateToolingSetRevisionBindingCommand {
  return (
    record(value) &&
    exact(value, ["toolingRevisionGlobalId", "reason"]) &&
    uuid(value.toolingRevisionGlobalId) &&
    text(value.reason, 500)
  );
}
