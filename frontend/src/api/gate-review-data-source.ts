import { NpiHttpClient, NpiTransportError } from "./http";
import {
  isGateEvidenceResponse,
  isGateEvidenceResponseForRoute,
} from "./gate-evidence-data-source";
import type {
  GateDecisionDetailViewModel,
  GateDecisionOutcome,
  GateDecisionSummaryViewModel,
  GateReviewAuthorityBindingViewModel,
  GateReviewAuthorityPurpose,
  GateReviewAvailablePolicyViewModel,
  GateReviewBlockerViewModel,
  GateReviewClosureActionReferenceViewModel,
  GateReviewClosureActionViewModel,
  GateReviewCycleState,
  GateReviewCycleTrigger,
  GateReviewCycleViewModel,
  GateReviewDependencyChangeViewModel,
  GateReviewDependencyEventType,
  GateReviewDecisionBlockedReasonCode,
  GateReviewDecisionReadinessViewModel,
  GateReviewExceptionDecisionViewModel,
  GateReviewExceptionRequestOptionViewModel,
  GateReviewExceptionRuleViewModel,
  GateReviewExceptionState,
  GateReviewExceptionViewModel,
  GateReviewExactObjectReferenceViewModel,
  GateReviewInputBlockerViewModel,
  GateReviewInputDependencyViewModel,
  GateReviewInputEvidenceViewModel,
  GateReviewInputRequirementViewModel,
  GateReviewInputSnapshotViewModel,
  GateReviewMemberViewModel,
  GateReviewOutcome,
  GateReviewRecordViewModel,
  GateReviewSelectedStepViewModel,
  GateReviewState,
  GateReviewStepState,
  GateReviewViewModel,
} from "../domain/view-models";
import { isProjectPolicyLabelSource } from "../generated/project-policy-label-sources";

export interface GateReviewBindingInput {
  slot: string;
  memberGlobalId: string;
}

export interface StartGateReviewCommand {
  expectedGateVersion: number;
  policyGlobalId: string;
  policyVersion: number;
  policySnapshotHash: string;
  bindings: readonly GateReviewBindingInput[];
}

export interface SubmitGateReviewCommand {
  expectedCycleVersion: number;
  expectedInputHash: string;
  stepKey: string;
  outcome: GateReviewOutcome;
  opinion: string;
}

export interface RequestGateReviewExceptionCommand {
  expectedCycleVersion: number;
  expectedInputHash: string;
  requirementGlobalId: string;
  requirementKey: string;
  kind: string;
  reason: string;
  risk: string;
  expiresAt: string;
  closureActionGlobalId: string;
}

export interface DecideGateReviewExceptionCommand {
  expectedCycleVersion: number;
  expectedExceptionVersion: number;
  expectedInputHash: string;
  outcome: GateReviewOutcome;
  opinion: string;
}

export interface DecideGateCommand {
  expectedGateVersion: number;
  expectedCycleVersion: number;
  expectedInputHash: string;
  outcome: GateDecisionOutcome;
}

export interface ReopenGateCommand {
  expectedGateVersion: number;
  expectedCycleVersion: number;
  expectedInputHash: string;
  reason: string;
  policyGlobalId: string;
  policyVersion: number;
  policySnapshotHash: string;
  bindings: readonly GateReviewBindingInput[];
}

export interface GateReviewCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export type GateReviewCommandOperation =
  | "gate.review.start"
  | "gate.review.submit"
  | "gate.review.exception.request"
  | "gate.review.exception.decide"
  | "gate.review.decide"
  | "gate.review.reopen";

export interface GateReviewCommandReceipt {
  operation: GateReviewCommandOperation;
  status: "completed" | "absent";
  workspaceReloadRequired: true;
}

export interface GateReviewReceiptContext {
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface GateReviewDataSource {
  load: (
    projectGlobalId: string,
    gateGlobalId: string,
    signal: AbortSignal,
  ) => Promise<GateReviewViewModel>;
  startReview: (
    projectGlobalId: string,
    gateGlobalId: string,
    command: StartGateReviewCommand,
    context: GateReviewCommandContext,
  ) => Promise<GateReviewViewModel>;
  submitReview: (
    projectGlobalId: string,
    gateGlobalId: string,
    cycleGlobalId: string,
    command: SubmitGateReviewCommand,
    context: GateReviewCommandContext,
  ) => Promise<GateReviewViewModel>;
  requestException: (
    projectGlobalId: string,
    gateGlobalId: string,
    cycleGlobalId: string,
    command: RequestGateReviewExceptionCommand,
    context: GateReviewCommandContext,
  ) => Promise<GateReviewViewModel>;
  decideException: (
    projectGlobalId: string,
    gateGlobalId: string,
    cycleGlobalId: string,
    exceptionGlobalId: string,
    command: DecideGateReviewExceptionCommand,
    context: GateReviewCommandContext,
  ) => Promise<GateReviewViewModel>;
  decideGate: (
    projectGlobalId: string,
    gateGlobalId: string,
    command: DecideGateCommand,
    context: GateReviewCommandContext,
  ) => Promise<GateReviewViewModel>;
  reopenGate: (
    projectGlobalId: string,
    gateGlobalId: string,
    command: ReopenGateCommand,
    context: GateReviewCommandContext,
  ) => Promise<GateReviewViewModel>;
  reconcileCommandReceipt: (
    projectGlobalId: string,
    gateGlobalId: string,
    operation: GateReviewCommandOperation,
    context: GateReviewReceiptContext,
  ) => Promise<GateReviewCommandReceipt>;
}

export class GateReviewRequestCancelledError extends Error {
  constructor() {
    super("The Gate review request was cancelled.");
    this.name = "GateReviewRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const nilUuid = "00000000-0000-0000-0000-000000000000";
const sha256Pattern = /^[a-f0-9]{64}$/u;
const controlledKeyPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/u;
const stateKeyPattern = /^[a-z][a-z0-9_.-]{0,63}$/u;
const utcTimestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/u;
const idempotencyKeyPattern = /^[!-~]{16,255}$/u;
const commandOperations = new Set<GateReviewCommandOperation>([
  "gate.review.start",
  "gate.review.submit",
  "gate.review.exception.request",
  "gate.review.exception.decide",
  "gate.review.decide",
  "gate.review.reopen",
]);

const reviewStates = new Set<GateReviewState>([
  "not_started",
  "in_review",
  "decided",
  "requires_review",
]);
const reviewOutcomes = new Set<GateReviewOutcome>(["approved", "rejected"]);
const decisionOutcomes = new Set<GateDecisionOutcome>([
  "pass",
  "conditional_pass",
  "reject",
]);
const cycleTriggers = new Set<GateReviewCycleTrigger>([
  "manual_start",
  "manual_reopen",
  "dependency_change",
]);
const cycleStates = new Set<GateReviewCycleState>([
  "active",
  "decided",
  "invalidated",
  "superseded",
]);
const stepStates = new Set<GateReviewStepState>([
  "waiting",
  "available",
  "approved",
  "rejected",
]);
const exceptionStates = new Set<GateReviewExceptionState>([
  "pending",
  "approved",
  "rejected",
]);
const authorityPurposes = new Set<GateReviewAuthorityPurpose>([
  "review",
  "decision",
  "reopen",
  "exception",
]);
const blockerKinds = new Set(["risk", "issue", "action", "decision_request"]);
const dependencyEventTypes = new Set<GateReviewDependencyEventType>([
  "invalidated",
  "refreshed",
]);
const decisionBlockedReasonCodes = new Set<GateReviewDecisionBlockedReasonCode>(
  [
    "REVIEW_CYCLE_CLOSED",
    "GATE_INPUT_CHANGED",
    "DECISION_AUTHORITY_REQUIRED",
    "REVIEWS_INCOMPLETE",
    "FILE_EVIDENCE_UNSAFE",
    "GATE_BLOCKED",
    "REQUIRED_P0_EVIDENCE_MISSING",
    "REQUIRED_EVIDENCE_MISSING",
    "EXCEPTION_NOT_REQUIRED",
    "APPROVED_EXCEPTION_REQUIRED",
  ],
);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function hasExactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
): boolean {
  const expected = new Set(required);
  return (
    Object.keys(value).length === expected.size &&
    required.every((key) => Object.hasOwn(value, key)) &&
    Object.keys(value).every((key) => expected.has(key))
  );
}

function isConstrainedString(
  value: unknown,
  minimum: number,
  maximum: number,
  pattern?: RegExp,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    value.trim().length > 0 &&
    (!pattern || pattern.test(value))
  );
}

function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" && value !== nilUuid && uuidPattern.test(value)
  );
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function isHash(value: unknown): value is string {
  return typeof value === "string" && sha256Pattern.test(value);
}

function isKey(value: unknown): value is string {
  return typeof value === "string" && controlledKeyPattern.test(value);
}

function isStateKey(value: unknown): value is string {
  return typeof value === "string" && stateKeyPattern.test(value);
}

function isUtcTimestamp(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match = utcTimestampPattern.exec(value);
  if (!match) return false;
  const [
    ,
    yearSource,
    monthSource,
    daySource,
    hourSource,
    minuteSource,
    secondSource,
  ] = match;
  const year = Number(yearSource);
  const month = Number(monthSource);
  const day = Number(daySource);
  const hour = Number(hourSource);
  const minute = Number(minuteSource);
  const second = Number(secondSource);
  const parsed = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day &&
    parsed.getUTCHours() === hour &&
    parsed.getUTCMinutes() === minute &&
    parsed.getUTCSeconds() === second
  );
}

function isExpectedVersion(value: unknown): value is number {
  return isPositiveInteger(value) && value < Number.MAX_SAFE_INTEGER;
}

function utcTimestampSortKey(value: string): string {
  const match = utcTimestampPattern.exec(value);
  if (!match) return value;
  const [, year, month, day, hour, minute, second, fraction = ""] = match;
  if (!year || !month || !day || !hour || !minute || !second) return value;
  return `${year}-${month}-${day}T${hour}:${minute}:${second}.${fraction.padEnd(6, "0")}Z`;
}

function isMember(value: unknown): value is GateReviewMemberViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["memberGlobalId", "userId", "displayName"]) &&
    isUuid(value.memberGlobalId) &&
    isConstrainedString(value.userId, 1, 254) &&
    isConstrainedString(value.displayName, 1, 280)
  );
}

function isPolicyReference(
  value: unknown,
): value is GateReviewAvailablePolicyViewModel["policyRef"] {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "version", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    isHash(value.snapshotHash)
  );
}

function isClosureActionReference(
  value: unknown,
): value is GateReviewClosureActionReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "version", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    ((isPositiveInteger(value.version) && isHash(value.snapshotHash)) ||
      (value.version === null && value.snapshotHash === null))
  );
}

function exactReferencesMatch(
  left: GateReviewExactObjectReferenceViewModel,
  right: GateReviewExactObjectReferenceViewModel,
): boolean {
  return (
    left.globalId === right.globalId &&
    left.version === right.version &&
    left.snapshotHash === right.snapshotHash
  );
}

function isStrictlyAscendingByGlobalId(
  values: readonly { globalId: string }[],
): boolean {
  return values.every((value, index) => {
    const previous = values[index - 1];
    return (
      index === 0 ||
      (previous !== undefined && previous.globalId < value.globalId)
    );
  });
}

function isInputRequirement(
  value: unknown,
): value is GateReviewInputRequirementViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "requirementKey",
      "priority",
      "sourceVersion",
      "sourceHash",
      "evidenceComplete",
    ]) &&
    isUuid(value.globalId) &&
    isKey(value.requirementKey) &&
    (value.priority === "P0" ||
      value.priority === "P1" ||
      value.priority === "P2") &&
    isPositiveInteger(value.sourceVersion) &&
    isHash(value.sourceHash) &&
    typeof value.evidenceComplete === "boolean"
  );
}

function isInputEvidence(
  value: unknown,
): value is GateReviewInputEvidenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "requirementGlobalId",
      "evidenceKind",
      "sourceGlobalId",
      "sourceVersion",
      "sourceHash",
      "isFile",
      "fileSafe",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.requirementGlobalId) &&
    (value.evidenceKind === "wbs_item" ||
      value.evidenceKind === "file_revision") &&
    isUuid(value.sourceGlobalId) &&
    isPositiveInteger(value.sourceVersion) &&
    isHash(value.sourceHash) &&
    typeof value.isFile === "boolean" &&
    typeof value.fileSafe === "boolean" &&
    value.isFile === (value.evidenceKind === "file_revision") &&
    (value.isFile || value.fileSafe)
  );
}

function isInputBlocker(
  value: unknown,
): value is GateReviewInputBlockerViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "version",
      "state",
      "blocking",
      "terminal",
    ]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    isKey(value.state) &&
    typeof value.blocking === "boolean" &&
    typeof value.terminal === "boolean"
  );
}

function isInputDependency(
  value: unknown,
): value is GateReviewInputDependencyViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["kind", "globalId", "version", "snapshotHash"]) &&
    value.kind === "gate_input_snapshot" &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    isHash(value.snapshotHash)
  );
}

function isInputSnapshot(
  value: unknown,
): value is GateReviewInputSnapshotViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "schemaVersion",
      "gateGlobalId",
      "projectGlobalId",
      "tenantId",
      "gateVersion",
      "requirements",
      "evidence",
      "blockers",
      "dependencies",
    ]) ||
    value.schemaVersion !== 1 ||
    !isUuid(value.gateGlobalId) ||
    !isUuid(value.projectGlobalId) ||
    !isConstrainedString(value.tenantId, 1, 140) ||
    !isPositiveInteger(value.gateVersion) ||
    !Array.isArray(value.requirements) ||
    value.requirements.length > 256 ||
    !value.requirements.every(isInputRequirement) ||
    !Array.isArray(value.evidence) ||
    value.evidence.length > 512 ||
    !value.evidence.every(isInputEvidence) ||
    !Array.isArray(value.blockers) ||
    value.blockers.length > 256 ||
    !value.blockers.every(isInputBlocker) ||
    !Array.isArray(value.dependencies) ||
    value.dependencies.length > 256 ||
    !value.dependencies.every(isInputDependency)
  ) {
    return false;
  }
  const requirements =
    value.requirements as readonly GateReviewInputRequirementViewModel[];
  const evidence =
    value.evidence as readonly GateReviewInputEvidenceViewModel[];
  const blockers = value.blockers as readonly GateReviewInputBlockerViewModel[];
  const dependencies =
    value.dependencies as readonly GateReviewInputDependencyViewModel[];
  return (
    isStrictlyAscendingByGlobalId(requirements) &&
    isStrictlyAscendingByGlobalId(evidence) &&
    isStrictlyAscendingByGlobalId(blockers) &&
    isStrictlyAscendingByGlobalId(dependencies) &&
    new Set(requirements.map((item) => item.requirementKey.toLowerCase()))
      .size === requirements.length &&
    evidence.every((item) =>
      requirements.some(
        (requirement) => requirement.globalId === item.requirementGlobalId,
      ),
    )
  );
}

function isDecisionDetail(
  value: unknown,
): value is GateDecisionDetailViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "lineageHash",
      "cycleNumber",
      "policyRef",
      "inputSnapshot",
      "reviewHashes",
      "exceptionHashes",
      "cycleVersion",
    ]) ||
    !isHash(value.lineageHash) ||
    !isPositiveInteger(value.cycleNumber) ||
    !isPolicyReference(value.policyRef) ||
    !isInputSnapshot(value.inputSnapshot) ||
    !Array.isArray(value.reviewHashes) ||
    value.reviewHashes.length > 32 ||
    !value.reviewHashes.every(isHash) ||
    new Set(value.reviewHashes).size !== value.reviewHashes.length ||
    !Array.isArray(value.exceptionHashes) ||
    value.exceptionHashes.length > 256 ||
    !value.exceptionHashes.every(isHash) ||
    new Set(value.exceptionHashes).size !== value.exceptionHashes.length ||
    !isPositiveInteger(value.cycleVersion)
  ) {
    return false;
  }
  return true;
}

function isAuthoritySlot(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["slot", "purpose"]) &&
    isKey(value.slot) &&
    typeof value.purpose === "string" &&
    authorityPurposes.has(value.purpose as GateReviewAuthorityPurpose)
  );
}

function isExceptionRule(
  value: unknown,
): value is GateReviewExceptionRuleViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "kind",
      "eligibleRequirementKeys",
      "approvalAuthoritySlot",
      "maximumValidityDays",
      "requiredClosureActionKind",
    ]) ||
    !isKey(value.kind) ||
    !Array.isArray(value.eligibleRequirementKeys) ||
    value.eligibleRequirementKeys.length < 1 ||
    value.eligibleRequirementKeys.length > 256 ||
    !value.eligibleRequirementKeys.every(isKey) ||
    new Set(value.eligibleRequirementKeys).size !==
      value.eligibleRequirementKeys.length ||
    !isKey(value.approvalAuthoritySlot) ||
    !isPositiveInteger(value.maximumValidityDays) ||
    value.maximumValidityDays > 3650 ||
    value.requiredClosureActionKind !== "action"
  ) {
    return false;
  }
  return true;
}

function isAvailablePolicy(
  value: unknown,
): value is GateReviewAvailablePolicyViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["policyRef", "authoritySlots", "exceptionRules"]) ||
    !isPolicyReference(value.policyRef) ||
    !Array.isArray(value.authoritySlots) ||
    value.authoritySlots.length < 1 ||
    value.authoritySlots.length > 64 ||
    !value.authoritySlots.every(isAuthoritySlot) ||
    new Set(
      value.authoritySlots.map((slot) => {
        const record = slot as Record<string, unknown>;
        return String(record.slot).toLowerCase();
      }),
    ).size !== value.authoritySlots.length ||
    !Array.isArray(value.exceptionRules) ||
    value.exceptionRules.length > 32 ||
    !value.exceptionRules.every(isExceptionRule) ||
    new Set(
      value.exceptionRules.map(
        (rule: GateReviewExceptionRuleViewModel) => rule.kind,
      ),
    ).size !== value.exceptionRules.length
  ) {
    return false;
  }
  const authoritySlots = value.authoritySlots as readonly {
    slot: string;
    purpose: GateReviewAuthorityPurpose;
  }[];
  const exceptionRules =
    value.exceptionRules as readonly GateReviewExceptionRuleViewModel[];
  const exceptionSlots = new Set(
    exceptionRules.map((rule) => rule.approvalAuthoritySlot.toLowerCase()),
  );
  return (
    authoritySlots.filter((slot) => slot.purpose === "review").length >= 1 &&
    authoritySlots.filter((slot) => slot.purpose === "decision").length === 1 &&
    authoritySlots.filter((slot) => slot.purpose === "reopen").length === 1 &&
    authoritySlots.filter((slot) => slot.purpose === "exception").length ===
      exceptionSlots.size &&
    authoritySlots
      .filter((slot) => slot.purpose === "exception")
      .every((slot) => exceptionSlots.has(slot.slot.toLowerCase())) &&
    exceptionRules.every((rule) =>
      authoritySlots.some(
        (slot) =>
          slot.slot.toLowerCase() ===
            rule.approvalAuthoritySlot.toLowerCase() &&
          slot.purpose === "exception",
      ),
    )
  );
}

function isAuthorityBinding(
  value: unknown,
): value is GateReviewAuthorityBindingViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["slot", "memberGlobalId", "userId", "displayName"]) &&
    isKey(value.slot) &&
    isUuid(value.memberGlobalId) &&
    isConstrainedString(value.userId, 1, 254) &&
    isConstrainedString(value.displayName, 1, 280)
  );
}

function isReviewRecord(value: unknown): value is GateReviewRecordViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "stepKey",
      "outcome",
      "opinion",
      "actor",
      "reviewedAt",
      "inputHash",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isKey(value.stepKey) &&
    typeof value.outcome === "string" &&
    reviewOutcomes.has(value.outcome as GateReviewOutcome) &&
    isConstrainedString(value.opinion, 1, 4000) &&
    isConstrainedString(value.actor, 1, 254) &&
    isUtcTimestamp(value.reviewedAt) &&
    isHash(value.inputHash) &&
    isHash(value.snapshotHash)
  );
}

function isSelectedStep(
  value: unknown,
): value is GateReviewSelectedStepViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "stepKey",
      "sequence",
      "slot",
      "assignedMember",
      "state",
      "review",
    ]) ||
    !isKey(value.stepKey) ||
    !isPositiveInteger(value.sequence) ||
    !isKey(value.slot) ||
    !isMember(value.assignedMember) ||
    typeof value.state !== "string" ||
    !stepStates.has(value.state as GateReviewStepState) ||
    !(value.review === null || isReviewRecord(value.review))
  ) {
    return false;
  }
  if (value.review === null)
    return value.state === "waiting" || value.state === "available";
  return (
    (value.state === "approved" || value.state === "rejected") &&
    value.review.stepKey === value.stepKey &&
    value.review.outcome === value.state &&
    value.review.actor.toLowerCase() ===
      value.assignedMember.userId.toLowerCase()
  );
}

function isExceptionDecision(
  value: unknown,
): value is GateReviewExceptionDecisionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "outcome",
      "approver",
      "opinion",
      "decidedAt",
      "snapshotHash",
    ]) &&
    typeof value.outcome === "string" &&
    reviewOutcomes.has(value.outcome as GateReviewOutcome) &&
    isMember(value.approver) &&
    isConstrainedString(value.opinion, 1, 4000) &&
    isUtcTimestamp(value.decidedAt) &&
    isHash(value.snapshotHash)
  );
}

function isReviewException(
  value: unknown,
): value is GateReviewExceptionViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "requirementGlobalId",
      "requirementKey",
      "kind",
      "reason",
      "risk",
      "requester",
      "requestedAt",
      "expiresAt",
      "requestSchemaVersion",
      "closureActionRef",
      "state",
      "version",
      "requestSnapshotHash",
      "decision",
      "allowedOutcomes",
    ]) ||
    !isUuid(value.globalId) ||
    !isUuid(value.requirementGlobalId) ||
    !isKey(value.requirementKey) ||
    !isKey(value.kind) ||
    !isConstrainedString(value.reason, 1, 4000) ||
    !isConstrainedString(value.risk, 1, 4000) ||
    !isMember(value.requester) ||
    !isUtcTimestamp(value.requestedAt) ||
    !isUtcTimestamp(value.expiresAt) ||
    utcTimestampSortKey(value.requestedAt) >=
      utcTimestampSortKey(value.expiresAt) ||
    (value.requestSchemaVersion !== 1 && value.requestSchemaVersion !== 2) ||
    !isClosureActionReference(value.closureActionRef) ||
    typeof value.state !== "string" ||
    !exceptionStates.has(value.state as GateReviewExceptionState) ||
    !isPositiveInteger(value.version) ||
    !isHash(value.requestSnapshotHash) ||
    !(value.decision === null || isExceptionDecision(value.decision)) ||
    !Array.isArray(value.allowedOutcomes) ||
    value.allowedOutcomes.length > 2 ||
    !value.allowedOutcomes.every(
      (outcome) =>
        typeof outcome === "string" &&
        reviewOutcomes.has(outcome as GateReviewOutcome),
    ) ||
    new Set(value.allowedOutcomes).size !== value.allowedOutcomes.length
  ) {
    return false;
  }
  if (
    (value.closureActionRef.version === null &&
      (value.requestSchemaVersion !== 1 ||
        value.allowedOutcomes.length !== 0)) ||
    (value.requestSchemaVersion === 2 &&
      value.closureActionRef.version === null)
  ) {
    return false;
  }
  if (value.state === "pending") return value.decision === null;
  return (
    value.allowedOutcomes.length === 0 &&
    value.decision !== null &&
    value.decision.outcome === value.state &&
    utcTimestampSortKey(value.decision.decidedAt) >=
      utcTimestampSortKey(value.requestedAt) &&
    (value.state !== "approved" ||
      utcTimestampSortKey(value.decision.decidedAt) <
        utcTimestampSortKey(value.expiresAt))
  );
}

function isExceptionRequestOption(
  value: unknown,
): value is GateReviewExceptionRequestOptionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "requirementGlobalId",
      "requirementKey",
      "kind",
      "maximumValidityDays",
      "closureActionGlobalIds",
    ]) &&
    isUuid(value.requirementGlobalId) &&
    isKey(value.requirementKey) &&
    isKey(value.kind) &&
    isPositiveInteger(value.maximumValidityDays) &&
    value.maximumValidityDays <= 3650 &&
    Array.isArray(value.closureActionGlobalIds) &&
    value.closureActionGlobalIds.length > 0 &&
    value.closureActionGlobalIds.length <= 500 &&
    value.closureActionGlobalIds.every(isUuid) &&
    new Set(value.closureActionGlobalIds).size ===
      value.closureActionGlobalIds.length
  );
}

function isDecisionReadiness(
  value: unknown,
): value is GateReviewDecisionReadinessViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["allowedOutcomes", "blockedReasons"]) ||
    !Array.isArray(value.allowedOutcomes) ||
    value.allowedOutcomes.length > 3 ||
    !value.allowedOutcomes.every(
      (outcome) =>
        typeof outcome === "string" &&
        decisionOutcomes.has(outcome as GateDecisionOutcome),
    ) ||
    new Set(value.allowedOutcomes).size !== value.allowedOutcomes.length ||
    !Array.isArray(value.blockedReasons) ||
    value.blockedReasons.length > 3 ||
    !value.blockedReasons.every(
      (reason) =>
        isRecord(reason) &&
        hasExactKeys(reason, ["outcome", "code"]) &&
        typeof reason.outcome === "string" &&
        decisionOutcomes.has(reason.outcome as GateDecisionOutcome) &&
        typeof reason.code === "string" &&
        decisionBlockedReasonCodes.has(
          reason.code as GateReviewDecisionBlockedReasonCode,
        ),
    )
  ) {
    return false;
  }
  const blockedReasons = value.blockedReasons as readonly {
    outcome: GateDecisionOutcome;
    code: GateReviewDecisionBlockedReasonCode;
  }[];
  const allowedOutcomes =
    value.allowedOutcomes as readonly GateDecisionOutcome[];
  return (
    new Set(blockedReasons.map((reason) => reason.outcome)).size ===
      blockedReasons.length &&
    blockedReasons.every(
      (reason) => !allowedOutcomes.includes(reason.outcome),
    ) &&
    new Set([
      ...allowedOutcomes,
      ...blockedReasons.map((reason) => reason.outcome),
    ]).size === decisionOutcomes.size
  );
}

function membersMatch(
  left: GateReviewMemberViewModel,
  right: GateReviewMemberViewModel,
): boolean {
  return (
    left.memberGlobalId === right.memberGlobalId &&
    left.userId === right.userId &&
    left.displayName === right.displayName
  );
}

function isCycle(value: unknown): value is GateReviewCycleViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "number",
      "trigger",
      "state",
      "version",
      "policyRef",
      "policyDefinition",
      "inputHash",
      "bindings",
      "selectedSteps",
      "exceptions",
      "startedAt",
      "startedBy",
    ]) ||
    !isUuid(value.globalId) ||
    !isPositiveInteger(value.number) ||
    typeof value.trigger !== "string" ||
    !cycleTriggers.has(value.trigger as GateReviewCycleTrigger) ||
    typeof value.state !== "string" ||
    !cycleStates.has(value.state as GateReviewCycleState) ||
    !isPositiveInteger(value.version) ||
    !isPolicyReference(value.policyRef) ||
    !isAvailablePolicy(value.policyDefinition) ||
    value.policyDefinition.policyRef.globalId !== value.policyRef.globalId ||
    value.policyDefinition.policyRef.version !== value.policyRef.version ||
    value.policyDefinition.policyRef.snapshotHash !==
      value.policyRef.snapshotHash ||
    !isHash(value.inputHash) ||
    !Array.isArray(value.bindings) ||
    value.bindings.length < 1 ||
    value.bindings.length > 64 ||
    !value.bindings.every(isAuthorityBinding) ||
    new Set(
      value.bindings.map((binding: GateReviewAuthorityBindingViewModel) =>
        binding.slot.toLowerCase(),
      ),
    ).size !== value.bindings.length ||
    !Array.isArray(value.selectedSteps) ||
    value.selectedSteps.length < 1 ||
    value.selectedSteps.length > 32 ||
    !value.selectedSteps.every(isSelectedStep) ||
    new Set(
      value.selectedSteps.map(
        (step: GateReviewSelectedStepViewModel) => step.stepKey,
      ),
    ).size !== value.selectedSteps.length ||
    !Array.isArray(value.exceptions) ||
    value.exceptions.length > 256 ||
    !value.exceptions.every(isReviewException) ||
    new Set(
      value.exceptions.map(
        (exception: GateReviewExceptionViewModel) => exception.globalId,
      ),
    ).size !== value.exceptions.length ||
    !isUtcTimestamp(value.startedAt) ||
    !isConstrainedString(value.startedBy, 1, 254)
  ) {
    return false;
  }
  const bindings =
    value.bindings as readonly GateReviewAuthorityBindingViewModel[];
  const selectedSteps =
    value.selectedSteps as readonly GateReviewSelectedStepViewModel[];
  const authoritySlots = value.policyDefinition.authoritySlots;
  const reviewRecords = selectedSteps.flatMap((step) =>
    step.review ? [step.review] : [],
  );
  return (
    (value.number === 1
      ? value.trigger === "manual_start"
      : value.trigger !== "manual_start") &&
    bindings.length === authoritySlots.length &&
    authoritySlots.every((authority) =>
      bindings.some((binding) => binding.slot === authority.slot),
    ) &&
    new Set(reviewRecords.map((review) => review.globalId)).size ===
      reviewRecords.length &&
    new Set(reviewRecords.map((review) => review.snapshotHash)).size ===
      reviewRecords.length &&
    selectedSteps.every((step) => {
      const binding = bindings.find(
        (candidate) => candidate.slot.toLowerCase() === step.slot.toLowerCase(),
      );
      const authority = authoritySlots.find(
        (candidate) => candidate.slot.toLowerCase() === step.slot.toLowerCase(),
      );
      return (
        binding !== undefined &&
        authority?.purpose === "review" &&
        membersMatch(step.assignedMember, {
          memberGlobalId: binding.memberGlobalId,
          userId: binding.userId,
          displayName: binding.displayName,
        }) &&
        (step.review === null || step.review.inputHash === value.inputHash) &&
        (step.review === null ||
          selectedSteps
            .filter((candidate) => candidate.sequence < step.sequence)
            .every((candidate) => candidate.state === "approved")) &&
        (selectedSteps
          .filter((candidate) => candidate.sequence < step.sequence)
          .every((candidate) => candidate.state === "approved") ||
          step.state === "waiting")
      );
    })
  );
}

function isDecisionSummary(
  value: unknown,
): value is GateDecisionSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "cycleGlobalId",
      "outcome",
      "inputHash",
      "snapshotHash",
      "decidedAt",
      "decidedBy",
      "current",
      "detail",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.cycleGlobalId) &&
    typeof value.outcome === "string" &&
    decisionOutcomes.has(value.outcome as GateDecisionOutcome) &&
    isHash(value.inputHash) &&
    isHash(value.snapshotHash) &&
    isUtcTimestamp(value.decidedAt) &&
    isConstrainedString(value.decidedBy, 1, 254) &&
    typeof value.current === "boolean" &&
    isDecisionDetail(value.detail)
  );
}

function isClosureAction(
  value: unknown,
): value is GateReviewClosureActionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "title",
      "state",
      "stateLabelSource",
      "version",
    ]) &&
    isUuid(value.globalId) &&
    isConstrainedString(value.title, 1, 280) &&
    isStateKey(value.state) &&
    isProjectPolicyLabelSource(value.stateLabelSource) &&
    isPositiveInteger(value.version)
  );
}

function isBlocker(value: unknown): value is GateReviewBlockerViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "kind",
      "title",
      "state",
      "stateLabelSource",
      "dueAt",
      "owner",
    ]) &&
    isUuid(value.globalId) &&
    typeof value.kind === "string" &&
    blockerKinds.has(value.kind) &&
    isConstrainedString(value.title, 1, 280) &&
    isStateKey(value.state) &&
    isProjectPolicyLabelSource(value.stateLabelSource) &&
    isUtcTimestamp(value.dueAt) &&
    isConstrainedString(value.owner, 1, 254)
  );
}

function isDependencyChange(
  value: unknown,
): value is GateReviewDependencyChangeViewModel {
  if (!isRecord(value)) return false;
  const requiredKeys = [
    "eventGlobalId",
    "eventType",
    "priorCycleGlobalId",
    "successorCycleGlobalId",
    "oldInputHash",
    "newInputHash",
    "priorDecisionGlobalId",
    "priorDecisionLineageHash",
    "actorUserId",
    "initiatedByUserId",
    "occurredAt",
    "reason",
  ] as const;
  const keys = Object.keys(value);
  if (
    !requiredKeys.every((key) => Object.hasOwn(value, key)) ||
    !keys.every(
      (key) =>
        requiredKeys.includes(key as (typeof requiredKeys)[number]) ||
        key === "impactActionGlobalId",
    ) ||
    keys.length >
      requiredKeys.length +
        (Object.hasOwn(value, "impactActionGlobalId") ? 1 : 0)
  ) {
    return false;
  }
  return (
    isUuid(value.eventGlobalId) &&
    typeof value.eventType === "string" &&
    dependencyEventTypes.has(
      value.eventType as GateReviewDependencyEventType,
    ) &&
    isUuid(value.priorCycleGlobalId) &&
    isUuid(value.successorCycleGlobalId) &&
    value.priorCycleGlobalId !== value.successorCycleGlobalId &&
    (!Object.hasOwn(value, "impactActionGlobalId") ||
      value.impactActionGlobalId === null ||
      isUuid(value.impactActionGlobalId)) &&
    isHash(value.oldInputHash) &&
    isHash(value.newInputHash) &&
    value.oldInputHash !== value.newInputHash &&
    (value.priorDecisionGlobalId === null ||
      isUuid(value.priorDecisionGlobalId)) &&
    (value.priorDecisionLineageHash === null ||
      isHash(value.priorDecisionLineageHash)) &&
    (value.priorDecisionGlobalId === null) ===
      (value.priorDecisionLineageHash === null) &&
    (value.eventType !== "invalidated" ||
      value.priorDecisionGlobalId !== null) &&
    isConstrainedString(value.actorUserId, 1, 254) &&
    (value.initiatedByUserId === null ||
      isConstrainedString(value.initiatedByUserId, 1, 254)) &&
    isUtcTimestamp(value.occurredAt) &&
    isConstrainedString(value.reason, 1, 140)
  );
}

function isReviewGate(value: unknown): value is GateReviewViewModel["gate"] {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "key",
      "title",
      "reviewState",
      "version",
      "currentCycleGlobalId",
      "latestDecisionGlobalId",
      "latestDecisionHash",
      "latestDecisionOutcome",
      "downstreamDecisionCurrent",
    ]) ||
    !isUuid(value.globalId) ||
    !isKey(value.key) ||
    !isConstrainedString(value.title, 1, 140) ||
    typeof value.reviewState !== "string" ||
    !reviewStates.has(value.reviewState as GateReviewState) ||
    !isPositiveInteger(value.version) ||
    !(
      value.currentCycleGlobalId === null || isUuid(value.currentCycleGlobalId)
    ) ||
    !(
      value.latestDecisionGlobalId === null ||
      isUuid(value.latestDecisionGlobalId)
    ) ||
    !(value.latestDecisionHash === null || isHash(value.latestDecisionHash)) ||
    !(
      value.latestDecisionOutcome === null ||
      (typeof value.latestDecisionOutcome === "string" &&
        decisionOutcomes.has(
          value.latestDecisionOutcome as GateDecisionOutcome,
        ))
    ) ||
    typeof value.downstreamDecisionCurrent !== "boolean"
  ) {
    return false;
  }
  const latestFields = [
    value.latestDecisionGlobalId,
    value.latestDecisionHash,
    value.latestDecisionOutcome,
  ];
  return (
    latestFields.every((field) => field === null) ||
    latestFields.every((field) => field !== null)
  );
}

function isPermissions(
  value: unknown,
): value is GateReviewViewModel["permissions"] {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "canView",
      "canStartReview",
      "canReview",
      "canRequestException",
      "canApproveException",
      "canDecide",
      "canReopen",
    ]) &&
    value.canView === true &&
    typeof value.canStartReview === "boolean" &&
    typeof value.canReview === "boolean" &&
    typeof value.canRequestException === "boolean" &&
    typeof value.canApproveException === "boolean" &&
    typeof value.canDecide === "boolean" &&
    typeof value.canReopen === "boolean"
  );
}

export function isGateReviewResponse(
  value: unknown,
): value is GateReviewViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "project",
      "gate",
      "evidence",
      "activeCycle",
      "decisions",
      "availablePolicies",
      "eligibleMembers",
      "eligibleClosureActions",
      "exceptionRequestOptions",
      "decisionReadiness",
      "blockers",
      "dependencyChanges",
      "permissions",
    ]) ||
    !isReviewGate(value.gate) ||
    !isGateEvidenceResponse(value.evidence) ||
    !(value.activeCycle === null || isCycle(value.activeCycle)) ||
    !Array.isArray(value.decisions) ||
    value.decisions.length > 1000 ||
    !value.decisions.every(isDecisionSummary) ||
    !Array.isArray(value.availablePolicies) ||
    value.availablePolicies.length > 100 ||
    !value.availablePolicies.every(isAvailablePolicy) ||
    !Array.isArray(value.eligibleMembers) ||
    value.eligibleMembers.length > 500 ||
    !value.eligibleMembers.every(isMember) ||
    !Array.isArray(value.eligibleClosureActions) ||
    value.eligibleClosureActions.length > 500 ||
    !value.eligibleClosureActions.every(isClosureAction) ||
    !Array.isArray(value.exceptionRequestOptions) ||
    value.exceptionRequestOptions.length > 8192 ||
    !value.exceptionRequestOptions.every(isExceptionRequestOption) ||
    !isDecisionReadiness(value.decisionReadiness) ||
    !Array.isArray(value.blockers) ||
    value.blockers.length > 256 ||
    !value.blockers.every(isBlocker) ||
    !Array.isArray(value.dependencyChanges) ||
    value.dependencyChanges.length > 1000 ||
    !value.dependencyChanges.every(isDependencyChange) ||
    !isPermissions(value.permissions)
  ) {
    return false;
  }
  const evidence = value.evidence;
  const project = value.project;
  const gate = value.gate;
  if (
    !isRecord(project) ||
    !hasExactKeys(project, ["globalId", "businessCode", "title"]) ||
    project.globalId !== evidence.project.globalId ||
    project.businessCode !== evidence.project.businessCode ||
    project.title !== evidence.project.title ||
    gate.globalId !== evidence.gate.globalId ||
    gate.key !== evidence.gate.key ||
    gate.title !== evidence.gate.title ||
    gate.version !== evidence.gate.version
  ) {
    return false;
  }
  const activeCycle = value.activeCycle;
  if (
    (activeCycle === null) !== (gate.currentCycleGlobalId === null) ||
    (activeCycle !== null && activeCycle.globalId !== gate.currentCycleGlobalId)
  ) {
    return false;
  }
  const decisions = value.decisions as readonly GateDecisionSummaryViewModel[];
  if (
    new Set(decisions.map((decision) => decision.globalId)).size !==
      decisions.length ||
    new Set(decisions.map((decision) => decision.cycleGlobalId)).size !==
      decisions.length ||
    !decisions.every((decision, index) => {
      const previous = decisions[index - 1];
      return (
        decision.detail.inputSnapshot.projectGlobalId === project.globalId &&
        decision.detail.inputSnapshot.gateGlobalId === gate.globalId &&
        (activeCycle === null ||
          exactReferencesMatch(
            decision.detail.policyRef,
            activeCycle.policyRef,
          )) &&
        (index === 0 ||
          (previous !== undefined &&
            previous.detail.cycleNumber < decision.detail.cycleNumber))
      );
    })
  ) {
    return false;
  }
  const dependencyChanges = value.dependencyChanges;
  if (
    new Set(dependencyChanges.map((change) => change.eventGlobalId)).size !==
      dependencyChanges.length ||
    new Set(dependencyChanges.map((change) => change.successorCycleGlobalId))
      .size !== dependencyChanges.length ||
    !dependencyChanges.every((change, index) => {
      const previous = dependencyChanges[index - 1];
      const priorDecision =
        change.priorDecisionGlobalId === null
          ? undefined
          : decisions.find(
              (decision) => decision.globalId === change.priorDecisionGlobalId,
            );
      const priorDecisionLineageMatches =
        change.priorDecisionGlobalId === null
          ? change.eventType === "refreshed"
          : priorDecision?.detail.lineageHash ===
              change.priorDecisionLineageHash &&
            utcTimestampSortKey(priorDecision.decidedAt) <=
              utcTimestampSortKey(change.occurredAt) &&
            (change.eventType === "invalidated"
              ? priorDecision.cycleGlobalId === change.priorCycleGlobalId &&
                priorDecision.inputHash === change.oldInputHash
              : priorDecision.cycleGlobalId !== change.priorCycleGlobalId);
      return (
        (!previous ||
          utcTimestampSortKey(previous.occurredAt) >=
            utcTimestampSortKey(change.occurredAt)) &&
        priorDecisionLineageMatches
      );
    })
  ) {
    return false;
  }
  const currentDecisions = decisions.filter((decision) => decision.current);
  const latestDecision =
    gate.latestDecisionGlobalId === null ? undefined : decisions.at(-1);
  const currentDecisionAuthority =
    activeCycle === null
      ? undefined
      : (() => {
          const slot = activeCycle.policyDefinition.authoritySlots.find(
            (authority) => authority.purpose === "decision",
          )?.slot;
          return slot
            ? activeCycle.bindings.find(
                (binding) => binding.slot.toLowerCase() === slot.toLowerCase(),
              )
            : undefined;
        })();
  const currentDecisionMatchesActiveCycle = (): boolean => {
    if (!gate.downstreamDecisionCurrent) return true;
    if (activeCycle === null || currentDecisions.length !== 1) return false;
    const currentDecision = currentDecisions[0];
    if (currentDecision === undefined) return false;
    const reviewedSteps = activeCycle.selectedSteps.filter(
      (
        step,
      ): step is GateReviewSelectedStepViewModel & {
        review: GateReviewRecordViewModel;
      } => step.review !== null,
    );
    return (
      currentDecision.globalId === gate.latestDecisionGlobalId &&
      currentDecision.cycleGlobalId === activeCycle.globalId &&
      currentDecision.inputHash === activeCycle.inputHash &&
      currentDecision.detail.cycleNumber === activeCycle.number &&
      currentDecision.detail.cycleVersion + 1 === activeCycle.version &&
      currentDecision.detail.policyRef.globalId ===
        activeCycle.policyRef.globalId &&
      currentDecision.detail.policyRef.version ===
        activeCycle.policyRef.version &&
      currentDecision.detail.policyRef.snapshotHash ===
        activeCycle.policyRef.snapshotHash &&
      currentDecision.detail.reviewHashes.length === reviewedSteps.length &&
      reviewedSteps.every(
        (step, index) =>
          currentDecision.detail.reviewHashes[index] ===
          step.review.snapshotHash,
      )
    );
  };
  if (
    (decisions.length === 0) !== (gate.latestDecisionGlobalId === null) ||
    (gate.latestDecisionGlobalId !== null &&
      (latestDecision?.globalId !== gate.latestDecisionGlobalId ||
        latestDecision.snapshotHash !== gate.latestDecisionHash ||
        latestDecision.outcome !== gate.latestDecisionOutcome)) ||
    currentDecisions.some(
      (decision) =>
        currentDecisionAuthority?.userId.toLowerCase() !==
        decision.decidedBy.toLowerCase(),
    ) ||
    !currentDecisionMatchesActiveCycle() ||
    (!gate.downstreamDecisionCurrent && currentDecisions.length !== 0)
  ) {
    return false;
  }
  const availablePolicies =
    value.availablePolicies as readonly GateReviewAvailablePolicyViewModel[];
  if (
    new Set(
      availablePolicies.map(
        (policy) =>
          `${policy.policyRef.globalId}\u001f${String(policy.policyRef.version)}\u001f${policy.policyRef.snapshotHash}`,
      ),
    ).size !== availablePolicies.length
  ) {
    return false;
  }
  const eligibleMembers =
    value.eligibleMembers as readonly GateReviewMemberViewModel[];
  const closureActions =
    value.eligibleClosureActions as readonly GateReviewClosureActionViewModel[];
  const exceptionRequestOptions =
    value.exceptionRequestOptions as readonly GateReviewExceptionRequestOptionViewModel[];
  const blockers = value.blockers as readonly GateReviewBlockerViewModel[];
  if (
    new Set(eligibleMembers.map((member) => member.memberGlobalId)).size !==
      eligibleMembers.length ||
    new Set(eligibleMembers.map((member) => member.userId.toLowerCase()))
      .size !== eligibleMembers.length ||
    new Set(closureActions.map((action) => action.globalId)).size !==
      closureActions.length ||
    new Set(
      exceptionRequestOptions.map(
        (option) => `${option.requirementGlobalId}\u001f${option.kind}`,
      ),
    ).size !== exceptionRequestOptions.length ||
    new Set(blockers.map((blocker) => blocker.globalId)).size !==
      blockers.length
  ) {
    return false;
  }
  const requirements = evidence.requirements;
  if (
    activeCycle?.exceptions.some((exception) => {
      const requirement = requirements.find(
        (candidate) => candidate.globalId === exception.requirementGlobalId,
      );
      const rule = activeCycle.policyDefinition.exceptionRules.find(
        (candidate) => candidate.kind === exception.kind,
      );
      const approverBinding =
        rule === undefined
          ? undefined
          : activeCycle.bindings.find(
              (binding) =>
                binding.slot.toLowerCase() ===
                rule.approvalAuthoritySlot.toLowerCase(),
            );
      return (
        requirement?.key !== exception.requirementKey ||
        requirement.classification !== "required" ||
        requirement.priority === "P0" ||
        rule === undefined ||
        !rule.eligibleRequirementKeys.includes(exception.requirementKey) ||
        approverBinding === undefined ||
        exception.requester.memberGlobalId === approverBinding.memberGlobalId ||
        exception.requester.userId.toLowerCase() ===
          approverBinding.userId.toLowerCase() ||
        (exception.decision !== null &&
          (!membersMatch(exception.decision.approver, approverBinding) ||
            exception.decision.approver.memberGlobalId ===
              exception.requester.memberGlobalId ||
            exception.decision.approver.userId.toLowerCase() ===
              exception.requester.userId.toLowerCase()))
      );
    }) ||
    (activeCycle !== null &&
      new Set(
        activeCycle.exceptions.flatMap((exception) =>
          exception.decision ? [exception.decision.snapshotHash] : [],
        ),
      ).size !==
        activeCycle.exceptions.filter(
          (exception) => exception.decision !== null,
        ).length) ||
    exceptionRequestOptions.some((option) => {
      const requirement = requirements.find(
        (candidate) => candidate.globalId === option.requirementGlobalId,
      );
      const rule = activeCycle?.policyDefinition.exceptionRules.find(
        (candidate) => candidate.kind === option.kind,
      );
      return (
        requirement?.key !== option.requirementKey ||
        requirement.classification !== "required" ||
        requirement.priority === "P0" ||
        requirement.evidenceState === "attached" ||
        requirement.evidenceState === "scan_clean" ||
        evidence.summary.unsafeScanCount !== 0 ||
        activeCycle?.state !== "active" ||
        gate.reviewState !== "in_review" ||
        rule === undefined ||
        !rule.eligibleRequirementKeys.includes(option.requirementKey) ||
        rule.maximumValidityDays !== option.maximumValidityDays ||
        option.closureActionGlobalIds.some(
          (globalId) =>
            !closureActions.some((action) => action.globalId === globalId),
        )
      );
    })
  ) {
    return false;
  }
  const permissions = value.permissions;
  const decisionReadiness = value.decisionReadiness;
  const exactActivePolicyIsAvailable =
    activeCycle !== null &&
    availablePolicies.some(
      (policy) =>
        policy.policyRef.globalId === activeCycle.policyRef.globalId &&
        policy.policyRef.version === activeCycle.policyRef.version &&
        policy.policyRef.snapshotHash === activeCycle.policyRef.snapshotHash,
    );
  const activeBindingsAreEligible =
    activeCycle?.bindings.every((binding) =>
      eligibleMembers.some(
        (member) =>
          member.memberGlobalId === binding.memberGlobalId &&
          member.userId === binding.userId &&
          member.displayName === binding.displayName,
      ),
    ) ?? false;
  const exceptionDecisionAvailable = Boolean(
    activeCycle?.exceptions.some(
      (exception) => exception.allowedOutcomes.length > 0,
    ),
  );
  if (
    permissions.canRequestException !== exceptionRequestOptions.length > 0 ||
    permissions.canApproveException !== exceptionDecisionAvailable ||
    permissions.canDecide !== decisionReadiness.allowedOutcomes.length > 0
  ) {
    return false;
  }
  const noInReviewActions =
    !permissions.canReview &&
    !permissions.canRequestException &&
    !permissions.canApproveException &&
    !permissions.canDecide;
  const noActionAvailability =
    exceptionRequestOptions.length === 0 &&
    decisionReadiness.allowedOutcomes.length === 0 &&
    !exceptionDecisionAvailable;
  const activeStepSequenceIsCurrent =
    activeCycle?.selectedSteps.every((step) => {
      if (step.review !== null) return true;
      const priorSequencesApproved = activeCycle.selectedSteps
        .filter((candidate) => candidate.sequence < step.sequence)
        .every((candidate) => candidate.state === "approved");
      return step.state === (priorSequencesApproved ? "available" : "waiting");
    }) ?? false;
  switch (gate.reviewState) {
    case "not_started":
      return (
        activeCycle === null &&
        decisions.length === 0 &&
        noInReviewActions &&
        !permissions.canReopen &&
        noActionAvailability &&
        (!permissions.canStartReview ||
          (availablePolicies.length > 0 && eligibleMembers.length > 0))
      );
    case "in_review":
      return (
        activeCycle?.state === "active" &&
        activeStepSequenceIsCurrent &&
        !permissions.canStartReview &&
        !permissions.canReopen &&
        !gate.downstreamDecisionCurrent
      );
    case "decided":
      return (
        activeCycle?.state === "decided" &&
        latestDecision?.cycleGlobalId === activeCycle.globalId &&
        latestDecision.inputHash === activeCycle.inputHash &&
        noInReviewActions &&
        !permissions.canStartReview &&
        noActionAvailability &&
        (!permissions.canReopen ||
          (exactActivePolicyIsAvailable && activeBindingsAreEligible))
      );
    case "requires_review": {
      if (activeCycle === null) return false;
      const currentDependency = value.dependencyChanges[0];
      const invalidatedLineage =
        currentDependency?.eventType === "invalidated" &&
        latestDecision !== undefined &&
        activeCycle.number === latestDecision.detail.cycleNumber + 1 &&
        currentDependency.priorCycleGlobalId === latestDecision.cycleGlobalId &&
        currentDependency.priorDecisionGlobalId === latestDecision.globalId &&
        currentDependency.priorDecisionLineageHash ===
          latestDecision.detail.lineageHash &&
        currentDependency.oldInputHash === latestDecision.inputHash;
      const refreshedLineage =
        currentDependency?.eventType === "refreshed" &&
        (latestDecision === undefined
          ? activeCycle.number >= 2 &&
            currentDependency.priorDecisionGlobalId === null &&
            currentDependency.priorDecisionLineageHash === null
          : activeCycle.number >= latestDecision.detail.cycleNumber + 2 &&
            currentDependency.priorCycleGlobalId !==
              latestDecision.cycleGlobalId &&
            currentDependency.priorDecisionGlobalId ===
              latestDecision.globalId &&
            currentDependency.priorDecisionLineageHash ===
              latestDecision.detail.lineageHash);
      return (
        activeCycle.state === "active" &&
        activeCycle.trigger === "dependency_change" &&
        activeCycle.version === 1 &&
        activeCycle.exceptions.length === 0 &&
        activeCycle.selectedSteps.every(
          (step) => step.state === "waiting" && step.review === null,
        ) &&
        (invalidatedLineage || refreshedLineage) &&
        currentDependency.successorCycleGlobalId === activeCycle.globalId &&
        currentDependency.newInputHash === activeCycle.inputHash &&
        !gate.downstreamDecisionCurrent &&
        noInReviewActions &&
        !permissions.canReopen &&
        noActionAvailability &&
        (!permissions.canStartReview ||
          (activeBindingsAreEligible && exactActivePolicyIsAvailable))
      );
    }
  }
}

export function isGateReviewResponseForRoute(
  value: unknown,
  projectGlobalId: string,
  gateGlobalId: string,
): value is GateReviewViewModel {
  return (
    isGateReviewResponse(value) &&
    value.project.globalId === projectGlobalId &&
    value.gate.globalId === gateGlobalId &&
    isGateEvidenceResponseForRoute(
      value.evidence,
      projectGlobalId,
      gateGlobalId,
    )
  );
}

function isBindingInput(value: unknown): value is GateReviewBindingInput {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["slot", "memberGlobalId"]) &&
    isKey(value.slot) &&
    isUuid(value.memberGlobalId)
  );
}

function areBindings(
  value: unknown,
): value is readonly GateReviewBindingInput[] {
  return (
    Array.isArray(value) &&
    value.length >= 1 &&
    value.length <= 64 &&
    value.every(isBindingInput) &&
    new Set(
      value.map((binding: GateReviewBindingInput) =>
        binding.slot.toLowerCase(),
      ),
    ).size === value.length
  );
}

function isText(value: unknown): value is string {
  return isConstrainedString(value, 1, 4000);
}

function isStartCommand(value: unknown): value is StartGateReviewCommand {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "expectedGateVersion",
      "policyGlobalId",
      "policyVersion",
      "policySnapshotHash",
      "bindings",
    ]) &&
    isExpectedVersion(value.expectedGateVersion) &&
    isUuid(value.policyGlobalId) &&
    isPositiveInteger(value.policyVersion) &&
    isHash(value.policySnapshotHash) &&
    areBindings(value.bindings)
  );
}

function isSubmitCommand(value: unknown): value is SubmitGateReviewCommand {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "expectedCycleVersion",
      "expectedInputHash",
      "stepKey",
      "outcome",
      "opinion",
    ]) &&
    isExpectedVersion(value.expectedCycleVersion) &&
    isHash(value.expectedInputHash) &&
    isKey(value.stepKey) &&
    typeof value.outcome === "string" &&
    reviewOutcomes.has(value.outcome as GateReviewOutcome) &&
    isText(value.opinion)
  );
}

function isRequestExceptionCommand(
  value: unknown,
): value is RequestGateReviewExceptionCommand {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "expectedCycleVersion",
      "expectedInputHash",
      "requirementGlobalId",
      "requirementKey",
      "kind",
      "reason",
      "risk",
      "expiresAt",
      "closureActionGlobalId",
    ]) &&
    isExpectedVersion(value.expectedCycleVersion) &&
    isHash(value.expectedInputHash) &&
    isUuid(value.requirementGlobalId) &&
    isKey(value.requirementKey) &&
    isKey(value.kind) &&
    isText(value.reason) &&
    isText(value.risk) &&
    isUtcTimestamp(value.expiresAt) &&
    isUuid(value.closureActionGlobalId)
  );
}

function isDecideExceptionCommand(
  value: unknown,
): value is DecideGateReviewExceptionCommand {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "expectedCycleVersion",
      "expectedExceptionVersion",
      "expectedInputHash",
      "outcome",
      "opinion",
    ]) &&
    isExpectedVersion(value.expectedCycleVersion) &&
    isExpectedVersion(value.expectedExceptionVersion) &&
    isHash(value.expectedInputHash) &&
    typeof value.outcome === "string" &&
    reviewOutcomes.has(value.outcome as GateReviewOutcome) &&
    isText(value.opinion)
  );
}

function isDecideGateCommand(value: unknown): value is DecideGateCommand {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "expectedGateVersion",
      "expectedCycleVersion",
      "expectedInputHash",
      "outcome",
    ]) &&
    isExpectedVersion(value.expectedGateVersion) &&
    isExpectedVersion(value.expectedCycleVersion) &&
    isHash(value.expectedInputHash) &&
    typeof value.outcome === "string" &&
    decisionOutcomes.has(value.outcome as GateDecisionOutcome)
  );
}

function isReopenCommand(value: unknown): value is ReopenGateCommand {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "expectedGateVersion",
      "expectedCycleVersion",
      "expectedInputHash",
      "reason",
      "policyGlobalId",
      "policyVersion",
      "policySnapshotHash",
      "bindings",
    ]) &&
    isExpectedVersion(value.expectedGateVersion) &&
    isExpectedVersion(value.expectedCycleVersion) &&
    isHash(value.expectedInputHash) &&
    isText(value.reason) &&
    isUuid(value.policyGlobalId) &&
    isPositiveInteger(value.policyVersion) &&
    isHash(value.policySnapshotHash) &&
    areBindings(value.bindings)
  );
}

function isAbortSignal(value: unknown): value is AbortSignal {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as AbortSignal).aborted === "boolean" &&
    typeof (value as AbortSignal).addEventListener === "function"
  );
}

function isCommandContext(value: unknown): value is GateReviewCommandContext {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["csrfToken", "idempotencyKey", "signal"]) &&
    typeof value.csrfToken === "string" &&
    value.csrfToken.length >= 32 &&
    value.csrfToken.length <= 128 &&
    !/[\r\n]/u.test(value.csrfToken) &&
    typeof value.idempotencyKey === "string" &&
    idempotencyKeyPattern.test(value.idempotencyKey) &&
    isAbortSignal(value.signal)
  );
}

function isReceiptContext(value: unknown): value is GateReviewReceiptContext {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["idempotencyKey", "signal"]) &&
    typeof value.idempotencyKey === "string" &&
    idempotencyKeyPattern.test(value.idempotencyKey) &&
    isAbortSignal(value.signal)
  );
}

function isCommandOperation(
  value: unknown,
): value is GateReviewCommandOperation {
  return (
    typeof value === "string" &&
    commandOperations.has(value as GateReviewCommandOperation)
  );
}

function isCommandReceiptForOperation(
  value: unknown,
  operation: GateReviewCommandOperation,
): value is GateReviewCommandReceipt {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["operation", "status", "workspaceReloadRequired"]) &&
    value.operation === operation &&
    isCommandOperation(value.operation) &&
    (value.status === "completed" || value.status === "absent") &&
    value.workspaceReloadRequired === true
  );
}

function clientReference(): string {
  return `client-${globalThis.crypto.randomUUID()}`;
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    clientReference(),
    "client",
  );
}

function throwIfCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new GateReviewRequestCancelledError();
}

function validRouteIds(...values: readonly string[]): boolean {
  return values.every(isUuid);
}

function responseBindingsMatchCommand(
  bindings: readonly GateReviewAuthorityBindingViewModel[],
  commandBindings: readonly GateReviewBindingInput[],
): boolean {
  return (
    bindings.length === commandBindings.length &&
    commandBindings.every((commandBinding) =>
      bindings.some(
        (binding) =>
          binding.slot === commandBinding.slot &&
          binding.memberGlobalId === commandBinding.memberGlobalId,
      ),
    )
  );
}

export class LiveGateReviewDataSource implements GateReviewDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async load(
    projectGlobalId: string,
    gateGlobalId: string,
    signal: AbortSignal,
  ): Promise<GateReviewViewModel> {
    if (
      !validRouteIds(projectGlobalId, gateGlobalId) ||
      !isAbortSignal(signal)
    ) {
      throw requestNotReady();
    }
    throwIfCancelled(signal);
    try {
      return await this.http.request<GateReviewViewModel>(
        `/projects/${projectGlobalId}/gates/${gateGlobalId}/review`,
        { signal },
        {
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is GateReviewViewModel =>
            isGateReviewResponseForRoute(value, projectGlobalId, gateGlobalId),
        },
      );
    } catch (error) {
      throwIfCancelled(signal);
      throw error;
    }
  }

  async reconcileCommandReceipt(
    projectGlobalId: string,
    gateGlobalId: string,
    operation: GateReviewCommandOperation,
    context: GateReviewReceiptContext,
  ): Promise<GateReviewCommandReceipt> {
    if (
      !validRouteIds(projectGlobalId, gateGlobalId) ||
      !isCommandOperation(operation) ||
      !isReceiptContext(context)
    ) {
      throw requestNotReady();
    }
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<GateReviewCommandReceipt>(
        `/projects/${projectGlobalId}/gates/${gateGlobalId}/review-command-receipts/${operation}`,
        {
          headers: { "Idempotency-Key": context.idempotencyKey },
          signal: context.signal,
        },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is GateReviewCommandReceipt =>
            isCommandReceiptForOperation(value, operation),
        },
      );
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }

  async startReview(
    projectGlobalId: string,
    gateGlobalId: string,
    command: StartGateReviewCommand,
    context: GateReviewCommandContext,
  ): Promise<GateReviewViewModel> {
    if (
      !validRouteIds(projectGlobalId, gateGlobalId) ||
      !isStartCommand(command)
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectGlobalId}/gates/${gateGlobalId}:start-review`,
      command,
      context,
      (value): value is GateReviewViewModel =>
        isGateReviewResponseForRoute(value, projectGlobalId, gateGlobalId) &&
        value.gate.version === command.expectedGateVersion + 1 &&
        value.gate.reviewState === "in_review" &&
        value.activeCycle?.state === "active" &&
        value.activeCycle.version === 1 &&
        value.activeCycle.policyRef.globalId === command.policyGlobalId &&
        value.activeCycle.policyRef.version === command.policyVersion &&
        value.activeCycle.policyRef.snapshotHash ===
          command.policySnapshotHash &&
        responseBindingsMatchCommand(
          value.activeCycle.bindings,
          command.bindings,
        ) &&
        value.activeCycle.exceptions.length === 0 &&
        value.activeCycle.selectedSteps.every((step) => step.review === null) &&
        (value.activeCycle.number === 1
          ? value.activeCycle.trigger === "manual_start" &&
            value.decisions.length === 0
          : value.activeCycle.trigger === "dependency_change" &&
            value.dependencyChanges[0]?.successorCycleGlobalId ===
              value.activeCycle.globalId &&
            value.dependencyChanges[0].newInputHash ===
              value.activeCycle.inputHash),
    );
  }

  async submitReview(
    projectGlobalId: string,
    gateGlobalId: string,
    cycleGlobalId: string,
    command: SubmitGateReviewCommand,
    context: GateReviewCommandContext,
  ): Promise<GateReviewViewModel> {
    if (
      !validRouteIds(projectGlobalId, gateGlobalId, cycleGlobalId) ||
      !isSubmitCommand(command)
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectGlobalId}/gates/${gateGlobalId}/review-cycles/${cycleGlobalId}/reviews`,
      command,
      context,
      (value): value is GateReviewViewModel =>
        isGateReviewResponseForRoute(value, projectGlobalId, gateGlobalId) &&
        value.activeCycle?.globalId === cycleGlobalId &&
        value.activeCycle.version === command.expectedCycleVersion + 1 &&
        value.activeCycle.inputHash === command.expectedInputHash &&
        value.activeCycle.selectedSteps.some(
          (step) =>
            step.stepKey === command.stepKey &&
            step.state === command.outcome &&
            step.review?.opinion === command.opinion.trim(),
        ),
    );
  }

  async requestException(
    projectGlobalId: string,
    gateGlobalId: string,
    cycleGlobalId: string,
    command: RequestGateReviewExceptionCommand,
    context: GateReviewCommandContext,
  ): Promise<GateReviewViewModel> {
    if (
      !validRouteIds(projectGlobalId, gateGlobalId, cycleGlobalId) ||
      !isRequestExceptionCommand(command)
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectGlobalId}/gates/${gateGlobalId}/review-cycles/${cycleGlobalId}/exceptions`,
      command,
      context,
      (value): value is GateReviewViewModel =>
        isGateReviewResponseForRoute(value, projectGlobalId, gateGlobalId) &&
        value.activeCycle?.globalId === cycleGlobalId &&
        value.activeCycle.version === command.expectedCycleVersion + 1 &&
        value.activeCycle.inputHash === command.expectedInputHash &&
        value.activeCycle.exceptions.some(
          (exception) =>
            exception.requirementGlobalId === command.requirementGlobalId &&
            exception.requirementKey === command.requirementKey &&
            exception.kind === command.kind &&
            exception.reason === command.reason.trim() &&
            exception.risk === command.risk.trim() &&
            exception.expiresAt === command.expiresAt &&
            exception.closureActionRef.globalId ===
              command.closureActionGlobalId &&
            exception.closureActionRef.version ===
              value.eligibleClosureActions.find(
                (action) => action.globalId === command.closureActionGlobalId,
              )?.version &&
            exception.state === "pending",
        ),
    );
  }

  async decideException(
    projectGlobalId: string,
    gateGlobalId: string,
    cycleGlobalId: string,
    exceptionGlobalId: string,
    command: DecideGateReviewExceptionCommand,
    context: GateReviewCommandContext,
  ): Promise<GateReviewViewModel> {
    if (
      !validRouteIds(
        projectGlobalId,
        gateGlobalId,
        cycleGlobalId,
        exceptionGlobalId,
      ) ||
      !isDecideExceptionCommand(command)
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectGlobalId}/gates/${gateGlobalId}/review-cycles/${cycleGlobalId}/exceptions/${exceptionGlobalId}:decide`,
      command,
      context,
      (value): value is GateReviewViewModel =>
        isGateReviewResponseForRoute(value, projectGlobalId, gateGlobalId) &&
        value.activeCycle?.globalId === cycleGlobalId &&
        value.activeCycle.version === command.expectedCycleVersion + 1 &&
        value.activeCycle.inputHash === command.expectedInputHash &&
        value.activeCycle.exceptions.some(
          (exception) =>
            exception.globalId === exceptionGlobalId &&
            exception.version === command.expectedExceptionVersion + 1 &&
            exception.state === command.outcome &&
            exception.decision?.outcome === command.outcome &&
            exception.decision.opinion === command.opinion.trim(),
        ),
    );
  }

  async decideGate(
    projectGlobalId: string,
    gateGlobalId: string,
    command: DecideGateCommand,
    context: GateReviewCommandContext,
  ): Promise<GateReviewViewModel> {
    if (
      !validRouteIds(projectGlobalId, gateGlobalId) ||
      !isDecideGateCommand(command)
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectGlobalId}/gates/${gateGlobalId}:decide`,
      command,
      context,
      (value): value is GateReviewViewModel =>
        isGateReviewResponseForRoute(value, projectGlobalId, gateGlobalId) &&
        value.gate.version === command.expectedGateVersion + 1 &&
        value.activeCycle?.state === "decided" &&
        value.activeCycle.version === command.expectedCycleVersion + 1 &&
        value.activeCycle.inputHash === command.expectedInputHash &&
        value.gate.latestDecisionOutcome === command.outcome &&
        value.decisions.some(
          (decision) =>
            decision.globalId === value.gate.latestDecisionGlobalId &&
            decision.cycleGlobalId === value.activeCycle?.globalId &&
            decision.outcome === command.outcome &&
            decision.inputHash === command.expectedInputHash &&
            decision.current,
        ),
    );
  }

  async reopenGate(
    projectGlobalId: string,
    gateGlobalId: string,
    command: ReopenGateCommand,
    context: GateReviewCommandContext,
  ): Promise<GateReviewViewModel> {
    if (
      !validRouteIds(projectGlobalId, gateGlobalId) ||
      !isReopenCommand(command)
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectGlobalId}/gates/${gateGlobalId}:reopen`,
      command,
      context,
      (value): value is GateReviewViewModel =>
        isGateReviewResponseForRoute(value, projectGlobalId, gateGlobalId) &&
        value.gate.version === command.expectedGateVersion + 1 &&
        value.gate.reviewState === "in_review" &&
        value.activeCycle?.state === "active" &&
        value.activeCycle.version === 1 &&
        value.activeCycle.number > 1 &&
        value.activeCycle.trigger === "manual_reopen" &&
        value.activeCycle.policyRef.globalId === command.policyGlobalId &&
        value.activeCycle.policyRef.version === command.policyVersion &&
        value.activeCycle.policyRef.snapshotHash ===
          command.policySnapshotHash &&
        responseBindingsMatchCommand(
          value.activeCycle.bindings,
          command.bindings,
        ) &&
        value.activeCycle.exceptions.length === 0 &&
        value.activeCycle.selectedSteps.every((step) => step.review === null) &&
        value.decisions.length > 0 &&
        value.decisions.every(
          (decision) =>
            !decision.current &&
            decision.cycleGlobalId !== value.activeCycle?.globalId,
        ),
    );
  }

  private async command(
    path: string,
    body: object,
    context: GateReviewCommandContext,
    validate: (value: unknown) => value is GateReviewViewModel,
  ): Promise<GateReviewViewModel> {
    if (!isCommandContext(context)) throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<GateReviewViewModel>(
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
