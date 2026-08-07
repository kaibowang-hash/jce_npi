import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
import { createPortal } from "react-dom";

import { CommandPalette, type ShellCommand } from "./command-palette";
import {
  buildContextualNavigationTarget,
  currentReturnTarget,
  type AppRoute,
} from "./router";
import {
  ProjectControlsRequestCancelledError,
  type ProjectControlsDataSource,
} from "../api/project-controls-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { scenarioLabel } from "../i18n/copy";
import { supportedLocales, useI18n, type Locale } from "../i18n/runtime";
import { scenarios } from "../fixtures/prototype";
import {
  Button,
  focusControl,
  Icon,
  Select,
  TextInput,
  type NpiIconName,
} from "../ui-adapters/npi-ui";
import {
  DisplayBrandCompanyMark,
  DisplayBrandPlatformIcon,
  DisplayBrandWordmark,
} from "../ui-adapters/display-brand";
import { RequestFailurePanel } from "../components/problem-details-panel";

interface NavigationItem {
  id: string;
  label: string;
  icon: NpiIconName;
  path?: string;
  screen?: AppRoute["screen"];
  unavailableReason?: string;
}

interface NavigationTooltipState {
  id: string;
  label: string;
  left: number;
  maxWidth: number;
  reason: string | undefined;
  top: number;
}

type QuickCreateState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "available"; projectId: string }
  | { kind: "unavailable"; reason: string }
  | { kind: "failed"; failure: RequestFailure };

const prototypeSearchTargets: Readonly<Record<string, string>> = {
  "PJ-26018": "/demo/projects/PJ-26018",
  "TL-26018-01": "/tooling/TL-26018-01",
  T1: "/trials/T1",
};

function optionalMatchMedia(query: string): MediaQueryList | null {
  const matchMedia = (
    globalThis as unknown as {
      matchMedia?: ((mediaQuery: string) => MediaQueryList) | undefined;
    }
  ).matchMedia;
  return matchMedia?.(query) ?? null;
}

function useResponsiveNavigationCollapsed(): boolean {
  const query = "(max-width: 720px)";
  const [collapsed, setCollapsed] = useState(
    () => optionalMatchMedia(query)?.matches ?? false,
  );
  useEffect(() => {
    const media = optionalMatchMedia(query);
    if (!media) return undefined;
    const update = (): void => {
      setCollapsed(media.matches);
    };
    update();
    media.addEventListener("change", update);
    return () => {
      media.removeEventListener("change", update);
    };
  }, []);
  return collapsed;
}

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
  projectControlsDataSource,
  children,
}: PropsWithChildren<{
  route: AppRoute;
  navigate: (target: string) => void;
  projectControlsDataSource?: ProjectControlsDataSource | undefined;
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
    navigationCollapsed,
    isNavigationPreferencePending,
    navigationPreferenceFailure,
    retryNavigationPreference,
    sessionCommandContext,
    setNavigationCollapsed,
  } = useI18n();
  const [utilityMessage, setUtilityMessage] = useState<string | null>(null);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [navigationTooltip, setNavigationTooltip] =
    useState<NavigationTooltipState | null>(null);
  const [quickCreateOpen, setQuickCreateOpen] = useState(false);
  const [quickCreateState, setQuickCreateState] = useState<QuickCreateState>({
    kind: "idle",
  });
  const quickCreateRequest = useRef<AbortController | null>(null);
  const responsiveNavigationCollapsed = useResponsiveNavigationCollapsed();
  const effectiveNavigationCollapsed =
    navigationCollapsed || responsiveNavigationCollapsed;
  const isLiveProject =
    route.screen === "project" && route.projectMode === "live";
  const isLiveGate = route.screen === "gate" && route.gateMode === "live";
  const isLiveTooling =
    route.screen === "tooling" && route.toolingMode === "live";
  const isLiveWork = route.screen === "work" && route.workMode === "live";
  const isLiveProjectContext = isLiveProject || isLiveGate || isLiveTooling;
  const isLiveDataContext = isLiveWork || isLiveProjectContext;
  const prototypeNavigationAllowed = !isLiveDataContext;
  const liveProjectPath =
    route.projectGlobalId === null
      ? null
      : `/projects/${route.projectGlobalId}`;
  const liveToolingPath = liveProjectPath ? `${liveProjectPath}/tooling` : null;
  const denied = route.scenario === "no_permission";
  const routeContext = denied
    ? { exempt: false, value: t("Protected object") }
    : route.screen === "work"
      ? { exempt: false, value: t("Cross-object work queue") }
      : route.screen === "project"
        ? {
            exempt:
              route.projectMode === "demo" || route.projectGlobalId !== null,
            value:
              route.projectMode === "demo"
                ? "PJ-26018"
                : (route.projectGlobalId ?? t("Project")),
          }
        : route.screen === "gate"
          ? {
              exempt: true,
              value: isLiveGate
                ? `${route.gateGlobalId ?? ""} · ${route.projectGlobalId ?? ""}`
                : `${route.qualityFailure ? "G6" : "G5"} · PJ-26018`,
            }
          : route.screen === "tooling"
            ? {
                exempt: true,
                value: isLiveTooling
                  ? `${route.projectGlobalId ?? ""}${
                      route.toolingMasterGlobalId
                        ? ` · ${route.toolingMasterGlobalId}`
                        : ""
                    }`
                  : "PJ-26018 · TL-26018-01",
              }
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
  const liveNavigationUnavailable = t(
    "Prototype navigation is unavailable from live data. Open an authorized link instead.",
  );
  const navigation: NavigationItem[] = [
    {
      id: "work",
      icon: "work",
      label: t("My Work"),
      path: "/work",
      screen: "work",
    },
    {
      id: "portfolio",
      icon: "projects",
      label: t("Project Portfolio"),
      ...(prototypeNavigationAllowed
        ? { path: "/demo/projects/PJ-26018" }
        : { unavailableReason: liveNavigationUnavailable }),
    },
    {
      id: "project",
      icon: "project",
      label: t("Project"),
      ...(isLiveProjectContext && liveProjectPath
        ? { path: liveProjectPath }
        : prototypeNavigationAllowed
          ? { path: "/demo/projects/PJ-26018" }
          : {}),
      screen: "project",
      ...(!isLiveProjectContext && !prototypeNavigationAllowed
        ? { unavailableReason: t("Open a Project from an authorized link.") }
        : {}),
    },
    {
      id: "tooling",
      icon: "maintenance",
      label: t("Tooling"),
      ...(isLiveProjectContext && liveToolingPath
        ? { path: liveToolingPath }
        : prototypeNavigationAllowed
          ? { path: "/tooling/TL-26018-01" }
          : { unavailableReason: liveNavigationUnavailable }),
      screen: "tooling",
    },
    {
      id: "design",
      icon: "document",
      label: t("Design and Baselines"),
      unavailableReason: t("Available in a later phase"),
    },
    {
      id: "trial",
      icon: "play",
      label: t("Trial and NPI"),
      ...(prototypeNavigationAllowed
        ? { path: "/trials/T1" }
        : { unavailableReason: liveNavigationUnavailable }),
      screen: "trial",
    },
    {
      id: "changes",
      icon: "history",
      label: t("Changes"),
      unavailableReason: t("Available in a later phase"),
    },
    {
      id: "execution",
      icon: "apps",
      label: t("Execution and Reconciliation"),
      ...(prototypeNavigationAllowed
        ? { path: "/execution" }
        : { unavailableReason: liveNavigationUnavailable }),
      screen: "execution",
    },
    {
      id: "analytics",
      icon: "analysis",
      label: t("Analytics"),
      unavailableReason: t("Available in a later phase"),
    },
    {
      id: "administration",
      icon: "user",
      label: t("Administration"),
      unavailableReason: t("Available in a later phase"),
    },
  ];
  const commands = useMemo<readonly ShellCommand[]>(
    () => [
      {
        id: "my-work",
        label: t("Open My Work"),
        description: t("Open the authorized cross-object work queue."),
        icon: "work",
        keywords: [t("Work"), t("Actions"), t("Approvals")],
        target: "/work",
      },
      {
        id: "project",
        label: isLiveProjectContext
          ? t("Open current Project")
          : t("Open Project prototype"),
        description: isLiveProjectContext
          ? t("Return to the current authorized Project cockpit.")
          : t("Open the governed Project prototype workspace."),
        icon: "project",
        keywords: [t("Project"), t("Cockpit")],
        ...(isLiveProjectContext && liveProjectPath
          ? { target: liveProjectPath }
          : prototypeNavigationAllowed
            ? { target: "/demo/projects/PJ-26018" }
            : {
                unavailableReason: t("Open a Project from an authorized link."),
              }),
      },
      {
        id: "part",
        label: t("Open Part"),
        description: t("Open a Part workspace."),
        icon: "document",
        keywords: [t("Part"), t("Drawing")],
        unavailableReason: t(
          "Part navigation is unavailable because no approved Part route exists.",
        ),
      },
      {
        id: "tooling",
        label: isLiveProjectContext
          ? t("Open Project Tooling")
          : t("Open Tooling prototype"),
        description: isLiveProjectContext
          ? t("Open the authorized live Tooling workspace for this Project.")
          : t("Open the existing Tooling prototype workspace."),
        icon: "maintenance",
        keywords: [t("Tooling"), t("Mould")],
        ...(isLiveProjectContext && liveToolingPath
          ? { target: liveToolingPath }
          : prototypeNavigationAllowed
            ? { target: "/tooling/TL-26018-01" }
            : { unavailableReason: liveNavigationUnavailable }),
      },
      {
        id: "trial",
        label: t("Open Trial prototype"),
        description: t("Open the existing Trial prototype workspace."),
        icon: "play",
        keywords: [t("Trial"), t("NPI")],
        ...(prototypeNavigationAllowed
          ? { target: "/trials/T1" }
          : { unavailableReason: liveNavigationUnavailable }),
      },
      {
        id: "execution",
        label: t("Open Execution prototype"),
        description: t(
          "Open the existing execution and reconciliation prototype.",
        ),
        icon: "apps",
        keywords: [t("Execution"), t("Reconciliation")],
        ...(prototypeNavigationAllowed
          ? { target: "/execution" }
          : { unavailableReason: liveNavigationUnavailable }),
      },
    ],
    [
      isLiveProjectContext,
      liveNavigationUnavailable,
      liveProjectPath,
      liveToolingPath,
      prototypeNavigationAllowed,
      t,
    ],
  );
  const returnTarget = currentReturnTarget();
  const hideNavigationTooltip = useCallback((): void => {
    setNavigationTooltip(null);
  }, []);
  const commandPaletteReturnFocusTarget = useCallback(
    (): HTMLElement | null =>
      document.getElementById("command-palette-trigger") ??
      document.getElementById("main-content"),
    [],
  );
  const openCommandPalette = useCallback((): void => {
    quickCreateRequest.current?.abort();
    setQuickCreateOpen(false);
    setCommandPaletteOpen(true);
  }, []);
  const restoreQuickCreateTriggerFocus = useCallback((): void => {
    queueMicrotask(() => {
      void focusControl(document.getElementById("quick-create-trigger"));
    });
  }, []);
  const showNavigationTooltip = useCallback(
    (target: HTMLElement, id: string, label: string, reason?: string): void => {
      if (!effectiveNavigationCollapsed) return;
      const bounds = target.getBoundingClientRect();
      const edgeGap = 8;
      const maximumWidth = 280;
      const minimumWidth = 160;
      const estimatedMaximumHeight = 112;
      setNavigationTooltip({
        id,
        label,
        left: bounds.right + edgeGap,
        maxWidth: Math.min(
          maximumWidth,
          Math.max(
            minimumWidth,
            globalThis.innerWidth - bounds.right - edgeGap * 2,
          ),
        ),
        reason,
        top: Math.max(
          edgeGap,
          Math.min(
            bounds.top,
            globalThis.innerHeight - estimatedMaximumHeight - edgeGap,
          ),
        ),
      });
    },
    [effectiveNavigationCollapsed],
  );

  const checkQuickCreate = useCallback((): void => {
    quickCreateRequest.current?.abort();
    if (
      !isLiveProjectContext ||
      !route.projectGlobalId ||
      !projectControlsDataSource
    ) {
      setQuickCreateState({
        kind: "unavailable",
        reason: isLiveProjectContext
          ? t("Creation capabilities for this Project are unavailable.")
          : t(
              "Open an authorized live Project before using contextual quick-create.",
            ),
      });
      return;
    }
    if (!sessionCommandContext) {
      setQuickCreateState({
        kind: "unavailable",
        reason: t(
          "The authenticated session is not ready. Reconcile the session before creating a record.",
        ),
      });
      return;
    }
    const controller = new AbortController();
    quickCreateRequest.current = controller;
    setQuickCreateState({ kind: "checking" });
    void projectControlsDataSource
      .loadLearning(route.projectGlobalId, { limit: 1 }, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) return;
        setQuickCreateState(
          page.permissions.canCreate
            ? { kind: "available", projectId: route.projectGlobalId ?? "" }
            : {
                kind: "unavailable",
                reason: t(
                  "Your current Project capability does not allow creating a learning record.",
                ),
              },
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ProjectControlsRequestCancelledError
        ) {
          return;
        }
        setQuickCreateState({
          failure: toRequestFailure(error),
          kind: "failed",
        });
      });
  }, [
    isLiveProjectContext,
    projectControlsDataSource,
    route.projectGlobalId,
    sessionCommandContext,
    t,
  ]);

  useEffect(() => {
    quickCreateRequest.current?.abort();
    quickCreateRequest.current = null;
    queueMicrotask(() => {
      setQuickCreateOpen(false);
      setQuickCreateState({ kind: "idle" });
    });
    return () => {
      quickCreateRequest.current?.abort();
    };
  }, [route.pathname]);

  useEffect(() => {
    if (!quickCreateOpen) return undefined;
    const closeOnEscape = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        event.preventDefault();
        setQuickCreateOpen(false);
        restoreQuickCreateTriggerFocus();
      }
    };
    globalThis.addEventListener("keydown", closeOnEscape);
    return () => {
      globalThis.removeEventListener("keydown", closeOnEscape);
    };
  }, [quickCreateOpen, restoreQuickCreateTriggerFocus]);
  useEffect(() => {
    globalThis.addEventListener("resize", hideNavigationTooltip);
    return () => {
      globalThis.removeEventListener("resize", hideNavigationTooltip);
    };
  }, [hideNavigationTooltip]);
  const updateScenario = (scenario: string): void => {
    const url = new URL(globalThis.location.href);
    if (scenario === "normal") url.searchParams.delete("scenario");
    else url.searchParams.set("scenario", scenario);
    navigate(`${url.pathname}${url.search}`);
  };

  return (
    <div
      className="app-shell"
      data-navigation-collapsed={effectiveNavigationCollapsed}
      data-navigation-preference={navigationCollapsed ? "collapsed" : "full"}
      data-navigation-responsive={responsiveNavigationCollapsed}
    >
      <header className="app-header">
        <button
          aria-label={t("Open LaunchFlow home")}
          className="app-header__brand"
          onClick={() => {
            navigate("/work");
          }}
          type="button"
        >
          <DisplayBrandWordmark
            accessibleName={t("LaunchFlow")}
            decorative
            surface="dark"
          />
          <DisplayBrandPlatformIcon
            accessibleName={t("LaunchFlow")}
            decorative
          />
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
              if (isLiveDataContext) {
                setUtilityMessage(
                  isLiveWork
                    ? t(
                        "Live global search is not available in this phase. Open an authorized work item or project link.",
                      )
                    : t(
                        "Live global search is not available in this phase. Open this project from an authorized project link.",
                      ),
                );
                return;
              }
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
          aria-expanded={commandPaletteOpen}
          aria-haspopup="dialog"
          aria-keyshortcuts="Control+K Meta+K"
          aria-label={t("Open command palette")}
          icon="keyboard"
          id="command-palette-trigger"
          onClick={openCommandPalette}
          visual="ghost"
        >
          <span>{t("Commands")}</span>
          <kbd data-language-exempt="identifier">Ctrl/⌘+K</kbd>
        </Button>
        <Button
          aria-label={t("Notifications")}
          icon="alarm"
          onClick={() => {
            setUtilityMessage(
              isLiveDataContext
                ? t(
                    "No live notification feed is connected in this phase. Use My Work for assigned actions.",
                  )
                : t(
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
              isLiveDataContext
                ? t("The current identity is managed by the Frappe session.")
                : t("Signed in for the test environment with prototype data."),
            );
          }}
          visual="ghost"
        >
          {isLiveDataContext ? (
            t("Signed-in user")
          ) : (
            <span data-language-exempt="business-data">Alex Chen</span>
          )}
        </Button>
      </header>
      <aside className="domain-navigation">
        {isLiveProjectContext && route.projectGlobalId ? (
          <button
            aria-describedby={
              effectiveNavigationCollapsed
                ? "navigation-current-project-tooltip"
                : undefined
            }
            aria-label={t("Current Project {{project}}", {
              project: route.projectGlobalId,
            })}
            className="domain-navigation__project-context"
            onBlur={hideNavigationTooltip}
            onClick={() => {
              if (liveProjectPath) navigate(liveProjectPath);
            }}
            onFocus={(event) => {
              showNavigationTooltip(
                event.currentTarget,
                "navigation-current-project-tooltip",
                t("Current Project {{project}}", {
                  project: route.projectGlobalId ?? "",
                }),
              );
            }}
            onMouseEnter={(event) => {
              showNavigationTooltip(
                event.currentTarget,
                "navigation-current-project-tooltip",
                t("Current Project {{project}}", {
                  project: route.projectGlobalId ?? "",
                }),
              );
            }}
            onMouseLeave={hideNavigationTooltip}
            type="button"
          >
            <Icon name="project" />
            <span
              className="domain-navigation__label"
              data-language-exempt="identifier"
            >
              {route.projectGlobalId}
            </span>
          </button>
        ) : null}
        <nav
          aria-label={t("Domain navigation")}
          onScroll={(event) => {
            const focusedControl = document.activeElement;
            if (
              focusedControl instanceof HTMLElement &&
              event.currentTarget.contains(focusedControl)
            ) {
              const tooltipId = focusedControl.getAttribute("aria-describedby");
              const label = focusedControl.getAttribute("aria-label");
              if (tooltipId && label) {
                showNavigationTooltip(
                  focusedControl,
                  tooltipId,
                  label,
                  focusedControl.dataset.navigationTooltipReason,
                );
                return;
              }
            }
            hideNavigationTooltip();
          }}
        >
          <ul>
            {navigation.map((item) => {
              const active =
                route.screen === item.screen ||
                (item.id === "project" && route.screen === "gate");
              const tooltipId = `navigation-${item.id}-tooltip`;
              return (
                <li key={item.id}>
                  <span className="domain-navigation__target">
                    {item.path ? (
                      <button
                        aria-current={active ? "page" : undefined}
                        aria-describedby={
                          effectiveNavigationCollapsed ? tooltipId : undefined
                        }
                        aria-label={item.label}
                        className={`domain-navigation__item${
                          active ? " is-active" : ""
                        }`}
                        data-navigation-tooltip-reason={item.unavailableReason}
                        onBlur={hideNavigationTooltip}
                        onClick={() => {
                          if (item.path) navigate(item.path);
                        }}
                        onFocus={(event) => {
                          showNavigationTooltip(
                            event.currentTarget,
                            tooltipId,
                            item.label,
                            item.unavailableReason,
                          );
                        }}
                        onMouseEnter={(event) => {
                          showNavigationTooltip(
                            event.currentTarget,
                            tooltipId,
                            item.label,
                            item.unavailableReason,
                          );
                        }}
                        onMouseLeave={hideNavigationTooltip}
                        type="button"
                      >
                        <Icon name={item.icon} />
                        <span className="domain-navigation__label">
                          {item.label}
                        </span>
                      </button>
                    ) : (
                      <button
                        aria-disabled="true"
                        aria-describedby={
                          effectiveNavigationCollapsed ? tooltipId : undefined
                        }
                        aria-label={item.label}
                        className="domain-navigation__item domain-navigation__item--disabled"
                        data-navigation-tooltip-reason={item.unavailableReason}
                        onBlur={hideNavigationTooltip}
                        onFocus={(event) => {
                          showNavigationTooltip(
                            event.currentTarget,
                            tooltipId,
                            item.label,
                            item.unavailableReason,
                          );
                        }}
                        onMouseEnter={(event) => {
                          showNavigationTooltip(
                            event.currentTarget,
                            tooltipId,
                            item.label,
                            item.unavailableReason,
                          );
                        }}
                        onMouseLeave={hideNavigationTooltip}
                        type="button"
                      >
                        <Icon name={item.icon} />
                        <span className="domain-navigation__label">
                          {item.label}
                        </span>
                      </button>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </nav>
        <button
          aria-label={
            responsiveNavigationCollapsed
              ? t("Navigation is compact at this window size.")
              : navigationCollapsed
                ? t("Expand domain navigation")
                : t("Collapse domain navigation")
          }
          className="domain-navigation__toggle"
          disabled={
            isLocalizationUnavailable ||
            isLocalizationPending ||
            isNavigationPreferencePending ||
            Boolean(navigationPreferenceFailure) ||
            responsiveNavigationCollapsed
          }
          onClick={() => {
            hideNavigationTooltip();
            setNavigationCollapsed(!navigationCollapsed);
          }}
          title={
            responsiveNavigationCollapsed
              ? t("Navigation is compact at this window size.")
              : navigationCollapsed
                ? t("Expand domain navigation")
                : t("Collapse domain navigation")
          }
          type="button"
        >
          <Icon name={effectiveNavigationCollapsed ? "expand" : "collapse"} />
          <span className="domain-navigation__label">
            {isNavigationPreferencePending
              ? t("Saving navigation preference")
              : responsiveNavigationCollapsed
                ? t("Navigation is compact at this window size.")
                : navigationCollapsed
                  ? t("Expand navigation")
                  : t("Collapse navigation")}
          </span>
        </button>
        <div className="environment-marker">
          <strong>{t("Test environment")}</strong>
          <span className="environment-marker__detail">
            {isLiveWork
              ? t("Live My Work data")
              : isLiveProjectContext
                ? t("Live project data")
                : t("Prototype data")}
          </span>
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
            {returnTarget ? (
              <Button
                icon="chevron"
                onClick={() => {
                  navigate(returnTarget);
                }}
              >
                {t("Return to previous context")}
              </Button>
            ) : null}
            <div className="quick-create">
              <Button
                aria-controls="quick-create-menu"
                aria-expanded={quickCreateOpen}
                aria-haspopup="dialog"
                icon="add"
                id="quick-create-trigger"
                onClick={() => {
                  const nextOpen = !quickCreateOpen;
                  setQuickCreateOpen(nextOpen);
                  if (nextOpen) checkQuickCreate();
                  else quickCreateRequest.current?.abort();
                }}
              >
                {t("Quick create")}
              </Button>
              {quickCreateOpen ? (
                <section
                  aria-label={t("Contextual quick-create")}
                  aria-live="polite"
                  className="quick-create__menu"
                  id="quick-create-menu"
                  role="dialog"
                >
                  <header>
                    <strong>{t("Contextual quick-create")}</strong>
                    <span>
                      {isLiveProjectContext
                        ? t("Current Project")
                        : t("No authorized Project context")}
                    </span>
                  </header>
                  {quickCreateState.kind === "checking" ? (
                    <p aria-busy="true">
                      {t("Checking current Project capabilities")}
                    </p>
                  ) : quickCreateState.kind === "available" ? (
                    <Button
                      icon="add"
                      onClick={() => {
                        const target = buildContextualNavigationTarget(
                          `/projects/${quickCreateState.projectId}?tab=learning&quickCreate=learning`,
                        );
                        setQuickCreateOpen(false);
                        navigate(target);
                      }}
                    >
                      {t("Create Project learning record")}
                    </Button>
                  ) : quickCreateState.kind === "failed" ? (
                    <div className="quick-create__failure">
                      <p>
                        {t(
                          "The current Project capabilities could not be checked.",
                        )}
                      </p>
                      <RequestFailurePanel failure={quickCreateState.failure} />
                      <Button icon="refresh" onClick={checkQuickCreate}>
                        {t("Retry")}
                      </Button>
                    </div>
                  ) : quickCreateState.kind === "unavailable" ? (
                    <p>{quickCreateState.reason}</p>
                  ) : null}
                </section>
              ) : null}
            </div>
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
                if (isLiveWork) {
                  globalThis.dispatchEvent(
                    new CustomEvent("npi:refresh-my-work"),
                  );
                  setUtilityMessage(
                    t("The live My Work request is being refreshed."),
                  );
                  return;
                }
                if (isLiveProjectContext) {
                  if (isLiveGate) {
                    globalThis.dispatchEvent(
                      new CustomEvent("npi:refresh-gate-evidence"),
                    );
                    setUtilityMessage(
                      t("The live Gate evidence request is being refreshed."),
                    );
                    return;
                  }
                  globalThis.dispatchEvent(
                    new CustomEvent("npi:refresh-project"),
                  );
                  setUtilityMessage(
                    t("The live project request is being refreshed."),
                  );
                  return;
                }
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
          {navigationPreferenceFailure ? (
            <div className="navigation-preference-failure" role="alert">
              <Icon name="warning" />
              <div>
                <strong>
                  {t("The navigation preference could not be confirmed.")}
                </strong>
                <p>
                  {t(
                    "The last confirmed navigation mode was kept. Retry to reconcile with the current Frappe session.",
                  )}
                </p>
                <RequestFailurePanel
                  failure={navigationPreferenceFailure.requestFailure}
                />
                <Button
                  disabled={isNavigationPreferencePending}
                  icon="refresh"
                  onClick={retryNavigationPreference}
                >
                  {t("Retry")}
                </Button>
              </div>
            </div>
          ) : null}
          <div
            className={`prototype-banner${isLocalizationUnavailable ? " prototype-banner--error" : ""}`}
            aria-busy={isLocalizationPending}
            role="status"
          >
            <Icon name="info" />
            <strong>
              {isLiveWork
                ? t(
                    "Live My Work data. No production ERPNext system is connected.",
                  )
                : isLiveProjectContext
                  ? t(
                      "Live project data. No production ERPNext system is connected.",
                    )
                  : t("Prototype data - no production system is connected.")}
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
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
        <footer className="status-bar">
          <div className="status-bar__brand">
            <DisplayBrandWordmark
              accessibleName={t("LaunchFlow")}
              surface="light"
            />
            <span aria-hidden="true" className="status-bar__brand-divider" />
            <DisplayBrandCompanyMark
              accessibleName={t("Company ownership mark")}
            />
          </div>
          <span>{t("Test environment")}</span>
          <span className="status-bar__catalog">
            {t("Catalog")}:{" "}
            <code data-language-exempt="identifier">{catalogVersion}</code>
          </span>
          <span className="status-bar__timezone">
            {isLiveWork ? t("System time zone") : t("Time zone")}:{" "}
            <span data-language-exempt="identifier">UTC</span>
          </span>
          <label>
            <span>{t("Language")}</span>
            <Select
              aria-label={t("Language")}
              disabled={
                isLocalizationUnavailable ||
                isLocalizationPending ||
                isNavigationPreferencePending ||
                Boolean(navigationPreferenceFailure)
              }
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
          {isLiveDataContext ? null : (
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
          )}
        </footer>
      </div>
      <CommandPalette
        commands={commands}
        onClose={() => {
          setCommandPaletteOpen(false);
        }}
        onOpen={openCommandPalette}
        onSelect={(command) => {
          if (!command.target) return;
          setCommandPaletteOpen(false);
          navigate(buildContextualNavigationTarget(command.target));
        }}
        open={commandPaletteOpen}
        returnFocusTarget={commandPaletteReturnFocusTarget}
      />
      {effectiveNavigationCollapsed && navigationTooltip
        ? createPortal(
            <span
              className="domain-navigation__tooltip"
              id={navigationTooltip.id}
              role="tooltip"
              style={{
                left: navigationTooltip.left,
                maxWidth: navigationTooltip.maxWidth,
                top: navigationTooltip.top,
              }}
            >
              <strong>{navigationTooltip.label}</strong>
              {navigationTooltip.reason ? (
                <small>{navigationTooltip.reason}</small>
              ) : null}
            </span>,
            document.body,
          )
        : null}
    </div>
  );
}
