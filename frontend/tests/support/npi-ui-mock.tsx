import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  JSX,
  PropsWithChildren,
  SelectHTMLAttributes,
} from "react";

export type NpiIconName =
  | "alarm"
  | "check"
  | "chevron"
  | "error"
  | "filter"
  | "help"
  | "info"
  | "refresh"
  | "search"
  | "user"
  | "warning";

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
      data-visual-primary={visual === "primary" ? "true" : undefined}
      {...properties}
    >
      {children}
    </button>
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

export function TextInput(
  properties: InputHTMLAttributes<HTMLInputElement>,
): JSX.Element {
  return <input {...properties} />;
}

export function Select(
  properties: SelectHTMLAttributes<HTMLSelectElement>,
): JSX.Element {
  return <select {...properties} />;
}
