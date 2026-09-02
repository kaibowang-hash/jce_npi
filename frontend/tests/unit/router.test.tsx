import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  buildContextualNavigationTarget,
  currentReturnTarget,
  parseRoute,
  useAppRouter,
  validateInternalNavigationTarget,
} from "../../src/app/router";

function locationFor(path: string): Location {
  return new URL(path, "https://npi.example.test") as unknown as Location;
}

describe("application routing", () => {
  it.each([
    ["/work", "work"],
    ["/portfolio", "portfolio"],
    ["/reports", "portfolio"],
    ["/administration", "portfolio"],
    ["/demo/work", "work"],
    ["/demo/projects/PJ-26018", "project"],
    ["/projects/11111111-1111-4111-8111-111111111111", "project"],
    ["/demo/projects/PJ-26018/gates/G5", "gate"],
    [
      "/projects/11111111-1111-4111-8111-111111111111/gates/44444444-4444-4444-8444-444444444444",
      "gate",
    ],
    ["/tooling/TL-26018-01", "tooling"],
    ["/projects/11111111-1111-4111-8111-111111111111/tooling", "tooling"],
    [
      "/projects/11111111-1111-4111-8111-111111111111/tooling/22222222-2222-4222-8222-222222222222",
      "tooling",
    ],
    ["/trials/T1", "trial"],
    ["/projects/11111111-1111-4111-8111-111111111111/trials", "trial"],
    [
      "/projects/11111111-1111-4111-8111-111111111111/integration-operations",
      "execution",
    ],
    ["/execution", "execution"],
  ] as const)("maps %s to the %s screen", (path, screen) => {
    expect(parseRoute(locationFor(path)).screen).toBe(screen);
  });

  it("separates the explicit demo route from the live UUID route", () => {
    expect(parseRoute(locationFor("/portfolio"))).toMatchObject({
      reportingView: "portfolio",
      scenario: "normal",
      screen: "portfolio",
    });
    expect(parseRoute(locationFor("/reports"))).toMatchObject({
      reportingView: "kpis",
      screen: "portfolio",
    });
    expect(parseRoute(locationFor("/administration"))).toMatchObject({
      reportingView: "configuration",
      screen: "portfolio",
    });
    expect(parseRoute(locationFor("/demo/work?scenario=error"))).toMatchObject({
      scenario: "error",
      workMode: "demo",
    });
    expect(parseRoute(locationFor("/work?scenario=error"))).toMatchObject({
      scenario: "normal",
      workMode: "live",
    });
    expect(
      parseRoute(locationFor("/demo/not-a-work-fixture?scenario=error")),
    ).toMatchObject({
      scenario: "normal",
      workMode: "live",
    });
    expect(parseRoute(locationFor("/demo/projects/PJ-26018"))).toMatchObject({
      projectGlobalId: null,
      projectMode: "demo",
      scenario: "normal",
    });
    expect(
      parseRoute(
        locationFor(
          "/projects/11111111-1111-4111-8111-111111111111?scenario=error",
        ),
      ),
    ).toMatchObject({
      projectGlobalId: "11111111-1111-4111-8111-111111111111",
      projectMode: "live",
      scenario: "normal",
    });
    expect(
      parseRoute(
        locationFor("/demo/projects/PJ-26018/gates/G5?scenario=partial"),
      ),
    ).toMatchObject({
      gateGlobalId: null,
      gateMode: "demo",
      projectGlobalId: null,
      scenario: "partial",
    });
    expect(
      parseRoute(
        locationFor(
          "/projects/11111111-1111-4111-8111-111111111111/gates/44444444-4444-4444-8444-444444444444?scenario=error",
        ),
      ),
    ).toMatchObject({
      gateGlobalId: "44444444-4444-4444-8444-444444444444",
      gateMode: "live",
      projectGlobalId: "11111111-1111-4111-8111-111111111111",
      scenario: "normal",
    });
    expect(parseRoute(locationFor("/projects/not-a-uuid"))).toMatchObject({
      projectGlobalId: null,
      projectMode: "live",
      screen: "project",
    });
    expect(
      parseRoute(
        locationFor(
          "/projects/11111111-1111-4111-8111-111111111111/tooling/22222222-2222-4222-8222-222222222222?scenario=error",
        ),
      ),
    ).toMatchObject({
      projectGlobalId: "11111111-1111-4111-8111-111111111111",
      scenario: "normal",
      toolingMasterGlobalId: "22222222-2222-4222-8222-222222222222",
      toolingMode: "live",
    });
    expect(parseRoute(locationFor("/tooling/TL-26018-01"))).toMatchObject({
      projectGlobalId: null,
      toolingMasterGlobalId: null,
      toolingMode: "demo",
      toolingWorkspace: "cockpit",
    });
    expect(
      parseRoute(
        locationFor(
          "/projects/11111111-1111-4111-8111-111111111111/trials?scenario=error",
        ),
      ),
    ).toMatchObject({
      projectGlobalId: "11111111-1111-4111-8111-111111111111",
      scenario: "normal",
      screen: "trial",
      trialMode: "live",
    });
    expect(parseRoute(locationFor("/trials/T1"))).toMatchObject({
      projectGlobalId: null,
      trialMode: "demo",
    });
    expect(
      parseRoute(
        locationFor(
          "/projects/11111111-1111-4111-8111-111111111111/integration-operations?scenario=error",
        ),
      ),
    ).toMatchObject({
      projectGlobalId: "11111111-1111-4111-8111-111111111111",
      scenario: "normal",
      screen: "execution",
    });
    expect(
      parseRoute(
        locationFor(
          "/projects/11111111-1111-4111-8111-111111111111/tooling?workspace=import",
        ),
      ),
    ).toMatchObject({
      projectGlobalId: "11111111-1111-4111-8111-111111111111",
      toolingMode: "live",
      toolingWorkspace: "import",
    });
    expect(
      parseRoute(
        locationFor(
          "/projects/11111111-1111-4111-8111-111111111111/tooling/22222222-2222-4222-8222-222222222222?workspace=import",
        ),
      ).toolingWorkspace,
    ).toBe("cockpit");
    expect(
      parseRoute(
        locationFor(
          "/projects/11111111-1111-4111-8111-111111111111/gates/not-a-uuid",
        ),
      ),
    ).toMatchObject({
      gateGlobalId: null,
      gateMode: "live",
      projectGlobalId: null,
      screen: "gate",
    });
  });

  it("normalizes unknown scenarios and preserves the quality-failure fixture", () => {
    expect(
      parseRoute(locationFor("/execution?scenario=unknown")).scenario,
    ).toBe("normal");
    expect(
      parseRoute(
        locationFor(
          "/demo/projects/PJ-26018/gates/G6?scenario=error&quality=failed",
        ),
      ),
    ).toMatchObject({
      qualityFailure: true,
      scenario: "error",
      screen: "gate",
    });
  });

  it("accepts only exact same-origin return routes", () => {
    const origin = "https://npi.example.test";
    const projectId = "11111111-1111-4111-8111-111111111111";
    const gateId = "44444444-4444-4444-8444-444444444444";
    for (const target of [
      "/work",
      "/portfolio",
      "/reports",
      "/administration",
      "/demo/work?scenario=partial",
      "/demo/projects/PJ-26018",
      "/demo/projects/PJ-26018/gates/G5",
      `/projects/${projectId}?tab=learning`,
      `/projects/${projectId}/gates/${gateId}`,
      `/projects/${projectId}/tooling`,
      `/projects/${projectId}/tooling/${gateId}`,
      `/projects/${projectId}/trials`,
      `/projects/${projectId}/integration-operations`,
      "/tooling/TL-26018-01",
      "/trials/T1",
      "/execution",
    ]) {
      expect(validateInternalNavigationTarget(target, origin)).toBe(target);
    }
  });

  it.each([
    "https://attacker.invalid/work",
    "//attacker.invalid/work",
    "/unknown",
    "/projects/not-a-uuid",
    "/projects/11111111-1111-4111-8111-111111111111/extra",
    "/work?returnTo=%2Fexecution",
    "/work\u0000",
    `/work?value=${"x".repeat(1100)}`,
  ])("rejects unsafe return target %s", (target) => {
    expect(
      validateInternalNavigationTarget(target, "https://npi.example.test"),
    ).toBeNull();
  });

  it("adds one validated return path and reads it without nesting", () => {
    const current = locationFor(
      "/projects/11111111-1111-4111-8111-111111111111?tab=activity",
    );
    const target = buildContextualNavigationTarget("/work", current);
    const targetUrl = new URL(target, current.origin);
    expect(targetUrl.pathname).toBe("/work");
    expect(targetUrl.searchParams.get("returnTo")).toBe(
      "/projects/11111111-1111-4111-8111-111111111111?tab=activity",
    );
    expect(currentReturnTarget(locationFor(target))).toBe(
      "/projects/11111111-1111-4111-8111-111111111111?tab=activity",
    );

    expect(
      buildContextualNavigationTarget(
        "/execution",
        locationFor("/work?returnTo=%2Ftrials%2FT1"),
      ),
    ).toBe("/execution?returnTo=%2Fwork");
  });

  it("navigates without reloading and follows browser history", () => {
    vi.stubGlobal("scrollTo", vi.fn());
    globalThis.history.replaceState({}, "", "/work");
    const { result } = renderHook(() => useAppRouter());

    act(() => {
      result.current.navigate("/tooling/TL-26018-01?scenario=partial");
    });
    expect(result.current.route).toMatchObject({
      screen: "tooling",
      scenario: "partial",
    });
    expect(globalThis.scrollTo).toHaveBeenCalledWith({
      behavior: "auto",
      top: 0,
    });

    globalThis.history.pushState(
      {},
      "",
      "/projects/11111111-1111-4111-8111-111111111111/integration-operations?scenario=processing",
    );
    act(() => {
      globalThis.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current.route).toMatchObject({
      screen: "execution",
      scenario: "normal",
      projectGlobalId: "11111111-1111-4111-8111-111111111111",
    });
  });
});
