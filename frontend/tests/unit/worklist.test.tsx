import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Worklist, worklistWindowSize } from "../../src/components/worklist";
import {
  PrototypeWorklistTransport,
  type WorklistQuery,
} from "../../src/api/worklist-data-source";
import { NpiApiError } from "../../src/api/http";
import type { WorkItemViewModel } from "../../src/domain/view-models";
import { prototypeTimestamp, workItems } from "../../src/fixtures/prototype";
import { renderWithLocale } from "../support/render";

function manyItems(count: number): WorkItemViewModel[] {
  const fixture = workItems[0];
  if (!fixture) throw new Error("The worklist fixture must contain one item.");
  return Array.from({ length: count }, (_, index) => ({
    ...fixture,
    contextCode: `PJ-${String(index + 1).padStart(5, "0")}`,
    dueAt: `2026-08-${String((index % 28) + 1).padStart(2, "0")}T08:00:00Z`,
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
  }));
}

function dataSource(
  items: readonly WorkItemViewModel[] = workItems,
): PrototypeWorklistTransport {
  return new PrototypeWorklistTransport(items);
}

describe("dense cross-object worklist", () => {
  it("queries only the requested page through the fixture transport contract", async () => {
    const transport = dataSource(manyItems(55));
    const page = await transport.query({
      asOf: prototypeTimestamp,
      filter: "",
      groupBy: "none",
      limit: worklistWindowSize,
      offset: worklistWindowSize,
      savedView: "focus",
      sortDescending: false,
    });

    expect(page.offset).toBe(worklistWindowSize);
    expect(page.items).toHaveLength(worklistWindowSize);
    expect(page.total).toBe(55);
  });

  it("shows assignment rationale, context, due date, state, source, and next action", async () => {
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource()}
        onOpen={vi.fn()}
      />,
    );
    await screen.findByText("Review G5 sample approval");
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader")).toHaveLength(7);
    expect(within(table).getAllByRole("row")).toHaveLength(
      workItems.length + 1,
    );
    expect(
      screen.getAllByText("You are the engineering signatory.").length,
    ).toBeGreaterThan(0);
    expect(
      screen.queryByText("11111111-1111-4111-8111-111111111111"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("LaunchFlow")).toBeVisible();
    expect(
      screen.getByRole("img", { name: "LaunchFlow platform" }),
    ).toHaveAttribute("data-brand-context", "platform-source");
  });

  it("filters by object context and opens the selected next action", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource()}
        onOpen={onOpen}
      />,
    );

    await screen.findByText("Review G5 sample approval");
    await user.type(
      screen.getByRole("searchbox", { name: "Filter" }),
      "Asset handover",
    );
    await within(screen.getByRole("table")).findByRole("button", {
      name: "View execution",
    });
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(
      2,
    );
    await user.click(
      within(screen.getByRole("table")).getByRole("button", {
        name: "View execution",
      }),
    );
    expect(onOpen).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "integration" }),
    );
  });

  it("changes selection without navigation and toggles due-date order", async () => {
    const user = userEvent.setup();
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource()}
        onOpen={vi.fn()}
      />,
    );
    await screen.findByText("Review G5 sample approval");
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    const selectedRow = rows.at(2);
    expect(selectedRow).toBeDefined();
    if (!selectedRow)
      throw new Error("The worklist fixture must contain a selectable row.");
    await user.click(selectedRow);
    expect(selectedRow).toHaveAttribute("aria-selected", "true");
    await user.click(screen.getByRole("button", { name: "Newest first" }));
    expect(screen.getByRole("button", { name: "Oldest first" })).toBeVisible();
  });

  it("restores selected work context after the worklist remounts", async () => {
    const user = userEvent.setup();
    const first = renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource()}
        onOpen={vi.fn()}
      />,
    );
    const integrationTitle = await within(screen.getByRole("table")).findByText(
      "Tool asset creation failed",
    );
    const selectedRow = integrationTitle.closest("tr");
    expect(selectedRow).not.toBeNull();
    if (!selectedRow) throw new Error("The integration row is required.");
    await user.click(selectedRow);
    expect(selectedRow).toHaveAttribute("aria-selected", "true");

    first.unmount();
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource()}
        onOpen={vi.fn()}
      />,
    );
    const restoredRow = (
      await within(screen.getByRole("table")).findByText(
        "Tool asset creation failed",
      )
    ).closest("tr");
    expect(restoredRow).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Asset handover")).toBeVisible();
  });

  it("applies and persists saved views, groups rows, and changes visible columns", async () => {
    const user = userEvent.setup();
    const firstRender = renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource()}
        onOpen={vi.fn()}
      />,
    );

    await screen.findByText("Review G5 sample approval");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Saved view" }),
      "integration",
    );
    await within(screen.getByRole("table")).findByRole("button", {
      name: "View execution",
    });
    expect(globalThis.localStorage.getItem("npi-one-worklist-saved-view")).toBe(
      "integration",
    );
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(
      2,
    );

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Group by" }),
      "kind",
    );
    await within(screen.getByRole("treegrid")).findByRole("button", {
      name: "View execution",
    });
    expect(screen.getByText("Grouped by Type")).toBeVisible();
    const treegrid = screen.getByRole("treegrid");
    const groupToggle = within(treegrid).getByRole("button", {
      name: "Toggle group",
    });
    expect(groupToggle).toHaveAttribute("aria-expanded", "true");
    await user.click(groupToggle);
    expect(
      within(treegrid).queryByRole("button", { name: "View execution" }),
    ).not.toBeInTheDocument();
    await user.click(groupToggle);

    await user.click(screen.getByRole("button", { name: "Columns" }));
    await user.click(screen.getByRole("checkbox", { name: "Due" }));
    expect(
      within(treegrid).queryByRole("columnheader", {
        name: "Due",
      }),
    ).not.toBeInTheDocument();

    firstRender.unmount();
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource()}
        onOpen={vi.fn()}
      />,
    );
    await within(screen.getByRole("treegrid")).findByRole("button", {
      name: "View execution",
    });
    expect(screen.getByRole("combobox", { name: "Saved view" })).toHaveValue(
      "integration",
    );
    expect(screen.getByRole("combobox", { name: "Group by" })).toHaveValue(
      "kind",
    );
    expect(
      within(screen.getByRole("treegrid")).queryByRole("columnheader", {
        name: "Due",
      }),
    ).not.toBeInTheDocument();
  });

  it("shows an actionable no-match row and clears the active query", async () => {
    const user = userEvent.setup();
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource()}
        onOpen={vi.fn()}
      />,
    );

    await screen.findByText("Review G5 sample approval");
    await user.type(
      screen.getByRole("searchbox", { name: "Filter" }),
      "no matching object",
    );
    expect(await screen.findByText("No items match this view.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    await screen.findByText("Review G5 sample approval");
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(
      workItems.length + 1,
    );
  });

  it("preserves a safe query problem trace and retries the same worklist query", async () => {
    const user = userEvent.setup();
    const healthyTransport = dataSource();
    const failure = new NpiApiError({
      type: "urn:npi:problem:worklist_unavailable",
      title: "The worklist is temporarily unavailable.",
      status: 503,
      code: "WORKLIST_UNAVAILABLE",
      traceId: "trace-worklist-query",
      retryable: true,
    });
    Object.defineProperty(failure, "cause", {
      value: new Error("raw database password must never render"),
    });
    const query = vi
      .fn()
      .mockRejectedValueOnce(failure)
      .mockImplementation((worklistQuery: WorklistQuery) =>
        healthyTransport.query(worklistQuery),
      );
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={{ query }}
        onOpen={vi.fn()}
      />,
    );

    expect(
      await screen.findByText("The worklist is temporarily unavailable."),
    ).toBeVisible();
    expect(screen.getByText("trace-worklist-query")).toBeVisible();
    expect(document.body).not.toHaveTextContent(
      "raw database password must never render",
    );
    const retry = screen.getByRole("button", { name: "Retry" });
    retry.focus();
    expect(retry).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(await screen.findByText("Review G5 sample approval")).toBeVisible();
    expect(screen.queryByText("trace-worklist-query")).not.toBeInTheDocument();
    expect(query).toHaveBeenCalledTimes(2);
  });

  it("marks final failures as danger and never mislabels a read-only source as editable", async () => {
    const fixture = workItems[0];
    if (!fixture)
      throw new Error("The worklist fixture must contain one item.");
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource([
          {
            ...fixture,
            status: "failed_final",
            source: {
              ...fixture.source,
              editableIn: "NONE",
              syncState: "failed_final",
            },
          },
        ])}
        onOpen={vi.fn()}
      />,
    );

    await screen.findByText("No system is editable");
    expect(
      within(screen.getByRole("table"))
        .getByText("Failed, manual action required")
        .closest(".semantic-status"),
    ).toHaveAttribute("data-status-tone", "danger");
    expect(screen.getByText("No system is editable")).toBeVisible();
  });

  it("bounds the rendered row window and pages through a larger result", async () => {
    const user = userEvent.setup();
    const items = manyItems(worklistWindowSize + 5);
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource(items)}
        onOpen={vi.fn()}
      />,
    );
    await screen.findByText(
      `Showing 1–${String(worklistWindowSize)} of ${String(items.length)} items`,
    );
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(
      worklistWindowSize + 1,
    );
    expect(
      screen.getByText(
        `Showing 1–${String(worklistWindowSize)} of ${String(items.length)} items`,
      ),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Showing 21–25 of 25 items");
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(
      6,
    );
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Previous page" }));
    await screen.findByText("Showing 1–20 of 25 items");
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
  });

  it("keeps a 10,000-item result bounded and renders the first page within three seconds", async () => {
    const items = manyItems(10_000);
    const startedAt = performance.now();
    renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource(items)}
        onOpen={vi.fn()}
      />,
    );
    await screen.findByText("Showing 1–20 of 10,000 items");
    const elapsedMilliseconds = performance.now() - startedAt;

    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(
      worklistWindowSize + 1,
    );
    expect(screen.getByText("Showing 1–20 of 10,000 items")).toBeVisible();
    expect(elapsedMilliseconds).toBeLessThan(3_000);
  });

  it("renders an empty worklist without a stale inspector selection", async () => {
    const { container } = renderWithLocale(
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={dataSource([])}
        onOpen={vi.fn()}
      />,
    );
    expect(await screen.findByText("Showing 0–0 of 0 items")).toBeVisible();
    expect(
      container.querySelector(".docked-inspector"),
    ).not.toBeInTheDocument();
  });
});
