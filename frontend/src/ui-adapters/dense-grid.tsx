import {
  Fragment,
  useId,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type HTMLAttributes,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  type UIEventHandler,
} from "react";

export interface DenseGridColumn<Row, ColumnId extends string> {
  readonly accessibilityLabel: string;
  readonly defaultWidth: number;
  readonly id: ColumnId;
  readonly label: ReactNode;
  readonly maximumWidth: number;
  readonly minimumWidth: number;
  readonly renderCell: (row: Row) => ReactNode;
}

export interface DenseGridLayout<ColumnId extends string> {
  readonly columnOrder: readonly ColumnId[];
  readonly fixedColumnCount: number;
  readonly hiddenColumnIds: readonly ColumnId[];
  readonly widths: Readonly<Record<ColumnId, number>>;
}

export type DenseGridLayoutChangeReason =
  | "auto_fit"
  | "keyboard_resize"
  | "pointer_resize";

export interface DenseGridLayoutChange<ColumnId extends string> {
  readonly columnId: ColumnId;
  readonly layout: DenseGridLayout<ColumnId>;
  readonly reason: DenseGridLayoutChangeReason;
}

type DenseGridRowProperties = Omit<
  HTMLAttributes<HTMLTableRowElement>,
  "children" | "key"
>;

export interface DenseGridProps<Row, ColumnId extends string> {
  readonly ariaBusy?: boolean;
  readonly ariaLabel: string;
  readonly caption?: ReactNode;
  readonly className?: string;
  readonly columns: readonly DenseGridColumn<Row, ColumnId>[];
  readonly emptyContent?: ReactNode;
  readonly getRowKey: (row: Row) => string;
  readonly getRowProperties?: (
    row: Row,
    rowIndex: number,
  ) => DenseGridRowProperties;
  readonly interactionDisabled?: boolean;
  readonly layout: DenseGridLayout<ColumnId>;
  readonly measureColumn?: (
    columnId: ColumnId,
    table: HTMLTableElement,
  ) => number;
  readonly onLayoutChange: (change: DenseGridLayoutChange<ColumnId>) => void;
  readonly renderSpanningRow?: (
    row: Row,
    visibleColumnCount: number,
  ) => ReactNode | null;
  readonly resizeColumnLabel: (columnLabel: string) => string;
  readonly resizeHelp: string;
  readonly rows: readonly Row[];
  readonly tableRole?: "grid" | "table" | "treegrid";
  readonly viewportRef?: { current: HTMLDivElement | null };
  readonly onViewportScroll?: UIEventHandler<HTMLDivElement>;
}

interface DragState<ColumnId extends string> {
  readonly baseLayout: DenseGridLayout<ColumnId>;
  readonly columnId: ColumnId;
  readonly pointerId: number;
  readonly startWidth: number;
  readonly startX: number;
}

interface PreviewState<ColumnId extends string> {
  readonly baseLayout: DenseGridLayout<ColumnId>;
  readonly widths: Readonly<Record<ColumnId, number>>;
}

const keyboardWidthStep = 8;
const intrinsicMeasurementStyle = {
  display: "inline-block",
  width: "max-content",
} satisfies CSSProperties;

function clamp(value: number, minimum: number, maximum: number): number {
  if (!Number.isFinite(value)) return minimum;
  return Math.min(maximum, Math.max(minimum, Math.round(value)));
}

function pointerIdentity(value: number): number {
  return Number.isInteger(value) ? value : 0;
}

function invokePointerCapture(
  target: HTMLDivElement,
  method: "releasePointerCapture" | "setPointerCapture",
  pointerId: number,
): void {
  const candidate: unknown = Reflect.get(target, method);
  if (typeof candidate === "function") {
    Reflect.apply(candidate, target, [pointerId]);
  }
}

function columnMap<Row, ColumnId extends string>(
  columns: readonly DenseGridColumn<Row, ColumnId>[],
): ReadonlyMap<ColumnId, DenseGridColumn<Row, ColumnId>> {
  return new Map(columns.map((column) => [column.id, column]));
}

function defaultColumnMeasurement(
  columnId: string,
  table: HTMLTableElement,
): number {
  const escaped = columnId.replace(/[^A-Za-z0-9_-]/gu, "\\$&");
  const contents = table.querySelectorAll<HTMLElement>(
    `[data-grid-measure-column="${escaped}"]`,
  );
  let measured = 0;
  for (const content of contents) {
    measured = Math.max(measured, content.scrollWidth + 20);
  }
  return measured;
}

export function DenseGrid<Row, ColumnId extends string>({
  ariaBusy = false,
  ariaLabel,
  caption,
  className = "",
  columns,
  emptyContent,
  getRowKey,
  getRowProperties,
  interactionDisabled = false,
  layout,
  measureColumn = defaultColumnMeasurement,
  onLayoutChange,
  renderSpanningRow,
  resizeColumnLabel,
  resizeHelp,
  rows,
  tableRole = "table",
  viewportRef,
  onViewportScroll,
}: DenseGridProps<Row, ColumnId>): React.JSX.Element {
  const gridIdentity = useId().replace(/:/gu, "");
  const resizeHelpId = `${gridIdentity}-resize-help`;
  const tableRef = useRef<HTMLTableElement | null>(null);
  const dragState = useRef<DragState<ColumnId> | null>(null);
  const [preview, setPreview] = useState<PreviewState<ColumnId> | null>(null);
  const columnsById = useMemo(() => columnMap(columns), [columns]);
  const hiddenIds = useMemo(
    () => new Set(layout.hiddenColumnIds),
    [layout.hiddenColumnIds],
  );
  const orderedColumns = useMemo(
    () =>
      layout.columnOrder
        .map((columnId) => columnsById.get(columnId))
        .filter(
          (column): column is DenseGridColumn<Row, ColumnId> =>
            column !== undefined && !hiddenIds.has(column.id),
        ),
    [columnsById, hiddenIds, layout.columnOrder],
  );
  const widths =
    preview?.baseLayout === layout ? preview.widths : layout.widths;
  const fixedCount = Math.min(
    Math.max(0, layout.fixedColumnCount),
    orderedColumns.length,
  );
  const fixedOffsets = useMemo(() => {
    const offsets = new Map<ColumnId, number>();
    let offset = 0;
    for (const column of orderedColumns.slice(0, fixedCount)) {
      offsets.set(column.id, offset);
      offset += widths[column.id];
    }
    return offsets;
  }, [fixedCount, orderedColumns, widths]);
  const totalWidth = orderedColumns.reduce(
    (total, column) => total + widths[column.id],
    0,
  );

  const layoutWithWidth = (
    columnId: ColumnId,
    candidateWidth: number,
  ): DenseGridLayout<ColumnId> => {
    const column = columnsById.get(columnId);
    if (!column) return layout;
    const safeCandidate = Number.isFinite(candidateWidth)
      ? candidateWidth
      : layout.widths[columnId];
    return {
      ...layout,
      widths: {
        ...layout.widths,
        [columnId]: clamp(
          safeCandidate,
          column.minimumWidth,
          column.maximumWidth,
        ),
      },
    };
  };

  const commitWidth = (
    columnId: ColumnId,
    candidateWidth: number,
    reason: DenseGridLayoutChangeReason,
    currentWidth = layout.widths[columnId],
  ): void => {
    const nextLayout = layoutWithWidth(columnId, candidateWidth);
    if (nextLayout.widths[columnId] === currentWidth) return;
    onLayoutChange({ columnId, layout: nextLayout, reason });
  };

  const autoFit = (columnId: ColumnId): void => {
    const table = tableRef.current;
    const column = columnsById.get(columnId);
    if (!table || !column) return;
    const measured = measureColumn(columnId, table);
    if (!Number.isFinite(measured)) return;
    commitWidth(columnId, measured, "auto_fit");
  };

  const handleSeparatorKey = (
    event: KeyboardEvent<HTMLDivElement>,
    column: DenseGridColumn<Row, ColumnId>,
  ): void => {
    if (interactionDisabled) return;
    let nextWidth: number | null = null;
    if (event.key === "ArrowLeft") {
      nextWidth = widths[column.id] - keyboardWidthStep;
    } else if (event.key === "ArrowRight") {
      nextWidth = widths[column.id] + keyboardWidthStep;
    } else if (event.key === "Home") {
      nextWidth = column.minimumWidth;
    } else if (event.key === "End") {
      nextWidth = column.maximumWidth;
    } else if (event.key === "Enter") {
      event.preventDefault();
      autoFit(column.id);
      return;
    }
    if (nextWidth === null) return;
    event.preventDefault();
    commitWidth(column.id, nextWidth, "keyboard_resize");
  };

  const fixedStyle = (columnId: ColumnId): CSSProperties | undefined => {
    const offset = fixedOffsets.get(columnId);
    return offset === undefined ? undefined : { left: `${String(offset)}px` };
  };

  const tableStyle = {
    minWidth: `${String(totalWidth)}px`,
    width: `${String(totalWidth)}px`,
  } satisfies CSSProperties;

  return (
    <div
      aria-busy={ariaBusy}
      className={`dense-grid__viewport ${className}`.trim()}
      onScroll={onViewportScroll}
      ref={(node) => {
        if (viewportRef) viewportRef.current = node;
      }}
      tabIndex={0}
    >
      <span className="visually-hidden" id={resizeHelpId}>
        {resizeHelp}
      </span>
      <table
        aria-label={ariaLabel}
        className="data-table dense-grid"
        ref={tableRef}
        role={tableRole}
        style={tableStyle}
      >
        {caption === undefined ? null : <caption>{caption}</caption>}
        <colgroup>
          {orderedColumns.map((column) => (
            <col
              data-grid-column={column.id}
              key={column.id}
              style={{ width: `${String(widths[column.id])}px` }}
            />
          ))}
        </colgroup>
        <thead>
          <tr>
            {orderedColumns.map((column) => {
              const isFixed = fixedOffsets.has(column.id);
              const labelId = `${gridIdentity}-${column.id}-label`;
              return (
                <th
                  aria-labelledby={labelId}
                  data-fixed-column={isFixed ? "start" : undefined}
                  data-grid-column={column.id}
                  key={column.id}
                  scope="col"
                  style={fixedStyle(column.id)}
                >
                  <span className="dense-grid__header-label" id={labelId}>
                    <span
                      data-grid-measure-column={column.id}
                      style={intrinsicMeasurementStyle}
                    >
                      {column.label}
                    </span>
                  </span>
                  <div
                    aria-describedby={resizeHelpId}
                    aria-disabled={interactionDisabled || undefined}
                    aria-label={resizeColumnLabel(column.accessibilityLabel)}
                    aria-orientation="vertical"
                    aria-valuemax={column.maximumWidth}
                    aria-valuemin={column.minimumWidth}
                    aria-valuenow={widths[column.id]}
                    className="dense-grid__resize-handle"
                    onDoubleClick={(event) => {
                      if (interactionDisabled) return;
                      event.preventDefault();
                      autoFit(column.id);
                    }}
                    onKeyDown={(event) => {
                      handleSeparatorKey(event, column);
                    }}
                    onLostPointerCapture={(event) => {
                      const active = dragState.current;
                      if (
                        active?.pointerId !==
                          pointerIdentity(event.pointerId) ||
                        active.columnId !== column.id
                      ) {
                        return;
                      }
                      dragState.current = null;
                      setPreview(null);
                    }}
                    onPointerCancel={(event) => {
                      const active = dragState.current;
                      if (
                        active?.pointerId !==
                          pointerIdentity(event.pointerId) ||
                        active.columnId !== column.id
                      ) {
                        return;
                      }
                      dragState.current = null;
                      setPreview(null);
                    }}
                    onPointerDown={(event: PointerEvent<HTMLDivElement>) => {
                      if (interactionDisabled) return;
                      if (dragState.current !== null) return;
                      if (Number.isFinite(event.button) && event.button !== 0) {
                        return;
                      }
                      event.preventDefault();
                      setPreview(null);
                      const pointerId = pointerIdentity(event.pointerId);
                      invokePointerCapture(
                        event.currentTarget,
                        "setPointerCapture",
                        pointerId,
                      );
                      dragState.current = {
                        baseLayout: layout,
                        columnId: column.id,
                        pointerId,
                        startWidth: layout.widths[column.id],
                        startX: event.clientX,
                      };
                    }}
                    onPointerMove={(event: PointerEvent<HTMLDivElement>) => {
                      const active = dragState.current;
                      if (
                        active?.pointerId !==
                          pointerIdentity(event.pointerId) ||
                        active.baseLayout !== layout ||
                        active.columnId !== column.id
                      ) {
                        return;
                      }
                      const nextLayout = layoutWithWidth(
                        column.id,
                        active.startWidth + event.clientX - active.startX,
                      );
                      setPreview({
                        baseLayout: layout,
                        widths: nextLayout.widths,
                      });
                    }}
                    onPointerUp={(event: PointerEvent<HTMLDivElement>) => {
                      const active = dragState.current;
                      if (
                        active?.pointerId !==
                          pointerIdentity(event.pointerId) ||
                        active.columnId !== column.id
                      ) {
                        return;
                      }
                      invokePointerCapture(
                        event.currentTarget,
                        "releasePointerCapture",
                        active.pointerId,
                      );
                      dragState.current = null;
                      setPreview(null);
                      if (active.baseLayout !== layout) return;
                      commitWidth(
                        column.id,
                        active.startWidth + event.clientX - active.startX,
                        "pointer_resize",
                        active.startWidth,
                      );
                    }}
                    role="separator"
                    tabIndex={interactionDisabled ? -1 : 0}
                    title={resizeHelp}
                  />
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={Math.max(1, orderedColumns.length)}>
                {emptyContent}
              </td>
            </tr>
          ) : (
            rows.map((row, rowIndex) => {
              const spanningContent = renderSpanningRow?.(
                row,
                orderedColumns.length,
              );
              const properties = getRowProperties?.(row, rowIndex) ?? {};
              return (
                <Fragment key={getRowKey(row)}>
                  <tr {...properties}>
                    {spanningContent === null ||
                    spanningContent === undefined ? (
                      orderedColumns.map((column) => {
                        const isFixed = fixedOffsets.has(column.id);
                        return (
                          <td
                            data-fixed-column={isFixed ? "start" : undefined}
                            data-grid-column={column.id}
                            key={column.id}
                            style={fixedStyle(column.id)}
                          >
                            <div
                              data-grid-measure-column={column.id}
                              style={intrinsicMeasurementStyle}
                            >
                              {column.renderCell(row)}
                            </div>
                          </td>
                        );
                      })
                    ) : (
                      <td colSpan={Math.max(1, orderedColumns.length)}>
                        {spanningContent}
                      </td>
                    )}
                  </tr>
                </Fragment>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
