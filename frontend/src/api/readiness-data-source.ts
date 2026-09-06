import { NpiHttpClient, NpiTransportError } from "./http";

export const readinessProjectTypes = [
  "customer_owned_tool",
  "new_tool",
  "tool_change",
] as const;
export type ReadinessProjectType = (typeof readinessProjectTypes)[number];

export const readinessSourceKinds = [
  "project",
  "domain_work_item",
  "released_document",
  "release_baseline",
  "file_revision",
  "tooling_capacity_scenario",
  "trial_input_lock",
  "trial_actual",
  "trial_sample",
  "trial_cavity_result",
  "trial_defect",
  "trial_defect_verification",
  "trial_comparison",
  "trial_review_reference",
  "trial_conclusion",
  "controlled_quality_result",
  "erp_material_specification",
  "erp_quality_result",
  "erp_run_at_rate",
  "erp_hr_qualification",
  "erp_supplier_execution",
] as const;
export type ReadinessSourceKind = (typeof readinessSourceKinds)[number];

export const readinessInternalSourceKinds = readinessSourceKinds.slice(
  0,
  16,
) as readonly ReadinessSourceKind[];
export type ReadinessInternalSourceKind = Exclude<
  ReadinessSourceKind,
  ReadinessExternalSourceKind
>;

export const readinessExternalSourceKinds = [
  "erp_hr_qualification",
  "erp_material_specification",
  "erp_quality_result",
  "erp_run_at_rate",
  "erp_supplier_execution",
] as const;
export type ReadinessExternalSourceKind =
  (typeof readinessExternalSourceKinds)[number];

export type ReadinessPublicationState = "draft" | "published";
export type ReadinessBlockingLevel = "P0" | "P1" | "P2" | "none";
export type ReadinessCompletionRule =
  | "confirmation"
  | "exact_evidence"
  | "exact_source_result";
export type ReadinessItemState =
  | "not_started"
  | "in_progress"
  | "complete"
  | "failed"
  | "not_applicable";
export type ReadinessEditableItemState = Exclude<
  ReadinessItemState,
  "not_applicable"
>;
export type ReadinessSourceState = "satisfied" | "failed" | "unavailable";
export type ReadinessBlockerCode =
  | "incomplete_p0"
  | "failed_mandatory_quality"
  | "required_source_unavailable";

export interface ReadinessApplicabilitySelector {
  projectTypes: readonly ReadinessProjectType[];
  customerReferenceKeys: readonly string[];
  industryKeys: readonly string[];
}

export interface ReadinessCategoryDefinition {
  key: string;
  title: string;
}

export interface ReadinessEvidenceRequirement {
  key: string;
  acceptedSourceKinds: readonly ReadinessSourceKind[];
  minimumCount: number;
  unavailableBlocks: boolean;
}

export interface ReadinessItemDefinition {
  key: string;
  title: string;
  categoryKey: string;
  weight: number;
  required: boolean;
  blockingLevel: ReadinessBlockingLevel;
  gateKey: string;
  completionRule: ReadinessCompletionRule;
  applicability: ReadinessApplicabilitySelector;
  evidenceRequirements: readonly ReadinessEvidenceRequirement[];
}

export interface ReadinessTemplateVersion {
  globalId: string;
  templateGlobalId: string;
  templateCode: string;
  templateVersion: number;
  optimisticVersion: number;
  title: string;
  publicationState: ReadinessPublicationState;
  applicability: ReadinessApplicabilitySelector;
  categories: readonly ReadinessCategoryDefinition[];
  items: readonly ReadinessItemDefinition[];
  changedByUserId: string;
  changedAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface ReadinessExactReference {
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface ReadinessProjectSnapshot {
  globalId: string;
  optimisticVersion: number;
  snapshotHash: string;
  projectType: ReadinessProjectType;
  customerReferenceKeys: readonly string[];
  industryKey: string;
}

export interface ReadinessMemberReference {
  globalId: string;
  userId: string;
  optimisticVersion: number;
}

export interface ReadinessGateReference {
  globalId: string;
  gateKey: string;
  optimisticVersion: number;
  snapshotHash: string;
}

export interface ReadinessSourceReference {
  requirementKey: string;
  kind: ReadinessSourceKind;
  state: ReadinessSourceState;
  globalId: string | null;
  sourceVersion: number | null;
  snapshotHash: string | null;
  reasonCode: string | null;
}

export interface ReadinessItemSnapshot {
  globalId: string;
  itemVersion: number;
  definition: ReadinessItemDefinition;
  applicable: boolean;
  gate: ReadinessGateReference;
  owner: ReadinessMemberReference | null;
  dueDate: string | null;
  state: ReadinessItemState;
  confirmationValue: string | null;
  sources: readonly ReadinessSourceReference[];
}

export interface ReadinessScore {
  categoryKey: string | null;
  earnedWeight: number;
  applicableWeight: number;
  basisPoints: number | null;
  state: "scored" | "not_applicable";
}

export interface ReadinessBlocker {
  code: ReadinessBlockerCode;
  itemGlobalId: string;
  itemKey: string;
  gate: ReadinessGateReference;
}

export interface ReadinessEvaluation {
  formulaVersion: "readiness-score.v1";
  categoryScores: readonly ReadinessScore[];
  totalScore: ReadinessScore;
  blockers: readonly ReadinessBlocker[];
  ready: boolean;
}

export interface ReadinessInstanceRevision {
  globalId: string;
  instanceGlobalId: string;
  tenantId: string;
  project: ReadinessProjectSnapshot;
  templateRevision: ReadinessExactReference;
  instanceVersion: number;
  predecessorGlobalId: string | null;
  predecessorSnapshotHash: string | null;
  categories: readonly ReadinessCategoryDefinition[];
  items: readonly ReadinessItemSnapshot[];
  evaluation: ReadinessEvaluation;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  versionKeyHash: string;
  snapshotHash: string;
}

export interface ReadinessSourceOption {
  kind: "domain_work_item";
  globalId: string;
  sourceVersion: number;
  snapshotHash: string;
  label: string;
  stateLabelSource:
    | "Draft"
    | "Identified"
    | "Not started"
    | "Open"
    | "Requested";
  stateTerminal: boolean;
}

export type ReadinessUnavailableProjection = {
  [Kind in ReadinessExternalSourceKind]: {
    kind: Kind;
    state: "unavailable";
    reasonCode: `${Kind}_provider_unavailable`;
  };
}[ReadinessExternalSourceKind];

export interface ReadinessPermissions {
  canManageTemplates: boolean;
  canInitialize: boolean;
  canRevise: boolean;
}

export interface ReadinessWorkspace {
  projectGlobalId: string;
  currentRevision: ReadinessInstanceRevision | null;
  revisions: readonly ReadinessInstanceRevision[];
  sourceOptions: readonly ReadinessSourceOption[];
  unavailableProjections: readonly ReadinessUnavailableProjection[];
  permissions: ReadinessPermissions;
}

export interface ReadinessTemplateCatalog {
  projectGlobalId: string;
  templates: readonly ReadinessTemplateVersion[];
}

export interface CreateReadinessTemplateCommand {
  templateCode: string;
  title: string;
  applicability: ReadinessApplicabilitySelector;
  categories: readonly ReadinessCategoryDefinition[];
  items: readonly ReadinessItemDefinition[];
}

export interface EditReadinessTemplateCommand {
  expectedOptimisticVersion: number;
  title: string;
  applicability: ReadinessApplicabilitySelector;
  categories: readonly ReadinessCategoryDefinition[];
  items: readonly ReadinessItemDefinition[];
}

export interface PublishReadinessTemplateCommand {
  expectedOptimisticVersion: number;
}

export interface ReadinessAssignment {
  itemKey: string;
  ownerMemberGlobalId: string;
  dueDate: string;
}

export interface InitializeProjectReadinessCommand {
  templateRevisionGlobalId: string;
  templateVersion: number;
  templateSnapshotHash: string;
  industryKey: string;
  assignments: readonly ReadinessAssignment[];
}

export interface ReadinessInternalSourceSelection {
  requirementKey: string;
  kind: ReadinessInternalSourceKind;
  globalId: string;
  sourceVersion: number;
  snapshotHash: string;
}

export interface ReadinessExternalSourceSelection {
  requirementKey: string;
  kind: ReadinessExternalSourceKind;
}

export type ReadinessSourceSelection =
  | ReadinessInternalSourceSelection
  | ReadinessExternalSourceSelection;

export interface ReviseProjectReadinessItemCommand {
  expectedInstanceVersion: number;
  expectedRevisionGlobalId: string;
  expectedRevisionSnapshotHash: string;
  itemKey: string;
  ownerMemberGlobalId: string;
  dueDate: string;
  state: ReadinessEditableItemState;
  confirmationValue: string | null;
  sources: readonly ReadinessSourceSelection[];
}

export interface ReadinessCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface ReadinessTemplateCommandResult {
  template: ReadinessTemplateVersion;
  replayed: boolean;
}

export interface ReadinessCommandResult {
  workspace: ReadinessWorkspace;
  replayed: boolean;
}

export interface ReadinessDataSource {
  listEligibleTemplates(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ReadinessTemplateCatalog>;
  loadWorkspace(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ReadinessWorkspace>;
  createTemplate(
    command: CreateReadinessTemplateCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessTemplateCommandResult>;
  editTemplate(
    templateId: string,
    templateVersion: number,
    command: EditReadinessTemplateCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessTemplateCommandResult>;
  publishTemplate(
    templateId: string,
    templateVersion: number,
    command: PublishReadinessTemplateCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessTemplateCommandResult>;
  initialize(
    projectId: string,
    command: InitializeProjectReadinessCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessCommandResult>;
  reviseItem(
    projectId: string,
    instanceId: string,
    command: ReviseProjectReadinessItemCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessCommandResult>;
}

export class ReadinessRequestCancelledError extends Error {
  constructor() {
    super("The NPI Readiness request was cancelled.");
    this.name = "ReadinessRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[0-9a-f]{64}$/u;
const codePattern = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$/u;
const keyPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const tenantPattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const tracePattern = /^[A-Za-z0-9._:-]{1,128}$/u;
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/u;

const projectTypeSet = new Set<ReadinessProjectType>(readinessProjectTypes);
const sourceKindSet = new Set<ReadinessSourceKind>(readinessSourceKinds);
const internalSourceKindSet = new Set<ReadinessSourceKind>(
  readinessInternalSourceKinds,
);
const externalSourceKindSet = new Set<ReadinessSourceKind>(
  readinessExternalSourceKinds,
);
const resultSourceKindSet = new Set<ReadinessSourceKind>([
  "tooling_capacity_scenario",
  "trial_cavity_result",
  "trial_defect",
  "trial_defect_verification",
  "trial_conclusion",
  "erp_quality_result",
  "erp_run_at_rate",
  "erp_hr_qualification",
  "erp_supplier_execution",
]);
const qualitySourceKindSet = new Set<ReadinessSourceKind>([
  "trial_cavity_result",
  "trial_defect",
  "trial_defect_verification",
  "erp_quality_result",
]);
const publicationStateSet = new Set<ReadinessPublicationState>([
  "draft",
  "published",
]);
const blockingLevelSet = new Set<ReadinessBlockingLevel>([
  "P0",
  "P1",
  "P2",
  "none",
]);
const completionRuleSet = new Set<ReadinessCompletionRule>([
  "confirmation",
  "exact_evidence",
  "exact_source_result",
]);
const itemStateSet = new Set<ReadinessItemState>([
  "not_started",
  "in_progress",
  "complete",
  "failed",
  "not_applicable",
]);
const editableItemStateSet = new Set<ReadinessEditableItemState>([
  "not_started",
  "in_progress",
  "complete",
  "failed",
]);
const sourceStateSet = new Set<ReadinessSourceState>([
  "satisfied",
  "failed",
  "unavailable",
]);
const sourceOptionStateLabels = new Set<
  ReadinessSourceOption["stateLabelSource"]
>(["Draft", "Identified", "Not started", "Open", "Requested"]);
const unavailableReasons: Readonly<
  Record<ReadinessExternalSourceKind, string>
> = {
  erp_hr_qualification: "erp_hr_qualification_provider_unavailable",
  erp_material_specification: "erp_material_specification_provider_unavailable",
  erp_quality_result: "erp_quality_result_provider_unavailable",
  erp_run_at_rate: "erp_run_at_rate_provider_unavailable",
  erp_supplier_execution: "erp_supplier_execution_provider_unavailable",
};

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function exact(
  value: Record<string, unknown>,
  fields: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return (
    keys.length === fields.length &&
    fields.every((field) => Object.hasOwn(value, field))
  );
}

function text(
  value: unknown,
  minimum: number,
  maximum: number,
  pattern?: RegExp,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    value === value.trim() &&
    (pattern?.test(value) ?? true)
  );
}

function member<T extends string>(value: unknown, values: Set<T>): value is T {
  return typeof value === "string" && values.has(value as T);
}

function uuid(value: unknown): value is string {
  return text(value, 36, 36, uuidPattern);
}

function hash(value: unknown): value is string {
  return text(value, 64, 64, hashPattern);
}

function positive(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 1;
}

function nullable<T>(
  value: unknown,
  validate: (candidate: unknown) => candidate is T,
): value is T | null {
  return value === null || validate(value);
}

function date(value: unknown): value is string {
  if (!text(value, 10, 10, datePattern)) return false;
  const [year, month, day] = value.split("-").map(Number);
  if (year === undefined || month === undefined || day === undefined)
    return false;
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

function timestamp(value: unknown): value is string {
  return (
    text(value, 20, 32, timestampPattern) && !Number.isNaN(Date.parse(value))
  );
}

function boolean(value: unknown): value is boolean {
  return typeof value === "boolean";
}

function array(
  value: unknown,
  minimum: number,
  maximum: number,
): value is readonly unknown[] {
  return (
    Array.isArray(value) && value.length >= minimum && value.length <= maximum
  );
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

function sorted(values: readonly string[]): boolean {
  return values.every(
    (value, index) => index === 0 || String(values[index - 1]) <= value,
  );
}

function lexical(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function deepEqual(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) && Array.isArray(right))
    return (
      left.length === right.length &&
      left.every((entry, index) => deepEqual(entry, right[index]))
    );
  if (record(left) && record(right)) {
    const leftKeys = Object.keys(left).sort();
    const rightKeys = Object.keys(right).sort();
    return (
      leftKeys.length === rightKeys.length &&
      leftKeys.every(
        (key, index) =>
          key === rightKeys[index] && deepEqual(left[key], right[key]),
      )
    );
  }
  return false;
}

function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value))
      throw new Error("Unsafe canonical number.");
    return String(value);
  }
  if (Array.isArray(value))
    return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
  if (record(value)) {
    const fields = Object.keys(value).sort();
    return `{${fields
      .map((field) => `${JSON.stringify(field)}:${canonicalJson(value[field])}`)
      .join(",")}}`;
  }
  throw new Error("Unsupported canonical JSON value.");
}

function withoutField(
  value: Record<string, unknown>,
  omitted: string,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).filter(([field]) => field !== omitted),
  );
}

async function digest(
  algorithm: "SHA-1" | "SHA-256",
  value: Uint8Array<ArrayBuffer>,
): Promise<Uint8Array<ArrayBuffer>> {
  const result = await globalThis.crypto.subtle.digest(algorithm, value);
  return new Uint8Array(result);
}

function bytesToHex(value: Uint8Array<ArrayBuffer>): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

async function canonicalSha256(value: unknown): Promise<string> {
  return bytesToHex(
    await digest("SHA-256", new TextEncoder().encode(canonicalJson(value))),
  );
}

function uuidBytes(value: string): Uint8Array<ArrayBuffer> {
  const hex = value.replaceAll("-", "");
  const result = new Uint8Array(16);
  for (let index = 0; index < result.length; index += 1) {
    result[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
  }
  return result;
}

function concatBytes(
  left: Uint8Array<ArrayBuffer>,
  right: Uint8Array<ArrayBuffer>,
): Uint8Array<ArrayBuffer> {
  const result = new Uint8Array(left.length + right.length);
  result.set(left);
  result.set(right, left.length);
  return result;
}

async function uuidV5(namespace: string, name: string): Promise<string> {
  const bytes = (
    await digest(
      "SHA-1",
      concatBytes(uuidBytes(namespace), new TextEncoder().encode(name)),
    )
  ).slice(0, 16);
  const versionByte = bytes[6];
  const variantByte = bytes[8];
  if (versionByte === undefined || variantByte === undefined)
    throw new Error("The UUID digest is incomplete.");
  bytes[6] = (versionByte & 0x0f) | 0x50;
  bytes[8] = (variantByte & 0x3f) | 0x80;
  const hex = bytesToHex(bytes);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function cachedUuidV5(
  cache: Map<string, Promise<string>>,
  namespace: string,
  name: string,
): Promise<string> {
  const key = `${namespace}\u0000${name}`;
  const existing = cache.get(key);
  if (existing) return existing;
  const created = uuidV5(namespace, name);
  cache.set(key, created);
  return created;
}

async function hasCanonicalTemplateIdentity(
  template: ReadinessTemplateVersion,
): Promise<boolean> {
  const expectedGlobalId = await uuidV5(
    template.templateGlobalId,
    `npi-readiness-template-version:${String(template.templateVersion)}`,
  );
  const expectedSnapshotHash = await canonicalSha256(
    withoutField(
      template as unknown as Record<string, unknown>,
      "snapshotHash",
    ),
  );
  return (
    template.globalId === expectedGlobalId &&
    template.snapshotHash === expectedSnapshotHash
  );
}

async function hasCanonicalRevisionIdentity(
  revision: ReadinessInstanceRevision,
  itemIdentityCache: Map<string, Promise<string>>,
): Promise<boolean> {
  const expectedVersionKeyHash = await canonicalSha256({
    instanceGlobalId: revision.instanceGlobalId,
    instanceVersion: revision.instanceVersion,
  });
  if (revision.versionKeyHash !== expectedVersionKeyHash) return false;
  const expectedItemIds = await Promise.all(
    revision.items.map((item) =>
      cachedUuidV5(
        itemIdentityCache,
        revision.instanceGlobalId,
        `npi-readiness-item:${item.definition.key.toLowerCase()}`,
      ),
    ),
  );
  if (
    revision.items.some(
      (item, index) => item.globalId !== expectedItemIds[index],
    )
  )
    return false;
  const expectedSnapshotHash = await canonicalSha256(
    withoutField(
      revision as unknown as Record<string, unknown>,
      "snapshotHash",
    ),
  );
  return revision.snapshotHash === expectedSnapshotHash;
}

export async function isCanonicalReadinessTemplateVersion(
  value: unknown,
  signal?: AbortSignal,
): Promise<boolean> {
  if (!isReadinessTemplateVersion(value)) return false;
  try {
    return (
      !signal?.aborted &&
      (await hasCanonicalTemplateIdentity(value)) &&
      !signal?.aborted
    );
  } catch {
    return false;
  }
}

export async function isCanonicalReadinessTemplateCatalog(
  value: unknown,
  signal?: AbortSignal,
): Promise<boolean> {
  if (!isReadinessTemplateCatalog(value)) return false;
  try {
    for (const template of value.templates) {
      if (signal?.aborted || !(await hasCanonicalTemplateIdentity(template)))
        return false;
    }
    return !signal?.aborted;
  } catch {
    return false;
  }
}

export async function isCanonicalReadinessWorkspace(
  value: unknown,
  signal?: AbortSignal,
): Promise<boolean> {
  if (!isReadinessWorkspace(value)) return false;
  try {
    const itemIdentityCache = new Map<string, Promise<string>>();
    for (const revision of value.revisions) {
      if (
        signal?.aborted ||
        !(await hasCanonicalRevisionIdentity(revision, itemIdentityCache))
      )
        return false;
    }
    return !signal?.aborted;
  } catch {
    return false;
  }
}

function isApplicability(
  value: unknown,
): value is ReadinessApplicabilitySelector {
  if (
    !record(value) ||
    !exact(value, ["projectTypes", "customerReferenceKeys", "industryKeys"]) ||
    !array(value.projectTypes, 0, 20) ||
    !value.projectTypes.every((item) => member(item, projectTypeSet)) ||
    !unique(value.projectTypes) ||
    !sorted(value.projectTypes) ||
    !array(value.customerReferenceKeys, 0, 100) ||
    !value.customerReferenceKeys.every((item) => text(item, 1, 256)) ||
    !unique(value.customerReferenceKeys) ||
    !sorted(value.customerReferenceKeys) ||
    !array(value.industryKeys, 0, 100) ||
    !value.industryKeys.every((item) => text(item, 1, 128, keyPattern)) ||
    !unique(value.industryKeys) ||
    !sorted(value.industryKeys)
  )
    return false;
  return true;
}

function isCategory(value: unknown): value is ReadinessCategoryDefinition {
  return (
    record(value) &&
    exact(value, ["key", "title"]) &&
    text(value.key, 1, 128, keyPattern) &&
    text(value.title, 1, 200)
  );
}

function isRequirement(value: unknown): value is ReadinessEvidenceRequirement {
  return (
    record(value) &&
    exact(value, [
      "key",
      "acceptedSourceKinds",
      "minimumCount",
      "unavailableBlocks",
    ]) &&
    text(value.key, 1, 128, keyPattern) &&
    array(value.acceptedSourceKinds, 1, 30) &&
    value.acceptedSourceKinds.every((kind) => member(kind, sourceKindSet)) &&
    unique(value.acceptedSourceKinds) &&
    sorted(value.acceptedSourceKinds) &&
    positive(value.minimumCount) &&
    value.minimumCount <= 100 &&
    boolean(value.unavailableBlocks)
  );
}

function isItemDefinition(value: unknown): value is ReadinessItemDefinition {
  if (
    !record(value) ||
    !exact(value, [
      "key",
      "title",
      "categoryKey",
      "weight",
      "required",
      "blockingLevel",
      "gateKey",
      "completionRule",
      "applicability",
      "evidenceRequirements",
    ]) ||
    !text(value.key, 1, 128, keyPattern) ||
    !text(value.title, 1, 240) ||
    !text(value.categoryKey, 1, 128, keyPattern) ||
    !positive(value.weight) ||
    !boolean(value.required) ||
    !member(value.blockingLevel, blockingLevelSet) ||
    !text(value.gateKey, 1, 128, keyPattern) ||
    !member(value.completionRule, completionRuleSet) ||
    !isApplicability(value.applicability) ||
    !array(value.evidenceRequirements, 0, 20) ||
    !value.evidenceRequirements.every(isRequirement)
  )
    return false;
  const requirements = value.evidenceRequirements;
  if (
    !unique(requirements.map((entry) => entry.key.toLowerCase())) ||
    (value.completionRule !== "confirmation" && requirements.length === 0) ||
    (value.completionRule === "exact_source_result" &&
      requirements.some((requirement) =>
        requirement.acceptedSourceKinds.some(
          (kind) => !resultSourceKindSet.has(kind),
        ),
      ))
  )
    return false;
  return true;
}

function hasSafeWeightTotal(
  items: readonly ReadinessItemDefinition[],
): boolean {
  let total = 0;
  for (const item of items) {
    total += item.weight;
    if (!Number.isSafeInteger(total)) return false;
  }
  return true;
}

function validTemplateConfiguration(
  applicability: unknown,
  categories: unknown,
  items: unknown,
): applicability is ReadinessApplicabilitySelector {
  if (
    !isApplicability(applicability) ||
    applicability.projectTypes.length === 0 ||
    !array(categories, 1, 100) ||
    !categories.every(isCategory) ||
    !array(items, 1, 1000) ||
    !items.every(isItemDefinition)
  )
    return false;
  const categoryValues = categories;
  const itemValues = items;
  const categoryKeys = new Set(categoryValues.map((entry) => entry.key));
  return (
    unique(categoryValues.map((entry) => entry.key.toLowerCase())) &&
    unique(itemValues.map((entry) => entry.key.toLowerCase())) &&
    hasSafeWeightTotal(itemValues) &&
    itemValues.every(
      (entry) =>
        categoryKeys.has(entry.categoryKey) &&
        (entry.applicability.projectTypes.length === 0 ||
          entry.applicability.projectTypes.every((type) =>
            applicability.projectTypes.includes(type),
          )),
    )
  );
}

export function isReadinessTemplateVersion(
  value: unknown,
): value is ReadinessTemplateVersion {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "templateGlobalId",
      "templateCode",
      "templateVersion",
      "optimisticVersion",
      "title",
      "publicationState",
      "applicability",
      "categories",
      "items",
      "changedByUserId",
      "changedAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.templateGlobalId) &&
    text(value.templateCode, 1, 64, codePattern) &&
    positive(value.templateVersion) &&
    positive(value.optimisticVersion) &&
    text(value.title, 1, 200) &&
    member(value.publicationState, publicationStateSet) &&
    validTemplateConfiguration(
      value.applicability,
      value.categories,
      value.items,
    ) &&
    text(value.changedByUserId, 3, 254, emailPattern) &&
    value.changedByUserId === value.changedByUserId.toLowerCase() &&
    timestamp(value.changedAt) &&
    uuid(value.requestId) &&
    text(value.traceId, 1, 128, tracePattern) &&
    hash(value.snapshotHash)
  );
}

function isExactReference(value: unknown): value is ReadinessExactReference {
  return (
    record(value) &&
    exact(value, ["globalId", "version", "snapshotHash"]) &&
    uuid(value.globalId) &&
    positive(value.version) &&
    hash(value.snapshotHash)
  );
}

function isProject(value: unknown): value is ReadinessProjectSnapshot {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "optimisticVersion",
      "snapshotHash",
      "projectType",
      "customerReferenceKeys",
      "industryKey",
    ]) &&
    uuid(value.globalId) &&
    positive(value.optimisticVersion) &&
    hash(value.snapshotHash) &&
    member(value.projectType, projectTypeSet) &&
    array(value.customerReferenceKeys, 0, 100) &&
    value.customerReferenceKeys.every((entry) => text(entry, 1, 256)) &&
    unique(value.customerReferenceKeys) &&
    sorted(value.customerReferenceKeys) &&
    text(value.industryKey, 1, 128, keyPattern)
  );
}

function isMemberReference(value: unknown): value is ReadinessMemberReference {
  return (
    record(value) &&
    exact(value, ["globalId", "userId", "optimisticVersion"]) &&
    uuid(value.globalId) &&
    text(value.userId, 3, 254, emailPattern) &&
    value.userId === value.userId.toLowerCase() &&
    positive(value.optimisticVersion)
  );
}

function isGateReference(value: unknown): value is ReadinessGateReference {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "gateKey",
      "optimisticVersion",
      "snapshotHash",
    ]) &&
    uuid(value.globalId) &&
    text(value.gateKey, 1, 128, keyPattern) &&
    positive(value.optimisticVersion) &&
    hash(value.snapshotHash)
  );
}

function isSourceReference(value: unknown): value is ReadinessSourceReference {
  if (
    !record(value) ||
    !exact(value, [
      "requirementKey",
      "kind",
      "state",
      "globalId",
      "sourceVersion",
      "snapshotHash",
      "reasonCode",
    ]) ||
    !text(value.requirementKey, 1, 128, keyPattern) ||
    !member(value.kind, sourceKindSet) ||
    !member(value.state, sourceStateSet)
  )
    return false;
  if (value.state === "unavailable")
    return (
      externalSourceKindSet.has(value.kind) &&
      value.globalId === null &&
      value.sourceVersion === null &&
      value.snapshotHash === null &&
      value.reasonCode ===
        unavailableReasons[value.kind as ReadinessExternalSourceKind]
    );
  return (
    uuid(value.globalId) &&
    positive(value.sourceVersion) &&
    hash(value.snapshotHash) &&
    (value.reasonCode === null || text(value.reasonCode, 1, 128, keyPattern))
  );
}

function appliesTo(
  selector: ReadinessApplicabilitySelector,
  project: ReadinessProjectSnapshot,
): boolean {
  return (
    (selector.projectTypes.length === 0 ||
      selector.projectTypes.includes(project.projectType)) &&
    (selector.customerReferenceKeys.length === 0 ||
      selector.customerReferenceKeys.some((key) =>
        project.customerReferenceKeys.includes(key),
      )) &&
    (selector.industryKeys.length === 0 ||
      selector.industryKeys.includes(project.industryKey))
  );
}

function requirementsSatisfied(item: ReadinessItemSnapshot): boolean {
  return item.definition.evidenceRequirements.every((requirement) => {
    const satisfied = item.sources.filter(
      (source) =>
        source.requirementKey === requirement.key &&
        requirement.acceptedSourceKinds.includes(source.kind) &&
        source.state === "satisfied",
    ).length;
    return satisfied >= requirement.minimumCount;
  });
}

function hasRequiredUnavailableSource(item: ReadinessItemSnapshot): boolean {
  return item.definition.evidenceRequirements.some((requirement) => {
    const matching = item.sources.filter(
      (source) =>
        source.requirementKey === requirement.key &&
        requirement.acceptedSourceKinds.includes(source.kind),
    );
    const satisfied = matching.filter(
      (source) => source.state === "satisfied",
    ).length;
    return (
      requirement.unavailableBlocks &&
      satisfied < requirement.minimumCount &&
      matching.some((source) => source.state === "unavailable")
    );
  });
}

function isItemSnapshot(
  value: unknown,
  project: ReadinessProjectSnapshot,
): value is ReadinessItemSnapshot {
  if (
    !record(value) ||
    !exact(value, [
      "globalId",
      "itemVersion",
      "definition",
      "applicable",
      "gate",
      "owner",
      "dueDate",
      "state",
      "confirmationValue",
      "sources",
    ]) ||
    !uuid(value.globalId) ||
    !positive(value.itemVersion) ||
    !isItemDefinition(value.definition) ||
    !boolean(value.applicable) ||
    !isGateReference(value.gate) ||
    value.gate.gateKey !== value.definition.gateKey ||
    !(value.owner === null || isMemberReference(value.owner)) ||
    !nullable(value.dueDate, date) ||
    !member(value.state, itemStateSet) ||
    !nullable(value.confirmationValue, (entry): entry is string =>
      text(entry, 1, 4000),
    ) ||
    !array(value.sources, 0, 100) ||
    !value.sources.every(isSourceReference)
  )
    return false;
  const item = value as unknown as ReadinessItemSnapshot;
  const requirements = new Map(
    item.definition.evidenceRequirements.map((requirement) => [
      requirement.key,
      requirement,
    ]),
  );
  const sourceIdentities = item.sources.map((source) =>
    [
      source.requirementKey,
      source.kind,
      source.globalId ?? "",
      source.sourceVersion ?? "",
    ].join("\u0000"),
  );
  const expectedSourceOrder = [...item.sources].sort((left, right) =>
    lexical(
      [left.requirementKey, left.kind, left.globalId ?? ""].join("\u0000"),
      [right.requirementKey, right.kind, right.globalId ?? ""].join("\u0000"),
    ),
  );
  if (
    !unique(sourceIdentities) ||
    !deepEqual(item.sources, expectedSourceOrder) ||
    item.sources.some((source) => {
      const requirement = requirements.get(source.requirementKey);
      return !requirement?.acceptedSourceKinds.includes(source.kind);
    }) ||
    item.applicable !== appliesTo(item.definition.applicability, project)
  )
    return false;
  if (!item.applicable)
    return (
      item.state === "not_applicable" &&
      item.owner === null &&
      item.dueDate === null &&
      item.confirmationValue === null &&
      item.sources.length === 0
    );
  if (
    item.state === "not_applicable" ||
    item.owner === null ||
    item.dueDate === null
  )
    return false;
  if (
    item.state === "complete" &&
    ((item.definition.completionRule === "confirmation" &&
      item.confirmationValue === null) ||
      !requirementsSatisfied(item))
  )
    return false;
  if (
    item.state === "failed" &&
    !item.sources.some((source) => source.state === "failed")
  )
    return false;
  return true;
}

function halfEvenBasisPoints(earned: number, applicable: number): number {
  const numerator = BigInt(earned) * 10_000n;
  const denominator = BigInt(applicable);
  const quotient = numerator / denominator;
  const remainder = numerator % denominator;
  const doubledRemainder = remainder * 2n;
  if (doubledRemainder > denominator) return Number(quotient + 1n);
  if (doubledRemainder < denominator) return Number(quotient);
  return Number(quotient % 2n === 0n ? quotient : quotient + 1n);
}

function deriveScore(
  items: readonly ReadinessItemSnapshot[],
  categoryKey: string | null,
): ReadinessScore {
  const applicable = items.filter(
    (item) =>
      item.applicable &&
      (categoryKey === null || item.definition.categoryKey === categoryKey),
  );
  const applicableWeight = applicable.reduce(
    (total, item) => total + item.definition.weight,
    0,
  );
  const earnedWeight = applicable.reduce(
    (total, item) =>
      total + (item.state === "complete" ? item.definition.weight : 0),
    0,
  );
  return applicableWeight === 0
    ? {
        categoryKey,
        earnedWeight: 0,
        applicableWeight: 0,
        basisPoints: null,
        state: "not_applicable",
      }
    : {
        categoryKey,
        earnedWeight,
        applicableWeight,
        basisPoints: halfEvenBasisPoints(earnedWeight, applicableWeight),
        state: "scored",
      };
}

function deriveEvaluation(
  categories: readonly ReadinessCategoryDefinition[],
  items: readonly ReadinessItemSnapshot[],
): ReadinessEvaluation {
  const blockers: ReadinessBlocker[] = [];
  for (const item of items) {
    if (!item.applicable) continue;
    if (item.definition.blockingLevel === "P0" && item.state !== "complete")
      blockers.push({
        code: "incomplete_p0",
        itemGlobalId: item.globalId,
        itemKey: item.definition.key,
        gate: item.gate,
      });
    if (
      item.sources.some(
        (source) =>
          qualitySourceKindSet.has(source.kind) && source.state === "failed",
      )
    )
      blockers.push({
        code: "failed_mandatory_quality",
        itemGlobalId: item.globalId,
        itemKey: item.definition.key,
        gate: item.gate,
      });
    if (hasRequiredUnavailableSource(item))
      blockers.push({
        code: "required_source_unavailable",
        itemGlobalId: item.globalId,
        itemKey: item.definition.key,
        gate: item.gate,
      });
  }
  blockers.sort((left, right) =>
    lexical(
      [left.gate.gateKey, left.itemKey, left.code].join("\u0000"),
      [right.gate.gateKey, right.itemKey, right.code].join("\u0000"),
    ),
  );
  return {
    formulaVersion: "readiness-score.v1",
    categoryScores: categories.map((category) =>
      deriveScore(items, category.key),
    ),
    totalScore: deriveScore(items, null),
    blockers,
    ready:
      blockers.length === 0 &&
      items.every(
        (item) =>
          !item.applicable ||
          !item.definition.required ||
          item.state === "complete",
      ),
  };
}

function isInstanceRevision(
  value: unknown,
): value is ReadinessInstanceRevision {
  if (
    !record(value) ||
    !exact(value, [
      "globalId",
      "instanceGlobalId",
      "tenantId",
      "project",
      "templateRevision",
      "instanceVersion",
      "predecessorGlobalId",
      "predecessorSnapshotHash",
      "categories",
      "items",
      "evaluation",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "versionKeyHash",
      "snapshotHash",
    ])
  )
    return false;
  const project = value.project;
  if (
    !uuid(value.globalId) ||
    !uuid(value.instanceGlobalId) ||
    !text(value.tenantId, 1, 128, tenantPattern) ||
    !isProject(project) ||
    !isExactReference(value.templateRevision) ||
    !positive(value.instanceVersion) ||
    !nullable(value.predecessorGlobalId, uuid) ||
    !nullable(value.predecessorSnapshotHash, hash) ||
    !array(value.categories, 1, 100) ||
    !value.categories.every(isCategory) ||
    !array(value.items, 1, 1000) ||
    !value.items.every((item) => isItemSnapshot(item, project)) ||
    !text(value.createdByUserId, 3, 254, emailPattern) ||
    value.createdByUserId !== value.createdByUserId.toLowerCase() ||
    !timestamp(value.createdAt) ||
    !uuid(value.requestId) ||
    !text(value.traceId, 1, 128, tracePattern) ||
    !hash(value.versionKeyHash) ||
    !hash(value.snapshotHash)
  )
    return false;
  const revision = value as unknown as ReadinessInstanceRevision;
  const categories = revision.categories;
  const items = revision.items;
  const categoryKeys = new Set(categories.map((entry) => entry.key));
  if (
    (revision.instanceVersion === 1) !==
      (revision.predecessorGlobalId === null &&
        revision.predecessorSnapshotHash === null) ||
    !unique(categories.map((entry) => entry.key.toLowerCase())) ||
    !unique(items.map((entry) => entry.definition.key.toLowerCase())) ||
    !unique(items.map((entry) => entry.globalId)) ||
    !hasSafeWeightTotal(items.map((entry) => entry.definition)) ||
    items.some((item) => !categoryKeys.has(item.definition.categoryKey)) ||
    !deepEqual(revision.evaluation, deriveEvaluation(categories, items))
  )
    return false;
  return true;
}

function isSuccessor(
  current: ReadinessInstanceRevision,
  successor: ReadinessInstanceRevision,
): boolean {
  if (
    successor.instanceGlobalId !== current.instanceGlobalId ||
    successor.tenantId !== current.tenantId ||
    !deepEqual(successor.project, current.project) ||
    !deepEqual(successor.templateRevision, current.templateRevision) ||
    successor.instanceVersion !== current.instanceVersion + 1 ||
    successor.predecessorGlobalId !== current.globalId ||
    successor.predecessorSnapshotHash !== current.snapshotHash ||
    !deepEqual(successor.categories, current.categories) ||
    successor.items.length !== current.items.length
  )
    return false;
  const changed: (readonly [ReadinessItemSnapshot, ReadinessItemSnapshot])[] =
    [];
  for (let index = 0; index < current.items.length; index += 1) {
    const before = current.items[index];
    const after = successor.items[index];
    if (!before || !after) return false;
    if (!deepEqual(before, after)) changed.push([before, after]);
  }
  if (changed.length !== 1) return false;
  const pair = changed[0];
  if (!pair) return false;
  const [before, after] = pair;
  return (
    before.globalId === after.globalId &&
    deepEqual(before.definition, after.definition) &&
    before.applicable === after.applicable &&
    deepEqual(before.gate, after.gate) &&
    after.itemVersion === before.itemVersion + 1
  );
}

function isSourceOption(value: unknown): value is ReadinessSourceOption {
  return (
    record(value) &&
    exact(value, [
      "kind",
      "globalId",
      "sourceVersion",
      "snapshotHash",
      "label",
      "stateLabelSource",
      "stateTerminal",
    ]) &&
    value.kind === "domain_work_item" &&
    uuid(value.globalId) &&
    positive(value.sourceVersion) &&
    hash(value.snapshotHash) &&
    text(value.label, 1, 280) &&
    member(value.stateLabelSource, sourceOptionStateLabels) &&
    boolean(value.stateTerminal)
  );
}

function isUnavailableProjection(
  value: unknown,
): value is ReadinessUnavailableProjection {
  return (
    record(value) &&
    exact(value, ["kind", "state", "reasonCode"]) &&
    member(value.kind, externalSourceKindSet) &&
    value.state === "unavailable" &&
    value.reasonCode ===
      unavailableReasons[value.kind as ReadinessExternalSourceKind]
  );
}

function isPermissions(value: unknown): value is ReadinessPermissions {
  return (
    record(value) &&
    exact(value, ["canManageTemplates", "canInitialize", "canRevise"]) &&
    boolean(value.canManageTemplates) &&
    boolean(value.canInitialize) &&
    boolean(value.canRevise)
  );
}

export function isReadinessWorkspace(
  value: unknown,
): value is ReadinessWorkspace {
  if (
    !record(value) ||
    !exact(value, [
      "projectGlobalId",
      "currentRevision",
      "revisions",
      "sourceOptions",
      "unavailableProjections",
      "permissions",
    ]) ||
    !uuid(value.projectGlobalId) ||
    !(
      value.currentRevision === null ||
      isInstanceRevision(value.currentRevision)
    ) ||
    !array(value.revisions, 0, 1000) ||
    !value.revisions.every(isInstanceRevision) ||
    !array(value.sourceOptions, 0, 1000) ||
    !value.sourceOptions.every(isSourceOption) ||
    !array(value.unavailableProjections, 5, 5) ||
    !value.unavailableProjections.every(isUnavailableProjection) ||
    !isPermissions(value.permissions)
  )
    return false;
  const workspace = value as unknown as ReadinessWorkspace;
  if (
    (workspace.revisions.length > 0 &&
      workspace.revisions[0]?.instanceVersion !== 1) ||
    workspace.revisions.some(
      (revision) => revision.project.globalId !== workspace.projectGlobalId,
    ) ||
    !unique(workspace.revisions.map((revision) => revision.globalId)) ||
    !unique(
      workspace.revisions.map((revision) =>
        [revision.instanceGlobalId, revision.instanceVersion].join("\u0000"),
      ),
    ) ||
    workspace.revisions.some((revision, index) => {
      const previous = workspace.revisions[index - 1];
      return index > 0 && (!previous || !isSuccessor(previous, revision));
    }) ||
    (workspace.currentRevision === null) !==
      (workspace.revisions.length === 0) ||
    (workspace.currentRevision !== null &&
      !deepEqual(
        workspace.currentRevision,
        workspace.revisions[workspace.revisions.length - 1],
      )) ||
    !unique(
      workspace.sourceOptions.map((option) =>
        [option.kind, option.globalId, option.sourceVersion].join("\u0000"),
      ),
    ) ||
    !deepEqual(
      workspace.unavailableProjections,
      readinessExternalSourceKinds.map((kind) => ({
        kind,
        state: "unavailable",
        reasonCode: unavailableReasons[kind],
      })),
    )
  )
    return false;
  return true;
}

export function isReadinessTemplateCatalog(
  value: unknown,
): value is ReadinessTemplateCatalog {
  return (
    record(value) &&
    exact(value, ["projectGlobalId", "templates"]) &&
    uuid(value.projectGlobalId) &&
    array(value.templates, 0, 1000) &&
    value.templates.every(
      (template) =>
        isReadinessTemplateVersion(template) &&
        template.publicationState === "published",
    ) &&
    unique(
      (value.templates as readonly ReadinessTemplateVersion[]).map(
        (template) => template.globalId,
      ),
    )
  );
}

function isCreateTemplateCommand(
  value: unknown,
): value is CreateReadinessTemplateCommand {
  return (
    record(value) &&
    exact(value, [
      "templateCode",
      "title",
      "applicability",
      "categories",
      "items",
    ]) &&
    text(value.templateCode, 1, 64, codePattern) &&
    text(value.title, 1, 200) &&
    validTemplateConfiguration(
      value.applicability,
      value.categories,
      value.items,
    )
  );
}

function isEditTemplateCommand(
  value: unknown,
): value is EditReadinessTemplateCommand {
  return (
    record(value) &&
    exact(value, [
      "expectedOptimisticVersion",
      "title",
      "applicability",
      "categories",
      "items",
    ]) &&
    positive(value.expectedOptimisticVersion) &&
    text(value.title, 1, 200) &&
    validTemplateConfiguration(
      value.applicability,
      value.categories,
      value.items,
    )
  );
}

function isPublishTemplateCommand(
  value: unknown,
): value is PublishReadinessTemplateCommand {
  return (
    record(value) &&
    exact(value, ["expectedOptimisticVersion"]) &&
    positive(value.expectedOptimisticVersion)
  );
}

function isAssignment(value: unknown): value is ReadinessAssignment {
  return (
    record(value) &&
    exact(value, ["itemKey", "ownerMemberGlobalId", "dueDate"]) &&
    text(value.itemKey, 1, 128, keyPattern) &&
    uuid(value.ownerMemberGlobalId) &&
    date(value.dueDate)
  );
}

function isInitializeCommand(
  value: unknown,
): value is InitializeProjectReadinessCommand {
  return (
    record(value) &&
    exact(value, [
      "templateRevisionGlobalId",
      "templateVersion",
      "templateSnapshotHash",
      "industryKey",
      "assignments",
    ]) &&
    uuid(value.templateRevisionGlobalId) &&
    positive(value.templateVersion) &&
    hash(value.templateSnapshotHash) &&
    text(value.industryKey, 1, 128, keyPattern) &&
    array(value.assignments, 1, 1000) &&
    value.assignments.every(isAssignment) &&
    unique(value.assignments.map((assignment) => assignment.itemKey))
  );
}

function isSourceSelection(value: unknown): value is ReadinessSourceSelection {
  if (!record(value)) return false;
  if (member(value.kind, internalSourceKindSet))
    return (
      exact(value, [
        "requirementKey",
        "kind",
        "globalId",
        "sourceVersion",
        "snapshotHash",
      ]) &&
      text(value.requirementKey, 1, 128, keyPattern) &&
      uuid(value.globalId) &&
      positive(value.sourceVersion) &&
      hash(value.snapshotHash)
    );
  return (
    member(value.kind, externalSourceKindSet) &&
    exact(value, ["requirementKey", "kind"]) &&
    text(value.requirementKey, 1, 128, keyPattern)
  );
}

function isReviseItemCommand(
  value: unknown,
): value is ReviseProjectReadinessItemCommand {
  if (
    !record(value) ||
    !exact(value, [
      "expectedInstanceVersion",
      "expectedRevisionGlobalId",
      "expectedRevisionSnapshotHash",
      "itemKey",
      "ownerMemberGlobalId",
      "dueDate",
      "state",
      "confirmationValue",
      "sources",
    ]) ||
    !positive(value.expectedInstanceVersion) ||
    !uuid(value.expectedRevisionGlobalId) ||
    !hash(value.expectedRevisionSnapshotHash) ||
    !text(value.itemKey, 1, 128, keyPattern) ||
    !uuid(value.ownerMemberGlobalId) ||
    !date(value.dueDate) ||
    !member(value.state, editableItemStateSet) ||
    !nullable(value.confirmationValue, (entry): entry is string =>
      text(entry, 1, 4000),
    ) ||
    !array(value.sources, 0, 100) ||
    !value.sources.every(isSourceSelection)
  )
    return false;
  const sources = value.sources;
  return unique(
    sources.map((source) =>
      "globalId" in source
        ? [
            source.requirementKey,
            source.kind,
            source.globalId,
            source.sourceVersion,
          ].join("\u0000")
        : [source.requirementKey, source.kind, "", ""].join("\u0000"),
    ),
  );
}

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit < 32 || codeUnit === 127) return true;
  }
  return false;
}

function isContext(value: ReadinessCommandContext): boolean {
  return (
    typeof value.csrfToken === "string" &&
    value.csrfToken.length >= 32 &&
    value.csrfToken.length <= 128 &&
    !hasControlCharacter(value.csrfToken) &&
    idempotencyPattern.test(value.idempotencyKey) &&
    value.signal instanceof AbortSignal
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function invalidResponse(traceId?: string): NpiTransportError {
  return new NpiTransportError(
    "invalid_response",
    traceId ?? `client-${globalThis.crypto.randomUUID()}`,
    traceId ? "trace" : "client",
  );
}

function requireUuid(value: string): string {
  if (!uuid(value)) throw requestNotReady();
  return value;
}

function requirePositive(value: number): number {
  if (!positive(value)) throw requestNotReady();
  return value;
}

function cancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ReadinessRequestCancelledError();
}

function replayHeader(response: Response): boolean | null {
  const header = response.headers.get("Idempotency-Replayed");
  if (header === "true") return true;
  if (header === "false") return false;
  return null;
}

function templateMatchesConfiguration(
  template: ReadinessTemplateVersion,
  command: CreateReadinessTemplateCommand | EditReadinessTemplateCommand,
): boolean {
  return (
    template.title === command.title &&
    deepEqual(template.applicability, command.applicability) &&
    deepEqual(template.categories, command.categories) &&
    deepEqual(template.items, command.items)
  );
}

function selectedSourcesMatch(
  sources: readonly ReadinessSourceReference[],
  selections: readonly ReadinessSourceSelection[],
): boolean {
  if (sources.length !== selections.length) return false;
  return selections.every((selection) =>
    sources.some((source) => {
      if (
        source.requirementKey !== selection.requirementKey ||
        source.kind !== selection.kind
      )
        return false;
      if ("globalId" in selection)
        return (
          source.globalId === selection.globalId &&
          source.sourceVersion === selection.sourceVersion &&
          source.snapshotHash === selection.snapshotHash &&
          source.state !== "unavailable"
        );
      return (
        source.state === "unavailable" &&
        source.globalId === null &&
        source.sourceVersion === null &&
        source.snapshotHash === null
      );
    }),
  );
}

export class LiveReadinessDataSource implements ReadinessDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async listEligibleTemplates(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ReadinessTemplateCatalog> {
    const expectedProjectId = requireUuid(projectId);
    cancelled(signal);
    try {
      const catalog = await this.http.request<ReadinessTemplateCatalog>(
        "/npi-readiness/templates",
        { signal },
        {
          query: { projectId: expectedProjectId },
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ReadinessTemplateCatalog =>
            isReadinessTemplateCatalog(value) &&
            value.projectGlobalId === expectedProjectId,
          validateResponse: (response) => response.status === 200,
        },
      );
      if (!(await isCanonicalReadinessTemplateCatalog(catalog, signal)))
        throw invalidResponse(catalog.templates.at(-1)?.traceId);
      return catalog;
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  async loadWorkspace(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ReadinessWorkspace> {
    const expectedProjectId = requireUuid(projectId);
    cancelled(signal);
    try {
      const workspace = await this.http.request<ReadinessWorkspace>(
        `/projects/${expectedProjectId}/npi-readiness`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ReadinessWorkspace =>
            isReadinessWorkspace(value) &&
            value.projectGlobalId === expectedProjectId,
          validateResponse: (response) => response.status === 200,
        },
      );
      if (!(await isCanonicalReadinessWorkspace(workspace, signal)))
        throw invalidResponse(workspace.currentRevision?.traceId);
      return workspace;
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  createTemplate(
    command: CreateReadinessTemplateCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessTemplateCommandResult> {
    if (!isCreateTemplateCommand(command) || !isContext(context))
      return Promise.reject(requestNotReady());
    return this.templateCommand(
      "/npi-readiness/templates",
      "POST",
      201,
      command,
      context,
      (template) =>
        template.publicationState === "draft" &&
        template.templateCode === command.templateCode &&
        template.templateVersion === 1 &&
        template.optimisticVersion === 1 &&
        templateMatchesConfiguration(template, command),
    );
  }

  editTemplate(
    templateId: string,
    templateVersion: number,
    command: EditReadinessTemplateCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessTemplateCommandResult> {
    const expectedTemplateId = requireUuid(templateId);
    const expectedTemplateVersion = requirePositive(templateVersion);
    if (!isEditTemplateCommand(command) || !isContext(context))
      return Promise.reject(requestNotReady());
    return this.templateCommand(
      `/npi-readiness/templates/${expectedTemplateId}/versions/${String(expectedTemplateVersion)}`,
      "PUT",
      200,
      command,
      context,
      (template) =>
        template.templateGlobalId === expectedTemplateId &&
        template.templateVersion === expectedTemplateVersion &&
        template.publicationState === "draft" &&
        template.optimisticVersion === command.expectedOptimisticVersion + 1 &&
        templateMatchesConfiguration(template, command),
    );
  }

  publishTemplate(
    templateId: string,
    templateVersion: number,
    command: PublishReadinessTemplateCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessTemplateCommandResult> {
    const expectedTemplateId = requireUuid(templateId);
    const expectedTemplateVersion = requirePositive(templateVersion);
    if (!isPublishTemplateCommand(command) || !isContext(context))
      return Promise.reject(requestNotReady());
    return this.templateCommand(
      `/npi-readiness/templates/${expectedTemplateId}/versions/${String(expectedTemplateVersion)}:publish`,
      "POST",
      200,
      command,
      context,
      (template) =>
        template.templateGlobalId === expectedTemplateId &&
        template.templateVersion === expectedTemplateVersion &&
        template.publicationState === "published" &&
        template.optimisticVersion === command.expectedOptimisticVersion + 1,
    );
  }

  initialize(
    projectId: string,
    command: InitializeProjectReadinessCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    if (!isInitializeCommand(command) || !isContext(context))
      return Promise.reject(requestNotReady());
    return this.workspaceCommand(
      `/projects/${expectedProjectId}/npi-readiness`,
      201,
      command,
      context,
      (workspace) => {
        const current = workspace.currentRevision;
        if (!current) return false;
        if (
          workspace.projectGlobalId !== expectedProjectId ||
          current.instanceVersion !== 1 ||
          current.project.industryKey !== command.industryKey ||
          current.templateRevision.globalId !==
            command.templateRevisionGlobalId ||
          current.templateRevision.version !== command.templateVersion ||
          current.templateRevision.snapshotHash !== command.templateSnapshotHash
        )
          return false;
        const applicableItems = current.items.filter((item) => item.applicable);
        return (
          applicableItems.length === command.assignments.length &&
          command.assignments.every((assignment) => {
            const item = applicableItems.find(
              (candidate) => candidate.definition.key === assignment.itemKey,
            );
            return (
              item?.owner?.globalId === assignment.ownerMemberGlobalId &&
              item.dueDate === assignment.dueDate &&
              item.state === "not_started"
            );
          })
        );
      },
    );
  }

  reviseItem(
    projectId: string,
    instanceId: string,
    command: ReviseProjectReadinessItemCommand,
    context: ReadinessCommandContext,
  ): Promise<ReadinessCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    const expectedInstanceId = requireUuid(instanceId);
    if (!isReviseItemCommand(command) || !isContext(context))
      return Promise.reject(requestNotReady());
    return this.workspaceCommand(
      `/projects/${expectedProjectId}/npi-readiness/${expectedInstanceId}/revisions`,
      201,
      command,
      context,
      (workspace) => {
        const current = workspace.currentRevision;
        if (!current) return false;
        if (
          workspace.projectGlobalId !== expectedProjectId ||
          current.instanceGlobalId !== expectedInstanceId ||
          current.instanceVersion !== command.expectedInstanceVersion + 1 ||
          current.predecessorGlobalId !== command.expectedRevisionGlobalId ||
          current.predecessorSnapshotHash !==
            command.expectedRevisionSnapshotHash
        )
          return false;
        const predecessor = workspace.revisions.at(-2);
        if (!predecessor) return false;
        const changedIndexes = current.items.flatMap((candidate, index) =>
          deepEqual(candidate, predecessor.items[index]) ? [] : [index],
        );
        const changedIndex = changedIndexes[0];
        if (changedIndexes.length !== 1 || changedIndex === undefined)
          return false;
        const changedBefore = predecessor.items[changedIndex];
        const changedAfter = current.items[changedIndex];
        if (
          changedAfter?.definition.key !== command.itemKey ||
          changedAfter.itemVersion !== (changedBefore?.itemVersion ?? 0) + 1
        )
          return false;
        const item = current.items.find(
          (candidate) => candidate.definition.key === command.itemKey,
        );
        return (
          item?.owner?.globalId === command.ownerMemberGlobalId &&
          item.dueDate === command.dueDate &&
          item.state === command.state &&
          item.confirmationValue === command.confirmationValue &&
          selectedSourcesMatch(item.sources, command.sources)
        );
      },
    );
  }

  private async templateCommand(
    path: string,
    method: "POST" | "PUT",
    expectedStatus: 200 | 201,
    body: object,
    context: ReadinessCommandContext,
    correlate: (template: ReadinessTemplateVersion) => boolean,
  ): Promise<ReadinessTemplateCommandResult> {
    cancelled(context.signal);
    let replayed = false;
    try {
      const template = await this.http.request<ReadinessTemplateVersion>(
        path,
        {
          body: JSON.stringify(body),
          headers: { "Idempotency-Key": context.idempotencyKey },
          method,
          signal: context.signal,
        },
        {
          csrfToken: context.csrfToken,
          requireIdempotencyReplay: true,
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ReadinessTemplateVersion =>
            isReadinessTemplateVersion(value) && correlate(value),
          validateResponse: (response) => {
            const header = replayHeader(response);
            if (response.status !== expectedStatus || header === null)
              return false;
            replayed = header;
            return true;
          },
        },
      );
      if (
        !(await isCanonicalReadinessTemplateVersion(template, context.signal))
      )
        throw invalidResponse(template.traceId);
      return { template, replayed };
    } catch (error) {
      cancelled(context.signal);
      throw error;
    }
  }

  private async workspaceCommand(
    path: string,
    expectedStatus: 201,
    body: object,
    context: ReadinessCommandContext,
    correlate: (workspace: ReadinessWorkspace) => boolean,
  ): Promise<ReadinessCommandResult> {
    cancelled(context.signal);
    let replayed = false;
    try {
      const workspace = await this.http.request<ReadinessWorkspace>(
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
          validate: (value): value is ReadinessWorkspace =>
            isReadinessWorkspace(value) && correlate(value),
          validateResponse: (response) => {
            const header = replayHeader(response);
            if (response.status !== expectedStatus || header === null)
              return false;
            replayed = header;
            return true;
          },
        },
      );
      if (!(await isCanonicalReadinessWorkspace(workspace, context.signal)))
        throw invalidResponse(workspace.currentRevision?.traceId);
      return { workspace, replayed };
    } catch (error) {
      cancelled(context.signal);
      throw error;
    }
  }
}
