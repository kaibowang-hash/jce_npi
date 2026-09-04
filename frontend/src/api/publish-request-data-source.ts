import { NpiHttpClient, NpiTransportError } from "./http";
import type {
  EngineeringBomCommandContext,
  EngineeringBomProjectViewModel,
  EngineeringBomRevisionReferenceViewModel,
  EngineeringBomSummaryViewModel,
} from "./ebom-data-source";

export type PublishRequestState = "validated" | "manual_intervention";
export type PublishNodeState =
  | "validated"
  | "queued"
  | "processing"
  | "succeeded"
  | "failed_retryable"
  | "failed_final"
  | "uncertain_after_timeout"
  | "blocked_mapping"
  | "target_unavailable";
export type PublishMappingState = "unmapped" | "current" | "stale" | "conflict";
export type PublishFaultKind =
  | "duplicate_request"
  | "payload_conflict"
  | "timeout_after_possible_commit"
  | "rate_limited"
  | "target_server_error"
  | "business_validation"
  | "partial_node_success"
  | "stale_mapping"
  | "target_unavailable"
  | "restart_replay";
export type PublishRetryDirective =
  | "none"
  | "replay_sealed_response"
  | "reject_payload_conflict"
  | "reconcile_before_retry"
  | "retry_after"
  | "retry_same_idempotency"
  | "manual_correction"
  | "retry_failed_nodes_only"
  | "resolve_mapping"
  | "replay_original_request";
export type PublishNodeOperation =
  | "create_item"
  | "update_item_engineering_fields"
  | "create_or_update_mbom";

export interface PublishPolicyReferenceViewModel {
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface PublishPolicyOptionViewModel extends PublishPolicyReferenceViewModel {
  key: string;
  title: string;
  targetMode: "mock";
}

export interface ReleasedEbomEvidenceViewModel {
  projectGlobalId: string;
  ebomGlobalId: string;
  ebomVersion: number;
  revisionGlobalId: string;
  revisionNumber: number;
  revisionSnapshotHash: string;
  lifecycleVersion: number;
  releaseEventGlobalId: string;
  releaseEventHash: string;
  ebomPolicyGlobalId: string;
  ebomPolicyVersion: number;
  ebomPolicySnapshotHash: string;
  approvalEvidenceIds: readonly string[];
  releasedAt: string;
}

export interface PublishLineInputViewModel {
  globalId: string;
  lineKey: string;
  parentLineKey: string | null;
  engineeringItemId: string;
  description: string;
  quantity: string;
  engineeringUom: string;
  alternateForLineKey: string | null;
  alternateGroupKey: string | null;
  effectivityStart: string | null;
  effectivityEnd: string | null;
  attributes: Readonly<Record<string, string>>;
  lineHash: string;
}

export interface PublishMappingObservationViewModel {
  state: PublishMappingState;
  version: number;
  formalItemCode: null;
  formalMbomId: null;
  targetVersion: null;
  observedAt: string | null;
}

export interface PublishNodeResultViewModel {
  globalId: string;
  nodeGlobalId: string;
  nodeInputHash: string;
  attemptNumber: number;
  state: PublishNodeState;
  faultKind: PublishFaultKind | null;
  futureRetryDirective: PublishRetryDirective;
  futureRetryable: boolean;
  reconciliationRequired: boolean;
  retryAfterRequired: boolean;
  phase5DispatchAllowed: false;
  formalItemCode: null;
  formalMbomId: null;
  targetVersion: null;
  occurredAt: string;
  resultHash: string;
}

export interface PublishNodeViewModel {
  globalId: string;
  line: PublishLineInputViewModel;
  mapping: PublishMappingObservationViewModel;
  operations: readonly PublishNodeOperation[];
  resultState: PublishNodeState;
  inputHash: string;
  results: readonly PublishNodeResultViewModel[];
}

export interface PublishRequestCapabilitiesViewModel {
  view: boolean;
  create: boolean;
  dispatch: false;
  retry: false;
  reconcile: false;
}

export interface EngineeringBomPublishRequestViewModel {
  globalId: string;
  operation: "publish_released_ebom_item_mbom";
  apiVersion: "npi.erp-publish.v1";
  policy: PublishPolicyReferenceViewModel;
  releasedEbom: ReleasedEbomEvidenceViewModel;
  targetMode: "mock";
  state: PublishRequestState;
  dispatchAllowed: false;
  actorUserId: string;
  requestId: string;
  traceId: string;
  payloadHash: string;
  ownedFields: readonly string[];
  nodes: readonly PublishNodeViewModel[];
  capabilities: PublishRequestCapabilitiesViewModel;
  createdAt: string;
}

export interface PublishRequestPermissionsViewModel {
  view: boolean;
  create: boolean;
}

export interface EngineeringBomPublishRequestListViewModel {
  project: EngineeringBomProjectViewModel;
  ebom: EngineeringBomSummaryViewModel;
  revision: EngineeringBomRevisionReferenceViewModel;
  permissions: PublishRequestPermissionsViewModel;
  policies: readonly PublishPolicyOptionViewModel[];
  items: readonly EngineeringBomPublishRequestViewModel[];
}

export interface CreateEngineeringBomPublishRequestCommand {
  expectedEbomVersion: number;
  expectedRevisionSnapshotHash: string;
  expectedLifecycleVersion: number;
  publishPolicyGlobalId: string;
  publishPolicyVersion: number;
  publishPolicySnapshotHash: string;
  targetMode: "mock";
  confirmed: true;
  confirmationIntent: "validate_exact_released_ebom_for_item_mbom_publish";
  reason: string;
}

export interface EngineeringBomPublishRequestDataSource {
  loadRequests(
    projectId: string,
    ebomId: string,
    revisionId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomPublishRequestListViewModel>;
  loadRequest(
    projectId: string,
    ebomId: string,
    revisionId: string,
    publishRequestId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomPublishRequestViewModel>;
  createRequest(
    projectId: string,
    ebomId: string,
    revisionId: string,
    command: CreateEngineeringBomPublishRequestCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomPublishRequestViewModel>;
}

export class PublishRequestCancelledError extends Error {
  constructor() {
    super("The publish request was cancelled.");
    this.name = "PublishRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const keyPattern = /^[a-z][a-z0-9_.-]{0,63}$/u;
const tracePattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const decimalPattern = /^[0-9]+(?:\.[0-9]+)?$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u;
const mappingStates = new Set<PublishMappingState>([
  "unmapped",
  "current",
  "stale",
  "conflict",
]);
const nodeStates = new Set<PublishNodeState>([
  "validated",
  "queued",
  "processing",
  "succeeded",
  "failed_retryable",
  "failed_final",
  "uncertain_after_timeout",
  "blocked_mapping",
  "target_unavailable",
]);
const faultKinds = new Set<PublishFaultKind>([
  "duplicate_request",
  "payload_conflict",
  "timeout_after_possible_commit",
  "rate_limited",
  "target_server_error",
  "business_validation",
  "partial_node_success",
  "stale_mapping",
  "target_unavailable",
  "restart_replay",
]);
const retryDirectives = new Set<PublishRetryDirective>([
  "none",
  "replay_sealed_response",
  "reject_payload_conflict",
  "reconcile_before_retry",
  "retry_after",
  "retry_same_idempotency",
  "manual_correction",
  "retry_failed_nodes_only",
  "resolve_mapping",
  "replay_original_request",
]);
const operations = new Set<PublishNodeOperation>([
  "create_item",
  "update_item_engineering_fields",
  "create_or_update_mbom",
]);
const ownedFields = new Set([
  "engineering_item_id",
  "engineering_description",
  "ebom_hierarchy",
  "engineering_quantity",
  "engineering_uom",
  "alternates",
  "effectivity",
  "engineering_attributes",
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

function string(
  value: unknown,
  minimum: number,
  maximum: number,
  pattern?: RegExp,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    (pattern?.test(value) ?? true)
  );
}

function positive(value: unknown): value is number {
  return (
    Number.isInteger(value) &&
    Number(value) >= 1 &&
    Number(value) <= 2_147_483_647
  );
}

function nonNegative(value: unknown): value is number {
  return (
    Number.isInteger(value) &&
    Number(value) >= 0 &&
    Number(value) <= 2_147_483_647
  );
}

function uuid(value: unknown): value is string {
  return string(value, 36, 36, uuidPattern);
}

function hash(value: unknown): value is string {
  return string(value, 64, 64, hashPattern);
}

function timestamp(value: unknown): value is string {
  return (
    string(value, 20, 40, timestampPattern) && !Number.isNaN(Date.parse(value))
  );
}

function nullable<T>(
  value: unknown,
  check: (candidate: unknown) => candidate is T,
): value is T | null {
  return value === null || check(value);
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

function isPolicyReference(
  value: unknown,
): value is PublishPolicyReferenceViewModel {
  return (
    record(value) &&
    exact(value, ["globalId", "version", "snapshotHash"]) &&
    uuid(value.globalId) &&
    positive(value.version) &&
    hash(value.snapshotHash)
  );
}

function isPolicyOption(value: unknown): value is PublishPolicyOptionViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "version",
      "snapshotHash",
      "key",
      "title",
      "targetMode",
    ]) &&
    uuid(value.globalId) &&
    positive(value.version) &&
    hash(value.snapshotHash) &&
    string(value.key, 1, 64, keyPattern) &&
    string(value.title, 1, 140) &&
    value.targetMode === "mock"
  );
}

function isProject(value: unknown): value is EngineeringBomProjectViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "businessCode",
      "title",
      "lifecycleState",
      "optimisticVersion",
    ]) &&
    uuid(value.globalId) &&
    string(value.businessCode, 1, 140) &&
    string(value.title, 1, 280) &&
    string(value.lifecycleState, 1, 64) &&
    positive(value.optimisticVersion)
  );
}

function isRevisionReference(
  value: unknown,
): value is EngineeringBomRevisionReferenceViewModel {
  return (
    record(value) &&
    exact(value, ["globalId", "revisionNumber", "snapshotHash"]) &&
    uuid(value.globalId) &&
    positive(value.revisionNumber) &&
    hash(value.snapshotHash)
  );
}

function isEbomSummary(
  value: unknown,
): value is EngineeringBomSummaryViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "engineeringBomKey",
      "title",
      "policy",
      "optimisticVersion",
      "latestRevision",
    ]) &&
    uuid(value.globalId) &&
    string(value.engineeringBomKey, 1, 64) &&
    string(value.title, 1, 140) &&
    isPolicyReference(value.policy) &&
    positive(value.optimisticVersion) &&
    nullable(value.latestRevision, isRevisionReference)
  );
}

function isEvidence(value: unknown): value is ReleasedEbomEvidenceViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "projectGlobalId",
      "ebomGlobalId",
      "ebomVersion",
      "revisionGlobalId",
      "revisionNumber",
      "revisionSnapshotHash",
      "lifecycleVersion",
      "releaseEventGlobalId",
      "releaseEventHash",
      "ebomPolicyGlobalId",
      "ebomPolicyVersion",
      "ebomPolicySnapshotHash",
      "approvalEvidenceIds",
      "releasedAt",
    ])
  )
    return false;
  const approvals = value.approvalEvidenceIds;
  return (
    uuid(value.projectGlobalId) &&
    uuid(value.ebomGlobalId) &&
    positive(value.ebomVersion) &&
    uuid(value.revisionGlobalId) &&
    positive(value.revisionNumber) &&
    hash(value.revisionSnapshotHash) &&
    positive(value.lifecycleVersion) &&
    uuid(value.releaseEventGlobalId) &&
    hash(value.releaseEventHash) &&
    uuid(value.ebomPolicyGlobalId) &&
    positive(value.ebomPolicyVersion) &&
    hash(value.ebomPolicySnapshotHash) &&
    Array.isArray(approvals) &&
    approvals.length >= 1 &&
    approvals.length <= 32 &&
    approvals.every(uuid) &&
    unique(approvals) &&
    timestamp(value.releasedAt)
  );
}

function isAttributes(
  value: unknown,
): value is Readonly<Record<string, string>> {
  return (
    record(value) &&
    Object.keys(value).length <= 50 &&
    Object.entries(value).every(
      ([key, entry]) => keyPattern.test(key) && string(entry, 0, 280),
    )
  );
}

function isLine(value: unknown): value is PublishLineInputViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "lineKey",
      "parentLineKey",
      "engineeringItemId",
      "description",
      "quantity",
      "engineeringUom",
      "alternateForLineKey",
      "alternateGroupKey",
      "effectivityStart",
      "effectivityEnd",
      "attributes",
      "lineHash",
    ]) &&
    uuid(value.globalId) &&
    string(value.lineKey, 1, 64) &&
    nullable(value.parentLineKey, (item): item is string =>
      string(item, 1, 64),
    ) &&
    string(value.engineeringItemId, 1, 128) &&
    string(value.description, 1, 280) &&
    string(value.quantity, 1, 64, decimalPattern) &&
    string(value.engineeringUom, 1, 16) &&
    nullable(value.alternateForLineKey, (item): item is string =>
      string(item, 1, 64),
    ) &&
    nullable(value.alternateGroupKey, (item): item is string =>
      string(item, 1, 64),
    ) &&
    nullable(value.effectivityStart, (item): item is string =>
      string(item, 10, 10, datePattern),
    ) &&
    nullable(value.effectivityEnd, (item): item is string =>
      string(item, 10, 10, datePattern),
    ) &&
    isAttributes(value.attributes) &&
    hash(value.lineHash)
  );
}

function isMapping(
  value: unknown,
): value is PublishMappingObservationViewModel {
  return (
    record(value) &&
    exact(value, [
      "state",
      "version",
      "formalItemCode",
      "formalMbomId",
      "targetVersion",
      "observedAt",
    ]) &&
    mappingStates.has(value.state as PublishMappingState) &&
    nonNegative(value.version) &&
    value.formalItemCode === null &&
    value.formalMbomId === null &&
    value.targetVersion === null &&
    nullable(value.observedAt, timestamp)
  );
}

function isResult(value: unknown): value is PublishNodeResultViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "nodeGlobalId",
      "nodeInputHash",
      "attemptNumber",
      "state",
      "faultKind",
      "futureRetryDirective",
      "futureRetryable",
      "reconciliationRequired",
      "retryAfterRequired",
      "phase5DispatchAllowed",
      "formalItemCode",
      "formalMbomId",
      "targetVersion",
      "occurredAt",
      "resultHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.nodeGlobalId) &&
    hash(value.nodeInputHash) &&
    nonNegative(value.attemptNumber) &&
    nodeStates.has(value.state as PublishNodeState) &&
    (value.faultKind === null ||
      faultKinds.has(value.faultKind as PublishFaultKind)) &&
    retryDirectives.has(value.futureRetryDirective as PublishRetryDirective) &&
    typeof value.futureRetryable === "boolean" &&
    typeof value.reconciliationRequired === "boolean" &&
    typeof value.retryAfterRequired === "boolean" &&
    value.phase5DispatchAllowed === false &&
    value.formalItemCode === null &&
    value.formalMbomId === null &&
    value.targetVersion === null &&
    timestamp(value.occurredAt) &&
    hash(value.resultHash)
  );
}

function isNode(value: unknown): value is PublishNodeViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "globalId",
      "line",
      "mapping",
      "operations",
      "resultState",
      "inputHash",
      "results",
    ]) ||
    !uuid(value.globalId) ||
    !isLine(value.line) ||
    !isMapping(value.mapping) ||
    !Array.isArray(value.operations) ||
    value.operations.length > 2 ||
    !value.operations.every((item) =>
      operations.has(item as PublishNodeOperation),
    ) ||
    !unique(value.operations as string[]) ||
    !nodeStates.has(value.resultState as PublishNodeState) ||
    !hash(value.inputHash) ||
    !Array.isArray(value.results) ||
    value.results.length < 1 ||
    value.results.length > 100 ||
    !value.results.every(isResult)
  )
    return false;
  return value.results.every(
    (result) =>
      result.nodeGlobalId === value.globalId &&
      result.nodeInputHash === value.inputHash,
  );
}

function isCapabilities(
  value: unknown,
): value is PublishRequestCapabilitiesViewModel {
  return (
    record(value) &&
    exact(value, ["view", "create", "dispatch", "retry", "reconcile"]) &&
    typeof value.view === "boolean" &&
    typeof value.create === "boolean" &&
    value.dispatch === false &&
    value.retry === false &&
    value.reconcile === false
  );
}

export function isEngineeringBomPublishRequestResponse(
  value: unknown,
): value is EngineeringBomPublishRequestViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "globalId",
      "operation",
      "apiVersion",
      "policy",
      "releasedEbom",
      "targetMode",
      "state",
      "dispatchAllowed",
      "actorUserId",
      "requestId",
      "traceId",
      "payloadHash",
      "ownedFields",
      "nodes",
      "capabilities",
      "createdAt",
    ]) ||
    !uuid(value.globalId) ||
    value.operation !== "publish_released_ebom_item_mbom" ||
    value.apiVersion !== "npi.erp-publish.v1" ||
    !isPolicyReference(value.policy) ||
    !isEvidence(value.releasedEbom) ||
    value.targetMode !== "mock" ||
    (value.state !== "validated" && value.state !== "manual_intervention") ||
    value.dispatchAllowed !== false ||
    !string(value.actorUserId, 1, 254) ||
    !uuid(value.requestId) ||
    !string(value.traceId, 8, 128, tracePattern) ||
    !hash(value.payloadHash) ||
    !Array.isArray(value.ownedFields) ||
    value.ownedFields.length < 1 ||
    value.ownedFields.length > 8 ||
    !value.ownedFields.every(
      (item) => typeof item === "string" && ownedFields.has(item),
    ) ||
    !unique(value.ownedFields as string[]) ||
    !Array.isArray(value.nodes) ||
    value.nodes.length < 1 ||
    value.nodes.length > 500 ||
    !value.nodes.every(isNode) ||
    !isCapabilities(value.capabilities) ||
    !timestamp(value.createdAt)
  )
    return false;
  return true;
}

export function isEngineeringBomPublishRequestListResponse(
  value: unknown,
): value is EngineeringBomPublishRequestListViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "project",
      "ebom",
      "revision",
      "permissions",
      "policies",
      "items",
    ]) ||
    !isProject(value.project) ||
    !isEbomSummary(value.ebom) ||
    !isRevisionReference(value.revision) ||
    !record(value.permissions) ||
    !exact(value.permissions, ["view", "create"]) ||
    typeof value.permissions.view !== "boolean" ||
    typeof value.permissions.create !== "boolean" ||
    !Array.isArray(value.policies) ||
    value.policies.length > 64 ||
    !value.policies.every(isPolicyOption) ||
    !Array.isArray(value.items) ||
    value.items.length > 200 ||
    !value.items.every(isEngineeringBomPublishRequestResponse)
  )
    return false;
  const projectGlobalId = value.project.globalId;
  const ebomGlobalId = value.ebom.globalId;
  const revisionGlobalId = value.revision.globalId;
  const revisionSnapshotHash = value.revision.snapshotHash;
  const policies = value.policies;
  return value.items.every(
    (item) =>
      item.releasedEbom.projectGlobalId === projectGlobalId &&
      item.releasedEbom.ebomGlobalId === ebomGlobalId &&
      item.releasedEbom.revisionGlobalId === revisionGlobalId &&
      item.releasedEbom.revisionSnapshotHash === revisionSnapshotHash &&
      policies.some(
        (policy) =>
          policy.globalId === item.policy.globalId &&
          policy.version === item.policy.version &&
          policy.snapshotHash === item.policy.snapshotHash,
      ),
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
  if (signal.aborted) throw new PublishRequestCancelledError();
}

function validContext(context: EngineeringBomCommandContext): boolean {
  return (
    string(context.csrfToken, 16, 512) &&
    string(context.idempotencyKey, 8, 128, /^[A-Za-z0-9._:-]+$/u) &&
    context.signal instanceof AbortSignal
  );
}

export class LiveEngineeringBomPublishRequestDataSource implements EngineeringBomPublishRequestDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadRequests(
    projectId: string,
    ebomId: string,
    revisionId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomPublishRequestListViewModel> {
    if (![projectId, ebomId, revisionId].every(uuid)) throw requestNotReady();
    return this.query(
      `/projects/${projectId}/eboms/${ebomId}/revisions/${revisionId}/publish-requests`,
      signal,
      (value): value is EngineeringBomPublishRequestListViewModel =>
        isEngineeringBomPublishRequestListResponse(value) &&
        value.project.globalId === projectId &&
        value.ebom.globalId === ebomId &&
        value.revision.globalId === revisionId,
    );
  }

  async loadRequest(
    projectId: string,
    ebomId: string,
    revisionId: string,
    publishRequestId: string,
    signal: AbortSignal,
  ): Promise<EngineeringBomPublishRequestViewModel> {
    if (![projectId, ebomId, revisionId, publishRequestId].every(uuid))
      throw requestNotReady();
    return this.query(
      `/projects/${projectId}/eboms/${ebomId}/revisions/${revisionId}/publish-requests/${publishRequestId}`,
      signal,
      (value): value is EngineeringBomPublishRequestViewModel =>
        isEngineeringBomPublishRequestResponse(value) &&
        value.globalId === publishRequestId &&
        value.releasedEbom.projectGlobalId === projectId &&
        value.releasedEbom.ebomGlobalId === ebomId &&
        value.releasedEbom.revisionGlobalId === revisionId,
    );
  }

  async createRequest(
    projectId: string,
    ebomId: string,
    revisionId: string,
    command: CreateEngineeringBomPublishRequestCommand,
    context: EngineeringBomCommandContext,
  ): Promise<EngineeringBomPublishRequestViewModel> {
    const targetMode: unknown = command.targetMode;
    const confirmed: unknown = command.confirmed;
    const confirmationIntent: unknown = command.confirmationIntent;
    const body = {
      expectedEbomVersion: command.expectedEbomVersion,
      expectedRevisionSnapshotHash: command.expectedRevisionSnapshotHash,
      expectedLifecycleVersion: command.expectedLifecycleVersion,
      publishPolicyGlobalId: command.publishPolicyGlobalId,
      publishPolicyVersion: command.publishPolicyVersion,
      publishPolicySnapshotHash: command.publishPolicySnapshotHash,
      targetMode,
      confirmed,
      confirmationIntent,
      reason: command.reason.trim(),
    };
    if (
      ![projectId, ebomId, revisionId, body.publishPolicyGlobalId].every(
        uuid,
      ) ||
      !positive(body.expectedEbomVersion) ||
      !hash(body.expectedRevisionSnapshotHash) ||
      !positive(body.expectedLifecycleVersion) ||
      !positive(body.publishPolicyVersion) ||
      !hash(body.publishPolicySnapshotHash) ||
      targetMode !== "mock" ||
      confirmed !== true ||
      confirmationIntent !==
        "validate_exact_released_ebom_for_item_mbom_publish" ||
      !string(body.reason, 1, 280) ||
      !validContext(context)
    )
      throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<EngineeringBomPublishRequestViewModel>(
        `/projects/${projectId}/eboms/${ebomId}/revisions/${revisionId}/publish-requests`,
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
          validate: (value): value is EngineeringBomPublishRequestViewModel =>
            isEngineeringBomPublishRequestResponse(value) &&
            value.state === "validated" &&
            value.releasedEbom.projectGlobalId === projectId &&
            value.releasedEbom.ebomGlobalId === ebomId &&
            value.releasedEbom.revisionGlobalId === revisionId &&
            value.releasedEbom.ebomVersion === body.expectedEbomVersion &&
            value.releasedEbom.revisionSnapshotHash ===
              body.expectedRevisionSnapshotHash &&
            value.releasedEbom.lifecycleVersion ===
              body.expectedLifecycleVersion &&
            value.policy.globalId === body.publishPolicyGlobalId &&
            value.policy.version === body.publishPolicyVersion &&
            value.policy.snapshotHash === body.publishPolicySnapshotHash,
        },
      );
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }

  private async query<T>(
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
}
