import { NpiHttpClient, NpiTransportError } from "./http";

export type ToolingRequirementKind =
  | "new_tool"
  | "customer_owned_intake"
  | "copy_or_additional_set"
  | "modification"
  | "repair"
  | "capacity_need";

export interface ToolingProjectViewModel {
  globalId: string;
  businessCode: string;
  title: string;
}

export interface ToolingSourceViewModel {
  sourceSystem: "NPI_ONE";
  editableIn: "NPI_ONE";
  syncState: "local";
}

export interface EngineeringPartRevisionReferenceViewModel {
  globalId: string;
  partGlobalId: string;
  revisionNumber: number;
  revisionLabel: string;
  snapshotHash: string;
}

export interface EngineeringPartSummaryViewModel {
  globalId: string;
  title: string;
  version: number;
  currentRevision: EngineeringPartRevisionReferenceViewModel;
  source: ToolingSourceViewModel;
}

export interface ToolingRequirementSummaryViewModel {
  globalId: string;
  projectGlobalId: string;
  kind: ToolingRequirementKind;
  title: string;
  reason: string;
  targetPartRevisionGlobalId: string | null;
  targetDate: string | null;
  snapshotHash: string;
}

export interface ToolingMasterSummaryViewModel {
  globalId: string;
  title: string;
  originatingProjectGlobalId: string;
  snapshotHash: string;
  source: ToolingSourceViewModel;
}

export interface ToolingExternalReferenceViewModel {
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
}

export interface ToolingApplicabilitySummaryViewModel {
  globalId: string;
  relationshipGlobalId: string;
  relationshipKeyHash: string;
  projectGlobalId: string;
  toolingMasterGlobalId: string;
  part: EngineeringPartRevisionReferenceViewModel;
  product: ToolingExternalReferenceViewModel | null;
  model: ToolingExternalReferenceViewModel | null;
  version: number;
  predecessorGlobalId: string | null;
  effectiveFrom: string;
  effectiveTo: string | null;
  snapshotHash: string;
}

export interface ToolingPermissionsViewModel {
  view: boolean;
  createPart: boolean;
  createRequirement: boolean;
  createMaster: boolean;
  createApplicability: boolean;
  transitionLifecycle: false;
}

export type ToolingDownstreamReason =
  | "lifecycle_policy_unavailable"
  | "physical_set_not_delivered"
  | "tooling_revision_not_delivered"
  | "trial_not_delivered"
  | "erp_projection_unavailable";

export interface ToolingDownstreamCapabilityViewModel {
  state: "unavailable";
  reasonCode: ToolingDownstreamReason;
}

export interface ToolingCockpitViewModel {
  project: ToolingProjectViewModel;
  permissions: ToolingPermissionsViewModel;
  masters: readonly ToolingMasterSummaryViewModel[];
  requirements: readonly ToolingRequirementSummaryViewModel[];
  parts: readonly EngineeringPartSummaryViewModel[];
  applicability: readonly ToolingApplicabilitySummaryViewModel[];
  downstream: Readonly<{
    lifecycle: ToolingDownstreamCapabilityViewModel;
    revision: ToolingDownstreamCapabilityViewModel;
    physicalSet: ToolingDownstreamCapabilityViewModel;
    trial: ToolingDownstreamCapabilityViewModel;
    erp: ToolingDownstreamCapabilityViewModel;
  }>;
}

export interface ToolingCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface CreateEngineeringPartCommand {
  title: string;
  revisionLabel: string;
  reason: string;
}

export interface CreateEngineeringPartRevisionCommand {
  expectedVersion: number;
  revisionLabel: string;
  title: string;
  reason: string;
}

export interface CreateToolingRequirementCommand {
  kind: ToolingRequirementKind;
  title: string;
  reason: string;
  targetPartRevisionGlobalId?: string | undefined;
  targetDate?: string | undefined;
}

export interface CreateToolingMasterCommand {
  title: string;
}

export interface CreateToolingApplicabilityCommand {
  toolingMasterGlobalId: string;
  partRevisionGlobalId: string;
  product?: ToolingExternalReferenceViewModel | undefined;
  model?: ToolingExternalReferenceViewModel | undefined;
  relationshipGlobalId?: string | undefined;
  expectedVersion?: number | undefined;
  effectiveFrom: string;
  effectiveTo?: string | undefined;
  reason: string;
}

export interface ToolingDataSource {
  loadCockpit(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel>;
  loadMaster(
    projectId: string,
    masterId: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel>;
  createPart(
    projectId: string,
    command: CreateEngineeringPartCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  createPartRevision(
    projectId: string,
    partId: string,
    command: CreateEngineeringPartRevisionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  createRequirement(
    projectId: string,
    command: CreateToolingRequirementCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  createMaster(
    projectId: string,
    command: CreateToolingMasterCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
  createApplicability(
    projectId: string,
    command: CreateToolingApplicabilityCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel>;
}

export class ToolingRequestCancelledError extends Error {
  constructor() {
    super("The Tooling request was cancelled.");
    this.name = "ToolingRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const hashPattern = /^[a-f0-9]{64}$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const idempotencyPattern = /^[A-Za-z0-9._:-]{8,128}$/u;
const referencePattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$/u;
const requirementKinds = new Set<ToolingRequirementKind>([
  "new_tool",
  "customer_owned_intake",
  "copy_or_additional_set",
  "modification",
  "repair",
  "capacity_need",
]);
const downstreamReasons = new Set<ToolingDownstreamReason>([
  "lifecycle_policy_unavailable",
  "physical_set_not_delivered",
  "tooling_revision_not_delivered",
  "trial_not_delivered",
  "erp_projection_unavailable",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return (
    keys.length === required.length && required.every((key) => key in value)
  );
}

function isString(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= maximum
  );
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isHash(value: unknown): value is string {
  return typeof value === "string" && hashPattern.test(value);
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function isDate(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value)
  );
}

function isNullableUuid(value: unknown): value is string | null {
  return value === null || isUuid(value);
}

function isNullableDate(value: unknown): value is string | null {
  return value === null || isDate(value);
}

function isProject(value: unknown): value is ToolingProjectViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "businessCode", "title"]) &&
    isUuid(value.globalId) &&
    isString(value.businessCode, 64) &&
    isString(value.title, 140)
  );
}

function isSource(value: unknown): value is ToolingSourceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["sourceSystem", "editableIn", "syncState"]) &&
    value.sourceSystem === "NPI_ONE" &&
    value.editableIn === "NPI_ONE" &&
    value.syncState === "local"
  );
}

function isRevision(
  value: unknown,
): value is EngineeringPartRevisionReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "partGlobalId",
      "revisionNumber",
      "revisionLabel",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.partGlobalId) &&
    isPositiveInteger(value.revisionNumber) &&
    isString(value.revisionLabel, 40) &&
    isHash(value.snapshotHash)
  );
}

function isPart(value: unknown): value is EngineeringPartSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "title",
      "version",
      "currentRevision",
      "source",
    ]) &&
    isUuid(value.globalId) &&
    isString(value.title, 140) &&
    isPositiveInteger(value.version) &&
    isRevision(value.currentRevision) &&
    value.currentRevision.partGlobalId === value.globalId &&
    isSource(value.source)
  );
}

function isRequirement(
  value: unknown,
): value is ToolingRequirementSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "projectGlobalId",
      "kind",
      "title",
      "reason",
      "targetPartRevisionGlobalId",
      "targetDate",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.projectGlobalId) &&
    typeof value.kind === "string" &&
    requirementKinds.has(value.kind as ToolingRequirementKind) &&
    isString(value.title, 140) &&
    isString(value.reason, 500) &&
    isNullableUuid(value.targetPartRevisionGlobalId) &&
    isNullableDate(value.targetDate) &&
    isHash(value.snapshotHash)
  );
}

function isMaster(value: unknown): value is ToolingMasterSummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "title",
      "originatingProjectGlobalId",
      "snapshotHash",
      "source",
    ]) &&
    isUuid(value.globalId) &&
    isString(value.title, 140) &&
    isUuid(value.originatingProjectGlobalId) &&
    isHash(value.snapshotHash) &&
    isSource(value.source)
  );
}

function isExternalReference(
  value: unknown,
): value is ToolingExternalReferenceViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["sourceSystem", "sourceObjectId"]) &&
    (value.sourceSystem === "NPI_ONE" || value.sourceSystem === "ERPNEXT") &&
    typeof value.sourceObjectId === "string" &&
    referencePattern.test(value.sourceObjectId)
  );
}

function isNullableReference(
  value: unknown,
): value is ToolingExternalReferenceViewModel | null {
  return value === null || isExternalReference(value);
}

function isApplicability(
  value: unknown,
): value is ToolingApplicabilitySummaryViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "globalId",
      "relationshipGlobalId",
      "relationshipKeyHash",
      "projectGlobalId",
      "toolingMasterGlobalId",
      "part",
      "product",
      "model",
      "version",
      "predecessorGlobalId",
      "effectiveFrom",
      "effectiveTo",
      "snapshotHash",
    ]) &&
    isUuid(value.globalId) &&
    isUuid(value.relationshipGlobalId) &&
    isHash(value.relationshipKeyHash) &&
    isUuid(value.projectGlobalId) &&
    isUuid(value.toolingMasterGlobalId) &&
    isRevision(value.part) &&
    isNullableReference(value.product) &&
    isNullableReference(value.model) &&
    isPositiveInteger(value.version) &&
    isNullableUuid(value.predecessorGlobalId) &&
    isDate(value.effectiveFrom) &&
    isNullableDate(value.effectiveTo) &&
    (value.effectiveTo === null || value.effectiveFrom < value.effectiveTo) &&
    isHash(value.snapshotHash)
  );
}

function isPermissions(value: unknown): value is ToolingPermissionsViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "view",
      "createPart",
      "createRequirement",
      "createMaster",
      "createApplicability",
      "transitionLifecycle",
    ]) &&
    value.view === true &&
    typeof value.createPart === "boolean" &&
    typeof value.createRequirement === "boolean" &&
    typeof value.createMaster === "boolean" &&
    typeof value.createApplicability === "boolean" &&
    value.transitionLifecycle === false
  );
}

function isDownstreamCapability(
  value: unknown,
): value is ToolingDownstreamCapabilityViewModel {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["state", "reasonCode"]) &&
    value.state === "unavailable" &&
    typeof value.reasonCode === "string" &&
    downstreamReasons.has(value.reasonCode as ToolingDownstreamReason)
  );
}

function isDownstream(
  value: unknown,
): value is ToolingCockpitViewModel["downstream"] {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "lifecycle",
      "revision",
      "physicalSet",
      "trial",
      "erp",
    ]) &&
    isDownstreamCapability(value.lifecycle) &&
    value.lifecycle.reasonCode === "lifecycle_policy_unavailable" &&
    isDownstreamCapability(value.revision) &&
    value.revision.reasonCode === "tooling_revision_not_delivered" &&
    isDownstreamCapability(value.physicalSet) &&
    value.physicalSet.reasonCode === "physical_set_not_delivered" &&
    isDownstreamCapability(value.trial) &&
    value.trial.reasonCode === "trial_not_delivered" &&
    isDownstreamCapability(value.erp) &&
    value.erp.reasonCode === "erp_projection_unavailable"
  );
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

export function isToolingCockpitResponse(
  value: unknown,
): value is ToolingCockpitViewModel {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "project",
      "permissions",
      "masters",
      "requirements",
      "parts",
      "applicability",
      "downstream",
    ]) ||
    !isProject(value.project) ||
    !isPermissions(value.permissions) ||
    !Array.isArray(value.masters) ||
    value.masters.length > 200 ||
    !value.masters.every(isMaster) ||
    !Array.isArray(value.requirements) ||
    value.requirements.length > 200 ||
    !value.requirements.every(isRequirement) ||
    !Array.isArray(value.parts) ||
    value.parts.length > 500 ||
    !value.parts.every(isPart) ||
    !Array.isArray(value.applicability) ||
    value.applicability.length > 1_000 ||
    !value.applicability.every(isApplicability) ||
    !isDownstream(value.downstream)
  ) {
    return false;
  }
  const project = value.project;
  const masters = value.masters as readonly ToolingMasterSummaryViewModel[];
  const requirements =
    value.requirements as readonly ToolingRequirementSummaryViewModel[];
  const parts = value.parts as readonly EngineeringPartSummaryViewModel[];
  const applicability =
    value.applicability as readonly ToolingApplicabilitySummaryViewModel[];
  const masterIds = new Set(masters.map((item) => item.globalId));
  const partIds = new Set(parts.map((item) => item.globalId));
  return (
    unique(masters.map((item) => item.globalId)) &&
    unique(requirements.map((item) => item.globalId)) &&
    unique(parts.map((item) => item.globalId)) &&
    unique(applicability.map((item) => item.globalId)) &&
    requirements.every((item) => item.projectGlobalId === project.globalId) &&
    applicability.every(
      (item) =>
        item.projectGlobalId === project.globalId &&
        masterIds.has(item.toolingMasterGlobalId) &&
        partIds.has(item.part.partGlobalId),
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

function requireUuid(value: string): string {
  if (!uuidPattern.test(value)) throw requestNotReady();
  return value;
}

function throwIfCancelled(signal: AbortSignal): void {
  if (signal.aborted) throw new ToolingRequestCancelledError();
}

function isCommandContext(value: ToolingCommandContext): boolean {
  return (
    typeof value.csrfToken === "string" &&
    value.csrfToken.length >= 32 &&
    value.csrfToken.length <= 128 &&
    !/[\r\n]/u.test(value.csrfToken) &&
    idempotencyPattern.test(value.idempotencyKey) &&
    value.signal instanceof AbortSignal
  );
}

export class LiveToolingDataSource implements ToolingDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadCockpit(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel> {
    return await this.query(
      `/projects/${requireUuid(projectId)}/tooling`,
      signal,
    );
  }

  async loadMaster(
    projectId: string,
    masterId: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel> {
    return await this.query(
      `/projects/${requireUuid(projectId)}/tooling/${requireUuid(masterId)}`,
      signal,
    );
  }

  async createPart(
    projectId: string,
    command: CreateEngineeringPartCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/parts`,
      command,
      context,
    );
  }

  async createPartRevision(
    projectId: string,
    partId: string,
    command: CreateEngineeringPartRevisionCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/parts/${requireUuid(partId)}/revisions`,
      command,
      context,
    );
  }

  async createRequirement(
    projectId: string,
    command: CreateToolingRequirementCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/tooling-requirements`,
      command,
      context,
    );
  }

  async createMaster(
    projectId: string,
    command: CreateToolingMasterCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/tooling-masters`,
      command,
      context,
    );
  }

  async createApplicability(
    projectId: string,
    command: CreateToolingApplicabilityCommand,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    return await this.command(
      `/projects/${requireUuid(projectId)}/tooling-applicabilities`,
      command,
      context,
    );
  }

  private async query(
    path: string,
    signal: AbortSignal,
  ): Promise<ToolingCockpitViewModel> {
    throwIfCancelled(signal);
    try {
      return await this.http.request<ToolingCockpitViewModel>(
        path,
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: isToolingCockpitResponse,
        },
      );
    } catch (error) {
      throwIfCancelled(signal);
      throw error;
    }
  }

  private async command(
    path: string,
    body: object,
    context: ToolingCommandContext,
  ): Promise<ToolingCockpitViewModel> {
    if (!isCommandContext(context)) throw requestNotReady();
    throwIfCancelled(context.signal);
    try {
      return await this.http.request<ToolingCockpitViewModel>(
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
          validate: isToolingCockpitResponse,
        },
      );
    } catch (error) {
      throwIfCancelled(context.signal);
      throw error;
    }
  }
}
