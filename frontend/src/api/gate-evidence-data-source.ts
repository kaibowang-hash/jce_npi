import { NpiHttpClient, NpiTransportError } from "./http";
import type {
  GateEvidenceKind,
  GateEvidencePersonViewModel,
  GateEvidenceReferenceViewModel,
  GateEvidenceScanState,
  GateEvidenceViewModel,
  GateRequirementEvidenceState,
  GateRequirementViewModel,
} from "../domain/view-models";

export interface GateEvidenceDataSource {
  load: (
    projectGlobalId: string,
    gateGlobalId: string,
    signal: AbortSignal,
  ) => Promise<GateEvidenceViewModel>;
}

export class GateEvidenceRequestCancelledError extends Error {
  constructor() {
    super("The Gate evidence request was cancelled.");
    this.name = "GateEvidenceRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const utcTimestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const sha256Pattern = /^[0-9a-f]{64}$/u;
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/u;
const businessCodePattern = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/u;
const controlledKeyPattern = /^[A-Za-z0-9][A-Za-z0-9._-]*$/u;
const mimeTypePattern =
  /^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$/u;

const evidenceKinds = new Set<GateEvidenceKind>(["wbs_item", "file_revision"]);
const scanStates = new Set<GateEvidenceScanState>([
  "pending",
  "clean",
  "failed",
  "infected",
]);
const evidenceStates = new Set<GateRequirementEvidenceState>([
  "missing",
  "attached",
  "scan_pending",
  "scan_clean",
  "scan_failed",
  "scan_infected",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function hasExactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = [],
): boolean {
  const allowed = new Set([...required, ...optional]);
  return (
    required.every((key) => Object.hasOwn(value, key)) &&
    Object.keys(value).every((key) => allowed.has(key))
  );
}

function isConstrainedString(
  value: unknown,
  maximumLength: number,
  pattern?: RegExp,
): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
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
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value)
  );
}

function isUtcTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    utcTimestampPattern.test(value) &&
    !Number.isNaN(Date.parse(value))
  );
}

function isPerson(value: unknown): value is GateEvidencePersonViewModel {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, ["memberId", "userId", "displayName"]) &&
    isUuid(value.memberId) &&
    isConstrainedString(value.userId, 254, emailPattern) &&
    isConstrainedString(value.displayName, 280)
  );
}

function isFileMetadata(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, ["fileName", "mimeType", "sizeBytes", "scanState"]) &&
    isConstrainedString(value.fileName, 255) &&
    isConstrainedString(value.mimeType, 255, mimeTypePattern) &&
    isNonnegativeInteger(value.sizeBytes) &&
    typeof value.scanState === "string" &&
    scanStates.has(value.scanState as GateEvidenceScanState)
  );
}

function isEvidenceReference(
  value: unknown,
): value is GateEvidenceReferenceViewModel {
  if (!isRecord(value)) return false;
  if (
    !hasExactKeys(
      value,
      [
        "globalId",
        "kind",
        "sourceObjectType",
        "sourceGlobalId",
        "revision",
        "objectHash",
        "createdAt",
        "createdBy",
      ],
      ["file"],
    ) ||
    !isUuid(value.globalId) ||
    typeof value.kind !== "string" ||
    !evidenceKinds.has(value.kind as GateEvidenceKind) ||
    typeof value.sourceObjectType !== "string" ||
    !evidenceKinds.has(value.sourceObjectType as GateEvidenceKind) ||
    value.sourceObjectType !== value.kind ||
    !isUuid(value.sourceGlobalId) ||
    !isPositiveInteger(value.revision) ||
    typeof value.objectHash !== "string" ||
    !sha256Pattern.test(value.objectHash) ||
    !isUtcTimestamp(value.createdAt) ||
    !isConstrainedString(value.createdBy, 254)
  ) {
    return false;
  }
  return value.kind === "file_revision"
    ? Object.hasOwn(value, "file") && isFileMetadata(value.file)
    : !Object.hasOwn(value, "file");
}

function evidenceStateForReferences(
  evidence: readonly GateEvidenceReferenceViewModel[],
): GateRequirementEvidenceState {
  if (evidence.length === 0) return "missing";
  const scanStates = evidence.flatMap((reference) =>
    reference.file ? [reference.file.scanState] : [],
  );
  if (scanStates.includes("infected")) return "scan_infected";
  if (scanStates.includes("failed")) return "scan_failed";
  if (scanStates.includes("pending")) return "scan_pending";
  if (scanStates.length > 0) return "scan_clean";
  return "attached";
}

function isRequirement(value: unknown): value is GateRequirementViewModel {
  if (!isRecord(value)) return false;
  if (
    !hasExactKeys(value, [
      "globalId",
      "key",
      "title",
      "classification",
      "priority",
      "owner",
      "reviewers",
      "dueDate",
      "allowedEvidenceKinds",
      "evidenceState",
      "evidence",
    ]) ||
    !isUuid(value.globalId) ||
    !isConstrainedString(value.key, 64, controlledKeyPattern) ||
    !isConstrainedString(value.title, 280) ||
    (value.classification !== "required" &&
      value.classification !== "optional") ||
    (value.priority !== "P0" &&
      value.priority !== "P1" &&
      value.priority !== "P2") ||
    !isPerson(value.owner) ||
    !Array.isArray(value.reviewers) ||
    value.reviewers.length < 1 ||
    value.reviewers.length > 50 ||
    !value.reviewers.every(isPerson) ||
    new Set(
      value.reviewers.map(
        (reviewer: GateEvidencePersonViewModel) => reviewer.memberId,
      ),
    ).size !== value.reviewers.length ||
    !isIsoDate(value.dueDate) ||
    !Array.isArray(value.allowedEvidenceKinds) ||
    value.allowedEvidenceKinds.length < 1 ||
    value.allowedEvidenceKinds.length > evidenceKinds.size ||
    !value.allowedEvidenceKinds.every(
      (kind: unknown): kind is GateEvidenceKind =>
        typeof kind === "string" && evidenceKinds.has(kind as GateEvidenceKind),
    ) ||
    new Set(value.allowedEvidenceKinds).size !==
      value.allowedEvidenceKinds.length ||
    typeof value.evidenceState !== "string" ||
    !evidenceStates.has(value.evidenceState as GateRequirementEvidenceState) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 100 ||
    !value.evidence.every(isEvidenceReference) ||
    new Set(
      value.evidence.map(
        (evidence: GateEvidenceReferenceViewModel) => evidence.globalId,
      ),
    ).size !== value.evidence.length
  ) {
    return false;
  }
  const allowedEvidenceKinds =
    value.allowedEvidenceKinds as readonly GateEvidenceKind[];
  const evidence = value.evidence as readonly GateEvidenceReferenceViewModel[];
  const evidenceState = value.evidenceState as GateRequirementEvidenceState;
  if (
    evidence.some((reference) => !allowedEvidenceKinds.includes(reference.kind))
  ) {
    return false;
  }
  return evidenceState === evidenceStateForReferences(evidence);
}

function isProject(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, ["globalId", "businessCode", "title"]) &&
    isUuid(value.globalId) &&
    isConstrainedString(value.businessCode, 64, businessCodePattern) &&
    isConstrainedString(value.title, 140)
  );
}

function isGate(value: unknown): boolean {
  if (!isRecord(value) || !isRecord(value.templateRef)) return false;
  return (
    hasExactKeys(value, [
      "globalId",
      "key",
      "title",
      "state",
      "version",
      "dueDate",
      "templateRef",
      "requirementSnapshotHash",
      "frozenAt",
      "frozenBy",
    ]) &&
    isUuid(value.globalId) &&
    isConstrainedString(value.key, 64, controlledKeyPattern) &&
    isConstrainedString(value.title, 140) &&
    value.state === "not_started" &&
    isPositiveInteger(value.version) &&
    isIsoDate(value.dueDate) &&
    hasExactKeys(value.templateRef, ["globalId", "version", "snapshotHash"]) &&
    isUuid(value.templateRef.globalId) &&
    isPositiveInteger(value.templateRef.version) &&
    typeof value.templateRef.snapshotHash === "string" &&
    sha256Pattern.test(value.templateRef.snapshotHash) &&
    typeof value.requirementSnapshotHash === "string" &&
    sha256Pattern.test(value.requirementSnapshotHash) &&
    isUtcTimestamp(value.frozenAt) &&
    isConstrainedString(value.frozenBy, 254)
  );
}

function isPermissions(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, ["canView", "canAttachEvidence", "canAdminister"]) &&
    value.canView === true &&
    typeof value.canAttachEvidence === "boolean" &&
    typeof value.canAdminister === "boolean"
  );
}

export function isGateEvidenceResponse(
  value: unknown,
): value is GateEvidenceViewModel {
  if (!isRecord(value) || !isRecord(value.summary)) return false;
  if (
    !hasExactKeys(value, [
      "project",
      "gate",
      "requirements",
      "summary",
      "permissions",
    ]) ||
    !isProject(value.project) ||
    !isGate(value.gate) ||
    !Array.isArray(value.requirements) ||
    value.requirements.length < 1 ||
    value.requirements.length > 500 ||
    !value.requirements.every(isRequirement) ||
    new Set(
      value.requirements.map(
        (requirement: GateRequirementViewModel) => requirement.globalId,
      ),
    ).size !== value.requirements.length ||
    new Set(
      value.requirements.map(
        (requirement: GateRequirementViewModel) => requirement.key,
      ),
    ).size !== value.requirements.length ||
    !hasExactKeys(value.summary, [
      "requiredCount",
      "missingRequiredCount",
      "unsafeScanCount",
      "evidenceCount",
    ]) ||
    !isNonnegativeInteger(value.summary.requiredCount) ||
    !isNonnegativeInteger(value.summary.missingRequiredCount) ||
    !isNonnegativeInteger(value.summary.unsafeScanCount) ||
    !isNonnegativeInteger(value.summary.evidenceCount) ||
    value.summary.requiredCount > 500 ||
    value.summary.missingRequiredCount > 500 ||
    value.summary.unsafeScanCount > 50000 ||
    value.summary.evidenceCount > 50000 ||
    !isPermissions(value.permissions)
  ) {
    return false;
  }
  const requirements =
    value.requirements as readonly GateRequirementViewModel[];
  const evidence = requirements.flatMap((requirement) => requirement.evidence);
  const requiredCount = requirements.filter(
    (requirement) => requirement.classification === "required",
  ).length;
  const missingRequiredCount = requirements.filter(
    (requirement) =>
      requirement.classification === "required" &&
      requirement.evidenceState === "missing",
  ).length;
  const unsafeScanCount = evidence.filter(
    (reference) =>
      reference.file !== undefined && reference.file.scanState !== "clean",
  ).length;
  return (
    value.summary.requiredCount === requiredCount &&
    value.summary.missingRequiredCount === missingRequiredCount &&
    value.summary.unsafeScanCount === unsafeScanCount &&
    value.summary.evidenceCount === evidence.length &&
    new Set(evidence.map((reference) => reference.globalId)).size ===
      evidence.length
  );
}

export function isGateEvidenceResponseForRoute(
  value: unknown,
  projectGlobalId: string,
  gateGlobalId: string,
): value is GateEvidenceViewModel {
  return (
    isGateEvidenceResponse(value) &&
    value.project.globalId === projectGlobalId &&
    value.gate.globalId === gateGlobalId
  );
}

function clientReference(): string {
  return `client-${globalThis.crypto.randomUUID()}`;
}

export class LiveGateEvidenceDataSource implements GateEvidenceDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async load(
    projectGlobalId: string,
    gateGlobalId: string,
    signal: AbortSignal,
  ): Promise<GateEvidenceViewModel> {
    if (!isUuid(projectGlobalId) || !isUuid(gateGlobalId)) {
      throw new NpiTransportError(
        "request_not_ready",
        clientReference(),
        "client",
      );
    }
    try {
      return await this.http.request<GateEvidenceViewModel>(
        `/projects/${projectGlobalId}/gates/${gateGlobalId}/evidence`,
        { signal },
        {
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is GateEvidenceViewModel =>
            isGateEvidenceResponseForRoute(
              value,
              projectGlobalId,
              gateGlobalId,
            ),
        },
      );
    } catch (error) {
      if (signal.aborted) throw new GateEvidenceRequestCancelledError();
      throw error;
    }
  }
}
