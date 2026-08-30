import {
  useEffect,
  useId,
  useRef,
  useState,
  type PropsWithChildren,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import type {
  SemanticTone,
  SourceSystem,
  SourceStatus as SourceStatusModel,
  SyncState,
} from "../domain/view-models";
import { sourceSystemLabel, syncStateLabel } from "../i18n/copy";
import { useI18n } from "../i18n/runtime";
import {
  Button,
  focusControl,
  Icon,
  type NpiIconName,
} from "../ui-adapters/npi-ui";
import {
  DisplayBrandErpIdentity,
  DisplayBrandPlatformIcon,
} from "../ui-adapters/display-brand";

export function Panel({
  title,
  actions,
  bodyClassName = "",
  children,
  className = "",
  id,
  scrollableBody = false,
}: PropsWithChildren<{
  title: string;
  actions?: ReactNode;
  bodyClassName?: string;
  className?: string;
  id?: string;
  scrollableBody?: boolean;
}>): React.JSX.Element {
  return (
    <section
      className={`panel ${className}`.trim()}
      id={id}
      tabIndex={id ? -1 : undefined}
    >
      <header className="panel__header">
        <h2>{title}</h2>
        {actions ? <div className="panel__actions">{actions}</div> : null}
      </header>
      <div
        aria-label={scrollableBody ? title : undefined}
        className={`panel__body ${bodyClassName}`.trim()}
        tabIndex={scrollableBody ? 0 : undefined}
      >
        {children}
      </div>
    </section>
  );
}

const toneIcon: Record<SemanticTone, NpiIconName> = {
  neutral: "info",
  info: "info",
  success: "check",
  warning: "warning",
  danger: "error",
};

export function SemanticStatus({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: SemanticTone;
}): React.JSX.Element {
  return (
    <span
      className={`semantic-status semantic-status--${tone}`}
      data-status-tone={tone}
    >
      <span aria-hidden="true" className="semantic-status__shape" />
      <Icon name={toneIcon[tone]} />
      <span>{label}</span>
    </span>
  );
}

function toneForSync(
  state: SyncState | "queued" | "cancelled" | "succeeded",
): SemanticTone {
  if (state === "succeeded" || state === "synced") return "success";
  if (state === "failed_final") return "danger";
  if (state === "failed_retryable" || state === "partial" || state === "stale")
    return "warning";
  if (state === "processing" || state === "queued" || state === "pending")
    return "info";
  return "neutral";
}

export function SourceBadge({
  source,
}: {
  source: SourceStatusModel;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <span className="source-badge">
      <span>{t("Source")}</span>
      <SourceSystemIdentity emphasized sourceSystem={source.sourceSystem} />
    </span>
  );
}

export function SourceSystemIdentity({
  emphasized = false,
  sourceSystem,
}: {
  emphasized?: boolean;
  sourceSystem: SourceSystem;
}): React.JSX.Element {
  const { t } = useI18n();
  if (sourceSystem === "NPI_ONE") {
    return (
      <DisplayBrandPlatformIcon accessibleName={t("LaunchFlow platform")} />
    );
  }
  if (sourceSystem === "ERPNEXT") {
    return <DisplayBrandErpIdentity accessibleName={t("JCE Core")} />;
  }
  const label = sourceSystemLabel(t, sourceSystem);
  return emphasized ? <strong>{label}</strong> : <span>{label}</span>;
}

export function SyncBadge({
  state,
}: {
  state: SyncState | "queued" | "cancelled" | "succeeded";
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <SemanticStatus
      label={syncStateLabel(t, state)}
      tone={toneForSync(state)}
    />
  );
}

export interface ImpactReviewDetails {
  objectIdentity: string;
  version: string;
  impact: string;
  permission: string;
  irreversible: string;
  failureHandling: string;
  audit: string;
}

export interface ImpactReviewContextRow {
  label: string;
  value: ReactNode;
  exempt?: "business-data" | "identifier" | "unit";
}

const IMPACT_REVIEW_REASON_MAX_LENGTH = 4000;

export function ImpactReview({
  title,
  details,
  contextRows = [],
  confirmLabel,
  onCancel,
  onConfirm,
  reasonRequired = true,
  reasonMaxLength = IMPACT_REVIEW_REASON_MAX_LENGTH,
  returnFocusTarget,
}: {
  title: string;
  details: ImpactReviewDetails;
  contextRows?: readonly ImpactReviewContextRow[];
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
  reasonRequired?: boolean;
  reasonMaxLength?: number;
  returnFocusTarget?: () => HTMLElement | null;
}): React.JSX.Element {
  const { t } = useI18n();
  const headingId = useId();
  const reasonHelpId = useId();
  const [reason, setReason] = useState("");
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(
    document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null,
  );
  useEffect(() => {
    const root = document.querySelector<HTMLElement>("#root");
    const returnFocus = returnFocusRef.current;
    if (root) root.inert = true;
    const focusableSelector =
      'ix-button:not([disabled]), button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const focusable = (): HTMLElement[] => [
      ...(dialogRef.current?.querySelectorAll<HTMLElement>(focusableSelector) ??
        []),
    ];
    void focusControl(headingRef.current);
    const handleKey = (event: KeyboardEvent): void => {
      if (event.key === "Escape") onCancel();
      if (event.key === "Tab") {
        const controls = focusable();
        if (controls.length === 0) return;
        const first = controls[0];
        const last = controls.at(-1);
        if (!first || !last) return;
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === headingRef.current)
        ) {
          event.preventDefault();
          void focusControl(last);
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          void focusControl(first);
        }
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      if (root) root.inert = false;
      if (returnFocusTarget) {
        globalThis.queueMicrotask(() => {
          void focusControl(returnFocusTarget());
        });
      } else {
        void focusControl(returnFocus);
      }
    };
  }, [onCancel, returnFocusTarget]);

  return createPortal(
    <div
      aria-labelledby={headingId}
      aria-modal="true"
      className="impact-review"
      ref={dialogRef}
      role="dialog"
    >
      <div className="impact-review__surface">
        <header className="impact-review__header">
          <Icon name="warning" />
          <h2 id={headingId} ref={headingRef} tabIndex={-1}>
            {title}
          </h2>
        </header>
        <dl className="field-list">
          <div>
            <dt>{t("Object")}</dt>
            <dd data-language-exempt="identifier">{details.objectIdentity}</dd>
          </div>
          <div>
            <dt>{t("Locked version")}</dt>
            <dd data-language-exempt="identifier">{details.version}</dd>
          </div>
          {contextRows.map((row) => (
            <div key={row.label}>
              <dt>{row.label}</dt>
              <dd data-language-exempt={row.exempt}>{row.value}</dd>
            </div>
          ))}
          <div>
            <dt>{t("Impact")}</dt>
            <dd>{details.impact}</dd>
          </div>
          <div>
            <dt>{t("Required permission")}</dt>
            <dd>{details.permission}</dd>
          </div>
          <div>
            <dt>{t("Irreversible effect")}</dt>
            <dd>{details.irreversible}</dd>
          </div>
          <div>
            <dt>{t("Failure handling")}</dt>
            <dd>{details.failureHandling}</dd>
          </div>
          <div>
            <dt>{t("Audit result")}</dt>
            <dd>{details.audit}</dd>
          </div>
        </dl>
        {reasonRequired ? (
          <label className="field-control">
            <span>
              {t("Reason")} <span aria-hidden="true">*</span>
            </span>
            <textarea
              aria-describedby={reasonHelpId}
              aria-label={t("Reason")}
              maxLength={reasonMaxLength}
              onChange={(event) => {
                setReason(
                  event.currentTarget.value.slice(
                    0,
                    IMPACT_REVIEW_REASON_MAX_LENGTH,
                  ),
                );
              }}
              required
              rows={3}
              value={reason}
            />
            <small id={reasonHelpId}>
              {t("A reason is required to prepare this command.")}
            </small>
          </label>
        ) : null}
        <footer className="impact-review__footer">
          <Button className="impact-review__cancel" onClick={onCancel}>
            {t("Cancel")}
          </Button>
          <Button
            disabled={reasonRequired && !reason.trim()}
            onClick={() => {
              onConfirm(reason.trim());
            }}
            visual="primary"
          >
            {confirmLabel}
          </Button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}

export function DefinitionList({
  rows,
}: {
  rows: readonly {
    rowKey?: string;
    label: string;
    value: ReactNode;
    exempt?: "business-data" | "identifier" | "unit";
  }[];
}): React.JSX.Element {
  return (
    <dl className="field-list">
      {rows.map((row) => (
        <div key={row.rowKey ?? row.label}>
          <dt>{row.label}</dt>
          <dd data-language-exempt={row.exempt}>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}
