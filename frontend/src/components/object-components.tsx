import {
  useEffect,
  useRef,
  useState,
  type PropsWithChildren,
  type ReactNode,
} from "react";

import type { RequestFailure } from "../api/http";
import type {
  ActivityEvent,
  GateStep,
  LifecycleStep,
  SemanticTone,
  SourceStatus,
} from "../domain/view-models";
import { activityLabel, gateLabel, lifecycleLabel } from "../i18n/copy";
import { formatDateTime } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, CompactAction, focusControl } from "../ui-adapters/npi-ui";
import { ResizablePaneSeparator } from "../ui-adapters/resizable-pane";
import { RequestFailurePanel } from "./problem-details-panel";
import { Panel, SemanticStatus, SourceBadge, SyncBadge } from "./primitives";

export function ObjectHeader({
  code,
  name,
  metadata,
  status,
  source,
  secondaryAction,
  primaryAction,
  nameIsBusinessData = true,
}: {
  code: string;
  name: string;
  metadata: ReactNode;
  status: ReactNode;
  source: SourceStatus;
  secondaryAction?: ReactNode;
  primaryAction?:
    | {
        label: string;
        onClick: () => void;
        disabled?: boolean;
        id?: string;
      }
    | undefined;
  nameIsBusinessData?: boolean;
}): React.JSX.Element {
  return (
    <header className="object-header">
      <div className="object-header__identity">
        <div className="object-header__title-row">
          <h1>
            <span data-language-exempt="identifier">{code}</span>{" "}
            <span
              data-language-exempt={
                nameIsBusinessData ? "business-data" : undefined
              }
            >
              {name}
            </span>
          </h1>
          {status}
        </div>
        <div className="object-header__metadata">{metadata}</div>
        <div className="object-header__provenance">
          <SourceBadge source={source} />
          <SyncBadge state={source.syncState} />
        </div>
      </div>
      {secondaryAction ? (
        <div className="object-header__actions">
          {secondaryAction}
          {primaryAction ? (
            <Button
              disabled={primaryAction.disabled}
              id={primaryAction.id}
              onClick={primaryAction.onClick}
              visual="primary"
            >
              {primaryAction.label}
            </Button>
          ) : null}
        </div>
      ) : primaryAction ? (
        <Button
          disabled={primaryAction.disabled}
          id={primaryAction.id}
          onClick={primaryAction.onClick}
          visual="primary"
        >
          {primaryAction.label}
        </Button>
      ) : null}
    </header>
  );
}

export function GateTrack({
  steps,
  onSelect,
}: {
  steps: readonly GateStep[];
  onSelect?: (step: GateStep) => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <ol aria-label={t("Gate track")} className="stage-track">
      {steps.map((step) => (
        <li
          aria-current={step.state === "current" ? "step" : undefined}
          className={`stage-track__step stage-track__step--${step.state}`}
          key={step.code}
        >
          {onSelect ? (
            <button
              className="stage-track__control"
              onClick={() => {
                onSelect(step);
              }}
              type="button"
            >
              <SemanticStatus
                label={`${step.code} ${gateLabel(t, step)}`}
                tone={
                  step.state === "blocked"
                    ? "danger"
                    : step.state === "current"
                      ? "info"
                      : step.state === "completed"
                        ? "success"
                        : "neutral"
                }
              />
            </button>
          ) : (
            <SemanticStatus
              label={`${step.code} ${gateLabel(t, step)}`}
              tone={
                step.state === "blocked"
                  ? "danger"
                  : step.state === "current"
                    ? "info"
                    : step.state === "completed"
                      ? "success"
                      : "neutral"
              }
            />
          )}
        </li>
      ))}
    </ol>
  );
}

export function LifecycleTrack({
  steps,
}: {
  steps: readonly LifecycleStep[];
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <ol aria-label={t("Tooling lifecycle")} className="stage-track">
      {steps.map((step) => (
        <li
          aria-current={step.state === "current" ? "step" : undefined}
          className={`stage-track__step stage-track__step--${step.state}`}
          key={step.code}
        >
          <SemanticStatus
            label={lifecycleLabel(t, step)}
            tone={
              step.state === "blocked"
                ? "danger"
                : step.state === "current"
                  ? "info"
                  : step.state === "completed"
                    ? "success"
                    : "neutral"
            }
          />
        </li>
      ))}
    </ol>
  );
}

export function MetricStrip({
  className = "",
  metrics,
}: {
  className?: string;
  metrics: readonly {
    label: string;
    value: ReactNode;
    tone?: "neutral" | "warning" | "danger";
  }[];
}): React.JSX.Element {
  return (
    <dl className={`metric-strip ${className}`.trim()}>
      {metrics.map((metric) => (
        <div
          className={`metric-strip__item metric-strip__item--${metric.tone ?? "neutral"}`}
          key={metric.label}
        >
          <dt>{metric.label}</dt>
          <dd>{metric.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SectionAnchors({
  sections,
}: {
  sections: readonly { id: string; label: string }[];
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <nav
      aria-label={t("Object page sections", undefined, "aria-label")}
      className="section-anchors"
    >
      {sections.map((section) => (
        <button
          key={section.id}
          onClick={() => {
            const target = document.getElementById(section.id);
            target?.scrollIntoView({ block: "nearest" });
            target?.focus({ preventScroll: true });
          }}
          type="button"
        >
          {section.label}
        </button>
      ))}
    </nav>
  );
}

const controlledInspectorDefaultWidthPx = 340;
const legacyInspectorDefaultWidthPx = 320;
const inspectorMinimumWidthPx = 260;
const inspectorMaximumWidthPx = 480;
const inspectorKeyboardStepPx = 20;

export type DockedInspectorLayoutStatus =
  | "failed"
  | "loading"
  | "ready"
  | "saving"
  | "unavailable";

export interface DockedInspectorLayout {
  readonly collapsed: boolean;
  readonly widthPx: number;
  readonly canUpdate: boolean;
  readonly status: DockedInspectorLayoutStatus;
  readonly failure: RequestFailure | null;
  readonly recoveryReason: "stored_preference_invalid" | null;
  readonly onChange: (next: {
    readonly collapsed: boolean;
    readonly widthPx: number;
  }) => void;
  readonly onReload: () => void;
}

function clampInspectorWidth(widthPx: number): number {
  if (!Number.isFinite(widthPx)) return controlledInspectorDefaultWidthPx;
  return Math.min(
    inspectorMaximumWidthPx,
    Math.max(inspectorMinimumWidthPx, Math.round(widthPx)),
  );
}

function inspectorLayoutStatusCopy(
  status: DockedInspectorLayoutStatus,
  recoveryReason: DockedInspectorLayout["recoveryReason"],
  t: ReturnType<typeof useI18n>["t"],
): {
  readonly label: string;
  readonly text: string;
  readonly tone: SemanticTone;
} {
  switch (status) {
    case "failed":
      return {
        label: t("Not saved"),
        text: t(
          "Pane layout was not saved. The last confirmed layout remains active.",
        ),
        tone: "danger",
      };
    case "loading":
      return {
        label: t("Loading"),
        text: t("Loading pane layout"),
        tone: "info",
      };
    case "ready":
      return recoveryReason === "stored_preference_invalid"
        ? {
            label: t("Defaults active"),
            text: t(
              "Stored pane layout was invalid. The default layout is active.",
            ),
            tone: "warning",
          }
        : {
            label: t("Confirmed"),
            text: t("Pane layout is confirmed by the server."),
            tone: "neutral",
          };
    case "saving":
      return {
        label: t("Saving"),
        text: t("Saving pane layout"),
        tone: "info",
      };
    case "unavailable":
      return {
        label: t("Unavailable"),
        text: t(
          "Session verification is required before pane layout can be saved.",
        ),
        tone: "warning",
      };
  }
}

export function DockedInspector({
  title,
  children,
  activities,
  id,
  layout,
}: PropsWithChildren<{
  title: string;
  activities?: readonly ActivityEvent[];
  id?: string;
  layout?: DockedInspectorLayout;
}>): React.JSX.Element {
  const { locale, t } = useI18n();
  const inspectorRef = useRef<HTMLElement | null>(null);
  const collapseControlRef = useRef<HTMLDivElement | null>(null);
  const reloadControlRef = useRef<HTMLDivElement | null>(null);
  const focusWasInsideInspector = useRef(false);
  const previousCollapsed = useRef(layout?.collapsed ?? false);
  const controlled = layout !== undefined;
  const [legacyWidth, setLegacyWidth] = useState(() => {
    if (layout) return legacyInspectorDefaultWidthPx;
    const stored = Number(
      globalThis.localStorage.getItem("npi-one-inspector-width"),
    );
    return Number.isFinite(stored) &&
      stored >= inspectorMinimumWidthPx &&
      stored <= inspectorMaximumWidthPx
      ? stored
      : legacyInspectorDefaultWidthPx;
  });
  const [legacyCollapsed, setLegacyCollapsed] = useState(() =>
    layout
      ? false
      : globalThis.localStorage.getItem("npi-one-inspector-collapsed") ===
        "true",
  );
  const collapsed = layout?.collapsed ?? legacyCollapsed;
  const recoveryExpanded = Boolean(collapsed && layout?.failure);
  const confirmedWidth = layout
    ? clampInspectorWidth(layout.widthPx)
    : legacyWidth;

  useEffect(() => {
    if (!controlled) return undefined;
    const handleFocusIn = (event: FocusEvent): void => {
      focusWasInsideInspector.current = Boolean(
        event.target instanceof Node &&
        inspectorRef.current?.contains(event.target),
      );
    };
    document.addEventListener("focusin", handleFocusIn);
    return () => {
      document.removeEventListener("focusin", handleFocusIn);
    };
  }, [controlled]);

  useEffect(() => {
    if (
      controlled &&
      collapsed &&
      !previousCollapsed.current &&
      focusWasInsideInspector.current
    ) {
      const focusContainer = recoveryExpanded
        ? reloadControlRef.current
        : collapseControlRef.current;
      void focusControl(
        focusContainer?.querySelector<HTMLElement>("button, ix-button") ?? null,
      );
    }
    previousCollapsed.current = collapsed;
  }, [collapsed, controlled, recoveryExpanded]);

  useEffect(() => {
    const layout = inspectorRef.current?.parentElement;
    layout?.style.setProperty(
      "--npi-inspector-width",
      collapsed && !recoveryExpanded ? "40px" : `${String(confirmedWidth)}px`,
    );
    if (!controlled) {
      globalThis.localStorage.setItem(
        "npi-one-inspector-width",
        String(legacyWidth),
      );
      globalThis.localStorage.setItem(
        "npi-one-inspector-collapsed",
        String(legacyCollapsed),
      );
    }
    return () => {
      layout?.style.removeProperty("--npi-inspector-width");
    };
  }, [
    collapsed,
    confirmedWidth,
    controlled,
    legacyCollapsed,
    legacyWidth,
    recoveryExpanded,
  ]);

  const inspectorContent = (
    <>
      <Panel title={title}>{children}</Panel>
      {activities ? (
        <Panel title={t("Activity")}>
          <ol className="activity-timeline">
            {activities.map((event) => (
              <li key={event.id}>
                <span
                  aria-hidden="true"
                  className="activity-timeline__marker"
                />
                <div>
                  <strong data-language-exempt="business-data">
                    {event.actor}
                  </strong>
                  <p>{activityLabel(t, event)}</p>
                  <code data-language-exempt="identifier">
                    {event.reference}
                  </code>
                  <time dateTime={event.occurredAt}>
                    {formatDateTime(locale, event.occurredAt)}
                  </time>
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      ) : null}
    </>
  );
  const statusCopy = layout
    ? inspectorLayoutStatusCopy(layout.status, layout.recoveryReason, t)
    : null;

  return (
    <aside
      aria-label={title}
      className={`docked-inspector${controlled ? " docked-inspector--controlled" : ""}${collapsed ? " docked-inspector--collapsed" : ""}${recoveryExpanded ? " docked-inspector--recovery-open" : ""}`}
      id={id}
      ref={inspectorRef}
      tabIndex={0}
    >
      {layout && !collapsed ? (
        <ResizablePaneSeparator
          defaultValue={controlledInspectorDefaultWidthPx}
          disabled={!layout.canUpdate}
          label={t("Resize inspector")}
          maximum={inspectorMaximumWidthPx}
          minimum={inspectorMinimumWidthPx}
          onCommit={(widthPx) => {
            layout.onChange({
              collapsed: false,
              widthPx: clampInspectorWidth(widthPx),
            });
          }}
          onPreview={(widthPx) => {
            inspectorRef.current?.parentElement?.style.setProperty(
              "--npi-inspector-width",
              `${String(clampInspectorWidth(widthPx))}px`,
            );
          }}
          step={inspectorKeyboardStepPx}
          title={t(
            "Drag to resize. Use Left and Right Arrow keys, Home or End for a limit, or double-click to reset.",
          )}
          value={confirmedWidth}
        />
      ) : null}
      <div className="inspector-controls">
        <div ref={collapseControlRef}>
          {controlled ? (
            <CompactAction
              aria-expanded={!collapsed}
              disabled={!layout.canUpdate}
              icon={collapsed ? "expand" : "collapse"}
              intent="familiar-low-risk"
              label={
                collapsed ? t("Expand inspector") : t("Collapse inspector")
              }
              onClick={(event) => {
                void focusControl(event.currentTarget);
                layout.onChange({
                  collapsed: !collapsed,
                  widthPx: confirmedWidth,
                });
              }}
              tooltipPlacement={collapsed ? "left" : "bottom-start"}
            />
          ) : (
            <Button
              aria-expanded={!collapsed}
              onClick={(event) => {
                void focusControl(event.currentTarget);
                setLegacyCollapsed((current) => !current);
              }}
            >
              {collapsed ? t("Expand inspector") : t("Collapse inspector")}
            </Button>
          )}
        </div>
        {statusCopy &&
        (!collapsed ||
          layout?.status !== "ready" ||
          layout.recoveryReason !== null) ? (
          <div className="docked-inspector__layout-status">
            <span
              aria-atomic="true"
              aria-live="polite"
              className={
                collapsed && !recoveryExpanded ? "visually-hidden" : undefined
              }
            >
              {statusCopy.text}
            </span>
            <SemanticStatus label={statusCopy.label} tone={statusCopy.tone} />
          </div>
        ) : null}
        {!controlled && !collapsed ? (
          <label className="inspector-controls__range">
            <span className="visually-hidden">{t("Inspector width")}</span>
            <input
              aria-label={t("Inspector width")}
              max={inspectorMaximumWidthPx}
              min={inspectorMinimumWidthPx}
              onChange={(event) => {
                setLegacyWidth(Number(event.currentTarget.value));
              }}
              step={20}
              type="range"
              value={legacyWidth}
            />
          </label>
        ) : null}
      </div>
      {layout?.failure ? (
        <div className="docked-inspector__layout-failure">
          <RequestFailurePanel failure={layout.failure} />
          <div ref={reloadControlRef}>
            <CompactAction
              icon="refresh"
              intent="ambiguous"
              label={t("Reload pane layout")}
              onClick={layout.onReload}
            />
          </div>
        </div>
      ) : null}
      {controlled ? (
        <div className="docked-inspector__content" hidden={collapsed}>
          {inspectorContent}
        </div>
      ) : collapsed ? null : (
        inspectorContent
      )}
    </aside>
  );
}
