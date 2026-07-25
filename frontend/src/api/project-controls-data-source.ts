import type {
  ProjectActivityAttachmentViewModel,
  ProjectActivityItemViewModel,
  ProjectActivityPageViewModel,
  ProjectCommentDetailViewModel,
  ProjectControlAction,
  ProjectControlAuthorityViewModel,
  ProjectControlBindingOptionsViewModel,
  ProjectControlPolicyReferenceViewModel,
  ProjectControlsViewModel,
  ProjectFollowStateViewModel,
  ProjectHealthDimension,
  ProjectHealthDimensionResultViewModel,
  ProjectHealthAssessmentSummaryViewModel,
  ProjectHealthEvaluationViewModel,
  ProjectHealthStatus,
  ProjectLearningKind,
  ProjectLearningPageViewModel,
  ProjectLearningViewModel,
  ProjectLifecycleActionViewModel,
  ProjectLifecyclePrerequisiteViewModel,
  ProjectLifecycleState,
  ProjectMentionViewModel,
  ProjectObjectLinkType,
  ProjectObjectLinkViewModel,
  ProjectObjectTargetViewModel,
} from "../domain/view-models";
import { NpiHttpClient, NpiTransportError } from "./http";

export interface ProjectCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface ProjectControlBindingInput {
  slot: string;
  memberGlobalId: string;
}

export interface BindProjectControlPolicyCommand {
  expectedProjectVersion: number;
  policyRef: ProjectControlPolicyReferenceViewModel;
  bindings: readonly ProjectControlBindingInput[];
}

export interface ProjectHealthMeasurementInput {
  dimension: ProjectHealthDimension;
  numericValue: number | string | null;
  manualStatus: Extract<ProjectHealthStatus, "green" | "yellow" | "red"> | null;
}

export interface AssessProjectHealthCommand {
  expectedProjectVersion: number;
  measurements: readonly ProjectHealthMeasurementInput[];
  reason: string | null;
  recoveryPlan: string | null;
}

export interface TransitionProjectCommand {
  expectedProjectVersion: number;
  action: ProjectControlAction;
  reason: string;
}

export interface ProjectCommentReferenceInput {
  globalId: string;
  version: number;
}

export interface ProjectCommentObjectLinkInput extends ProjectCommentReferenceInput {
  type: ProjectObjectLinkType;
}

export interface AddProjectCommentCommand {
  body: string;
  mentions: readonly Readonly<{ memberGlobalId: string }>[];
  attachments: readonly ProjectCommentReferenceInput[];
  objectLinks: readonly ProjectCommentObjectLinkInput[];
}

export interface ProjectLearningQuery {
  kind?: ProjectLearningKind | undefined;
  search?: string | undefined;
  learningId?: string | undefined;
  limit?: number | undefined;
}

export interface CreateProjectLearningCommand {
  kind: ProjectLearningKind;
  title: string;
  content: string;
  recommendation: string | null;
  tags: readonly string[];
}

export interface ProjectControlsDataSource {
  loadControls(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ProjectControlsViewModel>;
  bindPolicy(
    projectId: string,
    command: BindProjectControlPolicyCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectControlsViewModel>;
  assessHealth(
    projectId: string,
    command: AssessProjectHealthCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectControlsViewModel>;
  transition(
    projectId: string,
    command: TransitionProjectCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectControlsViewModel>;
  loadActivity(
    projectId: string,
    signal: AbortSignal,
    limit?: number,
    cursor?: string,
  ): Promise<ProjectActivityPageViewModel>;
  addComment(
    projectId: string,
    command: AddProjectCommentCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectActivityItemViewModel>;
  changeFollowing(
    projectId: string,
    following: boolean,
    expectedVersion: number,
    context: ProjectCommandContext,
  ): Promise<ProjectFollowStateViewModel>;
  loadLearning(
    projectId: string,
    query: ProjectLearningQuery,
    signal: AbortSignal,
  ): Promise<ProjectLearningPageViewModel>;
  createLearning(
    projectId: string,
    command: CreateProjectLearningCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectLearningViewModel>;
}

export class ProjectControlsRequestCancelledError extends Error {
  constructor() {
    super("The Project controls request was cancelled.");
    this.name = "ProjectControlsRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const cursorPattern = /^[A-Za-z0-9._~:-]{1,500}$/u;
const keyPattern = /^[a-z][a-z0-9_.-]{0,63}$/u;
const businessCodePattern = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$/u;
const tenantPattern = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u;
const decimalPattern = /^-?[0-9]+(?:\.[0-9]+)?$/u;
const emailPattern = /^[^\s@]+@[^\s@]+$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u;

const lifecycleStates = new Set<ProjectLifecycleState>([
  "draft",
  "proposed",
  "active",
  "on_hold",
  "completed",
  "cancelled",
]);
const healthStatuses = new Set<ProjectHealthStatus>([
  "unassessed",
  "unavailable",
  "green",
  "yellow",
  "red",
]);
const dimensions = new Set<ProjectHealthDimension>([
  "progress",
  "cost",
  "quality",
  "risk",
]);
const ruleModes = new Set([
  "manual",
  "higher_is_better",
  "lower_is_better",
  "unavailable",
]);
const projectActions = new Set<ProjectControlAction>([
  "pause",
  "cancel",
  "resume",
  "complete",
]);
const prerequisiteKeys = new Set([
  "open_blockers",
  "controlled_files",
  "handover",
  "cost",
]);
const prerequisiteStatuses = new Set(["satisfied", "blocked", "unavailable"]);
const lifecycleReasonCodes = new Set([
  "available",
  "policy_missing",
  "project_terminal",
  "transition_not_defined",
  "command_access_required",
  "authority_required",
  "prerequisite_unavailable",
  "prerequisite_blocked",
]);
const learningKinds = new Set<ProjectLearningKind>([
  "retrospective",
  "lesson",
  "template_improvement",
]);
const manualHealthStatuses = new Set<
  Exclude<ProjectHealthMeasurementInput["manualStatus"], null>
>(["green", "yellow", "red"]);
const objectLinkTypes = new Set<ProjectObjectLinkType>([
  "project",
  "gate",
  "domain_work_item",
  "file_revision",
  "learning",
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

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    timestampPattern.test(value) &&
    !Number.isNaN(Date.parse(value))
  );
}

function isEmail(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length >= 3 &&
    value.length <= 254 &&
    emailPattern.test(value)
  );
}

function isFrappeUserId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length >= 1 &&
    value.length <= 254 &&
    !/[\s\p{Cc}]/u.test(value)
  );
}

function hasUniqueValues<T>(
  values: readonly T[],
  identity: (value: T) => string,
): boolean {
  return new Set(values.map(identity)).size === values.length;
}

function timestampMicroseconds(value: string): bigint {
  const fraction = /\.(\d{1,6})(?:Z|[+-]\d{2}:\d{2})$/u.exec(value)?.[1] ?? "";
  const subMillisecond = fraction.padEnd(6, "0").slice(3);
  return BigInt(Date.parse(value)) * 1000n + BigInt(subMillisecond || "0");
}

function compareActivityItems(
  left: ProjectActivityItemViewModel,
  right: ProjectActivityItemViewModel,
): number {
  const leftTime = timestampMicroseconds(left.occurredAt);
  const rightTime = timestampMicroseconds(right.occurredAt);
  if (leftTime !== rightTime) return leftTime > rightTime ? -1 : 1;
  if (left.globalId === right.globalId) return 0;
  return left.globalId > right.globalId ? -1 : 1;
}

function isStrictlyDescendingActivity(
  items: readonly ProjectActivityItemViewModel[],
): boolean {
  return items.every((item, index) => {
    const previous = items[index - 1];
    return previous === undefined || compareActivityItems(previous, item) < 0;
  });
}

function isPolicyReference(
  value: unknown,
): value is ProjectControlPolicyReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "version", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    isString(value.snapshotHash, 64, 64, hashPattern)
  );
}

function isAuthority(
  value: unknown,
): value is ProjectControlAuthorityViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["slot", "memberGlobalId", "userId", "displayName"]) &&
    isString(value.slot, 1, 64, keyPattern) &&
    isUuid(value.memberGlobalId) &&
    isEmail(value.userId) &&
    isString(value.displayName, 1, 140)
  );
}

function isBindingOptions(
  value: unknown,
): value is ProjectControlBindingOptionsViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["policies", "eligibleMembers"]) ||
    !Array.isArray(value.policies) ||
    value.policies.length > 500 ||
    !Array.isArray(value.eligibleMembers) ||
    value.eligibleMembers.length > 500
  ) {
    return false;
  }
  const policies: readonly unknown[] = value.policies;
  const eligibleMembers: readonly unknown[] = value.eligibleMembers;
  const policyKeys = new Set<string>();
  for (const policy of policies) {
    if (
      !isRecord(policy) ||
      !hasExactKeys(policy, ["policyRef", "code", "title", "authoritySlots"]) ||
      !isPolicyReference(policy.policyRef) ||
      !isString(policy.code, 1, 64, businessCodePattern) ||
      !isString(policy.title, 1, 140) ||
      !Array.isArray(policy.authoritySlots) ||
      policy.authoritySlots.length < 1 ||
      policy.authoritySlots.length > 64
    ) {
      return false;
    }
    const authoritySlots: readonly unknown[] = policy.authoritySlots;
    if (
      !authoritySlots.every((slot) => isString(slot, 1, 64, keyPattern)) ||
      new Set(authoritySlots).size !== authoritySlots.length
    ) {
      return false;
    }
    const identity = `${policy.policyRef.globalId}:${String(policy.policyRef.version)}`;
    if (policyKeys.has(identity)) return false;
    policyKeys.add(identity);
  }
  const memberIds = new Set<string>();
  for (const member of eligibleMembers) {
    if (
      !isRecord(member) ||
      !hasExactKeys(member, ["memberGlobalId", "userId", "displayName"]) ||
      !isUuid(member.memberGlobalId) ||
      !isEmail(member.userId) ||
      !isString(member.displayName, 1, 140) ||
      memberIds.has(member.memberGlobalId)
    ) {
      return false;
    }
    memberIds.add(member.memberGlobalId);
  }
  return true;
}

function isDimensionResult(
  value: unknown,
): value is ProjectHealthDimensionResultViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["dimension", "ruleMode", "status", "numericValue"]) &&
    typeof value.dimension === "string" &&
    dimensions.has(value.dimension as ProjectHealthDimension) &&
    typeof value.ruleMode === "string" &&
    ruleModes.has(value.ruleMode) &&
    typeof value.status === "string" &&
    healthStatuses.has(value.status as ProjectHealthStatus) &&
    (value.numericValue === null ||
      isString(value.numericValue, 1, 100, decimalPattern))
  );
}

function isCompleteDimensionSet(
  value: unknown,
): value is readonly ProjectHealthDimensionResultViewModel[] {
  return (
    Array.isArray(value) &&
    value.length === dimensions.size &&
    value.every(isDimensionResult) &&
    hasUniqueValues(value, (item) => item.dimension) &&
    [...dimensions].every((dimension) =>
      value.some((item) => item.dimension === dimension),
    )
  );
}

function isAssessmentSummary(
  value: unknown,
): value is ProjectHealthAssessmentSummaryViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "assessedAt",
      "actor",
      "reason",
      "recoveryPlan",
    ])
  ) {
    return false;
  }
  return (
    isUuid(value.globalId) &&
    isTimestamp(value.assessedAt) &&
    isAuthority(value.actor) &&
    (value.reason === null || isString(value.reason, 1, 2000)) &&
    (value.recoveryPlan === null || isString(value.recoveryPlan, 1, 4000))
  );
}

function isPrerequisite(
  value: unknown,
): value is ProjectLifecyclePrerequisiteViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["key", "status"]) &&
    typeof value.key === "string" &&
    prerequisiteKeys.has(value.key) &&
    typeof value.status === "string" &&
    prerequisiteStatuses.has(value.status)
  );
}

function isLifecycleAction(
  value: unknown,
): value is ProjectLifecycleActionViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "action",
      "available",
      "targetState",
      "authoritySlot",
      "reasonCode",
      "prerequisites",
    ]) ||
    typeof value.action !== "string" ||
    !projectActions.has(value.action as ProjectControlAction) ||
    typeof value.available !== "boolean" ||
    typeof value.reasonCode !== "string" ||
    !lifecycleReasonCodes.has(value.reasonCode) ||
    !Array.isArray(value.prerequisites) ||
    value.prerequisites.length > 4 ||
    !value.prerequisites.every(isPrerequisite) ||
    !hasUniqueValues(value.prerequisites, (item) => item.key)
  ) {
    return false;
  }
  const action = value.action as ProjectControlAction;
  const target = {
    pause: "on_hold",
    cancel: "cancelled",
    resume: "active",
    complete: "completed",
  }[action];
  return (
    value.targetState === target &&
    (value.authoritySlot === null ||
      isString(value.authoritySlot, 1, 64, keyPattern)) &&
    (value.available
      ? value.reasonCode === "available" && value.authoritySlot !== null
      : value.reasonCode !== "available")
  );
}

export function isProjectControlsResponse(
  value: unknown,
): value is ProjectControlsViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "project",
      "policy",
      "binding",
      "bindingOptions",
      "health",
      "lifecycleActions",
      "permissions",
    ]) ||
    !isRecord(value.project) ||
    !hasExactKeys(value.project, [
      "globalId",
      "businessCode",
      "title",
      "state",
      "version",
      "tenantId",
    ]) ||
    !isUuid(value.project.globalId) ||
    !isString(value.project.businessCode, 1, 64, businessCodePattern) ||
    !isString(value.project.title, 1, 140) ||
    typeof value.project.state !== "string" ||
    !lifecycleStates.has(value.project.state as ProjectLifecycleState) ||
    !isPositiveInteger(value.project.version) ||
    !isString(value.project.tenantId, 1, 128, tenantPattern)
  ) {
    return false;
  }
  const policyIsValid =
    value.policy === null ||
    (isRecord(value.policy) &&
      hasExactKeys(value.policy, [
        "globalId",
        "code",
        "version",
        "snapshotHash",
        "title",
        "healthAssessmentSlot",
      ]) &&
      isUuid(value.policy.globalId) &&
      isString(value.policy.code, 1, 64, businessCodePattern) &&
      isPositiveInteger(value.policy.version) &&
      isString(value.policy.snapshotHash, 64, 64, hashPattern) &&
      isString(value.policy.title, 1, 140) &&
      isString(value.policy.healthAssessmentSlot, 1, 64, keyPattern));
  const bindingIsValid =
    value.binding === null ||
    (isRecord(value.binding) &&
      hasExactKeys(value.binding, ["globalId", "version", "authorities"]) &&
      isUuid(value.binding.globalId) &&
      isPositiveInteger(value.binding.version) &&
      Array.isArray(value.binding.authorities) &&
      value.binding.authorities.length >= 1 &&
      value.binding.authorities.length <= 64 &&
      value.binding.authorities.every(isAuthority) &&
      hasUniqueValues(value.binding.authorities, (item) => item.slot) &&
      hasUniqueValues(
        value.binding.authorities,
        (item) => `${item.slot}:${item.memberGlobalId}`,
      ));
  if (
    !policyIsValid ||
    !bindingIsValid ||
    (value.policy === null) !== (value.binding === null) ||
    !(
      value.bindingOptions === null || isBindingOptions(value.bindingOptions)
    ) ||
    !isRecord(value.health) ||
    !hasExactKeys(value.health, [
      "overallStatus",
      "dimensions",
      "assessment",
    ]) ||
    typeof value.health.overallStatus !== "string" ||
    !healthStatuses.has(value.health.overallStatus as ProjectHealthStatus) ||
    !isCompleteDimensionSet(value.health.dimensions) ||
    !(
      value.health.assessment === null ||
      isAssessmentSummary(value.health.assessment)
    ) ||
    !Array.isArray(value.lifecycleActions) ||
    value.lifecycleActions.length !== projectActions.size ||
    !value.lifecycleActions.every(isLifecycleAction) ||
    !isRecord(value.permissions) ||
    !hasExactKeys(value.permissions, [
      "canBindPolicy",
      "canAssessHealth",
      "canTransition",
    ]) ||
    typeof value.permissions.canBindPolicy !== "boolean" ||
    typeof value.permissions.canAssessHealth !== "boolean" ||
    typeof value.permissions.canTransition !== "boolean"
  ) {
    return false;
  }
  const actionValues =
    value.lifecycleActions as readonly ProjectLifecycleActionViewModel[];
  const bindingAuthorities =
    (value.binding as ProjectControlsViewModel["binding"])?.authorities ?? [];
  if (
    !hasUniqueValues(actionValues, (item) => item.action) ||
    ![...projectActions].every((action) =>
      actionValues.some((item) => item.action === action),
    ) ||
    actionValues.some(
      (action) =>
        action.authoritySlot !== null &&
        !bindingAuthorities.some(
          (authority) => authority.slot === action.authoritySlot,
        ),
    )
  ) {
    return false;
  }
  const dimensionValues = value.health.dimensions;
  const hasRed =
    value.health.overallStatus === "red" ||
    dimensionValues.some((item) => item.status === "red");
  const assessment = value.health.assessment;
  return (
    (assessment !== null || value.health.overallStatus === "unassessed") &&
    (!hasRed || Boolean(assessment?.reason && assessment.recoveryPlan)) &&
    (value.permissions.canBindPolicy
      ? value.bindingOptions !== null
      : value.bindingOptions === null) &&
    value.permissions.canTransition ===
      actionValues.some((action) => action.available) &&
    (value.policy !== null ||
      (!value.permissions.canAssessHealth &&
        !value.permissions.canTransition &&
        actionValues.every((action) => action.reasonCode === "policy_missing")))
  );
}

function isMention(value: unknown): value is ProjectMentionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["memberGlobalId", "userId", "displayName"]) &&
    isUuid(value.memberGlobalId) &&
    isEmail(value.userId) &&
    isString(value.displayName, 1, 140)
  );
}

function isAttachment(
  value: unknown,
): value is ProjectActivityAttachmentViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "version",
      "fileName",
      "mimeType",
      "sizeBytes",
      "sha256",
      "scanState",
    ]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    isString(value.fileName, 1, 255) &&
    isString(value.mimeType, 1, 255) &&
    isNonnegativeInteger(value.sizeBytes) &&
    isString(value.sha256, 64, 64, hashPattern) &&
    value.scanState === "clean"
  );
}

function isObjectTarget(
  value: unknown,
  projectId: string,
): value is ProjectObjectTargetViewModel {
  if (!isRecord(value) || typeof value.kind !== "string") return false;
  if (value.kind === "project" && hasExactKeys(value, ["kind", "projectId"])) {
    return value.projectId === projectId;
  }
  if (
    value.kind === "gate" &&
    hasExactKeys(value, ["kind", "projectId", "gateId"])
  ) {
    return value.projectId === projectId && isUuid(value.gateId);
  }
  if (
    value.kind === "project_work_item" &&
    hasExactKeys(value, ["kind", "projectId", "workItemId"])
  ) {
    return value.projectId === projectId && isUuid(value.workItemId);
  }
  if (
    value.kind === "project_learning" &&
    hasExactKeys(value, ["kind", "projectId", "learningId"])
  ) {
    return value.projectId === projectId && isUuid(value.learningId);
  }
  return false;
}

function isObjectLink(
  value: unknown,
  projectId: string,
): value is ProjectObjectLinkViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "type",
      "globalId",
      "version",
      "code",
      "title",
      "target",
    ]) ||
    typeof value.type !== "string" ||
    !objectLinkTypes.has(value.type as ProjectObjectLinkType) ||
    !isUuid(value.globalId) ||
    !isPositiveInteger(value.version) ||
    !isString(value.code, 1, 64) ||
    !isString(value.title, 1, 280) ||
    !isObjectTarget(value.target, projectId)
  ) {
    return false;
  }
  const target = value.target;
  switch (value.type as ProjectObjectLinkType) {
    case "gate":
      return target.kind === "gate" && target.gateId === value.globalId;
    case "domain_work_item":
      return (
        target.kind === "project_work_item" &&
        target.workItemId === value.globalId
      );
    case "learning":
      return (
        target.kind === "project_learning" &&
        target.learningId === value.globalId
      );
    case "project":
    case "file_revision":
      return target.kind === "project";
  }
}

function isCommentDetail(
  value: unknown,
  projectId: string,
): value is ProjectCommentDetailViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["body", "mentions", "attachments", "objectLinks"]) &&
    isString(value.body, 1, 4000) &&
    Array.isArray(value.mentions) &&
    value.mentions.length <= 50 &&
    value.mentions.every(isMention) &&
    hasUniqueValues(value.mentions, (item) => item.memberGlobalId) &&
    Array.isArray(value.attachments) &&
    value.attachments.length <= 20 &&
    value.attachments.every(isAttachment) &&
    hasUniqueValues(value.attachments, (item) => item.globalId) &&
    Array.isArray(value.objectLinks) &&
    value.objectLinks.length <= 20 &&
    value.objectLinks.every((item) => isObjectLink(item, projectId)) &&
    hasUniqueValues(
      value.objectLinks,
      (item) => `${item.type}:${item.globalId}`,
    )
  );
}

function isHealthEvaluation(
  value: unknown,
): value is ProjectHealthEvaluationViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "policyRef",
      "dimensionResults",
      "overallStatus",
      "reason",
      "recoveryPlan",
    ]) ||
    !isPolicyReference(value.policyRef) ||
    !isCompleteDimensionSet(value.dimensionResults) ||
    typeof value.overallStatus !== "string" ||
    !healthStatuses.has(value.overallStatus as ProjectHealthStatus) ||
    !(value.reason === null || isString(value.reason, 1, 2000)) ||
    !(value.recoveryPlan === null || isString(value.recoveryPlan, 1, 4000))
  ) {
    return false;
  }
  const results = value.dimensionResults;
  return (
    !(
      value.overallStatus === "red" ||
      results.some((item) => item.status === "red")
    ) ||
    (value.reason !== null && value.recoveryPlan !== null)
  );
}

function isActivityItem(
  value: unknown,
  projectId: string,
): value is ProjectActivityItemViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "eventType",
      "actorUserId",
      "occurredAt",
      "detail",
    ]) ||
    !isUuid(value.globalId) ||
    !isFrappeUserId(value.actorUserId) ||
    !isTimestamp(value.occurredAt) ||
    typeof value.eventType !== "string" ||
    !isRecord(value.detail)
  ) {
    return false;
  }
  if (value.eventType === "comment_added") {
    return isCommentDetail(value.detail, projectId);
  }
  if (value.eventType === "followed" || value.eventType === "unfollowed") {
    return (
      hasExactKeys(value.detail, ["active"]) &&
      typeof value.detail.active === "boolean" &&
      value.detail.active === (value.eventType === "followed")
    );
  }
  if (value.eventType === "health_assessed") {
    return (
      hasExactKeys(value.detail, [
        "assessment",
        "policyRef",
        "bindingGlobalId",
        "projectVersion",
      ]) &&
      isHealthEvaluation(value.detail.assessment) &&
      isPolicyReference(value.detail.policyRef) &&
      value.detail.policyRef.globalId ===
        value.detail.assessment.policyRef.globalId &&
      value.detail.policyRef.version ===
        value.detail.assessment.policyRef.version &&
      value.detail.policyRef.snapshotHash ===
        value.detail.assessment.policyRef.snapshotHash &&
      isUuid(value.detail.bindingGlobalId) &&
      isPositiveInteger(value.detail.projectVersion)
    );
  }
  if (value.eventType === "lifecycle_transition") {
    if (
      !hasExactKeys(value.detail, [
        "action",
        "fromState",
        "toState",
        "reason",
        "approvedBy",
        "policyRef",
        "bindingGlobalId",
        "prerequisites",
        "projectVersion",
      ]) ||
      typeof value.detail.action !== "string" ||
      !projectActions.has(value.detail.action as ProjectControlAction) ||
      typeof value.detail.fromState !== "string" ||
      !lifecycleStates.has(value.detail.fromState as ProjectLifecycleState) ||
      typeof value.detail.toState !== "string" ||
      !lifecycleStates.has(value.detail.toState as ProjectLifecycleState) ||
      !isString(value.detail.reason, 1, 2000) ||
      !isAuthority(value.detail.approvedBy) ||
      !isPolicyReference(value.detail.policyRef) ||
      !isUuid(value.detail.bindingGlobalId) ||
      !Array.isArray(value.detail.prerequisites) ||
      value.detail.prerequisites.length > 4 ||
      !value.detail.prerequisites.every(isPrerequisite) ||
      !hasUniqueValues(value.detail.prerequisites, (item) => item.key) ||
      !isPositiveInteger(value.detail.projectVersion)
    ) {
      return false;
    }
    return (
      value.detail.toState ===
      {
        pause: "on_hold",
        cancel: "cancelled",
        resume: "active",
        complete: "completed",
      }[value.detail.action as ProjectControlAction]
    );
  }
  if (value.eventType === "learning_created") {
    return (
      hasExactKeys(value.detail, ["learningGlobalId", "kind", "title"]) &&
      isUuid(value.detail.learningGlobalId) &&
      typeof value.detail.kind === "string" &&
      learningKinds.has(value.detail.kind as ProjectLearningKind) &&
      isString(value.detail.title, 1, 280)
    );
  }
  return false;
}

export function isProjectActivityPageResponse(
  value: unknown,
): value is ProjectActivityPageViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "projectId",
      "items",
      "nextCursor",
      "permissions",
      "following",
      "followerVersion",
      "commentOptions",
    ]) ||
    !isUuid(value.projectId) ||
    !Array.isArray(value.items)
  ) {
    return false;
  }
  const projectId = value.projectId;
  const items = value.items;
  if (
    items.length > 100 ||
    !items.every((item): item is ProjectActivityItemViewModel =>
      isActivityItem(item, projectId),
    ) ||
    !hasUniqueValues(items, (item) => item.globalId) ||
    !isStrictlyDescendingActivity(items) ||
    !(
      value.nextCursor === null ||
      isString(value.nextCursor, 1, 500, cursorPattern)
    ) ||
    (value.nextCursor !== null && items.length === 0)
  ) {
    return false;
  }
  return (
    isRecord(value.permissions) &&
    hasExactKeys(value.permissions, ["canComment", "canFollow"]) &&
    typeof value.permissions.canComment === "boolean" &&
    typeof value.permissions.canFollow === "boolean" &&
    typeof value.following === "boolean" &&
    isNonnegativeInteger(value.followerVersion) &&
    isRecord(value.commentOptions) &&
    hasExactKeys(value.commentOptions, [
      "truncated",
      "mentions",
      "attachments",
      "objectLinks",
    ]) &&
    typeof value.commentOptions.truncated === "boolean" &&
    Array.isArray(value.commentOptions.mentions) &&
    value.commentOptions.mentions.length <= 500 &&
    value.commentOptions.mentions.every(isMention) &&
    hasUniqueValues(
      value.commentOptions.mentions,
      (mention) => mention.memberGlobalId,
    ) &&
    Array.isArray(value.commentOptions.attachments) &&
    value.commentOptions.attachments.length <= 500 &&
    value.commentOptions.attachments.every(isAttachment) &&
    hasUniqueValues(
      value.commentOptions.attachments,
      (attachment) => attachment.globalId,
    ) &&
    Array.isArray(value.commentOptions.objectLinks) &&
    value.commentOptions.objectLinks.length <= 500 &&
    value.commentOptions.objectLinks.every((link) =>
      isObjectLink(link, projectId),
    ) &&
    hasUniqueValues(
      value.commentOptions.objectLinks,
      (link) => `${link.type}:${link.globalId}`,
    )
  );
}

export function mergeProjectActivityPages(
  current: ProjectActivityPageViewModel,
  continuation: ProjectActivityPageViewModel,
): ProjectActivityPageViewModel | null {
  if (current.projectId !== continuation.projectId) return null;
  const itemsById = new Map<string, ProjectActivityItemViewModel>();
  for (const item of [...current.items, ...continuation.items]) {
    const previous = itemsById.get(item.globalId);
    if (
      previous !== undefined &&
      JSON.stringify(previous) !== JSON.stringify(item)
    ) {
      return null;
    }
    itemsById.set(item.globalId, item);
  }
  return {
    ...current,
    items: [...itemsById.values()].sort(compareActivityItems),
    nextCursor: continuation.nextCursor,
  };
}

export function isProjectActivityItemResponse(
  value: unknown,
  projectId: string,
): value is ProjectActivityItemViewModel {
  return isUuid(projectId) && isActivityItem(value, projectId);
}

export function isProjectFollowStateResponse(
  value: unknown,
): value is ProjectFollowStateViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["projectId", "following", "version", "changedAt"]) &&
    isUuid(value.projectId) &&
    typeof value.following === "boolean" &&
    isPositiveInteger(value.version) &&
    isTimestamp(value.changedAt)
  );
}

function isLearning(
  value: unknown,
  expectedProjectId?: string,
): value is ProjectLearningViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "globalId",
      "projectGlobalId",
      "kind",
      "title",
      "content",
      "recommendation",
      "tags",
      "templateRef",
      "createdBy",
      "createdAt",
      "version",
      "target",
    ]) ||
    !isUuid(value.globalId) ||
    !isUuid(value.projectGlobalId) ||
    (expectedProjectId !== undefined &&
      value.projectGlobalId !== expectedProjectId) ||
    typeof value.kind !== "string" ||
    !learningKinds.has(value.kind as ProjectLearningKind) ||
    !isString(value.title, 1, 280) ||
    !isString(value.content, 1, 4000) ||
    !isString(value.recommendation, 0, 4000) ||
    !Array.isArray(value.tags) ||
    value.tags.length > 20 ||
    !value.tags.every((tag) => isString(tag, 1, 64)) ||
    !hasUniqueValues(value.tags, (tag) => tag) ||
    !isPolicyReference(value.templateRef) ||
    !isFrappeUserId(value.createdBy) ||
    !isTimestamp(value.createdAt) ||
    !isPositiveInteger(value.version) ||
    !isObjectTarget(value.target, value.projectGlobalId)
  ) {
    return false;
  }
  return (
    value.target.kind === "project_learning" &&
    value.target.learningId === value.globalId
  );
}

export function isProjectLearningResponse(
  value: unknown,
  expectedProjectId?: string,
): value is ProjectLearningViewModel {
  return isLearning(value, expectedProjectId);
}

export function isProjectLearningPageResponse(
  value: unknown,
): value is ProjectLearningPageViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["projectId", "items", "permissions"]) &&
    isUuid(value.projectId) &&
    Array.isArray(value.items) &&
    value.items.length <= 100 &&
    value.items.every((item) => isLearning(item, value.projectId as string)) &&
    hasUniqueValues(value.items, (item) => item.globalId) &&
    isRecord(value.permissions) &&
    hasExactKeys(value.permissions, ["canCreate"]) &&
    typeof value.permissions.canCreate === "boolean"
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function isCommandContext(value: ProjectCommandContext): boolean {
  return (
    isString(value.csrfToken, 32, 128) &&
    !/[\r\n]/u.test(value.csrfToken) &&
    isString(value.idempotencyKey, 8, 128, idempotencyPattern) &&
    !value.signal.aborted
  );
}

function isReferenceInput(value: ProjectCommentReferenceInput): boolean {
  return isUuid(value.globalId) && isPositiveInteger(value.version);
}

function isHealthMeasurementInput(
  value: ProjectHealthMeasurementInput,
): boolean {
  const numericValid =
    value.numericValue === null ||
    (typeof value.numericValue === "number" &&
      Number.isFinite(value.numericValue)) ||
    isString(value.numericValue, 1, 100, decimalPattern);
  return (
    dimensions.has(value.dimension) &&
    numericValid &&
    (value.manualStatus === null ||
      manualHealthStatuses.has(value.manualStatus)) &&
    !(value.numericValue !== null && value.manualStatus !== null)
  );
}

function isLearningQuery(query: ProjectLearningQuery): boolean {
  const exactTarget =
    query.learningId === undefined ||
    (isUuid(query.learningId) &&
      query.kind === undefined &&
      query.search === undefined);
  return (
    exactTarget &&
    (query.kind === undefined || learningKinds.has(query.kind)) &&
    (query.search === undefined || isString(query.search, 1, 140)) &&
    (query.limit === undefined ||
      (isPositiveInteger(query.limit) && query.limit <= 100))
  );
}

function throwIfCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ProjectControlsRequestCancelledError();
}

export class LiveProjectControlsDataSource implements ProjectControlsDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadControls(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ProjectControlsViewModel> {
    if (!isUuid(projectId)) throw requestNotReady();
    return this.query(
      `/projects/${projectId}/controls`,
      signal,
      {},
      (value): value is ProjectControlsViewModel =>
        isProjectControlsResponse(value) &&
        value.project.globalId === projectId,
    );
  }

  async bindPolicy(
    projectId: string,
    command: BindProjectControlPolicyCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectControlsViewModel> {
    if (
      !isUuid(projectId) ||
      !isPositiveInteger(command.expectedProjectVersion) ||
      !isPolicyReference(command.policyRef) ||
      command.bindings.length < 1 ||
      command.bindings.length > 64 ||
      !command.bindings.every(
        (binding) =>
          isString(binding.slot, 1, 64, keyPattern) &&
          isUuid(binding.memberGlobalId),
      ) ||
      !hasUniqueValues(command.bindings, (binding) => binding.slot)
    ) {
      throw requestNotReady();
    }
    return this.controlsCommand(
      `/projects/${projectId}:bind-control-policy`,
      command,
      context,
      (value): value is ProjectControlsViewModel =>
        isProjectControlsResponse(value) &&
        value.project.globalId === projectId &&
        value.project.version === command.expectedProjectVersion + 1 &&
        value.policy?.globalId === command.policyRef.globalId &&
        value.policy.version === command.policyRef.version &&
        value.policy.snapshotHash === command.policyRef.snapshotHash &&
        value.binding !== null &&
        value.binding.authorities.length === command.bindings.length &&
        command.bindings.every((submitted) =>
          value.binding?.authorities.some(
            (recorded) =>
              recorded.slot === submitted.slot &&
              recorded.memberGlobalId === submitted.memberGlobalId,
          ),
        ),
    );
  }

  async assessHealth(
    projectId: string,
    command: AssessProjectHealthCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectControlsViewModel> {
    if (
      !isUuid(projectId) ||
      !isPositiveInteger(command.expectedProjectVersion) ||
      command.measurements.length > 4 ||
      !command.measurements.every(isHealthMeasurementInput) ||
      !hasUniqueValues(
        command.measurements,
        (measurement) => measurement.dimension,
      ) ||
      !(command.reason === null || isString(command.reason, 1, 2000)) ||
      !(
        command.recoveryPlan === null || isString(command.recoveryPlan, 1, 4000)
      )
    ) {
      throw requestNotReady();
    }
    return this.controlsCommand(
      `/projects/${projectId}:assess-health`,
      command,
      context,
      (value): value is ProjectControlsViewModel =>
        isProjectControlsResponse(value) &&
        value.project.globalId === projectId &&
        value.project.version === command.expectedProjectVersion + 1 &&
        value.health.assessment !== null &&
        value.health.assessment.reason === command.reason &&
        value.health.assessment.recoveryPlan === command.recoveryPlan,
    );
  }

  async transition(
    projectId: string,
    command: TransitionProjectCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectControlsViewModel> {
    if (
      !isUuid(projectId) ||
      !isPositiveInteger(command.expectedProjectVersion) ||
      !projectActions.has(command.action) ||
      !isString(command.reason.trim(), 1, 2000)
    ) {
      throw requestNotReady();
    }
    const expectedState = {
      pause: "on_hold",
      cancel: "cancelled",
      resume: "active",
      complete: "completed",
    }[command.action];
    return this.controlsCommand(
      `/projects/${projectId}:transition`,
      { ...command, reason: command.reason.trim() },
      context,
      (value): value is ProjectControlsViewModel =>
        isProjectControlsResponse(value) &&
        value.project.globalId === projectId &&
        value.project.version === command.expectedProjectVersion + 1 &&
        value.project.state === expectedState,
    );
  }

  async loadActivity(
    projectId: string,
    signal: AbortSignal,
    limit = 50,
    cursor?: string,
  ): Promise<ProjectActivityPageViewModel> {
    if (
      !isUuid(projectId) ||
      !isPositiveInteger(limit) ||
      limit > 100 ||
      (cursor !== undefined && !cursorPattern.test(cursor))
    ) {
      throw requestNotReady();
    }
    const query: Record<string, string> = { limit: String(limit) };
    if (cursor !== undefined) query.cursor = cursor;
    return this.query(
      `/projects/${projectId}/activity`,
      signal,
      query,
      (value): value is ProjectActivityPageViewModel =>
        isProjectActivityPageResponse(value) &&
        value.projectId === projectId &&
        (cursor === undefined || value.nextCursor !== cursor),
    );
  }

  async addComment(
    projectId: string,
    command: AddProjectCommentCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectActivityItemViewModel> {
    const body = command.body.trim();
    if (
      !isUuid(projectId) ||
      !isString(body, 1, 4000) ||
      command.mentions.length > 50 ||
      !command.mentions.every((mention) => isUuid(mention.memberGlobalId)) ||
      !hasUniqueValues(command.mentions, (mention) => mention.memberGlobalId) ||
      command.attachments.length > 20 ||
      !command.attachments.every(isReferenceInput) ||
      !hasUniqueValues(
        command.attachments,
        (attachment) => attachment.globalId,
      ) ||
      command.objectLinks.length > 20 ||
      !command.objectLinks.every(
        (link) => objectLinkTypes.has(link.type) && isReferenceInput(link),
      ) ||
      !hasUniqueValues(
        command.objectLinks,
        (link) => `${link.type}:${link.globalId}`,
      )
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectId}/comments`,
      { ...command, body },
      context,
      (value): value is ProjectActivityItemViewModel =>
        isProjectActivityItemResponse(value, projectId) &&
        value.eventType === "comment_added" &&
        value.detail.body === body &&
        value.detail.mentions.length === command.mentions.length &&
        command.mentions.every((submitted) =>
          value.detail.mentions.some(
            (resolved) => resolved.memberGlobalId === submitted.memberGlobalId,
          ),
        ) &&
        value.detail.attachments.length === command.attachments.length &&
        command.attachments.every((submitted) =>
          value.detail.attachments.some(
            (resolved) =>
              resolved.globalId === submitted.globalId &&
              resolved.version === submitted.version,
          ),
        ) &&
        value.detail.objectLinks.length === command.objectLinks.length &&
        command.objectLinks.every((submitted) =>
          value.detail.objectLinks.some(
            (resolved) =>
              resolved.type === submitted.type &&
              resolved.globalId === submitted.globalId &&
              resolved.version === submitted.version,
          ),
        ),
    );
  }

  async changeFollowing(
    projectId: string,
    following: boolean,
    expectedVersion: number,
    context: ProjectCommandContext,
  ): Promise<ProjectFollowStateViewModel> {
    if (
      !isUuid(projectId) ||
      typeof following !== "boolean" ||
      !isNonnegativeInteger(expectedVersion)
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectId}:${following ? "follow" : "unfollow"}`,
      { expectedVersion },
      context,
      (value): value is ProjectFollowStateViewModel =>
        isProjectFollowStateResponse(value) &&
        value.projectId === projectId &&
        value.following === following &&
        value.version === expectedVersion + 1,
    );
  }

  async loadLearning(
    projectId: string,
    query: ProjectLearningQuery,
    signal: AbortSignal,
  ): Promise<ProjectLearningPageViewModel> {
    if (!isUuid(projectId) || !isLearningQuery(query)) {
      throw requestNotReady();
    }
    const parameters: Record<string, string> = {};
    if (query.kind !== undefined) parameters.kind = query.kind;
    if (query.search !== undefined) parameters.search = query.search;
    if (query.learningId !== undefined) {
      parameters.learningId = query.learningId;
    }
    parameters.limit = String(query.limit ?? 50);
    return this.query(
      `/projects/${projectId}/learning`,
      signal,
      parameters,
      (value): value is ProjectLearningPageViewModel =>
        isProjectLearningPageResponse(value) &&
        value.projectId === projectId &&
        (query.learningId === undefined ||
          (value.items.length === 1 &&
            value.items[0]?.globalId === query.learningId)),
    );
  }

  async createLearning(
    projectId: string,
    command: CreateProjectLearningCommand,
    context: ProjectCommandContext,
  ): Promise<ProjectLearningViewModel> {
    const title = command.title.trim();
    const content = command.content.trim();
    let recommendation: string | null = null;
    if (command.recommendation !== null) {
      const candidate = command.recommendation.trim();
      if (candidate.length > 0) recommendation = candidate;
    }
    const tags = command.tags.map((tag) => tag.trim());
    if (
      !isUuid(projectId) ||
      !learningKinds.has(command.kind) ||
      !isString(title, 1, 280) ||
      !isString(content, 1, 4000) ||
      !(recommendation === null || isString(recommendation, 1, 4000)) ||
      tags.length > 20 ||
      !tags.every((tag) => isString(tag, 1, 64)) ||
      !hasUniqueValues(tags, (tag) => tag)
    ) {
      throw requestNotReady();
    }
    return this.command(
      `/projects/${projectId}/learning`,
      { ...command, title, content, recommendation, tags },
      context,
      (value): value is ProjectLearningViewModel =>
        isProjectLearningResponse(value, projectId) &&
        value.kind === command.kind &&
        value.title === title &&
        value.content === content &&
        value.recommendation === (recommendation ?? "") &&
        value.tags.length === tags.length &&
        value.tags.every((tag, index) => tag === tags[index]),
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

  private async controlsCommand(
    path: string,
    body: object,
    context: ProjectCommandContext,
    validate: (value: unknown) => value is ProjectControlsViewModel,
  ): Promise<ProjectControlsViewModel> {
    return this.command(path, body, context, validate);
  }

  private async command<T>(
    path: string,
    body: object,
    context: ProjectCommandContext,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    if (!isCommandContext(context)) throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<T>(
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
          validate,
        },
      );
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }
}
