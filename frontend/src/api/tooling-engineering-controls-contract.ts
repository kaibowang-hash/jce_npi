import {
  isToolingProjectMemberResponsibility,
  isToolingReleasedDocumentEvidence,
  type ToolingProjectMemberResponsibilityViewModel,
  type ToolingReleasedDocumentEvidenceViewModel,
} from "./tooling-manufacturing-contract";

export type ToolingDefectSeverity = "low" | "medium" | "high" | "critical";
export type ToolingDefectState =
  | "open"
  | "assigned"
  | "in_progress"
  | "ready_for_verification"
  | "closed"
  | "reopened";
export type ToolingDefectActionType =
  | "containment"
  | "corrective"
  | "preventive";
export type ToolingDefectActionState = "planned" | "completed" | "verified";
export type ToolingDefectEvidenceRole =
  | "detection"
  | "analysis"
  | "action"
  | "verification";
export type ToolingDefectDetectionKind =
  | "tooling_revision"
  | "manufacturing_milestone_observation"
  | "tooling_intake"
  | "unavailable_trial_context";
export type ToolingProcessMetricCode =
  | "cycle_time"
  | "part_weight"
  | "runner_weight"
  | "gross_weight_per_cavity"
  | "machine_tonnage"
  | "machine_type";
export type ToolingProcessComparisonState =
  | "not_measured"
  | "within_tolerance"
  | "outside_tolerance"
  | "unavailable";
export type ToolingCapacityProvenanceKind =
  | "customer_standard"
  | "tooling_revision"
  | "tooling_applicability"
  | "tooling_set_selection"
  | "scenario_assumption";

export interface ToolingDefectDetectionContextViewModel {
  kind: ToolingDefectDetectionKind;
  globalId: string | null;
  snapshotHash: string | null;
}

export interface CreateToolingDefectEvidenceCommand {
  role: ToolingDefectEvidenceRole;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: number;
  frappeContentHash: string;
  sha256: string;
}

export interface ToolingDefectEvidenceViewModel extends CreateToolingDefectEvidenceCommand {
  globalId: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
}

export interface CreateToolingDefectActionCommand {
  globalId?: string | undefined;
  actionType: ToolingDefectActionType;
  state: ToolingDefectActionState;
  detail: string;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel;
  dueDate: string;
  evidence: readonly CreateToolingDefectEvidenceCommand[];
}

export interface ToolingDefectActionViewModel {
  globalId: string;
  actionType: ToolingDefectActionType;
  state: ToolingDefectActionState;
  detail: string;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel;
  dueDate: string;
  evidence: readonly ToolingDefectEvidenceViewModel[];
}

export interface CreateToolingDefectRevisionCommand {
  defectGlobalId?: string | undefined;
  expectedVersion?: number | undefined;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  cavityGlobalId: string | null;
  businessCode: string;
  title: string;
  description: string;
  categoryKey: string;
  severity: ToolingDefectSeverity;
  blocking: boolean;
  state: ToolingDefectState;
  detectionContext: ToolingDefectDetectionContextViewModel;
  rootCauseState: "pending" | "recorded";
  rootCause: string | null;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel | null;
  targetRoundLabel: string | null;
  actions: readonly CreateToolingDefectActionCommand[];
  evidence: readonly CreateToolingDefectEvidenceCommand[];
  reason: string;
}

export interface ToolingDefectRevisionViewModel {
  schemaVersion: 1;
  globalId: string;
  defectGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  cavityGlobalId: string | null;
  cavityIdentifier: string | null;
  defectVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  businessCode: string;
  title: string;
  description: string;
  categoryKey: string;
  severity: ToolingDefectSeverity;
  blocking: boolean;
  state: ToolingDefectState;
  detectionContext: ToolingDefectDetectionContextViewModel;
  rootCauseState: "pending" | "recorded";
  rootCause: string | null;
  responsibleMember: ToolingProjectMemberResponsibilityViewModel | null;
  targetRoundLabel: string | null;
  trialReference: {
    state: "unavailable";
    reasonCode: "trial_context_unavailable";
  };
  actions: readonly ToolingDefectActionViewModel[];
  evidence: readonly ToolingDefectEvidenceViewModel[];
  reason: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  versionKeyHash: string;
  snapshotHash: string;
}

export interface ToolingProcessContextInputViewModel {
  kind: "released_document" | "tooling_revision_specification";
  globalId: string;
  snapshotHash: string;
}

export interface ToolingProcessComparisonRuleInputViewModel {
  unit: string;
  minimum: string;
  maximum: string;
}

export interface ToolingProcessMetricInputViewModel {
  code: ToolingProcessMetricCode;
  valueKind: "numeric" | "text";
  numericValue: string | null;
  textValue: string | null;
  unit: string | null;
  comparisonRule: ToolingProcessComparisonRuleInputViewModel | null;
}

export interface CreateToolingProcessProfileRevisionCommand {
  profileGlobalId?: string | undefined;
  expectedVersion?: number | undefined;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  context: ToolingProcessContextInputViewModel;
  effectiveFrom: string;
  metrics: readonly ToolingProcessMetricInputViewModel[];
  reason: string;
}

export interface ToolingProcessComparisonRuleViewModel extends ToolingProcessComparisonRuleInputViewModel {
  globalId: string;
  ruleVersion: number;
  snapshotHash: string;
}

export interface ToolingProcessMetricViewModel {
  globalId: string;
  code: ToolingProcessMetricCode;
  valueKind: "numeric" | "text";
  numericValue: string | null;
  textValue: string | null;
  unit: string | null;
  comparisonRule: ToolingProcessComparisonRuleViewModel | null;
}

export interface ToolingProcessContextEvidenceViewModel {
  kind:
    | "released_document"
    | "tooling_revision_specification"
    | "trial_measurement"
    | "approved_trial";
  globalId: string;
  snapshotHash: string;
  releasedDocument: ToolingReleasedDocumentEvidenceViewModel | null;
  approvalEventGlobalId: string | null;
  approvalEventHash: string | null;
}

export interface ToolingProcessProfileRevisionViewModel {
  schemaVersion: 1;
  globalId: string;
  profileGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  layer: "customer_standard" | "trial_actual" | "approved_baseline";
  profileVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  context: ToolingProcessContextEvidenceViewModel;
  effectiveFrom: string;
  metrics: readonly ToolingProcessMetricViewModel[];
  reason: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  versionKeyHash: string;
  snapshotHash: string;
}

export interface ToolingProcessComparisonViewModel {
  state: ToolingProcessComparisonState;
  referenceLayer: "customer_standard" | "approved_baseline";
  metricCode: ToolingProcessMetricCode;
  unit: string | null;
  referenceValue: string | null;
  actualValue: string | null;
  delta: string | null;
  percentDelta: string | null;
  ruleGlobalId: string | null;
  ruleVersion: number | null;
  ruleSnapshotHash: string | null;
  visualSemantics: {
    state: "unavailable";
    reasonCode: "variance_exception_color_policy_unavailable";
  };
}

export interface ToolingCapacityInputProvenanceViewModel {
  kind: ToolingCapacityProvenanceKind;
  globalId: string | null;
  snapshotHash: string;
}

export interface ToolingCapacityLineInputCommand {
  partRevisionGlobalId: string;
  partRevisionSnapshotHash: string;
  applicabilityGlobalId: string;
  applicabilitySnapshotHash: string;
  availableHoursPerDay: string;
  workingDaysPerMonth: number;
  oeeRatio: string;
  yieldRatio: string;
  cycleSeconds: string;
  cavityCount: number;
  usagePerAssembly: string;
  effectiveSetCount: number;
  selectedToolingSetGlobalIds: readonly string[];
  cycleProvenance: ToolingCapacityInputProvenanceViewModel;
  cavityProvenance: ToolingCapacityInputProvenanceViewModel;
  usageProvenance: ToolingCapacityInputProvenanceViewModel;
  setProvenance: ToolingCapacityInputProvenanceViewModel;
}

export interface ToolingCapacityLineInputViewModel extends ToolingCapacityLineInputCommand {
  globalId: string;
}

export interface ToolingCapacityLineResultViewModel {
  globalId: string;
  partsPerDay: string;
  partsPerMonth: string;
  assemblyUnitsPerDay: string;
  assemblyUnitsPerMonth: string;
}

export interface ToolingCapacityScenarioResultViewModel {
  formulaVersion: "capacity.v1";
  roundingRule: "decimal-6-half-even";
  lineResults: readonly ToolingCapacityLineResultViewModel[];
  scenarioAssemblyUnitsPerMonth: string;
  bottleneckLineGlobalIds: readonly string[];
  gap: string;
}

export interface CreateToolingCapacityScenarioRevisionCommand {
  scenarioGlobalId?: string | undefined;
  expectedVersion?: number | undefined;
  title: string;
  effectiveFrom: string;
  targetMonthlyAssemblyUnits: string;
  lines: readonly ToolingCapacityLineInputCommand[];
  reason: string;
}

export interface ToolingCapacityScenarioRevisionViewModel {
  schemaVersion: 1;
  globalId: string;
  scenarioGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  scenarioVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  title: string;
  effectiveFrom: string;
  targetMonthlyAssemblyUnits: string;
  formulaVersion: "capacity.v1";
  roundingRule: "decimal-6-half-even";
  lines: readonly ToolingCapacityLineInputViewModel[];
  result: ToolingCapacityScenarioResultViewModel;
  reason: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  versionKeyHash: string;
  snapshotHash: string;
}

export interface ToolingEngineeringControlsPermissionsViewModel {
  view: true;
  reviseDefect: boolean;
  createCustomerStandard: boolean;
  createCapacityScenario: boolean;
  createTrialActual: false;
  approveProcessBaseline: false;
  editHealth: false;
  transitionGate: false;
  transitionToolingLifecycle: false;
}

export interface ToolingEngineeringControlsViewModel {
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  permissions: ToolingEngineeringControlsPermissionsViewModel;
  defectRevisions: readonly ToolingDefectRevisionViewModel[];
  process: {
    customerStandardRevisions: readonly ToolingProcessProfileRevisionViewModel[];
    trialActual: {
      state: "not_measured";
      reasonCode: "trial_context_unavailable";
    };
    approvedBaseline: {
      state: "unavailable";
      reasonCode: "approved_trial_evidence_unavailable";
    };
    comparisons: readonly ToolingProcessComparisonViewModel[];
  };
  capacityScenarioRevisions: readonly ToolingCapacityScenarioRevisionViewModel[];
  health: {
    sourceSystem: "ERPNEXT";
    editableIn: "ERPNEXT";
    state: "unavailable";
    shotCount: ToolingEngineeringUnavailableFieldViewModel;
    calibration: ToolingEngineeringUnavailableFieldViewModel;
    maintenance: ToolingEngineeringUnavailableFieldViewModel;
    healthScore: ToolingEngineeringUnavailableFieldViewModel;
  };
}

export interface ToolingEngineeringUnavailableFieldViewModel {
  state: "unavailable";
  reasonCode:
    | "erp_shot_count_unavailable"
    | "shot_count_calibration_policy_unavailable"
    | "erp_maintenance_projection_unavailable"
    | "tooling_health_policy_unavailable";
}

export interface ToolingDefectRevisionCommandViewModel {
  defect: ToolingDefectRevisionViewModel;
}

export interface ToolingProcessProfileRevisionCommandViewModel {
  profile: ToolingProcessProfileRevisionViewModel;
}

export interface ToolingCapacityScenarioRevisionCommandViewModel {
  scenario: ToolingCapacityScenarioRevisionViewModel;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const contentHashPattern = /^[a-f0-9]{32,128}$/u;
const decimalPattern = /^-?[0-9]+(?:[.][0-9]+)?$/u;
const unsignedDecimalPattern = /^[0-9]+(?:[.][0-9]+)?$/u;
const resultPattern = /^[0-9]+[.][0-9]{6}$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const defectStates = new Set<ToolingDefectState>([
  "open",
  "assigned",
  "in_progress",
  "ready_for_verification",
  "closed",
  "reopened",
]);
const severities = new Set<ToolingDefectSeverity>([
  "low",
  "medium",
  "high",
  "critical",
]);
const actionTypes = new Set<ToolingDefectActionType>([
  "containment",
  "corrective",
  "preventive",
]);
const actionStates = new Set<ToolingDefectActionState>([
  "planned",
  "completed",
  "verified",
]);
const evidenceRoles = new Set<ToolingDefectEvidenceRole>([
  "detection",
  "analysis",
  "action",
  "verification",
]);
const detectionKinds = new Set<ToolingDefectDetectionKind>([
  "tooling_revision",
  "manufacturing_milestone_observation",
  "tooling_intake",
  "unavailable_trial_context",
]);
const metricCodes = new Set<ToolingProcessMetricCode>([
  "cycle_time",
  "part_weight",
  "runner_weight",
  "gross_weight_per_cavity",
  "machine_tonnage",
  "machine_type",
]);
const provenanceKinds = new Set<ToolingCapacityProvenanceKind>([
  "customer_standard",
  "tooling_revision",
  "tooling_applicability",
  "tooling_set_selection",
  "scenario_assumption",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function property(value: unknown, key: string): unknown {
  return isRecord(value) ? value[key] : undefined;
}

function exact(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  const observed = Object.keys(value);
  return observed.length === keys.length && keys.every((key) => key in value);
}

function allowed(
  value: Record<string, unknown>,
  required: readonly string[],
  accepted: readonly string[],
): boolean {
  const keys = new Set(accepted);
  return (
    required.every((key) => key in value) &&
    Object.keys(value).every((key) => keys.has(key))
  );
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function hash(value: unknown): value is string {
  return typeof value === "string" && hashPattern.test(value);
}

function text(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= maximum
  );
}

function integer(
  value: unknown,
  minimum = 1,
  maximum = Number.MAX_SAFE_INTEGER,
) {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function date(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value)
  );
}

function dateTime(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 64) return false;
  const parsed = new Date(value);
  return (
    !Number.isNaN(parsed.valueOf()) && /(?:Z|[+-]\d{2}:\d{2})$/u.test(value)
  );
}

function nullable<T>(
  value: unknown,
  predicate: (item: unknown) => item is T,
): value is T | null {
  return value === null || predicate(value);
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

function isDetectionContext(
  value: unknown,
): value is ToolingDefectDetectionContextViewModel {
  if (
    !isRecord(value) ||
    !exact(value, ["kind", "globalId", "snapshotHash"]) ||
    typeof value.kind !== "string" ||
    !detectionKinds.has(value.kind as ToolingDefectDetectionKind)
  )
    return false;
  return value.kind === "unavailable_trial_context"
    ? value.globalId === null && value.snapshotHash === null
    : uuid(value.globalId) && hash(value.snapshotHash);
}

function isDefectEvidenceInput(
  value: unknown,
  response: boolean,
): value is ToolingDefectEvidenceViewModel {
  if (!isRecord(value)) return false;
  const inputKeys = [
    "role",
    "fileRevisionGlobalId",
    "fileOptimisticVersion",
    "frappeContentHash",
    "sha256",
  ];
  const responseKeys = [
    "globalId",
    ...inputKeys,
    "fileName",
    "mimeType",
    "sizeBytes",
  ];
  return (
    exact(value, response ? responseKeys : inputKeys) &&
    (!response ||
      (uuid(value.globalId) &&
        text(value.fileName, 255) &&
        text(value.mimeType, 255) &&
        integer(value.sizeBytes))) &&
    typeof value.role === "string" &&
    evidenceRoles.has(value.role as ToolingDefectEvidenceRole) &&
    uuid(value.fileRevisionGlobalId) &&
    integer(value.fileOptimisticVersion) &&
    typeof value.frappeContentHash === "string" &&
    contentHashPattern.test(value.frappeContentHash) &&
    hash(value.sha256)
  );
}

function isDefectActionInput(
  value: unknown,
  response: boolean,
): value is ToolingDefectActionViewModel {
  if (!isRecord(value)) return false;
  const required = [
    "actionType",
    "state",
    "detail",
    "responsibleMember",
    "dueDate",
    "evidence",
  ];
  if (
    !(response
      ? exact(value, ["globalId", ...required])
      : allowed(value, required, ["globalId", ...required])) ||
    ("globalId" in value && !uuid(value.globalId)) ||
    typeof value.actionType !== "string" ||
    !actionTypes.has(value.actionType as ToolingDefectActionType) ||
    typeof value.state !== "string" ||
    !actionStates.has(value.state as ToolingDefectActionState) ||
    !text(value.detail, 2000) ||
    !isToolingProjectMemberResponsibility(value.responsibleMember) ||
    !date(value.dueDate) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 20
  )
    return false;
  return value.evidence.every((item) => isDefectEvidenceInput(item, response));
}

export function isCreateToolingDefectRevisionCommand(
  value: unknown,
): value is CreateToolingDefectRevisionCommand {
  if (!isRecord(value)) return false;
  const required = [
    "toolingRevisionGlobalId",
    "toolingRevisionSnapshotHash",
    "cavityGlobalId",
    "businessCode",
    "title",
    "description",
    "categoryKey",
    "severity",
    "blocking",
    "state",
    "detectionContext",
    "rootCauseState",
    "rootCause",
    "responsibleMember",
    "targetRoundLabel",
    "actions",
    "evidence",
    "reason",
  ];
  if (
    !allowed(value, required, [
      "defectGlobalId",
      "expectedVersion",
      ...required,
    ]) ||
    ("defectGlobalId" in value && !uuid(value.defectGlobalId)) ||
    ("expectedVersion" in value && !integer(value.expectedVersion)) ||
    !uuid(value.toolingRevisionGlobalId) ||
    !hash(value.toolingRevisionSnapshotHash) ||
    !nullable(value.cavityGlobalId, uuid) ||
    !text(value.businessCode, 64) ||
    !text(value.title, 255) ||
    !text(value.description, 4000) ||
    !text(value.categoryKey, 128) ||
    typeof value.severity !== "string" ||
    !severities.has(value.severity as ToolingDefectSeverity) ||
    typeof value.blocking !== "boolean" ||
    typeof value.state !== "string" ||
    !defectStates.has(value.state as ToolingDefectState) ||
    !isDetectionContext(value.detectionContext) ||
    (value.rootCauseState !== "pending" &&
      value.rootCauseState !== "recorded") ||
    !nullable(value.rootCause, (item): item is string => text(item, 4000)) ||
    (value.rootCauseState === "pending" && value.rootCause !== null) ||
    (value.rootCauseState === "recorded" && !text(value.rootCause, 4000)) ||
    !nullable(value.responsibleMember, isToolingProjectMemberResponsibility) ||
    !nullable(value.targetRoundLabel, (item): item is string =>
      text(item, 64),
    ) ||
    !Array.isArray(value.actions) ||
    value.actions.length > 100 ||
    !value.actions.every((item) => isDefectActionInput(item, false)) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 100 ||
    !value.evidence.every((item) => isDefectEvidenceInput(item, false)) ||
    !text(value.reason, 1000)
  )
    return false;
  return (
    "defectGlobalId" in value === "expectedVersion" in value &&
    (value.state === "open" || value.responsibleMember !== null)
  );
}

function isDefectRevision(
  value: unknown,
): value is ToolingDefectRevisionViewModel {
  if (
    !isRecord(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "defectGlobalId",
      "tenantId",
      "projectGlobalId",
      "toolingMasterGlobalId",
      "toolingRevisionGlobalId",
      "toolingRevisionSnapshotHash",
      "cavityGlobalId",
      "cavityIdentifier",
      "defectVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "businessCode",
      "title",
      "description",
      "categoryKey",
      "severity",
      "blocking",
      "state",
      "detectionContext",
      "rootCauseState",
      "rootCause",
      "responsibleMember",
      "targetRoundLabel",
      "trialReference",
      "actions",
      "evidence",
      "reason",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "versionKeyHash",
      "snapshotHash",
    ]) ||
    value.schemaVersion !== 1 ||
    !uuid(value.globalId) ||
    !uuid(value.defectGlobalId) ||
    !text(value.tenantId, 128) ||
    !uuid(value.projectGlobalId) ||
    !uuid(value.toolingMasterGlobalId) ||
    !uuid(value.toolingRevisionGlobalId) ||
    !hash(value.toolingRevisionSnapshotHash) ||
    !nullable(value.cavityGlobalId, uuid) ||
    !nullable(value.cavityIdentifier, (item): item is string =>
      text(item, 128),
    ) ||
    !integer(value.defectVersion) ||
    !nullable(value.predecessorGlobalId, uuid) ||
    !nullable(value.predecessorSnapshotHash, hash) ||
    !text(value.businessCode, 64) ||
    !text(value.title, 255) ||
    !text(value.description, 4000) ||
    !text(value.categoryKey, 128) ||
    typeof value.severity !== "string" ||
    !severities.has(value.severity as ToolingDefectSeverity) ||
    typeof value.blocking !== "boolean" ||
    typeof value.state !== "string" ||
    !defectStates.has(value.state as ToolingDefectState) ||
    !isDetectionContext(value.detectionContext) ||
    (value.rootCauseState !== "pending" &&
      value.rootCauseState !== "recorded") ||
    !nullable(value.rootCause, (item): item is string => text(item, 4000)) ||
    !nullable(value.responsibleMember, isToolingProjectMemberResponsibility) ||
    !nullable(value.targetRoundLabel, (item): item is string =>
      text(item, 64),
    ) ||
    !isRecord(value.trialReference) ||
    !exact(value.trialReference, ["state", "reasonCode"]) ||
    value.trialReference.state !== "unavailable" ||
    value.trialReference.reasonCode !== "trial_context_unavailable" ||
    !Array.isArray(value.actions) ||
    value.actions.length > 100 ||
    !value.actions.every((item) => isDefectActionInput(item, true)) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 100 ||
    !value.evidence.every((item) => isDefectEvidenceInput(item, true)) ||
    !text(value.reason, 1000) ||
    !text(value.createdByUserId, 254) ||
    !dateTime(value.createdAt) ||
    !uuid(value.requestId) ||
    !text(value.traceId, 128) ||
    !hash(value.versionKeyHash) ||
    !hash(value.snapshotHash)
  )
    return false;
  return (
    (value.defectVersion === 1) ===
      (value.predecessorGlobalId === null &&
        value.predecessorSnapshotHash === null) &&
    (value.cavityGlobalId === null) === (value.cavityIdentifier === null) &&
    (value.rootCauseState === "recorded") === (value.rootCause !== null)
  );
}

function isProcessContextInput(value: unknown, response: boolean): boolean {
  if (!isRecord(value)) return false;
  if (!response)
    return (
      exact(value, ["kind", "globalId", "snapshotHash"]) &&
      (value.kind === "released_document" ||
        value.kind === "tooling_revision_specification") &&
      uuid(value.globalId) &&
      hash(value.snapshotHash)
    );
  return (
    exact(value, [
      "kind",
      "globalId",
      "snapshotHash",
      "releasedDocument",
      "approvalEventGlobalId",
      "approvalEventHash",
    ]) &&
    [
      "released_document",
      "tooling_revision_specification",
      "trial_measurement",
      "approved_trial",
    ].includes(String(value.kind)) &&
    uuid(value.globalId) &&
    hash(value.snapshotHash) &&
    nullable(value.releasedDocument, isToolingReleasedDocumentEvidence) &&
    nullable(value.approvalEventGlobalId, uuid) &&
    nullable(value.approvalEventHash, hash)
  );
}

function isComparisonRule(value: unknown, response: boolean): boolean {
  if (!isRecord(value)) return false;
  const input = ["unit", "minimum", "maximum"];
  return (
    exact(
      value,
      response ? ["globalId", "ruleVersion", ...input, "snapshotHash"] : input,
    ) &&
    (!response ||
      (uuid(value.globalId) &&
        integer(value.ruleVersion) &&
        hash(value.snapshotHash))) &&
    text(value.unit, 32) &&
    typeof value.minimum === "string" &&
    decimalPattern.test(value.minimum) &&
    typeof value.maximum === "string" &&
    decimalPattern.test(value.maximum) &&
    Number(value.minimum) <= Number(value.maximum)
  );
}

function isMetric(value: unknown, response: boolean): boolean {
  if (!isRecord(value)) return false;
  const input = [
    "code",
    "valueKind",
    "numericValue",
    "textValue",
    "unit",
    "comparisonRule",
  ];
  if (
    !exact(value, response ? ["globalId", ...input] : input) ||
    (response && !uuid(value.globalId)) ||
    typeof value.code !== "string" ||
    !metricCodes.has(value.code as ToolingProcessMetricCode) ||
    (value.valueKind !== "numeric" && value.valueKind !== "text") ||
    !nullable(value.unit, (item): item is string => text(item, 32)) ||
    !nullable(value.comparisonRule, (item): item is Record<string, unknown> =>
      isComparisonRule(item, response),
    )
  )
    return false;
  return value.valueKind === "numeric"
    ? typeof value.numericValue === "string" &&
        decimalPattern.test(value.numericValue) &&
        value.textValue === null &&
        text(value.unit, 32)
    : value.numericValue === null &&
        text(value.textValue, 255) &&
        value.unit === null &&
        value.comparisonRule === null;
}

export function isCreateToolingProcessProfileRevisionCommand(
  value: unknown,
): value is CreateToolingProcessProfileRevisionCommand {
  if (!isRecord(value)) return false;
  const required = [
    "toolingRevisionGlobalId",
    "toolingRevisionSnapshotHash",
    "context",
    "effectiveFrom",
    "metrics",
    "reason",
  ];
  return (
    allowed(value, required, [
      "profileGlobalId",
      "expectedVersion",
      ...required,
    ]) &&
    "profileGlobalId" in value === "expectedVersion" in value &&
    (!("profileGlobalId" in value) || uuid(value.profileGlobalId)) &&
    (!("expectedVersion" in value) || integer(value.expectedVersion)) &&
    uuid(value.toolingRevisionGlobalId) &&
    hash(value.toolingRevisionSnapshotHash) &&
    isProcessContextInput(value.context, false) &&
    date(value.effectiveFrom) &&
    Array.isArray(value.metrics) &&
    value.metrics.length >= 1 &&
    value.metrics.length <= 32 &&
    value.metrics.every((item) => isMetric(item, false)) &&
    unique(value.metrics.map((item) => String(property(item, "code")))) &&
    text(value.reason, 1000)
  );
}

function isProcessProfile(
  value: unknown,
): value is ToolingProcessProfileRevisionViewModel {
  if (
    !isRecord(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "profileGlobalId",
      "tenantId",
      "projectGlobalId",
      "toolingMasterGlobalId",
      "toolingRevisionGlobalId",
      "toolingRevisionSnapshotHash",
      "layer",
      "profileVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "context",
      "effectiveFrom",
      "metrics",
      "reason",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "versionKeyHash",
      "snapshotHash",
    ]) ||
    value.schemaVersion !== 1 ||
    !uuid(value.globalId) ||
    !uuid(value.profileGlobalId) ||
    !text(value.tenantId, 128) ||
    !uuid(value.projectGlobalId) ||
    !uuid(value.toolingMasterGlobalId) ||
    !uuid(value.toolingRevisionGlobalId) ||
    !hash(value.toolingRevisionSnapshotHash) ||
    !["customer_standard", "trial_actual", "approved_baseline"].includes(
      String(value.layer),
    ) ||
    !integer(value.profileVersion) ||
    !nullable(value.predecessorGlobalId, uuid) ||
    !nullable(value.predecessorSnapshotHash, hash) ||
    !isProcessContextInput(value.context, true) ||
    !date(value.effectiveFrom) ||
    !Array.isArray(value.metrics) ||
    value.metrics.length < 1 ||
    value.metrics.length > 32 ||
    !value.metrics.every((item) => isMetric(item, true)) ||
    !unique(value.metrics.map((item) => String(property(item, "code")))) ||
    !text(value.reason, 1000) ||
    !text(value.createdByUserId, 254) ||
    !dateTime(value.createdAt) ||
    !uuid(value.requestId) ||
    !text(value.traceId, 128) ||
    !hash(value.versionKeyHash) ||
    !hash(value.snapshotHash)
  )
    return false;
  return (
    (value.profileVersion === 1) ===
    (value.predecessorGlobalId === null &&
      value.predecessorSnapshotHash === null)
  );
}

function isComparison(
  value: unknown,
): value is ToolingProcessComparisonViewModel {
  if (!isRecord(value)) return false;
  const nullableDecimal = (item: unknown): item is string =>
    typeof item === "string" && decimalPattern.test(item);
  return (
    exact(value, [
      "state",
      "referenceLayer",
      "metricCode",
      "unit",
      "referenceValue",
      "actualValue",
      "delta",
      "percentDelta",
      "ruleGlobalId",
      "ruleVersion",
      "ruleSnapshotHash",
      "visualSemantics",
    ]) &&
    [
      "not_measured",
      "within_tolerance",
      "outside_tolerance",
      "unavailable",
    ].includes(String(value.state)) &&
    (value.referenceLayer === "customer_standard" ||
      value.referenceLayer === "approved_baseline") &&
    typeof value.metricCode === "string" &&
    metricCodes.has(value.metricCode as ToolingProcessMetricCode) &&
    nullable(value.unit, (item): item is string => text(item, 32)) &&
    nullable(value.referenceValue, (item): item is string => text(item, 255)) &&
    nullable(value.actualValue, (item): item is string => text(item, 255)) &&
    nullable(value.delta, nullableDecimal) &&
    nullable(value.percentDelta, nullableDecimal) &&
    nullable(value.ruleGlobalId, uuid) &&
    (value.ruleVersion === null || integer(value.ruleVersion)) &&
    nullable(value.ruleSnapshotHash, hash) &&
    isRecord(value.visualSemantics) &&
    exact(value.visualSemantics, ["state", "reasonCode"]) &&
    value.visualSemantics.state === "unavailable" &&
    value.visualSemantics.reasonCode ===
      "variance_exception_color_policy_unavailable"
  );
}

function isProvenance(
  value: unknown,
): value is ToolingCapacityInputProvenanceViewModel {
  return (
    isRecord(value) &&
    exact(value, ["kind", "globalId", "snapshotHash"]) &&
    typeof value.kind === "string" &&
    provenanceKinds.has(value.kind as ToolingCapacityProvenanceKind) &&
    nullable(value.globalId, uuid) &&
    hash(value.snapshotHash)
  );
}

function isCapacityLine(value: unknown, response: boolean): boolean {
  if (!isRecord(value)) return false;
  const input = [
    "partRevisionGlobalId",
    "partRevisionSnapshotHash",
    "applicabilityGlobalId",
    "applicabilitySnapshotHash",
    "availableHoursPerDay",
    "workingDaysPerMonth",
    "oeeRatio",
    "yieldRatio",
    "cycleSeconds",
    "cavityCount",
    "usagePerAssembly",
    "effectiveSetCount",
    "selectedToolingSetGlobalIds",
    "cycleProvenance",
    "cavityProvenance",
    "usageProvenance",
    "setProvenance",
  ];
  return (
    exact(value, response ? ["globalId", ...input] : input) &&
    (!response || uuid(value.globalId)) &&
    uuid(value.partRevisionGlobalId) &&
    hash(value.partRevisionSnapshotHash) &&
    uuid(value.applicabilityGlobalId) &&
    hash(value.applicabilitySnapshotHash) &&
    typeof value.availableHoursPerDay === "string" &&
    unsignedDecimalPattern.test(value.availableHoursPerDay) &&
    Number(value.availableHoursPerDay) > 0 &&
    integer(value.workingDaysPerMonth, 1, 31) &&
    typeof value.oeeRatio === "string" &&
    unsignedDecimalPattern.test(value.oeeRatio) &&
    Number(value.oeeRatio) >= 0 &&
    Number(value.oeeRatio) <= 1 &&
    typeof value.yieldRatio === "string" &&
    unsignedDecimalPattern.test(value.yieldRatio) &&
    Number(value.yieldRatio) >= 0 &&
    Number(value.yieldRatio) <= 1 &&
    typeof value.cycleSeconds === "string" &&
    unsignedDecimalPattern.test(value.cycleSeconds) &&
    Number(value.cycleSeconds) > 0 &&
    integer(value.cavityCount) &&
    typeof value.usagePerAssembly === "string" &&
    unsignedDecimalPattern.test(value.usagePerAssembly) &&
    Number(value.usagePerAssembly) > 0 &&
    integer(value.effectiveSetCount, 0) &&
    Array.isArray(value.selectedToolingSetGlobalIds) &&
    value.selectedToolingSetGlobalIds.length <= 100 &&
    value.selectedToolingSetGlobalIds.every(uuid) &&
    unique(value.selectedToolingSetGlobalIds) &&
    value.selectedToolingSetGlobalIds.length === value.effectiveSetCount &&
    isProvenance(value.cycleProvenance) &&
    isProvenance(value.cavityProvenance) &&
    isProvenance(value.usageProvenance) &&
    isProvenance(value.setProvenance)
  );
}

export function isCreateToolingCapacityScenarioRevisionCommand(
  value: unknown,
): value is CreateToolingCapacityScenarioRevisionCommand {
  if (!isRecord(value)) return false;
  const required = [
    "title",
    "effectiveFrom",
    "targetMonthlyAssemblyUnits",
    "lines",
    "reason",
  ];
  return (
    allowed(value, required, [
      "scenarioGlobalId",
      "expectedVersion",
      ...required,
    ]) &&
    "scenarioGlobalId" in value === "expectedVersion" in value &&
    (!("scenarioGlobalId" in value) || uuid(value.scenarioGlobalId)) &&
    (!("expectedVersion" in value) || integer(value.expectedVersion)) &&
    text(value.title, 255) &&
    date(value.effectiveFrom) &&
    typeof value.targetMonthlyAssemblyUnits === "string" &&
    unsignedDecimalPattern.test(value.targetMonthlyAssemblyUnits) &&
    Array.isArray(value.lines) &&
    value.lines.length >= 1 &&
    value.lines.length <= 100 &&
    value.lines.every((item) => isCapacityLine(item, false)) &&
    unique(
      value.lines.map((item) =>
        String(property(item, "applicabilityGlobalId")),
      ),
    ) &&
    text(value.reason, 1000)
  );
}

function isCapacityResult(
  value: unknown,
): value is ToolingCapacityScenarioResultViewModel {
  if (
    !isRecord(value) ||
    !exact(value, [
      "formulaVersion",
      "roundingRule",
      "lineResults",
      "scenarioAssemblyUnitsPerMonth",
      "bottleneckLineGlobalIds",
      "gap",
    ]) ||
    value.formulaVersion !== "capacity.v1" ||
    value.roundingRule !== "decimal-6-half-even" ||
    !Array.isArray(value.lineResults) ||
    value.lineResults.length < 1 ||
    value.lineResults.length > 100 ||
    !value.lineResults.every(
      (item) =>
        isRecord(item) &&
        exact(item, [
          "globalId",
          "partsPerDay",
          "partsPerMonth",
          "assemblyUnitsPerDay",
          "assemblyUnitsPerMonth",
        ]) &&
        uuid(item.globalId) &&
        [
          item.partsPerDay,
          item.partsPerMonth,
          item.assemblyUnitsPerDay,
          item.assemblyUnitsPerMonth,
        ].every(
          (number) => typeof number === "string" && resultPattern.test(number),
        ),
    ) ||
    typeof value.scenarioAssemblyUnitsPerMonth !== "string" ||
    !resultPattern.test(value.scenarioAssemblyUnitsPerMonth) ||
    !Array.isArray(value.bottleneckLineGlobalIds) ||
    value.bottleneckLineGlobalIds.length < 1 ||
    !value.bottleneckLineGlobalIds.every(uuid) ||
    !unique(value.bottleneckLineGlobalIds) ||
    typeof value.gap !== "string" ||
    !resultPattern.test(value.gap)
  )
    return false;
  const lineIds = new Set(
    value.lineResults.map((item) => String(property(item, "globalId"))),
  );
  return value.bottleneckLineGlobalIds.every((item) => lineIds.has(item));
}

function isCapacityScenario(
  value: unknown,
): value is ToolingCapacityScenarioRevisionViewModel {
  if (
    !isRecord(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "scenarioGlobalId",
      "tenantId",
      "projectGlobalId",
      "toolingMasterGlobalId",
      "scenarioVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "title",
      "effectiveFrom",
      "targetMonthlyAssemblyUnits",
      "formulaVersion",
      "roundingRule",
      "lines",
      "result",
      "reason",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "versionKeyHash",
      "snapshotHash",
    ]) ||
    value.schemaVersion !== 1 ||
    !uuid(value.globalId) ||
    !uuid(value.scenarioGlobalId) ||
    !text(value.tenantId, 128) ||
    !uuid(value.projectGlobalId) ||
    !uuid(value.toolingMasterGlobalId) ||
    !integer(value.scenarioVersion) ||
    !nullable(value.predecessorGlobalId, uuid) ||
    !nullable(value.predecessorSnapshotHash, hash) ||
    !text(value.title, 255) ||
    !date(value.effectiveFrom) ||
    typeof value.targetMonthlyAssemblyUnits !== "string" ||
    !unsignedDecimalPattern.test(value.targetMonthlyAssemblyUnits) ||
    value.formulaVersion !== "capacity.v1" ||
    value.roundingRule !== "decimal-6-half-even" ||
    !Array.isArray(value.lines) ||
    value.lines.length < 1 ||
    value.lines.length > 100 ||
    !value.lines.every((item) => isCapacityLine(item, true)) ||
    !unique(
      value.lines.map((item) =>
        String(property(item, "applicabilityGlobalId")),
      ),
    ) ||
    !isCapacityResult(value.result) ||
    !text(value.reason, 1000) ||
    !text(value.createdByUserId, 254) ||
    !dateTime(value.createdAt) ||
    !uuid(value.requestId) ||
    !text(value.traceId, 128) ||
    !hash(value.versionKeyHash) ||
    !hash(value.snapshotHash)
  )
    return false;
  const result = value.result;
  return (
    (value.scenarioVersion === 1) ===
      (value.predecessorGlobalId === null &&
        value.predecessorSnapshotHash === null) &&
    value.lines.length === result.lineResults.length &&
    value.lines.every(
      (item, index) =>
        property(item, "globalId") === result.lineResults[index]?.globalId,
    )
  );
}

function isUnavailableField(
  value: unknown,
): value is ToolingEngineeringUnavailableFieldViewModel {
  return (
    isRecord(value) &&
    exact(value, ["state", "reasonCode"]) &&
    value.state === "unavailable" &&
    [
      "erp_shot_count_unavailable",
      "shot_count_calibration_policy_unavailable",
      "erp_maintenance_projection_unavailable",
      "tooling_health_policy_unavailable",
    ].includes(String(value.reasonCode))
  );
}

export function isToolingEngineeringControls(
  value: unknown,
): value is ToolingEngineeringControlsViewModel {
  if (
    !isRecord(value) ||
    !exact(value, [
      "projectGlobalId",
      "toolingMasterGlobalId",
      "permissions",
      "defectRevisions",
      "process",
      "capacityScenarioRevisions",
      "health",
    ]) ||
    !uuid(value.projectGlobalId) ||
    !uuid(value.toolingMasterGlobalId) ||
    !isRecord(value.permissions) ||
    !exact(value.permissions, [
      "view",
      "reviseDefect",
      "createCustomerStandard",
      "createCapacityScenario",
      "createTrialActual",
      "approveProcessBaseline",
      "editHealth",
      "transitionGate",
      "transitionToolingLifecycle",
    ]) ||
    value.permissions.view !== true ||
    typeof value.permissions.reviseDefect !== "boolean" ||
    typeof value.permissions.createCustomerStandard !== "boolean" ||
    typeof value.permissions.createCapacityScenario !== "boolean" ||
    value.permissions.createTrialActual !== false ||
    value.permissions.approveProcessBaseline !== false ||
    value.permissions.editHealth !== false ||
    value.permissions.transitionGate !== false ||
    value.permissions.transitionToolingLifecycle !== false ||
    !Array.isArray(value.defectRevisions) ||
    value.defectRevisions.length > 1000 ||
    !value.defectRevisions.every(isDefectRevision) ||
    !isRecord(value.process) ||
    !exact(value.process, [
      "customerStandardRevisions",
      "trialActual",
      "approvedBaseline",
      "comparisons",
    ]) ||
    !Array.isArray(value.process.customerStandardRevisions) ||
    value.process.customerStandardRevisions.length > 500 ||
    !value.process.customerStandardRevisions.every(isProcessProfile) ||
    !isRecord(value.process.trialActual) ||
    !exact(value.process.trialActual, ["state", "reasonCode"]) ||
    value.process.trialActual.state !== "not_measured" ||
    value.process.trialActual.reasonCode !== "trial_context_unavailable" ||
    !isRecord(value.process.approvedBaseline) ||
    !exact(value.process.approvedBaseline, ["state", "reasonCode"]) ||
    value.process.approvedBaseline.state !== "unavailable" ||
    value.process.approvedBaseline.reasonCode !==
      "approved_trial_evidence_unavailable" ||
    !Array.isArray(value.process.comparisons) ||
    value.process.comparisons.length > 3000 ||
    !value.process.comparisons.every(isComparison) ||
    !Array.isArray(value.capacityScenarioRevisions) ||
    value.capacityScenarioRevisions.length > 500 ||
    !value.capacityScenarioRevisions.every(isCapacityScenario) ||
    !isRecord(value.health) ||
    !exact(value.health, [
      "sourceSystem",
      "editableIn",
      "state",
      "shotCount",
      "calibration",
      "maintenance",
      "healthScore",
    ]) ||
    value.health.sourceSystem !== "ERPNEXT" ||
    value.health.editableIn !== "ERPNEXT" ||
    value.health.state !== "unavailable" ||
    !isUnavailableField(value.health.shotCount) ||
    !isUnavailableField(value.health.calibration) ||
    !isUnavailableField(value.health.maintenance) ||
    !isUnavailableField(value.health.healthScore)
  )
    return false;
  return (
    value.defectRevisions.every(
      (item) =>
        item.projectGlobalId === value.projectGlobalId &&
        item.toolingMasterGlobalId === value.toolingMasterGlobalId,
    ) &&
    value.process.customerStandardRevisions.every(
      (item) =>
        item.layer === "customer_standard" &&
        item.projectGlobalId === value.projectGlobalId &&
        item.toolingMasterGlobalId === value.toolingMasterGlobalId,
    ) &&
    value.capacityScenarioRevisions.every(
      (item) =>
        item.projectGlobalId === value.projectGlobalId &&
        item.toolingMasterGlobalId === value.toolingMasterGlobalId,
    )
  );
}

export function isToolingDefectRevisionCommand(
  value: unknown,
): value is ToolingDefectRevisionCommandViewModel {
  return (
    isRecord(value) &&
    exact(value, ["defect"]) &&
    isDefectRevision(value.defect)
  );
}

export function isToolingProcessProfileRevisionCommand(
  value: unknown,
): value is ToolingProcessProfileRevisionCommandViewModel {
  return (
    isRecord(value) &&
    exact(value, ["profile"]) &&
    isProcessProfile(value.profile)
  );
}

export function isToolingCapacityScenarioRevisionCommand(
  value: unknown,
): value is ToolingCapacityScenarioRevisionCommandViewModel {
  return (
    isRecord(value) &&
    exact(value, ["scenario"]) &&
    isCapacityScenario(value.scenario)
  );
}
