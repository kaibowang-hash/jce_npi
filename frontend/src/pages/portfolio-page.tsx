import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  ConfigurationCapabilityCatalog,
  KpiSeries,
  KpiTrendResponse,
  PortfolioLifecycleState,
  PortfolioProjectType,
  ProjectPortfolioResponse,
  ReportingAvailability,
  ReportingDataSource,
  ReportingFilters,
} from "../api/reporting-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import {
  Panel,
  SemanticStatus,
  SourceSystemIdentity,
} from "../components/primitives";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { formatDate, formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

export type ReportingView = "portfolio" | "kpis" | "configuration";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };

const emptyFilters: Partial<ReportingFilters> = {};

function availabilityLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ReportingAvailability,
): string {
  switch (value) {
    case "available":
      return t("Available");
    case "stale":
      return t("Stale");
    case "partial":
      return t("Partial");
    case "unavailable":
      return t("Unavailable");
  }
}

function availabilityTone(
  value: ReportingAvailability,
): "success" | "warning" | "danger" | "neutral" {
  if (value === "available") return "success";
  if (value === "stale" || value === "partial") return "warning";
  return "danger";
}

function projectTypeLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: PortfolioProjectType,
): string {
  switch (value) {
    case "customer_owned_tool":
      return t("Customer-owned tool project");
    case "new_tool":
      return t("New tool project");
    case "tool_change":
      return t("Tool change project");
  }
}

function lifecycleLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: PortfolioLifecycleState,
): string {
  switch (value) {
    case "draft":
      return t("Draft");
    case "proposed":
      return t("Proposed");
    case "active":
      return t("Active");
    case "on_hold":
      return t("On hold");
    case "completed":
      return t("Completed");
    case "cancelled":
      return t("Cancelled");
  }
}

function gateStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: "not_started" | "in_review" | "decided" | "requires_review",
): string {
  switch (value) {
    case "not_started":
      return t("Not started");
    case "in_review":
      return t("In review");
    case "decided":
      return t("Decided");
    case "requires_review":
      return t("Requires review");
  }
}

function healthLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: "unassessed" | "unavailable" | "green" | "yellow" | "red",
): string {
  switch (value) {
    case "unassessed":
      return t("Unassessed");
    case "unavailable":
      return t("Unavailable");
    case "green":
      return t("Green");
    case "yellow":
      return t("Yellow");
    case "red":
      return t("Red");
  }
}

function kpiLabel(
  t: ReturnType<typeof useI18n>["t"],
  key: KpiSeries["definition"]["key"],
): string {
  switch (key) {
    case "project_sop_on_time_rate":
      return t("Project SOP on-time rate");
    case "project_cycle_time_days":
      return t("Project cycle time");
    case "trial_first_pass_rate":
      return t("Trial first-pass rate");
    case "project_cost_variance_rate":
      return t("Project cost variance rate");
  }
}

function configurationLabel(
  t: ReturnType<typeof useI18n>["t"],
  key: string,
): string {
  switch (key) {
    case "project_templates":
      return t("Project templates");
    case "gate_templates":
      return t("Gate templates");
    case "project_work_policies":
      return t("Project work policies");
    case "npi_readiness_templates":
      return t("NPI readiness templates");
    case "production_transition_policies":
      return t("Production transition policies");
    default:
      return t("Controlled configuration");
  }
}

type ActivationState =
  | "ready"
  | "action_required"
  | "disabled"
  | "enabled"
  | "configured"
  | "not_configured"
  | "external_verification_required"
  | "implementation_required";

function activationStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ActivationState,
): string {
  switch (state) {
    case "ready":
      return t("Ready");
    case "action_required":
      return t("Action required");
    case "disabled":
      return t("Disabled");
    case "enabled":
      return t("Enabled");
    case "configured":
      return t("Configured");
    case "not_configured":
      return t("Not configured");
    case "external_verification_required":
      return t("External verification required");
    case "implementation_required":
      return t("Implementation required");
  }
}

function activationStateTone(
  state: ActivationState,
): "success" | "warning" | "neutral" {
  if (state === "ready" || state === "configured") return "success";
  if (state === "enabled" || state === "disabled") return "neutral";
  return "warning";
}

function previousMonth(month: string, offset: number): string {
  const [yearValue, monthValue] = month.split("-").map(Number);
  const date = new Date(
    Date.UTC(yearValue ?? 1970, (monthValue ?? 1) - 1 - offset, 1),
  );
  return `${String(date.getUTCFullYear()).padStart(4, "0")}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

function currentMonth(): string {
  const now = new Date();
  return `${String(now.getUTCFullYear()).padStart(4, "0")}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
}

function Loading({ label }: { label: string }): React.JSX.Element {
  return (
    <section
      aria-busy="true"
      aria-label={label}
      className="state-surface state-surface--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">{label}</span>
    </section>
  );
}

function Failure({
  failure,
  retry,
}: {
  failure: RequestFailure;
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section className="state-surface" role="alert">
      <SemanticStatus label={t("Unavailable")} tone="danger" />
      <h2>{t("The reporting response could not be used safely")}</h2>
      <p>
        {t(
          "No reporting data was displayed. Retry or share the reference ID with support.",
        )}
      </p>
      <RequestFailurePanel failure={failure} />
      <Button icon="refresh" onClick={retry}>
        {t("Retry")}
      </Button>
    </section>
  );
}

function PortfolioFilters({
  value,
  onApply,
}: {
  value: Partial<ReportingFilters>;
  onApply: (value: Partial<ReportingFilters>) => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const [draft, setDraft] = useState(value);
  return (
    <form
      className="reporting-filters"
      onSubmit={(event) => {
        event.preventDefault();
        onApply(draft);
      }}
    >
      <label>
        <span>{t("Customer reference")}</span>
        <TextInput
          value={draft.customerReferenceKey ?? ""}
          onChange={(event) => {
            setDraft({
              ...draft,
              customerReferenceKey: event.currentTarget.value || null,
            });
          }}
        />
      </label>
      <label>
        <span>{t("Project manager")}</span>
        <TextInput
          inputMode="email"
          value={draft.ownerUserId ?? ""}
          onChange={(event) => {
            setDraft({
              ...draft,
              ownerUserId: event.currentTarget.value || null,
            });
          }}
        />
      </label>
      <label>
        <span>{t("Project type")}</span>
        <Select
          value={draft.projectType ?? ""}
          onChange={(event) => {
            setDraft({
              ...draft,
              projectType: (event.currentTarget.value ||
                null) as PortfolioProjectType | null,
            });
          }}
        >
          <option value="">{t("All")}</option>
          <option value="customer_owned_tool">
            {t("Customer-owned tool")}
          </option>
          <option value="new_tool">{t("New tool")}</option>
          <option value="tool_change">{t("Tool change")}</option>
        </Select>
      </label>
      <label>
        <span>{t("Factory reference")}</span>
        <TextInput
          value={draft.factoryReferenceKey ?? ""}
          onChange={(event) => {
            setDraft({
              ...draft,
              factoryReferenceKey: event.currentTarget.value || null,
            });
          }}
        />
      </label>
      <label>
        <span>{t("SOP month")}</span>
        <TextInput
          placeholder={t("Year and month")}
          value={draft.sopMonth ?? ""}
          onChange={(event) => {
            setDraft({
              ...draft,
              sopMonth: event.currentTarget.value || null,
            });
          }}
        />
      </label>
      <label>
        <span>{t("Lifecycle")}</span>
        <Select
          value={draft.lifecycleState ?? ""}
          onChange={(event) => {
            setDraft({
              ...draft,
              lifecycleState: (event.currentTarget.value ||
                null) as PortfolioLifecycleState | null,
            });
          }}
        >
          <option value="">{t("All")}</option>
          <option value="draft">{t("Draft")}</option>
          <option value="proposed">{t("Proposed")}</option>
          <option value="active">{t("Active")}</option>
          <option value="on_hold">{t("On hold")}</option>
          <option value="completed">{t("Completed")}</option>
          <option value="cancelled">{t("Cancelled")}</option>
        </Select>
      </label>
      <div className="reporting-filters__actions">
        <Button
          className="reporting-filters__apply"
          icon="filter"
          type="submit"
          visual="primary"
        >
          {t("Apply filters")}
        </Button>
        <Button
          type="button"
          onClick={() => {
            setDraft({});
            onApply({});
          }}
        >
          {t("Clear")}
        </Button>
      </div>
    </form>
  );
}

function PortfolioTable({
  response,
  navigate,
}: {
  response: ProjectPortfolioResponse;
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (!response.items.length)
    return (
      <div className="table-empty">{t("No Projects match these filters.")}</div>
    );
  return (
    <div className="engineering-table reporting-table">
      <table className="data-table data-table--compact">
        <thead>
          <tr>
            <th>{t("Project")}</th>
            <th>{t("Type and owner")}</th>
            <th>{t("Target SOP")}</th>
            <th>{t("Current Gate")}</th>
            <th>{t("Active work")}</th>
            <th>{t("Health")}</th>
            <th>{t("ERPNext truth")}</th>
          </tr>
        </thead>
        <tbody>
          {response.items.map((item) => (
            <tr key={item.globalId}>
              <td>
                <Button
                  visual="ghost"
                  onClick={() => {
                    navigate(item.detailRoute);
                  }}
                >
                  <span data-language-exempt="identifier">
                    {item.businessCode}
                  </span>{" "}
                  ·{" "}
                  <span data-language-exempt="business-data">{item.title}</span>
                </Button>
                <small className="reporting-table__secondary">
                  {lifecycleLabel(t, item.lifecycleState)} ·{" "}
                  {t("Version {{version}}", { version: item.version })}
                </small>
              </td>
              <td>
                {projectTypeLabel(t, item.projectType)}
                <small
                  className="reporting-table__secondary"
                  data-language-exempt="business-data"
                >
                  {item.ownerUserId}
                </small>
              </td>
              <td>
                <time dateTime={item.targetSop}>
                  {formatDate(locale, item.targetSop)}
                </time>
              </td>
              <td>
                {item.currentGate ? (
                  <>
                    <strong data-language-exempt="identifier">
                      {item.currentGate.key}
                    </strong>
                    <small className="reporting-table__secondary">
                      {gateStateLabel(t, item.currentGate.reviewState)}
                    </small>
                  </>
                ) : (
                  <span>{t("Not assigned")}</span>
                )}
              </td>
              <td>
                {formatNumber(locale, item.work.activeCount, 0)}
                <small className="reporting-table__secondary">
                  {t("{{overdue}} overdue · {{blockers}} blockers", {
                    overdue: item.work.overdueCount,
                    blockers: item.work.blockerCount,
                  })}
                </small>
              </td>
              <td>
                <SemanticStatus
                  label={healthLabel(t, item.health.state)}
                  tone={
                    item.health.state === "green"
                      ? "success"
                      : item.health.state === "yellow"
                        ? "warning"
                        : item.health.state === "red"
                          ? "danger"
                          : "neutral"
                  }
                />
              </td>
              <td>
                <span className="reporting-table__truth">
                  <SourceSystemIdentity sourceSystem="ERPNEXT" />
                  <SemanticStatus
                    label={availabilityLabel(t, item.erp.availability)}
                    tone={availabilityTone(item.erp.availability)}
                  />
                </span>
                {item.erp.freshestAt ? (
                  <small className="reporting-table__secondary">
                    {formatDateTime(locale, item.erp.freshestAt)}
                  </small>
                ) : (
                  <small className="reporting-table__secondary">
                    {t("No observation")}
                  </small>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function KpiTable({
  response,
}: {
  response: KpiTrendResponse;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  return (
    <div className="engineering-table reporting-table">
      <table className="data-table data-table--compact">
        <thead>
          <tr>
            <th>{t("KPI")}</th>
            <th>{t("Availability")}</th>
            <th>{t("Source")}</th>
            <th>{t("Latest value")}</th>
            <th>{t("Definition")}</th>
          </tr>
        </thead>
        <tbody>
          {response.series.map((series) => {
            const point = series.points.at(-1);
            const value = point
              ? formatNumber(
                  locale,
                  point.value,
                  series.definition.valueKind === "percent" ? 1 : 0,
                )
              : "—";
            return (
              <tr key={series.definition.key}>
                <td>{kpiLabel(t, series.definition.key)}</td>
                <td>
                  <SemanticStatus
                    label={availabilityLabel(t, series.availability)}
                    tone={availabilityTone(series.availability)}
                  />
                </td>
                <td>
                  <SourceSystemIdentity
                    sourceSystem={
                      series.definition.sourceSystem === "MIXED"
                        ? "COMPUTED"
                        : "NPI_ONE"
                    }
                  />
                </td>
                <td>
                  {value}
                  {point && series.definition.valueKind === "percent"
                    ? "%"
                    : null}
                  <small className="reporting-table__secondary">
                    {point?.month ?? t("No verified point")}
                  </small>
                </td>
                <td>
                  <small className="reporting-table__secondary">
                    {t("Numerator")}:{" "}
                    <span data-language-exempt="identifier">
                      {series.definition.numeratorSource}
                    </span>
                  </small>
                  <small className="reporting-table__secondary">
                    {t("Denominator")}:{" "}
                    <span data-language-exempt="identifier">
                      {series.definition.denominatorSource}
                    </span>
                  </small>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ConfigurationTable({
  response,
}: {
  response: ConfigurationCapabilityCatalog;
}): React.JSX.Element {
  const { sessionCommandContext, t } = useI18n();
  const deploymentEnvironment = sessionCommandContext?.deploymentEnvironment;
  const activation = response.activation;
  const activationRows: readonly {
    key: string;
    capability: string;
    authority: string;
    state: ActivationState;
    action: React.ReactNode;
  }[] = [
    {
      key: "entra-login",
      capability: t("Sign-in and MFA"),
      authority: t("Microsoft Entra"),
      state: activation.entraLoginState,
      action:
        activation.entraLoginState === "ready"
          ? t("No change")
          : t("Configure Microsoft Entra sign-in on this LaunchFlow Site."),
    },
    {
      key: "self-signup",
      capability: t("Self signup"),
      authority: t("Frappe"),
      state: activation.selfSignupState,
      action:
        activation.selfSignupState === "disabled"
          ? t("No change")
          : t("Disable self signup for every enabled login provider."),
    },
    {
      key: "user-authority",
      capability: t("User, role and scope management"),
      authority: t("JCE Core"),
      state: "external_verification_required",
      action: t(
        "Manage enabled users, NPI roles and approved scopes in JCE Core.",
      ),
    },
    {
      key: "authorization-ingress",
      capability: t("Authorization projection ingress"),
      authority: t("LaunchFlow"),
      state: activation.authorizationIngressState,
      action:
        activation.authorizationIngressState === "disabled"
          ? t("Keep disabled until the ERPNext sender and Sandbox tests pass.")
          : t(
              "Verify ERPNext sender and Sandbox evidence before production use.",
            ),
    },
    {
      key: "authorization-enforcement",
      capability: t("Authorization projection enforcement"),
      authority: t("LaunchFlow"),
      state: activation.authorizationEnforcementState,
      action:
        activation.authorizationEnforcementState === "disabled"
          ? t("Keep disabled until the ERPNext sender and Sandbox tests pass.")
          : t(
              "Verify ERPNext sender and Sandbox evidence before production use.",
            ),
    },
    {
      key: "authorization-policy",
      capability: t("Authorization projection policy"),
      authority: t("LaunchFlow"),
      state: activation.authorizationPolicyState,
      action:
        activation.authorizationPolicyState === "configured"
          ? t("No change")
          : t(
              "Configure the exact role allowlist and projection validity window.",
            ),
    },
    {
      key: "erp-authorization-sender",
      capability: t("ERPNext authorization sender"),
      authority: t("JCE Core"),
      state: activation.erpAuthorizationSenderState,
      action: t("Implement and verify the operation-specific ERPNext sender."),
    },
    {
      key: "local-user-provisioning",
      capability: t("LaunchFlow user provisioning"),
      authority: t("JCE Core"),
      state: activation.localUserProvisioningState,
      action: t("No change"),
    },
    {
      key: "erp-business-adapters",
      capability: t("ERPNext business adapters"),
      authority: t("LaunchFlow"),
      state: activation.erpBusinessAdaptersState,
      action: t(
        "Implement and verify each operation-specific ERPNext business adapter.",
      ),
    },
    {
      key: "support-administration",
      capability: t("Local support administration"),
      authority: t("Frappe"),
      state: "ready",
      action: (
        <a className="table-link" href={activation.supportAdministrationPath}>
          {t("Open Frappe administration")}
        </a>
      ),
    },
  ];
  return (
    <>
      <div className="scenario-banner scenario-banner--read_only" role="status">
        <SemanticStatus label={t("Read only")} tone="info" />
        <span>
          {t(
            "Configuration remains operation-specific. A generic field or DocType writer is not available.",
          )}
        </span>
      </div>
      <section aria-labelledby="production-activation-readiness-title">
        <h2 id="production-activation-readiness-title">
          {t("Production activation readiness")}
        </h2>
        <p>
          {t(
            "Only server-observed, non-secret configuration is shown. User and permission ownership is not duplicated in LaunchFlow.",
          )}
        </p>
        <div className="engineering-table reporting-table">
          <table className="data-table data-table--compact">
            <thead>
              <tr>
                <th>{t("Capability")}</th>
                <th>{t("System of authority")}</th>
                <th>{t("Current state")}</th>
                <th>{t("Required action")}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{t("LaunchFlow Site environment")}</td>
                <td>{t("LaunchFlow")}</td>
                <td>
                  <SemanticStatus
                    label={
                      deploymentEnvironment === "production"
                        ? t("Production environment")
                        : deploymentEnvironment === "sandbox"
                          ? t("Sandbox environment")
                          : t("Deployment environment not confirmed")
                    }
                    tone={
                      deploymentEnvironment === "production"
                        ? "success"
                        : "warning"
                    }
                  />
                </td>
                <td>
                  {deploymentEnvironment === "production"
                    ? t("No change")
                    : t(
                        "Set the exact LaunchFlow Site environment before go-live.",
                      )}
                </td>
              </tr>
              {activationRows.map((item) => (
                <tr key={item.key}>
                  <td>{item.capability}</td>
                  <td>{item.authority}</td>
                  <td>
                    <SemanticStatus
                      label={activationStateLabel(t, item.state)}
                      tone={activationStateTone(item.state)}
                    />
                  </td>
                  <td>{item.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <h2>{t("Controlled configuration")}</h2>
      <div className="engineering-table reporting-table">
        <table className="data-table data-table--compact">
          <thead>
            <tr>
              <th>{t("Capability")}</th>
              <th>{t("Control mode")}</th>
              <th>{t("Authorized workspace")}</th>
            </tr>
          </thead>
          <tbody>
            {response.items.map((item) => (
              <tr key={item.key}>
                <td>
                  {configurationLabel(t, item.key)}
                  <small
                    className="reporting-table__secondary"
                    data-language-exempt="identifier"
                  >
                    {item.key}
                  </small>
                </td>
                <td>
                  {item.mode === "versioned_commands"
                    ? t("Versioned commands")
                    : t("Operation-specific command")}
                </td>
                <td>{t("Available through its governed command workspace")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function PortfolioPage({
  dataSource,
  navigate,
  view,
}: {
  dataSource: ReportingDataSource;
  navigate: (target: string) => void;
  view: ReportingView;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [filters, setFilters] =
    useState<Partial<ReportingFilters>>(emptyFilters);
  const month = useMemo(() => currentMonth(), []);
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const [state, setState] = useState<
    ResourceState<
      | ProjectPortfolioResponse
      | KpiTrendResponse
      | ConfigurationCapabilityCatalog
    >
  >({ kind: "loading" });
  const retry = useCallback(() => {
    setState({ kind: "loading" });
    setAttempt((value) => value + 1);
  }, []);
  useEffect(() => {
    const refresh = (): void => {
      retry();
    };
    globalThis.addEventListener("npi:refresh-reporting", refresh);
    return () => {
      globalThis.removeEventListener("npi:refresh-reporting", refresh);
    };
  }, [retry]);
  useEffect(() => {
    const controller = new AbortController();
    const current = generation.current + 1;
    generation.current = current;
    const request =
      view === "portfolio"
        ? dataSource.loadPortfolio(filters, { limit: 50 }, controller.signal)
        : view === "kpis"
          ? dataSource.loadKpis(
              previousMonth(month, 5),
              month,
              filters,
              controller.signal,
            )
          : dataSource.loadConfiguration(controller.signal);
    void request
      .then((value) => {
        if (!controller.signal.aborted && generation.current === current)
          setState({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && generation.current === current)
          setState({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, filters, month, view]);
  const title =
    view === "portfolio"
      ? t("Project Portfolio")
      : view === "kpis"
        ? t("KPI reporting")
        : t("Administration capabilities");
  return (
    <article className="page page--reporting">
      <header className="page-heading">
        <div>
          <h1>{title}</h1>
          <p>
            {view === "portfolio"
              ? t(
                  "Permission-filtered cross-project status with NPI One and ERPNext truth kept separate.",
                )
              : view === "kpis"
                ? t(
                    "Fixed KPI definitions expose unavailable data instead of fabricated trends.",
                  )
                : t(
                    "Read-only inventory of versioned, operation-specific configuration surfaces.",
                  )}
          </p>
        </div>
        {state.kind === "loaded" && view !== "configuration" ? (
          <small>
            {view === "portfolio" && "asOf" in state.value
              ? t("As of {{time}}", {
                  time: formatDateTime(locale, state.value.asOf),
                })
              : "visibleProjectCount" in state.value
                ? t("{{count}} visible Projects", {
                    count: state.value.visibleProjectCount,
                  })
                : null}
          </small>
        ) : null}
      </header>
      <nav
        aria-label={t("Reporting workspaces")}
        className="rectangular-tabs reporting-tabs"
      >
        <Button
          className="reporting-tabs__button"
          aria-current={view === "portfolio" ? "page" : undefined}
          onClick={() => {
            navigate("/portfolio");
          }}
        >
          {t("Portfolio")}
        </Button>
        <Button
          className="reporting-tabs__button"
          aria-current={view === "kpis" ? "page" : undefined}
          onClick={() => {
            navigate("/reports");
          }}
        >
          {t("KPI trends")}
        </Button>
        <Button
          className="reporting-tabs__button"
          aria-current={view === "configuration" ? "page" : undefined}
          onClick={() => {
            navigate("/administration");
          }}
        >
          {t("Administration")}
        </Button>
      </nav>
      {view !== "configuration" ? (
        <PortfolioFilters value={filters} onApply={setFilters} />
      ) : null}
      <Panel title={title} scrollableBody>
        {state.kind === "loading" ? (
          <Loading label={t("Loading reporting workspace")} />
        ) : state.kind === "failed" ? (
          <Failure failure={state.failure} retry={retry} />
        ) : view === "portfolio" && "asOf" in state.value ? (
          <PortfolioTable response={state.value} navigate={navigate} />
        ) : view === "kpis" && "series" in state.value ? (
          <KpiTable response={state.value} />
        ) : "genericWriterAvailable" in state.value ? (
          <ConfigurationTable response={state.value} />
        ) : (
          <Failure
            failure={{
              kind: "invalid_response",
              referenceId: `client-${globalThis.crypto.randomUUID()}`,
              referenceKind: "client",
            }}
            retry={retry}
          />
        )}
      </Panel>
    </article>
  );
}
