import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PortfolioPage from "../../src/pages/portfolio-page";
import {
  portfolioFixture,
  SyntheticReportingDataSource,
} from "../support/reporting-fixture";
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
    expect(within(table).getByText("Project linked")).toBeVisible();
    expect(within(table).getByText("SYN-ERP-PROJECT-001")).toBeVisible();
    expect(within(table).getByText(/ERP facts.*Stale/u)).toBeVisible();
  });

  it("does not label an unobserved project as an unavailable ERPNext system", async () => {
    const dataSource = new SyntheticReportingDataSource();
    vi.spyOn(dataSource, "loadPortfolio").mockResolvedValue({
      ...portfolioFixture(),
      items: portfolioFixture().items.map((item) => ({
        ...item,
        erp: {
          ...item.erp,
          availability: "unavailable",
          reasonCode: "erp_projection_not_observed",
          observedKinds: [],
          freshestAt: null,
        },
      })),
    });
    renderWithLocale(
      <PortfolioPage
        dataSource={dataSource}
        navigate={vi.fn()}
        view="portfolio"
      />,
      "en",
      "/portfolio",
    );

    expect(await screen.findByText("Project linked")).toBeVisible();
    expect(screen.getByText("No ERP fact observations yet.")).toBeVisible();
    expect(screen.queryByText("Unavailable")).toBeNull();
  });

  it("distinguishes an unbound NPI project from ERPNext service availability", async () => {
    const dataSource = new SyntheticReportingDataSource();
    vi.spyOn(dataSource, "loadPortfolio").mockResolvedValue({
      ...portfolioFixture(),
      items: portfolioFixture().items.map((item) => ({
        ...item,
        erp: {
          ...item.erp,
          projectBinding: {
            sourceSystem: "ERPNEXT",
            state: "unbound",
            sourceObjectId: null,
            lastProcessedAt: null,
            requestGlobalId: null,
            errorCode: null,
          },
        },
      })),
    });
    renderWithLocale(
      <PortfolioPage
        dataSource={dataSource}
        navigate={vi.fn()}
        view="portfolio"
      />,
      "en",
      "/portfolio",
    );

    expect(await screen.findByText("Project not linked")).toBeVisible();
    expect(screen.queryByText("SYN-ERP-PROJECT-001")).toBeNull();
    expect(screen.getByText(/ERP facts.*Stale/u)).toBeVisible();
  });

  it.each([
    ["linking", "Project link in progress"],
    ["failed", "Project link failed"],
  ] as const)(
    "renders the %s ERP Project publication state",
    async (state, label) => {
      const dataSource = new SyntheticReportingDataSource();
      vi.spyOn(dataSource, "loadPortfolio").mockResolvedValue({
        ...portfolioFixture(),
        items: portfolioFixture().items.map((item) => ({
          ...item,
          erp: {
            ...item.erp,
            projectBinding: {
              sourceSystem: "ERPNEXT",
              state,
              sourceObjectId: null,
              lastProcessedAt: "2026-09-06T08:00:00Z",
              requestGlobalId: "66666666-6666-4666-8666-666666666666",
              errorCode:
                state === "failed" ? "ERP_PROJECT_CREATE_REJECTED" : null,
            },
          },
        })),
      });
      renderWithLocale(
        <PortfolioPage
          dataSource={dataSource}
          navigate={vi.fn()}
          view="portfolio"
        />,
        "en",
        "/portfolio",
      );

      expect(await screen.findByText(label)).toBeVisible();
    },
  );

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
      screen.getByRole("heading", {
        level: 2,
        name: "Production activation readiness",
      }),
    ).toBeVisible();
    const readiness = screen.getAllByRole("table")[0];
    if (!readiness)
      throw new Error("The activation readiness table is missing.");
    expect(within(readiness).getByText("Sign-in and MFA")).toBeVisible();
    expect(
      within(readiness).getByText("User, role and scope management"),
    ).toBeVisible();
    expect(
      within(readiness).getAllByText("Implementation required"),
    ).toHaveLength(1);
    const provisioning = within(readiness).getByRole("row", {
      name: /LaunchFlow user provisioning/u,
    });
    expect(within(provisioning).getByText("Ready")).toBeVisible();
    expect(within(provisioning).getByText("No change")).toBeVisible();
    expect(
      within(readiness).getByRole("link", {
        name: "Open Frappe administration",
      }),
    ).toHaveAttribute("href", "/app");
    expect(
      screen.getByRole("link", { name: "Configure project templates" }),
    ).toHaveAttribute("href", "/app/npi-project-template");
    expect(
      screen.getByRole("link", { name: "Configure project template versions" }),
    ).toHaveAttribute("href", "/app/npi-project-template-version");
    expect(
      screen.queryByRole("button", { name: "Open controlled configuration" }),
    ).toBeNull();
    await user.click(screen.getByRole("button", { name: "Portfolio" }));
    expect(navigate).toHaveBeenCalledWith("/portfolio");
  });
});
