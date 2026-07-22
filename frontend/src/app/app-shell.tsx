import { useState, type PropsWithChildren } from "react";

import type { AppRoute } from "./router";
import { scenarioLabel } from "../i18n/copy";
import { supportedLocales, useI18n, type Locale } from "../i18n/runtime";
import { scenarios } from "../fixtures/prototype";
import {
  Button,
  focusControl,
  Icon,
  Select,
  TextInput,
} from "../ui-adapters/npi-ui";
import { RequestFailurePanel } from "../components/problem-details-panel";

interface NavigationItem {
  id: string;
  label: string;
  path?: string;
  screen?: AppRoute["screen"];
}

const prototypeSearchTargets: Readonly<Record<string, string>> = {
  "PJ-26018": "/projects/PJ-26018",
  "TL-26018-01": "/tooling/TL-26018-01",
  T1: "/trials/T1",
};

function localeLabel(
  locale: Locale,
  t: ReturnType<typeof useI18n>["t"],
): string {
  if (locale === "zh") return t("Simplified Chinese");
  if (locale === "zh-TW") return t("Traditional Chinese");
  return t("English");
}

export function AppShell({
  route,
  navigate,
  children,
}: PropsWithChildren<{
  route: AppRoute;
  navigate: (target: string) => void;
}>): React.JSX.Element {
  const {
    locale,
    setLocale,
    t,
    isPrototypeFallback,
    isLocalizationUnavailable,
    isLocalizationPending,
    localizationFailure,
    retryLocalization,
    catalogVersion,
  } = useI18n();
  const [utilityMessage, setUtilityMessage] = useState<string | null>(null);
  const denied = route.scenario === "no_permission";
  const routeContext = denied
    ? { exempt: false, value: t("Protected object") }
    : route.screen === "work"
      ? { exempt: false, value: t("Cross-object work queue") }
      : route.screen === "project"
        ? { exempt: true, value: "PJ-26018" }
        : route.screen === "gate"
          ? {
              exempt: true,
              value: `${route.qualityFailure ? "G6" : "G5"} · PJ-26018`,
            }
          : route.screen === "tooling"
            ? { exempt: true, value: "PJ-26018 · TL-26018-01" }
            : route.screen === "trial"
              ? { exempt: true, value: "TL-26018-01 · T1" }
              : { exempt: false, value: t("Cross-system operations") };
  const breadcrumbRoot =
    route.screen === "tooling"
      ? t("Tooling")
      : route.screen === "trial"
        ? t("Trial and NPI")
        : route.screen === "execution"
          ? t("Execution and Reconciliation")
          : t("Engineering projects");
  const breadcrumbCurrent = denied
    ? { exempt: false, value: t("Protected object") }
    : route.screen === "work"
      ? { exempt: false, value: t("My Work") }
      : routeContext;
  const navigation: NavigationItem[] = [
    { id: "work", label: t("My Work"), path: "/work", screen: "work" },
    {
      id: "portfolio",
      label: t("Project Portfolio"),
      path: "/projects/PJ-26018",
    },
    {
      id: "project",
      label: t("Project"),
      path: "/projects/PJ-26018",
      screen: "project",
    },
    {
      id: "tooling",
      label: t("Tooling"),
      path: "/tooling/TL-26018-01",
      screen: "tooling",
    },
    { id: "design", label: t("Design and Baselines") },
    {
      id: "trial",
      label: t("Trial and NPI"),
      path: "/trials/T1",
      screen: "trial",
    },
    { id: "changes", label: t("Changes") },
    {
      id: "execution",
      label: t("Execution and Reconciliation"),
      path: "/execution",
      screen: "execution",
    },
    { id: "analytics", label: t("Analytics") },
    { id: "administration", label: t("Administration") },
  ];
  const updateScenario = (scenario: string): void => {
    const url = new URL(globalThis.location.href);
    if (scenario === "normal") url.searchParams.delete("scenario");
    else url.searchParams.set("scenario", scenario);
    navigate(`${url.pathname}${url.search}`);
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <button
          className="app-header__brand"
          onClick={() => {
            navigate("/work");
          }}
          type="button"
        >
          {t("NPI One")}
        </button>
        <span
          className="app-header__context"
          data-language-exempt={routeContext.exempt ? "identifier" : undefined}
        >
          {routeContext.value}
        </span>
        <label className="global-search">
          <span className="visually-hidden">{t("Global search")}</span>
          <Icon name="search" />
          <TextInput
            aria-label={t("Global search")}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              const query = event.currentTarget.value.trim().toUpperCase();
              const target = prototypeSearchTargets[query];
              if (target) {
                setUtilityMessage(null);
                navigate(target);
                return;
              }
              setUtilityMessage(
                t("No prototype search result matched this query."),
              );
            }}
            placeholder={t("Search projects, tools, trials, and drawings")}
            type="search"
          />
        </label>
        <Button
          aria-label={t("Notifications")}
          icon="alarm"
          onClick={() => {
            setUtilityMessage(
              t(
                "No prototype notification feed is connected. Use My Work for assigned actions.",
              ),
            );
          }}
          visual="ghost"
        >
          {t("{{count}} notifications", { count: 0 })}
        </Button>
        <Button
          aria-label={t("Help")}
          icon="help"
          onClick={() => {
            setUtilityMessage(
              t(
                "Select an object to see its source, sync state, and next safe action.",
              ),
            );
          }}
          visual="ghost"
        >
          {t("Help")}
        </Button>
        <Button
          aria-label={t("Current user")}
          icon="user"
          onClick={() => {
            setUtilityMessage(
              t("Signed in for the test environment with prototype data."),
            );
          }}
          visual="ghost"
        >
          <span data-language-exempt="business-data">Alex Chen</span>
        </Button>
      </header>
      <aside className="domain-navigation">
        <nav aria-label={t("Domain navigation")}>
          <ul>
            {navigation.map((item) => (
              <li key={item.id}>
                {item.path ? (
                  <button
                    aria-current={
                      route.screen === item.screen ? "page" : undefined
                    }
                    className={
                      route.screen === item.screen ? "is-active" : undefined
                    }
                    onClick={() => {
                      if (item.path) navigate(item.path);
                    }}
                    type="button"
                  >
                    {item.label}
                  </button>
                ) : (
                  <span
                    aria-disabled="true"
                    title={t("Available in a later phase")}
                  >
                    {item.label}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </nav>
        <div className="environment-marker">
          <strong>{t("Test environment")}</strong>
          <span>{t("Prototype data")}</span>
        </div>
      </aside>
      <div className="page-frame">
        <div className="page-toolbar">
          <div className="breadcrumbs" aria-label={t("Breadcrumb")}>
            <span>{breadcrumbRoot}</span>
            <span aria-hidden="true">/</span>
            <strong
              data-language-exempt={
                breadcrumbCurrent.exempt ? "identifier" : undefined
              }
            >
              {breadcrumbCurrent.value}
            </strong>
          </div>
          <div className="page-toolbar__actions">
            <Button
              icon="filter"
              onClick={() => {
                const control = document.querySelector<HTMLElement>(
                  ".table-tools select, .table-tools input",
                );
                if (control) {
                  void focusControl(control);
                  setUtilityMessage(
                    t("Worklist filters and column controls are focused."),
                  );
                  return;
                }
                setUtilityMessage(
                  t("This workspace has no configurable table columns."),
                );
              }}
            >
              {t("Filters and columns")}
            </Button>
            <Button
              icon="refresh"
              onClick={() => {
                setUtilityMessage(
                  t(
                    "Prototype refresh is unavailable because this view uses fixed in-memory data.",
                  ),
                );
              }}
            >
              {t("Refresh")}
            </Button>
          </div>
        </div>
        <div className="page-messages">
          {utilityMessage ? (
            <div className="utility-message" role="status">
              <Icon name="info" />
              <span>{utilityMessage}</span>
            </div>
          ) : null}
          <div
            className={`prototype-banner${isLocalizationUnavailable ? " prototype-banner--error" : ""}`}
            aria-busy={isLocalizationPending}
            role="status"
          >
            <Icon name="info" />
            <strong>
              {t("Prototype data - no production system is connected.")}
            </strong>
            {localizationFailure ? (
              <div className="localization-failure">
                <p>
                  {localizationFailure.operation === "bootstrap"
                    ? t("The session language and catalog could not be loaded.")
                    : t("The language change could not be confirmed.")}
                </p>
                <p>
                  {t(
                    "This screen kept its previous language and catalog. Retry to reconcile with the session, or share the reference ID with support.",
                  )}
                </p>
                <RequestFailurePanel
                  failure={localizationFailure.requestFailure}
                />
                <Button
                  disabled={isLocalizationPending}
                  icon="refresh"
                  onClick={retryLocalization}
                >
                  {t("Retry")}
                </Button>
              </div>
            ) : (
              <span>
                {isLocalizationUnavailable
                  ? t("Localization resources are unavailable.")
                  : isPrototypeFallback
                    ? t(
                        "Language persistence uses the prototype fallback because no Frappe Site is active.",
                      )
                    : t("Language is managed by the Frappe session.")}
              </span>
            )}
          </div>
        </div>
        <main id="main-content">{children}</main>
        <footer className="status-bar">
          <span>{t("Test environment")}</span>
          <span>
            {t("Catalog")}:{" "}
            <code data-language-exempt="identifier">{catalogVersion}</code>
          </span>
          <span>
            {t("Time zone")}: <span data-language-exempt="identifier">UTC</span>
          </span>
          <label>
            <span>{t("Language")}</span>
            <Select
              aria-label={t("Language")}
              disabled={isLocalizationUnavailable || isLocalizationPending}
              onChange={(event) => {
                setLocale(event.currentTarget.value as Locale);
              }}
              value={locale}
            >
              {supportedLocales.map((supportedLocale) => (
                <option key={supportedLocale} value={supportedLocale}>
                  {localeLabel(supportedLocale, t)}
                </option>
              ))}
            </Select>
          </label>
          <label>
            <span>{t("Fixture state")}</span>
            <Select
              aria-label={t("Fixture state")}
              onChange={(event) => {
                updateScenario(event.currentTarget.value);
              }}
              value={route.scenario}
            >
              {scenarios.map((scenario) => (
                <option key={scenario} value={scenario}>
                  {scenarioLabel(t, scenario)}
                </option>
              ))}
            </Select>
          </label>
        </footer>
      </div>
    </div>
  );
}
