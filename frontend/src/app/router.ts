import { useCallback, useEffect, useState } from "react";

import type { Scenario, ScreenId } from "../domain/view-models";
import { scenarios } from "../fixtures/prototype";

export interface AppRoute {
  screen: ScreenId;
  pathname: string;
  scenario: Scenario;
  qualityFailure: boolean;
  workMode: "live" | "demo" | null;
  projectGlobalId: string | null;
  projectMode: "live" | "demo" | null;
  gateGlobalId: string | null;
  gateMode: "live" | "demo" | null;
}

function parseScenario(value: string | null): Scenario {
  return scenarios.find((scenario) => scenario === value) ?? "normal";
}

export function parseRoute(location: Location = globalThis.location): AppRoute {
  const pathname = location.pathname;
  const parameters = new URLSearchParams(location.search);
  const demoProjectMatch = /^\/demo\/projects\/([^/]+)\/?$/u.exec(pathname);
  const demoGateMatch = /^\/demo\/projects\/([^/]+)\/gates\/([^/]+)\/?$/u.exec(
    pathname,
  );
  const liveProjectMatch = /^\/projects\/([^/]+)\/?$/u.exec(pathname);
  const liveGateMatch = /^\/projects\/([^/]+)\/gates\/([^/]+)\/?$/u.exec(
    pathname,
  );
  const demoWork = /^\/demo\/work\/?$/u.test(pathname);
  const screen: ScreenId =
    demoGateMatch || liveGateMatch
      ? "gate"
      : demoProjectMatch
        ? "project"
        : pathname.startsWith("/projects/")
          ? "project"
          : pathname.startsWith("/tooling/")
            ? "tooling"
            : pathname.startsWith("/trials/")
              ? "trial"
              : pathname.startsWith("/execution")
                ? "execution"
                : "work";
  const projectMode =
    screen === "project" ? (demoProjectMatch ? "demo" : "live") : null;
  const gateMode = screen === "gate" ? (demoGateMatch ? "demo" : "live") : null;
  const workMode = screen === "work" ? (demoWork ? "demo" : "live") : null;
  const liveRoute =
    workMode === "live" || projectMode === "live" || gateMode === "live";
  return {
    gateGlobalId: liveGateMatch?.[2] ?? null,
    gateMode,
    screen,
    pathname,
    scenario: liveRoute ? "normal" : parseScenario(parameters.get("scenario")),
    qualityFailure: parameters.get("quality") === "failed",
    projectGlobalId: liveProjectMatch?.[1] ?? liveGateMatch?.[1] ?? null,
    projectMode,
    workMode,
  };
}

export function useAppRouter(): {
  route: AppRoute;
  navigate: (target: string) => void;
  syncRoute: () => void;
} {
  const [route, setRoute] = useState(parseRoute);
  const syncRoute = useCallback((): void => {
    setRoute(parseRoute());
  }, []);
  useEffect(() => {
    globalThis.addEventListener("popstate", syncRoute);
    return () => {
      globalThis.removeEventListener("popstate", syncRoute);
    };
  }, [syncRoute]);
  const navigate = useCallback((target: string): void => {
    globalThis.history.pushState({}, "", target);
    setRoute(parseRoute());
    globalThis.scrollTo({ top: 0, behavior: "auto" });
  }, []);
  return { route, navigate, syncRoute };
}
