import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  DomainWorkItemQuery,
  ProjectDomainWorkItemsDataSource,
  ProjectWorkContextDataSource,
} from "../api/project-work-data-source";
import { ProjectWorkRequestCancelledError } from "../api/project-work-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { DockedInspector } from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import type {
  DomainWorkItemKind,
  DomainWorkItemPageViewModel,
  DomainWorkItemSeverity,
  DomainWorkItemViewModel,
  ProjectCockpitViewModel,
  ProjectMemberViewModel,
  ProjectRoleAssignmentViewModel,
  ProjectWbsItemViewModel,
  ProjectWorkContextViewModel,
} from "../domain/view-models";
import {
  domainWorkItemKindLabel,
  domainWorkItemSeverityLabel,
  governedPolicyLabel,
  projectResponsibilityContextLabel,
  projectResponsibilityLabel,
  sourceSystemLabel,
} from "../i18n/copy";
import { formatDate, formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n, type Locale } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ProjectWorkspaceTab = "overview" | "team" | "plan" | "work-items";

type ResourceState<T> =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: T; signature?: string }
  | { kind: "failed"; failure: RequestFailure; signature?: string };

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function invalidWorkspaceResponseFailure(): RequestFailure {
  return {
    kind: "invalid_response",
    referenceId: `client-${globalThis.crypto.randomUUID()}`,
    referenceKind: "client",
  };
}

function WorkspaceResourceFailure({
  failure,
  resource,
  retry,
}: {
  failure: RequestFailure;
  resource: "context" | "work-items";
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const invalid =
    failure.kind === "invalid_response" || failure.kind === "unexpected";
  const title =
    resource === "context"
      ? invalid
        ? t("The project work context response could not be used safely")
        : t("Project work context is unavailable")
      : invalid
        ? t("The domain work item response could not be used safely")
        : t("Domain work items are unavailable");
  const detail =
    resource === "context"
      ? t(
          "No Team, responsibility, or plan data was displayed. Use the reference ID for support.",
        )
      : t(
          "No domain work item data was displayed. Use the reference ID for support.",
        );
  return (
    <section className="workspace-resource-state" role="alert">
      <SemanticStatus label={t("Error")} tone="danger" />
      <h2>{title}</h2>
      <p>{detail}</p>
      <RequestFailurePanel failure={failure} />
      {canRetry(failure) ? (
        <Button icon="refresh" onClick={retry}>
          {t("Retry")}
        </Button>
      ) : null}
    </section>
  );
}

function WorkspaceResourceLoading({
  label,
}: {
  label: string;
}): React.JSX.Element {
  return (
    <section
      aria-busy="true"
      aria-label={label}
      className="workspace-resource-state workspace-resource-state--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">{label}</span>
    </section>
  );
}

function MissingWorkspaceDataSource({
  resource,
}: {
  resource: "context" | "work-items";
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section className="workspace-resource-state" role="status">
      <SemanticStatus label={t("Unavailable")} tone="warning" />
      <p>
        {resource === "context"
          ? t("The live project work context data source is not configured.")
          : t("The live domain work item data source is not configured.")}
      </p>
    </section>
  );
}

function MemberRows({
  context,
  selectedMemberId,
  selectMember,
}: {
  context: ProjectWorkContextViewModel;
  selectedMemberId: string;
  selectMember: (memberId: string) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (context.members.length === 0) {
    return (
      <div className="table-empty">
        {t("No team members are assigned to this project.")}
      </div>
    );
  }
  return (
    <table className="data-table data-table--compact">
      <thead>
        <tr>
          <th>{t("User")}</th>
          <th>{t("Roles")}</th>
        </tr>
      </thead>
      <tbody>
        {context.members.map((member) => {
          const roleCount = context.roleAssignments.filter(
            (assignment) => assignment.memberId === member.globalId,
          ).length;
          return (
            <tr
              aria-selected={selectedMemberId === member.globalId}
              className={
                selectedMemberId === member.globalId ? "is-selected" : undefined
              }
              key={member.globalId}
              onClick={() => {
                selectMember(member.globalId);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  selectMember(member.globalId);
                }
              }}
              tabIndex={0}
            >
              <td>
                <strong data-language-exempt="business-data">
                  {member.userId}
                </strong>
                <br />
                <small>
                  {t("Effective from")}{" "}
                  <time dateTime={member.effectiveFrom}>
                    {formatDate(locale, member.effectiveFrom)}
                  </time>
                </small>
              </td>
              <td>{formatNumber(locale, roleCount, 0)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function roleForRaci(
  context: ProjectWorkContextViewModel,
  roleAssignmentId: string,
): ProjectRoleAssignmentViewModel | undefined {
  return context.roleAssignments.find(
    (assignment) => assignment.globalId === roleAssignmentId,
  );
}

function memberForRole(
  context: ProjectWorkContextViewModel,
  role: ProjectRoleAssignmentViewModel | undefined,
): ProjectMemberViewModel | undefined {
  return context.members.find((member) => member.globalId === role?.memberId);
}

function ResponsibilityRows({
  context,
}: {
  context: ProjectWorkContextViewModel;
}): React.JSX.Element {
  const { t } = useI18n();
  if (context.raciAssignments.length === 0) {
    return (
      <div className="table-empty">
        {t("No responsibility assignments are configured for this project.")}
      </div>
    );
  }
  return (
    <table className="data-table data-table--compact">
      <thead>
        <tr>
          <th>{t("Scope")}</th>
          <th>{t("Responsibility key")}</th>
          <th>{t("Role key")}</th>
          <th>{t("User")}</th>
          <th>{t("Responsibility")}</th>
        </tr>
      </thead>
      <tbody>
        {context.raciAssignments.map((assignment) => {
          const role = roleForRaci(context, assignment.roleAssignmentId);
          const member = memberForRole(context, role);
          return (
            <tr key={assignment.globalId}>
              <td>
                {projectResponsibilityContextLabel(t, assignment.contextType)}
                <br />
                <small data-language-exempt="identifier">
                  {assignment.contextId}
                </small>
              </td>
              <td data-language-exempt="identifier">
                {assignment.responsibilityKey}
              </td>
              <td data-language-exempt="identifier">{role?.roleKey ?? "—"}</td>
              <td data-language-exempt="business-data">
                {member?.userId ?? "—"}
              </td>
              <td>
                <SemanticStatus
                  label={projectResponsibilityLabel(t, assignment.raci)}
                  tone={assignment.raci === "accountable" ? "info" : "neutral"}
                />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function MemberInspector({
  context,
  selected,
}: {
  context: ProjectWorkContextViewModel;
  selected: ProjectMemberViewModel | undefined;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (!selected) {
    return (
      <DockedInspector title={t("Team member details")}>
        <p>{t("Select a team member to inspect role coverage.")}</p>
      </DockedInspector>
    );
  }
  const roles = context.roleAssignments.filter(
    (assignment) => assignment.memberId === selected.globalId,
  );
  const roleIds = new Set(roles.map((role) => role.globalId));
  const substitutions = context.substitutions.filter(
    (substitution) =>
      roleIds.has(substitution.roleAssignmentId) ||
      substitution.substituteMemberId === selected.globalId,
  );
  return (
    <DockedInspector title={t("Team member details")}>
      <DefinitionList
        rows={[
          {
            label: t("User"),
            value: selected.userId,
            exempt: "business-data",
          },
          {
            label: t("Effective from"),
            value: formatDate(locale, selected.effectiveFrom),
          },
          {
            label: t("Effective to"),
            value: selected.effectiveTo
              ? formatDate(locale, selected.effectiveTo)
              : t("No end date"),
          },
          {
            label: t("Version"),
            value: formatNumber(locale, selected.version, 0),
          },
          {
            label: t("Role keys"),
            value:
              roles.length > 0 ? (
                <ul className="compact-value-list">
                  {roles.map((role) => (
                    <li key={role.globalId}>
                      <span data-language-exempt="identifier">
                        {role.roleKey}
                      </span>
                      <br />
                      <small>
                        <time dateTime={role.effectiveFrom}>
                          {formatDate(locale, role.effectiveFrom)}
                        </time>
                        {" – "}
                        {role.effectiveTo ? (
                          <time dateTime={role.effectiveTo}>
                            {formatDate(locale, role.effectiveTo)}
                          </time>
                        ) : (
                          t("No end date")
                        )}
                      </small>
                    </li>
                  ))}
                </ul>
              ) : (
                t("No role assignment")
              ),
          },
          {
            label: t("Substitution assignments"),
            value:
              substitutions.length > 0 ? (
                <div className="substitution-details">
                  {substitutions.map((substitution) => {
                    const role = context.roleAssignments.find(
                      (assignment) =>
                        assignment.globalId === substitution.roleAssignmentId,
                    );
                    const originalHolder = context.members.find(
                      (member) => member.globalId === role?.memberId,
                    );
                    const substitute = context.members.find(
                      (member) =>
                        member.globalId === substitution.substituteMemberId,
                    );
                    return (
                      <dl
                        className="substitution-detail-list"
                        key={substitution.globalId}
                      >
                        <div className="substitution-detail-row">
                          <dt className="substitution-detail-term">
                            {t("Role key")}
                          </dt>
                          <dd
                            className="substitution-detail-value"
                            data-language-exempt="identifier"
                          >
                            {role?.roleKey ?? "—"}
                          </dd>
                        </div>
                        <div className="substitution-detail-row">
                          <dt className="substitution-detail-term">
                            {t("Original member")}
                          </dt>
                          <dd
                            className="substitution-detail-value"
                            data-language-exempt="business-data"
                          >
                            {originalHolder?.userId ?? "—"}
                          </dd>
                        </div>
                        <div className="substitution-detail-row">
                          <dt className="substitution-detail-term">
                            {t("Substitute member")}
                          </dt>
                          <dd
                            className="substitution-detail-value"
                            data-language-exempt="business-data"
                          >
                            {substitute?.userId ?? "—"}
                          </dd>
                        </div>
                        <div className="substitution-detail-row">
                          <dt className="substitution-detail-term">
                            {t("Effective from")}
                          </dt>
                          <dd className="substitution-detail-value">
                            <time dateTime={substitution.effectiveFrom}>
                              {formatDate(locale, substitution.effectiveFrom)}
                            </time>
                          </dd>
                        </div>
                        <div className="substitution-detail-row">
                          <dt className="substitution-detail-term">
                            {t("Effective to")}
                          </dt>
                          <dd className="substitution-detail-value">
                            <time dateTime={substitution.effectiveTo}>
                              {formatDate(locale, substitution.effectiveTo)}
                            </time>
                          </dd>
                        </div>
                      </dl>
                    );
                  })}
                </div>
              ) : (
                t("None")
              ),
          },
        ]}
      />
      <div className="governance-note">
        <SemanticStatus label={t("Responsibility only")} tone="info" />
        <p>{t("Project roles do not grant Gate approval authority.")}</p>
      </div>
    </DockedInspector>
  );
}

function TeamWorkspace({
  context,
}: {
  context: ProjectWorkContextViewModel;
}): React.JSX.Element {
  const { t } = useI18n();
  const [selectedMemberId, setSelectedMemberId] = useState(
    context.members[0]?.globalId ?? "",
  );
  const selected =
    context.members.find((member) => member.globalId === selectedMemberId) ??
    context.members[0];
  return (
    <>
      {!context.initialized ? (
        <div className="scenario-banner scenario-banner--empty" role="status">
          <SemanticStatus label={t("Not initialized")} />
          <span>
            {t(
              "Team, responsibility, and plan data have not been initialized.",
            )}
          </span>
        </div>
      ) : null}
      <div className="engineering-layout engineering-layout--team">
        <Panel
          className="project-team-panel"
          scrollableBody
          title={t("Team members")}
        >
          <MemberRows
            context={context}
            selectedMemberId={selectedMemberId}
            selectMember={setSelectedMemberId}
          />
        </Panel>
        <Panel
          className="project-team-panel"
          scrollableBody
          title={t("Responsibility assignments")}
        >
          <ResponsibilityRows context={context} />
        </Panel>
        <MemberInspector context={context} selected={selected} />
      </div>
    </>
  );
}

function flattenWbs(
  items: readonly ProjectWbsItemViewModel[],
): readonly Readonly<{ item: ProjectWbsItemViewModel; depth: number }>[] {
  const children = new Map<string | undefined, ProjectWbsItemViewModel[]>();
  for (const item of items) {
    const siblings = children.get(item.parentId) ?? [];
    siblings.push(item);
    children.set(item.parentId, siblings);
  }
  const flattened: { item: ProjectWbsItemViewModel; depth: number }[] = [];
  const visit = (parentId: string | undefined, depth: number): void => {
    for (const item of children.get(parentId) ?? []) {
      flattened.push({ item, depth });
      visit(item.globalId, depth + 1);
    }
  };
  visit(undefined, 0);
  return flattened;
}

function varianceLabel(
  t: ReturnType<typeof useI18n>["t"],
  locale: Locale,
  value: number,
): string {
  if (value > 0) {
    if (value === 1) return t("1 day late");
    return t("{{days}} days late", {
      days: formatNumber(locale, value, 0),
    });
  }
  if (value < 0) {
    if (value === -1) return t("1 day early");
    return t("{{days}} days early", {
      days: formatNumber(locale, Math.abs(value), 0),
    });
  }
  return t("On baseline");
}

function PlanWorkspace({
  context,
}: {
  context: ProjectWorkContextViewModel;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const flattened = useMemo(() => flattenWbs(context.wbsItems), [context]);
  const [selectedId, setSelectedId] = useState(
    flattened[0]?.item.globalId ?? "",
  );
  const selected =
    context.wbsItems.find((item) => item.globalId === selectedId) ??
    context.wbsItems[0];
  const comparisons = new Map(
    context.baselineComparison?.items.map((item) => [item.wbsItemId, item]) ??
      [],
  );
  const selectedComparison = selected
    ? comparisons.get(selected.globalId)
    : undefined;
  const selectedOwnerRole = context.roleAssignments.find(
    (assignment) => assignment.globalId === selected?.ownerRoleAssignmentId,
  );
  const selectedPredecessors = context.dependencies.filter(
    (dependency) => dependency.successorItemId === selected?.globalId,
  );
  const selectedSuccessors = context.dependencies.filter(
    (dependency) => dependency.predecessorItemId === selected?.globalId,
  );
  const baseline = context.baselines.find(
    (candidate) =>
      candidate.globalId === context.baselineComparison?.baselineId,
  );
  return (
    <>
      {context.baselineComparison === null ? (
        <div className="scenario-banner scenario-banner--empty" role="status">
          <SemanticStatus label={t("No baseline")} />
          <span>{t("No plan baseline is recorded for this project.")}</span>
        </div>
      ) : null}
      <div className="worklist-layout project-plan-layout">
        <Panel
          className="worklist-panel"
          scrollableBody
          title={t("Project plan")}
        >
          {flattened.length === 0 ? (
            <div className="table-empty">
              {t("No WBS items are configured for this project.")}
            </div>
          ) : (
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th>{t("WBS item")}</th>
                  <th>{t("State")}</th>
                  <th>{t("Owner role")}</th>
                  <th>{t("Current finish")}</th>
                  <th>{t("Baseline finish")}</th>
                  <th>{t("Finish variance")}</th>
                  <th>{t("Progress")}</th>
                  <th>{t("Schedule marker")}</th>
                </tr>
              </thead>
              <tbody>
                {flattened.map(({ item, depth }) => {
                  const comparison = comparisons.get(item.globalId);
                  const role = context.roleAssignments.find(
                    (assignment) =>
                      assignment.globalId === item.ownerRoleAssignmentId,
                  );
                  return (
                    <tr
                      aria-selected={item.globalId === selected?.globalId}
                      className={
                        item.globalId === selected?.globalId
                          ? "is-selected"
                          : undefined
                      }
                      key={item.globalId}
                      onClick={() => {
                        setSelectedId(item.globalId);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId(item.globalId);
                        }
                      }}
                      tabIndex={0}
                    >
                      <td>
                        <span className="wbs-tree-cell">
                          {Array.from({ length: depth }, (_, index) => (
                            <span
                              aria-hidden="true"
                              className="wbs-tree-indent"
                              key={index}
                            />
                          ))}
                          <span>
                            <strong data-language-exempt="identifier">
                              {item.code}
                            </strong>{" "}
                            <span data-language-exempt="business-data">
                              {item.title}
                            </span>
                          </span>
                        </span>
                      </td>
                      <td>
                        <SemanticStatus
                          label={governedPolicyLabel(t, item.statusLabelSource)}
                        />
                      </td>
                      <td data-language-exempt="identifier">
                        {role?.roleKey ?? "—"}
                      </td>
                      <td>
                        <time dateTime={item.plannedFinish}>
                          {formatDate(locale, item.plannedFinish)}
                        </time>
                      </td>
                      <td>
                        {comparison ? (
                          <time dateTime={comparison.baselinePlannedFinish}>
                            {formatDate(
                              locale,
                              comparison.baselinePlannedFinish,
                            )}
                          </time>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        {comparison
                          ? varianceLabel(
                              t,
                              locale,
                              comparison.finishVarianceDays,
                            )
                          : "—"}
                      </td>
                      <td>
                        {t("{{percent}} percent", {
                          percent: formatNumber(
                            locale,
                            item.progressPercent,
                            0,
                          ),
                        })}
                      </td>
                      <td>
                        {item.critical ? (
                          <SemanticStatus
                            label={t("Critical task")}
                            tone="warning"
                          />
                        ) : item.milestone ? (
                          <SemanticStatus label={t("Milestone")} tone="info" />
                        ) : (
                          <SemanticStatus label={t("Standard task")} />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
        <DockedInspector title={t("Plan item details")}>
          {selected ? (
            <>
              <DefinitionList
                rows={[
                  {
                    label: t("WBS item"),
                    value: `${selected.code} ${selected.title}`,
                    exempt: "business-data",
                  },
                  {
                    label: t("Parent item"),
                    value:
                      context.wbsItems.find(
                        (item) => item.globalId === selected.parentId,
                      )?.code ?? t("None"),
                    ...(selected.parentId
                      ? { exempt: "identifier" as const }
                      : {}),
                  },
                  {
                    label: t("Owner role"),
                    value: selectedOwnerRole?.roleKey ?? t("Unassigned"),
                    ...(selectedOwnerRole
                      ? { exempt: "identifier" as const }
                      : {}),
                  },
                  {
                    label: t("Planned start"),
                    value: formatDate(locale, selected.plannedStart),
                  },
                  {
                    label: t("Planned finish"),
                    value: formatDate(locale, selected.plannedFinish),
                  },
                  {
                    label: t("Actual start"),
                    value: selected.actualStart
                      ? formatDate(locale, selected.actualStart)
                      : t("Not recorded"),
                  },
                  {
                    label: t("Actual finish"),
                    value: selected.actualFinish
                      ? formatDate(locale, selected.actualFinish)
                      : t("Not recorded"),
                  },
                  {
                    label: t("Start variance"),
                    value: selectedComparison
                      ? varianceLabel(
                          t,
                          locale,
                          selectedComparison.startVarianceDays,
                        )
                      : t("No baseline"),
                  },
                  {
                    label: t("Finish variance"),
                    value: selectedComparison
                      ? varianceLabel(
                          t,
                          locale,
                          selectedComparison.finishVarianceDays,
                        )
                      : t("No baseline"),
                  },
                  {
                    label: t("Predecessors"),
                    value: formatNumber(locale, selectedPredecessors.length, 0),
                  },
                  {
                    label: t("Successors"),
                    value: formatNumber(locale, selectedSuccessors.length, 0),
                  },
                  {
                    label: t("Baseline"),
                    value: baseline?.label ?? t("No baseline"),
                    ...(baseline ? { exempt: "business-data" as const } : {}),
                  },
                ]}
              />
              <div className="governance-note">
                <SemanticStatus label={t("Explicit indicator")} tone="info" />
                <p>
                  {t(
                    "Critical task is a recorded plan indicator, not a computed critical path.",
                  )}
                </p>
              </div>
            </>
          ) : (
            <p>{t("Select a WBS item to inspect plan details.")}</p>
          )}
        </DockedInspector>
      </div>
    </>
  );
}

function severityTone(
  severity: DomainWorkItemSeverity,
): "neutral" | "info" | "warning" | "danger" {
  if (severity === "critical") return "danger";
  if (severity === "high") return "warning";
  if (severity === "medium") return "info";
  return "neutral";
}

function WorkItemInspector({
  item,
}: {
  item: DomainWorkItemViewModel | undefined;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (!item) {
    return (
      <DockedInspector title={t("Domain work item details")}>
        <p>{t("Select a domain work item to inspect its governed context.")}</p>
      </DockedInspector>
    );
  }
  return (
    <DockedInspector title={t("Domain work item details")}>
      <DefinitionList
        rows={[
          {
            label: t("Global ID"),
            value: item.globalId,
            exempt: "identifier",
          },
          {
            label: t("Kind"),
            value: domainWorkItemKindLabel(t, item.kind),
          },
          {
            label: t("Lifecycle State"),
            value: governedPolicyLabel(t, item.stateLabelSource),
          },
          {
            label: t("Owner"),
            value: item.ownerUserId,
            exempt: "business-data",
          },
          {
            label: t("Due date"),
            value: formatDateTime(locale, item.dueAt),
          },
          {
            label: t("Severity"),
            value: domainWorkItemSeverityLabel(t, item.severity),
          },
          {
            label: t("Stage"),
            value: item.context.stageId ?? t("Project level"),
            ...(item.context.stageId ? { exempt: "identifier" as const } : {}),
          },
          {
            label: t("WBS item"),
            value: item.context.wbsItemId ?? t("Not linked"),
            ...(item.context.wbsItemId
              ? { exempt: "identifier" as const }
              : {}),
          },
          {
            label: t("Related work items"),
            value: formatNumber(locale, item.relatedWorkItemIds.length, 0),
          },
          {
            label: t("Work policy version"),
            value: formatNumber(locale, item.workPolicyRef.version, 0),
          },
          {
            label: t("Version"),
            value: formatNumber(locale, item.version, 0),
          },
          {
            label: t("Created"),
            value: formatDateTime(locale, item.createdAt),
          },
          {
            label: t("Last updated"),
            value: formatDateTime(locale, item.lastChangedAt),
          },
          {
            label: t("Source"),
            value: sourceSystemLabel(t, item.source.sourceSystem),
          },
        ]}
      />
      {item.detail !== undefined ? (
        <section className="inspector-note">
          <h3>{t("Detail")}</h3>
          <p data-language-exempt="business-data">{item.detail}</p>
        </section>
      ) : null}
    </DockedInspector>
  );
}

function stageLabel(
  t: ReturnType<typeof useI18n>["t"],
  gates: ProjectCockpitViewModel["gates"],
  stageId: string | undefined,
): ReactNode {
  if (!stageId) return t("Project level");
  const gate = gates.find((candidate) => candidate.globalId === stageId);
  if (!gate) {
    return <span data-language-exempt="identifier">{stageId}</span>;
  }
  return (
    <>
      <span data-language-exempt="identifier">{gate.key}</span>{" "}
      <span data-language-exempt="business-data">{gate.title}</span>
    </>
  );
}

function DomainWorkItemsWorkspace({
  cockpit,
  goToNextPage,
  goToPreviousPage,
  page,
  pageNumber,
  query,
  setQuery,
}: {
  cockpit: ProjectCockpitViewModel;
  goToNextPage: () => void;
  goToPreviousPage: () => void;
  page: DomainWorkItemPageViewModel;
  pageNumber: number;
  query: DomainWorkItemQuery;
  setQuery: (query: DomainWorkItemQuery) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [selectedId, setSelectedId] = useState(page.items[0]?.globalId ?? "");
  const [ownerFilter, setOwnerFilter] = useState(query.ownerUserId ?? "");
  const selected =
    page.items.find((item) => item.globalId === selectedId) ?? page.items[0];
  return (
    <>
      {page.nextCursor ? (
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus label={t("Partial data")} tone="warning" />
          <span>
            {t(
              "More domain work items are available. Use the page controls or refine the filters.",
            )}
          </span>
        </div>
      ) : null}
      <div className="worklist-layout project-work-items-layout">
        <Panel
          actions={
            <div className="table-tools">
              <label>
                <span className="visually-hidden">{t("Stage")}</span>
                <Select
                  aria-label={t("Stage")}
                  onChange={(event) => {
                    const remaining = { ...query };
                    delete remaining.cursor;
                    delete remaining.stageId;
                    const stageId = event.currentTarget.value;
                    setQuery(stageId ? { ...remaining, stageId } : remaining);
                  }}
                  value={query.stageId ?? ""}
                >
                  <option value="">{t("All stages")}</option>
                  {cockpit.gates.map((gate) => (
                    <option
                      data-language-exempt="business-data"
                      key={gate.globalId}
                      value={gate.globalId}
                    >
                      {gate.key} {gate.title}
                    </option>
                  ))}
                </Select>
              </label>
              <form
                className="owner-filter"
                onSubmit={(event) => {
                  event.preventDefault();
                  const remaining = { ...query };
                  delete remaining.cursor;
                  delete remaining.ownerUserId;
                  const ownerUserId = ownerFilter.trim().toLowerCase();
                  setOwnerFilter(ownerUserId);
                  setQuery(
                    ownerUserId ? { ...remaining, ownerUserId } : remaining,
                  );
                }}
              >
                <label>
                  <span className="visually-hidden">{t("Owner email")}</span>
                  <TextInput
                    aria-label={t("Owner email")}
                    maxLength={254}
                    onChange={(event) => {
                      setOwnerFilter(event.currentTarget.value);
                    }}
                    placeholder={t("Owner email")}
                    type="email"
                    value={ownerFilter}
                  />
                </label>
                <Button type="submit">{t("Apply owner filter")}</Button>
              </form>
              <label>
                <span className="visually-hidden">{t("Kind")}</span>
                <Select
                  aria-label={t("Kind")}
                  onChange={(event) => {
                    const remaining = { ...query };
                    delete remaining.cursor;
                    delete remaining.kind;
                    const kind = event.currentTarget.value;
                    setQuery(
                      kind
                        ? {
                            ...remaining,
                            kind: kind as DomainWorkItemKind,
                          }
                        : remaining,
                    );
                  }}
                  value={query.kind ?? ""}
                >
                  <option value="">{t("All kinds")}</option>
                  <option value="risk">{t("Risk")}</option>
                  <option value="issue">{t("Issue")}</option>
                  <option value="action">
                    {domainWorkItemKindLabel(t, "action")}
                  </option>
                  <option value="decision_request">
                    {t("Decision request")}
                  </option>
                </Select>
              </label>
              <label>
                <span className="visually-hidden">{t("Due state")}</span>
                <Select
                  aria-label={t("Due state")}
                  onChange={(event) => {
                    const remaining = { ...query };
                    delete remaining.cursor;
                    delete remaining.overdue;
                    const dueState = event.currentTarget.value;
                    setQuery(
                      dueState
                        ? {
                            ...remaining,
                            overdue: dueState === "true",
                          }
                        : remaining,
                    );
                  }}
                  value={
                    query.overdue === undefined
                      ? ""
                      : query.overdue
                        ? "true"
                        : "false"
                  }
                >
                  <option value="">{t("All due states")}</option>
                  <option value="true">{t("Overdue only")}</option>
                  <option value="false">{t("Not overdue")}</option>
                </Select>
              </label>
            </div>
          }
          className="worklist-panel"
          scrollableBody
          title={t("Domain work items")}
        >
          {page.items.length === 0 ? (
            <div className="table-empty">
              {t("No domain work items match the current filters.")}
            </div>
          ) : (
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th>{t("Kind")}</th>
                  <th>{t("Item")}</th>
                  <th>{t("Stage")}</th>
                  <th>{t("Owner")}</th>
                  <th>{t("Due date")}</th>
                  <th>{t("Severity")}</th>
                  <th>{t("Lifecycle State")}</th>
                  <th>{t("Impact")}</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((item) => (
                  <tr
                    aria-selected={item.globalId === selected?.globalId}
                    className={
                      item.globalId === selected?.globalId
                        ? "is-selected"
                        : undefined
                    }
                    key={item.globalId}
                    onClick={() => {
                      setSelectedId(item.globalId);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedId(item.globalId);
                      }
                    }}
                    tabIndex={0}
                  >
                    <td>
                      <SemanticStatus
                        label={domainWorkItemKindLabel(t, item.kind)}
                        tone={item.blocking ? "danger" : "neutral"}
                      />
                    </td>
                    <td>
                      <strong data-language-exempt="business-data">
                        {item.title}
                      </strong>
                    </td>
                    <td>
                      {stageLabel(t, cockpit.gates, item.context.stageId)}
                    </td>
                    <td data-language-exempt="business-data">
                      {item.ownerUserId}
                    </td>
                    <td>
                      <time dateTime={item.dueAt}>
                        {formatDateTime(locale, item.dueAt)}
                      </time>
                      {item.overdue ? (
                        <>
                          <br />
                          <SemanticStatus label={t("Overdue")} tone="danger" />
                        </>
                      ) : null}
                    </td>
                    <td>
                      <SemanticStatus
                        label={domainWorkItemSeverityLabel(t, item.severity)}
                        tone={severityTone(item.severity)}
                      />
                    </td>
                    <td>
                      <SemanticStatus
                        label={governedPolicyLabel(t, item.stateLabelSource)}
                      />
                    </td>
                    <td>
                      {item.blocking ? (
                        <SemanticStatus label={t("Blocking")} tone="danger" />
                      ) : (
                        <SemanticStatus label={t("Non-blocking")} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <footer className="table-footer">
            <span>
              {t("Page {{page}}", {
                page: formatNumber(locale, pageNumber, 0),
              })}
            </span>
            <nav aria-label={t("Domain work item pages")}>
              <Button
                disabled={query.cursor === undefined}
                onClick={goToPreviousPage}
              >
                {t("Previous page")}
              </Button>
              <Button
                disabled={page.nextCursor === null}
                onClick={goToNextPage}
              >
                {t("Next page")}
              </Button>
            </nav>
          </footer>
        </Panel>
        <WorkItemInspector item={selected} />
      </div>
    </>
  );
}

export function ProjectWorkspace({
  cockpit,
  contextDataSource,
  domainWorkItemsDataSource,
  overview,
}: {
  cockpit: ProjectCockpitViewModel;
  contextDataSource?: ProjectWorkContextDataSource | undefined;
  domainWorkItemsDataSource?: ProjectDomainWorkItemsDataSource | undefined;
  overview: ReactNode;
}): React.JSX.Element {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<ProjectWorkspaceTab>("overview");
  const [contextRequested, setContextRequested] = useState(false);
  const [workItemsRequested, setWorkItemsRequested] = useState(false);
  const [contextAttempt, setContextAttempt] = useState(0);
  const [workItemsAttempt, setWorkItemsAttempt] = useState(0);
  const [workItemsPageNumber, setWorkItemsPageNumber] = useState(1);
  const contextGeneration = useRef(0);
  const workItemsGeneration = useRef(0);
  const workItemsCursorStack = useRef<readonly (string | undefined)[]>([
    undefined,
  ]);
  const [contextState, setContextState] = useState<
    ResourceState<ProjectWorkContextViewModel>
  >({ kind: "idle" });
  const [workItemsState, setWorkItemsState] = useState<
    ResourceState<DomainWorkItemPageViewModel>
  >({ kind: "idle" });
  const [workItemsQuery, setWorkItemsQuery] = useState<DomainWorkItemQuery>({
    limit: 100,
  });
  const workItemsQuerySignature = JSON.stringify(workItemsQuery);

  useEffect(() => {
    if (!contextRequested || !contextDataSource) return undefined;
    const controller = new AbortController();
    const requestGeneration = contextGeneration.current + 1;
    contextGeneration.current = requestGeneration;
    void contextDataSource
      .load(
        cockpit.project.globalId,
        cockpit.project.version,
        controller.signal,
      )
      .then((value) => {
        if (
          !controller.signal.aborted &&
          contextGeneration.current === requestGeneration
        ) {
          if (
            value.projectId !== cockpit.project.globalId ||
            value.projectVersion !== cockpit.project.version
          ) {
            setContextState({
              failure: invalidWorkspaceResponseFailure(),
              kind: "failed",
            });
            return;
          }
          setContextState({ kind: "loaded", value });
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          contextGeneration.current !== requestGeneration ||
          error instanceof ProjectWorkRequestCancelledError
        ) {
          return;
        }
        setContextState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
    };
  }, [
    cockpit.project.globalId,
    cockpit.project.version,
    contextAttempt,
    contextDataSource,
    contextRequested,
  ]);

  useEffect(() => {
    if (!workItemsRequested || !domainWorkItemsDataSource) return undefined;
    const controller = new AbortController();
    const requestGeneration = workItemsGeneration.current + 1;
    workItemsGeneration.current = requestGeneration;
    const signature = workItemsQuerySignature;
    void domainWorkItemsDataSource
      .load(
        cockpit.project.globalId,
        cockpit.project.version,
        workItemsQuery,
        controller.signal,
      )
      .then((value) => {
        if (
          !controller.signal.aborted &&
          workItemsGeneration.current === requestGeneration
        ) {
          if (
            value.projectId !== cockpit.project.globalId ||
            value.projectVersion !== cockpit.project.version ||
            (value.nextCursor !== null &&
              workItemsCursorStack.current.includes(value.nextCursor))
          ) {
            setWorkItemsState({
              failure: invalidWorkspaceResponseFailure(),
              kind: "failed",
              signature,
            });
            return;
          }
          setWorkItemsState({ kind: "loaded", signature, value });
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          workItemsGeneration.current !== requestGeneration ||
          error instanceof ProjectWorkRequestCancelledError
        ) {
          return;
        }
        setWorkItemsState({
          failure: toRequestFailure(error),
          kind: "failed",
          signature,
        });
      });
    return () => {
      controller.abort();
    };
  }, [
    cockpit.project.globalId,
    cockpit.project.version,
    domainWorkItemsDataSource,
    workItemsAttempt,
    workItemsQuery,
    workItemsQuerySignature,
    workItemsRequested,
  ]);

  const tabs = [
    { id: "overview", label: t("Overview") },
    { id: "team", label: t("Team and responsibilities") },
    { id: "plan", label: t("Plan") },
    { id: "work-items", label: t("Work items") },
  ] as const satisfies readonly Readonly<{
    id: ProjectWorkspaceTab;
    label: string;
  }>[];

  const selectTab = (tab: ProjectWorkspaceTab): void => {
    setActiveTab(tab);
    if (tab === "team" || tab === "plan") setContextRequested(true);
    if (tab === "work-items") setWorkItemsRequested(true);
  };
  const selectAdjacentTab = (
    current: ProjectWorkspaceTab,
    direction: -1 | 1,
  ): void => {
    const currentIndex = tabs.findIndex((tab) => tab.id === current);
    const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
    const next = tabs[nextIndex];
    if (!next) return;
    selectTab(next.id);
    document.getElementById(`project-workspace-tab-${next.id}`)?.focus();
  };
  const setFilteredWorkItemsQuery = (query: DomainWorkItemQuery): void => {
    const firstPageQuery = { ...query };
    delete firstPageQuery.cursor;
    workItemsCursorStack.current = [undefined];
    setWorkItemsPageNumber(1);
    setWorkItemsQuery(firstPageQuery);
  };
  const goToNextWorkItemsPage = (): void => {
    if (
      workItemsState.kind !== "loaded" ||
      workItemsState.signature !== workItemsQuerySignature ||
      workItemsState.value.nextCursor === null
    ) {
      return;
    }
    const cursor = workItemsState.value.nextCursor;
    if (workItemsCursorStack.current.includes(cursor)) {
      setWorkItemsState({
        failure: invalidWorkspaceResponseFailure(),
        kind: "failed",
        signature: workItemsQuerySignature,
      });
      return;
    }
    workItemsCursorStack.current = [...workItemsCursorStack.current, cursor];
    setWorkItemsPageNumber((current) => current + 1);
    setWorkItemsQuery({ ...workItemsQuery, cursor });
  };
  const goToPreviousWorkItemsPage = (): void => {
    if (workItemsCursorStack.current.length <= 1) return;
    const previousStack = workItemsCursorStack.current.slice(0, -1);
    const cursor = previousStack.at(-1);
    workItemsCursorStack.current = previousStack;
    setWorkItemsPageNumber((current) => Math.max(1, current - 1));
    const previousQuery = { ...workItemsQuery };
    delete previousQuery.cursor;
    if (cursor !== undefined) previousQuery.cursor = cursor;
    setWorkItemsQuery(previousQuery);
  };

  let content: ReactNode = overview;
  if (activeTab === "team" || activeTab === "plan") {
    if (!contextDataSource) {
      content = <MissingWorkspaceDataSource resource="context" />;
    } else if (
      contextState.kind === "idle" ||
      contextState.kind === "loading"
    ) {
      content = (
        <WorkspaceResourceLoading label={t("Loading project work context")} />
      );
    } else if (contextState.kind === "failed") {
      content = (
        <WorkspaceResourceFailure
          failure={contextState.failure}
          resource="context"
          retry={() => {
            setContextState({ kind: "loading" });
            setContextAttempt((current) => current + 1);
          }}
        />
      );
    } else {
      content =
        activeTab === "team" ? (
          <TeamWorkspace context={contextState.value} />
        ) : (
          <PlanWorkspace context={contextState.value} />
        );
    }
  } else if (activeTab === "work-items") {
    if (!domainWorkItemsDataSource) {
      content = <MissingWorkspaceDataSource resource="work-items" />;
    } else if (
      workItemsState.kind === "idle" ||
      workItemsState.kind === "loading" ||
      workItemsState.signature !== workItemsQuerySignature
    ) {
      content = (
        <WorkspaceResourceLoading label={t("Loading domain work items")} />
      );
    } else if (workItemsState.kind === "failed") {
      content = (
        <WorkspaceResourceFailure
          failure={workItemsState.failure}
          resource="work-items"
          retry={() => {
            setWorkItemsState({ kind: "loading" });
            setWorkItemsAttempt((current) => current + 1);
          }}
        />
      );
    } else {
      content = (
        <DomainWorkItemsWorkspace
          cockpit={cockpit}
          goToNextPage={goToNextWorkItemsPage}
          goToPreviousPage={goToPreviousWorkItemsPage}
          page={workItemsState.value}
          pageNumber={workItemsPageNumber}
          query={workItemsQuery}
          setQuery={setFilteredWorkItemsQuery}
        />
      );
    }
  }

  return (
    <section className="project-workspace">
      <div
        aria-label={t("Project workspace sections")}
        className="rectangular-tabs project-workspace__tabs"
        role="tablist"
      >
        {tabs.map((tab) => (
          <button
            aria-controls="project-workspace-panel"
            aria-selected={activeTab === tab.id}
            id={`project-workspace-tab-${tab.id}`}
            key={tab.id}
            onClick={() => {
              selectTab(tab.id);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight") {
                event.preventDefault();
                selectAdjacentTab(tab.id, 1);
              }
              if (event.key === "ArrowLeft") {
                event.preventDefault();
                selectAdjacentTab(tab.id, -1);
              }
              if (event.key === "Home") {
                event.preventDefault();
                selectTab("overview");
                document
                  .getElementById("project-workspace-tab-overview")
                  ?.focus();
              }
              if (event.key === "End") {
                event.preventDefault();
                selectTab("work-items");
                document
                  .getElementById("project-workspace-tab-work-items")
                  ?.focus();
              }
            }}
            role="tab"
            tabIndex={activeTab === tab.id ? 0 : -1}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div
        aria-labelledby={`project-workspace-tab-${activeTab}`}
        id="project-workspace-panel"
        role="tabpanel"
        tabIndex={0}
      >
        {content}
      </div>
    </section>
  );
}
