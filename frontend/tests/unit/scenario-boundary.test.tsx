import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ScenarioBoundary } from "../../src/components/scenario-boundary";
import { scenarios } from "../../src/fixtures/prototype";
import { renderWithLocale } from "../support/render";

describe("core page scenario boundary", () => {
  it("renders the normal workspace without an artificial state surface", () => {
    const { container } = renderWithLocale(
      <ScenarioBoundary scenario="normal">
        <div>fixture child</div>
      </ScenarioBoundary>,
    );
    expect(screen.getByText("fixture child")).toBeVisible();
    expect(container.querySelector(".state-surface")).not.toBeInTheDocument();
  });

  it.each(["read_only", "partial", "dirty"] as const)(
    "keeps contextual work visible under the %s banner",
    (scenario) => {
      const { container } = renderWithLocale(
        <ScenarioBoundary scenario={scenario}>
          <div>fixture child</div>
        </ScenarioBoundary>,
      );
      expect(screen.getByText("fixture child")).toBeVisible();
      expect(
        container.querySelector(`.scenario-banner--${scenario}`),
      ).toHaveAttribute("role", "status");
    },
  );

  it("exposes a labelled busy skeleton while loading", () => {
    renderWithLocale(
      <ScenarioBoundary scenario="loading">
        <div>fixture child</div>
      </ScenarioBoundary>,
    );
    expect(screen.getByLabelText("Loading")).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(screen.queryByText("fixture child")).not.toBeInTheDocument();
  });

  it.each(
    scenarios.filter(
      (scenario) =>
        !["normal", "read_only", "partial", "dirty", "loading"].includes(
          scenario,
        ),
    ),
  )("renders an honest, actionable %s terminal state", (scenario) => {
    renderWithLocale(
      <ScenarioBoundary scenario={scenario}>
        <div>fixture child</div>
      </ScenarioBoundary>,
    );
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("trc-phase3-fixture");
    expect(status.querySelector("button")).toBeEnabled();
    expect(screen.queryByText("fixture child")).not.toBeInTheDocument();
  });

  it.each(["zh", "zh-TW"] as const)(
    "does not silently fall back for %s state copy",
    (locale) => {
      renderWithLocale(
        <ScenarioBoundary scenario="failed_retryable" />,
        locale,
      );
      expect(document.body).not.toHaveTextContent("⟦Missing:");
      expect(document.body.textContent).not.toMatch(/\bRetry\b/);
    },
  );

  it("reveals substantive conflict details without replacing either version", async () => {
    const user = userEvent.setup();
    renderWithLocale(<ScenarioBoundary scenario="conflict" />);

    await user.click(
      screen.getByRole("button", { name: "Review differences" }),
    );
    expect(
      screen.getByText(
        "Prototype comparison: server version v4 differs from draft v3. Neither version was replaced.",
      ),
    ).toBeVisible();
  });

  it("renders localized field errors from the Problem Details contract", async () => {
    const user = userEvent.setup();
    renderWithLocale(<ScenarioBoundary scenario="validation" />);

    await user.click(screen.getByRole("button", { name: "Review fields" }));
    const details = screen.getByRole("alert", { name: "Error details" });
    expect(details).toHaveTextContent("governedValue");
    expect(details).toHaveTextContent("Select an approved governed value.");
    expect(details).toHaveTextContent("trc-phase3-fixture");
  });

  it("restores the normal URL for retry and routes denied users to My Work", async () => {
    const user = userEvent.setup();
    const first = renderWithLocale(
      <ScenarioBoundary scenario="error" />,
      "en",
      "/execution?scenario=error",
    );
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(globalThis.location.pathname).toBe("/execution");
    expect(
      new URLSearchParams(globalThis.location.search).has("scenario"),
    ).toBe(false);

    first.unmount();
    renderWithLocale(
      <ScenarioBoundary scenario="no_permission" />,
      "en",
      "/projects/PJ-26018?scenario=no_permission",
    );
    await user.click(screen.getByRole("button", { name: "Return to My Work" }));
    expect(globalThis.location.pathname).toBe("/work");
  });
});
