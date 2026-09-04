import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { ResizablePaneSeparator } from "../../src/ui-adapters/resizable-pane";

function dispatchPointer(
  element: Element,
  type:
    | "lostpointercapture"
    | "pointercancel"
    | "pointerdown"
    | "pointermove"
    | "pointerup",
  properties: {
    button?: number;
    clientX: number;
    pointerId: number;
  },
): void {
  const event = new Event(type, { bubbles: true, cancelable: true });
  for (const [name, value] of Object.entries(properties)) {
    Object.defineProperty(event, name, { value });
  }
  fireEvent(element, event);
}

function ControlledSeparator({
  disabled = false,
  initialValue = 340,
  onCommit,
  onPreview,
  step,
}: {
  readonly disabled?: boolean;
  readonly initialValue?: number;
  readonly onCommit: (value: number) => void;
  readonly onPreview: (value: number) => void;
  readonly step?: number;
}): React.JSX.Element {
  const [confirmedValue, setConfirmedValue] = useState(initialValue);
  return (
    <ResizablePaneSeparator
      defaultValue={340}
      disabled={disabled}
      label="Resize inspector"
      maximum={480}
      minimum={260}
      onCommit={(nextValue) => {
        setConfirmedValue(nextValue);
        onCommit(nextValue);
      }}
      onPreview={onPreview}
      {...(step === undefined ? {} : { step })}
      title="Drag or use arrow keys"
      value={confirmedValue}
    />
  );
}

describe("ResizablePaneSeparator", () => {
  it("previews left-edge geometry and commits one bounded width on pointerup", () => {
    const onPreview = vi.fn<(value: number) => void>();
    const onCommit = vi.fn<(value: number) => void>();
    render(<ControlledSeparator onCommit={onCommit} onPreview={onPreview} />);
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });
    const setPointerCapture = vi.fn();
    const releasePointerCapture = vi.fn();
    Object.defineProperties(separator, {
      releasePointerCapture: { value: releasePointerCapture },
      setPointerCapture: { value: setPointerCapture },
    });

    expect(separator).toHaveAttribute("aria-orientation", "vertical");
    expect(separator).toHaveAttribute("aria-valuemin", "260");
    expect(separator).toHaveAttribute("aria-valuemax", "480");
    expect(separator).toHaveAttribute("aria-valuenow", "340");
    expect(separator).toHaveAttribute("title", "Drag or use arrow keys");

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 400,
      pointerId: 7,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 360,
      pointerId: 7,
    });
    expect(separator).toHaveAttribute("aria-valuenow", "380");
    expect(onCommit).not.toHaveBeenCalled();

    dispatchPointer(separator, "pointermove", {
      clientX: 0,
      pointerId: 7,
    });
    expect(separator).toHaveAttribute("aria-valuenow", "480");
    dispatchPointer(separator, "pointerup", {
      clientX: 370,
      pointerId: 7,
    });

    expect(setPointerCapture).toHaveBeenCalledWith(7);
    expect(releasePointerCapture).toHaveBeenCalledWith(7);
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith(370);
    expect(separator).toHaveAttribute("aria-valuenow", "370");
  });

  it("cancels pointer previews to the confirmed value on Escape and capture loss", () => {
    const onPreview = vi.fn<(value: number) => void>();
    const onCommit = vi.fn<(value: number) => void>();
    render(<ControlledSeparator onCommit={onCommit} onPreview={onPreview} />);
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });
    Object.defineProperties(separator, {
      releasePointerCapture: { value: vi.fn() },
      setPointerCapture: { value: vi.fn() },
    });

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 400,
      pointerId: 8,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 360,
      pointerId: 8,
    });
    expect(separator).toHaveAttribute("aria-valuenow", "380");
    fireEvent.keyDown(separator, { key: "Escape" });
    expect(separator).toHaveAttribute("aria-valuenow", "340");
    expect(onPreview).toHaveBeenLastCalledWith(340);
    expect(onCommit).not.toHaveBeenCalled();

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 400,
      pointerId: 9,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 320,
      pointerId: 9,
    });
    expect(separator).toHaveAttribute("aria-valuenow", "420");
    dispatchPointer(separator, "lostpointercapture", {
      clientX: 320,
      pointerId: 9,
    });
    expect(separator).toHaveAttribute("aria-valuenow", "340");
    expect(onPreview).toHaveBeenLastCalledWith(340);
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("cancels to a newer controlled value confirmed during an active drag", () => {
    const onPreview = vi.fn<(value: number) => void>();
    const onCommit = vi.fn<(value: number) => void>();
    const props = {
      defaultValue: 340,
      label: "Resize inspector",
      maximum: 480,
      minimum: 260,
      onCommit,
      onPreview,
    };
    const { rerender } = render(
      <ResizablePaneSeparator {...props} value={340} />,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });
    Object.defineProperties(separator, {
      releasePointerCapture: { value: vi.fn() },
      setPointerCapture: { value: vi.fn() },
    });

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 400,
      pointerId: 17,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 360,
      pointerId: 17,
    });
    rerender(<ResizablePaneSeparator {...props} value={380} />);
    fireEvent.keyDown(separator, { key: "Escape" });

    expect(onPreview).toHaveBeenLastCalledWith(380);
    expect(onCommit).not.toHaveBeenCalled();

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 400,
      pointerId: 18,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 360,
      pointerId: 18,
    });
    rerender(<ResizablePaneSeparator {...props} value={420} />);
    dispatchPointer(separator, "lostpointercapture", {
      clientX: 360,
      pointerId: 18,
    });

    expect(onPreview).toHaveBeenLastCalledWith(420);
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("does not let a stale active drag overwrite a newer controlled value", () => {
    const onPreview = vi.fn<(value: number) => void>();
    const onCommit = vi.fn<(value: number) => void>();
    const props = {
      defaultValue: 340,
      label: "Resize inspector",
      maximum: 480,
      minimum: 260,
      onCommit,
      onPreview,
    };
    const { rerender } = render(
      <ResizablePaneSeparator {...props} value={340} />,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });
    Object.defineProperties(separator, {
      releasePointerCapture: { value: vi.fn() },
      setPointerCapture: { value: vi.fn() },
    });

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 400,
      pointerId: 19,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 360,
      pointerId: 19,
    });
    rerender(<ResizablePaneSeparator {...props} value={420} />);
    dispatchPointer(separator, "pointerup", {
      clientX: 360,
      pointerId: 19,
    });

    expect(onPreview).toHaveBeenLastCalledWith(420);
    expect(onCommit).not.toHaveBeenCalled();
    expect(separator).toHaveAttribute("aria-valuenow", "420");
  });

  it("expands left, contracts right, reaches bounds, and resets by keyboard or double-click", () => {
    const onPreview = vi.fn<(value: number) => void>();
    const onCommit = vi.fn<(value: number) => void>();
    render(<ControlledSeparator onCommit={onCommit} onPreview={onPreview} />);
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });

    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    fireEvent.keyDown(separator, { key: "ArrowRight" });
    fireEvent.keyDown(separator, { key: "Home" });
    fireEvent.keyDown(separator, { key: "End" });
    fireEvent.doubleClick(separator);

    expect(onCommit.mock.calls.map(([value]) => value)).toEqual([
      360, 340, 260, 480, 340,
    ]);
    expect(onPreview.mock.calls.map(([value]) => value)).toEqual([
      360, 340, 260, 480, 340,
    ]);
    expect(separator).toHaveAttribute("aria-valuenow", "340");
  });

  it("uses a bounded 20px default step and suppresses boundary no-ops", () => {
    const onPreview = vi.fn<(value: number) => void>();
    const onCommit = vi.fn<(value: number) => void>();
    render(
      <ControlledSeparator
        initialValue={470}
        onCommit={onCommit}
        onPreview={onPreview}
      />,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });

    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    fireEvent.keyDown(separator, { key: "ArrowLeft" });

    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith(480);
    expect(separator).toHaveAttribute("aria-valuenow", "480");
  });

  it("removes pointer, keyboard, and reset mutation paths while disabled", () => {
    const onPreview = vi.fn<(value: number) => void>();
    const onCommit = vi.fn<(value: number) => void>();
    render(
      <ControlledSeparator
        disabled
        onCommit={onCommit}
        onPreview={onPreview}
      />,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });

    expect(separator).toHaveAttribute("aria-disabled", "true");
    expect(separator).toHaveAttribute("tabindex", "-1");
    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    fireEvent.doubleClick(separator);
    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 400,
      pointerId: 10,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 300,
      pointerId: 10,
    });
    dispatchPointer(separator, "pointerup", {
      clientX: 300,
      pointerId: 10,
    });

    expect(onPreview).not.toHaveBeenCalled();
    expect(onCommit).not.toHaveBeenCalled();
    expect(separator).toHaveAttribute("aria-valuenow", "340");
  });
});
