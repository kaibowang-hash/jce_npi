import { NpiHttpClient, NpiTransportError } from "./http";
import {
  ToolingRequestCancelledError,
  type ToolingCommandContext,
} from "./tooling-data-source";

export const toolingListViewIds = [
  "all",
  "missing_applicability",
  "single_part",
  "shared_parts",
  "missing_physical_set",
  "single_physical_set",
  "multiple_physical_sets",
  "missing_design_revision",
  "has_design_revision",
  "customer_owned_set",
] as const;
export type ToolingListViewId = (typeof toolingListViewIds)[number];

export const toolingListSortKeys = [
  "title",
  "applicability_count",
  "physical_set_count",
  "latest_revision_number",
] as const;
export type ToolingListSortKey = (typeof toolingListSortKeys)[number];

export const toolingListSortDirections = ["asc", "desc"] as const;
export type ToolingListSortDirection =
  (typeof toolingListSortDirections)[number];

export const toolingListGroupKeys = [
  "none",
  "applicability_scope",
  "physical_set_presence",
  "design_revision_presence",
] as const;
export type ToolingListGroupKey = (typeof toolingListGroupKeys)[number];

export const toolingListColumnIds = [
  "selection",
  "tooling",
  "applicability",
  "part_revisions",
  "physical_sets",
  "design_revisions",
  "origin",
  "source",
  "action",
] as const;
export type ToolingListColumnId = (typeof toolingListColumnIds)[number];

export interface ToolingListFilterSnapshot {
  viewId: ToolingListViewId;
  search: string;
  sortKey: ToolingListSortKey;
  sortDirection: ToolingListSortDirection;
  groupKey: ToolingListGroupKey;
}

export interface ToolingListRow {
  toolingMasterGlobalId: string;
  toolingMasterSnapshotHash: string;
  title: string;
  projectGlobalId: string;
  projectCode: string;
  originatingProjectGlobalId: string;
  applicabilityCount: number;
  distinctPartRevisionCount: number;
  physicalSetCount: number;
  designRevisionCount: number;
  latestRevisionNumber: number | null;
  customerOwnedSet: boolean;
  source: "manual" | "controlled_xlsx_import";
}

export interface ToolingListPermissions {
  view: true;
  canExport: boolean;
  exportUnavailableReason: "separate_export_authority_required" | null;
}

export interface ToolingListPage {
  projectGlobalId: string;
  filter: ToolingListFilterSnapshot;
  querySnapshotHash: string;
  totalCount: number;
  pageSize: number;
  nextCursor: string | null;
  items: readonly ToolingListRow[];
  permissions: ToolingListPermissions;
}

export interface ToolingListColumnWidth {
  columnId: ToolingListColumnId;
  width: number;
}

export interface ToolingListPreferenceSnapshot {
  gridId: "tooling-list";
  tableSchemaVersion: "tooling-list-grid-v1";
  viewId: ToolingListViewId;
  filter: ToolingListFilterSnapshot;
  columnOrder: readonly ToolingListColumnId[];
  hiddenColumns: readonly Exclude<
    ToolingListColumnId,
    "selection" | "tooling" | "action"
  >[];
  columnWidths: readonly ToolingListColumnWidth[];
}

export interface ToolingListPreference {
  stored: boolean;
  globalId: string | null;
  optimisticVersion: number;
  snapshotHash: string | null;
  preference: ToolingListPreferenceSnapshot;
}

export interface SetToolingListPreference {
  expectedVersion: number;
  expectedSnapshotHash: string | null;
  preference: ToolingListPreferenceSnapshot;
}

export interface ToolingListSelectionReference {
  toolingMasterGlobalId: string;
  snapshotHash: string;
}

export type ToolingExportRequest =
  | {
      mode: "selection";
      selection: readonly ToolingListSelectionReference[];
    }
  | {
      mode: "filtered";
      filter: ToolingListFilterSnapshot;
      querySnapshotHash: string;
    };

export interface ToolingExportPackage {
  globalId: string;
  projectGlobalId: string;
  createdByUserId: string;
  mode: "selection" | "filtered";
  language: "en" | "zh" | "zh-TW";
  confidentialityClass: "internal_project";
  objectCount: number;
  querySnapshotHash: string | null;
  objectRefs: readonly ToolingListSelectionReference[];
  generatedAt: string;
  expiresAt: string;
  fileName: string;
  mimeType: "application/zip";
  sizeBytes: number;
  sha256: string;
  manifestSha256: string;
  snapshotHash: string;
}

export interface ToolingExportCommandResult {
  package: ToolingExportPackage;
  replayed: boolean;
}

export interface DownloadedToolingExportPackage {
  blob: Blob;
  fileName: string;
  replayed: boolean;
}

export interface ToolingListDataSource {
  loadList(
    projectId: string,
    filter: ToolingListFilterSnapshot,
    pageSize: number,
    cursor: string | null,
    signal: AbortSignal,
  ): Promise<ToolingListPage>;
  loadPreference(
    projectId: string,
    viewId: ToolingListViewId,
    signal: AbortSignal,
  ): Promise<ToolingListPreference>;
  savePreference(
    projectId: string,
    viewId: ToolingListViewId,
    command: SetToolingListPreference,
    csrfToken: string,
    signal: AbortSignal,
  ): Promise<ToolingListPreference>;
  createExport(
    projectId: string,
    request: ToolingExportRequest,
    context: ToolingCommandContext,
  ): Promise<ToolingExportCommandResult>;
  downloadExport(
    projectId: string,
    packageValue: ToolingExportPackage,
    context: ToolingCommandContext,
  ): Promise<DownloadedToolingExportPackage>;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const safeFileNamePattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,134}[.]zip$/u;
const hiddenColumnIds = new Set<ToolingListColumnId>([
  "applicability",
  "part_revisions",
  "physical_sets",
  "design_revisions",
  "origin",
  "source",
]);

function exact(value: object, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function member<T extends string>(
  value: unknown,
  values: readonly T[],
): value is T {
  return typeof value === "string" && values.includes(value as T);
}

function whole(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER) {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function unique(values: readonly unknown[]): boolean {
  return new Set(values).size === values.length;
}

function hasControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    return codePoint <= 31 || codePoint === 127;
  });
}

function validDateTime(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length >= 20 &&
    value.length <= 40 &&
    value.includes("T") &&
    Number.isFinite(Date.parse(value))
  );
}

export function isToolingListFilterSnapshot(
  value: unknown,
): value is ToolingListFilterSnapshot {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["viewId", "search", "sortKey", "sortDirection", "groupKey"]) &&
    member(item.viewId, toolingListViewIds) &&
    typeof item.search === "string" &&
    item.search.length <= 120 &&
    !hasControlCharacter(item.search) &&
    member(item.sortKey, toolingListSortKeys) &&
    member(item.sortDirection, toolingListSortDirections) &&
    member(item.groupKey, toolingListGroupKeys)
  );
}

export function isToolingListRow(value: unknown): value is ToolingListRow {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, [
      "toolingMasterGlobalId",
      "toolingMasterSnapshotHash",
      "title",
      "projectGlobalId",
      "projectCode",
      "originatingProjectGlobalId",
      "applicabilityCount",
      "distinctPartRevisionCount",
      "physicalSetCount",
      "designRevisionCount",
      "latestRevisionNumber",
      "customerOwnedSet",
      "source",
    ]) &&
    typeof item.toolingMasterGlobalId === "string" &&
    uuidPattern.test(item.toolingMasterGlobalId) &&
    typeof item.toolingMasterSnapshotHash === "string" &&
    hashPattern.test(item.toolingMasterSnapshotHash) &&
    typeof item.title === "string" &&
    item.title.length >= 1 &&
    item.title.length <= 140 &&
    !hasControlCharacter(item.title) &&
    typeof item.projectGlobalId === "string" &&
    uuidPattern.test(item.projectGlobalId) &&
    typeof item.projectCode === "string" &&
    item.projectCode.length >= 1 &&
    item.projectCode.length <= 64 &&
    !hasControlCharacter(item.projectCode) &&
    typeof item.originatingProjectGlobalId === "string" &&
    uuidPattern.test(item.originatingProjectGlobalId) &&
    whole(item.applicabilityCount) &&
    whole(item.distinctPartRevisionCount) &&
    whole(item.physicalSetCount) &&
    whole(item.designRevisionCount) &&
    (item.latestRevisionNumber === null ||
      whole(item.latestRevisionNumber, 1)) &&
    typeof item.customerOwnedSet === "boolean" &&
    member(item.source, ["manual", "controlled_xlsx_import"] as const)
  );
}

function isToolingListPermissions(
  value: unknown,
): value is ToolingListPermissions {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["view", "canExport", "exportUnavailableReason"]) &&
    item.view === true &&
    typeof item.canExport === "boolean" &&
    (item.exportUnavailableReason === null ||
      item.exportUnavailableReason === "separate_export_authority_required") &&
    (item.canExport
      ? item.exportUnavailableReason === null
      : item.exportUnavailableReason === "separate_export_authority_required")
  );
}

export function isToolingListPage(value: unknown): value is ToolingListPage {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "projectGlobalId",
      "filter",
      "querySnapshotHash",
      "totalCount",
      "pageSize",
      "nextCursor",
      "items",
      "permissions",
    ]) ||
    typeof item.projectGlobalId !== "string" ||
    !uuidPattern.test(item.projectGlobalId) ||
    !isToolingListFilterSnapshot(item.filter) ||
    typeof item.querySnapshotHash !== "string" ||
    !hashPattern.test(item.querySnapshotHash) ||
    !whole(item.totalCount) ||
    !whole(item.pageSize, 1, 100) ||
    (item.nextCursor !== null &&
      (typeof item.nextCursor !== "string" ||
        item.nextCursor.length < 1 ||
        item.nextCursor.length > 500 ||
        hasControlCharacter(item.nextCursor))) ||
    !Array.isArray(item.items) ||
    item.items.length > 100 ||
    !item.items.every(isToolingListRow) ||
    !isToolingListPermissions(item.permissions)
  )
    return false;
  const rows = item.items as readonly ToolingListRow[];
  return (
    rows.length <= (item.pageSize as number) &&
    rows.length <= (item.totalCount as number) &&
    unique(rows.map((row) => row.toolingMasterGlobalId))
  );
}

function isToolingListColumnWidth(
  value: unknown,
): value is ToolingListColumnWidth {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["columnId", "width"]) &&
    member(item.columnId, toolingListColumnIds) &&
    whole(item.width, 56, 480)
  );
}

export function isToolingListPreferenceSnapshot(
  value: unknown,
): value is ToolingListPreferenceSnapshot {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "gridId",
      "tableSchemaVersion",
      "viewId",
      "filter",
      "columnOrder",
      "hiddenColumns",
      "columnWidths",
    ]) ||
    item.gridId !== "tooling-list" ||
    item.tableSchemaVersion !== "tooling-list-grid-v1" ||
    !member(item.viewId, toolingListViewIds) ||
    !isToolingListFilterSnapshot(item.filter) ||
    item.filter.viewId !== item.viewId ||
    !Array.isArray(item.columnOrder) ||
    !Array.isArray(item.hiddenColumns) ||
    !Array.isArray(item.columnWidths) ||
    item.columnOrder.length !== toolingListColumnIds.length
  )
    return false;
  const columnOrder = item.columnOrder as readonly unknown[];
  const hiddenColumns = item.hiddenColumns as readonly unknown[];
  const columnWidths = item.columnWidths as readonly unknown[];
  if (
    !columnOrder.every((column) => member(column, toolingListColumnIds)) ||
    !unique(columnOrder) ||
    !toolingListColumnIds.every((column) => columnOrder.includes(column)) ||
    hiddenColumns.length > 6 ||
    !hiddenColumns.every(
      (column) =>
        member(column, toolingListColumnIds) && hiddenColumnIds.has(column),
    ) ||
    !unique(hiddenColumns) ||
    columnWidths.length > 9 ||
    !columnWidths.every(isToolingListColumnWidth)
  )
    return false;
  const widths = columnWidths;
  return unique(widths.map((entry) => entry.columnId));
}

export function isToolingListPreference(
  value: unknown,
): value is ToolingListPreference {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "stored",
      "globalId",
      "optimisticVersion",
      "snapshotHash",
      "preference",
    ]) ||
    typeof item.stored !== "boolean" ||
    !(
      item.globalId === null ||
      (typeof item.globalId === "string" && uuidPattern.test(item.globalId))
    ) ||
    !whole(item.optimisticVersion) ||
    !(
      item.snapshotHash === null ||
      (typeof item.snapshotHash === "string" &&
        hashPattern.test(item.snapshotHash))
    ) ||
    !isToolingListPreferenceSnapshot(item.preference)
  )
    return false;
  const optimisticVersion = item.optimisticVersion as number;
  return item.stored
    ? item.globalId !== null &&
        optimisticVersion >= 1 &&
        item.snapshotHash !== null
    : item.globalId === null &&
        optimisticVersion === 0 &&
        item.snapshotHash === null;
}

function isSelectionReference(
  value: unknown,
): value is ToolingListSelectionReference {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    exact(item, ["toolingMasterGlobalId", "snapshotHash"]) &&
    typeof item.toolingMasterGlobalId === "string" &&
    uuidPattern.test(item.toolingMasterGlobalId) &&
    typeof item.snapshotHash === "string" &&
    hashPattern.test(item.snapshotHash)
  );
}

export function isToolingExportPackage(
  value: unknown,
): value is ToolingExportPackage {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (
    !exact(item, [
      "globalId",
      "projectGlobalId",
      "createdByUserId",
      "mode",
      "language",
      "confidentialityClass",
      "objectCount",
      "querySnapshotHash",
      "objectRefs",
      "generatedAt",
      "expiresAt",
      "fileName",
      "mimeType",
      "sizeBytes",
      "sha256",
      "manifestSha256",
      "snapshotHash",
    ]) ||
    typeof item.globalId !== "string" ||
    !uuidPattern.test(item.globalId) ||
    typeof item.projectGlobalId !== "string" ||
    !uuidPattern.test(item.projectGlobalId) ||
    typeof item.createdByUserId !== "string" ||
    item.createdByUserId.length < 1 ||
    item.createdByUserId.length > 254 ||
    hasControlCharacter(item.createdByUserId) ||
    !member(item.mode, ["selection", "filtered"] as const) ||
    !member(item.language, ["en", "zh", "zh-TW"] as const) ||
    item.confidentialityClass !== "internal_project" ||
    !whole(item.objectCount, 1, 100) ||
    (item.querySnapshotHash !== null &&
      (typeof item.querySnapshotHash !== "string" ||
        !hashPattern.test(item.querySnapshotHash))) ||
    !Array.isArray(item.objectRefs) ||
    item.objectRefs.length < 1 ||
    item.objectRefs.length > 100 ||
    !item.objectRefs.every(isSelectionReference) ||
    !validDateTime(item.generatedAt) ||
    !validDateTime(item.expiresAt) ||
    Date.parse(item.expiresAt) - Date.parse(item.generatedAt) !== 3_600_000 ||
    typeof item.fileName !== "string" ||
    item.fileName.length > 140 ||
    !safeFileNamePattern.test(item.fileName) ||
    item.mimeType !== "application/zip" ||
    !whole(item.sizeBytes, 1, 1_000_000) ||
    typeof item.sha256 !== "string" ||
    !hashPattern.test(item.sha256) ||
    typeof item.manifestSha256 !== "string" ||
    !hashPattern.test(item.manifestSha256) ||
    typeof item.snapshotHash !== "string" ||
    !hashPattern.test(item.snapshotHash)
  )
    return false;
  const refs = item.objectRefs as readonly ToolingListSelectionReference[];
  return (
    refs.length === item.objectCount &&
    unique(refs.map((entry) => entry.toolingMasterGlobalId)) &&
    (item.mode === "selection"
      ? item.querySnapshotHash === null
      : item.querySnapshotHash !== null)
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function invalidResponse(): NpiTransportError {
  return new NpiTransportError(
    "invalid_response",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function requireUuid(value: string): string {
  if (!uuidPattern.test(value)) throw requestNotReady();
  return value;
}

function validContext(value: ToolingCommandContext): boolean {
  return (
    typeof value.csrfToken === "string" &&
    value.csrfToken.length >= 32 &&
    value.csrfToken.length <= 128 &&
    !hasControlCharacter(value.csrfToken) &&
    idempotencyPattern.test(value.idempotencyKey) &&
    value.signal instanceof AbortSignal
  );
}

function cancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ToolingRequestCancelledError();
}

function sameFilter(
  left: ToolingListFilterSnapshot,
  right: ToolingListFilterSnapshot,
): boolean {
  return (
    left.viewId === right.viewId &&
    left.search === right.search &&
    left.sortKey === right.sortKey &&
    left.sortDirection === right.sortDirection &&
    left.groupKey === right.groupKey
  );
}

function validExportRequest(value: ToolingExportRequest): boolean {
  if (value.mode === "selection") {
    return (
      exact(value, ["mode", "selection"]) &&
      value.selection.length >= 1 &&
      value.selection.length <= 100 &&
      value.selection.every(isSelectionReference) &&
      unique(value.selection.map((entry) => entry.toolingMasterGlobalId))
    );
  }
  return (
    exact(value, ["mode", "filter", "querySnapshotHash"]) &&
    isToolingListFilterSnapshot(value.filter) &&
    hashPattern.test(value.querySnapshotHash)
  );
}

function replayHeader(response: Response): boolean | null {
  const value = response.headers.get("Idempotency-Replayed");
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

async function sha256(blob: Blob): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    await blob.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

export class LiveToolingListDataSource implements ToolingListDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadList(
    projectId: string,
    filter: ToolingListFilterSnapshot,
    pageSize: number,
    cursor: string | null,
    signal: AbortSignal,
  ): Promise<ToolingListPage> {
    const expectedProjectId = requireUuid(projectId);
    if (
      !isToolingListFilterSnapshot(filter) ||
      !whole(pageSize, 1, 100) ||
      (cursor !== null &&
        (cursor.length < 1 ||
          cursor.length > 500 ||
          hasControlCharacter(cursor)))
    )
      throw requestNotReady();
    cancelled(signal);
    try {
      return await this.http.request<ToolingListPage>(
        `/projects/${expectedProjectId}/tooling-list`,
        { signal },
        {
          query: {
            groupKey: filter.groupKey,
            pageSize: String(pageSize),
            search: filter.search,
            sortDirection: filter.sortDirection,
            sortKey: filter.sortKey,
            viewId: filter.viewId,
            ...(cursor === null ? {} : { cursor }),
          },
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ToolingListPage =>
            isToolingListPage(value) &&
            value.projectGlobalId === expectedProjectId &&
            value.pageSize === pageSize &&
            sameFilter(value.filter, filter) &&
            value.items.every(
              (row) => row.projectGlobalId === expectedProjectId,
            ),
        },
      );
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  async loadPreference(
    projectId: string,
    viewId: ToolingListViewId,
    signal: AbortSignal,
  ): Promise<ToolingListPreference> {
    const expectedProjectId = requireUuid(projectId);
    if (!member(viewId, toolingListViewIds)) throw requestNotReady();
    cancelled(signal);
    try {
      return await this.http.request<ToolingListPreference>(
        `/projects/${expectedProjectId}/tooling-list/preferences/${viewId}`,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ToolingListPreference =>
            isToolingListPreference(value) &&
            value.preference.viewId === viewId,
        },
      );
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  async savePreference(
    projectId: string,
    viewId: ToolingListViewId,
    command: SetToolingListPreference,
    csrfToken: string,
    signal: AbortSignal,
  ): Promise<ToolingListPreference> {
    const expectedProjectId = requireUuid(projectId);
    if (
      !member(viewId, toolingListViewIds) ||
      !whole(command.expectedVersion) ||
      (command.expectedSnapshotHash !== null &&
        !hashPattern.test(command.expectedSnapshotHash)) ||
      !isToolingListPreferenceSnapshot(command.preference) ||
      command.preference.viewId !== viewId ||
      typeof csrfToken !== "string" ||
      csrfToken.length < 32 ||
      csrfToken.length > 128 ||
      hasControlCharacter(csrfToken)
    )
      throw requestNotReady();
    cancelled(signal);
    try {
      return await this.http.request<ToolingListPreference>(
        `/projects/${expectedProjectId}/tooling-list/preferences/${viewId}`,
        {
          body: JSON.stringify(command),
          method: "PUT",
          signal,
        },
        {
          csrfToken,
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ToolingListPreference =>
            isToolingListPreference(value) &&
            value.stored &&
            value.preference.viewId === viewId,
        },
      );
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  async createExport(
    projectId: string,
    request: ToolingExportRequest,
    context: ToolingCommandContext,
  ): Promise<ToolingExportCommandResult> {
    const expectedProjectId = requireUuid(projectId);
    if (!validContext(context) || !validExportRequest(request))
      throw requestNotReady();
    cancelled(context.signal);
    let replayed = false;
    try {
      const result = await this.http.request<{ package: ToolingExportPackage }>(
        `/projects/${expectedProjectId}/tooling-exports`,
        {
          body: JSON.stringify(request),
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
          validate: (value): value is { package: ToolingExportPackage } =>
            value !== null &&
            typeof value === "object" &&
            exact(value, ["package"]) &&
            isToolingExportPackage((value as { package?: unknown }).package) &&
            (value as { package: ToolingExportPackage }).package
              .projectGlobalId === expectedProjectId,
          validateResponse: (response) => {
            const header = replayHeader(response);
            if (header === null) return false;
            replayed = header;
            return true;
          },
        },
      );
      return { package: result.package, replayed };
    } catch (error) {
      cancelled(context.signal);
      throw error;
    }
  }

  async downloadExport(
    projectId: string,
    packageValue: ToolingExportPackage,
    context: ToolingCommandContext,
  ): Promise<DownloadedToolingExportPackage> {
    const expectedProjectId = requireUuid(projectId);
    if (
      !validContext(context) ||
      !isToolingExportPackage(packageValue) ||
      packageValue.projectGlobalId !== expectedProjectId
    )
      throw requestNotReady();
    cancelled(context.signal);
    let replayed = false;
    try {
      const blob = await this.http.request<Blob>(
        `/projects/${expectedProjectId}/tooling-exports/${packageValue.globalId}:content`,
        {
          body: JSON.stringify({
            expectedSnapshotHash: packageValue.snapshotHash,
          }),
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
          responseType: "blob",
          validate: (value): value is Blob =>
            value instanceof Blob && value.size === packageValue.sizeBytes,
          validateResponse: (response) => {
            const header = replayHeader(response);
            if (header === null) return false;
            replayed = header;
            return (
              response.headers.get("Content-Type")?.toLowerCase() ===
                "application/zip" &&
              response.headers.get("Content-Disposition") ===
                `attachment; filename="${packageValue.fileName}"` &&
              response.headers.get("X-Content-Type-Options")?.toLowerCase() ===
                "nosniff" &&
              response.headers.get("Content-Security-Policy") ===
                "sandbox; default-src 'none'" &&
              response.headers.get("Referrer-Policy")?.toLowerCase() ===
                "no-referrer"
            );
          },
        },
      );
      if ((await sha256(blob)) !== packageValue.sha256) throw invalidResponse();
      return { blob, fileName: packageValue.fileName, replayed };
    } catch (error) {
      cancelled(context.signal);
      throw error;
    }
  }
}
