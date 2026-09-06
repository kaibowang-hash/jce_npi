import { useState } from "react";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ERPMasterSelect } from "../../src/components/erp-master-select";
import type {
  ERPMasterDataSource,
  ERPMasterRecord,
} from "../../src/api/erp-master-data-source";
import { NpiTransportError } from "../../src/api/http";
import { renderWithLocale } from "../support/render";
import { masterPage } from "../support/erp-master-fixture";

function Harness({
  source,
  changed = vi.fn(),
  disabled = false,
}: {
  source: ERPMasterDataSource;
  changed?: (row: ERPMasterRecord | null) => void;
  disabled?: boolean;
}): React.JSX.Element {
  const [value, setValue] = useState("");
  return (
    <ERPMasterSelect
      kind="machine"
      label="Machine"
      value={value}
      disabled={disabled}
      dataSource={source}
      onChange={(row) => {
        setValue(row?.sourceKey ?? "");
        changed(row);
      }}
    />
  );
}

describe("ERP master selector", () => {
  it("searches by name and selects the returned identity by keyboard", async () => {
    const page = masterPage("machine");
    const first = page.items[0];
    if (!first) throw new Error("Fixture record missing");
    page.items = [
      {
        ...first,
        sourceKey: "机台 550-02",
        displayName: "Injection machine 550T",
      },
    ];
    const load = vi.fn<ERPMasterDataSource["load"]>().mockResolvedValue(page),
      changed = vi.fn(),
      user = userEvent.setup();
    renderWithLocale(<Harness source={{ load }} changed={changed} />);
    const input = screen.getByRole("combobox", { name: "Machine" });
    await user.type(input, "550");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading ERPNext choices",
    );
    await screen.findByRole("option", { name: /机台 550-02/u });
    expect(load).toHaveBeenLastCalledWith(
      "machine",
      "550",
      0,
      expect.any(AbortSignal),
      undefined,
    );
    await user.keyboard("{ArrowDown}{Enter}");
    expect(changed).toHaveBeenCalledWith(page.items[0]);
    expect(input).toHaveValue("机台 550-02 — Injection machine 550T");
    expect(input).toHaveFocus();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(changed).toHaveBeenLastCalledWith(null);
  });
  it("does not select disabled records and distinguishes empty and stale catalogs", async () => {
    const page = masterPage("machine");
    const first = page.items[0];
    if (!first) throw new Error("Fixture record missing");
    page.items = [{ ...first, enabled: false }];
    const changed = vi.fn(),
      load = vi.fn<ERPMasterDataSource["load"]>().mockResolvedValue(page),
      user = userEvent.setup();
    renderWithLocale(<Harness source={{ load }} changed={changed} />);
    await user.click(screen.getByRole("combobox"));
    const option = await screen.findByRole("option");
    expect(option).toHaveAttribute("aria-disabled", "true");
    await user.click(option);
    expect(changed).not.toHaveBeenCalled();
    load.mockResolvedValue(masterPage("machine", { items: [], total: 0 }));
    await user.type(screen.getByRole("combobox"), "missing");
    await screen.findByText(
      "No matching ERPNext records are available in this scope.",
    );
    load.mockResolvedValue(
      masterPage("machine", { lastSynchronizedAt: "2000-01-01T00:00:00Z" }),
    );
    await user.type(screen.getByRole("combobox"), "stale");
    await screen.findByText(
      "ERPNext choices are unavailable or out of date. Refresh after synchronization.",
    );
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });
  it("shows failures with retry and pages the same query", async () => {
    const load = vi
      .fn<ERPMasterDataSource["load"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "trace-select-test", "client"),
      )
      .mockResolvedValue(masterPage("machine", { total: 21 }));
    const user = userEvent.setup();
    renderWithLocale(<Harness source={{ load }} />);
    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByRole("button", { name: "Retry" }));
    await screen.findByRole("option");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(load).toHaveBeenLastCalledWith(
        "machine",
        "",
        20,
        expect.any(AbortSignal),
        undefined,
      );
    });
  });
  it("never requests data in read-only mode", () => {
    const load = vi.fn<ERPMasterDataSource["load"]>();
    renderWithLocale(<Harness source={{ load }} disabled />);
    expect(screen.getByRole("combobox")).toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Show ERPNext choices" }),
    );
    expect(load).not.toHaveBeenCalled();
  });
  it.each(["en", "zh", "zh-TW"] as const)(
    "renders loading/empty controls through the %s catalog",
    async (locale) => {
      renderWithLocale(
        <Harness
          source={{
            load: () =>
              Promise.resolve(masterPage("machine", { items: [], total: 0 })),
          }}
        />,
        locale,
      );
      fireEvent.click(screen.getByRole("combobox"));
      await waitFor(() => {
        expect(screen.getByRole("status")).not.toHaveTextContent(
          /Loading ERPNext choices|正在加载|正在載入/u,
        );
      });
      if (locale !== "en")
        expect(screen.getByRole("status").textContent).not.toMatch(
          /No matching|Refresh|unavailable/u,
        );
    },
  );
});
