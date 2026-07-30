import { NpiHttpClient, NpiTransportError } from "./http";

export type DocumentLifecycleState =
  | "draft"
  | "proposed"
  | "active"
  | "on_hold"
  | "completed"
  | "cancelled";
export type DocumentCapabilityState = "available" | "unavailable" | "blocked";
export type DocumentRelationshipKind =
  | "project"
  | "project_reference"
  | "gate"
  | "wbs_item"
  | "domain_work_item";
export type DocumentProjectReferenceType =
  | "customer"
  | "product"
  | "part"
  | "tooling"
  | "order";
export type DocumentSourceSystem = "NPI_ONE" | "ERPNEXT";

export interface DocumentProjectViewModel {
  globalId: string;
  businessCode: string;
  title: string;
  lifecycleState: DocumentLifecycleState;
  optimisticVersion: number;
}

export interface DocumentPermissionsViewModel {
  view: boolean;
  create: boolean;
  revise: boolean;
  lock: boolean;
  recoverLock: boolean;
  preview: boolean;
  download: boolean;
  share: false;
  review: false;
  release: false;
}

export interface DocumentTypeOptionViewModel {
  key: string;
  prefix: string;
  titleSource: string;
}

export interface DocumentPolicyOptionViewModel {
  globalId: string;
  versionId: string;
  version: number;
  snapshotHash: string;
  key: string;
  title: string;
  documentTypes: readonly DocumentTypeOptionViewModel[];
  confidentialityKeys: readonly string[];
  allowedMimeTypes: readonly string[];
  previewMimeTypes: readonly string[];
  maximumFileBytes: number;
  lockLeaseMinutes: number;
}

export interface DocumentPolicyReferenceViewModel {
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface CurrentDocumentRevisionViewModel {
  globalId: string;
  major: number;
  minor: number;
  snapshotHash: string;
}

export interface CurrentDocumentLockViewModel {
  globalId: string;
  version: number;
  holderUserId: string;
  expiresAt: string;
}

export interface ControlledDocumentSummaryViewModel {
  globalId: string;
  documentNumber: string;
  documentTypeKey: string;
  title: string;
  confidentialityKey: string;
  documentPolicyRef: DocumentPolicyReferenceViewModel;
  currentRevision: CurrentDocumentRevisionViewModel | null;
  currentLock: CurrentDocumentLockViewModel | null;
  source: Readonly<{
    sourceSystem: "NPI_ONE";
    editableIn: "NPI_ONE";
    syncState: "local";
  }>;
  optimisticVersion: number;
}

export interface ControlledDocumentPageViewModel {
  project: DocumentProjectViewModel;
  permissions: DocumentPermissionsViewModel;
  policies: readonly DocumentPolicyOptionViewModel[];
  items: readonly ControlledDocumentSummaryViewModel[];
  nextCursor: string | null;
}

export interface DocumentCapabilityViewModel {
  state: DocumentCapabilityState;
  reasonCode: string;
}

export interface DocumentPreviewCapabilityViewModel extends DocumentCapabilityViewModel {
  mode: "native_pdf" | "native_image" | "none";
}

export interface DocumentFileCapabilitiesViewModel {
  integrity: DocumentCapabilityViewModel;
  preview: DocumentPreviewCapabilityViewModel;
  download: DocumentCapabilityViewModel;
  externalRetrieval: Readonly<{
    state: "unavailable";
    reasonCode: "external_access_policy_unavailable";
  }>;
  connector: Readonly<{
    state: "unavailable" | "failed";
    reasonCode: string;
  }>;
}

export interface DocumentFileMetadataViewModel {
  globalId: string;
  fileDocumentId: string;
  revision: number;
  optimisticVersion: number;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  sha256: string;
  scanState: "pending" | "clean" | "infected" | "failed";
  scanObservedAt: string | null;
  private: true;
  released: boolean;
}

export interface DocumentRevisionFileViewModel extends DocumentFileMetadataViewModel {
  associationId: string;
  role: "primary" | "source" | "derivative";
  provenance: string;
  connector: Readonly<{
    state: "unavailable" | "failed";
    reasonCode: string;
  }>;
  capabilities: DocumentFileCapabilitiesViewModel;
}

export interface DocumentRevisionViewModel {
  globalId: string;
  major: number;
  minor: number;
  state: "draft";
  reason: string;
  effectiveDate: string | null;
  predecessorRevisionId: string | null;
  snapshotHash: string;
  optimisticVersion: number;
  createdByUserId: string;
  createdAt: string;
  files: readonly DocumentRevisionFileViewModel[];
}

export interface DocumentRelationshipViewModel {
  globalId: string;
  kind: DocumentRelationshipKind;
  projectReferenceType: DocumentProjectReferenceType | null;
  targetSourceSystem: DocumentSourceSystem | null;
  targetReferenceGlobalId: string | null;
  targetIdentity: string;
  targetVersion: number;
  snapshotHash: string;
}

export interface DocumentLockEventViewModel {
  globalId: string;
  lockId: string;
  version: number;
  eventType: "acquired" | "released" | "recovered" | "expired";
  holderUserId: string;
  actorUserId: string;
  acquiredAt: string;
  expiresAt: string;
  occurredAt: string;
  reason: string | null;
  snapshotHash: string;
}

export interface ControlledDocumentWorkspaceViewModel {
  project: DocumentProjectViewModel;
  permissions: DocumentPermissionsViewModel;
  document: ControlledDocumentSummaryViewModel;
  revisions: readonly DocumentRevisionViewModel[];
  relationships: readonly DocumentRelationshipViewModel[];
  lockHistory: readonly DocumentLockEventViewModel[];
  externalRetrieval: Readonly<{
    state: "unavailable";
    reasonCode: "external_access_policy_unavailable";
  }>;
}

export interface DocumentFileCapabilityResultViewModel {
  projectId: string;
  documentId: string;
  revisionId: string;
  fileRevisionId: string;
  file: DocumentFileMetadataViewModel;
  capabilities: DocumentFileCapabilitiesViewModel;
}

export interface DocumentCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface DocumentObjectRelationshipInput {
  kind: Exclude<DocumentRelationshipKind, "project_reference">;
  targetIdentity: string;
  targetVersion: number;
}

export interface DocumentProjectReferenceInput {
  kind: "project_reference";
  targetIdentity: string;
  targetVersion: number;
  projectReferenceType: DocumentProjectReferenceType;
  targetSourceSystem: DocumentSourceSystem;
  targetReferenceGlobalId: string | null;
}

export type DocumentRelationshipInput =
  | DocumentObjectRelationshipInput
  | DocumentProjectReferenceInput;

export interface CreateControlledDocumentCommand {
  policyGlobalId: string;
  policyVersion: number;
  policySnapshotHash: string;
  documentTypeKey: string;
  title: string;
  confidentialityKey: string;
  objectLinks: readonly DocumentRelationshipInput[];
}

export interface CreateDocumentRevisionCommand {
  expectedDocumentVersion: number;
  expectedLockVersion: number;
  major: number;
  minor: number;
  reason: string;
  effectiveDate: string | null;
  predecessorRevisionId: string | null;
  file: File;
}

export interface DocumentListQuery {
  limit?: number | undefined;
  cursor?: string | undefined;
  relationshipKind?: DocumentRelationshipKind | undefined;
  targetIdentity?: string | undefined;
  targetVersion?: number | undefined;
  projectReferenceType?: DocumentProjectReferenceType | undefined;
  targetSourceSystem?: DocumentSourceSystem | undefined;
  targetReferenceGlobalId?: string | undefined;
}

export interface DocumentDataSource {
  loadDocuments(
    projectId: string,
    signal: AbortSignal,
    query?: DocumentListQuery,
  ): Promise<ControlledDocumentPageViewModel>;
  loadDocument(
    projectId: string,
    documentId: string,
    signal: AbortSignal,
  ): Promise<ControlledDocumentWorkspaceViewModel>;
  createDocument(
    projectId: string,
    command: CreateControlledDocumentCommand,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel>;
  checkOut(
    projectId: string,
    documentId: string,
    expectedDocumentVersion: number,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel>;
  checkIn(
    projectId: string,
    documentId: string,
    expectedDocumentVersion: number,
    expectedLockVersion: number,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel>;
  recoverLock(
    projectId: string,
    documentId: string,
    expectedDocumentVersion: number,
    expectedLockVersion: number,
    reason: string,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel>;
  createRevision(
    projectId: string,
    documentId: string,
    command: CreateDocumentRevisionCommand,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel>;
  loadCapabilities(
    projectId: string,
    documentId: string,
    revisionId: string,
    fileRevisionId: string,
    signal: AbortSignal,
  ): Promise<DocumentFileCapabilityResultViewModel>;
  loadContent(
    projectId: string,
    documentId: string,
    revisionId: string,
    expectedDocumentVersion: number,
    file: DocumentRevisionFileViewModel,
    disposition: "inline" | "attachment",
    context: DocumentCommandContext,
  ): Promise<Blob>;
}

export class DocumentRequestCancelledError extends Error {
  constructor() {
    super("The controlled document request was cancelled.");
    this.name = "DocumentRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const keyPattern = /^[a-z][a-z0-9_.-]{0,63}$/u;
const prefixPattern = /^[A-Z0-9][A-Z0-9-]{0,15}$/u;
const cursorPattern = /^[A-Za-z0-9._~:-]{1,500}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const mimePattern =
  /^[a-z0-9!#$&^_.+-]+\/[a-z0-9!#$&^_.+-]+(?:;[a-z0-9!#$&^_.+\-=" ]+)?$/u;
const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const contentDispositionPattern =
  /^(?:inline|attachment); filename="[A-Za-z0-9._-]{1,255}"; filename\*=UTF-8''(?:[A-Za-z0-9._~-]|%[0-9A-F]{2}){1,1024}$/u;

const lifecycleStates = new Set<DocumentLifecycleState>([
  "draft",
  "proposed",
  "active",
  "on_hold",
  "completed",
  "cancelled",
]);
const relationshipKinds = new Set<DocumentRelationshipKind>([
  "project",
  "project_reference",
  "gate",
  "wbs_item",
  "domain_work_item",
]);
const objectRelationshipKinds = new Set<
  Exclude<DocumentRelationshipKind, "project_reference">
>(["project", "gate", "wbs_item", "domain_work_item"]);
const projectReferenceTypes = new Set<DocumentProjectReferenceType>([
  "customer",
  "product",
  "part",
  "tooling",
  "order",
]);
const sourceSystems = new Set<DocumentSourceSystem>(["NPI_ONE", "ERPNEXT"]);
const capabilityStates = new Set<DocumentCapabilityState>([
  "available",
  "unavailable",
  "blocked",
]);
const previewModes = new Set(["native_pdf", "native_image", "none"]);
const scanStates = new Set(["pending", "clean", "infected", "failed"]);
const fileRoles = new Set(["primary", "source", "derivative"]);
const connectorStates = new Set(["unavailable", "failed"]);
const lockEventTypes = new Set([
  "acquired",
  "released",
  "recovered",
  "expired",
]);
const previewMimeTypes = new Set([
  "application/pdf",
  "image/gif",
  "image/jpeg",
  "image/png",
  "image/webp",
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
    keys.length === required.length &&
    required.every((key) => Object.hasOwn(value, key))
  );
}

function isString(
  value: unknown,
  minimumLength: number,
  maximumLength: number,
  pattern?: RegExp,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimumLength &&
    value.length <= maximumLength &&
    (!pattern || pattern.test(value))
  );
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    timestampPattern.test(value) &&
    !Number.isNaN(Date.parse(value))
  );
}

function isDate(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value)
  );
}

function isUserId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length >= 1 &&
    value.length <= 254 &&
    !/[\s\p{Cc}]/u.test(value)
  );
}

function hasUniqueValues<T>(
  values: readonly T[],
  identify: (value: T) => string,
): boolean {
  return new Set(values.map(identify)).size === values.length;
}

function isBoundedUniqueStringArray(
  value: unknown,
  minimum: number,
  maximum: number,
  validator: (candidate: unknown) => candidate is string,
): value is readonly string[] {
  return (
    Array.isArray(value) &&
    value.length >= minimum &&
    value.length <= maximum &&
    value.every(validator) &&
    hasUniqueValues(value, (candidate) => candidate)
  );
}

function isDocumentProject(value: unknown): value is DocumentProjectViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "businessCode",
      "title",
      "lifecycleState",
      "optimisticVersion",
    ])
  )
    return false;
  return (
    isUuid(value.globalId) &&
    isString(value.businessCode, 1, 64) &&
    isString(value.title, 1, 280) &&
    typeof value.lifecycleState === "string" &&
    lifecycleStates.has(value.lifecycleState as DocumentLifecycleState) &&
    isPositiveInteger(value.optimisticVersion)
  );
}

function isDocumentPermissions(
  value: unknown,
): value is DocumentPermissionsViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "view",
      "create",
      "revise",
      "lock",
      "recoverLock",
      "preview",
      "download",
      "share",
      "review",
      "release",
    ])
  )
    return false;
  return (
    value.view === true &&
    typeof value.create === "boolean" &&
    typeof value.revise === "boolean" &&
    typeof value.lock === "boolean" &&
    typeof value.recoverLock === "boolean" &&
    typeof value.preview === "boolean" &&
    typeof value.download === "boolean" &&
    value.share === false &&
    value.review === false &&
    value.release === false
  );
}

function isPolicyReference(
  value: unknown,
): value is DocumentPolicyReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "version", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    isString(value.snapshotHash, 64, 64, hashPattern)
  );
}

function isDocumentTypeOption(
  value: unknown,
): value is DocumentTypeOptionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["key", "prefix", "titleSource"]) &&
    isString(value.key, 1, 64, keyPattern) &&
    isString(value.prefix, 1, 16, prefixPattern) &&
    isString(value.titleSource, 1, 140)
  );
}

function isDocumentPolicyOption(
  value: unknown,
): value is DocumentPolicyOptionViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "versionId",
      "version",
      "snapshotHash",
      "key",
      "title",
      "documentTypes",
      "confidentialityKeys",
      "allowedMimeTypes",
      "previewMimeTypes",
      "maximumFileBytes",
      "lockLeaseMinutes",
    ]) ||
    !Array.isArray(value.documentTypes) ||
    value.documentTypes.length < 1 ||
    value.documentTypes.length > 64 ||
    !value.documentTypes.every(isDocumentTypeOption) ||
    !hasUniqueValues(value.documentTypes, (option) => option.key) ||
    !hasUniqueValues(value.documentTypes, (option) => option.prefix)
  )
    return false;
  return (
    isUuid(value.globalId) &&
    isUuid(value.versionId) &&
    isPositiveInteger(value.version) &&
    isString(value.snapshotHash, 64, 64, hashPattern) &&
    isString(value.key, 1, 64, keyPattern) &&
    isString(value.title, 1, 140) &&
    isBoundedUniqueStringArray(
      value.confidentialityKeys,
      1,
      32,
      (candidate): candidate is string =>
        isString(candidate, 1, 64, keyPattern),
    ) &&
    isBoundedUniqueStringArray(
      value.allowedMimeTypes,
      1,
      64,
      (candidate): candidate is string =>
        isString(candidate, 3, 255, mimePattern),
    ) &&
    isBoundedUniqueStringArray(
      value.previewMimeTypes,
      0,
      64,
      (candidate): candidate is string =>
        typeof candidate === "string" && previewMimeTypes.has(candidate),
    ) &&
    isPositiveInteger(value.maximumFileBytes) &&
    value.maximumFileBytes <= 67_108_864 &&
    isPositiveInteger(value.lockLeaseMinutes) &&
    value.lockLeaseMinutes <= 1_440
  );
}

function isCurrentRevision(
  value: unknown,
): value is CurrentDocumentRevisionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "major", "minor", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    isNonnegativeInteger(value.major) &&
    isNonnegativeInteger(value.minor) &&
    isString(value.snapshotHash, 64, 64, hashPattern)
  );
}

function isCurrentLock(value: unknown): value is CurrentDocumentLockViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "version", "holderUserId", "expiresAt"]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    isUserId(value.holderUserId) &&
    isTimestamp(value.expiresAt)
  );
}

function isSourceStatus(
  value: unknown,
): value is ControlledDocumentSummaryViewModel["source"] {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["sourceSystem", "editableIn", "syncState"]) &&
    value.sourceSystem === "NPI_ONE" &&
    value.editableIn === "NPI_ONE" &&
    value.syncState === "local"
  );
}

function isDocumentSummary(
  value: unknown,
): value is ControlledDocumentSummaryViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "documentNumber",
      "documentTypeKey",
      "title",
      "confidentialityKey",
      "documentPolicyRef",
      "currentRevision",
      "currentLock",
      "source",
      "optimisticVersion",
    ])
  )
    return false;
  return (
    isUuid(value.globalId) &&
    isString(value.documentNumber, 1, 64) &&
    isString(value.documentTypeKey, 1, 64, keyPattern) &&
    isString(value.title, 1, 280) &&
    isString(value.confidentialityKey, 1, 64, keyPattern) &&
    isPolicyReference(value.documentPolicyRef) &&
    (value.currentRevision === null ||
      isCurrentRevision(value.currentRevision)) &&
    (value.currentLock === null || isCurrentLock(value.currentLock)) &&
    isSourceStatus(value.source) &&
    isPositiveInteger(value.optimisticVersion)
  );
}

function isExternalRetrievalCapability(
  value: unknown,
): value is ControlledDocumentWorkspaceViewModel["externalRetrieval"] {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "reasonCode"]) &&
    value.state === "unavailable" &&
    value.reasonCode === "external_access_policy_unavailable"
  );
}

function isConnectorCapability(
  value: unknown,
): value is DocumentFileCapabilitiesViewModel["connector"] {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "reasonCode"]) &&
    typeof value.state === "string" &&
    connectorStates.has(value.state) &&
    isString(value.reasonCode, 1, 64, keyPattern)
  );
}

function isCapability(value: unknown): value is DocumentCapabilityViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "reasonCode"]) &&
    typeof value.state === "string" &&
    capabilityStates.has(value.state as DocumentCapabilityState) &&
    isString(value.reasonCode, 1, 64, keyPattern)
  );
}

function isPreviewCapability(
  value: unknown,
): value is DocumentPreviewCapabilityViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "reasonCode", "mode"]) &&
    typeof value.state === "string" &&
    capabilityStates.has(value.state as DocumentCapabilityState) &&
    isString(value.reasonCode, 1, 64, keyPattern) &&
    typeof value.mode === "string" &&
    previewModes.has(value.mode) &&
    (value.state === "available"
      ? value.mode === "native_pdf" || value.mode === "native_image"
      : value.mode === "none")
  );
}

function isFileCapabilities(
  value: unknown,
): value is DocumentFileCapabilitiesViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "integrity",
      "preview",
      "download",
      "externalRetrieval",
      "connector",
    ]) &&
    isCapability(value.integrity) &&
    isPreviewCapability(value.preview) &&
    isCapability(value.download) &&
    isExternalRetrievalCapability(value.externalRetrieval) &&
    isConnectorCapability(value.connector)
  );
}

function isFileMetadata(
  value: unknown,
): value is DocumentFileMetadataViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "fileDocumentId",
      "revision",
      "optimisticVersion",
      "fileName",
      "mimeType",
      "sizeBytes",
      "sha256",
      "scanState",
      "scanObservedAt",
      "private",
      "released",
    ])
  )
    return false;
  return (
    isUuid(value.globalId) &&
    isUuid(value.fileDocumentId) &&
    isPositiveInteger(value.revision) &&
    isPositiveInteger(value.optimisticVersion) &&
    isString(value.fileName, 1, 255) &&
    isString(value.mimeType, 3, 255, mimePattern) &&
    isNonnegativeInteger(value.sizeBytes) &&
    value.sizeBytes <= 67_108_864 &&
    isString(value.sha256, 64, 64, hashPattern) &&
    typeof value.scanState === "string" &&
    scanStates.has(value.scanState) &&
    (value.scanObservedAt === null || isTimestamp(value.scanObservedAt)) &&
    value.private === true &&
    typeof value.released === "boolean"
  );
}

function isRevisionFile(
  value: unknown,
): value is DocumentRevisionFileViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "associationId",
      "role",
      "provenance",
      "connector",
      "globalId",
      "fileDocumentId",
      "revision",
      "optimisticVersion",
      "fileName",
      "mimeType",
      "sizeBytes",
      "sha256",
      "scanState",
      "scanObservedAt",
      "private",
      "released",
      "capabilities",
    ])
  )
    return false;
  const metadata = {
    globalId: value.globalId,
    fileDocumentId: value.fileDocumentId,
    revision: value.revision,
    optimisticVersion: value.optimisticVersion,
    fileName: value.fileName,
    mimeType: value.mimeType,
    sizeBytes: value.sizeBytes,
    sha256: value.sha256,
    scanState: value.scanState,
    scanObservedAt: value.scanObservedAt,
    private: value.private,
    released: value.released,
  };
  return (
    isUuid(value.associationId) &&
    typeof value.role === "string" &&
    fileRoles.has(value.role) &&
    isString(value.provenance, 1, 64, keyPattern) &&
    isConnectorCapability(value.connector) &&
    isFileMetadata(metadata) &&
    isFileCapabilities(value.capabilities)
  );
}

function isDocumentRevision(
  value: unknown,
): value is DocumentRevisionViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "major",
      "minor",
      "state",
      "reason",
      "effectiveDate",
      "predecessorRevisionId",
      "snapshotHash",
      "optimisticVersion",
      "createdByUserId",
      "createdAt",
      "files",
    ]) ||
    !Array.isArray(value.files) ||
    value.files.length < 1 ||
    value.files.length > 256 ||
    !value.files.every(isRevisionFile) ||
    !hasUniqueValues(value.files, (file) => file.associationId) ||
    !hasUniqueValues(value.files, (file) => file.globalId)
  )
    return false;
  return (
    isUuid(value.globalId) &&
    isNonnegativeInteger(value.major) &&
    isNonnegativeInteger(value.minor) &&
    value.state === "draft" &&
    isString(value.reason, 1, 2_000) &&
    (value.effectiveDate === null || isDate(value.effectiveDate)) &&
    (value.predecessorRevisionId === null ||
      isUuid(value.predecessorRevisionId)) &&
    isString(value.snapshotHash, 64, 64, hashPattern) &&
    isPositiveInteger(value.optimisticVersion) &&
    isUserId(value.createdByUserId) &&
    isTimestamp(value.createdAt)
  );
}

function isDocumentRelationship(
  value: unknown,
): value is DocumentRelationshipViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "kind",
      "projectReferenceType",
      "targetSourceSystem",
      "targetReferenceGlobalId",
      "targetIdentity",
      "targetVersion",
      "snapshotHash",
    ]) ||
    !isUuid(value.globalId) ||
    typeof value.kind !== "string" ||
    !relationshipKinds.has(value.kind as DocumentRelationshipKind) ||
    !isPositiveInteger(value.targetVersion) ||
    !isString(value.snapshotHash, 64, 64, hashPattern)
  )
    return false;
  if (value.kind === "project_reference") {
    return (
      typeof value.projectReferenceType === "string" &&
      projectReferenceTypes.has(
        value.projectReferenceType as DocumentProjectReferenceType,
      ) &&
      typeof value.targetSourceSystem === "string" &&
      sourceSystems.has(value.targetSourceSystem as DocumentSourceSystem) &&
      (value.targetReferenceGlobalId === null ||
        isUuid(value.targetReferenceGlobalId)) &&
      isString(value.targetIdentity, 1, 512)
    );
  }
  return (
    value.projectReferenceType === null &&
    value.targetSourceSystem === null &&
    value.targetReferenceGlobalId === null &&
    isUuid(value.targetIdentity)
  );
}

function isDocumentLockEvent(
  value: unknown,
): value is DocumentLockEventViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "lockId",
      "version",
      "eventType",
      "holderUserId",
      "actorUserId",
      "acquiredAt",
      "expiresAt",
      "occurredAt",
      "reason",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.lockId) &&
    isPositiveInteger(value.version) &&
    value.version <= 2 &&
    typeof value.eventType === "string" &&
    lockEventTypes.has(value.eventType) &&
    isUserId(value.holderUserId) &&
    isUserId(value.actorUserId) &&
    isTimestamp(value.acquiredAt) &&
    isTimestamp(value.expiresAt) &&
    isTimestamp(value.occurredAt) &&
    (value.reason === null || isString(value.reason, 1, 1_000)) &&
    isString(value.snapshotHash, 64, 64, hashPattern)
  );
}

export function isControlledDocumentPageResponse(
  value: unknown,
): value is ControlledDocumentPageViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "project",
      "permissions",
      "policies",
      "items",
      "nextCursor",
    ]) ||
    !isDocumentProject(value.project) ||
    !isDocumentPermissions(value.permissions) ||
    !Array.isArray(value.policies) ||
    value.policies.length > 64 ||
    !value.policies.every(isDocumentPolicyOption) ||
    !hasUniqueValues(value.policies, (policy) => policy.versionId) ||
    !Array.isArray(value.items) ||
    value.items.length > 100 ||
    !value.items.every(isDocumentSummary) ||
    !hasUniqueValues(value.items, (item) => item.globalId)
  )
    return false;
  return value.nextCursor === null || isString(value.nextCursor, 1, 500);
}

export function isControlledDocumentWorkspaceResponse(
  value: unknown,
): value is ControlledDocumentWorkspaceViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "project",
      "permissions",
      "document",
      "revisions",
      "relationships",
      "lockHistory",
      "externalRetrieval",
    ]) ||
    !isDocumentProject(value.project) ||
    !isDocumentPermissions(value.permissions) ||
    !isDocumentSummary(value.document) ||
    !Array.isArray(value.revisions) ||
    value.revisions.length > 256 ||
    !value.revisions.every(isDocumentRevision) ||
    !hasUniqueValues(value.revisions, (revision) => revision.globalId) ||
    !Array.isArray(value.relationships) ||
    value.relationships.length > 256 ||
    !value.relationships.every(isDocumentRelationship) ||
    !hasUniqueValues(
      value.relationships,
      (relationship) => relationship.globalId,
    ) ||
    !Array.isArray(value.lockHistory) ||
    value.lockHistory.length > 256 ||
    !value.lockHistory.every(isDocumentLockEvent) ||
    !hasUniqueValues(value.lockHistory, (event) => event.globalId) ||
    !isExternalRetrievalCapability(value.externalRetrieval)
  )
    return false;
  const currentRevision = value.document.currentRevision;
  if (
    currentRevision !== null &&
    !value.revisions.some(
      (revision) =>
        revision.globalId === currentRevision.globalId &&
        revision.major === currentRevision.major &&
        revision.minor === currentRevision.minor &&
        revision.snapshotHash === currentRevision.snapshotHash,
    )
  )
    return false;
  const currentLock = value.document.currentLock;
  return (
    currentLock === null ||
    value.lockHistory.some(
      (event) =>
        event.lockId === currentLock.globalId &&
        event.version === currentLock.version &&
        event.holderUserId === currentLock.holderUserId &&
        event.expiresAt === currentLock.expiresAt &&
        event.eventType === "acquired",
    )
  );
}

export function isDocumentFileCapabilityResponse(
  value: unknown,
): value is DocumentFileCapabilityResultViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "projectId",
      "documentId",
      "revisionId",
      "fileRevisionId",
      "file",
      "capabilities",
    ]) &&
    isUuid(value.projectId) &&
    isUuid(value.documentId) &&
    isUuid(value.revisionId) &&
    isUuid(value.fileRevisionId) &&
    isFileMetadata(value.file) &&
    value.file.globalId === value.fileRevisionId &&
    isFileCapabilities(value.capabilities)
  );
}

function isRelationshipInput(value: DocumentRelationshipInput): boolean {
  if (
    !isPositiveInteger(value.targetVersion) ||
    !relationshipKinds.has(value.kind)
  )
    return false;
  if (value.kind === "project_reference") {
    return (
      projectReferenceTypes.has(value.projectReferenceType) &&
      sourceSystems.has(value.targetSourceSystem) &&
      isString(value.targetIdentity, 1, 512) &&
      (value.targetReferenceGlobalId === null ||
        isUuid(value.targetReferenceGlobalId))
    );
  }
  return (
    objectRelationshipKinds.has(value.kind) && isUuid(value.targetIdentity)
  );
}

function isListQuery(query: DocumentListQuery): boolean {
  const hasRelationship = query.relationshipKind !== undefined;
  const hasTargetIdentity = query.targetIdentity !== undefined;
  const hasTargetVersion = query.targetVersion !== undefined;
  const requiredFilterFields = hasTargetIdentity && hasTargetVersion;
  const anyTargetFilterField = hasTargetIdentity || hasTargetVersion;
  const projectReferenceFields =
    query.projectReferenceType !== undefined ||
    query.targetSourceSystem !== undefined ||
    query.targetReferenceGlobalId !== undefined;
  return (
    (query.limit === undefined ||
      (isPositiveInteger(query.limit) && query.limit <= 100)) &&
    (query.cursor === undefined || cursorPattern.test(query.cursor)) &&
    (query.relationshipKind === undefined ||
      relationshipKinds.has(query.relationshipKind)) &&
    (!hasRelationship ||
      (requiredFilterFields &&
        isString(query.targetIdentity, 1, 512) &&
        isPositiveInteger(query.targetVersion))) &&
    (hasRelationship || (!anyTargetFilterField && !projectReferenceFields)) &&
    (query.relationshipKind === "project_reference"
      ? query.projectReferenceType !== undefined &&
        projectReferenceTypes.has(query.projectReferenceType) &&
        query.targetSourceSystem !== undefined &&
        sourceSystems.has(query.targetSourceSystem) &&
        (query.targetReferenceGlobalId === undefined ||
          isUuid(query.targetReferenceGlobalId))
      : !projectReferenceFields) &&
    (query.relationshipKind === undefined ||
      query.relationshipKind === "project_reference" ||
      isUuid(query.targetIdentity))
  );
}

function isCommandContext(context: DocumentCommandContext): boolean {
  return (
    isString(context.csrfToken, 1, 4_096) &&
    isString(context.idempotencyKey, 8, 128, idempotencyPattern) &&
    context.signal instanceof AbortSignal
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
  if (signal.aborted) throw new DocumentRequestCancelledError();
}

function contentType(response: Response): string {
  return (
    (response.headers.get("Content-Type") ?? "")
      .split(";", 1)[0]
      ?.trim()
      .toLowerCase() ?? ""
  );
}

function isBinaryBlob(value: unknown): value is Blob {
  return (
    value instanceof Blob ||
    (Boolean(value) &&
      typeof value === "object" &&
      Object.prototype.toString.call(value) === "[object Blob]")
  );
}

export class LiveDocumentDataSource implements DocumentDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadDocuments(
    projectId: string,
    signal: AbortSignal,
    query: DocumentListQuery = {},
  ): Promise<ControlledDocumentPageViewModel> {
    if (!isUuid(projectId) || !isListQuery(query)) throw requestNotReady();
    const parameters: Record<string, string> = {
      limit: String(query.limit ?? 50),
    };
    if (query.cursor !== undefined) parameters.cursor = query.cursor;
    if (query.relationshipKind !== undefined)
      parameters.relationshipKind = query.relationshipKind;
    if (query.targetIdentity !== undefined)
      parameters.targetIdentity = query.targetIdentity;
    if (query.targetVersion !== undefined)
      parameters.targetVersion = String(query.targetVersion);
    if (query.projectReferenceType !== undefined)
      parameters.projectReferenceType = query.projectReferenceType;
    if (query.targetSourceSystem !== undefined)
      parameters.targetSourceSystem = query.targetSourceSystem;
    if (query.targetReferenceGlobalId !== undefined)
      parameters.targetReferenceGlobalId = query.targetReferenceGlobalId;
    return this.query(
      `/projects/${projectId}/documents`,
      signal,
      parameters,
      (value): value is ControlledDocumentPageViewModel =>
        isControlledDocumentPageResponse(value) &&
        value.project.globalId === projectId &&
        (query.cursor === undefined || value.nextCursor !== query.cursor),
    );
  }

  async loadDocument(
    projectId: string,
    documentId: string,
    signal: AbortSignal,
  ): Promise<ControlledDocumentWorkspaceViewModel> {
    if (!isUuid(projectId) || !isUuid(documentId)) throw requestNotReady();
    return this.query(
      `/projects/${projectId}/documents/${documentId}`,
      signal,
      {},
      (value): value is ControlledDocumentWorkspaceViewModel =>
        isControlledDocumentWorkspaceResponse(value) &&
        value.project.globalId === projectId &&
        value.document.globalId === documentId,
    );
  }

  async createDocument(
    projectId: string,
    command: CreateControlledDocumentCommand,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel> {
    const title = command.title.trim();
    if (
      !isUuid(projectId) ||
      !isUuid(command.policyGlobalId) ||
      !isPositiveInteger(command.policyVersion) ||
      !isString(command.policySnapshotHash, 64, 64, hashPattern) ||
      !isString(command.documentTypeKey, 1, 64, keyPattern) ||
      !isString(title, 1, 280) ||
      !isString(command.confidentialityKey, 1, 64, keyPattern) ||
      command.objectLinks.length > 64 ||
      !command.objectLinks.every(isRelationshipInput) ||
      !hasUniqueValues(
        command.objectLinks,
        (link) =>
          `${link.kind}:${link.targetIdentity}:${String(link.targetVersion)}`,
      )
    )
      throw requestNotReady();
    return this.command(
      `/projects/${projectId}/documents`,
      { ...command, title },
      context,
      (value): value is ControlledDocumentWorkspaceViewModel =>
        isControlledDocumentWorkspaceResponse(value) &&
        value.project.globalId === projectId &&
        value.document.documentPolicyRef.globalId === command.policyGlobalId &&
        value.document.documentPolicyRef.version === command.policyVersion &&
        value.document.documentPolicyRef.snapshotHash ===
          command.policySnapshotHash &&
        value.document.documentTypeKey === command.documentTypeKey &&
        value.document.title === title &&
        value.document.confidentialityKey === command.confidentialityKey &&
        value.document.currentRevision === null,
    );
  }

  async checkOut(
    projectId: string,
    documentId: string,
    expectedDocumentVersion: number,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel> {
    return this.versionedCommand(
      projectId,
      documentId,
      ":check-out",
      { expectedDocumentVersion },
      expectedDocumentVersion,
      context,
      (value) => value.document.currentLock !== null,
    );
  }

  async checkIn(
    projectId: string,
    documentId: string,
    expectedDocumentVersion: number,
    expectedLockVersion: number,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel> {
    if (!isPositiveInteger(expectedLockVersion)) throw requestNotReady();
    return this.versionedCommand(
      projectId,
      documentId,
      ":check-in",
      { expectedDocumentVersion, expectedLockVersion },
      expectedDocumentVersion,
      context,
      (value) => value.document.currentLock === null,
    );
  }

  async recoverLock(
    projectId: string,
    documentId: string,
    expectedDocumentVersion: number,
    expectedLockVersion: number,
    reason: string,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel> {
    const normalizedReason = reason.trim();
    if (
      !isPositiveInteger(expectedLockVersion) ||
      !isString(normalizedReason, 1, 1_000)
    )
      throw requestNotReady();
    return this.versionedCommand(
      projectId,
      documentId,
      ":recover-lock",
      {
        expectedDocumentVersion,
        expectedLockVersion,
        reason: normalizedReason,
      },
      expectedDocumentVersion,
      context,
      (value) =>
        value.document.currentLock === null &&
        value.lockHistory.some(
          (event) =>
            event.eventType === "recovered" &&
            event.version === expectedLockVersion + 1 &&
            event.reason === normalizedReason,
        ),
    );
  }

  async createRevision(
    projectId: string,
    documentId: string,
    command: CreateDocumentRevisionCommand,
    context: DocumentCommandContext,
  ): Promise<ControlledDocumentWorkspaceViewModel> {
    const reason = command.reason.trim();
    if (
      !isUuid(projectId) ||
      !isUuid(documentId) ||
      !isPositiveInteger(command.expectedDocumentVersion) ||
      !isPositiveInteger(command.expectedLockVersion) ||
      !isNonnegativeInteger(command.major) ||
      !isNonnegativeInteger(command.minor) ||
      !isString(reason, 1, 2_000) ||
      !(command.effectiveDate === null || isDate(command.effectiveDate)) ||
      !(
        command.predecessorRevisionId === null ||
        isUuid(command.predecessorRevisionId)
      ) ||
      !(command.file instanceof File) ||
      !isString(command.file.name, 1, 255) ||
      command.file.size < 1 ||
      command.file.size > 67_108_864
    )
      throw requestNotReady();
    const form = new FormData();
    form.append(
      "metadata",
      JSON.stringify({
        expectedDocumentVersion: command.expectedDocumentVersion,
        expectedLockVersion: command.expectedLockVersion,
        major: command.major,
        minor: command.minor,
        reason,
        effectiveDate: command.effectiveDate,
        predecessorRevisionId: command.predecessorRevisionId,
      }),
    );
    form.append("file", command.file, command.file.name);
    return this.command(
      `/projects/${projectId}/documents/${documentId}/revisions`,
      form,
      context,
      (value): value is ControlledDocumentWorkspaceViewModel =>
        isControlledDocumentWorkspaceResponse(value) &&
        value.project.globalId === projectId &&
        value.document.globalId === documentId &&
        value.document.optimisticVersion ===
          command.expectedDocumentVersion + 1 &&
        value.document.currentRevision?.major === command.major &&
        value.document.currentRevision.minor === command.minor &&
        value.revisions.some(
          (revision) =>
            revision.globalId === value.document.currentRevision?.globalId &&
            revision.reason === reason &&
            revision.effectiveDate === command.effectiveDate &&
            revision.predecessorRevisionId === command.predecessorRevisionId &&
            revision.files.some(
              (file) =>
                file.fileName === command.file.name &&
                file.sizeBytes === command.file.size &&
                file.scanState === "pending",
            ),
        ),
    );
  }

  async loadCapabilities(
    projectId: string,
    documentId: string,
    revisionId: string,
    fileRevisionId: string,
    signal: AbortSignal,
  ): Promise<DocumentFileCapabilityResultViewModel> {
    if (![projectId, documentId, revisionId, fileRevisionId].every(isUuid))
      throw requestNotReady();
    return this.query(
      `/projects/${projectId}/documents/${documentId}/revisions/${revisionId}/files/${fileRevisionId}/capabilities`,
      signal,
      {},
      (value): value is DocumentFileCapabilityResultViewModel =>
        isDocumentFileCapabilityResponse(value) &&
        value.projectId === projectId &&
        value.documentId === documentId &&
        value.revisionId === revisionId &&
        value.fileRevisionId === fileRevisionId,
    );
  }

  async loadContent(
    projectId: string,
    documentId: string,
    revisionId: string,
    expectedDocumentVersion: number,
    file: DocumentRevisionFileViewModel,
    disposition: "inline" | "attachment",
    context: DocumentCommandContext,
  ): Promise<Blob> {
    if (
      !isUuid(projectId) ||
      !isUuid(documentId) ||
      !isUuid(revisionId) ||
      !isPositiveInteger(expectedDocumentVersion) ||
      !isRevisionFile(file) ||
      !["inline", "attachment"].includes(disposition) ||
      !isCommandContext(context)
    )
      throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<Blob>(
        `/projects/${projectId}/documents/${documentId}/revisions/${revisionId}/files/${file.globalId}:content`,
        {
          body: JSON.stringify({
            expectedDocumentVersion,
            expectedFileVersion: file.optimisticVersion,
            disposition,
          }),
          headers: {
            Accept: file.mimeType,
            "Idempotency-Key": context.idempotencyKey,
          },
          method: "POST",
          signal: context.signal,
        },
        {
          csrfToken: context.csrfToken,
          requireIdempotencyReplay: true,
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          responseType: "blob",
          validate: (value): value is Blob =>
            isBinaryBlob(value) &&
            value.size === file.sizeBytes &&
            value.type.toLowerCase() === file.mimeType.toLowerCase(),
          validateResponse: (response) => {
            const contentLength = Number(
              response.headers.get("Content-Length"),
            );
            const contentDisposition =
              response.headers.get("Content-Disposition") ?? "";
            return (
              contentType(response) === file.mimeType.toLowerCase() &&
              Number.isSafeInteger(contentLength) &&
              contentLength === file.sizeBytes &&
              contentDispositionPattern.test(contentDisposition) &&
              contentDisposition.startsWith(disposition) &&
              response.headers.get("Content-Security-Policy") ===
                "sandbox; default-src 'none'" &&
              response.headers.get("Referrer-Policy") === "no-referrer" &&
              response.headers.get("X-Content-Type-Options") === "nosniff"
            );
          },
        },
      );
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }

  private async versionedCommand(
    projectId: string,
    documentId: string,
    suffix: ":check-out" | ":check-in" | ":recover-lock",
    body: object,
    expectedDocumentVersion: number,
    context: DocumentCommandContext,
    check: (value: ControlledDocumentWorkspaceViewModel) => boolean,
  ): Promise<ControlledDocumentWorkspaceViewModel> {
    if (
      !isUuid(projectId) ||
      !isUuid(documentId) ||
      !isPositiveInteger(expectedDocumentVersion)
    )
      throw requestNotReady();
    return this.command(
      `/projects/${projectId}/documents/${documentId}${suffix}`,
      body,
      context,
      (value): value is ControlledDocumentWorkspaceViewModel =>
        isControlledDocumentWorkspaceResponse(value) &&
        value.project.globalId === projectId &&
        value.document.globalId === documentId &&
        value.document.optimisticVersion === expectedDocumentVersion + 1 &&
        check(value),
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
    body: object | FormData,
    context: DocumentCommandContext,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    if (!isCommandContext(context)) throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<T>(
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
          validate,
        },
      );
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }
}
