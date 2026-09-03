import { useCallback, useEffect, useState } from "react";

import type { Scenario, ScreenId } from "../domain/view-models";
import { scenarios } from "../fixtures/prototype";

const maximumInternalTargetLength = 1024;
const uuidRouteSegment =
  "[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
const fixtureRouteSegment = "[A-Za-z0-9][A-Za-z0-9._-]{0,79}";
const liveProjectRoutePattern = new RegExp(
  `^/projects/(${uuidRouteSegment})/?$`,
  "u",
);
const liveGateRoutePattern = new RegExp(
  `^/projects/(${uuidRouteSegment})/gates/(${uuidRouteSegment})/?$`,
  "u",
);
const liveGatePathPattern = /^\/projects\/[^/]+\/gates\/[^/]+\/?$/u;
const liveToolingRoutePattern = new RegExp(
  `^/projects/(${uuidRouteSegment})/tooling/?$`,
  "u",
);
const liveToolingMasterRoutePattern = new RegExp(
  `^/projects/(${uuidRouteSegment})/tooling/(${uuidRouteSegment})/?$`,
  "u",
);
const liveTrialRoutePattern = new RegExp(
  `^/projects/(${uuidRouteSegment})/trials/?$`,
  "u",
);
const liveIntegrationOperationsRoutePattern = new RegExp(
  `^/projects/(${uuidRouteSegment})/integration-operations/?$`,
  "u",
);
const approvedPathPatterns = [
  /^\/work\/?$/u,
  /^\/portfolio\/?$/u,
  /^\/reports\/?$/u,
  /^\/administration\/?$/u,
  /^\/administration\/migration-rehearsal\/?$/u,
  /^\/demo\/work\/?$/u,
  new RegExp(`^/demo/projects/${fixtureRouteSegment}/?$`, "u"),
  new RegExp(
    `^/demo/projects/${fixtureRouteSegment}/gates/${fixtureRouteSegment}/?$`,
    "u",
  ),
  liveProjectRoutePattern,
  liveGateRoutePattern,
  liveToolingRoutePattern,
  liveToolingMasterRoutePattern,
  liveTrialRoutePattern,
  liveIntegrationOperationsRoutePattern,
  new RegExp(`^/tooling/${fixtureRouteSegment}/?$`, "u"),
  new RegExp(`^/trials/${fixtureRouteSegment}/?$`, "u"),
  /^\/execution\/?$/u,
] as const;

function containsControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0);
    return codePoint !== undefined && (codePoint <= 0x1f || codePoint === 0x7f);
  });
}

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
  toolingMasterGlobalId: string | null;
  toolingMode: "live" | "demo" | null;
  toolingWorkspace: "cockpit" | "import";
  trialMode: "live" | "demo" | null;
  reportingView: "portfolio" | "kpis" | "configuration" | "migration" | null;
}

function parseScenario(value: string | null): Scenario {
  return scenarios.find((scenario) => scenario === value) ?? "normal";
}

export function validateInternalNavigationTarget(
  target: string | null | undefined,
  origin = globalThis.location.origin,
): string | null {
  if (
    !target ||
    target.length > maximumInternalTargetLength ||
    containsControlCharacter(target) ||
    !target.startsWith("/") ||
    target.startsWith("//")
  ) {
    return null;
  }
  let candidate: URL;
  try {
    candidate = new URL(target, origin);
  } catch {
    return null;
  }
  if (
    candidate.origin !== origin ||
    candidate.username ||
    candidate.password ||
    candidate.searchParams.has("returnTo") ||
    !approvedPathPatterns.some((pattern) => pattern.test(candidate.pathname))
  ) {
    return null;
  }
  return `${candidate.pathname}${candidate.search}${candidate.hash}`;
}

export function currentReturnTarget(
  location: Location = globalThis.location,
): string | null {
  const parameters = new URLSearchParams(location.search);
  return validateInternalNavigationTarget(parameters.get("returnTo"));
}

export function buildContextualNavigationTarget(
  target: string,
  location: Location = globalThis.location,
): string {
  const validatedTarget = validateInternalNavigationTarget(target);
  if (!validatedTarget) {
    throw new Error("The requested navigation target is not approved.");
  }
  const destination = new URL(validatedTarget, location.origin);
  const currentParameters = new URLSearchParams(location.search);
  currentParameters.delete("returnTo");
  const current = validateInternalNavigationTarget(
    `${location.pathname}${
      currentParameters.size ? `?${currentParameters.toString()}` : ""
    }${location.hash}`,
    location.origin,
  );
  if (current && current !== validatedTarget) {
    destination.searchParams.set("returnTo", current);
  }
  return `${destination.pathname}${destination.search}${destination.hash}`;
}

export function parseRoute(location: Location = globalThis.location): AppRoute {
  const pathname = location.pathname;
  const parameters = new URLSearchParams(location.search);
  const demoProjectMatch = /^\/demo\/projects\/([^/]+)\/?$/u.exec(pathname);
  const demoGateMatch = /^\/demo\/projects\/([^/]+)\/gates\/([^/]+)\/?$/u.exec(
    pathname,
  );
  const liveProjectMatch = liveProjectRoutePattern.exec(pathname);
  const liveGateMatch = liveGateRoutePattern.exec(pathname);
  const liveToolingMatch = liveToolingRoutePattern.exec(pathname);
  const liveToolingMasterMatch = liveToolingMasterRoutePattern.exec(pathname);
  const liveTrialMatch = liveTrialRoutePattern.exec(pathname);
  const liveIntegrationOperationsMatch =
    liveIntegrationOperationsRoutePattern.exec(pathname);
  const demoWork = /^\/demo\/work\/?$/u.test(pathname);
  const reportingView = /^\/portfolio\/?$/u.test(pathname)
    ? "portfolio"
    : /^\/reports\/?$/u.test(pathname)
      ? "kpis"
      : /^\/administration\/?$/u.test(pathname)
        ? "configuration"
        : /^\/administration\/migration-rehearsal\/?$/u.test(pathname)
          ? "migration"
          : null;
  const screen: ScreenId = reportingView
    ? "portfolio"
    : liveIntegrationOperationsMatch
      ? "execution"
      : demoGateMatch || liveGateMatch || liveGatePathPattern.test(pathname)
        ? "gate"
        : liveTrialMatch
          ? "trial"
          : liveToolingMatch || liveToolingMasterMatch
            ? "tooling"
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
  const toolingMode =
    screen === "tooling"
      ? liveToolingMatch || liveToolingMasterMatch
        ? "live"
        : "demo"
      : null;
  const trialMode =
    screen === "trial" ? (liveTrialMatch ? "live" : "demo") : null;
  const workMode = screen === "work" ? (demoWork ? "demo" : "live") : null;
  const liveRoute =
    screen === "portfolio" ||
    workMode === "live" ||
    projectMode === "live" ||
    gateMode === "live" ||
    toolingMode === "live" ||
    trialMode === "live" ||
    (screen === "execution" && liveIntegrationOperationsMatch !== null);
  return {
    gateGlobalId: liveGateMatch?.[2] ?? null,
    gateMode,
    screen,
    pathname,
    scenario: liveRoute ? "normal" : parseScenario(parameters.get("scenario")),
    qualityFailure: parameters.get("quality") === "failed",
    projectGlobalId:
      liveProjectMatch?.[1] ??
      liveGateMatch?.[1] ??
      liveToolingMatch?.[1] ??
      liveToolingMasterMatch?.[1] ??
      liveTrialMatch?.[1] ??
      liveIntegrationOperationsMatch?.[1] ??
      null,
    projectMode,
    toolingMasterGlobalId: liveToolingMasterMatch?.[2] ?? null,
    toolingMode,
    toolingWorkspace:
      toolingMode === "live" &&
      liveToolingMatch &&
      parameters.get("workspace") === "import"
        ? "import"
        : "cockpit",
    trialMode,
    workMode,
    reportingView,
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
