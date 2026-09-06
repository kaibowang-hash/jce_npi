import {
  isToolingProjectMemberResponsibility,
  type ToolingProjectMemberResponsibilityViewModel,
} from "./tooling-manufacturing-contract";

export const TOOL_ASSET_MOCK_ACKNOWLEDGEMENT =
  "I confirm this only validates a local Mock draft. It does not approve Tooling, contact ERPNext or create an Asset.";

export const toolingAcceptanceCategories = [
  "technical",
  "quality",
  "cycle_capacity",
  "spares_maintenance",
  "documents",
  "warranty_responsibility",
  "cost",
  "safety_interface",
  "asset_location",
] as const;

export type ToolingAcceptanceCategory =
  (typeof toolingAcceptanceCategories)[number];
export type ToolingEvidenceDisposition =
  | "evidence_recorded"
  | "evidence_missing"
  | "not_applicable_asserted";
export type ToolingAcceptanceEvidenceRole =
  | "checklist"
  | "action"
  | "approval_reference"
  | "customer_authorization"
  | "quote"
  | "repair_verification";
export type ToolingAssetActionKind =
  | "move"
  | "loan"
  | "return"
  | "archive"
  | "scrap";
export type ToolingSpareKind = "critical_spare" | "wear_part";

export interface ToolingAcceptanceFileEvidenceInputViewModel {
  role: ToolingAcceptanceEvidenceRole;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: number;
  frappeContentHash: string;
  sha256: string;
}

export interface ToolingAcceptanceChecklistItemInputViewModel {
  category: ToolingAcceptanceCategory;
  requirementKey: string;
  requirementStatement: string;
  disposition: ToolingEvidenceDisposition;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel | null;
  evidence: readonly ToolingAcceptanceFileEvidenceInputViewModel[];
  note: string | null;
}

export interface ToolingAssetActionEvidenceInputViewModel {
  actionKind: ToolingAssetActionKind;
  reason: string;
  approvalReference: string;
  proposedEffectiveDate: string | null;
  evidence: readonly ToolingAcceptanceFileEvidenceInputViewModel[];
}

export interface ToolingSpareRecommendationInputViewModel {
  recommendationKey: string;
  kind: ToolingSpareKind;
  description: string;
  recommendedMinimumQuantity: string;
  unit: string;
  supplierSourceSystem: "ERPNEXT" | null;
  supplierSourceObjectId: string | null;
}

export interface ToolingRepairEvidenceInputViewModel {
  authorizationReference: string;
  quoteReference: string | null;
  quoteCurrency: string | null;
  quoteAmount: string | null;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel;
  downtimeImpactHours: string;
  detail: string;
  customerAuthorizationEvidence: readonly ToolingAcceptanceFileEvidenceInputViewModel[];
  verificationEvidence: readonly ToolingAcceptanceFileEvidenceInputViewModel[];
}

export interface CreateToolingAcceptanceEvidenceRevisionCommand {
  acceptanceGlobalId?: string | undefined;
  expectedVersion?: number | undefined;
  toolingSetGlobalId: string;
  toolingSetSnapshotHash: string;
  setRevisionBindingGlobalId: string;
  setRevisionBindingSnapshotHash: string;
  toolingRevisionGlobalId: string;
  toolingRevisionNumber: number;
  toolingRevisionSnapshotHash: string;
  checklist: readonly ToolingAcceptanceChecklistItemInputViewModel[];
  assetActions: readonly ToolingAssetActionEvidenceInputViewModel[];
  spareRecommendations: readonly ToolingSpareRecommendationInputViewModel[];
  repairs: readonly ToolingRepairEvidenceInputViewModel[];
  reason: string;
}

export interface ToolingAcceptanceFileEvidenceViewModel extends ToolingAcceptanceFileEvidenceInputViewModel {
  globalId: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
}

export interface ToolingAcceptanceChecklistItemViewModel {
  globalId: string;
  category: ToolingAcceptanceCategory;
  requirementKey: string;
  requirementStatement: string;
  disposition: ToolingEvidenceDisposition;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel | null;
  evidence: readonly ToolingAcceptanceFileEvidenceViewModel[];
  note: string | null;
}

export interface ToolingAssetActionEvidenceViewModel {
  globalId: string;
  actionKind: ToolingAssetActionKind;
  reason: string;
  approvalReference: string;
  proposedEffectiveDate: string | null;
  erpExecution: ToolingUnavailableStateViewModel;
  evidence: readonly ToolingAcceptanceFileEvidenceViewModel[];
}

export interface ToolingSpareRecommendationViewModel {
  globalId: string;
  recommendationKey: string;
  kind: ToolingSpareKind;
  description: string;
  recommendedMinimumQuantity: string;
  unit: string;
  supplierReference:
    | { sourceSystem: "ERPNEXT"; sourceObjectId: string }
    | ToolingUnavailableStateViewModel;
  formalItemAndInventory: ToolingUnavailableStateViewModel;
}

export interface ToolingRepairEvidenceViewModel {
  globalId: string;
  authorizationReference: string;
  quoteReference: string | null;
  quote: { currency: string; amount: string } | null;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel;
  downtimeImpactHours: string;
  detail: string;
  customerAuthorizationEvidence: readonly ToolingAcceptanceFileEvidenceViewModel[];
  verificationEvidence: readonly ToolingAcceptanceFileEvidenceViewModel[];
  erpRepairResult: ToolingUnavailableStateViewModel;
}

export interface ToolingAcceptanceCategoryCoverageViewModel {
  category: ToolingAcceptanceCategory;
  itemCount: number;
  recordedCount: number;
  missingCount: number;
  notApplicableCount: number;
}

export interface ToolingUnavailableStateViewModel {
  state: "unavailable";
  reasonCode: string;
}

export interface ToolingAcceptanceEvidenceRevisionViewModel {
  schemaVersion: 1;
  globalId: string;
  acceptanceGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  toolingMasterSnapshotHash: string;
  toolingSetGlobalId: string;
  toolingSetSnapshotHash: string;
  toolingRequirementKind:
    | "new_tool"
    | "customer_owned_intake"
    | "copy_or_additional_set"
    | "modification"
    | "repair"
    | "capacity_need";
  setRevisionBindingGlobalId: string;
  setRevisionBindingSnapshotHash: string;
  toolingRevisionGlobalId: string;
  toolingRevisionNumber: number;
  toolingRevisionSnapshotHash: string;
  acceptanceVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  checklist: readonly ToolingAcceptanceChecklistItemViewModel[];
  assetActions: readonly ToolingAssetActionEvidenceViewModel[];
  spareRecommendations: readonly ToolingSpareRecommendationViewModel[];
  repairs: readonly ToolingRepairEvidenceViewModel[];
  reason: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  versionKeyHash: string;
  snapshotHash: string;
  categoryCoverage: readonly ToolingAcceptanceCategoryCoverageViewModel[];
  businessApproval: ToolingUnavailableStateViewModel;
}

export interface ToolingAcceptanceEvidenceCommandViewModel {
  acceptanceEvidence: ToolingAcceptanceEvidenceRevisionViewModel;
}

export interface ToolAssetRequestInputViewModel {
  schemaVersion: 1;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  toolingMasterTitle: string;
  toolingMasterSnapshotHash: string;
  toolingSetGlobalId: string;
  toolingSetPhysicalSerial: string;
  toolingSetSnapshotHash: string;
  toolingRequirementKind: ToolingAcceptanceEvidenceRevisionViewModel["toolingRequirementKind"];
  setRevisionBindingGlobalId: string;
  setRevisionBindingSnapshotHash: string;
  toolingRevisionGlobalId: string;
  toolingRevisionNumber: number;
  toolingRevisionLabel: string;
  toolingRevisionSnapshotHash: string;
  acceptanceRevisionGlobalId: string;
  acceptanceVersion: number;
  acceptanceSnapshotHash: string;
  ownedFieldsManifest: readonly [
    "tooling_master_title",
    "physical_set_serial",
    "tooling_requirement_kind",
    "source_tooling_revision",
    "acceptance_evidence_reference",
  ];
}

export interface ToolAssetRequestViewModel {
  globalId: string;
  tenantId: string;
  apiVersion: "npi.tooling-asset.v1";
  operation: "create_or_update_tool_asset";
  targetMode: "mock";
  requestState: "draft";
  inputValidationState: "validated_mock";
  businessApprovalState: "unavailable";
  dispatchState: "prohibited";
  targetResultState: "not_requested";
  requestInput: ToolAssetRequestInputViewModel;
  requestInputHash: string;
  payloadHash: string;
  actorUserId: string;
  requestId: string;
  traceId: string;
  idempotencyKeyHash: string;
  createdAt: string;
  formalAssetMapping: {
    sourceSystem: "ERPNEXT";
    editableIn: "ERPNEXT";
    state: "unavailable";
    reasonCode: "erp_asset_mapping_unavailable";
    mappingCardinality: "zero_or_one_per_physical_set";
  };
  targetResult: {
    state: "not_requested";
    reasonCode: "phase_6_dispatch_prohibited";
  };
  snapshotHash: string;
}

export interface ToolAssetRequestCollectionViewModel {
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  items: readonly ToolAssetRequestViewModel[];
}

export interface ToolingAcceptanceAssetContextViewModel {
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  permissions: {
    view: true;
    recordEvidence: boolean;
    prepareMockAssetRequest: boolean;
    approveAcceptance: false;
    dispatchAssetRequest: false;
    editErpProjection: false;
  };
  businessApproval: ToolingUnavailableStateViewModel;
  acceptanceRevisions: readonly ToolingAcceptanceEvidenceRevisionViewModel[];
  assetRequests: readonly ToolAssetRequestViewModel[];
  assetProjection: {
    sourceSystem: "ERPNEXT";
    editableIn: "ERPNEXT";
    state: "unavailable";
    reasonCode: "erp_asset_projection_unavailable";
    mappingCardinality: "zero_or_one_per_physical_set";
  };
}

export interface CreateToolAssetRequestCommand {
  targetMode: "mock";
  acceptanceRevisionGlobalId: string;
  acceptanceVersion: number;
  acceptanceSnapshotHash: string;
  expectedToolingMasterSnapshotHash: string;
  expectedToolingSetSnapshotHash: string;
  expectedBindingSnapshotHash: string;
  expectedToolingRevisionNumber: number;
  expectedToolingRevisionSnapshotHash: string;
  acknowledgement: typeof TOOL_ASSET_MOCK_ACKNOWLEDGEMENT;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const contentHashPattern = /^[a-f0-9]{32,128}$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const decimalPattern = /^[0-9]+(?:[.][0-9]+)?$/u;
const keyPattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$/u;
const categories = new Set<string>(toolingAcceptanceCategories);
const dispositions = new Set<string>([
  "evidence_recorded",
  "evidence_missing",
  "not_applicable_asserted",
]);
const evidenceRoles = new Set<string>([
  "checklist",
  "action",
  "approval_reference",
  "customer_authorization",
  "quote",
  "repair_verification",
]);
const actionKinds = new Set<string>([
  "move",
  "loan",
  "return",
  "archive",
  "scrap",
]);
const requirementKinds = new Set<string>([
  "new_tool",
  "customer_owned_intake",
  "copy_or_additional_set",
  "modification",
  "repair",
  "capacity_need",
]);
const manifest = [
  "tooling_master_title",
  "physical_set_serial",
  "tooling_requirement_kind",
  "source_tooling_revision",
  "acceptance_evidence_reference",
] as const;

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function exact(
  value: Record<string, unknown>,
  required: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return (
    keys.length === required.length && required.every((key) => key in value)
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

function nonnegative(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function date(value: unknown): value is string {
  return (
    typeof value === "string" &&
    datePattern.test(value) &&
    !Number.isNaN(Date.parse(`${value}T00:00:00Z`))
  );
}

function datetime(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 64 &&
    !Number.isNaN(Date.parse(value)) &&
    /(?:Z|[+-]\d{2}:\d{2})$/u.test(value)
  );
}

function nullableUuid(value: unknown): value is string | null {
  return value === null || uuid(value);
}

function nullableHash(value: unknown): value is string | null {
  return value === null || hash(value);
}

function unavailable(
  value: unknown,
  reasonCode?: string,
): value is ToolingUnavailableStateViewModel {
  return (
    record(value) &&
    exact(value, ["state", "reasonCode"]) &&
    value.state === "unavailable" &&
    text(value.reasonCode, 128) &&
    (reasonCode === undefined || value.reasonCode === reasonCode)
  );
}

function fileInput(
  value: unknown,
): value is ToolingAcceptanceFileEvidenceInputViewModel {
  return (
    record(value) &&
    exact(value, [
      "role",
      "fileRevisionGlobalId",
      "fileOptimisticVersion",
      "frappeContentHash",
      "sha256",
    ]) &&
    typeof value.role === "string" &&
    evidenceRoles.has(value.role) &&
    uuid(value.fileRevisionGlobalId) &&
    positive(value.fileOptimisticVersion) &&
    typeof value.frappeContentHash === "string" &&
    contentHashPattern.test(value.frappeContentHash) &&
    hash(value.sha256)
  );
}

function fileEvidence(
  value: unknown,
): value is ToolingAcceptanceFileEvidenceViewModel {
  return (
    record(value) &&
    exact(value, [
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
    uuid(value.globalId) &&
    typeof value.role === "string" &&
    evidenceRoles.has(value.role) &&
    uuid(value.fileRevisionGlobalId) &&
    positive(value.fileOptimisticVersion) &&
    typeof value.frappeContentHash === "string" &&
    contentHashPattern.test(value.frappeContentHash) &&
    text(value.fileName, 255) &&
    text(value.mimeType, 255) &&
    positive(value.sizeBytes) &&
    hash(value.sha256)
  );
}

function checklistInput(
  value: unknown,
): value is ToolingAcceptanceChecklistItemInputViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "category",
      "requirementKey",
      "requirementStatement",
      "disposition",
      "responsibleMember",
      "evidence",
      "note",
    ]) ||
    typeof value.category !== "string" ||
    !categories.has(value.category) ||
    !text(value.requirementKey, 128) ||
    !keyPattern.test(value.requirementKey) ||
    !text(value.requirementStatement, 1000) ||
    typeof value.disposition !== "string" ||
    !dispositions.has(value.disposition) ||
    (value.responsibleMember !== null &&
      !isToolingProjectMemberResponsibility(value.responsibleMember)) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 20 ||
    !value.evidence.every(fileInput) ||
    !(
      value.note === null ||
      (typeof value.note === "string" &&
        value.note.trim().length > 0 &&
        value.note.length <= 2000)
    )
  )
    return false;
  if (value.disposition === "evidence_recorded")
    return (
      value.evidence.length > 0 &&
      value.evidence.every((item) => item.role === "checklist")
    );
  if (value.disposition === "evidence_missing")
    return value.evidence.length === 0;
  return value.evidence.length === 0 && typeof value.note === "string";
}

function checklist(
  value: unknown,
): value is ToolingAcceptanceChecklistItemViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "category",
      "requirementKey",
      "requirementStatement",
      "disposition",
      "responsibleMember",
      "evidence",
      "note",
    ]) &&
    uuid(value.globalId) &&
    typeof value.category === "string" &&
    categories.has(value.category) &&
    text(value.requirementKey, 128) &&
    text(value.requirementStatement, 1000) &&
    typeof value.disposition === "string" &&
    dispositions.has(value.disposition) &&
    (value.responsibleMember === null ||
      isToolingProjectMemberResponsibility(value.responsibleMember)) &&
    Array.isArray(value.evidence) &&
    value.evidence.length <= 20 &&
    value.evidence.every(fileEvidence) &&
    (value.note === null ||
      (typeof value.note === "string" && value.note.length <= 2000))
  );
}

function assetActionInput(
  value: unknown,
): value is ToolingAssetActionEvidenceInputViewModel {
  return (
    record(value) &&
    exact(value, [
      "actionKind",
      "reason",
      "approvalReference",
      "proposedEffectiveDate",
      "evidence",
    ]) &&
    typeof value.actionKind === "string" &&
    actionKinds.has(value.actionKind) &&
    text(value.reason, 2000) &&
    text(value.approvalReference, 500) &&
    (value.proposedEffectiveDate === null ||
      date(value.proposedEffectiveDate)) &&
    Array.isArray(value.evidence) &&
    value.evidence.length > 0 &&
    value.evidence.length <= 20 &&
    value.evidence.every(fileInput) &&
    value.evidence.every(
      (item) => item.role === "action" || item.role === "approval_reference",
    )
  );
}

function assetAction(
  value: unknown,
): value is ToolingAssetActionEvidenceViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "actionKind",
      "reason",
      "approvalReference",
      "proposedEffectiveDate",
      "erpExecution",
      "evidence",
    ]) &&
    uuid(value.globalId) &&
    typeof value.actionKind === "string" &&
    actionKinds.has(value.actionKind) &&
    text(value.reason, 2000) &&
    text(value.approvalReference, 500) &&
    (value.proposedEffectiveDate === null ||
      date(value.proposedEffectiveDate)) &&
    unavailable(value.erpExecution, "erp_asset_action_execution_unavailable") &&
    Array.isArray(value.evidence) &&
    value.evidence.length > 0 &&
    value.evidence.length <= 20 &&
    value.evidence.every(fileEvidence)
  );
}

function spareInput(
  value: unknown,
): value is ToolingSpareRecommendationInputViewModel {
  return (
    record(value) &&
    exact(value, [
      "recommendationKey",
      "kind",
      "description",
      "recommendedMinimumQuantity",
      "unit",
      "supplierSourceSystem",
      "supplierSourceObjectId",
    ]) &&
    text(value.recommendationKey, 128) &&
    keyPattern.test(value.recommendationKey) &&
    (value.kind === "critical_spare" || value.kind === "wear_part") &&
    text(value.description, 1000) &&
    typeof value.recommendedMinimumQuantity === "string" &&
    decimalPattern.test(value.recommendedMinimumQuantity) &&
    text(value.unit, 32) &&
    ((value.supplierSourceSystem === null &&
      value.supplierSourceObjectId === null) ||
      (value.supplierSourceSystem === "ERPNEXT" &&
        text(value.supplierSourceObjectId, 128)))
  );
}

function spare(value: unknown): value is ToolingSpareRecommendationViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "globalId",
      "recommendationKey",
      "kind",
      "description",
      "recommendedMinimumQuantity",
      "unit",
      "supplierReference",
      "formalItemAndInventory",
    ]) ||
    !uuid(value.globalId) ||
    !text(value.recommendationKey, 128) ||
    (value.kind !== "critical_spare" && value.kind !== "wear_part") ||
    !text(value.description, 1000) ||
    typeof value.recommendedMinimumQuantity !== "string" ||
    !decimalPattern.test(value.recommendedMinimumQuantity) ||
    !text(value.unit, 32) ||
    !unavailable(
      value.formalItemAndInventory,
      "erp_spare_inventory_projection_unavailable",
    )
  )
    return false;
  return (
    unavailable(
      value.supplierReference,
      "formal_supplier_projection_unavailable",
    ) ||
    (record(value.supplierReference) &&
      exact(value.supplierReference, ["sourceSystem", "sourceObjectId"]) &&
      value.supplierReference.sourceSystem === "ERPNEXT" &&
      text(value.supplierReference.sourceObjectId, 128))
  );
}

function repairInput(
  value: unknown,
): value is ToolingRepairEvidenceInputViewModel {
  return (
    record(value) &&
    exact(value, [
      "authorizationReference",
      "quoteReference",
      "quoteCurrency",
      "quoteAmount",
      "responsibleMember",
      "downtimeImpactHours",
      "detail",
      "customerAuthorizationEvidence",
      "verificationEvidence",
    ]) &&
    text(value.authorizationReference, 500) &&
    (value.quoteReference === null || text(value.quoteReference, 500)) &&
    ((value.quoteCurrency === null && value.quoteAmount === null) ||
      (typeof value.quoteCurrency === "string" &&
        /^[A-Z]{3}$/u.test(value.quoteCurrency) &&
        typeof value.quoteAmount === "string" &&
        decimalPattern.test(value.quoteAmount))) &&
    isToolingProjectMemberResponsibility(value.responsibleMember) &&
    typeof value.downtimeImpactHours === "string" &&
    decimalPattern.test(value.downtimeImpactHours) &&
    text(value.detail, 4000) &&
    Array.isArray(value.customerAuthorizationEvidence) &&
    value.customerAuthorizationEvidence.length <= 20 &&
    value.customerAuthorizationEvidence.every(fileInput) &&
    value.customerAuthorizationEvidence.every(
      (item) => item.role === "customer_authorization",
    ) &&
    Array.isArray(value.verificationEvidence) &&
    value.verificationEvidence.length <= 20 &&
    value.verificationEvidence.every(fileInput) &&
    value.verificationEvidence.every(
      (item) => item.role === "repair_verification",
    )
  );
}

function repair(value: unknown): value is ToolingRepairEvidenceViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "authorizationReference",
      "quoteReference",
      "quote",
      "responsibleMember",
      "downtimeImpactHours",
      "detail",
      "customerAuthorizationEvidence",
      "verificationEvidence",
      "erpRepairResult",
    ]) &&
    uuid(value.globalId) &&
    text(value.authorizationReference, 500) &&
    (value.quoteReference === null || text(value.quoteReference, 500)) &&
    (value.quote === null ||
      (record(value.quote) &&
        exact(value.quote, ["currency", "amount"]) &&
        typeof value.quote.currency === "string" &&
        /^[A-Z]{3}$/u.test(value.quote.currency) &&
        typeof value.quote.amount === "string" &&
        decimalPattern.test(value.quote.amount))) &&
    isToolingProjectMemberResponsibility(value.responsibleMember) &&
    typeof value.downtimeImpactHours === "string" &&
    decimalPattern.test(value.downtimeImpactHours) &&
    text(value.detail, 4000) &&
    Array.isArray(value.customerAuthorizationEvidence) &&
    value.customerAuthorizationEvidence.length <= 20 &&
    value.customerAuthorizationEvidence.every(fileEvidence) &&
    Array.isArray(value.verificationEvidence) &&
    value.verificationEvidence.length <= 20 &&
    value.verificationEvidence.every(fileEvidence) &&
    unavailable(value.erpRepairResult, "erp_repair_projection_unavailable")
  );
}

function coverage(
  value: unknown,
): value is ToolingAcceptanceCategoryCoverageViewModel {
  return (
    record(value) &&
    exact(value, [
      "category",
      "itemCount",
      "recordedCount",
      "missingCount",
      "notApplicableCount",
    ]) &&
    typeof value.category === "string" &&
    categories.has(value.category) &&
    positive(value.itemCount) &&
    nonnegative(value.recordedCount) &&
    nonnegative(value.missingCount) &&
    nonnegative(value.notApplicableCount) &&
    value.itemCount ===
      value.recordedCount + value.missingCount + value.notApplicableCount
  );
}

export function isCreateToolingAcceptanceEvidenceRevisionCommand(
  value: unknown,
): value is CreateToolingAcceptanceEvidenceRevisionCommand {
  if (!record(value)) return false;
  const required = [
    "toolingSetGlobalId",
    "toolingSetSnapshotHash",
    "setRevisionBindingGlobalId",
    "setRevisionBindingSnapshotHash",
    "toolingRevisionGlobalId",
    "toolingRevisionNumber",
    "toolingRevisionSnapshotHash",
    "checklist",
    "assetActions",
    "spareRecommendations",
    "repairs",
    "reason",
  ];
  const allowed = new Set([
    ...required,
    "acceptanceGlobalId",
    "expectedVersion",
  ]);
  if (
    Object.keys(value).some((key) => !allowed.has(key)) ||
    required.some((key) => !(key in value)) ||
    "acceptanceGlobalId" in value !== "expectedVersion" in value ||
    (value.acceptanceGlobalId !== undefined &&
      !uuid(value.acceptanceGlobalId)) ||
    (value.expectedVersion !== undefined && !positive(value.expectedVersion)) ||
    !uuid(value.toolingSetGlobalId) ||
    !hash(value.toolingSetSnapshotHash) ||
    !uuid(value.setRevisionBindingGlobalId) ||
    !hash(value.setRevisionBindingSnapshotHash) ||
    !uuid(value.toolingRevisionGlobalId) ||
    !positive(value.toolingRevisionNumber) ||
    !hash(value.toolingRevisionSnapshotHash) ||
    !Array.isArray(value.checklist) ||
    value.checklist.length < 9 ||
    value.checklist.length > 200 ||
    !value.checklist.every(checklistInput) ||
    new Set(value.checklist.map((item) => item.category)).size !==
      toolingAcceptanceCategories.length ||
    new Set(value.checklist.map((item) => item.requirementKey)).size !==
      value.checklist.length ||
    !Array.isArray(value.assetActions) ||
    value.assetActions.length > 100 ||
    !value.assetActions.every(assetActionInput) ||
    !Array.isArray(value.spareRecommendations) ||
    value.spareRecommendations.length > 200 ||
    !value.spareRecommendations.every(spareInput) ||
    !Array.isArray(value.repairs) ||
    value.repairs.length > 100 ||
    !value.repairs.every(repairInput) ||
    !text(value.reason, 1000)
  )
    return false;
  return true;
}

export function isToolingAcceptanceEvidenceRevision(
  value: unknown,
): value is ToolingAcceptanceEvidenceRevisionViewModel {
  const keys = [
    "schemaVersion",
    "globalId",
    "acceptanceGlobalId",
    "tenantId",
    "projectGlobalId",
    "toolingMasterGlobalId",
    "toolingMasterSnapshotHash",
    "toolingSetGlobalId",
    "toolingSetSnapshotHash",
    "toolingRequirementKind",
    "setRevisionBindingGlobalId",
    "setRevisionBindingSnapshotHash",
    "toolingRevisionGlobalId",
    "toolingRevisionNumber",
    "toolingRevisionSnapshotHash",
    "acceptanceVersion",
    "predecessorGlobalId",
    "predecessorSnapshotHash",
    "checklist",
    "assetActions",
    "spareRecommendations",
    "repairs",
    "reason",
    "createdByUserId",
    "createdAt",
    "requestId",
    "traceId",
    "versionKeyHash",
    "snapshotHash",
    "categoryCoverage",
    "businessApproval",
  ];
  if (
    !record(value) ||
    !exact(value, keys) ||
    value.schemaVersion !== 1 ||
    !uuid(value.globalId) ||
    !uuid(value.acceptanceGlobalId) ||
    !text(value.tenantId, 128) ||
    !uuid(value.projectGlobalId) ||
    !uuid(value.toolingMasterGlobalId) ||
    !hash(value.toolingMasterSnapshotHash) ||
    !uuid(value.toolingSetGlobalId) ||
    !hash(value.toolingSetSnapshotHash) ||
    typeof value.toolingRequirementKind !== "string" ||
    !requirementKinds.has(value.toolingRequirementKind) ||
    !uuid(value.setRevisionBindingGlobalId) ||
    !hash(value.setRevisionBindingSnapshotHash) ||
    !uuid(value.toolingRevisionGlobalId) ||
    !positive(value.toolingRevisionNumber) ||
    !hash(value.toolingRevisionSnapshotHash) ||
    !positive(value.acceptanceVersion) ||
    !nullableUuid(value.predecessorGlobalId) ||
    !nullableHash(value.predecessorSnapshotHash) ||
    (value.acceptanceVersion === 1) !==
      (value.predecessorGlobalId === null &&
        value.predecessorSnapshotHash === null) ||
    !Array.isArray(value.checklist) ||
    value.checklist.length < 9 ||
    value.checklist.length > 200 ||
    !value.checklist.every(checklist) ||
    !Array.isArray(value.assetActions) ||
    value.assetActions.length > 100 ||
    !value.assetActions.every(assetAction) ||
    !Array.isArray(value.spareRecommendations) ||
    value.spareRecommendations.length > 200 ||
    !value.spareRecommendations.every(spare) ||
    !Array.isArray(value.repairs) ||
    value.repairs.length > 100 ||
    !value.repairs.every(repair) ||
    !text(value.reason, 1000) ||
    !text(value.createdByUserId, 254) ||
    !datetime(value.createdAt) ||
    !uuid(value.requestId) ||
    !text(value.traceId, 128) ||
    !hash(value.versionKeyHash) ||
    !hash(value.snapshotHash) ||
    !Array.isArray(value.categoryCoverage) ||
    value.categoryCoverage.length !== 9 ||
    !value.categoryCoverage.every(coverage) ||
    !unavailable(
      value.businessApproval,
      "tooling_acceptance_policy_unavailable",
    )
  )
    return false;
  return (
    new Set(value.categoryCoverage.map((item) => item.category)).size === 9
  );
}

export function isToolingAcceptanceEvidenceCommand(
  value: unknown,
): value is ToolingAcceptanceEvidenceCommandViewModel {
  return (
    record(value) &&
    exact(value, ["acceptanceEvidence"]) &&
    isToolingAcceptanceEvidenceRevision(value.acceptanceEvidence)
  );
}

function requestInput(value: unknown): value is ToolAssetRequestInputViewModel {
  const keys = [
    "schemaVersion",
    "projectGlobalId",
    "toolingMasterGlobalId",
    "toolingMasterTitle",
    "toolingMasterSnapshotHash",
    "toolingSetGlobalId",
    "toolingSetPhysicalSerial",
    "toolingSetSnapshotHash",
    "toolingRequirementKind",
    "setRevisionBindingGlobalId",
    "setRevisionBindingSnapshotHash",
    "toolingRevisionGlobalId",
    "toolingRevisionNumber",
    "toolingRevisionLabel",
    "toolingRevisionSnapshotHash",
    "acceptanceRevisionGlobalId",
    "acceptanceVersion",
    "acceptanceSnapshotHash",
    "ownedFieldsManifest",
  ];
  return (
    record(value) &&
    exact(value, keys) &&
    value.schemaVersion === 1 &&
    uuid(value.projectGlobalId) &&
    uuid(value.toolingMasterGlobalId) &&
    text(value.toolingMasterTitle, 140) &&
    hash(value.toolingMasterSnapshotHash) &&
    uuid(value.toolingSetGlobalId) &&
    text(value.toolingSetPhysicalSerial, 80) &&
    hash(value.toolingSetSnapshotHash) &&
    typeof value.toolingRequirementKind === "string" &&
    requirementKinds.has(value.toolingRequirementKind) &&
    uuid(value.setRevisionBindingGlobalId) &&
    hash(value.setRevisionBindingSnapshotHash) &&
    uuid(value.toolingRevisionGlobalId) &&
    positive(value.toolingRevisionNumber) &&
    text(value.toolingRevisionLabel, 40) &&
    hash(value.toolingRevisionSnapshotHash) &&
    uuid(value.acceptanceRevisionGlobalId) &&
    positive(value.acceptanceVersion) &&
    hash(value.acceptanceSnapshotHash) &&
    Array.isArray(value.ownedFieldsManifest) &&
    value.ownedFieldsManifest.length === manifest.length &&
    manifest.every(
      (item, index) =>
        (value.ownedFieldsManifest as readonly unknown[])[index] === item,
    )
  );
}

export function isToolAssetRequest(
  value: unknown,
): value is ToolAssetRequestViewModel {
  const keys = [
    "globalId",
    "tenantId",
    "apiVersion",
    "operation",
    "targetMode",
    "requestState",
    "inputValidationState",
    "businessApprovalState",
    "dispatchState",
    "targetResultState",
    "requestInput",
    "requestInputHash",
    "payloadHash",
    "actorUserId",
    "requestId",
    "traceId",
    "idempotencyKeyHash",
    "createdAt",
    "formalAssetMapping",
    "targetResult",
    "snapshotHash",
  ];
  return (
    record(value) &&
    exact(value, keys) &&
    uuid(value.globalId) &&
    text(value.tenantId, 128) &&
    value.apiVersion === "npi.tooling-asset.v1" &&
    value.operation === "create_or_update_tool_asset" &&
    value.targetMode === "mock" &&
    value.requestState === "draft" &&
    value.inputValidationState === "validated_mock" &&
    value.businessApprovalState === "unavailable" &&
    value.dispatchState === "prohibited" &&
    value.targetResultState === "not_requested" &&
    requestInput(value.requestInput) &&
    hash(value.requestInputHash) &&
    hash(value.payloadHash) &&
    text(value.actorUserId, 254) &&
    uuid(value.requestId) &&
    text(value.traceId, 128) &&
    hash(value.idempotencyKeyHash) &&
    datetime(value.createdAt) &&
    record(value.formalAssetMapping) &&
    exact(value.formalAssetMapping, [
      "sourceSystem",
      "editableIn",
      "state",
      "reasonCode",
      "mappingCardinality",
    ]) &&
    value.formalAssetMapping.sourceSystem === "ERPNEXT" &&
    value.formalAssetMapping.editableIn === "ERPNEXT" &&
    value.formalAssetMapping.state === "unavailable" &&
    value.formalAssetMapping.reasonCode === "erp_asset_mapping_unavailable" &&
    value.formalAssetMapping.mappingCardinality ===
      "zero_or_one_per_physical_set" &&
    record(value.targetResult) &&
    exact(value.targetResult, ["state", "reasonCode"]) &&
    value.targetResult.state === "not_requested" &&
    value.targetResult.reasonCode === "phase_6_dispatch_prohibited" &&
    hash(value.snapshotHash)
  );
}

export function isToolAssetRequestCollection(
  value: unknown,
): value is ToolAssetRequestCollectionViewModel {
  return (
    record(value) &&
    exact(value, ["projectGlobalId", "toolingMasterGlobalId", "items"]) &&
    uuid(value.projectGlobalId) &&
    uuid(value.toolingMasterGlobalId) &&
    Array.isArray(value.items) &&
    value.items.length <= 500 &&
    value.items.every(isToolAssetRequest) &&
    value.items.every(
      (item) =>
        item.requestInput.projectGlobalId === value.projectGlobalId &&
        item.requestInput.toolingMasterGlobalId === value.toolingMasterGlobalId,
    )
  );
}

export function isToolingAcceptanceAssetContext(
  value: unknown,
): value is ToolingAcceptanceAssetContextViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "projectGlobalId",
      "toolingMasterGlobalId",
      "permissions",
      "businessApproval",
      "acceptanceRevisions",
      "assetRequests",
      "assetProjection",
    ]) ||
    !uuid(value.projectGlobalId) ||
    !uuid(value.toolingMasterGlobalId) ||
    !record(value.permissions) ||
    !exact(value.permissions, [
      "view",
      "recordEvidence",
      "prepareMockAssetRequest",
      "approveAcceptance",
      "dispatchAssetRequest",
      "editErpProjection",
    ]) ||
    value.permissions.view !== true ||
    typeof value.permissions.recordEvidence !== "boolean" ||
    typeof value.permissions.prepareMockAssetRequest !== "boolean" ||
    value.permissions.approveAcceptance !== false ||
    value.permissions.dispatchAssetRequest !== false ||
    value.permissions.editErpProjection !== false ||
    !unavailable(
      value.businessApproval,
      "tooling_acceptance_policy_unavailable",
    ) ||
    !Array.isArray(value.acceptanceRevisions) ||
    value.acceptanceRevisions.length > 500 ||
    !value.acceptanceRevisions.every(isToolingAcceptanceEvidenceRevision) ||
    !Array.isArray(value.assetRequests) ||
    value.assetRequests.length > 500 ||
    !value.assetRequests.every(isToolAssetRequest) ||
    !record(value.assetProjection) ||
    !exact(value.assetProjection, [
      "sourceSystem",
      "editableIn",
      "state",
      "reasonCode",
      "mappingCardinality",
    ]) ||
    value.assetProjection.sourceSystem !== "ERPNEXT" ||
    value.assetProjection.editableIn !== "ERPNEXT" ||
    value.assetProjection.state !== "unavailable" ||
    value.assetProjection.reasonCode !== "erp_asset_projection_unavailable" ||
    value.assetProjection.mappingCardinality !== "zero_or_one_per_physical_set"
  )
    return false;
  return (
    value.acceptanceRevisions.every(
      (item) =>
        item.projectGlobalId === value.projectGlobalId &&
        item.toolingMasterGlobalId === value.toolingMasterGlobalId,
    ) &&
    value.assetRequests.every(
      (item) =>
        item.requestInput.projectGlobalId === value.projectGlobalId &&
        item.requestInput.toolingMasterGlobalId === value.toolingMasterGlobalId,
    )
  );
}

export function isCreateToolAssetRequestCommand(
  value: unknown,
): value is CreateToolAssetRequestCommand {
  return (
    record(value) &&
    exact(value, [
      "targetMode",
      "acceptanceRevisionGlobalId",
      "acceptanceVersion",
      "acceptanceSnapshotHash",
      "expectedToolingMasterSnapshotHash",
      "expectedToolingSetSnapshotHash",
      "expectedBindingSnapshotHash",
      "expectedToolingRevisionNumber",
      "expectedToolingRevisionSnapshotHash",
      "acknowledgement",
    ]) &&
    value.targetMode === "mock" &&
    uuid(value.acceptanceRevisionGlobalId) &&
    positive(value.acceptanceVersion) &&
    hash(value.acceptanceSnapshotHash) &&
    hash(value.expectedToolingMasterSnapshotHash) &&
    hash(value.expectedToolingSetSnapshotHash) &&
    hash(value.expectedBindingSnapshotHash) &&
    positive(value.expectedToolingRevisionNumber) &&
    hash(value.expectedToolingRevisionSnapshotHash) &&
    value.acknowledgement === TOOL_ASSET_MOCK_ACKNOWLEDGEMENT
  );
}
