export type ToolingSourcingStrategy = "internal" | "supplier" | "hybrid";
export type ToolingManufacturingMilestoneCategory =
  | "design"
  | "material_preparation"
  | "heat_treatment"
  | "machining"
  | "assembly"
  | "trial_preparation"
  | "delivery";
export type ToolingMilestoneResponsibilityKind = "internal" | "supplier";
export type ToolingPlanEvidenceRole =
  | "dfm"
  | "tooling_proposal"
  | "quotation"
  | "budget";
export type ToolingMilestoneEvidenceRole =
  | "progress_evidence"
  | "technical_evidence"
  | "delivery_evidence";

export interface ToolingProjectMemberResponsibilityViewModel {
  globalId: string;
  userId: string;
  optimisticVersion: number;
}

export interface ToolingPlanningMoneyViewModel {
  amount: string;
  currency: string;
}

export interface ToolingReleasedDocumentEvidenceViewModel {
  revisionGlobalId: string;
  revisionSnapshotHash: string;
  lifecycleGlobalId: string;
  lifecycleVersion: number;
  releaseEventGlobalId: string;
  releaseEventHash: string;
  releaseSnapshotHash: string;
}

export interface ToolingManufacturingPlanEvidenceViewModel {
  role: ToolingPlanEvidenceRole;
  document: ToolingReleasedDocumentEvidenceViewModel;
}

export interface ToolingManufacturingMilestoneViewModel {
  globalId: string;
  sequence: number;
  category: ToolingManufacturingMilestoneCategory;
  plannedStart: string;
  plannedFinish: string;
  responsibilityKind: ToolingMilestoneResponsibilityKind;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel | null;
  predecessorGlobalIds: readonly string[];
  snapshotHash: string;
}

export interface ToolingManufacturingPlanRevisionViewModel {
  globalId: string;
  planGlobalId: string;
  toolingMasterGlobalId: string;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  planVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  sourcingStrategy: ToolingSourcingStrategy;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel;
  engineeringEstimate: ToolingPlanningMoneyViewModel | null;
  budget: ToolingPlanningMoneyViewModel | null;
  evidence: readonly ToolingManufacturingPlanEvidenceViewModel[];
  designReleaseEvidence: readonly ToolingReleasedDocumentEvidenceViewModel[];
  milestones: readonly ToolingManufacturingMilestoneViewModel[];
  reason: string;
  snapshotHash: string;
}

export interface ToolingMilestoneFileEvidenceViewModel {
  globalId: string;
  role: ToolingMilestoneEvidenceRole;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: number;
  frappeContentHash: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  sha256: string;
}

export interface ToolingManufacturingMilestoneObservationViewModel {
  globalId: string;
  planRevisionGlobalId: string;
  planRevisionSnapshotHash: string;
  milestoneGlobalId: string;
  milestoneSnapshotHash: string;
  observationVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  progressPercentage: number;
  actualStart: string | null;
  actualFinish: string | null;
  risk: string | null;
  note: string | null;
  evidence: readonly ToolingMilestoneFileEvidenceViewModel[];
  reportedByMember: ToolingProjectMemberResponsibilityViewModel;
  snapshotHash: string;
}

export type ToolingDesignReleaseEvidenceCapabilityViewModel =
  | Readonly<{
      state: "satisfied";
      reasonCode: null;
      items: readonly ToolingReleasedDocumentEvidenceViewModel[];
    }>
  | Readonly<{
      state: "blocked";
      reasonCode: "no_design_documents" | "release_evidence_incomplete";
      items: readonly [];
    }>;

export interface ToolingManufacturingAuthorizationViewModel {
  state: "unavailable";
  reasonCode: "tooling_lifecycle_policy_unavailable";
}

export interface ToolingFormalSupplierReferenceViewModel {
  sourceObjectId: string;
  targetVersion: string;
  supplierCode: string;
  supplierName: string;
}

export interface ToolingErpActualCostRowViewModel {
  toolingMasterGlobalId: string;
  sourceRowId: string;
  sourceRowVersion: string;
  supplierSourceObjectId: string;
  purchaseOrderSourceId: string;
  purchaseReceiptSourceId: string;
  purchaseInvoiceSourceId: string;
  actualCostSourceId: string;
  costTypeCode: string;
  postingDate: string;
  currency: string;
  amount: string;
}

export interface ToolingErpActualCostSummaryViewModel {
  toolingMasterGlobalId: string;
  supplierSourceObjectId: string;
  costTypeCode: string;
  currency: string;
  amount: string;
}

export type ToolingProcurementCostProjectionViewModel =
  | Readonly<{
      sourceSystem: "ERPNEXT";
      editableIn: "ERPNEXT";
      state: "unavailable";
      reasonCode: "erp_projection_unavailable";
    }>
  | Readonly<{
      sourceSystem: "ERPNEXT";
      editableIn: "ERPNEXT";
      state: "available";
      toolingMasterGlobalId: string;
      observedAt: string;
      targetVersion: string;
      supplier: ToolingFormalSupplierReferenceViewModel;
      rows: readonly ToolingErpActualCostRowViewModel[];
      summaries: readonly ToolingErpActualCostSummaryViewModel[];
    }>;

export interface ToolingManufacturingPermissionsViewModel {
  view: boolean;
  createPlan: boolean;
  observeMilestone: boolean;
  transitionLifecycle: false;
  editErpProjection: false;
}

export interface ToolingManufacturingPlanItemViewModel {
  plan: ToolingManufacturingPlanRevisionViewModel;
  observations: readonly ToolingManufacturingMilestoneObservationViewModel[];
  designReleaseEvidence: ToolingDesignReleaseEvidenceCapabilityViewModel;
}

export interface ToolingManufacturingPlanCollectionViewModel {
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  permissions: ToolingManufacturingPermissionsViewModel;
  manufacturingAuthorization: ToolingManufacturingAuthorizationViewModel;
  erpProjection: ToolingProcurementCostProjectionViewModel;
  items: readonly ToolingManufacturingPlanItemViewModel[];
}

export interface ToolingManufacturingPlanDetailViewModel {
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  permissions: ToolingManufacturingPermissionsViewModel;
  manufacturingAuthorization: ToolingManufacturingAuthorizationViewModel;
  erpProjection: ToolingProcurementCostProjectionViewModel;
  item: ToolingManufacturingPlanItemViewModel;
}

export interface CreateToolingManufacturingMilestoneCommand {
  globalId: string;
  sequence: number;
  category: ToolingManufacturingMilestoneCategory;
  plannedStart: string;
  plannedFinish: string;
  responsibilityKind: ToolingMilestoneResponsibilityKind;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel | null;
  predecessorGlobalIds: readonly string[];
}

export interface CreateToolingManufacturingPlanCommand {
  planGlobalId?: string | undefined;
  expectedVersion?: number | undefined;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  sourcingStrategy: ToolingSourcingStrategy;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel;
  engineeringEstimate?: ToolingPlanningMoneyViewModel | undefined;
  budget?: ToolingPlanningMoneyViewModel | undefined;
  evidence: readonly ToolingManufacturingPlanEvidenceViewModel[];
  designReleaseEvidence: readonly ToolingReleasedDocumentEvidenceViewModel[];
  milestones: readonly CreateToolingManufacturingMilestoneCommand[];
  reason: string;
}

export interface CreateToolingMilestoneFileEvidenceCommand {
  role: ToolingMilestoneEvidenceRole;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: number;
  frappeContentHash: string;
  sha256: string;
}

export interface CreateToolingManufacturingObservationCommand {
  expectedVersion?: number | undefined;
  planRevisionSnapshotHash: string;
  milestoneSnapshotHash: string;
  progressPercentage: number;
  actualStart?: string | undefined;
  actualFinish?: string | undefined;
  risk?: string | undefined;
  note?: string | undefined;
  evidence: readonly CreateToolingMilestoneFileEvidenceCommand[];
}

export interface ToolingManufacturingPlanCommandViewModel {
  plan: ToolingManufacturingPlanRevisionViewModel;
  designReleaseEvidence: ToolingDesignReleaseEvidenceCapabilityViewModel;
}

export interface ToolingManufacturingObservationCommandViewModel {
  observation: ToolingManufacturingMilestoneObservationViewModel;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const contentHashPattern = /^[a-f0-9]{32,128}$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const currencyPattern = /^[A-Z]{3}$/u;
const unsignedAmountPattern = /^[0-9]+(?:\.[0-9]+)?$/u;
const signedAmountPattern = /^-?[0-9]+(?:\.[0-9]+)?$/u;
const categories = new Set<ToolingManufacturingMilestoneCategory>([
  "design",
  "material_preparation",
  "heat_treatment",
  "machining",
  "assembly",
  "trial_preparation",
  "delivery",
]);
const sourcingStrategies = new Set<ToolingSourcingStrategy>([
  "internal",
  "supplier",
  "hybrid",
]);
const planEvidenceRoles = new Set<ToolingPlanEvidenceRole>([
  "dfm",
  "tooling_proposal",
  "quotation",
  "budget",
]);
const fileEvidenceRoles = new Set<ToolingMilestoneEvidenceRole>([
  "progress_evidence",
  "technical_evidence",
  "delivery_evidence",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  const observed = Object.keys(value);
  return observed.length === keys.length && keys.every((key) => key in value);
}

function hasRequiredAndAllowedKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  allowed: readonly string[],
): boolean {
  const accepted = new Set(allowed);
  return (
    required.every((key) => key in value) &&
    Object.keys(value).every((key) => accepted.has(key))
  );
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isHash(value: unknown): value is string {
  return typeof value === "string" && hashPattern.test(value);
}

function isText(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= maximum
  );
}

function isInteger(value: unknown, minimum: number, maximum: number): boolean {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function isDate(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value)
  );
}

function isDateTime(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 64) return false;
  const parsed = new Date(value);
  return (
    !Number.isNaN(parsed.valueOf()) && /(?:Z|[+-]\d{2}:\d{2})$/u.test(value)
  );
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

export function isToolingProjectMemberResponsibility(
  value: unknown,
): value is ToolingProjectMemberResponsibilityViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "userId", "optimisticVersion"]) &&
    isUuid(value.globalId) &&
    isText(value.userId, 254) &&
    isInteger(value.optimisticVersion, 1, Number.MAX_SAFE_INTEGER)
  );
}

function isMoney(
  value: unknown,
  signed = false,
): value is ToolingPlanningMoneyViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["amount", "currency"]) &&
    typeof value.amount === "string" &&
    value.amount.length <= 32 &&
    (signed ? signedAmountPattern : unsignedAmountPattern).test(value.amount) &&
    typeof value.currency === "string" &&
    currencyPattern.test(value.currency)
  );
}

export function isToolingReleasedDocumentEvidence(
  value: unknown,
): value is ToolingReleasedDocumentEvidenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "revisionGlobalId",
      "revisionSnapshotHash",
      "lifecycleGlobalId",
      "lifecycleVersion",
      "releaseEventGlobalId",
      "releaseEventHash",
      "releaseSnapshotHash",
    ]) &&
    isUuid(value.revisionGlobalId) &&
    isHash(value.revisionSnapshotHash) &&
    isUuid(value.lifecycleGlobalId) &&
    isInteger(value.lifecycleVersion, 1, Number.MAX_SAFE_INTEGER) &&
    isUuid(value.releaseEventGlobalId) &&
    isHash(value.releaseEventHash) &&
    isHash(value.releaseSnapshotHash)
  );
}

function isPlanEvidence(
  value: unknown,
): value is ToolingManufacturingPlanEvidenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["role", "document"]) &&
    typeof value.role === "string" &&
    planEvidenceRoles.has(value.role as ToolingPlanEvidenceRole) &&
    isToolingReleasedDocumentEvidence(value.document)
  );
}

function isMilestoneBase(
  value: unknown,
  withSnapshot: boolean,
): value is ToolingManufacturingMilestoneViewModel {
  if (!isRecord(value)) return false;
  const keys = [
    "globalId",
    "sequence",
    "category",
    "plannedStart",
    "plannedFinish",
    "responsibilityKind",
    "responsibleMember",
    "predecessorGlobalIds",
    ...(withSnapshot ? ["snapshotHash"] : []),
  ];
  if (
    !hasExactKeys(value, keys) ||
    !isUuid(value.globalId) ||
    !isInteger(value.sequence, 1, 100) ||
    typeof value.category !== "string" ||
    !categories.has(value.category as ToolingManufacturingMilestoneCategory) ||
    !isDate(value.plannedStart) ||
    !isDate(value.plannedFinish) ||
    value.plannedFinish < value.plannedStart ||
    (value.responsibilityKind !== "internal" &&
      value.responsibilityKind !== "supplier") ||
    !Array.isArray(value.predecessorGlobalIds) ||
    value.predecessorGlobalIds.length > 20 ||
    !value.predecessorGlobalIds.every(isUuid) ||
    !unique(value.predecessorGlobalIds) ||
    (withSnapshot && !isHash(value.snapshotHash))
  )
    return false;
  return value.responsibilityKind === "internal"
    ? isToolingProjectMemberResponsibility(value.responsibleMember)
    : value.responsibleMember === null;
}

function isCoherentMilestoneGraph(
  value: readonly (
    | ToolingManufacturingMilestoneViewModel
    | CreateToolingManufacturingMilestoneCommand
  )[],
): boolean {
  if (value.length < 1 || value.length > 100) return false;
  const ids = value.map((item) => item.globalId);
  const sequences = value.map((item) => item.sequence);
  if (!unique(ids) || !unique(sequences.map(String))) return false;
  const sequenceById = new Map(
    value.map((item) => [item.globalId, item.sequence]),
  );
  return value.every((item) =>
    item.predecessorGlobalIds.every(
      (predecessor) =>
        sequenceById.has(predecessor) &&
        (sequenceById.get(predecessor) ?? item.sequence) < item.sequence,
    ),
  );
}

export function isToolingManufacturingPlanRevision(
  value: unknown,
): value is ToolingManufacturingPlanRevisionViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "planGlobalId",
      "toolingMasterGlobalId",
      "toolingRevisionGlobalId",
      "toolingRevisionSnapshotHash",
      "planVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "sourcingStrategy",
      "responsibleMember",
      "engineeringEstimate",
      "budget",
      "evidence",
      "designReleaseEvidence",
      "milestones",
      "reason",
      "snapshotHash",
    ]) ||
    !isUuid(value.globalId) ||
    !isUuid(value.planGlobalId) ||
    !isUuid(value.toolingMasterGlobalId) ||
    !isUuid(value.toolingRevisionGlobalId) ||
    !isHash(value.toolingRevisionSnapshotHash) ||
    !isInteger(value.planVersion, 1, Number.MAX_SAFE_INTEGER) ||
    typeof value.sourcingStrategy !== "string" ||
    !sourcingStrategies.has(
      value.sourcingStrategy as ToolingSourcingStrategy,
    ) ||
    !isToolingProjectMemberResponsibility(value.responsibleMember) ||
    (value.engineeringEstimate !== null &&
      !isMoney(value.engineeringEstimate)) ||
    (value.budget !== null && !isMoney(value.budget)) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 4 ||
    !value.evidence.every(isPlanEvidence) ||
    !unique(value.evidence.map((item) => item.role)) ||
    !Array.isArray(value.designReleaseEvidence) ||
    value.designReleaseEvidence.length < 1 ||
    value.designReleaseEvidence.length > 50 ||
    !value.designReleaseEvidence.every(isToolingReleasedDocumentEvidence) ||
    !unique(value.designReleaseEvidence.map((item) => item.revisionGlobalId)) ||
    !Array.isArray(value.milestones) ||
    !value.milestones.every((item) => isMilestoneBase(item, true)) ||
    !isCoherentMilestoneGraph(value.milestones) ||
    !isText(value.reason, 500) ||
    !isHash(value.snapshotHash)
  )
    return false;
  const initial = value.planVersion === 1;
  if (
    initial !==
    (value.predecessorGlobalId === null &&
      value.predecessorSnapshotHash === null)
  )
    return false;
  if (
    !initial &&
    (!isUuid(value.predecessorGlobalId) ||
      !isHash(value.predecessorSnapshotHash))
  )
    return false;
  if (
    value.engineeringEstimate &&
    value.budget &&
    value.engineeringEstimate.currency !== value.budget.currency
  )
    return false;
  const releaseByRevision = new Map<string, string>();
  for (const released of [
    ...value.designReleaseEvidence,
    ...value.evidence.map((item) => item.document),
  ]) {
    const canonical = JSON.stringify(released);
    const previous = releaseByRevision.get(released.revisionGlobalId);
    if (previous && previous !== canonical) return false;
    releaseByRevision.set(released.revisionGlobalId, canonical);
  }
  return true;
}

function isFileEvidence(
  value: unknown,
): value is ToolingMilestoneFileEvidenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "role",
      "fileRevisionGlobalId",
      "fileOptimisticVersion",
      "frappeContentHash",
      "fileName",
      "mimeType",
      "sizeBytes",
      "sha256",
    ]) &&
    isUuid(value.globalId) &&
    typeof value.role === "string" &&
    fileEvidenceRoles.has(value.role as ToolingMilestoneEvidenceRole) &&
    isUuid(value.fileRevisionGlobalId) &&
    isInteger(value.fileOptimisticVersion, 1, Number.MAX_SAFE_INTEGER) &&
    typeof value.frappeContentHash === "string" &&
    contentHashPattern.test(value.frappeContentHash) &&
    isText(value.fileName, 255) &&
    isText(value.mimeType, 127) &&
    isInteger(value.sizeBytes, 1, Number.MAX_SAFE_INTEGER) &&
    isHash(value.sha256)
  );
}

export function isToolingManufacturingMilestoneObservation(
  value: unknown,
): value is ToolingManufacturingMilestoneObservationViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "planRevisionGlobalId",
      "planRevisionSnapshotHash",
      "milestoneGlobalId",
      "milestoneSnapshotHash",
      "observationVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "progressPercentage",
      "actualStart",
      "actualFinish",
      "risk",
      "note",
      "evidence",
      "reportedByMember",
      "snapshotHash",
    ]) ||
    !isUuid(value.globalId) ||
    !isUuid(value.planRevisionGlobalId) ||
    !isHash(value.planRevisionSnapshotHash) ||
    !isUuid(value.milestoneGlobalId) ||
    !isHash(value.milestoneSnapshotHash) ||
    !isInteger(value.observationVersion, 1, Number.MAX_SAFE_INTEGER) ||
    !isInteger(value.progressPercentage, 0, 100) ||
    (value.actualStart !== null && !isDate(value.actualStart)) ||
    (value.actualFinish !== null && !isDate(value.actualFinish)) ||
    (value.actualFinish !== null && value.actualStart === null) ||
    (typeof value.actualStart === "string" &&
      typeof value.actualFinish === "string" &&
      value.actualFinish < value.actualStart) ||
    (value.risk !== null && !isText(value.risk, 240)) ||
    (value.note !== null && !isText(value.note, 1000)) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 20 ||
    !value.evidence.every(isFileEvidence) ||
    !unique(value.evidence.map((item) => item.globalId)) ||
    !unique(value.evidence.map((item) => item.fileRevisionGlobalId)) ||
    !isToolingProjectMemberResponsibility(value.reportedByMember) ||
    !isHash(value.snapshotHash)
  )
    return false;
  const initial = value.observationVersion === 1;
  return initial
    ? value.predecessorGlobalId === null &&
        value.predecessorSnapshotHash === null
    : isUuid(value.predecessorGlobalId) &&
        isHash(value.predecessorSnapshotHash);
}

export function isToolingDesignReleaseEvidenceCapability(
  value: unknown,
): value is ToolingDesignReleaseEvidenceCapabilityViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["state", "reasonCode", "items"]) ||
    !Array.isArray(value.items) ||
    value.items.length > 50 ||
    !value.items.every(isToolingReleasedDocumentEvidence)
  )
    return false;
  if (value.state === "satisfied")
    return value.reasonCode === null && value.items.length > 0;
  return (
    value.state === "blocked" &&
    (value.reasonCode === "no_design_documents" ||
      value.reasonCode === "release_evidence_incomplete") &&
    value.items.length === 0
  );
}

function isPermissions(
  value: unknown,
): value is ToolingManufacturingPermissionsViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "view",
      "createPlan",
      "observeMilestone",
      "transitionLifecycle",
      "editErpProjection",
    ]) &&
    value.view === true &&
    typeof value.createPlan === "boolean" &&
    typeof value.observeMilestone === "boolean" &&
    value.transitionLifecycle === false &&
    value.editErpProjection === false
  );
}

function isAuthorization(
  value: unknown,
): value is ToolingManufacturingAuthorizationViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "reasonCode"]) &&
    value.state === "unavailable" &&
    value.reasonCode === "tooling_lifecycle_policy_unavailable"
  );
}

function decimalParts(value: string): readonly [bigint, number] {
  const negative = value.startsWith("-");
  const normalized = negative ? value.slice(1) : value;
  const [whole = "0", fraction = ""] = normalized.split(".");
  const integer = BigInt(`${whole}${fraction}` || "0") * (negative ? -1n : 1n);
  return [integer, fraction.length];
}

function decimalEqual(left: string, right: string): boolean {
  const [leftInteger, leftScale] = decimalParts(left);
  const [rightInteger, rightScale] = decimalParts(right);
  const scale = Math.max(leftScale, rightScale);
  return (
    leftInteger * 10n ** BigInt(scale - leftScale) ===
    rightInteger * 10n ** BigInt(scale - rightScale)
  );
}

function decimalSum(values: readonly string[]): string {
  const parts = values.map(decimalParts);
  const scale = Math.max(0, ...parts.map(([, itemScale]) => itemScale));
  const total = parts.reduce(
    (sum, [integer, itemScale]) =>
      sum + integer * 10n ** BigInt(scale - itemScale),
    0n,
  );
  return scale === 0
    ? total.toString()
    : `${total < 0 ? "-" : ""}${(total < 0 ? -total : total)
        .toString()
        .padStart(scale + 1, "0")
        .slice(0, -scale)}.${(total < 0 ? -total : total)
        .toString()
        .padStart(scale + 1, "0")
        .slice(-scale)}`;
}

function isErpProjection(
  value: unknown,
  expectedMasterId: string,
): value is ToolingProcurementCostProjectionViewModel {
  if (!isRecord(value)) return false;
  if (value.state === "unavailable")
    return (
      hasExactKeys(value, [
        "sourceSystem",
        "editableIn",
        "state",
        "reasonCode",
      ]) &&
      value.sourceSystem === "ERPNEXT" &&
      value.editableIn === "ERPNEXT" &&
      value.reasonCode === "erp_projection_unavailable"
    );
  if (
    value.state !== "available" ||
    !hasExactKeys(value, [
      "sourceSystem",
      "editableIn",
      "state",
      "toolingMasterGlobalId",
      "observedAt",
      "targetVersion",
      "supplier",
      "rows",
      "summaries",
    ]) ||
    value.sourceSystem !== "ERPNEXT" ||
    value.editableIn !== "ERPNEXT" ||
    value.toolingMasterGlobalId !== expectedMasterId ||
    !isDateTime(value.observedAt) ||
    !isText(value.targetVersion, 128) ||
    !isRecord(value.supplier) ||
    !hasExactKeys(value.supplier, [
      "sourceObjectId",
      "targetVersion",
      "supplierCode",
      "supplierName",
    ]) ||
    !isText(value.supplier.sourceObjectId, 128) ||
    !isText(value.supplier.targetVersion, 128) ||
    !isText(value.supplier.supplierCode, 128) ||
    !isText(value.supplier.supplierName, 200) ||
    !Array.isArray(value.rows) ||
    value.rows.length < 1 ||
    value.rows.length > 1000 ||
    !Array.isArray(value.summaries) ||
    value.summaries.length < 1 ||
    value.summaries.length > 1000
  )
    return false;
  const rowKeys: string[] = [];
  const grouped = new Map<string, string[]>();
  for (const row of value.rows) {
    if (
      !isRecord(row) ||
      !hasExactKeys(row, [
        "toolingMasterGlobalId",
        "sourceRowId",
        "sourceRowVersion",
        "supplierSourceObjectId",
        "purchaseOrderSourceId",
        "purchaseReceiptSourceId",
        "purchaseInvoiceSourceId",
        "actualCostSourceId",
        "costTypeCode",
        "postingDate",
        "currency",
        "amount",
      ]) ||
      row.toolingMasterGlobalId !== expectedMasterId ||
      !isText(row.sourceRowId, 128) ||
      !isText(row.sourceRowVersion, 128) ||
      !isText(row.supplierSourceObjectId, 128) ||
      !isText(row.purchaseOrderSourceId, 128) ||
      !isText(row.purchaseReceiptSourceId, 128) ||
      !isText(row.purchaseInvoiceSourceId, 128) ||
      !isText(row.actualCostSourceId, 128) ||
      !isText(row.costTypeCode, 128) ||
      row.supplierSourceObjectId !== value.supplier.sourceObjectId ||
      !isDate(row.postingDate) ||
      typeof row.currency !== "string" ||
      !currencyPattern.test(row.currency) ||
      typeof row.amount !== "string" ||
      row.amount.length > 32 ||
      !signedAmountPattern.test(row.amount)
    )
      return false;
    rowKeys.push(`${row.sourceRowId}\u0000${row.sourceRowVersion}`);
    const group = `${row.supplierSourceObjectId}\u0000${row.costTypeCode}\u0000${row.currency}`;
    grouped.set(group, [...(grouped.get(group) ?? []), row.amount]);
  }
  if (!unique(rowKeys)) return false;
  const summaryKeys: string[] = [];
  for (const summary of value.summaries) {
    if (
      !isRecord(summary) ||
      !hasExactKeys(summary, [
        "toolingMasterGlobalId",
        "supplierSourceObjectId",
        "costTypeCode",
        "currency",
        "amount",
      ]) ||
      summary.toolingMasterGlobalId !== expectedMasterId ||
      !isText(summary.supplierSourceObjectId, 128) ||
      !isText(summary.costTypeCode, 128) ||
      typeof summary.currency !== "string" ||
      !currencyPattern.test(summary.currency) ||
      typeof summary.amount !== "string" ||
      summary.amount.length > 32 ||
      !signedAmountPattern.test(summary.amount)
    )
      return false;
    const key = `${summary.supplierSourceObjectId}\u0000${summary.costTypeCode}\u0000${summary.currency}`;
    const amounts = grouped.get(key);
    if (!amounts || !decimalEqual(decimalSum(amounts), summary.amount))
      return false;
    summaryKeys.push(key);
  }
  return (
    unique(summaryKeys) &&
    unique([...grouped.keys()]) &&
    summaryKeys.length === grouped.size
  );
}

function isPlanItem(
  value: unknown,
  expectedMasterId: string,
): value is ToolingManufacturingPlanItemViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["plan", "observations", "designReleaseEvidence"]) ||
    !isToolingManufacturingPlanRevision(value.plan) ||
    value.plan.toolingMasterGlobalId !== expectedMasterId ||
    !Array.isArray(value.observations) ||
    value.observations.length > 1000 ||
    !value.observations.every(isToolingManufacturingMilestoneObservation) ||
    !isToolingDesignReleaseEvidenceCapability(value.designReleaseEvidence)
  )
    return false;
  const plan = value.plan;
  const milestoneById = new Map(
    plan.milestones.map((item) => [item.globalId, item.snapshotHash]),
  );
  if (
    value.observations.some(
      (item) =>
        item.planRevisionGlobalId !== plan.globalId ||
        item.planRevisionSnapshotHash !== plan.snapshotHash ||
        milestoneById.get(item.milestoneGlobalId) !==
          item.milestoneSnapshotHash,
    )
  )
    return false;
  const expectedDesign = plan.designReleaseEvidence.map(
    (item) => item.revisionGlobalId,
  );
  const observedDesign = value.designReleaseEvidence.items.map(
    (item) => item.revisionGlobalId,
  );
  return value.designReleaseEvidence.state === "satisfied"
    ? JSON.stringify(expectedDesign) === JSON.stringify(observedDesign)
    : observedDesign.length === 0;
}

export function isToolingManufacturingPlanCollection(
  value: unknown,
): value is ToolingManufacturingPlanCollectionViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "projectGlobalId",
      "toolingMasterGlobalId",
      "permissions",
      "manufacturingAuthorization",
      "erpProjection",
      "items",
    ]) ||
    !isUuid(value.projectGlobalId) ||
    !isUuid(value.toolingMasterGlobalId) ||
    !isPermissions(value.permissions) ||
    !isAuthorization(value.manufacturingAuthorization) ||
    !isErpProjection(value.erpProjection, value.toolingMasterGlobalId) ||
    !Array.isArray(value.items) ||
    value.items.length > 200
  )
    return false;
  const masterId = value.toolingMasterGlobalId;
  if (!value.items.every((item) => isPlanItem(item, masterId))) return false;
  return unique(value.items.map((item) => item.plan.globalId));
}

export function isToolingManufacturingPlanDetail(
  value: unknown,
): value is ToolingManufacturingPlanDetailViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "projectGlobalId",
      "toolingMasterGlobalId",
      "permissions",
      "manufacturingAuthorization",
      "erpProjection",
      "item",
    ]) &&
    isUuid(value.projectGlobalId) &&
    isUuid(value.toolingMasterGlobalId) &&
    isPermissions(value.permissions) &&
    isAuthorization(value.manufacturingAuthorization) &&
    isErpProjection(value.erpProjection, value.toolingMasterGlobalId) &&
    isPlanItem(value.item, value.toolingMasterGlobalId)
  );
}

export function isCreateToolingManufacturingPlanCommand(
  value: unknown,
): value is CreateToolingManufacturingPlanCommand {
  if (
    !isRecord(value) ||
    !hasRequiredAndAllowedKeys(
      value,
      [
        "toolingRevisionGlobalId",
        "toolingRevisionSnapshotHash",
        "sourcingStrategy",
        "responsibleMember",
        "evidence",
        "designReleaseEvidence",
        "milestones",
        "reason",
      ],
      [
        "planGlobalId",
        "expectedVersion",
        "toolingRevisionGlobalId",
        "toolingRevisionSnapshotHash",
        "sourcingStrategy",
        "responsibleMember",
        "engineeringEstimate",
        "budget",
        "evidence",
        "designReleaseEvidence",
        "milestones",
        "reason",
      ],
    ) ||
    !isUuid(value.toolingRevisionGlobalId) ||
    !isHash(value.toolingRevisionSnapshotHash) ||
    typeof value.sourcingStrategy !== "string" ||
    !sourcingStrategies.has(
      value.sourcingStrategy as ToolingSourcingStrategy,
    ) ||
    !isToolingProjectMemberResponsibility(value.responsibleMember) ||
    (value.engineeringEstimate !== undefined &&
      !isMoney(value.engineeringEstimate)) ||
    (value.budget !== undefined && !isMoney(value.budget)) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 4 ||
    !value.evidence.every(isPlanEvidence) ||
    !unique(value.evidence.map((item) => item.role)) ||
    !Array.isArray(value.designReleaseEvidence) ||
    value.designReleaseEvidence.length < 1 ||
    value.designReleaseEvidence.length > 50 ||
    !value.designReleaseEvidence.every(isToolingReleasedDocumentEvidence) ||
    !unique(value.designReleaseEvidence.map((item) => item.revisionGlobalId)) ||
    !Array.isArray(value.milestones) ||
    !value.milestones.every((item) => isMilestoneBase(item, false)) ||
    !isCoherentMilestoneGraph(value.milestones) ||
    !isText(value.reason, 500)
  )
    return false;
  const successor =
    value.planGlobalId !== undefined || value.expectedVersion !== undefined;
  if (
    successor &&
    (!isUuid(value.planGlobalId) ||
      !isInteger(value.expectedVersion, 1, Number.MAX_SAFE_INTEGER))
  )
    return false;
  return !(
    value.engineeringEstimate &&
    value.budget &&
    value.engineeringEstimate.currency !== value.budget.currency
  );
}

function isCreateFileEvidence(
  value: unknown,
): value is CreateToolingMilestoneFileEvidenceCommand {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "role",
      "fileRevisionGlobalId",
      "fileOptimisticVersion",
      "frappeContentHash",
      "sha256",
    ]) &&
    typeof value.role === "string" &&
    fileEvidenceRoles.has(value.role as ToolingMilestoneEvidenceRole) &&
    isUuid(value.fileRevisionGlobalId) &&
    isInteger(value.fileOptimisticVersion, 1, Number.MAX_SAFE_INTEGER) &&
    typeof value.frappeContentHash === "string" &&
    contentHashPattern.test(value.frappeContentHash) &&
    isHash(value.sha256)
  );
}

export function isCreateToolingManufacturingObservationCommand(
  value: unknown,
): value is CreateToolingManufacturingObservationCommand {
  return (
    isRecord(value) &&
    hasRequiredAndAllowedKeys(
      value,
      [
        "planRevisionSnapshotHash",
        "milestoneSnapshotHash",
        "progressPercentage",
        "evidence",
      ],
      [
        "expectedVersion",
        "planRevisionSnapshotHash",
        "milestoneSnapshotHash",
        "progressPercentage",
        "actualStart",
        "actualFinish",
        "risk",
        "note",
        "evidence",
      ],
    ) &&
    (value.expectedVersion === undefined ||
      isInteger(value.expectedVersion, 1, Number.MAX_SAFE_INTEGER)) &&
    isHash(value.planRevisionSnapshotHash) &&
    isHash(value.milestoneSnapshotHash) &&
    isInteger(value.progressPercentage, 0, 100) &&
    (value.actualStart === undefined || isDate(value.actualStart)) &&
    (value.actualFinish === undefined || isDate(value.actualFinish)) &&
    !(value.actualFinish !== undefined && value.actualStart === undefined) &&
    !(
      typeof value.actualStart === "string" &&
      typeof value.actualFinish === "string" &&
      value.actualFinish < value.actualStart
    ) &&
    (value.risk === undefined || isText(value.risk, 240)) &&
    (value.note === undefined || isText(value.note, 1000)) &&
    Array.isArray(value.evidence) &&
    value.evidence.length <= 20 &&
    value.evidence.every(isCreateFileEvidence) &&
    unique(value.evidence.map((item) => item.fileRevisionGlobalId))
  );
}

export function isToolingManufacturingPlanCommand(
  value: unknown,
): value is ToolingManufacturingPlanCommandViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["plan", "designReleaseEvidence"]) &&
    isToolingManufacturingPlanRevision(value.plan) &&
    isToolingDesignReleaseEvidenceCapability(value.designReleaseEvidence)
  );
}

export function isToolingManufacturingObservationCommand(
  value: unknown,
): value is ToolingManufacturingObservationCommandViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["observation"]) &&
    isToolingManufacturingMilestoneObservation(value.observation)
  );
}
