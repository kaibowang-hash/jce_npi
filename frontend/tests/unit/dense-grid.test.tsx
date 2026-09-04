import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  DenseGrid,
  type DenseGridColumn,
  type DenseGridLayout,
  type DenseGridLayoutChange,
} from "../../src/ui-adapters/dense-grid";
import {
  createDefaultDenseGridLayout,
  resetDenseGridColumn,
  resetDenseGridLayout,
} from "../../src/ui-adapters/dense-grid-layout";

type ColumnId = "code" | "name" | "status";

interface Row {
  code: string;
  name: string;
  status: string;
}

type LayoutChangeHandler = (change: DenseGridLayoutChange<ColumnId>) => void;

const rows: readonly Row[] = [
  { code: "P-001", name: "Battery housing", status: "Ready" },
  { code: "P-002", name: "Connector", status: "Blocked" },
];

const columns: readonly DenseGridColumn<Row, ColumnId>[] = [
  {
    accessibilityLabel: "Code",
    defaultWidth: 100,
    id: "code",
    label: "Code",
    maximumWidth: 180,
    minimumWidth: 80,
    renderCell: (row) => row.code,
  },
  {
    accessibilityLabel: "Name",
    defaultWidth: 180,
    id: "name",
    label: "Name",
    maximumWidth: 260,
    minimumWidth: 120,
    renderCell: (row) => row.name,
  },
  {
    accessibilityLabel: "Status",
    defaultWidth: 120,
    id: "status",
    label: "Status",
    maximumWidth: 200,
    minimumWidth: 96,
    renderCell: (row) => row.status,
  },
];

function ControlledGrid({
  initialLayout,
  measureColumn,
  onLayoutChange,
}: {
  initialLayout: DenseGridLayout<ColumnId>;
  measureColumn?: (columnId: ColumnId, table: HTMLTableElement) => number;
  onLayoutChange: LayoutChangeHandler;
}): React.JSX.Element {
  const [layout, setLayout] = useState(initialLayout);
  return (
    <DenseGrid
      ariaLabel="Engineering grid"
      columns={columns}
      getRowKey={(row) => row.code}
      layout={layout}
      {...(measureColumn ? { measureColumn } : {})}
      onLayoutChange={(change) => {
        setLayout(change.layout);
        onLayoutChange(change);
      }}
      resizeColumnLabel={(label) => `Resize ${label} column`}
      resizeHelp="Use arrow keys or press Enter to fit rendered rows."
      rows={rows}
    />
  );
}

function renderGrid(
  layout: DenseGridLayout<ColumnId> = createDefaultDenseGridLayout(columns, 2),
  onLayoutChange: LayoutChangeHandler = () => undefined,
  measureColumn?: (columnId: ColumnId, table: HTMLTableElement) => number,
) {
  return {
    onLayoutChange,
    ...render(
      <ControlledGrid
        initialLayout={layout}
        {...(measureColumn ? { measureColumn } : {})}
        onLayoutChange={onLayoutChange}
      />,
    ),
  };
}

function dispatchPointer(
  element: Element,
  type:
    | "lostpointercapture"
    | "pointercancel"
    | "pointerdown"
    | "pointermove"
    | "pointerup",
  properties: {
    button?: number;
    clientX: number;
    pointerId: number;
  },
): void {
  const event = new Event(type, { bubbles: true, cancelable: true });
  for (const [name, value] of Object.entries(properties)) {
    Object.defineProperty(event, name, { value });
  }
  fireEvent(element, event);
}

describe("DenseGrid", () => {
  it("applies exact col widths, hidden columns, and cumulative fixed-start offsets", () => {
    const layout: DenseGridLayout<ColumnId> = {
      columnOrder: ["name", "code", "status"],
      fixedColumnCount: 2,
      hiddenColumnIds: ["status"],
      widths: { code: 96, name: 200, status: 120 },
    };
    const { container } = renderGrid(layout);

    const table = screen.getByRole("table", { name: "Engineering grid" });
    expect(table).toBeVisible();
    expect(table).toHaveStyle({ minWidth: "296px", width: "296px" });
    expect(screen.getAllByRole("columnheader")).toHaveLength(2);
    expect(
      screen.queryByRole("columnheader", { name: /Status/u }),
    ).not.toBeInTheDocument();
    const fixedHeaders = container.querySelectorAll(
      "th[data-fixed-column='start']",
    );
    expect(fixedHeaders).toHaveLength(2);
    expect(fixedHeaders[0]).toHaveStyle({ left: "0px" });
    expect(fixedHeaders[1]).toHaveStyle({ left: "200px" });
    const columnWidths = [
      ...container.querySelectorAll<HTMLTableColElement>("colgroup col"),
    ].map((column) => column.style.width);
    expect(columnWidths).toEqual(["200px", "96px"]);
  });

  it("previews pointer resize and commits one bounded change on pointer release", () => {
    const onLayoutChange = vi.fn<LayoutChangeHandler>();
    renderGrid(createDefaultDenseGridLayout(columns), onLayoutChange);
    const separator = screen.getByRole("separator", {
      name: "Resize Code column",
    });

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 100,
      pointerId: 7,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 400,
      pointerId: 7,
    });
    expect(onLayoutChange).not.toHaveBeenCalled();
    dispatchPointer(separator, "pointerup", {
      clientX: 400,
      pointerId: 7,
    });

    expect(onLayoutChange).toHaveBeenCalledTimes(1);
    const change = onLayoutChange.mock.calls[0]?.[0];
    expect(change?.columnId).toBe("code");
    expect(change?.layout.widths.code).toBe(180);
    expect(change?.reason).toBe("pointer_resize");
  });

  it("auto-fits only through the rendered-cell measurement and clamps the result", () => {
    const onLayoutChange = vi.fn<LayoutChangeHandler>();
    const measureColumn = vi.fn(() => 999);
    renderGrid(
      createDefaultDenseGridLayout(columns),
      onLayoutChange,
      measureColumn,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize Name column",
    });

    fireEvent.doubleClick(separator);

    expect(measureColumn).toHaveBeenCalledWith(
      "name",
      screen.getByRole("table", { name: "Engineering grid" }),
    );
    const change = onLayoutChange.mock.calls[0]?.[0];
    expect(change?.columnId).toBe("name");
    expect(change?.layout.widths.name).toBe(260);
    expect(change?.reason).toBe("auto_fit");
  });

  it("measures intrinsic wrappers so auto-fit can shrink an oversized column", () => {
    const onLayoutChange = vi.fn<LayoutChangeHandler>();
    const { container } = renderGrid(
      {
        ...createDefaultDenseGridLayout(columns),
        widths: { code: 100, name: 260, status: 120 },
      },
      onLayoutChange,
    );
    const intrinsicContents = container.querySelectorAll<HTMLElement>(
      '[data-grid-measure-column="name"]',
    );
    expect(intrinsicContents.length).toBeGreaterThan(1);
    for (const content of intrinsicContents) {
      Object.defineProperty(content, "scrollWidth", {
        configurable: true,
        value: 100,
      });
    }

    fireEvent.doubleClick(
      screen.getByRole("separator", {
        name: "Resize Name column",
      }),
    );

    expect(onLayoutChange).toHaveBeenCalledTimes(1);
    const change = onLayoutChange.mock.calls[0]?.[0];
    expect(change?.layout.widths.name).toBe(120);
    expect(change?.reason).toBe("auto_fit");
  });

  it("suppresses click-sequence and bounded resize no-ops", () => {
    const onLayoutChange = vi.fn<LayoutChangeHandler>();
    renderGrid(
      {
        ...createDefaultDenseGridLayout(columns),
        widths: { code: 80, name: 180, status: 120 },
      },
      onLayoutChange,
      () => 150,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize Code column",
    });

    for (const pointerId of [11, 12]) {
      dispatchPointer(separator, "pointerdown", {
        button: 0,
        clientX: 80,
        pointerId,
      });
      dispatchPointer(separator, "pointerup", {
        clientX: 80,
        pointerId,
      });
    }
    fireEvent.keyDown(separator, { key: "Home" });
    expect(onLayoutChange).not.toHaveBeenCalled();

    fireEvent.doubleClick(separator);
    expect(onLayoutChange).toHaveBeenCalledTimes(1);
    const change = onLayoutChange.mock.calls[0]?.[0];
    expect(change?.columnId).toBe("code");
    expect(change?.layout.widths.code).toBe(150);
    expect(change?.reason).toBe("auto_fit");
  });

  it("clears a pointer preview when release returns to the starting width", () => {
    const onLayoutChange = vi.fn<LayoutChangeHandler>();
    const { container } = renderGrid(
      createDefaultDenseGridLayout(columns),
      onLayoutChange,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize Code column",
    });

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 100,
      pointerId: 13,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 132,
      pointerId: 13,
    });
    expect(separator).toHaveAttribute("aria-valuenow", "132");
    expect(
      container.querySelector<HTMLTableColElement>(
        'col[data-grid-column="code"]',
      ),
    ).toHaveStyle({ width: "132px" });

    dispatchPointer(separator, "pointerup", {
      clientX: 100,
      pointerId: 13,
    });

    expect(onLayoutChange).not.toHaveBeenCalled();
    expect(separator).toHaveAttribute("aria-valuenow", "100");
    expect(
      container.querySelector<HTMLTableColElement>(
        'col[data-grid-column="code"]',
      ),
    ).toHaveStyle({ width: "100px" });
  });

  it("restores the confirmed width after pointer capture is lost", () => {
    const onLayoutChange = vi.fn<LayoutChangeHandler>();
    renderGrid(createDefaultDenseGridLayout(columns), onLayoutChange);
    const separator = screen.getByRole("separator", {
      name: "Resize Code column",
    });

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 100,
      pointerId: 14,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 132,
      pointerId: 14,
    });
    expect(separator).toHaveAttribute("aria-valuenow", "132");
    dispatchPointer(separator, "lostpointercapture", {
      clientX: 132,
      pointerId: 14,
    });
    expect(separator).toHaveAttribute("aria-valuenow", "100");

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 200,
      pointerId: 15,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 208,
      pointerId: 15,
    });
    dispatchPointer(separator, "pointerup", {
      clientX: 208,
      pointerId: 15,
    });

    expect(onLayoutChange).toHaveBeenCalledTimes(1);
    expect(onLayoutChange.mock.calls[0]?.[0].layout.widths.code).toBe(108);
    expect(separator).toHaveAttribute("aria-valuenow", "108");
  });

  it("provides Arrow, Home, End, and Enter keyboard alternatives", () => {
    const onLayoutChange = vi.fn<LayoutChangeHandler>();
    renderGrid(
      createDefaultDenseGridLayout(columns),
      onLayoutChange,
      () => 150,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize Code column",
    });

    fireEvent.keyDown(separator, { key: "ArrowRight" });
    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    fireEvent.keyDown(separator, { key: "Home" });
    fireEvent.keyDown(separator, { key: "End" });
    fireEvent.keyDown(separator, { key: "Enter" });

    expect(onLayoutChange.mock.calls.map(([change]) => change.reason)).toEqual([
      "keyboard_resize",
      "keyboard_resize",
      "keyboard_resize",
      "keyboard_resize",
      "auto_fit",
    ]);
    expect(
      onLayoutChange.mock.calls.map(([change]) => change.layout.widths.code),
    ).toEqual([108, 100, 80, 180, 150]);
    expect(separator).toHaveAttribute("aria-valuemin", "80");
    expect(separator).toHaveAttribute("aria-valuemax", "180");
    expect(separator).toHaveAttribute("aria-valuenow", "150");
  });

  it("supports spanning group rows while retaining normal data rows", () => {
    render(
      <DenseGrid
        ariaLabel="Grouped grid"
        columns={columns}
        getRowKey={(row) => row.code}
        layout={createDefaultDenseGridLayout(columns)}
        onLayoutChange={vi.fn()}
        renderSpanningRow={(row) =>
          row.code === "P-001" ? <strong>Group A</strong> : null
        }
        resizeColumnLabel={(label) => `Resize ${label} column`}
        resizeHelp="Resize help"
        rows={rows}
        tableRole="treegrid"
      />,
    );

    const grid = screen.getByRole("treegrid", { name: "Grouped grid" });
    expect(within(grid).getByText("Group A")).toBeVisible();
    expect(within(grid).getByText("Connector")).toBeVisible();
  });

  it("disables persistence interactions until its owner is ready", () => {
    const onLayoutChange = vi.fn<LayoutChangeHandler>();
    const measureColumn = vi.fn(() => 150);
    render(
      <DenseGrid
        ariaLabel="Loading grid"
        columns={columns}
        getRowKey={(row) => row.code}
        interactionDisabled
        layout={createDefaultDenseGridLayout(columns)}
        measureColumn={measureColumn}
        onLayoutChange={onLayoutChange}
        resizeColumnLabel={(label) => `Resize ${label} column`}
        resizeHelp="Resize help"
        rows={rows}
      />,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize Code column",
    });

    expect(separator).toHaveAttribute("aria-disabled", "true");
    expect(separator).toHaveAttribute("tabindex", "-1");
    fireEvent.keyDown(separator, { key: "ArrowRight" });
    fireEvent.doubleClick(separator);
    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 100,
      pointerId: 18,
    });
    dispatchPointer(separator, "pointerup", {
      clientX: 124,
      pointerId: 18,
    });
    expect(measureColumn).not.toHaveBeenCalled();
    expect(onLayoutChange).not.toHaveBeenCalled();
  });

  it("resets one width or the complete code-owned layout", () => {
    const changed: DenseGridLayout<ColumnId> = {
      columnOrder: ["status", "name", "code"],
      fixedColumnCount: 1,
      hiddenColumnIds: ["status"],
      widths: { code: 140, name: 240, status: 160 },
    };
    expect(resetDenseGridColumn(columns, changed, "code").widths.code).toBe(
      100,
    );
    expect(resetDenseGridLayout(columns, 2)).toEqual({
      columnOrder: ["code", "name", "status"],
      fixedColumnCount: 2,
      hiddenColumnIds: [],
      widths: { code: 100, name: 180, status: 120 },
    });
  });
});
