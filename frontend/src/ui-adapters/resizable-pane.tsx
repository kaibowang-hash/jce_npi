import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

export interface ResizablePaneSeparatorProps {
  readonly defaultValue: number;
  readonly disabled?: boolean;
  readonly label: string;
  readonly maximum: number;
  readonly minimum: number;
  readonly onCommit: (value: number) => void;
  readonly onPreview: (value: number) => void;
  readonly step?: number;
  readonly title?: string;
  readonly value: number;
}

interface DragState {
  readonly pointerId: number;
  readonly startValue: number;
  readonly startX: number;
}

interface PreviewState {
  readonly baseValue: number;
  readonly value: number;
}

function normalizeInteger(value: number, fallback: number): number {
  return Number.isFinite(value) ? Math.round(value) : fallback;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, normalizeInteger(value, minimum)));
}

function pointerIdentity(value: number): number {
  return Number.isInteger(value) ? value : 0;
}

function invokePointerCapture(
  target: HTMLDivElement,
  method: "releasePointerCapture" | "setPointerCapture",
  pointerId: number,
): void {
  const candidate: unknown = Reflect.get(target, method);
  if (typeof candidate === "function") {
    Reflect.apply(candidate, target, [pointerId]);
  }
}

export function ResizablePaneSeparator({
  defaultValue,
  disabled = false,
  label,
  maximum,
  minimum,
  onCommit,
  onPreview,
  step = 20,
  title,
  value,
}: ResizablePaneSeparatorProps): React.JSX.Element {
  const safeMinimum = normalizeInteger(minimum, 0);
  const safeMaximum = Math.max(
    safeMinimum,
    normalizeInteger(maximum, safeMinimum),
  );
  const safeValue = clamp(value, safeMinimum, safeMaximum);
  const safeDefaultValue = clamp(defaultValue, safeMinimum, safeMaximum);
  const safeStep = Math.max(1, normalizeInteger(step, 20));
  const dragState = useRef<DragState | null>(null);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const displayedValue =
    preview?.baseValue === safeValue ? preview.value : safeValue;

  const cancelDrag = (target: HTMLDivElement, active: DragState): void => {
    dragState.current = null;
    invokePointerCapture(target, "releasePointerCapture", active.pointerId);
    setPreview(null);
    onPreview(safeValue);
  };

  const commit = (candidate: number, confirmedValue = safeValue): void => {
    const nextValue = clamp(candidate, safeMinimum, safeMaximum);
    setPreview(null);
    onPreview(nextValue);
    if (nextValue !== confirmedValue) {
      onCommit(nextValue);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    const active = dragState.current;
    if (event.key === "Escape" && active !== null) {
      event.preventDefault();
      cancelDrag(event.currentTarget, active);
      return;
    }
    if (disabled) return;
    let nextValue: number | null = null;
    if (event.key === "ArrowLeft") {
      nextValue = safeValue + safeStep;
    } else if (event.key === "ArrowRight") {
      nextValue = safeValue - safeStep;
    } else if (event.key === "Home") {
      nextValue = safeMinimum;
    } else if (event.key === "End") {
      nextValue = safeMaximum;
    }
    if (nextValue === null) return;
    event.preventDefault();
    commit(nextValue);
  };

  return (
    <div
      aria-disabled={disabled || undefined}
      aria-label={label}
      aria-orientation="vertical"
      aria-valuemax={safeMaximum}
      aria-valuemin={safeMinimum}
      aria-valuenow={displayedValue}
      className="resizable-pane-separator"
      onDoubleClick={(event) => {
        if (disabled) return;
        event.preventDefault();
        commit(safeDefaultValue);
      }}
      onKeyDown={handleKeyDown}
      onLostPointerCapture={(event) => {
        const active = dragState.current;
        if (active?.pointerId !== pointerIdentity(event.pointerId)) {
          return;
        }
        dragState.current = null;
        setPreview(null);
        onPreview(safeValue);
      }}
      onPointerCancel={(event) => {
        const active = dragState.current;
        if (active?.pointerId !== pointerIdentity(event.pointerId)) {
          return;
        }
        cancelDrag(event.currentTarget, active);
      }}
      onPointerDown={(event: PointerEvent<HTMLDivElement>) => {
        if (disabled || dragState.current !== null) return;
        if (Number.isFinite(event.button) && event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.focus();
        setPreview(null);
        const pointerId = pointerIdentity(event.pointerId);
        invokePointerCapture(
          event.currentTarget,
          "setPointerCapture",
          pointerId,
        );
        dragState.current = {
          pointerId,
          startValue: safeValue,
          startX: event.clientX,
        };
      }}
      onPointerMove={(event: PointerEvent<HTMLDivElement>) => {
        const active = dragState.current;
        if (
          disabled ||
          active?.pointerId !== pointerIdentity(event.pointerId)
        ) {
          return;
        }
        if (safeValue !== active.startValue) {
          cancelDrag(event.currentTarget, active);
          return;
        }
        const nextValue = clamp(
          active.startValue + active.startX - event.clientX,
          safeMinimum,
          safeMaximum,
        );
        setPreview({ baseValue: safeValue, value: nextValue });
        onPreview(nextValue);
      }}
      onPointerUp={(event: PointerEvent<HTMLDivElement>) => {
        const active = dragState.current;
        if (
          disabled ||
          active?.pointerId !== pointerIdentity(event.pointerId)
        ) {
          return;
        }
        if (safeValue !== active.startValue) {
          cancelDrag(event.currentTarget, active);
          return;
        }
        const nextValue = clamp(
          active.startValue + active.startX - event.clientX,
          safeMinimum,
          safeMaximum,
        );
        dragState.current = null;
        invokePointerCapture(
          event.currentTarget,
          "releasePointerCapture",
          active.pointerId,
        );
        commit(nextValue, active.startValue);
      }}
      role="separator"
      tabIndex={disabled ? -1 : 0}
      title={title}
    />
  );
}
