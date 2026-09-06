import {
  useId,
  useState,
  type ChangeEvent,
  type FormEvent,
  type MouseEvent,
} from "react";

import { useI18n } from "../i18n/runtime";
import { Button, TextInput } from "../ui-adapters/npi-ui";
import { SemanticStatus } from "./primitives";

const SCANNED_REFERENCE_MAX_LENGTH = 128;

export interface AuthorizedScanReference {
  readonly label: string;
  readonly value: string;
}

type ScanReviewError = "ambiguous" | "control" | "empty" | "long" | "unknown";

type ScanReviewState =
  | { readonly kind: "idle" }
  | { readonly kind: "error"; readonly reason: ScanReviewError }
  | {
      readonly kind: "reviewed" | "applied";
      readonly reference: AuthorizedScanReference;
    };

type ScanReviewResult =
  | { readonly kind: "error"; readonly reason: ScanReviewError }
  | { readonly kind: "match"; readonly reference: AuthorizedScanReference };

function containsUnsupportedControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0);
    return codePoint !== undefined && (codePoint < 0x20 || codePoint === 0x7f);
  });
}

function reviewScannedReference(
  rawValue: string,
  references: readonly AuthorizedScanReference[],
): ScanReviewResult {
  if (rawValue.length > SCANNED_REFERENCE_MAX_LENGTH) {
    return { kind: "error", reason: "long" };
  }
  if (containsUnsupportedControlCharacter(rawValue)) {
    return { kind: "error", reason: "control" };
  }

  const value = rawValue.trim();
  if (!value) return { kind: "error", reason: "empty" };

  const matches = references.filter((reference) => reference.value === value);
  if (matches.length === 0) return { kind: "error", reason: "unknown" };
  if (matches.length > 1) return { kind: "error", reason: "ambiguous" };
  const reference = matches[0];
  return reference
    ? { kind: "match", reference }
    : { kind: "error", reason: "unknown" };
}

function sameReference(
  left: AuthorizedScanReference,
  right: AuthorizedScanReference,
): boolean {
  return left.label === right.label && left.value === right.value;
}

export function ReviewedScanEntry({
  disabled = false,
  onApply,
  references,
}: {
  readonly disabled?: boolean;
  readonly onApply: (reference: AuthorizedScanReference) => void;
  readonly references: readonly AuthorizedScanReference[];
}): React.JSX.Element {
  const { t } = useI18n();
  const generatedId = useId().replaceAll(":", "");
  const inputId = `reviewed-scan-${generatedId}`;
  const helpId = `${inputId}-help`;
  const statusId = `${inputId}-status`;
  const [rawValue, setRawValue] = useState("");
  const [reviewState, setReviewState] = useState<ScanReviewState>({
    kind: "idle",
  });

  const currentResult = reviewScannedReference(rawValue, references);
  const retainedReference =
    reviewState.kind === "reviewed" || reviewState.kind === "applied"
      ? reviewState.reference
      : null;
  const retainedReviewIsCurrent =
    retainedReference !== null &&
    currentResult.kind === "match" &&
    sameReference(retainedReference, currentResult.reference);
  const visibleReviewState = retainedReviewIsCurrent
    ? reviewState
    : reviewState.kind === "error"
      ? reviewState
      : ({ kind: "idle" } as const);

  const errorMessage =
    visibleReviewState.kind === "error"
      ? {
          ambiguous: t(
            "More than one authorized reference matches this value.",
          ),
          control: t(
            "The scanned value contains unsupported control characters.",
          ),
          empty: t("Enter a reference before review."),
          long: t("The scanned value is too long."),
          unknown: t("No authorized reference matches this value."),
        }[visibleReviewState.reason]
      : null;

  function handleInputChange(event: ChangeEvent<HTMLInputElement>): void {
    setRawValue(event.currentTarget.value);
    setReviewState({ kind: "idle" });
  }

  function handleReview(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (disabled) return;
    const result = reviewScannedReference(rawValue, references);
    setReviewState(
      result.kind === "match"
        ? { kind: "reviewed", reference: result.reference }
        : result,
    );
  }

  function handleApply(event: MouseEvent<HTMLElement>): void {
    event.preventDefault();
    if (disabled || visibleReviewState.kind !== "reviewed") return;
    const result = reviewScannedReference(rawValue, references);
    if (
      result.kind !== "match" ||
      !sameReference(result.reference, visibleReviewState.reference)
    ) {
      setReviewState(
        result.kind === "error" ? result : { kind: "error", reason: "unknown" },
      );
      return;
    }
    onApply(result.reference);
    setReviewState({ kind: "applied", reference: result.reference });
  }

  const reviewedReference =
    visibleReviewState.kind === "reviewed" ||
    visibleReviewState.kind === "applied"
      ? visibleReviewState.reference
      : null;

  return (
    <section
      aria-labelledby={`${inputId}-title`}
      className="reviewed-scan-entry"
      data-testid="reviewed-scan-entry"
    >
      <div className="reviewed-scan-entry__heading">
        <h3 className="mobile-field-action__title" id={`${inputId}-title`}>
          {t("Reviewed scan entry")}
        </h3>
        <SemanticStatus
          label={disabled ? t("Unavailable") : t("Input assistance")}
          tone={disabled ? "warning" : "info"}
        />
      </div>
      <form className="reviewed-scan-entry__form" onSubmit={handleReview}>
        <label className="reviewed-scan-entry__label" htmlFor={inputId}>
          {t("Scanned value")}
        </label>
        <TextInput
          aria-describedby={`${helpId} ${statusId}`}
          aria-invalid={visibleReviewState.kind === "error" ? true : undefined}
          autoComplete="off"
          disabled={disabled}
          id={inputId}
          maxLength={SCANNED_REFERENCE_MAX_LENGTH}
          onChange={handleInputChange}
          spellCheck={false}
          value={rawValue}
        />
        <small className="reviewed-scan-entry__help" id={helpId}>
          {t(
            "Scan or enter an exact authorized reference. Review it before use.",
          )}
        </small>
        <div className="reviewed-scan-entry__actions">
          <Button
            className="reviewed-scan-entry__action"
            disabled={disabled}
            type="submit"
            visual={reviewedReference ? "secondary" : "primary"}
          >
            {t("Review scanned value")}
          </Button>
          {!disabled && visibleReviewState.kind === "reviewed" ? (
            <Button
              className="reviewed-scan-entry__action"
              onClick={handleApply}
              type="button"
              visual="primary"
            >
              {t("Use reviewed value")}
            </Button>
          ) : null}
        </div>
      </form>
      {reviewedReference ? (
        <dl className="reviewed-scan-entry__match">
          <div className="reviewed-scan-entry__match-row">
            <dt className="reviewed-scan-entry__match-key">
              {t("Reviewed reference")}
            </dt>
            <dd className="reviewed-scan-entry__match-value">
              <span data-language-exempt="business-data">
                {reviewedReference.label}
              </span>
              <code data-language-exempt="identifier">
                {reviewedReference.value}
              </code>
            </dd>
          </div>
        </dl>
      ) : null}
      <div aria-atomic="true" aria-live="polite" id={statusId}>
        {disabled ? (
          <SemanticStatus
            label={t("Scan entry is unavailable in this state.")}
            tone="warning"
          />
        ) : errorMessage ? (
          <SemanticStatus label={errorMessage} tone="danger" />
        ) : visibleReviewState.kind === "reviewed" ? (
          <SemanticStatus
            label={t("Ready to use. No command has been submitted.")}
            tone="success"
          />
        ) : visibleReviewState.kind === "applied" ? (
          <SemanticStatus
            label={t("Reference applied. No command has been submitted.")}
            tone="success"
          />
        ) : null}
      </div>
    </section>
  );
}

export function MobileEngineeringHandoff(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <aside className="mobile-engineering-handoff mobile-field-only" role="note">
      <div className="mobile-engineering-handoff__heading">
        <h3 className="mobile-field-action__title">
          {t("Desktop engineering analysis")}
        </h3>
        <SemanticStatus label={t("Same authorized workspace")} tone="info" />
      </div>
      <p className="mobile-engineering-handoff__copy">
        {t(
          "Complex engineering tables remain available on desktop. Continue from this same authorized link.",
        )}
      </p>
    </aside>
  );
}
