import { NpiHttpClient, NpiTransportError } from "./http";

export type ERPMasterKind =
  | "customer"
  | "supplier"
  | "item_group"
  | "item"
  | "machine";
export interface ERPMasterRecord {
  sourceKey: string;
  displayName: string;
  enabled: boolean;
  sourceModifiedAt: string;
  groupKey?: string | null;
  parentKey?: string | null;
  isGroup?: boolean;
  stockUom?: string;
  isStockItem?: boolean;
}
export interface ERPMasterPage {
  schemaVersion: 1;
  catalogKind: ERPMasterKind;
  sourceVersion: number;
  sourceModifiedAt: string | null;
  lastSynchronizedAt: string | null;
  total: number;
  offset: number;
  limit: number;
  items: readonly ERPMasterRecord[];
}
export interface ERPMasterDataSource {
  load(
    kind: ERPMasterKind,
    query: string,
    offset: number,
    signal: AbortSignal,
    projectId?: string,
  ): Promise<ERPMasterPage>;
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return (
    Object.keys(value).length === keys.length &&
    keys.every((key) => Object.hasOwn(value, key))
  );
}
function text(value: unknown, max = 255): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= max &&
    value.trim() === value &&
    Array.from(value).every(
      (character) =>
        character.charCodeAt(0) >= 32 && character.charCodeAt(0) !== 127,
    )
  );
}
function time(value: unknown): boolean {
  return (
    typeof value === "string" &&
    /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/u.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}
function integer(value: unknown, min: number, max: number): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= min &&
    value <= max
  );
}
export function isERPMasterPage(
  value: unknown,
  kind: ERPMasterKind,
): value is ERPMasterPage {
  if (
    !record(value) ||
    !exact(value, [
      "schemaVersion",
      "catalogKind",
      "sourceVersion",
      "sourceModifiedAt",
      "lastSynchronizedAt",
      "total",
      "offset",
      "limit",
      "items",
    ]) ||
    value.schemaVersion !== 1 ||
    value.catalogKind !== kind ||
    !integer(value.sourceVersion, 0, 2147483647) ||
    !integer(value.total, 0, 10000) ||
    !integer(value.offset, 0, 50000) ||
    !integer(value.limit, 1, 200) ||
    !Array.isArray(value.items) ||
    value.items.length > value.limit ||
    value.items.length > Math.max(0, value.total - value.offset)
  )
    return false;
  if (
    value.sourceVersion === 0
      ? value.sourceModifiedAt !== null ||
        value.lastSynchronizedAt !== null ||
        value.total !== 0
      : !time(value.sourceModifiedAt) || !time(value.lastSynchronizedAt)
  )
    return false;
  const fields = ["sourceKey", "displayName", "enabled", "sourceModifiedAt"];
  const extra =
    kind === "item"
      ? ["groupKey", "stockUom", "isStockItem"]
      : kind === "item_group"
        ? ["parentKey", "isGroup"]
        : ["groupKey"];
  return (
    new Set(
      value.items.map((item: unknown) =>
        record(item) ? item.sourceKey : null,
      ),
    ).size === value.items.length &&
    value.items.every((item: unknown) => {
      if (
        !record(item) ||
        !exact(item, [...fields, ...extra]) ||
        !text(item.sourceKey) ||
        !text(item.displayName) ||
        typeof item.enabled !== "boolean" ||
        !time(item.sourceModifiedAt)
      )
        return false;
      if (kind === "item")
        return (
          text(item.groupKey) &&
          text(item.stockUom, 140) &&
          typeof item.isStockItem === "boolean"
        );
      if (kind === "item_group")
        return (
          (item.parentKey === null || text(item.parentKey)) &&
          typeof item.isGroup === "boolean"
        );
      return item.groupKey === null || text(item.groupKey);
    })
  );
}
export class LiveERPMasterDataSource implements ERPMasterDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}
  load(
    kind: ERPMasterKind,
    query: string,
    offset: number,
    signal: AbortSignal,
    projectId?: string,
  ): Promise<ERPMasterPage> {
    if (
      query.length > 100 ||
      !integer(offset, 0, 50000) ||
      (projectId !== undefined &&
        !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/u.test(projectId))
    )
      throw new NpiTransportError(
        "request_not_ready",
        `client-${globalThis.crypto.randomUUID()}`,
        "client",
      );
    const params = new URLSearchParams({
      kind,
      limit: "20",
      offset: String(offset),
    });
    if (query.trim()) params.set("query", query.trim());
    if (projectId) params.set("projectId", projectId);
    return this.http.request<ERPMasterPage>(
      "/integration/erpnext/master-data",
      { signal },
      {
        query: Object.fromEntries(params),
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: (value): value is ERPMasterPage =>
          isERPMasterPage(value, kind) &&
          value.offset === offset &&
          value.limit === 20,
      },
    );
  }
}
