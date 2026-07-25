import type {
  ButtonHTMLAttributes,
  ComponentProps,
  InputHTMLAttributes,
  MouseEvent,
  PropsWithChildren,
  SelectHTMLAttributes,
} from "react";
import { useCallback, useEffect, useRef } from "react";
import { IxButton, IxIcon } from "@siemens/ix-react";
import {
  iconAlarmBell,
  iconCheck,
  iconChevronRightSmall,
  iconError,
  iconFilter,
  iconQuestion,
  iconInfo,
  iconRefresh,
  iconSearch,
  iconUser,
  iconWarning,
} from "@siemens/ix-icons/icons";
import "@siemens/ix/dist/siemens-ix/siemens-ix.css";

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

const icons: Record<NpiIconName, string> = {
  alarm: iconAlarmBell,
  check: iconCheck,
  chevron: iconChevronRightSmall,
  error: iconError,
  filter: iconFilter,
  help: iconQuestion,
  info: iconInfo,
  refresh: iconRefresh,
  search: iconSearch,
  user: iconUser,
  warning: iconWarning,
};

type HydratableElement = HTMLElement & {
  componentOnReady?: () => Promise<unknown>;
};

type ShadowAriaAttribute = readonly [name: string, value: string];

function partitionButtonProperties(properties: object): {
  hostProperties: Record<string, unknown>;
  shadowAriaAttributes: ShadowAriaAttribute[];
} {
  const hostProperties: Record<string, unknown> = {};
  const shadowAriaAttributes: ShadowAriaAttribute[] = [];

  for (const [name, value] of Object.entries(properties)) {
    if (name.startsWith("aria-")) {
      if (value !== undefined && value !== null) {
        shadowAriaAttributes.push([name, String(value)]);
      }
      continue;
    }
    hostProperties[name] = value;
  }

  return { hostProperties, shadowAriaAttributes };
}

/**
 * Focus a control through the local UI adapter boundary.
 *
 * iX buttons are Stencil web components. Focusing their host before hydration
 * does not reliably forward focus to the native button in the shadow root, so
 * callers that manage keyboard focus must wait for the component to be ready.
 */
export async function focusControl(element: HTMLElement | null): Promise<void> {
  if (!element) return;

  // Preserve synchronous focus for native controls and test adapters.
  element.focus();
  if (element.localName !== "ix-button") return;

  await globalThis.customElements.whenDefined("ix-button");
  await (element as HydratableElement).componentOnReady?.();
  if (!element.isConnected) return;

  element.focus();
  element.shadowRoot?.querySelector<HTMLButtonElement>("button")?.focus();
}

export function Icon({
  name,
  label,
}: {
  name: NpiIconName;
  label?: string;
}): React.JSX.Element {
  return (
    <IxIcon
      aria-hidden={label ? undefined : true}
      aria-label={label}
      name={icons[name]}
      size="16"
    />
  );
}

type ButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "color" | "onClick" | "type"
> & {
  visual?: "primary" | "secondary" | "danger" | "ghost";
  icon?: NpiIconName;
  onClick?: (event: MouseEvent<HTMLElement>) => void;
  type?: "button" | "submit";
};

export function Button({
  children,
  visual = "secondary",
  icon,
  className = "",
  ...props
}: PropsWithChildren<ButtonProps>): React.JSX.Element {
  const {
    "aria-label": ariaLabel,
    disabled = false,
    onClick,
    type = "button",
    ...hostProperties
  } = props;
  const buttonHostRef = useRef<HydratableElement | null>(null);
  const synchronizedAriaNamesRef = useRef<Set<string>>(new Set());
  const setButtonHostRef = useCallback((element: HTMLElement | null) => {
    buttonHostRef.current = element;
  }, []);
  const { hostProperties: nonAriaHostProperties, shadowAriaAttributes } =
    partitionButtonProperties(hostProperties);

  useEffect(() => {
    let cancelled = false;
    const host = buttonHostRef.current;

    async function synchronizeShadowButtonAria(): Promise<void> {
      if (!host) return;

      await globalThis.customElements.whenDefined("ix-button");
      await host.componentOnReady?.();
      if (cancelled || buttonHostRef.current !== host || !host.isConnected) {
        return;
      }

      const nativeButton =
        host.shadowRoot?.querySelector<HTMLButtonElement>("button");
      if (!nativeButton) return;

      const nextNames = new Set(shadowAriaAttributes.map(([name]) => name));
      for (const name of synchronizedAriaNamesRef.current) {
        if (!nextNames.has(name)) nativeButton.removeAttribute(name);
      }
      for (const [name, value] of shadowAriaAttributes) {
        nativeButton.setAttribute(name, value);
      }
      synchronizedAriaNamesRef.current = nextNames;
    }

    void synchronizeShadowButtonAria();
    return () => {
      cancelled = true;
    };
  });

  const variant =
    visual === "danger"
      ? "danger"
      : visual === "primary"
        ? "primary"
        : "secondary";
  const forwardedProperties = nonAriaHostProperties as ComponentProps<
    typeof IxButton
  >;
  return (
    <IxButton
      {...forwardedProperties}
      {...(ariaLabel ? { ariaLabelButton: ariaLabel } : {})}
      {...(onClick ? { onClick } : {})}
      className={`npi-button ${className}`.trim()}
      data-visual-primary={visual === "primary" ? "true" : "false"}
      disabled={disabled}
      ghost={visual === "ghost"}
      outline={visual === "secondary"}
      ref={setButtonHostRef}
      type={type}
      variant={variant}
    >
      {icon ? <IxIcon aria-hidden={true} name={icons[icon]} size="16" /> : null}
      {children}
    </IxButton>
  );
}

export function TextInput({
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement>): React.JSX.Element {
  return <input className={`npi-input ${className}`.trim()} {...props} />;
}

export function Select({
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>): React.JSX.Element {
  return <select className={`npi-select ${className}`.trim()} {...props} />;
}
