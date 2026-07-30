import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CompactAction } from "../../src/ui-adapters/npi-ui";

describe("CompactAction", () => {
  it("exposes a translated accessible name, tooltip, focus, and keyboard path", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <CompactAction
        icon="clear"
        intent="familiar-low-risk"
        label="Clear local selection"
        onClick={onClick}
      />,
    );

    const button = screen.getByRole("button", {
      name: "Clear local selection",
    });
    const tooltip = screen.getByRole("tooltip", {
      name: "Clear local selection",
    });
    expect(button).toHaveAttribute("title", "Clear local selection");
    expect(button).toHaveAttribute("aria-describedby", tooltip.id);
    expect(button.parentElement).toHaveAttribute("data-icon-action", "true");
    expect(button).toHaveAttribute("data-icon", "clear");
    expect(button).toHaveTextContent("");

    await user.tab();
    expect(button).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("keeps a disabled compact action disabled without removing its name", () => {
    render(
      <CompactAction
        disabled
        icon="expand"
        intent="familiar-low-risk"
        label="Expand inspector"
      />,
    );

    const button = screen.getByRole("button", { name: "Expand inspector" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Expand inspector");
    expect(button.parentElement).toHaveAttribute("data-icon-action", "true");
  });

  it("retains visible labels for primary, ambiguous, and high-risk actions", () => {
    render(
      <>
        <CompactAction
          icon="upload"
          intent="familiar-low-risk"
          label="Start file transport"
          prominence="primary"
        />
        <CompactAction
          icon="refresh"
          intent="ambiguous"
          label="Reload attachment truth"
        />
        <CompactAction
          icon="clear"
          intent="high-risk"
          label="Delete registered attachment"
        />
      </>,
    );

    const primary = screen.getByRole("button", {
      name: "Start file transport",
    });
    const ambiguous = screen.getByRole("button", {
      name: "Reload attachment truth",
    });
    const highRisk = screen.getByRole("button", {
      name: "Delete registered attachment",
    });
    expect(primary).toHaveTextContent("Start file transport");
    expect(primary).toHaveAttribute("data-visual", "primary");
    expect(ambiguous).toHaveTextContent("Reload attachment truth");
    expect(ambiguous).toHaveAttribute("data-visual", "secondary");
    expect(highRisk).toHaveTextContent("Delete registered attachment");
    expect(highRisk).toHaveAttribute("data-visual", "danger");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});
