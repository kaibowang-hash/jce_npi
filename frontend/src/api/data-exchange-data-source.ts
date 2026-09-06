import { NpiHttpClient, NpiTransportError } from "./http";

export type DataExchangeDataset = "project_portfolio.v1" | "kpi_trends.v1";
export type DataExchangeLanguage = "en" | "zh" | "zh-TW";
export type RetentionScope =
  | "tenant"
  | "customer_reference"
  | "regulation_reference";
export type RetentionCategory =
  | "project"
  | "quality"
  | "change"
  | "file"
  | "data_exchange_export"
  | "controlled_print";
export type ArchiveSourceKind =
  | "project"
  | "quality_revision"
  | "change_revision"
  | "file_revision"
  | "data_exchange_export"
  | "controlled_print";

export interface DataExchangeCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface DataExchangeProfile {
  schemaVersion: "data-exchange-export-profile.v1";
  globalId: string;
  version: number;
  datasetId: DataExchangeDataset;
  columns: readonly string[];
  language: DataExchangeLanguage;
  redactionProfile: "internal_report.v1" | "minimum_disclosure.v1";
  query: Readonly<Record<string, string | null>>;
  outputs: readonly ["csv", "xlsx", "pdf", "readme"];
  maxRows: number;
  maxBytes: number;
  publishedByUserId: string;
  publishedAt: string;
  definitionHash: string;
}

export interface DataExchangeExport {
  schemaVersion: "data-exchange-export.v1";
  globalId: string;
  tenantId: string;
  datasetId: DataExchangeDataset;
  profileGlobalId: string;
  profileVersion: number;
  profileHash: string;
  sourceHash: string;
  dataHash: string;
  rowCount: number;
  artifact: Readonly<{
    fileName: string;
    mimeType: "application/zip";
    sizeBytes: number;
    sha256: string;
    manifestSha256: string;
  }>;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  privateFileBound: true;
  recordHash: string;
}

export interface RetentionPolicyVersion {
  schemaVersion: "retention-policy.v1";
  globalId: string;
  version: number;
  scope: RetentionScope;
  scopeReference: string | null;
  effectiveFrom: string;
  effectiveUntil: string | null;
  retentionYears: Readonly<Record<RetentionCategory, number>>;
  publishedByUserId: string;
  publishedAt: string;
  definitionHash: string;
}

export interface RetentionArchiveRecord {
  schemaVersion: "retention-archive-record.v1";
  globalId: string;
  tenantId: string;
  sourceKind: ArchiveSourceKind;
  category: RetentionCategory;
  sourceId: string;
  sourceVersion: number;
  sourceHash: string;
  sourceDate: string;
  sourceSnapshot: Readonly<Record<string, unknown>>;
  policyId: string;
  policyVersion: number;
  policyHash: string;
  retainUntil: string;
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  recordHash: string;
}

export interface DataExchangeWorkspace {
  schemaVersion: "data-exchange.v1";
  mode: "closed_operation_specific";
  routesEnabled: boolean;
  productionContact: false;
  genericWriterAvailable: false;
  automaticDispositionAvailable: false;
  capabilities: readonly Readonly<{
    id: string;
    mode: "specialized_existing" | "report_export_profile";
    exportableHere: boolean;
    route: string;
  }>[];
  profiles: readonly DataExchangeProfile[];
  exports: readonly DataExchangeExport[];
  retentionPolicies: readonly RetentionPolicyVersion[];
  archiveRecords: readonly RetentionArchiveRecord[];
}

export interface PublishProfileCommand {
  globalId: string;
  version: number;
  datasetId: DataExchangeDataset;
  columns: readonly string[];
  language: DataExchangeLanguage;
  redactionProfile: "internal_report.v1" | "minimum_disclosure.v1";
  query: Readonly<Record<string, string | null>>;
  maxRows: number;
  maxBytes: number;
}

export interface PublishRetentionPolicyCommand {
  globalId: string;
  version: number;
  scope: RetentionScope;
  scopeReference: string | null;
  effectiveFrom: string;
  effectiveUntil: string | null;
  retentionYears: Readonly<Record<RetentionCategory, number>>;
}

export interface CreateArchiveCommand {
  globalId: string;
  sourceKind: ArchiveSourceKind;
  sourceId: string;
  sourceVersion: number;
  sourceHash: string;
  policyId: string;
  policyVersion: number;
  policyHash: string;
  scope: RetentionScope;
  scopeReference: string | null;
}

export interface DataExchangeDataSource {
  load(signal: AbortSignal): Promise<DataExchangeWorkspace>;
  publishProfile(
    command: PublishProfileCommand,
    context: DataExchangeCommandContext,
  ): Promise<DataExchangeProfile>;
  createExport(
    profile: DataExchangeProfile,
    context: DataExchangeCommandContext,
  ): Promise<DataExchangeExport>;
  downloadExport(
    value: DataExchangeExport,
    context: DataExchangeCommandContext,
  ): Promise<Blob>;
  publishPolicy(
    command: PublishRetentionPolicyCommand,
    context: DataExchangeCommandContext,
  ): Promise<RetentionPolicyVersion>;
  createArchive(
    command: CreateArchiveCommand,
    context: DataExchangeCommandContext,
  ): Promise<RetentionArchiveRecord>;
}

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const HASH = /^[a-f0-9]{64}$/u;

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function array(value: unknown, maximum = 50): value is unknown[] {
  return Array.isArray(value) && value.length <= maximum;
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

function validProfile(value: unknown): value is DataExchangeProfile {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "globalId",
      "version",
      "datasetId",
      "columns",
      "language",
      "redactionProfile",
      "query",
      "outputs",
      "maxRows",
      "maxBytes",
      "publishedByUserId",
      "publishedAt",
      "definitionHash",
    ]) &&
    value.schemaVersion === "data-exchange-export-profile.v1" &&
    typeof value.globalId === "string" &&
    UUID.test(value.globalId) &&
    Number.isInteger(value.version) &&
    (value.datasetId === "project_portfolio.v1" ||
      value.datasetId === "kpi_trends.v1") &&
    array(value.columns, 10) &&
    value.columns.length > 0 &&
    value.columns.every((item) => typeof item === "string") &&
    (value.language === "en" ||
      value.language === "zh" ||
      value.language === "zh-TW") &&
    (value.redactionProfile === "internal_report.v1" ||
      value.redactionProfile === "minimum_disclosure.v1") &&
    record(value.query) &&
    array(value.outputs, 4) &&
    value.outputs.join("|") === "csv|xlsx|pdf|readme" &&
    Number.isInteger(value.maxRows) &&
    Number(value.maxRows) >= 1 &&
    Number(value.maxRows) <= 5000 &&
    Number.isInteger(value.maxBytes) &&
    typeof value.publishedByUserId === "string" &&
    typeof value.publishedAt === "string" &&
    typeof value.definitionHash === "string" &&
    HASH.test(value.definitionHash)
  );
}

function validExport(value: unknown): value is DataExchangeExport {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "globalId",
      "tenantId",
      "datasetId",
      "profileGlobalId",
      "profileVersion",
      "profileHash",
      "sourceHash",
      "dataHash",
      "rowCount",
      "artifact",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "privateFileBound",
      "recordHash",
    ]) &&
    value.schemaVersion === "data-exchange-export.v1" &&
    typeof value.globalId === "string" &&
    UUID.test(value.globalId) &&
    typeof value.profileGlobalId === "string" &&
    UUID.test(value.profileGlobalId) &&
    typeof value.profileHash === "string" &&
    HASH.test(value.profileHash) &&
    typeof value.sourceHash === "string" &&
    HASH.test(value.sourceHash) &&
    typeof value.dataHash === "string" &&
    HASH.test(value.dataHash) &&
    Number.isInteger(value.rowCount) &&
    Number(value.rowCount) >= 0 &&
    Number(value.rowCount) <= 5000 &&
    record(value.artifact) &&
    value.artifact.mimeType === "application/zip" &&
    typeof value.artifact.sha256 === "string" &&
    HASH.test(value.artifact.sha256) &&
    value.privateFileBound === true &&
    typeof value.recordHash === "string" &&
    HASH.test(value.recordHash)
  );
}

function validPolicy(value: unknown): value is RetentionPolicyVersion {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "globalId",
      "version",
      "scope",
      "scopeReference",
      "effectiveFrom",
      "effectiveUntil",
      "retentionYears",
      "publishedByUserId",
      "publishedAt",
      "definitionHash",
    ]) &&
    value.schemaVersion === "retention-policy.v1" &&
    typeof value.globalId === "string" &&
    UUID.test(value.globalId) &&
    Number.isInteger(value.version) &&
    record(value.retentionYears) &&
    typeof value.definitionHash === "string" &&
    HASH.test(value.definitionHash)
  );
}

function validArchive(value: unknown): value is RetentionArchiveRecord {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "globalId",
      "tenantId",
      "sourceKind",
      "category",
      "sourceId",
      "sourceVersion",
      "sourceHash",
      "sourceDate",
      "sourceSnapshot",
      "policyId",
      "policyVersion",
      "policyHash",
      "retainUntil",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "recordHash",
    ]) &&
    value.schemaVersion === "retention-archive-record.v1" &&
    typeof value.globalId === "string" &&
    UUID.test(value.globalId) &&
    typeof value.sourceHash === "string" &&
    HASH.test(value.sourceHash) &&
    typeof value.policyHash === "string" &&
    HASH.test(value.policyHash) &&
    typeof value.recordHash === "string" &&
    HASH.test(value.recordHash)
  );
}

function validWorkspace(value: unknown): value is DataExchangeWorkspace {
  return (
    record(value) &&
    exact(value, [
      "schemaVersion",
      "mode",
      "routesEnabled",
      "productionContact",
      "genericWriterAvailable",
      "automaticDispositionAvailable",
      "capabilities",
      "profiles",
      "exports",
      "retentionPolicies",
      "archiveRecords",
    ]) &&
    value.schemaVersion === "data-exchange.v1" &&
    value.mode === "closed_operation_specific" &&
    typeof value.routesEnabled === "boolean" &&
    value.productionContact === false &&
    value.genericWriterAvailable === false &&
    value.automaticDispositionAvailable === false &&
    array(value.capabilities, 6) &&
    array(value.profiles) &&
    value.profiles.every(validProfile) &&
    array(value.exports) &&
    value.exports.every(validExport) &&
    array(value.retentionPolicies) &&
    value.retentionPolicies.every(validPolicy) &&
    array(value.archiveRecords) &&
    value.archiveRecords.every(validArchive)
  );
}

function invalidRequest(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function validContext(value: DataExchangeCommandContext): boolean {
  return (
    value.csrfToken.length >= 32 &&
    value.idempotencyKey.length >= 8 &&
    !value.signal.aborted
  );
}

export class LiveDataExchangeDataSource implements DataExchangeDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async load(signal: AbortSignal): Promise<DataExchangeWorkspace> {
    return await this.http.request(
      "/administration/data-exchange",
      { signal },
      this.readOptions(validWorkspace),
    );
  }

  async publishProfile(
    command: PublishProfileCommand,
    context: DataExchangeCommandContext,
  ): Promise<DataExchangeProfile> {
    if (!UUID.test(command.globalId) || !validContext(context))
      throw invalidRequest();
    return await this.command(
      "/administration/data-exchange/profiles",
      command,
      context,
      validProfile,
    );
  }

  async createExport(
    profile: DataExchangeProfile,
    context: DataExchangeCommandContext,
  ): Promise<DataExchangeExport> {
    if (!validProfile(profile) || !validContext(context))
      throw invalidRequest();
    return await this.command(
      "/administration/data-exchange/exports",
      {
        profileId: profile.globalId,
        profileVersion: profile.version,
        profileHash: profile.definitionHash,
      },
      context,
      validExport,
    );
  }

  async downloadExport(
    value: DataExchangeExport,
    context: DataExchangeCommandContext,
  ): Promise<Blob> {
    if (!validExport(value) || !validContext(context)) throw invalidRequest();
    return await this.http.request(
      `/administration/data-exchange/exports/${value.globalId}:content`,
      {
        method: "POST",
        signal: context.signal,
        body: JSON.stringify({ expectedPackageHash: value.artifact.sha256 }),
        headers: { "Idempotency-Key": context.idempotencyKey },
      },
      {
        ...this.readOptions(
          (candidate): candidate is Blob =>
            candidate instanceof Blob &&
            candidate.size === value.artifact.sizeBytes,
        ),
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        responseType: "blob",
        validateResponse: (response) =>
          response.headers
            .get("Content-Type")
            ?.toLowerCase()
            .startsWith("application/zip") === true &&
          response.headers
            .get("Content-Disposition")
            ?.toLowerCase()
            .includes("attachment") === true,
      },
    );
  }

  async publishPolicy(
    command: PublishRetentionPolicyCommand,
    context: DataExchangeCommandContext,
  ): Promise<RetentionPolicyVersion> {
    if (!UUID.test(command.globalId) || !validContext(context))
      throw invalidRequest();
    return await this.command(
      "/administration/data-exchange/retention-policies",
      command,
      context,
      validPolicy,
    );
  }

  async createArchive(
    command: CreateArchiveCommand,
    context: DataExchangeCommandContext,
  ): Promise<RetentionArchiveRecord> {
    if (
      !UUID.test(command.globalId) ||
      !UUID.test(command.sourceId) ||
      !UUID.test(command.policyId) ||
      !validContext(context)
    )
      throw invalidRequest();
    return await this.command(
      "/administration/data-exchange/archive-records",
      command,
      context,
      validArchive,
    );
  }

  private async command<T>(
    path: string,
    body: object,
    context: DataExchangeCommandContext,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    return await this.http.request(
      path,
      {
        method: "POST",
        signal: context.signal,
        body: JSON.stringify(body),
        headers: { "Idempotency-Key": context.idempotencyKey },
      },
      {
        ...this.readOptions(validate),
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
      },
    );
  }

  private readOptions<T>(validate: (value: unknown) => value is T) {
    return {
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
      validate,
    } as const;
  }
}
