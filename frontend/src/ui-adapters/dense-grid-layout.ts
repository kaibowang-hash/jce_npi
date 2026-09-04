import type { DenseGridColumn, DenseGridLayout } from "./dense-grid";

export function createDefaultDenseGridLayout<Row, ColumnId extends string>(
  columns: readonly DenseGridColumn<Row, ColumnId>[],
  fixedColumnCount = 0,
): DenseGridLayout<ColumnId> {
  const widths = Object.fromEntries(
    columns.map((column) => [column.id, column.defaultWidth]),
  ) as Record<ColumnId, number>;
  return {
    columnOrder: columns.map((column) => column.id),
    fixedColumnCount: Math.min(
      Math.max(0, Math.trunc(fixedColumnCount)),
      columns.length,
    ),
    hiddenColumnIds: [],
    widths,
  };
}

export function resetDenseGridColumn<Row, ColumnId extends string>(
  columns: readonly DenseGridColumn<Row, ColumnId>[],
  layout: DenseGridLayout<ColumnId>,
  columnId: ColumnId,
): DenseGridLayout<ColumnId> {
  const column = columns.find((candidate) => candidate.id === columnId);
  if (!column) return layout;
  return {
    ...layout,
    widths: { ...layout.widths, [columnId]: column.defaultWidth },
  };
}

export function resetDenseGridLayout<Row, ColumnId extends string>(
  columns: readonly DenseGridColumn<Row, ColumnId>[],
  fixedColumnCount = 0,
): DenseGridLayout<ColumnId> {
  return createDefaultDenseGridLayout(columns, fixedColumnCount);
}
