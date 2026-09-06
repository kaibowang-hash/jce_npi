import type { EngineeringBomCommandContext } from "./ebom-data-source";
import { NpiHttpClient, NpiTransportError } from "./http";

export const MBOM_PUBLISH_ACKNOWLEDGEMENT =
  "I confirm this request uses the exact released EBOM topology, current Item readiness, MBOM expectations, and execution profile.";

export type MbomTargetMode = "mock" | "synthetic" | "sandbox";
export type MbomRequestState =
  | "validated_mock"
  | "queued"
  | "processing"
  | "synthetic_verified"
  | "partially_succeeded"
  | "succeeded"
  | "failed_retryable"
  | "failed_final"
  | "uncertain_after_timeout"
  | "mapping_conflict";
export type MbomNodeState =
  | "component_only"
  | "queued"
  | "processing"
  | "synthetic_verified"
  | "succeeded_authoritative"
  | "failed_retryable"
  | "failed_final"
  | "blocked_item_mapping"
  | "blocked_submitted"
  | "uncertain_after_timeout"
  | "observed_conflict";

export interface MbomProfileViewModel {
  profileId: string;
  profileVersion: number;
  targetMode: MbomTargetMode;
  environmentCode: string;
  projectionPolicyId: string;
  projectionPolicyVersion: number;
  projectionPolicyHash: string;
  snapshotHash: string;
}

export interface MbomSourceLineViewModel {
  lineGlobalId: string;
  stableLineKey: string;
  parentLineKey: string | null;
  engineeringItemId: string;
  quantity: string;
  engineeringUom: string;
  alternates: readonly string[];
  effectivity: Readonly<Record<string, string>>;
  attributes: Readonly<Record<string, string>>;
  lineHash: string;
  sourceRole: "assembly" | "component_only";
}

export interface MbomItemReadinessViewModel {
  engineeringItemId: string;
  disposition: "advanced" | "not_ready" | "synthetic_reference";
  itemStreamKeyHash: string;
  mappingVersion: number;
  formalItemCode: string | null;
  targetVersion: string | null;
  observationHash: string | null;
  authority: "none" | "synthetic" | "authoritative_sandbox";
  responseAuthenticated: boolean;
  syntheticItemReference: string | null;
}

export interface MbomExpectationViewModel {
  assemblySourceKey: string;
  stableLineKey: string;
  mappingVersion: number;
  submissionState: "unmapped_create" | "editable_draft" | "submitted_immutable";
  intent: "create_draft" | "update_draft";
  formalBomId: string | null;
  targetVersion: string | null;
  observationHash: string | null;
}

export interface MbomRequestViewModel {
  schemaVersion: 2;
  apiVersion: "npi.erp-mbom-publish.v1";
  operation: "publish_released_mbom";
  globalId: string;
  source: {
    schemaVersion: 2;
    tenantId: string;
    projectGlobalId: string;
    ebomGlobalId: string;
    phase5PublishRequestGlobalId: string;
    phase5PublishRequestPayloadHash: string;
    publishPolicyGlobalId: string;
    publishPolicyVersion: number;
    publishPolicySnapshotHash: string;
    lifecycleVersion: number;
    releaseEventGlobalId: string;
    releaseEventHash: string;
    approvalEvidenceIds: readonly string[];
    releasedAt: string;
    topology: {
      revisionGlobalId: string;
      revisionNumber: number;
      revisionSnapshotHash: string;
      lines: readonly MbomSourceLineViewModel[];
    };
    sourceStreamKeyHash: string;
    topologyHash: string;
    sourceHash: string;
  };
  itemReadiness: readonly MbomItemReadinessViewModel[];
  itemMappingSetHash: string;
  mbomExpectations: readonly MbomExpectationViewModel[];
  mbomMappingSetHash: string;
  profile: MbomProfileViewModel;
  actorUserId: string;
  serviceActorUserId: string | null;
  requestId: string;
  traceId: string;
  idempotencyKeyHash: string;
  targetIdempotencyKeyHash: string;
  semanticEffectHash: string;
  state: MbomRequestState;
  dispatchAllowed: boolean;
  payloadHash: string;
  createdAt: string;
}

export interface MbomRequestSummaryViewModel {
  requestGlobalId: string;
  request: MbomRequestViewModel;
  outboxEventId: string | null;
  updatedAt: string;
}

export interface MbomNodeViewModel {
  globalId: string;
  requestGlobalId: string;
  line: MbomSourceLineViewModel;
  itemReadiness: MbomItemReadinessViewModel;
  mbomExpectation: MbomExpectationViewModel | null;
  state: MbomNodeState;
  nodeSnapshotHash: string;
}

export interface MbomAttemptViewModel {
  globalId: string;
  requestGlobalId: string;
  outboxEventId: string;
  attemptNumber: number;
  state:
    | "started"
    | "synthetic_verified"
    | "observed_success"
    | "observed_partial"
    | "observed_failure"
    | "uncertain";
  adapterBoundaryCrossed: boolean;
  transportDisposition: string | null;
  responseHash: string | null;
  faultKind: string | null;
  reconciliationRequired: boolean;
  safeErrorCode: string | null;
  startedAt: string;
  finishedAt: string | null;
  attemptHash: string;
}

export interface MbomAggregateResultViewModel {
  schemaVersion: 1;
  globalId: string;
  requestGlobalId: string;
  outboxEventId: string;
  attemptGlobalId: string;
  attemptNumber: number;
  sourceHash: string;
  topologyHash: string;
  itemMappingSetHash: string;
  mbomMappingSetHash: string;
  state: Exclude<MbomRequestState, "validated_mock" | "queued" | "processing">;
  authority: "none" | "synthetic" | "authoritative_sandbox";
  responseAuthenticated: boolean;
  responseHash: string;
  faultKind: string;
  nodeResultSetHash: string;
  observedAt: string;
  resultHash: string;
}

export interface MbomNodeResultViewModel {
  schemaVersion: 1;
  globalId: string;
  requestGlobalId: string;
  resultGlobalId: string;
  attemptGlobalId: string;
  nodeGlobalId: string;
  stableLineKey: string;
  assemblySourceKey: string;
  state: Exclude<MbomNodeState, "component_only" | "queued" | "processing">;
  authority: "none" | "synthetic" | "authoritative_sandbox";
  responseAuthenticated: boolean;
  responseHash: string;
  formalBomId: string | null;
  targetVersion: string | null;
  targetSubmissionState: "editable_draft" | "submitted_immutable" | null;
  faultKind: string;
  observedAt: string;
  nodeResultHash: string;
}

export interface MbomCurrentMappingViewModel {
  stableLineKey: string;
  assemblySourceKey: string;
  mappingVersion: number;
  formalBomId: string;
  targetVersion: string;
  targetSubmissionState: "editable_draft" | "submitted_immutable";
  authority: "authoritative_sandbox";
  responseAuthenticated: true;
  observationHash: string;
  updatedAt: string;
}

export interface MbomPermissionsViewModel {
  canView: boolean;
  canExecute: boolean;
}

export interface MbomRequestListViewModel {
  projectGlobalId: string;
  phase5PublishRequestGlobalId: string | null;
  permissions: MbomPermissionsViewModel;
  executionProfile: MbomProfileViewModel | null;
  createContext: MbomCreateContextViewModel | null;
  items: readonly MbomRequestSummaryViewModel[];
}

export interface MbomCreateContextViewModel {
  phase5PublishRequestGlobalId: string;
  source: MbomRequestViewModel["source"];
  itemReadiness: readonly MbomItemReadinessViewModel[];
  itemMappingSetHash: string;
  mbomExpectations: readonly MbomExpectationViewModel[];
  mbomMappingSetHash: string;
  profile: MbomProfileViewModel;
}

export interface MbomRequestDetailViewModel extends MbomRequestSummaryViewModel {
  nodes: readonly MbomNodeViewModel[];
  attempts: readonly MbomAttemptViewModel[];
  result: MbomAggregateResultViewModel | null;
  nodeResults: readonly MbomNodeResultViewModel[];
  currentMappings: readonly MbomCurrentMappingViewModel[];
  permissions: MbomPermissionsViewModel;
}

export interface CreateMbomRequestCommand {
  phase5PublishRequestGlobalId: string;
  expectedSourceHash: string;
  expectedTopologyHash: string;
  expectedItemMappingSetHash: string;
  expectedMbomMappingSetHash: string;
  acknowledgement: typeof MBOM_PUBLISH_ACKNOWLEDGEMENT;
}

export interface MbomPublishDataSource {
  loadRequests(
    projectId: string,
    phase5PublishRequestId: string,
    signal: AbortSignal,
  ): Promise<MbomRequestListViewModel>;
  loadRequest(
    projectId: string,
    requestId: string,
    signal: AbortSignal,
  ): Promise<MbomRequestDetailViewModel>;
  createRequest(
    projectId: string,
    command: CreateMbomRequestCommand,
    context: EngineeringBomCommandContext,
  ): Promise<MbomRequestSummaryViewModel>;
}

export class MbomPublishCancelledError extends Error {}

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA = /^[a-f0-9]{64}$/u;
const TRACE = /^[A-Za-z0-9._:-]{8,128}$/u;
const STATES = new Set<MbomRequestState>([
  "validated_mock",
  "queued",
  "processing",
  "synthetic_verified",
  "partially_succeeded",
  "succeeded",
  "failed_retryable",
  "failed_final",
  "uncertain_after_timeout",
  "mapping_conflict",
]);
const NODE_STATES = new Set<MbomNodeState>([
  "component_only",
  "queued",
  "processing",
  "synthetic_verified",
  "succeeded_authoritative",
  "failed_retryable",
  "failed_final",
  "blocked_item_mapping",
  "blocked_submitted",
  "uncertain_after_timeout",
  "observed_conflict",
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
    keys.every((key) => key in value)
  );
}

function text(value: unknown, maximum = 280): value is string {
  return (
    typeof value === "string" && value.length > 0 && value.length <= maximum
  );
}

function nullableText(value: unknown, maximum = 280): value is string | null {
  return value === null || text(value, maximum);
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}
function sha(value: unknown): value is string {
  return typeof value === "string" && SHA.test(value);
}
function dateTime(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}
function integer(value: unknown, minimum = 0): value is number {
  return Number.isInteger(value) && Number(value) >= minimum;
}

function stringRecord(
  value: unknown,
): value is Readonly<Record<string, string>> {
  return (
    record(value) &&
    Object.keys(value).length <= 50 &&
    Object.values(value).every((item) => text(item))
  );
}

function isProfile(value: unknown): value is MbomProfileViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "profileId",
      "profileVersion",
      "targetMode",
      "environmentCode",
      "projectionPolicyId",
      "projectionPolicyVersion",
      "projectionPolicyHash",
      "snapshotHash",
    ])
  )
    return false;
  return (
    text(value.profileId, 128) &&
    integer(value.profileVersion, 1) &&
    ["mock", "synthetic", "sandbox"].includes(String(value.targetMode)) &&
    text(value.environmentCode, 64) &&
    text(value.projectionPolicyId, 128) &&
    integer(value.projectionPolicyVersion, 1) &&
    sha(value.projectionPolicyHash) &&
    sha(value.snapshotHash)
  );
}

function isLine(value: unknown): value is MbomSourceLineViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "lineGlobalId",
      "stableLineKey",
      "parentLineKey",
      "engineeringItemId",
      "quantity",
      "engineeringUom",
      "alternates",
      "effectivity",
      "attributes",
      "lineHash",
      "sourceRole",
    ])
  )
    return false;
  return (
    uuid(value.lineGlobalId) &&
    text(value.stableLineKey, 128) &&
    (value.parentLineKey === null || text(value.parentLineKey, 128)) &&
    text(value.engineeringItemId, 128) &&
    typeof value.quantity === "string" &&
    /^\d+(?:\.\d+)?$/u.test(value.quantity) &&
    text(value.engineeringUom, 16) &&
    Array.isArray(value.alternates) &&
    value.alternates.length <= 32 &&
    value.alternates.every((item) => text(item, 128)) &&
    stringRecord(value.effectivity) &&
    stringRecord(value.attributes) &&
    sha(value.lineHash) &&
    ["assembly", "component_only"].includes(String(value.sourceRole))
  );
}

function isReadiness(value: unknown): value is MbomItemReadinessViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "engineeringItemId",
      "disposition",
      "itemStreamKeyHash",
      "mappingVersion",
      "formalItemCode",
      "targetVersion",
      "observationHash",
      "authority",
      "responseAuthenticated",
      "syntheticItemReference",
    ])
  )
    return false;
  if (
    !text(value.engineeringItemId, 128) ||
    !["advanced", "not_ready", "synthetic_reference"].includes(
      String(value.disposition),
    ) ||
    !sha(value.itemStreamKeyHash) ||
    !integer(value.mappingVersion) ||
    !nullableText(value.formalItemCode, 140) ||
    !nullableText(value.targetVersion, 140) ||
    !(value.observationHash === null || sha(value.observationHash)) ||
    !["none", "synthetic", "authoritative_sandbox"].includes(
      String(value.authority),
    ) ||
    typeof value.responseAuthenticated !== "boolean" ||
    !nullableText(value.syntheticItemReference, 64)
  )
    return false;
  if (value.disposition === "advanced")
    return (
      value.mappingVersion > 0 &&
      value.authority === "authoritative_sandbox" &&
      value.responseAuthenticated &&
      value.formalItemCode !== null &&
      value.targetVersion !== null &&
      value.observationHash !== null &&
      value.syntheticItemReference === null
    );
  if (value.disposition === "synthetic_reference")
    return (
      value.mappingVersion === 0 &&
      value.authority === "synthetic" &&
      !value.responseAuthenticated &&
      value.formalItemCode === null &&
      value.targetVersion === null &&
      value.observationHash === null &&
      typeof value.syntheticItemReference === "string" &&
      /^synthetic-item-[a-f0-9]{24}$/u.test(value.syntheticItemReference)
    );
  return (
    value.mappingVersion === 0 &&
    value.authority === "none" &&
    !value.responseAuthenticated &&
    value.formalItemCode === null &&
    value.targetVersion === null &&
    value.observationHash === null &&
    value.syntheticItemReference === null
  );
}

function isExpectation(value: unknown): value is MbomExpectationViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "assemblySourceKey",
      "stableLineKey",
      "mappingVersion",
      "submissionState",
      "intent",
      "formalBomId",
      "targetVersion",
      "observationHash",
    ])
  )
    return false;
  if (
    !sha(value.assemblySourceKey) ||
    !text(value.stableLineKey, 128) ||
    !integer(value.mappingVersion) ||
    !["unmapped_create", "editable_draft", "submitted_immutable"].includes(
      String(value.submissionState),
    ) ||
    !["create_draft", "update_draft"].includes(String(value.intent)) ||
    !nullableText(value.formalBomId, 140) ||
    !nullableText(value.targetVersion, 140) ||
    !(value.observationHash === null || sha(value.observationHash))
  )
    return false;
  return value.mappingVersion === 0
    ? value.submissionState === "unmapped_create" &&
        value.intent === "create_draft" &&
        value.formalBomId === null &&
        value.targetVersion === null &&
        value.observationHash === null
    : value.submissionState !== "unmapped_create" &&
        value.intent === "update_draft" &&
        value.formalBomId !== null &&
        value.targetVersion !== null &&
        value.observationHash !== null;
}

function isRequest(value: unknown): value is MbomRequestViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "schemaVersion",
      "apiVersion",
      "operation",
      "globalId",
      "source",
      "itemReadiness",
      "itemMappingSetHash",
      "mbomExpectations",
      "mbomMappingSetHash",
      "profile",
      "actorUserId",
      "serviceActorUserId",
      "requestId",
      "traceId",
      "idempotencyKeyHash",
      "targetIdempotencyKeyHash",
      "semanticEffectHash",
      "state",
      "dispatchAllowed",
      "payloadHash",
      "createdAt",
    ])
  )
    return false;
  if (
    value.schemaVersion !== 2 ||
    value.apiVersion !== "npi.erp-mbom-publish.v1" ||
    value.operation !== "publish_released_mbom" ||
    !uuid(value.globalId) ||
    !record(value.source) ||
    !isProfile(value.profile) ||
    !Array.isArray(value.itemReadiness) ||
    value.itemReadiness.length < 1 ||
    value.itemReadiness.length > 500 ||
    !value.itemReadiness.every(isReadiness) ||
    !Array.isArray(value.mbomExpectations) ||
    value.mbomExpectations.length < 1 ||
    value.mbomExpectations.length > 499 ||
    !value.mbomExpectations.every(isExpectation) ||
    !sha(value.itemMappingSetHash) ||
    !sha(value.mbomMappingSetHash) ||
    !text(value.actorUserId, 254) ||
    !(
      value.serviceActorUserId === null || text(value.serviceActorUserId, 254)
    ) ||
    !uuid(value.requestId) ||
    typeof value.traceId !== "string" ||
    !TRACE.test(value.traceId) ||
    !sha(value.idempotencyKeyHash) ||
    !sha(value.targetIdempotencyKeyHash) ||
    !sha(value.semanticEffectHash) ||
    !STATES.has(value.state as MbomRequestState) ||
    typeof value.dispatchAllowed !== "boolean" ||
    !sha(value.payloadHash) ||
    !dateTime(value.createdAt)
  )
    return false;
  const source = value.source;
  if (
    !exact(source, [
      "schemaVersion",
      "tenantId",
      "projectGlobalId",
      "ebomGlobalId",
      "phase5PublishRequestGlobalId",
      "phase5PublishRequestPayloadHash",
      "publishPolicyGlobalId",
      "publishPolicyVersion",
      "publishPolicySnapshotHash",
      "lifecycleVersion",
      "releaseEventGlobalId",
      "releaseEventHash",
      "approvalEvidenceIds",
      "releasedAt",
      "topology",
      "sourceStreamKeyHash",
      "topologyHash",
      "sourceHash",
    ]) ||
    source.schemaVersion !== 2 ||
    !text(source.tenantId, 128) ||
    !uuid(source.projectGlobalId) ||
    !uuid(source.ebomGlobalId) ||
    !uuid(source.phase5PublishRequestGlobalId) ||
    !sha(source.phase5PublishRequestPayloadHash) ||
    !uuid(source.publishPolicyGlobalId) ||
    !integer(source.publishPolicyVersion, 1) ||
    !sha(source.publishPolicySnapshotHash) ||
    !integer(source.lifecycleVersion, 1) ||
    !uuid(source.releaseEventGlobalId) ||
    !sha(source.releaseEventHash) ||
    !Array.isArray(source.approvalEvidenceIds) ||
    source.approvalEvidenceIds.length < 1 ||
    source.approvalEvidenceIds.length > 32 ||
    !source.approvalEvidenceIds.every(uuid) ||
    !dateTime(source.releasedAt) ||
    !record(source.topology) ||
    !sha(source.sourceStreamKeyHash) ||
    !sha(source.topologyHash) ||
    !sha(source.sourceHash)
  )
    return false;
  const topology = source.topology;
  if (
    !exact(topology, [
      "revisionGlobalId",
      "revisionNumber",
      "revisionSnapshotHash",
      "lines",
    ]) ||
    !uuid(topology.revisionGlobalId) ||
    !integer(topology.revisionNumber, 1) ||
    !sha(topology.revisionSnapshotHash) ||
    !Array.isArray(topology.lines) ||
    topology.lines.length < 1 ||
    topology.lines.length > 500 ||
    !topology.lines.every(isLine)
  )
    return false;
  const assemblyKeys = topology.lines
    .filter((line) => line.sourceRole === "assembly")
    .map((line) => line.stableLineKey)
    .sort();
  const profile = value.profile;
  return (
    value.mbomExpectations
      .map((item) => item.stableLineKey)
      .sort()
      .join("\0") === assemblyKeys.join("\0") &&
    value.itemReadiness.every((item) =>
      profile.targetMode === "sandbox"
        ? item.disposition === "advanced"
        : profile.targetMode === "synthetic"
          ? item.disposition === "synthetic_reference"
          : item.disposition === "not_ready",
    )
  );
}

function isSummary(value: unknown): value is MbomRequestSummaryViewModel {
  return (
    record(value) &&
    exact(value, [
      "requestGlobalId",
      "request",
      "outboxEventId",
      "updatedAt",
    ]) &&
    uuid(value.requestGlobalId) &&
    isRequest(value.request) &&
    value.requestGlobalId === value.request.globalId &&
    (value.outboxEventId === null || uuid(value.outboxEventId)) &&
    dateTime(value.updatedAt) &&
    ((value.request.profile.targetMode === "mock" &&
      value.outboxEventId === null) ||
      (value.request.profile.targetMode !== "mock" &&
        value.outboxEventId !== null))
  );
}

function isPermissions(value: unknown): value is MbomPermissionsViewModel {
  return (
    record(value) &&
    exact(value, ["canView", "canExecute"]) &&
    typeof value.canView === "boolean" &&
    typeof value.canExecute === "boolean"
  );
}

function isNode(value: unknown): value is MbomNodeViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "requestGlobalId",
      "line",
      "itemReadiness",
      "mbomExpectation",
      "state",
      "nodeSnapshotHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.requestGlobalId) &&
    isLine(value.line) &&
    isReadiness(value.itemReadiness) &&
    (value.mbomExpectation === null || isExpectation(value.mbomExpectation)) &&
    NODE_STATES.has(value.state as MbomNodeState) &&
    sha(value.nodeSnapshotHash) &&
    value.line.engineeringItemId === value.itemReadiness.engineeringItemId &&
    (value.line.sourceRole === "assembly") === (value.mbomExpectation !== null)
  );
}

function isAttempt(value: unknown): value is MbomAttemptViewModel {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "requestGlobalId",
      "outboxEventId",
      "attemptNumber",
      "state",
      "adapterBoundaryCrossed",
      "transportDisposition",
      "responseHash",
      "faultKind",
      "reconciliationRequired",
      "safeErrorCode",
      "startedAt",
      "finishedAt",
      "attemptHash",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.requestGlobalId) &&
    uuid(value.outboxEventId) &&
    integer(value.attemptNumber, 1) &&
    [
      "started",
      "synthetic_verified",
      "observed_success",
      "observed_partial",
      "observed_failure",
      "uncertain",
    ].includes(String(value.state)) &&
    typeof value.adapterBoundaryCrossed === "boolean" &&
    nullableText(value.transportDisposition, 100) &&
    (value.responseHash === null || sha(value.responseHash)) &&
    nullableText(value.faultKind, 100) &&
    typeof value.reconciliationRequired === "boolean" &&
    nullableText(value.safeErrorCode, 100) &&
    dateTime(value.startedAt) &&
    (value.finishedAt === null || dateTime(value.finishedAt)) &&
    sha(value.attemptHash)
  );
}

function isResult(value: unknown): value is MbomAggregateResultViewModel {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "globalId",
      "requestGlobalId",
      "outboxEventId",
      "attemptGlobalId",
      "attemptNumber",
      "sourceHash",
      "topologyHash",
      "itemMappingSetHash",
      "mbomMappingSetHash",
      "state",
      "authority",
      "responseAuthenticated",
      "responseHash",
      "faultKind",
      "nodeResultSetHash",
      "observedAt",
      "resultHash",
    ]) &&
    value.schemaVersion === 1 &&
    uuid(value.globalId) &&
    uuid(value.requestGlobalId) &&
    uuid(value.outboxEventId) &&
    uuid(value.attemptGlobalId) &&
    integer(value.attemptNumber, 1) &&
    sha(value.sourceHash) &&
    sha(value.topologyHash) &&
    sha(value.itemMappingSetHash) &&
    sha(value.mbomMappingSetHash) &&
    STATES.has(value.state as MbomRequestState) &&
    !["validated_mock", "queued", "processing"].includes(String(value.state)) &&
    ["none", "synthetic", "authoritative_sandbox"].includes(
      String(value.authority),
    ) &&
    typeof value.responseAuthenticated === "boolean" &&
    sha(value.responseHash) &&
    text(value.faultKind, 100) &&
    sha(value.nodeResultSetHash) &&
    dateTime(value.observedAt) &&
    sha(value.resultHash)
  );
}

function isNodeResult(value: unknown): value is MbomNodeResultViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "requestGlobalId",
      "resultGlobalId",
      "attemptGlobalId",
      "nodeGlobalId",
      "stableLineKey",
      "assemblySourceKey",
      "state",
      "authority",
      "responseAuthenticated",
      "responseHash",
      "formalBomId",
      "targetVersion",
      "targetSubmissionState",
      "faultKind",
      "observedAt",
      "nodeResultHash",
    ])
  )
    return false;
  if (
    value.schemaVersion !== 1 ||
    ![
      value.globalId,
      value.requestGlobalId,
      value.resultGlobalId,
      value.attemptGlobalId,
      value.nodeGlobalId,
    ].every(uuid) ||
    !text(value.stableLineKey, 128) ||
    !sha(value.assemblySourceKey) ||
    !NODE_STATES.has(value.state as MbomNodeState) ||
    ["component_only", "queued", "processing"].includes(String(value.state)) ||
    !["none", "synthetic", "authoritative_sandbox"].includes(
      String(value.authority),
    ) ||
    typeof value.responseAuthenticated !== "boolean" ||
    !sha(value.responseHash) ||
    !nullableText(value.formalBomId, 140) ||
    !nullableText(value.targetVersion, 140) ||
    !(
      value.targetSubmissionState === null ||
      (typeof value.targetSubmissionState === "string" &&
        ["editable_draft", "submitted_immutable"].includes(
          value.targetSubmissionState,
        ))
    ) ||
    !text(value.faultKind, 100) ||
    !dateTime(value.observedAt) ||
    !sha(value.nodeResultHash)
  )
    return false;
  const authoritative =
    value.state === "succeeded_authoritative" &&
    value.authority === "authoritative_sandbox" &&
    value.responseAuthenticated;
  const formalIdentity =
    value.formalBomId !== null &&
    value.targetVersion !== null &&
    value.targetSubmissionState === "editable_draft";
  const redactedIdentity =
    value.formalBomId === null &&
    value.targetVersion === null &&
    value.targetSubmissionState === null;
  return authoritative ? formalIdentity || redactedIdentity : redactedIdentity;
}

function isMapping(value: unknown): value is MbomCurrentMappingViewModel {
  return (
    record(value) &&
    exact(value, [
      "stableLineKey",
      "assemblySourceKey",
      "mappingVersion",
      "formalBomId",
      "targetVersion",
      "targetSubmissionState",
      "authority",
      "responseAuthenticated",
      "observationHash",
      "updatedAt",
    ]) &&
    text(value.stableLineKey, 128) &&
    sha(value.assemblySourceKey) &&
    integer(value.mappingVersion, 1) &&
    text(value.formalBomId, 140) &&
    text(value.targetVersion, 140) &&
    ["editable_draft", "submitted_immutable"].includes(
      String(value.targetSubmissionState),
    ) &&
    value.authority === "authoritative_sandbox" &&
    value.responseAuthenticated === true &&
    sha(value.observationHash) &&
    dateTime(value.updatedAt)
  );
}

function aggregateNodeState(
  values: readonly MbomNodeResultViewModel[],
): MbomRequestState | null {
  if (
    values.length === 0 ||
    new Set(values.map((item) => item.stableLineKey)).size !== values.length
  )
    return null;
  const [first] = values;
  if (!first) return null;
  const states = new Set(values.map((item) => item.state));
  if (states.size === 1) {
    const aggregateByNodeState: Readonly<
      Record<MbomNodeResultViewModel["state"], MbomRequestState>
    > = {
      blocked_item_mapping: "failed_final",
      blocked_submitted: "mapping_conflict",
      failed_final: "failed_final",
      failed_retryable: "failed_retryable",
      observed_conflict: "mapping_conflict",
      succeeded_authoritative: "succeeded",
      synthetic_verified: "synthetic_verified",
      uncertain_after_timeout: "uncertain_after_timeout",
    };
    return aggregateByNodeState[first.state];
  }
  return states.has("uncertain_after_timeout")
    ? "uncertain_after_timeout"
    : "partially_succeeded";
}

export function isMbomRequestList(
  value: unknown,
): value is MbomRequestListViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "projectGlobalId",
      "phase5PublishRequestGlobalId",
      "permissions",
      "executionProfile",
      "createContext",
      "items",
    ]) ||
    !uuid(value.projectGlobalId) ||
    !(
      value.phase5PublishRequestGlobalId === null ||
      uuid(value.phase5PublishRequestGlobalId)
    ) ||
    !isPermissions(value.permissions) ||
    !(value.executionProfile === null || isProfile(value.executionProfile)) ||
    !Array.isArray(value.items) ||
    value.items.length > 200 ||
    !value.items.every(isSummary) ||
    !value.items.every(
      (item) =>
        item.request.source.projectGlobalId === value.projectGlobalId &&
        (value.phase5PublishRequestGlobalId === null ||
          item.request.source.phase5PublishRequestGlobalId ===
            value.phase5PublishRequestGlobalId),
    )
  )
    return false;
  if (value.createContext === null) return true;
  const context = value.createContext;
  if (
    !record(context) ||
    !exact(context, [
      "phase5PublishRequestGlobalId",
      "source",
      "itemReadiness",
      "itemMappingSetHash",
      "mbomExpectations",
      "mbomMappingSetHash",
      "profile",
    ]) ||
    !uuid(context.phase5PublishRequestGlobalId) ||
    !record(context.source) ||
    !Array.isArray(context.itemReadiness) ||
    !context.itemReadiness.every(isReadiness) ||
    !sha(context.itemMappingSetHash) ||
    !Array.isArray(context.mbomExpectations) ||
    !context.mbomExpectations.every(isExpectation) ||
    !sha(context.mbomMappingSetHash) ||
    !isProfile(context.profile)
  )
    return false;
  const candidate = {
    schemaVersion: 2,
    apiVersion: "npi.erp-mbom-publish.v1",
    operation: "publish_released_mbom",
    globalId: "00000000-0000-4000-8000-000000000001",
    source: context.source,
    itemReadiness: context.itemReadiness,
    itemMappingSetHash: context.itemMappingSetHash,
    mbomExpectations: context.mbomExpectations,
    mbomMappingSetHash: context.mbomMappingSetHash,
    profile: context.profile,
    actorUserId: "candidate@example.invalid",
    serviceActorUserId:
      context.profile.targetMode === "mock"
        ? null
        : "candidate@example.invalid",
    requestId: "00000000-0000-4000-8000-000000000002",
    traceId: "trace-candidate",
    idempotencyKeyHash: "0".repeat(64),
    targetIdempotencyKeyHash: "1".repeat(64),
    semanticEffectHash: "2".repeat(64),
    state: context.profile.targetMode === "mock" ? "validated_mock" : "queued",
    dispatchAllowed: context.profile.targetMode !== "mock",
    payloadHash: "3".repeat(64),
    createdAt: "2026-01-01T00:00:00Z",
  };
  return (
    isRequest(candidate) &&
    context.phase5PublishRequestGlobalId ===
      value.phase5PublishRequestGlobalId &&
    context.source.projectGlobalId === value.projectGlobalId &&
    context.source.phase5PublishRequestGlobalId ===
      context.phase5PublishRequestGlobalId &&
    (value.executionProfile === null ||
      (context.profile.profileId === value.executionProfile.profileId &&
        context.profile.profileVersion ===
          value.executionProfile.profileVersion &&
        context.profile.snapshotHash === value.executionProfile.snapshotHash))
  );
}

export function isMbomRequestDetail(
  value: unknown,
): value is MbomRequestDetailViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "requestGlobalId",
      "request",
      "outboxEventId",
      "updatedAt",
      "nodes",
      "attempts",
      "result",
      "nodeResults",
      "currentMappings",
      "permissions",
    ]) ||
    !isSummary({
      requestGlobalId: value.requestGlobalId,
      request: value.request,
      outboxEventId: value.outboxEventId,
      updatedAt: value.updatedAt,
    }) ||
    !isPermissions(value.permissions) ||
    !Array.isArray(value.nodes) ||
    value.nodes.length < 1 ||
    value.nodes.length > 500 ||
    !value.nodes.every(isNode) ||
    !Array.isArray(value.attempts) ||
    value.attempts.length > 100 ||
    !value.attempts.every(isAttempt) ||
    !(value.result === null || isResult(value.result)) ||
    !Array.isArray(value.nodeResults) ||
    !value.nodeResults.every(isNodeResult) ||
    !Array.isArray(value.currentMappings) ||
    !value.currentMappings.every(isMapping)
  )
    return false;
  if (!isRequest(value.request)) return false;
  const request = value.request;
  const nodes = value.nodes;
  const attempts = value.attempts;
  const result = value.result;
  const nodeResults = value.nodeResults;
  const mappings = value.currentMappings;
  const topologyLines = request.source.topology.lines;
  const nodeKeys = new Set(nodes.map((node) => node.line.stableLineKey));
  const mappingKeys = new Set(mappings.map((mapping) => mapping.stableLineKey));
  const matchingAttempt =
    result === null
      ? null
      : attempts.find(
          (attempt) =>
            attempt.globalId === result.attemptGlobalId &&
            attempt.attemptNumber === result.attemptNumber,
        );
  const aggregateState = aggregateNodeState(nodeResults);
  const aggregateAuthority = nodeResults.every(
    (item) => item.authority === "synthetic",
  )
    ? "synthetic"
    : nodeResults.every((item) => item.authority === "authoritative_sandbox")
      ? "authoritative_sandbox"
      : "none";
  if (
    nodes.length !== topologyLines.length ||
    nodeKeys.size !== nodes.length ||
    mappingKeys.size !== mappings.length ||
    !nodes.every((node) => {
      const expectation = node.mbomExpectation;
      return (
        node.requestGlobalId === request.globalId &&
        topologyLines.some(
          (line) =>
            line.lineGlobalId === node.line.lineGlobalId &&
            line.stableLineKey === node.line.stableLineKey &&
            line.lineHash === node.line.lineHash,
        ) &&
        request.itemReadiness.some(
          (item) =>
            item.engineeringItemId === node.itemReadiness.engineeringItemId &&
            item.itemStreamKeyHash === node.itemReadiness.itemStreamKeyHash,
        ) &&
        (expectation === null ||
          request.mbomExpectations.some(
            (item) =>
              item.stableLineKey === expectation.stableLineKey &&
              item.assemblySourceKey === expectation.assemblySourceKey,
          ))
      );
    }) ||
    !attempts.every(
      (attempt) =>
        attempt.requestGlobalId === request.globalId &&
        attempt.outboxEventId === value.outboxEventId,
    ) ||
    (result !== null &&
      (matchingAttempt === null ||
        result.requestGlobalId !== request.globalId ||
        result.outboxEventId !== value.outboxEventId ||
        result.state !== request.state ||
        result.state !== aggregateState ||
        result.authority !== aggregateAuthority ||
        result.responseAuthenticated !==
          nodeResults.every((item) => item.responseAuthenticated) ||
        result.sourceHash !== request.source.sourceHash ||
        result.topologyHash !== request.source.topologyHash ||
        result.itemMappingSetHash !== request.itemMappingSetHash ||
        result.mbomMappingSetHash !== request.mbomMappingSetHash)) ||
    nodeResults.some(
      (item) =>
        result === null ||
        item.requestGlobalId !== request.globalId ||
        item.resultGlobalId !== result.globalId ||
        item.attemptGlobalId !== result.attemptGlobalId ||
        !nodes.some(
          (node) =>
            node.globalId === item.nodeGlobalId &&
            node.line.stableLineKey === item.stableLineKey &&
            node.mbomExpectation?.assemblySourceKey === item.assemblySourceKey,
        ),
    ) ||
    mappings.some(
      (mapping) =>
        !nodeResults.some(
          (item) =>
            item.stableLineKey === mapping.stableLineKey &&
            item.assemblySourceKey === mapping.assemblySourceKey &&
            item.authority === "authoritative_sandbox" &&
            item.responseAuthenticated &&
            item.formalBomId === mapping.formalBomId &&
            item.targetVersion === mapping.targetVersion,
        ),
    ) ||
    (value.permissions.canView
      ? nodeResults.some(
          (item) =>
            item.authority === "authoritative_sandbox" &&
            item.responseAuthenticated &&
            !mappings.some(
              (mapping) =>
                mapping.stableLineKey === item.stableLineKey &&
                mapping.assemblySourceKey === item.assemblySourceKey &&
                mapping.formalBomId === item.formalBomId &&
                mapping.targetVersion === item.targetVersion,
            ),
        )
      : mappings.length > 0 ||
        nodeResults.some(
          (item) =>
            item.formalBomId !== null ||
            item.targetVersion !== null ||
            item.targetSubmissionState !== null,
        ))
  )
    return false;
  const terminal = ![
    "validated_mock",
    "queued",
    "processing",
    "failed_retryable",
  ].includes(request.state);
  return terminal
    ? result !== null && nodeResults.length === request.mbomExpectations.length
    : result === null
      ? nodeResults.length === 0 && mappings.length === 0
      : true;
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}
function throwIfCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new MbomPublishCancelledError();
}
function validContext(context: EngineeringBomCommandContext): boolean {
  return (
    text(context.csrfToken, 512) &&
    text(context.idempotencyKey, 128) &&
    /^[A-Za-z0-9._:-]+$/u.test(context.idempotencyKey) &&
    context.signal instanceof AbortSignal
  );
}
function validAcknowledgement(
  value: unknown,
): value is typeof MBOM_PUBLISH_ACKNOWLEDGEMENT {
  return value === MBOM_PUBLISH_ACKNOWLEDGEMENT;
}

export class LiveMbomPublishDataSource implements MbomPublishDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadRequests(
    projectId: string,
    phase5PublishRequestId: string,
    signal: AbortSignal,
  ): Promise<MbomRequestListViewModel> {
    if (!uuid(projectId) || !uuid(phase5PublishRequestId))
      throw requestNotReady();
    return this.query(
      `/projects/${projectId}/mbom-publish-requests`,
      signal,
      (value): value is MbomRequestListViewModel =>
        isMbomRequestList(value) &&
        value.projectGlobalId === projectId &&
        value.phase5PublishRequestGlobalId === phase5PublishRequestId,
      { phase5PublishRequestGlobalId: phase5PublishRequestId },
    );
  }

  async loadRequest(
    projectId: string,
    requestId: string,
    signal: AbortSignal,
  ): Promise<MbomRequestDetailViewModel> {
    if (!uuid(projectId) || !uuid(requestId)) throw requestNotReady();
    return this.query(
      `/projects/${projectId}/mbom-publish-requests/${requestId}`,
      signal,
      (value): value is MbomRequestDetailViewModel =>
        isMbomRequestDetail(value) &&
        value.requestGlobalId === requestId &&
        value.request.source.projectGlobalId === projectId,
    );
  }

  async createRequest(
    projectId: string,
    command: CreateMbomRequestCommand,
    context: EngineeringBomCommandContext,
  ): Promise<MbomRequestSummaryViewModel> {
    if (
      !uuid(projectId) ||
      !uuid(command.phase5PublishRequestGlobalId) ||
      ![
        command.expectedSourceHash,
        command.expectedTopologyHash,
        command.expectedItemMappingSetHash,
        command.expectedMbomMappingSetHash,
      ].every(sha) ||
      !validAcknowledgement(command.acknowledgement) ||
      !validContext(context)
    )
      throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<MbomRequestSummaryViewModel>(
        `/projects/${projectId}/mbom-publish-requests`,
        {
          body: JSON.stringify(command),
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
          validate: (value): value is MbomRequestSummaryViewModel =>
            isSummary(value) &&
            value.request.source.projectGlobalId === projectId &&
            value.request.source.phase5PublishRequestGlobalId ===
              command.phase5PublishRequestGlobalId &&
            value.request.source.sourceHash === command.expectedSourceHash &&
            value.request.source.topologyHash ===
              command.expectedTopologyHash &&
            value.request.itemMappingSetHash ===
              command.expectedItemMappingSetHash &&
            value.request.mbomMappingSetHash ===
              command.expectedMbomMappingSetHash,
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
