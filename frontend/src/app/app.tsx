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
import { LiveProjectCockpitDataSource } from "../api/project-data-source";
import { LiveGateEvidenceDataSource } from "../api/gate-evidence-data-source";
import {
  LiveProjectDomainWorkItemsDataSource,
  LiveProjectWorkContextDataSource,
} from "../api/project-work-data-source";

const WorkPage = lazy(() => import("../pages/work-page"));
const ProjectPage = lazy(() => import("../pages/project-page"));
const ProjectDemoPage = lazy(() => import("../pages/project-demo-page"));
const GatePage = lazy(() => import("../pages/gate-page"));
const GateEvidencePage = lazy(() => import("../pages/gate-evidence-page"));
const ToolingPage = lazy(() => import("../pages/tooling-page"));
const TrialPage = lazy(() => import("../pages/trial-page"));
const ExecutionPage = lazy(() => import("../pages/execution-page"));
const liveProjectDataSource = new LiveProjectCockpitDataSource();
const liveProjectWorkContextDataSource = new LiveProjectWorkContextDataSource();
const liveProjectDomainWorkItemsDataSource =
  new LiveProjectDomainWorkItemsDataSource();
const liveGateEvidenceDataSource = new LiveGateEvidenceDataSource();

export function App(): React.JSX.Element {
  const { route, navigate, syncRoute } = useAppRouter();
  const { t } = useI18n();
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(
    null,
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
    if (route.scenario !== "dirty") return undefined;
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
      setPendingNavigation(attemptedLocation);
    };
    globalThis.addEventListener("beforeunload", handleBeforeUnload);
    globalThis.addEventListener("popstate", handlePopState);
    return () => {
      globalThis.removeEventListener("beforeunload", handleBeforeUnload);
      globalThis.removeEventListener("popstate", handlePopState);
    };
  }, [route.scenario, syncRoute]);
  const guardedNavigate = useCallback(
    (target: string): void => {
      if (route.scenario === "dirty") {
        setPendingNavigation(target);
        return;
      }
      navigate(target);
    },
    [navigate, route.scenario],
  );
  const page =
    route.screen === "project" && route.projectMode === "demo" ? (
      <ProjectDemoPage navigate={guardedNavigate} scenario={route.scenario} />
    ) : route.screen === "project" ? (
      <ProjectPage
        contextDataSource={liveProjectWorkContextDataSource}
        dataSource={liveProjectDataSource}
        domainWorkItemsDataSource={liveProjectDomainWorkItemsDataSource}
        globalId={route.projectGlobalId ?? ""}
        navigate={guardedNavigate}
      />
    ) : route.screen === "gate" && route.gateMode === "live" ? (
      <GateEvidencePage
        dataSource={liveGateEvidenceDataSource}
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
    ) : route.screen === "tooling" ? (
      <ToolingPage navigate={guardedNavigate} scenario={route.scenario} />
    ) : route.screen === "trial" ? (
      <TrialPage navigate={guardedNavigate} scenario={route.scenario} />
    ) : route.screen === "execution" ? (
      <ExecutionPage scenario={route.scenario} />
    ) : (
      <WorkPage navigate={guardedNavigate} />
    );
  const terminalScenario =
    route.projectMode !== "live" &&
    route.gateMode !== "live" &&
    !["normal", "read_only", "partial", "dirty"].includes(route.scenario);
  const pageClass =
    route.screen === "work"
      ? "page--work"
      : route.screen === "execution"
        ? "page--execution"
        : "page--object";
  return (
    <>
      <AppShell navigate={guardedNavigate} route={route}>
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
      {pendingNavigation ? (
        <ImpactReview
          confirmLabel={t("Discard changes and leave")}
          details={{
            objectIdentity: route.pathname,
            version: "unsaved-draft",
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
            setPendingNavigation(null);
          }}
          onConfirm={() => {
            const target = pendingNavigation;
            setPendingNavigation(null);
            navigate(target);
          }}
          title={t("Unsaved changes")}
        />
      ) : null}
    </>
  );
}
