import { NpiHttpClient, NpiTransportError } from "./http";
import {
  ToolingRequestCancelledError,
  type ToolingCommandContext,
} from "./tooling-data-source";
import {
  isToolingImportBatchCollection,
  isToolingImportBatchCommand,
  isToolingImportBatchDetail,
  isToolingImportCorrectionCommand,
  isToolingImportEligibilityCommand,
  isToolingImportInspectionCommand,
  isToolingImportJob,
  isToolingImportJobCommand,
  isToolingImportMappingCommand,
  isToolingImportPreviewCommand,
  isToolingImportReconciliationCommand,
  isToolingImportRollbackCommand,
  type ToolingImportBatchCollection,
  type ToolingImportBatchDetail,
  type ToolingImportCorrectionArtifact,
  type ToolingImportInspectionRevision,
  type ToolingImportJobSnapshot,
  type ToolingImportMappingRevision,
  type ToolingImportPreviewRevision,
  type ToolingImportReconciliationRevision,
  type ToolingImportSource,
} from "./tooling-import-contract";

export type { ToolingCommandContext } from "./tooling-data-source";
export * from "./tooling-import-contract";

export interface RegisterToolingImportSourceCommand {
  customerScopeId: string;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: number;
  frappeContentHash: string;
  sha256: string;
}

export interface CreateToolingImportMappingCommand {
  inspectionGlobalId: string;
  inspectionSnapshotHash: string;
  templateKey: string;
  reason: string;
}

export interface CreateToolingImportPreviewCommand {
  inspectionGlobalId: string;
  inspectionSnapshotHash: string;
  mappingGlobalId: string;
  mappingSnapshotHash: string;
}

export interface ToolingImportConfirmationInput {
  kind: "image_anchor" | "relationship";
  worksheetName: string;
  sourceRow: number;
  anchorKey?: string | undefined;
  selectedTargetObject: "part_revision" | "tooling_master";
  selectedTargetGlobalId: string;
  selectedTargetSnapshotHash: string;
  reason: string;
}

export interface CreateToolingImportConfirmationCommand {
  expectedVersion: number;
  expectedSnapshotHash: string;
  confirmations: readonly ToolingImportConfirmationInput[];
}

export interface ToolingImportVersionCommand {
  expectedVersion: number;
  expectedSnapshotHash: string;
}

export interface ToolingImportCorrectionInput {
  worksheetName: string;
  sourceRow: number;
  sourceHeader: string;
  correctedValue: string;
}

export interface CreateToolingImportCorrectionCommand extends ToolingImportVersionCommand {
  corrections: readonly ToolingImportCorrectionInput[];
}

export interface RetryToolingImportJobCommand extends ToolingImportVersionCommand {
  correctionArtifactGlobalId: string;
  correctionArtifactSnapshotHash: string;
}

export interface RollbackToolingImportJobCommand extends ToolingImportVersionCommand {
  eligibilityGlobalId: string;
  eligibilitySnapshotHash: string;
}

export interface DownloadedCorrectionArtifact {
  blob: Blob;
  fileName: string;
}

export interface ToolingImportDataSource {
  loadBatches(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ToolingImportBatchCollection>;
  loadBatch(
    projectId: string,
    batchId: string,
    signal: AbortSignal,
  ): Promise<ToolingImportBatchDetail>;
  registerSource(
    projectId: string,
    command: RegisterToolingImportSourceCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportSource>;
  inspect(
    projectId: string,
    batchId: string,
    context: ToolingCommandContext,
  ): Promise<ToolingImportInspectionRevision>;
  createMappingProposal(
    projectId: string,
    batchId: string,
    command: CreateToolingImportMappingCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportMappingRevision>;
  createPreview(
    projectId: string,
    batchId: string,
    command: CreateToolingImportPreviewCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportPreviewRevision>;
  confirmPreview(
    projectId: string,
    batchId: string,
    previewId: string,
    command: CreateToolingImportConfirmationCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportPreviewRevision>;
  execute(
    projectId: string,
    batchId: string,
    previewId: string,
    command: ToolingImportVersionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportJobSnapshot>;
  loadJob(
    projectId: string,
    batchId: string,
    jobId: string,
    signal: AbortSignal,
  ): Promise<ToolingImportJobSnapshot>;
  createCorrectionArtifact(
    projectId: string,
    batchId: string,
    jobId: string,
    command: CreateToolingImportCorrectionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportCorrectionArtifact>;
  downloadCorrectionArtifact(
    projectId: string,
    batchId: string,
    jobId: string,
    artifact: ToolingImportCorrectionArtifact,
    context: ToolingCommandContext,
  ): Promise<DownloadedCorrectionArtifact>;
  retry(
    projectId: string,
    batchId: string,
    jobId: string,
    command: RetryToolingImportJobCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportJobSnapshot>;
  reconcile(
    projectId: string,
    batchId: string,
    jobId: string,
    command: ToolingImportVersionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportReconciliationRevision>;
  evaluateRollback(
    projectId: string,
    batchId: string,
    jobId: string,
    command: ToolingImportVersionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportReconciliationRevision>;
  rollback(
    projectId: string,
    batchId: string,
    jobId: string,
    command: RollbackToolingImportJobCommand,
    context: ToolingCommandContext,
  ): Promise<
    Readonly<{
      job: ToolingImportJobSnapshot;
      rollback: ToolingImportReconciliationRevision;
    }>
  >;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const frappeHashPattern = /^[a-f0-9]{32,128}$/u;
const keyPattern = /^[a-z][a-z0-9_.-]{0,127}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

function requireUuid(value: string): string {
  if (!uuidPattern.test(value)) throw requestNotReady();
  return value;
}

function requireHash(value: string): string {
  if (!hashPattern.test(value)) throw requestNotReady();
  return value;
}

function validContext(value: ToolingCommandContext): boolean {
  return (
    typeof value.csrfToken === "string" &&
    value.csrfToken.length >= 32 &&
    value.csrfToken.length <= 128 &&
    !/[\r\n]/u.test(value.csrfToken) &&
    idempotencyPattern.test(value.idempotencyKey) &&
    value.signal instanceof AbortSignal
  );
}

function validateVersion(value: ToolingImportVersionCommand): boolean {
  return (
    Number.isInteger(value.expectedVersion) &&
    value.expectedVersion >= 1 &&
    hashPattern.test(value.expectedSnapshotHash)
  );
}

function validText(value: string, maximum: number): boolean {
  return (
    value.trim().length > 0 &&
    value.length <= maximum &&
    !value.includes("\u0000") &&
    !/[\r\n]/u.test(value)
  );
}

function cancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ToolingRequestCancelledError();
}

export class LiveToolingImportDataSource implements ToolingImportDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadBatches(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ToolingImportBatchCollection> {
    const expectedProjectId = requireUuid(projectId);
    return await this.query(
      `/projects/${expectedProjectId}/tooling-imports`,
      signal,
      (value): value is ToolingImportBatchCollection =>
        isToolingImportBatchCollection(value) &&
        value.projectGlobalId === expectedProjectId,
    );
  }

  async loadBatch(
    projectId: string,
    batchId: string,
    signal: AbortSignal,
  ): Promise<ToolingImportBatchDetail> {
    const expectedProjectId = requireUuid(projectId);
    const expectedBatchId = requireUuid(batchId);
    return await this.query(
      `/projects/${expectedProjectId}/tooling-imports/${expectedBatchId}`,
      signal,
      (value): value is ToolingImportBatchDetail =>
        isToolingImportBatchDetail(value) &&
        value.projectGlobalId === expectedProjectId &&
        value.batch.batchGlobalId === expectedBatchId,
    );
  }

  async registerSource(
    projectId: string,
    command: RegisterToolingImportSourceCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportSource> {
    const expectedProjectId = requireUuid(projectId);
    if (
      !validText(command.customerScopeId, 128) ||
      !uuidPattern.test(command.fileRevisionGlobalId) ||
      !Number.isInteger(command.fileOptimisticVersion) ||
      command.fileOptimisticVersion < 1 ||
      !frappeHashPattern.test(command.frappeContentHash) ||
      !hashPattern.test(command.sha256)
    )
      throw requestNotReady();
    const result = await this.command(
      `/projects/${expectedProjectId}/tooling-imports`,
      command,
      context,
      isToolingImportBatchCommand,
    );
    if (result.batch.projectGlobalId !== expectedProjectId)
      throw requestNotReady();
    return result.batch;
  }

  async inspect(
    projectId: string,
    batchId: string,
    context: ToolingCommandContext,
  ): Promise<ToolingImportInspectionRevision> {
    const expectedBatchId = requireUuid(batchId);
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${expectedBatchId}/inspections`,
      {},
      context,
      isToolingImportInspectionCommand,
    );
    if (result.inspection.batchGlobalId !== expectedBatchId)
      throw requestNotReady();
    return result.inspection;
  }

  async createMappingProposal(
    projectId: string,
    batchId: string,
    command: CreateToolingImportMappingCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportMappingRevision> {
    const expectedBatchId = requireUuid(batchId);
    if (
      !uuidPattern.test(command.inspectionGlobalId) ||
      !hashPattern.test(command.inspectionSnapshotHash) ||
      !keyPattern.test(command.templateKey) ||
      !validText(command.reason, 1000)
    )
      throw requestNotReady();
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${expectedBatchId}/mapping-proposals`,
      command,
      context,
      isToolingImportMappingCommand,
    );
    if (result.mappingProposal.batchGlobalId !== expectedBatchId)
      throw requestNotReady();
    return result.mappingProposal;
  }

  async createPreview(
    projectId: string,
    batchId: string,
    command: CreateToolingImportPreviewCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportPreviewRevision> {
    const expectedBatchId = requireUuid(batchId);
    if (
      !uuidPattern.test(command.inspectionGlobalId) ||
      !hashPattern.test(command.inspectionSnapshotHash) ||
      !uuidPattern.test(command.mappingGlobalId) ||
      !hashPattern.test(command.mappingSnapshotHash)
    )
      throw requestNotReady();
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${expectedBatchId}/previews`,
      command,
      context,
      isToolingImportPreviewCommand,
    );
    if (result.preview.batchGlobalId !== expectedBatchId)
      throw requestNotReady();
    return result.preview;
  }

  async confirmPreview(
    projectId: string,
    batchId: string,
    previewId: string,
    command: CreateToolingImportConfirmationCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportPreviewRevision> {
    const expectedBatchId = requireUuid(batchId);
    const expectedPreviewId = requireUuid(previewId);
    if (
      !validateVersion(command) ||
      command.confirmations.length < 1 ||
      command.confirmations.length > 100 ||
      !command.confirmations.every(
        (item) =>
          validText(item.worksheetName, 255) &&
          Number.isInteger(item.sourceRow) &&
          item.sourceRow >= 1 &&
          (!item.anchorKey || keyPattern.test(item.anchorKey)) &&
          uuidPattern.test(item.selectedTargetGlobalId) &&
          hashPattern.test(item.selectedTargetSnapshotHash) &&
          validText(item.reason, 1000),
      )
    )
      throw requestNotReady();
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${expectedBatchId}/previews/${expectedPreviewId}/confirmations`,
      command,
      context,
      isToolingImportPreviewCommand,
    );
    if (
      result.preview.batchGlobalId !== expectedBatchId ||
      result.preview.previewGlobalId !== expectedPreviewId
    )
      throw requestNotReady();
    return result.preview;
  }

  async execute(
    projectId: string,
    batchId: string,
    previewId: string,
    command: ToolingImportVersionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportJobSnapshot> {
    const expectedBatchId = requireUuid(batchId);
    const expectedPreviewId = requireUuid(previewId);
    if (!validateVersion(command)) throw requestNotReady();
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${expectedBatchId}/previews/${expectedPreviewId}:execute`,
      command,
      context,
      isToolingImportJobCommand,
    );
    if (
      result.job.batchGlobalId !== expectedBatchId ||
      result.job.previewGlobalId !== expectedPreviewId
    )
      throw requestNotReady();
    return result.job;
  }

  async loadJob(
    projectId: string,
    batchId: string,
    jobId: string,
    signal: AbortSignal,
  ): Promise<ToolingImportJobSnapshot> {
    const expectedBatchId = requireUuid(batchId);
    const expectedJobId = requireUuid(jobId);
    return await this.query(
      `/projects/${requireUuid(projectId)}/tooling-imports/${expectedBatchId}/jobs/${expectedJobId}`,
      signal,
      (value): value is ToolingImportJobSnapshot =>
        isToolingImportJob(value) &&
        value.globalId === expectedJobId &&
        value.batchGlobalId === expectedBatchId,
    );
  }

  async createCorrectionArtifact(
    projectId: string,
    batchId: string,
    jobId: string,
    command: CreateToolingImportCorrectionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportCorrectionArtifact> {
    const expectedBatchId = requireUuid(batchId);
    const expectedJobId = requireUuid(jobId);
    if (
      !validateVersion(command) ||
      command.corrections.length < 1 ||
      command.corrections.length > 5000 ||
      !command.corrections.every(
        (item) =>
          validText(item.worksheetName, 255) &&
          Number.isInteger(item.sourceRow) &&
          item.sourceRow >= 1 &&
          validText(item.sourceHeader, 500) &&
          item.correctedValue.length <= 32_767 &&
          !item.correctedValue.includes("\u0000") &&
          !/[\r\n]/u.test(item.correctedValue),
      )
    )
      throw requestNotReady();
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${expectedBatchId}/jobs/${expectedJobId}/correction-artifacts`,
      command,
      context,
      isToolingImportCorrectionCommand,
    );
    if (
      result.correctionArtifact.batchGlobalId !== expectedBatchId ||
      result.correctionArtifact.jobGlobalId !== expectedJobId
    )
      throw requestNotReady();
    return result.correctionArtifact;
  }

  async downloadCorrectionArtifact(
    projectId: string,
    batchId: string,
    jobId: string,
    artifact: ToolingImportCorrectionArtifact,
    context: ToolingCommandContext,
  ): Promise<DownloadedCorrectionArtifact> {
    if (!validContext(context)) throw requestNotReady();
    const path = `/projects/${requireUuid(projectId)}/tooling-imports/${requireUuid(batchId)}/jobs/${requireUuid(jobId)}/correction-artifacts/${requireUuid(artifact.globalId)}:content`;
    cancelled(context.signal);
    const blob = await this.http.request<Blob>(
      path,
      {
        body: JSON.stringify({
          expectedSnapshotHash: requireHash(artifact.snapshotHash),
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

  async retry(
    projectId: string,
    batchId: string,
    jobId: string,
    command: RetryToolingImportJobCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportJobSnapshot> {
    if (
      !validateVersion(command) ||
      !uuidPattern.test(command.correctionArtifactGlobalId) ||
      !hashPattern.test(command.correctionArtifactSnapshotHash)
    )
      throw requestNotReady();
    return await this.jobCommand(
      projectId,
      batchId,
      jobId,
      ":retry",
      command,
      context,
    );
  }

  async reconcile(
    projectId: string,
    batchId: string,
    jobId: string,
    command: ToolingImportVersionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportReconciliationRevision> {
    if (!validateVersion(command)) throw requestNotReady();
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${requireUuid(batchId)}/jobs/${requireUuid(jobId)}:reconcile`,
      command,
      context,
      isToolingImportReconciliationCommand,
    );
    return result.reconciliation;
  }

  async evaluateRollback(
    projectId: string,
    batchId: string,
    jobId: string,
    command: ToolingImportVersionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingImportReconciliationRevision> {
    if (!validateVersion(command)) throw requestNotReady();
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${requireUuid(batchId)}/jobs/${requireUuid(jobId)}:evaluate-rollback`,
      command,
      context,
      isToolingImportEligibilityCommand,
    );
    return result.rollbackEligibility;
  }

  async rollback(
    projectId: string,
    batchId: string,
    jobId: string,
    command: RollbackToolingImportJobCommand,
    context: ToolingCommandContext,
  ): Promise<
    Readonly<{
      job: ToolingImportJobSnapshot;
      rollback: ToolingImportReconciliationRevision;
    }>
  > {
    if (
      !validateVersion(command) ||
      !uuidPattern.test(command.eligibilityGlobalId) ||
      !hashPattern.test(command.eligibilitySnapshotHash)
    )
      throw requestNotReady();
    return await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${requireUuid(batchId)}/jobs/${requireUuid(jobId)}:rollback`,
      command,
      context,
      isToolingImportRollbackCommand,
    );
  }

  private async jobCommand(
    projectId: string,
    batchId: string,
    jobId: string,
    suffix: ":retry",
    body: object,
    context: ToolingCommandContext,
  ): Promise<ToolingImportJobSnapshot> {
    const expectedBatchId = requireUuid(batchId);
    const expectedJobId = requireUuid(jobId);
    const result = await this.command(
      `/projects/${requireUuid(projectId)}/tooling-imports/${expectedBatchId}/jobs/${expectedJobId}${suffix}`,
      body,
      context,
      isToolingImportJobCommand,
    );
    if (result.job.batchGlobalId !== expectedBatchId) throw requestNotReady();
    return result.job;
  }

  private async query<T>(
    path: string,
    signal: AbortSignal,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    cancelled(signal);
    try {
      return await this.http.request<T>(
        path,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate,
        },
      );
    } catch (error) {
      cancelled(signal);
      throw error;
    }
  }

  private async command<T>(
    path: string,
    body: object,
    context: ToolingCommandContext,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    if (!validContext(context)) throw requestNotReady();
    cancelled(context.signal);
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
      cancelled(context.signal);
      throw error;
    }
  }
}
