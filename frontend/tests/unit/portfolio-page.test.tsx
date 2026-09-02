import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PortfolioPage from "../../src/pages/portfolio-page";
import { SyntheticReportingDataSource } from "../support/reporting-fixture";
import { renderWithLocale } from "../support/render";

describe("Portfolio reporting workspace", () => {
  it("renders permission-filtered NPI and ERP truth without merging ownership", async () => {
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(
      <PortfolioPage
        dataSource={new SyntheticReportingDataSource()}
        navigate={navigate}
        view="portfolio"
      />,
      "en",
      "/portfolio",
    );

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Project Portfolio",
      }),
    ).toBeVisible();
    const table = screen.getByRole("table");
    expect(within(table).getByText("SYN-PROJECT-001")).toBeVisible();
    expect(within(table).getByText("Yellow")).toBeVisible();
    expect(within(table).getByText("JCE Core")).toBeVisible();
    expect(within(table).getByText("Stale")).toBeVisible();
  });

  it("shows fixed KPI definitions and honest availability", async () => {
    renderWithLocale(
      <PortfolioPage
        dataSource={new SyntheticReportingDataSource()}
        navigate={vi.fn()}
        view="kpis"
      />,
      "en",
      "/reports",
    );

    expect(await screen.findByText("Project SOP on-time rate")).toBeVisible();
    expect(screen.getAllByText("Available")).toHaveLength(4);
    expect(screen.getAllByText("governed_numerator")).toHaveLength(4);
  });

  it("keeps administration read-only and routes only approved top-level workspaces", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    renderWithLocale(
      <PortfolioPage
        dataSource={new SyntheticReportingDataSource()}
        navigate={navigate}
        view="configuration"
      />,
      "en",
      "/administration",
    );

    expect(
      await screen.findByText(
        "Configuration remains operation-specific. A generic field or DocType writer is not available.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText("Available through its governed command workspace"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Open controlled configuration" }),
    ).toBeNull();
    await user.click(screen.getByRole("button", { name: "Portfolio" }));
    expect(navigate).toHaveBeenCalledWith("/portfolio");
  });
});
