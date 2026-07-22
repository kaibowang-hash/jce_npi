import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

vi.mock("../src/ui-adapters/npi-ui", () => import("./support/npi-ui-mock"));

class ResizeObserverStub implements ResizeObserver {
  disconnect(): void {
    return undefined;
  }
  observe(): void {
    return undefined;
  }
  unobserve(): void {
    return undefined;
  }
}

globalThis.ResizeObserver = ResizeObserverStub;

beforeEach(() => {
  globalThis.localStorage.clear();
  globalThis.history.replaceState({}, "", "/");
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.reject(
        new Error("No Frappe Site is active in the component-test fixture."),
      ),
    ),
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
