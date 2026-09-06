import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  toolingListColumnIds,
  toolingListGroupKeys,
  toolingListSortDirections,
  toolingListSortKeys,
  toolingListViewIds,
  type ToolingExportPackage,
  type ToolingExportRequest,
  type ToolingListColumnId,
  type ToolingListDataSource,
  type ToolingListFilterSnapshot,
  type ToolingListGroupKey,
  type ToolingListPage,
  type ToolingListPreference,
  type ToolingListPreferenceSnapshot,
  type ToolingListRow,
  type ToolingListSortDirection,
  type ToolingListSortKey,
  type ToolingListViewId,
} from "../api/tooling-list-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { ToolingRequestCancelledError } from "../api/tooling-data-source";
import { RequestFailurePanel } from "./problem-details-panel";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
} from "./primitives";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import {
  DenseGrid,
  type DenseGridColumn,
  type DenseGridLayout,
} from "../ui-adapters/dense-grid";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };

type PreferenceCommandState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved" }
  | { kind: "failed"; failure: RequestFailure };

type ExportCommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | {
      kind: "failed";
      failure: RequestFailure;
      retry: { key: string; request: ToolingExportRequest };
    }
  | {
      kind: "succeeded";
      package: ToolingExportPackage;
      replayed: boolean;
    };

type DownloadCommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | {
      kind: "failed";
      failure: RequestFailure;
      retry: { key: string; package: ToolingExportPackage };
    }
  | { kind: "succeeded"; replayed: boolean };

type GridRow =
  | { kind: "group"; key: string; label: string }
  | { kind: "item"; key: string; value: ToolingListRow };

interface ListRequest {
  filter: ToolingListFilterSnapshot;
  cursor: string | null;
  sequence: number;
}

const pageSize = 50;
const defaultWidths: Readonly<Record<ToolingListColumnId, number>> = {
  selection: 64,
  tooling: 260,
  applicability: 112,
  part_revisions: 118,
  physical_sets: 112,
  design_revisions: 128,
  origin: 184,
  source: 150,
  action: 88,
};
const optionalColumns = [
  "applicability",
  "part_revisions",
  "physical_sets",
  "design_revisions",
  "origin",
  "source",
] as const;

function defaultFilter(viewId: ToolingListViewId): ToolingListFilterSnapshot {
  return {
    groupKey: "none",
    search: "",
    sortDirection: "asc",
    sortKey: "title",
    viewId,
  };
}

function normalizedFilter(
  filter: ToolingListFilterSnapshot,
): ToolingListFilterSnapshot {
  return { ...filter, search: filter.search.trim() };
}

function layoutFromPreference(
  preference: ToolingListPreferenceSnapshot,
): DenseGridLayout<ToolingListColumnId> {
  const widths = { ...defaultWidths };
  for (const entry of preference.columnWidths)
    widths[entry.columnId] = entry.width;
  return {
    columnOrder: preference.columnOrder,
    fixedColumnCount: 2,
    hiddenColumnIds: preference.hiddenColumns,
    widths,
  };
}

function preferenceFromLayout(
  viewId: ToolingListViewId,
  filter: ToolingListFilterSnapshot,
  layout: DenseGridLayout<ToolingListColumnId>,
): ToolingListPreferenceSnapshot {
  return {
    columnOrder: layout.columnOrder,
    columnWidths: layout.columnOrder.map((columnId) => ({
      columnId,
      width: layout.widths[columnId],
    })),
    filter,
    gridId: "tooling-list",
    hiddenColumns: layout.hiddenColumnIds.filter(
      (column): column is (typeof optionalColumns)[number] =>
        optionalColumns.includes(column as (typeof optionalColumns)[number]),
    ),
    tableSchemaVersion: "tooling-list-grid-v1",
    viewId,
  };
}

function viewLabel(
  t: ReturnType<typeof useI18n>["t"],
  viewId: ToolingListViewId,
): string {
  switch (viewId) {
    case "all":
      return t("All Tooling Masters");
    case "missing_applicability":
      return t("Missing applicability");
    case "single_part":
      return t("Single Part Revision");
    case "shared_parts":
      return t("Shared across Part Revisions");
    case "missing_physical_set":
      return t("Missing physical Set");
    case "single_physical_set":
      return t("Single physical Set");
    case "multiple_physical_sets":
      return t("Multiple physical Sets");
    case "missing_design_revision":
      return t("Missing design Revision");
    case "has_design_revision":
      return t("Has design Revision");
    case "customer_owned_set":
      return t("Customer-owned Set");
  }
}

function sortLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingListSortKey,
): string {
  switch (value) {
    case "title":
      return t("Tooling title");
    case "applicability_count":
      return t("Applicability count");
    case "physical_set_count":
      return t("Physical Set count");
    case "latest_revision_number":
      return t("Latest Revision number");
  }
}

function directionLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingListSortDirection,
): string {
  return value === "asc" ? t("Ascending") : t("Descending");
}

function groupLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingListGroupKey,
): string {
  switch (value) {
    case "none":
      return t("No grouping");
    case "applicability_scope":
      return t("Applicability scope");
    case "physical_set_presence":
      return t("Physical Set presence");
    case "design_revision_presence":
      return t("Design Revision presence");
  }
}

function columnLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingListColumnId,
): string {
  switch (value) {
    case "selection":
      return t("Selection");
    case "tooling":
      return t("Tooling Master");
    case "applicability":
      return t("Applicability");
    case "part_revisions":
      return t("Part Revisions");
    case "physical_sets":
      return t("Physical Sets");
    case "design_revisions":
      return t("Design Revisions");
    case "origin":
      return t("Origin");
    case "source":
      return t("Source");
    case "action":
      return t("Action");
  }
}

function groupValue(
  t: ReturnType<typeof useI18n>["t"],
  row: ToolingListRow,
  groupKey: ToolingListGroupKey,
): string {
  if (groupKey === "applicability_scope") {
    if (row.applicabilityCount === 0) return t("No applicability");
    return row.distinctPartRevisionCount > 1
      ? t("Shared Part Revision scope")
      : t("Single Part Revision scope");
  }
  if (groupKey === "physical_set_presence") {
    return row.physicalSetCount === 0
      ? t("No physical Set")
      : t("Physical Set recorded");
  }
  if (groupKey === "design_revision_presence") {
    return row.designRevisionCount === 0
      ? t("No design Revision")
      : t("Design Revision recorded");
  }
  return "";
}

function groupedRows(
  t: ReturnType<typeof useI18n>["t"],
  rows: readonly ToolingListRow[],
  groupKey: ToolingListGroupKey,
): readonly GridRow[] {
  const result: GridRow[] = [];
  let previousGroup: string | null = null;
  for (const row of rows) {
    if (groupKey !== "none") {
      const label = groupValue(t, row, groupKey);
      if (label !== previousGroup) {
        result.push({
          key: `group-${groupKey}-${label}`,
          kind: "group",
          label,
        });
        previousGroup = label;
      }
    }
    result.push({
      key: row.toolingMasterGlobalId,
      kind: "item",
      value: row,
    });
  }
  return result;
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function triggerDownload(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.download = fileName;
  anchor.href = url;
  anchor.hidden = true;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ToolingListWorkspace({
  dataSource,
  navigate,
  projectId,
  selectedMasterId,
}: {
  dataSource: ToolingListDataSource;
  navigate: (target: string) => void;
  projectId: string;
  selectedMasterId: string | null;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [viewId, setViewId] = useState<ToolingListViewId>("all");
  const [preference, setPreference] = useState<
    ResourceState<ToolingListPreference>
  >({ kind: "loading" });
  const [preferenceCommand, setPreferenceCommand] =
    useState<PreferenceCommandState>({ kind: "idle" });
  const [draftFilter, setDraftFilter] = useState<ToolingListFilterSnapshot>(
    defaultFilter("all"),
  );
  const [layout, setLayout] = useState<DenseGridLayout<ToolingListColumnId>>({
    columnOrder: toolingListColumnIds,
    fixedColumnCount: 2,
    hiddenColumnIds: [],
    widths: defaultWidths,
  });
  const [dirty, setDirty] = useState(false);
  const [listRequest, setListRequest] = useState<ListRequest | null>(null);
  const [list, setList] = useState<ResourceState<ToolingListPage>>({
    kind: "loading",
  });
  const [cursorHistory, setCursorHistory] = useState<
    readonly (string | null)[]
  >([]);
  const [selection, setSelection] = useState<ReadonlyMap<string, string>>(
    new Map(),
  );
  const [exportMode, setExportMode] = useState<"selection" | "filtered">(
    "selection",
  );
  const [reviewRequest, setReviewRequest] = useState<{
    count: number;
    request: ToolingExportRequest;
  } | null>(null);
  const [exportCommand, setExportCommand] = useState<ExportCommandState>({
    kind: "idle",
  });
  const [downloadCommand, setDownloadCommand] = useState<DownloadCommandState>({
    kind: "idle",
  });
  const [clock, setClock] = useState(() => Date.now());
  const [preferenceReload, setPreferenceReload] = useState(0);
  const preferenceController = useRef<AbortController | null>(null);
  const exportController = useRef<AbortController | null>(null);
  const downloadController = useRef<AbortController | null>(null);
  const exportTrigger = useRef<HTMLElement | null>(null);
  const loadedPage = list.kind === "loaded" ? list.value : null;
  const loadedPreference =
    preference.kind === "loaded" ? preference.value : null;
  const activePackage =
    exportCommand.kind === "succeeded" ? exportCommand.package : null;

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadPreference(projectId, viewId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        const filter = normalizedFilter(value.preference.filter);
        setPreference({ kind: "loaded", value });
        setDraftFilter(filter);
        setLayout(layoutFromPreference(value.preference));
        setListRequest({ cursor: null, filter, sequence: Date.now() });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        )
          return;
        setPreference({ kind: "failed", failure: toRequestFailure(error) });
        setList({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, preferenceReload, projectId, viewId]);

  useEffect(() => {
    if (!listRequest) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadList(
        projectId,
        listRequest.filter,
        pageSize,
        listRequest.cursor,
        controller.signal,
      )
      .then((value) => {
        if (!controller.signal.aborted) setList({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        )
          return;
        setList({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, listRequest, projectId]);

  useEffect(
    () => () => {
      preferenceController.current?.abort();
      exportController.current?.abort();
      downloadController.current?.abort();
    },
    [],
  );

  useEffect(() => {
    if (!activePackage) return undefined;
    const timer = globalThis.setInterval(() => {
      setClock(Date.now());
    }, 30_000);
    return () => {
      globalThis.clearInterval(timer);
    };
  }, [activePackage]);

  const applyFilter = useCallback((): void => {
    const filter = normalizedFilter(draftFilter);
    setDraftFilter(filter);
    setCursorHistory([]);
    setSelection(new Map());
    setList({ kind: "loading" });
    setListRequest({ cursor: null, filter, sequence: Date.now() });
  }, [draftFilter]);

  const savePreference = (): void => {
    if (!loadedPreference || !sessionCommandContext) return;
    const filter = normalizedFilter(draftFilter);
    const next = preferenceFromLayout(viewId, filter, layout);
    preferenceController.current?.abort();
    const controller = new AbortController();
    preferenceController.current = controller;
    setPreferenceCommand({ kind: "saving" });
    void dataSource
      .savePreference(
        projectId,
        viewId,
        {
          expectedSnapshotHash: loadedPreference.snapshotHash,
          expectedVersion: loadedPreference.optimisticVersion,
          preference: next,
        },
        sessionCommandContext.csrfToken,
        controller.signal,
      )
      .then((value) => {
        if (controller.signal.aborted) return;
        setPreference({ kind: "loaded", value });
        setPreferenceCommand({ kind: "saved" });
        setDirty(false);
        setDraftFilter(filter);
        setCursorHistory([]);
        setSelection(new Map());
        setList({ kind: "loading" });
        setListRequest({ cursor: null, filter, sequence: Date.now() });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        )
          return;
        setPreferenceCommand({
          failure: toRequestFailure(error),
          kind: "failed",
        });
      });
  };

  const reloadPreference = (): void => {
    setPreference({ kind: "loading" });
    setPreferenceCommand({ kind: "idle" });
    setList({ kind: "loading" });
    setDirty(false);
    setCursorHistory([]);
    setSelection(new Map());
    setPreferenceReload((current) => current + 1);
  };

  const buildExportRequest = (): ToolingExportRequest | null => {
    if (!loadedPage) return null;
    if (exportMode === "selection") {
      const refs = Array.from(selection.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([toolingMasterGlobalId, snapshotHash]) => ({
          snapshotHash,
          toolingMasterGlobalId,
        }));
      return refs.length >= 1 && refs.length <= 100
        ? { mode: "selection", selection: refs }
        : null;
    }
    return loadedPage.totalCount >= 1 && loadedPage.totalCount <= 100
      ? {
          filter: loadedPage.filter,
          mode: "filtered",
          querySnapshotHash: loadedPage.querySnapshotHash,
        }
      : null;
  };

  const runExport = useCallback(
    (request: ToolingExportRequest, key: string): void => {
      if (!sessionCommandContext) return;
      exportController.current?.abort();
      const controller = new AbortController();
      exportController.current = controller;
      setExportCommand({ kind: "processing" });
      setDownloadCommand({ kind: "idle" });
      void dataSource
        .createExport(projectId, request, {
          ...sessionCommandContext,
          idempotencyKey: key,
          signal: controller.signal,
        })
        .then((result) => {
          if (controller.signal.aborted) return;
          setClock(Date.now());
          setExportCommand({
            kind: "succeeded",
            package: result.package,
            replayed: result.replayed,
          });
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ToolingRequestCancelledError
          )
            return;
          setExportCommand({
            failure: toRequestFailure(error),
            kind: "failed",
            retry: { key, request },
          });
        });
    },
    [dataSource, projectId, sessionCommandContext],
  );

  const runDownload = useCallback(
    (packageValue: ToolingExportPackage, key: string): void => {
      if (!sessionCommandContext) return;
      downloadController.current?.abort();
      const controller = new AbortController();
      downloadController.current = controller;
      setDownloadCommand({ kind: "processing" });
      void dataSource
        .downloadExport(projectId, packageValue, {
          ...sessionCommandContext,
          idempotencyKey: key,
          signal: controller.signal,
        })
        .then((result) => {
          if (controller.signal.aborted) return;
          triggerDownload(result.blob, result.fileName);
          setDownloadCommand({ kind: "succeeded", replayed: result.replayed });
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ToolingRequestCancelledError
          )
            return;
          setDownloadCommand({
            failure: toRequestFailure(error),
            kind: "failed",
            retry: { key, package: packageValue },
          });
        });
    },
    [dataSource, projectId, sessionCommandContext],
  );

  const pageRows = useMemo(() => loadedPage?.items ?? [], [loadedPage?.items]);
  const pageSelectedCount = pageRows.filter((row) =>
    selection.has(row.toolingMasterGlobalId),
  ).length;
  const allPageSelected =
    pageRows.length > 0 && pageSelectedCount === pageRows.length;
  const somePageSelected = pageSelectedCount > 0 && !allPageSelected;
  const togglePage = useCallback(
    (checked: boolean): void => {
      setSelection((current) => {
        const next = new Map(current);
        for (const row of pageRows) {
          if (checked)
            next.set(row.toolingMasterGlobalId, row.toolingMasterSnapshotHash);
          else next.delete(row.toolingMasterGlobalId);
        }
        return next;
      });
    },
    [pageRows],
  );

  const columns = useMemo<
    readonly DenseGridColumn<GridRow, ToolingListColumnId>[]
  >(
    () => [
      {
        accessibilityLabel: t("Selection"),
        defaultWidth: 64,
        id: "selection",
        label: (
          <input
            aria-label={t("Select all objects on this page")}
            checked={allPageSelected}
            onChange={(event) => {
              togglePage(event.currentTarget.checked);
            }}
            ref={(element) => {
              if (element) element.indeterminate = somePageSelected;
            }}
            type="checkbox"
          />
        ),
        maximumWidth: 80,
        minimumWidth: 56,
        renderCell: (row) =>
          row.kind === "item" ? (
            <input
              aria-label={t("Select {{title}}", { title: row.value.title })}
              checked={selection.has(row.value.toolingMasterGlobalId)}
              data-language-exempt-tokens={JSON.stringify([row.value.title])}
              onChange={(event) => {
                const checked = event.currentTarget.checked;
                setSelection((current) => {
                  const next = new Map(current);
                  if (checked)
                    next.set(
                      row.value.toolingMasterGlobalId,
                      row.value.toolingMasterSnapshotHash,
                    );
                  else next.delete(row.value.toolingMasterGlobalId);
                  return next;
                });
              }}
              onClick={(event) => {
                event.stopPropagation();
              }}
              type="checkbox"
            />
          ) : null,
      },
      {
        accessibilityLabel: t("Tooling Master"),
        defaultWidth: 260,
        id: "tooling",
        label: t("Tooling Master"),
        maximumWidth: 480,
        minimumWidth: 180,
        renderCell: (row) =>
          row.kind === "item" ? (
            <span className="tooling-list__identity">
              <strong data-language-exempt="business-data">
                {row.value.title}
              </strong>
              <small data-language-exempt="identifier">
                {row.value.toolingMasterGlobalId}
              </small>
            </span>
          ) : null,
      },
      ...(
        [
          ["applicability", "applicabilityCount"],
          ["part_revisions", "distinctPartRevisionCount"],
          ["physical_sets", "physicalSetCount"],
          ["design_revisions", "designRevisionCount"],
        ] as const
      ).map(([id, field]) => ({
        accessibilityLabel: columnLabel(t, id),
        defaultWidth: defaultWidths[id],
        id,
        label: columnLabel(t, id),
        maximumWidth: 180,
        minimumWidth: 88,
        renderCell: (row: GridRow) =>
          row.kind === "item"
            ? formatNumber(locale, row.value[field], 0)
            : null,
      })),
      {
        accessibilityLabel: t("Origin"),
        defaultWidth: 184,
        id: "origin",
        label: t("Origin"),
        maximumWidth: 320,
        minimumWidth: 120,
        renderCell: (row) =>
          row.kind === "item" ? (
            <span className="tooling-list__origin">
              <span data-language-exempt="business-data">
                {row.value.projectCode}
              </span>
              {row.value.originatingProjectGlobalId !==
              row.value.projectGlobalId ? (
                <SemanticStatus label={t("Shared Master")} tone="info" />
              ) : (
                <span>{t("This Project")}</span>
              )}
            </span>
          ) : null,
      },
      {
        accessibilityLabel: t("Source"),
        defaultWidth: 150,
        id: "source",
        label: t("Source"),
        maximumWidth: 240,
        minimumWidth: 112,
        renderCell: (row) =>
          row.kind === "item"
            ? row.value.source === "manual"
              ? t("Manual record")
              : t("Controlled XLSX import")
            : null,
      },
      {
        accessibilityLabel: t("Action"),
        defaultWidth: 88,
        id: "action",
        label: t("Action"),
        maximumWidth: 120,
        minimumWidth: 72,
        renderCell: (row) =>
          row.kind === "item" ? (
            <Button
              aria-label={t("Open {{title}}", { title: row.value.title })}
              data-language-exempt-tokens={JSON.stringify([row.value.title])}
              icon="chevron"
              onClick={(event) => {
                event.stopPropagation();
                navigate(
                  `/projects/${projectId}/tooling/${row.value.toolingMasterGlobalId}`,
                );
              }}
            >
              {t("Open")}
            </Button>
          ) : null,
      },
    ],
    [
      allPageSelected,
      locale,
      navigate,
      projectId,
      selection,
      somePageSelected,
      t,
      togglePage,
    ],
  );

  const gridRows = useMemo(
    () => groupedRows(t, pageRows, loadedPage?.filter.groupKey ?? "none"),
    [loadedPage?.filter.groupKey, pageRows, t],
  );
  const exportCount =
    exportMode === "selection" ? selection.size : (loadedPage?.totalCount ?? 0);
  const exportReady = exportCount >= 1 && exportCount <= 100;
  const canExport = Boolean(
    loadedPage?.permissions.canExport && sessionCommandContext && exportReady,
  );
  const packageExpired = Boolean(
    activePackage && clock >= Date.parse(activePackage.expiresAt),
  );

  return (
    <Panel
      actions={
        <Button
          disabled={!canExport || exportCommand.kind === "processing"}
          icon="document"
          onClick={(event) => {
            const request = buildExportRequest();
            if (!request) return;
            exportTrigger.current = event.currentTarget;
            setReviewRequest({ count: exportCount, request });
          }}
        >
          {t("Export object package")}
        </Button>
      }
      bodyClassName="tooling-list__body"
      className="tooling-list"
      id="tooling-list-workspace"
      title={t("Tooling List")}
    >
      <div className="tooling-list__toolbar">
        <label>
          <span>{t("Common view")}</span>
          <Select
            onChange={(event) => {
              setPreference({ kind: "loading" });
              setPreferenceCommand({ kind: "idle" });
              setList({ kind: "loading" });
              setDirty(false);
              setCursorHistory([]);
              setSelection(new Map());
              setViewId(event.currentTarget.value as ToolingListViewId);
            }}
            value={viewId}
          >
            {toolingListViewIds.map((item) => (
              <option key={item} value={item}>
                {viewLabel(t, item)}
              </option>
            ))}
          </Select>
        </label>
        <label>
          <span>{t("Search Tooling")}</span>
          <TextInput
            maxLength={120}
            onChange={(event) => {
              setDraftFilter({
                ...draftFilter,
                search: event.currentTarget.value,
              });
              setDirty(true);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                applyFilter();
              }
            }}
            value={draftFilter.search}
          />
        </label>
        <label>
          <span>{t("Sort by")}</span>
          <Select
            onChange={(event) => {
              setDraftFilter({
                ...draftFilter,
                sortKey: event.currentTarget.value as ToolingListSortKey,
              });
              setDirty(true);
            }}
            value={draftFilter.sortKey}
          >
            {toolingListSortKeys.map((item) => (
              <option key={item} value={item}>
                {sortLabel(t, item)}
              </option>
            ))}
          </Select>
        </label>
        <label>
          <span>{t("Direction")}</span>
          <Select
            onChange={(event) => {
              setDraftFilter({
                ...draftFilter,
                sortDirection: event.currentTarget
                  .value as ToolingListSortDirection,
              });
              setDirty(true);
            }}
            value={draftFilter.sortDirection}
          >
            {toolingListSortDirections.map((item) => (
              <option key={item} value={item}>
                {directionLabel(t, item)}
              </option>
            ))}
          </Select>
        </label>
        <label>
          <span>{t("Group by")}</span>
          <Select
            onChange={(event) => {
              setDraftFilter({
                ...draftFilter,
                groupKey: event.currentTarget.value as ToolingListGroupKey,
              });
              setDirty(true);
            }}
            value={draftFilter.groupKey}
          >
            {toolingListGroupKeys.map((item) => (
              <option key={item} value={item}>
                {groupLabel(t, item)}
              </option>
            ))}
          </Select>
        </label>
        <div className="tooling-list__toolbar-actions">
          <Button onClick={applyFilter}>{t("Apply view")}</Button>
          <Button
            disabled={
              !dirty ||
              !loadedPreference ||
              !sessionCommandContext ||
              preferenceCommand.kind === "saving"
            }
            onClick={savePreference}
          >
            {preferenceCommand.kind === "saving"
              ? t("Saving view")
              : t("Save view")}
          </Button>
        </div>
      </div>
      <div className="tooling-list__secondary-toolbar">
        <details>
          <summary>{t("Columns")}</summary>
          <div className="tooling-list__column-controls">
            {optionalColumns.map((column) => (
              <label key={column}>
                <input
                  checked={!layout.hiddenColumnIds.includes(column)}
                  onChange={(event) => {
                    const visible = event.currentTarget.checked;
                    setLayout((current) => ({
                      ...current,
                      hiddenColumnIds: visible
                        ? current.hiddenColumnIds.filter(
                            (item) => item !== column,
                          )
                        : [...current.hiddenColumnIds, column],
                    }));
                    setDirty(true);
                  }}
                  type="checkbox"
                />
                <span>{columnLabel(t, column)}</span>
              </label>
            ))}
            <small>
              {t(
                "Selection and Tooling identity stay fixed. Selection, Tooling and Action columns cannot be hidden.",
              )}
            </small>
          </div>
        </details>
        <label>
          <span>{t("Export mode")}</span>
          <Select
            onChange={(event) => {
              setExportMode(
                event.currentTarget.value as "selection" | "filtered",
              );
            }}
            value={exportMode}
          >
            <option value="selection">{t("Exact selected objects")}</option>
            <option value="filtered">{t("Complete filtered result")}</option>
          </Select>
        </label>
        <span aria-live="polite" className="tooling-list__selection-status">
          {t("Selected objects: {{count}}", {
            count: formatNumber(locale, selection.size, 0),
          })}
        </span>
        {dirty ? (
          <SemanticStatus label={t("View changes not saved")} tone="warning" />
        ) : (
          <SemanticStatus
            label={
              loadedPreference?.stored
                ? t("Saved personal view")
                : t("Default view")
            }
            tone="neutral"
          />
        )}
      </div>
      {!sessionCommandContext ? (
        <div
          className="scenario-banner scenario-banner--read_only tooling-list__banner"
          role="status"
        >
          <span>
            {t("Tooling List commands are read only in this session.")}
          </span>
          <span>
            {t(
              "Session verification is required to save a view or export a package.",
            )}
          </span>
        </div>
      ) : null}
      {loadedPage && !loadedPage.permissions.canExport ? (
        <div
          className="scenario-banner scenario-banner--read_only tooling-list__banner"
          role="status"
        >
          <span>{t("Tooling List export is unavailable.")}</span>
          <span>{t("Separate export authority is required.")}</span>
        </div>
      ) : null}
      {exportMode === "filtered" && loadedPage && !exportReady ? (
        <div
          className="scenario-banner scenario-banner--read_only tooling-list__banner"
          role="status"
        >
          <span>{t("The current filtered result cannot be exported.")}</span>
          <span>
            {t(
              "Narrow the view to between one and one hundred Tooling Masters.",
            )}
          </span>
        </div>
      ) : null}
      {preference.kind === "loading" ? (
        <div aria-busy="true" className="tooling-list__loading" role="status">
          {t("Loading saved Tooling List view")}
        </div>
      ) : null}
      {preference.kind === "failed" ? (
        <div className="tooling-list__failure">
          <RequestFailurePanel failure={preference.failure} />
          <Button onClick={reloadPreference}>{t("Retry saved view")}</Button>
        </div>
      ) : null}
      {preferenceCommand.kind === "failed" ? (
        <div className="tooling-list__failure" role="alert">
          {preferenceCommand.failure.problem?.status === 409 ? (
            <p>
              {t(
                "The saved view changed in another session. Reload it before saving again.",
              )}
            </p>
          ) : null}
          <RequestFailurePanel failure={preferenceCommand.failure} />
          <Button onClick={reloadPreference}>{t("Reload saved view")}</Button>
        </div>
      ) : null}
      {preferenceCommand.kind === "saved" ? (
        <div className="scenario-banner scenario-banner--success" role="status">
          <span>{t("Personal Tooling List view saved.")}</span>
        </div>
      ) : null}
      {list.kind === "failed" ? (
        <div className="tooling-list__failure">
          <RequestFailurePanel failure={list.failure} />
          {canRetry(list.failure) && listRequest ? (
            <Button
              onClick={() => {
                setList({ kind: "loading" });
                setListRequest({ ...listRequest, sequence: Date.now() });
              }}
            >
              {t("Retry Tooling List")}
            </Button>
          ) : null}
        </div>
      ) : null}
      <DenseGrid
        ariaBusy={list.kind === "loading"}
        ariaLabel={t("Project Tooling List")}
        className="tooling-list__grid"
        columns={columns}
        emptyContent={
          <div className="empty-state" role="status">
            <strong>{t("No Tooling Masters match this view.")}</strong>
            <span>
              {t("Change the common view or narrow search controls.")}
            </span>
          </div>
        }
        getRowKey={(row) => row.key}
        getRowProperties={(row) =>
          row.kind === "group"
            ? { className: "tooling-list__group-row" }
            : {
                "aria-selected":
                  row.value.toolingMasterGlobalId === selectedMasterId,
                className:
                  row.value.toolingMasterGlobalId === selectedMasterId
                    ? "is-selected"
                    : undefined,
                onClick: () => {
                  navigate(
                    `/projects/${projectId}/tooling/${row.value.toolingMasterGlobalId}`,
                  );
                },
                onKeyDown: (event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    navigate(
                      `/projects/${projectId}/tooling/${row.value.toolingMasterGlobalId}`,
                    );
                  }
                },
                tabIndex: 0,
              }
        }
        layout={layout}
        onLayoutChange={(change) => {
          setLayout(change.layout);
          setDirty(true);
        }}
        renderSpanningRow={(row) =>
          row.kind === "group" ? (
            <strong className="tooling-list__group-label">{row.label}</strong>
          ) : null
        }
        resizeColumnLabel={(label) => t("Resize {{column}}", { column: label })}
        resizeHelp={t(
          "Use Left and Right Arrow to resize. Press Enter to fit the column.",
        )}
        rows={gridRows}
        tableRole="grid"
      />
      <div className="tooling-list__status-bar">
        <span aria-live="polite">
          {loadedPage
            ? t("Showing {{shown}} of {{total}} Tooling Masters", {
                shown: formatNumber(locale, loadedPage.items.length, 0),
                total: formatNumber(locale, loadedPage.totalCount, 0),
              })
            : t("Loading Tooling List page")}
        </span>
        <div className="detail-actions tooling-list__pager">
          <Button
            disabled={cursorHistory.length === 0 || list.kind === "loading"}
            onClick={() => {
              const previous = cursorHistory.at(-1);
              if (previous === undefined || !loadedPage) return;
              setCursorHistory((current) => current.slice(0, -1));
              setList({ kind: "loading" });
              setListRequest({
                cursor: previous,
                filter: loadedPage.filter,
                sequence: Date.now(),
              });
            }}
          >
            {t("Previous page")}
          </Button>
          <Button
            disabled={!loadedPage?.nextCursor || list.kind === "loading"}
            onClick={() => {
              if (!loadedPage?.nextCursor || !listRequest) return;
              setCursorHistory((current) => [...current, listRequest.cursor]);
              setList({ kind: "loading" });
              setListRequest({
                cursor: loadedPage.nextCursor,
                filter: loadedPage.filter,
                sequence: Date.now(),
              });
            }}
          >
            {t("Next page")}
          </Button>
        </div>
      </div>
      {exportCommand.kind === "processing" ? (
        <div
          aria-busy="true"
          className="scenario-banner scenario-banner--processing tooling-list__banner"
          role="status"
        >
          <span>{t("Creating immutable Tooling object package")}</span>
          <span>
            {t(
              "Keep this workspace open while exact snapshots are revalidated.",
            )}
          </span>
        </div>
      ) : null}
      {exportCommand.kind === "failed" ? (
        <div className="tooling-list__failure" role="alert">
          {exportCommand.failure.problem?.status === 409 ? (
            <p>
              {t(
                "The reviewed Tooling List changed. Reload the list and review the export again.",
              )}
            </p>
          ) : null}
          {exportCommand.failure.problem?.status === 422 ? (
            <p>
              {t(
                "The export request is outside the supported one-to-one-hundred object boundary.",
              )}
            </p>
          ) : null}
          <RequestFailurePanel failure={exportCommand.failure} />
          {canRetry(exportCommand.failure) ? (
            <Button
              onClick={() => {
                runExport(exportCommand.retry.request, exportCommand.retry.key);
              }}
            >
              {t("Retry exact export")}
            </Button>
          ) : null}
          <Button onClick={applyFilter}>{t("Reload current view")}</Button>
        </div>
      ) : null}
      {exportCommand.kind === "succeeded" ? (
        <section
          className="tooling-list__package"
          aria-label={t("Export package result")}
        >
          <header>
            <SemanticStatus
              label={
                packageExpired
                  ? t("Expired")
                  : exportCommand.replayed
                    ? t("Replayed exact package")
                    : t("Package created")
              }
              tone={packageExpired ? "warning" : "success"}
            />
            <strong data-language-exempt="business-data">
              {exportCommand.package.fileName}
            </strong>
          </header>
          <DefinitionList
            rows={[
              {
                label: t("Export mode"),
                value:
                  exportCommand.package.mode === "selection"
                    ? t("Exact selected objects")
                    : t("Complete filtered result"),
              },
              {
                label: t("Object count"),
                value: formatNumber(
                  locale,
                  exportCommand.package.objectCount,
                  0,
                ),
              },
              {
                label: t("Generated at"),
                value: formatDateTime(
                  locale,
                  exportCommand.package.generatedAt,
                ),
              },
              {
                label: t("Download valid until"),
                value: formatDateTime(locale, exportCommand.package.expiresAt),
              },
              {
                exempt: "identifier",
                label: t("Package SHA-256"),
                value: exportCommand.package.sha256,
              },
            ]}
          />
          <p>
            {t(
              "The package contains fixed manifest, localized CSV and readme members. Private files, raw workbook values, external identifiers, cost, repair, custody, evidence and ERP or lifecycle truth are omitted.",
            )}
          </p>
          {packageExpired ? (
            <p role="status">
              {t(
                "This package has expired. Create a new package to download current exact bytes.",
              )}
            </p>
          ) : null}
          <div className="detail-actions">
            <Button
              disabled={
                packageExpired ||
                !sessionCommandContext ||
                downloadCommand.kind === "processing"
              }
              icon="document"
              onClick={() => {
                const key = `tooling-export-download-${globalThis.crypto.randomUUID()}`;
                runDownload(exportCommand.package, key);
              }}
            >
              {downloadCommand.kind === "processing"
                ? t("Preparing secure download")
                : t("Download object package")}
            </Button>
            <Button
              onClick={() => {
                setExportCommand({ kind: "idle" });
                setDownloadCommand({ kind: "idle" });
              }}
            >
              {t("Dismiss package result")}
            </Button>
          </div>
        </section>
      ) : null}
      {downloadCommand.kind === "failed" ? (
        <div className="tooling-list__failure" role="alert">
          {downloadCommand.failure.problem?.code ===
          "TOOLING_EXPORT_EXPIRED" ? (
            <p>
              {t(
                "This package has expired. Create a new package to download current exact bytes.",
              )}
            </p>
          ) : (
            <p>
              {t(
                "The secure package download failed. No raw private URL was exposed.",
              )}
            </p>
          )}
          <RequestFailurePanel failure={downloadCommand.failure} />
          {canRetry(downloadCommand.failure) ? (
            <Button
              onClick={() => {
                runDownload(
                  downloadCommand.retry.package,
                  downloadCommand.retry.key,
                );
              }}
            >
              {t("Retry exact download")}
            </Button>
          ) : null}
        </div>
      ) : null}
      {downloadCommand.kind === "succeeded" ? (
        <div
          className="scenario-banner scenario-banner--success tooling-list__banner"
          role="status"
        >
          <span>
            {downloadCommand.replayed
              ? t("The exact package download was replayed safely.")
              : t("The exact package download started.")}
          </span>
          <span>
            {t("The immutable package remains private and audit retained.")}
          </span>
        </div>
      ) : null}
      {reviewRequest ? (
        <ImpactReview
          confirmLabel={t("Create object package")}
          contextRows={[
            {
              label: t("Export mode"),
              value:
                reviewRequest.request.mode === "selection"
                  ? t("Exact selected objects")
                  : t("Complete filtered result"),
            },
            {
              label: t("Object count"),
              value: formatNumber(locale, reviewRequest.count, 0),
            },
            { label: t("Download validity"), value: t("One hour") },
            {
              label: t("Redactions"),
              value: t(
                "Confidential and external execution fields are omitted.",
              ),
            },
          ]}
          details={{
            audit: t(
              "Creation and every download retain actor-bound hash and count evidence.",
            ),
            failureHandling: t(
              "Stale, inaccessible or oversized results fail without creating a package.",
            ),
            impact: t(
              "Create one immutable private three-member object package from the reviewed exact versions.",
            ),
            irreversible: t(
              "Package history is immutable; download expires after one hour.",
            ),
            objectIdentity: projectId,
            permission: t(
              "Separate export authority and current Project visibility are required.",
            ),
            version:
              reviewRequest.request.mode === "selection"
                ? t("Exact object snapshots")
                : t("Exact filtered query snapshot"),
          }}
          onCancel={() => {
            setReviewRequest(null);
          }}
          onConfirm={() => {
            const request = reviewRequest.request;
            setReviewRequest(null);
            runExport(
              request,
              `tooling-export-create-${globalThis.crypto.randomUUID()}`,
            );
          }}
          reasonRequired={false}
          returnFocusTarget={() => exportTrigger.current}
          title={t("Review Tooling object package export")}
        />
      ) : null}
    </Panel>
  );
}
