import { NpiHttpClient, NpiTransportError } from "./http";
import type { Locale } from "../i18n/runtime";

export interface ControlledPrintSourceIdentity {
  sourceKind: string;
  sourceGlobalId: string;
  sourceVersion: number;
}

export interface ControlledPrintRegistryReferenceViewModel {
  globalId: string;
  registryGlobalId: string;
  version: number;
  snapshotHash: string;
  templateSha256: string;
}

export interface ControlledPrintCapabilityViewModel extends ControlledPrintSourceIdentity {
  available: boolean;
  language: Locale;
  deliveryMode: "controlled_pdf" | null;
  copyState: "not_numbered" | null;
  registry: ControlledPrintRegistryReferenceViewModel | null;
  permissions: Readonly<{
    create: boolean;
    download: boolean;
  }>;
}

export interface ControlledPrintSourceReferenceViewModel extends ControlledPrintSourceIdentity {
  sourceState: string;
  sourceSnapshotHash: string;
}

export interface ControlledPrintOutputViewModel {
  globalId: string;
  fileName: string;
  mimeType: "application/pdf";
  sizeBytes: number;
  sha256: string;
  recordHash: string;
}

export interface ControlledPrintSnapshotViewModel {
  globalId: string;
  version: 1;
  source: ControlledPrintSourceReferenceViewModel;
  registry: ControlledPrintRegistryReferenceViewModel;
  language: Locale;
  deliveryMode: "controlled_pdf";
  copyState: "not_numbered";
  watermarkSource: string;
  actorUserId: string;
  printedAt: string;
  snapshotHash: string;
  verificationPayload: string;
  output: ControlledPrintOutputViewModel;
}

export interface ControlledPrintCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface ControlledPrintCreateResult {
  snapshot: ControlledPrintSnapshotViewModel;
  replayed: boolean;
}

export interface ControlledPrintDownloadResult {
  blob: Blob;
  fileName: string;
  outputHash: string;
  snapshotHash: string;
}

export interface ControlledPrintDataSource {
  loadCapability(
    projectId: string,
    source: ControlledPrintSourceIdentity,
    language: Locale,
    signal: AbortSignal,
  ): Promise<ControlledPrintCapabilityViewModel>;
  createSnapshot(
    projectId: string,
    source: ControlledPrintSourceIdentity,
    language: Locale,
    context: ControlledPrintCommandContext,
  ): Promise<ControlledPrintCreateResult>;
  loadSnapshot(
    projectId: string,
    controlledPrintId: string,
    signal: AbortSignal,
  ): Promise<ControlledPrintSnapshotViewModel>;
  download(
    projectId: string,
    snapshot: ControlledPrintSnapshotViewModel,
    signal: AbortSignal,
  ): Promise<ControlledPrintDownloadResult>;
}

export class ControlledPrintCancelledError extends Error {
  constructor() {
    super("The controlled print request was cancelled.");
    this.name = "ControlledPrintCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const sourceKindPattern = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u;
const fileNamePattern = /^[^/\\]{1,136}[.]pdf$/u;
const timestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function exact(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return (
    actual.length === keys.length && keys.every((key) => actual.includes(key))
  );
}

function boundedString(
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

function uuid(value: unknown): value is string {
  return boundedString(value, 36, 36, uuidPattern);
}

function hash(value: unknown): value is string {
  return boundedString(value, 64, 64, hashPattern);
}

function positive(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= 1 &&
    value <= 2_147_483_647
  );
}

function locale(value: unknown): value is Locale {
  return value === "en" || value === "zh" || value === "zh-TW";
}

function isSourceIdentity(
  value: unknown,
): value is ControlledPrintSourceIdentity {
  if (!record(value)) return false;
  return (
    exact(value, ["sourceKind", "sourceGlobalId", "sourceVersion"]) &&
    boundedString(value.sourceKind, 1, 128, sourceKindPattern) &&
    uuid(value.sourceGlobalId) &&
    positive(value.sourceVersion)
  );
}

function isRegistryReference(
  value: unknown,
): value is ControlledPrintRegistryReferenceViewModel {
  if (!record(value)) return false;
  return (
    exact(value, [
      "globalId",
      "registryGlobalId",
      "version",
      "snapshotHash",
      "templateSha256",
    ]) &&
    uuid(value.globalId) &&
    uuid(value.registryGlobalId) &&
    positive(value.version) &&
    hash(value.snapshotHash) &&
    hash(value.templateSha256)
  );
}

function isPermissions(value: unknown): value is Readonly<{
  create: boolean;
  download: boolean;
}> {
  if (!record(value)) return false;
  return (
    exact(value, ["create", "download"]) &&
    typeof value.create === "boolean" &&
    typeof value.download === "boolean"
  );
}

export function isControlledPrintCapabilityResponse(
  value: unknown,
): value is ControlledPrintCapabilityViewModel {
  if (!record(value)) return false;
  if (
    !exact(value, [
      "available",
      "sourceKind",
      "sourceGlobalId",
      "sourceVersion",
      "language",
      "deliveryMode",
      "copyState",
      "registry",
      "permissions",
    ]) ||
    typeof value.available !== "boolean" ||
    !boundedString(value.sourceKind, 1, 128, sourceKindPattern) ||
    !uuid(value.sourceGlobalId) ||
    !positive(value.sourceVersion) ||
    !locale(value.language) ||
    !isPermissions(value.permissions)
  ) {
    return false;
  }
  if (value.available) {
    return (
      value.deliveryMode === "controlled_pdf" &&
      value.copyState === "not_numbered" &&
      isRegistryReference(value.registry) &&
      value.permissions.create &&
      value.permissions.download
    );
  }
  return (
    value.deliveryMode === null &&
    value.copyState === null &&
    value.registry === null &&
    !value.permissions.create &&
    !value.permissions.download
  );
}

function isSourceReference(
  value: unknown,
): value is ControlledPrintSourceReferenceViewModel {
  if (!record(value)) return false;
  return (
    exact(value, [
      "sourceKind",
      "sourceGlobalId",
      "sourceVersion",
      "sourceState",
      "sourceSnapshotHash",
    ]) &&
    boundedString(value.sourceKind, 1, 128, sourceKindPattern) &&
    uuid(value.sourceGlobalId) &&
    positive(value.sourceVersion) &&
    boundedString(value.sourceState, 1, 128, sourceKindPattern) &&
    hash(value.sourceSnapshotHash)
  );
}

function isOutput(value: unknown): value is ControlledPrintOutputViewModel {
  if (!record(value)) return false;
  return (
    exact(value, [
      "globalId",
      "fileName",
      "mimeType",
      "sizeBytes",
      "sha256",
      "recordHash",
    ]) &&
    uuid(value.globalId) &&
    boundedString(value.fileName, 5, 140, fileNamePattern) &&
    value.mimeType === "application/pdf" &&
    positive(value.sizeBytes) &&
    hash(value.sha256) &&
    hash(value.recordHash)
  );
}

export function isControlledPrintSnapshotResponse(
  value: unknown,
): value is ControlledPrintSnapshotViewModel {
  if (!record(value)) return false;
  if (
    !exact(value, [
      "globalId",
      "version",
      "source",
      "registry",
      "language",
      "deliveryMode",
      "copyState",
      "watermarkSource",
      "actorUserId",
      "printedAt",
      "snapshotHash",
      "verificationPayload",
      "output",
    ]) ||
    !uuid(value.globalId) ||
    value.version !== 1 ||
    !isSourceReference(value.source) ||
    !isRegistryReference(value.registry) ||
    !locale(value.language) ||
    value.deliveryMode !== "controlled_pdf" ||
    value.copyState !== "not_numbered" ||
    !boundedString(value.watermarkSource, 1, 140) ||
    !boundedString(value.actorUserId, 1, 254) ||
    !boundedString(value.printedAt, 20, 40, timestampPattern) ||
    !hash(value.snapshotHash) ||
    !boundedString(value.verificationPayload, 1, 256) ||
    !isOutput(value.output)
  ) {
    return false;
  }
  return (
    value.verificationPayload ===
    `urn:npi:controlled-print:${value.globalId}:${value.snapshotHash}`
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
  if (signal.aborted) throw new ControlledPrintCancelledError();
}

function validContext(context: ControlledPrintCommandContext): boolean {
  return (
    boundedString(context.csrfToken, 16, 512) &&
    boundedString(context.idempotencyKey, 8, 128, idempotencyPattern) &&
    context.signal instanceof AbortSignal
  );
}

function sourceMatches(
  actual: ControlledPrintSourceIdentity,
  expected: ControlledPrintSourceIdentity,
): boolean {
  return (
    actual.sourceKind === expected.sourceKind &&
    actual.sourceGlobalId === expected.sourceGlobalId &&
    actual.sourceVersion === expected.sourceVersion
  );
}

export class LiveControlledPrintDataSource implements ControlledPrintDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadCapability(
    projectId: string,
    source: ControlledPrintSourceIdentity,
    language: Locale,
    signal: AbortSignal,
  ): Promise<ControlledPrintCapabilityViewModel> {
    if (!uuid(projectId) || !isSourceIdentity(source) || !locale(language))
      throw requestNotReady();
    return this.query(
      `/projects/${projectId}/controlled-print/capability`,
      signal,
      {
        language,
        sourceGlobalId: source.sourceGlobalId,
        sourceKind: source.sourceKind,
        sourceVersion: String(source.sourceVersion),
      },
      (value): value is ControlledPrintCapabilityViewModel =>
        isControlledPrintCapabilityResponse(value) &&
        sourceMatches(value, source) &&
        value.language === language,
    );
  }

  async createSnapshot(
    projectId: string,
    source: ControlledPrintSourceIdentity,
    language: Locale,
    context: ControlledPrintCommandContext,
  ): Promise<ControlledPrintCreateResult> {
    if (
      !uuid(projectId) ||
      !isSourceIdentity(source) ||
      !locale(language) ||
      !validContext(context)
    ) {
      throw requestNotReady();
    }
    throwIfCancelled(context.signal);
    const responseMetadata: { replayed?: boolean } = {};
    try {
      const snapshot =
        await this.http.request<ControlledPrintSnapshotViewModel>(
          `/projects/${projectId}/controlled-prints`,
          {
            body: JSON.stringify({ ...source, language }),
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
            validate: (value): value is ControlledPrintSnapshotViewModel =>
              isControlledPrintSnapshotResponse(value) &&
              sourceMatches(value.source, source) &&
              value.language === language,
            validateResponse: (response) => {
              const header = response.headers.get("Idempotency-Replayed");
              if (header !== "true" && header !== "false") return false;
              responseMetadata.replayed = header === "true";
              return true;
            },
          },
        );
      if (responseMetadata.replayed === undefined) throw requestNotReady();
      return { replayed: responseMetadata.replayed, snapshot };
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }

  async loadSnapshot(
    projectId: string,
    controlledPrintId: string,
    signal: AbortSignal,
  ): Promise<ControlledPrintSnapshotViewModel> {
    if (!uuid(projectId) || !uuid(controlledPrintId)) throw requestNotReady();
    return this.query(
      `/projects/${projectId}/controlled-prints/${controlledPrintId}`,
      signal,
      undefined,
      (value): value is ControlledPrintSnapshotViewModel =>
        isControlledPrintSnapshotResponse(value) &&
        value.globalId === controlledPrintId,
    );
  }

  async download(
    projectId: string,
    snapshot: ControlledPrintSnapshotViewModel,
    signal: AbortSignal,
  ): Promise<ControlledPrintDownloadResult> {
    if (!uuid(projectId) || !isControlledPrintSnapshotResponse(snapshot))
      throw requestNotReady();
    throwIfCancelled(signal);
    try {
      const blob = await this.http.request<Blob>(
        `/projects/${projectId}/controlled-prints/${snapshot.globalId}/content`,
        {
          headers: { Accept: "application/pdf" },
          signal,
        },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          responseType: "blob",
          validate: (value): value is Blob =>
            value instanceof Blob &&
            value.type === "application/pdf" &&
            value.size === snapshot.output.sizeBytes,
          validateResponse: (response) => {
            const disposition =
              response.headers.get("Content-Disposition") ?? "";
            const match =
              /^attachment; filename="([A-Za-z0-9._-]{1,140}[.]pdf)"$/u.exec(
                disposition,
              );
            return (
              response.headers.get("Content-Type")?.split(";", 1)[0]?.trim() ===
                "application/pdf" &&
              match?.[1] === snapshot.output.fileName &&
              response.headers.get("X-NPI-Snapshot-Hash") ===
                snapshot.snapshotHash &&
              response.headers.get("X-NPI-Output-Hash") ===
                snapshot.output.sha256
            );
          },
        },
      );
      return {
        blob,
        fileName: snapshot.output.fileName,
        outputHash: snapshot.output.sha256,
        snapshotHash: snapshot.snapshotHash,
      };
    } catch (error) {
      throwIfCancelled(signal);
      throw error;
    }
  }

  private async query<T>(
    path: string,
    signal: AbortSignal,
    query: Readonly<Record<string, string>> | undefined,
    validate: (value: unknown) => value is T,
  ): Promise<T> {
    throwIfCancelled(signal);
    try {
      return await this.http.request<T>(
        path,
        { signal },
        {
          query,
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate,
        },
      );
    } catch (error) {
      throwIfCancelled(signal);
      throw error;
    }
  }
}
