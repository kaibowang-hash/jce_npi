import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { parseRoute, useAppRouter } from "../../src/app/router";

function locationFor(path: string): Location {
  return new URL(path, "https://npi.example.test") as unknown as Location;
}

describe("application routing", () => {
  it.each([
    ["/work", "work"],
    ["/projects/PJ-26018", "project"],
    ["/projects/PJ-26018/gates/G5", "gate"],
    ["/tooling/TL-26018-01", "tooling"],
    ["/trials/T1", "trial"],
    ["/execution", "execution"],
  ] as const)("maps %s to the %s screen", (path, screen) => {
    expect(parseRoute(locationFor(path)).screen).toBe(screen);
  });

  it("normalizes unknown scenarios and preserves the quality-failure fixture", () => {
    expect(
      parseRoute(locationFor("/execution?scenario=unknown")).scenario,
    ).toBe("normal");
    expect(
      parseRoute(
        locationFor(
          "/projects/PJ-26018/gates/G6?scenario=error&quality=failed",
        ),
      ),
    ).toMatchObject({
      qualityFailure: true,
      scenario: "error",
      screen: "gate",
    });
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

    globalThis.history.pushState({}, "", "/execution?scenario=processing");
    act(() => {
      globalThis.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current.route).toMatchObject({
      screen: "execution",
      scenario: "processing",
    });
  });
});
