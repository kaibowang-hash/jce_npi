import type { EngineeringBomCommandContext } from "./ebom-data-source";
import { NpiHttpClient, NpiTransportError } from "./http";

export const ITEM_PUBLISH_ACKNOWLEDGEMENT =
  "I confirm this request uses the exact released Item source and current execution profile.";

export type ItemPublishTargetMode = "mock" | "synthetic" | "sandbox";
export type ItemPublishIntent =
  | "create_item"
  | "update_item_engineering_fields";
export type ItemPublishRequestState =
  | "validated_mock"
  | "queued"
  | "processing"
  | "synthetic_verified"
  | "succeeded"
  | "failed_retryable"
  | "failed_final"
  | "uncertain_after_timeout"
  | "mapping_conflict";
export type ItemPublishAttemptState =
  | "started"
  | "synthetic_verified"
  | "observed_success"
  | "observed_failure"
  | "uncertain";

export interface ItemPublishProfileViewModel {
  profileId: string;
  profileVersion: number;
  targetMode: ItemPublishTargetMode;
  environmentCode: string;
  snapshotHash: string;
}

export interface ItemPublishOccurrenceViewModel {
  publishNodeGlobalId: string;
  lineGlobalId: string;
  engineeringItemId: string;
  description: string;
  engineeringUom: string;
  attributes: Readonly<Record<string, string>>;
  lineHash: string;
  nodeInputHash: string;
}

export interface ItemPublishSourceViewModel {
  schemaVersion: 1;
  tenantId: string;
  projectGlobalId: string;
  engineeringItemId: string;
  selectedPublishNodeGlobalId: string;
  itemMaster: Readonly<{
    description: string;
    engineeringUom: string;
    attributes: Readonly<Record<string, string>>;
  }>;
  occurrences: readonly ItemPublishOccurrenceViewModel[];
  streamKeyHash: string;
  sourceHash: string;
}

export interface ItemPublishReleasedEvidenceViewModel {
  publishRequestGlobalId: string;
  publishRequestPayloadHash: string;
  publishPolicyGlobalId: string;
  publishPolicyVersion: number;
  publishPolicySnapshotHash: string;
  ebomGlobalId: string;
  ebomVersion: number;
  revisionGlobalId: string;
  revisionNumber: number;
  revisionSnapshotHash: string;
  lifecycleVersion: number;
  releaseEventGlobalId: string;
  releaseEventHash: string;
  approvalEvidenceIds: readonly string[];
  releasedAt: string;
}

export interface ItemPublishMappingExpectationViewModel {
  mappingVersion: number;
  formalItemCode: string | null;
  targetVersion: string | null;
  observationHash: string | null;
}

export interface ItemPublishRequestViewModel {
  schemaVersion: 1;
  globalId: string;
  apiVersion: "npi.erp-item-publish.v1";
  operation: "publish_released_item";
  source: ItemPublishSourceViewModel;
  releasedEvidence: ItemPublishReleasedEvidenceViewModel;
  profile: ItemPublishProfileViewModel;
  mappingExpectation: ItemPublishMappingExpectationViewModel;
  intent: ItemPublishIntent;
  actorUserId: string;
  requestId: string;
  traceId: string;
  idempotencyKeyHash: string;
  payloadHash: string;
  state: ItemPublishRequestState;
  dispatchAllowed: boolean;
  outboxEventId: string | null;
  resultGlobalId: string | null;
  optimisticVersion: number;
  createdAt: string;
  updatedAt: string;
}

export interface ItemPublishAttemptViewModel {
  globalId: string;
  requestGlobalId: string;
  outboxEventId: string;
  attemptNumber: number;
  state: ItemPublishAttemptState;
  adapterBoundaryCrossed: boolean;
  targetIdempotencyKeyHash: string;
  requestSnapshotHash: string;
  startedAt: string;
  finishedAt: string | null;
  targetStatusCode: number | null;
  responseHash: string | null;
  faultKind: string | null;
  reconciliationRequired: boolean;
  safeErrorCode: string | null;
  attemptHash: string;
}

export interface ItemPublishResultViewModel {
  globalId: string;
  requestGlobalId: string;
  outboxEventId: string;
  attemptGlobalId: string;
  attemptNumber: number;
  sourceHash: string;
  state: Exclude<
    ItemPublishRequestState,
    "validated_mock" | "queued" | "processing" | "mapping_conflict"
  >;
  authority: "none" | "synthetic" | "authoritative_sandbox";
  responseAuthenticated: boolean;
  responseHash: string;
  formalItemCode: string | null;
  targetVersion: string | null;
  faultKind: string;
  resultHash: string;
  observedAt: string;
}

export interface ItemPublishCurrentMappingViewModel {
  mappingVersion: number;
  formalItemCode: string;
  targetVersion: string;
  observationHash: string;
}

export interface ItemPublishPermissionsViewModel {
  canView: boolean;
  canExecute: boolean;
}

export interface ItemPublishRequestListViewModel {
  projectGlobalId: string;
  sourceFilters: Readonly<{
    publishRequestGlobalId: string | null;
    selectedPublishNodeGlobalId: string | null;
  }>;
  permissions: ItemPublishPermissionsViewModel;
  executionProfile: ItemPublishProfileViewModel | null;
  mappingExpectation: ItemPublishMappingExpectationViewModel | null;
  items: readonly ItemPublishRequestViewModel[];
}

export interface ItemPublishRequestDetailViewModel {
  requestGlobalId: string;
  request: ItemPublishRequestViewModel;
  currentMapping: ItemPublishCurrentMappingViewModel | null;
  attempts: readonly ItemPublishAttemptViewModel[];
  result: ItemPublishResultViewModel | null;
  permissions: ItemPublishPermissionsViewModel;
}

export interface CreateItemPublishRequestCommand {
  publishRequestGlobalId: string;
  selectedPublishNodeGlobalId: string;
  expectedMappingVersion: number;
  acknowledgement: typeof ITEM_PUBLISH_ACKNOWLEDGEMENT;
}

export interface ItemPublishDataSource {
  loadRequests(
    projectId: string,
    publishRequestId: string,
    selectedPublishNodeId: string,
    signal: AbortSignal,
  ): Promise<ItemPublishRequestListViewModel>;
  loadRequest(
    projectId: string,
    requestId: string,
    signal: AbortSignal,
  ): Promise<ItemPublishRequestDetailViewModel>;
  createRequest(
    projectId: string,
    command: CreateItemPublishRequestCommand,
    context: EngineeringBomCommandContext,
  ): Promise<ItemPublishRequestDetailViewModel>;
}

export class ItemPublishCancelledError extends Error {
  constructor() {
    super("The Item publish request was cancelled.");
    this.name = "ItemPublishCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u;
const identifierPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const targetModes = new Set<ItemPublishTargetMode>([
  "mock",
  "synthetic",
  "sandbox",
]);
const requestStates = new Set<ItemPublishRequestState>([
  "validated_mock",
  "queued",
  "processing",
  "synthetic_verified",
  "succeeded",
  "failed_retryable",
  "failed_final",
  "uncertain_after_timeout",
  "mapping_conflict",
]);
const attemptStates = new Set<ItemPublishAttemptState>([
  "started",
  "synthetic_verified",
  "observed_success",
  "observed_failure",
  "uncertain",
]);
const resultStates = new Set([
  "synthetic_verified",
  "succeeded",
  "failed_retryable",
  "failed_final",
  "uncertain_after_timeout",
]);
const authorities = new Set(["none", "synthetic", "authoritative_sandbox"]);

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

function boundedString(
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

function uuid(value: unknown): value is string {
  return boundedString(value, 36, 36, uuidPattern);
}

function hash(value: unknown): value is string {
  return boundedString(value, 64, 64, hashPattern);
}

function timestamp(value: unknown): value is string {
  return boundedString(value, 20, 32, timestampPattern);
}

function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function nonNegative(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function nullable<T>(
  value: unknown,
  validator: (candidate: unknown) => candidate is T,
): value is T | null {
  return value === null || validator(value);
}

function attributes(value: unknown): value is Readonly<Record<string, string>> {
  return (
    record(value) &&
    Object.keys(value).length <= 50 &&
    Object.values(value).every((item) => boundedString(item, 1, 280))
  );
}

function profile(value: unknown): value is ItemPublishProfileViewModel {
  return (
    record(value) &&
    exact(value, [
      "profileId",
      "profileVersion",
      "targetMode",
      "environmentCode",
      "snapshotHash",
    ]) &&
    boundedString(value.profileId, 1, 128) &&
    positive(value.profileVersion) &&
    targetModes.has(value.targetMode as ItemPublishTargetMode) &&
    boundedString(value.environmentCode, 1, 64) &&
    hash(value.snapshotHash)
  );
}

function occurrence(value: unknown): value is ItemPublishOccurrenceViewModel {
  return (
    record(value) &&
    exact(value, [
      "publishNodeGlobalId",
      "lineGlobalId",
      "engineeringItemId",
      "description",
      "engineeringUom",
      "attributes",
      "lineHash",
      "nodeInputHash",
    ]) &&
    uuid(value.publishNodeGlobalId) &&
    uuid(value.lineGlobalId) &&
    boundedString(value.engineeringItemId, 1, 128) &&
    boundedString(value.description, 1, 280) &&
    boundedString(value.engineeringUom, 1, 16) &&
    attributes(value.attributes) &&
    hash(value.lineHash) &&
    hash(value.nodeInputHash)
  );
}

function source(value: unknown): value is ItemPublishSourceViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "schemaVersion",
      "tenantId",
      "projectGlobalId",
      "engineeringItemId",
      "selectedPublishNodeGlobalId",
      "itemMaster",
      "occurrences",
      "streamKeyHash",
      "sourceHash",
    ]) ||
    value.schemaVersion !== 1 ||
    !boundedString(value.tenantId, 1, 128) ||
    !uuid(value.projectGlobalId) ||
    !boundedString(value.engineeringItemId, 1, 128) ||
    !uuid(value.selectedPublishNodeGlobalId) ||
    !record(value.itemMaster) ||
    !exact(value.itemMaster, ["description", "engineeringUom", "attributes"]) ||
    !boundedString(value.itemMaster.description, 1, 280) ||
    !boundedString(value.itemMaster.engineeringUom, 1, 16) ||
    !attributes(value.itemMaster.attributes) ||
    !Array.isArray(value.occurrences) ||
    value.occurrences.length < 1 ||
    value.occurrences.length > 500 ||
    !value.occurrences.every(occurrence) ||
    !hash(value.streamKeyHash) ||
    !hash(value.sourceHash)
  )
    return false;
  return value.occurrences.every(
    (item) => item.engineeringItemId === value.engineeringItemId,
  );
}

function evidence(
  value: unknown,
): value is ItemPublishReleasedEvidenceViewModel {
  return (
    record(value) &&
    exact(value, [
      "publishRequestGlobalId",
      "publishRequestPayloadHash",
      "publishPolicyGlobalId",
      "publishPolicyVersion",
      "publishPolicySnapshotHash",
      "ebomGlobalId",
      "ebomVersion",
      "revisionGlobalId",
      "revisionNumber",
      "revisionSnapshotHash",
      "lifecycleVersion",
      "releaseEventGlobalId",
      "releaseEventHash",
      "approvalEvidenceIds",
      "releasedAt",
    ]) &&
    uuid(value.publishRequestGlobalId) &&
    hash(value.publishRequestPayloadHash) &&
    uuid(value.publishPolicyGlobalId) &&
    positive(value.publishPolicyVersion) &&
    hash(value.publishPolicySnapshotHash) &&
    uuid(value.ebomGlobalId) &&
    positive(value.ebomVersion) &&
    uuid(value.revisionGlobalId) &&
    positive(value.revisionNumber) &&
    hash(value.revisionSnapshotHash) &&
    positive(value.lifecycleVersion) &&
    uuid(value.releaseEventGlobalId) &&
    hash(value.releaseEventHash) &&
    Array.isArray(value.approvalEvidenceIds) &&
    value.approvalEvidenceIds.length >= 1 &&
    value.approvalEvidenceIds.length <= 32 &&
    value.approvalEvidenceIds.every(uuid) &&
    new Set(value.approvalEvidenceIds).size ===
      value.approvalEvidenceIds.length &&
    timestamp(value.releasedAt)
  );
}

function mappingExpectation(
  value: unknown,
): value is ItemPublishMappingExpectationViewModel {
  return (
    record(value) &&
    exact(value, [
      "mappingVersion",
      "formalItemCode",
      "targetVersion",
      "observationHash",
    ]) &&
    nonNegative(value.mappingVersion) &&
    nullable(value.formalItemCode, (item): item is string =>
      boundedString(item, 1, 140),
    ) &&
    nullable(value.targetVersion, (item): item is string =>
      boundedString(item, 1, 140),
    ) &&
    nullable(value.observationHash, hash) &&
    (value.mappingVersion > 0
      ? value.formalItemCode !== null &&
        value.targetVersion !== null &&
        value.observationHash !== null
      : value.formalItemCode === null &&
        value.targetVersion === null &&
        value.observationHash === null)
  );
}

export function isItemPublishRequest(
  value: unknown,
): value is ItemPublishRequestViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "apiVersion",
      "operation",
      "source",
      "releasedEvidence",
      "profile",
      "mappingExpectation",
      "intent",
      "actorUserId",
      "requestId",
      "traceId",
      "idempotencyKeyHash",
      "payloadHash",
      "state",
      "dispatchAllowed",
      "outboxEventId",
      "resultGlobalId",
      "optimisticVersion",
      "createdAt",
      "updatedAt",
    ]) ||
    value.schemaVersion !== 1 ||
    !uuid(value.globalId) ||
    value.apiVersion !== "npi.erp-item-publish.v1" ||
    value.operation !== "publish_released_item" ||
    !source(value.source) ||
    !evidence(value.releasedEvidence) ||
    !profile(value.profile) ||
    !mappingExpectation(value.mappingExpectation) ||
    (value.intent !== "create_item" &&
      value.intent !== "update_item_engineering_fields") ||
    !boundedString(value.actorUserId, 1, 254) ||
    !uuid(value.requestId) ||
    !boundedString(value.traceId, 8, 128, identifierPattern) ||
    !hash(value.idempotencyKeyHash) ||
    !hash(value.payloadHash) ||
    !requestStates.has(value.state as ItemPublishRequestState) ||
    typeof value.dispatchAllowed !== "boolean" ||
    !nullable(value.outboxEventId, uuid) ||
    !nullable(value.resultGlobalId, uuid) ||
    !positive(value.optimisticVersion) ||
    !timestamp(value.createdAt) ||
    !timestamp(value.updatedAt)
  )
    return false;
  if (value.profile.targetMode === "mock") {
    return (
      value.state === "validated_mock" &&
      !value.dispatchAllowed &&
      value.outboxEventId === null &&
      value.resultGlobalId === null
    );
  }
  return value.dispatchAllowed && value.outboxEventId !== null;
}

function permissions(value: unknown): value is ItemPublishPermissionsViewModel {
  return (
    record(value) &&
    exact(value, ["canView", "canExecute"]) &&
    typeof value.canView === "boolean" &&
    typeof value.canExecute === "boolean"
  );
}

function attempt(value: unknown): value is ItemPublishAttemptViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "requestGlobalId",
      "outboxEventId",
      "attemptNumber",
      "state",
      "adapterBoundaryCrossed",
      "targetIdempotencyKeyHash",
      "requestSnapshotHash",
      "startedAt",
      "finishedAt",
      "targetStatusCode",
      "responseHash",
      "faultKind",
      "reconciliationRequired",
      "safeErrorCode",
      "attemptHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.requestGlobalId) &&
    uuid(value.outboxEventId) &&
    positive(value.attemptNumber) &&
    attemptStates.has(value.state as ItemPublishAttemptState) &&
    typeof value.adapterBoundaryCrossed === "boolean" &&
    hash(value.targetIdempotencyKeyHash) &&
    hash(value.requestSnapshotHash) &&
    timestamp(value.startedAt) &&
    nullable(value.finishedAt, timestamp) &&
    nullable(
      value.targetStatusCode,
      (item): item is number =>
        typeof item === "number" &&
        Number.isInteger(item) &&
        item >= 100 &&
        item <= 599,
    ) &&
    nullable(value.responseHash, hash) &&
    nullable(value.faultKind, (item): item is string =>
      boundedString(item, 1, 100),
    ) &&
    typeof value.reconciliationRequired === "boolean" &&
    nullable(value.safeErrorCode, (item): item is string =>
      boundedString(item, 1, 100),
    ) &&
    hash(value.attemptHash)
  );
}

function result(value: unknown): value is ItemPublishResultViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "globalId",
      "requestGlobalId",
      "outboxEventId",
      "attemptGlobalId",
      "attemptNumber",
      "sourceHash",
      "state",
      "authority",
      "responseAuthenticated",
      "responseHash",
      "formalItemCode",
      "targetVersion",
      "faultKind",
      "resultHash",
      "observedAt",
    ]) ||
    !uuid(value.globalId) ||
    !uuid(value.requestGlobalId) ||
    !uuid(value.outboxEventId) ||
    !uuid(value.attemptGlobalId) ||
    !positive(value.attemptNumber) ||
    !hash(value.sourceHash) ||
    !resultStates.has(value.state as string) ||
    !authorities.has(value.authority as string) ||
    typeof value.responseAuthenticated !== "boolean" ||
    !hash(value.responseHash) ||
    !nullable(value.formalItemCode, (item): item is string =>
      boundedString(item, 1, 140),
    ) ||
    !nullable(value.targetVersion, (item): item is string =>
      boundedString(item, 1, 140),
    ) ||
    !boundedString(value.faultKind, 1, 100) ||
    !hash(value.resultHash) ||
    !timestamp(value.observedAt)
  )
    return false;
  const authoritative =
    value.state === "succeeded" &&
    value.authority === "authoritative_sandbox" &&
    value.responseAuthenticated;
  return authoritative
    ? value.formalItemCode !== null && value.targetVersion !== null
    : value.formalItemCode === null && value.targetVersion === null;
}

function currentMapping(
  value: unknown,
): value is ItemPublishCurrentMappingViewModel {
  return (
    record(value) &&
    exact(value, [
      "mappingVersion",
      "formalItemCode",
      "targetVersion",
      "observationHash",
    ]) &&
    positive(value.mappingVersion) &&
    boundedString(value.formalItemCode, 1, 140) &&
    boundedString(value.targetVersion, 1, 140) &&
    hash(value.observationHash)
  );
}

export function isItemPublishRequestList(
  value: unknown,
): value is ItemPublishRequestListViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "projectGlobalId",
      "sourceFilters",
      "permissions",
      "executionProfile",
      "mappingExpectation",
      "items",
    ]) ||
    !uuid(value.projectGlobalId) ||
    !record(value.sourceFilters) ||
    !exact(value.sourceFilters, [
      "publishRequestGlobalId",
      "selectedPublishNodeGlobalId",
    ]) ||
    !nullable(value.sourceFilters.publishRequestGlobalId, uuid) ||
    !nullable(value.sourceFilters.selectedPublishNodeGlobalId, uuid) ||
    !permissions(value.permissions) ||
    !nullable(value.executionProfile, profile) ||
    !nullable(value.mappingExpectation, mappingExpectation) ||
    !Array.isArray(value.items) ||
    value.items.length > 200 ||
    !value.items.every(isItemPublishRequest)
  )
    return false;
  const candidate = value as unknown as ItemPublishRequestListViewModel;
  const exactSourceSelected =
    candidate.sourceFilters.publishRequestGlobalId !== null &&
    candidate.sourceFilters.selectedPublishNodeGlobalId !== null;
  return (
    (!exactSourceSelected || candidate.mappingExpectation !== null) &&
    candidate.items.every(
      (item) =>
        item.source.projectGlobalId === candidate.projectGlobalId &&
        (candidate.sourceFilters.publishRequestGlobalId === null ||
          item.releasedEvidence.publishRequestGlobalId ===
            candidate.sourceFilters.publishRequestGlobalId) &&
        (candidate.sourceFilters.selectedPublishNodeGlobalId === null ||
          item.source.selectedPublishNodeGlobalId ===
            candidate.sourceFilters.selectedPublishNodeGlobalId),
    )
  );
}

export function isItemPublishRequestDetail(
  value: unknown,
): value is ItemPublishRequestDetailViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "requestGlobalId",
      "request",
      "currentMapping",
      "attempts",
      "result",
      "permissions",
    ]) ||
    !uuid(value.requestGlobalId) ||
    !isItemPublishRequest(value.request) ||
    value.request.globalId !== value.requestGlobalId ||
    !nullable(value.currentMapping, currentMapping) ||
    !Array.isArray(value.attempts) ||
    value.attempts.length > 100 ||
    !value.attempts.every(attempt) ||
    !nullable(value.result, result) ||
    !permissions(value.permissions)
  )
    return false;
  const candidate = value as unknown as ItemPublishRequestDetailViewModel;
  const request = candidate.request;
  const attemptsAreBound = candidate.attempts.every(
    (item, index) =>
      item.requestGlobalId === request.globalId &&
      item.outboxEventId === request.outboxEventId &&
      item.attemptNumber === index + 1,
  );
  const observedResult = candidate.result;
  const resultIsBound =
    observedResult === null
      ? request.resultGlobalId === null
      : observedResult.globalId === request.resultGlobalId &&
        observedResult.requestGlobalId === request.globalId &&
        observedResult.outboxEventId === request.outboxEventId &&
        observedResult.sourceHash === request.source.sourceHash &&
        candidate.attempts.some(
          (item) =>
            item.globalId === observedResult.attemptGlobalId &&
            item.attemptNumber === observedResult.attemptNumber,
        );
  const mappingConflictTruth =
    request.state !== "mapping_conflict" ||
    (observedResult !== null &&
      observedResult.state === "succeeded" &&
      observedResult.authority === "authoritative_sandbox" &&
      observedResult.responseAuthenticated &&
      candidate.currentMapping !== null);
  return attemptsAreBound && resultIsBound && mappingConflictTruth;
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function throwIfCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ItemPublishCancelledError();
}

function validContext(context: EngineeringBomCommandContext): boolean {
  return (
    boundedString(context.csrfToken, 16, 512) &&
    boundedString(context.idempotencyKey, 8, 128, /^[A-Za-z0-9._:-]+$/u) &&
    context.signal instanceof AbortSignal
  );
}

export class LiveItemPublishDataSource implements ItemPublishDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadRequests(
    projectId: string,
    publishRequestId: string,
    selectedPublishNodeId: string,
    signal: AbortSignal,
  ): Promise<ItemPublishRequestListViewModel> {
    if (![projectId, publishRequestId, selectedPublishNodeId].every(uuid))
      throw requestNotReady();
    return this.query(
      `/projects/${projectId}/item-publish-requests`,
      signal,
      (value): value is ItemPublishRequestListViewModel =>
        isItemPublishRequestList(value) &&
        value.projectGlobalId === projectId &&
        value.sourceFilters.publishRequestGlobalId === publishRequestId &&
        value.sourceFilters.selectedPublishNodeGlobalId ===
          selectedPublishNodeId,
      {
        publishRequestGlobalId: publishRequestId,
        selectedPublishNodeGlobalId: selectedPublishNodeId,
      },
    );
  }

  async loadRequest(
    projectId: string,
    requestId: string,
    signal: AbortSignal,
  ): Promise<ItemPublishRequestDetailViewModel> {
    if (![projectId, requestId].every(uuid)) throw requestNotReady();
    return this.query(
      `/projects/${projectId}/item-publish-requests/${requestId}`,
      signal,
      (value): value is ItemPublishRequestDetailViewModel =>
        isItemPublishRequestDetail(value) &&
        value.requestGlobalId === requestId &&
        value.request.source.projectGlobalId === projectId,
    );
  }

  async createRequest(
    projectId: string,
    command: CreateItemPublishRequestCommand,
    context: EngineeringBomCommandContext,
  ): Promise<ItemPublishRequestDetailViewModel> {
    const acknowledgement: unknown = command.acknowledgement;
    const body = {
      publishRequestGlobalId: command.publishRequestGlobalId,
      selectedPublishNodeGlobalId: command.selectedPublishNodeGlobalId,
      expectedMappingVersion: command.expectedMappingVersion,
      acknowledgement,
    };
    if (
      ![
        projectId,
        body.publishRequestGlobalId,
        body.selectedPublishNodeGlobalId,
      ].every(uuid) ||
      !nonNegative(body.expectedMappingVersion) ||
      body.acknowledgement !== ITEM_PUBLISH_ACKNOWLEDGEMENT ||
      !validContext(context)
    )
      throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<ItemPublishRequestDetailViewModel>(
        `/projects/${projectId}/item-publish-requests`,
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
          validate: (value): value is ItemPublishRequestDetailViewModel =>
            isItemPublishRequestDetail(value) &&
            value.request.source.projectGlobalId === projectId &&
            value.request.releasedEvidence.publishRequestGlobalId ===
              body.publishRequestGlobalId &&
            value.request.source.selectedPublishNodeGlobalId ===
              body.selectedPublishNodeGlobalId &&
            value.request.mappingExpectation.mappingVersion ===
              body.expectedMappingVersion,
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
    query?: Readonly<Record<string, string>>,
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
}
