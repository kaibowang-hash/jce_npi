import { NpiHttpClient, NpiTransportError } from "./http";
import type {
  MyWorkAction,
  MyWorkCategory,
  MyWorkCountsViewModel,
  MyWorkDueState,
  MyWorkItemViewModel,
  MyWorkPageViewModel,
  MyWorkPriorityViewModel,
  MyWorkProjectViewModel,
  MyWorkSourceType,
  MyWorkStatus,
  MyWorkWhy,
  SourceStatus,
  SourceSystem,
  SyncState,
} from "../domain/view-models";

export type MyWorkView =
  | "all"
  | "today"
  | "overdue"
  | "approvals"
  | "blockers"
  | "waiting"
  | "integration";

export interface MyWorkQuery {
  view: MyWorkView;
  projectId?: string;
  priority?: MyWorkPriorityViewModel;
  search?: string;
  cursor?: string;
  limit?: number;
}

export interface MyWorkDataSource {
  load: (
    query: MyWorkQuery,
    signal: AbortSignal,
  ) => Promise<MyWorkPageViewModel>;
}

export class MyWorkRequestCancelledError extends Error {
  constructor() {
    super("The My Work request was cancelled.");
    this.name = "MyWorkRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const utcTimestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/u;
const cursorPattern = /^[A-Za-z0-9._~:-]{1,500}$/u;

const views = new Set<MyWorkView>([
  "all",
  "today",
  "overdue",
  "approvals",
  "blockers",
  "waiting",
  "integration",
]);
const categories = new Set<MyWorkCategory>([
  "task",
  "approval",
  "blocker",
  "risk",
  "issue",
  "decision",
]);
const domainCategories = new Set<MyWorkCategory>([
  "task",
  "risk",
  "issue",
  "decision",
]);
const sourceTypes = new Set<MyWorkSourceType>([
  "domain_work_item",
  "gate_review_assignment",
  "gate_review_invalidation",
]);
const whyCodes = new Set<MyWorkWhy>([
  "domain_work_item_owner",
  "gate_review_step",
  "gate_final_decision",
  "gate_reopen",
  "gate_exception",
  "gate_dependency_change",
]);
const statuses = new Set<MyWorkStatus>([
  "ready",
  "waiting",
  "blocked",
  "in_review",
]);
const dueStates = new Set<MyWorkDueState>([
  "overdue",
  "today",
  "upcoming",
  "unscheduled",
]);
const actions = new Set<MyWorkAction>(["view_work_item", "open_gate_review"]);
const domainSeverityValues = new Set(["low", "medium", "high", "critical"]);
const gatePriorityValues = new Set(["P0", "P1", "P2"]);
const sourceSystems = new Set<SourceSystem>(["NPI_ONE", "ERPNEXT", "COMPUTED"]);
const editableSystems = new Set<SourceStatus["editableIn"]>([
  "NPI_ONE",
  "ERPNEXT",
  "NONE",
]);
const syncStates = new Set<SyncState>([
  "local",
  "pending",
  "processing",
  "synced",
  "partial",
  "failed_retryable",
  "failed_final",
  "stale",
  "conflict",
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
  minimum: number,
  maximum: number,
): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum
  );
}

function isBusinessString(value: unknown, maximum: number): value is string {
  return isConstrainedString(value, 1, maximum) && value.trim().length > 0;
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isUtcTimestamp(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match = utcTimestampPattern.exec(value);
  if (!match) return false;
  const [, year, month, day, hour, minute, second] = match.map(Number);
  const parsed = new Date(value);
  return (
    !Number.isNaN(parsed.valueOf()) &&
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() + 1 === month &&
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

function isTimeZone(value: unknown): value is string {
  if (!isConstrainedString(value, 1, 64)) return false;
  try {
    new Intl.DateTimeFormat("en", { timeZone: value }).format(new Date(0));
    return true;
  } catch {
    return false;
  }
}

function localDateKey(timestamp: string, timeZone: string): string | null {
  try {
    const parts = new Intl.DateTimeFormat("en", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(new Date(timestamp));
    const part = (type: Intl.DateTimeFormatPartTypes): string | undefined =>
      parts.find((candidate) => candidate.type === type)?.value;
    const year = part("year");
    const month = part("month");
    const day = part("day");
    return year && month && day ? `${year}-${month}-${day}` : null;
  } catch {
    return null;
  }
}

function isPriority(value: unknown): value is MyWorkPriorityViewModel {
  if (!isRecord(value) || !hasExactKeys(value, ["scheme", "value"])) {
    return false;
  }
  return (
    (value.scheme === "domain_severity" &&
      typeof value.value === "string" &&
      domainSeverityValues.has(value.value)) ||
    (value.scheme === "gate_requirement_priority" &&
      typeof value.value === "string" &&
      gatePriorityValues.has(value.value))
  );
}

function isProject(value: unknown): value is MyWorkProjectViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "businessCode", "title"]) &&
    isUuid(value.globalId) &&
    isBusinessString(value.businessCode, 64) &&
    isBusinessString(value.title, 280)
  );
}

function isContext(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["type", "globalId", "code", "title"]) &&
    (value.type === "domain_work_item" || value.type === "gate") &&
    isUuid(value.globalId) &&
    isBusinessString(value.code, 64) &&
    isBusinessString(value.title, 280)
  );
}

function isSource(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["type", "globalId", "version"]) &&
    typeof value.type === "string" &&
    sourceTypes.has(value.type as MyWorkSourceType) &&
    isUuid(value.globalId) &&
    isPositiveInteger(value.version)
  );
}

function isTarget(value: unknown): boolean {
  if (!isRecord(value) || typeof value.kind !== "string") return false;
  if (value.kind === "my_work_item") {
    return (
      hasExactKeys(value, ["kind", "workItemId"]) && isUuid(value.workItemId)
    );
  }
  if (value.kind === "gate_review") {
    return (
      hasExactKeys(value, ["kind", "projectId", "gateId"]) &&
      isUuid(value.projectId) &&
      isUuid(value.gateId)
    );
  }
  return false;
}

function isSourceStatus(value: unknown): value is SourceStatus {
  if (
    !isRecord(value) ||
    !hasExactKeys(
      value,
      ["sourceSystem", "editableIn", "syncState"],
      ["lastSyncedAt", "externalReference"],
    ) ||
    typeof value.sourceSystem !== "string" ||
    !sourceSystems.has(value.sourceSystem as SourceSystem) ||
    typeof value.editableIn !== "string" ||
    !editableSystems.has(value.editableIn as SourceStatus["editableIn"]) ||
    typeof value.syncState !== "string" ||
    !syncStates.has(value.syncState as SyncState)
  ) {
    return false;
  }
  return (
    (!Object.hasOwn(value, "lastSyncedAt") ||
      isUtcTimestamp(value.lastSyncedAt)) &&
    (!Object.hasOwn(value, "externalReference") ||
      isBusinessString(value.externalReference, 2048))
  );
}

function hasConsistentItemIdentity(item: MyWorkItemViewModel): boolean {
  if (item.source.type === "domain_work_item") {
    return (
      item.context.type === "domain_work_item" &&
      item.context.globalId === item.source.globalId &&
      item.target.kind === "my_work_item" &&
      item.target.workItemId === item.source.globalId &&
      item.action === "view_work_item" &&
      item.why === "domain_work_item_owner" &&
      domainCategories.has(item.category) &&
      (item.priority === null || item.priority.scheme === "domain_severity")
    );
  }

  if (
    item.context.type !== "gate" ||
    item.context.globalId !== item.source.globalId ||
    item.target.kind !== "gate_review" ||
    item.target.projectId !== item.project.globalId ||
    item.target.gateId !== item.source.globalId ||
    item.action !== "open_gate_review" ||
    item.why === "domain_work_item_owner" ||
    (item.priority !== null &&
      item.priority.scheme !== "gate_requirement_priority")
  ) {
    return false;
  }

  return item.source.type === "gate_review_invalidation"
    ? item.category === "blocker" &&
        item.blocking &&
        item.why === "gate_dependency_change"
    : item.category === "approval" && item.why !== "gate_dependency_change";
}

function isMyWorkItem(value: unknown): value is MyWorkItemViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "id",
      "category",
      "title",
      "project",
      "context",
      "source",
      "why",
      "status",
      "dueAt",
      "dueState",
      "priority",
      "blocking",
      "action",
      "target",
      "sourceStatus",
    ]) ||
    !isUuid(value.id) ||
    typeof value.category !== "string" ||
    !categories.has(value.category as MyWorkCategory) ||
    !isBusinessString(value.title, 280) ||
    !isProject(value.project) ||
    !isContext(value.context) ||
    !isSource(value.source) ||
    typeof value.why !== "string" ||
    !whyCodes.has(value.why as MyWorkWhy) ||
    typeof value.status !== "string" ||
    !statuses.has(value.status as MyWorkStatus) ||
    !(value.dueAt === null || isUtcTimestamp(value.dueAt)) ||
    typeof value.dueState !== "string" ||
    !dueStates.has(value.dueState as MyWorkDueState) ||
    (value.dueState === "unscheduled") !== (value.dueAt === null) ||
    !(value.priority === null || isPriority(value.priority)) ||
    typeof value.blocking !== "boolean" ||
    typeof value.action !== "string" ||
    !actions.has(value.action as MyWorkAction) ||
    !isTarget(value.target) ||
    !isSourceStatus(value.sourceStatus)
  ) {
    return false;
  }
  return hasConsistentItemIdentity(value as unknown as MyWorkItemViewModel);
}

function isAvailableCount(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["availability", "value"]) &&
    value.availability === "available" &&
    isNonnegativeInteger(value.value)
  );
}

function isUnavailableCount(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["availability", "reason"]) &&
    value.availability === "unavailable" &&
    value.reason === "source_not_available"
  );
}

function isCounts(value: unknown): value is MyWorkCountsViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "all",
      "today",
      "overdue",
      "approvals",
      "blockers",
      "waiting",
      "integration",
    ]) ||
    !isAvailableCount(value.all) ||
    !isAvailableCount(value.today) ||
    !isAvailableCount(value.overdue) ||
    !isAvailableCount(value.approvals) ||
    !isAvailableCount(value.blockers) ||
    !isAvailableCount(value.waiting) ||
    !isUnavailableCount(value.integration)
  ) {
    return false;
  }
  const counts = value as unknown as MyWorkCountsViewModel;
  return [
    counts.today.value,
    counts.overdue.value,
    counts.approvals.value,
    counts.blockers.value,
    counts.waiting.value,
  ].every((count) => count <= counts.all.value);
}

function compareItems(
  left: MyWorkItemViewModel,
  right: MyWorkItemViewModel,
): number {
  if (left.dueAt === null && right.dueAt !== null) return 1;
  if (left.dueAt !== null && right.dueAt === null) return -1;
  if (left.dueAt !== null && right.dueAt !== null) {
    const dueComparison = utcTimestampSortKey(left.dueAt).localeCompare(
      utcTimestampSortKey(right.dueAt),
    );
    if (dueComparison !== 0) return dueComparison;
  }
  return left.id.localeCompare(right.id);
}

function expectedDueState(
  item: MyWorkItemViewModel,
  asOf: string,
  timeZone: string,
): MyWorkDueState | null {
  if (item.dueAt === null) return "unscheduled";
  if (utcTimestampSortKey(item.dueAt) < utcTimestampSortKey(asOf)) {
    return "overdue";
  }
  const dueDate = localDateKey(item.dueAt, timeZone);
  const asOfDate = localDateKey(asOf, timeZone);
  if (dueDate === null || asOfDate === null) return null;
  return dueDate === asOfDate ? "today" : "upcoming";
}

export function isMyWorkPageResponse(
  value: unknown,
): value is MyWorkPageViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "asOf",
      "timeZone",
      "projectOptions",
      "items",
      "nextCursor",
      "counts",
    ]) ||
    !isUtcTimestamp(value.asOf) ||
    !isTimeZone(value.timeZone) ||
    !Array.isArray(value.projectOptions) ||
    value.projectOptions.length > 2000 ||
    !value.projectOptions.every(isProject) ||
    !Array.isArray(value.items) ||
    value.items.length > 100 ||
    !value.items.every(isMyWorkItem) ||
    !(
      value.nextCursor === null ||
      (isConstrainedString(value.nextCursor, 1, 500) &&
        cursorPattern.test(value.nextCursor))
    ) ||
    !isCounts(value.counts)
  ) {
    return false;
  }

  const items = value.items as readonly MyWorkItemViewModel[];
  const projectOptions =
    value.projectOptions as readonly MyWorkProjectViewModel[];
  const projectsById = new Map(
    projectOptions.map((project) => [project.globalId, project]),
  );
  const counts = value.counts;
  const asOf = value.asOf;
  const timeZone = value.timeZone;
  return (
    projectsById.size === projectOptions.length &&
    new Set(items.map((item) => item.id)).size === items.length &&
    items.every((item) => {
      const project = projectsById.get(item.project.globalId);
      return (
        project?.businessCode === item.project.businessCode &&
        project.title === item.project.title
      );
    }) &&
    items.every(
      (item) => item.dueState === expectedDueState(item, asOf, timeZone),
    ) &&
    items.every((item, index) => {
      const previous = items[index - 1];
      return previous === undefined || compareItems(previous, item) < 0;
    }) &&
    counts.all.value >= items.length &&
    (value.nextCursor === null || items.length > 0)
  );
}

function isMyWorkQuery(value: unknown): value is MyWorkQuery {
  if (
    !isRecord(value) ||
    !hasExactKeys(
      value,
      ["view"],
      ["projectId", "priority", "search", "cursor", "limit"],
    ) ||
    typeof value.view !== "string" ||
    !views.has(value.view as MyWorkView)
  ) {
    return false;
  }
  return (
    (!Object.hasOwn(value, "projectId") || isUuid(value.projectId)) &&
    (!Object.hasOwn(value, "priority") || isPriority(value.priority)) &&
    (!Object.hasOwn(value, "search") ||
      isConstrainedString(value.search, 0, 140)) &&
    (!Object.hasOwn(value, "cursor") ||
      (isConstrainedString(value.cursor, 1, 500) &&
        cursorPattern.test(value.cursor))) &&
    (!Object.hasOwn(value, "limit") ||
      (isPositiveInteger(value.limit) && value.limit <= 100))
  );
}

function queryParameters(query: MyWorkQuery): Readonly<Record<string, string>> {
  const parameters: Record<string, string> = { view: query.view };
  if (query.projectId !== undefined) parameters.projectId = query.projectId;
  if (query.priority !== undefined) {
    parameters.priorityScheme = query.priority.scheme;
    parameters.priorityValue = query.priority.value;
  }
  if (query.search !== undefined) parameters.search = query.search;
  if (query.cursor !== undefined) parameters.cursor = query.cursor;
  if (query.limit !== undefined) parameters.limit = String(query.limit);
  return parameters;
}

function matchesView(
  item: MyWorkItemViewModel,
  page: MyWorkPageViewModel,
  view: MyWorkView,
): boolean {
  if (view === "all") return true;
  if (view === "today") {
    if (item.dueAt === null) return false;
    const dueDate = localDateKey(item.dueAt, page.timeZone);
    const asOfDate = localDateKey(page.asOf, page.timeZone);
    return dueDate !== null && dueDate === asOfDate;
  }
  if (view === "overdue") {
    return (
      item.dueAt !== null &&
      utcTimestampSortKey(item.dueAt) < utcTimestampSortKey(page.asOf)
    );
  }
  if (view === "approvals") return item.category === "approval";
  if (view === "blockers") return item.blocking;
  if (view === "waiting") return item.status === "waiting";
  return false;
}

function selectedCount(
  counts: MyWorkCountsViewModel,
  view: MyWorkView,
): number | null {
  if (view === "all") return counts.all.value;
  if (view === "today") return counts.today.value;
  if (view === "overdue") return counts.overdue.value;
  if (view === "approvals") return counts.approvals.value;
  if (view === "blockers") return counts.blockers.value;
  if (view === "waiting") return counts.waiting.value;
  return null;
}

function matchesQuery(page: MyWorkPageViewModel, query: MyWorkQuery): boolean {
  const count = selectedCount(page.counts, query.view);
  return (
    page.items.length <= (query.limit ?? 100) &&
    (query.cursor === undefined || page.nextCursor !== query.cursor) &&
    (count === null ? page.items.length === 0 : count >= page.items.length) &&
    page.items.every(
      (item) =>
        (query.projectId === undefined ||
          item.project.globalId === query.projectId) &&
        (query.priority === undefined ||
          (item.priority?.scheme === query.priority.scheme &&
            item.priority.value === query.priority.value)) &&
        matchesView(item, page, query.view),
    )
  );
}

function clientReference(): string {
  return `client-${globalThis.crypto.randomUUID()}`;
}

function throwIfRequestWasCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new MyWorkRequestCancelledError();
}

export class LiveMyWorkDataSource implements MyWorkDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async load(
    query: MyWorkQuery,
    signal: AbortSignal,
  ): Promise<MyWorkPageViewModel> {
    throwIfRequestWasCancelled(signal);
    if (!isMyWorkQuery(query)) {
      throw new NpiTransportError(
        "request_not_ready",
        clientReference(),
        "client",
      );
    }

    try {
      return await this.http.request<MyWorkPageViewModel>(
        "/me/work",
        { method: "GET", signal },
        {
          query: queryParameters(query),
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is MyWorkPageViewModel =>
            isMyWorkPageResponse(value) && matchesQuery(value, query),
        },
      );
    } catch (error) {
      throwIfRequestWasCancelled(signal);
      throw error;
    }
  }
}
