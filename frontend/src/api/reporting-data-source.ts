import { NpiHttpClient, NpiTransportError } from "./http";

export type ReportingAvailability =
  | "available"
  | "stale"
  | "partial"
  | "unavailable";
export type GlobalSearchKind =
  | "project"
  | "customer"
  | "part"
  | "tooling"
  | "document"
  | "trial"
  | "defect"
  | "change"
  | "file";
export type PortfolioProjectType =
  | "customer_owned_tool"
  | "new_tool"
  | "tool_change";
export type PortfolioLifecycleState =
  | "draft"
  | "proposed"
  | "active"
  | "on_hold"
  | "completed"
  | "cancelled";

export interface ReportingPage {
  limit: number;
  hasMore: boolean;
  nextCursor: string | null;
}

export interface GlobalSearchItem {
  schemaVersion: 1;
  kind: GlobalSearchKind;
  globalId: string;
  projectGlobalId: string;
  label: string;
  code: string | null;
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  availability: ReportingAvailability;
  reasonCode?: string;
  detailRoute: string;
  version: number;
}

export interface GlobalSearchResponse {
  schemaVersion: 1;
  query: string;
  kinds: readonly GlobalSearchKind[];
  items: readonly GlobalSearchItem[];
  page: ReportingPage;
  permissions: { serverFiltered: true };
}

export interface ReportingFilters {
  customerReferenceKey: string | null;
  factoryReferenceKey: string | null;
  lifecycleState: PortfolioLifecycleState | null;
  ownerUserId: string | null;
  projectType: PortfolioProjectType | null;
  sopMonth: string | null;
}

export interface ProjectPortfolioItem {
  schemaVersion: 1;
  globalId: string;
  businessCode: string;
  title: string;
  projectType: PortfolioProjectType;
  ownerUserId: string;
  targetSop: string;
  lifecycleState: PortfolioLifecycleState;
  version: number;
  customerReferenceKeys: readonly string[];
  factoryReferenceKeys: readonly string[];
  health: {
    state: "unassessed" | "unavailable" | "green" | "yellow" | "red";
    assessedAt: string | null;
    sourceSystem: "NPI_ONE";
  };
  currentGate: {
    globalId: string;
    key: string;
    title: string;
    sequence: number;
    reviewState: "not_started" | "in_review" | "decided" | "requires_review";
    dueDate: string | null;
  } | null;
  work: {
    activeCount: number;
    overdueCount: number;
    blockerCount: number;
    decisionCount: number;
    sourceSystem: "NPI_ONE";
  };
  erp: {
    sourceSystem: "ERPNEXT";
    availability: ReportingAvailability;
    reasonCode: string | null;
    observedKinds: readonly string[];
    freshestAt: string | null;
  };
  detailRoute: string;
}

export interface ProjectPortfolioResponse {
  schemaVersion: 1;
  asOf: string;
  filters: ReportingFilters;
  items: readonly ProjectPortfolioItem[];
  page: ReportingPage;
  permissions: { serverFiltered: true };
}

export interface KpiSeries {
  definition: {
    schemaVersion: 1;
    key:
      | "project_sop_on_time_rate"
      | "project_cycle_time_days"
      | "trial_first_pass_rate"
      | "project_cost_variance_rate";
    labelSource: string;
    valueKind: "percent" | "days";
    numeratorSource: string;
    denominatorSource: string;
    sourceSystem: "NPI_ONE" | "MIXED";
    timeZone: "site";
  };
  availability: ReportingAvailability;
  reasonCode: string;
  points: readonly {
    month: string;
    numerator: number;
    denominator: number;
    value: number;
  }[];
}

export interface KpiTrendResponse {
  schemaVersion: 1;
  fromMonth: string;
  toMonth: string;
  filters: ReportingFilters;
  visibleProjectCount: number;
  series: readonly KpiSeries[];
  permissions: { serverFiltered: true };
}

export interface ConfigurationCapabilityCatalog {
  schemaVersion: 1;
  mode: "read_only_catalog";
  genericWriterAvailable: false;
  activation: {
    identityAuthority: "MICROSOFT_ENTRA";
    sessionAuthority: "FRAPPE";
    authorizationAuthority: "ERPNEXT";
    entraLoginState: "ready" | "action_required";
    selfSignupState: "disabled" | "action_required";
    authorizationIngressState: "enabled" | "disabled";
    authorizationEnforcementState: "enabled" | "disabled";
    authorizationPolicyState: "configured" | "not_configured";
    localUserProvisioningState: "implementation_required";
    erpAuthorizationSenderState: "external_verification_required";
    erpBusinessAdaptersState: "implementation_required";
    supportAdministrationPath: "/app";
  };
  items: readonly {
    key: string;
    labelSource: string;
    mode: "versioned_commands" | "operation_specific";
    route: string;
  }[];
}

export interface ReportingQuery {
  cursor?: string;
  limit?: number;
}

export interface ReportingDataSource {
  search(
    query: string,
    kinds: readonly GlobalSearchKind[],
    page: ReportingQuery,
    signal: AbortSignal,
  ): Promise<GlobalSearchResponse>;
  loadPortfolio(
    filters: Partial<ReportingFilters>,
    page: ReportingQuery,
    signal: AbortSignal,
  ): Promise<ProjectPortfolioResponse>;
  loadKpis(
    fromMonth: string,
    toMonth: string,
    filters: Partial<ReportingFilters>,
    signal: AbortSignal,
  ): Promise<KpiTrendResponse>;
  loadConfiguration(
    signal: AbortSignal,
  ): Promise<ConfigurationCapabilityCatalog>;
}

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const MONTH = /^\d{4}-(?:0[1-9]|1[0-2])$/u;
const DATE = /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$/u;
const EMAIL = /^[^\s@]+@[^\s@]+$/u;
const SEARCH_KINDS = new Set<GlobalSearchKind>([
  "project",
  "customer",
  "part",
  "tooling",
  "document",
  "trial",
  "defect",
  "change",
  "file",
]);
const PROJECT_TYPES = new Set<PortfolioProjectType>([
  "customer_owned_tool",
  "new_tool",
  "tool_change",
]);
const LIFECYCLE = new Set<PortfolioLifecycleState>([
  "draft",
  "proposed",
  "active",
  "on_hold",
  "completed",
  "cancelled",
]);
const AVAILABILITY = new Set<ReportingAvailability>([
  "available",
  "stale",
  "partial",
  "unavailable",
]);

function object(value: unknown): value is Record<string, unknown> {
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

function text(value: unknown, maximum = 1024, minimum = 1): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    !Array.from(value).some((character) => {
      const code = character.charCodeAt(0);
      return code <= 31 || code === 127;
    })
  );
}

function integer(value: unknown, minimum = 0, maximum = 5000): value is number {
  return (
    Number.isSafeInteger(value) &&
    Number(value) >= minimum &&
    Number(value) <= maximum
  );
}

function dateTime(value: unknown): value is string {
  return text(value, 64) && !Number.isNaN(Date.parse(value));
}

function stringOrNull(value: unknown, maximum = 1024): value is string | null {
  return value === null || text(value, maximum);
}

function stringArray(value: unknown, maximum: number): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= maximum &&
    value.every((item) => text(item, 280)) &&
    new Set(value).size === value.length
  );
}

function permissions(value: unknown): value is { serverFiltered: true } {
  return (
    object(value) &&
    exact(value, ["serverFiltered"]) &&
    value.serverFiltered === true
  );
}

function page(value: unknown): value is ReportingPage {
  return (
    object(value) &&
    exact(value, ["limit", "hasMore", "nextCursor"]) &&
    integer(value.limit, 1, 100) &&
    typeof value.hasMore === "boolean" &&
    stringOrNull(value.nextCursor, 1024) &&
    value.hasMore === (value.nextCursor !== null)
  );
}

function filters(value: unknown): value is ReportingFilters {
  return (
    object(value) &&
    exact(value, [
      "customerReferenceKey",
      "factoryReferenceKey",
      "lifecycleState",
      "ownerUserId",
      "projectType",
      "sopMonth",
    ]) &&
    stringOrNull(value.customerReferenceKey, 128) &&
    stringOrNull(value.factoryReferenceKey, 128) &&
    (value.lifecycleState === null ||
      LIFECYCLE.has(value.lifecycleState as PortfolioLifecycleState)) &&
    (value.ownerUserId === null ||
      (text(value.ownerUserId, 254) && EMAIL.test(value.ownerUserId))) &&
    (value.projectType === null ||
      PROJECT_TYPES.has(value.projectType as PortfolioProjectType)) &&
    (value.sopMonth === null ||
      (text(value.sopMonth, 7) && MONTH.test(value.sopMonth)))
  );
}

function validDetailRoute(value: unknown, projectId: string): value is string {
  const root = `/projects/${projectId}`;
  return (
    text(value, 512) &&
    (value === root ||
      value.startsWith(`${root}/`) ||
      value.startsWith(`${root}?`)) &&
    !value.includes("//")
  );
}

function globalSearchItem(value: unknown): value is GlobalSearchItem {
  if (!object(value)) return false;
  const required = [
    "schemaVersion",
    "kind",
    "globalId",
    "projectGlobalId",
    "label",
    "code",
    "sourceSystem",
    "availability",
    "detailRoute",
    "version",
  ];
  const keys = Object.keys(value);
  if (
    !keys.every((key) => [...required, "reasonCode"].includes(key)) ||
    !required.every((key) => Object.hasOwn(value, key))
  )
    return false;
  return (
    value.schemaVersion === 1 &&
    SEARCH_KINDS.has(value.kind as GlobalSearchKind) &&
    text(value.globalId, 140) &&
    text(value.projectGlobalId, 36) &&
    UUID.test(value.projectGlobalId) &&
    text(value.label, 280) &&
    stringOrNull(value.code, 280) &&
    (value.sourceSystem === "NPI_ONE" || value.sourceSystem === "ERPNEXT") &&
    AVAILABILITY.has(value.availability as ReportingAvailability) &&
    (value.reasonCode === undefined || text(value.reasonCode, 128)) &&
    validDetailRoute(value.detailRoute, value.projectGlobalId) &&
    integer(value.version, 1)
  );
}

export function isGlobalSearchResponse(
  value: unknown,
): value is GlobalSearchResponse {
  return (
    object(value) &&
    exact(value, [
      "schemaVersion",
      "query",
      "kinds",
      "items",
      "page",
      "permissions",
    ]) &&
    value.schemaVersion === 1 &&
    text(value.query, 100, 2) &&
    Array.isArray(value.kinds) &&
    value.kinds.length >= 1 &&
    value.kinds.length <= 9 &&
    value.kinds.every((kind) => SEARCH_KINDS.has(kind as GlobalSearchKind)) &&
    new Set(value.kinds).size === value.kinds.length &&
    Array.isArray(value.items) &&
    value.items.length <= 100 &&
    value.items.every(globalSearchItem) &&
    page(value.page) &&
    permissions(value.permissions)
  );
}

function projectGate(value: unknown): boolean {
  return (
    object(value) &&
    exact(value, [
      "globalId",
      "key",
      "title",
      "sequence",
      "reviewState",
      "dueDate",
    ]) &&
    text(value.globalId, 36) &&
    UUID.test(value.globalId) &&
    text(value.key, 64) &&
    text(value.title, 140) &&
    integer(value.sequence, 1) &&
    ["not_started", "in_review", "decided", "requires_review"].includes(
      String(value.reviewState),
    ) &&
    (value.dueDate === null ||
      (text(value.dueDate, 10) && DATE.test(value.dueDate)))
  );
}

function projectPortfolioItem(value: unknown): value is ProjectPortfolioItem {
  if (
    !object(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "businessCode",
      "title",
      "projectType",
      "ownerUserId",
      "targetSop",
      "lifecycleState",
      "version",
      "customerReferenceKeys",
      "factoryReferenceKeys",
      "health",
      "currentGate",
      "work",
      "erp",
      "detailRoute",
    ])
  )
    return false;
  return (
    value.schemaVersion === 1 &&
    text(value.globalId, 36) &&
    UUID.test(value.globalId) &&
    text(value.businessCode, 64) &&
    text(value.title, 140) &&
    PROJECT_TYPES.has(value.projectType as PortfolioProjectType) &&
    text(value.ownerUserId, 254) &&
    EMAIL.test(value.ownerUserId) &&
    text(value.targetSop, 10) &&
    DATE.test(value.targetSop) &&
    LIFECYCLE.has(value.lifecycleState as PortfolioLifecycleState) &&
    integer(value.version, 1) &&
    stringArray(value.customerReferenceKeys, 100) &&
    stringArray(value.factoryReferenceKeys, 100) &&
    object(value.health) &&
    exact(value.health, ["state", "assessedAt", "sourceSystem"]) &&
    ["unassessed", "unavailable", "green", "yellow", "red"].includes(
      String(value.health.state),
    ) &&
    (value.health.assessedAt === null || dateTime(value.health.assessedAt)) &&
    value.health.sourceSystem === "NPI_ONE" &&
    (value.currentGate === null || projectGate(value.currentGate)) &&
    object(value.work) &&
    exact(value.work, [
      "activeCount",
      "overdueCount",
      "blockerCount",
      "decisionCount",
      "sourceSystem",
    ]) &&
    integer(value.work.activeCount) &&
    integer(value.work.overdueCount) &&
    integer(value.work.blockerCount) &&
    integer(value.work.decisionCount) &&
    value.work.sourceSystem === "NPI_ONE" &&
    object(value.erp) &&
    exact(value.erp, [
      "sourceSystem",
      "availability",
      "reasonCode",
      "observedKinds",
      "freshestAt",
    ]) &&
    value.erp.sourceSystem === "ERPNEXT" &&
    AVAILABILITY.has(value.erp.availability as ReportingAvailability) &&
    stringOrNull(value.erp.reasonCode, 128) &&
    stringArray(value.erp.observedKinds, 100) &&
    (value.erp.freshestAt === null || dateTime(value.erp.freshestAt)) &&
    validDetailRoute(value.detailRoute, value.globalId)
  );
}

export function isProjectPortfolioResponse(
  value: unknown,
): value is ProjectPortfolioResponse {
  return (
    object(value) &&
    exact(value, [
      "schemaVersion",
      "asOf",
      "filters",
      "items",
      "page",
      "permissions",
    ]) &&
    value.schemaVersion === 1 &&
    dateTime(value.asOf) &&
    filters(value.filters) &&
    Array.isArray(value.items) &&
    value.items.length <= 100 &&
    value.items.every(projectPortfolioItem) &&
    page(value.page) &&
    permissions(value.permissions)
  );
}

function kpiSeries(value: unknown): value is KpiSeries {
  if (
    !object(value) ||
    !exact(value, ["definition", "availability", "reasonCode", "points"]) ||
    !object(value.definition)
  )
    return false;
  const definition = value.definition;
  const keys = new Set([
    "project_sop_on_time_rate",
    "project_cycle_time_days",
    "trial_first_pass_rate",
    "project_cost_variance_rate",
  ]);
  return (
    exact(definition, [
      "schemaVersion",
      "key",
      "labelSource",
      "valueKind",
      "numeratorSource",
      "denominatorSource",
      "sourceSystem",
      "timeZone",
    ]) &&
    definition.schemaVersion === 1 &&
    keys.has(String(definition.key)) &&
    text(definition.labelSource, 140) &&
    (definition.valueKind === "percent" || definition.valueKind === "days") &&
    text(definition.numeratorSource, 200) &&
    text(definition.denominatorSource, 200) &&
    (definition.sourceSystem === "NPI_ONE" ||
      definition.sourceSystem === "MIXED") &&
    definition.timeZone === "site" &&
    AVAILABILITY.has(value.availability as ReportingAvailability) &&
    text(value.reasonCode, 128) &&
    Array.isArray(value.points) &&
    value.points.length <= 24 &&
    value.points.every(
      (point) =>
        object(point) &&
        exact(point, ["month", "numerator", "denominator", "value"]) &&
        text(point.month, 7) &&
        MONTH.test(point.month) &&
        typeof point.numerator === "number" &&
        Number.isFinite(point.numerator) &&
        typeof point.denominator === "number" &&
        point.denominator > 0 &&
        Number.isFinite(point.denominator) &&
        typeof point.value === "number" &&
        Number.isFinite(point.value),
    ) &&
    (value.availability === "available" || value.points.length === 0)
  );
}

export function isKpiTrendResponse(value: unknown): value is KpiTrendResponse {
  return (
    object(value) &&
    exact(value, [
      "schemaVersion",
      "fromMonth",
      "toMonth",
      "filters",
      "visibleProjectCount",
      "series",
      "permissions",
    ]) &&
    value.schemaVersion === 1 &&
    text(value.fromMonth, 7) &&
    MONTH.test(value.fromMonth) &&
    text(value.toMonth, 7) &&
    MONTH.test(value.toMonth) &&
    value.fromMonth <= value.toMonth &&
    filters(value.filters) &&
    integer(value.visibleProjectCount) &&
    Array.isArray(value.series) &&
    value.series.length === 4 &&
    value.series.every(kpiSeries) &&
    permissions(value.permissions)
  );
}

export function isConfigurationCapabilityCatalog(
  value: unknown,
): value is ConfigurationCapabilityCatalog {
  return (
    object(value) &&
    exact(value, [
      "schemaVersion",
      "mode",
      "genericWriterAvailable",
      "activation",
      "items",
    ]) &&
    value.schemaVersion === 1 &&
    value.mode === "read_only_catalog" &&
    value.genericWriterAvailable === false &&
    object(value.activation) &&
    exact(value.activation, [
      "identityAuthority",
      "sessionAuthority",
      "authorizationAuthority",
      "entraLoginState",
      "selfSignupState",
      "authorizationIngressState",
      "authorizationEnforcementState",
      "authorizationPolicyState",
      "localUserProvisioningState",
      "erpAuthorizationSenderState",
      "erpBusinessAdaptersState",
      "supportAdministrationPath",
    ]) &&
    value.activation.identityAuthority === "MICROSOFT_ENTRA" &&
    value.activation.sessionAuthority === "FRAPPE" &&
    value.activation.authorizationAuthority === "ERPNEXT" &&
    (value.activation.entraLoginState === "ready" ||
      value.activation.entraLoginState === "action_required") &&
    (value.activation.selfSignupState === "disabled" ||
      value.activation.selfSignupState === "action_required") &&
    (value.activation.authorizationIngressState === "enabled" ||
      value.activation.authorizationIngressState === "disabled") &&
    (value.activation.authorizationEnforcementState === "enabled" ||
      value.activation.authorizationEnforcementState === "disabled") &&
    (value.activation.authorizationPolicyState === "configured" ||
      value.activation.authorizationPolicyState === "not_configured") &&
    value.activation.localUserProvisioningState === "implementation_required" &&
    value.activation.erpAuthorizationSenderState ===
      "external_verification_required" &&
    value.activation.erpBusinessAdaptersState === "implementation_required" &&
    value.activation.supportAdministrationPath === "/app" &&
    Array.isArray(value.items) &&
    value.items.length >= 1 &&
    value.items.length <= 50 &&
    value.items.every(
      (item) =>
        object(item) &&
        exact(item, ["key", "labelSource", "mode", "route"]) &&
        text(item.key, 64) &&
        text(item.labelSource, 140) &&
        (item.mode === "versioned_commands" ||
          item.mode === "operation_specific") &&
        text(item.route, 512) &&
        item.route.startsWith("/administration/") &&
        !item.route.includes("//"),
    )
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function validPage(query: ReportingQuery): boolean {
  return (
    (query.cursor === undefined || text(query.cursor, 1024)) &&
    (query.limit === undefined || integer(query.limit, 1, 100))
  );
}

function queryFilters(
  value: Partial<ReportingFilters>,
): Record<string, string> | null {
  const allowed = new Set([
    "customerReferenceKey",
    "factoryReferenceKey",
    "lifecycleState",
    "ownerUserId",
    "projectType",
    "sopMonth",
  ]);
  if (!Object.keys(value).every((key) => allowed.has(key))) return null;
  const query: Record<string, string> = {};
  if (
    value.customerReferenceKey !== undefined &&
    value.customerReferenceKey !== null
  ) {
    if (!text(value.customerReferenceKey, 128)) return null;
    query.customerReferenceKey = value.customerReferenceKey;
  }
  if (
    value.factoryReferenceKey !== undefined &&
    value.factoryReferenceKey !== null
  ) {
    if (!text(value.factoryReferenceKey, 128)) return null;
    query.factoryReferenceKey = value.factoryReferenceKey;
  }
  if (value.lifecycleState !== undefined && value.lifecycleState !== null) {
    if (!LIFECYCLE.has(value.lifecycleState)) return null;
    query.lifecycleState = value.lifecycleState;
  }
  if (value.ownerUserId !== undefined && value.ownerUserId !== null) {
    if (!text(value.ownerUserId, 254) || !EMAIL.test(value.ownerUserId))
      return null;
    query.ownerUserId = value.ownerUserId;
  }
  if (value.projectType !== undefined && value.projectType !== null) {
    if (!PROJECT_TYPES.has(value.projectType)) return null;
    query.projectType = value.projectType;
  }
  if (value.sopMonth !== undefined && value.sopMonth !== null) {
    if (!MONTH.test(value.sopMonth)) return null;
    query.sopMonth = value.sopMonth;
  }
  return query;
}

export class LiveReportingDataSource implements ReportingDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async search(
    query: string,
    kinds: readonly GlobalSearchKind[],
    pageQuery: ReportingQuery,
    signal: AbortSignal,
  ): Promise<GlobalSearchResponse> {
    const normalized = query.trim();
    if (
      !text(normalized, 100, 2) ||
      kinds.length < 1 ||
      kinds.length > 9 ||
      new Set(kinds).size !== kinds.length ||
      !kinds.every((kind) => SEARCH_KINDS.has(kind)) ||
      !validPage(pageQuery)
    )
      throw requestNotReady();
    return this.http.request(
      "/search",
      { signal },
      {
        query: {
          query: normalized,
          kinds: [...kinds].sort().join(","),
          ...(pageQuery.cursor ? { cursor: pageQuery.cursor } : {}),
          ...(pageQuery.limit ? { limit: String(pageQuery.limit) } : {}),
        },
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isGlobalSearchResponse,
      },
    );
  }

  async loadPortfolio(
    filterValue: Partial<ReportingFilters>,
    pageQuery: ReportingQuery,
    signal: AbortSignal,
  ): Promise<ProjectPortfolioResponse> {
    const query = queryFilters(filterValue);
    if (!query || !validPage(pageQuery)) throw requestNotReady();
    if (pageQuery.cursor) query.cursor = pageQuery.cursor;
    if (pageQuery.limit) query.limit = String(pageQuery.limit);
    return this.http.request(
      "/portfolio/projects",
      { signal },
      {
        query,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isProjectPortfolioResponse,
      },
    );
  }

  async loadKpis(
    fromMonth: string,
    toMonth: string,
    filterValue: Partial<ReportingFilters>,
    signal: AbortSignal,
  ): Promise<KpiTrendResponse> {
    const query = queryFilters(filterValue);
    if (
      !query ||
      !MONTH.test(fromMonth) ||
      !MONTH.test(toMonth) ||
      fromMonth > toMonth
    )
      throw requestNotReady();
    query.fromMonth = fromMonth;
    query.toMonth = toMonth;
    return this.http.request(
      "/reports/kpis",
      { signal },
      {
        query,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isKpiTrendResponse,
      },
    );
  }

  async loadConfiguration(
    signal: AbortSignal,
  ): Promise<ConfigurationCapabilityCatalog> {
    return this.http.request(
      "/administration/capabilities",
      { signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isConfigurationCapabilityCatalog,
      },
    );
  }
}
