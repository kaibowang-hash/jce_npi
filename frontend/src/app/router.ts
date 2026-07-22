import { useCallback, useEffect, useState } from "react";

import type { Scenario, ScreenId } from "../domain/view-models";
import { scenarios } from "../fixtures/prototype";

export interface AppRoute {
  screen: ScreenId;
  pathname: string;
  scenario: Scenario;
  qualityFailure: boolean;
}

function parseScenario(value: string | null): Scenario {
  return scenarios.find((scenario) => scenario === value) ?? "normal";
}

export function parseRoute(location: Location = globalThis.location): AppRoute {
  const pathname = location.pathname;
  const parameters = new URLSearchParams(location.search);
  const screen: ScreenId =
    pathname.startsWith("/projects/") && pathname.includes("/gates/")
      ? "gate"
      : pathname.startsWith("/projects/")
        ? "project"
        : pathname.startsWith("/tooling/")
          ? "tooling"
          : pathname.startsWith("/trials/")
            ? "trial"
            : pathname.startsWith("/execution")
              ? "execution"
              : "work";
  return {
    screen,
    pathname,
    scenario: parseScenario(parameters.get("scenario")),
    qualityFailure: parameters.get("quality") === "failed",
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
