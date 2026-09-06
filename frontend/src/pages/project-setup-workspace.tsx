import { useEffect, useRef, useState } from "react";
import type {
  ProjectSetupDataSource,
  SetupCommand,
  SetupOptions,
  SetupPlanCommand,
  SetupPolicy,
  SetupTeamCommand,
} from "../api/project-setup-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type {
  ReportWorkspaceDirty,
  RequestWorkspaceTransition,
} from "../app/workspace-navigation";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { ImpactReview, Panel, SemanticStatus } from "../components/primitives";
import type {
  ProjectResponsibility,
  ProjectWorkContextViewModel,
} from "../domain/view-models";
import { governedPolicyLabel, projectResponsibilityLabel } from "../i18n/copy";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";
import "./project-setup-workspace.css";
import {
  InjectionTemplateDraft,
  ProjectRoleDefinitions,
} from "./injection-template-draft";

interface TeamRow {
  id: string;
  email: string;
  role: string;
  from: string;
  to: string;
  responsibility: string;
  raci: ProjectResponsibility;
}
type PlanRow = SetupPlanCommand["items"][number];
interface Operation {
  command: SetupCommand;
  idempotencyKey: string;
}
const newTeamRow = (): TeamRow => ({
  id: crypto.randomUUID(),
  email: "",
  role: "",
  from: "",
  to: "",
  responsibility: "",
  raci: "responsible",
});
const newPlanRow = (state: string): PlanRow => ({
  globalId: crypto.randomUUID(),
  code: "",
  title: "",
  plannedStart: "",
  plannedFinish: "",
  milestone: false,
  statusKey: state,
  progressPercent: 0,
  critical: false,
});

function departmentLabel(
  t: ReturnType<typeof useI18n>["t"],
  role: string,
): string {
  switch (role) {
    case "engineering":
      return t("Engineering");
    case "quality":
      return t("Quality");
    case "purchasing":
      return t("Purchasing");
    case "sales":
      return t("Sales");
    case "warehouse":
      return t("Warehouse");
    case "materials_control":
      return t("Materials control");
    default:
      return role;
  }
}

function injectionTasks(
  t: ReturnType<typeof useI18n>["t"],
): readonly { code: string; title: string }[] {
  return [
    {
      code: "G0.1",
      title: t("Confirm customer requirements and target delivery"),
    },
    { code: "G1.1", title: t("Review moulding feasibility and project risks") },
    {
      code: "G1.2",
      title: t("Confirm supplier capacity and material lead times"),
    },
    { code: "G2.1", title: t("Review DFM and freeze the design inputs") },
    {
      code: "G2.2",
      title: t("Define inspection criteria and sample requirements"),
    },
    { code: "G3.1", title: t("Review tooling design and manufacturing plan") },
    { code: "G3.2", title: t("Prepare material purchasing and arrival plan") },
    {
      code: "G4.1",
      title: t("Verify tooling, machine and trial material readiness"),
    },
    {
      code: "G4.2",
      title: t("Prepare receiving, lot identification and storage"),
    },
    {
      code: "G5.1",
      title: t("Execute trial rounds and close tooling defects"),
    },
    {
      code: "G5.2",
      title: t("Verify dimensions, appearance and sample evidence"),
    },
    { code: "G5.3", title: t("Track customer sample feedback") },
    {
      code: "G6.1",
      title: t("Review pilot material, packaging and capacity readiness"),
    },
    {
      code: "G6.2",
      title: t("Verify process instructions and quality controls"),
    },
    {
      code: "G7.1",
      title: t("Review production handover evidence and open actions"),
    },
    {
      code: "G7.2",
      title: t("Monitor launch issues and record lessons learned"),
    },
  ];
}

export function ProjectSetupWorkspace({
  context,
  dataSource,
  section,
  onChanged,
  reload,
  reportWorkspaceDirty,
  requestWorkspaceTransition,
}: {
  context: ProjectWorkContextViewModel;
  dataSource: ProjectSetupDataSource;
  section: "team" | "plan";
  onChanged: (version: number) => void;
  reload: () => void;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  requestWorkspaceTransition?: RequestWorkspaceTransition | undefined;
}): React.JSX.Element {
  const { t, sessionCommandContext } = useI18n();
  const [editing, setEditing] = useState(false);
  const [catalog, setCatalog] = useState<SetupOptions | null>(null);
  const [catalogFailure, setCatalogFailure] = useState<RequestFailure | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [after, setAfter] = useState<string | undefined>();
  const [selected, setSelected] = useState("");
  const [team, setTeam] = useState<TeamRow[]>([]);
  const [plan, setPlan] = useState<PlanRow[]>([]);
  const [dependencies, setDependencies] = useState<
    SetupPlanCommand["dependencies"]
  >([]);
  const [baselineLabel, setBaselineLabel] = useState("");
  const [mode, setMode] = useState<"roles" | "team" | "plan" | "baseline">(
    section,
  );
  const [review, setReview] = useState<Operation | null>(null);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [retryOperation, setRetryOperation] = useState<Operation | null>(null);
  const [success, setSuccess] = useState(false);
  const [dirty, setDirty] = useState(false);
  const submitLock = useRef(false);
  const commandController = useRef<AbortController | null>(null);
  const trigger = useRef<HTMLDivElement>(null);
  const currentVersion = useRef(context.projectVersion);
  const currentProject = useRef(context.projectId);
  useEffect(() => {
    currentVersion.current = context.projectVersion;
    currentProject.current = context.projectId;
  }, [context.projectVersion, context.projectId]);
  const policy = catalog?.policies.find(
    (item) =>
      `${item.reference.globalId}:${String(item.reference.version)}` ===
      selected,
  );
  const editable = context.permissions.canAdminister;

  useEffect(
    () => () => {
      commandController.current?.abort();
    },
    [],
  );
  useEffect(() => {
    if (!editing || !editable) return;
    const controller = new AbortController();
    void dataSource
      .loadOptions(
        context.projectId,
        context.projectVersion,
        controller.signal,
        after,
      )
      .then((value) => {
        if (controller.signal.aborted) return;
        setCatalog(value);
        if (context.workPolicyRef)
          setSelected(
            `${context.workPolicyRef.globalId}:${String(context.workPolicyRef.version)}`,
          );
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setCatalogFailure(toRequestFailure(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
    };
  }, [
    after,
    attempt,
    context.projectId,
    context.projectVersion,
    context.workPolicyRef,
    dataSource,
    editable,
    editing,
  ]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return;
    reportWorkspaceDirty(
      dirty || pending
        ? {
            objectIdentity: `${context.projectId}:setup`,
            version: String(context.projectVersion),
            returnFocusTarget: () =>
              trigger.current?.querySelector<HTMLElement>(
                "ix-button, button",
              ) ?? null,
          }
        : null,
    );
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [
    context.projectId,
    context.projectVersion,
    dirty,
    pending,
    reportWorkspaceDirty,
  ]);

  function open(next: "roles" | "team" | "plan" | "baseline"): void {
    setLoading(true);
    setAfter(undefined);
    setCatalog(null);
    setSelected("");
    setCatalogFailure(null);
    setMode(next);
    setEditing(true);
    setSuccess(false);
    setFailure(null);
    setRetryOperation(null);
    setReview(null);
    setTeam([newTeamRow()]);
    setPlan(
      context.wbsItems.map((item) => {
        const row = { ...item };
        const fields: string[] = ["projectId", "version", "statusLabelSource"];
        for (const field of fields) Reflect.deleteProperty(row, field);
        return row;
      }),
    );
    setDependencies(
      context.dependencies.map((item) => ({
        globalId: item.globalId,
        predecessorItemId: item.predecessorItemId,
        successorItemId: item.successorItemId,
      })),
    );
    setBaselineLabel("");
    setDirty(false);
  }
  function requestOpen(
    next: "roles" | "team" | "plan" | "baseline",
    target: HTMLElement,
  ): void {
    if (requestWorkspaceTransition)
      requestWorkspaceTransition(() => {
        open(next);
      }, target);
    else open(next);
  }
  function touch(): void {
    setDirty(true);
    setFailure(null);
    setRetryOperation(null);
    setSuccess(false);
  }
  function close(): void {
    setEditing(false);
    setDirty(false);
    setReview(null);
    setRetryOperation(null);
    setFailure(null);
  }
  function updateTeam(id: string, patch: Partial<TeamRow>): void {
    touch();
    setTeam((rows) =>
      rows.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    );
  }
  function updatePlan(id: string, patch: Partial<PlanRow>): void {
    touch();
    setPlan((rows) =>
      rows.map((row) => (row.globalId === id ? { ...row, ...patch } : row)),
    );
  }
  function buildTeam(selectedPolicy: SetupPolicy): SetupTeamCommand {
    const members = new Map<string, SetupTeamCommand["members"][number]>();
    const roles: SetupTeamCommand["roleAssignments"][number][] = [];
    const raci: SetupTeamCommand["raciAssignments"][number][] = [];
    for (const row of team) {
      const email = row.email.trim().toLowerCase();
      let member = members.get(email);
      if (!member) {
        const existing = context.members.find(
          (item) => item.userId.toLowerCase() === email,
        );
        member = existing
          ? {
              globalId: existing.globalId,
              userId: existing.userId,
              effectiveFrom: existing.effectiveFrom,
              ...(existing.effectiveTo
                ? { effectiveTo: existing.effectiveTo }
                : {}),
            }
          : {
              globalId: crypto.randomUUID(),
              userId: email,
              effectiveFrom: row.from,
              ...(row.to ? { effectiveTo: row.to } : {}),
            };
        members.set(email, member);
      }
      const roleId = crypto.randomUUID();
      roles.push({
        globalId: roleId,
        memberId: member.globalId,
        roleKey: row.role,
        effectiveFrom: row.from,
        ...(row.to ? { effectiveTo: row.to } : {}),
      });
      raci.push({
        globalId: crypto.randomUUID(),
        contextType: "project",
        contextId: context.projectId,
        responsibilityKey: row.responsibility.trim(),
        roleAssignmentId: roleId,
        raci: row.raci,
      });
    }
    return {
      expectedProjectVersion: context.projectVersion,
      workPolicyRef: selectedPolicy.reference,
      members: [...members.values()],
      roleAssignments: roles,
      substitutions: [],
      raciAssignments: raci,
    };
  }
  function prepare(): void {
    if (
      !policy ||
      !sessionCommandContext ||
      !editable ||
      loading ||
      catalog?.projectVersion !== context.projectVersion ||
      pending ||
      retryOperation
    )
      return;
    const base = {
      expectedProjectVersion: context.projectVersion,
      workPolicyRef: policy.reference,
    };
    const command: SetupCommand =
      mode === "roles"
        ? { kind: "roles", body: base }
        : mode === "team"
          ? { kind: "team", body: buildTeam(policy) }
          : mode === "plan"
            ? { kind: "plan", body: { ...base, items: plan, dependencies } }
            : {
                kind: "baseline",
                body: { ...base, label: baselineLabel.trim() },
              };
    setReview({
      command,
      idempotencyKey: `project-setup-${crypto.randomUUID()}`,
    });
  }
  async function execute(operation: Operation): Promise<void> {
    if (submitLock.current || !sessionCommandContext || !editable) return;
    submitLock.current = true;
    setPending(true);
    setReview(null);
    setFailure(null);
    setRetryOperation(operation);
    const controller = new AbortController();
    commandController.current = controller;
    const projectId = context.projectId;
    try {
      const result = await dataSource.execute(projectId, operation.command, {
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey: operation.idempotencyKey,
        signal: controller.signal,
      });
      if (controller.signal.aborted || currentProject.current !== projectId)
        return;
      setRetryOperation(null);
      setDirty(false);
      setEditing(false);
      setSuccess(true);
      onChanged(Math.max(currentVersion.current, result.projectVersion));
      reload();
    } catch (error: unknown) {
      if (!controller.signal.aborted && currentProject.current === projectId)
        setFailure(toRequestFailure(error));
    } finally {
      if (!controller.signal.aborted) {
        submitLock.current = false;
        setPending(false);
      }
    }
  }
  const uncertain =
    failure && (failure.kind !== "problem" || failure.problem?.retryable);
  const conflict = failure?.problem?.status === 409;
  const locked = pending || retryOperation !== null;
  if (!editable)
    return (
      <p className="project-setup-note">
        {t(
          "An authorized administrator must configure the Project team and plan.",
        )}
      </p>
    );

  return (
    <section className="project-setup" ref={trigger}>
      {!editing && section === "team" ? (
        <InjectionTemplateDraft
          dataSource={dataSource}
          projectId={context.projectId}
          projectVersion={context.projectVersion}
          reportWorkspaceDirty={reportWorkspaceDirty}
        />
      ) : null}
      {!editing ? (
        <div className="project-setup-toolbar">
          <Button
            type="button"
            onClick={(event) => {
              requestOpen(
                section === "team" && !context.initialized ? "roles" : section,
                event.currentTarget,
              );
            }}
            visual="primary"
          >
            {section === "team"
              ? context.initialized
                ? t("Add team assignments")
                : t("Initialize project roles")
              : context.wbsItems.length
                ? t("Edit project plan")
                : t("Set up project plan")}
          </Button>
          {section === "team" && context.initialized ? (
            <Button
              type="button"
              onClick={(event) => {
                requestOpen("roles", event.currentTarget);
              }}
            >
              {t("Role definitions")}
            </Button>
          ) : null}
          {section === "plan" && context.wbsItems.length > 0 ? (
            <Button
              type="button"
              onClick={(event) => {
                requestOpen("baseline", event.currentTarget);
              }}
            >
              {t("Capture plan baseline")}
            </Button>
          ) : null}
          <a className="table-link" href="/administration">
            {t("Template configuration")}
          </a>
          {success ? (
            <SemanticStatus label={t("Project setup saved")} tone="success" />
          ) : null}
        </div>
      ) : (
        <Panel
          title={
            mode === "roles"
              ? t("Initialize project roles")
              : mode === "team"
                ? t("Team setup")
                : mode === "plan"
                  ? t("Plan setup")
                  : t("Capture plan baseline")
          }
        >
          <p>
            {t(
              "Select a published work policy, assign responsibilities, then save the plan and its baseline.",
            )}
          </p>
          {catalogFailure ? (
            <>
              <RequestFailurePanel failure={catalogFailure} />
              <Button
                type="button"
                onClick={() => {
                  setLoading(true);
                  setCatalogFailure(null);
                  setAttempt((value) => value + 1);
                }}
              >
                {t("Retry")}
              </Button>
            </>
          ) : null}
          {loading ? (
            <p role="status">{t("Loading project setup options")}</p>
          ) : null}
          {!loading && catalog && !catalog.policies.length ? (
            <div role="status">
              <SemanticStatus
                label={t("No published Project work policy")}
                tone="warning"
              />
              <p>
                {t(
                  "An administrator must create and publish a Project Work Policy before team and plan setup.",
                )}
              </p>
              <a
                className="table-link"
                href="/app/npi-project-work-policy-version"
                target="_blank"
                rel="noreferrer"
              >
                {t("Configure project work policies")}
              </a>
            </div>
          ) : null}
          {catalog && catalog.policies.length > 0 && !catalogFailure ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                prepare();
              }}
            >
              <fieldset disabled={locked || loading}>
                <label className="project-setup-policy">
                  <span>{t("Published work policy")}</span>
                  <Select
                    required
                    disabled={context.initialized}
                    value={selected}
                    onChange={(event) => {
                      touch();
                      setSelected(event.currentTarget.value);
                    }}
                  >
                    <option value="">{t("Select published policy")}</option>
                    {catalog.policies.map((item) => (
                      <option
                        data-language-exempt="business-data"
                        key={`${item.reference.globalId}:${String(item.reference.version)}`}
                        value={`${item.reference.globalId}:${String(item.reference.version)}`}
                      >
                        {item.title}
                      </option>
                    ))}
                  </Select>
                </label>
                {catalog.nextCursor ? (
                  <Button
                    type="button"
                    disabled={dirty}
                    onClick={() => {
                      setLoading(true);
                      setSelected("");
                      setAfter(catalog.nextCursor ?? undefined);
                    }}
                  >
                    {t("More policies")}
                  </Button>
                ) : null}
                {context.initialized ? (
                  <p>
                    {t(
                      "This Project keeps its previously bound work policy version.",
                    )}
                  </p>
                ) : null}
                {mode === "roles" && policy ? (
                  <>
                    <p>
                      {t(
                        "Initializes the published role definitions without named members or dates. Existing access and approval permissions remain unchanged.",
                      )}
                    </p>
                    <ProjectRoleDefinitions roleKeys={policy.roleKeys} />
                  </>
                ) : null}
                {mode === "team" && policy ? (
                  <>
                    <p>
                      {t(
                        "Responsibilities do not grant access or Gate approval authority. Existing assignments are retained.",
                      )}
                    </p>
                    <div className="project-setup-grid">
                      <table className="data-table data-table--compact">
                        <thead>
                          <tr>
                            {[
                              t("Member email"),
                              t("Role"),
                              t("Effective from"),
                              t("Effective to"),
                              t("Responsibility key"),
                              t("Responsibility"),
                              t("Actions"),
                            ].map((label) => (
                              <th key={label}>{label}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {team.map((row, index) => (
                            <tr key={row.id}>
                              <td>
                                <TextInput
                                  aria-label={t("Member email {{row}}", {
                                    row: index + 1,
                                  })}
                                  type="email"
                                  required
                                  maxLength={254}
                                  value={row.email}
                                  onChange={(e) => {
                                    updateTeam(row.id, {
                                      email: e.currentTarget.value,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <Select
                                  aria-label={t("Role {{row}}", {
                                    row: index + 1,
                                  })}
                                  required
                                  value={row.role}
                                  onChange={(e) => {
                                    updateTeam(row.id, {
                                      role: e.currentTarget.value,
                                    });
                                  }}
                                >
                                  <option value="">{t("Select role")}</option>
                                  {policy.roleKeys.map((role) => (
                                    <option
                                      data-language-exempt="identifier"
                                      key={role}
                                      value={role}
                                    >
                                      {departmentLabel(t, role)}
                                    </option>
                                  ))}
                                </Select>
                              </td>
                              <td>
                                <TextInput
                                  aria-label={t("Effective from {{row}}", {
                                    row: index + 1,
                                  })}
                                  type="date"
                                  required
                                  value={row.from}
                                  onChange={(e) => {
                                    updateTeam(row.id, {
                                      from: e.currentTarget.value,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <TextInput
                                  aria-label={t("Effective to {{row}}", {
                                    row: index + 1,
                                  })}
                                  type="date"
                                  min={row.from}
                                  value={row.to}
                                  onChange={(e) => {
                                    updateTeam(row.id, {
                                      to: e.currentTarget.value,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <TextInput
                                  aria-label={t("Responsibility key {{row}}", {
                                    row: index + 1,
                                  })}
                                  required
                                  maxLength={64}
                                  pattern="[a-z][a-z0-9_.-]*"
                                  value={row.responsibility}
                                  onChange={(e) => {
                                    updateTeam(row.id, {
                                      responsibility: e.currentTarget.value,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <Select
                                  aria-label={t("Responsibility {{row}}", {
                                    row: index + 1,
                                  })}
                                  value={row.raci}
                                  onChange={(e) => {
                                    updateTeam(row.id, {
                                      raci: e.currentTarget
                                        .value as ProjectResponsibility,
                                    });
                                  }}
                                >
                                  {(
                                    [
                                      "responsible",
                                      "accountable",
                                      "consulted",
                                      "informed",
                                    ] as const
                                  ).map((value) => (
                                    <option key={value} value={value}>
                                      {projectResponsibilityLabel(t, value)}
                                    </option>
                                  ))}
                                </Select>
                              </td>
                              <td>
                                <Button
                                  type="button"
                                  disabled={team.length === 1}
                                  aria-label={t("Remove assignment {{row}}", {
                                    row: index + 1,
                                  })}
                                  onClick={() => {
                                    touch();
                                    setTeam((rows) =>
                                      rows.filter((item) => item.id !== row.id),
                                    );
                                  }}
                                >
                                  {t("Remove")}
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <Button
                      type="button"
                      disabled={team.length >= 500}
                      onClick={() => {
                        touch();
                        setTeam((rows) => [...rows, newTeamRow()]);
                      }}
                    >
                      {t("Add team assignment")}
                    </Button>
                  </>
                ) : null}
                {mode === "plan" && policy ? (
                  <>
                    <div className="project-setup-toolbar">
                      <Button
                        type="button"
                        onClick={() => {
                          touch();
                          setPlan((rows) => [
                            ...rows,
                            newPlanRow(policy.wbsLifecycle.initialStateKey),
                          ]);
                        }}
                      >
                        {t("Add plan item")}
                      </Button>
                      {!context.wbsItems.length && !plan.length ? (
                        <Button
                          type="button"
                          onClick={() => {
                            touch();
                            setPlan(
                              injectionTasks(t).map((item) => ({
                                ...newPlanRow(
                                  policy.wbsLifecycle.initialStateKey,
                                ),
                                ...item,
                              })),
                            );
                          }}
                        >
                          {t("Use injection-moulding task draft")}
                        </Button>
                      ) : null}
                    </div>
                    <p>
                      {t(
                        "Review every owner, date and dependency before saving. Existing plan items are retained.",
                      )}
                    </p>
                    <div className="project-setup-grid">
                      <table className="data-table data-table--compact">
                        <thead>
                          <tr>
                            {[
                              t("Code"),
                              t("Title"),
                              t("Owner role"),
                              t("Planned start"),
                              t("Planned finish"),
                              t("Parent item"),
                              t("State"),
                              t("Progress (%)"),
                              t("Milestone"),
                              t("Actions"),
                            ].map((label) => (
                              <th key={label}>{label}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {plan.map((row, index) => (
                            <tr key={row.globalId}>
                              <td>
                                <TextInput
                                  aria-label={t("Plan code {{row}}", {
                                    row: index + 1,
                                  })}
                                  required
                                  maxLength={64}
                                  value={row.code}
                                  onChange={(e) => {
                                    updatePlan(row.globalId, {
                                      code: e.currentTarget.value,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <TextInput
                                  aria-label={t("Plan title {{row}}", {
                                    row: index + 1,
                                  })}
                                  required
                                  maxLength={280}
                                  value={row.title}
                                  onChange={(e) => {
                                    updatePlan(row.globalId, {
                                      title: e.currentTarget.value,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <Select
                                  aria-label={t("Plan owner {{row}}", {
                                    row: index + 1,
                                  })}
                                  value={row.ownerRoleAssignmentId ?? ""}
                                  onChange={(e) => {
                                    const value = e.currentTarget.value;
                                    touch();
                                    setPlan((rows) =>
                                      rows.map((item) => {
                                        if (item.globalId !== row.globalId)
                                          return item;
                                        const rest = { ...item };
                                        delete rest.ownerRoleAssignmentId;
                                        return value
                                          ? {
                                              ...rest,
                                              ownerRoleAssignmentId: value,
                                            }
                                          : rest;
                                      }),
                                    );
                                  }}
                                >
                                  <option value="">{t("Unassigned")}</option>
                                  {context.roleAssignments.map((role) => (
                                    <option
                                      data-language-exempt="business-data"
                                      key={role.globalId}
                                      value={role.globalId}
                                    >
                                      {departmentLabel(t, role.roleKey)} ·{" "}
                                      {
                                        context.members.find(
                                          (member) =>
                                            member.globalId === role.memberId,
                                        )?.userId
                                      }
                                    </option>
                                  ))}
                                </Select>
                              </td>
                              <td>
                                <TextInput
                                  aria-label={t("Planned start {{row}}", {
                                    row: index + 1,
                                  })}
                                  type="date"
                                  required
                                  value={row.plannedStart}
                                  onChange={(e) => {
                                    updatePlan(row.globalId, {
                                      plannedStart: e.currentTarget.value,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <TextInput
                                  aria-label={t("Planned finish {{row}}", {
                                    row: index + 1,
                                  })}
                                  type="date"
                                  required
                                  min={row.plannedStart}
                                  value={row.plannedFinish}
                                  onChange={(e) => {
                                    updatePlan(row.globalId, {
                                      plannedFinish: e.currentTarget.value,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <Select
                                  aria-label={t("Parent item {{row}}", {
                                    row: index + 1,
                                  })}
                                  value={row.parentId ?? ""}
                                  onChange={(e) => {
                                    const value = e.currentTarget.value;
                                    touch();
                                    setPlan((rows) =>
                                      rows.map((item) => {
                                        if (item.globalId !== row.globalId)
                                          return item;
                                        const rest = { ...item };
                                        delete rest.parentId;
                                        return value
                                          ? { ...rest, parentId: value }
                                          : rest;
                                      }),
                                    );
                                  }}
                                >
                                  <option value="">{t("None")}</option>
                                  {plan
                                    .filter(
                                      (item) => item.globalId !== row.globalId,
                                    )
                                    .map((item) => (
                                      <option
                                        data-language-exempt="business-data"
                                        key={item.globalId}
                                        value={item.globalId}
                                      >
                                        {item.code} {item.title}
                                      </option>
                                    ))}
                                </Select>
                              </td>
                              <td>
                                <Select
                                  aria-label={t("Plan state {{row}}", {
                                    row: index + 1,
                                  })}
                                  value={row.statusKey}
                                  onChange={(e) => {
                                    updatePlan(row.globalId, {
                                      statusKey: e.currentTarget.value,
                                    });
                                  }}
                                >
                                  {policy.wbsLifecycle.states.map((state) => (
                                    <option key={state.key} value={state.key}>
                                      {governedPolicyLabel(
                                        t,
                                        state.labelSource,
                                      )}
                                    </option>
                                  ))}
                                </Select>
                              </td>
                              <td>
                                <TextInput
                                  aria-label={t("Progress {{row}}", {
                                    row: index + 1,
                                  })}
                                  type="number"
                                  required
                                  min={0}
                                  max={100}
                                  value={row.progressPercent}
                                  onChange={(e) => {
                                    updatePlan(row.globalId, {
                                      progressPercent: Number(
                                        e.currentTarget.value,
                                      ),
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <input
                                  aria-label={t("Milestone {{row}}", {
                                    row: index + 1,
                                  })}
                                  type="checkbox"
                                  checked={row.milestone}
                                  onChange={(e) => {
                                    updatePlan(row.globalId, {
                                      milestone: e.currentTarget.checked,
                                    });
                                  }}
                                />
                              </td>
                              <td>
                                <Button
                                  type="button"
                                  disabled={
                                    context.wbsItems.some(
                                      (item) => item.globalId === row.globalId,
                                    ) ||
                                    plan.some(
                                      (item) => item.parentId === row.globalId,
                                    )
                                  }
                                  aria-label={t("Remove plan item {{row}}", {
                                    row: index + 1,
                                  })}
                                  onClick={() => {
                                    touch();
                                    setPlan((rows) =>
                                      rows.filter(
                                        (item) =>
                                          item.globalId !== row.globalId,
                                      ),
                                    );
                                    setDependencies((rows) =>
                                      rows.filter(
                                        (item) =>
                                          item.predecessorItemId !==
                                            row.globalId &&
                                          item.successorItemId !== row.globalId,
                                      ),
                                    );
                                  }}
                                >
                                  {t("Remove")}
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="project-setup-dependencies">
                      <h3>{t("Dependencies")}</h3>
                      {dependencies.map((dependency, index) => (
                        <div
                          className="project-setup-toolbar"
                          key={dependency.globalId}
                        >
                          {(
                            ["predecessorItemId", "successorItemId"] as const
                          ).map((field) => (
                            <label key={field}>
                              <span>
                                {field === "predecessorItemId"
                                  ? t("Predecessor")
                                  : t("Successor")}
                              </span>
                              <Select
                                required
                                aria-label={
                                  field === "predecessorItemId"
                                    ? t("Predecessor {{row}}", {
                                        row: index + 1,
                                      })
                                    : t("Successor {{row}}", { row: index + 1 })
                                }
                                value={dependency[field]}
                                onChange={(e) => {
                                  const value = e.currentTarget.value;
                                  touch();
                                  setDependencies((rows) =>
                                    rows.map((item) =>
                                      item.globalId === dependency.globalId
                                        ? { ...item, [field]: value }
                                        : item,
                                    ),
                                  );
                                }}
                              >
                                <option value="">
                                  {t("Select plan item")}
                                </option>
                                {plan.map((item) => (
                                  <option
                                    data-language-exempt="business-data"
                                    key={item.globalId}
                                    value={item.globalId}
                                  >
                                    {item.code} {item.title}
                                  </option>
                                ))}
                              </Select>
                            </label>
                          ))}
                          <Button
                            type="button"
                            disabled={context.dependencies.some(
                              (item) => item.globalId === dependency.globalId,
                            )}
                            onClick={() => {
                              touch();
                              setDependencies((rows) =>
                                rows.filter(
                                  (item) =>
                                    item.globalId !== dependency.globalId,
                                ),
                              );
                            }}
                          >
                            {t("Remove")}
                          </Button>
                        </div>
                      ))}
                      <Button
                        type="button"
                        disabled={plan.length < 2}
                        onClick={() => {
                          touch();
                          setDependencies((rows) => [
                            ...rows,
                            {
                              globalId: crypto.randomUUID(),
                              predecessorItemId: "",
                              successorItemId: "",
                            },
                          ]);
                        }}
                      >
                        {t("Add dependency")}
                      </Button>
                    </div>
                  </>
                ) : null}
                {mode === "baseline" && policy ? (
                  <label>
                    <span>{t("Baseline label")}</span>
                    <TextInput
                      required
                      maxLength={140}
                      value={baselineLabel}
                      onChange={(e) => {
                        touch();
                        setBaselineLabel(e.currentTarget.value);
                      }}
                    />
                  </label>
                ) : null}
              </fieldset>
              <div className="project-setup-toolbar">
                <Button
                  visual="primary"
                  type="submit"
                  disabled={
                    !policy ||
                    (mode === "roles" && context.initialized) ||
                    !sessionCommandContext ||
                    locked ||
                    loading ||
                    (mode === "plan" && !plan.length)
                  }
                >
                  {t("Review project setup")}
                </Button>
                <Button type="button" disabled={pending} onClick={close}>
                  {t("Cancel")}
                </Button>
              </div>
              {!sessionCommandContext ? (
                <p>
                  {t("Session verification is required before initialization.")}
                </p>
              ) : null}
            </form>
          ) : (
            <Button type="button" onClick={close}>
              {t("Cancel")}
            </Button>
          )}
          {pending ? (
            <p role="status" aria-busy="true">
              {t("Saving project setup")}
            </p>
          ) : null}
          {failure ? (
            <div role="alert">
              <RequestFailurePanel failure={failure} />
              {uncertain && retryOperation ? (
                <Button
                  type="button"
                  disabled={pending}
                  onClick={() => {
                    void execute(retryOperation);
                  }}
                >
                  {t("Retry exact setup command")}
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={() => {
                    setRetryOperation(null);
                    setFailure(null);
                  }}
                >
                  {t("Edit inputs")}
                </Button>
              )}
              {conflict ? (
                <p>
                  {t(
                    "The Project changed. Reload its current version before reviewing another setup command.",
                  )}
                </p>
              ) : null}
              {conflict ? (
                <Button
                  type="button"
                  onClick={() => {
                    globalThis.location.reload();
                  }}
                >
                  {t("Reload project")}
                </Button>
              ) : null}
            </div>
          ) : null}
        </Panel>
      )}
      {review ? (
        <ImpactReview
          title={t("Review project setup")}
          confirmLabel={t("Confirm project setup")}
          reasonRequired={false}
          returnFocusTarget={() =>
            trigger.current?.querySelector<HTMLElement>("ix-button, button") ??
            null
          }
          contextRows={[
            ...(review.command.kind === "baseline"
              ? [
                  {
                    label: t("Baseline label"),
                    value: review.command.body.label,
                    exempt: "business-data" as const,
                  },
                ]
              : []),
            {
              label: t("Project version"),
              value: String(review.command.body.expectedProjectVersion),
            },
            {
              label: t("Work policy version"),
              value: String(review.command.body.workPolicyRef.version),
            },
            {
              label: t("Operation"),
              value:
                review.command.kind === "roles"
                  ? t("Initialize project roles")
                  : review.command.kind === "team"
                    ? t("Team setup")
                    : review.command.kind === "plan"
                      ? t("Plan setup")
                      : t("Capture plan baseline"),
            },
            {
              label: t("Rows"),
              value: String(
                review.command.kind === "roles"
                  ? (policy?.roleKeys.length ?? 0)
                  : review.command.kind === "team"
                    ? review.command.body.roleAssignments.length
                    : review.command.kind === "plan"
                      ? review.command.body.items.length
                      : 1,
              ),
            },
          ]}
          details={{
            objectIdentity: context.projectId,
            version: String(context.projectVersion),
            impact: t(
              "Saves the reviewed Project configuration using its exact current version.",
            ),
            permission: t(
              "An authorized administrator is required. Responsibilities do not grant approval authority.",
            ),
            irreversible: t(
              "Captured baselines and published template snapshots cannot be overwritten.",
            ),
            audit: t(
              "The actor, Project version and applied changes are audited.",
            ),
            failureHandling: t(
              "Failures retain your inputs. Retry sends the same command identity and contents.",
            ),
          }}
          onCancel={() => {
            setReview(null);
          }}
          onConfirm={() => {
            void execute(review);
          }}
        />
      ) : null}
    </section>
  );
}
