import { useEffect, useMemo, useRef, useState } from "react";

import {
  MyWorkRequestCancelledError,
  type MyWorkDataSource,
  type MyWorkQuery,
  type MyWorkView,
} from "../api/my-work-data-source";
import {
  defaultMyWorkGridLayout,
  myWorkGridColumnWidthSpecs,
  truncateMyWorkGridSearch,
  type MyWorkGridColumnId,
  type MyWorkGridFilter,
  type MyWorkGridLayout,
  type MyWorkGridPreferencesDataSource,
  type MyWorkGridPriority,
  type MyWorkGridViewId,
} from "../api/grid-preferences-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { MyWorkInspectorPreferencesDataSource } from "../api/my-work-inspector-preferences-data-source";
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
import { useI18n, type I18nContextValue } from "../i18n/runtime";
import {
  DenseGrid,
  type DenseGridColumn,
  type DenseGridLayoutChange,
} from "../ui-adapters/dense-grid";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";
import {
  useMyWorkGridPersonalization,
  type MyWorkGridPersonalizationController,
} from "./my-work-grid-personalization";
import { useMyWorkInspectorPersonalization } from "./my-work-inspector-personalization";
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

const requiredGridColumns = new Set<MyWorkGridColumnId>(["item", "action"]);

function viewLabel(t: I18nContextValue["t"], view: MyWorkGridViewId): string {
  switch (view) {
    case "all":
      return t("All assigned work");
    case "today":
      return t("Due today");
    case "overdue":
      return t("Overdue");
    case "approvals":
      return t("Pending approvals");
    case "blockers":
      return t("Blocking");
    case "waiting":
      return t("Waiting");
    case "integration":
      return t("Integration unavailable");
  }
}

function gridColumnLabel(
  t: I18nContextValue["t"],
  columnId: MyWorkGridColumnId,
): string {
  switch (columnId) {
    case "type":
      return t("Type");
    case "item":
      return t("Item");
    case "context":
      return t("Project or object");
    case "assignment":
      return t("Why assigned");
    case "priority":
      return t("Priority");
    case "due":
      return t("Due");
    case "status":
      return t("Status");
    case "action":
      return t("Next action");
  }
}

function toGridPriority(
  priorityFilter: PriorityFilter,
): MyWorkGridPriority | null {
  const priority = priorityValues.get(priorityFilter);
  return priority ? { ...priority } : null;
}

function fromGridPriority(priority: MyWorkGridPriority | null): PriorityFilter {
  return priority
    ? (`${priority.scheme}:${priority.value}` as PriorityFilter)
    : "all";
}

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

function moveGridColumn(
  layout: MyWorkGridLayout,
  columnId: MyWorkGridColumnId,
  direction: -1 | 1,
): MyWorkGridLayout {
  const currentIndex = layout.columnOrder.indexOf(columnId);
  const nextIndex = currentIndex + direction;
  if (
    currentIndex < 0 ||
    nextIndex < 0 ||
    nextIndex >= layout.columnOrder.length
  ) {
    return layout;
  }
  const columnOrder = [...layout.columnOrder];
  const displaced = columnOrder[nextIndex];
  if (!displaced) return layout;
  columnOrder[currentIndex] = displaced;
  columnOrder[nextIndex] = columnId;
  return { ...layout, columnOrder };
}

function GridSettings({
  controller,
  currentView,
  onClose,
  onLayoutChange,
  onSaveCurrentFilters,
  onSelectView,
  projectOptions,
}: {
  controller: MyWorkGridPersonalizationController;
  currentView: MyWorkGridViewId;
  onClose: () => void;
  onLayoutChange: (layout: MyWorkGridLayout) => void;
  onSaveCurrentFilters: () => void;
  onSelectView: (view: MyWorkGridViewId) => void;
  projectOptions: readonly MyWorkItemViewModel["project"][];
}): React.JSX.Element {
  const { t } = useI18n();
  const currentPreference =
    controller.preferences.viewLayouts.find(
      (candidate) => candidate.viewId === currentView,
    ) ?? controller.preferences.viewLayouts[0];
  const layout = currentPreference?.layout ?? defaultMyWorkGridLayout();
  const hidden = new Set(layout.hiddenColumnIds);
  const isFavorite =
    controller.preferences.favoriteViewIds.includes(currentView);
  const controlsDisabled = !controller.canUpdate;
  const statusCopy = {
    failed: {
      label: t("Not saved"),
      tone: "danger" as const,
      text: t(
        "Personal grid settings were not saved. The last confirmed settings remain active.",
      ),
    },
    loading: {
      label: t("Loading"),
      tone: "info" as const,
      text: t("Loading personal grid settings"),
    },
    ready:
      controller.preferences.recoveryReason === "stored_preference_invalid"
        ? {
            label: t("Defaults active"),
            tone: "warning" as const,
            text: t(
              "Stored grid settings were invalid. Code-owned defaults are active.",
            ),
          }
        : {
            label: t("Confirmed"),
            tone: "neutral" as const,
            text: t("Personal grid settings are confirmed by the server."),
          },
    saving: {
      label: t("Saving"),
      tone: "info" as const,
      text: t("Saving personal grid settings"),
    },
    unavailable: {
      label: t("Unavailable"),
      tone: "warning" as const,
      text: t(
        "Session verification is required before personal grid settings can be saved.",
      ),
    },
  }[controller.status];
  const toggleFavorite = (): void => {
    const favoriteViewIds = isFavorite
      ? controller.preferences.favoriteViewIds.filter(
          (viewId) => viewId !== currentView,
        )
      : [...controller.preferences.favoriteViewIds, currentView];
    controller.update({ favoriteViewIds, viewId: currentView });
  };
  const setHidden = (columnId: MyWorkGridColumnId, visible: boolean): void => {
    const hiddenColumnIds = visible
      ? layout.hiddenColumnIds.filter((candidate) => candidate !== columnId)
      : layout.columnOrder.filter(
          (candidate) => candidate === columnId || hidden.has(candidate),
        );
    onLayoutChange({ ...layout, hiddenColumnIds });
  };

  return (
    <section aria-label={t("Personal grid settings")} className="grid-settings">
      <header className="grid-settings__header">
        <div className="grid-settings__title">
          <strong>{t("Personal grid settings")}</strong>
          <span
            aria-atomic="true"
            aria-live="polite"
            className="grid-settings__status-copy"
            role="status"
          >
            {statusCopy.text}
          </span>
        </div>
        <SemanticStatus label={statusCopy.label} tone={statusCopy.tone} />
        <Button onClick={onClose} visual="ghost">
          {t("Close settings")}
        </Button>
      </header>
      {controller.failure ? (
        <div className="grid-settings__failure">
          <RequestFailurePanel failure={controller.failure} />
          <Button icon="refresh" onClick={controller.reload} visual="secondary">
            {t("Reload personal settings")}
          </Button>
        </div>
      ) : null}
      <div className="grid-settings__body">
        <fieldset
          className="grid-settings__columns"
          disabled={controlsDisabled}
        >
          <legend>{t("Columns and widths")}</legend>
          {layout.columnOrder.map((columnId, index) => {
            const label = gridColumnLabel(t, columnId);
            const required = requiredGridColumns.has(columnId);
            return (
              <div className="grid-settings__column" key={columnId}>
                <label>
                  <input
                    checked={!hidden.has(columnId)}
                    disabled={controlsDisabled || required}
                    onChange={(event) => {
                      setHidden(columnId, event.currentTarget.checked);
                    }}
                    type="checkbox"
                  />
                  <span>{label}</span>
                </label>
                <span className="grid-settings__width">
                  {t("{{width}} pixels", {
                    width: layout.widths[columnId],
                  })}
                </span>
                <div className="grid-settings__column-actions">
                  <Button
                    aria-label={t("Move {{column}} left", {
                      column: label,
                    })}
                    disabled={controlsDisabled || index === 0}
                    onClick={() => {
                      onLayoutChange(moveGridColumn(layout, columnId, -1));
                    }}
                    visual="ghost"
                  >
                    ←
                  </Button>
                  <Button
                    aria-label={t("Move {{column}} right", {
                      column: label,
                    })}
                    disabled={
                      controlsDisabled ||
                      index === layout.columnOrder.length - 1
                    }
                    onClick={() => {
                      onLayoutChange(moveGridColumn(layout, columnId, 1));
                    }}
                    visual="ghost"
                  >
                    →
                  </Button>
                  <Button
                    aria-label={t("Reset {{column}} width", {
                      column: label,
                    })}
                    disabled={controlsDisabled}
                    onClick={() => {
                      onLayoutChange({
                        ...layout,
                        widths: {
                          ...layout.widths,
                          [columnId]:
                            myWorkGridColumnWidthSpecs[columnId].default,
                        },
                      });
                    }}
                    visual="ghost"
                  >
                    {t("Reset")}
                  </Button>
                </div>
              </div>
            );
          })}
        </fieldset>
        <fieldset
          className="grid-settings__personal"
          disabled={controlsDisabled}
        >
          <legend>{t("Personal view")}</legend>
          <label>
            <span>{t("Fixed columns")}</span>
            <Select
              aria-label={t("Fixed columns")}
              disabled={controlsDisabled}
              onChange={(event) => {
                onLayoutChange({
                  ...layout,
                  fixedColumnCount: Number.parseInt(
                    event.currentTarget.value,
                    10,
                  ),
                });
              }}
              value={String(layout.fixedColumnCount)}
            >
              <option value="0">{t("No fixed columns")}</option>
              <option value="1">{t("One fixed column")}</option>
              <option value="2">{t("Two fixed columns")}</option>
            </Select>
          </label>
          <label>
            <input
              checked={isFavorite}
              onChange={toggleFavorite}
              type="checkbox"
            />
            <span>{t("Favorite this view")}</span>
          </label>
          <label>
            <span>{t("Default Project")}</span>
            <Select
              aria-label={t("Default Project")}
              disabled={controlsDisabled}
              onChange={(event) => {
                const candidate = event.currentTarget.value;
                controller.update({
                  defaultProjectId: projectOptions.some(
                    (project) => project.globalId === candidate,
                  )
                    ? candidate
                    : null,
                  viewId: currentView,
                });
              }}
              value={controller.preferences.defaultProjectId ?? ""}
            >
              <option value="">{t("No default Project")}</option>
              {projectOptions.map((project) => (
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
          <Button
            disabled={controlsDisabled}
            onClick={onSaveCurrentFilters}
            visual="secondary"
          >
            {t("Save current filters")}
          </Button>
          <Button
            disabled={controlsDisabled}
            onClick={() => {
              onLayoutChange(defaultMyWorkGridLayout());
            }}
            visual="secondary"
          >
            {t("Reset grid layout")}
          </Button>
        </fieldset>
        <div className="grid-settings__access">
          <section>
            <h3>{t("Favorite views")}</h3>
            <div className="grid-settings__view-links">
              {controller.preferences.favoriteViewIds.length === 0 ? (
                <span>{t("No favorite views")}</span>
              ) : (
                controller.preferences.favoriteViewIds.map((viewId) => (
                  <Button
                    disabled={controlsDisabled}
                    key={viewId}
                    onClick={() => {
                      onSelectView(viewId);
                    }}
                    visual="ghost"
                  >
                    {viewLabel(t, viewId)}
                  </Button>
                ))
              )}
            </div>
          </section>
          <section>
            <h3>{t("Recent views")}</h3>
            <div className="grid-settings__view-links">
              {controller.preferences.recentViewIds.length === 0 ? (
                <span>{t("No recent views")}</span>
              ) : (
                controller.preferences.recentViewIds.map((viewId) => (
                  <Button
                    disabled={controlsDisabled}
                    key={viewId}
                    onClick={() => {
                      onSelectView(viewId);
                    }}
                    visual="ghost"
                  >
                    {viewLabel(t, viewId)}
                  </Button>
                ))
              )}
            </div>
          </section>
        </div>
        <div className="grid-settings__capabilities">
          <DefinitionList
            rows={[
              {
                label: t("Sorting and grouping"),
                value: t("Server-defined for this live worklist"),
              },
              {
                label: t("Bulk actions"),
                value: t("Domain bulk-action contract required"),
              },
              {
                label: t("Export"),
                value: t("Export contract required"),
              },
              {
                label: t("Shared view publishing"),
                value: t("Publisher authority policy required"),
              },
            ]}
          />
        </div>
      </div>
    </section>
  );
}

export function LiveMyWorklist({
  dataSource,
  gridPreferencesDataSource,
  navigate,
  panePreferencesDataSource,
}: {
  dataSource: MyWorkDataSource;
  gridPreferencesDataSource?: MyWorkGridPreferencesDataSource;
  navigate: (target: string) => void;
  panePreferencesDataSource?: MyWorkInspectorPreferencesDataSource;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const personalization = useMyWorkGridPersonalization({
    ...(gridPreferencesDataSource
      ? { dataSource: gridPreferencesDataSource }
      : {}),
    session: sessionCommandContext,
  });
  const inspectorPersonalization = useMyWorkInspectorPersonalization({
    ...(panePreferencesDataSource
      ? { dataSource: panePreferencesDataSource }
      : {}),
    session: sessionCommandContext,
  });
  const generation = useRef(0);
  const appliedPreferenceLoad = useRef(0);
  const [view, setView] = useState<MyWorkView>("all");
  const [projectId, setProjectId] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("all");
  const [search, setSearch] = useState("");
  const [cursorStack, setCursorStack] = useState<
    readonly (string | undefined)[]
  >([undefined]);
  const [attempt, setAttempt] = useState(0);
  const [selectedId, setSelectedId] = useState("");
  const [gridSettingsOpen, setGridSettingsOpen] = useState(false);
  const [knownProjects, setKnownProjects] = useState<
    readonly MyWorkItemViewModel["project"][]
  >([]);
  useEffect(() => {
    let cancelled = false;
    if (
      personalization.failure ||
      personalization.preferences.recoveryReason === "stored_preference_invalid"
    ) {
      queueMicrotask(() => {
        if (!cancelled) setGridSettingsOpen(true);
      });
    }
    return () => {
      cancelled = true;
    };
  }, [personalization.failure, personalization.preferences.recoveryReason]);
  const priority = priorityValues.get(priorityFilter) ?? null;
  const cursor = cursorStack.at(-1);
  const query = useMemo<MyWorkQuery>(() => {
    const nextQuery: MyWorkQuery = { limit: liveMyWorkPageSize, view };
    if (projectId) nextQuery.projectId = projectId;
    if (priority) nextQuery.priority = priority;
    const boundedSearch = truncateMyWorkGridSearch(search.trim());
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

  useEffect(() => {
    if (
      personalization.loadEpoch === 0 ||
      personalization.loadEpoch <= appliedPreferenceLoad.current
    ) {
      return;
    }
    const stored = personalization.preferences.viewLayouts.find(
      (candidate) => candidate.viewId === view,
    );
    if (!stored) return;
    const preferredProjectId = stored.hasSavedFilter
      ? stored.filter.projectId
      : personalization.preferences.defaultProjectId;
    if (preferredProjectId && knownProjects.length === 0) {
      return;
    }
    const loadEpoch = personalization.loadEpoch;
    const nextProjectId =
      preferredProjectId &&
      knownProjects.some((project) => project.globalId === preferredProjectId)
        ? preferredProjectId
        : "";
    const nextPriorityFilter = fromGridPriority(stored.filter.priority);
    const nextSearch = stored.filter.search;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled || loadEpoch <= appliedPreferenceLoad.current) return;
      appliedPreferenceLoad.current = loadEpoch;
      setProjectId(nextProjectId);
      setPriorityFilter(nextPriorityFilter);
      setSearch(nextSearch);
      setCursorStack([undefined]);
      setSelectedId("");
    });
    return () => {
      cancelled = true;
    };
  }, [
    knownProjects,
    personalization.loadEpoch,
    personalization.preferences,
    view,
  ]);

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
  const currentViewPreference =
    personalization.preferences.viewLayouts.find(
      (candidate) => candidate.viewId === view,
    ) ?? personalization.preferences.viewLayouts[0];
  const currentLayout =
    currentViewPreference?.layout ?? defaultMyWorkGridLayout();
  const currentGridFilter: MyWorkGridFilter = {
    priority: toGridPriority(priorityFilter),
    projectId: projectId || null,
    search: truncateMyWorkGridSearch(search.trim()),
  };
  const selectGridView = (nextView: MyWorkGridViewId): void => {
    setView(nextView);
    const stored = personalization.preferences.viewLayouts.find(
      (candidate) => candidate.viewId === nextView,
    );
    if (stored) {
      const preferredProjectId = stored.hasSavedFilter
        ? stored.filter.projectId
        : personalization.preferences.defaultProjectId;
      setProjectId(
        preferredProjectId &&
          knownProjects.some(
            (project) => project.globalId === preferredProjectId,
          )
          ? preferredProjectId
          : "",
      );
      setPriorityFilter(fromGridPriority(stored.filter.priority));
      setSearch(stored.filter.search);
    }
    resetPagination();
    personalization.update({
      recentViewIds: [
        nextView,
        ...personalization.preferences.recentViewIds.filter(
          (candidate) => candidate !== nextView,
        ),
      ].slice(0, 5),
      viewId: nextView,
    });
  };
  const updateGridLayout = (layout: MyWorkGridLayout): void => {
    personalization.update({ layout, viewId: view });
  };
  const gridColumns = useMemo<
    readonly DenseGridColumn<MyWorkItemViewModel, MyWorkGridColumnId>[]
  >(
    () => [
      {
        accessibilityLabel: t("Type"),
        defaultWidth: myWorkGridColumnWidthSpecs.type.default,
        id: "type",
        label: t("Type"),
        maximumWidth: myWorkGridColumnWidthSpecs.type.maximum,
        minimumWidth: myWorkGridColumnWidthSpecs.type.minimum,
        renderCell: (item) => (
          <SemanticStatus
            label={myWorkCategoryLabel(t, item.category)}
            tone={categoryTone(item)}
          />
        ),
      },
      {
        accessibilityLabel: t("Item"),
        defaultWidth: myWorkGridColumnWidthSpecs.item.default,
        id: "item",
        label: t("Item"),
        maximumWidth: myWorkGridColumnWidthSpecs.item.maximum,
        minimumWidth: myWorkGridColumnWidthSpecs.item.minimum,
        renderCell: (item) => (
          <strong data-language-exempt="business-data">{item.title}</strong>
        ),
      },
      {
        accessibilityLabel: t("Project or object"),
        defaultWidth: myWorkGridColumnWidthSpecs.context.default,
        id: "context",
        label: t("Project or object"),
        maximumWidth: myWorkGridColumnWidthSpecs.context.maximum,
        minimumWidth: myWorkGridColumnWidthSpecs.context.minimum,
        renderCell: (item) => (
          <>
            <span data-language-exempt="identifier">
              {item.project.businessCode}
            </span>
            <br />
            <span data-language-exempt="business-data">
              {item.context.title}
            </span>
          </>
        ),
      },
      {
        accessibilityLabel: t("Why assigned"),
        defaultWidth: myWorkGridColumnWidthSpecs.assignment.default,
        id: "assignment",
        label: t("Why assigned"),
        maximumWidth: myWorkGridColumnWidthSpecs.assignment.maximum,
        minimumWidth: myWorkGridColumnWidthSpecs.assignment.minimum,
        renderCell: (item) => myWorkWhyLabel(t, item.why),
      },
      {
        accessibilityLabel: t("Priority"),
        defaultWidth: myWorkGridColumnWidthSpecs.priority.default,
        id: "priority",
        label: t("Priority"),
        maximumWidth: myWorkGridColumnWidthSpecs.priority.maximum,
        minimumWidth: myWorkGridColumnWidthSpecs.priority.minimum,
        renderCell: (item) => myWorkPriorityLabel(t, item.priority),
      },
      {
        accessibilityLabel: t("Due"),
        defaultWidth: myWorkGridColumnWidthSpecs.due.default,
        id: "due",
        label: t("Due"),
        maximumWidth: myWorkGridColumnWidthSpecs.due.maximum,
        minimumWidth: myWorkGridColumnWidthSpecs.due.minimum,
        renderCell: (item) => (
          <div className="my-work-due">
            {item.dueAt === null ? null : (
              <time dateTime={item.dueAt}>
                {formatDateTime(locale, item.dueAt, page?.timeZone)}
              </time>
            )}
            <SemanticStatus
              label={myWorkDueStateLabel(t, item.dueState)}
              tone={dueStateTone(item.dueState)}
            />
          </div>
        ),
      },
      {
        accessibilityLabel: t("Status"),
        defaultWidth: myWorkGridColumnWidthSpecs.status.default,
        id: "status",
        label: t("Status"),
        maximumWidth: myWorkGridColumnWidthSpecs.status.maximum,
        minimumWidth: myWorkGridColumnWidthSpecs.status.minimum,
        renderCell: (item) => (
          <SemanticStatus
            label={myWorkStatusLabel(t, item.status)}
            tone={statusTone(item.status)}
          />
        ),
      },
      {
        accessibilityLabel: t("Next action"),
        defaultWidth: myWorkGridColumnWidthSpecs.action.default,
        id: "action",
        label: t("Next action"),
        maximumWidth: myWorkGridColumnWidthSpecs.action.maximum,
        minimumWidth: myWorkGridColumnWidthSpecs.action.minimum,
        renderCell: (item) => (
          <Button
            onClick={(event) => {
              event.stopPropagation();
              navigate(myWorkTargetPath(item));
            }}
            visual="ghost"
          >
            {myWorkActionLabel(t, item.action)}
          </Button>
        ),
      },
    ],
    [locale, navigate, page?.timeZone, t],
  );
  const gridRows =
    currentState.kind === "loaded" ? currentState.page.items : [];
  const gridEmptyContent =
    currentState.kind === "loading" ? (
      <div className="table-empty" role="status">
        {t("Loading My Work")}
      </div>
    ) : currentState.kind === "failed" ? (
      <FailureState
        failure={currentState.failure}
        reload={reload}
        retry={retry}
      />
    ) : (
      <div className="table-empty">
        <span>{t("No assigned work is available in this view.")}</span>
        {filtersApplied ? (
          <Button onClick={clearFilters}>{t("Clear filters")}</Button>
        ) : null}
      </div>
    );

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
                    selectGridView(parseView(event.currentTarget.value));
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
                  onChange={(event) => {
                    setSearch(
                      truncateMyWorkGridSearch(event.currentTarget.value),
                    );
                    resetPagination();
                  }}
                  placeholder={t("Search assigned work")}
                  type="search"
                  value={search}
                />
              </label>
              <Button
                aria-expanded={gridSettingsOpen}
                icon="maintenance"
                onClick={() => {
                  setGridSettingsOpen((current) => !current);
                }}
                visual="secondary"
              >
                {t("Grid settings")}
              </Button>
            </div>
          }
          className="worklist-panel"
          title={t("Worklist")}
        >
          {gridSettingsOpen ? (
            <div id="my-work-grid-settings">
              <GridSettings
                controller={personalization}
                currentView={view}
                onClose={() => {
                  setGridSettingsOpen(false);
                }}
                onLayoutChange={updateGridLayout}
                onSaveCurrentFilters={() => {
                  personalization.update({
                    filter: currentGridFilter,
                    viewId: view,
                  });
                }}
                onSelectView={selectGridView}
                projectOptions={knownProjects}
              />
            </div>
          ) : null}
          <DenseGrid
            ariaBusy={currentState.kind === "loading"}
            ariaLabel={t("My Work grid")}
            className="table-scroll"
            columns={gridColumns}
            emptyContent={gridEmptyContent}
            getRowKey={(item) => item.id}
            getRowProperties={(item) => ({
              "aria-selected": item.id === selected?.id,
              className: item.id === selected?.id ? "is-selected" : undefined,
              onClick: () => {
                setSelectedId(item.id);
              },
              onKeyDown: (event) => {
                if (event.target !== event.currentTarget) return;
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedId(item.id);
                }
              },
              tabIndex: 0,
            })}
            interactionDisabled={!personalization.canUpdate}
            layout={currentLayout}
            onLayoutChange={(
              change: DenseGridLayoutChange<MyWorkGridColumnId>,
            ) => {
              updateGridLayout(change.layout);
            }}
            resizeColumnLabel={(column) =>
              t("Resize {{column}} column", { column })
            }
            resizeHelp={t(
              "Use Left and Right Arrow keys to resize. Press Home or End for the limit, or Enter to fit the rendered rows.",
            )}
            rows={gridRows}
          />
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
          <DockedInspector
            layout={{
              canUpdate: inspectorPersonalization.canUpdate,
              collapsed: inspectorPersonalization.preference.collapsed,
              failure: inspectorPersonalization.failure,
              onChange: inspectorPersonalization.update,
              onReload: inspectorPersonalization.reload,
              recoveryReason:
                inspectorPersonalization.preference.recoveryReason,
              status: inspectorPersonalization.status,
              widthPx: inspectorPersonalization.preference.widthPx,
            }}
            title={t("Work item details")}
          >
            <DefinitionList
              rows={[
                {
                  exempt: "business-data",
                  label: t("Item"),
                  rowKey: "item",
                  value: selected.title,
                },
                {
                  exempt: "identifier",
                  label: t("Project"),
                  rowKey: "project",
                  value: selected.project.businessCode,
                },
                {
                  exempt: "business-data",
                  label: t("Project title"),
                  rowKey: "project-title",
                  value: selected.project.title,
                },
                {
                  exempt: "identifier",
                  label: t("Context"),
                  rowKey: "context",
                  value: selected.context.code,
                },
                {
                  exempt: "business-data",
                  label: t("Context title"),
                  rowKey: "context-title",
                  value: selected.context.title,
                },
                {
                  label: t("Why assigned"),
                  rowKey: "why-assigned",
                  value: myWorkWhyLabel(t, selected.why),
                },
                {
                  label: t("Priority"),
                  rowKey: "priority",
                  value: myWorkPriorityLabel(t, selected.priority),
                },
                {
                  label: t("Due"),
                  rowKey: "due",
                  value:
                    selected.dueAt === null
                      ? t("No due date")
                      : formatDateTime(locale, selected.dueAt, page?.timeZone),
                },
                {
                  label: t("Due state"),
                  rowKey: "due-state",
                  value: myWorkDueStateLabel(t, selected.dueState),
                },
                {
                  exempt: "identifier",
                  label: t("Due time zone"),
                  rowKey: "due-time-zone",
                  value: page?.timeZone ?? "UTC",
                },
                {
                  label: t("Assignment source"),
                  rowKey: "assignment-source",
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
