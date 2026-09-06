import type { SessionCommandContext } from "../i18n/runtime";
import { NpiHttpClient } from "./http";

export const myWorkGridId = "my-work" as const;
export const myWorkTableSchemaVersion = "my-work-grid-v1" as const;
export const myWorkGridSearchMaximumCodePoints = 140;

export const myWorkGridViewIds = [
  "all",
  "today",
  "overdue",
  "approvals",
  "blockers",
  "waiting",
  "integration",
] as const;

export const myWorkGridColumnIds = [
  "type",
  "item",
  "context",
  "assignment",
  "priority",
  "due",
  "status",
  "action",
] as const;

export type MyWorkGridViewId = (typeof myWorkGridViewIds)[number];
export type MyWorkGridColumnId = (typeof myWorkGridColumnIds)[number];

export interface MyWorkGridColumnWidthSpec {
  readonly default: number;
  readonly maximum: number;
  readonly minimum: number;
}

export const myWorkGridColumnWidthSpecs: Readonly<
  Record<MyWorkGridColumnId, MyWorkGridColumnWidthSpec>
> = Object.freeze({
  type: Object.freeze({ default: 112, maximum: 180, minimum: 88 }),
  item: Object.freeze({ default: 260, maximum: 480, minimum: 180 }),
  context: Object.freeze({ default: 240, maximum: 420, minimum: 160 }),
  assignment: Object.freeze({ default: 180, maximum: 320, minimum: 140 }),
  priority: Object.freeze({ default: 112, maximum: 180, minimum: 96 }),
  due: Object.freeze({ default: 144, maximum: 220, minimum: 120 }),
  status: Object.freeze({ default: 136, maximum: 220, minimum: 112 }),
  action: Object.freeze({ default: 160, maximum: 260, minimum: 120 }),
});

export interface MyWorkGridLayout {
  readonly columnOrder: readonly MyWorkGridColumnId[];
  readonly fixedColumnCount: number;
  readonly hiddenColumnIds: readonly MyWorkGridColumnId[];
  readonly widths: Readonly<Record<MyWorkGridColumnId, number>>;
}

export type MyWorkGridPriority =
  | Readonly<{
      scheme: "domain_severity";
      value: "low" | "medium" | "high" | "critical";
    }>
  | Readonly<{
      scheme: "gate_requirement_priority";
      value: "P0" | "P1" | "P2";
    }>;

export interface MyWorkGridFilter {
  readonly priority: MyWorkGridPriority | null;
  readonly projectId: string | null;
  readonly search: string;
}

export interface MyWorkGridViewPreference {
  readonly filter: MyWorkGridFilter;
  readonly hasSavedFilter: boolean;
  readonly layout: MyWorkGridLayout;
  readonly viewId: MyWorkGridViewId;
}

export interface MyWorkGridCapabilities {
  readonly bulkUnavailableReason: "bulk_action_contract_required";
  readonly canExport: false;
  readonly canPublishSharedView: false;
  readonly canRollbackSharedView: false;
  readonly canRunBulkActions: false;
  readonly exportUnavailableReason: "export_contract_required";
  readonly publishUnavailableReason: "publisher_authority_policy_required";
  readonly rollbackUnavailableReason: "publisher_authority_policy_required";
}

export interface MyWorkGridPreferences {
  readonly capabilities: MyWorkGridCapabilities;
  readonly defaultProjectId: string | null;
  readonly favoriteViewIds: readonly MyWorkGridViewId[];
  readonly gridId: typeof myWorkGridId;
  readonly recentViewIds: readonly MyWorkGridViewId[];
  readonly recoveryReason: "stored_preference_invalid" | null;
  readonly tableSchemaVersion: typeof myWorkTableSchemaVersion;
  readonly version: number;
  readonly viewLayouts: readonly MyWorkGridViewPreference[];
}

export interface SaveMyWorkGridPreference {
  readonly defaultProjectId: string | null;
  readonly expectedVersion: number;
  readonly favoriteViewIds: readonly MyWorkGridViewId[];
  readonly filter: MyWorkGridFilter;
  readonly layout: MyWorkGridLayout;
  readonly recentViewIds: readonly MyWorkGridViewId[];
  readonly saveFilter: boolean;
  readonly tableSchemaVersion: typeof myWorkTableSchemaVersion;
  readonly viewId: MyWorkGridViewId;
}

export interface MyWorkGridPreferencesDataSource {
  load(signal?: AbortSignal): Promise<MyWorkGridPreferences>;
  save(
    command: SaveMyWorkGridPreference,
    session: SessionCommandContext,
    signal?: AbortSignal,
  ): Promise<MyWorkGridPreferences>;
}

export function truncateMyWorkGridSearch(value: string): string {
  return Array.from(value).slice(0, myWorkGridSearchMaximumCodePoints).join("");
}

const endpoint = "/me/preferences/my-work-grid";
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const nilUuid = "00000000-0000-0000-0000-000000000000";
const requiredVisibleColumns = new Set<MyWorkGridColumnId>(["item", "action"]);
const viewIdSet = new Set<MyWorkGridViewId>(myWorkGridViewIds);
const columnIdSet = new Set<MyWorkGridColumnId>(myWorkGridColumnIds);

function hasExactKeys(
  value: Readonly<Record<string, unknown>>,
  keys: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return (
    actual.length === keys.length && keys.every((key) => actual.includes(key))
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isCanonicalUuid(value: unknown): value is string {
  return (
    typeof value === "string" && value !== nilUuid && uuidPattern.test(value)
  );
}

function isClosedUniqueList<T extends string>(
  value: unknown,
  allowed: ReadonlySet<T>,
  maximum: number,
): value is readonly T[] {
  return (
    Array.isArray(value) &&
    value.length <= maximum &&
    value.every((item) => typeof item === "string" && allowed.has(item as T)) &&
    new Set(value).size === value.length
  );
}

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit <= 0x1f || codeUnit === 0x7f) {
      return true;
    }
  }
  return false;
}

function isMyWorkGridPriority(value: unknown): value is MyWorkGridPriority {
  if (!isRecord(value) || !hasExactKeys(value, ["scheme", "value"])) {
    return false;
  }
  if (value.scheme === "domain_severity") {
    return (
      value.value === "low" ||
      value.value === "medium" ||
      value.value === "high" ||
      value.value === "critical"
    );
  }
  return (
    value.scheme === "gate_requirement_priority" &&
    (value.value === "P0" || value.value === "P1" || value.value === "P2")
  );
}

export function isMyWorkGridFilter(value: unknown): value is MyWorkGridFilter {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["projectId", "priority", "search"])
  ) {
    return false;
  }
  const searchIsSafe =
    typeof value.search === "string" &&
    Array.from(value.search).length <= myWorkGridSearchMaximumCodePoints &&
    value.search.trim() === value.search &&
    !hasControlCharacter(value.search);
  return (
    (value.projectId === null || isCanonicalUuid(value.projectId)) &&
    (value.priority === null || isMyWorkGridPriority(value.priority)) &&
    searchIsSafe
  );
}

export function isMyWorkGridLayout(value: unknown): value is MyWorkGridLayout {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "columnOrder",
      "widths",
      "hiddenColumnIds",
      "fixedColumnCount",
    ])
  ) {
    return false;
  }
  const columnOrder = value.columnOrder;
  const widthValues = value.widths;
  const hiddenColumnIds = value.hiddenColumnIds;
  if (
    !isClosedUniqueList<MyWorkGridColumnId>(
      columnOrder,
      columnIdSet,
      myWorkGridColumnIds.length,
    ) ||
    columnOrder.length !== myWorkGridColumnIds.length ||
    !myWorkGridColumnIds.every((columnId) => columnOrder.includes(columnId)) ||
    !isRecord(widthValues) ||
    !hasExactKeys(widthValues, myWorkGridColumnIds) ||
    !isClosedUniqueList<MyWorkGridColumnId>(
      hiddenColumnIds,
      columnIdSet,
      myWorkGridColumnIds.length,
    ) ||
    hiddenColumnIds.some((columnId) => requiredVisibleColumns.has(columnId))
  ) {
    return false;
  }
  const widthsAreValid = myWorkGridColumnIds.every((columnId) => {
    const width = widthValues[columnId];
    const spec = myWorkGridColumnWidthSpecs[columnId];
    return (
      typeof width === "number" &&
      Number.isInteger(width) &&
      width >= spec.minimum &&
      width <= spec.maximum
    );
  });
  const visibleCount = myWorkGridColumnIds.length - hiddenColumnIds.length;
  return (
    widthsAreValid &&
    typeof value.fixedColumnCount === "number" &&
    Number.isInteger(value.fixedColumnCount) &&
    value.fixedColumnCount >= 0 &&
    value.fixedColumnCount <= 2 &&
    value.fixedColumnCount <= visibleCount
  );
}

function isMyWorkGridViewPreference(
  value: unknown,
  expectedViewId: MyWorkGridViewId,
): value is MyWorkGridViewPreference {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["viewId", "layout", "filter", "hasSavedFilter"]) &&
    value.viewId === expectedViewId &&
    isMyWorkGridLayout(value.layout) &&
    isMyWorkGridFilter(value.filter) &&
    typeof value.hasSavedFilter === "boolean" &&
    (value.hasSavedFilter ||
      (value.filter.projectId === null &&
        value.filter.priority === null &&
        value.filter.search === ""))
  );
}

function isCapabilities(value: unknown): value is MyWorkGridCapabilities {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "canPublishSharedView",
      "canRollbackSharedView",
      "canExport",
      "canRunBulkActions",
      "publishUnavailableReason",
      "rollbackUnavailableReason",
      "exportUnavailableReason",
      "bulkUnavailableReason",
    ]) &&
    value.canPublishSharedView === false &&
    value.canRollbackSharedView === false &&
    value.canExport === false &&
    value.canRunBulkActions === false &&
    value.publishUnavailableReason === "publisher_authority_policy_required" &&
    value.rollbackUnavailableReason === "publisher_authority_policy_required" &&
    value.exportUnavailableReason === "export_contract_required" &&
    value.bulkUnavailableReason === "bulk_action_contract_required"
  );
}

export function isMyWorkGridPreferences(
  value: unknown,
): value is MyWorkGridPreferences {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "gridId",
      "tableSchemaVersion",
      "version",
      "viewLayouts",
      "favoriteViewIds",
      "recentViewIds",
      "defaultProjectId",
      "recoveryReason",
      "capabilities",
    ]) ||
    value.gridId !== myWorkGridId ||
    value.tableSchemaVersion !== myWorkTableSchemaVersion ||
    typeof value.version !== "number" ||
    !Number.isInteger(value.version) ||
    value.version < 0 ||
    !Array.isArray(value.viewLayouts) ||
    value.viewLayouts.length !== myWorkGridViewIds.length ||
    !isClosedUniqueList<MyWorkGridViewId>(
      value.favoriteViewIds,
      viewIdSet,
      myWorkGridViewIds.length,
    ) ||
    !isClosedUniqueList<MyWorkGridViewId>(value.recentViewIds, viewIdSet, 5) ||
    (value.defaultProjectId !== null &&
      !isCanonicalUuid(value.defaultProjectId)) ||
    (value.recoveryReason !== null &&
      value.recoveryReason !== "stored_preference_invalid") ||
    !isCapabilities(value.capabilities)
  ) {
    return false;
  }
  const viewLayouts = value.viewLayouts;
  return myWorkGridViewIds.every((viewId, index) =>
    isMyWorkGridViewPreference(viewLayouts[index], viewId),
  );
}

export function defaultMyWorkGridLayout(): MyWorkGridLayout {
  return Object.freeze({
    columnOrder: myWorkGridColumnIds,
    fixedColumnCount: 2,
    hiddenColumnIds: Object.freeze([]),
    widths: Object.freeze(
      Object.fromEntries(
        myWorkGridColumnIds.map((columnId) => [
          columnId,
          myWorkGridColumnWidthSpecs[columnId].default,
        ]),
      ) as Record<MyWorkGridColumnId, number>,
    ),
  });
}

export function defaultMyWorkGridFilter(): MyWorkGridFilter {
  return Object.freeze({ priority: null, projectId: null, search: "" });
}

export function defaultMyWorkGridPreferences(): MyWorkGridPreferences {
  const defaultLayout = defaultMyWorkGridLayout();
  const defaultFilter = defaultMyWorkGridFilter();
  return Object.freeze({
    capabilities: Object.freeze({
      bulkUnavailableReason: "bulk_action_contract_required",
      canExport: false,
      canPublishSharedView: false,
      canRollbackSharedView: false,
      canRunBulkActions: false,
      exportUnavailableReason: "export_contract_required",
      publishUnavailableReason: "publisher_authority_policy_required",
      rollbackUnavailableReason: "publisher_authority_policy_required",
    }),
    defaultProjectId: null,
    favoriteViewIds: Object.freeze([]),
    gridId: myWorkGridId,
    recentViewIds: Object.freeze([]),
    recoveryReason: null,
    tableSchemaVersion: myWorkTableSchemaVersion,
    version: 0,
    viewLayouts: Object.freeze(
      myWorkGridViewIds.map((viewId) =>
        Object.freeze({
          filter: defaultFilter,
          hasSavedFilter: false,
          layout: defaultLayout,
          viewId,
        }),
      ),
    ),
  });
}

export class FrappeMyWorkGridPreferencesDataSource implements MyWorkGridPreferencesDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  load(signal?: AbortSignal): Promise<MyWorkGridPreferences> {
    return this.http.request<MyWorkGridPreferences>(
      endpoint,
      signal ? { signal } : {},
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isMyWorkGridPreferences,
      },
    );
  }

  save(
    command: SaveMyWorkGridPreference,
    session: SessionCommandContext,
    signal?: AbortSignal,
  ): Promise<MyWorkGridPreferences> {
    return this.http.request<MyWorkGridPreferences>(
      endpoint,
      {
        body: JSON.stringify(command),
        method: "PUT",
        ...(signal ? { signal } : {}),
      },
      {
        csrfToken: session.csrfToken,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isMyWorkGridPreferences,
      },
    );
  }
}
