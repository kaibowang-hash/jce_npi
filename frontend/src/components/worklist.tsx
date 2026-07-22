import { Fragment, useEffect, useRef, useState } from "react";

import type {
  SavedWorklistView,
  WorklistDataSource,
  WorklistGroup,
  WorklistPage,
} from "../api/worklist-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { WorkItemViewModel } from "../domain/view-models";
import {
  actionLabel,
  assignmentLabel,
  syncStateLabel,
  workKindLabel,
  workTitleLabel,
} from "../i18n/copy";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";
import { DockedInspector } from "./object-components";
import { RequestFailurePanel } from "./problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
  SourceBadge,
  SyncBadge,
} from "./primitives";

export const worklistWindowSize = 20;
const savedViewStorageKey = "npi-one-worklist-saved-view";
const worklistConfigurationKey = "npi-one-worklist-configuration";
const worklistNavigationKey = "npi-one-worklist-navigation";

interface WorklistConfiguration {
  groupBy: WorklistGroup;
  showAssignment: boolean;
  showDue: boolean;
  sortDescending: boolean;
}

interface WorklistNavigationState {
  offset: number;
  scrollTop: number;
  selectedId: string;
}

function initialSavedView(): SavedWorklistView {
  const stored = globalThis.localStorage.getItem(savedViewStorageKey);
  return stored === "overdue" ||
    stored === "approvals" ||
    stored === "integration"
    ? stored
    : "focus";
}

function initialConfiguration(): WorklistConfiguration {
  try {
    const parsed = JSON.parse(
      globalThis.localStorage.getItem(worklistConfigurationKey) ?? "null",
    ) as Partial<WorklistConfiguration> | null;
    return {
      groupBy:
        parsed?.groupBy === "context" || parsed?.groupBy === "kind"
          ? parsed.groupBy
          : "none",
      showAssignment: parsed?.showAssignment !== false,
      showDue: parsed?.showDue !== false,
      sortDescending: parsed?.sortDescending === true,
    };
  } catch {
    return {
      groupBy: "none",
      showAssignment: true,
      showDue: true,
      sortDescending: false,
    };
  }
}

function initialNavigationState(): WorklistNavigationState {
  try {
    const parsed = JSON.parse(
      globalThis.localStorage.getItem(worklistNavigationKey) ?? "null",
    ) as Partial<WorklistNavigationState> | null;
    return {
      offset:
        typeof parsed?.offset === "number" && parsed.offset >= 0
          ? parsed.offset
          : 0,
      scrollTop:
        typeof parsed?.scrollTop === "number" && parsed.scrollTop >= 0
          ? parsed.scrollTop
          : 0,
      selectedId:
        typeof parsed?.selectedId === "string" ? parsed.selectedId : "",
    };
  } catch {
    return { offset: 0, scrollTop: 0, selectedId: "" };
  }
}

function statusTone(
  item: WorkItemViewModel,
): "neutral" | "info" | "success" | "warning" | "danger" {
  switch (item.status) {
    case "blocked":
    case "failed_final":
      return "danger";
    case "failed_retryable":
    case "partial":
    case "stale":
    case "conflict":
      return "warning";
    case "pending":
    case "processing":
    case "pending_approval":
      return "info";
    case "synced":
      return "success";
    case "local":
    case "not_started":
      return "neutral";
  }
}

export function Worklist({
  asOf,
  dataSource,
  onOpen,
}: {
  asOf: string;
  dataSource: WorklistDataSource;
  onOpen: (item: WorkItemViewModel) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [initialPreferences] = useState(initialConfiguration);
  const [initialNavigation] = useState(initialNavigationState);
  const tableScrollRef = useRef<HTMLDivElement | null>(null);
  const restoreScrollTop = useRef(initialNavigation.scrollTop);
  const [filter, setFilter] = useState("");
  const [sortDescending, setSortDescending] = useState(
    initialPreferences.sortDescending,
  );
  const [windowStart, setWindowStart] = useState(initialNavigation.offset);
  const [selectedId, setSelectedId] = useState(initialNavigation.selectedId);
  const [savedView, setSavedView] =
    useState<SavedWorklistView>(initialSavedView);
  const [groupBy, setGroupBy] = useState<WorklistGroup>(
    initialPreferences.groupBy,
  );
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [showAssignment, setShowAssignment] = useState(
    initialPreferences.showAssignment,
  );
  const [showDue, setShowDue] = useState(initialPreferences.showDue);
  const [queryResult, setQueryResult] = useState<{
    dataSource: WorklistDataSource | null;
    failure: RequestFailure | null;
    page: WorklistPage | null;
    signature: string;
  }>({ dataSource: null, failure: null, page: null, signature: "" });
  const [queryNonce, setQueryNonce] = useState(0);
  const [collapsedGroups, setCollapsedGroups] = useState<readonly string[]>([]);
  const querySignature = JSON.stringify({
    asOf,
    filter,
    groupBy,
    queryNonce,
    savedView,
    sortDescending,
    windowStart,
  });
  useEffect(() => {
    globalThis.localStorage.setItem(savedViewStorageKey, savedView);
  }, [savedView]);
  useEffect(() => {
    globalThis.localStorage.setItem(
      worklistConfigurationKey,
      JSON.stringify({ groupBy, showAssignment, showDue, sortDescending }),
    );
  }, [groupBy, showAssignment, showDue, sortDescending]);
  useEffect(() => {
    const currentScrollTop = tableScrollRef.current?.scrollTop ?? 0;
    globalThis.localStorage.setItem(
      worklistNavigationKey,
      JSON.stringify({
        offset: windowStart,
        scrollTop: currentScrollTop,
        selectedId,
      }),
    );
  }, [selectedId, windowStart]);
  useEffect(() => {
    let active = true;
    void dataSource
      .query({
        asOf,
        filter,
        groupBy,
        limit: worklistWindowSize,
        offset: windowStart,
        savedView,
        sortDescending,
      })
      .then((result) => {
        if (active) {
          setQueryResult({
            dataSource,
            failure: null,
            page: result,
            signature: querySignature,
          });
          setSelectedId((current) =>
            result.items.some((item) => item.id === current)
              ? current
              : (result.items[0]?.id ?? ""),
          );
          globalThis.queueMicrotask(() => {
            if (tableScrollRef.current) {
              tableScrollRef.current.scrollTop = restoreScrollTop.current;
              restoreScrollTop.current = 0;
            }
          });
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setQueryResult({
            dataSource,
            failure: toRequestFailure(error),
            page: null,
            signature: querySignature,
          });
        }
      });
    return () => {
      active = false;
    };
  }, [
    asOf,
    dataSource,
    filter,
    groupBy,
    queryNonce,
    querySignature,
    savedView,
    sortDescending,
    windowStart,
  ]);
  const hasCurrentQuery =
    queryResult.dataSource === dataSource &&
    queryResult.signature === querySignature;
  const page = hasCurrentQuery ? queryResult.page : null;
  const queryFailure = hasCurrentQuery ? queryResult.failure : null;
  const visible = page?.items ?? [];
  const selected = visible.find((item) => item.id === selectedId) ?? visible[0];

  return (
    <div className="worklist-layout">
      <Panel
        actions={
          <div className="table-tools">
            <label>
              <span className="visually-hidden">{t("Saved view")}</span>
              <Select
                aria-label={t("Saved view")}
                onChange={(event) => {
                  setSavedView(event.currentTarget.value as SavedWorklistView);
                  setWindowStart(0);
                }}
                value={savedView}
              >
                <option value="focus">{t("All assigned work")}</option>
                <option value="overdue">{t("Overdue")}</option>
                <option value="approvals">{t("Pending approvals")}</option>
                <option value="integration">
                  {t("Integration exceptions")}
                </option>
              </Select>
            </label>
            <label>
              <span className="visually-hidden">{t("Group by")}</span>
              <Select
                aria-label={t("Group by")}
                onChange={(event) => {
                  setGroupBy(event.currentTarget.value as WorklistGroup);
                  setCollapsedGroups([]);
                  setWindowStart(0);
                }}
                value={groupBy}
              >
                <option value="none">{t("No grouping")}</option>
                <option value="context">{t("Project or object")}</option>
                <option value="kind">{t("Type")}</option>
              </Select>
            </label>
            <label>
              <span className="visually-hidden">{t("Filter")}</span>
              <TextInput
                aria-label={t("Filter")}
                onChange={(event) => {
                  setFilter(event.currentTarget.value);
                  setWindowStart(0);
                }}
                placeholder={t("Filter by project or object")}
                type="search"
                value={filter}
              />
            </label>
            <Button
              icon="filter"
              onClick={() => {
                setSortDescending((current) => !current);
              }}
            >
              {sortDescending ? t("Oldest first") : t("Newest first")}
            </Button>
            <Button
              aria-controls="worklist-column-settings"
              aria-expanded={columnsOpen}
              onClick={() => {
                setColumnsOpen((current) => !current);
              }}
            >
              {t("Columns")}
            </Button>
          </div>
        }
        className="worklist-panel"
        title={t("Worklist")}
      >
        {columnsOpen ? (
          <fieldset className="column-settings" id="worklist-column-settings">
            <legend>{t("Columns")}</legend>
            <label>
              <input
                checked={showAssignment}
                onChange={(event) => {
                  setShowAssignment(event.currentTarget.checked);
                }}
                type="checkbox"
              />
              {t("Why assigned")}
            </label>
            <label>
              <input
                checked={showDue}
                onChange={(event) => {
                  setShowDue(event.currentTarget.checked);
                }}
                type="checkbox"
              />
              {t("Due")}
            </label>
          </fieldset>
        ) : null}
        <div
          className="table-scroll"
          data-window-size={worklistWindowSize}
          onScroll={(event) => {
            globalThis.localStorage.setItem(
              worklistNavigationKey,
              JSON.stringify({
                offset: windowStart,
                scrollTop: event.currentTarget.scrollTop,
                selectedId,
              }),
            );
          }}
          ref={tableScrollRef}
        >
          <table
            className="data-table"
            role={groupBy === "none" ? undefined : "treegrid"}
          >
            {groupBy === "none" ? null : (
              <caption>
                {t("Grouped by {{field}}", {
                  field:
                    groupBy === "context" ? t("Project or object") : t("Type"),
                })}
              </caption>
            )}
            <thead>
              <tr>
                <th scope="col">{t("Type")}</th>
                <th scope="col">{t("Item")}</th>
                <th scope="col">{t("Project or object")}</th>
                {showAssignment ? (
                  <th scope="col">{t("Why assigned")}</th>
                ) : null}
                {showDue ? <th scope="col">{t("Due")}</th> : null}
                <th scope="col">{t("Status")}</th>
                <th scope="col">{t("Next action")}</th>
              </tr>
            </thead>
            <tbody>
              {!page && !queryFailure ? (
                <tr>
                  <td colSpan={5 + Number(showAssignment) + Number(showDue)}>
                    <div aria-busy="true" className="table-empty">
                      <span>{t("Loading worklist")}</span>
                    </div>
                  </td>
                </tr>
              ) : queryFailure ? (
                <tr>
                  <td colSpan={5 + Number(showAssignment) + Number(showDue)}>
                    <div className="table-empty table-empty--error">
                      <span>
                        {t(
                          "The worklist query failed. No data was changed. Change a filter or retry.",
                        )}
                      </span>
                      <RequestFailurePanel failure={queryFailure} />
                      <Button
                        onClick={() => {
                          setQueryNonce((current) => current + 1);
                        }}
                      >
                        {t("Retry")}
                      </Button>
                    </div>
                  </td>
                </tr>
              ) : visible.length === 0 ? (
                <tr>
                  <td colSpan={5 + Number(showAssignment) + Number(showDue)}>
                    <div className="table-empty">
                      <span>{t("No items match this view.")}</span>
                      <Button
                        onClick={() => {
                          setFilter("");
                          setSavedView("focus");
                          setWindowStart(0);
                        }}
                      >
                        {t("Clear filters")}
                      </Button>
                    </div>
                  </td>
                </tr>
              ) : (
                visible.map((item, index) => {
                  const groupKey =
                    groupBy === "context"
                      ? item.contextCode
                      : groupBy === "kind"
                        ? item.kind
                        : "";
                  const previousGroupKey =
                    groupBy === "context"
                      ? visible[index - 1]?.contextCode
                      : groupBy === "kind"
                        ? visible[index - 1]?.kind
                        : "";
                  const groupStart =
                    groupBy !== "none" && groupKey !== previousGroupKey;
                  const collapsed = collapsedGroups.includes(groupKey);
                  return (
                    <Fragment key={item.id}>
                      {groupStart ? (
                        <tr aria-level={1} className="worklist-group-row">
                          <th
                            colSpan={
                              5 + Number(showAssignment) + Number(showDue)
                            }
                            scope="rowgroup"
                          >
                            <button
                              aria-expanded={!collapsed}
                              aria-label={t("Toggle group")}
                              className="worklist-group-toggle"
                              onClick={() => {
                                setCollapsedGroups((current) =>
                                  current.includes(groupKey)
                                    ? current.filter((key) => key !== groupKey)
                                    : [...current, groupKey],
                                );
                              }}
                              type="button"
                            >
                              {groupBy === "context" ? (
                                <>
                                  <span data-language-exempt="identifier">
                                    {item.contextCode}
                                  </span>{" "}
                                  <span data-language-exempt="business-data">
                                    {item.contextName}
                                  </span>
                                </>
                              ) : (
                                workKindLabel(t, item.kind)
                              )}
                            </button>
                          </th>
                        </tr>
                      ) : null}
                      {collapsed ? null : (
                        <tr
                          aria-level={groupBy === "none" ? undefined : 2}
                          aria-selected={selected?.id === item.id}
                          className={
                            selected?.id === item.id ? "is-selected" : undefined
                          }
                          data-group-start={
                            groupBy === "context"
                              ? visible[index - 1]?.contextCode !==
                                item.contextCode
                              : groupBy === "kind"
                                ? visible[index - 1]?.kind !== item.kind
                                : undefined
                          }
                          onClick={() => {
                            setSelectedId(item.id);
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedId(item.id);
                            }
                          }}
                          tabIndex={0}
                        >
                          <td>
                            <SemanticStatus
                              label={workKindLabel(t, item.kind)}
                              tone={item.blocking ? "danger" : "neutral"}
                            />
                          </td>
                          <td>
                            <strong>{workTitleLabel(t, item.titleCode)}</strong>
                          </td>
                          <td>
                            <span data-language-exempt="identifier">
                              {item.contextCode}
                            </span>
                            <br />
                            <span data-language-exempt="business-data">
                              {item.contextName}
                            </span>
                          </td>
                          {showAssignment ? (
                            <td>{assignmentLabel(t, item.assignmentCode)}</td>
                          ) : null}
                          {showDue ? (
                            <td>
                              <time dateTime={item.dueAt}>
                                {formatDateTime(locale, item.dueAt)}
                              </time>
                            </td>
                          ) : null}
                          <td>
                            <SemanticStatus
                              label={syncStateLabel(t, item.status)}
                              tone={statusTone(item)}
                            />
                          </td>
                          <td>
                            <Button
                              onClick={(event) => {
                                event.stopPropagation();
                                onOpen(item);
                              }}
                              visual="ghost"
                            >
                              {actionLabel(t, item.actionCode)}
                            </Button>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <footer className="table-footer">
          <span>
            {t("Showing {{start}}–{{end}} of {{total}} items", {
              start: formatNumber(
                locale,
                (page?.total ?? 0) === 0 ? 0 : windowStart + 1,
                0,
              ),
              end: formatNumber(
                locale,
                Math.min(windowStart + worklistWindowSize, page?.total ?? 0),
                0,
              ),
              total: formatNumber(locale, page?.total ?? 0, 0),
            })}
          </span>
          <div>
            <Button
              disabled={windowStart === 0}
              onClick={() => {
                setWindowStart(Math.max(0, windowStart - worklistWindowSize));
              }}
            >
              {t("Previous page")}
            </Button>
            <Button
              disabled={!page || windowStart + worklistWindowSize >= page.total}
              onClick={() => {
                setWindowStart(windowStart + worklistWindowSize);
              }}
            >
              {t("Next page")}
            </Button>
          </div>
        </footer>
      </Panel>
      {selected ? (
        <DockedInspector title={t("Work item details")}>
          <DefinitionList
            rows={[
              {
                label: t("Item"),
                value: workTitleLabel(t, selected.titleCode),
              },
              {
                label: t("Why assigned"),
                value: assignmentLabel(t, selected.assignmentCode),
              },
              {
                label: t("Context"),
                value: selected.contextCode,
                exempt: "identifier",
              },
              {
                label: t("Due"),
                value: formatDateTime(locale, selected.dueAt),
              },
              {
                label: t("Editable in"),
                value:
                  selected.source.editableIn === "ERPNEXT"
                    ? t("ERPNext")
                    : selected.source.editableIn === "NPI_ONE"
                      ? t("NPI One")
                      : t("No system is editable"),
              },
            ]}
          />
          <div className="inspector-badges">
            <SourceBadge source={selected.source} />
            <SyncBadge state={selected.source.syncState} />
          </div>
          <Button
            onClick={() => {
              onOpen(selected);
            }}
            visual="primary"
          >
            {actionLabel(t, selected.actionCode)}
          </Button>
        </DockedInspector>
      ) : null}
    </div>
  );
}
