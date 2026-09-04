import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ControlledUndoPrototype } from "../../src/components/controlled-undo-prototype";
import {
  controlledUndoPrototypeRequested,
  controlledUndoPrototypeStateFromSearch,
  controlledUndoPrototypeStates,
} from "../../src/components/controlled-undo-prototype-model";
import { renderWithLocale } from "../support/render";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("controlled undo review prototype", () => {
  it("opens only for the exact review query and closes unknown state values", () => {
    expect(
      controlledUndoPrototypeRequested(
        "?prototype=my-work-grid-reset-undo&undoState=available",
      ),
    ).toBe(true);
    expect(controlledUndoPrototypeRequested("?prototype=grid-reset-undo")).toBe(
      false,
    );
    expect(controlledUndoPrototypeRequested("?undoState=available")).toBe(
      false,
    );
    expect(controlledUndoPrototypeStateFromSearch("?undoState=conflict")).toBe(
      "conflict",
    );
    expect(controlledUndoPrototypeStateFromSearch("?undoState=unknown")).toBe(
      "review",
    );
  });

  it("walks the confirmed reset and reconciled undo review without transport", async () => {
    const user = userEvent.setup();
    const fetch = vi.fn<typeof globalThis.fetch>();
    vi.stubGlobal("fetch", fetch);
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    renderWithLocale(<ControlledUndoPrototype />, "en");

    expect(screen.getByText("Prototype only")).toBeVisible();
    expect(
      screen.getByText(
        "This review surface sends no production request and changes no saved settings.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Pending Product Owner approval")).toBeVisible();
    const stateRegion = screen.getByRole("region", {
      name: "Prototype state",
    });
    expect(stateRegion).toHaveAttribute("data-prototype-state", "review");

    await user.click(screen.getByRole("button", { name: "Review reset" }));
    expect(stateRegion).toHaveAttribute("data-prototype-state", "confirmation");
    expect(stateRegion).toHaveFocus();
    expect(
      screen.getByText(
        "Only this personal view would return to code-owned defaults. No business data or shared view would change.",
      ),
    ).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Show reset-confirmed state" }),
    );
    expect(stateRegion).toHaveAttribute("data-prototype-state", "available");
    expect(screen.getByText("10 seconds remaining")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Undo reset" }));
    expect(stateRegion).toHaveAttribute("data-prototype-state", "processing");
    expect(
      screen.getByText(
        "Review state: the undo request is processing. The previous layout is not reported as restored.",
      ),
    ).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Show reconciled result" }),
    );
    expect(stateRegion).toHaveAttribute("data-prototype-state", "restored");
    expect(screen.getByText("Previous personal layout")).toBeVisible();

    expect(
      fetch.mock.calls.map(([request, init]) => ({
        method: init?.method ?? "GET",
        request:
          typeof request === "string"
            ? request
            : request instanceof URL
              ? request.href
              : request.url,
      })),
    ).toEqual([
      {
        method: "GET",
        request: "/api/npi/v1/session/bootstrap",
      },
    ]);
    expect(setItem.mock.calls).toEqual([["npi-one-prototype-locale", "en"]]);
  });

  it.each(controlledUndoPrototypeStates)(
    "renders the closed %s state with a non-hover recovery path",
    (initialState) => {
      renderWithLocale(
        <ControlledUndoPrototype initialState={initialState} />,
        "en",
      );
      expect(
        screen.getByRole("region", { name: "Prototype state" }),
      ).toHaveAttribute("data-prototype-state", initialState);
      expect(
        screen.getByRole("button", {
          name:
            initialState === "review"
              ? "Review reset"
              : initialState === "confirmation"
                ? "Show reset-confirmed state"
                : initialState === "available"
                  ? "Undo reset"
                  : initialState === "processing"
                    ? "Show reconciled result"
                    : initialState === "conflict"
                      ? "Reload prototype state"
                      : initialState === "retryable"
                        ? "Retry prototype state"
                        : "Return to review",
        }),
      ).toBeVisible();
    },
  );

  it.each([
    ["zh" as const, "受控撤销审查原型", "等待产品负责人批准"],
    ["zh-TW" as const, "受控復原審查原型", "等待產品負責人核准"],
  ])("uses direct %s review copy", (locale, title, approval) => {
    renderWithLocale(
      <ControlledUndoPrototype initialState="available" />,
      locale,
    );
    expect(screen.getByRole("heading", { name: title })).toBeVisible();
    expect(screen.getByText(approval)).toBeVisible();
    expect(document.documentElement).toHaveAttribute("lang", locale);
  });
});
