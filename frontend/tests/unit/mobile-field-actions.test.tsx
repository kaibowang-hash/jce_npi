import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  MobileEngineeringHandoff,
  ReviewedScanEntry,
  type AuthorizedScanReference,
} from "../../src/components/mobile-field-actions";
import { renderWithLocale } from "../support/render";

const references: readonly AuthorizedScanReference[] = [
  { label: "Cavity A", value: "CAV-A" },
  { label: "Cavity B", value: "CAV-B" },
];

describe("P7-08 mobile field actions", () => {
  it("separates exact reference review from explicit apply and invalidates changed input", async () => {
    const user = userEvent.setup();
    const onApply = vi.fn();
    const { container } = renderWithLocale(
      <ReviewedScanEntry onApply={onApply} references={references} />,
    );
    const input = screen.getByLabelText("Scanned value");

    await user.type(input, "  CAV-A  ");
    await user.click(
      screen.getByRole("button", { name: "Review scanned value" }),
    );

    expect(onApply).not.toHaveBeenCalled();
    expect(screen.getByText("Cavity A")).toBeVisible();
    expect(screen.getByText("CAV-A")).toHaveAttribute(
      "data-language-exempt",
      "identifier",
    );
    expect(
      screen.getByText("Ready to use. No command has been submitted."),
    ).toBeVisible();
    expect(
      container.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);

    await user.click(
      screen.getByRole("button", { name: "Use reviewed value" }),
    );
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledWith(references[0]);
    expect(
      screen.getByText("Reference applied. No command has been submitted."),
    ).toBeVisible();

    await user.clear(input);
    await user.type(input, "CAV-B");
    expect(screen.queryByText("Cavity A")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Use reviewed value" }),
    ).not.toBeInTheDocument();
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("fails closed for empty, unknown, ambiguous, control and overlong values", async () => {
    const user = userEvent.setup();
    const onApply = vi.fn();
    renderWithLocale(
      <ReviewedScanEntry
        onApply={onApply}
        references={[
          ...references,
          { label: "Duplicate cavity", value: "CAV-A" },
        ]}
      />,
    );
    const input = screen.getByLabelText("Scanned value");
    const review = screen.getByRole("button", {
      name: "Review scanned value",
    });

    await user.click(review);
    expect(screen.getByText("Enter a reference before review.")).toBeVisible();

    await user.type(input, "MISSING");
    await user.click(review);
    expect(
      screen.getByText("No authorized reference matches this value."),
    ).toBeVisible();

    await user.clear(input);
    await user.type(input, "CAV-A");
    await user.click(review);
    expect(
      screen.getByText(
        "More than one authorized reference matches this value.",
      ),
    ).toBeVisible();

    fireEvent.change(input, { target: { value: "CAV-A\u0001" } });
    await user.click(review);
    expect(
      screen.getByText(
        "The scanned value contains unsupported control characters.",
      ),
    ).toBeVisible();

    fireEvent.change(input, { target: { value: "X".repeat(129) } });
    await user.click(review);
    expect(screen.getByText("The scanned value is too long.")).toBeVisible();
    expect(onApply).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: "Use reviewed value" }),
    ).not.toBeInTheDocument();
  });

  it("keeps unavailable scan entry explicit and non-interactive", () => {
    const onApply = vi.fn();
    renderWithLocale(
      <ReviewedScanEntry disabled onApply={onApply} references={references} />,
    );

    expect(screen.getByLabelText("Scanned value")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Review scanned value" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Scan entry is unavailable in this state."),
    ).toBeVisible();
    expect(onApply).not.toHaveBeenCalled();
  });

  it.each([
    ["zh", "已评审扫描录入", "桌面端工程分析", "同一授权工作区"],
    ["zh-TW", "已評審掃描輸入", "桌面工程分析", "相同授權工作區"],
  ] as const)(
    "renders direct reviewed-scan and desktop-handoff copy in %s",
    (locale, scanTitle, handoffTitle, workspaceLabel) => {
      renderWithLocale(
        <>
          <ReviewedScanEntry onApply={vi.fn()} references={references} />
          <MobileEngineeringHandoff />
        </>,
        locale,
      );

      expect(screen.getByText(scanTitle)).toBeVisible();
      expect(screen.getByText(handoffTitle)).toBeVisible();
      expect(screen.getByText(workspaceLabel)).toBeVisible();
      expect(document.body.textContent).not.toContain("⟦Missing:");
    },
  );
});
