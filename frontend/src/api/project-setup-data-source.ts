import { NpiHttpClient, NpiTransportError } from "./http";
import {
  isBaseline,
  isPolicyReference,
  isProjectWorkContextResponse,
} from "./project-work-data-source";
import {
  isProjectPolicyLabelSource,
  type ProjectPolicyLabelSource,
} from "../generated/project-policy-label-sources";
import type {
  ProjectMemberViewModel,
  ProjectRoleAssignmentViewModel,
  ProjectRaciAssignmentViewModel,
  ProjectWbsItemViewModel,
  ProjectWorkContextViewModel,
  ProjectPlanBaselineViewModel,
  ProjectWorkPolicyReference,
  ProjectDependencyViewModel,
} from "../domain/view-models";

export interface SetupPolicy {
  reference: ProjectWorkPolicyReference;
  title: string;
  roleKeys: readonly string[];
  wbsLifecycle: {
    initialStateKey: string;
    states: readonly {
      key: string;
      labelSource: ProjectPolicyLabelSource;
      terminal: boolean;
    }[];
  };
}
export interface SetupOptions {
  projectId: string;
  projectVersion: number;
  policies: readonly SetupPolicy[];
  nextCursor: string | null;
}
type CommandRow<T> = Omit<T, "projectId" | "version">;
interface SetupCommandBase {
  expectedProjectVersion: number;
  workPolicyRef: ProjectWorkPolicyReference;
}
export interface SetupTeamCommand extends SetupCommandBase {
  members: readonly CommandRow<ProjectMemberViewModel>[];
  roleAssignments: readonly CommandRow<ProjectRoleAssignmentViewModel>[];
  substitutions: readonly [];
  raciAssignments: readonly CommandRow<ProjectRaciAssignmentViewModel>[];
}
export interface SetupPlanCommand extends SetupCommandBase {
  items: readonly Omit<
    CommandRow<ProjectWbsItemViewModel>,
    "statusLabelSource"
  >[];
  dependencies: readonly CommandRow<ProjectDependencyViewModel>[];
}
export type SetupCommand =
  | { kind: "roles"; body: SetupCommandBase }
  | { kind: "team"; body: SetupTeamCommand }
  | { kind: "plan"; body: SetupPlanCommand }
  | { kind: "baseline"; body: SetupCommandBase & { label: string } };
export interface SetupResult {
  projectVersion: number;
  context?: ProjectWorkContextViewModel;
  replayed: boolean;
}
export interface ProjectSetupDataSource {
  createDrafts(
    projectId: string,
    command: {
      expectedProjectVersion: number;
      templateCode: string;
      title: string;
    },
    options: { csrfToken: string; idempotencyKey: string; signal: AbortSignal },
  ): Promise<SetupDrafts>;
  loadOptions(
    projectId: string,
    projectVersion: number,
    signal: AbortSignal,
    after?: string,
  ): Promise<SetupOptions>;
  execute(
    projectId: string,
    command: SetupCommand,
    options: { csrfToken: string; idempotencyKey: string; signal: AbortSignal },
  ): Promise<SetupResult>;
}
export interface SetupDrafts {
  projectId: string;
  projectVersion: number;
  templateGlobalId: string;
  policyGlobalId: string;
  templateVersion: 1;
  policyVersion: 1;
  publicationState: "draft";
}

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/u;
const key = /^[a-z][a-z0-9_.-]{0,63}$/u;
const cursor = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}:[1-9][0-9]{0,8}$/u;
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function exact(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return (
    Object.keys(value).length === keys.length &&
    keys.every((name) => Object.hasOwn(value, name))
  );
}
function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}
function bounded(value: unknown, max: number): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= max &&
    !Array.from(value).some(
      (character) =>
        character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127,
    )
  );
}
export function isSetupOptions(value: unknown): value is SetupOptions {
  if (
    !object(value) ||
    !exact(value, ["projectId", "projectVersion", "policies", "nextCursor"]) ||
    typeof value.projectId !== "string" ||
    !uuid.test(value.projectId) ||
    !positive(value.projectVersion) ||
    !Array.isArray(value.policies) ||
    value.policies.length > 50 ||
    !(
      value.nextCursor === null ||
      (typeof value.nextCursor === "string" && cursor.test(value.nextCursor))
    )
  )
    return false;
  const refs = new Set<string>();
  for (const policy of value.policies) {
    if (
      !object(policy) ||
      !exact(policy, ["reference", "title", "roleKeys", "wbsLifecycle"]) ||
      !isPolicyReference(policy.reference) ||
      !bounded(policy.title, 280) ||
      !Array.isArray(policy.roleKeys) ||
      !policy.roleKeys.length ||
      !policy.roleKeys.every(
        (role) => typeof role === "string" && key.test(role),
      ) ||
      new Set(policy.roleKeys).size !== policy.roleKeys.length
    )
      return false;
    const identity = `${policy.reference.globalId}:${String(policy.reference.version)}`;
    if (refs.has(identity)) return false;
    refs.add(identity);
    const lifecycle = policy.wbsLifecycle;
    if (
      !object(lifecycle) ||
      !exact(lifecycle, ["initialStateKey", "states"]) ||
      !Array.isArray(lifecycle.states) ||
      !lifecycle.states.length ||
      !lifecycle.states.every(
        (state) =>
          object(state) &&
          exact(state, ["key", "labelSource", "terminal"]) &&
          typeof state.key === "string" &&
          key.test(state.key) &&
          isProjectPolicyLabelSource(state.labelSource) &&
          typeof state.terminal === "boolean",
      ) ||
      !lifecycle.states.some(
        (state: unknown) =>
          object(state) && state.key === lifecycle.initialStateKey,
      ) ||
      new Set(
        lifecycle.states.map((state: unknown) =>
          object(state) ? state.key : undefined,
        ),
      ).size !== lifecycle.states.length
    )
      return false;
  }
  return (
    value.nextCursor === null ||
    (value.policies.length > 0 && refs.has(value.nextCursor))
  );
}
function ready(projectId: string, version: number): void {
  if (!uuid.test(projectId) || !positive(version))
    throw new NpiTransportError(
      "request_not_ready",
      `client-${crypto.randomUUID()}`,
      "client",
    );
}
function policyMatches(
  left: ProjectWorkPolicyReference | null,
  right: ProjectWorkPolicyReference,
): boolean {
  return (
    left !== null &&
    left.globalId === right.globalId &&
    left.version === right.version &&
    left.snapshotHash === right.snapshotHash
  );
}
function rowsMatch(
  actual: readonly object[],
  expected: readonly object[],
): boolean {
  return expected.every((row) =>
    actual.some((candidate) =>
      Object.entries(row).every(
        ([field, value]) =>
          (candidate as Record<string, unknown>)[field] === value,
      ),
    ),
  );
}
export class LiveProjectSetupDataSource implements ProjectSetupDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}
  async createDrafts(
    projectId: string,
    command: {
      expectedProjectVersion: number;
      templateCode: string;
      title: string;
    },
    options: { csrfToken: string; idempotencyKey: string; signal: AbortSignal },
  ): Promise<SetupDrafts> {
    ready(projectId, command.expectedProjectVersion);
    return this.http.request(
      `/projects/${projectId}:prepare-injection-template`,
      {
        method: "POST",
        body: JSON.stringify(command),
        headers: { "Idempotency-Key": options.idempotencyKey },
        signal: options.signal,
      },
      {
        csrfToken: options.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validateResponse: (response) => response.status === 201,
        validate: (value): value is SetupDrafts =>
          object(value) &&
          exact(value, [
            "projectId",
            "projectVersion",
            "templateGlobalId",
            "policyGlobalId",
            "templateVersion",
            "policyVersion",
            "publicationState",
          ]) &&
          value.projectId === projectId &&
          value.projectVersion === command.expectedProjectVersion &&
          typeof value.templateGlobalId === "string" &&
          uuid.test(value.templateGlobalId) &&
          typeof value.policyGlobalId === "string" &&
          uuid.test(value.policyGlobalId) &&
          value.templateVersion === 1 &&
          value.policyVersion === 1 &&
          value.publicationState === "draft",
      },
    );
  }
  async loadOptions(
    projectId: string,
    version: number,
    signal: AbortSignal,
    after?: string,
  ): Promise<SetupOptions> {
    ready(projectId, version);
    if (after !== undefined && !cursor.test(after))
      throw new NpiTransportError(
        "request_not_ready",
        `client-${crypto.randomUUID()}`,
        "client",
      );
    return this.http.request(
      `/projects/${projectId}/setup-options`,
      { signal },
      {
        query: after ? { after } : undefined,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: (value): value is SetupOptions =>
          isSetupOptions(value) &&
          value.projectId === projectId &&
          value.projectVersion === version,
      },
    );
  }
  async execute(
    projectId: string,
    command: SetupCommand,
    options: { csrfToken: string; idempotencyKey: string; signal: AbortSignal },
  ): Promise<SetupResult> {
    const version = command.body.expectedProjectVersion;
    ready(projectId, version);
    if (
      !isPolicyReference(command.body.workPolicyRef) ||
      !bounded(options.idempotencyKey, 128)
    )
      throw new NpiTransportError(
        "request_not_ready",
        `client-${crypto.randomUUID()}`,
        "client",
      );
    const action =
      command.kind === "roles"
        ? "initialize-work-roles"
        : command.kind === "team"
          ? "configure-team"
          : command.kind === "plan"
            ? "apply-work-plan"
            : "capture-plan-baseline";
    let replayed = false;
    const value = await this.http.request(
      `/projects/${projectId}:${action}`,
      {
        method: "POST",
        signal: options.signal,
        headers: { "Idempotency-Key": options.idempotencyKey },
        body: JSON.stringify(command.body),
      },
      {
        csrfToken: options.csrfToken,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        requireIdempotencyReplay: true,
        validateResponse: (response) => {
          replayed = response.headers.get("Idempotency-Replayed") === "true";
          return response.status === (command.kind === "baseline" ? 201 : 200);
        },
        validate: (
          candidate,
        ): candidate is
          | ProjectWorkContextViewModel
          | ProjectPlanBaselineViewModel => {
          if (command.kind === "baseline")
            return (
              isBaseline(candidate) &&
              candidate.projectId === projectId &&
              candidate.projectVersion === version &&
              candidate.label === command.body.label &&
              policyMatches(candidate.workPolicyRef, command.body.workPolicyRef)
            );
          if (
            !isProjectWorkContextResponse(candidate) ||
            candidate.projectId !== projectId ||
            candidate.projectVersion !== version + 1 ||
            !policyMatches(candidate.workPolicyRef, command.body.workPolicyRef)
          )
            return false;
          if (command.kind === "roles") return candidate.initialized;
          return command.kind === "team"
            ? rowsMatch(candidate.members, command.body.members) &&
                rowsMatch(
                  candidate.roleAssignments,
                  command.body.roleAssignments,
                ) &&
                rowsMatch(
                  candidate.raciAssignments,
                  command.body.raciAssignments,
                )
            : rowsMatch(candidate.wbsItems, command.body.items) &&
                rowsMatch(candidate.dependencies, command.body.dependencies);
        },
      },
    );
    return {
      projectVersion: version + 1,
      ...(isProjectWorkContextResponse(value) ? { context: value } : {}),
      replayed,
    };
  }
}
