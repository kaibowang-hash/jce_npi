import { NpiHttpClient, NpiTransportError } from "./http";

export const erpProjectionKinds = [
  "customer_master",
  "supplier_master",
  "formal_item_master",
  "tooling_procurement_cost",
  "project_cost",
  "formal_quality_status",
  "tool_asset_status",
] as const;

export type ErpProjectionKind = (typeof erpProjectionKinds)[number];
export type ErpProjectionScopeKind =
  | "project"
  | "tooling_master"
  | "tooling_set"
  | "engineering_item"
  | "trial_round"
  | "readiness";
export type ErpProjectionAvailability =
  | "available"
  | "unavailable"
  | "synthetic";
export type ErpProjectionFreshness = "fresh" | "stale" | "unknown";
export type ErpProjectionDisposition =
  | "applied_current"
  | "unavailable_current"
  | "superseded"
  | "duplicate_exact"
  | "conflicted"
  | "synthetic_retained";

export interface ErpProjectionMasterValues {
  code: string;
  displayName: string;
  enabled: boolean;
  statusCode: string | null;
}

export interface ErpProjectionItemValues {
  itemCode: string;
  stockUom: string;
  enabled: boolean;
  statusCode: string | null;
}

export interface ErpProjectionSupplierReference {
  sourceObjectId: string;
  targetVersion: string;
  supplierCode: string;
  supplierName: string;
}

export interface ErpProjectionToolingCostRow {
  toolingMasterGlobalId: string;
  sourceRowId: string;
  sourceRowVersion: string;
  supplierSourceObjectId: string;
  purchaseOrderSourceId: string;
  purchaseReceiptSourceId: string;
  purchaseInvoiceSourceId: string;
  actualCostSourceId: string;
  costTypeCode: string;
  postingDate: string;
  currency: string;
  amount: string;
}

export interface ErpProjectionToolingCostValues {
  toolingMasterGlobalId: string;
  supplier: ErpProjectionSupplierReference;
  rows: readonly ErpProjectionToolingCostRow[];
}

export interface ErpProjectionProjectCostRow {
  rowKind: "commitment" | "actual_cost" | "labor_hours" | "expense";
  sourceRowId: string;
  sourceRowVersion: string;
  postingDate: string;
  currency: string | null;
  amount: string | null;
  hours: string | null;
}

export interface ErpProjectionProjectCostValues {
  rows: readonly ErpProjectionProjectCostRow[];
}

export interface ErpProjectionQualityValues {
  recordKind: "quality_inspection" | "ncr" | "capa";
  statusCode: string;
  resultCode: string | null;
  observedAt: string;
}

export interface ErpProjectionAssetMovement {
  globalId: string;
  actionKind: "move" | "loan" | "return" | "archive" | "scrap";
  fromLocation: string | null;
  toLocation: string | null;
  occurredAt: string;
  sourceObjectId: string;
}

export interface ErpProjectionAssetRepair {
  globalId: string;
  summary: string;
  downtimeHours: string;
  completedAt: string;
  sourceObjectId: string;
}

export interface ErpProjectionAssetSpare {
  formalItemId: string;
  description: string;
  stockOnHand: string;
  minimumStock: string;
  unit: string;
  supplierId: string | null;
}

export interface ErpProjectionToolAssetValues {
  toolingSetGlobalId: string;
  mappingVersion: number;
  formalAssetId: string;
  targetVersion: string;
  assetState: string;
  currentLocation: string;
  shotCount: number;
  expectedLifeShots: number | null;
  maintenanceDue: string | null;
  movements: readonly ErpProjectionAssetMovement[];
  repairs: readonly ErpProjectionAssetRepair[];
  spares: readonly ErpProjectionAssetSpare[];
}

export type ErpProjectionValues =
  | ErpProjectionMasterValues
  | ErpProjectionItemValues
  | ErpProjectionToolingCostValues
  | ErpProjectionProjectCostValues
  | ErpProjectionQualityValues
  | ErpProjectionToolAssetValues;

export interface ErpProjectionCurrentTruthViewModel {
  observationGlobalId: string;
  sourceVersion: string;
  sourceModifiedAt: string;
  receivedAt: string;
  payloadHash: string;
  values: ErpProjectionValues;
}

export interface ErpProjectionItemViewModel {
  observationGlobalId: string;
  projectionKind: ErpProjectionKind;
  scopeKind: ErpProjectionScopeKind;
  scopeGlobalId: string;
  availability: ErpProjectionAvailability;
  freshness: ErpProjectionFreshness;
  disposition: ErpProjectionDisposition;
  sourceSystem: "ERPNEXT";
  sourceObjectType: string;
  sourceObjectId: string;
  sourceVersion: string | null;
  sourceModifiedAt: string | null;
  receivedAt: string;
  payloadHash: string;
  unavailableReasonCode: string | null;
  values: ErpProjectionValues | null;
  currentTruth: ErpProjectionCurrentTruthViewModel | null;
  editable: false;
}

export interface ErpProjectionCollectionViewModel {
  projectGlobalId: string;
  accessState: "available" | "redacted";
  reasonCode: "projection_access_redacted" | null;
  permissions: Readonly<{ view: boolean; edit: false; refresh: false }>;
  items: readonly ErpProjectionItemViewModel[];
}

export interface ErpProjectionsDataSource {
  loadProjectProjections(
    projectId: string,
    signal: AbortSignal,
    kind?: ErpProjectionKind,
  ): Promise<ErpProjectionCollectionViewModel>;
}

export class ErpProjectionsRequestCancelledError extends Error {
  constructor() {
    super("The ERP projection request was cancelled.");
    this.name = "ErpProjectionsRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const codePattern = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u;
const currencyPattern = /^[A-Z]{3}$/u;
const decimalPattern = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/u;
const nonnegativeDecimalPattern = /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const dateTimePattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u;

const kindSet = new Set<ErpProjectionKind>(erpProjectionKinds);
const availabilitySet = new Set<ErpProjectionAvailability>([
  "available",
  "unavailable",
  "synthetic",
]);
const freshnessSet = new Set<ErpProjectionFreshness>([
  "fresh",
  "stale",
  "unknown",
]);
const dispositionSet = new Set<ErpProjectionDisposition>([
  "applied_current",
  "unavailable_current",
  "superseded",
  "duplicate_exact",
  "conflicted",
  "synthetic_retained",
]);
const sourceDefinitions: Readonly<
  Record<
    ErpProjectionKind,
    Readonly<{
      sourceObjectType: string;
      scopes: ReadonlySet<ErpProjectionScopeKind>;
    }>
  >
> = {
  customer_master: {
    scopes: new Set(["project"]),
    sourceObjectType: "Customer",
  },
  supplier_master: {
    scopes: new Set(["tooling_master"]),
    sourceObjectType: "Supplier",
  },
  formal_item_master: {
    scopes: new Set(["engineering_item"]),
    sourceObjectType: "Item",
  },
  tooling_procurement_cost: {
    scopes: new Set(["tooling_master"]),
    sourceObjectType: "ToolingProcurementCost",
  },
  project_cost: {
    scopes: new Set(["project"]),
    sourceObjectType: "ProjectCost",
  },
  formal_quality_status: {
    scopes: new Set(["project", "trial_round", "readiness"]),
    sourceObjectType: "FormalQualityStatus",
  },
  tool_asset_status: {
    scopes: new Set(["tooling_set"]),
    sourceObjectType: "Asset",
  },
};

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
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

function containsControlCharacter(value: string): boolean {
  for (const character of value) {
    const codePoint = character.codePointAt(0) ?? 0;
    if (codePoint <= 31 || codePoint === 127) return true;
  }
  return false;
}

function text(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.length >= 1 &&
    value.length <= maximum &&
    value === value.trim() &&
    !containsControlCharacter(value)
  );
}

function nullableText(value: unknown, maximum: number): value is string | null {
  return value === null || text(value, maximum);
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function hash(value: unknown): value is string {
  return typeof value === "string" && hashPattern.test(value);
}

function code(value: unknown): value is string {
  return typeof value === "string" && codePattern.test(value);
}

function date(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) &&
    parsed.toISOString().slice(0, 10) === value
  );
}

function dateTime(value: unknown): value is string {
  return (
    typeof value === "string" &&
    dateTimePattern.test(value) &&
    date(value.slice(0, 10)) &&
    !Number.isNaN(Date.parse(value))
  );
}

function integer(value: unknown, minimum: number): value is number {
  return (
    typeof value === "number" && Number.isSafeInteger(value) && value >= minimum
  );
}

function boundedArray(
  value: unknown,
  maximum: number,
): value is readonly unknown[] {
  return Array.isArray(value) && value.length <= maximum;
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

function masterValues(value: unknown): value is ErpProjectionMasterValues {
  return (
    record(value) &&
    exact(value, ["code", "displayName", "enabled", "statusCode"]) &&
    code(value.code) &&
    text(value.displayName, 200) &&
    typeof value.enabled === "boolean" &&
    (value.statusCode === null || code(value.statusCode))
  );
}

function itemValues(value: unknown): value is ErpProjectionItemValues {
  return (
    record(value) &&
    exact(value, ["itemCode", "stockUom", "enabled", "statusCode"]) &&
    code(value.itemCode) &&
    code(value.stockUom) &&
    typeof value.enabled === "boolean" &&
    (value.statusCode === null || code(value.statusCode))
  );
}

function supplierReference(
  value: unknown,
): value is ErpProjectionSupplierReference {
  return (
    record(value) &&
    exact(value, [
      "sourceObjectId",
      "targetVersion",
      "supplierCode",
      "supplierName",
    ]) &&
    text(value.sourceObjectId, 128) &&
    text(value.targetVersion, 128) &&
    code(value.supplierCode) &&
    text(value.supplierName, 200)
  );
}

function toolingCostRow(
  value: unknown,
  masterId: string,
  supplierId: string,
): value is ErpProjectionToolingCostRow {
  return (
    record(value) &&
    exact(value, [
      "toolingMasterGlobalId",
      "sourceRowId",
      "sourceRowVersion",
      "supplierSourceObjectId",
      "purchaseOrderSourceId",
      "purchaseReceiptSourceId",
      "purchaseInvoiceSourceId",
      "actualCostSourceId",
      "costTypeCode",
      "postingDate",
      "currency",
      "amount",
    ]) &&
    value.toolingMasterGlobalId === masterId &&
    text(value.sourceRowId, 128) &&
    text(value.sourceRowVersion, 128) &&
    value.supplierSourceObjectId === supplierId &&
    text(value.purchaseOrderSourceId, 128) &&
    text(value.purchaseReceiptSourceId, 128) &&
    text(value.purchaseInvoiceSourceId, 128) &&
    text(value.actualCostSourceId, 128) &&
    code(value.costTypeCode) &&
    date(value.postingDate) &&
    typeof value.currency === "string" &&
    currencyPattern.test(value.currency) &&
    typeof value.amount === "string" &&
    value.amount.length <= 32 &&
    decimalPattern.test(value.amount)
  );
}

function toolingCostValues(
  value: unknown,
): value is ErpProjectionToolingCostValues {
  if (
    !record(value) ||
    !exact(value, ["toolingMasterGlobalId", "supplier", "rows"]) ||
    !uuid(value.toolingMasterGlobalId) ||
    !supplierReference(value.supplier) ||
    !boundedArray(value.rows, 1000) ||
    value.rows.length < 1
  )
    return false;
  const masterId = value.toolingMasterGlobalId;
  const supplierId = value.supplier.sourceObjectId;
  if (!value.rows.every((row) => toolingCostRow(row, masterId, supplierId)))
    return false;
  return unique(
    value.rows.map((row) => `${row.sourceRowId}\u0000${row.sourceRowVersion}`),
  );
}

function projectCostRow(value: unknown): value is ErpProjectionProjectCostRow {
  if (
    !record(value) ||
    !exact(value, [
      "rowKind",
      "sourceRowId",
      "sourceRowVersion",
      "postingDate",
      "currency",
      "amount",
      "hours",
    ]) ||
    !["commitment", "actual_cost", "labor_hours", "expense"].includes(
      String(value.rowKind),
    ) ||
    !text(value.sourceRowId, 128) ||
    !text(value.sourceRowVersion, 128) ||
    !date(value.postingDate)
  )
    return false;
  if (value.rowKind === "labor_hours") {
    return (
      value.currency === null &&
      value.amount === null &&
      typeof value.hours === "string" &&
      value.hours.length <= 32 &&
      nonnegativeDecimalPattern.test(value.hours)
    );
  }
  return (
    typeof value.currency === "string" &&
    currencyPattern.test(value.currency) &&
    typeof value.amount === "string" &&
    value.amount.length <= 32 &&
    decimalPattern.test(value.amount) &&
    value.hours === null
  );
}

function projectCostValues(
  value: unknown,
): value is ErpProjectionProjectCostValues {
  if (
    !record(value) ||
    !exact(value, ["rows"]) ||
    !boundedArray(value.rows, 1000) ||
    value.rows.length < 1 ||
    !value.rows.every(projectCostRow)
  )
    return false;
  return unique(
    value.rows.map((row) => `${row.sourceRowId}\u0000${row.sourceRowVersion}`),
  );
}

function qualityValues(value: unknown): value is ErpProjectionQualityValues {
  return (
    record(value) &&
    exact(value, ["recordKind", "statusCode", "resultCode", "observedAt"]) &&
    ["quality_inspection", "ncr", "capa"].includes(String(value.recordKind)) &&
    code(value.statusCode) &&
    (value.resultCode === null || code(value.resultCode)) &&
    dateTime(value.observedAt)
  );
}

function assetMovement(value: unknown): value is ErpProjectionAssetMovement {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "actionKind",
      "fromLocation",
      "toLocation",
      "occurredAt",
      "sourceObjectId",
    ]) &&
    uuid(value.globalId) &&
    ["move", "loan", "return", "archive", "scrap"].includes(
      String(value.actionKind),
    ) &&
    nullableText(value.fromLocation, 255) &&
    nullableText(value.toLocation, 255) &&
    dateTime(value.occurredAt) &&
    text(value.sourceObjectId, 128)
  );
}

function assetRepair(value: unknown): value is ErpProjectionAssetRepair {
  return (
    record(value) &&
    exact(value, [
      "globalId",
      "summary",
      "downtimeHours",
      "completedAt",
      "sourceObjectId",
    ]) &&
    uuid(value.globalId) &&
    text(value.summary, 2000) &&
    typeof value.downtimeHours === "string" &&
    value.downtimeHours.length <= 32 &&
    nonnegativeDecimalPattern.test(value.downtimeHours) &&
    dateTime(value.completedAt) &&
    text(value.sourceObjectId, 128)
  );
}

function assetSpare(value: unknown): value is ErpProjectionAssetSpare {
  return (
    record(value) &&
    exact(value, [
      "formalItemId",
      "description",
      "stockOnHand",
      "minimumStock",
      "unit",
      "supplierId",
    ]) &&
    text(value.formalItemId, 128) &&
    text(value.description, 1000) &&
    typeof value.stockOnHand === "string" &&
    value.stockOnHand.length <= 32 &&
    nonnegativeDecimalPattern.test(value.stockOnHand) &&
    typeof value.minimumStock === "string" &&
    value.minimumStock.length <= 32 &&
    nonnegativeDecimalPattern.test(value.minimumStock) &&
    typeof value.unit === "string" &&
    value.unit.length <= 32 &&
    codePattern.test(value.unit) &&
    nullableText(value.supplierId, 128)
  );
}

export function isErpProjectionToolAssetValues(
  value: unknown,
): value is ErpProjectionToolAssetValues {
  if (
    !record(value) ||
    !exact(value, [
      "toolingSetGlobalId",
      "mappingVersion",
      "formalAssetId",
      "targetVersion",
      "assetState",
      "currentLocation",
      "shotCount",
      "expectedLifeShots",
      "maintenanceDue",
      "movements",
      "repairs",
      "spares",
    ]) ||
    !uuid(value.toolingSetGlobalId) ||
    !integer(value.mappingVersion, 1) ||
    !text(value.formalAssetId, 128) ||
    !text(value.targetVersion, 128) ||
    !code(value.assetState) ||
    !text(value.currentLocation, 255) ||
    !integer(value.shotCount, 0) ||
    !(
      value.expectedLifeShots === null || integer(value.expectedLifeShots, 1)
    ) ||
    !(value.maintenanceDue === null || date(value.maintenanceDue)) ||
    !boundedArray(value.movements, 200) ||
    !value.movements.every(assetMovement) ||
    !boundedArray(value.repairs, 200) ||
    !value.repairs.every(assetRepair) ||
    !boundedArray(value.spares, 500) ||
    !value.spares.every(assetSpare)
  )
    return false;
  return (
    unique(value.movements.map((item) => item.globalId)) &&
    unique(value.repairs.map((item) => item.globalId))
  );
}

function projectionValues(kind: ErpProjectionKind, value: unknown): boolean {
  switch (kind) {
    case "customer_master":
    case "supplier_master":
      return masterValues(value);
    case "formal_item_master":
      return itemValues(value);
    case "tooling_procurement_cost":
      return toolingCostValues(value);
    case "project_cost":
      return projectCostValues(value);
    case "formal_quality_status":
      return qualityValues(value);
    case "tool_asset_status":
      return isErpProjectionToolAssetValues(value);
  }
}

function currentTruth(
  kind: ErpProjectionKind,
  value: unknown,
): value is ErpProjectionCurrentTruthViewModel {
  return (
    record(value) &&
    exact(value, [
      "observationGlobalId",
      "sourceVersion",
      "sourceModifiedAt",
      "receivedAt",
      "payloadHash",
      "values",
    ]) &&
    uuid(value.observationGlobalId) &&
    text(value.sourceVersion, 255) &&
    dateTime(value.sourceModifiedAt) &&
    dateTime(value.receivedAt) &&
    hash(value.payloadHash) &&
    projectionValues(kind, value.values)
  );
}

function projectionItem(
  value: unknown,
  projectId: string,
  expectedKind?: ErpProjectionKind,
): value is ErpProjectionItemViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "observationGlobalId",
      "projectionKind",
      "scopeKind",
      "scopeGlobalId",
      "availability",
      "freshness",
      "disposition",
      "sourceSystem",
      "sourceObjectType",
      "sourceObjectId",
      "sourceVersion",
      "sourceModifiedAt",
      "receivedAt",
      "payloadHash",
      "unavailableReasonCode",
      "values",
      "currentTruth",
      "editable",
    ]) ||
    typeof value.projectionKind !== "string" ||
    !kindSet.has(value.projectionKind as ErpProjectionKind)
  )
    return false;
  const kind = value.projectionKind as ErpProjectionKind;
  const definition = sourceDefinitions[kind];
  if (
    (expectedKind !== undefined && kind !== expectedKind) ||
    typeof value.scopeKind !== "string" ||
    !definition.scopes.has(value.scopeKind as ErpProjectionScopeKind) ||
    !uuid(value.observationGlobalId) ||
    !uuid(value.scopeGlobalId) ||
    (value.scopeKind === "project" && value.scopeGlobalId !== projectId) ||
    typeof value.availability !== "string" ||
    !availabilitySet.has(value.availability as ErpProjectionAvailability) ||
    typeof value.freshness !== "string" ||
    !freshnessSet.has(value.freshness as ErpProjectionFreshness) ||
    typeof value.disposition !== "string" ||
    !dispositionSet.has(value.disposition as ErpProjectionDisposition) ||
    value.sourceSystem !== "ERPNEXT" ||
    value.sourceObjectType !== definition.sourceObjectType ||
    !text(value.sourceObjectId, 255) ||
    !(value.sourceVersion === null || text(value.sourceVersion, 255)) ||
    !(value.sourceModifiedAt === null || dateTime(value.sourceModifiedAt)) ||
    !dateTime(value.receivedAt) ||
    !hash(value.payloadHash) ||
    !(
      value.unavailableReasonCode === null || code(value.unavailableReasonCode)
    ) ||
    value.editable !== false ||
    !(value.values === null || projectionValues(kind, value.values)) ||
    !(value.currentTruth === null || currentTruth(kind, value.currentTruth))
  )
    return false;
  const availability = value.availability as ErpProjectionAvailability;
  const disposition = value.disposition as ErpProjectionDisposition;
  if (
    (availability === "unavailable") !== (value.values === null) ||
    (availability === "unavailable") !==
      (value.unavailableReasonCode !== null) ||
    (availability === "available" && value.currentTruth === null) ||
    (disposition === "applied_current" &&
      (availability !== "available" ||
        value.currentTruth?.observationGlobalId !== value.observationGlobalId ||
        value.currentTruth.sourceVersion !== value.sourceVersion ||
        value.currentTruth.sourceModifiedAt !== value.sourceModifiedAt ||
        value.currentTruth.receivedAt !== value.receivedAt ||
        value.currentTruth.payloadHash !== value.payloadHash)) ||
    (disposition === "unavailable_current" && availability !== "unavailable") ||
    (disposition === "synthetic_retained" && availability !== "synthetic")
  )
    return false;
  return true;
}

export function isErpProjectionCollection(
  value: unknown,
  expectedProjectId?: string,
  expectedKind?: ErpProjectionKind,
): value is ErpProjectionCollectionViewModel {
  if (
    !record(value) ||
    !exact(value, [
      "projectGlobalId",
      "accessState",
      "reasonCode",
      "permissions",
      "items",
    ]) ||
    !uuid(value.projectGlobalId) ||
    (expectedProjectId !== undefined &&
      value.projectGlobalId !== expectedProjectId) ||
    !record(value.permissions) ||
    !exact(value.permissions, ["view", "edit", "refresh"]) ||
    value.permissions.edit !== false ||
    value.permissions.refresh !== false ||
    !boundedArray(value.items, 200) ||
    !value.items.every((item) =>
      projectionItem(item, value.projectGlobalId as string, expectedKind),
    )
  )
    return false;
  if (value.accessState === "redacted") {
    if (
      value.reasonCode !== "projection_access_redacted" ||
      value.permissions.view !== false ||
      value.items.length !== 0
    )
      return false;
  } else if (
    value.accessState !== "available" ||
    value.reasonCode !== null ||
    value.permissions.view !== true
  ) {
    return false;
  }
  const identities = value.items.map((item) => {
    return [
      item.projectionKind,
      item.scopeKind,
      item.scopeGlobalId,
      item.sourceObjectId,
      item.observationGlobalId,
    ].join("\u0000");
  });
  return (
    unique(identities) &&
    identities.every((identity, index) => {
      const previous = identities[index - 1];
      return index === 0 || (previous !== undefined && previous < identity);
    })
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function throwIfCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ErpProjectionsRequestCancelledError();
}

export class LiveErpProjectionsDataSource implements ErpProjectionsDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadProjectProjections(
    projectId: string,
    signal: AbortSignal,
    kind?: ErpProjectionKind,
  ): Promise<ErpProjectionCollectionViewModel> {
    if (!uuid(projectId) || (kind !== undefined && !kindSet.has(kind)))
      throw requestNotReady();
    throwIfCancelled(signal);
    try {
      return await this.http.request<ErpProjectionCollectionViewModel>(
        `/projects/${projectId}/erp-projections`,
        { signal },
        {
          query: kind === undefined ? {} : { kind },
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: (value): value is ErpProjectionCollectionViewModel =>
            isErpProjectionCollection(value, projectId, kind),
        },
      );
    } catch (error) {
      throwIfCancelled(signal);
      throw error;
    }
  }
}
