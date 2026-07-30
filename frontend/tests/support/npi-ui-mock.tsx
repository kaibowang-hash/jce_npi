import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  JSX,
  PropsWithChildren,
  SelectHTMLAttributes,
} from "react";
import { forwardRef, useId } from "react";

import {
  isIconOnlyAction,
  type CompactActionIntent,
  type CompactActionProminence,
  type NpiIconName,
} from "../../src/ui-adapters/action-policy";

export type { NpiIconName } from "../../src/ui-adapters/action-policy";

// The test adapter intentionally mirrors both component and imperative exports.
// eslint-disable-next-line react-refresh/only-export-components
export function focusControl(element: HTMLElement | null): Promise<void> {
  element?.focus();
  return Promise.resolve();
}

type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "color"> & {
  visual?: "primary" | "secondary" | "danger" | "ghost";
  icon?: NpiIconName;
};

export function Button({
  children,
  visual = "secondary",
  icon,
  ...properties
}: PropsWithChildren<ButtonProps>): JSX.Element {
  return (
    <button
      data-icon={icon}
      data-visual={visual}
      data-visual-primary={visual === "primary" ? "true" : undefined}
      {...properties}
    >
      {children}
    </button>
  );
}

type CompactActionProps = Omit<
  ButtonProps,
  "aria-label" | "children" | "icon" | "visual"
> & {
  readonly icon: NpiIconName;
  readonly intent: CompactActionIntent;
  readonly label: string;
  readonly prominence?: CompactActionProminence;
  readonly tooltipPlacement?: "bottom" | "bottom-end" | "bottom-start" | "left";
};

export function CompactAction({
  className = "",
  icon,
  intent,
  label,
  prominence = "secondary",
  tooltipPlacement = "bottom",
  ...properties
}: CompactActionProps): JSX.Element {
  const generatedId = useId().replaceAll(":", "");
  const tooltipId = `npi-icon-action-${generatedId}`;
  const iconOnly = isIconOnlyAction(intent, prominence);
  const visual =
    intent === "high-risk"
      ? "danger"
      : prominence === "primary"
        ? "primary"
        : "secondary";

  if (!iconOnly) {
    return (
      <Button {...properties} className={className} icon={icon} visual={visual}>
        {label}
      </Button>
    );
  }

  return (
    <span
      className="npi-icon-action"
      data-icon-action="true"
      data-tooltip-placement={tooltipPlacement}
    >
      <Button
        {...properties}
        aria-describedby={tooltipId}
        aria-label={label}
        className={`npi-icon-action__button ${className}`.trim()}
        icon={icon}
        title={label}
        visual="ghost"
      />
      <span className="npi-icon-action__tooltip" id={tooltipId} role="tooltip">
        {label}
      </span>
    </span>
  );
}

export function Icon({
  name,
  label,
}: {
  name: NpiIconName;
  label?: string;
}): JSX.Element {
  return (
    <span
      aria-hidden={label ? undefined : true}
      aria-label={label}
      data-icon={name}
    >
      {label}
    </span>
  );
}

export const TextInput = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function TextInput(properties, ref): JSX.Element {
  return <input ref={ref} {...properties} />;
});

export function Select(
  properties: SelectHTMLAttributes<HTMLSelectElement>,
): JSX.Element {
  return <select {...properties} />;
}
