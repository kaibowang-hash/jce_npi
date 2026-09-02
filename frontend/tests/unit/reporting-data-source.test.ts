import { describe, expect, it, vi } from "vitest";

import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  isConfigurationCapabilityCatalog,
  isGlobalSearchResponse,
  isKpiTrendResponse,
  isProjectPortfolioResponse,
  LiveReportingDataSource,
} from "../../src/api/reporting-data-source";
import {
  configurationFixture,
  globalSearchFixture,
  kpiFixture,
  portfolioFixture,
} from "../support/reporting-fixture";

describe("reporting data source", () => {
  it("uses fixed read-only reporting paths with bounded server filters", async () => {
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(globalSearchFixture("synthetic"))
      .mockResolvedValueOnce(portfolioFixture({ lifecycleState: "active" }))
      .mockResolvedValueOnce(kpiFixture())
      .mockResolvedValueOnce(configurationFixture());
    const source = new LiveReportingDataSource(http);
    const signal = new AbortController().signal;

    await source.search("synthetic", ["project"], { limit: 25 }, signal);
    await source.loadPortfolio(
      { lifecycleState: "active" },
      { limit: 50 },
      signal,
    );
    await source.loadKpis("2026-04", "2026-09", {}, signal);
    await source.loadConfiguration(signal);

    expect(request.mock.calls.map((call) => call[0])).toEqual([
      "/search",
      "/portfolio/projects",
      "/reports/kpis",
      "/administration/capabilities",
    ]);
    expect(request.mock.calls[0]?.[2]).toMatchObject({
      query: { kinds: "project", limit: "25", query: "synthetic" },
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(request.mock.calls[1]?.[2]).toMatchObject({
      query: { lifecycleState: "active", limit: "50" },
    });
  });

  it("fails closed on extra fields, foreign routes, and fabricated KPI points", () => {
    expect(isGlobalSearchResponse(globalSearchFixture())).toBe(true);
    expect(
      isGlobalSearchResponse({
        ...globalSearchFixture(),
        leakedValue: "secret",
      }),
    ).toBe(false);
    const portfolio = portfolioFixture();
    expect(isProjectPortfolioResponse(portfolio)).toBe(true);
    expect(
      isProjectPortfolioResponse({
        ...portfolio,
        items: [{ ...portfolio.items[0], detailRoute: "//attacker.invalid" }],
      }),
    ).toBe(false);
    expect(
      isProjectPortfolioResponse({
        ...portfolio,
        items: [
          {
            ...portfolio.items[0],
            detailRoute: `/projects/${portfolio.items[0]?.globalId ?? ""}-suffix`,
          },
        ],
      }),
    ).toBe(false);
    const kpis = kpiFixture();
    expect(isKpiTrendResponse(kpis)).toBe(true);
    expect(
      isKpiTrendResponse({
        ...kpis,
        series: [
          {
            ...kpis.series[0],
            availability: "unavailable",
            points: [
              { month: "2026-09", numerator: 1, denominator: 1, value: 100 },
            ],
          },
          ...kpis.series.slice(1),
        ],
      }),
    ).toBe(false);
    expect(isConfigurationCapabilityCatalog(configurationFixture())).toBe(true);
  });

  it("rejects caller-selected filters and invalid query bounds before transport", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveReportingDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.search("x", ["project"], { limit: 25 }, signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.loadPortfolio(
        { ownerUserId: "not-an-email" },
        { limit: 50 },
        signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.loadKpis("2026-10", "2026-09", {}, signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
