import {
  useEffect,
  useRef,
  useState,
  type PropsWithChildren,
  type ReactNode,
} from "react";

import type {
  ActivityEvent,
  GateStep,
  LifecycleStep,
  SourceStatus,
} from "../domain/view-models";
import { activityLabel, gateLabel, lifecycleLabel } from "../i18n/copy";
import { formatDateTime } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import { Panel, SemanticStatus, SourceBadge, SyncBadge } from "./primitives";

export function ObjectHeader({
  code,
  name,
  metadata,
  status,
  source,
  primaryAction,
  nameIsBusinessData = true,
}: {
  code: string;
  name: string;
  metadata: ReactNode;
  status: ReactNode;
  source: SourceStatus;
  primaryAction?: { label: string; onClick: () => void; disabled?: boolean };
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
      {primaryAction ? (
        <Button
          disabled={primaryAction.disabled}
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
  metrics,
}: {
  metrics: readonly {
    label: string;
    value: ReactNode;
    tone?: "neutral" | "warning" | "danger";
  }[];
}): React.JSX.Element {
  return (
    <dl className="metric-strip">
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

export function DockedInspector({
  title,
  children,
  activities,
  id,
}: PropsWithChildren<{
  title: string;
  activities?: readonly ActivityEvent[];
  id?: string;
}>): React.JSX.Element {
  const { locale, t } = useI18n();
  const inspectorRef = useRef<HTMLElement | null>(null);
  const [width, setWidth] = useState(() => {
    const stored = Number(
      globalThis.localStorage.getItem("npi-one-inspector-width"),
    );
    return Number.isFinite(stored) && stored >= 260 && stored <= 480
      ? stored
      : 320;
  });
  const [collapsed, setCollapsed] = useState(
    () =>
      globalThis.localStorage.getItem("npi-one-inspector-collapsed") === "true",
  );
  useEffect(() => {
    const layout = inspectorRef.current?.parentElement;
    layout?.style.setProperty(
      "--npi-inspector-width",
      collapsed ? "40px" : `${String(width)}px`,
    );
    globalThis.localStorage.setItem("npi-one-inspector-width", String(width));
    globalThis.localStorage.setItem(
      "npi-one-inspector-collapsed",
      String(collapsed),
    );
    return () => {
      layout?.style.removeProperty("--npi-inspector-width");
    };
  }, [collapsed, width]);
  return (
    <aside
      aria-label={title}
      className={`docked-inspector${collapsed ? " docked-inspector--collapsed" : ""}`}
      id={id}
      ref={inspectorRef}
      tabIndex={0}
    >
      <div className="inspector-controls">
        <Button
          aria-expanded={!collapsed}
          onClick={() => {
            setCollapsed((current) => !current);
          }}
        >
          {collapsed ? t("Expand inspector") : t("Collapse inspector")}
        </Button>
        {collapsed ? null : (
          <label>
            <span className="visually-hidden">{t("Inspector width")}</span>
            <input
              aria-label={t("Inspector width")}
              max={480}
              min={260}
              onChange={(event) => {
                setWidth(Number(event.currentTarget.value));
              }}
              step={20}
              type="range"
              value={width}
            />
          </label>
        )}
      </div>
      {collapsed ? null : <Panel title={title}>{children}</Panel>}
      {!collapsed && activities ? (
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
    </aside>
  );
}
