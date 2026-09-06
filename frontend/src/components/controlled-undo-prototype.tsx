import { useEffect, useRef, useState } from "react";

import { formatNumber } from "../i18n/formatters";
import { useI18n, type I18nContextValue } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import { DefinitionList, Panel, SemanticStatus } from "./primitives";
import {
  controlledUndoPrototypeDurationSeconds,
  controlledUndoPrototypeRevision,
  controlledUndoPrototypeStateFromSearch,
  type ControlledUndoPrototypeState,
} from "./controlled-undo-prototype-model";

interface StateCopy {
  description: string;
  label: string;
  tone: "neutral" | "info" | "success" | "warning" | "danger";
}

function stateCopy(
  t: I18nContextValue["t"],
  state: ControlledUndoPrototypeState,
): StateCopy {
  switch (state) {
    case "review":
      return {
        description: t(
          "The personal layout is customized. Review the reset consequence before continuing.",
        ),
        label: t("Ready for review"),
        tone: "neutral",
      };
    case "confirmation":
      return {
        description: t(
          "Only this personal view would return to code-owned defaults. No business data or shared view would change.",
        ),
        label: t("Confirmation"),
        tone: "warning",
      };
    case "available":
      return {
        description: t(
          "Review state: the reset response is confirmed and one undo is available for the displayed time.",
        ),
        label: t("Undo available"),
        tone: "info",
      };
    case "processing":
      return {
        description: t(
          "Review state: the undo request is processing. The previous layout is not reported as restored.",
        ),
        label: t("Processing"),
        tone: "info",
      };
    case "restored":
      return {
        description: t(
          "Review state: reconciliation confirms the previous layout as a new preference version.",
        ),
        label: t("Confirmed"),
        tone: "success",
      };
    case "expired":
      return {
        description: t(
          "Review state: the undo window expired. The confirmed reset remains active.",
        ),
        label: t("Expired"),
        tone: "warning",
      };
    case "conflict":
      return {
        description: t(
          "Review state: the layout changed in another session. Reload current settings before another command.",
        ),
        label: t("Conflict"),
        tone: "warning",
      };
    case "denied":
      return {
        description: t(
          "Review state: permission is no longer available. No command is sent.",
        ),
        label: t("Unavailable"),
        tone: "danger",
      };
    case "retryable":
      return {
        description: t(
          "Review state: the result is unknown. Reconcile the prepared request before retrying.",
        ),
        label: t("Result unknown"),
        tone: "warning",
      };
    case "final":
      return {
        description: t(
          "Review state: undo cannot continue. The confirmed reset remains active and the reference ID remains visible.",
        ),
        label: t("Error"),
        tone: "danger",
      };
  }
}

function layoutLabel(
  t: I18nContextValue["t"],
  state: ControlledUndoPrototypeState,
): string {
  if (state === "restored") return t("Previous personal layout");
  if (
    state === "available" ||
    state === "processing" ||
    state === "expired" ||
    state === "retryable" ||
    state === "final"
  ) {
    return t("Code-owned default layout");
  }
  return t("Customized personal layout");
}

export function ControlledUndoPrototype({
  initialState = controlledUndoPrototypeStateFromSearch(),
}: {
  initialState?: ControlledUndoPrototypeState;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [state, setState] =
    useState<ControlledUndoPrototypeState>(initialState);
  const stateRegion = useRef<HTMLDivElement | null>(null);
  const initialRender = useRef(true);
  const copy = stateCopy(t, state);

  useEffect(() => {
    if (initialRender.current) {
      initialRender.current = false;
      return;
    }
    stateRegion.current?.focus();
  }, [state]);

  const restart = (): void => {
    setState("review");
  };

  const actions = (() => {
    switch (state) {
      case "review":
        return (
          <Button
            onClick={() => {
              setState("confirmation");
            }}
            visual="primary"
          >
            {t("Review reset")}
          </Button>
        );
      case "confirmation":
        return (
          <>
            <Button onClick={restart}>{t("Cancel review")}</Button>
            <Button
              onClick={() => {
                setState("available");
              }}
              visual="primary"
            >
              {t("Show reset-confirmed state")}
            </Button>
          </>
        );
      case "available":
        return (
          <>
            <Button
              onClick={() => {
                setState("expired");
              }}
            >
              {t("Show expired state")}
            </Button>
            <Button
              onClick={() => {
                setState("processing");
              }}
              visual="primary"
            >
              {t("Undo reset")}
            </Button>
          </>
        );
      case "processing":
        return (
          <>
            <Button
              onClick={() => {
                setState("conflict");
              }}
            >
              {t("Show conflict state")}
            </Button>
            <Button
              onClick={() => {
                setState("retryable");
              }}
            >
              {t("Show retryable error")}
            </Button>
            <Button
              onClick={() => {
                setState("restored");
              }}
              visual="primary"
            >
              {t("Show reconciled result")}
            </Button>
          </>
        );
      case "conflict":
        return (
          <Button onClick={restart} visual="primary">
            {t("Reload prototype state")}
          </Button>
        );
      case "retryable":
        return (
          <Button
            onClick={() => {
              setState("processing");
            }}
            visual="primary"
          >
            {t("Retry prototype state")}
          </Button>
        );
      case "restored":
      case "expired":
      case "denied":
      case "final":
        return (
          <Button onClick={restart} visual="primary">
            {t("Return to review")}
          </Button>
        );
    }
  })();

  return (
    <Panel
      actions={<SemanticStatus label={copy.label} tone={copy.tone} />}
      className="controlled-undo-prototype"
      title={t("Controlled undo review prototype")}
    >
      <div className="controlled-undo-prototype__notice" role="note">
        <strong>{t("Prototype only")}</strong>
        <span>
          {t(
            "This review surface sends no production request and changes no saved settings.",
          )}
        </span>
      </div>
      <div className="controlled-undo-prototype__workspace">
        <section
          aria-label={t("Prototype state")}
          className="controlled-undo-prototype__state"
          data-prototype-state={state}
          ref={stateRegion}
          tabIndex={-1}
        >
          <div className="controlled-undo-prototype__context">
            <span>{t("Personal grid settings")}</span>
            <strong>{t("All assigned work")}</strong>
          </div>
          <div aria-live="polite" className="controlled-undo-prototype__copy">
            <h3>{copy.label}</h3>
            <p>{copy.description}</p>
          </div>
          {state === "available" ? (
            <div className="controlled-undo-prototype__countdown">
              <span>{t("Undo window")}</span>
              <strong>
                {t("{{seconds}} seconds remaining", {
                  seconds: formatNumber(
                    locale,
                    controlledUndoPrototypeDurationSeconds,
                    0,
                  ),
                })}
              </strong>
            </div>
          ) : null}
          {state === "final" ? (
            <div className="controlled-undo-prototype__reference">
              <span>{t("Reference ID")}</span>
              <code data-language-exempt="identifier">
                prototype-r1-06-final
              </code>
            </div>
          ) : null}
          <div className="controlled-undo-prototype__actions">{actions}</div>
        </section>
        <aside
          aria-label={t("Prototype review facts")}
          className="controlled-undo-prototype__facts"
        >
          <DefinitionList
            rows={[
              {
                label: t("Current layout"),
                value: layoutLabel(t, state),
              },
              {
                label: t("Eligible action"),
                value: t("Reset one personal My Work grid view"),
              },
              {
                label: t("Prototype duration"),
                value: t(
                  "{{seconds}} seconds for interaction review; the production value is pending.",
                  {
                    seconds: formatNumber(
                      locale,
                      controlledUndoPrototypeDurationSeconds,
                      0,
                    ),
                  },
                ),
              },
              {
                label: t("Backend implementation gate"),
                value: t("Pending Product Owner approval"),
              },
              {
                exempt: "identifier",
                label: t("Prototype revision"),
                value: controlledUndoPrototypeRevision,
              },
            ]}
          />
          <p>
            {t(
              "Approvals, releases, baselines, registered revisions, deletes, and external execution never use this generic undo.",
            )}
          </p>
          <p>
            {t(
              "Their approved forward-correction, new-revision, reconciliation, or support path remains visible in the owning workflow.",
            )}
          </p>
        </aside>
      </div>
    </Panel>
  );
}
