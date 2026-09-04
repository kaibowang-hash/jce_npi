import type { ProblemDetails, RequestFailure } from "../api/http";
import { useI18n } from "../i18n/runtime";

export function ProblemDetailsPanel({
  announce = true,
  problem,
}: {
  announce?: boolean;
  problem: ProblemDetails;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section
      aria-label={t("Error details")}
      className="problem-details"
      role={announce ? "alert" : undefined}
    >
      <h3>{problem.title}</h3>
      {problem.detail ? <p>{problem.detail}</p> : null}
      {problem.fieldErrors?.length ? (
        <div>
          <strong>{t("Field errors")}</strong>
          <ul>
            {problem.fieldErrors.map((fieldError) => (
              <li key={`${fieldError.path}:${fieldError.message}`}>
                <code data-language-exempt="identifier">{fieldError.path}</code>{" "}
                <span>{fieldError.message}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="trace-reference">
        {t("Trace ID")}:{" "}
        <code data-language-exempt="identifier">{problem.traceId}</code>
      </p>
    </section>
  );
}

function referenceLabel(
  failure: RequestFailure,
  t: ReturnType<typeof useI18n>["t"],
): string {
  if (failure.referenceKind === "trace") return t("Trace ID");
  if (failure.referenceKind === "request") return t("Request ID");
  return t("Client reference ID");
}

export function RequestFailurePanel({
  announce = true,
  failure,
}: {
  announce?: boolean;
  failure: RequestFailure;
}): React.JSX.Element {
  const { t } = useI18n();
  if (failure.problem)
    return (
      <ProblemDetailsPanel announce={announce} problem={failure.problem} />
    );
  const title =
    failure.kind === "network"
      ? t("The service could not be reached.")
      : failure.kind === "invalid_response"
        ? t("The service returned an invalid response.")
        : failure.kind === "request_not_ready"
          ? t("The request could not be prepared safely.")
          : t("An unexpected request error occurred.");
  return (
    <section
      aria-label={t("Error details")}
      className="problem-details"
      role={announce ? "alert" : undefined}
    >
      <h3>{title}</h3>
      <p className="trace-reference">
        {referenceLabel(failure, t)}:{" "}
        <code data-language-exempt="identifier">{failure.referenceId}</code>
      </p>
    </section>
  );
}
