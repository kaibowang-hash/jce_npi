import { NpiHttpClient, NpiTransportError } from "./http";
import type {
  ProjectCockpitViewModel,
  ProjectGateShellViewModel,
  ProjectLifecycleState,
  ProjectReferenceViewModel,
  ProjectType,
} from "../domain/view-models";

export interface ProjectCockpitDataSource {
  load: (
    globalId: string,
    signal: AbortSignal,
  ) => Promise<ProjectCockpitViewModel>;
}

export interface ProjectCreationTemplate {
  globalId: string;
  code: string;
  version: number;
  expectedVersion: number;
  title: string;
  applicableProjectTypes: readonly ProjectType[];
  referenceRules: readonly Readonly<{
    type: ProjectReferenceViewModel["type"];
    required: boolean;
    allowMultiple: boolean;
  }>[];
}

export interface ProjectCreationContext {
  tenantId: string;
  ownerUserId: string;
  templates: readonly ProjectCreationTemplate[];
}

export interface CreateProjectDraftCommand {
  businessCode: string;
  title: string;
  projectType: ProjectType;
  targetSop: string;
  templateGlobalId: string;
  templateVersion: number;
  expectedVersion: number;
}

export interface ProjectCreationCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface ProjectCreationDataSource {
  loadCreationContext(signal: AbortSignal): Promise<ProjectCreationContext>;
  create(
    command: CreateProjectDraftCommand,
    creation: ProjectCreationContext,
    context: ProjectCreationCommandContext,
  ): Promise<ProjectCockpitViewModel>;
}

export class ProjectRequestCancelledError extends Error {
  constructor() {
    super("The project request was cancelled.");
    this.name = "ProjectRequestCancelledError";
  }
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const utcTimestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/u;
const datePattern = /^\d{4}-\d{2}-\d{2}$/u;
const snapshotHashPattern = /^[0-9a-f]{64}$/u;
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/u;
const businessCodePattern = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/u;
const tenantIdPattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]*$/u;
const idempotencyKeyPattern = /^[!-~]{16,255}$/u;
const sourceObjectIdPattern = /^[A-Za-z0-9][A-Za-z0-9._:@/-]*$/u;
const gateKeyPattern = /^[A-Za-z0-9][A-Za-z0-9._-]*$/u;
const projectTypes = new Set<ProjectType>([
  "customer_owned_tool",
  "new_tool",
  "tool_change",
]);
const projectStates = new Set<ProjectLifecycleState>([
  "draft",
  "proposed",
  "active",
  "on_hold",
  "completed",
  "cancelled",
]);
const referenceTypes = new Set<ProjectReferenceViewModel["type"]>([
  "customer",
  "factory",
  "product",
  "part",
  "tooling",
  "order",
]);
const referenceSourceSystems = new Set<
  ProjectReferenceViewModel["sourceSystem"]
>(["NPI_ONE", "ERPNEXT"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function hasExactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = [],
): boolean {
  const allowed = new Set([...required, ...optional]);
  const actual = Object.keys(value);
  return (
    required.every((key) => Object.hasOwn(value, key)) &&
    actual.every((key) => allowed.has(key))
  );
}

function isNonemptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isConstrainedString(
  value: unknown,
  maximumLength: number,
  pattern?: RegExp,
): value is string {
  return (
    isNonemptyString(value) &&
    value.length <= maximumLength &&
    (!pattern || pattern.test(value))
  );
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isUtcTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    utcTimestampPattern.test(value) &&
    !Number.isNaN(Date.parse(value))
  );
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== "string" || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value)
  );
}

function isProjectSource(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["sourceSystem", "editableIn", "syncState"]) &&
    value.sourceSystem === "NPI_ONE" &&
    value.editableIn === "NPI_ONE" &&
    value.syncState === "local"
  );
}

function isProject(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, [
      "globalId",
      "businessCode",
      "title",
      "projectType",
      "state",
      "version",
      "tenantId",
      "ownerUserId",
      "targetSop",
      "createdAt",
      "lastChangedAt",
      "lastChangedBy",
      "source",
    ]) &&
    isUuid(value.globalId) &&
    isConstrainedString(value.businessCode, 64, businessCodePattern) &&
    isConstrainedString(value.title, 140) &&
    typeof value.projectType === "string" &&
    projectTypes.has(value.projectType as ProjectType) &&
    typeof value.state === "string" &&
    projectStates.has(value.state as ProjectLifecycleState) &&
    isPositiveInteger(value.version) &&
    isConstrainedString(value.tenantId, 128, tenantIdPattern) &&
    typeof value.ownerUserId === "string" &&
    value.ownerUserId.length >= 3 &&
    value.ownerUserId.length <= 254 &&
    emailPattern.test(value.ownerUserId) &&
    isIsoDate(value.targetSop) &&
    isUtcTimestamp(value.createdAt) &&
    isUtcTimestamp(value.lastChangedAt) &&
    isConstrainedString(value.lastChangedBy, 254) &&
    isProjectSource(value.source)
  );
}

function isTemplateReference(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["globalId", "code", "version", "snapshotHash"]) &&
    isUuid(value.globalId) &&
    isConstrainedString(value.code, 64, businessCodePattern) &&
    isPositiveInteger(value.version) &&
    typeof value.snapshotHash === "string" &&
    snapshotHashPattern.test(value.snapshotHash)
  );
}

function isProjectReference(
  value: unknown,
): value is ProjectReferenceViewModel {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(
      value,
      ["type", "sourceSystem", "sourceObjectId"],
      ["globalId"],
    ) &&
    typeof value.type === "string" &&
    referenceTypes.has(value.type as ProjectReferenceViewModel["type"]) &&
    typeof value.sourceSystem === "string" &&
    referenceSourceSystems.has(
      value.sourceSystem as ProjectReferenceViewModel["sourceSystem"],
    ) &&
    isConstrainedString(value.sourceObjectId, 128, sourceObjectIdPattern) &&
    (!Object.hasOwn(value, "globalId") || isUuid(value.globalId))
  );
}

function isGate(value: unknown): value is ProjectGateShellViewModel {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, [
      "globalId",
      "key",
      "title",
      "sequence",
      "state",
      "version",
    ]) &&
    isUuid(value.globalId) &&
    isConstrainedString(value.key, 64, gateKeyPattern) &&
    isConstrainedString(value.title, 140) &&
    isPositiveInteger(value.sequence) &&
    value.state === "not_started" &&
    isPositiveInteger(value.version)
  );
}

function isPermissions(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["canView", "canContribute", "canAdminister"]) &&
    value.canView === true &&
    typeof value.canContribute === "boolean" &&
    typeof value.canAdminister === "boolean"
  );
}

export function isProjectCockpitResponse(
  value: unknown,
): value is ProjectCockpitViewModel {
  if (!isRecord(value)) return false;
  if (
    !hasExactKeys(value, [
      "project",
      "templateRef",
      "references",
      "gates",
      "permissions",
    ]) ||
    !isProject(value.project) ||
    !isTemplateReference(value.templateRef) ||
    !Array.isArray(value.references) ||
    value.references.length > 100 ||
    !value.references.every(isProjectReference) ||
    !Array.isArray(value.gates) ||
    value.gates.length < 1 ||
    !value.gates.every(isGate) ||
    !isPermissions(value.permissions)
  ) {
    return false;
  }
  const references = value.references as readonly ProjectReferenceViewModel[];
  const gates = value.gates as readonly ProjectGateShellViewModel[];
  return (
    references.every(
      (reference, index) =>
        references.findIndex(
          (candidate) =>
            candidate.type === reference.type &&
            candidate.sourceSystem === reference.sourceSystem &&
            candidate.sourceObjectId === reference.sourceObjectId &&
            candidate.globalId === reference.globalId,
        ) === index,
    ) &&
    gates.every(
      (gate, index) =>
        (index === 0 || gate.sequence > (gates[index - 1]?.sequence ?? 0)) &&
        gates.findIndex((candidate) => candidate.globalId === gate.globalId) ===
          index &&
        gates.findIndex((candidate) => candidate.key === gate.key) === index,
    )
  );
}

function isCreationTemplate(value: unknown): value is ProjectCreationTemplate {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, [
      "globalId",
      "code",
      "version",
      "expectedVersion",
      "title",
      "applicableProjectTypes",
      "referenceRules",
    ]) &&
    isUuid(value.globalId) &&
    isConstrainedString(value.code, 64, businessCodePattern) &&
    isPositiveInteger(value.version) &&
    isPositiveInteger(value.expectedVersion) &&
    isConstrainedString(value.title, 140) &&
    Array.isArray(value.applicableProjectTypes) &&
    value.applicableProjectTypes.length > 0 &&
    value.applicableProjectTypes.length <= projectTypes.size &&
    value.applicableProjectTypes.every(
      (item) =>
        typeof item === "string" && projectTypes.has(item as ProjectType),
    ) &&
    new Set(value.applicableProjectTypes).size ===
      value.applicableProjectTypes.length &&
    Array.isArray(value.referenceRules) &&
    value.referenceRules.length <= referenceTypes.size &&
    value.referenceRules.every(
      (rule) =>
        isRecord(rule) &&
        hasExactKeys(rule, ["type", "required", "allowMultiple"]) &&
        typeof rule.type === "string" &&
        referenceTypes.has(rule.type as ProjectReferenceViewModel["type"]) &&
        typeof rule.required === "boolean" &&
        typeof rule.allowMultiple === "boolean",
    ) &&
    new Set(
      value.referenceRules.map((rule) =>
        isRecord(rule) && typeof rule.type === "string" ? rule.type : "",
      ),
    ).size === value.referenceRules.length
  );
}

export function isProjectCreationContextResponse(
  value: unknown,
): value is ProjectCreationContext {
  if (!isRecord(value)) return false;
  return (
    hasExactKeys(value, ["tenantId", "ownerUserId", "templates"]) &&
    isConstrainedString(value.tenantId, 128, tenantIdPattern) &&
    typeof value.ownerUserId === "string" &&
    emailPattern.test(value.ownerUserId) &&
    Array.isArray(value.templates) &&
    value.templates.length <= 50 &&
    value.templates.every(isCreationTemplate) &&
    new Set(
      value.templates.map((template) =>
        isRecord(template)
          ? `${template.globalId}:${String(template.version)}`
          : "",
      ),
    ).size === value.templates.length
  );
}

function clientReference(): string {
  return `client-${globalThis.crypto.randomUUID()}`;
}

export class LiveProjectCockpitDataSource implements ProjectCockpitDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async load(
    globalId: string,
    signal: AbortSignal,
  ): Promise<ProjectCockpitViewModel> {
    if (!isUuid(globalId)) {
      throw new NpiTransportError(
        "request_not_ready",
        clientReference(),
        "client",
      );
    }
    try {
      return await this.http.request<ProjectCockpitViewModel>(
        `/projects/${globalId}/cockpit`,
        { signal },
        {
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: isProjectCockpitResponse,
        },
      );
    } catch (error) {
      if (signal.aborted) throw new ProjectRequestCancelledError();
      throw error;
    }
  }
}

export class LiveProjectCreationDataSource implements ProjectCreationDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadCreationContext(
    signal: AbortSignal,
  ): Promise<ProjectCreationContext> {
    try {
      return await this.http.request<ProjectCreationContext>(
        "/projects/creation-context",
        { signal },
        {
          requirePrivateNoStore: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
          validate: isProjectCreationContextResponse,
        },
      );
    } catch (error) {
      if (signal.aborted) throw new ProjectRequestCancelledError();
      throw error;
    }
  }

  async create(
    command: CreateProjectDraftCommand,
    creation: ProjectCreationContext,
    context: ProjectCreationCommandContext,
  ): Promise<ProjectCockpitViewModel> {
    const template = creation.templates.find(
      (candidate) =>
        candidate.globalId === command.templateGlobalId &&
        candidate.version === command.templateVersion &&
        candidate.expectedVersion === command.expectedVersion,
    );
    if (
      !template ||
      !template.applicableProjectTypes.includes(command.projectType) ||
      template.referenceRules.some((rule) => rule.required) ||
      !isConstrainedString(command.businessCode, 64, businessCodePattern) ||
      !isConstrainedString(command.title, 140) ||
      !isIsoDate(command.targetSop) ||
      context.csrfToken.length < 32 ||
      context.csrfToken.length > 128 ||
      !idempotencyKeyPattern.test(context.idempotencyKey) ||
      context.signal.aborted
    ) {
      throw new NpiTransportError(
        "request_not_ready",
        clientReference(),
        "client",
      );
    }
    return this.http.request<ProjectCockpitViewModel>(
      "/projects",
      {
        body: JSON.stringify({
          tenantId: creation.tenantId,
          businessCode: command.businessCode,
          title: command.title,
          projectType: command.projectType,
          ownerUserId: creation.ownerUserId,
          targetSop: command.targetSop,
          templateGlobalId: command.templateGlobalId,
          templateVersion: command.templateVersion,
          expectedVersion: command.expectedVersion,
          references: [],
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
        validate: isProjectCockpitResponse,
      },
    );
  }
}
