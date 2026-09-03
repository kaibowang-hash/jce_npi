import { NpiHttpClient, NpiTransportError } from "./http";
export interface HistoricalMigrationCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export type HistoricalMigrationFamily =
  | "project"
  | "tooling_mapping"
  | "file_index"
  | "npi_reference";
export type HistoricalMigrationAction = "create" | "link" | "skip" | "blocked";
export type HistoricalMigrationJobState =
  | "queued"
  | "processing"
  | "partially_succeeded"
  | "succeeded"
  | "failed_retryable"
  | "failed_final"
  | "reconciled"
  | "rolled_back"
  | "rollback_denied";

export interface HistoricalMigrationPreviewRow {
  family: HistoricalMigrationFamily;
  ordinal: number;
  sourceKey: string;
  sourceHash: string;
  action: HistoricalMigrationAction;
  targetGlobalId: string | null;
  targetVersion: number | null;
  targetSnapshotHash: string | null;
  differences: readonly Readonly<{
    field: string;
    sourceValue: string | null;
    targetValue: string | null;
  }>[];
  findings: readonly Readonly<{
    code: string;
    field: string;
    message: string;
  }>[];
}

export interface HistoricalMigrationPreview {
  schemaVersion: "historical-migration-preview.v1";
  globalId: string;
  bundleId: string;
  manifestHash: string;
  sourceSha256: string;
  sourceFileRevisionGlobalId: string;
  sourceFileOptimisticVersion: number;
  tenantId: string;
  version: number;
  summary: Readonly<Record<HistoricalMigrationAction, number>>;
  rows: readonly HistoricalMigrationPreviewRow[];
  createdByUserId: string;
  createdAt: string;
  requestId: string;
  traceId: string;
  snapshotHash: string;
}

export interface HistoricalMigrationResult {
  family: HistoricalMigrationFamily | "job";
  sourceKey: string;
  sourceHash?: string;
  action?: HistoricalMigrationAction;
  state:
    | "created"
    | "linked"
    | "skipped"
    | "failed_retryable"
    | "failed_final"
    | "rolled_back"
    | "rollback_denied";
  targetDoctype?: string;
  targetGlobalId?: string;
  targetVersion?: number;
  targetSnapshotHash?: string;
  findingCodes?: readonly string[];
}

export interface HistoricalMigrationCorrectionArtifact {
  schemaVersion: "historical-migration-correction.v1";
  jobGlobalId: string;
  fileName: string;
  sizeBytes: number;
  sha256: string;
  failedRowCount: number;
  executionKeyHash?: string;
  private: true;
}

export interface DownloadedHistoricalMigrationCorrection {
  blob: Blob;
  fileName: string;
}

export interface HistoricalMigrationJob {
  schemaVersion: "historical-migration-job.v1";
  globalId: string;
  batchGlobalId: string;
  previewGlobalId: string;
  previewSnapshotHash: string;
  state: HistoricalMigrationJobState;
  optimisticVersion: number;
  results: readonly HistoricalMigrationResult[];
  queuedAt: string;
  updatedAt: string;
  actorUserId: string;
  requestId: string;
  traceId: string;
  productionContact: false;
  correction?: HistoricalMigrationCorrectionArtifact;
  reconciliation?: Readonly<{
    schemaVersion: "historical-migration-reconciliation.v1";
    observationCount: number;
    mismatchCount: number;
  }>;
  rollback?: Readonly<{
    schemaVersion: "historical-migration-rollback.v1";
    decision: "allowed" | "denied";
  }>;
  snapshotHash: string;
}

export interface HistoricalMigrationWorkspace {
  schemaVersion: "historical-migration-rehearsal.v1";
  mode: "non_production_rehearsal";
  executionEnabled: boolean;
  productionContact: false;
  previews: readonly HistoricalMigrationPreview[];
  jobs: readonly HistoricalMigrationJob[];
}

export interface CreateHistoricalMigrationPreviewCommand {
  tenantId: string;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: number;
  sha256: string;
}

export interface HistoricalMigrationDataSource {
  load(signal: AbortSignal): Promise<HistoricalMigrationWorkspace>;
  createPreview(
    command: CreateHistoricalMigrationPreviewCommand,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationPreview>;
  execute(
    preview: HistoricalMigrationPreview,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationJob>;
  loadJob(jobId: string, signal: AbortSignal): Promise<HistoricalMigrationJob>;
  createCorrection(
    jobId: string,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationCorrectionArtifact>;
  downloadCorrection(
    job: HistoricalMigrationJob,
    context: HistoricalMigrationCommandContext,
  ): Promise<DownloadedHistoricalMigrationCorrection>;
  reconcile(
    job: HistoricalMigrationJob,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationJob>;
  rollback(
    job: HistoricalMigrationJob,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationJob>;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const jobStates = new Set<HistoricalMigrationJobState>([
  "queued",
  "processing",
  "partially_succeeded",
  "succeeded",
  "failed_retryable",
  "failed_final",
  "reconciled",
  "rolled_back",
  "rollback_denied",
]);
const actions = new Set<HistoricalMigrationAction>([
  "create",
  "link",
  "skip",
  "blocked",
]);
const families = new Set<HistoricalMigrationFamily>([
  "project",
  "tooling_mapping",
  "file_index",
  "npi_reference",
]);
const resultStates = new Set([
  "created",
  "linked",
  "skipped",
  "failed_retryable",
  "failed_final",
  "rolled_back",
  "rollback_denied",
]);

function invalidRequest(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
): boolean {
  const expected = new Set(allowed);
  return Object.keys(value).every((key) => expected.has(key));
}

function validFinding(value: unknown): boolean {
  return (
    record(value) &&
    exactKeys(value, ["code", "field", "message"]) &&
    typeof value.code === "string" &&
    typeof value.field === "string" &&
    typeof value.message === "string" &&
    value.code.length <= 128 &&
    value.field.length <= 128 &&
    value.message.length <= 500
  );
}

function validDifference(value: unknown): boolean {
  return (
    record(value) &&
    exactKeys(value, ["field", "sourceValue", "targetValue"]) &&
    typeof value.field === "string" &&
    value.field.length > 0 &&
    value.field.length <= 128 &&
    [value.sourceValue, value.targetValue].every(
      (item) =>
        item === null || (typeof item === "string" && item.length <= 1000),
    )
  );
}

function validPreviewRow(value: unknown): boolean {
  if (!record(value)) return false;
  return (
    exactKeys(value, [
      "family",
      "ordinal",
      "sourceKey",
      "sourceHash",
      "action",
      "targetGlobalId",
      "targetVersion",
      "targetSnapshotHash",
      "differences",
      "findings",
    ]) &&
    typeof value.family === "string" &&
    families.has(value.family as HistoricalMigrationFamily) &&
    Number.isInteger(value.ordinal) &&
    Number(value.ordinal) >= 2 &&
    typeof value.sourceKey === "string" &&
    value.sourceKey.length > 0 &&
    value.sourceKey.length <= 128 &&
    typeof value.sourceHash === "string" &&
    hashPattern.test(value.sourceHash) &&
    typeof value.action === "string" &&
    actions.has(value.action as HistoricalMigrationAction) &&
    (value.targetGlobalId === null ||
      (typeof value.targetGlobalId === "string" &&
        uuidPattern.test(value.targetGlobalId))) &&
    (value.targetVersion === null ||
      (Number.isInteger(value.targetVersion) &&
        Number(value.targetVersion) > 0)) &&
    (value.targetSnapshotHash === null ||
      (typeof value.targetSnapshotHash === "string" &&
        hashPattern.test(value.targetSnapshotHash))) &&
    Array.isArray(value.differences) &&
    value.differences.length <= 12 &&
    value.differences.every(validDifference) &&
    Array.isArray(value.findings) &&
    value.findings.length <= 50 &&
    value.findings.every(validFinding)
  );
}

function validPreview(value: unknown): value is HistoricalMigrationPreview {
  if (!record(value)) return false;
  const summary = value.summary;
  return (
    exactKeys(value, [
      "schemaVersion",
      "globalId",
      "bundleId",
      "manifestHash",
      "sourceSha256",
      "sourceFileRevisionGlobalId",
      "sourceFileOptimisticVersion",
      "tenantId",
      "version",
      "summary",
      "rows",
      "createdByUserId",
      "createdAt",
      "requestId",
      "traceId",
      "snapshotHash",
    ]) &&
    value.schemaVersion === "historical-migration-preview.v1" &&
    [
      value.globalId,
      value.bundleId,
      value.sourceFileRevisionGlobalId,
      value.requestId,
    ].every((item) => typeof item === "string" && uuidPattern.test(item)) &&
    [value.manifestHash, value.sourceSha256, value.snapshotHash].every(
      (item) => typeof item === "string" && hashPattern.test(item),
    ) &&
    Number.isInteger(value.sourceFileOptimisticVersion) &&
    Number.isInteger(value.version) &&
    typeof value.tenantId === "string" &&
    value.tenantId.length > 0 &&
    value.tenantId.length <= 128 &&
    record(summary) &&
    exactKeys(summary, ["create", "link", "skip", "blocked"]) &&
    ["create", "link", "skip", "blocked"].every(
      (key) => Number.isInteger(summary[key]) && Number(summary[key]) >= 0,
    ) &&
    Array.isArray(value.rows) &&
    value.rows.length > 0 &&
    value.rows.length <= 8000 &&
    value.rows.every(validPreviewRow) &&
    typeof value.createdByUserId === "string" &&
    typeof value.createdAt === "string" &&
    typeof value.traceId === "string"
  );
}

function validReconciliationItem(value: unknown): boolean {
  return (
    record(value) &&
    exactKeys(value, [
      "family",
      "sourceKey",
      "targetGlobalId",
      "expectedSnapshotHash",
      "observedSnapshotHash",
      "state",
    ]) &&
    typeof value.family === "string" &&
    families.has(value.family as HistoricalMigrationFamily) &&
    typeof value.sourceKey === "string" &&
    value.sourceKey.length > 0 &&
    value.sourceKey.length <= 128 &&
    typeof value.targetGlobalId === "string" &&
    uuidPattern.test(value.targetGlobalId) &&
    typeof value.expectedSnapshotHash === "string" &&
    hashPattern.test(value.expectedSnapshotHash) &&
    (value.observedSnapshotHash === null ||
      (typeof value.observedSnapshotHash === "string" &&
        hashPattern.test(value.observedSnapshotHash))) &&
    (value.state === "matched" || value.state === "changed")
  );
}

function validResult(value: unknown): boolean {
  if (!record(value)) return false;
  return (
    exactKeys(value, [
      "family",
      "sourceKey",
      "sourceHash",
      "action",
      "state",
      "targetDoctype",
      "targetGlobalId",
      "targetVersion",
      "targetSnapshotHash",
      "findingCodes",
    ]) &&
    typeof value.family === "string" &&
    (value.family === "job" ||
      families.has(value.family as HistoricalMigrationFamily)) &&
    typeof value.sourceKey === "string" &&
    value.sourceKey.length > 0 &&
    value.sourceKey.length <= 128 &&
    typeof value.state === "string" &&
    resultStates.has(value.state) &&
    (value.sourceHash === undefined ||
      (typeof value.sourceHash === "string" &&
        hashPattern.test(value.sourceHash))) &&
    (value.action === undefined ||
      (typeof value.action === "string" &&
        actions.has(value.action as HistoricalMigrationAction))) &&
    (value.targetDoctype === undefined ||
      (typeof value.targetDoctype === "string" &&
        value.targetDoctype.length <= 140)) &&
    (value.targetGlobalId === undefined ||
      (typeof value.targetGlobalId === "string" &&
        uuidPattern.test(value.targetGlobalId))) &&
    (value.targetVersion === undefined ||
      (Number.isInteger(value.targetVersion) &&
        Number(value.targetVersion) > 0)) &&
    (value.targetSnapshotHash === undefined ||
      (typeof value.targetSnapshotHash === "string" &&
        hashPattern.test(value.targetSnapshotHash))) &&
    (value.findingCodes === undefined ||
      (Array.isArray(value.findingCodes) &&
        value.findingCodes.length <= 50 &&
        value.findingCodes.every(
          (item) => typeof item === "string" && item.length <= 128,
        )))
  );
}

function validReconciliation(value: unknown): boolean {
  if (!record(value)) return false;
  return (
    exactKeys(value, [
      "schemaVersion",
      "jobGlobalId",
      "jobSnapshotHash",
      "observationCount",
      "mismatchCount",
      "items",
      "executionKeyHash",
      "createdAt",
    ]) &&
    value.schemaVersion === "historical-migration-reconciliation.v1" &&
    typeof value.jobGlobalId === "string" &&
    uuidPattern.test(value.jobGlobalId) &&
    typeof value.jobSnapshotHash === "string" &&
    hashPattern.test(value.jobSnapshotHash) &&
    Number.isInteger(value.observationCount) &&
    Number(value.observationCount) >= 0 &&
    Number.isInteger(value.mismatchCount) &&
    Number(value.mismatchCount) >= 0 &&
    Array.isArray(value.items) &&
    value.items.length <= 8000 &&
    value.items.every(validReconciliationItem) &&
    typeof value.executionKeyHash === "string" &&
    hashPattern.test(value.executionKeyHash) &&
    typeof value.createdAt === "string"
  );
}

function validRollbackItem(value: unknown): boolean {
  return (
    record(value) &&
    exactKeys(value, [
      "family",
      "sourceKey",
      "targetGlobalId",
      "decision",
      "targetRetained",
    ]) &&
    typeof value.family === "string" &&
    families.has(value.family as HistoricalMigrationFamily) &&
    typeof value.sourceKey === "string" &&
    value.sourceKey.length > 0 &&
    value.sourceKey.length <= 128 &&
    typeof value.targetGlobalId === "string" &&
    uuidPattern.test(value.targetGlobalId) &&
    (value.decision === "logical_binding_rolled_back" ||
      value.decision === "forward_correction_required") &&
    value.targetRetained === true
  );
}

function validRollback(value: unknown): boolean {
  if (!record(value)) return false;
  return (
    exactKeys(value, [
      "schemaVersion",
      "jobGlobalId",
      "decision",
      "items",
      "executionKeyHash",
      "createdAt",
    ]) &&
    value.schemaVersion === "historical-migration-rollback.v1" &&
    typeof value.jobGlobalId === "string" &&
    uuidPattern.test(value.jobGlobalId) &&
    (value.decision === "allowed" || value.decision === "denied") &&
    Array.isArray(value.items) &&
    value.items.length <= 2000 &&
    value.items.every(validRollbackItem) &&
    typeof value.executionKeyHash === "string" &&
    hashPattern.test(value.executionKeyHash) &&
    typeof value.createdAt === "string"
  );
}

function validCorrection(
  value: unknown,
): value is HistoricalMigrationCorrectionArtifact {
  return (
    record(value) &&
    exactKeys(value, [
      "schemaVersion",
      "jobGlobalId",
      "fileName",
      "sizeBytes",
      "sha256",
      "failedRowCount",
      "executionKeyHash",
      "private",
    ]) &&
    value.schemaVersion === "historical-migration-correction.v1" &&
    typeof value.jobGlobalId === "string" &&
    uuidPattern.test(value.jobGlobalId) &&
    typeof value.fileName === "string" &&
    value.fileName.length > 0 &&
    value.fileName.length <= 255 &&
    Number.isInteger(value.sizeBytes) &&
    Number(value.sizeBytes) > 0 &&
    typeof value.sha256 === "string" &&
    hashPattern.test(value.sha256) &&
    Number.isInteger(value.failedRowCount) &&
    Number(value.failedRowCount) > 0 &&
    (value.executionKeyHash === undefined ||
      (typeof value.executionKeyHash === "string" &&
        hashPattern.test(value.executionKeyHash))) &&
    value.private === true
  );
}

function validJob(value: unknown): value is HistoricalMigrationJob {
  if (!record(value)) return false;
  return (
    exactKeys(value, [
      "schemaVersion",
      "globalId",
      "batchGlobalId",
      "previewGlobalId",
      "previewSnapshotHash",
      "state",
      "optimisticVersion",
      "results",
      "queuedAt",
      "updatedAt",
      "actorUserId",
      "requestId",
      "traceId",
      "productionContact",
      "correction",
      "reconciliation",
      "rollback",
      "snapshotHash",
    ]) &&
    value.schemaVersion === "historical-migration-job.v1" &&
    [
      value.globalId,
      value.batchGlobalId,
      value.previewGlobalId,
      value.requestId,
    ].every((item) => typeof item === "string" && uuidPattern.test(item)) &&
    [value.previewSnapshotHash, value.snapshotHash].every(
      (item) => typeof item === "string" && hashPattern.test(item),
    ) &&
    typeof value.state === "string" &&
    jobStates.has(value.state as HistoricalMigrationJobState) &&
    Number.isInteger(value.optimisticVersion) &&
    Number(value.optimisticVersion) > 0 &&
    Array.isArray(value.results) &&
    value.results.length <= 8000 &&
    value.results.every(validResult) &&
    typeof value.queuedAt === "string" &&
    typeof value.updatedAt === "string" &&
    typeof value.actorUserId === "string" &&
    typeof value.traceId === "string" &&
    value.productionContact === false &&
    (value.correction === undefined || validCorrection(value.correction)) &&
    (value.reconciliation === undefined ||
      validReconciliation(value.reconciliation)) &&
    (value.rollback === undefined || validRollback(value.rollback))
  );
}

function validWorkspace(value: unknown): value is HistoricalMigrationWorkspace {
  return (
    record(value) &&
    exactKeys(value, [
      "schemaVersion",
      "mode",
      "executionEnabled",
      "productionContact",
      "previews",
      "jobs",
    ]) &&
    value.schemaVersion === "historical-migration-rehearsal.v1" &&
    value.mode === "non_production_rehearsal" &&
    typeof value.executionEnabled === "boolean" &&
    value.productionContact === false &&
    Array.isArray(value.previews) &&
    value.previews.length <= 50 &&
    value.previews.every(validPreview) &&
    Array.isArray(value.jobs) &&
    value.jobs.length <= 50 &&
    value.jobs.every(validJob)
  );
}

function validContext(context: HistoricalMigrationCommandContext): boolean {
  return context.csrfToken.length >= 32 && context.idempotencyKey.length >= 8;
}

export class LiveHistoricalMigrationDataSource implements HistoricalMigrationDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async load(signal: AbortSignal): Promise<HistoricalMigrationWorkspace> {
    return await this.http.request(
      "/administration/historical-migration-rehearsals",
      { signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: validWorkspace,
      },
    );
  }

  async createPreview(
    command: CreateHistoricalMigrationPreviewCommand,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationPreview> {
    if (
      !validContext(context) ||
      !command.tenantId.trim() ||
      command.tenantId.length > 128 ||
      !uuidPattern.test(command.fileRevisionGlobalId) ||
      !Number.isInteger(command.fileOptimisticVersion) ||
      command.fileOptimisticVersion < 1 ||
      !hashPattern.test(command.sha256)
    )
      throw invalidRequest();
    return await this.command(
      "/administration/historical-migration-rehearsals",
      command,
      context,
      validPreview,
    );
  }

  async execute(
    preview: HistoricalMigrationPreview,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationJob> {
    return await this.command(
      `/administration/historical-migration-rehearsals/${preview.globalId}:execute`,
      {
        expectedVersion: preview.version,
        expectedSnapshotHash: preview.snapshotHash,
      },
      context,
      validJob,
    );
  }

  async loadJob(
    jobId: string,
    signal: AbortSignal,
  ): Promise<HistoricalMigrationJob> {
    if (!uuidPattern.test(jobId)) throw invalidRequest();
    const job = await this.http.request(
      `/administration/historical-migration-jobs/${jobId}`,
      { signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: validJob,
      },
    );
    if (job.globalId !== jobId) throw invalidRequest();
    return job;
  }

  async createCorrection(
    jobId: string,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationCorrectionArtifact> {
    if (!uuidPattern.test(jobId)) throw invalidRequest();
    const artifact = await this.command(
      `/administration/historical-migration-jobs/${jobId}/correction-artifacts`,
      {},
      context,
      validCorrection,
    );
    if (artifact.jobGlobalId !== jobId) throw invalidRequest();
    return artifact;
  }

  async downloadCorrection(
    job: HistoricalMigrationJob,
    context: HistoricalMigrationCommandContext,
  ): Promise<DownloadedHistoricalMigrationCorrection> {
    const artifact = job.correction;
    if (
      artifact?.jobGlobalId !== job.globalId ||
      !validContext(context) ||
      context.signal.aborted
    )
      throw invalidRequest();
    const blob = await this.http.request<Blob>(
      `/administration/historical-migration-jobs/${job.globalId}/correction-artifact:content`,
      {
        method: "POST",
        signal: context.signal,
        body: JSON.stringify({ expectedSnapshotHash: job.snapshotHash }),
        headers: { "Idempotency-Key": context.idempotencyKey },
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        responseType: "blob",
        validate: (value): value is Blob =>
          value instanceof Blob && value.size === artifact.sizeBytes,
        validateResponse: (response) =>
          response.headers
            .get("Content-Type")
            ?.toLowerCase()
            .startsWith("text/csv") === true &&
          response.headers.get("X-Content-Type-Options")?.toLowerCase() ===
            "nosniff" &&
          response.headers
            .get("Content-Disposition")
            ?.toLowerCase()
            .includes("attachment") === true,
      },
    );
    return { blob, fileName: artifact.fileName };
  }

  async reconcile(
    job: HistoricalMigrationJob,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationJob> {
    return await this.versionedJobCommand(job, ":reconcile", context);
  }

  async rollback(
    job: HistoricalMigrationJob,
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationJob> {
    return await this.versionedJobCommand(job, ":rollback", context);
  }

  private async versionedJobCommand(
    job: HistoricalMigrationJob,
    suffix: ":reconcile" | ":rollback",
    context: HistoricalMigrationCommandContext,
  ): Promise<HistoricalMigrationJob> {
    const result = await this.command(
      `/administration/historical-migration-jobs/${job.globalId}${suffix}`,
      {
        expectedVersion: job.optimisticVersion,
        expectedSnapshotHash: job.snapshotHash,
      },
      context,
      validJob,
    );
    if (result.globalId !== job.globalId) throw invalidRequest();
    return result;
  }

  private async command<T>(
    path: string,
    body: object,
    context: HistoricalMigrationCommandContext,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    if (!validContext(context) || context.signal.aborted)
      throw invalidRequest();
    return await this.http.request(
      path,
      {
        method: "POST",
        signal: context.signal,
        body: JSON.stringify(body),
        headers: { "Idempotency-Key": context.idempotencyKey },
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
  }
}
