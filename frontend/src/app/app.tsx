import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useState,
} from "react";

import { AppShell } from "./app-shell";
import { useAppRouter } from "./router";
import { ImpactReview } from "../components/primitives";
import { ScenarioBoundary } from "../components/scenario-boundary";
import { useI18n } from "../i18n/runtime";
import { prototypeUsabilityRecorder } from "../telemetry/recorder";
import { LiveProjectControlsDataSource } from "../api/project-controls-data-source";
import { LiveReportingDataSource } from "../api/reporting-data-source";
import { LiveCollaborationDataSource } from "../api/collaboration-data-source";
import type {
  RequestWorkspaceTransition,
  WorkspaceDirtyRegistration,
} from "./workspace-navigation";

const WorkPage = lazy(() => import("../pages/work-page"));
const LiveWorkRoute = lazy(() => import("./live-work-route"));
const LiveProjectRoute = lazy(() => import("./live-project-route"));
const ProjectDemoPage = lazy(() => import("../pages/project-demo-page"));
const GatePage = lazy(() => import("../pages/gate-page"));
const LiveGateRoute = lazy(() => import("./live-gate-route"));
const ToolingPage = lazy(() => import("../pages/tooling-page"));
const LiveToolingRoute = lazy(() => import("./live-tooling-route"));
const ToolingImportRoute = lazy(() => import("./tooling-import-route"));
const TrialPage = lazy(() => import("../pages/trial-page"));
const LiveTrialRoute = lazy(() => import("./live-trial-route"));
const LiveExecutionRoute = lazy(() => import("./live-execution-route"));
const ExecutionPrototypePage = lazy(
  () => import("../pages/execution-prototype-page"),
);
const PortfolioPage = lazy(() => import("../pages/portfolio-page"));
const HistoricalMigrationRoute = lazy(
  () => import("./historical-migration-route"),
);
const DataExchangeRoute = lazy(() => import("./data-exchange-route"));
const liveProjectControlsDataSource = new LiveProjectControlsDataSource();
const liveReportingDataSource = new LiveReportingDataSource();
const liveCollaborationDataSource = new LiveCollaborationDataSource();

export function App(): React.JSX.Element {
  const { route, navigate, syncRoute } = useAppRouter();
  const { t } = useI18n();
  const [workspaceDirty, setWorkspaceDirty] =
    useState<WorkspaceDirtyRegistration | null>(null);
  const [pendingTransition, setPendingTransition] = useState<{
    perform: () => void;
    returnFocusTarget: HTMLElement | null;
    target: string;
  } | null>(null);
  const dirty = route.scenario === "dirty" || workspaceDirty !== null;
  const reportWorkspaceDirty = useCallback(
    (registration: WorkspaceDirtyRegistration | null): void => {
      setWorkspaceDirty(registration);
    },
    [],
  );
  const requestWorkspaceTransition: RequestWorkspaceTransition = useCallback(
    (perform, returnFocusTarget): void => {
      if (!dirty) {
        perform();
        return;
      }
      const activeElement =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      setPendingTransition({
        perform,
        returnFocusTarget:
          returnFocusTarget ??
          activeElement ??
          workspaceDirty?.returnFocusTarget() ??
          document.getElementById("main-content"),
        target: globalThis.location.pathname,
      });
    },
    [dirty, workspaceDirty],
  );
  useEffect(() => {
    if (import.meta.env.DEV || import.meta.env.VITE_NPI_PROTOTYPE === "true") {
      void prototypeUsabilityRecorder.record({
        name: "route_viewed",
        route: `/${route.screen}`,
        outcome: "viewed",
        contextSwitches: 0,
        occurredAt: new Date().toISOString(),
      });
    }
  }, [route.pathname, route.screen]);
  useLayoutEffect(() => {
    if (!dirty) return undefined;
    const protectedLocation = `${globalThis.location.pathname}${globalThis.location.search}${globalThis.location.hash}`;
    const handleBeforeUnload = (event: BeforeUnloadEvent): void => {
      event.preventDefault();
      // The legacy assignment remains required for browsers that do not act on
      // preventDefault alone when a native unload confirmation is requested.
      // eslint-disable-next-line @typescript-eslint/no-deprecated
      event.returnValue = "";
    };
    const handlePopState = (): void => {
      const attemptedLocation = `${globalThis.location.pathname}${globalThis.location.search}${globalThis.location.hash}`;
      globalThis.history.pushState({}, "", protectedLocation);
      syncRoute();
      setPendingTransition({
        perform: () => {
          navigate(attemptedLocation);
        },
        returnFocusTarget:
          workspaceDirty?.returnFocusTarget() ??
          document.getElementById("main-content"),
        target: attemptedLocation,
      });
    };
    globalThis.addEventListener("beforeunload", handleBeforeUnload);
    globalThis.addEventListener("popstate", handlePopState);
    return () => {
      globalThis.removeEventListener("beforeunload", handleBeforeUnload);
      globalThis.removeEventListener("popstate", handlePopState);
    };
  }, [dirty, navigate, syncRoute, workspaceDirty]);
  const guardedNavigate = useCallback(
    (target: string): void => {
      const activeElement =
        document.activeElement instanceof HTMLElement &&
        document.activeElement !== document.body
          ? document.activeElement
          : null;
      const returnFocusTarget = activeElement?.closest('[role="dialog"]')
        ? document.getElementById("command-palette-trigger")
        : (activeElement ??
          document.getElementById("command-palette-trigger") ??
          document.getElementById("main-content"));
      requestWorkspaceTransition(() => {
        navigate(target);
      }, returnFocusTarget);
    },
    [navigate, requestWorkspaceTransition],
  );
  const page =
    route.screen === "project" && route.projectMode === "demo" ? (
      <ProjectDemoPage navigate={guardedNavigate} scenario={route.scenario} />
    ) : route.screen === "project" ? (
      <LiveProjectRoute
        collaborationDataSource={liveCollaborationDataSource}
        controlsDataSource={liveProjectControlsDataSource}
        globalId={route.projectGlobalId ?? ""}
        navigate={guardedNavigate}
        reportWorkspaceDirty={reportWorkspaceDirty}
        requestWorkspaceTransition={requestWorkspaceTransition}
      />
    ) : route.screen === "gate" && route.gateMode === "live" ? (
      <LiveGateRoute
        gateGlobalId={route.gateGlobalId ?? ""}
        navigate={guardedNavigate}
        projectGlobalId={route.projectGlobalId ?? ""}
      />
    ) : route.screen === "gate" ? (
      <GatePage
        navigate={guardedNavigate}
        qualityFailure={route.qualityFailure}
        scenario={route.scenario}
      />
    ) : route.screen === "tooling" &&
      route.toolingMode === "live" &&
      route.toolingWorkspace === "import" ? (
      <ToolingImportRoute
        navigate={guardedNavigate}
        projectId={route.projectGlobalId ?? ""}
        reportWorkspaceDirty={reportWorkspaceDirty}
      />
    ) : route.screen === "tooling" && route.toolingMode === "live" ? (
      <LiveToolingRoute
        masterId={route.toolingMasterGlobalId}
        navigate={guardedNavigate}
        projectId={route.projectGlobalId ?? ""}
        reportWorkspaceDirty={reportWorkspaceDirty}
      />
    ) : route.screen === "tooling" ? (
      <ToolingPage navigate={guardedNavigate} scenario={route.scenario} />
    ) : route.screen === "trial" && route.trialMode === "live" ? (
      <LiveTrialRoute
        navigate={guardedNavigate}
        projectId={route.projectGlobalId ?? ""}
        reportWorkspaceDirty={reportWorkspaceDirty}
      />
    ) : route.screen === "trial" ? (
      <TrialPage navigate={guardedNavigate} scenario={route.scenario} />
    ) : route.screen === "execution" && route.projectGlobalId !== null ? (
      <LiveExecutionRoute projectId={route.projectGlobalId} />
    ) : route.screen === "execution" ? (
      <ExecutionPrototypePage scenario={route.scenario} />
    ) : route.screen === "portfolio" && route.reportingView === "migration" ? (
      <HistoricalMigrationRoute />
    ) : route.screen === "portfolio" &&
      route.reportingView === "data_exchange" ? (
      <DataExchangeRoute />
    ) : route.screen === "portfolio" ? (
      <PortfolioPage
        dataSource={liveReportingDataSource}
        key={route.reportingView}
        navigate={guardedNavigate}
        view={
          route.reportingView === "kpis"
            ? "kpis"
            : route.reportingView === "configuration"
              ? "configuration"
              : "portfolio"
        }
      />
    ) : route.workMode === "demo" ? (
      <WorkPage navigate={guardedNavigate} />
    ) : (
      <LiveWorkRoute navigate={guardedNavigate} />
    );
  const terminalScenario =
    route.workMode !== "live" &&
    route.projectMode !== "live" &&
    route.gateMode !== "live" &&
    route.toolingMode !== "live" &&
    route.trialMode !== "live" &&
    !["normal", "read_only", "partial", "dirty"].includes(route.scenario);
  const pageClass =
    route.screen === "work"
      ? "page--work"
      : route.screen === "portfolio"
        ? "page--reporting"
        : route.screen === "execution"
          ? "page--execution"
          : "page--object";
  return (
    <>
      <AppShell
        collaborationDataSource={liveCollaborationDataSource}
        navigate={guardedNavigate}
        projectControlsDataSource={liveProjectControlsDataSource}
        reportingDataSource={liveReportingDataSource}
        route={route}
      >
        <Suspense
          fallback={
            <div aria-busy="true" className="route-loading">
              {t("Loading workspace")}
            </div>
          }
        >
          {terminalScenario ? (
            <article className={`page ${pageClass}`}>
              <ScenarioBoundary scenario={route.scenario}>
                {page}
              </ScenarioBoundary>
            </article>
          ) : (
            <ScenarioBoundary scenario={route.scenario}>
              {page}
            </ScenarioBoundary>
          )}
        </Suspense>
      </AppShell>
      {pendingTransition ? (
        <ImpactReview
          confirmLabel={t("Discard changes and leave")}
          details={{
            objectIdentity:
              workspaceDirty?.objectIdentity ?? pendingTransition.target,
            version: workspaceDirty?.version ?? "unsaved-draft",
            impact: t(
              "Your unsaved changes in the current workspace will be discarded.",
            ),
            permission: t("No additional permission is required."),
            irreversible: t("Discarded prototype changes cannot be restored."),
            failureHandling: t(
              "Cancel keeps the current workspace and its unsaved changes.",
            ),
            audit: t(
              "This prototype does not persist an audit record. A submitted navigation decision would record the actor and outcome without field content.",
            ),
          }}
          onCancel={() => {
            setPendingTransition(null);
          }}
          onConfirm={() => {
            const transition = pendingTransition;
            setPendingTransition(null);
            transition.perform();
          }}
          returnFocusTarget={() => pendingTransition.returnFocusTarget}
          title={t("Unsaved changes")}
        />
      ) : null}
    </>
  );
}
