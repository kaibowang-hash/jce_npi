import type {
  ConfigurationCapabilityCatalog,
  GlobalSearchResponse,
  KpiTrendResponse,
  ProjectPortfolioResponse,
  ReportingDataSource,
  ReportingFilters,
} from "../../src/api/reporting-data-source";

export const reportingProjectId = "11111111-1111-4111-8111-111111111111";

export function globalSearchFixture(query = "SYN"): GlobalSearchResponse {
  return {
    schemaVersion: 1,
    query,
    kinds: ["project", "tooling"],
    items: [
      {
        schemaVersion: 1,
        kind: "project",
        globalId: reportingProjectId,
        projectGlobalId: reportingProjectId,
        label: "Synthetic project cockpit",
        code: "SYN-PROJECT-001",
        sourceSystem: "NPI_ONE",
        availability: "available",
        detailRoute: `/projects/${reportingProjectId}`,
        version: 3,
      },
    ],
    page: { limit: 25, hasMore: false, nextCursor: null },
    permissions: { serverFiltered: true },
  };
}

export function portfolioFixture(
  filters: Partial<ReportingFilters> = {},
): ProjectPortfolioResponse {
  return {
    schemaVersion: 1,
    asOf: "2026-09-01T08:00:00Z",
    filters: {
      customerReferenceKey: filters.customerReferenceKey ?? null,
      factoryReferenceKey: filters.factoryReferenceKey ?? null,
      lifecycleState: filters.lifecycleState ?? null,
      ownerUserId: filters.ownerUserId ?? null,
      projectType: filters.projectType ?? null,
      sopMonth: filters.sopMonth ?? null,
    },
    items: [
      {
        schemaVersion: 1,
        globalId: reportingProjectId,
        businessCode: "SYN-PROJECT-001",
        title: "Synthetic project cockpit",
        projectType: "new_tool",
        ownerUserId: "project.owner@example.invalid",
        targetSop: "2026-10-15",
        lifecycleState: "active",
        version: 3,
        customerReferenceKeys: ["SYN-CUSTOMER-001"],
        factoryReferenceKeys: ["SYN-FACTORY-001"],
        health: {
          state: "yellow",
          assessedAt: "2026-09-01T07:30:00Z",
          sourceSystem: "NPI_ONE",
        },
        currentGate: {
          globalId: "22222222-2222-4222-8222-222222222222",
          key: "G2",
          title: "Synthetic design release",
          sequence: 3,
          reviewState: "in_review",
          dueDate: "2026-09-15",
        },
        work: {
          activeCount: 5,
          overdueCount: 1,
          blockerCount: 1,
          decisionCount: 2,
          sourceSystem: "NPI_ONE",
        },
        erp: {
          sourceSystem: "ERPNEXT",
          availability: "stale",
          reasonCode: "projection_stale",
          observedKinds: ["customer", "item"],
          freshestAt: "2026-08-31T12:00:00Z",
        },
        detailRoute: `/projects/${reportingProjectId}`,
      },
    ],
    page: { limit: 50, hasMore: false, nextCursor: null },
    permissions: { serverFiltered: true },
  };
}

export function kpiFixture(
  filters: Partial<ReportingFilters> = {},
): KpiTrendResponse {
  const normalized = portfolioFixture(filters).filters;
  return {
    schemaVersion: 1,
    fromMonth: "2026-04",
    toMonth: "2026-09",
    filters: normalized,
    visibleProjectCount: 1,
    series: [
      ["project_sop_on_time_rate", "percent"],
      ["project_cycle_time_days", "days"],
      ["trial_first_pass_rate", "percent"],
      ["project_cost_variance_rate", "percent"],
    ].map(([key, valueKind]) => ({
      definition: {
        schemaVersion: 1,
        key: key as KpiTrendResponse["series"][number]["definition"]["key"],
        labelSource: String(key),
        valueKind: valueKind as "percent" | "days",
        numeratorSource: "governed_numerator",
        denominatorSource: "governed_denominator",
        sourceSystem: "NPI_ONE" as const,
        timeZone: "site" as const,
      },
      availability: "available" as const,
      reasonCode: "available",
      points: [{ month: "2026-09", numerator: 8, denominator: 10, value: 80 }],
    })),
    permissions: { serverFiltered: true },
  };
}

export function configurationFixture(): ConfigurationCapabilityCatalog {
  return {
    schemaVersion: 1,
    mode: "read_only_catalog",
    genericWriterAvailable: false,
    activation: {
      identityAuthority: "MICROSOFT_ENTRA",
      sessionAuthority: "FRAPPE",
      authorizationAuthority: "ERPNEXT",
      entraLoginState: "ready",
      selfSignupState: "disabled",
      authorizationIngressState: "disabled",
      authorizationEnforcementState: "disabled",
      authorizationPolicyState: "not_configured",
      localUserProvisioningState: "ready",
      erpAuthorizationSenderState: "external_verification_required",
      erpBusinessAdaptersState: "implementation_required",
      supportAdministrationPath: "/app",
    },
    items: [
      {
        key: "project_templates",
        labelSource: "Project templates",
        mode: "versioned_commands",
        route: "/administration/project-templates",
      },
    ],
  };
}

export class SyntheticReportingDataSource implements ReportingDataSource {
  search(query: string): Promise<GlobalSearchResponse> {
    const response = globalSearchFixture(query);
    return Promise.resolve(
      query.toUpperCase().includes("SYN")
        ? response
        : { ...response, items: [] },
    );
  }

  loadPortfolio(
    filters: Partial<ReportingFilters>,
  ): Promise<ProjectPortfolioResponse> {
    return Promise.resolve(portfolioFixture(filters));
  }

  loadKpis(
    _fromMonth: string,
    _toMonth: string,
    filters: Partial<ReportingFilters>,
  ): Promise<KpiTrendResponse> {
    return Promise.resolve(kpiFixture(filters));
  }

  loadConfiguration(): Promise<ConfigurationCapabilityCatalog> {
    return Promise.resolve(configurationFixture());
  }
}
