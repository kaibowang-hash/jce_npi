import { NpiHttpClient, NpiTransportError } from "./http";

export const integrationOperationKinds = [
  "receive_project_submission",
  "publish_item",
  "publish_mbom",
  "create_tool_asset",
  "update_tool_asset",
  "receive_engineering_change_event",
  "publish_change_implementation_summary",
] as const;
export type IntegrationOperationKind =
  (typeof integrationOperationKinds)[number];

export const integrationOperationStates = [
  "queued",
  "processing",
  "succeeded",
  "failed_retryable",
  "failed_final",
  "uncertain",
  "partial",
  "conflict",
  "quarantined",
  "unavailable",
] as const;
export type IntegrationOperationState =
  (typeof integrationOperationStates)[number];

export type IntegrationOperationFaultClass =
  | "none"
  | "retryable_before_uncertain_boundary"
  | "final_business_failure"
  | "uncertain_after_boundary"
  | "partial_result"
  | "identity_conflict"
  | "authenticity_quarantine"
  | "target_unavailable"
  | "unknown_raw_state";

export type IntegrationOperationReplayReason =
  | "eligible"
  | "unknown_raw_state"
  | "state_not_retryable"
  | "uncertain_boundary"
  | "reconciliation_required"
  | "partial_result";

export interface IntegrationOperationItem {
  tenantId: string;
  projectGlobalId: string;
  operationKind: IntegrationOperationKind;
  operationGlobalId: string;
  sourceGlobalId: string;
  operationVersion: number;
  rawState: string;
  sharedState: IntegrationOperationState;
  sourceSnapshotHash: string;
  targetIdempotencyKeyHash: string;
  logicalDlq: boolean;
  faultClass: IntegrationOperationFaultClass;
  replayEligible: boolean;
  replayEligibilityReason: IntegrationOperationReplayReason;
  reconciliationRequired: boolean;
  updatedAt: string;
}

export interface IntegrationOperationCollection {
  projectGlobalId: string;
  permissions: { view: boolean; act: boolean };
  items: readonly IntegrationOperationItem[];
  nextCursor: string | null;
}

export type IntegrationOperationAttempt =
  | {
      attemptNumber: number;
      state: string;
      adapterBoundaryCrossed: boolean;
      reconciliationRequired: boolean;
      safeErrorCode: string | null;
    }
  | {
      attemptGlobalId: string;
      attemptNumber: number;
      state: string;
      adapterBoundaryCrossed: boolean;
      reconciliationRequired: boolean;
      safeErrorCode: string | null;
      startedAt: string | null;
      finishedAt: string | null;
    };

export interface IntegrationOperationResult {
  resultGlobalId: string;
  attemptGlobalId: string;
  attemptNumber: number;
  state: string;
  authority: "none" | "synthetic" | "authoritative_sandbox";
  responseAuthenticated: boolean;
  faultKind: string | null;
  observedAt: string | null;
}

export interface IntegrationOperationActionHistoryItem {
  actionGlobalId: string;
  actionKind: IntegrationOperationActionKind;
  outcomeState: IntegrationOperationActionOutcome;
  outcomeReferenceGlobalId: string | null;
  actorUserId: string;
  traceId: string;
  createdAt: string;
}

export interface IntegrationOperationDetail {
  projectGlobalId: string;
  permissions: { view: boolean; act: boolean };
  operation: IntegrationOperationItem & {
    attempts: readonly IntegrationOperationAttempt[];
    results: readonly IntegrationOperationResult[];
    actions: readonly IntegrationOperationActionHistoryItem[];
  };
}

export type IntegrationOperationActionKind =
  | "replay"
  | "request_reconciliation";
export type IntegrationOperationActionOutcome =
  | "replay_requested"
  | "reconciliation_requested";

export interface IntegrationOperationActionResult {
  actionGlobalId: string;
  operationGlobalId: string;
  outcomeState: IntegrationOperationActionOutcome;
  outcomeReferenceGlobalId: string | null;
}

export interface IntegrationOperationFilters {
  operationKind?: IntegrationOperationKind | undefined;
  sharedState?: IntegrationOperationState | undefined;
  cursor?: string | undefined;
  limit?: number | undefined;
  logicalDlq?: boolean | undefined;
}

export interface IntegrationOperationCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface IntegrationOperationsDataSource {
  loadOperations(
    projectId: string,
    filters: IntegrationOperationFilters,
    signal: AbortSignal,
  ): Promise<IntegrationOperationCollection>;
  loadOperation(
    projectId: string,
    operationKind: IntegrationOperationKind,
    operationId: string,
    signal: AbortSignal,
  ): Promise<IntegrationOperationDetail>;
  requestAction(
    projectId: string,
    operation: IntegrationOperationItem,
    action: IntegrationOperationActionKind,
    context: IntegrationOperationCommandContext,
  ): Promise<IntegrationOperationActionResult>;
}

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA = /^[a-f0-9]{64}$/u;
const SAFE_STATE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$/u;
const SAFE_IDEMPOTENCY = /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/u;
const SAFE_TRACE = /^[A-Za-z0-9._:-]{8,128}$/u;
const KIND = new Set<string>(integrationOperationKinds);
const STATE = new Set<string>(integrationOperationStates);
const FAULT = new Set<string>([
  "none",
  "retryable_before_uncertain_boundary",
  "final_business_failure",
  "uncertain_after_boundary",
  "partial_result",
  "identity_conflict",
  "authenticity_quarantine",
  "target_unavailable",
  "unknown_raw_state",
]);
const REPLAY_REASON = new Set<string>([
  "eligible",
  "unknown_raw_state",
  "state_not_retryable",
  "uncertain_boundary",
  "reconciliation_required",
  "partial_result",
]);
const AUTHORITY = new Set<string>([
  "none",
  "synthetic",
  "authoritative_sandbox",
]);
const ACTION_OUTCOME = new Set<string>([
  "replay_requested",
  "reconciliation_requested",
]);
const LOGICAL_DLQ_STATES = new Set<IntegrationOperationState>([
  "failed_retryable",
  "failed_final",
  "uncertain",
  "partial",
  "conflict",
  "quarantined",
]);
const ACTION_PATH: Readonly<Partial<Record<IntegrationOperationKind, string>>> =
  {
    receive_project_submission: "receive-project-submissions",
    publish_item: "item-publishes",
    publish_mbom: "mbom-publishes",
    create_tool_asset: "tool-asset-creates",
    update_tool_asset: "tool-asset-updates",
  };

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

function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

function sha(value: unknown): value is string {
  return typeof value === "string" && SHA.test(value);
}

function boundedText(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= maximum &&
    value === value.trim()
  );
}

function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function instant(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length >= 20 &&
    value.length <= 40 &&
    Number.isFinite(Date.parse(value))
  );
}

function optionalInstant(value: unknown): value is string | null {
  return value === null || instant(value);
}

function optionalBoundedText(value: unknown, maximum: number): boolean {
  return value === null || boundedText(value, maximum);
}

function permissions(value: unknown): value is {
  view: boolean;
  act: boolean;
} {
  return (
    record(value) &&
    exact(value, ["view", "act"]) &&
    typeof value.view === "boolean" &&
    typeof value.act === "boolean" &&
    (!value.act || value.view)
  );
}

export function isIntegrationOperationItem(
  value: unknown,
  projectId?: string,
): value is IntegrationOperationItem {
  if (
    !record(value) ||
    !exact(value, [
      "tenantId",
      "projectGlobalId",
      "operationKind",
      "operationGlobalId",
      "sourceGlobalId",
      "operationVersion",
      "rawState",
      "sharedState",
      "sourceSnapshotHash",
      "targetIdempotencyKeyHash",
      "logicalDlq",
      "faultClass",
      "replayEligible",
      "replayEligibilityReason",
      "reconciliationRequired",
      "updatedAt",
    ])
  )
    return false;
  if (
    !boundedText(value.tenantId, 128) ||
    !uuid(value.projectGlobalId) ||
    (projectId !== undefined && value.projectGlobalId !== projectId) ||
    typeof value.operationKind !== "string" ||
    !KIND.has(value.operationKind) ||
    !uuid(value.operationGlobalId) ||
    !uuid(value.sourceGlobalId) ||
    !positive(value.operationVersion) ||
    typeof value.rawState !== "string" ||
    !SAFE_STATE.test(value.rawState) ||
    typeof value.sharedState !== "string" ||
    !STATE.has(value.sharedState) ||
    !sha(value.sourceSnapshotHash) ||
    !sha(value.targetIdempotencyKeyHash) ||
    typeof value.logicalDlq !== "boolean" ||
    typeof value.faultClass !== "string" ||
    !FAULT.has(value.faultClass) ||
    typeof value.replayEligible !== "boolean" ||
    typeof value.replayEligibilityReason !== "string" ||
    !REPLAY_REASON.has(value.replayEligibilityReason) ||
    typeof value.reconciliationRequired !== "boolean" ||
    !instant(value.updatedAt)
  )
    return false;
  const state = value.sharedState as IntegrationOperationState;
  return (
    value.logicalDlq === LOGICAL_DLQ_STATES.has(state) &&
    value.replayEligible === (value.replayEligibilityReason === "eligible") &&
    (!value.replayEligible ||
      (state === "failed_retryable" && !value.reconciliationRequired))
  );
}

export function isIntegrationOperationCollection(
  value: unknown,
  projectId: string,
): value is IntegrationOperationCollection {
  return (
    record(value) &&
    exact(value, ["projectGlobalId", "permissions", "items", "nextCursor"]) &&
    value.projectGlobalId === projectId &&
    permissions(value.permissions) &&
    Array.isArray(value.items) &&
    value.items.length <= 200 &&
    value.items.every((item) => isIntegrationOperationItem(item, projectId)) &&
    (value.nextCursor === null || boundedText(value.nextCursor, 512)) &&
    new Set(
      value.items.map((item) =>
        record(item) ? item.operationGlobalId : undefined,
      ),
    ).size === value.items.length
  );
}

function attempt(value: unknown): value is IntegrationOperationAttempt {
  if (!record(value)) return false;
  const common =
    positive(value.attemptNumber) &&
    boundedText(value.state, 140) &&
    typeof value.adapterBoundaryCrossed === "boolean" &&
    typeof value.reconciliationRequired === "boolean" &&
    optionalBoundedText(value.safeErrorCode, 128);
  if (!common) return false;
  if (
    exact(value, [
      "attemptNumber",
      "state",
      "adapterBoundaryCrossed",
      "reconciliationRequired",
      "safeErrorCode",
    ])
  )
    return true;
  return (
    exact(value, [
      "attemptGlobalId",
      "attemptNumber",
      "state",
      "adapterBoundaryCrossed",
      "reconciliationRequired",
      "safeErrorCode",
      "startedAt",
      "finishedAt",
    ]) &&
    uuid(value.attemptGlobalId) &&
    optionalInstant(value.startedAt) &&
    optionalInstant(value.finishedAt)
  );
}

function result(value: unknown): value is IntegrationOperationResult {
  return (
    record(value) &&
    exact(value, [
      "resultGlobalId",
      "attemptGlobalId",
      "attemptNumber",
      "state",
      "authority",
      "responseAuthenticated",
      "faultKind",
      "observedAt",
    ]) &&
    uuid(value.resultGlobalId) &&
    uuid(value.attemptGlobalId) &&
    positive(value.attemptNumber) &&
    boundedText(value.state, 140) &&
    typeof value.authority === "string" &&
    AUTHORITY.has(value.authority) &&
    typeof value.responseAuthenticated === "boolean" &&
    optionalBoundedText(value.faultKind, 128) &&
    optionalInstant(value.observedAt)
  );
}

function actionHistory(
  value: unknown,
): value is IntegrationOperationActionHistoryItem {
  return (
    record(value) &&
    exact(value, [
      "actionGlobalId",
      "actionKind",
      "outcomeState",
      "outcomeReferenceGlobalId",
      "actorUserId",
      "traceId",
      "createdAt",
    ]) &&
    uuid(value.actionGlobalId) &&
    (value.actionKind === "replay" ||
      value.actionKind === "request_reconciliation") &&
    typeof value.outcomeState === "string" &&
    ACTION_OUTCOME.has(value.outcomeState) &&
    (value.actionKind === "replay"
      ? value.outcomeState === "replay_requested"
      : value.outcomeState === "reconciliation_requested") &&
    (value.outcomeReferenceGlobalId === null ||
      uuid(value.outcomeReferenceGlobalId)) &&
    boundedText(value.actorUserId, 254) &&
    typeof value.traceId === "string" &&
    SAFE_TRACE.test(value.traceId) &&
    instant(value.createdAt)
  );
}

export function isIntegrationOperationDetail(
  value: unknown,
  projectId: string,
  operationKind: IntegrationOperationKind,
  operationId: string,
): value is IntegrationOperationDetail {
  if (
    !record(value) ||
    !exact(value, ["projectGlobalId", "permissions", "operation"]) ||
    value.projectGlobalId !== projectId ||
    !permissions(value.permissions) ||
    !record(value.operation)
  )
    return false;
  const operation = value.operation;
  const itemFields = Object.fromEntries(
    Object.entries(operation).filter(
      ([key]) => !["attempts", "results", "actions"].includes(key),
    ),
  );
  return (
    exact(operation, [
      "tenantId",
      "projectGlobalId",
      "operationKind",
      "operationGlobalId",
      "sourceGlobalId",
      "operationVersion",
      "rawState",
      "sharedState",
      "sourceSnapshotHash",
      "targetIdempotencyKeyHash",
      "logicalDlq",
      "faultClass",
      "replayEligible",
      "replayEligibilityReason",
      "reconciliationRequired",
      "updatedAt",
      "attempts",
      "results",
      "actions",
    ]) &&
    isIntegrationOperationItem(itemFields, projectId) &&
    operation.operationKind === operationKind &&
    operation.operationGlobalId === operationId &&
    Array.isArray(operation.attempts) &&
    operation.attempts.length <= 256 &&
    operation.attempts.every(attempt) &&
    Array.isArray(operation.results) &&
    operation.results.length <= 256 &&
    operation.results.every(result) &&
    new Set(
      operation.results.map((item) =>
        record(item) ? item.resultGlobalId : undefined,
      ),
    ).size === operation.results.length &&
    Array.isArray(operation.actions) &&
    operation.actions.length <= 256 &&
    operation.actions.every(actionHistory) &&
    new Set(
      operation.actions.map((item) =>
        record(item) ? item.actionGlobalId : undefined,
      ),
    ).size === operation.actions.length
  );
}

function actionResult(
  value: unknown,
  operationId: string,
  action: IntegrationOperationActionKind,
): value is IntegrationOperationActionResult {
  return (
    record(value) &&
    exact(value, [
      "actionGlobalId",
      "operationGlobalId",
      "outcomeState",
      "outcomeReferenceGlobalId",
    ]) &&
    uuid(value.actionGlobalId) &&
    value.operationGlobalId === operationId &&
    value.outcomeState ===
      (action === "replay" ? "replay_requested" : "reconciliation_requested") &&
    (value.outcomeReferenceGlobalId === null ||
      uuid(value.outcomeReferenceGlobalId))
  );
}

function commandReady(
  projectId: string,
  operation: IntegrationOperationItem,
  action: IntegrationOperationActionKind,
  context: IntegrationOperationCommandContext,
): boolean {
  return (
    uuid(projectId) &&
    isIntegrationOperationItem(operation, projectId) &&
    ACTION_PATH[operation.operationKind] !== undefined &&
    context.csrfToken.length >= 32 &&
    context.csrfToken.length <= 128 &&
    SAFE_IDEMPOTENCY.test(context.idempotencyKey) &&
    (action === "replay"
      ? operation.replayEligible &&
        operation.sharedState === "failed_retryable" &&
        !operation.reconciliationRequired
      : operation.reconciliationRequired)
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

export class LiveIntegrationOperationsDataSource implements IntegrationOperationsDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadOperations(
    projectId: string,
    filters: IntegrationOperationFilters,
    signal: AbortSignal,
  ): Promise<IntegrationOperationCollection> {
    if (
      !uuid(projectId) ||
      (filters.operationKind !== undefined &&
        !KIND.has(filters.operationKind)) ||
      (filters.sharedState !== undefined && !STATE.has(filters.sharedState)) ||
      (filters.cursor !== undefined && !boundedText(filters.cursor, 512)) ||
      (filters.limit !== undefined &&
        (!Number.isSafeInteger(filters.limit) ||
          filters.limit < 1 ||
          filters.limit > 200))
    )
      throw requestNotReady();
    const query: Record<string, string> = {};
    if (filters.operationKind) query.operationKind = filters.operationKind;
    if (filters.sharedState) query.sharedState = filters.sharedState;
    if (filters.cursor) query.cursor = filters.cursor;
    if (filters.limit !== undefined) query.limit = String(filters.limit);
    const path = `/projects/${projectId}/integration-operations${
      filters.logicalDlq ? "/dlq" : ""
    }`;
    return this.http.request(
      path,
      { signal },
      {
        query,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: (value): value is IntegrationOperationCollection =>
          isIntegrationOperationCollection(value, projectId),
      },
    );
  }

  async loadOperation(
    projectId: string,
    operationKind: IntegrationOperationKind,
    operationId: string,
    signal: AbortSignal,
  ): Promise<IntegrationOperationDetail> {
    if (!uuid(projectId) || !KIND.has(operationKind) || !uuid(operationId))
      throw requestNotReady();
    return this.http.request(
      `/projects/${projectId}/integration-operations/${operationKind}/${operationId}`,
      { signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: (value): value is IntegrationOperationDetail =>
          isIntegrationOperationDetail(
            value,
            projectId,
            operationKind,
            operationId,
          ),
      },
    );
  }

  async requestAction(
    projectId: string,
    operation: IntegrationOperationItem,
    action: IntegrationOperationActionKind,
    context: IntegrationOperationCommandContext,
  ): Promise<IntegrationOperationActionResult> {
    if (!commandReady(projectId, operation, action, context))
      throw requestNotReady();
    const actionPath = ACTION_PATH[operation.operationKind];
    if (!actionPath) throw requestNotReady();
    const suffix = action === "replay" ? "replay" : "request-reconciliation";
    return this.http.request(
      `/projects/${projectId}/integration-operations/${actionPath}/${operation.operationGlobalId}:${suffix}`,
      {
        body: JSON.stringify({
          expectedRawState: operation.rawState,
          expectedVersion: operation.operationVersion,
        }),
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
        validate: (value): value is IntegrationOperationActionResult =>
          actionResult(value, operation.operationGlobalId, action),
      },
    );
  }
}
