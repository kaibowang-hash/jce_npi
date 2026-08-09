const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const keyPattern = /^[a-z][a-z0-9_.-]{0,127}$/u;
const cellPattern = /^[A-Z]{1,3}[1-9][0-9]*$/u;

export interface ToolingImportPermissions {
  view: true;
  registerSource: boolean;
  inspect: boolean;
  createMappingProposal: boolean;
  createPreview: boolean;
  confirmPreview: boolean;
  activateProductionMapping: false;
  execute: boolean;
  retry: boolean;
  createCorrectionArtifact: boolean;
  downloadCorrectionArtifact: boolean;
  reconcile: boolean;
  evaluateRollback: boolean;
  rollback: boolean;
}

export type ToolingImportMappingAuthority =
  | { state: "unavailable"; reasonCode: "production_mapping_unavailable" }
  | {
      state: "approved_fixture";
      reasonCode: "synthetic_fixture_scope_only";
      mappingRevisionGlobalId: string;
      mappingSnapshotHash: string;
      activationGlobalId: string;
      activationSnapshotHash: string;
    };

export interface ToolingImportSource {
  schemaVersion: "tooling-import.v1";
  batchGlobalId: string;
  tenantId: string;
  projectGlobalId: string;
  customerScopeId: string;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: number;
  frappeContentHash: string;
  fileName: string;
  mimeType:
    | "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    | "application/octet-stream";
  sizeBytes: number;
  sha256: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface ToolingImportDetectedColumn {
  ordinal: number;
  sourceHeader: string;
  headerCell: string;
}

export interface ToolingImportDetectedRegion {
  kind:
    | "title"
    | "header"
    | "data"
    | "shared_tooling_marker"
    | "shared_tooling_data"
    | "summary"
    | "section";
  firstRow: number;
  lastRow: number;
  evidence: string;
  requiresConfirmation: boolean;
}

export interface ToolingImportInspectionRevision {
  schemaVersion: "tooling-import.v1";
  inspectionPolicyVersion: "tooling-xlsx-inspection.v1";
  detectionPolicyVersion: "tooling-list-detection.v1";
  globalId: string;
  batchGlobalId: string;
  sourceSnapshotHash: string;
  inspectionVersion: number;
  worksheetName: string;
  headerRow: number;
  sourceSignature: string;
  columns: readonly ToolingImportDetectedColumn[];
  regions: readonly ToolingImportDetectedRegion[];
  formulaErrors: readonly Readonly<{ cell: string; errorCode: string }>[];
  imageAnchors: readonly Readonly<{
    anchorKey: string;
    row: number | null;
    column: number | null;
    confidence: "high" | "ambiguous";
    candidateSourceRow: number | null;
    requiresConfirmation: boolean;
  }>[];
  passiveReportHash: string;
  createdAt: string;
  snapshotHash: string;
}

export interface ToolingImportMappingEntry {
  sourceOrdinal: number;
  sourceHeader: string;
  disposition: "candidate" | "unmapped";
  targetObjectCandidate: string | null;
  targetFieldCandidate: string | null;
  semanticClassification:
    | "unclassified"
    | "identity"
    | "descriptive"
    | "legacy_grade"
    | "relation_candidate"
    | "calculated_unverified";
  transformationKey: string;
  validationRuleKeys: readonly string[];
}

export interface ToolingImportMappingRevision {
  schemaVersion: "tooling-import.v1";
  globalId: string;
  mappingGlobalId: string;
  batchGlobalId: string;
  sourceSnapshotHash: string;
  inspectionGlobalId: string;
  inspectionSnapshotHash: string;
  mappingVersion: number;
  state: "proposal" | "approved_fixture";
  customerScopeId: string;
  templateKey: string;
  sourceSignature: string;
  entries: readonly ToolingImportMappingEntry[];
  reason: string;
  createdByUserId: string;
  createdAt: string;
  snapshotHash: string;
}

export interface ToolingImportFieldFinding {
  code: string;
  severity: "warning" | "error" | "confirmation_required";
  message: string;
}

export interface ToolingImportTransformedField {
  sourceOrdinal: number;
  sourceHeader: string;
  rawValue: string;
  rawValueHash: string;
  normalizedCandidates: readonly string[];
  stateCandidate: "new_tooling" | null;
  transformationKey: string;
  findings: readonly ToolingImportFieldFinding[];
}

export interface ToolingImportPreviewRow {
  worksheetName: string;
  sourceRow: number;
  action: "create" | "update" | "skip" | "blocked";
  fields: readonly ToolingImportTransformedField[];
  reasonCodes: readonly string[];
  requiresConfirmation: boolean;
}

export interface ToolingImportConfirmation {
  kind: "image_anchor" | "relationship";
  worksheetName: string;
  sourceRow: number;
  anchorKey: string | null;
  selectedTargetObject: "part_revision" | "tooling_master";
  selectedTargetGlobalId: string;
  selectedTargetSnapshotHash: string;
  reason: string;
  confirmedByUserId: string;
  confirmedAt: string;
}

export interface ToolingImportPreviewRevision {
  schemaVersion: "tooling-import.v1";
  transformationPolicyVersion: "tooling-list-transform.v1";
  globalId: string;
  previewGlobalId: string;
  previewVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  batchGlobalId: string;
  sourceSnapshotHash: string;
  inspectionGlobalId: string;
  inspectionSnapshotHash: string;
  mappingGlobalId: string;
  mappingSnapshotHash: string;
  mappingState: "proposal" | "approved_fixture";
  executionEligible: boolean;
  rows: readonly ToolingImportPreviewRow[];
  confirmations: readonly ToolingImportConfirmation[];
  createdAt: string;
  snapshotHash: string;
}

export type ToolingImportJobState =
  | "queued"
  | "processing"
  | "partially_succeeded"
  | "succeeded"
  | "failed_retryable"
  | "failed_final"
  | "rolled_back"
  | "rollback_denied";

export interface ToolingImportFieldResult {
  sourceOrdinal: number;
  sourceHeader: string;
  resultCode: string;
  message: string;
  targetField: string | null;
}

export interface ToolingImportRowResult {
  globalId: string;
  worksheetName: string;
  sourceRow: number;
  attempt: number;
  state:
    | "created"
    | "updated"
    | "skipped"
    | "failed_retryable"
    | "failed_final"
    | "confirmation_required";
  targetObjectType: string | null;
  targetGlobalId: string | null;
  targetSnapshotHash: string | null;
  fieldResults: readonly ToolingImportFieldResult[];
  traceId: string;
}

export interface ToolingImportCorrectionArtifact {
  schemaVersion: "tooling-import-correction.v1";
  globalId: string;
  batchGlobalId: string;
  jobGlobalId: string;
  jobSnapshotHash: string;
  frappeFileId: string;
  fileName: string;
  mimeType: "text/csv";
  sizeBytes: number;
  sha256: string;
  entryCount: number;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface ToolingImportReconciliationItem {
  rowResultGlobalId: string;
  targetObjectType: string;
  targetGlobalId: string;
  expectedSnapshotHash: string;
  observedSnapshotHash: string | null;
  downstreamReferenceCount: number;
  state: "matched" | "missing" | "changed" | "downstream_used" | "rolled_back";
}

export interface ToolingImportReconciliationRevision {
  schemaVersion: "tooling-import-reconciliation.v1";
  globalId: string;
  jobGlobalId: string;
  jobSnapshotHash: string;
  kind: "reconciliation" | "rollback_eligibility" | "rollback_result";
  items: readonly ToolingImportReconciliationItem[];
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface ToolingImportJobSnapshot {
  schemaVersion: "tooling-import.v1";
  globalId: string;
  batchGlobalId: string;
  previewGlobalId: string;
  previewSnapshotHash: string;
  attempt: number;
  state: ToolingImportJobState;
  counts: Readonly<{
    created: number;
    updated: number;
    skipped: number;
    failed_retryable: number;
    failed_final: number;
    confirmation_required: number;
  }>;
  rowResults: readonly ToolingImportRowResult[];
  queuedAt: string;
  updatedAt: string;
  correctionArtifactGlobalId: string | null;
  correctionArtifactSnapshotHash: string | null;
  failure: Readonly<{ code: string; message: string; traceId: string }> | null;
  optimisticVersion: number;
  snapshotHash: string;
  correctionArtifacts?: readonly ToolingImportCorrectionArtifact[];
  reconciliations?: readonly ToolingImportReconciliationRevision[];
}

export interface ToolingImportBatchCollection {
  projectGlobalId: string;
  permissions: ToolingImportPermissions;
  mappingAuthority: ToolingImportMappingAuthority;
  batches: readonly ToolingImportSource[];
}

export interface ToolingImportBatchDetail {
  projectGlobalId: string;
  permissions: ToolingImportPermissions;
  mappingAuthority: ToolingImportMappingAuthority;
  batch: ToolingImportSource;
  inspections: readonly ToolingImportInspectionRevision[];
  mappingProposals: readonly ToolingImportMappingRevision[];
  previews: readonly ToolingImportPreviewRevision[];
  jobs: readonly ToolingImportJobSnapshot[];
}

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function keys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = [],
): boolean {
  const allowed = new Set([...required, ...optional]);
  return (
    required.every((key) => Object.prototype.hasOwnProperty.call(value, key)) &&
    Object.keys(value).every((key) => allowed.has(key))
  );
}

function string(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum
  );
}

function integer(
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

function uuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function hash(value: unknown): value is string {
  return typeof value === "string" && hashPattern.test(value);
}

function timestamp(value: unknown): value is string {
  return (
    string(value, 20, 64) &&
    /(?:Z|[+-]\d{2}:\d{2})$/u.test(value) &&
    !Number.isNaN(Date.parse(value))
  );
}

function nullable<T>(
  value: unknown,
  accept: (candidate: unknown) => candidate is T,
): value is T | null {
  return value === null || accept(value);
}

function array<T>(
  value: unknown,
  maximum: number,
  accept: (candidate: unknown) => candidate is T,
  minimum = 0,
): value is T[] {
  return (
    Array.isArray(value) &&
    value.length >= minimum &&
    value.length <= maximum &&
    value.every(accept)
  );
}

function uniqueStrings(value: unknown, maximum: number): value is string[] {
  return (
    array(value, maximum, (item): item is string => typeof item === "string") &&
    new Set(value).size === value.length
  );
}

export function isToolingImportPermissions(
  value: unknown,
): value is ToolingImportPermissions {
  if (!record(value)) return false;
  const names = [
    "view",
    "registerSource",
    "inspect",
    "createMappingProposal",
    "createPreview",
    "confirmPreview",
    "activateProductionMapping",
    "execute",
    "retry",
    "createCorrectionArtifact",
    "downloadCorrectionArtifact",
    "reconcile",
    "evaluateRollback",
    "rollback",
  ] as const;
  return (
    keys(value, names) &&
    names.every((name) => typeof value[name] === "boolean") &&
    value.view === true &&
    value.activateProductionMapping === false
  );
}

export function isToolingImportMappingAuthority(
  value: unknown,
): value is ToolingImportMappingAuthority {
  if (!record(value) || typeof value.state !== "string") return false;
  if (value.state === "unavailable") {
    return (
      keys(value, ["state", "reasonCode"]) &&
      value.reasonCode === "production_mapping_unavailable"
    );
  }
  return (
    value.state === "approved_fixture" &&
    keys(value, [
      "state",
      "reasonCode",
      "mappingRevisionGlobalId",
      "mappingSnapshotHash",
      "activationGlobalId",
      "activationSnapshotHash",
    ]) &&
    value.reasonCode === "synthetic_fixture_scope_only" &&
    uuid(value.mappingRevisionGlobalId) &&
    hash(value.mappingSnapshotHash) &&
    uuid(value.activationGlobalId) &&
    hash(value.activationSnapshotHash)
  );
}

export function isToolingImportSource(
  value: unknown,
): value is ToolingImportSource {
  if (!record(value)) return false;
  const required = [
    "schemaVersion",
    "batchGlobalId",
    "tenantId",
    "projectGlobalId",
    "customerScopeId",
    "fileRevisionGlobalId",
    "fileOptimisticVersion",
    "frappeContentHash",
    "fileName",
    "mimeType",
    "sizeBytes",
    "sha256",
    "createdByUserId",
    "createdAt",
    "requestId",
    "traceId",
    "snapshotHash",
  ];
  return (
    keys(value, required) &&
    value.schemaVersion === "tooling-import.v1" &&
    uuid(value.batchGlobalId) &&
    string(value.tenantId, 1, 128) &&
    uuid(value.projectGlobalId) &&
    string(value.customerScopeId, 1, 128) &&
    uuid(value.fileRevisionGlobalId) &&
    integer(value.fileOptimisticVersion, 1) &&
    string(value.frappeContentHash, 32, 128) &&
    string(value.fileName, 6, 255) &&
    !/[\\/]/u.test(value.fileName) &&
    /[.]xlsx$/iu.test(value.fileName) &&
    (value.mimeType ===
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
      value.mimeType === "application/octet-stream") &&
    integer(value.sizeBytes, 1, 100_000_000) &&
    hash(value.sha256) &&
    string(value.createdByUserId, 1, 254) &&
    timestamp(value.createdAt) &&
    uuid(value.requestId) &&
    string(value.traceId, 1, 128) &&
    hash(value.snapshotHash)
  );
}

function isColumn(value: unknown): value is ToolingImportDetectedColumn {
  return (
    record(value) &&
    keys(value, ["ordinal", "sourceHeader", "headerCell"]) &&
    integer(value.ordinal, 1, 16_384) &&
    string(value.sourceHeader, 1, 500) &&
    typeof value.headerCell === "string" &&
    cellPattern.test(value.headerCell)
  );
}

function isRegion(value: unknown): value is ToolingImportDetectedRegion {
  const kinds = new Set([
    "title",
    "header",
    "data",
    "shared_tooling_marker",
    "shared_tooling_data",
    "summary",
    "section",
  ]);
  return (
    record(value) &&
    keys(value, [
      "kind",
      "firstRow",
      "lastRow",
      "evidence",
      "requiresConfirmation",
    ]) &&
    typeof value.kind === "string" &&
    kinds.has(value.kind) &&
    integer(value.firstRow, 1, 1_048_576) &&
    integer(value.lastRow, value.firstRow, 1_048_576) &&
    string(value.evidence, 1, 500) &&
    typeof value.requiresConfirmation === "boolean"
  );
}

function isFormulaError(
  value: unknown,
): value is { cell: string; errorCode: string } {
  return (
    record(value) &&
    keys(value, ["cell", "errorCode"]) &&
    typeof value.cell === "string" &&
    cellPattern.test(value.cell) &&
    string(value.errorCode, 2, 32)
  );
}

function isImageAnchor(
  value: unknown,
): value is ToolingImportInspectionRevision["imageAnchors"][number] {
  return (
    record(value) &&
    keys(value, [
      "anchorKey",
      "row",
      "column",
      "confidence",
      "candidateSourceRow",
      "requiresConfirmation",
    ]) &&
    string(value.anchorKey, 1, 128) &&
    nullable(value.row, (item): item is number =>
      integer(item, 1, 1_048_576),
    ) &&
    nullable(value.column, (item): item is number =>
      integer(item, 1, 16_384),
    ) &&
    (value.confidence === "high" || value.confidence === "ambiguous") &&
    nullable(value.candidateSourceRow, (item): item is number =>
      integer(item, 1, 1_048_576),
    ) &&
    typeof value.requiresConfirmation === "boolean"
  );
}

export function isToolingImportInspection(
  value: unknown,
): value is ToolingImportInspectionRevision {
  if (!record(value)) return false;
  const required = [
    "schemaVersion",
    "inspectionPolicyVersion",
    "detectionPolicyVersion",
    "globalId",
    "batchGlobalId",
    "sourceSnapshotHash",
    "inspectionVersion",
    "worksheetName",
    "headerRow",
    "sourceSignature",
    "columns",
    "regions",
    "formulaErrors",
    "imageAnchors",
    "passiveReportHash",
    "createdAt",
    "snapshotHash",
  ];
  return (
    keys(value, required) &&
    value.schemaVersion === "tooling-import.v1" &&
    value.inspectionPolicyVersion === "tooling-xlsx-inspection.v1" &&
    value.detectionPolicyVersion === "tooling-list-detection.v1" &&
    uuid(value.globalId) &&
    uuid(value.batchGlobalId) &&
    hash(value.sourceSnapshotHash) &&
    integer(value.inspectionVersion, 1) &&
    string(value.worksheetName, 1, 255) &&
    integer(value.headerRow, 1, 1_048_576) &&
    hash(value.sourceSignature) &&
    array(value.columns, 16_384, isColumn, 1) &&
    array(value.regions, 10_000, isRegion, 2) &&
    array(value.formulaErrors, 100_000, isFormulaError) &&
    array(value.imageAnchors, 100_000, isImageAnchor) &&
    hash(value.passiveReportHash) &&
    timestamp(value.createdAt) &&
    hash(value.snapshotHash)
  );
}

function isMappingEntry(value: unknown): value is ToolingImportMappingEntry {
  const semantics = new Set([
    "unclassified",
    "identity",
    "descriptive",
    "legacy_grade",
    "relation_candidate",
    "calculated_unverified",
  ]);
  return (
    record(value) &&
    keys(value, [
      "sourceOrdinal",
      "sourceHeader",
      "disposition",
      "targetObjectCandidate",
      "targetFieldCandidate",
      "semanticClassification",
      "transformationKey",
      "validationRuleKeys",
    ]) &&
    integer(value.sourceOrdinal, 1, 16_384) &&
    string(value.sourceHeader, 1, 500) &&
    (value.disposition === "candidate" || value.disposition === "unmapped") &&
    nullable(value.targetObjectCandidate, (item): item is string =>
      string(item, 1, 255),
    ) &&
    nullable(value.targetFieldCandidate, (item): item is string =>
      string(item, 1, 255),
    ) &&
    typeof value.semanticClassification === "string" &&
    semantics.has(value.semanticClassification) &&
    typeof value.transformationKey === "string" &&
    keyPattern.test(value.transformationKey) &&
    uniqueStrings(value.validationRuleKeys, 32) &&
    value.validationRuleKeys.every((item) => keyPattern.test(item))
  );
}

export function isToolingImportMapping(
  value: unknown,
): value is ToolingImportMappingRevision {
  if (!record(value)) return false;
  const required = [
    "schemaVersion",
    "globalId",
    "mappingGlobalId",
    "batchGlobalId",
    "sourceSnapshotHash",
    "inspectionGlobalId",
    "inspectionSnapshotHash",
    "mappingVersion",
    "state",
    "customerScopeId",
    "templateKey",
    "sourceSignature",
    "entries",
    "reason",
    "createdByUserId",
    "createdAt",
    "snapshotHash",
  ];
  return (
    keys(value, required) &&
    value.schemaVersion === "tooling-import.v1" &&
    uuid(value.globalId) &&
    uuid(value.mappingGlobalId) &&
    uuid(value.batchGlobalId) &&
    hash(value.sourceSnapshotHash) &&
    uuid(value.inspectionGlobalId) &&
    hash(value.inspectionSnapshotHash) &&
    integer(value.mappingVersion, 1) &&
    (value.state === "proposal" || value.state === "approved_fixture") &&
    string(value.customerScopeId, 1, 128) &&
    typeof value.templateKey === "string" &&
    keyPattern.test(value.templateKey) &&
    hash(value.sourceSignature) &&
    array(value.entries, 16_384, isMappingEntry, 1) &&
    string(value.reason, 1, 1000) &&
    string(value.createdByUserId, 1, 254) &&
    timestamp(value.createdAt) &&
    hash(value.snapshotHash)
  );
}

function isFinding(value: unknown): value is ToolingImportFieldFinding {
  return (
    record(value) &&
    keys(value, ["code", "severity", "message"]) &&
    typeof value.code === "string" &&
    keyPattern.test(value.code) &&
    (value.severity === "warning" ||
      value.severity === "error" ||
      value.severity === "confirmation_required") &&
    string(value.message, 1, 1000)
  );
}

function isTransformedField(
  value: unknown,
): value is ToolingImportTransformedField {
  return (
    record(value) &&
    keys(value, [
      "sourceOrdinal",
      "sourceHeader",
      "rawValue",
      "rawValueHash",
      "normalizedCandidates",
      "stateCandidate",
      "transformationKey",
      "findings",
    ]) &&
    integer(value.sourceOrdinal, 1, 16_384) &&
    string(value.sourceHeader, 1, 500) &&
    string(value.rawValue, 0, 32_767) &&
    hash(value.rawValueHash) &&
    array(value.normalizedCandidates, 100, (item): item is string =>
      string(item, 0, 32_767),
    ) &&
    (value.stateCandidate === null || value.stateCandidate === "new_tooling") &&
    typeof value.transformationKey === "string" &&
    keyPattern.test(value.transformationKey) &&
    array(value.findings, 100, isFinding)
  );
}

function isPreviewRow(value: unknown): value is ToolingImportPreviewRow {
  return (
    record(value) &&
    keys(value, [
      "worksheetName",
      "sourceRow",
      "action",
      "fields",
      "reasonCodes",
      "requiresConfirmation",
    ]) &&
    string(value.worksheetName, 1, 255) &&
    integer(value.sourceRow, 1, 1_048_576) &&
    (value.action === "create" ||
      value.action === "update" ||
      value.action === "skip" ||
      value.action === "blocked") &&
    array(value.fields, 16_384, isTransformedField, 1) &&
    uniqueStrings(value.reasonCodes, 1000) &&
    value.reasonCodes.every((item) => keyPattern.test(item)) &&
    typeof value.requiresConfirmation === "boolean"
  );
}

function isConfirmation(value: unknown): value is ToolingImportConfirmation {
  return (
    record(value) &&
    keys(value, [
      "kind",
      "worksheetName",
      "sourceRow",
      "anchorKey",
      "selectedTargetObject",
      "selectedTargetGlobalId",
      "selectedTargetSnapshotHash",
      "reason",
      "confirmedByUserId",
      "confirmedAt",
    ]) &&
    (value.kind === "image_anchor" || value.kind === "relationship") &&
    string(value.worksheetName, 1, 255) &&
    integer(value.sourceRow, 1, 1_048_576) &&
    nullable(
      value.anchorKey,
      (item): item is string =>
        typeof item === "string" && keyPattern.test(item),
    ) &&
    (value.selectedTargetObject === "part_revision" ||
      value.selectedTargetObject === "tooling_master") &&
    uuid(value.selectedTargetGlobalId) &&
    hash(value.selectedTargetSnapshotHash) &&
    string(value.reason, 1, 1000) &&
    string(value.confirmedByUserId, 1, 254) &&
    timestamp(value.confirmedAt)
  );
}

export function isToolingImportPreview(
  value: unknown,
): value is ToolingImportPreviewRevision {
  if (!record(value)) return false;
  const required = [
    "schemaVersion",
    "transformationPolicyVersion",
    "globalId",
    "previewGlobalId",
    "previewVersion",
    "predecessorGlobalId",
    "predecessorSnapshotHash",
    "batchGlobalId",
    "sourceSnapshotHash",
    "inspectionGlobalId",
    "inspectionSnapshotHash",
    "mappingGlobalId",
    "mappingSnapshotHash",
    "mappingState",
    "executionEligible",
    "rows",
    "confirmations",
    "createdAt",
    "snapshotHash",
  ];
  return (
    keys(value, required) &&
    value.schemaVersion === "tooling-import.v1" &&
    value.transformationPolicyVersion === "tooling-list-transform.v1" &&
    uuid(value.globalId) &&
    uuid(value.previewGlobalId) &&
    integer(value.previewVersion, 1) &&
    nullable(value.predecessorGlobalId, uuid) &&
    nullable(value.predecessorSnapshotHash, hash) &&
    uuid(value.batchGlobalId) &&
    hash(value.sourceSnapshotHash) &&
    uuid(value.inspectionGlobalId) &&
    hash(value.inspectionSnapshotHash) &&
    uuid(value.mappingGlobalId) &&
    hash(value.mappingSnapshotHash) &&
    (value.mappingState === "proposal" ||
      value.mappingState === "approved_fixture") &&
    typeof value.executionEligible === "boolean" &&
    array(value.rows, 100_000, isPreviewRow, 1) &&
    array(value.confirmations, 1000, isConfirmation) &&
    timestamp(value.createdAt) &&
    hash(value.snapshotHash)
  );
}

function isFieldResult(value: unknown): value is ToolingImportFieldResult {
  return (
    record(value) &&
    keys(value, [
      "sourceOrdinal",
      "sourceHeader",
      "resultCode",
      "message",
      "targetField",
    ]) &&
    integer(value.sourceOrdinal, 1, 16_384) &&
    string(value.sourceHeader, 1, 500) &&
    typeof value.resultCode === "string" &&
    keyPattern.test(value.resultCode) &&
    string(value.message, 1, 1000) &&
    nullable(value.targetField, (item): item is string => string(item, 1, 255))
  );
}

function isRowResult(value: unknown): value is ToolingImportRowResult {
  const states = new Set([
    "created",
    "updated",
    "skipped",
    "failed_retryable",
    "failed_final",
    "confirmation_required",
  ]);
  return (
    record(value) &&
    keys(value, [
      "globalId",
      "worksheetName",
      "sourceRow",
      "attempt",
      "state",
      "targetObjectType",
      "targetGlobalId",
      "targetSnapshotHash",
      "fieldResults",
      "traceId",
    ]) &&
    uuid(value.globalId) &&
    string(value.worksheetName, 1, 255) &&
    integer(value.sourceRow, 1, 1_048_576) &&
    integer(value.attempt, 1) &&
    typeof value.state === "string" &&
    states.has(value.state) &&
    nullable(
      value.targetObjectType,
      (item): item is string =>
        typeof item === "string" && keyPattern.test(item),
    ) &&
    nullable(value.targetGlobalId, uuid) &&
    nullable(value.targetSnapshotHash, hash) &&
    array(value.fieldResults, 16_384, isFieldResult, 1) &&
    string(value.traceId, 1, 128)
  );
}

export function isToolingImportCorrectionArtifact(
  value: unknown,
): value is ToolingImportCorrectionArtifact {
  if (!record(value)) return false;
  const required = [
    "schemaVersion",
    "globalId",
    "batchGlobalId",
    "jobGlobalId",
    "jobSnapshotHash",
    "frappeFileId",
    "fileName",
    "mimeType",
    "sizeBytes",
    "sha256",
    "entryCount",
    "createdByUserId",
    "createdAt",
    "requestId",
    "traceId",
    "snapshotHash",
  ];
  return (
    keys(value, required) &&
    value.schemaVersion === "tooling-import-correction.v1" &&
    uuid(value.globalId) &&
    uuid(value.batchGlobalId) &&
    uuid(value.jobGlobalId) &&
    hash(value.jobSnapshotHash) &&
    string(value.frappeFileId, 1, 140) &&
    string(value.fileName, 1, 255) &&
    value.mimeType === "text/csv" &&
    integer(value.sizeBytes, 1) &&
    hash(value.sha256) &&
    integer(value.entryCount, 1, 5000) &&
    string(value.createdByUserId, 1, 254) &&
    timestamp(value.createdAt) &&
    uuid(value.requestId) &&
    string(value.traceId, 1, 128) &&
    hash(value.snapshotHash)
  );
}

function isReconciliationItem(
  value: unknown,
): value is ToolingImportReconciliationItem {
  const states = new Set([
    "matched",
    "missing",
    "changed",
    "downstream_used",
    "rolled_back",
  ]);
  return (
    record(value) &&
    keys(value, [
      "rowResultGlobalId",
      "targetObjectType",
      "targetGlobalId",
      "expectedSnapshotHash",
      "observedSnapshotHash",
      "downstreamReferenceCount",
      "state",
    ]) &&
    uuid(value.rowResultGlobalId) &&
    typeof value.targetObjectType === "string" &&
    keyPattern.test(value.targetObjectType) &&
    uuid(value.targetGlobalId) &&
    hash(value.expectedSnapshotHash) &&
    nullable(value.observedSnapshotHash, hash) &&
    integer(value.downstreamReferenceCount, 0) &&
    typeof value.state === "string" &&
    states.has(value.state)
  );
}

export function isToolingImportReconciliation(
  value: unknown,
): value is ToolingImportReconciliationRevision {
  if (!record(value)) return false;
  const required = [
    "schemaVersion",
    "globalId",
    "jobGlobalId",
    "jobSnapshotHash",
    "kind",
    "items",
    "createdByUserId",
    "createdAt",
    "requestId",
    "traceId",
    "snapshotHash",
  ];
  return (
    keys(value, required) &&
    value.schemaVersion === "tooling-import-reconciliation.v1" &&
    uuid(value.globalId) &&
    uuid(value.jobGlobalId) &&
    hash(value.jobSnapshotHash) &&
    (value.kind === "reconciliation" ||
      value.kind === "rollback_eligibility" ||
      value.kind === "rollback_result") &&
    array(value.items, 100_000, isReconciliationItem) &&
    string(value.createdByUserId, 1, 254) &&
    timestamp(value.createdAt) &&
    uuid(value.requestId) &&
    string(value.traceId, 1, 128) &&
    hash(value.snapshotHash)
  );
}

function isCounts(value: unknown): value is ToolingImportJobSnapshot["counts"] {
  if (!record(value)) return false;
  const names = [
    "created",
    "updated",
    "skipped",
    "failed_retryable",
    "failed_final",
    "confirmation_required",
  ] as const;
  return keys(value, names) && names.every((name) => integer(value[name], 0));
}

function isFailure(
  value: unknown,
): value is NonNullable<ToolingImportJobSnapshot["failure"]> {
  return (
    record(value) &&
    keys(value, ["code", "message", "traceId"]) &&
    typeof value.code === "string" &&
    keyPattern.test(value.code) &&
    string(value.message, 1, 1000) &&
    string(value.traceId, 1, 128)
  );
}

export function isToolingImportJob(
  value: unknown,
): value is ToolingImportJobSnapshot {
  if (!record(value)) return false;
  const required = [
    "schemaVersion",
    "globalId",
    "batchGlobalId",
    "previewGlobalId",
    "previewSnapshotHash",
    "attempt",
    "state",
    "counts",
    "rowResults",
    "queuedAt",
    "updatedAt",
    "correctionArtifactGlobalId",
    "correctionArtifactSnapshotHash",
    "failure",
    "optimisticVersion",
    "snapshotHash",
  ];
  const states = new Set([
    "queued",
    "processing",
    "partially_succeeded",
    "succeeded",
    "failed_retryable",
    "failed_final",
    "rolled_back",
    "rollback_denied",
  ]);
  return (
    keys(value, required, ["correctionArtifacts", "reconciliations"]) &&
    value.schemaVersion === "tooling-import.v1" &&
    uuid(value.globalId) &&
    uuid(value.batchGlobalId) &&
    uuid(value.previewGlobalId) &&
    hash(value.previewSnapshotHash) &&
    integer(value.attempt, 1) &&
    typeof value.state === "string" &&
    states.has(value.state) &&
    isCounts(value.counts) &&
    array(value.rowResults, 100_000, isRowResult) &&
    timestamp(value.queuedAt) &&
    timestamp(value.updatedAt) &&
    nullable(value.correctionArtifactGlobalId, uuid) &&
    nullable(value.correctionArtifactSnapshotHash, hash) &&
    nullable(value.failure, isFailure) &&
    integer(value.optimisticVersion, 1) &&
    hash(value.snapshotHash) &&
    (value.correctionArtifacts === undefined ||
      array(
        value.correctionArtifacts,
        500,
        isToolingImportCorrectionArtifact,
      )) &&
    (value.reconciliations === undefined ||
      array(value.reconciliations, 1000, isToolingImportReconciliation))
  );
}

export function isToolingImportBatchCollection(
  value: unknown,
): value is ToolingImportBatchCollection {
  return (
    record(value) &&
    keys(value, [
      "projectGlobalId",
      "permissions",
      "mappingAuthority",
      "batches",
    ]) &&
    uuid(value.projectGlobalId) &&
    isToolingImportPermissions(value.permissions) &&
    isToolingImportMappingAuthority(value.mappingAuthority) &&
    array(value.batches, 200, isToolingImportSource) &&
    value.batches.every(
      (item) => item.projectGlobalId === value.projectGlobalId,
    )
  );
}

export function isToolingImportBatchDetail(
  value: unknown,
): value is ToolingImportBatchDetail {
  if (
    !record(value) ||
    !keys(value, [
      "projectGlobalId",
      "permissions",
      "mappingAuthority",
      "batch",
      "inspections",
      "mappingProposals",
      "previews",
      "jobs",
    ]) ||
    !uuid(value.projectGlobalId) ||
    !isToolingImportPermissions(value.permissions) ||
    !isToolingImportMappingAuthority(value.mappingAuthority) ||
    !isToolingImportSource(value.batch)
  )
    return false;
  const batchGlobalId = value.batch.batchGlobalId;
  return (
    value.batch.projectGlobalId === value.projectGlobalId &&
    array(value.inspections, 500, isToolingImportInspection) &&
    value.inspections.every((item) => item.batchGlobalId === batchGlobalId) &&
    array(value.mappingProposals, 500, isToolingImportMapping) &&
    value.mappingProposals.every(
      (item) => item.batchGlobalId === batchGlobalId,
    ) &&
    array(value.previews, 500, isToolingImportPreview) &&
    value.previews.every((item) => item.batchGlobalId === batchGlobalId) &&
    array(value.jobs, 500, isToolingImportJob) &&
    value.jobs.every((item) => item.batchGlobalId === batchGlobalId)
  );
}

export function isToolingImportBatchCommand(value: unknown): value is {
  batch: ToolingImportSource;
  mappingAuthority: ToolingImportMappingAuthority;
} {
  return (
    record(value) &&
    keys(value, ["batch", "mappingAuthority"]) &&
    isToolingImportSource(value.batch) &&
    isToolingImportMappingAuthority(value.mappingAuthority)
  );
}

export function isToolingImportInspectionCommand(
  value: unknown,
): value is { inspection: ToolingImportInspectionRevision } {
  return (
    record(value) &&
    keys(value, ["inspection"]) &&
    isToolingImportInspection(value.inspection)
  );
}

export function isToolingImportMappingCommand(value: unknown): value is {
  mappingProposal: ToolingImportMappingRevision;
  mappingAuthority: ToolingImportMappingAuthority;
} {
  return (
    record(value) &&
    keys(value, ["mappingProposal", "mappingAuthority"]) &&
    isToolingImportMapping(value.mappingProposal) &&
    isToolingImportMappingAuthority(value.mappingAuthority)
  );
}

export function isToolingImportPreviewCommand(value: unknown): value is {
  preview: ToolingImportPreviewRevision;
  mappingAuthority: ToolingImportMappingAuthority;
} {
  return (
    record(value) &&
    keys(value, ["preview", "mappingAuthority"]) &&
    isToolingImportPreview(value.preview) &&
    isToolingImportMappingAuthority(value.mappingAuthority)
  );
}

export function isToolingImportJobCommand(
  value: unknown,
): value is { job: ToolingImportJobSnapshot } {
  return record(value) && keys(value, ["job"]) && isToolingImportJob(value.job);
}

export function isToolingImportCorrectionCommand(
  value: unknown,
): value is { correctionArtifact: ToolingImportCorrectionArtifact } {
  return (
    record(value) &&
    keys(value, ["correctionArtifact"]) &&
    isToolingImportCorrectionArtifact(value.correctionArtifact)
  );
}

export function isToolingImportReconciliationCommand(
  value: unknown,
): value is { reconciliation: ToolingImportReconciliationRevision } {
  return (
    record(value) &&
    keys(value, ["reconciliation"]) &&
    isToolingImportReconciliation(value.reconciliation)
  );
}

export function isToolingImportEligibilityCommand(
  value: unknown,
): value is { rollbackEligibility: ToolingImportReconciliationRevision } {
  return (
    record(value) &&
    keys(value, ["rollbackEligibility"]) &&
    isToolingImportReconciliation(value.rollbackEligibility) &&
    value.rollbackEligibility.kind === "rollback_eligibility"
  );
}

export function isToolingImportRollbackCommand(value: unknown): value is {
  job: ToolingImportJobSnapshot;
  rollback: ToolingImportReconciliationRevision;
} {
  return (
    record(value) &&
    keys(value, ["job", "rollback"]) &&
    isToolingImportJob(value.job) &&
    isToolingImportReconciliation(value.rollback) &&
    value.rollback.kind === "rollback_result" &&
    value.job.globalId === value.rollback.jobGlobalId
  );
}
