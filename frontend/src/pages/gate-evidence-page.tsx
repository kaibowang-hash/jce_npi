import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  GateReviewRequestCancelledError,
  type GateReviewBindingInput,
  type GateReviewCommandContext,
  type GateReviewCommandOperation,
  type GateReviewDataSource,
} from "../api/gate-review-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import {
  DockedInspector,
  MetricStrip,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
  type ImpactReviewDetails,
} from "../components/primitives";
import type {
  GateDecisionOutcome,
  GateEvidenceReferenceViewModel,
  GateEvidenceScanState,
  GateRequirementEvidenceState,
  GateRequirementViewModel,
  GateReviewExceptionRequestOptionViewModel,
  GateReviewExceptionViewModel,
  GateReviewOutcome,
  GateReviewSelectedStepViewModel,
  GateReviewViewModel,
} from "../domain/view-models";
import {
  domainWorkItemKindLabel,
  gateDecisionOutcomeLabel,
  gateEvidenceKindLabel,
  gateEvidenceScanStateLabel,
  gateRequirementClassificationLabel,
  gateRequirementEvidenceStateLabel,
  gateReviewDependencyEventTypeLabel,
  gateReviewDependencyReasonLabel,
  gateReviewAuthorityPurposeLabel,
  gateReviewCycleStateLabel,
  gateReviewCycleTriggerLabel,
  gateReviewDecisionBlockedReasonLabel,
  gateReviewExceptionStateLabel,
  gateReviewOutcomeLabel,
  gateReviewStateLabel,
  gateReviewStepStateLabel,
  governedPolicyLabel,
  type Translator,
} from "../i18n/copy";
import {
  formatDate,
  formatDateTime,
  formatList,
  formatNumber,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type FailureKind =
  | "not_found"
  | "no_permission"
  | "validation"
  | "conflict"
  | "retryable"
  | "final";

type GateReviewLoadState =
  | { kind: "loading"; projectGlobalId: string; gateGlobalId: string }
  | {
      kind: "loaded";
      projectGlobalId: string;
      gateGlobalId: string;
      review: GateReviewViewModel;
    }
  | {
      kind: "failed";
      projectGlobalId: string;
      gateGlobalId: string;
      failureKind: FailureKind;
      failure: RequestFailure;
    };

type GateReviewReceiptRecoveryState =
  | {
      kind: "pending";
      marker: GateReviewReceiptMarker;
      epoch: number;
    }
  | {
      kind: "failed";
      marker: GateReviewReceiptMarker;
      failure: RequestFailure;
      failureKind: FailureKind;
      epoch: number;
    }
  | {
      kind: "ready";
      notice: "completed" | "absent" | "unresolved" | null;
    };

type ReviewAction =
  | {
      key: "start";
      kind: "start";
      acknowledgeInputChange: boolean;
    }
  | {
      key: `review:${string}`;
      kind: "review";
      step: GateReviewSelectedStepViewModel;
    }
  | {
      key: `request_exception:${string}`;
      kind: "request_exception";
      option: GateReviewExceptionRequestOptionViewModel;
    }
  | {
      key: `decide_exception:${string}`;
      kind: "decide_exception";
      exception: GateReviewExceptionViewModel;
    }
  | { key: "decide_gate"; kind: "decide_gate" }
  | { key: "reopen"; kind: "reopen" };

interface PreparedCommand {
  actorUserId: string;
  actionLabel: string;
  idempotencyKey: string;
  issuedAt: string;
  operation: GateReviewCommandOperation;
  run: (context: GateReviewCommandContext) => Promise<GateReviewViewModel>;
}

interface CommandFailureState {
  actionLabel: string;
  failure: RequestFailure;
  failureKind: FailureKind;
}

type CoordinatedCommandState = "pending" | "fulfilled" | "rejected";

interface CoordinatedCommand {
  cleanupTimer?: ReturnType<typeof globalThis.setTimeout>;
  completion: Promise<void>;
  error?: unknown;
  prepared: PreparedCommand;
  result?: GateReviewViewModel;
  state: CoordinatedCommandState;
}

const coordinatedCommands = new Map<string, CoordinatedCommand>();
const coordinatedCommandRetentionMilliseconds = 30_000;

export const GATE_REVIEW_RECEIPT_STORAGE_KEY =
  "npi-one:gate-review-command-receipt";

interface GateReviewReceiptMarker {
  operation: GateReviewCommandOperation;
  key: string;
  project: string;
  gate: string;
  actor: string;
  issuedAt: string;
}

const markerUuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const markerKeyPattern = /^[!-~]{16,255}$/u;
const markerTimestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/u;
const markerOperations = new Set<GateReviewCommandOperation>([
  "gate.review.start",
  "gate.review.submit",
  "gate.review.exception.request",
  "gate.review.exception.decide",
  "gate.review.decide",
  "gate.review.reopen",
]);

function parseReceiptMarker(source: string): GateReviewReceiptMarker | null {
  let value: unknown;
  try {
    value = JSON.parse(source);
  } catch {
    return null;
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const marker = value as Record<string, unknown>;
  const keys = ["operation", "key", "project", "gate", "actor", "issuedAt"];
  if (
    Object.keys(marker).length !== keys.length ||
    !keys.every((key) => Object.hasOwn(marker, key)) ||
    typeof marker.operation !== "string" ||
    !markerOperations.has(marker.operation as GateReviewCommandOperation) ||
    typeof marker.key !== "string" ||
    !markerKeyPattern.test(marker.key) ||
    typeof marker.project !== "string" ||
    !markerUuidPattern.test(marker.project) ||
    typeof marker.gate !== "string" ||
    !markerUuidPattern.test(marker.gate) ||
    typeof marker.actor !== "string" ||
    marker.actor.length < 1 ||
    marker.actor.length > 254 ||
    /[\r\n]/u.test(marker.actor) ||
    typeof marker.issuedAt !== "string" ||
    !markerTimestampPattern.test(marker.issuedAt) ||
    Number.isNaN(Date.parse(marker.issuedAt))
  ) {
    return null;
  }
  return marker as unknown as GateReviewReceiptMarker;
}

function markersMatch(
  left: GateReviewReceiptMarker,
  right: GateReviewReceiptMarker,
): boolean {
  return (
    left.operation === right.operation &&
    left.key === right.key &&
    left.project === right.project &&
    left.gate === right.gate &&
    left.actor.toLowerCase() === right.actor.toLowerCase() &&
    left.issuedAt === right.issuedAt
  );
}

function readReceiptMarker(): GateReviewReceiptMarker | null {
  try {
    const source = globalThis.sessionStorage.getItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
    );
    return source ? parseReceiptMarker(source) : null;
  } catch {
    return null;
  }
}

function persistReceiptMarker(marker: GateReviewReceiptMarker): boolean {
  try {
    const existingSource = globalThis.sessionStorage.getItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
    );
    if (existingSource) {
      const existing = parseReceiptMarker(existingSource);
      if (!existing || !markersMatch(existing, marker)) return false;
    }
    globalThis.sessionStorage.setItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
      JSON.stringify(marker),
    );
    const persistedSource = globalThis.sessionStorage.getItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
    );
    const persisted = persistedSource
      ? parseReceiptMarker(persistedSource)
      : null;
    return persisted !== null && markersMatch(persisted, marker);
  } catch {
    return false;
  }
}

function clearReceiptMarker(marker: GateReviewReceiptMarker): void {
  try {
    const current = readReceiptMarker();
    if (current && markersMatch(current, marker)) {
      globalThis.sessionStorage.removeItem(GATE_REVIEW_RECEIPT_STORAGE_KEY);
    }
  } catch {
    // Storage cleanup is best-effort; a surviving marker remains fail-closed.
  }
}

function markerForCommand(
  projectGlobalId: string,
  gateGlobalId: string,
  prepared: PreparedCommand,
): GateReviewReceiptMarker {
  return {
    operation: prepared.operation,
    key: prepared.idempotencyKey,
    project: projectGlobalId,
    gate: gateGlobalId,
    actor: prepared.actorUserId,
    issuedAt: prepared.issuedAt,
  };
}

function initialReceiptRecoveryState(): GateReviewReceiptRecoveryState {
  const marker = readReceiptMarker();
  return marker
    ? { epoch: 0, kind: "pending", marker }
    : { kind: "ready", notice: null };
}

function waitForReceiptRetry(
  milliseconds: number,
  signal: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new GateReviewRequestCancelledError());
      return;
    }
    const timeoutId = globalThis.setTimeout(() => {
      signal.removeEventListener("abort", cancel);
      resolve();
    }, milliseconds);
    const cancel = (): void => {
      globalThis.clearTimeout(timeoutId);
      reject(new GateReviewRequestCancelledError());
    };
    signal.addEventListener("abort", cancel, { once: true });
  });
}

function commandRouteKey(
  projectGlobalId: string,
  gateGlobalId: string,
): string {
  return `${projectGlobalId}:${gateGlobalId}`;
}

function lockPageUnload(event: BeforeUnloadEvent): void {
  if (
    [...coordinatedCommands.values()].some(
      (command) => command.state === "pending",
    )
  ) {
    event.preventDefault();
    // The legacy assignment remains required for browsers that do not act on
    // preventDefault alone when a native unload confirmation is requested.
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    event.returnValue = "";
  }
}

let pageUnloadLocked = false;

function synchronizePageUnloadLock(): void {
  const shouldLock = [...coordinatedCommands.values()].some(
    (command) => command.state === "pending",
  );
  if (shouldLock === pageUnloadLocked) return;
  pageUnloadLocked = shouldLock;
  if (shouldLock) {
    globalThis.addEventListener("beforeunload", lockPageUnload);
  } else {
    globalThis.removeEventListener("beforeunload", lockPageUnload);
  }
}

function startCoordinatedCommand(
  key: string,
  prepared: PreparedCommand,
  csrfToken: string,
): CoordinatedCommand {
  const existing = coordinatedCommands.get(key);
  if (existing) return existing;
  const controller = new AbortController();
  const command: CoordinatedCommand = {
    completion: Promise.resolve(),
    prepared,
    state: "pending",
  };
  coordinatedCommands.set(key, command);
  synchronizePageUnloadLock();
  command.completion = Promise.resolve()
    .then(() =>
      prepared.run({
        csrfToken,
        idempotencyKey: prepared.idempotencyKey,
        signal: controller.signal,
      }),
    )
    .then(
      (result) => {
        command.result = result;
        command.state = "fulfilled";
      },
      (error: unknown) => {
        command.error = error;
        command.state = "rejected";
      },
    )
    .finally(() => {
      synchronizePageUnloadLock();
      command.cleanupTimer = globalThis.setTimeout(() => {
        clearCoordinatedCommand(key, command);
      }, coordinatedCommandRetentionMilliseconds);
    });
  return command;
}

function clearCoordinatedCommand(
  key: string,
  command: CoordinatedCommand,
): void {
  if (coordinatedCommands.get(key) === command) {
    if (command.cleanupTimer !== undefined) {
      globalThis.clearTimeout(command.cleanupTimer);
      delete command.cleanupTimer;
    }
    coordinatedCommands.delete(key);
    synchronizePageUnloadLock();
  }
}

const source = {
  sourceSystem: "NPI_ONE" as const,
  editableIn: "NPI_ONE" as const,
  syncState: "local" as const,
};

function classifyFailure(failure: RequestFailure): FailureKind {
  if (failure.kind === "request_not_ready") return "validation";
  if (failure.kind === "network" || failure.kind === "invalid_response")
    return "retryable";
  const status = failure.problem?.status;
  if (status === 404) return "not_found";
  if (status === 401 || status === 403) return "no_permission";
  if (status === 422) return "validation";
  if (status === 409) return "conflict";
  if (failure.problem?.retryable) return "retryable";
  return "final";
}

function evidenceStateTone(
  state: GateRequirementEvidenceState,
): "neutral" | "info" | "success" | "warning" | "danger" {
  switch (state) {
    case "missing":
    case "scan_failed":
    case "scan_infected":
      return "danger";
    case "scan_pending":
      return "warning";
    case "scan_clean":
      return "success";
    case "attached":
      return "info";
  }
}

function scanStateTone(
  state: GateEvidenceScanState,
): "success" | "warning" | "danger" {
  switch (state) {
    case "clean":
      return "success";
    case "pending":
      return "warning";
    case "failed":
    case "infected":
      return "danger";
  }
}

function stepStateTone(
  state: GateReviewSelectedStepViewModel["state"],
): "neutral" | "info" | "success" | "danger" {
  switch (state) {
    case "waiting":
      return "neutral";
    case "available":
      return "info";
    case "approved":
      return "success";
    case "rejected":
      return "danger";
  }
}

function reviewStateTone(
  state: GateReviewViewModel["gate"]["reviewState"],
): "neutral" | "info" | "success" | "warning" {
  switch (state) {
    case "not_started":
      return "neutral";
    case "in_review":
      return "info";
    case "decided":
      return "success";
    case "requires_review":
      return "warning";
  }
}

function cycleStateTone(
  state: NonNullable<GateReviewViewModel["activeCycle"]>["state"],
): "info" | "success" | "warning" {
  switch (state) {
    case "active":
      return "info";
    case "decided":
      return "success";
    case "invalidated":
    case "superseded":
      return "warning";
  }
}

function actionLabel(t: Translator, action: ReviewAction): string {
  switch (action.kind) {
    case "start":
      return action.acknowledgeInputChange
        ? t("Acknowledge change and start review")
        : t("Start review");
    case "review":
      return t("Submit review");
    case "request_exception":
      return t("Request controlled exception");
    case "decide_exception":
      return t("Decide exception");
    case "decide_gate":
      return t("Decide Gate");
    case "reopen":
      return t("Reopen Gate");
  }
}

function actionAccessibleLabel(t: Translator, action: ReviewAction): string {
  switch (action.kind) {
    case "review":
      return t("Submit review: {{step}}", { step: action.step.stepKey });
    case "request_exception":
      return t("Request exception: {{requirement}} / {{kind}}", {
        kind: action.option.kind,
        requirement: action.option.requirementKey,
      });
    case "decide_exception":
      return t("Decide exception: {{requirement}} / {{kind}}", {
        kind: action.exception.kind,
        requirement: action.exception.requirementKey,
      });
    case "start":
    case "decide_gate":
    case "reopen":
      return actionLabel(t, action);
  }
}

function actionIdentifierTokens(action: ReviewAction): string | undefined {
  const tokens = (() => {
    switch (action.kind) {
      case "review":
        return [action.step.stepKey];
      case "request_exception":
        return [action.option.requirementKey, action.option.kind];
      case "decide_exception":
        return [action.exception.requirementKey, action.exception.kind];
      case "start":
      case "decide_gate":
      case "reopen":
        return [];
    }
  })();
  return tokens.length > 0 ? JSON.stringify(tokens) : undefined;
}

function GateReviewLoadingSurface(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <article className="page page--object">
      <section
        aria-busy="true"
        aria-label={t("Loading Gate Review Room")}
        className="state-surface state-surface--loading"
        role="status"
      >
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <div className="skeleton" />
        <span className="visually-hidden">{t("Loading Gate Review Room")}</span>
      </section>
    </article>
  );
}

function GateReviewFailureSurface({
  failure,
  failureKind,
  navigate,
  projectGlobalId,
  retry,
}: {
  failure: RequestFailure;
  failureKind: FailureKind;
  navigate: (target: string) => void;
  projectGlobalId: string;
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const content = {
    not_found: {
      title: t("Gate Review Room is unavailable"),
      detail: t(
        "The Gate Review Room was not found or is not available to your account.",
      ),
    },
    no_permission: {
      title: t("Gate review access is not available"),
      detail: t(
        "Your account cannot open this Gate Review Room. No protected review or evidence data was displayed.",
      ),
    },
    validation: {
      title: t("The Gate review address is invalid"),
      detail: t(
        "Open the Gate Review Room from an authorized Project Gate reference.",
      ),
    },
    conflict: {
      title: t("The Gate review workspace is out of date"),
      detail: t("Reload the Gate Review Room before continuing."),
    },
    retryable: {
      title: t("The Gate Review Room could not be loaded"),
      detail: t(
        "Retry the live Gate review request or share the displayed reference ID with support.",
      ),
    },
    final: {
      title: t("The Gate review response could not be used safely"),
      detail: t(
        "No Gate review data was displayed. Share the displayed reference ID with support before trying another action.",
      ),
    },
  }[failureKind];
  const canRetry = failureKind === "retryable" || failureKind === "conflict";
  return (
    <article className="page page--object">
      <section
        aria-labelledby="gate-review-error-title"
        className="state-surface"
      >
        <SemanticStatus
          label={failureKind === "conflict" ? t("Conflict") : t("Error")}
          tone={failureKind === "conflict" ? "warning" : "danger"}
        />
        <h1 id="gate-review-error-title">{content.title}</h1>
        <p>{content.detail}</p>
        <RequestFailurePanel failure={failure} />
        <div className="detail-actions">
          {canRetry ? (
            <Button icon="refresh" onClick={retry} visual="primary">
              {failureKind === "conflict"
                ? t("Reload Gate review")
                : t("Retry")}
            </Button>
          ) : null}
          <Button
            onClick={() => {
              navigate(
                failureKind === "validation"
                  ? "/work"
                  : `/projects/${projectGlobalId}`,
              );
            }}
            visual={canRetry ? "secondary" : "primary"}
          >
            {failureKind === "validation"
              ? t("Return to My Work")
              : t("Return to project")}
          </Button>
        </div>
      </section>
    </article>
  );
}

function RequirementTable({
  requirements,
  selectedRequirement,
  selectRequirement,
}: {
  requirements: readonly GateRequirementViewModel[];
  selectedRequirement: GateRequirementViewModel;
  selectRequirement: (requirement: GateRequirementViewModel) => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <table
      aria-label={t("Frozen Gate requirements")}
      className="data-table data-table--compact gate-requirements-table"
    >
      <thead>
        <tr>
          <th>{t("Requirement")}</th>
          <th>{t("Classification")}</th>
          <th>{t("Evidence state")}</th>
        </tr>
      </thead>
      <tbody>
        {requirements.map((requirement) => (
          <tr
            aria-selected={
              requirement.globalId === selectedRequirement.globalId
            }
            key={requirement.globalId}
          >
            <td>
              <button
                className="table-selection-button"
                onClick={() => {
                  selectRequirement(requirement);
                }}
                type="button"
              >
                <strong data-language-exempt="identifier">
                  {requirement.key}
                </strong>
                <span data-language-exempt="business-data">
                  {requirement.title}
                </span>
              </button>
            </td>
            <td>
              {gateRequirementClassificationLabel(
                t,
                requirement.classification,
              )}{" "}
              <span data-language-exempt="identifier">
                {requirement.priority}
              </span>
            </td>
            <td>
              <SemanticStatus
                label={gateRequirementEvidenceStateLabel(
                  t,
                  requirement.evidenceState,
                )}
                tone={evidenceStateTone(requirement.evidenceState)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ReviewStepsTable({
  cycle,
}: {
  cycle: GateReviewViewModel["activeCycle"];
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const steps = cycle?.selectedSteps ?? [];
  const reviewRecords = steps.flatMap((step) =>
    step.review ? [{ review: step.review, step }] : [],
  );
  return (
    <>
      <h3>{t("Selected review sequence")}</h3>
      {steps.length ? (
        <>
          <table
            aria-label={t("Selected review steps")}
            className="data-table data-table--compact gate-review-steps-table"
          >
            <thead>
              <tr>
                <th>{t("Sequence")}</th>
                <th>{t("Step")}</th>
                <th>{t("Assignment")}</th>
                <th>{t("Review state")}</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((step) => (
                <tr key={step.stepKey}>
                  <td>{formatNumber(locale, step.sequence, 0)}</td>
                  <td data-language-exempt="identifier">{step.stepKey}</td>
                  <td className="gate-review-step-assignment">
                    <span data-language-exempt="identifier">{step.slot}</span>
                    <span data-language-exempt="business-data">
                      {step.assignedMember.displayName}
                    </span>
                  </td>
                  <td>
                    <SemanticStatus
                      label={gateReviewStepStateLabel(t, step.state)}
                      tone={stepStateTone(step.state)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="context-help">
            {t(
              "Steps with the same sequence are reviewed in parallel. Later sequences remain unavailable until prior selected steps approve.",
            )}
          </p>
          <h4>{t("Immutable review records")}</h4>
          {reviewRecords.length ? (
            <table
              aria-label={t("Immutable review records")}
              className="data-table data-table--compact gate-review-records-table"
            >
              <thead>
                <tr>
                  <th>{t("Step")}</th>
                  <th>{t("Review Actor")}</th>
                  <th>{t("Reviewed At")}</th>
                  <th>{t("Review Outcome")}</th>
                  <th>{t("Review Opinion")}</th>
                  <th>{t("Reviewed Input Hash")}</th>
                  <th>{t("Review Record Snapshot Hash")}</th>
                  <th>{t("Review Policy Version")}</th>
                  <th>{t("Review Policy Snapshot Hash")}</th>
                </tr>
              </thead>
              <tbody>
                {reviewRecords.map(({ review, step }) => (
                  <tr key={review.globalId}>
                    <td data-language-exempt="identifier">{step.stepKey}</td>
                    <td data-language-exempt="business-data">{review.actor}</td>
                    <td>{formatDateTime(locale, review.reviewedAt)}</td>
                    <td>{gateReviewOutcomeLabel(t, review.outcome)}</td>
                    <td data-language-exempt="business-data">
                      {review.opinion}
                    </td>
                    <td data-language-exempt="identifier">
                      {review.inputHash}
                    </td>
                    <td data-language-exempt="identifier">
                      {review.snapshotHash}
                    </td>
                    <td>
                      {cycle
                        ? formatNumber(locale, cycle.policyRef.version, 0)
                        : t("Not applicable")}
                    </td>
                    <td data-language-exempt="identifier">
                      {cycle?.policyRef.snapshotHash ?? t("Not applicable")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="empty-inline">
              {t("No immutable review record has been captured in this cycle.")}
            </p>
          )}
        </>
      ) : (
        <p className="empty-inline">
          {t("No review sequence is active for this Gate.")}
        </p>
      )}
    </>
  );
}

function DecisionInputTables({
  decision,
}: {
  decision: GateReviewViewModel["decisions"][number];
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const { inputSnapshot } = decision.detail;
  return (
    <details className="gate-decision-input-detail">
      <summary>{t("Frozen decision input rows")}</summary>
      <section className="gate-decision-input-detail__section">
        <h4>{t("Frozen requirements")}</h4>
        <table
          aria-label={t("Frozen requirements")}
          className="data-table data-table--compact"
        >
          <thead>
            <tr>
              <th>{t("Requirement")}</th>
              <th>{t("Priority")}</th>
              <th>{t("Source Version")}</th>
              <th>{t("Source Hash")}</th>
              <th>{t("Evidence complete")}</th>
            </tr>
          </thead>
          <tbody>
            {inputSnapshot.requirements.length ? (
              inputSnapshot.requirements.map((requirement) => (
                <tr key={requirement.globalId}>
                  <td>
                    <span data-language-exempt="identifier">
                      {requirement.requirementKey}
                    </span>
                    <code data-language-exempt="identifier">
                      {requirement.globalId}
                    </code>
                  </td>
                  <td data-language-exempt="identifier">
                    {requirement.priority}
                  </td>
                  <td>{formatNumber(locale, requirement.sourceVersion, 0)}</td>
                  <td data-language-exempt="identifier">
                    {requirement.sourceHash}
                  </td>
                  <td>{requirement.evidenceComplete ? t("Yes") : t("No")}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>{t("None")}</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
      <section className="gate-decision-input-detail__section">
        <h4>{t("Frozen evidence")}</h4>
        <table
          aria-label={t("Frozen evidence")}
          className="data-table data-table--compact"
        >
          <thead>
            <tr>
              <th>{t("Evidence")}</th>
              <th>{t("Requirement global ID")}</th>
              <th>{t("Evidence Kind")}</th>
              <th>{t("Source Global ID")}</th>
              <th>{t("Source Version")}</th>
              <th>{t("Source Hash")}</th>
              <th>{t("Is file")}</th>
              <th>{t("File safe")}</th>
            </tr>
          </thead>
          <tbody>
            {inputSnapshot.evidence.length ? (
              inputSnapshot.evidence.map((reference) => (
                <tr key={reference.globalId}>
                  <td data-language-exempt="identifier">
                    {reference.globalId}
                  </td>
                  <td data-language-exempt="identifier">
                    {reference.requirementGlobalId}
                  </td>
                  <td>{gateEvidenceKindLabel(t, reference.evidenceKind)}</td>
                  <td data-language-exempt="identifier">
                    {reference.sourceGlobalId}
                  </td>
                  <td>{formatNumber(locale, reference.sourceVersion, 0)}</td>
                  <td data-language-exempt="identifier">
                    {reference.sourceHash}
                  </td>
                  <td>{reference.isFile ? t("Yes") : t("No")}</td>
                  <td>{reference.fileSafe ? t("Yes") : t("No")}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8}>{t("None")}</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
      <section className="gate-decision-input-detail__section">
        <h4>{t("Frozen blockers")}</h4>
        <table
          aria-label={t("Frozen blockers")}
          className="data-table data-table--compact"
        >
          <thead>
            <tr>
              <th>{t("Blocker global ID")}</th>
              <th>{t("Version")}</th>
              <th>{t("State")}</th>
              <th>{t("Blocking")}</th>
              <th>{t("Terminal")}</th>
            </tr>
          </thead>
          <tbody>
            {inputSnapshot.blockers.length ? (
              inputSnapshot.blockers.map((blocker) => (
                <tr key={blocker.globalId}>
                  <td data-language-exempt="identifier">{blocker.globalId}</td>
                  <td>{formatNumber(locale, blocker.version, 0)}</td>
                  <td data-language-exempt="identifier">{blocker.state}</td>
                  <td>{blocker.blocking ? t("Yes") : t("No")}</td>
                  <td>{blocker.terminal ? t("Yes") : t("No")}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>{t("None")}</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
      <section className="gate-decision-input-detail__section">
        <h4>{t("Frozen dependencies")}</h4>
        <table
          aria-label={t("Frozen dependencies")}
          className="data-table data-table--compact"
        >
          <thead>
            <tr>
              <th>{t("Dependency kind")}</th>
              <th>{t("Global ID")}</th>
              <th>{t("Version")}</th>
              <th>{t("Snapshot hash")}</th>
            </tr>
          </thead>
          <tbody>
            {inputSnapshot.dependencies.length ? (
              inputSnapshot.dependencies.map((dependency) => (
                <tr key={dependency.globalId}>
                  <td data-language-exempt="identifier">{dependency.kind}</td>
                  <td data-language-exempt="identifier">
                    {dependency.globalId}
                  </td>
                  <td>{formatNumber(locale, dependency.version, 0)}</td>
                  <td data-language-exempt="identifier">
                    {dependency.snapshotHash}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4}>{t("None")}</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </details>
  );
}

function EvidenceTable({
  evidence,
  selectedEvidence,
  selectEvidence,
}: {
  evidence: readonly GateEvidenceReferenceViewModel[];
  selectedEvidence: GateEvidenceReferenceViewModel | null;
  selectEvidence: (evidence: GateEvidenceReferenceViewModel) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  return (
    <table
      aria-label={t("Controlled evidence")}
      className="data-table data-table--compact gate-evidence-table"
    >
      <thead>
        <tr>
          <th>{t("Evidence")}</th>
          <th>{t("Revision")}</th>
          <th>{t("Scan State")}</th>
        </tr>
      </thead>
      <tbody>
        {evidence.length ? (
          evidence.map((reference) => (
            <tr
              aria-selected={reference.globalId === selectedEvidence?.globalId}
              key={reference.globalId}
            >
              <td>
                <button
                  className="table-selection-button"
                  onClick={() => {
                    selectEvidence(reference);
                  }}
                  type="button"
                >
                  {gateEvidenceKindLabel(t, reference.kind)}
                  <span data-language-exempt="identifier">
                    {reference.sourceGlobalId}
                  </span>
                </button>
              </td>
              <td>{formatNumber(locale, reference.revision, 0)}</td>
              <td>
                {reference.file ? (
                  <SemanticStatus
                    label={gateEvidenceScanStateLabel(
                      t,
                      reference.file.scanState,
                    )}
                    tone={scanStateTone(reference.file.scanState)}
                  />
                ) : (
                  t("Not applicable")
                )}
              </td>
            </tr>
          ))
        ) : (
          <tr>
            <td colSpan={3}>{t("No controlled evidence is attached.")}</td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function SelectedEvidenceDetail({
  selectedEvidence,
}: {
  selectedEvidence: GateEvidenceReferenceViewModel | null;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (!selectedEvidence) {
    return (
      <p className="context-help">
        {t(
          "Select a requirement with evidence to inspect its exact controlled reference.",
        )}
      </p>
    );
  }
  return (
    <div className="gate-evidence-detail">
      <DefinitionList
        rows={[
          {
            label: t("Evidence kind"),
            value: gateEvidenceKindLabel(t, selectedEvidence.kind),
          },
          {
            label: t("Source object type"),
            value: gateEvidenceKindLabel(t, selectedEvidence.sourceObjectType),
          },
          {
            label: t("Source global ID"),
            value: selectedEvidence.sourceGlobalId,
            exempt: "identifier",
          },
          {
            label: t("Exact revision"),
            value: formatNumber(locale, selectedEvidence.revision, 0),
          },
          {
            label: t("Object hash"),
            value: selectedEvidence.objectHash,
            exempt: "identifier",
          },
          {
            label: t("Recorded"),
            value: formatDateTime(locale, selectedEvidence.createdAt),
          },
          {
            label: t("Recorded by"),
            value: selectedEvidence.createdBy,
            exempt: "business-data",
          },
          ...(selectedEvidence.file
            ? [
                {
                  label: t("File name"),
                  value: selectedEvidence.file.fileName,
                  exempt: "business-data" as const,
                },
                {
                  label: t("File media type"),
                  value: selectedEvidence.file.mimeType,
                  exempt: "identifier" as const,
                },
                {
                  label: t("File size"),
                  value: (
                    <>
                      {formatNumber(locale, selectedEvidence.file.sizeBytes, 0)}{" "}
                      <span data-language-exempt="unit">B</span>
                    </>
                  ),
                },
                {
                  label: t("Scan State"),
                  value: gateEvidenceScanStateLabel(
                    t,
                    selectedEvidence.file.scanState,
                  ),
                },
              ]
            : []),
        ]}
      />
    </div>
  );
}

function impactDetails(
  t: Translator,
  action: ReviewAction,
  view: GateReviewViewModel,
): ImpactReviewDetails {
  const cycleVersion = view.activeCycle?.version ?? 0;
  const version = `gate@${String(view.gate.version)}/cycle@${String(cycleVersion)}`;
  switch (action.kind) {
    case "request_exception":
      return {
        objectIdentity: view.gate.key,
        version,
        impact: t(
          "The request will record a bounded exception against the selected frozen requirement and closure action.",
        ),
        permission: t(
          "The server requires current exception-request permission under the exact review policy.",
        ),
        irreversible: t(
          "A successful request is preserved as controlled review history and cannot be overwritten.",
        ),
        failureHandling: t(
          "No exception is shown until the server returns the validated updated review workspace.",
        ),
        audit: t(
          "The request records the authenticated actor, reason, risk, expiry, input hash, and trace identity.",
        ),
      };
    case "decide_exception":
      return {
        objectIdentity: action.exception.globalId,
        version,
        impact: t(
          "The selected pending exception will receive one final approval or rejection opinion.",
        ),
        permission: t(
          "The exact exception authority and current internal Project membership are required.",
        ),
        irreversible: t(
          "A successful exception decision is append-only and cannot be replaced.",
        ),
        failureHandling: t(
          "No exception decision is shown until the server confirms the immutable result.",
        ),
        audit: t(
          "The decision records the authenticated authority, complete opinion, versions, input hash, and trace identity.",
        ),
      };
    case "decide_gate":
      return {
        objectIdentity: view.gate.key,
        version,
        impact: t(
          "The server will re-resolve evidence, blockers, exceptions, reviews, and input versions before creating an immutable decision snapshot.",
        ),
        permission: t(
          "The exact policy decision authority and current internal Project membership are required.",
        ),
        irreversible: t(
          "A successful decision creates immutable history; rejection does not delete evidence or reviews.",
        ),
        failureHandling: t(
          "No Gate decision is shown until the server returns a validated immutable snapshot and updated workspace.",
        ),
        audit: t(
          "The decision records the authenticated authority, exact outcome, versions, input hash, snapshot hash, and trace identity.",
        ),
      };
    case "reopen":
      return {
        objectIdentity: view.gate.key,
        version,
        impact: t(
          "A new review cycle will freeze current inputs and reset review progress without copying prior approvals.",
        ),
        permission: t(
          "The exact reopen authority and current internal Project membership are required.",
        ),
        irreversible: t(
          "The prior decision and its immutable snapshot remain preserved in history.",
        ),
        failureHandling: t(
          "The existing decision remains unchanged unless the server confirms a new active cycle.",
        ),
        audit: t(
          "The reopen event records the authenticated authority, reason, prior decision, versions, input hash, and trace identity.",
        ),
      };
    case "start":
    case "review":
      throw new Error("This action does not use an impact review.");
  }
}

function GateReviewWorkspace({
  dataSource,
  onReceiptRecoveryRequired,
  onTerminalFailure,
  receiptNotice,
  reload,
  replaceReview,
  view,
}: {
  dataSource: GateReviewDataSource;
  onReceiptRecoveryRequired: () => void;
  onTerminalFailure: (
    failure: RequestFailure,
    failureKind: FailureKind,
  ) => void;
  receiptNotice: "completed" | "absent" | "unresolved" | null;
  reload: () => void;
  replaceReview: (review: GateReviewViewModel) => void;
  view: GateReviewViewModel;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const { project, gate, evidence, activeCycle, permissions } = view;
  const commandKey = commandRouteKey(project.globalId, gate.globalId);
  const coordinatedCommand = coordinatedCommands.get(commandKey);
  const [selectedRequirementId, setSelectedRequirementId] = useState(
    evidence.requirements[0]?.globalId ?? "",
  );
  const selectedRequirementCandidate =
    evidence.requirements.find(
      (requirement) => requirement.globalId === selectedRequirementId,
    ) ?? evidence.requirements[0];
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(
    selectedRequirementCandidate?.evidence[0]?.globalId ?? "",
  );
  const [selectedActionKey, setSelectedActionKey] = useState("");
  const [selectedPolicyKey, setSelectedPolicyKey] = useState("");
  const [bindingSelections, setBindingSelections] = useState<
    Readonly<Record<string, string>>
  >({});
  const [reviewOutcome, setReviewOutcome] =
    useState<GateReviewOutcome>("approved");
  const [reviewOpinion, setReviewOpinion] = useState("");
  const [exceptionRisk, setExceptionRisk] = useState("");
  const [exceptionExpiryDate, setExceptionExpiryDate] = useState("");
  const [selectedClosureActionId, setSelectedClosureActionId] = useState("");
  const [exceptionDecisionOutcome, setExceptionDecisionOutcome] =
    useState<GateReviewOutcome>("approved");
  const [gateDecisionOutcome, setGateDecisionOutcome] =
    useState<GateDecisionOutcome>("pass");
  const [impactAction, setImpactAction] = useState<ReviewAction | null>(null);
  const [processingLabel, setProcessingLabel] = useState<string | null>(
    coordinatedCommand?.prepared.actionLabel ?? null,
  );
  const [commandFailure, setCommandFailure] =
    useState<CommandFailureState | null>(null);
  const [confirmedMessage, setConfirmedMessage] = useState<string | null>(null);
  const [retryCommand, setRetryCommand] = useState<PreparedCommand | null>(
    null,
  );
  const [commandEpoch, setCommandEpoch] = useState(0);
  if (!selectedRequirementCandidate) {
    throw new Error("A validated Gate review response has no requirements.");
  }
  const selectedRequirement = selectedRequirementCandidate;
  const selectedEvidence =
    selectedRequirement.evidence.find(
      (reference) => reference.globalId === selectedEvidenceId,
    ) ??
    selectedRequirement.evidence[0] ??
    null;
  const activePolicy = activeCycle?.policyDefinition;
  const selectablePolicies = view.availablePolicies;
  const frozenBindingsAreEligible = Boolean(
    activeCycle?.bindings.every((binding) =>
      view.eligibleMembers.some(
        (member) =>
          member.memberGlobalId === binding.memberGlobalId &&
          member.userId === binding.userId &&
          member.displayName === binding.displayName,
      ),
    ),
  );
  const actions = useMemo<readonly ReviewAction[]>(() => {
    const next: ReviewAction[] = [];
    const currentUserId = sessionCommandContext?.userId.toLowerCase();
    if (gate.reviewState === "requires_review") {
      if (permissions.canStartReview) {
        next.push({
          acknowledgeInputChange: true,
          key: "start",
          kind: "start",
        });
      }
      return next;
    }
    if (permissions.canApproveException && activeCycle?.state === "active") {
      for (const exception of activeCycle.exceptions) {
        if (
          exception.state === "pending" &&
          exception.allowedOutcomes.length > 0
        ) {
          next.push({
            key: `decide_exception:${exception.globalId}`,
            kind: "decide_exception",
            exception,
          });
        }
      }
    }
    if (permissions.canReview && activeCycle?.state === "active") {
      for (const step of activeCycle.selectedSteps) {
        if (
          step.state === "available" &&
          currentUserId &&
          step.assignedMember.userId.toLowerCase() === currentUserId
        ) {
          next.push({
            key: `review:${step.stepKey}`,
            kind: "review",
            step,
          });
        }
      }
    }
    if (
      permissions.canDecide &&
      activeCycle?.state === "active" &&
      view.decisionReadiness.allowedOutcomes.length > 0
    ) {
      next.push({ key: "decide_gate", kind: "decide_gate" });
    }
    if (permissions.canRequestException && activeCycle?.state === "active") {
      for (const option of view.exceptionRequestOptions) {
        if (
          option.requirementGlobalId === selectedRequirement.globalId &&
          option.requirementKey === selectedRequirement.key
        ) {
          next.push({
            key: `request_exception:${option.requirementGlobalId}:${option.kind}`,
            kind: "request_exception",
            option,
          });
        }
      }
    }
    if (permissions.canReopen && activeCycle?.state === "decided") {
      next.push({ key: "reopen", kind: "reopen" });
    }
    if (permissions.canStartReview && activeCycle === null) {
      next.push({
        acknowledgeInputChange: false,
        key: "start",
        kind: "start",
      });
    }
    return next;
  }, [
    activeCycle,
    gate.reviewState,
    permissions,
    selectedRequirement.globalId,
    selectedRequirement.key,
    sessionCommandContext?.userId,
    view.decisionReadiness.allowedOutcomes,
    view.exceptionRequestOptions,
  ]);
  const selectedAction =
    actions.find((action) => action.key === selectedActionKey) ?? actions[0];
  const selectedPolicy =
    gate.reviewState === "requires_review"
      ? activePolicy
      : (selectablePolicies.find(
          (policy) =>
            `${policy.policyRef.globalId}:${String(policy.policyRef.version)}:${policy.policyRef.snapshotHash}` ===
            selectedPolicyKey,
        ) ?? selectablePolicies[0]);
  const effectiveSelectedPolicyKey = selectedPolicy
    ? `${selectedPolicy.policyRef.globalId}:${String(selectedPolicy.policyRef.version)}:${selectedPolicy.policyRef.snapshotHash}`
    : "";
  const eligibleMemberIds = new Set(
    view.eligibleMembers.map((member) => member.memberGlobalId),
  );
  const effectiveBindingSelections: Readonly<Record<string, string>> =
    Object.fromEntries(
      (selectedPolicy?.authoritySlots ?? []).map((authority) => {
        const selectedMember = bindingSelections[authority.slot];
        return [
          authority.slot,
          selectedMember && eligibleMemberIds.has(selectedMember)
            ? selectedMember
            : (view.eligibleMembers[0]?.memberGlobalId ?? ""),
        ];
      }),
    );
  const allowedClosureActions =
    selectedAction?.kind === "request_exception"
      ? view.eligibleClosureActions.filter((closureAction) =>
          selectedAction.option.closureActionGlobalIds.includes(
            closureAction.globalId,
          ),
        )
      : [];
  const selectedClosureAction =
    allowedClosureActions.find(
      (closureAction) => closureAction.globalId === selectedClosureActionId,
    ) ?? allowedClosureActions[0];
  const effectiveClosureActionId = selectedClosureAction?.globalId ?? "";
  const effectiveExceptionDecisionOutcome =
    selectedAction?.kind === "decide_exception" &&
    selectedAction.exception.allowedOutcomes.includes(exceptionDecisionOutcome)
      ? exceptionDecisionOutcome
      : ((selectedAction?.kind === "decide_exception"
          ? selectedAction.exception.allowedOutcomes[0]
          : undefined) ?? "rejected");
  const effectiveGateDecisionOutcome =
    view.decisionReadiness.allowedOutcomes.includes(gateDecisionOutcome)
      ? gateDecisionOutcome
      : (view.decisionReadiness.allowedOutcomes[0] ?? "reject");
  const currentDependencyChange =
    gate.reviewState === "requires_review" &&
    activeCycle?.trigger === "dependency_change" &&
    view.dependencyChanges[0]?.successorCycleGlobalId ===
      activeCycle.globalId &&
    view.dependencyChanges[0].newInputHash === activeCycle.inputHash
      ? view.dependencyChanges[0]
      : undefined;
  const inputChanged = currentDependencyChange !== undefined;

  useEffect(() => {
    let current = true;
    const attachTimer = globalThis.setTimeout(() => {
      if (!current) return;
      const command = coordinatedCommands.get(commandKey);
      if (!command) {
        const receiptMarker = readReceiptMarker();
        if (
          receiptMarker?.actor.toLowerCase() ===
          sessionCommandContext?.userId.toLowerCase()
        ) {
          onReceiptRecoveryRequired();
          return;
        }
        setProcessingLabel(null);
        return;
      }
      setProcessingLabel(command.prepared.actionLabel);
      if (!sessionCommandContext) return;
      if (
        sessionCommandContext.userId.toLowerCase() !==
        command.prepared.actorUserId.toLowerCase()
      ) {
        const reconcileActorRotation = (): void => {
          if (
            !current ||
            coordinatedCommands.get(commandKey) !== command ||
            command.state === "pending"
          ) {
            return;
          }
          const receiptMarker = markerForCommand(
            project.globalId,
            gate.globalId,
            command.prepared,
          );
          if (command.state === "fulfilled" && command.result) {
            clearReceiptMarker(receiptMarker);
          } else {
            const failure = toRequestFailure(command.error);
            if (
              failure.kind === "problem" ||
              failure.kind === "request_not_ready"
            ) {
              clearReceiptMarker(receiptMarker);
            }
          }
          clearCoordinatedCommand(commandKey, command);
          setProcessingLabel(null);
          setCommandFailure(null);
          setConfirmedMessage(null);
          setRetryCommand(null);
          reload();
        };
        if (command.state === "pending") {
          void command.completion.then(reconcileActorRotation);
        } else {
          reconcileActorRotation();
        }
        return;
      }
      const reconcile = (): void => {
        if (
          !current ||
          coordinatedCommands.get(commandKey) !== command ||
          command.state === "pending"
        ) {
          return;
        }
        clearCoordinatedCommand(commandKey, command);
        setProcessingLabel(null);
        const receiptMarker = markerForCommand(
          project.globalId,
          gate.globalId,
          command.prepared,
        );
        if (command.state === "fulfilled" && command.result) {
          clearReceiptMarker(receiptMarker);
          setRetryCommand(null);
          setConfirmedMessage(
            t("The server confirmed the review workspace update."),
          );
          replaceReview(command.result);
          return;
        }
        const failure = toRequestFailure(command.error);
        const failureKind = classifyFailure(failure);
        if (
          failure.kind === "problem" ||
          failure.kind === "request_not_ready"
        ) {
          clearReceiptMarker(receiptMarker);
        }
        if (failureKind === "not_found" || failureKind === "no_permission") {
          onTerminalFailure(failure, failureKind);
          return;
        }
        setCommandFailure({
          actionLabel: command.prepared.actionLabel,
          failure,
          failureKind,
        });
        setRetryCommand(failureKind === "retryable" ? command.prepared : null);
      };
      if (command.state === "pending") {
        void command.completion.then(reconcile);
      } else {
        reconcile();
      }
    }, 0);
    return () => {
      current = false;
      globalThis.clearTimeout(attachTimer);
    };
  }, [
    commandEpoch,
    commandKey,
    gate.globalId,
    onReceiptRecoveryRequired,
    onTerminalFailure,
    project.globalId,
    reload,
    replaceReview,
    sessionCommandContext,
    t,
  ]);

  const selectRequirement = (requirement: GateRequirementViewModel): void => {
    setSelectedRequirementId(requirement.globalId);
    setSelectedEvidenceId(requirement.evidence[0]?.globalId ?? "");
    setSelectedActionKey("");
    setCommandFailure(null);
    setConfirmedMessage(null);
  };

  const executeCommand = useCallback(
    (prepared: PreparedCommand): void => {
      const commandContext = sessionCommandContext;
      if (
        coordinatedCommands.has(commandKey) ||
        commandContext?.userId !== prepared.actorUserId
      ) {
        return;
      }
      const receiptMarker = markerForCommand(
        project.globalId,
        gate.globalId,
        prepared,
      );
      if (!persistReceiptMarker(receiptMarker)) {
        const failure: RequestFailure = {
          kind: "request_not_ready",
          referenceId: `client-${globalThis.crypto.randomUUID()}`,
          referenceKind: "client",
        };
        setCommandFailure({
          actionLabel: prepared.actionLabel,
          failure,
          failureKind: "validation",
        });
        setRetryCommand(null);
        return;
      }
      setProcessingLabel(prepared.actionLabel);
      setCommandFailure(null);
      setConfirmedMessage(null);
      startCoordinatedCommand(commandKey, prepared, commandContext.csrfToken);
      setCommandEpoch((current) => current + 1);
    },
    [commandKey, gate.globalId, project.globalId, sessionCommandContext],
  );

  const prepareCommand = (
    action: ReviewAction,
    reason = "",
  ): PreparedCommand | null => {
    if (!sessionCommandContext) return null;
    const actorUserId = sessionCommandContext.userId;
    const idempotencyKey = `gate-review:${globalThis.crypto.randomUUID()}`;
    const issuedAt = new Date().toISOString();
    const preparedLabel = actionLabel(t, action);
    if (action.kind === "start") {
      const commandPolicy = action.acknowledgeInputChange
        ? activeCycle?.policyDefinition
        : selectedPolicy;
      if (!commandPolicy) return null;
      const bindings: readonly GateReviewBindingInput[] =
        action.acknowledgeInputChange && activeCycle
          ? activeCycle.bindings.map((binding) => ({
              memberGlobalId: binding.memberGlobalId,
              slot: binding.slot,
            }))
          : commandPolicy.authoritySlots.map((authority) => ({
              memberGlobalId: effectiveBindingSelections[authority.slot] ?? "",
              slot: authority.slot,
            }));
      if (bindings.some((binding) => !binding.memberGlobalId)) return null;
      if (
        action.acknowledgeInputChange &&
        (!activeCycle || !currentDependencyChange || !frozenBindingsAreEligible)
      ) {
        return null;
      }
      return {
        actorUserId,
        actionLabel: preparedLabel,
        idempotencyKey,
        issuedAt,
        operation: "gate.review.start",
        run: (context) =>
          dataSource.startReview(
            project.globalId,
            gate.globalId,
            {
              expectedGateVersion: gate.version,
              policyGlobalId: commandPolicy.policyRef.globalId,
              policySnapshotHash: commandPolicy.policyRef.snapshotHash,
              policyVersion: commandPolicy.policyRef.version,
              bindings,
            },
            context,
          ),
      };
    }
    if (!activeCycle) return null;
    switch (action.kind) {
      case "review":
        if (!reviewOpinion.trim()) return null;
        return {
          actorUserId,
          actionLabel: preparedLabel,
          idempotencyKey,
          issuedAt,
          operation: "gate.review.submit",
          run: (context) =>
            dataSource.submitReview(
              project.globalId,
              gate.globalId,
              activeCycle.globalId,
              {
                expectedCycleVersion: activeCycle.version,
                expectedInputHash: activeCycle.inputHash,
                stepKey: action.step.stepKey,
                outcome: reviewOutcome,
                opinion: reviewOpinion.trim(),
              },
              context,
            ),
        };
      case "request_exception": {
        if (
          !exceptionRisk.trim() ||
          !exceptionExpiryDate ||
          !selectedClosureAction ||
          !reason.trim()
        ) {
          return null;
        }
        return {
          actorUserId,
          actionLabel: preparedLabel,
          idempotencyKey,
          issuedAt,
          operation: "gate.review.exception.request",
          run: (context) =>
            dataSource.requestException(
              project.globalId,
              gate.globalId,
              activeCycle.globalId,
              {
                closureActionGlobalId: selectedClosureAction.globalId,
                expectedCycleVersion: activeCycle.version,
                expectedInputHash: activeCycle.inputHash,
                expiresAt: `${exceptionExpiryDate}T23:59:59Z`,
                kind: action.option.kind,
                reason: reason.trim(),
                requirementGlobalId: action.option.requirementGlobalId,
                requirementKey: action.option.requirementKey,
                risk: exceptionRisk.trim(),
              },
              context,
            ),
        };
      }
      case "decide_exception":
        if (
          !reason.trim() ||
          !action.exception.allowedOutcomes.includes(
            effectiveExceptionDecisionOutcome,
          )
        ) {
          return null;
        }
        return {
          actorUserId,
          actionLabel: preparedLabel,
          idempotencyKey,
          issuedAt,
          operation: "gate.review.exception.decide",
          run: (context) =>
            dataSource.decideException(
              project.globalId,
              gate.globalId,
              activeCycle.globalId,
              action.exception.globalId,
              {
                expectedCycleVersion: activeCycle.version,
                expectedExceptionVersion: action.exception.version,
                expectedInputHash: activeCycle.inputHash,
                opinion: reason.trim(),
                outcome: effectiveExceptionDecisionOutcome,
              },
              context,
            ),
        };
      case "decide_gate":
        if (
          !view.decisionReadiness.allowedOutcomes.includes(
            effectiveGateDecisionOutcome,
          )
        ) {
          return null;
        }
        return {
          actorUserId,
          actionLabel: preparedLabel,
          idempotencyKey,
          issuedAt,
          operation: "gate.review.decide",
          run: (context) =>
            dataSource.decideGate(
              project.globalId,
              gate.globalId,
              {
                expectedCycleVersion: activeCycle.version,
                expectedGateVersion: gate.version,
                expectedInputHash: activeCycle.inputHash,
                outcome: effectiveGateDecisionOutcome,
              },
              context,
            ),
        };
      case "reopen": {
        if (!reason.trim()) return null;
        const bindings: readonly GateReviewBindingInput[] =
          activeCycle.bindings.map((binding) => ({
            slot: binding.slot,
            memberGlobalId: binding.memberGlobalId,
          }));
        return {
          actorUserId,
          actionLabel: preparedLabel,
          idempotencyKey,
          issuedAt,
          operation: "gate.review.reopen",
          run: (context) =>
            dataSource.reopenGate(
              project.globalId,
              gate.globalId,
              {
                bindings,
                expectedCycleVersion: activeCycle.version,
                expectedGateVersion: gate.version,
                expectedInputHash: activeCycle.inputHash,
                policyGlobalId: activeCycle.policyRef.globalId,
                policySnapshotHash: activeCycle.policyRef.snapshotHash,
                policyVersion: activeCycle.policyRef.version,
                reason: reason.trim(),
              },
              context,
            ),
        };
      }
    }
  };

  const actionReady = (() => {
    if (!selectedAction || !sessionCommandContext || processingLabel) {
      return false;
    }
    switch (selectedAction.kind) {
      case "start":
        if (selectedAction.acknowledgeInputChange) {
          return Boolean(
            activeCycle &&
            selectedPolicy &&
            currentDependencyChange &&
            frozenBindingsAreEligible,
          );
        }
        return Boolean(
          selectedPolicy &&
          selectedPolicy.authoritySlots.length > 0 &&
          selectedPolicy.authoritySlots.every(
            (authority) => effectiveBindingSelections[authority.slot],
          ),
        );
      case "review":
        return Boolean(reviewOpinion.trim());
      case "request_exception":
        return Boolean(
          exceptionRisk.trim() && exceptionExpiryDate && selectedClosureAction,
        );
      case "decide_exception":
        return selectedAction.exception.allowedOutcomes.includes(
          effectiveExceptionDecisionOutcome,
        );
      case "decide_gate":
        return view.decisionReadiness.allowedOutcomes.includes(
          effectiveGateDecisionOutcome,
        );
      case "reopen":
        return true;
    }
  })();

  const invokePrimaryAction = (): void => {
    if (!selectedAction || !actionReady) return;
    if (
      selectedAction.kind === "request_exception" ||
      selectedAction.kind === "decide_exception" ||
      selectedAction.kind === "decide_gate" ||
      selectedAction.kind === "reopen"
    ) {
      setImpactAction(selectedAction);
      return;
    }
    const prepared = prepareCommand(selectedAction);
    if (prepared) executeCommand(prepared);
  };

  const commandFailureContent = commandFailure
    ? {
        validation: {
          label: t("Validation error"),
          detail: t(
            "The server rejected the prepared command. Review the controlled field details and reload current Gate data before changing the request.",
          ),
        },
        conflict: {
          label: t("Version conflict"),
          detail: t(
            "The Gate, review cycle, or input version changed. Reload current data before preparing another command.",
          ),
        },
        retryable: {
          label: t("Retryable failure"),
          detail: t(
            "The command result is unconfirmed. Retry uses the same actor-bound idempotency key and does not claim success early.",
          ),
        },
        final: {
          label: t("Final failure"),
          detail: t(
            "The command did not complete. Share the reference ID with support before preparing another action.",
          ),
        },
        not_found: {
          label: t("Error"),
          detail: t("The protected Gate review context is unavailable."),
        },
        no_permission: {
          label: t("Error"),
          detail: t("The protected Gate review context is unavailable."),
        },
      }[commandFailure.failureKind]
    : null;

  const primaryAction =
    selectedAction && !impactAction && !commandFailure
      ? {
          disabled: !actionReady,
          label: processingLabel
            ? t("Processing Gate review command")
            : actionLabel(t, selectedAction),
          onClick: invokePrimaryAction,
        }
      : undefined;

  return (
    <article className="page page--object gate-review-room">
      {!sessionCommandContext ? (
        <div
          className="scenario-banner scenario-banner--read_only"
          role="status"
        >
          <SemanticStatus
            label={t("Review commands unavailable")}
            tone="info"
          />
          <span>
            {t(
              "Review commands are unavailable while the authenticated session context is unavailable.",
            )}
          </span>
        </div>
      ) : null}
      {activeCycle === null ? (
        <div className="scenario-banner scenario-banner--empty" role="status">
          <SemanticStatus label={t("No active review cycle")} />
          <span>
            {permissions.canStartReview
              ? t(
                  "Select an exact published policy and explicit authority bindings before starting review.",
                )
              : t(
                  "This Gate has no active review cycle and your current server permissions do not allow one to be started.",
                )}
          </span>
        </div>
      ) : null}
      {inputChanged ? (
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus
            label={t("Gate input snapshot changed")}
            tone="warning"
          />
          <span>
            {t(
              "The server recorded an exact Gate input snapshot hash change. This response does not claim a field-level object diff.",
            )}
          </span>
        </div>
      ) : null}
      {processingLabel ? (
        <div
          aria-busy="true"
          className="scenario-banner scenario-banner--queued"
          role="status"
        >
          <SemanticStatus label={t("Processing")} tone="info" />
          <span>
            {t(
              "The command is processing. Other Gate review commands remain disabled until the server response is validated.",
            )}
          </span>
        </div>
      ) : null}
      {confirmedMessage ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Server confirmed")} tone="success" />
          <span>{confirmedMessage}</span>
        </div>
      ) : null}
      {receiptNotice === "completed" ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Server confirmed")} tone="success" />
          <span>{t("The server confirmed the review workspace update.")}</span>
        </div>
      ) : null}
      {receiptNotice === "absent" ? (
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus
            label={t("Command record not found")}
            tone="warning"
          />
          <span>
            {t(
              "No completed command record was found yet. The workspace was reloaded; verify its current state and re-enter the command inputs before submitting again.",
            )}
          </span>
        </div>
      ) : null}
      {receiptNotice === "unresolved" ? (
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus
            label={t("Command result unconfirmed")}
            tone="warning"
          />
          <span>
            {t(
              "The command receipt could not be reconciled. The workspace was reloaded without claiming a command result; verify its current state before submitting another command.",
            )}
          </span>
        </div>
      ) : null}
      {commandFailure && commandFailureContent ? (
        <section
          aria-label={t("Gate review command failure")}
          className="command-failure"
          role="alert"
        >
          <SemanticStatus
            label={commandFailureContent.label}
            tone={
              commandFailure.failureKind === "conflict" ||
              commandFailure.failureKind === "retryable"
                ? "warning"
                : "danger"
            }
          />
          <p>{commandFailureContent.detail}</p>
          <RequestFailurePanel failure={commandFailure.failure} />
          <div className="detail-actions">
            {retryCommand ? (
              <Button
                disabled={!sessionCommandContext}
                onClick={() => {
                  executeCommand(retryCommand);
                }}
                visual="primary"
              >
                {t("Retry command")}
              </Button>
            ) : commandFailure.failureKind === "conflict" ? (
              <Button onClick={reload} visual="primary">
                {t("Reload Gate review")}
              </Button>
            ) : null}
            <Button
              onClick={() => {
                setCommandFailure(null);
                setRetryCommand(null);
              }}
              visual={
                retryCommand || commandFailure.failureKind === "conflict"
                  ? "secondary"
                  : "primary"
              }
            >
              {t("Dismiss command error")}
            </Button>
          </div>
        </section>
      ) : null}
      <ObjectHeader
        {...(primaryAction ? { primaryAction } : {})}
        code={`${gate.key} / ${project.businessCode}`}
        metadata={
          <span>
            {t("Project")}:{" "}
            <span data-language-exempt="business-data">{project.title}</span> ·{" "}
            {t("Gate version")}: {formatNumber(locale, gate.version, 0)} ·{" "}
            {t("Review cycle")}:{" "}
            {activeCycle
              ? formatNumber(locale, activeCycle.number, 0)
              : t("None")}{" "}
            · {t("Downstream guard")}:{" "}
            {gate.downstreamDecisionCurrent
              ? t("Current decision accepted")
              : t("Downstream use denied")}
          </span>
        }
        name={gate.title}
        source={source}
        status={
          <SemanticStatus
            label={gateReviewStateLabel(t, gate.reviewState)}
            tone={reviewStateTone(gate.reviewState)}
          />
        }
      />
      <MetricStrip
        metrics={[
          {
            label: t("Selected review steps"),
            value: formatNumber(
              locale,
              activeCycle?.selectedSteps.length ?? 0,
              0,
            ),
          },
          {
            label: t("Unfinished review steps"),
            value: formatNumber(
              locale,
              activeCycle?.selectedSteps.filter(
                (step) =>
                  step.state === "waiting" || step.state === "available",
              ).length ?? 0,
              0,
            ),
          },
          {
            label: t("Open Gate blockers"),
            value: formatNumber(locale, view.blockers.length, 0),
            tone: view.blockers.length ? "danger" : "neutral",
          },
          {
            label: t("Pending exceptions"),
            value: formatNumber(
              locale,
              activeCycle?.exceptions.filter(
                (exception) => exception.state === "pending",
              ).length ?? 0,
              0,
            ),
          },
          {
            label: t("Decision history"),
            value: formatNumber(locale, view.decisions.length, 0),
          },
        ]}
      />
      <SectionAnchors
        sections={[
          { id: "gate-review-inputs", label: t("Frozen review inputs") },
          { id: "gate-review-work", label: t("Review evidence and blockers") },
          { id: "gate-review-inspector", label: t("Review inspector") },
        ]}
      />
      <div className="review-layout gate-review-layout">
        <Panel
          id="gate-review-inputs"
          scrollableBody
          title={t("Frozen requirements and review sequence")}
        >
          <RequirementTable
            requirements={evidence.requirements}
            selectedRequirement={selectedRequirement}
            selectRequirement={selectRequirement}
          />
          <ReviewStepsTable cycle={activeCycle} />
        </Panel>
        <Panel
          id="gate-review-work"
          scrollableBody
          title={t("Review evidence and blockers")}
        >
          <section
            aria-labelledby="selected-requirement-heading"
            className="review-room-section"
          >
            <h3 id="selected-requirement-heading">
              {t("Selected frozen requirement")}
            </h3>
            <DefinitionList
              rows={[
                {
                  label: t("Requirement global ID"),
                  value: selectedRequirement.globalId,
                  exempt: "identifier",
                },
                {
                  label: t("Requirement key"),
                  value: selectedRequirement.key,
                  exempt: "identifier",
                },
                {
                  label: t("Requirement title"),
                  value: selectedRequirement.title,
                  exempt: "business-data",
                },
                {
                  label: t("Owner"),
                  value: (
                    <span data-language-exempt="business-data">
                      {selectedRequirement.owner.displayName} ·{" "}
                      {selectedRequirement.owner.userId}
                    </span>
                  ),
                },
                {
                  label: t("Due date"),
                  value: formatDate(locale, selectedRequirement.dueDate),
                },
                {
                  label: t("Allowed evidence kinds"),
                  value: formatList(
                    locale,
                    selectedRequirement.allowedEvidenceKinds.map((kind) =>
                      gateEvidenceKindLabel(t, kind),
                    ),
                  ),
                },
              ]}
            />
          </section>
          <section
            aria-labelledby="controlled-evidence-heading"
            className="review-room-section"
          >
            <h3 id="controlled-evidence-heading">{t("Controlled evidence")}</h3>
            <EvidenceTable
              evidence={selectedRequirement.evidence}
              selectedEvidence={selectedEvidence}
              selectEvidence={(reference) => {
                setSelectedEvidenceId(reference.globalId);
              }}
            />
            <SelectedEvidenceDetail selectedEvidence={selectedEvidence} />
          </section>
          <section
            aria-labelledby="gate-blockers-heading"
            className="review-room-section"
          >
            <h3 id="gate-blockers-heading">{t("Current Gate blockers")}</h3>
            {view.blockers.length ? (
              <table
                aria-label={t("Current Gate blockers")}
                className="data-table data-table--compact gate-blockers-table"
              >
                <thead>
                  <tr>
                    <th>{t("Kind")}</th>
                    <th>{t("Title")}</th>
                    <th>{t("State")}</th>
                    <th>{t("Owner")}</th>
                    <th>{t("Due")}</th>
                  </tr>
                </thead>
                <tbody>
                  {view.blockers.map((blocker) => (
                    <tr key={blocker.globalId}>
                      <td>{domainWorkItemKindLabel(t, blocker.kind)}</td>
                      <td data-language-exempt="business-data">
                        {blocker.title}
                      </td>
                      <td>
                        {governedPolicyLabel(t, blocker.stateLabelSource)}
                      </td>
                      <td data-language-exempt="business-data">
                        {blocker.owner}
                      </td>
                      <td>{formatDateTime(locale, blocker.dueAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="empty-inline">
                {t("No current same-Gate blocking work items were returned.")}
              </p>
            )}
          </section>
          <section
            aria-labelledby="gate-input-history-heading"
            className="review-room-section"
          >
            <h3 id="gate-input-history-heading">
              {t("Input version and prior decisions")}
            </h3>
            {activeCycle ? (
              <DefinitionList
                rows={[
                  {
                    label: t("Current frozen input hash"),
                    value: activeCycle.inputHash,
                    exempt: "identifier",
                  },
                  {
                    label: t("Cycle trigger"),
                    value: gateReviewCycleTriggerLabel(t, activeCycle.trigger),
                  },
                  {
                    label: t("Cycle state"),
                    value: (
                      <SemanticStatus
                        label={gateReviewCycleStateLabel(t, activeCycle.state)}
                        tone={cycleStateTone(activeCycle.state)}
                      />
                    ),
                  },
                ]}
              />
            ) : null}
            <h4>{t("Gate input snapshot change events")}</h4>
            {view.dependencyChanges.length ? (
              <ol
                aria-label={t("Gate input snapshot change events")}
                className="gate-dependency-history"
              >
                {view.dependencyChanges.map((change) => (
                  <li
                    className="gate-dependency-history__item"
                    key={change.eventGlobalId}
                  >
                    <SemanticStatus
                      label={t("Gate input snapshot changed")}
                      tone="warning"
                    />
                    <DefinitionList
                      rows={[
                        {
                          label: t("Event outcome"),
                          value: gateReviewDependencyEventTypeLabel(
                            t,
                            change.eventType,
                          ),
                        },
                        {
                          label: t("Event global ID"),
                          value: change.eventGlobalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Old input hash"),
                          value: change.oldInputHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("New input hash"),
                          value: change.newInputHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("Prior cycle global ID"),
                          value: change.priorCycleGlobalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Successor cycle global ID"),
                          value: change.successorCycleGlobalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Prior decision global ID"),
                          value: change.priorDecisionGlobalId ?? t("None"),
                          ...(change.priorDecisionGlobalId
                            ? { exempt: "identifier" as const }
                            : {}),
                        },
                        {
                          label: t("Prior decision lineage hash"),
                          value: change.priorDecisionLineageHash ?? t("None"),
                          ...(change.priorDecisionLineageHash
                            ? { exempt: "identifier" as const }
                            : {}),
                        },
                        {
                          label: t("Recorded actor"),
                          value: change.actorUserId,
                          exempt: "business-data",
                        },
                        {
                          label: t("Initiated by"),
                          value: change.initiatedByUserId ?? t("System"),
                          ...(change.initiatedByUserId
                            ? { exempt: "business-data" as const }
                            : {}),
                        },
                        {
                          label: t("Occurred"),
                          value: formatDateTime(locale, change.occurredAt),
                        },
                        {
                          label: t("Recorded reason"),
                          value: (
                            <span className="controlled-code-value">
                              <span>
                                {gateReviewDependencyReasonLabel(
                                  t,
                                  change.reason,
                                )}
                              </span>
                              <code data-language-exempt="identifier">
                                {change.reason}
                              </code>
                            </span>
                          ),
                        },
                      ]}
                    />
                    <p className="context-help">
                      {t(
                        "This event proves an exact Gate input snapshot hash change. It does not claim which source-object fields changed.",
                      )}
                    </p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-inline">
                {t("No Gate input snapshot change event is recorded.")}
              </p>
            )}
            {view.decisions.length ? (
              <ol
                aria-label={t("Immutable Gate decision history")}
                className="gate-decision-history"
              >
                {view.decisions.map((decision) => (
                  <li
                    className="gate-decision-history__item"
                    key={decision.globalId}
                  >
                    <SemanticStatus
                      label={gateDecisionOutcomeLabel(t, decision.outcome)}
                      tone={decision.current ? "success" : "neutral"}
                    />
                    <DefinitionList
                      rows={[
                        {
                          label: t("Decision global ID"),
                          value: decision.globalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Cycle global ID"),
                          value: decision.cycleGlobalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Prior decision lineage hash"),
                          value: decision.detail.lineageHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("Review Cycle Number"),
                          value: formatNumber(
                            locale,
                            decision.detail.cycleNumber,
                            0,
                          ),
                        },
                        {
                          label: t("Cycle version"),
                          value: formatNumber(
                            locale,
                            decision.detail.cycleVersion,
                            0,
                          ),
                        },
                        {
                          label: t("Policy global ID"),
                          value: decision.detail.policyRef.globalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Policy version"),
                          value: formatNumber(
                            locale,
                            decision.detail.policyRef.version,
                            0,
                          ),
                        },
                        {
                          label: t("Policy snapshot hash"),
                          value: decision.detail.policyRef.snapshotHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("Snapshot hash"),
                          value: decision.snapshotHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("Input hash"),
                          value: decision.inputHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("Gate Global ID"),
                          value: decision.detail.inputSnapshot.gateGlobalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Project Global ID"),
                          value: decision.detail.inputSnapshot.projectGlobalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Tenant ID"),
                          value: decision.detail.inputSnapshot.tenantId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Review Input Version"),
                          value: formatNumber(
                            locale,
                            decision.detail.inputSnapshot.gateVersion,
                            0,
                          ),
                        },
                        {
                          label: t("Frozen Gate requirements"),
                          value: formatNumber(
                            locale,
                            decision.detail.inputSnapshot.requirements.length,
                            0,
                          ),
                        },
                        {
                          label: t("Evidence References"),
                          value: formatNumber(
                            locale,
                            decision.detail.inputSnapshot.evidence.length,
                            0,
                          ),
                        },
                        {
                          label: t("Blocker"),
                          value: formatNumber(
                            locale,
                            decision.detail.inputSnapshot.blockers.length,
                            0,
                          ),
                        },
                        {
                          label: t("Dependency change"),
                          value: formatNumber(
                            locale,
                            decision.detail.inputSnapshot.dependencies.length,
                            0,
                          ),
                        },
                        {
                          label: t("Review Record Hashes"),
                          value: decision.detail.reviewHashes.length ? (
                            <ul className="compact-value-list">
                              {decision.detail.reviewHashes.map((hash) => (
                                <li
                                  data-language-exempt="identifier"
                                  key={hash}
                                >
                                  {hash}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            t("None")
                          ),
                        },
                        {
                          label: t("Review Exception Hashes"),
                          value: decision.detail.exceptionHashes.length ? (
                            <ul className="compact-value-list">
                              {decision.detail.exceptionHashes.map((hash) => (
                                <li
                                  data-language-exempt="identifier"
                                  key={hash}
                                >
                                  {hash}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            t("None")
                          ),
                        },
                        {
                          label: t("Decided"),
                          value: formatDateTime(locale, decision.decidedAt),
                        },
                        {
                          label: t("Decided by"),
                          value: decision.decidedBy,
                          exempt: "business-data",
                        },
                        {
                          label: t("Downstream current"),
                          value: decision.current ? t("Yes") : t("No"),
                        },
                      ]}
                    />
                    <DecisionInputTables decision={decision} />
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-inline">
                {t("No immutable Gate decision has been recorded.")}
              </p>
            )}
          </section>
        </Panel>
        <DockedInspector
          id="gate-review-inspector"
          title={t("Review inspector")}
        >
          <DefinitionList
            rows={[
              {
                label: t("Review state"),
                value: gateReviewStateLabel(t, gate.reviewState),
              },
              {
                label: t("Cycle state"),
                value: activeCycle
                  ? gateReviewCycleStateLabel(t, activeCycle.state)
                  : t("No active cycle"),
              },
              {
                label: t("Cycle version"),
                value: activeCycle
                  ? formatNumber(locale, activeCycle.version, 0)
                  : t("Not applicable"),
              },
              {
                label: t("Policy version"),
                value: activeCycle
                  ? formatNumber(locale, activeCycle.policyRef.version, 0)
                  : t("Not applicable"),
              },
              {
                label: t("Downstream guard"),
                value: gate.downstreamDecisionCurrent
                  ? t("Current decision accepted")
                  : t("Downstream use denied"),
              },
              {
                label: t("Current server action"),
                value: selectedAction
                  ? actionLabel(t, selectedAction)
                  : t("No permitted review action"),
              },
            ]}
          />
          {view.decisionReadiness.blockedReasons.length ? (
            <section
              aria-labelledby="gate-decision-readiness-heading"
              className="review-room-section"
            >
              <h3 id="gate-decision-readiness-heading">
                {t("Gate decision readiness")}
              </h3>
              <ul className="compact-value-list">
                {view.decisionReadiness.blockedReasons.map((reason) => (
                  <li key={reason.outcome}>
                    <SemanticStatus
                      label={gateDecisionOutcomeLabel(t, reason.outcome)}
                      tone="warning"
                    />{" "}
                    <span>
                      {gateReviewDecisionBlockedReasonLabel(t, reason.code)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {actions.length > 1 ? (
            <label className="field-control">
              <span>{t("Review action")}</span>
              <Select
                aria-label={t("Review action")}
                disabled={Boolean(processingLabel)}
                onChange={(event) => {
                  setSelectedActionKey(event.currentTarget.value);
                  setCommandFailure(null);
                }}
                value={selectedAction?.key ?? ""}
              >
                {actions.map((action) => (
                  <option
                    aria-label={actionAccessibleLabel(t, action)}
                    data-language-exempt-tokens={actionIdentifierTokens(action)}
                    key={action.key}
                    value={action.key}
                  >
                    {actionAccessibleLabel(t, action)}
                  </option>
                ))}
              </Select>
            </label>
          ) : null}
          {selectedAction?.kind === "start" ? (
            <section className="review-action-form">
              <h3>{t("Review policy and authority bindings")}</h3>
              {selectedAction.acknowledgeInputChange ? (
                <div className="inspector-note">
                  <SemanticStatus
                    label={t("Gate input snapshot changed")}
                    tone="warning"
                  />
                  <p>
                    {t(
                      "Starting review acknowledges the recorded input snapshot change. Prior approvals remain immutable and are not copied.",
                    )}
                  </p>
                </div>
              ) : null}
              {selectedAction.acknowledgeInputChange && activeCycle ? (
                <>
                  <DefinitionList
                    rows={[
                      {
                        label: t("Policy global ID"),
                        value: activeCycle.policyRef.globalId,
                        exempt: "identifier",
                      },
                      {
                        label: t("Policy version"),
                        value: formatNumber(
                          locale,
                          activeCycle.policyRef.version,
                          0,
                        ),
                      },
                      {
                        label: t("Policy snapshot hash"),
                        value: activeCycle.policyRef.snapshotHash,
                        exempt: "identifier",
                      },
                    ]}
                  />
                  <ul
                    aria-label={t("Authority assignment")}
                    className="compact-value-list"
                  >
                    {activeCycle.bindings.map((binding) => (
                      <li key={binding.slot}>
                        <span data-language-exempt="identifier">
                          {binding.slot}
                        </span>{" "}
                        ·{" "}
                        <span data-language-exempt="business-data">
                          {binding.displayName} · {binding.userId}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <>
                  {selectablePolicies.length ? (
                    <label className="field-control">
                      <span>{t("Published review policy")}</span>
                      <Select
                        aria-label={t("Published review policy")}
                        data-language-exempt="identifier"
                        disabled={Boolean(processingLabel)}
                        onChange={(event) => {
                          setSelectedPolicyKey(event.currentTarget.value);
                        }}
                        value={effectiveSelectedPolicyKey}
                      >
                        {selectablePolicies.map((policy) => {
                          const key = `${policy.policyRef.globalId}:${String(policy.policyRef.version)}:${policy.policyRef.snapshotHash}`;
                          return (
                            <option
                              data-language-exempt="identifier"
                              key={key}
                              value={key}
                            >
                              {policy.policyRef.globalId}@
                              {policy.policyRef.version}
                            </option>
                          );
                        })}
                      </Select>
                    </label>
                  ) : (
                    <p className="empty-inline">
                      {t("No applicable published review policy is available.")}
                    </p>
                  )}
                  {selectedPolicy?.authoritySlots.map((authority) => (
                    <label className="field-control" key={authority.slot}>
                      <span>
                        {gateReviewAuthorityPurposeLabel(t, authority.purpose)}{" "}
                        ·{" "}
                        <span data-language-exempt="identifier">
                          {authority.slot}
                        </span>
                      </span>
                      <Select
                        aria-label={t("Authority assignment")}
                        disabled={Boolean(processingLabel)}
                        onChange={(event) => {
                          const memberGlobalId = event.currentTarget.value;
                          setBindingSelections((current) => ({
                            ...current,
                            [authority.slot]: memberGlobalId,
                          }));
                        }}
                        value={effectiveBindingSelections[authority.slot] ?? ""}
                      >
                        {view.eligibleMembers.map((member) => (
                          <option
                            data-language-exempt="business-data"
                            key={member.memberGlobalId}
                            value={member.memberGlobalId}
                          >
                            {member.displayName} · {member.userId}
                          </option>
                        ))}
                      </Select>
                    </label>
                  ))}
                  {!view.eligibleMembers.length ? (
                    <p className="empty-inline">
                      {t(
                        "No enabled internal Project member is available for authority binding.",
                      )}
                    </p>
                  ) : null}
                </>
              )}
            </section>
          ) : null}
          {selectedAction?.kind === "review" ? (
            <section className="review-action-form">
              <h3>{t("Assigned review opinion")}</h3>
              <DefinitionList
                rows={[
                  {
                    label: t("Step"),
                    value: selectedAction.step.stepKey,
                    exempt: "identifier",
                  },
                  {
                    label: t("Authority slot"),
                    value: selectedAction.step.slot,
                    exempt: "identifier",
                  },
                  {
                    label: t("Assigned member"),
                    value: selectedAction.step.assignedMember.displayName,
                    exempt: "business-data",
                  },
                ]}
              />
              <label className="field-control">
                <span>{t("Review outcome")}</span>
                <Select
                  aria-label={t("Review outcome")}
                  disabled={Boolean(processingLabel)}
                  onChange={(event) => {
                    setReviewOutcome(
                      event.currentTarget.value as GateReviewOutcome,
                    );
                  }}
                  value={reviewOutcome}
                >
                  <option value="approved">
                    {gateReviewOutcomeLabel(t, "approved")}
                  </option>
                  <option value="rejected">
                    {gateReviewOutcomeLabel(t, "rejected")}
                  </option>
                </Select>
              </label>
              <label className="field-control">
                <span>{t("Complete review opinion")}</span>
                <textarea
                  aria-label={t("Complete review opinion")}
                  disabled={Boolean(processingLabel)}
                  maxLength={4000}
                  onChange={(event) => {
                    setReviewOpinion(event.currentTarget.value);
                  }}
                  required
                  rows={4}
                  value={reviewOpinion}
                />
              </label>
            </section>
          ) : null}
          {selectedAction?.kind === "request_exception" ? (
            <section className="review-action-form">
              <h3>{t("Controlled exception request")}</h3>
              <DefinitionList
                rows={[
                  {
                    label: t("Requirement"),
                    value: selectedAction.option.requirementKey,
                    exempt: "identifier",
                  },
                  {
                    label: t("Exception kind"),
                    value: selectedAction.option.kind,
                    exempt: "identifier",
                  },
                  {
                    label: t("Maximum validity"),
                    value: formatNumber(
                      locale,
                      selectedAction.option.maximumValidityDays,
                      0,
                    ),
                  },
                ]}
              />
              <label className="field-control">
                <span>{t("Risk if accepted")}</span>
                <textarea
                  aria-label={t("Risk if accepted")}
                  disabled={Boolean(processingLabel)}
                  maxLength={4000}
                  onChange={(event) => {
                    setExceptionRisk(event.currentTarget.value);
                  }}
                  required
                  rows={3}
                  value={exceptionRisk}
                />
              </label>
              <label className="field-control">
                <span>{t("Exception expiry date")}</span>
                <TextInput
                  aria-label={t("Exception expiry date")}
                  disabled={Boolean(processingLabel)}
                  onChange={(event) => {
                    setExceptionExpiryDate(event.currentTarget.value);
                  }}
                  required
                  type="date"
                  value={exceptionExpiryDate}
                />
              </label>
              <label className="field-control">
                <span>{t("Required closure action")}</span>
                <Select
                  aria-label={t("Required closure action")}
                  disabled={Boolean(processingLabel)}
                  onChange={(event) => {
                    setSelectedClosureActionId(event.currentTarget.value);
                  }}
                  value={effectiveClosureActionId}
                >
                  {allowedClosureActions.map((closureAction) => (
                    <option
                      data-language-exempt="business-data"
                      key={closureAction.globalId}
                      value={closureAction.globalId}
                    >
                      {closureAction.title}
                    </option>
                  ))}
                </Select>
              </label>
              {selectedClosureAction ? (
                <DefinitionList
                  rows={[
                    {
                      label: t("Closure action state"),
                      value: governedPolicyLabel(
                        t,
                        selectedClosureAction.stateLabelSource,
                      ),
                    },
                  ]}
                />
              ) : null}
              {!allowedClosureActions.length ? (
                <p className="empty-inline">
                  {t(
                    "No eligible same-Project closure action is available for this exception.",
                  )}
                </p>
              ) : null}
            </section>
          ) : null}
          {selectedAction?.kind === "decide_exception" ? (
            <section className="review-action-form">
              <h3>{t("Pending exception decision")}</h3>
              <DefinitionList
                rows={[
                  {
                    label: t("Exception global ID"),
                    value: selectedAction.exception.globalId,
                    exempt: "identifier",
                  },
                  {
                    label: t("Requirement"),
                    value: selectedAction.exception.requirementKey,
                    exempt: "identifier",
                  },
                  {
                    label: t("Request reason"),
                    value: selectedAction.exception.reason,
                    exempt: "business-data",
                  },
                  {
                    label: t("Request risk"),
                    value: selectedAction.exception.risk,
                    exempt: "business-data",
                  },
                ]}
              />
              <label className="field-control">
                <span>{t("Exception decision")}</span>
                <Select
                  aria-label={t("Exception decision")}
                  disabled={Boolean(processingLabel)}
                  onChange={(event) => {
                    setExceptionDecisionOutcome(
                      event.currentTarget.value as GateReviewOutcome,
                    );
                  }}
                  value={effectiveExceptionDecisionOutcome}
                >
                  {selectedAction.exception.allowedOutcomes.map((outcome) => (
                    <option key={outcome} value={outcome}>
                      {gateReviewOutcomeLabel(t, outcome)}
                    </option>
                  ))}
                </Select>
              </label>
            </section>
          ) : null}
          {selectedAction?.kind === "decide_gate" ? (
            <section className="review-action-form">
              <h3>{t("Gate decision outcome")}</h3>
              <label className="field-control">
                <span>{t("Decision outcome")}</span>
                <Select
                  aria-label={t("Decision outcome")}
                  disabled={Boolean(processingLabel)}
                  onChange={(event) => {
                    setGateDecisionOutcome(
                      event.currentTarget.value as GateDecisionOutcome,
                    );
                  }}
                  value={effectiveGateDecisionOutcome}
                >
                  {view.decisionReadiness.allowedOutcomes.map((outcome) => (
                    <option key={outcome} value={outcome}>
                      {gateDecisionOutcomeLabel(t, outcome)}
                    </option>
                  ))}
                </Select>
              </label>
              <p className="context-help">
                {t(
                  "Decision readiness is determined again by the server. This page cannot override reviews, evidence safety, blockers, exceptions, or input drift.",
                )}
              </p>
            </section>
          ) : null}
          {selectedAction?.kind === "reopen" && activeCycle ? (
            <section className="review-action-form">
              <h3>{t("Reopen with preserved authority bindings")}</h3>
              <ul className="compact-value-list">
                {activeCycle.bindings.map((binding) => (
                  <li key={binding.slot}>
                    <span data-language-exempt="identifier">
                      {binding.slot}
                    </span>{" "}
                    ·{" "}
                    <span data-language-exempt="business-data">
                      {binding.displayName}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="context-help">
                {t(
                  "The server will preserve the prior immutable decision and start a new cycle from current frozen inputs.",
                )}
              </p>
            </section>
          ) : null}
          {!selectedAction ? (
            <div className="inspector-note">
              <SemanticStatus
                label={t("No permitted review action")}
                tone="neutral"
              />
              <p>
                {gate.reviewState === "requires_review" &&
                !frozenBindingsAreEligible
                  ? t(
                      "A frozen authority binding is no longer eligible. The recorded policy and bindings cannot be substituted in this review cycle.",
                    )
                  : t(
                      "The server returned view access without an applicable review command for this actor and state.",
                    )}
              </p>
            </div>
          ) : null}
          <section className="review-room-section">
            <h3>{t("Exceptions")}</h3>
            {activeCycle?.exceptions.length ? (
              <ol
                aria-label={t("Gate review exceptions")}
                className="gate-exception-list"
              >
                {activeCycle.exceptions.map((exception) => (
                  <li
                    className="gate-exception-list__item"
                    key={exception.globalId}
                  >
                    <SemanticStatus
                      label={gateReviewExceptionStateLabel(t, exception.state)}
                      tone={
                        exception.state === "approved"
                          ? "success"
                          : exception.state === "rejected"
                            ? "danger"
                            : "warning"
                      }
                    />
                    <span data-language-exempt="identifier">
                      {exception.requirementKey} · {exception.kind}
                    </span>
                    <time dateTime={exception.expiresAt}>
                      {formatDateTime(locale, exception.expiresAt)}
                    </time>
                    <DefinitionList
                      rows={[
                        {
                          label: t("Exception global ID"),
                          value: exception.globalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Exception Reason"),
                          value: exception.reason,
                          exempt: "business-data",
                        },
                        {
                          label: t("Exception Risk"),
                          value: exception.risk,
                          exempt: "business-data",
                        },
                        {
                          label: t("Requester User"),
                          value: (
                            <span data-language-exempt="business-data">
                              {exception.requester.displayName} ·{" "}
                              {exception.requester.userId}
                            </span>
                          ),
                        },
                        {
                          label: t("Requested At"),
                          value: formatDateTime(locale, exception.requestedAt),
                        },
                        {
                          label: t("Expires At"),
                          value: formatDateTime(locale, exception.expiresAt),
                        },
                        {
                          label: t("Exception validity"),
                          value:
                            exception.state === "approved"
                              ? t("Approved through recorded expiry")
                              : exception.state === "pending"
                                ? t("Pending approval")
                                : t("Not valid"),
                        },
                        {
                          label: t("Exception Request Snapshot Hash"),
                          value: exception.requestSnapshotHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("Version"),
                          value: formatNumber(
                            locale,
                            exception.requestSchemaVersion,
                            0,
                          ),
                        },
                        {
                          label: t("Closure Action Global ID"),
                          value: exception.closureActionRef.globalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Exact revision"),
                          value:
                            exception.closureActionRef.version === null
                              ? "—"
                              : formatNumber(
                                  locale,
                                  exception.closureActionRef.version,
                                  0,
                                ),
                        },
                        {
                          label: t("Object hash"),
                          value: exception.closureActionRef.snapshotHash ?? "—",
                          exempt: "identifier",
                        },
                        ...(exception.decision
                          ? [
                              {
                                label: t("Decision outcome"),
                                value: gateReviewOutcomeLabel(
                                  t,
                                  exception.decision.outcome,
                                ),
                              },
                              {
                                label: t("Approver User"),
                                value: (
                                  <span data-language-exempt="business-data">
                                    {exception.decision.approver.displayName} ·{" "}
                                    {exception.decision.approver.userId}
                                  </span>
                                ),
                              },
                              {
                                label: t("Decision opinion"),
                                value: exception.decision.opinion,
                                exempt: "business-data" as const,
                              },
                              {
                                label: t("Decided At"),
                                value: formatDateTime(
                                  locale,
                                  exception.decision.decidedAt,
                                ),
                              },
                              {
                                label: t("Exception Decision Snapshot Hash"),
                                value: exception.decision.snapshotHash,
                                exempt: "identifier" as const,
                              },
                            ]
                          : []),
                      ]}
                    />
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-inline">
                {t("No controlled exceptions are recorded in this cycle.")}
              </p>
            )}
          </section>
          <section className="review-room-section">
            <h3>{t("Cycle and immutable history")}</h3>
            {activeCycle ? (
              <DefinitionList
                rows={[
                  {
                    label: t("Cycle global ID"),
                    value: activeCycle.globalId,
                    exempt: "identifier",
                  },
                  {
                    label: t("Policy global ID"),
                    value: activeCycle.policyRef.globalId,
                    exempt: "identifier",
                  },
                  {
                    label: t("Policy snapshot hash"),
                    value: activeCycle.policyRef.snapshotHash,
                    exempt: "identifier",
                  },
                  {
                    label: t("Started"),
                    value: formatDateTime(locale, activeCycle.startedAt),
                  },
                  {
                    label: t("Started by"),
                    value: activeCycle.startedBy,
                    exempt: "business-data",
                  },
                  {
                    label: t("Latest decision hash"),
                    value: gate.latestDecisionHash ?? t("None"),
                    ...(gate.latestDecisionHash
                      ? { exempt: "identifier" as const }
                      : {}),
                  },
                ]}
              />
            ) : (
              <p className="empty-inline">
                {t("Cycle history is unavailable until review starts.")}
              </p>
            )}
          </section>
        </DockedInspector>
      </div>
      {impactAction ? (
        <ImpactReview
          confirmLabel={actionLabel(t, impactAction)}
          details={impactDetails(t, impactAction, view)}
          onCancel={() => {
            setImpactAction(null);
          }}
          onConfirm={(reason) => {
            const prepared = prepareCommand(impactAction, reason);
            setImpactAction(null);
            if (prepared) executeCommand(prepared);
          }}
          reasonRequired={impactAction.kind !== "decide_gate"}
          title={
            impactAction.kind === "request_exception"
              ? t("Review controlled exception request")
              : impactAction.kind === "decide_exception"
                ? t("Review exception decision")
                : impactAction.kind === "decide_gate"
                  ? t("Review immutable Gate decision")
                  : t("Review Gate reopen")
          }
        />
      ) : null}
    </article>
  );
}

export default function GateEvidencePage({
  dataSource,
  gateGlobalId,
  navigate,
  projectGlobalId,
}: {
  dataSource: GateReviewDataSource;
  gateGlobalId: string;
  navigate: (target: string) => void;
  projectGlobalId: string;
}): React.JSX.Element {
  const { sessionCommandContext } = useI18n();
  const sessionActorUserId = sessionCommandContext?.userId;
  const [receiptRecovery, setReceiptRecovery] =
    useState<GateReviewReceiptRecoveryState>(initialReceiptRecoveryState);
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const [state, setState] = useState<GateReviewLoadState>({
    gateGlobalId,
    kind: "loading",
    projectGlobalId,
  });
  const retry = useCallback((): void => {
    generation.current += 1;
    setState({ gateGlobalId, kind: "loading", projectGlobalId });
    setAttempt((current) => current + 1);
  }, [gateGlobalId, projectGlobalId]);
  const retryReceiptRecovery = useCallback((): void => {
    setReceiptRecovery((current) =>
      current.kind === "failed"
        ? {
            epoch: current.epoch + 1,
            kind: "pending",
            marker: current.marker,
          }
        : current,
    );
  }, []);
  const recoverPersistedReceipt = useCallback((): void => {
    const marker = readReceiptMarker();
    if (!marker) return;
    setReceiptRecovery((current) =>
      current.kind === "ready"
        ? {
            epoch: 0,
            kind: "pending",
            marker,
          }
        : current,
    );
  }, []);

  useEffect(() => {
    if (receiptRecovery.kind !== "pending" || !sessionActorUserId) {
      return;
    }
    const marker = receiptRecovery.marker;
    if (marker.actor.toLowerCase() !== sessionActorUserId.toLowerCase()) {
      const rotationTimer = globalThis.setTimeout(() => {
        setReceiptRecovery({ kind: "ready", notice: null });
      }, 0);
      return () => {
        globalThis.clearTimeout(rotationTimer);
      };
    }
    const controller = new AbortController();
    const markerMatchesCurrentRoute =
      marker.project === projectGlobalId && marker.gate === gateGlobalId;
    const reconcile = async (): Promise<void> => {
      try {
        let status: "completed" | "absent" = "absent";
        const retryDelays = [150, 350, 750] as const;
        for (
          let attemptIndex = 0;
          attemptIndex <= retryDelays.length;
          attemptIndex += 1
        ) {
          const receipt = await dataSource.reconcileCommandReceipt(
            marker.project,
            marker.gate,
            marker.operation,
            {
              idempotencyKey: marker.key,
              signal: controller.signal,
            },
          );
          status = receipt.status;
          if (status === "completed" || attemptIndex === retryDelays.length) {
            break;
          }
          await waitForReceiptRetry(
            retryDelays[attemptIndex] ?? 0,
            controller.signal,
          );
        }
        if (controller.signal.aborted) return;
        clearReceiptMarker(marker);
        generation.current += 1;
        setState({ gateGlobalId, kind: "loading", projectGlobalId });
        setAttempt((current) => current + 1);
        setReceiptRecovery({
          kind: "ready",
          notice: markerMatchesCurrentRoute ? status : null,
        });
      } catch (error) {
        if (
          controller.signal.aborted ||
          error instanceof GateReviewRequestCancelledError
        ) {
          return;
        }
        const failure = toRequestFailure(error);
        const failureKind = classifyFailure(failure);
        if (failureKind !== "retryable" && failureKind !== "conflict") {
          clearReceiptMarker(marker);
          generation.current += 1;
          setState({ gateGlobalId, kind: "loading", projectGlobalId });
          setAttempt((current) => current + 1);
          setReceiptRecovery({
            kind: "ready",
            notice: markerMatchesCurrentRoute ? "unresolved" : null,
          });
          return;
        }
        setReceiptRecovery({
          epoch: receiptRecovery.epoch,
          failure,
          failureKind,
          kind: "failed",
          marker,
        });
      }
    };
    // The production root uses React StrictMode. Defer the first lookup until
    // the effect setup is committed so StrictMode's probe cleanup can cancel
    // it before any transport call is issued.
    const startTimer = globalThis.setTimeout(() => {
      if (!controller.signal.aborted) {
        void reconcile();
      }
    }, 0);
    return () => {
      globalThis.clearTimeout(startTimer);
      controller.abort();
    };
  }, [
    dataSource,
    gateGlobalId,
    projectGlobalId,
    receiptRecovery,
    sessionActorUserId,
  ]);

  useEffect(() => {
    const handleRefresh = (): void => {
      retry();
    };
    globalThis.addEventListener("npi:refresh-gate-evidence", handleRefresh);
    return () => {
      globalThis.removeEventListener(
        "npi:refresh-gate-evidence",
        handleRefresh,
      );
    };
  }, [retry]);

  useEffect(() => {
    if (receiptRecovery.kind !== "ready") return;
    const controller = new AbortController();
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    dataSource
      .load(projectGlobalId, gateGlobalId, controller.signal)
      .then((review) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration
        ) {
          return;
        }
        setState({
          gateGlobalId,
          kind: "loaded",
          projectGlobalId,
          review,
        });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration ||
          error instanceof GateReviewRequestCancelledError
        ) {
          return;
        }
        const failure = toRequestFailure(error);
        setState({
          failure,
          failureKind: classifyFailure(failure),
          gateGlobalId,
          kind: "failed",
          projectGlobalId,
        });
      });
    return () => {
      controller.abort();
    };
  }, [
    attempt,
    dataSource,
    gateGlobalId,
    projectGlobalId,
    receiptRecovery.kind,
  ]);

  if (receiptRecovery.kind === "pending") {
    return <GateReviewLoadingSurface />;
  }
  if (receiptRecovery.kind === "failed") {
    return (
      <GateReviewFailureSurface
        failure={receiptRecovery.failure}
        failureKind={receiptRecovery.failureKind}
        navigate={navigate}
        projectGlobalId={projectGlobalId}
        retry={retryReceiptRecovery}
      />
    );
  }

  if (
    state.projectGlobalId !== projectGlobalId ||
    state.gateGlobalId !== gateGlobalId ||
    state.kind === "loading"
  ) {
    return <GateReviewLoadingSurface />;
  }
  if (state.kind === "failed") {
    return (
      <GateReviewFailureSurface
        failure={state.failure}
        failureKind={state.failureKind}
        navigate={navigate}
        projectGlobalId={projectGlobalId}
        retry={retry}
      />
    );
  }
  return (
    <GateReviewWorkspace
      dataSource={dataSource}
      key={`${state.review.gate.globalId}:${state.review.activeCycle?.globalId ?? "none"}`}
      onReceiptRecoveryRequired={recoverPersistedReceipt}
      onTerminalFailure={(failure, failureKind) => {
        setState({
          failure,
          failureKind,
          gateGlobalId,
          kind: "failed",
          projectGlobalId,
        });
      }}
      receiptNotice={receiptRecovery.notice}
      reload={retry}
      replaceReview={(review) => {
        setState({
          gateGlobalId,
          kind: "loaded",
          projectGlobalId,
          review,
        });
      }}
      view={state.review}
    />
  );
}
