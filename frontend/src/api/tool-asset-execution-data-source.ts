import type { EngineeringBomCommandContext } from "./ebom-data-source";
import { type ConfirmedToolAssetProjection } from "./tooling-acceptance-asset-data-source";
import { NpiHttpClient } from "./http";

export const CREATE_TOOL_ASSET_ACKNOWLEDGEMENT =
  "I confirm this request may create one formal ERP Asset only from the exact physical Tooling Set, separate business approval, mapping state, and execution profile.";
export const UPDATE_TOOL_ASSET_ACKNOWLEDGEMENT =
  "I confirm this request may update only the exact mapped ERP Asset from the physical Tooling Set, separate business approval, mapping state, and execution profile.";

export type ToolAssetExecutionOperation =
  | "create_tool_asset"
  | "update_tool_asset";
export type ToolAssetExecutionState =
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

export interface ToolAssetExecutionContext {
  operation: ToolAssetExecutionOperation;
  source: Record<string, unknown> & {
    projectGlobalId: string;
    toolingMasterGlobalId: string;
    toolingSetGlobalId: string;
    acceptanceRevisionGlobalId: string;
    sourceHash: string;
  };
  expectedSourceHash: string;
  approval: { state: "unavailable" | "verified" };
  expectedApprovalHash: string;
  mappingExpectation: {
    mappingVersion: number;
    formalAssetId: string | null;
    targetVersion: string | null;
  };
  expectedMappingExpectationHash: string;
  profile: {
    targetMode: "mock" | "synthetic" | "sandbox";
    environmentCode: string;
    snapshotHash: string;
  };
  expectedProfileSnapshotHash: string;
}

export interface ToolAssetExecutionSummary {
  requestGlobalId: string;
  request: {
    globalId: string;
    operation: ToolAssetExecutionOperation;
    state: ToolAssetExecutionState;
    source: ToolAssetExecutionContext["source"];
    approval: ToolAssetExecutionContext["approval"];
    mappingExpectation: ToolAssetExecutionContext["mappingExpectation"];
    profile: ToolAssetExecutionContext["profile"];
    optimisticVersion: number;
    payloadHash: string;
    createdAt: string;
  };
  dispatchAllowed: boolean;
  outboxEventId: string | null;
  targetIdempotencyKeyHash: string;
  semanticEffectHash: string;
  resultGlobalId: string | null;
}

export interface ToolAssetExecutionDetail extends ToolAssetExecutionSummary {
  attempts: readonly {
    globalId: string;
    attemptNumber: number;
    state: string;
    adapterBoundaryCrossed: boolean;
    transportDisposition: string | null;
    faultKind: string | null;
    reconciliationRequired: boolean;
    safeErrorCode: string | null;
    startedAt: string;
    finishedAt: string | null;
  }[];
  result: null | {
    globalId: string;
    attemptGlobalId: string;
    attemptNumber: number;
    operation: ToolAssetExecutionOperation;
    state: ToolAssetExecutionState;
    authority: "none" | "synthetic" | "authoritative_sandbox";
    responseAuthenticated: boolean;
    faultKind: string;
    observedAt: string;
    formalAssetId: null;
    targetVersion: null;
  };
  fieldResults: readonly {
    fieldCode: string;
    state: string;
    authority: "none" | "synthetic" | "authoritative_sandbox";
    responseAuthenticated: boolean;
    faultKind: string;
    observedAt: string;
  }[];
  mappingObservation: null | {
    disposition: string;
    authority: "none" | "synthetic" | "authoritative_sandbox";
    responseAuthenticated: boolean;
    observedAt: string;
    previousFormalAssetId: null;
    previousTargetVersion: null;
    observedFormalAssetId: null;
    observedTargetVersion: null;
  };
  currentMapping: null | {
    mappingVersion: number;
    formalAssetId: string;
    targetVersion: string;
    observationHash: string;
    updatedAt: string;
  };
  permissions: { canView: boolean; canCreate: boolean; canUpdate: boolean };
}

export interface ToolAssetExecutionCollection {
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  toolingSetGlobalId: string;
  permissions: ToolAssetExecutionDetail["permissions"];
  businessApproval: ToolAssetExecutionContext["approval"];
  executionProfile: ToolAssetExecutionContext["profile"] | null;
  commandContexts: Partial<
    Record<ToolAssetExecutionOperation, ToolAssetExecutionContext>
  > | null;
  items: readonly ToolAssetExecutionSummary[];
}

export interface ToolAssetExecutionDataSource {
  loadRequests(
    projectId: string,
    masterId: string,
    setId: string,
    acceptanceId: string,
    signal: AbortSignal,
  ): Promise<ToolAssetExecutionCollection>;
  loadRequest(
    projectId: string,
    masterId: string,
    setId: string,
    requestId: string,
    signal: AbortSignal,
  ): Promise<ToolAssetExecutionDetail>;
  createRequest(
    projectId: string,
    masterId: string,
    setId: string,
    context: ToolAssetExecutionContext,
    commandContext: EngineeringBomCommandContext,
  ): Promise<ToolAssetExecutionSummary>;
}

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA = /^[a-f0-9]{64}$/u;
const STATES = new Set<ToolAssetExecutionState>([
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
const FIELDS = new Set([
  "tooling_master_title",
  "physical_set_serial",
  "tooling_requirement_kind",
  "source_tooling_revision",
  "acceptance_evidence_reference",
]);

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}
function sha(value: unknown): value is string {
  return typeof value === "string" && SHA.test(value);
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
function request(
  value: unknown,
): value is ToolAssetExecutionSummary["request"] {
  if (
    !record(value) ||
    !record(value.source) ||
    !record(value.approval) ||
    !record(value.mappingExpectation) ||
    !record(value.profile)
  )
    return false;
  return (
    uuid(value.globalId) &&
    ["create_tool_asset", "update_tool_asset"].includes(
      String(value.operation),
    ) &&
    STATES.has(value.state as ToolAssetExecutionState) &&
    uuid(value.source.projectGlobalId) &&
    uuid(value.source.toolingMasterGlobalId) &&
    uuid(value.source.toolingSetGlobalId) &&
    uuid(value.source.acceptanceRevisionGlobalId) &&
    sha(value.source.sourceHash) &&
    sha(value.payloadHash) &&
    Number.isInteger(value.optimisticVersion) &&
    typeof value.createdAt === "string"
  );
}
function summary(value: unknown): value is ToolAssetExecutionSummary {
  if (
    !record(value) ||
    !exact(value, [
      "requestGlobalId",
      "request",
      "dispatchAllowed",
      "outboxEventId",
      "targetIdempotencyKeyHash",
      "semanticEffectHash",
      "resultGlobalId",
    ]) ||
    !request(value.request)
  )
    return false;
  const requestValue = value.request;
  return (
    uuid(value.requestGlobalId) &&
    value.requestGlobalId === requestValue.globalId &&
    typeof value.dispatchAllowed === "boolean" &&
    (value.outboxEventId === null || uuid(value.outboxEventId)) &&
    sha(value.targetIdempotencyKeyHash) &&
    sha(value.semanticEffectHash) &&
    (value.resultGlobalId === null || uuid(value.resultGlobalId))
  );
}
function context(value: unknown): value is ToolAssetExecutionContext {
  return (
    record(value) &&
    request({
      ...value,
      globalId: "00000000-0000-4000-8000-000000000000",
      state: "queued",
      payloadHash: "0".repeat(64),
      optimisticVersion: 1,
      createdAt: "2026-01-01T00:00:00Z",
    }) &&
    sha(value.expectedSourceHash) &&
    sha(value.expectedApprovalHash) &&
    sha(value.expectedMappingExpectationHash) &&
    sha(value.expectedProfileSnapshotHash)
  );
}
function collection(value: unknown): value is ToolAssetExecutionCollection {
  if (
    !record(value) ||
    !uuid(value.projectGlobalId) ||
    !uuid(value.toolingMasterGlobalId) ||
    !uuid(value.toolingSetGlobalId) ||
    !record(value.permissions) ||
    !Array.isArray(value.items) ||
    !value.items.every(summary)
  )
    return false;
  if (
    value.commandContexts !== null &&
    (!record(value.commandContexts) ||
      !Object.values(value.commandContexts).every(context))
  )
    return false;
  return value.items.every(
    (item) =>
      item.request.source.projectGlobalId === value.projectGlobalId &&
      item.request.source.toolingMasterGlobalId ===
        value.toolingMasterGlobalId &&
      item.request.source.toolingSetGlobalId === value.toolingSetGlobalId,
  );
}
function detail(value: unknown): value is ToolAssetExecutionDetail {
  if (
    !record(value) ||
    !exact(value, [
      "requestGlobalId",
      "request",
      "dispatchAllowed",
      "outboxEventId",
      "targetIdempotencyKeyHash",
      "semanticEffectHash",
      "resultGlobalId",
      "attempts",
      "result",
      "fieldResults",
      "mappingObservation",
      "currentMapping",
      "permissions",
    ])
  )
    return false;
  const base = Object.fromEntries(
    Object.entries(value).filter(([key]) =>
      [
        "requestGlobalId",
        "request",
        "dispatchAllowed",
        "outboxEventId",
        "targetIdempotencyKeyHash",
        "semanticEffectHash",
        "resultGlobalId",
      ].includes(key),
    ),
  );
  if (
    !summary(base) ||
    !Array.isArray(value.attempts) ||
    !Array.isArray(value.fieldResults) ||
    !record(value.permissions)
  )
    return false;
  if (value.result === null)
    return (
      value.fieldResults.length === 0 &&
      value.mappingObservation === null &&
      value.currentMapping === null
    );
  if (
    !record(value.result) ||
    !uuid(value.result.globalId) ||
    !STATES.has(value.result.state as ToolAssetExecutionState) ||
    value.result.formalAssetId !== null ||
    value.result.targetVersion !== null ||
    !record(value.mappingObservation)
  )
    return false;
  if (
    value.fieldResults.length !== 5 ||
    new Set(
      value.fieldResults.map((item) =>
        record(item) ? String(item.fieldCode) : "",
      ),
    ).size !== 5 ||
    !value.fieldResults.every(
      (item) => record(item) && FIELDS.has(String(item.fieldCode)),
    )
  )
    return false;
  if (value.currentMapping === null)
    return (
      value.result.authority !== "authoritative_sandbox" ||
      value.result.responseAuthenticated !== true ||
      value.result.state !== "succeeded"
    );
  return (
    record(value.currentMapping) &&
    value.result.authority === "authoritative_sandbox" &&
    value.result.responseAuthenticated === true &&
    value.result.state === "succeeded" &&
    Number.isInteger(value.currentMapping.mappingVersion) &&
    uuid(base.request.source.toolingSetGlobalId) &&
    typeof value.currentMapping.formalAssetId === "string" &&
    typeof value.currentMapping.targetVersion === "string" &&
    sha(value.currentMapping.observationHash)
  );
}

export function confirmedToolAssetExecutionProjection(
  detailValue: ToolAssetExecutionDetail,
  projection: ConfirmedToolAssetProjection | null,
): ToolAssetExecutionDetail["currentMapping"] {
  const mapping = detailValue.currentMapping;
  if (!mapping || !detailValue.permissions.canView || !projection) return null;
  if (
    projection.item.scopeGlobalId !==
      detailValue.request.source.toolingSetGlobalId ||
    projection.values.formalAssetId !== mapping.formalAssetId ||
    projection.values.targetVersion !== mapping.targetVersion ||
    projection.values.mappingVersion !== mapping.mappingVersion
  )
    return null;
  return mapping;
}

export class LiveToolAssetExecutionDataSource implements ToolAssetExecutionDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}
  async loadRequests(
    projectId: string,
    masterId: string,
    setId: string,
    acceptanceId: string,
    signal: AbortSignal,
  ): Promise<ToolAssetExecutionCollection> {
    const value = await this.http.request<ToolAssetExecutionCollection>(
      `/projects/${projectId}/tooling/${masterId}/sets/${setId}/asset-execution-requests`,
      { signal },
      {
        query: { acceptanceRevisionGlobalId: acceptanceId },
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: collection,
      },
    );
    if (
      value.projectGlobalId !== projectId ||
      value.toolingMasterGlobalId !== masterId ||
      value.toolingSetGlobalId !== setId
    )
      throw new Error("Tool Asset execution response is invalid.");
    return value;
  }
  async loadRequest(
    projectId: string,
    masterId: string,
    setId: string,
    requestId: string,
    signal: AbortSignal,
  ): Promise<ToolAssetExecutionDetail> {
    const value = await this.http.request<ToolAssetExecutionDetail>(
      `/projects/${projectId}/tooling/${masterId}/sets/${setId}/asset-execution-requests/${requestId}`,
      { signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: detail,
      },
    );
    if (
      value.requestGlobalId !== requestId ||
      value.request.source.projectGlobalId !== projectId ||
      value.request.source.toolingMasterGlobalId !== masterId ||
      value.request.source.toolingSetGlobalId !== setId
    )
      throw new Error("Tool Asset execution response is invalid.");
    return value;
  }
  async createRequest(
    projectId: string,
    masterId: string,
    setId: string,
    value: ToolAssetExecutionContext,
    commandContext: EngineeringBomCommandContext,
  ): Promise<ToolAssetExecutionSummary> {
    const acknowledgement =
      value.operation === "create_tool_asset"
        ? CREATE_TOOL_ASSET_ACKNOWLEDGEMENT
        : UPDATE_TOOL_ASSET_ACKNOWLEDGEMENT;
    return await this.http.request<ToolAssetExecutionSummary>(
      `/projects/${projectId}/tooling/${masterId}/sets/${setId}/asset-execution-requests:${value.operation === "create_tool_asset" ? "create" : "update"}`,
      {
        method: "POST",
        signal: commandContext.signal,
        headers: { "Idempotency-Key": commandContext.idempotencyKey },
        body: JSON.stringify({
          acceptanceRevisionGlobalId: value.source.acceptanceRevisionGlobalId,
          expectedSourceHash: value.expectedSourceHash,
          expectedApprovalHash: value.expectedApprovalHash,
          expectedMappingExpectationHash: value.expectedMappingExpectationHash,
          expectedProfileSnapshotHash: value.expectedProfileSnapshotHash,
          acknowledgement,
        }),
      },
      {
        csrfToken: commandContext.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: summary,
      },
    );
  }
}
