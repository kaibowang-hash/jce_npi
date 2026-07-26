import { useState, type PropsWithChildren } from "react";

import type { Scenario } from "../domain/view-models";
import { scenarioLabel } from "../i18n/copy";
import { useI18n } from "../i18n/runtime";
import { Button, Icon } from "../ui-adapters/npi-ui";
import { SemanticStatus } from "./primitives";
import { ProblemDetailsPanel } from "./problem-details-panel";

export function ScenarioBoundary({
  scenario,
  children,
}: PropsWithChildren<{ scenario: Scenario }>): React.JSX.Element {
  const { t } = useI18n();
  const [actionResult, setActionResult] = useState<{
    scenario: Scenario;
    message: string;
  } | null>(null);
  if (scenario === "normal") return <>{children}</>;
  if (
    scenario === "read_only" ||
    scenario === "partial" ||
    scenario === "dirty"
  ) {
    const message =
      scenario === "read_only"
        ? t(
            "This object is read only because the released version is immutable.",
          )
        : scenario === "partial"
          ? t(
              "Some ERPNext projections are unavailable. LaunchFlow data remains available.",
            )
          : t("You have unsaved changes. Leave protection is active.");
    return (
      <>
        <div
          className={`scenario-banner scenario-banner--${scenario}`}
          role="status"
        >
          <SemanticStatus
            label={scenarioLabel(t, scenario)}
            tone={scenario === "partial" ? "warning" : "info"}
          />
          <span>{message}</span>
        </div>
        {children}
      </>
    );
  }
  if (scenario === "loading") {
    return (
      <div
        aria-busy="true"
        aria-label={t("Loading")}
        className="state-surface state-surface--loading"
      >
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <div className="skeleton" />
        <span className="visually-hidden">{t("Loading")}</span>
      </div>
    );
  }

  const configuration = {
    empty: {
      icon: "info" as const,
      title: t("No items match this view."),
      detail: t("Change the filters or choose another saved view."),
      action: t("Clear filters"),
      result: t(
        "Filters were cleared and the normal prototype view was restored.",
      ),
      tone: "neutral" as const,
    },
    no_permission: {
      icon: "warning" as const,
      title: t("You do not have permission to view this object."),
      detail: t("Request project access from the project manager."),
      action: t("Return to My Work"),
      result: t("Returned to My Work without changing protected data."),
      tone: "warning" as const,
    },
    error: {
      icon: "error" as const,
      title: t("The page could not be loaded."),
      detail: t(
        "No data was changed. Retry or share the trace ID with support.",
      ),
      action: t("Retry"),
      result: t("The prototype retry restored the deterministic view."),
      tone: "danger" as const,
    },
    conflict: {
      icon: "warning" as const,
      title: t("A newer version is available."),
      detail: t("Review the differences before replacing your draft."),
      action: t("Review differences"),
      result: t(
        "Prototype comparison: server version v4 differs from draft v3. Neither version was replaced.",
      ),
      tone: "warning" as const,
    },
    validation: {
      icon: "warning" as const,
      title: t("The command failed validation."),
      detail: t("Correct the highlighted fields and submit again."),
      action: t("Review fields"),
      result: t(
        "Prototype field error: a required governed value is missing. No command was submitted.",
      ),
      tone: "warning" as const,
    },
    queued: {
      icon: "info" as const,
      title: t("The operation is queued."),
      detail: t("ERPNext has not completed the requested action."),
      action: t("View operation status"),
      result: t(
        "Current prototype status is queued. ERPNext completion has not been reported.",
      ),
      tone: "info" as const,
    },
    processing: {
      icon: "info" as const,
      title: t("The operation is processing."),
      detail: t(
        "This prototype refresh restores the simulated processing state; no durable remote operation is queried.",
      ),
      action: t("Refresh status"),
      result: t(
        "Current prototype status is processing. ERPNext completion has not been reported.",
      ),
      tone: "info" as const,
    },
    failed_retryable: {
      icon: "warning" as const,
      title: t("The operation failed and can be retried."),
      detail: t("Review the impact before queuing a safe retry."),
      action: t("Review retry"),
      result: t(
        "Retry impact: the same idempotency key and failed node would be reused. No retry was queued.",
      ),
      tone: "warning" as const,
    },
    failed_final: {
      icon: "error" as const,
      title: t("The operation failed and requires manual action."),
      detail: t(
        "No retry was queued. Follow the recovery guidance and use the trace ID.",
      ),
      action: t("Open recovery guidance"),
      result: t(
        "Recovery guidance: correct the governed source mapping and prepare a new request. Manual action is still required.",
      ),
      tone: "danger" as const,
    },
  }[scenario];
  const validationProblem = {
    type: "urn:npi:problem:validation_failed",
    title: t("The command failed validation."),
    status: 422,
    detail: t("Correct the highlighted fields and submit again."),
    code: "VALIDATION_FAILED",
    traceId: "trc-phase3-fixture",
    retryable: false,
    fieldErrors: [
      {
        path: "governedValue",
        message: t("Select an approved governed value."),
      },
    ],
  } as const;

  const runAction = (): void => {
    if (scenario === "no_permission") {
      globalThis.history.pushState({}, "", "/work");
      globalThis.dispatchEvent(new PopStateEvent("popstate"));
    } else if (scenario === "empty" || scenario === "error") {
      const url = new URL(globalThis.location.href);
      url.searchParams.delete("scenario");
      globalThis.history.pushState({}, "", `${url.pathname}${url.search}`);
      globalThis.dispatchEvent(new PopStateEvent("popstate"));
    }
    setActionResult({ scenario, message: configuration.result });
  };

  return (
    <section className="state-surface" role="status">
      <Icon name={configuration.icon} />
      <h2>{configuration.title}</h2>
      <p>{configuration.detail}</p>
      <p className="trace-reference">
        {t("Trace ID")}:{" "}
        <code data-language-exempt="identifier">trc-phase3-fixture</code>
      </p>
      <Button onClick={runAction}>{configuration.action}</Button>
      {actionResult?.scenario === scenario ? (
        <>
          <p aria-live="polite">{actionResult.message}</p>
          {scenario === "validation" ? (
            <ProblemDetailsPanel problem={validationProblem} />
          ) : null}
        </>
      ) : null}
      <SemanticStatus
        label={scenarioLabel(t, scenario)}
        tone={configuration.tone}
      />
    </section>
  );
}
