import { NpiHttpClient, NpiTransportError } from "./http";

export const engineeringChangeCategories = [
  "product",
  "drawing",
  "ebom",
  "mbom",
  "tooling",
  "process",
  "quality",
  "inventory_wip",
  "supplier",
  "cost",
  "delivery",
  "customer",
] as const;
export type EngineeringChangeCategory =
  (typeof engineeringChangeCategories)[number];

export const engineeringChangeStates = [
  "draft",
  "active",
  "ready_to_close",
  "closed",
  "cancelled",
] as const;
export type EngineeringChangeState = (typeof engineeringChangeStates)[number];

export type EngineeringChangeImpactConclusion =
  | "pending"
  | "not_affected"
  | "affected";

export interface FormalEngineeringChangeObservation {
  doctype: "Engineering Change Request";
  documentName: string;
  rawStatus: string;
  sourceVersion: string;
  sourceModifiedAt: string;
  sourceHash: string;
  observedAt: string;
}

export interface EngineeringChangeImpactAssessment {
  category: EngineeringChangeCategory;
  conclusion: EngineeringChangeImpactConclusion;
  responsibleUserId: string;
  rationale: string;
  evidenceReferenceGlobalIds: readonly string[];
}

export interface EngineeringChangeAffectedObject {
  category: EngineeringChangeCategory;
  kind:
    | "engineering_part_revision"
    | "engineering_bom_revision"
    | "manufacturing_bom_revision"
    | "controlled_document_revision"
    | "document_baseline"
    | "tooling_revision"
    | "tooling_set_binding"
    | "trial_plan_revision"
    | "trial_conclusion_revision"
    | "released_trial_summary_revision"
    | "gate_review_cycle"
    | "erp_item"
    | "erp_formal_quality"
    | "other_controlled_reference";
  objectGlobalId: string;
  priorVersionGlobalId: string | null;
  priorSnapshotHash: string | null;
  successorVersionGlobalId: string | null;
  successorSnapshotHash: string | null;
}

export interface EngineeringChangeTaskLink {
  kind:
    | "design"
    | "tool_modification"
    | "procurement"
    | "trial"
    | "quality"
    | "cutover";
  workItemGlobalId: string;
  purpose: string;
}

export interface EngineeringChangeEffectivity {
  kind:
    | "date"
    | "order"
    | "batch"
    | "inventory_depletion"
    | "serial_or_shot"
    | "customer_approval";
  effectiveDate: string | null;
  selectorReference: string | null;
  validationEvidenceGlobalId: string | null;
}

export interface EngineeringChangeDisposition {
  scope:
    | "old_inventory"
    | "work_in_progress"
    | "in_transit"
    | "old_label_or_file"
    | "customer_inventory";
  decision:
    | "use_as_is"
    | "rework"
    | "scrap"
    | "return_to_supplier"
    | "segregate"
    | "relabel"
    | "customer_approval"
    | "other";
  approvedByUserId: string;
  approvalEvidenceGlobalId: string;
  executionEvidenceGlobalId: string | null;
  note: string | null;
}

export interface EngineeringChangeRevalidation {
  kind:
    | "design_review"
    | "tool_modification"
    | "procurement"
    | "trial"
    | "fai"
    | "quality"
    | "customer_approval"
    | "npi_gate_review"
    | "cutover";
  state: "required" | "in_progress" | "satisfied" | "waived";
  responsibleUserId: string;
  workItemGlobalId: string | null;
  gateReviewGlobalId: string | null;
  evidenceReferenceGlobalIds: readonly string[];
  waiverApprovalGlobalId: string | null;
}

export interface EngineeringChangeCost {
  currency: string;
  engineeringCost: string;
  toolingCost: string;
  scrapCost: string;
  logisticsCost: string;
  downtimeMinutes: number;
  deliveryImpactDays: number;
}

export interface EngineeringChangeClosureEvidence {
  newVersionsReleased: boolean;
  erpUpdateObserved: boolean;
  oldVersionsWithdrawn: boolean;
  effectivityValidated: boolean;
  dispositionsExecuted: boolean;
  evidenceReferenceGlobalIds: readonly string[];
}

export interface EngineeringChangeContent {
  title: string;
  reason: string;
  impactAssessments: readonly EngineeringChangeImpactAssessment[];
  affectedObjects: readonly EngineeringChangeAffectedObject[];
  implementationTasks: readonly EngineeringChangeTaskLink[];
  effectivityRules: readonly EngineeringChangeEffectivity[];
  dispositions: readonly EngineeringChangeDisposition[];
  revalidationRequirements: readonly EngineeringChangeRevalidation[];
  costSummary: EngineeringChangeCost;
  closureEvidence: EngineeringChangeClosureEvidence | null;
}

export interface EngineeringChangeRevision extends EngineeringChangeContent {
  schemaVersion: 1;
  globalId: string;
  changeGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  revision: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  state: EngineeringChangeState;
  formalChange: FormalEngineeringChangeObservation | null;
  readyToClose: boolean;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface EngineeringChangeCurrent {
  globalId: string;
  projectGlobalId: string;
  title: string;
  state: EngineeringChangeState;
  optimisticVersion: number;
  currentRevisionGlobalId: string;
  currentRevisionNumber: number;
  currentRevisionSnapshotHash: string;
  formalChange: FormalEngineeringChangeObservation | null;
  readyToClose: boolean;
}

export interface EngineeringChangePermissions {
  canView: boolean;
  canCreate: boolean;
  canRevise: boolean;
  canLinkFormalObservation: boolean;
  canClose: boolean;
}

export interface EngineeringChangeListItem {
  change: EngineeringChangeCurrent;
  currentRevision: EngineeringChangeRevision;
}

export interface EngineeringChangeList {
  projectGlobalId: string;
  items: readonly EngineeringChangeListItem[];
  permissions: EngineeringChangePermissions;
}

export interface EngineeringChangeEvent {
  schemaVersion: 1;
  globalId: string;
  changeGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  revisionGlobalId: string;
  revision: number;
  revisionSnapshotHash: string;
  eventType:
    | "created"
    | "revised"
    | "formal_observation_linked"
    | "ready_to_close"
    | "closed"
    | "cancelled";
  actorUserId: string;
  occurredAt: string;
  requestId: string;
  traceId: string;
  eventHash: string;
}

export interface EngineeringChangeDetail {
  projectGlobalId: string;
  change: EngineeringChangeCurrent;
  currentRevision: EngineeringChangeRevision;
  revisions: readonly EngineeringChangeRevision[];
  events: readonly EngineeringChangeEvent[];
  permissions: EngineeringChangePermissions;
}

export interface EngineeringChangeCommandResult {
  operation:
    | "engineering_change.create"
    | "engineering_change.revise"
    | "engineering_change.link_formal_observation"
    | "engineering_change.close";
  change: EngineeringChangeCurrent;
  currentRevision: EngineeringChangeRevision;
}

export interface EngineeringChangeSummaryReceipt {
  schemaVersion: 1;
  requestGlobalId: string;
  changeGlobalId: string;
  revisionGlobalId: string;
  revisionNumber: number;
  sourceHash: string;
  state:
    | "queued"
    | "processing"
    | "synthetic_verified"
    | "succeeded"
    | "failed_retryable"
    | "failed_final"
    | "partially_succeeded"
    | "uncertain_after_timeout"
    | "identity_conflict";
  outboxEventId: string;
}

export interface EngineeringChangeCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface ChangeControlDataSource {
  loadChanges(
    projectId: string,
    signal: AbortSignal,
  ): Promise<EngineeringChangeList>;
  loadChange(
    projectId: string,
    changeId: string,
    signal: AbortSignal,
  ): Promise<EngineeringChangeDetail>;
  createChange(
    projectId: string,
    content: EngineeringChangeContent,
    context: EngineeringChangeCommandContext,
  ): Promise<EngineeringChangeCommandResult>;
  reviseChange(
    projectId: string,
    current: EngineeringChangeRevision,
    content: EngineeringChangeContent,
    context: EngineeringChangeCommandContext,
  ): Promise<EngineeringChangeCommandResult>;
  closeChange(
    projectId: string,
    current: EngineeringChangeRevision,
    context: EngineeringChangeCommandContext,
  ): Promise<EngineeringChangeCommandResult>;
  requestImplementationSummary(
    projectId: string,
    current: EngineeringChangeRevision,
    context: EngineeringChangeCommandContext,
  ): Promise<EngineeringChangeSummaryReceipt>;
}

export class ChangeControlRequestCancelledError extends Error {
  constructor() {
    super("The Engineering Change request was cancelled.");
    this.name = "ChangeControlRequestCancelledError";
  }
}

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const HASH = /^[a-f0-9]{64}$/u;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/u;
const CURRENCY = /^[A-Z]{3}$/u;
const DECIMAL = /^(0|[1-9][0-9]*)(?:\.[0-9]+)?$/u;
const IDEMPOTENCY = /^[A-Za-z0-9._:-]{8,128}$/u;
const TRACE = /^[A-Za-z0-9._:@/-]{8,140}$/u;
const CATEGORY = new Set<string>(engineeringChangeCategories);
const CHANGE_STATE = new Set<string>(engineeringChangeStates);
const CONCLUSION = new Set<string>(["pending", "not_affected", "affected"]);
const AFFECTED_KIND = new Set<string>([
  "engineering_part_revision",
  "engineering_bom_revision",
  "manufacturing_bom_revision",
  "controlled_document_revision",
  "document_baseline",
  "tooling_revision",
  "tooling_set_binding",
  "trial_plan_revision",
  "trial_conclusion_revision",
  "released_trial_summary_revision",
  "gate_review_cycle",
  "erp_item",
  "erp_formal_quality",
  "other_controlled_reference",
]);
const TASK_KIND = new Set<string>([
  "design",
  "tool_modification",
  "procurement",
  "trial",
  "quality",
  "cutover",
]);
const EFFECTIVITY_KIND = new Set<string>([
  "date",
  "order",
  "batch",
  "inventory_depletion",
  "serial_or_shot",
  "customer_approval",
]);
const DISPOSITION_SCOPE = new Set<string>([
  "old_inventory",
  "work_in_progress",
  "in_transit",
  "old_label_or_file",
  "customer_inventory",
]);
const DISPOSITION_DECISION = new Set<string>([
  "use_as_is",
  "rework",
  "scrap",
  "return_to_supplier",
  "segregate",
  "relabel",
  "customer_approval",
  "other",
]);
const REVALIDATION_KIND = new Set<string>([
  "design_review",
  "tool_modification",
  "procurement",
  "trial",
  "fai",
  "quality",
  "customer_approval",
  "npi_gate_review",
  "cutover",
]);
const REVALIDATION_STATE = new Set<string>([
  "required",
  "in_progress",
  "satisfied",
  "waived",
]);
const EVENT_TYPE = new Set<string>([
  "created",
  "revised",
  "formal_observation_linked",
  "ready_to_close",
  "closed",
  "cancelled",
]);
const SUMMARY_STATE = new Set<string>([
  "queued",
  "processing",
  "synthetic_verified",
  "succeeded",
  "failed_retryable",
  "failed_final",
  "partially_succeeded",
  "uncertain_after_timeout",
  "identity_conflict",
]);

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exact(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return (
    Object.keys(value).length === keys.length &&
    keys.every((key) => Object.hasOwn(value, key))
  );
}

function text(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= maximum &&
    value === value.trim()
  );
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}
function hash(value: unknown): value is string {
  return typeof value === "string" && HASH.test(value);
}
function positive(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) > 0;
}
function nonnegative(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}
function timestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.endsWith("Z") &&
    Number.isFinite(Date.parse(value))
  );
}
function date(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}$/u.test(value) &&
    Number.isFinite(Date.parse(`${value}T00:00:00Z`))
  );
}
function optionalUuid(value: unknown): value is string | null {
  return value === null || uuid(value);
}
function optionalHash(value: unknown): value is string | null {
  return value === null || hash(value);
}
function optionalText(value: unknown, maximum: number): value is string | null {
  return value === null || text(value, maximum);
}
function uniqueStrings(
  value: unknown,
  maximum = 1000,
): value is readonly string[] {
  return (
    Array.isArray(value) &&
    value.length <= maximum &&
    value.every(uuid) &&
    new Set(value).size === value.length
  );
}

function formalObservation(
  value: unknown,
): value is FormalEngineeringChangeObservation {
  return (
    record(value) &&
    exact(value, [
      "doctype",
      "documentName",
      "rawStatus",
      "sourceVersion",
      "sourceModifiedAt",
      "sourceHash",
      "observedAt",
    ]) &&
    value.doctype === "Engineering Change Request" &&
    text(value.documentName, 140) &&
    text(value.rawStatus, 140) &&
    text(value.sourceVersion, 140) &&
    timestamp(value.sourceModifiedAt) &&
    hash(value.sourceHash) &&
    timestamp(value.observedAt)
  );
}

function impact(value: unknown): value is EngineeringChangeImpactAssessment {
  return (
    record(value) &&
    exact(value, [
      "category",
      "conclusion",
      "responsibleUserId",
      "rationale",
      "evidenceReferenceGlobalIds",
    ]) &&
    CATEGORY.has(String(value.category)) &&
    CONCLUSION.has(String(value.conclusion)) &&
    typeof value.responsibleUserId === "string" &&
    EMAIL.test(value.responsibleUserId) &&
    text(value.rationale, 4000) &&
    uniqueStrings(value.evidenceReferenceGlobalIds)
  );
}

function affected(value: unknown): value is EngineeringChangeAffectedObject {
  return (
    record(value) &&
    exact(value, [
      "category",
      "kind",
      "objectGlobalId",
      "priorVersionGlobalId",
      "priorSnapshotHash",
      "successorVersionGlobalId",
      "successorSnapshotHash",
    ]) &&
    CATEGORY.has(String(value.category)) &&
    AFFECTED_KIND.has(String(value.kind)) &&
    uuid(value.objectGlobalId) &&
    optionalUuid(value.priorVersionGlobalId) &&
    optionalHash(value.priorSnapshotHash) &&
    optionalUuid(value.successorVersionGlobalId) &&
    optionalHash(value.successorSnapshotHash) &&
    (value.priorVersionGlobalId === null) ===
      (value.priorSnapshotHash === null) &&
    (value.successorVersionGlobalId === null) ===
      (value.successorSnapshotHash === null)
  );
}

function task(value: unknown): value is EngineeringChangeTaskLink {
  return (
    record(value) &&
    exact(value, ["kind", "workItemGlobalId", "purpose"]) &&
    TASK_KIND.has(String(value.kind)) &&
    uuid(value.workItemGlobalId) &&
    text(value.purpose, 500)
  );
}

function effectivity(value: unknown): value is EngineeringChangeEffectivity {
  return (
    record(value) &&
    exact(value, [
      "kind",
      "effectiveDate",
      "selectorReference",
      "validationEvidenceGlobalId",
    ]) &&
    EFFECTIVITY_KIND.has(String(value.kind)) &&
    (value.effectiveDate === null || date(value.effectiveDate)) &&
    optionalText(value.selectorReference, 280) &&
    optionalUuid(value.validationEvidenceGlobalId)
  );
}

function disposition(value: unknown): value is EngineeringChangeDisposition {
  return (
    record(value) &&
    exact(value, [
      "scope",
      "decision",
      "approvedByUserId",
      "approvalEvidenceGlobalId",
      "executionEvidenceGlobalId",
      "note",
    ]) &&
    DISPOSITION_SCOPE.has(String(value.scope)) &&
    DISPOSITION_DECISION.has(String(value.decision)) &&
    typeof value.approvedByUserId === "string" &&
    EMAIL.test(value.approvedByUserId) &&
    uuid(value.approvalEvidenceGlobalId) &&
    optionalUuid(value.executionEvidenceGlobalId) &&
    optionalText(value.note, 2000)
  );
}

function revalidation(value: unknown): value is EngineeringChangeRevalidation {
  return (
    record(value) &&
    exact(value, [
      "kind",
      "state",
      "responsibleUserId",
      "workItemGlobalId",
      "gateReviewGlobalId",
      "evidenceReferenceGlobalIds",
      "waiverApprovalGlobalId",
    ]) &&
    REVALIDATION_KIND.has(String(value.kind)) &&
    REVALIDATION_STATE.has(String(value.state)) &&
    typeof value.responsibleUserId === "string" &&
    EMAIL.test(value.responsibleUserId) &&
    optionalUuid(value.workItemGlobalId) &&
    optionalUuid(value.gateReviewGlobalId) &&
    uniqueStrings(value.evidenceReferenceGlobalIds) &&
    optionalUuid(value.waiverApprovalGlobalId)
  );
}

function cost(value: unknown): value is EngineeringChangeCost {
  return (
    record(value) &&
    exact(value, [
      "currency",
      "engineeringCost",
      "toolingCost",
      "scrapCost",
      "logisticsCost",
      "downtimeMinutes",
      "deliveryImpactDays",
    ]) &&
    typeof value.currency === "string" &&
    CURRENCY.test(value.currency) &&
    [
      value.engineeringCost,
      value.toolingCost,
      value.scrapCost,
      value.logisticsCost,
    ].every((entry) => typeof entry === "string" && DECIMAL.test(entry)) &&
    nonnegative(value.downtimeMinutes) &&
    nonnegative(value.deliveryImpactDays)
  );
}

function closure(value: unknown): value is EngineeringChangeClosureEvidence {
  return (
    record(value) &&
    exact(value, [
      "newVersionsReleased",
      "erpUpdateObserved",
      "oldVersionsWithdrawn",
      "effectivityValidated",
      "dispositionsExecuted",
      "evidenceReferenceGlobalIds",
    ]) &&
    [
      value.newVersionsReleased,
      value.erpUpdateObserved,
      value.oldVersionsWithdrawn,
      value.effectivityValidated,
      value.dispositionsExecuted,
    ].every((entry) => typeof entry === "boolean") &&
    uniqueStrings(value.evidenceReferenceGlobalIds)
  );
}

function content(value: unknown): value is EngineeringChangeContent {
  if (
    !record(value) ||
    !exact(value, [
      "title",
      "reason",
      "impactAssessments",
      "affectedObjects",
      "implementationTasks",
      "effectivityRules",
      "dispositions",
      "revalidationRequirements",
      "costSummary",
      "closureEvidence",
    ])
  )
    return false;
  const impacts = value.impactAssessments;
  return (
    text(value.title, 280) &&
    text(value.reason, 4000) &&
    Array.isArray(impacts) &&
    impacts.length === engineeringChangeCategories.length &&
    impacts.every(impact) &&
    impacts.every(
      (entry, index) => entry.category === engineeringChangeCategories[index],
    ) &&
    Array.isArray(value.affectedObjects) &&
    value.affectedObjects.length <= 1000 &&
    value.affectedObjects.every(affected) &&
    Array.isArray(value.implementationTasks) &&
    value.implementationTasks.length <= 1000 &&
    value.implementationTasks.every(task) &&
    Array.isArray(value.effectivityRules) &&
    value.effectivityRules.length <= 1000 &&
    value.effectivityRules.every(effectivity) &&
    Array.isArray(value.dispositions) &&
    value.dispositions.length <= 1000 &&
    value.dispositions.every(disposition) &&
    Array.isArray(value.revalidationRequirements) &&
    value.revalidationRequirements.length <= 1000 &&
    value.revalidationRequirements.every(revalidation) &&
    cost(value.costSummary) &&
    (value.closureEvidence === null || closure(value.closureEvidence))
  );
}

const REVISION_KEYS = [
  "schemaVersion",
  "globalId",
  "changeGlobalId",
  "tenantId",
  "projectGlobalId",
  "revision",
  "predecessorGlobalId",
  "predecessorSnapshotHash",
  "state",
  "title",
  "reason",
  "formalChange",
  "impactAssessments",
  "affectedObjects",
  "implementationTasks",
  "effectivityRules",
  "dispositions",
  "revalidationRequirements",
  "costSummary",
  "closureEvidence",
  "readyToClose",
  "createdByUserId",
  "createdAt",
  "requestId",
  "traceId",
  "snapshotHash",
] as const;

export function isEngineeringChangeRevision(
  value: unknown,
  projectId?: string,
  changeId?: string,
): value is EngineeringChangeRevision {
  if (
    !record(value) ||
    !exact(value, REVISION_KEYS) ||
    value.schemaVersion !== 1 ||
    !uuid(value.globalId) ||
    !uuid(value.changeGlobalId) ||
    !text(value.tenantId, 140) ||
    !uuid(value.projectGlobalId) ||
    !positive(value.revision) ||
    !optionalUuid(value.predecessorGlobalId) ||
    !optionalHash(value.predecessorSnapshotHash) ||
    !CHANGE_STATE.has(String(value.state)) ||
    !(value.formalChange === null || formalObservation(value.formalChange)) ||
    typeof value.readyToClose !== "boolean" ||
    typeof value.createdByUserId !== "string" ||
    !EMAIL.test(value.createdByUserId) ||
    !timestamp(value.createdAt) ||
    !uuid(value.requestId) ||
    !text(value.traceId, 140) ||
    !TRACE.test(value.traceId) ||
    !hash(value.snapshotHash)
  )
    return false;
  const payload = Object.fromEntries(
    Object.entries(value).filter(
      ([key]) =>
        ![
          "schemaVersion",
          "globalId",
          "changeGlobalId",
          "tenantId",
          "projectGlobalId",
          "revision",
          "predecessorGlobalId",
          "predecessorSnapshotHash",
          "state",
          "formalChange",
          "readyToClose",
          "createdByUserId",
          "createdAt",
          "requestId",
          "traceId",
          "snapshotHash",
        ].includes(key),
    ),
  );
  return (
    content(payload) &&
    (projectId === undefined || value.projectGlobalId === projectId) &&
    (changeId === undefined || value.changeGlobalId === changeId) &&
    (value.revision === 1
      ? value.predecessorGlobalId === null &&
        value.predecessorSnapshotHash === null
      : value.predecessorGlobalId !== null &&
        value.predecessorSnapshotHash !== null)
  );
}

function current(
  value: unknown,
  revision: EngineeringChangeRevision,
  projectId: string,
): value is EngineeringChangeCurrent {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "projectGlobalId",
      "title",
      "state",
      "optimisticVersion",
      "currentRevisionGlobalId",
      "currentRevisionNumber",
      "currentRevisionSnapshotHash",
      "formalChange",
      "readyToClose",
    ]) &&
    value.globalId === revision.changeGlobalId &&
    value.projectGlobalId === projectId &&
    value.title === revision.title &&
    value.state === revision.state &&
    value.optimisticVersion === revision.revision &&
    value.currentRevisionGlobalId === revision.globalId &&
    value.currentRevisionNumber === revision.revision &&
    value.currentRevisionSnapshotHash === revision.snapshotHash &&
    JSON.stringify(value.formalChange) ===
      JSON.stringify(revision.formalChange) &&
    value.readyToClose === revision.readyToClose
  );
}

function permissions(value: unknown): value is EngineeringChangePermissions {
  return (
    record(value) &&
    exact(value, [
      "canView",
      "canCreate",
      "canRevise",
      "canLinkFormalObservation",
      "canClose",
    ]) &&
    Object.values(value).every((entry) => typeof entry === "boolean")
  );
}

function event(
  value: unknown,
  currentRevision: EngineeringChangeRevision,
  revisionsByNumber: ReadonlyMap<number, EngineeringChangeRevision>,
): value is EngineeringChangeEvent {
  if (
    !record(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "changeGlobalId",
      "tenantId",
      "projectGlobalId",
      "revisionGlobalId",
      "revision",
      "revisionSnapshotHash",
      "eventType",
      "actorUserId",
      "occurredAt",
      "requestId",
      "traceId",
      "eventHash",
    ]) ||
    !positive(value.revision)
  )
    return false;
  const linkedRevision = revisionsByNumber.get(value.revision);
  return (
    linkedRevision !== undefined &&
    value.schemaVersion === 1 &&
    uuid(value.globalId) &&
    value.changeGlobalId === currentRevision.changeGlobalId &&
    value.tenantId === currentRevision.tenantId &&
    value.projectGlobalId === currentRevision.projectGlobalId &&
    value.revision <= currentRevision.revision &&
    value.revisionGlobalId === linkedRevision.globalId &&
    value.revisionSnapshotHash === linkedRevision.snapshotHash &&
    EVENT_TYPE.has(String(value.eventType)) &&
    typeof value.actorUserId === "string" &&
    EMAIL.test(value.actorUserId) &&
    timestamp(value.occurredAt) &&
    uuid(value.requestId) &&
    text(value.traceId, 140) &&
    TRACE.test(value.traceId) &&
    hash(value.eventHash)
  );
}

export function isEngineeringChangeList(
  value: unknown,
  projectId: string,
): value is EngineeringChangeList {
  return (
    record(value) &&
    exact(value, ["projectGlobalId", "items", "permissions"]) &&
    value.projectGlobalId === projectId &&
    Array.isArray(value.items) &&
    value.items.length <= 1000 &&
    value.items.every(
      (item) =>
        record(item) &&
        exact(item, ["change", "currentRevision"]) &&
        isEngineeringChangeRevision(item.currentRevision, projectId) &&
        current(item.change, item.currentRevision, projectId),
    ) &&
    permissions(value.permissions)
  );
}

export function isEngineeringChangeDetail(
  value: unknown,
  projectId: string,
  changeId: string,
): value is EngineeringChangeDetail {
  if (!record(value)) return false;
  const candidateCurrent = value.currentRevision;
  const candidateRevisions = value.revisions;
  const candidateEvents = value.events;
  if (
    !exact(value, [
      "projectGlobalId",
      "change",
      "currentRevision",
      "revisions",
      "events",
      "permissions",
    ]) ||
    value.projectGlobalId !== projectId ||
    !isEngineeringChangeRevision(candidateCurrent, projectId, changeId) ||
    !current(value.change, candidateCurrent, projectId) ||
    !permissions(value.permissions) ||
    !Array.isArray(candidateRevisions) ||
    !Array.isArray(candidateEvents) ||
    candidateRevisions.length < 1 ||
    candidateRevisions.length > 1000 ||
    candidateEvents.length < 1 ||
    candidateEvents.length > 1000
  )
    return false;
  const currentRevision = candidateCurrent;
  if (
    !candidateRevisions.every(
      (entry, index): entry is EngineeringChangeRevision =>
        isEngineeringChangeRevision(entry, projectId, changeId) &&
        entry.revision === index + 1,
    )
  )
    return false;
  const revisions = candidateRevisions;
  if (
    !revisions.every((entry, index) => {
      const predecessor = revisions[index - 1];
      return index === 0
        ? entry.predecessorGlobalId === null &&
            entry.predecessorSnapshotHash === null
        : entry.predecessorGlobalId === predecessor?.globalId &&
            entry.predecessorSnapshotHash === predecessor.snapshotHash;
    })
  )
    return false;
  const lastRevision = revisions.at(-1);
  if (
    lastRevision?.globalId !== currentRevision.globalId ||
    lastRevision.snapshotHash !== currentRevision.snapshotHash
  )
    return false;
  const revisionsByNumber = new Map(
    revisions.map((entry) => [entry.revision, entry]),
  );
  return candidateEvents.every((entry) =>
    event(entry, currentRevision, revisionsByNumber),
  );
}

function command(
  value: unknown,
  operation: EngineeringChangeCommandResult["operation"],
  projectId: string,
  changeId?: string,
): value is EngineeringChangeCommandResult {
  return (
    record(value) &&
    exact(value, ["operation", "change", "currentRevision"]) &&
    value.operation === operation &&
    isEngineeringChangeRevision(value.currentRevision, projectId, changeId) &&
    current(value.change, value.currentRevision, projectId)
  );
}

function summary(
  value: unknown,
  projectId: string,
  currentRevision: EngineeringChangeRevision,
): value is EngineeringChangeSummaryReceipt {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "requestGlobalId",
      "changeGlobalId",
      "revisionGlobalId",
      "revisionNumber",
      "sourceHash",
      "state",
      "outboxEventId",
    ]) &&
    value.schemaVersion === 1 &&
    uuid(value.requestGlobalId) &&
    value.changeGlobalId === currentRevision.changeGlobalId &&
    value.revisionGlobalId === currentRevision.globalId &&
    value.revisionNumber === currentRevision.revision &&
    hash(value.sourceHash) &&
    SUMMARY_STATE.has(String(value.state)) &&
    uuid(value.outboxEventId) &&
    currentRevision.projectGlobalId === projectId
  );
}

function readyProject(projectId: string): void {
  if (!uuid(projectId))
    throw new NpiTransportError(
      "request_not_ready",
      `client-${globalThis.crypto.randomUUID()}`,
      "client",
    );
}

function readyContext(context: EngineeringChangeCommandContext): void {
  if (
    !IDEMPOTENCY.test(context.idempotencyKey) ||
    !text(context.csrfToken, 1024)
  )
    throw new NpiTransportError(
      "request_not_ready",
      `client-${globalThis.crypto.randomUUID()}`,
      "client",
    );
}

function predecessor(currentRevision: EngineeringChangeRevision) {
  return {
    expectedRevision: currentRevision.revision,
    expectedRevisionGlobalId: currentRevision.globalId,
    expectedRevisionSnapshotHash: currentRevision.snapshotHash,
  };
}

export class LiveChangeControlDataSource implements ChangeControlDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadChanges(
    projectId: string,
    signal: AbortSignal,
  ): Promise<EngineeringChangeList> {
    readyProject(projectId);
    try {
      return await this.http.request(
        `/projects/${projectId}/engineering-changes`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          validate: (value): value is EngineeringChangeList =>
            isEngineeringChangeList(value, projectId),
        },
      );
    } catch (error) {
      if (signal.aborted) throw new ChangeControlRequestCancelledError();
      throw error;
    }
  }

  async loadChange(
    projectId: string,
    changeId: string,
    signal: AbortSignal,
  ): Promise<EngineeringChangeDetail> {
    readyProject(projectId);
    if (!uuid(changeId))
      throw new NpiTransportError(
        "request_not_ready",
        `client-${globalThis.crypto.randomUUID()}`,
        "client",
      );
    try {
      return await this.http.request(
        `/projects/${projectId}/engineering-changes/${changeId}`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          validate: (value): value is EngineeringChangeDetail =>
            isEngineeringChangeDetail(value, projectId, changeId),
        },
      );
    } catch (error) {
      if (signal.aborted) throw new ChangeControlRequestCancelledError();
      throw error;
    }
  }

  async createChange(
    projectId: string,
    value: EngineeringChangeContent,
    context: EngineeringChangeCommandContext,
  ): Promise<EngineeringChangeCommandResult> {
    readyProject(projectId);
    readyContext(context);
    return this.http.request(
      `/projects/${projectId}/engineering-changes`,
      {
        method: "POST",
        signal: context.signal,
        headers: { "Idempotency-Key": context.idempotencyKey },
        body: JSON.stringify({ content: value }),
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        validate: (candidate): candidate is EngineeringChangeCommandResult =>
          command(candidate, "engineering_change.create", projectId),
      },
    );
  }

  async reviseChange(
    projectId: string,
    currentRevision: EngineeringChangeRevision,
    value: EngineeringChangeContent,
    context: EngineeringChangeCommandContext,
  ): Promise<EngineeringChangeCommandResult> {
    readyProject(projectId);
    readyContext(context);
    return this.http.request(
      `/projects/${projectId}/engineering-changes/${currentRevision.changeGlobalId}/revisions`,
      {
        method: "POST",
        signal: context.signal,
        headers: { "Idempotency-Key": context.idempotencyKey },
        body: JSON.stringify({
          predecessor: predecessor(currentRevision),
          content: value,
        }),
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        validate: (candidate): candidate is EngineeringChangeCommandResult =>
          command(
            candidate,
            "engineering_change.revise",
            projectId,
            currentRevision.changeGlobalId,
          ),
      },
    );
  }

  async closeChange(
    projectId: string,
    currentRevision: EngineeringChangeRevision,
    context: EngineeringChangeCommandContext,
  ): Promise<EngineeringChangeCommandResult> {
    readyProject(projectId);
    readyContext(context);
    return this.http.request(
      `/projects/${projectId}/engineering-changes/${currentRevision.changeGlobalId}:close`,
      {
        method: "POST",
        signal: context.signal,
        headers: { "Idempotency-Key": context.idempotencyKey },
        body: JSON.stringify({ predecessor: predecessor(currentRevision) }),
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        validate: (candidate): candidate is EngineeringChangeCommandResult =>
          command(
            candidate,
            "engineering_change.close",
            projectId,
            currentRevision.changeGlobalId,
          ),
      },
    );
  }

  async requestImplementationSummary(
    projectId: string,
    currentRevision: EngineeringChangeRevision,
    context: EngineeringChangeCommandContext,
  ): Promise<EngineeringChangeSummaryReceipt> {
    readyProject(projectId);
    readyContext(context);
    return this.http.request(
      `/projects/${projectId}/engineering-changes/${currentRevision.changeGlobalId}:request-implementation-summary`,
      {
        method: "POST",
        signal: context.signal,
        headers: { "Idempotency-Key": context.idempotencyKey },
        body: JSON.stringify(predecessor(currentRevision)),
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        validate: (candidate): candidate is EngineeringChangeSummaryReceipt =>
          summary(candidate, projectId, currentRevision),
      },
    );
  }
}
