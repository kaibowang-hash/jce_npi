import type {
  ButtonHTMLAttributes,
  ComponentProps,
  InputHTMLAttributes,
  MouseEvent,
  PropsWithChildren,
  SelectHTMLAttributes,
} from "react";
import { forwardRef, useCallback, useEffect, useId, useRef } from "react";
import { IxButton, IxIcon } from "@siemens/ix-react";
import {
  iconAlarmBell,
  iconAdd,
  iconAnalysis,
  iconApps,
  iconCheck,
  iconChevronLeftSmall,
  iconChevronRightSmall,
  iconClear,
  iconDocument,
  iconError,
  iconFilter,
  iconHistory,
  iconQuestion,
  iconInfo,
  iconKeyboard,
  iconMaintenance,
  iconPlay,
  iconProject,
  iconProjects,
  iconRefresh,
  iconSearch,
  iconUpload,
  iconUser,
  iconWarning,
  iconWorkCase,
} from "@siemens/ix-icons/icons";
import "@siemens/ix/dist/siemens-ix/siemens-ix.css";

import {
  assertNpiIconName,
  isIconOnlyAction,
  type CompactActionIntent,
  type CompactActionProminence,
  type NpiIconName,
} from "./action-policy";

export type { NpiIconName } from "./action-policy";

const icons: Record<NpiIconName, string> = {
  add: iconAdd,
  alarm: iconAlarmBell,
  analysis: iconAnalysis,
  apps: iconApps,
  check: iconCheck,
  chevron: iconChevronRightSmall,
  clear: iconClear,
  collapse: iconChevronLeftSmall,
  document: iconDocument,
  error: iconError,
  expand: iconChevronRightSmall,
  filter: iconFilter,
  help: iconQuestion,
  history: iconHistory,
  info: iconInfo,
  keyboard: iconKeyboard,
  maintenance: iconMaintenance,
  play: iconPlay,
  project: iconProject,
  projects: iconProjects,
  refresh: iconRefresh,
  search: iconSearch,
  upload: iconUpload,
  user: iconUser,
  warning: iconWarning,
  work: iconWorkCase,
};

function localIcon(name: NpiIconName): string {
  return icons[assertNpiIconName(name)];
}

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
      name={localIcon(name)}
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
      data-visual={visual}
      data-visual-primary={visual === "primary" ? "true" : "false"}
      disabled={disabled}
      ghost={visual === "ghost"}
      outline={visual === "secondary"}
      ref={setButtonHostRef}
      type={type}
      variant={variant}
    >
      {icon ? (
        <IxIcon aria-hidden={true} name={localIcon(icon)} size="16" />
      ) : null}
      {children}
    </IxButton>
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
}: CompactActionProps): React.JSX.Element {
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

export const TextInput = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function TextInput({ className = "", ...props }, ref): React.JSX.Element {
  return (
    <input className={`npi-input ${className}`.trim()} ref={ref} {...props} />
  );
});

export function Select({
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>): React.JSX.Element {
  return <select className={`npi-select ${className}`.trim()} {...props} />;
}
