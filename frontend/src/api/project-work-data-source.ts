import { NpiHttpClient, NpiTransportError } from "./http";
import type {
  DomainWorkItemKind,
  DomainWorkItemPageViewModel,
  DomainWorkItemViewModel,
  ProjectDependencyViewModel,
  ProjectMemberViewModel,
  ProjectPlanBaselineComparisonItemViewModel,
  ProjectPlanBaselineComparisonViewModel,
  ProjectPlanBaselineViewModel,
  ProjectRaciAssignmentViewModel,
  ProjectResponsibility,
  ProjectResponsibilityContext,
  ProjectRoleAssignmentViewModel,
  ProjectSubstitutionViewModel,
  ProjectWbsItemViewModel,
  ProjectWorkContextViewModel,
  ProjectWorkPolicyReference,
} from "../domain/view-models";
import { isProjectPolicyLabelSource } from "../generated/project-policy-label-sources";

export interface ProjectWorkContextDataSource {
  load: (
    projectId: string,
    expectedProjectVersion: number,
    signal: AbortSignal,
  ) => Promise<ProjectWorkContextViewModel>;
}

export interface DomainWorkItemQuery {
  workItemId?: string;
  stageId?: string;
  ownerUserId?: string;
  overdue?: boolean;
  kind?: DomainWorkItemKind;
  cursor?: string;
  limit?: number;
}

export interface ProjectDomainWorkItemsDataSource {
  load: (
    projectId: string,
    expectedProjectVersion: number,
    query: DomainWorkItemQuery,
    signal: AbortSignal,
  ) => Promise<DomainWorkItemPageViewModel>;
}

export class ProjectWorkRequestCancelledError extends Error {
  constructor() {
    super("The Project work request was cancelled.");
    this.name = "ProjectWorkRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const utcTimestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/u;
const cursorPattern = /^[A-Za-z0-9._~:-]{1,500}$/u;
const snapshotHashPattern = /^[a-f0-9]{64}$/u;
const emailPattern =
  /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/u;
const keyPattern = /^[a-z][a-z0-9_.-]*$/u;
const businessCodePattern = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/u;
const millisecondsPerUtcDay = 86_400_000;

const responsibilityContexts = new Set<ProjectResponsibilityContext>([
  "project",
  "wbs_item",
  "domain_work_item",
]);
const responsibilities = new Set<ProjectResponsibility>([
  "responsible",
  "accountable",
  "consulted",
  "informed",
]);
const domainWorkItemKinds = new Set<DomainWorkItemKind>([
  "risk",
  "issue",
  "action",
  "decision_request",
]);
const severities = new Set(["low", "medium", "high", "critical"]);

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
  minimum: number,
  maximum: number,
  pattern?: RegExp,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    (!pattern || pattern.test(value))
  );
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isEmail(value: unknown): value is string {
  return isConstrainedString(value, 3, 254) && emailPattern.test(value);
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function isInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value);
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value)
  );
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

function utcTimestampSortKey(value: string): string {
  const match = utcTimestampPattern.exec(value);
  if (!match) return value;
  const [, year, month, day, hour, minute, second, fraction = ""] = match;
  if (!year || !month || !day || !hour || !minute || !second) return value;
  return `${year}-${month}-${day}T${hour}:${minute}:${second}.${fraction.padEnd(6, "0")}Z`;
}

function utcCalendarDayDifference(current: string, baseline: string): number {
  return (
    (Date.parse(`${current}T00:00:00Z`) - Date.parse(`${baseline}T00:00:00Z`)) /
    millisecondsPerUtcDay
  );
}

function isPolicyReference(
  value: unknown,
): value is ProjectWorkPolicyReference {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "version", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version) &&
    typeof value.snapshotHash === "string" &&
    snapshotHashPattern.test(value.snapshotHash)
  );
}

function isProjectSource(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["sourceSystem", "editableIn", "syncState"]) &&
    value.sourceSystem === "NPI_ONE" &&
    value.editableIn === "NPI_ONE" &&
    value.syncState === "local"
  );
}

function isPermissions(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["canView", "canContribute", "canAdminister"]) &&
    value.canView === true &&
    typeof value.canContribute === "boolean" &&
    typeof value.canAdminister === "boolean"
  );
}

function isMember(value: unknown): value is ProjectMemberViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(
      value,
      ["globalId", "projectId", "userId", "effectiveFrom", "version"],
      ["effectiveTo"],
    ) &&
    isUuid(value.globalId) &&
    isUuid(value.projectId) &&
    isEmail(value.userId) &&
    isIsoDate(value.effectiveFrom) &&
    (!Object.hasOwn(value, "effectiveTo") ||
      (isIsoDate(value.effectiveTo) &&
        value.effectiveTo >= value.effectiveFrom)) &&
    isPositiveInteger(value.version)
  );
}

function isRoleAssignment(
  value: unknown,
): value is ProjectRoleAssignmentViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(
      value,
      [
        "globalId",
        "projectId",
        "memberId",
        "roleKey",
        "effectiveFrom",
        "version",
      ],
      ["effectiveTo"],
    ) &&
    isUuid(value.globalId) &&
    isUuid(value.projectId) &&
    isUuid(value.memberId) &&
    isConstrainedString(value.roleKey, 1, 64, keyPattern) &&
    isIsoDate(value.effectiveFrom) &&
    (!Object.hasOwn(value, "effectiveTo") ||
      (isIsoDate(value.effectiveTo) &&
        value.effectiveTo >= value.effectiveFrom)) &&
    isPositiveInteger(value.version)
  );
}

function isSubstitution(value: unknown): value is ProjectSubstitutionViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "projectId",
      "roleAssignmentId",
      "substituteMemberId",
      "effectiveFrom",
      "effectiveTo",
      "version",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.projectId) &&
    isUuid(value.roleAssignmentId) &&
    isUuid(value.substituteMemberId) &&
    isIsoDate(value.effectiveFrom) &&
    isIsoDate(value.effectiveTo) &&
    value.effectiveTo >= value.effectiveFrom &&
    isPositiveInteger(value.version)
  );
}

function isRaciAssignment(
  value: unknown,
): value is ProjectRaciAssignmentViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "projectId",
      "contextType",
      "contextId",
      "responsibilityKey",
      "roleAssignmentId",
      "raci",
      "version",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.projectId) &&
    typeof value.contextType === "string" &&
    responsibilityContexts.has(
      value.contextType as ProjectResponsibilityContext,
    ) &&
    isUuid(value.contextId) &&
    isConstrainedString(value.responsibilityKey, 1, 64, keyPattern) &&
    isUuid(value.roleAssignmentId) &&
    typeof value.raci === "string" &&
    responsibilities.has(value.raci as ProjectResponsibility) &&
    isPositiveInteger(value.version)
  );
}

function isWbsItem(value: unknown): value is ProjectWbsItemViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(
      value,
      [
        "globalId",
        "projectId",
        "code",
        "title",
        "plannedStart",
        "plannedFinish",
        "milestone",
        "statusKey",
        "statusLabelSource",
        "progressPercent",
        "critical",
        "version",
      ],
      ["parentId", "ownerRoleAssignmentId", "actualStart", "actualFinish"],
    ) &&
    isUuid(value.globalId) &&
    isUuid(value.projectId) &&
    isConstrainedString(value.code, 1, 64, businessCodePattern) &&
    isConstrainedString(value.title, 1, 280) &&
    (!Object.hasOwn(value, "parentId") || isUuid(value.parentId)) &&
    (!Object.hasOwn(value, "ownerRoleAssignmentId") ||
      isUuid(value.ownerRoleAssignmentId)) &&
    isIsoDate(value.plannedStart) &&
    isIsoDate(value.plannedFinish) &&
    value.plannedFinish >= value.plannedStart &&
    (!Object.hasOwn(value, "actualStart") || isIsoDate(value.actualStart)) &&
    (!Object.hasOwn(value, "actualFinish") || isIsoDate(value.actualFinish)) &&
    (!isIsoDate(value.actualStart) ||
      !isIsoDate(value.actualFinish) ||
      value.actualFinish >= value.actualStart) &&
    typeof value.milestone === "boolean" &&
    isConstrainedString(value.statusKey, 1, 64, keyPattern) &&
    isProjectPolicyLabelSource(value.statusLabelSource) &&
    isInteger(value.progressPercent) &&
    value.progressPercent >= 0 &&
    value.progressPercent <= 100 &&
    typeof value.critical === "boolean" &&
    isPositiveInteger(value.version)
  );
}

function isDependency(value: unknown): value is ProjectDependencyViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "projectId",
      "predecessorItemId",
      "successorItemId",
      "version",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.projectId) &&
    isUuid(value.predecessorItemId) &&
    isUuid(value.successorItemId) &&
    value.predecessorItemId !== value.successorItemId &&
    isPositiveInteger(value.version)
  );
}

function isBaseline(value: unknown): value is ProjectPlanBaselineViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "projectId",
      "projectVersion",
      "workPolicyRef",
      "label",
      "snapshotHash",
      "capturedAt",
      "capturedBy",
      "version",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.projectId) &&
    isPositiveInteger(value.projectVersion) &&
    isPolicyReference(value.workPolicyRef) &&
    isConstrainedString(value.label, 1, 140) &&
    typeof value.snapshotHash === "string" &&
    snapshotHashPattern.test(value.snapshotHash) &&
    isUtcTimestamp(value.capturedAt) &&
    isConstrainedString(value.capturedBy, 1, 254) &&
    isPositiveInteger(value.version)
  );
}

function isComparisonItem(
  value: unknown,
): value is ProjectPlanBaselineComparisonItemViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "wbsItemId",
      "baselinePlannedStart",
      "baselinePlannedFinish",
      "currentPlannedStart",
      "currentPlannedFinish",
      "startVarianceDays",
      "finishVarianceDays",
      "critical",
    ]) &&
    isUuid(value.wbsItemId) &&
    isIsoDate(value.baselinePlannedStart) &&
    isIsoDate(value.baselinePlannedFinish) &&
    value.baselinePlannedFinish >= value.baselinePlannedStart &&
    isIsoDate(value.currentPlannedStart) &&
    isIsoDate(value.currentPlannedFinish) &&
    value.currentPlannedFinish >= value.currentPlannedStart &&
    isInteger(value.startVarianceDays) &&
    value.startVarianceDays ===
      utcCalendarDayDifference(
        value.currentPlannedStart,
        value.baselinePlannedStart,
      ) &&
    isInteger(value.finishVarianceDays) &&
    value.finishVarianceDays ===
      utcCalendarDayDifference(
        value.currentPlannedFinish,
        value.baselinePlannedFinish,
      ) &&
    typeof value.critical === "boolean"
  );
}

function isComparison(
  value: unknown,
): value is ProjectPlanBaselineComparisonViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "baselineId",
      "baselineProjectVersion",
      "currentProjectVersion",
      "items",
    ]) &&
    isUuid(value.baselineId) &&
    isPositiveInteger(value.baselineProjectVersion) &&
    isPositiveInteger(value.currentProjectVersion) &&
    value.baselineProjectVersion <= value.currentProjectVersion &&
    Array.isArray(value.items) &&
    value.items.length <= 2000 &&
    value.items.every(isComparisonItem)
  );
}

function hasUniqueIds(values: readonly { globalId: string }[]): boolean {
  return new Set(values.map((value) => value.globalId)).size === values.length;
}

function hasAcyclicParents(items: readonly ProjectWbsItemViewModel[]): boolean {
  const parentById = new Map(
    items.map((item) => [item.globalId, item.parentId] as const),
  );
  return items.every((item) => {
    const visited = new Set<string>([item.globalId]);
    let parentId = item.parentId;
    while (parentId) {
      if (visited.has(parentId)) return false;
      visited.add(parentId);
      parentId = parentById.get(parentId);
    }
    return true;
  });
}

function hasAcyclicDependencies(
  items: readonly ProjectWbsItemViewModel[],
  dependencies: readonly ProjectDependencyViewModel[],
): boolean {
  const successors = new Map<string, string[]>();
  for (const dependency of dependencies) {
    const current = successors.get(dependency.predecessorItemId) ?? [];
    current.push(dependency.successorItemId);
    successors.set(dependency.predecessorItemId, current);
  }
  const visiting = new Set<string>();
  const visited = new Set<string>();
  const visit = (itemId: string): boolean => {
    if (visiting.has(itemId)) return false;
    if (visited.has(itemId)) return true;
    visiting.add(itemId);
    for (const successor of successors.get(itemId) ?? []) {
      if (!visit(successor)) return false;
    }
    visiting.delete(itemId);
    visited.add(itemId);
    return true;
  };
  return items.every((item) => visit(item.globalId));
}

export function isProjectWorkContextResponse(
  value: unknown,
): value is ProjectWorkContextViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "projectId",
      "projectVersion",
      "initialized",
      "workPolicyRef",
      "members",
      "roleAssignments",
      "substitutions",
      "raciAssignments",
      "wbsItems",
      "dependencies",
      "baselines",
      "baselineComparison",
      "permissions",
    ]) ||
    !isUuid(value.projectId) ||
    !isPositiveInteger(value.projectVersion) ||
    typeof value.initialized !== "boolean" ||
    !(value.workPolicyRef === null || isPolicyReference(value.workPolicyRef)) ||
    !Array.isArray(value.members) ||
    value.members.length > 500 ||
    !value.members.every(isMember) ||
    !Array.isArray(value.roleAssignments) ||
    value.roleAssignments.length > 1000 ||
    !value.roleAssignments.every(isRoleAssignment) ||
    !Array.isArray(value.substitutions) ||
    value.substitutions.length > 1000 ||
    !value.substitutions.every(isSubstitution) ||
    !Array.isArray(value.raciAssignments) ||
    value.raciAssignments.length > 2000 ||
    !value.raciAssignments.every(isRaciAssignment) ||
    !Array.isArray(value.wbsItems) ||
    value.wbsItems.length > 2000 ||
    !value.wbsItems.every(isWbsItem) ||
    !Array.isArray(value.dependencies) ||
    value.dependencies.length > 5000 ||
    !value.dependencies.every(isDependency) ||
    !Array.isArray(value.baselines) ||
    value.baselines.length > 100 ||
    !value.baselines.every(isBaseline) ||
    !(
      value.baselineComparison === null ||
      isComparison(value.baselineComparison)
    ) ||
    !isPermissions(value.permissions)
  ) {
    return false;
  }

  const projectId = value.projectId;
  const projectVersion = value.projectVersion;
  const initialized = value.initialized;
  const members = value.members as readonly ProjectMemberViewModel[];
  const roleAssignments =
    value.roleAssignments as readonly ProjectRoleAssignmentViewModel[];
  const substitutions =
    value.substitutions as readonly ProjectSubstitutionViewModel[];
  const raciAssignments =
    value.raciAssignments as readonly ProjectRaciAssignmentViewModel[];
  const wbsItems = value.wbsItems as readonly ProjectWbsItemViewModel[];
  const dependencies =
    value.dependencies as readonly ProjectDependencyViewModel[];
  const baselines = value.baselines as readonly ProjectPlanBaselineViewModel[];
  const comparison = value.baselineComparison;

  if (
    !initialized &&
    (value.workPolicyRef !== null ||
      members.length > 0 ||
      roleAssignments.length > 0 ||
      substitutions.length > 0 ||
      raciAssignments.length > 0 ||
      wbsItems.length > 0 ||
      dependencies.length > 0 ||
      baselines.length > 0 ||
      comparison !== null)
  ) {
    return false;
  }
  if (initialized && value.workPolicyRef === null) return false;
  if (
    !hasUniqueIds(members) ||
    !hasUniqueIds(roleAssignments) ||
    !hasUniqueIds(substitutions) ||
    !hasUniqueIds(raciAssignments) ||
    !hasUniqueIds(wbsItems) ||
    !hasUniqueIds(dependencies) ||
    !hasUniqueIds(baselines)
  ) {
    return false;
  }

  const memberIds = new Set(members.map((member) => member.globalId));
  const roleIds = new Set(
    roleAssignments.map((assignment) => assignment.globalId),
  );
  const wbsById = new Map(wbsItems.map((item) => [item.globalId, item]));
  const baselineById = new Map(
    baselines.map((baseline) => [baseline.globalId, baseline]),
  );
  const allProjectRecords = [
    ...members,
    ...roleAssignments,
    ...substitutions,
    ...raciAssignments,
    ...wbsItems,
    ...dependencies,
    ...baselines,
  ];
  if (allProjectRecords.some((record) => record.projectId !== projectId)) {
    return false;
  }
  if (
    baselines.some((baseline) => baseline.projectVersion > projectVersion) ||
    roleAssignments.some((assignment) => !memberIds.has(assignment.memberId)) ||
    substitutions.some(
      (substitution) =>
        !roleIds.has(substitution.roleAssignmentId) ||
        !memberIds.has(substitution.substituteMemberId),
    ) ||
    raciAssignments.some(
      (assignment) =>
        !roleIds.has(assignment.roleAssignmentId) ||
        (assignment.contextType === "project" &&
          assignment.contextId !== projectId) ||
        (assignment.contextType === "wbs_item" &&
          !wbsById.has(assignment.contextId)),
    ) ||
    wbsItems.some(
      (item) =>
        (item.parentId !== undefined && !wbsById.has(item.parentId)) ||
        (item.ownerRoleAssignmentId !== undefined &&
          !roleIds.has(item.ownerRoleAssignmentId)),
    ) ||
    !hasAcyclicParents(wbsItems)
  ) {
    return false;
  }

  const dependencyEdges = new Set<string>();
  for (const dependency of dependencies) {
    const edge = `${dependency.predecessorItemId}:${dependency.successorItemId}`;
    if (
      !wbsById.has(dependency.predecessorItemId) ||
      !wbsById.has(dependency.successorItemId) ||
      dependencyEdges.has(edge)
    ) {
      return false;
    }
    dependencyEdges.add(edge);
  }
  if (!hasAcyclicDependencies(wbsItems, dependencies)) return false;

  if (comparison) {
    const baseline = baselineById.get(comparison.baselineId);
    if (
      comparison.baselineProjectVersion !== baseline?.projectVersion ||
      comparison.currentProjectVersion !== projectVersion ||
      new Set(comparison.items.map((item) => item.wbsItemId)).size !==
        comparison.items.length ||
      comparison.items.some((item) => {
        const wbsItem = wbsById.get(item.wbsItemId);
        return (
          item.currentPlannedStart !== wbsItem?.plannedStart ||
          item.currentPlannedFinish !== wbsItem.plannedFinish ||
          item.critical !== wbsItem.critical
        );
      })
    ) {
      return false;
    }
  }
  return true;
}

function isDomainWorkItem(value: unknown): value is DomainWorkItemViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(
      value,
      [
        "globalId",
        "projectId",
        "kind",
        "title",
        "context",
        "ownerUserId",
        "dueAt",
        "severity",
        "blocking",
        "relatedWorkItemIds",
        "workPolicyRef",
        "stateKey",
        "stateLabelSource",
        "overdue",
        "version",
        "createdAt",
        "lastChangedAt",
        "source",
      ],
      ["detail"],
    ) ||
    !isUuid(value.globalId) ||
    !isUuid(value.projectId) ||
    typeof value.kind !== "string" ||
    !domainWorkItemKinds.has(value.kind as DomainWorkItemKind) ||
    !isConstrainedString(value.title, 1, 280) ||
    (Object.hasOwn(value, "detail") &&
      !isConstrainedString(value.detail, 0, 4000)) ||
    !isRecord(value.context) ||
    !hasExactKeys(value.context, ["projectId"], ["stageId", "wbsItemId"]) ||
    !isUuid(value.context.projectId) ||
    (Object.hasOwn(value.context, "stageId") &&
      !isUuid(value.context.stageId)) ||
    (Object.hasOwn(value.context, "wbsItemId") &&
      !isUuid(value.context.wbsItemId)) ||
    !isEmail(value.ownerUserId) ||
    !isUtcTimestamp(value.dueAt) ||
    typeof value.severity !== "string" ||
    !severities.has(value.severity) ||
    typeof value.blocking !== "boolean" ||
    !Array.isArray(value.relatedWorkItemIds) ||
    value.relatedWorkItemIds.length > 100 ||
    !value.relatedWorkItemIds.every(isUuid) ||
    new Set(value.relatedWorkItemIds).size !==
      value.relatedWorkItemIds.length ||
    value.relatedWorkItemIds.includes(value.globalId) ||
    !isPolicyReference(value.workPolicyRef) ||
    !isConstrainedString(value.stateKey, 1, 64, keyPattern) ||
    !isProjectPolicyLabelSource(value.stateLabelSource) ||
    typeof value.overdue !== "boolean" ||
    !isPositiveInteger(value.version) ||
    !isUtcTimestamp(value.createdAt) ||
    !isUtcTimestamp(value.lastChangedAt) ||
    utcTimestampSortKey(value.lastChangedAt) <
      utcTimestampSortKey(value.createdAt) ||
    !isProjectSource(value.source)
  ) {
    return false;
  }
  return value.context.projectId === value.projectId;
}

export function isDomainWorkItemPageResponse(
  value: unknown,
): value is DomainWorkItemPageViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "projectId",
      "projectVersion",
      "items",
      "nextCursor",
    ]) ||
    !isUuid(value.projectId) ||
    !isPositiveInteger(value.projectVersion) ||
    !Array.isArray(value.items) ||
    value.items.length > 100 ||
    !value.items.every(isDomainWorkItem) ||
    !(
      value.nextCursor === null ||
      isConstrainedString(value.nextCursor, 1, 500, cursorPattern)
    )
  ) {
    return false;
  }
  const projectId = value.projectId;
  const items = value.items as readonly DomainWorkItemViewModel[];
  return (
    hasUniqueIds(items) &&
    items.every((item) => item.projectId === projectId) &&
    items.every((item, index) => {
      const previous = items[index - 1];
      const previousDueAt = previous
        ? utcTimestampSortKey(previous.dueAt)
        : undefined;
      const dueAt = utcTimestampSortKey(item.dueAt);
      return (
        !previous ||
        (previousDueAt !== undefined && previousDueAt < dueAt) ||
        (previousDueAt === dueAt &&
          previous.globalId.localeCompare(item.globalId) < 0)
      );
    })
  );
}

function clientReference(): string {
  return `client-${globalThis.crypto.randomUUID()}`;
}

function isDomainWorkItemQuery(query: DomainWorkItemQuery): boolean {
  const exactTarget =
    query.workItemId === undefined ||
    (isUuid(query.workItemId) &&
      query.stageId === undefined &&
      query.ownerUserId === undefined &&
      query.overdue === undefined &&
      query.kind === undefined &&
      query.cursor === undefined);
  return (
    exactTarget &&
    (query.stageId === undefined || isUuid(query.stageId)) &&
    (query.ownerUserId === undefined || isEmail(query.ownerUserId)) &&
    (query.overdue === undefined || typeof query.overdue === "boolean") &&
    (query.kind === undefined || domainWorkItemKinds.has(query.kind)) &&
    (query.cursor === undefined ||
      isConstrainedString(query.cursor, 1, 500, cursorPattern)) &&
    (query.limit === undefined ||
      (isPositiveInteger(query.limit) && query.limit <= 100))
  );
}

function domainWorkItemQueryParameters(
  query: DomainWorkItemQuery,
): Readonly<Record<string, string>> {
  const parameters: Record<string, string> = {};
  if (query.workItemId !== undefined) parameters.workItemId = query.workItemId;
  if (query.stageId !== undefined) parameters.stageId = query.stageId;
  if (query.ownerUserId !== undefined)
    parameters.ownerUserId = query.ownerUserId.toLowerCase();
  if (query.overdue !== undefined)
    parameters.overdue = query.overdue ? "true" : "false";
  if (query.kind !== undefined) parameters.kind = query.kind;
  if (query.cursor !== undefined) parameters.cursor = query.cursor;
  if (query.limit !== undefined) parameters.limit = String(query.limit);
  return parameters;
}

function matchesDomainWorkItemQuery(
  page: DomainWorkItemPageViewModel,
  projectId: string,
  expectedProjectVersion: number,
  query: DomainWorkItemQuery,
): boolean {
  return (
    page.projectId === projectId &&
    page.projectVersion === expectedProjectVersion &&
    (query.limit === undefined || page.items.length <= query.limit) &&
    (query.workItemId === undefined ||
      (page.items.length === 1 &&
        page.items[0]?.globalId === query.workItemId &&
        page.nextCursor === null)) &&
    page.items.every(
      (item) =>
        (query.stageId === undefined ||
          item.context.stageId === query.stageId) &&
        (query.ownerUserId === undefined ||
          item.ownerUserId.toLowerCase() === query.ownerUserId.toLowerCase()) &&
        (query.overdue === undefined || item.overdue === query.overdue) &&
        (query.kind === undefined || item.kind === query.kind),
    )
  );
}

export class LiveProjectWorkContextDataSource implements ProjectWorkContextDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async load(
    projectId: string,
    expectedProjectVersion: number,
    signal: AbortSignal,
  ): Promise<ProjectWorkContextViewModel> {
    if (!isUuid(projectId) || !isPositiveInteger(expectedProjectVersion)) {
      throw new NpiTransportError(
        "request_not_ready",
        clientReference(),
        "client",
      );
    }
    try {
      return await this.http.request<ProjectWorkContextViewModel>(
        `/projects/${projectId}/work-context`,
        { signal },
        {
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ProjectWorkContextViewModel =>
            isProjectWorkContextResponse(value) &&
            value.projectId === projectId &&
            value.projectVersion === expectedProjectVersion,
        },
      );
    } catch (error) {
      if (signal.aborted) throw new ProjectWorkRequestCancelledError();
      throw error;
    }
  }
}

export class LiveProjectDomainWorkItemsDataSource implements ProjectDomainWorkItemsDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async load(
    projectId: string,
    expectedProjectVersion: number,
    query: DomainWorkItemQuery,
    signal: AbortSignal,
  ): Promise<DomainWorkItemPageViewModel> {
    if (
      !isUuid(projectId) ||
      !isPositiveInteger(expectedProjectVersion) ||
      !isDomainWorkItemQuery(query)
    ) {
      throw new NpiTransportError(
        "request_not_ready",
        clientReference(),
        "client",
      );
    }
    try {
      return await this.http.request<DomainWorkItemPageViewModel>(
        `/projects/${projectId}/domain-work-items`,
        { signal },
        {
          query: domainWorkItemQueryParameters(query),
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is DomainWorkItemPageViewModel =>
            isDomainWorkItemPageResponse(value) &&
            matchesDomainWorkItemQuery(
              value,
              projectId,
              expectedProjectVersion,
              query,
            ),
        },
      );
    } catch (error) {
      if (signal.aborted) throw new ProjectWorkRequestCancelledError();
      throw error;
    }
  }
}
