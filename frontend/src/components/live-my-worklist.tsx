import { useEffect, useMemo, useRef, useState } from "react";

import {
  MyWorkRequestCancelledError,
  type MyWorkDataSource,
  type MyWorkQuery,
  type MyWorkView,
} from "../api/my-work-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { myWorkTargetPath } from "../app/my-work-navigation";
import type {
  DomainWorkItemSeverity,
  GateRequirementPriority,
  MyWorkItemViewModel,
  MyWorkPageViewModel,
  MyWorkPriorityViewModel,
  MyWorkStatus,
  SemanticTone,
} from "../domain/view-models";
import {
  domainWorkItemSeverityLabel,
  myWorkActionLabel,
  myWorkCategoryLabel,
  myWorkDueStateLabel,
  myWorkPriorityLabel,
  myWorkSourceTypeLabel,
  myWorkStatusLabel,
  myWorkWhyLabel,
} from "../i18n/copy";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";
import { DockedInspector, MetricStrip } from "./object-components";
import { RequestFailurePanel } from "./problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
  SourceBadge,
  SyncBadge,
} from "./primitives";

const liveMyWorkPageSize = 20;

type PriorityFilter =
  | "all"
  | `domain_severity:${DomainWorkItemSeverity}`
  | `gate_requirement_priority:${GateRequirementPriority}`;

type LoadState =
  | { kind: "loading"; signature: string }
  | {
      kind: "loaded";
      page: MyWorkPageViewModel;
      signature: string;
    }
  | { failure: RequestFailure; kind: "failed"; signature: string };

type FailureKind =
  | "no_permission"
  | "conflict"
  | "retryable"
  | "invalid"
  | "final";

const viewValues = new Set<MyWorkView>([
  "all",
  "today",
  "overdue",
  "approvals",
  "blockers",
  "waiting",
  "integration",
]);

const priorityValues = new Map<PriorityFilter, MyWorkPriorityViewModel | null>([
  ["all", null],
  ["domain_severity:low", { scheme: "domain_severity", value: "low" }],
  ["domain_severity:medium", { scheme: "domain_severity", value: "medium" }],
  ["domain_severity:high", { scheme: "domain_severity", value: "high" }],
  [
    "domain_severity:critical",
    { scheme: "domain_severity", value: "critical" },
  ],
  [
    "gate_requirement_priority:P0",
    { scheme: "gate_requirement_priority", value: "P0" },
  ],
  [
    "gate_requirement_priority:P1",
    { scheme: "gate_requirement_priority", value: "P1" },
  ],
  [
    "gate_requirement_priority:P2",
    { scheme: "gate_requirement_priority", value: "P2" },
  ],
]);

function parseView(value: string): MyWorkView {
  return viewValues.has(value as MyWorkView) ? (value as MyWorkView) : "all";
}

function parsePriority(value: string): PriorityFilter {
  return priorityValues.has(value as PriorityFilter)
    ? (value as PriorityFilter)
    : "all";
}

function failureKind(failure: RequestFailure): FailureKind {
  if (failure.problem?.status === 401 || failure.problem?.status === 403) {
    return "no_permission";
  }
  if (failure.problem?.status === 409) {
    return "conflict";
  }
  if (
    failure.kind === "invalid_response" ||
    failure.kind === "request_not_ready" ||
    failure.kind === "unexpected"
  ) {
    return "invalid";
  }
  if (failure.kind === "network" || failure.problem?.retryable) {
    return "retryable";
  }
  return "final";
}

function invalidResponseFailure(): RequestFailure {
  return {
    kind: "invalid_response",
    referenceId: `client-${globalThis.crypto.randomUUID()}`,
    referenceKind: "client",
  };
}

function statusTone(status: MyWorkStatus): SemanticTone {
  switch (status) {
    case "blocked":
      return "danger";
    case "waiting":
      return "warning";
    case "in_review":
      return "info";
    case "ready":
      return "neutral";
  }
}

function categoryTone(item: MyWorkItemViewModel): SemanticTone {
  if (item.blocking || item.category === "blocker") return "danger";
  if (item.category === "risk" || item.category === "issue") return "warning";
  if (item.category === "approval" || item.category === "decision") {
    return "info";
  }
  return "neutral";
}

function dueStateTone(dueState: MyWorkItemViewModel["dueState"]): SemanticTone {
  if (dueState === "overdue") return "danger";
  if (dueState === "today") return "warning";
  return "neutral";
}

function FailureState({
  failure,
  reload,
  retry,
}: {
  failure: RequestFailure;
  reload: () => void;
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const kind = failureKind(failure);
  const content = {
    no_permission: {
      detail: t(
        "Your account cannot open this work queue. No assigned work data was displayed.",
      ),
      title: t("My Work access is not available"),
    },
    conflict: {
      detail: t(
        "Reload the live My Work queue to review current assignments before continuing.",
      ),
      title: t("My Work changed"),
    },
    retryable: {
      detail: t(
        "Retry the live My Work request or share the displayed reference ID with support.",
      ),
      title: t("My Work could not be loaded"),
    },
    invalid: {
      detail: t(
        "No work data was displayed. Share the displayed reference ID with support before trying another action.",
      ),
      title: t("The My Work response could not be used safely"),
    },
    final: {
      detail: t(
        "No work data was displayed. Share the displayed reference ID with support.",
      ),
      title: t("My Work is unavailable"),
    },
  }[kind];
  return (
    <div className="table-empty table-empty--error">
      <SemanticStatus
        label={kind === "conflict" ? t("Conflict") : t("Error")}
        tone={kind === "conflict" ? "warning" : "danger"}
      />
      <strong>{content.title}</strong>
      <span>{content.detail}</span>
      <RequestFailurePanel failure={failure} />
      {kind === "retryable" || kind === "conflict" ? (
        <Button
          icon="refresh"
          onClick={kind === "conflict" ? reload : retry}
          visual="primary"
        >
          {kind === "conflict" ? t("Reload latest data") : t("Retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function LiveMyWorklist({
  dataSource,
  navigate,
}: {
  dataSource: MyWorkDataSource;
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const generation = useRef(0);
  const [view, setView] = useState<MyWorkView>("all");
  const [projectId, setProjectId] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("all");
  const [search, setSearch] = useState("");
  const [cursorStack, setCursorStack] = useState<
    readonly (string | undefined)[]
  >([undefined]);
  const [attempt, setAttempt] = useState(0);
  const [selectedId, setSelectedId] = useState("");
  const [knownProjects, setKnownProjects] = useState<
    readonly MyWorkItemViewModel["project"][]
  >([]);
  const priority = priorityValues.get(priorityFilter) ?? null;
  const cursor = cursorStack.at(-1);
  const query = useMemo<MyWorkQuery>(() => {
    const nextQuery: MyWorkQuery = { limit: liveMyWorkPageSize, view };
    if (projectId) nextQuery.projectId = projectId;
    if (priority) nextQuery.priority = priority;
    const boundedSearch = search.trim().slice(0, 140);
    if (boundedSearch) nextQuery.search = boundedSearch;
    if (cursor !== undefined) nextQuery.cursor = cursor;
    return nextQuery;
  }, [cursor, priority, projectId, search, view]);
  const requestSignature = JSON.stringify({
    attempt,
    cursorStack,
    query,
  });
  const [state, setState] = useState<LoadState>({
    kind: "loading",
    signature: requestSignature,
  });

  const resetPagination = (): void => {
    setCursorStack([undefined]);
    setSelectedId("");
  };
  const retry = (): void => {
    setAttempt((current) => current + 1);
  };
  const reload = (): void => {
    resetPagination();
    retry();
  };

  useEffect(() => {
    const handleRefresh = (): void => {
      retry();
    };
    globalThis.addEventListener("npi:refresh-my-work", handleRefresh);
    return () => {
      globalThis.removeEventListener("npi:refresh-my-work", handleRefresh);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    void dataSource
      .load(query, controller.signal)
      .then((page) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration
        ) {
          return;
        }
        if (page.nextCursor !== null && cursorStack.includes(page.nextCursor)) {
          setState({
            failure: invalidResponseFailure(),
            kind: "failed",
            signature: requestSignature,
          });
          return;
        }
        setKnownProjects((current) => {
          const options = [...page.projectOptions].sort((left, right) =>
            left.businessCode.localeCompare(right.businessCode),
          );
          return options.length === current.length &&
            options.every((project, index) => {
              const currentProject = current[index];
              if (currentProject === undefined) {
                return false;
              }
              return (
                project.globalId === currentProject.globalId &&
                project.businessCode === currentProject.businessCode &&
                project.title === currentProject.title
              );
            })
            ? current
            : options;
        });
        setSelectedId((current) =>
          page.items.some((item) => item.id === current)
            ? current
            : (page.items[0]?.id ?? ""),
        );
        setState({ kind: "loaded", page, signature: requestSignature });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration ||
          error instanceof MyWorkRequestCancelledError
        ) {
          return;
        }
        setState({
          failure: toRequestFailure(error),
          kind: "failed",
          signature: requestSignature,
        });
      });
    return () => {
      controller.abort();
    };
  }, [cursorStack, dataSource, query, requestSignature]);

  const currentState =
    state.signature === requestSignature
      ? state
      : ({
          kind: "loading",
          signature: requestSignature,
        } satisfies LoadState);
  const page = currentState.kind === "loaded" ? currentState.page : null;
  const selected =
    page?.items.find((item) => item.id === selectedId) ?? page?.items[0];
  const filtersApplied =
    view !== "all" ||
    projectId !== "" ||
    priorityFilter !== "all" ||
    search.trim() !== "";
  const clearFilters = (): void => {
    setView("all");
    setProjectId("");
    setPriorityFilter("all");
    setSearch("");
    resetPagination();
  };
  const metrics = page?.counts;

  return (
    <>
      <MetricStrip
        className="live-my-work-metrics"
        metrics={[
          {
            label: t("Overdue"),
            tone: "danger",
            value: metrics
              ? formatNumber(locale, metrics.overdue.value, 0)
              : "—",
          },
          {
            label: t("Due today"),
            value: metrics ? formatNumber(locale, metrics.today.value, 0) : "—",
          },
          {
            label: t("Pending approvals"),
            value: metrics
              ? formatNumber(locale, metrics.approvals.value, 0)
              : "—",
          },
          {
            label: t("Blocking"),
            tone: "warning",
            value: metrics
              ? formatNumber(locale, metrics.blockers.value, 0)
              : "—",
          },
          {
            label: t("Waiting"),
            value: metrics
              ? formatNumber(locale, metrics.waiting.value, 0)
              : "—",
          },
          {
            label: t("Integration"),
            tone: "warning",
            value: t("Unavailable"),
          },
        ]}
      />
      <div className="worklist-layout">
        <Panel
          actions={
            <div className="table-tools">
              <label>
                <span className="visually-hidden">{t("Saved view")}</span>
                <Select
                  aria-label={t("Saved view")}
                  onChange={(event) => {
                    setView(parseView(event.currentTarget.value));
                    resetPagination();
                  }}
                  value={view}
                >
                  <option value="all">{t("All assigned work")}</option>
                  <option value="today">{t("Due today")}</option>
                  <option value="overdue">{t("Overdue")}</option>
                  <option value="approvals">{t("Pending approvals")}</option>
                  <option value="blockers">{t("Blocking")}</option>
                  <option value="waiting">{t("Waiting")}</option>
                  <option value="integration">
                    {t("Integration unavailable")}
                  </option>
                </Select>
              </label>
              <label>
                <span className="visually-hidden">{t("Project")}</span>
                <Select
                  aria-label={t("Project")}
                  onChange={(event) => {
                    const nextProjectId = event.currentTarget.value;
                    setProjectId(
                      knownProjects.some(
                        (project) => project.globalId === nextProjectId,
                      )
                        ? nextProjectId
                        : "",
                    );
                    resetPagination();
                  }}
                  value={projectId}
                >
                  <option value="">{t("All projects")}</option>
                  {knownProjects.map((project) => (
                    <option
                      data-language-exempt="business-data"
                      key={project.globalId}
                      value={project.globalId}
                    >
                      {project.businessCode} · {project.title}
                    </option>
                  ))}
                </Select>
              </label>
              <label>
                <span className="visually-hidden">{t("Priority")}</span>
                <Select
                  aria-label={t("Priority")}
                  onChange={(event) => {
                    setPriorityFilter(parsePriority(event.currentTarget.value));
                    resetPagination();
                  }}
                  value={priorityFilter}
                >
                  <option value="all">{t("All priorities")}</option>
                  <optgroup label={t("Domain severity")}>
                    {(["low", "medium", "high", "critical"] as const).map(
                      (severity) => (
                        <option
                          key={severity}
                          value={`domain_severity:${severity}`}
                        >
                          {domainWorkItemSeverityLabel(t, severity)}
                        </option>
                      ),
                    )}
                  </optgroup>
                  <optgroup label={t("Gate requirement priority")}>
                    {(["P0", "P1", "P2"] as const).map((gatePriority) => (
                      <option
                        data-language-exempt="identifier"
                        key={gatePriority}
                        value={`gate_requirement_priority:${gatePriority}`}
                      >
                        {gatePriority}
                      </option>
                    ))}
                  </optgroup>
                </Select>
              </label>
              <label>
                <span className="visually-hidden">{t("Filter")}</span>
                <TextInput
                  aria-label={t("Filter")}
                  maxLength={140}
                  onChange={(event) => {
                    setSearch(event.currentTarget.value.slice(0, 140));
                    resetPagination();
                  }}
                  placeholder={t("Search assigned work")}
                  type="search"
                  value={search}
                />
              </label>
            </div>
          }
          className="worklist-panel"
          title={t("Worklist")}
        >
          <div
            aria-busy={currentState.kind === "loading"}
            className="table-scroll"
          >
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th scope="col">{t("Type")}</th>
                  <th scope="col">{t("Item")}</th>
                  <th scope="col">{t("Project or object")}</th>
                  <th scope="col">{t("Why assigned")}</th>
                  <th scope="col">{t("Priority")}</th>
                  <th scope="col">{t("Due")}</th>
                  <th scope="col">{t("Status")}</th>
                  <th scope="col">{t("Next action")}</th>
                </tr>
              </thead>
              <tbody>
                {currentState.kind === "loading" ? (
                  <tr>
                    <td colSpan={8}>
                      <div className="table-empty" role="status">
                        {t("Loading My Work")}
                      </div>
                    </td>
                  </tr>
                ) : currentState.kind === "failed" ? (
                  <tr>
                    <td colSpan={8}>
                      <FailureState
                        failure={currentState.failure}
                        reload={reload}
                        retry={retry}
                      />
                    </td>
                  </tr>
                ) : currentState.page.items.length === 0 ? (
                  <tr>
                    <td colSpan={8}>
                      <div className="table-empty">
                        <span>
                          {t("No assigned work is available in this view.")}
                        </span>
                        {filtersApplied ? (
                          <Button onClick={clearFilters}>
                            {t("Clear filters")}
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ) : (
                  currentState.page.items.map((item) => (
                    <tr
                      aria-selected={item.id === selected?.id}
                      className={
                        item.id === selected?.id ? "is-selected" : undefined
                      }
                      key={item.id}
                      onClick={() => {
                        setSelectedId(item.id);
                      }}
                      onKeyDown={(event) => {
                        if (event.target !== event.currentTarget) {
                          return;
                        }
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId(item.id);
                        }
                      }}
                      tabIndex={0}
                    >
                      <td>
                        <SemanticStatus
                          label={myWorkCategoryLabel(t, item.category)}
                          tone={categoryTone(item)}
                        />
                      </td>
                      <td>
                        <strong data-language-exempt="business-data">
                          {item.title}
                        </strong>
                      </td>
                      <td>
                        <span data-language-exempt="identifier">
                          {item.project.businessCode}
                        </span>
                        <br />
                        <span data-language-exempt="business-data">
                          {item.context.title}
                        </span>
                      </td>
                      <td>{myWorkWhyLabel(t, item.why)}</td>
                      <td>{myWorkPriorityLabel(t, item.priority)}</td>
                      <td>
                        <div className="my-work-due">
                          {item.dueAt === null ? null : (
                            <time dateTime={item.dueAt}>
                              {formatDateTime(
                                locale,
                                item.dueAt,
                                currentState.page.timeZone,
                              )}
                            </time>
                          )}
                          <SemanticStatus
                            label={myWorkDueStateLabel(t, item.dueState)}
                            tone={dueStateTone(item.dueState)}
                          />
                        </div>
                      </td>
                      <td>
                        <SemanticStatus
                          label={myWorkStatusLabel(t, item.status)}
                          tone={statusTone(item.status)}
                        />
                      </td>
                      <td>
                        <Button
                          onClick={(event) => {
                            event.stopPropagation();
                            navigate(myWorkTargetPath(item));
                          }}
                          visual="ghost"
                        >
                          {myWorkActionLabel(t, item.action)}
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <footer className="table-footer">
            <span>
              {t("Page {{page}}", {
                page: formatNumber(locale, cursorStack.length, 0),
              })}
            </span>
            <nav aria-label={t("My Work pages")}>
              <Button
                disabled={cursorStack.length === 1}
                onClick={() => {
                  setCursorStack((current) =>
                    current.length > 1 ? current.slice(0, -1) : current,
                  );
                  setSelectedId("");
                }}
              >
                {t("Previous page")}
              </Button>
              <Button
                disabled={page?.nextCursor === null || !page}
                onClick={() => {
                  const nextCursor = page?.nextCursor;
                  if (
                    nextCursor === null ||
                    nextCursor === undefined ||
                    cursorStack.includes(nextCursor)
                  ) {
                    return;
                  }
                  setCursorStack((current) => [...current, nextCursor]);
                  setSelectedId("");
                }}
              >
                {t("Next page")}
              </Button>
            </nav>
          </footer>
        </Panel>
        {selected ? (
          <DockedInspector title={t("Work item details")}>
            <DefinitionList
              rows={[
                {
                  exempt: "business-data",
                  label: t("Item"),
                  value: selected.title,
                },
                {
                  exempt: "identifier",
                  label: t("Project"),
                  value: selected.project.businessCode,
                },
                {
                  exempt: "business-data",
                  label: t("Project title"),
                  value: selected.project.title,
                },
                {
                  exempt: "identifier",
                  label: t("Context"),
                  value: selected.context.code,
                },
                {
                  exempt: "business-data",
                  label: t("Context title"),
                  value: selected.context.title,
                },
                {
                  label: t("Why assigned"),
                  value: myWorkWhyLabel(t, selected.why),
                },
                {
                  label: t("Priority"),
                  value: myWorkPriorityLabel(t, selected.priority),
                },
                {
                  label: t("Due"),
                  value:
                    selected.dueAt === null
                      ? t("No due date")
                      : formatDateTime(locale, selected.dueAt, page?.timeZone),
                },
                {
                  label: t("Due state"),
                  value: myWorkDueStateLabel(t, selected.dueState),
                },
                {
                  exempt: "identifier",
                  label: t("Due time zone"),
                  value: page?.timeZone ?? "UTC",
                },
                {
                  label: t("Assignment source"),
                  value: myWorkSourceTypeLabel(t, selected.source.type),
                },
              ]}
            />
            <div className="inspector-badges">
              <SourceBadge source={selected.sourceStatus} />
              <SyncBadge state={selected.sourceStatus.syncState} />
            </div>
            <Button
              onClick={() => {
                navigate(myWorkTargetPath(selected));
              }}
              visual="primary"
            >
              {myWorkActionLabel(t, selected.action)}
            </Button>
          </DockedInspector>
        ) : null}
      </div>
    </>
  );
}
