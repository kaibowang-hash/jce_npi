import {
  LiveErpProjectionsDataSource,
  type ErpProjectionItemViewModel,
  type ErpProjectionQualityValues,
  type ErpProjectionsDataSource,
} from "./erp-projections-data-source";
import { NpiHttpClient } from "./http";

export const FORMAL_QUALITY_LINK_ACKNOWLEDGEMENT =
  "I confirm this links only the exact observed formal quality reference. It does not write ERPNext or interpret a formal pass.";

export type FormalQualitySourceKind = "trial_defect" | "readiness_assessment";
export type FormalQualityReconciliationState =
  | "current"
  | "drifted"
  | "unavailable";

export interface FormalQualityCandidate {
  observationGlobalId: string;
  headGlobalId: string;
  headOptimisticVersion: number;
  headHash: string;
  scopeGlobalId: string;
  values: ErpProjectionQualityValues;
}

export interface FormalQualityLinkItem {
  linkHead: {
    globalId: string;
    sourceKind: string;
    sourceGlobalId: string;
    optimisticVersion: number;
    currentObservationGlobalId: string;
    currentProjectionHeadGlobalId: string;
    currentProjectionHeadVersion: number;
    headHash: string;
  };
  linkRevision: {
    globalId: string;
    revisionNumber: number;
    source: {
      sourceKind: string;
      sourceGlobalId: string;
      sourceVersion: number;
      sourceState: string;
      sourceSnapshotHash: string;
    };
    formalObservation: {
      observationGlobalId: string;
      headGlobalId: string;
      headOptimisticVersion: number;
      recordKind: string;
      statusCode: string;
      resultCode: string | null;
      payloadHash: string;
      observationHash: string;
      headHash: string;
    };
  };
  reconciliation: {
    state: FormalQualityReconciliationState;
    reasonCode: string;
  };
  formalQualityInterpretation: {
    state: "unavailable";
    reasonCode: "raw_formal_quality_codes_not_interpreted";
  };
}

export interface FormalQualityLinkCollection {
  projectGlobalId: string;
  permissions: { view: true; link: boolean };
  items: readonly FormalQualityLinkItem[];
}

export interface FormalQualitySourceReference {
  sourceKind: FormalQualitySourceKind;
  sourceGlobalId: string;
  sourceVersion: number;
  sourceSnapshotHash: string;
  sourceCapability: boolean;
  scopeKind: "trial_round" | "readiness";
  scopeGlobalId: string;
}

export interface FormalQualityLinkCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface FormalQualityLinkCommand {
  source: FormalQualitySourceReference;
  candidate: FormalQualityCandidate;
  expectedLinkHeadVersion: number;
}

export interface FormalQualityLinkDataSource {
  load(
    projectId: string,
    source: FormalQualitySourceReference,
    signal: AbortSignal,
  ): Promise<{
    collection: FormalQualityLinkCollection;
    candidate: FormalQualityCandidate | null;
  }>;
  link(
    projectId: string,
    command: FormalQualityLinkCommand,
    context: FormalQualityLinkCommandContext,
  ): Promise<FormalQualityLinkItem>;
}

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA = /^[a-f0-9]{64}$/u;
const SOURCE_KINDS = new Set([
  "trial_round",
  "trial_defect",
  "trial_review",
  "readiness_assessment",
  "controlled_quality_report",
]);
const RECORD_KINDS = new Set(["quality_inspection", "ncr", "capa"]);
const REASONS: Record<FormalQualityReconciliationState, Set<string>> = {
  current: new Set(["linked_truth_current"]),
  drifted: new Set([
    "linked_source_advanced",
    "linked_projection_advanced",
    "linked_source_and_projection_advanced",
  ]),
  unavailable: new Set(["current_truth_unavailable"]),
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
    keys.every((key) => key in value)
  );
}
function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}
function sha(value: unknown): value is string {
  return typeof value === "string" && SHA.test(value);
}
function text(value: unknown): value is string {
  return (
    typeof value === "string" && value.length > 0 && value === value.trim()
  );
}
function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function source(value: unknown): boolean {
  return (
    record(value) &&
    exact(value, [
      "tenantId",
      "projectGlobalId",
      "sourceKind",
      "sourceGlobalId",
      "sourceVersion",
      "sourceState",
      "sourceSnapshotHash",
    ]) &&
    text(value.tenantId) &&
    uuid(value.projectGlobalId) &&
    typeof value.sourceKind === "string" &&
    SOURCE_KINDS.has(value.sourceKind) &&
    uuid(value.sourceGlobalId) &&
    positive(value.sourceVersion) &&
    text(value.sourceState) &&
    sha(value.sourceSnapshotHash)
  );
}

function observation(value: unknown): boolean {
  return (
    record(value) &&
    exact(value, [
      "tenantId",
      "projectGlobalId",
      "scopeKind",
      "scopeGlobalId",
      "projectionKind",
      "sourceSystem",
      "availability",
      "freshness",
      "disposition",
      "observationGlobalId",
      "headGlobalId",
      "headOptimisticVersion",
      "sourceObjectType",
      "sourceObjectId",
      "sourceVersion",
      "recordKind",
      "statusCode",
      "resultCode",
      "payloadHash",
      "observationHash",
      "headHash",
      "freshnessPolicyRef",
    ]) &&
    text(value.tenantId) &&
    uuid(value.projectGlobalId) &&
    ["project", "trial_round", "readiness"].includes(String(value.scopeKind)) &&
    uuid(value.scopeGlobalId) &&
    value.projectionKind === "formal_quality_status" &&
    value.sourceSystem === "ERPNEXT" &&
    value.availability === "available" &&
    value.freshness === "fresh" &&
    value.disposition === "applied_current" &&
    uuid(value.observationGlobalId) &&
    uuid(value.headGlobalId) &&
    positive(value.headOptimisticVersion) &&
    text(value.sourceObjectType) &&
    text(value.sourceObjectId) &&
    text(value.sourceVersion) &&
    typeof value.recordKind === "string" &&
    RECORD_KINDS.has(value.recordKind) &&
    text(value.statusCode) &&
    (value.resultCode === null || text(value.resultCode)) &&
    sha(value.payloadHash) &&
    sha(value.observationHash) &&
    sha(value.headHash) &&
    text(value.freshnessPolicyRef)
  );
}

function head(value: unknown): boolean {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "globalId",
      "tenantId",
      "projectGlobalId",
      "sourceKind",
      "sourceGlobalId",
      "streamKeyHash",
      "currentRevisionGlobalId",
      "revisionNumber",
      "currentObservationGlobalId",
      "currentProjectionHeadGlobalId",
      "currentProjectionHeadVersion",
      "optimisticVersion",
      "updatedAt",
      "headHash",
    ]) &&
    value.schemaVersion === 1 &&
    uuid(value.globalId) &&
    text(value.tenantId) &&
    uuid(value.projectGlobalId) &&
    typeof value.sourceKind === "string" &&
    SOURCE_KINDS.has(value.sourceKind) &&
    uuid(value.sourceGlobalId) &&
    sha(value.streamKeyHash) &&
    uuid(value.currentRevisionGlobalId) &&
    positive(value.revisionNumber) &&
    uuid(value.currentObservationGlobalId) &&
    uuid(value.currentProjectionHeadGlobalId) &&
    positive(value.currentProjectionHeadVersion) &&
    positive(value.optimisticVersion) &&
    text(value.updatedAt) &&
    sha(value.headHash)
  );
}

function revision(value: unknown): boolean {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "globalId",
      "streamKeyHash",
      "revisionNumber",
      "predecessorGlobalId",
      "source",
      "formalObservation",
      "linkState",
      "actorUserId",
      "traceId",
      "createdAt",
      "linkHash",
    ]) &&
    value.schemaVersion === 1 &&
    uuid(value.globalId) &&
    sha(value.streamKeyHash) &&
    positive(value.revisionNumber) &&
    (value.predecessorGlobalId === null || uuid(value.predecessorGlobalId)) &&
    source(value.source) &&
    observation(value.formalObservation) &&
    ["linked", "superseded"].includes(String(value.linkState)) &&
    text(value.actorUserId) &&
    text(value.traceId) &&
    text(value.createdAt) &&
    sha(value.linkHash)
  );
}

export function isFormalQualityLinkItem(
  value: unknown,
): value is FormalQualityLinkItem {
  if (
    !record(value) ||
    !exact(value, [
      "linkHead",
      "linkRevision",
      "reconciliation",
      "formalQualityInterpretation",
    ])
  )
    return false;
  if (
    !head(value.linkHead) ||
    !revision(value.linkRevision) ||
    !record(value.reconciliation) ||
    !exact(value.reconciliation, ["state", "reasonCode"]) ||
    !record(value.formalQualityInterpretation) ||
    !exact(value.formalQualityInterpretation, ["state", "reasonCode"])
  )
    return false;
  const state = value.reconciliation.state;
  return (
    typeof state === "string" &&
    state in REASONS &&
    REASONS[state as FormalQualityReconciliationState].has(
      String(value.reconciliation.reasonCode),
    ) &&
    value.formalQualityInterpretation.state === "unavailable" &&
    value.formalQualityInterpretation.reasonCode ===
      "raw_formal_quality_codes_not_interpreted"
  );
}

export function isFormalQualityLinkCollection(
  value: unknown,
  projectId: string,
): value is FormalQualityLinkCollection {
  return (
    record(value) &&
    exact(value, ["projectGlobalId", "permissions", "items"]) &&
    value.projectGlobalId === projectId &&
    record(value.permissions) &&
    exact(value.permissions, ["view", "link"]) &&
    value.permissions.view === true &&
    typeof value.permissions.link === "boolean" &&
    Array.isArray(value.items) &&
    value.items.length <= 1000 &&
    value.items.every(isFormalQualityLinkItem)
  );
}

export function formalQualityCandidate(
  item: ErpProjectionItemViewModel,
  source: FormalQualitySourceReference,
): FormalQualityCandidate | null {
  const truth = item.currentTruth;
  if (
    item.projectionKind !== "formal_quality_status" ||
    item.scopeKind !== source.scopeKind ||
    item.scopeGlobalId !== source.scopeGlobalId ||
    item.availability !== "available" ||
    item.freshness !== "fresh" ||
    item.disposition !== "applied_current" ||
    truth?.observationGlobalId !== item.observationGlobalId ||
    truth.sourceVersion !== item.sourceVersion ||
    truth.payloadHash !== item.payloadHash ||
    !uuid(truth.headGlobalId) ||
    !positive(truth.headOptimisticVersion) ||
    !sha(truth.headHash) ||
    !record(truth.values) ||
    !RECORD_KINDS.has(String(truth.values.recordKind))
  )
    return null;
  return {
    observationGlobalId: truth.observationGlobalId,
    headGlobalId: truth.headGlobalId,
    headOptimisticVersion: truth.headOptimisticVersion,
    headHash: truth.headHash,
    scopeGlobalId: item.scopeGlobalId,
    values: truth.values as ErpProjectionQualityValues,
  };
}

function commandResult(
  value: unknown,
  projectId: string,
): value is Record<string, unknown> {
  return (
    record(value) &&
    exact(value, [
      "projectGlobalId",
      "operation",
      "linkRevision",
      "linkHead",
      "formalQualityInterpretation",
    ]) &&
    value.projectGlobalId === projectId &&
    value.operation === "link_observed_formal_quality_reference" &&
    revision(value.linkRevision) &&
    head(value.linkHead) &&
    record(value.formalQualityInterpretation) &&
    exact(value.formalQualityInterpretation, ["state", "reasonCode"]) &&
    value.formalQualityInterpretation.state === "unavailable" &&
    value.formalQualityInterpretation.reasonCode ===
      "raw_formal_quality_codes_not_interpreted"
  );
}

export class LiveFormalQualityLinkDataSource implements FormalQualityLinkDataSource {
  constructor(
    private readonly http = new NpiHttpClient(),
    private readonly projections: ErpProjectionsDataSource = new LiveErpProjectionsDataSource(),
  ) {}

  async load(
    projectId: string,
    sourceRef: FormalQualitySourceReference,
    signal: AbortSignal,
  ) {
    if (!uuid(projectId) || sourceRef.scopeGlobalId.length === 0)
      throw new Error("Formal quality request is not ready.");
    const [collection, projections] = await Promise.all([
      this.http.request<FormalQualityLinkCollection>(
        `/projects/${projectId}/formal-quality-links`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is FormalQualityLinkCollection =>
            isFormalQualityLinkCollection(value, projectId),
        },
      ),
      this.projections.loadProjectProjections(
        projectId,
        signal,
        "formal_quality_status",
      ),
    ]);
    const candidates = projections.items
      .map((item) => formalQualityCandidate(item, sourceRef))
      .filter((item): item is FormalQualityCandidate => item !== null);
    return {
      collection,
      candidate: candidates.length === 1 ? (candidates[0] ?? null) : null,
    };
  }

  async link(
    projectId: string,
    command: FormalQualityLinkCommand,
    context: FormalQualityLinkCommandContext,
  ): Promise<FormalQualityLinkItem> {
    const value = await this.http.request<Record<string, unknown>>(
      `/projects/${projectId}/formal-quality-links:link-observed-reference`,
      {
        method: "POST",
        signal: context.signal,
        headers: { "Idempotency-Key": context.idempotencyKey },
        body: JSON.stringify({
          sourceKind: command.source.sourceKind,
          sourceGlobalId: command.source.sourceGlobalId,
          expectedSourceVersion: command.source.sourceVersion,
          expectedSourceSnapshotHash: command.source.sourceSnapshotHash,
          formalObservationGlobalId: command.candidate.observationGlobalId,
          expectedProjectionHeadGlobalId: command.candidate.headGlobalId,
          expectedProjectionHeadVersion:
            command.candidate.headOptimisticVersion,
          expectedProjectionHeadHash: command.candidate.headHash,
          expectedLinkHeadVersion: command.expectedLinkHeadVersion,
          acknowledgement: FORMAL_QUALITY_LINK_ACKNOWLEDGEMENT,
        }),
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: (candidate): candidate is Record<string, unknown> =>
          commandResult(candidate, projectId),
      },
    );
    return {
      linkHead: value.linkHead as FormalQualityLinkItem["linkHead"],
      linkRevision: value.linkRevision as FormalQualityLinkItem["linkRevision"],
      reconciliation: { state: "current", reasonCode: "linked_truth_current" },
      formalQualityInterpretation:
        value.formalQualityInterpretation as FormalQualityLinkItem["formalQualityInterpretation"],
    };
  }
}
